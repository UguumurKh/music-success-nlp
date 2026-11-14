"""Conservative exact-key candidate audit. Never rank, choose, or fuzzy-match.

Only OUTPUTS may be overwritten. Existing raw data, tables, reports, code,
tests and normalization rules are fingerprinted before and after execution.
"""
import hashlib
import json
from pathlib import Path
import platform
import sys

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ["danceability", "energy", "key", "loudness", "mode", "speechiness",
         "acousticness", "instrumentalness", "liveness", "valence", "tempo", "duration_ms"]
ENRICHMENT = ["performer_extracted", "performer_norm", "performer_parse_success",
              "performer_parse_reason", "title_match_norm", "title_match_changed"]
TABLES = ["grammy_soty_enriched_2000_2024", "billboard_spotify_exact_candidates",
          "grammy_spotify_exact_candidates", "billboard_grammy_exact_candidates"]
REVIEWS = ["billboard_spotify_unmatched", "billboard_spotify_ambiguous",
           "grammy_spotify_unmatched", "grammy_spotify_ambiguous", "billboard_grammy_year_gap_review"]
OUTPUTS = [f"data/interim/{name}.parquet" for name in TABLES] + [f"reports/{name}.csv" for name in REVIEWS] + [
    "reports/exact_match_audit.md", "reports/exact_match_audit.json"]
STATUSES = ["no_exact_candidate", "one_exact_candidate", "multiple_exact_candidates"]


def enrich_grammy(original, audit):
    """Require identical source-row sets, one-to-one joins and unchanged originals."""
    for frame in (original, audit):
        if frame["source_row"].null_count() or frame["source_row"].n_unique() != frame.height:
            raise ValueError("Grammy source_row must be non-null and unique on both sides")
    if set(original["source_row"]) != set(audit["source_row"]):
        raise ValueError("Grammy source_row sets differ")
    # CSV inference need not use the same integer widths as Parquet.
    audit = audit.with_columns(pl.col("source_row").cast(original.schema["source_row"]))
    common = [c for c in original.columns if c in audit.columns]
    reference = original.select(common).sort("source_row")
    observed = audit.select([pl.col(c).cast(original.schema[c]) for c in common]).sort("source_row")
    if not reference.equals(observed):
        raise ValueError("Audited original Grammy fields do not agree with source table")
    enriched = original.join(audit.select("source_row", *ENRICHMENT), on="source_row",
                             how="left", validate="1:1", maintain_order="left")
    if not enriched.select(original.columns).equals(original):
        raise AssertionError("Grammy originals changed during enrichment")
    return enriched


def usable(frame, keys):
    return frame.filter(pl.all_horizontal([pl.col(c).is_not_null() & (pl.col(c).str.strip_chars() != "") for c in keys]))


def prefixed(frame, prefix):
    return frame.rename({c: f"{prefix}_{c}" for c in frame.columns})


def exact_candidates(left, right, left_prefix, right_prefix, left_keys, right_keys):
    """Retain every row pair satisfying both non-empty, unchanged normalized keys."""
    l = prefixed(usable(left, left_keys), left_prefix)
    r = prefixed(usable(right, right_keys), right_prefix)
    return l.join(r, left_on=[f"{left_prefix}_{c}" for c in left_keys],
                  right_on=[f"{right_prefix}_{c}" for c in right_keys], how="inner", coalesce=False)


