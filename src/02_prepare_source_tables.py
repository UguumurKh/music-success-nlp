"""Phase 2A: prepare separate source tables; never match sources or model.

Strict parsing, immutable raw inputs, conservative keys and auditable exclusions.
Spotify lyrics are scanned to compute counts and SHA-256, then immediately
projected away. Only its metadata index is collected into memory. If duplicated
IDs exist, exact equality of their original fields (including lyrics) is checked
in a second, filtered scan; hashes alone never authorize deletion.
"""
from __future__ import annotations

from datetime import date
import hashlib
import json
import platform
from pathlib import Path
import sys

import polars as pl

from music_success_nlp.normalization import add_normalized_fields

ROOT = Path(__file__).resolve().parents[1]
START, END = date(2000, 1, 1), date(2024, 12, 31)
SOURCE_ROW = "source_row"  # 1-based CSV data-record number, not physical line.


def collect(frame):
    return frame.collect(engine="streaming")


def fingerprint(path):
    with path.open("rb") as stream:
        sha = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"size_bytes": path.stat().st_size, "sha256": sha}


def pct(n, total):
    return 100 * n / total if total else None


def unusable(column):
    return pl.col(column).is_null() | (pl.col(column).str.strip_chars() == "")


def completeness(frame, title, artist):
    return frame.select([
        expr.alias(f"{label}_{suffix}")
        for label, column in [("title", title), ("artist", artist)]
        for suffix, expr in [("null", pl.col(column).is_null().sum()),
                             ("blank", (pl.col(column).str.strip_chars() == "").sum()),
                             ("unusable_normalized", unusable(f"{label}_norm").sum())]
    ]).row(0, named=True)


def exact_deduplicate(frame):
    """Retain first source occurrence only when every original value agrees."""
    columns = [c for c in frame.columns if c != SOURCE_ROW]
    kept = frame.unique(subset=columns, keep="first", maintain_order=True)
    removed = frame.join(kept.select(SOURCE_ROW), on=SOURCE_ROW, how="anti")
    return kept, removed


def ledger(frame, reason):
    return frame.select(SOURCE_ROW).with_columns(pl.lit(reason).alias("reason"))


def prepare_billboard(raw):
    original_count = raw.height
    original_counts = raw.group_by(["Song", "Artist"]).len(name="raw_weekly_records")
    unique, removed = exact_deduplicate(raw)
    unique = unique.with_columns(pl.col("Date").str.strptime(pl.Date, "%Y-%m-%d", strict=True))
    keys = ["Date", "Song", "Artist"]
    duplicate_keys = unique.group_by(keys).len().filter(pl.col("len") > 1)
    review = unique.join(duplicate_keys.select(keys), on=keys, how="inner", nulls_equal=True)
    review = review.with_columns(pl.lit("Unresolved non-identical weekly records; entire raw song–artist quarantined").alias("review_reason")).sort(keys + [SOURCE_ROW])
    # Treat differences in any source column conservatively, including Image URL.
    conflict_songs = review.select("Song", "Artist").unique()
    quarantine = unique.join(conflict_songs, on=["Song", "Artist"], how="semi", nulls_equal=True)
    safe = unique.join(conflict_songs, on=["Song", "Artist"], how="anti", nulls_equal=True)
    invalid = safe.filter(unusable("Song") | unusable("Artist") | pl.col("Date").is_null()
                          | pl.col("Rank").is_null() | ~pl.col("Rank").is_between(1, 100))
    invalid_songs = invalid.select("Song", "Artist").unique()
    invalid_quarantine = safe.join(invalid_songs, on=["Song", "Artist"], how="semi", nulls_equal=True)
    safe = safe.join(invalid_songs, on=["Song", "Artist"], how="anti", nulls_equal=True)
    songs = safe.group_by(["Song", "Artist"]).agg(
        pl.col("Date").min().alias("first_chart_date"),
        pl.col("Date").max().alias("last_chart_date"),
        pl.col("Date").n_unique().alias("chart_weeks"),
        pl.col("Rank").min().alias("peak_rank"),
        pl.len().alias("weekly_records_after_exact_dedup"),
    ).join(original_counts, on=["Song", "Artist"], how="left", validate="1:1")
    songs = songs.with_columns((pl.col("peak_rank") <= 10).cast(pl.Int8).alias("top10"),
                               (pl.col("peak_rank") == 1).cast(pl.Int8).alias("number_one"))
    in_period = pl.col("first_chart_date").is_between(START, END)
    excluded_songs = songs.filter(~in_period)
    out_of_period = safe.join(excluded_songs.select("Song", "Artist"), on=["Song", "Artist"], how="semi")
    output = add_normalized_fields(songs.filter(in_period), "Song", "Artist").sort("Song", "Artist")
    exclusions = pl.concat([ledger(removed, "exact_duplicate"), ledger(quarantine, "unresolved_song_conflict"),
        ledger(invalid_quarantine, "song_with_invalid_required_field"), ledger(out_of_period, "first_chart_date_outside_2000_2024")]).sort(SOURCE_ROW)
    stats = {"input_rows": original_count, "output_rows": output.height,
        "exact_duplicates_removed": removed.height, "unresolved_duplicate_groups": duplicate_keys.height,
        "unresolved_duplicate_rows": review.height, "quarantined_song_count": conflict_songs.height,
        "quarantined_weekly_rows": quarantine.height, "invalid_quarantined_rows": invalid_quarantine.height,
        "songs_before_period_filter": songs.height, "songs_excluded_by_first_chart_date": excluded_songs.height,
        "weekly_rows_excluded_by_first_chart_date": out_of_period.height,
        "weekly_rows_represented_in_output": int(output["weekly_records_after_exact_dedup"].sum()),
        "top10_songs": int(output["top10"].sum()), "top10_pct": pct(output["top10"].sum(), output.height),
        "chart_weeks": {"mean": output["chart_weeks"].mean(), "median": output["chart_weeks"].median(),
                        "min": output["chart_weeks"].min(), "max": output["chart_weeks"].max()},
        "missingness": completeness(output, "Song", "Artist")}
    assert stats["input_rows"] == exclusions.height + stats["weekly_rows_represented_in_output"]
    return output, review, exclusions, stats


