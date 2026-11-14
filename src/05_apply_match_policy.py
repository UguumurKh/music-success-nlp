"""Accept relationship sets, never representative recordings or averaged audio.

Consumes metadata/candidate tables only. Raw files are stat'ed, never opened.
"""
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import NormalDist
import sys

import polars as pl
from music_success_nlp.normalization import normalize_text

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ["danceability", "energy", "key", "loudness", "mode", "speechiness", "acousticness",
         "instrumentalness", "liveness", "valence", "tempo", "duration_ms"]
EN = "accepted_safe_artist_variant"
FEATURE = re.compile(r"(?<!\S)(?:featuring|feat\.?|ft\.?)(?=\s|$)", re.I)
STATUSES = ["single_spotify_id", "multiple_ids_identical_lyrics_and_audio",
    "multiple_ids_identical_lyrics_different_audio", "multiple_ids_different_lyrics_identical_audio",
    "multiple_ids_different_lyrics_and_audio", "missing_lyrics_information"]
TABLES = ["billboard_spotify_accepted_candidates", "grammy_spotify_accepted_candidates", "billboard_grammy_accepted_pairs"]
REVIEWS = ["tier1_manual_review", "title_version_candidates_not_accepted", "source_normalization_collision_quarantine",
    "billboard_grammy_variant_manual_review", "billboard_spotify_consolidation_status", "grammy_spotify_consolidation_status"]
OUTPUTS = [f"data/interim/{s}.parquet" for s in TABLES] + [f"reports/{s}.csv" for s in REVIEWS] + [
    "reports/match_policy_audit.md", "reports/match_policy_audit.json"]


def artist_components(value):
    if value is None:
        return {"primary_artist_norm": None, "featured_artist_norm": None, "has_feature_marker": False}
    marker = FEATURE.search(value)
    return {"primary_artist_norm": normalize_text(value[:marker.start()] if marker else value),
            "featured_artist_norm": normalize_text(value[marker.end():]) if marker else None,
            "has_feature_marker": marker is not None}


def safe_artist_rule(left, right):
    a, b = artist_components(left), artist_components(right)
    for component in (a, b):
        if not component["primary_artist_norm"]:
            return False, "unusable_primary_artist"
        if component["has_feature_marker"] and not component["featured_artist_norm"]:
            return False, "missing_or_unusable_featured_suffix"
    if a["primary_artist_norm"] != b["primary_artist_norm"]:
        return False, "primary_artists_differ"
    if a["has_feature_marker"] and b["has_feature_marker"]:
        return (True, "same_primary_and_featured_artists") if a["featured_artist_norm"] == b["featured_artist_norm"] else (False, "conflicting_featured_artists")
    if a["has_feature_marker"] != b["has_feature_marker"]:
        return True, "one_explicit_feature_suffix_primary_equals_complete_other_artist"
    return False, "no_explicit_feature_marker_on_either_side"


def source_keys(source, kind):
    title, artist, tk, ak = ("Song", "Artist", "title_norm", "artist_norm") if kind == "billboard" else (
        "song_or_album", "performer_extracted", "title_match_norm", "performer_norm")
    return source.with_columns(pl.col(title).alias("policy_raw_title"), pl.col(artist).alias("policy_raw_artist"),
        pl.col(tk).alias("policy_title_key"), pl.col(ak).alias("policy_artist_key"),
        pl.col(artist).map_elements(lambda x: artist_components(x)["primary_artist_norm"], return_dtype=pl.String).alias("policy_primary_artist_norm"))


def collision_sets(source, kind):
    frame = source_keys(source, kind)
    quarantines, sets = [], {}
    for rule, artist_key in [("exact", "policy_artist_key"), ("tier1", "policy_primary_artist_norm")]:
        keys = ["policy_title_key", artist_key]
        valid = frame.filter(pl.all_horizontal([pl.col(k).is_not_null() & (pl.col(k) != "") for k in keys]))
        groups = valid.group_by(keys).agg(pl.struct("policy_raw_title", "policy_raw_artist").n_unique().alias("distinct_raw_identities"))
        groups = groups.filter(pl.col("distinct_raw_identities") > 1)
        rows = frame.join(groups, on=keys, how="inner").with_columns(pl.lit(kind).alias("source_dataset"), pl.lit(rule).alias("collision_rule"))
        quarantines.append(rows)
        sets[rule] = set(rows["source_row"])
    return sets, pl.concat(quarantines, how="diagonal_relaxed")