def spotify_matches(source, spotify, prefix, title_key, artist_key):
    valid_spotify = usable(spotify, ["id"])
    candidates = exact_candidates(source, valid_spotify, prefix, "spotify",
                                  [title_key, artist_key], ["title_norm", "artist_norm"])
    source_id = f"{prefix}_source_row"
    candidates = candidates.sort(source_id, "spotify_id", "spotify_source_row")
    audio_columns = [f"spotify_{c}" for c in AUDIO if c in spotify.columns]
    if not audio_columns:
        raise ValueError("No available audio variables")
    stats = candidates.group_by(source_id).agg(
        pl.col("spotify_id").n_unique().alias("distinct_spotify_ids"),
        pl.len().alias("candidate_rows"),
        pl.col("spotify_lyric_sha256").drop_nulls().n_unique().alias("distinct_lyric_sha256"),
        pl.col("spotify_lyric_sha256").is_null().any().alias("any_missing_lyric_hash"),
        pl.struct(audio_columns).n_unique().alias("distinct_audio_combinations"),
        (pl.col("spotify_lyrics_missing").fill_null(True) | pl.col("spotify_lyrics_blank").fill_null(True)).any().alias("any_missing_or_blank_lyrics"),
        pl.col("spotify_duplicate_id_conflict").any().alias("any_conflicting_spotify_id"),
    ).rename({source_id: "source_row"})
    status = source.join(stats, on="source_row", how="left", validate="1:1", maintain_order="left")
    count_columns = ["distinct_spotify_ids", "candidate_rows", "distinct_lyric_sha256", "distinct_audio_combinations"]
    bool_columns = ["any_missing_lyric_hash", "any_missing_or_blank_lyrics", "any_conflicting_spotify_id"]
    status = status.with_columns([pl.col(c).fill_null(0) for c in count_columns] +
                                 [pl.col(c).fill_null(False) for c in bool_columns])
    status = status.with_columns(pl.when(pl.col("distinct_spotify_ids") == 0).then(pl.lit(STATUSES[0]))
        .when(pl.col("distinct_spotify_ids") == 1).then(pl.lit(STATUSES[1]))
        .otherwise(pl.lit(STATUSES[2])).alias("match_status"))
    assert status.height == source.height and status["source_row"].n_unique() == source.height
    return candidates, status


def billboard_grammy_matches(billboard, grammy):
    pairs = exact_candidates(billboard, grammy, "billboard", "grammy",
                             ["title_norm", "artist_norm"], ["title_match_norm", "performer_norm"])
    pairs = pairs.with_columns(pl.col("billboard_first_chart_date").dt.year().alias("billboard_first_chart_year"),
                               pl.col("grammy_year").alias("grammy_award_year"))
    return pairs.with_columns((pl.col("grammy_award_year") - pl.col("billboard_first_chart_year")).alias("year_gap")).with_columns(
        pl.col("year_gap").is_between(-1, 2).fill_null(False).alias("year_gap_provisionally_plausible")
    ).sort("billboard_source_row", "grammy_source_row")


def coverage(status):
    counts = {value: status.filter(pl.col("match_status") == value).height for value in STATUSES}
    matched = counts[STATUSES[1]] + counts[STATUSES[2]]
    return {"total_records": status.height, **counts, "at_least_one_candidate": matched,
            "coverage_pct": 100 * matched / status.height if status.height else None}


def summarize_spotify(status, split_column, group_labels, title, artist):
    multiple = status.filter(pl.col("match_status") == STATUSES[2])
    example_cols = ["source_row", title, artist, "match_status", "distinct_spotify_ids", "candidate_rows",
                    "distinct_lyric_sha256", "distinct_audio_combinations", "any_missing_or_blank_lyrics"]
    result = {"coverage": coverage(status), "subgroups": {
        label: coverage(status.filter(pl.col(split_column) == value)) for value, label in group_labels},
        "candidate_count_distribution": status.group_by("distinct_spotify_ids").len(name="source_records").sort("distinct_spotify_ids").to_dicts(),
        "ambiguity_diagnostics": {
            "same_known_lyric_hash": multiple.filter((pl.col("distinct_lyric_sha256") == 1) & ~pl.col("any_missing_lyric_hash")).height,
            "different_known_lyric_hashes": multiple.filter(pl.col("distinct_lyric_sha256") > 1).height,
            "any_unknown_lyric_hash": multiple.filter(pl.col("any_missing_lyric_hash")).height,
            "same_audio_combination": multiple.filter(pl.col("distinct_audio_combinations") == 1).height,
            "different_audio_combinations": multiple.filter(pl.col("distinct_audio_combinations") > 1).height,
            "any_missing_or_blank_lyrics": multiple.filter(pl.col("any_missing_or_blank_lyrics")).height,
            "any_conflicting_spotify_id": status.filter(pl.col("any_conflicting_spotify_id")).height},
        "ambiguous_examples": multiple.sort("distinct_spotify_ids", "source_row", descending=[True, False]).head(5).select(example_cols).to_dicts(),
        "unmatched_examples": status.filter(pl.col("match_status") == STATUSES[0]).head(5).select(example_cols).to_dicts()}
    # Durable, exhaustive source-level accounting, including all zero-candidate records.
    result["all_source_match_statuses"] = status.select(example_cols + ["any_missing_lyric_hash", "any_conflicting_spotify_id"]).to_dicts()
    return result


