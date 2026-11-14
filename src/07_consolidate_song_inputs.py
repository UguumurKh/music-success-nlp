"""One predictor record per accepted source, with outcome-blind consolidation."""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import median
import sys
import unicodedata

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
NUMERIC = ["danceability", "energy", "loudness", "speechiness", "acousticness", "instrumentalness",
           "liveness", "valence", "tempo", "duration_ms"]
AUDIO = NUMERIC + ["key", "mode"]
RELATION_COLUMNS = ["spotify_id", "all_match_methods", "exact_match", "safe_tier1_match", "strongest_match_method"]
OUTPUTS = ["data/interim/billboard_song_level_consolidated.parquet", "data/interim/grammy_song_level_consolidated.parquet",
           "reports/song_input_consolidation.md", "reports/song_input_consolidation.json",
           "reports/billboard_low_confidence_consolidation.csv", "reports/grammy_low_confidence_consolidation.csv",
           "reports/lyric_selection_ledger.csv"]


def lyrics_compare_norm(value):
    if value is None:
        return None
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).casefold()).strip()


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value is not None else None


def comparison_content(content):
    result = content.with_columns(pl.col("lyrics").map_elements(lyrics_compare_norm, return_dtype=pl.String).alias("lyrics_compare_norm"))
    result = result.with_columns(pl.col("lyrics_compare_norm").map_elements(digest, return_dtype=pl.String).alias("lyrics_compare_sha256"),
        pl.col("lyrics_compare_norm").str.count_matches(r"\S+").alias("lyrics_compare_word_count"),
        pl.col("lyrics").map_elements(digest, return_dtype=pl.String).alias("raw_lyric_sha256"))
    assert result.select(content.columns).equals(content)
    return result


def unique_mode(values):
    counts = Counter(v for v in values if v is not None)
    if not counts:
        return None, False
    maximum = max(counts.values())
    modes = [value for value, count in counts.items() if count == maximum]
    return (modes[0], False) if len(modes) == 1 else (None, True)


def missing_audio(value):
    return value is None or isinstance(value, float) and not math.isfinite(value)


def consolidate_records(records):
    """Receives Spotify content only: no source metadata/outcomes are accessible."""
    records = sorted(records, key=lambda r: r["id"])
    ids = [r["id"] for r in records]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Require a nonempty set of distinct Spotify IDs")
    groups = defaultdict(list)
    for row in records:
        groups[row["lyrics_compare_sha256"]].append(row)
    largest = max(map(len, groups.values()))
    tied = [group for group in groups.values() if len(group) == largest]
    selected = min(tied, key=lambda group: min(r["id"] for r in group))
    representative = min(selected, key=lambda r: r["id"])
    tie, n = len(tied) > 1, len(ids)
    lyric_missing = any(not r["lyrics_compare_norm"] for r in records)
    lyric_consistent = len(groups) == 1 and not lyric_missing
    majority = largest * 2 > n
    # A unique plurality without >50% support is not covered by the requested
    # three confidence definitions. Conservatively flag it low, not medium.
    lyric_confidence = "low" if lyric_missing else "high" if n == 1 or lyric_consistent else "medium" if majority else "low"
    rule = "single_spotify_id" if n == 1 else "largest_group_then_lexicographic_id" if not tie else "tied_groups_then_lexicographic_id"
    result = {"lyric_representative_spotify_id": representative["id"],
        "lyric_representative_raw_source_row": representative["source_row"],
        "lyric_candidate_id_count": n, "accepted_spotify_ids": ids,
        "distinct_raw_lyric_hashes": len({r["raw_lyric_sha256"] for r in records}),
        "distinct_comparison_lyric_hashes": len(groups), "dominant_lyric_group_size": largest,
        "dominant_lyric_group_share": largest / n, "lyric_group_tie": tie,
        "lyric_group_strict_majority": majority, "lyric_unique_plurality_without_majority": not tie and not majority,
        "lyrics_consistent_across_ids": lyric_consistent, "lyric_selection_rule": rule,
        "lyric_resolution_confidence": lyric_confidence, "any_missing_or_blank_lyrics": lyric_missing,
        "lyrics": representative["lyrics"], "lyrics_compare_norm": representative["lyrics_compare_norm"],
        "lyrics_compare_sha256": representative["lyrics_compare_sha256"],
        "lyrics_compare_word_count": representative["lyrics_compare_word_count"],
        "raw_lyric_sha256": representative["raw_lyric_sha256"]}
    # All accepted IDs contribute equally, independently of the selected group.
    any_missing = any(missing_audio(r[c]) for r in records for c in AUDIO)
    combinations = {tuple(None if missing_audio(r[c]) else r[c] for c in AUDIO) for r in records}
    complete_combinations = {tuple(r[c] for c in AUDIO) for r in records if not any(missing_audio(r[c]) for c in AUDIO)}
    for column in NUMERIC:
        values = [r[column] for r in records if not missing_audio(r[column])]
        result.update({f"{column}_median": median(values) if values else None,
                       f"{column}_min": min(values) if values else None,
                       f"{column}_max": max(values) if values else None,
                       f"{column}_range": max(values) - min(values) if values else None})
    for column in ("key", "mode"):
        value, is_tie = unique_mode([r[column] for r in records])
        result[f"{column}_mode"] = value
        result[f"{column}_mode_tie"] = is_tie
    audio_consistent = len(combinations) == 1 and not any_missing
    categorical_tie = result["key_mode_tie"] or result["mode_mode_tie"]
    result.update(audio_candidate_id_count=n, distinct_audio_combinations=len(combinations),
        distinct_complete_audio_combinations=len(complete_combinations), audio_consistent_across_ids=audio_consistent,
        any_missing_audio_value=any_missing, single_spotify_id=n == 1,
        strict_consistency_sample=n == 1 or lyric_consistent and audio_consistent,
        audio_resolution_confidence="low" if categorical_tie or any_missing else "high" if n == 1 or audio_consistent else "medium")
    ledger = [{"spotify_id": r["id"], "raw_source_row": r["source_row"], "raw_lyric_sha256": r["raw_lyric_sha256"],
        "lyrics_compare_sha256": r["lyrics_compare_sha256"], "lyrics_compare_word_count": r["lyrics_compare_word_count"],
        "lyric_group_id_count": len(groups[r["lyrics_compare_sha256"]]), "candidate_id_count": n,
        "selected_lyric_group": r["lyrics_compare_sha256"] == representative["lyrics_compare_sha256"],
        "lyric_representative_spotify_id": representative["id"], "is_lyric_representative": r["id"] == representative["id"],
        "lyric_selection_rule": rule} for r in records]
    return result, ledger