def apply_policy(source, exact, variants, kind):
    collisions, quarantine = collision_sets(source, kind)
    sid = f"{kind}_source_row"
    title_field = f"{kind}_title_norm" if kind == "billboard" else "grammy_title_match_norm"
    artist_field = f"{kind}_artist_norm" if kind == "billboard" else "grammy_performer_norm"
    raw_artist = f"{kind}_Artist" if kind == "billboard" else "grammy_performer_extracted"
    # Preserve full titles; no title_base_norm ever enters an accepted key.
    assert exact.select((pl.col(title_field) == pl.col("spotify_title_norm")).all()).item()
    assert exact.select((pl.col(artist_field) == pl.col("spotify_artist_norm")).all()).item()
    exact_ok = exact.filter(~pl.col(sid).is_in(list(collisions["exact"])))
    methods = [(r[sid], r["spotify_id"], "exact") for r in exact_ok.iter_rows(named=True)]
    tier1 = variants.filter(pl.col("candidate_tier") == 1)
    safe_flags, reasons, components = [], [], []
    for row in tier1.iter_rows(named=True):
        safe, reason = safe_artist_rule(row[raw_artist], row["spotify_artists"])
        if row[title_field] != row["spotify_title_norm"] or not row[title_field]:
            safe, reason = False, "complete_normalized_titles_differ_or_blank"
        if row[sid] in collisions["exact"] or row[sid] in collisions["tier1"]:
            safe, reason = False, "source_normalization_collision"
        safe_flags.append(safe)
        reasons.append(reason)
        components.append({f"policy_{side}_{k}": v for side, value in [("source", row[raw_artist]), ("spotify", row["spotify_artists"])]
                           for k, v in artist_components(value).items()})
        if safe:
            methods.append((row[sid], row["spotify_id"], EN))
    assessed = tier1.with_columns(pl.Series("policy_accepted", safe_flags, dtype=pl.Boolean),
                                  pl.Series("policy_reason", reasons, dtype=pl.String))
    for side in ("source", "spotify"):
        for key in ("primary_artist_norm", "featured_artist_norm", "has_feature_marker"):
            name = f"policy_{side}_{key}"
            assessed = assessed.with_columns(pl.Series(name, [x[name] for x in components], dtype=pl.Boolean if key == "has_feature_marker" else pl.String))
    manual = assessed.filter(~pl.col("policy_accepted")).with_columns(pl.lit("tier1_manual_review").alias("policy_classification"), pl.lit(kind).alias("source_dataset"))
    versions = variants.filter(pl.col("candidate_tier").is_in([2, 3])).with_columns(
        pl.lit("title_version_candidate_not_accepted").alias("policy_classification"), pl.lit(kind).alias("source_dataset"))
    accepted = deduplicate_methods(methods, source)
    counts = {"exact_candidate_rows_quarantined": exact.height - exact_ok.height,
        "exact_source_records_quarantined": exact.filter(pl.col(sid).is_in(list(collisions["exact"])))[sid].n_unique(),
        "tier1_rows_accepted": sum(safe_flags), "tier1_rows_manual_review": manual.height,
        "tier1_manual_review_sources": manual[sid].n_unique(),
        "tier1_manual_reasons": manual.group_by("policy_reason").len().sort("policy_reason").to_dicts(),
        "title_version_candidate_rows_not_accepted": versions.height,
        "exact_collision_source_rows": len(collisions["exact"]), "tier1_collision_source_rows": len(collisions["tier1"])}
    return accepted, manual, versions, quarantine, collisions, counts


def deduplicate_methods(method_rows, source):
    rows = pl.DataFrame(method_rows, schema={"source_row": source.schema["source_row"], "spotify_id": pl.String, "method": pl.String}, orient="row")
    grouped = rows.group_by("source_row", "spotify_id").agg(pl.col("method").unique().sort().alias("all_match_methods"),
        (pl.col("method") == "exact").any().alias("exact_match"),
        (pl.col("method") == EN).any().alias("safe_tier1_match"))
    grouped = grouped.with_columns(pl.when(pl.col("exact_match")).then(pl.lit("exact")).otherwise(pl.lit(EN)).alias("strongest_match_method"))
    # Method order expresses policy strength, not track preference.
    grouped = grouped.with_columns(pl.when(pl.col("exact_match") & pl.col("safe_tier1_match"))
        .then(pl.lit(["exact", EN])).otherwise(pl.col("all_match_methods")).alias("all_match_methods"))
    return source.join(grouped, on="source_row", how="inner", validate="1:m").sort("source_row", "spotify_id")