def prepare_grammy(raw):
    unique, removed = exact_deduplicate(raw)
    soty = unique.filter(pl.col("award") == "Song Of The Year")
    output = soty.filter(pl.col("year").is_between(2000, 2024)).with_columns(
        pl.lit(1, dtype=pl.Int8).alias("grammy_nominated"),
        pl.col("winner").cast(pl.Int8).alias("grammy_winner"))
    output = add_normalized_fields(output, "song_or_album", "artist").sort("year", SOURCE_ROW)
    # Absent artists are not inferred, including whitespace-only source values.
    output = output.with_columns(pl.when(unusable("artist")).then(None)
                                 .otherwise(pl.col("artist_norm")).alias("artist_norm"))
    review = output.with_columns(unusable("artist").alias("performer_review_required"))
    exclusions = pl.concat([ledger(removed, "exact_duplicate"),
        ledger(unique.filter((pl.col("award") != "Song Of The Year").fill_null(True)), "other_or_missing_award"),
        ledger(soty.filter((~pl.col("year").is_between(2000, 2024)).fill_null(True)), "award_year_outside_2000_2024_or_missing")]).sort(SOURCE_ROW)
    repeated = output.group_by("year", "song_or_album", "artist").len().filter(pl.col("len") > 1)
    stats = {"input_rows": raw.height, "output_rows": output.height, "exact_duplicates_removed": removed.height,
        "other_award_rows_excluded": unique.height - soty.height,
        "out_of_period_soty_rows_excluded": soty.height - output.height,
        "nominee_records_including_winners": output.height, "winner_records": int(output["grammy_winner"].sum()),
        "winner_missing": output["winner"].null_count(), "performer_review_required": int(review["performer_review_required"].sum()),
        "unresolved_year_title_artist_groups": repeated.height, "missingness": completeness(output, "song_or_album", "artist")}
    assert raw.height == output.height + exclusions.height
    return output, review, exclusions, stats


def lyric_hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value is not None else None