WARNINGS = [
    "Exact-match coverage is not final match coverage. Unmatched does not mean the song is absent from Spotify.",
    "Artist formatting, collaborations, featured artists and version labels can prevent exact matches. Existing normalization rules were not changed; blank/null keys never match.",
    "Several Spotify IDs may represent releases, remasters, albums or duplicates of the same recording. All candidate rows are retained, even when lyrics or audio agree. One exact ID is a candidate, not a verified recording match.",
    "Match rates may differ between successful and less-successful songs, creating selection bias in the final analytical sample. Top 10 and Grammy winner variables are used only for coverage diagnostics; no outcome variable may be used to choose among candidates.",
    "Distinct ID counts determine status, not joined row counts. Conflicting records sharing an ID remain present and flagged. Spotify rows with missing/blank IDs cannot count as track candidates and are explicitly counted as excluded.",
    "Lyric hash counts exclude nulls; any missing hash is reported separately. Same known hash means identical hashed content, not verified song identity. Audio combinations compare all available original values, including text key/mode and null patterns, without tolerance or recoding.",
    "Billboard source_row is a new 1-based position in the unchanged source Parquet. It is not a raw weekly CSV row number. Sing and Sing! remain distinct source records even though their normalized keys collide.",
    "Billboard–Grammy candidates have no year restriction. Gaps -1 through +2 are only provisionally plausible; other pairs remain in the complete candidate table and are exported for review.",
    "No fuzzy matching, automatic candidate selection, record merging or final modelling dataset was created.",
]


def protected_hashes():
    paths = set((ROOT / "data/raw").glob("*.csv")) | set((ROOT / "data/interim").glob("*.parquet"))
    paths |= {p for p in (ROOT / "reports").iterdir() if p.is_file()}
    paths |= {p for folder in ("src", "tests") for p in (ROOT / folder).rglob("*.py")}
    paths.add(ROOT / "README.md")
    excluded = set(OUTPUTS) | {"src/03_exact_match_audit.py", "tests/test_exact_match_audit.py"}
    result = {}
    for path in sorted(paths):
        relative = path.relative_to(ROOT).as_posix()
        if relative not in excluded:
            with path.open("rb") as stream:
                result[relative] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


def save_parquet(frame, stem):
    path = ROOT / f"data/interim/{stem}.parquet"
    frame.write_parquet(path, compression="zstd")
    loaded = pl.read_parquet(path)
    if frame.schema != loaded.schema or not frame.equals(loaded):
        raise AssertionError(f"Parquet round-trip failed: {stem}")