def consolidate_source(accepted, content, kind):
    if accepted.select("source_row", "spotify_id").unique().height != accepted.height:
        raise ValueError("Duplicate accepted source–ID relationships")
    if content["id"].n_unique() != content.height:
        raise ValueError("Extracted content IDs must be unique")
    source_columns = [c for c in accepted.columns if c not in RELATION_COLUMNS]
    source = accepted.select(source_columns).unique().sort("source_row")
    if source["source_row"].n_unique() != source.height:
        raise ValueError("Conflicting metadata for source record")
    content_by_id = {r["id"]: r for r in content.iter_rows(named=True)}
    groups = accepted.select("source_row", "spotify_id").group_by("source_row").agg(pl.col("spotify_id").sort())
    results, ledger = [], []
    for group in groups.sort("source_row").iter_rows(named=True):
        if any(track not in content_by_id for track in group["spotify_id"]):
            raise ValueError("Accepted candidate content missing")
        result, entries = consolidate_records([content_by_id[track] for track in group["spotify_id"]])
        results.append({"source_row": group["source_row"], **result})
        ledger.extend({"source_dataset": kind, "source_row": group["source_row"], **entry} for entry in entries)
    predictors = pl.DataFrame(results, infer_schema_length=None).with_columns(pl.col("source_row").cast(source.schema["source_row"]))
    # Modes preserve raw categorical types. Null medians remain numeric.
    predictors = predictors.with_columns([pl.col(f"{c}_{suffix}").cast(pl.Float64) for c in NUMERIC for suffix in ("median", "min", "max", "range")] +
        [pl.col(f"{c}_mode").cast(content.schema[c]) for c in ("key", "mode")])
    methods = accepted.group_by("source_row").agg(pl.col("all_match_methods").explode().unique().sort().alias("all_match_methods"),
        pl.col("exact_match").any(), pl.col("safe_tier1_match").any()).with_columns(
        pl.when(pl.col("exact_match")).then(pl.lit("exact")).otherwise(pl.lit("accepted_safe_artist_variant")).alias("strongest_match_method"))
    # Outcomes and source metadata are attached only after predictor decisions.
    output = source.join(predictors, on="source_row", validate="1:1").join(methods, on="source_row", validate="1:1").sort("source_row")
    assert output.select(source_columns).equals(source)
    assert set(output["source_row"]) == set(accepted["source_row"])
    for row in output.select("source_row", "lyric_representative_spotify_id", "lyrics").iter_rows(named=True):
        track = row["lyric_representative_spotify_id"]
        assert row["lyrics"] == content_by_id[track]["lyrics"]
    return output, pl.DataFrame(ledger, infer_schema_length=None).sort("source_row", "spotify_id")