def prepare_spotify(raw):
    columns = raw.collect_schema().names()
    if SOURCE_ROW not in columns:
        raise ValueError("Spotify input requires a source_row record number")
    projected = raw.with_columns(
        pl.col("lyrics").is_null().alias("lyrics_missing"),
        (pl.col("lyrics").str.strip_chars() == "").fill_null(False).alias("lyrics_blank"),
        pl.col("lyrics").str.count_matches(r"\S+").alias("lyric_word_count"),
        pl.col("lyrics").map_elements(lyric_hash, return_dtype=pl.String).alias("lyric_sha256"),
    ).drop("lyrics")
    index = collect(add_normalized_fields(projected, "name", "artists"))
    valid = index.filter(~unusable("id"))
    repeated_ids = valid.group_by("id").len().filter(pl.col("len") > 1)
    review = index.join(repeated_ids.select("id"), on="id", how="inner")
    removed_rows = pl.DataFrame({SOURCE_ROW: []}, schema={SOURCE_ROW: index.schema[SOURCE_ROW]})
    if repeated_ids.height:
        # Exact raw-field equality, including the actual lyric string, resolves
        # equivalence. No full lyrics leave this transient duplicate subset.
        duplicates_raw = collect(raw.filter(pl.col("id").is_in(repeated_ids["id"].implode())))
        _, removed = exact_deduplicate(duplicates_raw.sort(SOURCE_ROW))
        removed_rows = removed.select(SOURCE_ROW)
    index = index.join(removed_rows, on=SOURCE_ROW, how="anti")
    conflict_ids = index.filter(~unusable("id")).group_by("id").len().filter(pl.col("len") > 1).select("id")
    index = index.with_columns(
        pl.col("id").is_in(conflict_ids["id"].implode()).fill_null(False).alias("duplicate_id_conflict"),
        unusable("id").alias("id_unusable"))
    review = review.with_columns(
        pl.col(SOURCE_ROW).is_in(removed_rows[SOURCE_ROW].implode()).alias("removed_as_exact_duplicate"),
        pl.col("id").is_in(conflict_ids["id"].implode()).alias("duplicate_id_conflict")).sort("id", SOURCE_ROW)
    exclusions = ledger(removed_rows, "equivalent_duplicate_id")
    stats = {"input_rows": index.height + removed_rows.height, "output_rows": index.height,
        "exact_duplicates_removed": removed_rows.height, "duplicate_id_groups_before_dedup": repeated_ids.height,
        "duplicate_id_rows_before_dedup": review.height,
        "duplicate_id_excess_before_dedup": int((repeated_ids["len"] - 1).sum()),
        "unresolved_duplicate_id_groups": conflict_ids.height,
        "unresolved_duplicate_id_rows": int(index["duplicate_id_conflict"].sum()),
        "unusable_ids": int(index["id_unusable"].sum()),
        "lyrics_missing": int(index["lyrics_missing"].sum()), "lyrics_blank": int(index["lyrics_blank"].sum()),
        "missingness": completeness(index, "name", "artists")}
    return index.sort(SOURCE_ROW), review, exclusions, stats


def collision_reports(frame, title, artist, prefix, reports):
    """Report field and composite collisions; no list-valued CSV cells or merging."""
    result = {}
    for label, raw_cols, keys in [("title", [title], ["title_norm"]),
                                  ("artist", [artist], ["artist_norm"]),
                                  ("title_artist", [title, artist], ["title_norm", "artist_norm"])]:
        valid = frame.filter(~pl.any_horizontal([unusable(k) for k in keys]))
        counts = valid.group_by(keys).agg(pl.struct(raw_cols).n_unique().alias("distinct_raw_values"),
                                         pl.len().alias("source_records"))
        collisions = counts.filter(pl.col("distinct_raw_values") > 1)
        detail = valid.select(keys + raw_cols).unique().join(collisions, on=keys, how="inner").sort(keys + raw_cols)
        filename = f"{prefix}_{label}_normalization_collisions.csv"
        detail.write_csv(reports / filename)
        result[label] = {"collision_groups": collisions.height,
            "affected_records": int(collisions["source_records"].sum()),
            "distinct_raw_variants": detail.height, "review_file": f"reports/{filename}"}
    return result


DECISIONS = [
    "Strict UTF-8 parsing uses the profiled schemas; Billboard Weeks in Charts remains text to preserve '-'. No parse errors are ignored.",
    "source_row is the 1-based data-record number (header excluded, multiline CSV records counted once). Exclusion ledgers list every removed source record and reason.",
    "All raw title/artist columns survive unchanged. Normalization lowercases, uses unidecode, normalizes quotes, replaces punctuation with spaces and collapses whitespace. Version words and artist ordering remain. No base-title key is used.",
    "Normalization collision reports cover each final source table separately, exclude missing/empty normalized keys, and distinguish raw spelling collisions from repeated versions. No normalization collision is resolved automatically.",
    "Billboard removes only fully identical rows, then quarantines entire raw song–artist histories with any non-identical duplicate date key or invalid required field. This avoids shifting first-chart dates or undercounting histories. Duplicate review exports all conflicting rows, even outside the target period.",
    "Billboard aggregates raw Song/Artist across all available dates before filtering first_chart_date to 2000–2024. Chart weeks count distinct dates. Outcomes include subsequent observed weeks through the source end, including after 2024; histories near the source end may be right-censored. raw_weekly_records includes any original exact duplicates, while weekly_records_after_exact_dedup does not.",
    "Grammy exact duplicates are removed before selecting Song Of The Year and award years 2000–2024. Nominees are nomination records including winners. All source columns survive; artists are never inferred from contributors. Every retained nomination is exported for performer review.",
    "Spotify has no year filter. All source metadata/audio values retain their types and values, including mixed text key/mode coding. Lyrics are neither normalized nor stored; only missing/blank flags, whitespace word count and SHA-256 of the exact UTF-8 content are retained. Null lyrics have null count/hash; blanks have zero words.",
    "Spotify duplicate IDs are compared on all original fields, including exact lyric text in a filtered duplicate-only scan. Only equivalent copies are removed. Conflicting IDs remain flagged; absent/blank IDs remain flagged and are never treated as an identity for deduplication.",
    "No cross-source matching, fuzzy matching, NLP feature extraction beyond the requested lyric word count/hash, or modelling has been performed.",
]