def render(report):
    lines = ["# Conservative exact-match audit", "", "Candidate generation only; no selection, merging or fuzzy matching.", ""]
    for name in ("billboard_spotify", "grammy_spotify"):
        section = report[name]
        lines += [f"## {name.replace('_', '–').title()}", "",
            "| Group | Source records | At least one | One ID | Multiple IDs | Unmatched | Coverage % |",
            "|---|---:|---:|---:|---:|---:|---:|"]
        for label, c in [("All", section["coverage"]), *section["subgroups"].items()]:
            percentage = f"{c['coverage_pct']:.2f}" if c["coverage_pct"] is not None else "n/a"
            lines.append(f"| {label} | {c['total_records']} | {c['at_least_one_candidate']} | {c[STATUSES[1]]} | {c[STATUSES[2]]} | {c[STATUSES[0]]} | {percentage} |")
        for title, key in [("Candidate-count distribution", "candidate_count_distribution"),
                           ("Ambiguity diagnostics", "ambiguity_diagnostics"),
                           ("Ambiguous examples", "ambiguous_examples"), ("Unmatched examples", "unmatched_examples")]:
            lines += ["", f"### {title}", "", "```json", json.dumps(section[key], ensure_ascii=False, indent=2), "```"]
    lines += ["", "## Billboard–Grammy", "", "```json", json.dumps(report["billboard_grammy"], ensure_ascii=False, indent=2), "```",
              "", "## Methodological warnings", "", *[f"- {s}" for s in WARNINGS], "",
              "## Validation", "", "```json", json.dumps(report["validation"], indent=2), "```", "",
              "Every Billboard and Grammy source record has a match status in the JSON report. "
              "Candidate Parquet files contain every matching pair with source-prefixed columns, including both matching keys. "
              "Unmatched/ambiguous CSVs contain complete source metadata and counts; no full lyrics are included.", "",
              "## New outputs", "", *[f"- `{p}`" for p in OUTPUTS], "", "## Run", "", "```powershell",
              "uv run python -m unittest discover -s tests -v", "uv run python src/03_exact_match_audit.py",
              "uv run python -m unittest discover -s tests -v", "```", ""]
    return "\n".join(lines)