def safe_report_frame(frame):
    frame = frame.drop([c for c in ("lyrics", "lyrics_compare_norm") if c in frame.columns])
    return frame.with_columns([pl.col(c).list.join(" | ") for c, dtype in frame.schema.items() if isinstance(dtype, pl.List)])


def summarize(frame, outcome):
    strict = frame.filter(pl.col("strict_consistency_sample"))
    def outcomes(df):
        return {"positive": df.filter(pl.col(outcome) == 1).height, "negative": df.filter(pl.col(outcome) == 0).height}
    return {"source_records": frame.height, "single_id": int(frame["single_spotify_id"].sum()),
        "multi_id": int((~frame["single_spotify_id"]).sum()),
        "lyrics_consistent": int(frame["lyrics_consistent_across_ids"].sum()),
        "audio_consistent": int(frame["audio_consistent_across_ids"].sum()), "strict_consistency_sample_size": strict.height,
        "lyric_confidence": {level: frame.filter(pl.col("lyric_resolution_confidence") == level).height for level in ("high", "medium", "low")},
        "audio_confidence": {level: frame.filter(pl.col("audio_resolution_confidence") == level).height for level in ("high", "medium", "low")},
        "lyric_group_ties": int(frame["lyric_group_tie"].sum()),
        "unique_plurality_without_majority": int(frame["lyric_unique_plurality_without_majority"].sum()),
        "key_ties": int(frame["key_mode_tie"].sum()), "mode_ties": int(frame["mode_mode_tie"].sum()),
        "any_missing_audio": int(frame["any_missing_audio_value"].sum()),
        "candidate_id_count_distribution": frame.group_by("lyric_candidate_id_count").len().sort("lyric_candidate_id_count").to_dicts(),
        "dominant_lyric_group_share": {"median": frame["dominant_lyric_group_share"].median(), "max": frame["dominant_lyric_group_share"].max()},
        "audio_range_summaries": {c: {"mean": frame[f"{c}_range"].mean(), "median": frame[f"{c}_range"].median(),
            "max": frame[f"{c}_range"].max(), "nonzero_records": int((frame[f"{c}_range"] > 0).sum())} for c in NUMERIC},
        "outcome_field": outcome, "full_sample_outcomes": outcomes(frame), "strict_sample_outcomes": outcomes(strict),
        "low_confidence_review_records": frame.filter((pl.col("lyric_resolution_confidence") == "low") | (pl.col("audio_resolution_confidence") == "low")).height}


def snapshot():
    paths = set((ROOT / "data/interim").glob("*.parquet")) | {p for p in (ROOT / "reports").glob("*") if p.is_file()}
    paths |= {p for folder in ("src", "tests") for p in (ROOT / folder).rglob("*.py")}
    paths.add(ROOT / "README.md")
    excluded = set(OUTPUTS) | {"src/07_consolidate_song_inputs.py", "tests/test_consolidate_song_inputs.py"}
    result = {p.relative_to(ROOT).as_posix(): {"bytes": p.stat().st_size, "mtime_ns": p.stat().st_mtime_ns}
              for p in (ROOT / "data/raw").glob("*.csv")}
    for path in sorted(paths):
        name = path.relative_to(ROOT).as_posix()
        if name not in excluded:
            with path.open("rb") as stream:
                result[name] = {"sha256": hashlib.file_digest(stream, "sha256").hexdigest()}
    return result


DECISIONS = [
    "Comparison text applies only Unicode NFKC, casefold, whitespace collapse and trim. Punctuation, words and repetitions remain. Original raw lyrics are never modified; their original UTF-8 hash is retained.",
    "IDs vote equally for comparison-lyric groups. Choose the largest group; break group ties with the lexicographically smallest ID across tied groups. Within the selected group choose its smallest ID. The ID is a reproducible technical tie-breaker, not evidence of the historically correct chart recording.",
    "A unique largest group without a strict majority (e.g. 2–1–1) has low lyric confidence and an explicit unique-plurality flag. Medium requires >50% support. Missing/blank comparison lyrics are also low confidence. This closes the unspecified non-majority case without changing the requested selection rule.",
    "Audio medians/minima/maxima/ranges use all distinct accepted IDs, never only the lyric group or representative. Missing/nonfinite numeric values are excluded per variable and flagged; all missing yields null. Key/mode are unique modes of original non-null values, with null on ties. Mixed named/numeric text encodings remain distinct; no recoding is performed.",
    "Audio confidence is low for any missing audio or categorical tie, even for one ID; otherwise high for one ID or identical audio, and medium for differing audio. Complete audio consistency requires all fields observed. Full-tuple distinct counts and complete-only distinct counts are both reported.",
    "Strict consistency is one ID OR identical comparison lyrics and one complete audio combination. Thus a single-ID row remains in the strict sample even if its audio is missing, as explicitly specified. The same output rows and flags support later lyrics-only, audio-only and combined models; no model-specific sample is created here.",
    "Metadata/outcomes are attached after content-only consolidation. Outcomes are used only in post-consolidation descriptive counts. All accepted match methods are retained as source-level indicators; no outcome influences an ID vote, tie-break or audio aggregate.",
    "Low-confidence review CSVs contain rows with low lyric OR low audio confidence. The per-candidate lyric ledger and all reports omit both raw lyrics and comparison text; only Parquet contains text. Earlier inputs/reports/code are hashed unchanged, while raw CSVs are not opened and are checked by size/mtime.",
    "No fuzzy matching, NLP feature extraction or model training was performed. Comparison hashes/counts are consolidation diagnostics only. Outputs are consolidated song inputs, not a final joined modelling dataset.",
]