def render(report):
    lines = ["# Phase 2A preparation summary", "", "Three separate standardized source tables; no dataset matching.", "",
        "## Row accounting", "", "| Source | Input records | Output records | Exact duplicates removed |",
        "|---|---:|---:|---:|"]
    for name, stats in report["datasets"].items():
        lines.append(f"| {name} | {stats['input_rows']:,} | {stats['output_rows']:,} | {stats['exact_duplicates_removed']:,} |")
    lines += ["", "Output grain: Billboard raw song–artist; Grammy nomination; Spotify track record (conflicting IDs retained if present).", ""]
    b, g, s = (report["datasets"][name] for name in ("Billboard", "Grammy", "Spotify"))
    lines += ["## Main findings", "",
        f"- Billboard retains {b['output_rows']:,} songs first charting in 2000–2024. "
        f"{b['top10_songs']:,} ({b['top10_pct']:.2f}%) reached the Top 10. "
        f"Chart weeks: mean {b['chart_weeks']['mean']:.2f}, median {b['chart_weeks']['median']}, "
        f"range {b['chart_weeks']['min']}–{b['chart_weeks']['max']}.",
        f"- Billboard's {b['unresolved_duplicate_groups']} conflicting weekly keys involve "
        f"{b['unresolved_duplicate_rows']} records; {b['quarantined_song_count']} entire raw song–artist history "
        f"({b['quarantined_weekly_rows']} weekly records) is quarantined.",
        f"- Grammy retains {g['nominee_records_including_winners']} nominations including {g['winner_records']} winners. "
        f"{g['performer_review_required']} retained records need performer review; no identities were inferred.",
        f"- Spotify has {s['duplicate_id_groups_before_dedup']} duplicate ID groups. "
        f"{s['multiple_version_normalized_groups']:,} normalized title–artist keys span multiple IDs "
        f"({s['multiple_version_records']:,} records); these remain separate.",
        f"- Composite normalization collisions: Billboard {b['normalization_collisions']['title_artist']['collision_groups']:,}, "
        f"Grammy {g['normalization_collisions']['title_artist']['collision_groups']:,}, "
        f"Spotify {s['normalization_collisions']['title_artist']['collision_groups']:,}. "
        "Grammy's zero does not imply usable keys: missing artist keys are excluded from collision checks.",
        f"- Spotify has {s['missingness']['title_unusable_normalized']} unusable normalized titles and "
        f"{s['missingness']['artist_unusable_normalized']} unusable normalized artists, including "
        "punctuation/symbol-only or untranslated values. Original text is retained for review.", ""]
    for name, stats in report["datasets"].items():
        lines += [f"## {name}", "", "```json", json.dumps(stats, indent=2), "```", ""]
    lines += ["## Decisions", "", *[f"- {s}" for s in report["decisions"]], "", "## Unresolved risks", "",
              *[f"- {s}" for s in report["risks"]], "", "## Validation and raw-file integrity", "",
              "```json", json.dumps(report["validation"], indent=2), "```", "", "## Files produced", "",
              *[f"- `{s}`" for s in report["outputs"]], "", "## Rerun", "", "```powershell",
              "uv run python -m unittest discover -s tests -v", "uv run python src/02_prepare_source_tables.py", "```", ""]
    return "\n".join(lines)


