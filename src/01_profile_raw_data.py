"""Read-only raw CSV profiling. Run with Python 3.12 and the locked Polars version.

No normalization, matching, cleaned datasets, or song-level aggregation is produced.
All collect calls use the streaming engine; only small outputs, keys/counts and
the numeric lyric-length vector are retained. Raw lyrics are never serialized.
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
FILES = {"Spotify": "songs_with_attributes_and_lyrics.csv",
         "Billboard": "hot100.csv", "Grammy": "grammies_v4.csv"}
SOURCE = "https://developer.spotify.com/documentation/web-api/reference/get-audio-features"
# Lossless override established from a failed strict full-file scan. Keep '-'
# as text, not null; do not discard records or alter the CSV.
OVERRIDES = {"Billboard": {"Weeks in Charts": pl.String}}
ORIGINAL_BILLBOARD_ERROR = """could not parse `-` as dtype `i64` at column 'Weeks in Charts' (column number 7)

The current offset in the file is 516466 bytes.

You might want to try:
- increasing `infer_schema_length` (e.g. `infer_schema_length=10000`),
- increasing `infer_schema_files` (e.g. `infer_schema_files=50`),
- specifying correct dtype with the `schema_overrides` argument
- setting `ignore_errors` to `True`,
- adding `-` to the `null_values` list.