def render(report):
    lines = ["# Song-level input consolidation", "", "Outcome-blind lyric selection and independent audio aggregation.", ""]
    for kind in ("billboard", "grammy"):
        s = report[kind]
        lines += [f"## {kind.title()}", "", f"**{s['source_records']:,} source records**; **{s['strict_consistency_sample_size']:,}** in the strict-consistency sample.",
                  "", "```json", json.dumps(s, indent=2), "```", ""]
    lines += ["## Decisions and interpretation", "", *[f"- {s}" for s in DECISIONS], "", "## Validation", "",
              "```json", json.dumps(report["validation"], indent=2), "```", "", "## Files", "", *[f"- `{p}`" for p in OUTPUTS], "",
              "## Run", "", "```powershell", "uv run python -m unittest discover -s tests -v",
              "uv run python src/07_consolidate_song_inputs.py", "uv run python -m unittest discover -s tests -v", "```", ""]
    return "\n".join(lines)


def main():
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Python 3.12 is required")
    before = snapshot()
    content = comparison_content(pl.read_parquet(ROOT / "data/interim/spotify_accepted_candidate_content.parquet"))
    report, ledgers = {"decisions": DECISIONS, "outputs": OUTPUTS}, []
    for kind, expected, outcome in [("billboard", 6639, "top10"), ("grammy", 111, "grammy_winner")]:
        accepted = pl.read_parquet(ROOT / f"data/interim/{kind}_spotify_accepted_candidates.parquet")
        previous = pl.read_csv(ROOT / f"reports/{kind}_spotify_consolidation_status.csv")
        output, ledger = consolidate_source(accepted, content, kind)
        assert output.height == expected and output["source_row"].n_unique() == expected
        assert set(output["source_row"]) == set(previous["source_row"])
        counts = output.select("source_row", "lyric_candidate_id_count").join(previous.select("source_row", "distinct_spotify_ids"), on="source_row")
        assert counts.select((pl.col("lyric_candidate_id_count") == pl.col("distinct_spotify_ids")).all()).item()
        for field in ("lyric_resolution_confidence", "audio_resolution_confidence"):
            assert output[field].is_in(["high", "medium", "low"]).all()
        path = ROOT / f"data/interim/{kind}_song_level_consolidated.parquet"
        output.write_parquet(path, compression="zstd")
        loaded = pl.read_parquet(path)
        assert loaded.schema == output.schema and loaded.equals(output)
        safe_report_frame(output.filter((pl.col("lyric_resolution_confidence") == "low") | (pl.col("audio_resolution_confidence") == "low"))).write_csv(
            ROOT / f"reports/{kind}_low_confidence_consolidation.csv")
        ledgers.append(ledger)
        report[kind] = summarize(output, outcome)
        print(f"{kind}: {output.height} rows; strict sample {report[kind]['strict_consistency_sample_size']}.", flush=True)
    pl.concat(ledgers, how="vertical_relaxed").write_csv(ROOT / "reports/lyric_selection_ledger.csv")
    after = snapshot()
    if before != after:
        raise RuntimeError("Protected existing files changed")
    report["integrity"] = {"before": before, "after": after}
    report["validation"] = {"unique_source_grains_verified": True, "accepted_sets_fully_represented": True,
        "raw_lyrics_preserved": True, "comparison_did_not_change_original_content": True,
        "prior_candidate_counts_agree": True, "parquet_roundtrips_passed": True,
        "protected_files_unchanged": True, "protected_file_count": len(before), "outcomes_used_only_for_reporting": True,
        "no_fuzzy_matching": True, "no_nlp_feature_extraction": True, "no_modelling": True}
    (ROOT / "reports/song_input_consolidation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (ROOT / "reports/song_input_consolidation.md").write_text(render(report), encoding="utf-8")
    print("Consolidated inputs validated; prior files unchanged.")


if __name__ == "__main__":
    main()