def main():
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Python 3.12 is required")
    profile = json.loads((ROOT / "reports/raw_profile.json").read_text(encoding="utf-8"))
    reports, interim = ROOT / "reports", ROOT / "data/interim"
    reports.mkdir(exist_ok=True)
    interim.mkdir(exist_ok=True)
    before = {name: fingerprint(ROOT / d["path"]) for name, d in profile["datasets"].items()}
    if any(before[name] != d["after"] for name, d in profile["datasets"].items()):
        raise RuntimeError("Raw inputs differ from the completed profile; reprofile before preparation")
    result = {"runtime": {"python": platform.python_version(), "polars": pl.__version__},
              "datasets": {}, "decisions": DECISIONS, "risks": [
        "Billboard conflicting weekly records require manual review; raw song–artist strings can still combine different recordings or split spelling variants.",
        "Grammy performer identities may be absent while contributors are present. No performer inference is authorized yet.",
        "Spotify normalized keys often represent multiple track IDs/versions; neither normalized equality nor lyric-hash equality proves identity.",
        "Spotify cannot be limited to 2000–2024 from this metadata. Named/numeric key and mode encodings and profiled loudness outliers are preserved for later review.",
        "Normalization is lossy; missing/empty normalized keys are not usable matching keys. Collision files are review evidence, never merge instructions."],
        "outputs": [], "validation": {"before": before}}
    names = {"Billboard": (prepare_billboard, "billboard_song_level_2000_2024", "Song", "Artist", "billboard_duplicate_review"),
             "Grammy": (prepare_grammy, "grammy_soty_2000_2024", "song_or_album", "artist", "grammy_performer_review"),
             "Spotify": (prepare_spotify, "spotify_track_index", "name", "artists", "spotify_duplicate_id_review")}
    for name, (prepare, stem, title, artist, review_stem) in names.items():
        print(f"Preparing {name}...", flush=True)
        d = profile["datasets"][name]
        schema = {c["name"]: getattr(pl, c["dtype"]) for c in d["profile"]["columns"]}
        raw = pl.scan_csv(ROOT / d["path"], schema_overrides=schema, ignore_errors=False,
                          encoding="utf8", row_index_name=SOURCE_ROW, row_index_offset=1)
        output, review, exclusions, stats = prepare(raw if name == "Spotify" else collect(raw))
        assert stats["input_rows"] == d["profile"]["rows"], f"Input count mismatch: {name}"
        parquet = interim / f"{stem}.parquet"
        output.write_parquet(parquet, compression="zstd")
        assert pl.read_parquet(parquet).equals(output), f"Parquet roundtrip mismatch: {name}"
        assert "lyrics" not in output.columns and "lyrics" not in review.columns
        review.write_csv(reports / f"{review_stem}.csv")
        prefix = name.lower()
        exclusions.write_csv(reports / f"{prefix}_exclusions.csv")
        stats["normalization_collisions"] = collision_reports(output, title, artist, prefix, reports)
        if name == "Spotify":
            keys = ["title_norm", "artist_norm"]
            versions = output.filter(~unusable("title_norm") & ~unusable("artist_norm")).group_by(keys).agg(
                pl.len().alias("track_records"), pl.col("id").drop_nulls().n_unique().alias("distinct_track_ids"))
            versions = versions.filter(pl.col("distinct_track_ids") > 1)
            detail = output.join(versions, on=keys, how="inner").sort(keys + ["id", SOURCE_ROW])
            detail.write_csv(reports / "spotify_multiple_versions_review.csv")
            stats["multiple_version_normalized_groups"] = versions.height
            stats["multiple_version_records"] = detail.height
            result["outputs"].append("reports/spotify_multiple_versions_review.csv")
        stats["exclusion_records"] = exclusions.height
        stats["output_columns"] = {c: str(t) for c, t in output.schema.items()}
        result["datasets"][name] = stats
        result["outputs"] += [parquet.relative_to(ROOT).as_posix(), f"reports/{review_stem}.csv", f"reports/{prefix}_exclusions.csv"]
        result["outputs"] += [v["review_file"] for v in stats["normalization_collisions"].values()]
        print(f"{name}: {stats['input_rows']:,} input -> {stats['output_rows']:,} output records.", flush=True)
    after = {name: fingerprint(ROOT / d["path"]) for name, d in profile["datasets"].items()}
    result["validation"].update(after=after, raw_unchanged=before == after,
        matches_profile_fingerprints=True, parquet_roundtrips_passed=True,
        input_count_checks_passed=True, exclusion_accounting_passed=True,
        lyrics_excluded_from_outputs=True)
    if before != after:
        raise RuntimeError("Raw files changed during preparation")
    result["outputs"] += ["reports/preparation_summary.md", "reports/preparation_summary.json"]
    (reports / "preparation_summary.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    (reports / "preparation_summary.md").write_text(render(result), encoding="utf-8")
    print("Saved and validated all three source tables; raw SHA-256 fingerprints unchanged.")


if __name__ == "__main__":
    main()