def main():
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Python 3.12 is required")
    before = protected_hashes()
    b = pl.read_parquet(ROOT / "data/interim/billboard_song_level_2000_2024.parquet").with_row_index("source_row", offset=1)
    original_g = pl.read_parquet(ROOT / "data/interim/grammy_soty_2000_2024.parquet")
    audit = pl.read_csv(ROOT / "reports/grammy_performer_parse_audit.csv", infer_schema_length=None)
    g = enrich_grammy(original_g, audit)
    assert g.height == 150 and g["performer_parse_success"].all()
    s = pl.read_parquet(ROOT / "data/interim/spotify_track_index.parquet")
    print("Building all exact-key candidate pairs...", flush=True)
    bs, b_status = spotify_matches(b, s, "billboard", "title_norm", "artist_norm")
    gs, g_status = spotify_matches(g, s, "grammy", "title_match_norm", "performer_norm")
    bg = billboard_grammy_matches(b, g)
    # Validate rules independently on the materialized candidate tables.
    for pairs, prefix, title, artist, right in [(bs, "billboard", "title_norm", "artist_norm", "spotify"),
        (gs, "grammy", "title_match_norm", "performer_norm", "spotify"),
        (bg, "billboard", "title_norm", "artist_norm", "grammy")]:
        rt, ra = ("title_norm", "artist_norm") if right == "spotify" else ("title_match_norm", "performer_norm")
        assert pairs.select((pl.col(f"{prefix}_{title}") == pl.col(f"{right}_{rt}")).all()).item()
        assert pairs.select((pl.col(f"{prefix}_{artist}") == pl.col(f"{right}_{ra}")).all()).item()
    for pairs, status, prefix in [(bs, b_status, "billboard"), (gs, g_status, "grammy")]:
        distinct = pairs.select(f"{prefix}_source_row", "spotify_id").unique().height
        assert status["distinct_spotify_ids"].sum() == distinct
        assert status["candidate_rows"].sum() == pairs.height
        assert status["match_status"].is_in(STATUSES).all()
    sing = b_status.filter((pl.col("title_norm") == "sing") & (pl.col("artist_norm") == "glee cast"))
    assert set(sing["Song"]) == {"Sing", "Sing!"} and sing["source_row"].n_unique() == 2
    for frame, stem in zip([g, bs, gs, bg], TABLES):
        save_parquet(frame, stem)
    for prefix, status in [("billboard", b_status), ("grammy", g_status)]:
        for label, state in [("unmatched", STATUSES[0]), ("ambiguous", STATUSES[2])]:
            status.filter(pl.col("match_status") == state).write_csv(ROOT / f"reports/{prefix}_spotify_{label}.csv")
    unusual = bg.filter(~pl.col("year_gap_provisionally_plausible"))
    unusual.write_csv(ROOT / "reports/billboard_grammy_year_gap_review.csv")
    b_degrees = bg.group_by("billboard_source_row").agg(pl.col("grammy_source_row").n_unique().alias("grammy_records"))
    g_degrees = bg.group_by("grammy_source_row").agg(pl.col("billboard_source_row").n_unique().alias("billboard_songs"))
    ambiguous_pairs = bg.join(b_degrees, on="billboard_source_row").join(g_degrees, on="grammy_source_row").filter(
        (pl.col("grammy_records") > 1) | (pl.col("billboard_songs") > 1))
    report = {"runtime": {"python": platform.python_version(), "polars": pl.__version__},
        "billboard_spotify": summarize_spotify(b_status, "top10", [(1, "Top 10"), (0, "Non-Top-10")], "Song", "Artist"),
        "grammy_spotify": summarize_spotify(g_status, "grammy_winner", [(1, "Winners"), (0, "Non-winning nominees")], "song_or_album", "performer_extracted"),
        "billboard_grammy": {"candidate_pairs": bg.height, "distinct_billboard_songs": bg["billboard_source_row"].n_unique(),
            "distinct_grammy_records": bg["grammy_source_row"].n_unique(),
            "year_gap_distribution": bg.group_by("year_gap").len(name="candidate_pairs").sort("year_gap").to_dicts(),
            "inside_provisional_range": bg.height - unusual.height, "outside_provisional_range": unusual.height,
            "billboard_songs_with_multiple_grammy_records": b_degrees.filter(pl.col("grammy_records") > 1).height,
            "grammy_records_with_multiple_billboard_songs": g_degrees.filter(pl.col("billboard_songs") > 1).height,
            "ambiguous_pair_count": ambiguous_pairs.height,
            "many_to_many_pair_count": ambiguous_pairs.filter((pl.col("grammy_records") > 1) & (pl.col("billboard_songs") > 1)).height,
            "ambiguous_examples": ambiguous_pairs.select("billboard_source_row", "billboard_Song", "billboard_Artist", "grammy_source_row", "grammy_year", "year_gap").head(10).to_dicts()},
        "warnings": WARNINGS, "outputs": OUTPUTS,
        "validation": {"grammy_rows_preserved": g.height, "grammy_original_values_unchanged": True,
            "all_source_records_classified": True, "distinct_id_counts_validated": True, "exact_keys_validated": True,
            "all_candidate_rows_retained": True, "parquet_roundtrips_passed": True,
            "sing_records_separate": True, "spotify_rows_excluded_missing_or_blank_id": s.height - usable(s, ["id"]).height,
            "available_audio_variables": [c for c in AUDIO if c in s.columns],
            "fuzzy_matching_performed": False, "automatic_candidate_selection_performed": False}}
    after = protected_hashes()
    if before != after:
        raise RuntimeError("A protected existing file changed during audit")
    report["integrity"] = {"before": before, "after": after}
    report["validation"].update(protected_files_unchanged=True, protected_file_count=len(before))
    (ROOT / "reports/exact_match_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str, allow_nan=False) + "\n", encoding="utf-8")
    (ROOT / "reports/exact_match_audit.md").write_text(render(report), encoding="utf-8")
    print(json.dumps({name: report[name]["coverage"] for name in ("billboard_spotify", "grammy_spotify")}, indent=2))
    print(f"Billboard–Grammy: {bg.height} pairs, {unusual.height} unusual year gaps. All {len(before)} protected files unchanged.")


if __name__ == "__main__":
    main()