def consolidate(accepted, source, spotify):
    missing = [c for c in AUDIO if c not in spotify.columns]
    if missing:
        raise ValueError(f"Required audio columns missing: {missing}")
    # Metadata is not selected from competing IDs; every indexed row participates.
    joined = accepted.select("source_row", "spotify_id").join(
        spotify.rename({c: f"sp_{c}" for c in spotify.columns}), left_on="spotify_id", right_on="sp_id", how="left")
    if joined["sp_source_row"].null_count():
        raise ValueError("Accepted Spotify ID absent from track index")
    audio_cols = [f"sp_{c}" for c in AUDIO]
    stats = joined.group_by("source_row").agg(
        pl.col("spotify_id").n_unique().alias("distinct_spotify_ids"), pl.len().alias("spotify_metadata_rows"),
        pl.col("sp_lyric_sha256").drop_nulls().n_unique().alias("distinct_lyric_sha256"),
        pl.struct(audio_cols).n_unique().alias("distinct_audio_combinations"),
        pl.col("sp_album_name").drop_nulls().n_unique().alias("distinct_album_names"),
        pl.col("sp_album_name").is_null().any().alias("any_missing_album_name"),
        (pl.col("sp_lyrics_missing").fill_null(True) | pl.col("sp_lyrics_blank").fill_null(True)).any().alias("any_missing_or_blank_lyrics"),
        (pl.col("sp_lyric_sha256").is_null() | (pl.col("sp_lyric_sha256") == "")).any().alias("any_missing_lyric_hash"),
        pl.any_horizontal([pl.col(c).is_null() for c in audio_cols]).any().alias("any_missing_audio_value"))
    stats = stats.with_columns(((pl.col("distinct_lyric_sha256") == 1) & ~pl.col("any_missing_lyric_hash") & ~pl.col("any_missing_or_blank_lyrics")).alias("all_ids_identical_lyric_hashes"),
                                (pl.col("distinct_audio_combinations") == 1).alias("all_ids_identical_audio_combinations"))
    lyrics, audio = pl.col("all_ids_identical_lyric_hashes"), pl.col("all_ids_identical_audio_combinations")
    stats = stats.with_columns(pl.when(pl.col("any_missing_or_blank_lyrics") | pl.col("any_missing_lyric_hash")).then(pl.lit(STATUSES[5]))
        .when(pl.col("distinct_spotify_ids") == 1).then(pl.lit(STATUSES[0]))
        .when(lyrics & audio).then(pl.lit(STATUSES[1])).when(lyrics).then(pl.lit(STATUSES[2]))
        .when(audio).then(pl.lit(STATUSES[3])).otherwise(pl.lit(STATUSES[4])).alias("consolidation_status"))
    assert stats["source_row"].n_unique() == stats.height and stats["consolidation_status"].is_in(STATUSES).all()
    return source.join(stats, on="source_row", how="inner", validate="1:1").sort("source_row")


def coverage(source, accepted, statuses, collisions):
    ids = set(accepted["source_row"])
    exact_ids = set(accepted.filter(pl.col("exact_match"))["source_row"])
    tier_ids = set(accepted.filter(pl.col("safe_tier1_match"))["source_row"])
    relevant = set(source["source_row"])
    total, matched = source.height, len(relevant & ids)
    return {"total_source_records": total, "accepted_exact_only_records": len(relevant & exact_ids),
        "exact_only_coverage_pct": 100 * len(relevant & exact_ids) / total if total else None,
        "additional_safe_tier1_records": len((relevant & tier_ids) - exact_ids),
        "total_accepted_records": matched, "accepted_coverage_pct": 100 * matched / total if total else None,
        "exact_collision_quarantined_records": len(relevant & collisions["exact"]),
        "tier1_collision_flagged_records": len(relevant & collisions["tier1"]),
        "still_unmatched": total - matched,
        "consolidation_distribution": {s: statuses.filter(pl.col("source_row").is_in(list(relevant)) & (pl.col("consolidation_status") == s)).height for s in STATUSES}}


