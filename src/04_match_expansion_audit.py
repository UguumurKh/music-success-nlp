"""Candidate-only lexical expansion; existing exact candidates are read-only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

import polars as pl
from music_success_nlp.normalization import normalize_text

ROOT = Path(__file__).resolve().parents[1]
PAIRS = ["billboard_spotify", "grammy_spotify", "billboard_grammy"]
OUTPUTS = [f"data/interim/{p}_variant_candidates.parquet" for p in PAIRS] + [
    f"reports/{p}_variant_review.csv" for p in PAIRS] + [
    "reports/billboard_unmatched_diagnosis.csv", "reports/grammy_unmatched_diagnosis.csv",
    "reports/variant_collision_review.csv", "reports/match_expansion_audit.md", "reports/match_expansion_audit.json"]
TIERS = {1: ("original_title_key", "primary_artist_norm"),
         2: ("title_base_norm", "original_artist_key"),
         3: ("title_base_norm", "primary_artist_norm")}
FEATURE = re.compile(r"\s+(?:featuring|feat\.?|ft\.?)\s+", re.IGNORECASE)
VERSION = re.compile(r"\b(?:remix|remaster(?:ed)?|radio\s+edit|edit|live|acoustic|instrumental|mono|stereo|soundtrack|version)\b", re.IGNORECASE)
REASONS = ["exact_title_exists_artist_differs", "exact_artist_exists_title_differs",
           "title_and_artist_exist_separately", "neither_exact_title_nor_artist_exists", "unusable_or_blank_key"]


def primary_artist_norm(value):
    if value is None:
        return None
    match = FEATURE.search(value)
    return normalize_text(value[:match.start()] if match else value)


def title_base_norm(value):
    """Strip only terminal delimited descriptions containing a version keyword.

    Repeat for stacked suffixes. Hyphens require surrounding spaces, protecting
    hyphenated title words. Balanced nested brackets/parentheses are supported.
    '(Single)' is not a version keyword and is deliberately not removed here.
    """
    if value is None:
        return None
    text = value.strip()
    while text:
        cut = None
        if text[-1:] in (")", "]"):
            opening = "(" if text[-1] == ")" else "["
            closing, depth = text[-1], 0
            for i in range(len(text) - 1, -1, -1):
                if text[i] == closing:
                    depth += 1
                elif text[i] == opening:
                    depth -= 1
                    if depth == 0:
                        if VERSION.search(text[i + 1:-1]):
                            cut = i
                        break
        if cut is None:
            # Last separator only: never remove through a meaningful trailing suffix.
            separators = list(re.finditer(r"\s+-\s+", text))
            if separators and VERSION.search(text[separators[-1].end():]):
                cut = separators[-1].start()
        if cut is None:
            break
        text = text[:cut].rstrip()
    return normalize_text(text)


def variants(frame, raw_title, raw_artist, title_key, artist_key):
    result = frame.with_columns(pl.col(raw_title).alias("raw_title"), pl.col(raw_artist).alias("raw_artist"),
        pl.col(title_key).alias("original_title_key"), pl.col(artist_key).alias("original_artist_key"),
        pl.col(raw_title).map_elements(title_base_norm, return_dtype=pl.String).alias("title_base_norm"),
        pl.col(raw_artist).map_elements(primary_artist_norm, return_dtype=pl.String).alias("primary_artist_norm"))
    assert result.select(frame.columns).equals(frame)
    return result


def usable(frame, keys):
    return frame.filter(pl.all_horizontal([pl.col(k).is_not_null() & (pl.col(k).str.strip_chars() != "") for k in keys]))


def unmatched(source, exact_pairs, prefix):
    matched = exact_pairs.select(pl.col(f"{prefix}_source_row").alias("source_row")).unique()
    return source.join(matched, on="source_row", how="anti").sort("source_row")


def generate_candidates(left, right, left_prefix, right_prefix):
    frames = []
    for tier, keys in TIERS.items():
        l = usable(left, keys).rename({c: f"{left_prefix}_{c}" for c in left.columns})
        r = usable(right, keys).rename({c: f"{right_prefix}_{c}" for c in right.columns})
        frame = l.join(r, left_on=[f"{left_prefix}_{k}" for k in keys],
                       right_on=[f"{right_prefix}_{k}" for k in keys], how="inner", coalesce=False)
        frames.append(frame.with_columns(pl.lit(tier, dtype=pl.Int8).alias("candidate_tier")))
    return pl.concat(frames).sort("candidate_tier", f"{left_prefix}_source_row", f"{right_prefix}_source_row")


def diagnose(source, spotify):
    result = source
    for key, label in [("original_title_key", "title"), ("original_artist_key", "artist")]:
        # At most one aggregate row per key; no title-only Cartesian expansion.
        lookup = usable(spotify, [key]).group_by(key).agg(
            pl.col("id").drop_nulls().n_unique().alias(f"spotify_ids_with_exact_{label}"),
            pl.col("id").drop_nulls().unique().sort().head(3).alias(f"{label}_example_ids"))
        result = result.join(lookup, on=key, how="left", validate="m:1")
        result = result.with_columns(pl.col(f"spotify_ids_with_exact_{label}").fill_null(0),
                                    pl.col(f"{label}_example_ids").list.join(" | ").fill_null(""))
    t = pl.col("spotify_ids_with_exact_title") > 0
    a = pl.col("spotify_ids_with_exact_artist") > 0
    bad = pl.any_horizontal([pl.col(c).is_null() | (pl.col(c).str.strip_chars() == "")
                            for c in ["original_title_key", "original_artist_key"]])
    return result.with_columns(pl.when(bad).then(pl.lit(REASONS[4]))
        .when(t & a).then(pl.lit(REASONS[2])).when(t).then(pl.lit(REASONS[0]))
        .when(a).then(pl.lit(REASONS[1])).otherwise(pl.lit(REASONS[3])).alias("unmatched_reason")).sort("source_row")


def summarize_candidates(candidates, source, prefix, other_id, all_count, split_column, labels):
    sid = f"{prefix}_source_row"
    seen = set()
    tiers = []
    for tier in TIERS:
        subset = candidates.filter(pl.col("candidate_tier") == tier)
        counts = subset.group_by(sid).agg(pl.col(other_id).n_unique().alias("ids"))
        found = set(counts[sid])
        tiers.append({"tier": tier, "candidate_rows": subset.height, "source_records_with_candidates": len(found),
            "one_candidate": counts.filter(pl.col("ids") == 1).height,
            "multiple_candidates": counts.filter(pl.col("ids") > 1).height,
            "newly_covered_after_earlier_tiers": len(found - seen),
            "incremental_percentage_points_of_all_source": 100 * len(found - seen) / all_count if all_count else None,
            "examples": subset.select(sid, f"{prefix}_raw_title", f"{prefix}_raw_artist", other_id, "candidate_tier").head(5).to_dicts()})
        seen |= found
    counts = candidates.group_by(sid).agg(pl.col(other_id).n_unique().alias("distinct_candidate_ids"))
    status = source.join(counts.rename({sid: "source_row"}), on="source_row", how="left").with_columns(
        pl.col("distinct_candidate_ids").fill_null(0)).sort("source_row")
    def summary(frame):
        n = frame.filter(pl.col("distinct_candidate_ids") > 0).height
        return {"previously_unmatched": frame.height, "with_variant_candidates": n,
            "one_candidate": frame.filter(pl.col("distinct_candidate_ids") == 1).height,
            "multiple_candidates": frame.filter(pl.col("distinct_candidate_ids") > 1).height,
            "still_without_candidate": frame.filter(pl.col("distinct_candidate_ids") == 0).height,
            "pct_of_previously_unmatched": 100 * n / frame.height if frame.height else None}
    return {"all_tiers_combined": summary(status), "tiers": tiers,
            "additional_percentage_points_of_all_source": 100 * len(seen) / all_count if all_count else None,
            "subgroups": {label: {"combined": summary(status.filter(pl.col(split_column) == value)),
                "per_tier": [{"tier": tier, "source_records_with_candidates":
                    candidates.filter(pl.col("candidate_tier") == tier).join(
                        source.filter(pl.col(split_column) == value).select(pl.col("source_row").alias(sid)), on=sid, how="semi")[sid].n_unique()}
                             for tier in TIERS]} for value, label in labels},
            "source_statuses": status.select("source_row", "raw_title", "raw_artist", "distinct_candidate_ids").to_dicts()}


def overlap(bs, gs, bg):
    # A pair's Spotify candidates are the intersection of IDs from BOTH sides.
    shared = bg.select("billboard_source_row", "grammy_source_row").join(
        bs.select("billboard_source_row", "spotify_id").unique(), on="billboard_source_row", how="inner").join(
        gs.select("grammy_source_row", "spotify_id").unique(), on=["grammy_source_row", "spotify_id"], how="inner")
    counts = shared.group_by("billboard_source_row", "grammy_source_row").agg(pl.col("spotify_id").n_unique().alias("spotify_ids"))
    pair_status = bg.join(counts, on=["billboard_source_row", "grammy_source_row"], how="left").with_columns(pl.col("spotify_ids").fill_null(0))
    def summarize(frame):
        return {"billboard_grammy_pairs": frame.height,
            "no_spotify_candidate": frame.filter(pl.col("spotify_ids") == 0).height,
            "one_spotify_candidate": frame.filter(pl.col("spotify_ids") == 1).height,
            "multiple_spotify_candidates": frame.filter(pl.col("spotify_ids") > 1).height,
            "distinct_billboard_songs_with_both": frame.filter(pl.col("spotify_ids") > 0)["billboard_source_row"].n_unique()}
    return {"billboard_songs_matched_to_spotify": bs["billboard_source_row"].n_unique(),
            "billboard_songs_matched_to_grammy": bg["billboard_source_row"].n_unique(),
            "billboard_songs_matched_to_both": shared["billboard_source_row"].n_unique(),
            "pair_counts": summarize(pair_status),
            "winners": summarize(pair_status.filter(pl.col("grammy_grammy_winner") == 1)),
            "non_winning_nominees": summarize(pair_status.filter(pl.col("grammy_grammy_winner") == 0)),
            "definition": "Existing exact candidates only; distinct shared Spotify IDs per Billboard–Grammy pair, not cross-products of different track IDs."}


def collision_tables(b, g, s, destination):
    # One row per usable tier/key across ALL sources. No row-level pair join.
    source_frames = []
    fields = ["source_row", "raw_title", "raw_artist", "original_title_key", "original_artist_key", "title_base_norm", "primary_artist_norm"]
    for name, frame in [("billboard", b), ("grammy", g), ("spotify", s)]:
        source_frames.append(frame.select(fields + (["id"] if name == "spotify" else [])).with_columns(
            pl.lit(name).alias("source_kind"), *([] if name == "spotify" else [pl.lit(None, dtype=pl.String).alias("id")])).select(fields + ["id", "source_kind"]))
    combined = pl.concat(source_frames, how="vertical_relaxed")
    summary = []
    with destination.open("w", encoding="utf-8", newline="") as stream:
        for tier, keys in TIERS.items():
            table = usable(combined, keys).group_by(list(keys)).agg(
                pl.col("raw_title").drop_nulls().n_unique().alias("distinct_raw_titles"),
                pl.col("raw_artist").drop_nulls().n_unique().alias("distinct_raw_artists"),
                pl.col("id").drop_nulls().n_unique().alias("spotify_ids"),
                pl.struct("original_title_key", "original_artist_key").n_unique().alias("original_normalized_keys"),
                pl.col("source_row").filter(pl.col("source_kind") == "billboard").n_unique().alias("billboard_records"),
                pl.col("source_row").filter(pl.col("source_kind") == "grammy").n_unique().alias("grammy_records"),
            ).rename({keys[0]: "variant_title_key", keys[1]: "variant_artist_key"}).with_columns(
                pl.lit(tier, dtype=pl.Int8).alias("candidate_tier"),
                (pl.col("original_normalized_keys") > 1).alias("new_collision"),
                (pl.col("billboard_records") > 1).alias("multiple_billboard_records"),
                (pl.col("grammy_records") > 1).alias("multiple_grammy_records"),
            ).sort("variant_title_key", "variant_artist_key")
            table.write_csv(stream, include_header=tier == 1)
            summary.append({"tier": tier, "variant_keys": table.height,
                "raw_text_collision_keys": table.filter((pl.col("distinct_raw_titles") > 1) | (pl.col("distinct_raw_artists") > 1)).height,
                "new_collision_keys": table.filter(pl.col("new_collision")).height,
                "multiple_spotify_id_keys": table.filter(pl.col("spotify_ids") > 1).height,
                "multiple_billboard_record_keys": table.filter(pl.col("multiple_billboard_records")).height,
                "multiple_grammy_record_keys": table.filter(pl.col("multiple_grammy_records")).height})
    return summary


def protected_hashes():
    paths = set((ROOT / "data/raw").glob("*.csv")) | set((ROOT / "data/interim").glob("*.parquet"))
    paths |= {p for p in (ROOT / "reports").iterdir() if p.is_file()}
    paths |= {p for folder in ["src", "tests"] for p in (ROOT / folder).rglob("*.py")}
    paths.add(ROOT / "README.md")
    excluded = set(OUTPUTS) | {"src/04_match_expansion_audit.py", "tests/test_match_expansion_audit.py"}
    result = {}
    for path in sorted(paths):
        relative = path.relative_to(ROOT).as_posix()
        if relative not in excluded:
            with path.open("rb") as stream:
                result[relative] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


LIMITATIONS = [
    "All outputs are unaccepted candidates. No exact candidate files or earlier reports are changed. No fuzzy similarity, Spotify ID selection or final modelling dataset is used.",
    "Tier 1 compares original title keys plus primary artists; tier 2 base titles plus original artists; tier 3 both variants. Every matching pair/tier is retained. Incremental coverage counts new source records after earlier tiers for reporting only, never as a selection rule.",
    "Grammy original matching keys are audited title_match_norm and performer_norm; variant functions operate on song_or_album and performer_extracted. Billboard uses Song/Artist; Spotify uses name/artists. Existing normalization fields remain intact.",
    "The identical title-base function does not strip '(Single)' because it is not an authorized version term. The four already-audited Grammy Single-label removals remain in original_title_key for tier 1; tiers 2/3 use raw-title version stripping only.",
    "Featuring/feat/ft removal requires a separate explicit marker followed by an artist suffix. Commas, ampersands, and, x and semicolons are not split. Removing featured artists can create false candidates.",
    "Version suffix removal is lexical, not semantic verification. Explicit keywords in meaningful trailing descriptions can still trigger removal. Unrecognized version labels are retained; hyphen separators require surrounding spaces. Review all expansions.",
    "Diagnosis counts Spotify IDs by title and artist separately with at most three sorted ID examples per field, not title-only or artist-only Cartesian candidates. Separately-existing keys take precedence over title-only and artist-only reasons. Blank keys take precedence over all other reasons.",
    "variant_collision_review.csv contains EVERY usable tier/key, not only flagged keys. New collision means distinct original normalized title–artist keys collapse into one tier/key across the three sources. Counts per tier overlap and should not be summed as unique identities. Missing/empty tier keys never match.",
    "Billboard–Grammy expansion applies only to Grammy records with no prior Billboard–Grammy exact pair (independent of Spotify status). Year gaps 0 or 1 are flagged plausible but never accepted automatically; all other gaps remain.",
    "Outcome columns are used only to report coverage, never to rank or choose candidates. Coverage differences can create selection bias. No candidate does not establish absence from Spotify; multiple IDs may be releases or distinct recordings.",
    "Sing and Sing! retain separate Billboard source-row IDs. Normalized-key equality, lyric equality and audio equality do not establish identity.",
]


def render(report):
    lines = ["# Conservative match-expansion audit", "", "Candidate generation only; no candidates accepted or selected.", ""]
    for title, key in [("Three-way overlap (existing exact candidates)", "three_way_overlap"),
                       ("Unmatched diagnoses", "diagnoses"), ("Variant collision counts", "collisions")]:
        lines += [f"## {title}", "", "```json", json.dumps(report[key], ensure_ascii=False, indent=2), "```", ""]
    for pair in PAIRS:
        result = {k: v for k, v in report["expansion"][pair].items() if k != "source_statuses"}
        lines += [f"## {pair.replace('_', '–')}", "", "```json", json.dumps(result, ensure_ascii=False, indent=2), "```", ""]
    lines += ["## Methodological limitations", "", *[f"- {x}" for x in LIMITATIONS], "",
              "## Validation", "", "```json", json.dumps(report["validation"], indent=2), "```", "",
              "## Outputs", "", *[f"- `{p}`" for p in OUTPUTS], "", "## Run", "", "```powershell",
              "uv run python -m unittest discover -s tests -v", "uv run python src/04_match_expansion_audit.py",
              "uv run python -m unittest discover -s tests -v", "```", ""]
    return "\n".join(lines)


def main():
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Python 3.12 is required")
    before = protected_hashes()
    load = lambda name: pl.read_parquet(ROOT / f"data/interim/{name}.parquet")
    b = variants(load("billboard_song_level_2000_2024").with_row_index("source_row", offset=1), "Song", "Artist", "title_norm", "artist_norm")
    g = variants(load("grammy_soty_enriched_2000_2024"), "song_or_album", "performer_extracted", "title_match_norm", "performer_norm")
    s = variants(load("spotify_track_index"), "name", "artists", "title_norm", "artist_norm")
    exact = {pair: load(f"{pair}_exact_candidates") for pair in PAIRS}
    baseline = json.loads((ROOT / "reports/exact_match_audit.json").read_text(encoding="utf-8"))
    ub, ug = unmatched(b, exact[PAIRS[0]], "billboard"), unmatched(g, exact[PAIRS[1]], "grammy")
    ug_bg = unmatched(g, exact[PAIRS[2]], "grammy")
    assert ub.height == baseline[PAIRS[0]]["coverage"]["no_exact_candidate"]
    assert ug.height == baseline[PAIRS[1]]["coverage"]["no_exact_candidate"]
    report = {"three_way_overlap": overlap(exact[PAIRS[0]], exact[PAIRS[1]], exact[PAIRS[2]]),
              "diagnoses": {}, "expansion": {}, "limitations": LIMITATIONS, "outputs": OUTPUTS}
    for name, source, split, labels in [("billboard", ub, "top10", [(1, "Top 10"), (0, "Non-Top-10")]),
                                        ("grammy", ug, "grammy_winner", [(1, "Winners"), (0, "Non-winning nominees")])]:
        diagnosis = diagnose(source, usable(s, ["id"]))
        assert diagnosis.height == source.height
        diagnosis.write_csv(ROOT / f"reports/{name}_unmatched_diagnosis.csv")
        distribution = lambda df: {reason: df.filter(pl.col("unmatched_reason") == reason).height for reason in REASONS}
        report["diagnoses"][name] = {"all": distribution(diagnosis), "subgroups": {
            label: distribution(diagnosis.filter(pl.col(split) == value)) for value, label in labels}}
    print("Generating all candidate tiers for previously unmatched records...", flush=True)
    configs = [(PAIRS[0], ub, usable(s, ["id"]), "billboard", "spotify", "spotify_id", b.height, "top10", [(1, "Top 10"), (0, "Non-Top-10")]),
        (PAIRS[1], ug, usable(s, ["id"]), "grammy", "spotify", "spotify_id", g.height, "grammy_winner", [(1, "Winners"), (0, "Non-winning nominees")]),
        (PAIRS[2], ug_bg, b, "grammy", "billboard", "billboard_source_row", g.height, "grammy_winner", [(1, "Winners"), (0, "Non-winning nominees")])]
    for pair, left, right, lp, rp, target_id, total, split, labels in configs:
        candidates = generate_candidates(left, right, lp, rp)
        assert set(candidates[f"{lp}_source_row"]).issubset(set(left["source_row"]))
        for tier, keys in TIERS.items():
            part = candidates.filter(pl.col("candidate_tier") == tier)
            for key in keys:
                assert part.select((pl.col(f"{lp}_{key}") == pl.col(f"{rp}_{key}")).all()).item()
        if pair == PAIRS[2]:
            candidates = candidates.with_columns((pl.col("grammy_year") - pl.col("billboard_first_chart_date").dt.year()).alias("year_gap")).with_columns(
                pl.col("year_gap").is_in([0, 1]).fill_null(False).alias("year_gap_plausible"))
        path = ROOT / f"data/interim/{pair}_variant_candidates.parquet"
        candidates.write_parquet(path, compression="zstd")
        loaded = pl.read_parquet(path)
        assert loaded.schema == candidates.schema and loaded.equals(candidates)
        candidates.write_csv(ROOT / f"reports/{pair}_variant_review.csv")
        report["expansion"][pair] = summarize_candidates(candidates, left, lp, target_id, total, split, labels)
        report["expansion"][pair]["candidate_rows_including_repeated_tiers"] = candidates.height
        report["expansion"][pair]["distinct_source_target_pairs"] = candidates.select(f"{lp}_source_row", target_id).unique().height
        if pair == PAIRS[2]:
            dedup = candidates.unique(subset=["grammy_source_row", "billboard_source_row"])
            report["expansion"][pair]["year_gap_distribution_distinct_pairs"] = dedup.group_by("year_gap").len().sort("year_gap").to_dicts()
            report["expansion"][pair]["unusual_year_gap_distinct_pairs"] = dedup.filter(~pl.col("year_gap_plausible")).height
        print(pair, report["expansion"][pair]["all_tiers_combined"], flush=True)
    print("Auditing every variant key for collisions...", flush=True)
    report["collisions"] = collision_tables(b, g, s, ROOT / "reports/variant_collision_review.csv")
    sing = b.filter((pl.col("title_norm") == "sing") & (pl.col("artist_norm") == "glee cast"))
    assert sing.height == 2 and sing["source_row"].n_unique() == 2
    after = protected_hashes()
    if before != after:
        raise RuntimeError("Protected existing files changed")
    report["integrity"] = {"before": before, "after": after}
    report["validation"] = {"protected_files_unchanged": True, "protected_file_count": len(before),
        "exact_candidates_unchanged": True, "unmatched_only": True, "tier_keys_validated": True,
        "original_columns_unchanged": True, "sing_records_separate": True, "parquet_roundtrips_passed": True,
        "no_fuzzy_matching": True, "no_candidate_selection": True, "no_final_modelling_dataset": True}
    (ROOT / "reports/match_expansion_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str, allow_nan=False) + "\n", encoding="utf-8")
    (ROOT / "reports/match_expansion_audit.md").write_text(render(report), encoding="utf-8")
    print(f"Audit complete. {len(before)} protected files unchanged.")


if __name__ == "__main__":
    main()