Original error: ```invalid primitive value found during CSV parsing```"""


def collect(frame):
    return frame.collect(engine="streaming")


def summary(frame, expressions):
    return collect(frame.select(expressions)).row(0, named=True)


def fingerprint(path):
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"size_bytes": path.stat().st_size, "sha256": digest}


def pct(n, total):
    return 100 * n / total if total else None


def examples(frame, schema):
    # Omit even short lyrics, so a short complete lyric can never leak.
    return collect(frame.select([
        pl.lit("[lyrics omitted]").alias(c) if "lyric" in c.lower()
        else pl.when(pl.col(c).str.len_chars() > 200)
        .then(pl.col(c).str.slice(0, 197).add("...")).otherwise(pl.col(c)).alias(c)
        if dtype == pl.String else pl.col(c)
        for c, dtype in schema.items()
    ]).head(5)).to_dicts()


def duplicates(frame, keys):
    # Raw values: no casing, punctuation, whitespace or artist-list changes.
    counts = frame.group_by(keys).len()
    result = summary(counts, [pl.len().alias("unique_combinations_including_null"),
        (pl.col("len") - 1).sum().alias("duplicate_excess_rows"),
        (pl.col("len") > 1).sum().alias("duplicated_key_groups"),
        pl.col("len").filter(pl.col("len") > 1).sum().alias("rows_in_duplicate_groups")])
    result["keys"] = keys
    result["rows_with_any_null_key"] = summary(frame, [
        pl.any_horizontal(pl.col(c).is_null() for c in keys).sum().alias("n")])["n"]
    if len(keys) == 1:
        result["unique_non_null_values"] = summary(frame, [
            pl.col(keys[0]).drop_nulls().n_unique().alias("n")])["n"]
    return result


def general(frame, schema, name):
    expr = [pl.len().alias("rows")]
    for i, (c, dtype) in enumerate(schema.items()):
        expr.append(pl.col(c).null_count().alias(f"null_{i}"))
        if dtype == pl.String:
            expr.append((pl.col(c).str.strip_chars() == "").sum().alias(f"blank_{i}"))
    # Every column is consumed here: a count-only scan would not validate types.
    values = summary(frame, expr)
    n = values["rows"]
    columns = []
    for i, (c, dtype) in enumerate(schema.items()):
        nulls, blanks = values[f"null_{i}"], values.get(f"blank_{i}")
        columns.append({"name": c, "dtype": str(dtype), "missing_count": nulls,
            "missing_pct": pct(nulls, n), "blank_count": blanks,
            "blank_pct": pct(blanks, n) if blanks is not None else None})
    result = {"rows": n, "column_count": len(schema), "columns": columns,
              "examples": examples(frame, schema)}
    result["exact_duplicate_excess_rows"] = (None if name == "Spotify" else
        n - collect(frame.unique()).height)
    return result


def spotify(frame, schema):
    result = {"track_ids": duplicates(frame, ["id"]),
              "raw_song_artist": duplicates(frame, ["name", "artists"])}
    # Whitespace-delimited words; only the numeric lengths survive collection.
    lengths = collect(frame.select(pl.col("lyrics").str.count_matches(r"\S+").alias("words"))
                      .filter(pl.col("words") > 0))["words"]
    n = len(lengths)
    short = int((lengths < 20).sum())
    result["lyric_words"] = {"non_empty_lyrics": n, "mean": lengths.mean(),
        "median": lengths.median(), "p25": lengths.quantile(.25, interpolation="linear"),
        "p75": lengths.quantile(.75, interpolation="linear"),
        "min": lengths.min(), "max": lengths.max(), "fewer_than_20": short,
        "fewer_than_20_pct_of_non_empty": pct(short, n)}
    ranges = {c: (0, 1) for c in ["danceability", "energy", "speechiness",
        "acousticness", "instrumentalness", "liveness", "valence"]}
    ranges.update(loudness=(-60, 0), tempo=(0, None), key=(-1, 11),
                  mode=(0, 1), duration_ms=(0, None))
    result["audio"] = {}
    for c, (low, high) in ranges.items():
        if c not in schema:
            result["audio"][c] = {"available": False}
            continue
        raw = pl.col(c)
        numeric = raw.cast(pl.Float64, strict=False)
        finite = numeric.is_finite()
        invalid = (numeric < low) | ((numeric > high) if high is not None else pl.lit(False))
        if c in ("key", "mode", "duration_ms"):
            invalid = invalid | (numeric != numeric.floor())
        if c == "duration_ms":
            invalid = invalid | (numeric == 0)
        stats = summary(frame, [raw.null_count().alias("missing_count"),
            (raw.is_not_null() & numeric.is_null()).sum().alias("non_numeric_count"),
            (numeric.is_not_null() & ~finite).sum().alias("non_finite_count"),
            numeric.filter(finite).min().alias("observed_numeric_min"),
            numeric.filter(finite).max().alias("observed_numeric_max"),
            (invalid & finite).sum().alias("outside_expected_range_count")])
        stats.update(expected_lower=low, expected_upper=high,
                     rule="positive integer" if c == "duration_ms" else
                     "integer interval" if c in ("key", "mode") else "inclusive interval",
                     range_is_typical_not_hard_bound=c == "loudness")
        if schema[c] == pl.String:
            stats["raw_value_counts"] = collect(frame.group_by(c).len().sort(c)).to_dicts()
        result["audio"][c] = stats
    return result


def billboard(frame):
    date = pl.col("Date").str.strptime(pl.Date, "%Y-%m-%d", strict=False)
    result = summary(frame, [date.min().cast(pl.String).alias("min_chart_date"),
        date.max().cast(pl.String).alias("max_chart_date"),
        date.drop_nulls().n_unique().alias("distinct_chart_weeks"),
        (pl.col("Date").is_not_null() & date.is_null()).sum().alias("invalid_date_count"),
        pl.col("Rank").min().alias("min_rank"), pl.col("Rank").max().alias("max_rank"),
        (~pl.col("Rank").is_between(1, 100)).sum().alias("invalid_rank_count")])
    result["raw_song_artist"] = duplicates(frame, ["Song", "Artist"])
    result["date_song_artist"] = duplicates(frame, ["Date", "Song", "Artist"])
    result["weeks_in_charts_dtype"] = str(frame.collect_schema()["Weeks in Charts"])
    result["weeks_in_charts_values"] = collect(frame.select("Weeks in Charts").unique()
                                                .sort("Weeks in Charts")).to_series().to_list()
    result["weeks_in_charts_value_counts"] = collect(frame.group_by("Weeks in Charts").len()
                                                       .sort("Weeks in Charts")).to_dicts()
    return result


def grammy(frame, schema):
    result = summary(frame, [pl.col("year").min().alias("min_award_year"),
        pl.col("year").max().alias("max_award_year"),
        pl.col("award").drop_nulls().n_unique().alias("distinct_award_categories"),
        pl.len().alias("nomination_records"), pl.col("winner").sum().alias("winners")])
    result["winners_pct_of_all_records"] = pct(result["winners"], result["nomination_records"])
    soty = frame.filter(pl.col("award") == "Song Of The Year")
    result["song_of_the_year_records"] = collect(soty.select(pl.len())).item()
    period = soty.filter(pl.col("year").is_between(2000, 2024))
    result["song_of_the_year_2000_2024"] = summary(period, [
        pl.len().alias("nominee_records_including_winners"),
        pl.col("winner").sum().alias("winner_records"),
        (pl.col("winner") == False).sum().alias("non_winning_nominee_records")])
    result["song_of_the_year_examples"] = examples(soty, schema)
    result["year_artist_title_award"] = duplicates(frame, ["year", "artist", "song_or_album", "award"])
    return result


def render(report):
    lines = ["# Raw data profile", "", "Read-only profiling for Do Lyrics Matter for Music Success?", "",
             "## Method", "", *[f"- {s}" for s in report["method"]], "", "## File inventory", "",
             "| Dataset | File | Bytes | Parse status | Raw unchanged |",
             "|---|---|---:|---|---|"]
    for name, d in report["datasets"].items():
        lines.append(f"| {name} | {d['path']} | {d.get('before', {}).get('size_bytes', 'missing')} | {d['status']} | {d.get('raw_unchanged')} |")
    for name, d in report["datasets"].items():
        lines += ["", f"## {name}", ""]
        if "profile" not in d:
            lines += ["Profiling stopped; see errors below."]
            continue
        p = d["profile"]
        checks = d["checks"]
        if name == "Spotify":
            lines += [f"There are {checks['track_ids']['unique_non_null_values']:,} unique non-null track IDs and "
                      f"{checks['raw_song_artist']['unique_combinations_including_null']:,} raw song–artist combinations. "
                      f"Median lyric length is {checks['lyric_words']['median']} words; "
                      f"{checks['lyric_words']['fewer_than_20']:,} non-empty lyrics have fewer than 20 words.", ""]
        elif name == "Billboard":
            lines += [f"Coverage runs from {checks['min_chart_date']} to {checks['max_chart_date']} across "
                      f"{checks['distinct_chart_weeks']:,} chart weeks. There are {checks['invalid_rank_count']} ranks outside 1–100 and "
                      f"{checks['date_song_artist']['duplicate_excess_rows']} excess date–song–artist entries. "
                      "Repeating a song across different chart weeks is expected at this raw grain.", ""]
        else:
            period = checks['song_of_the_year_2000_2024']
            lines += [f"Award years span {checks['min_award_year']}–{checks['max_award_year']}. "
                      f"There are {checks['winners']:,} winners ({checks['winners_pct_of_all_records']:.2f}% of nomination records). "
                      f"Song of the Year has {period['nominee_records_including_winners']} nomination records including "
                      f"{period['winner_records']} winners during 2000–2024. Nominee counts are records, not unique people.", ""]
        lines += [f"Rows: **{p['rows']:,}**. Columns: **{p['column_count']}**. "
                  f"Exact duplicate excess rows: **{p['exact_duplicate_excess_rows']}** (null = not computed).", "",
                  "### Columns and completeness", "",
                  "| Column | Effective type (see schema notes) | Missing | Missing % | Blank | Blank % |",
                  "|---|---|---:|---:|---:|---:|"]
        for c in p["columns"]:
            lines.append("| " + " | ".join(str(c[k]) if c[k] is not None else "n/a"
                for k in ("name", "dtype", "missing_count", "missing_pct", "blank_count", "blank_pct")) + " |")
        lines += ["", "### Dataset-specific checks", "", "```json",
                  json.dumps(d["checks"], ensure_ascii=False, indent=2), "```", "",
                  "### Five example records (lyrics omitted; text capped at 200 characters)", "", "```json",
                  json.dumps(p["examples"], ensure_ascii=False, indent=2), "```"]
        lines += ["", "### Schema notes", "", "```json", json.dumps({
            "inferred_schema": d["inferred_schema"], "schema_overrides": d["schema_overrides"]}, indent=2), "```"]
    for title, key in [("Errors and warnings", "warnings"), ("Initial data-quality risks", "risks"),
                       ("Recommended next preparation steps", "next_steps")]:
        lines += ["", f"## {title}", "", *[f"- {x}" for x in report[key]]]
    lines += ["", "### Errors", "", "```json", json.dumps(report["errors"], indent=2), "```", "",
              "### Resolved initial parsing failure", "", "```json", json.dumps(report["resolved_parsing_errors"], indent=2), "```", "",
              "### Reproducibility and source integrity", "", "```json",
              json.dumps({"runtime": report["runtime"], "files": {k: {x: v.get(x) for x in
                ("before", "after", "raw_unchanged")} for k, v in report["datasets"].items()}}, indent=2), "```", ""]
    return "\n".join(lines)


def main():
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Python 3.12 is required.")
    report = {"runtime": {"python": platform.python_version(), "polars": pl.__version__},
        "method": ["UTF-8 strict CSV parsing; inference uses the first 10,000 records. Billboard Weeks in Charts is explicitly read as String to preserve the '-' sentinel that failed integer parsing. No ignored errors or discarded malformed rows.",
        "Missing means a Polars null (including unquoted empty CSV fields). Blank means non-null text empty after whitespace stripping. Percentages use all rows unless labelled otherwise. Literal NA/null strings are not recoded.",
        "Duplicate count means excess rows beyond one per raw key. Null key combinations are included and reported separately; raw strings are unchanged. Exact rows compare parsed field values.",
        "Lyric word counts use whitespace-delimited non-empty tokens. Percentiles use linear interpolation on non-empty lyrics only. This is a profiling statistic, not a persisted feature dataset.",
        "Five examples use source order. All lyric values are omitted, and other text is capped at 200 characters.",
        f"Audio numeric domains follow {SOURCE}. Loudness -60 to 0 dB is a typical range, not a hard validity constraint. Tempo >=0 and positive integer duration are plausibility checks without upper bounds. Text key/mode values are reported, not converted or repaired.",
        "The intended future period is 2000–2024 and grain is unique song–artist. Raw profiling covers every record; only the requested Grammy period check is filtered.",
        "Streaming scans validate every column. Spotify full-row duplicates are skipped to avoid retaining long lyrics; exact ID and song–artist counts are computed. Exact key grouping and lyric quantiles still require memory proportional to keys and numeric lengths."],
        "datasets": {}, "errors": [], "resolved_parsing_errors": [{"dataset": "Billboard",
            "type": "ComputeError", "exact_original_message": ORIGINAL_BILLBOARD_ERROR,
            "resolution": "Explicit Weeks in Charts String override preserves all values, including '-'. The failed scan was stopped; the corrected scan is a separate run."}],
        "warnings": ["Spotify exact full-row duplicates not computed (1.5 GB source with long lyrics).",
            "Billboard Weeks in Charts requires a lossless String override; '-' is retained, not recoded as missing."],
        "risks": ["High: Spotify has no release-date column, so its 2000–2024 eligibility cannot be established from this file alone.",
            "High: Grammy title fields cover songs and albums, while artist and contributor fields have different roles; direct title–artist joins could misidentify works.",
            "Medium: Spotify key/mode mix numeric codes and named musical categories. Non-numeric counts describe coding differences, not automatically invalid music values.",
            "Medium: Empty or very short lyrics may be unusable for NLP; no language, content validity or placeholder classification has been performed."], "next_steps": ["Agree on song–artist identity rules and the 2000–2024 eligibility date for each source before preparing data.",
        "Review missing titles, artists, lyrics, short lyrics, and audio coding against the source documentation before choosing handling rules.",
        "Plan how chart-week records and award nomination records will map to the future song–artist grain; no such aggregation or matching has been performed."]}
    for name, filename in FILES.items():
        path = ROOT / "data" / "raw" / filename
        d = {"path": path.relative_to(ROOT).as_posix(), "exists": path.is_file(), "status": "pending"}
        report["datasets"][name] = d
        print(f"Profiling {name}...", flush=True)
        try:
            d["before"] = fingerprint(path)
            frame = pl.scan_csv(path, infer_schema_length=10000, encoding="utf8", ignore_errors=False)
            schema = frame.collect_schema()
            d["inferred_schema"] = {c: str(t) for c, t in schema.items()}
            d["schema_overrides"] = {c: str(t) for c, t in OVERRIDES.get(name, {}).items()}
            if name in OVERRIDES:
                frame = pl.scan_csv(path, infer_schema_length=10000, encoding="utf8",
                                    ignore_errors=False, schema_overrides=OVERRIDES[name])
                schema = frame.collect_schema()
            required = {"Spotify": {"id", "name", "artists", "lyrics", "danceability"},
                        "Billboard": {"Date", "Song", "Artist", "Rank"},
                        "Grammy": {"year", "award", "artist", "song_or_album", "winner"}}[name]
            if not required.issubset(schema.names()):
                raise ValueError(f"Columns do not identify the expected {name} dataset: missing {sorted(required - set(schema.names()))}")
            d["identified_from_columns"] = name
            collect(frame.head(5))
            d["quick_parse"] = "passed"
            profile = general(frame, schema, name)
            checks = spotify(frame, schema) if name == "Spotify" else billboard(frame) if name == "Billboard" else grammy(frame, schema)
            d.update(profile=profile, checks=checks, status="passed")
            for c in profile["columns"]:
                if c["missing_count"] or c["blank_count"]:
                    report["risks"].append(f"{name}.{c['name']}: {c['missing_count']} missing ({c['missing_pct']:.2f}%), {c['blank_count']} blank; assess suitability before downstream use.")
            for key, value in checks.items():
                if isinstance(value, dict) and value.get("duplicate_excess_rows", 0):
                    report["risks"].append(f"{name} {key}: {value['duplicate_excess_rows']} excess raw-key rows; repeated source grain must be understood before matching.")
            if name == "Spotify":
                for c, stats in checks["audio"].items():
                    if any(stats.get(k, 0) for k in ("non_numeric_count", "non_finite_count", "outside_expected_range_count")):
                        report["warnings"].append(f"Spotify {c}: {stats.get('non_numeric_count', 0)} non-numeric, {stats.get('non_finite_count', 0)} non-finite, {stats.get('outside_expected_range_count', 0)} outside numeric expectations; inspect raw coding before use.")
            print(f"{name}: {profile['rows']:,} rows, {profile['column_count']} columns; parsed successfully.", flush=True)
        except Exception as exc:
            d["status"] = "failed"
            # Parser diagnostics can echo source lyrics. Redact backtick-quoted
            # values only; retain error class, column, byte offset and guidance.
            import re
            message = re.sub(r"could not parse `[^`]*`", "could not parse `[source value omitted]`", str(exc)) if name == "Spotify" else str(exc)
            report["errors"].append({"dataset": name, "type": type(exc).__name__,
                "message": message, "note": "Source-value quotations redacted to prevent lyric disclosure."})
            print(f"{name}: FAILED ({type(exc).__name__}); see report.", flush=True)
        finally:
            if path.is_file() and "before" in d:
                d["after"] = fingerprint(path)
                d["raw_unchanged"] = d["before"] == d["after"]
                if not d["raw_unchanged"]:
                    report["errors"].append({"dataset": name, "message": "Raw fingerprint changed during execution."})
    destination = ROOT / "reports"
    destination.mkdir(exist_ok=True)
    (destination / "raw_profile.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (destination / "raw_profile.md").write_text(render(report), encoding="utf-8")
    print("Saved reports/raw_profile.md and reports/raw_profile.json.")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