def wilson(x, n):
    z = NormalDist().inv_cdf(.975)
    p = x / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return max(0., center - half), min(1., center + half)


def billboard_grammy_policy(exact, variant):
    return exact.clone(), variant.with_columns(pl.lit("manual_review_not_accepted").alias("policy_classification"))


def compare_coverage(x1, n1, x2, n2, test=True):
    """Two-sided pooled z-test; Newcombe independent Wilson 95% difference CI."""
    if not n1 or not n2:
        return {"not_estimable": "empty comparison group"}
    p1, p2 = x1 / n1, x2 / n2
    lo1, hi1 = wilson(x1, n1)
    lo2, hi2 = wilson(x2, n2)
    diff = p1 - p2
    result = {"group1_accepted": x1, "group1_n": n1, "group2_accepted": x2, "group2_n": n2,
        "group1_coverage_pct": p1 * 100, "group2_coverage_pct": p2 * 100,
        "difference_percentage_points": diff * 100, "risk_ratio": p1 / p2 if p2 else None,
        "difference_95pct_ci_percentage_points": [100 * (diff - math.sqrt((p1 - lo1) ** 2 + (hi2 - p2) ** 2)),
                                                  100 * (diff + math.sqrt((hi1 - p1) ** 2 + (p2 - lo2) ** 2))],
        "ci_method": "Newcombe hybrid score (independent Wilson intervals, no continuity correction)"}
    if test:
        pooled = (x1 + x2) / (n1 + n2)
        se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
        z = diff / se if se else 0.
        result.update(z_statistic=z, two_sided_p_value=math.erfc(abs(z) / math.sqrt(2)),
                      null_hypothesis="equal coverage proportions", test_method="pooled two-sample proportion z-test, no continuity correction")
    return result


def protected_snapshot():
    # No raw CSV is opened: raw lyric access is explicitly out of scope.
    result = {p.relative_to(ROOT).as_posix(): {"verification": "metadata_only_no_read", "bytes": p.stat().st_size,
        "mtime_ns": p.stat().st_mtime_ns} for p in (ROOT / "data/raw").glob("*.csv")}
    paths = set((ROOT / "data/interim").glob("*.parquet")) | {p for p in (ROOT / "reports").iterdir() if p.is_file()}
    paths |= {p for folder in ["src", "tests"] for p in (ROOT / folder).rglob("*.py")}
    paths.add(ROOT / "README.md")
    excluded = set(OUTPUTS) | {"src/05_apply_match_policy.py", "tests/test_apply_match_policy.py"}
    for path in sorted(paths):
        relative = path.relative_to(ROOT).as_posix()
        if relative not in excluded:
            with path.open("rb") as stream:
                result[relative] = {"sha256": hashlib.file_digest(stream, "sha256").hexdigest()}
    return result


DECISIONS = [
    "Exact relationships are accepted only outside source-key collisions. Collision identity is the raw title plus raw artist/parsed performer, within each source. Grammy year alone does not make a new identity. Exact keys and Tier-1 title/primary keys are audited across all source records, including records already exact-matched.",
    "Exact source collisions block both exact and Tier-1 acceptance. Tier-1 source collisions block Tier 1 only. The collision CSV lists all flagged source/rule rows, even where no candidate is available; candidate impact counts are separately reported. Sing and Sing! stay separate and both are quarantined.",
    "Safe Tier 1 requires complete normalized title equality and either one usable explicit feature suffix with primary equal to the other complete artist, or equal primary and featured suffixes on both sides. No comma, ampersand, and, x or semicolon splitting is used.",
    "All Tier 2/3 evidence is rejected from the primary candidate set. Taylor's Version, other possessive version labels, remixes, live/acoustic/instrumental and other versions remain part of complete accepted title keys. Earlier variant files are unchanged.",
    "Accepted Parquets contain one source–Spotify-ID relationship per row, original source fields, all methods, strongest method and exact/safe-Tier-1 indicators. They intentionally do not select a metadata row from Spotify. Diagnostics join every indexed metadata row for every accepted ID. Exact is the strongest METHOD, never a preference for one track ID.",
    "Consolidation missing-lyrics status takes precedence, including for a single ID, when any lyric flag is missing/blank or hash is null/empty. Otherwise single ID precedes the four multiple-ID categories. Known lyric-hash distinct counts exclude nulls. Audio comparison uses all 12 original fields as a tuple, including null patterns if present; missing audio is separately flagged. Equality of missing patterns is not proof of measured audio equality. Album counts exclude null but preserve literal blanks.",
    "All 125 existing Billboard–Grammy exact rows are copied unchanged. All additional variant evidence stays in manual review with both full source records, years, gaps, tiers and keys.",
    "Coverage outcomes are used only after relationship acceptance and consolidation, never to select, rank or reject Spotify candidates. Statistical significance does not measure the practical size of selection bias. These source tables are not random population samples; independence assumptions may fail for repeated artists/works, so inference is exploratory.",
    "Grammy winner comparisons are descriptive with a difference confidence interval; only 25 winner records make precision limited. No formal winner/non-winner z-test is reported.",
    "Raw CSVs are never opened. Their size/mtime are checked, not rehashed; all existing non-raw data/report/code inputs are SHA-256 checked before/after. No raw lyrics extraction, fuzzy matching, representative ID selection, audio aggregation or final modelling dataset is performed.",
]


def render(report):
    lines = ["# Match-policy and candidate-consolidation audit", "", "Accepted relationships are sets of candidate IDs, not selected recordings.", ""]
    for kind in ["billboard", "grammy"]:
        lines += [f"## {kind.title()} accepted coverage", "", "| Group | Total | Exact accepted | Added safe Tier 1 | Accepted total | Coverage % | Still unmatched |",
                  "|---|---:|---:|---:|---:|---:|---:|"]
        for name, c in report[kind]["coverage"].items():
            lines.append(f"| {name} | {c['total_source_records']} | {c['accepted_exact_only_records']} | {c['additional_safe_tier1_records']} | {c['total_accepted_records']} | {c['accepted_coverage_pct']:.2f} | {c['still_unmatched']} |")
        for title, value in [("Consolidation (all accepted records)", report[kind]["coverage"]["All"]["consolidation_distribution"]),
                             ("Quarantine and manual review", report[kind]["policy_counts"]),
                             ("Coverage comparison", report[kind]["coverage_comparison"])]:
            lines += ["", f"### {title}", "", "```json", json.dumps(value, indent=2), "```"]
    lines += ["", "## Billboard–Grammy", "", "```json", json.dumps(report["billboard_grammy"], indent=2), "```",
        "", "## Decisions and limitations", "", *[f"- {x}" for x in DECISIONS], "",
        "Statistical definitions: [NIST two-proportion z-test](https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/diffprci.htm) and "
        "[Newcombe difference-interval documentation](https://www.statsmodels.org/dev/generated/statsmodels.stats.proportion.confint_proportions_2indep.html). "
        "Formulas are implemented with the Python standard library; no additional package is required.", "",
        "## Validation", "", "```json", json.dumps(report["validation"], indent=2), "```", "", "## Files", "",
        *[f"- `{p}`" for p in OUTPUTS], "", "## Run", "", "```powershell", "uv run python -m unittest discover -s tests -v",
        "uv run python src/05_apply_match_policy.py", "uv run python -m unittest discover -s tests -v", "```", ""]
    return "\n".join(lines)


def main():
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Python 3.12 is required")
    before = protected_snapshot()
    load = lambda stem: pl.read_parquet(ROOT / f"data/interim/{stem}.parquet")
    b = load("billboard_song_level_2000_2024").with_row_index("source_row", offset=1)
    g = load("grammy_soty_enriched_2000_2024")
    s = load("spotify_track_index")
    prior_exact = json.loads((ROOT / "reports/exact_match_audit.json").read_text(encoding="utf-8"))
    prior_variant = json.loads((ROOT / "reports/match_expansion_audit.json").read_text(encoding="utf-8"))
    report = {"decisions": DECISIONS, "outputs": OUTPUTS}
    manuals, versions, quarantines = [], [], []
    roundtrips = {}
    def save(frame, stem):
        path = ROOT / f"data/interim/{stem}.parquet"
        frame.write_parquet(path, compression="zstd")
        readback = pl.read_parquet(path)
        assert frame.schema == readback.schema and frame.equals(readback)
        roundtrips[stem] = frame.height
    for kind, source, split, labels in [("billboard", b, "top10", [(1, "Top 10"), (0, "Non-Top-10")]),
                                        ("grammy", g, "grammy_winner", [(1, "Winners"), (0, "Non-winning nominees")])]:
        print(f"Applying {kind} policy...", flush=True)
        ex, var = load(f"{kind}_spotify_exact_candidates"), load(f"{kind}_spotify_variant_candidates")
        assert ex[f"{kind}_source_row"].n_unique() == prior_exact[f"{kind}_spotify"]["coverage"]["at_least_one_candidate"]
        assert var.height == prior_variant["expansion"][f"{kind}_spotify"]["candidate_rows_including_repeated_tiers"]
        accepted, manual, rejected, quarantine, collision_ids, counts = apply_policy(source, ex, var, kind)
        status = consolidate(accepted, source, s)
        assert accepted.select("source_row", "spotify_id").unique().height == accepted.height
        assert set(accepted["strongest_match_method"]).issubset({"exact", EN})
        if kind == "billboard":
            sing = source.filter((pl.col("title_norm") == "sing") & (pl.col("artist_norm") == "glee cast"))
            assert sing.height == 2 and set(sing["source_row"]).issubset(collision_ids["exact"])
            assert not set(sing["source_row"]) & set(accepted["source_row"])
        save(accepted, f"{kind}_spotify_accepted_candidates")
        status.write_csv(ROOT / f"reports/{kind}_spotify_consolidation_status.csv")
        cov = {"All": coverage(source, accepted, status, collision_ids)}
        cov.update({label: coverage(source.filter(pl.col(split) == value), accepted, status, collision_ids) for value, label in labels})
        c1, c2 = (cov[label] for _, label in labels)
        comparison = compare_coverage(c1["total_accepted_records"], c1["total_source_records"], c2["total_accepted_records"], c2["total_source_records"], test=kind == "billboard")
        comparison["group1_label"], comparison["group2_label"] = labels[0][1], labels[1][1]
        report[kind] = {"coverage": cov, "policy_counts": counts, "accepted_relationships": accepted.height, "coverage_comparison": comparison}
        manuals.append(manual)
        versions.append(rejected)
        quarantines.append(quarantine)
        print(kind, cov["All"], flush=True)
    for frames, filename in [(manuals, "tier1_manual_review"), (versions, "title_version_candidates_not_accepted"),
                              (quarantines, "source_normalization_collision_quarantine")]:
        pl.concat(frames, how="diagonal_relaxed").write_csv(ROOT / f"reports/{filename}.csv")
    bg, bg_variant = load("billboard_grammy_exact_candidates"), load("billboard_grammy_variant_candidates")
    assert bg.height == 125
    bg_accepted, bg_review = billboard_grammy_policy(bg, bg_variant)
    save(bg_accepted, "billboard_grammy_accepted_pairs")
    bg_review.write_csv(ROOT / "reports/billboard_grammy_variant_manual_review.csv")
    report["billboard_grammy"] = {"accepted_exact_pairs": bg.height, "manual_variant_rows": bg_variant.height,
        "manual_distinct_variant_pairs": bg_variant.select("billboard_source_row", "grammy_source_row").unique().height}
    after = protected_snapshot()
    if before != after:
        raise RuntimeError("A protected existing file changed")
    report["integrity"] = {"before": before, "after": after}
    report["validation"] = {"protected_files_unchanged": True, "protected_file_count": len(before),
        "raw_files_not_opened": True, "raw_metadata_unchanged": True, "all_nonraw_protected_hashes_unchanged": True,
        "parquet_roundtrips": roundtrips, "billboard_grammy_exact_unchanged": True, "sing_quarantined": True,
        "no_fuzzy_matching": True, "no_representative_id_selection": True, "no_audio_aggregation": True,
        "no_raw_lyrics_extraction": True, "no_final_modelling_dataset": True}
    (ROOT / "reports/match_policy_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (ROOT / "reports/match_policy_audit.md").write_text(render(report), encoding="utf-8")
    print(f"Policy audit complete. {len(before)} existing files unchanged; raw CSVs not opened.")


if __name__ == "__main__":
    main()
