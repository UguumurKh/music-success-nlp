"""Stream accepted IDs' raw content to Parquet; validate without lyric disclosure."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("source_preparation", Path(__file__).with_name("02_prepare_source_tables.py"))
PREP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PREP)
AUDIO = ["danceability", "energy", "key", "loudness", "mode", "speechiness", "acousticness",
         "instrumentalness", "liveness", "valence", "tempo", "duration_ms"]
RAW_COLUMNS = ["id", "name", "album_name", "artists", *AUDIO, "lyrics"]
CHECK_COLUMNS = ["id", "source_row", "name", "album_name", "artists", *AUDIO,
                 "lyrics_missing", "lyrics_blank", "lyric_word_count", "lyric_sha256"]
OUTPUTS = ["data/interim/spotify_accepted_candidate_content.parquet", "reports/candidate_id_extraction_ledger.csv",
           "reports/candidate_content_extraction.md", "reports/candidate_content_extraction.json",
           "reports/candidate_content_validation_failures.csv"]
FAILURE_SCHEMA = {"id": pl.String, "source_row": pl.Int64, "field": pl.String,
                  "reason": pl.String, "raw_value": pl.String, "index_value": pl.String}


def requested_ledger(billboard, grammy):
    for frame in (billboard, grammy):
        if frame.filter(pl.col("spotify_id").is_null() | (pl.col("spotify_id").str.strip_chars() == "")).height:
            raise ValueError("Accepted relationships contain an unusable Spotify ID")
    ids = pl.concat([billboard.select(pl.col("spotify_id").alias("id")),
                     grammy.select(pl.col("spotify_id").alias("id"))]).unique().sort("id")
    for name, frame in [("billboard", billboard), ("grammy", grammy)]:
        counts = frame.group_by("spotify_id").agg(pl.col("source_row").n_unique().alias(f"accepted_{name}_source_records")).rename({"spotify_id": "id"})
        ids = ids.join(counts, on="id", how="left", validate="1:1").with_columns(pl.col(f"accepted_{name}_source_records").fill_null(0))
    return ids.with_columns((pl.col("accepted_billboard_source_records") > 0).alias("requested_by_billboard"),
                           (pl.col("accepted_grammy_source_records") > 0).alias("requested_by_grammy")).with_columns(
        (pl.col("requested_by_billboard") & pl.col("requested_by_grammy")).alias("requested_by_both")).sort("id")


def extract(raw_path, ledger, index_schema, destination):
    # Fixed profiled types, strict decoding, no error ignoring. source_row is
    # added by the scanner BEFORE filtering: 1-based CSV record, not text line.
    overrides = {c: index_schema[c] for c in RAW_COLUMNS if c != "lyrics"}
    overrides["lyrics"] = pl.String
    scan = pl.scan_csv(raw_path, schema_overrides=overrides, encoding="utf8", ignore_errors=False,
                       row_index_name="source_row", row_index_offset=1)
    scan.filter(pl.col("id").is_in(ledger["id"].implode())).sink_parquet(destination, compression="zstd", engine="streaming")


def validation_metadata(content):
    # Exactly the expressions in prepare_spotify, reusing its hashing function.
    return content.with_columns(
        pl.col("lyrics").is_null().alias("lyrics_missing"),
        (pl.col("lyrics").str.strip_chars() == "").fill_null(False).alias("lyrics_blank"),
        pl.col("lyrics").str.count_matches(r"\S+").alias("lyric_word_count"),
        pl.col("lyrics").map_elements(PREP.lyric_hash, return_dtype=pl.String).alias("lyric_sha256"),
        pl.col("lyrics").str.len_chars().alias("raw_character_length"),
    ).drop("lyrics")


def equal(a, b):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


def validate(ledger, metadata, index):
    failures = []
    def failure(track, row, field, reason, raw=None, expected=None):
        # No lyric column is ever passed here; cap any other diagnostic text.
        failures.append({"id": track, "source_row": row, "field": field, "reason": reason,
                         "raw_value": json.dumps(raw, ensure_ascii=False, default=str)[:200],
                         "index_value": json.dumps(expected, ensure_ascii=False, default=str)[:200]})
    requested = set(ledger["id"])
    by_row, by_id = {}, {}
    for row in index.select(CHECK_COLUMNS).iter_rows(named=True):
        by_row.setdefault(row["source_row"], []).append(row)
        by_id.setdefault(row["id"], []).append(row)
    raw_by_id = {}
    for row in metadata.iter_rows(named=True):
        raw_by_id.setdefault(row["id"], []).append(row)
        if row["id"] not in requested:
            failure(row["id"], row["source_row"], "id", "unexpected_extracted_id", row["id"])
        matches = by_row.get(row["source_row"], [])
        if len(matches) != 1:
            failure(row["id"], row["source_row"], "source_row", "index_source_row_not_unique_or_absent", row["source_row"],
                    [x["source_row"] for x in by_id.get(row["id"], [])])
            continue
        reference = matches[0]
        for field in CHECK_COLUMNS:
            if not equal(row[field], reference[field]):
                failure(row["id"], row["source_row"], field, "index_disagreement", row[field], reference[field])
    for track in requested:
        raw_rows = raw_by_id.get(track, [])
        if len(raw_rows) != 1:
            failure(track, None, "id", "missing_requested_id" if not raw_rows else "duplicate_raw_id", len(raw_rows), 1)
        if len(by_id.get(track, [])) != 1:
            failure(track, None, "id", "index_id_not_unique_or_absent", len(by_id.get(track, [])), 1)
    failed_ids = {row["id"] for row in failures}
    ledger_rows = []
    for request in ledger.iter_rows(named=True):
        rows = raw_by_id.get(request["id"], [])
        request.update(found_in_raw=bool(rows), raw_record_count=len(rows),
            raw_source_row=rows[0]["source_row"] if len(rows) == 1 else None,
            raw_source_rows=" | ".join(str(x["source_row"]) for x in rows), duplicate_raw_records=len(rows) > 1,
            lyrics_missing=any(x["lyrics_missing"] for x in rows) if rows else None,
            lyrics_blank=any(x["lyrics_blank"] for x in rows) if rows else None,
            validation_status="missing_requested_id" if not rows else "duplicate_raw_id" if len(rows) > 1 else
            "validation_failed" if request["id"] in failed_ids else "validated")
        ledger_rows.append(request)
    ledger_schema = dict(ledger.schema) | {"found_in_raw": pl.Boolean, "raw_record_count": pl.Int64,
        "raw_source_row": pl.Int64, "raw_source_rows": pl.String, "duplicate_raw_records": pl.Boolean,
        "lyrics_missing": pl.Boolean, "lyrics_blank": pl.Boolean, "validation_status": pl.String}
    return pl.DataFrame(ledger_rows, schema=ledger_schema), pl.DataFrame(failures, schema=FAILURE_SCHEMA).sort("id", "source_row", "field")


def protected_snapshot(root):
    paths = set((root / "data/raw").glob("*.csv")) | set((root / "data/interim").glob("*.parquet"))
    paths |= {p for p in (root / "reports").glob("*") if p.is_file()}
    paths |= {p for folder in ("src", "tests") for p in (root / folder).rglob("*.py")}
    if (root / "README.md").exists():
        paths.add(root / "README.md")
    excluded = set(OUTPUTS) | {"src/06_extract_candidate_content.py", "tests/test_extract_candidate_content.py"}
    result = {}
    for path in sorted(paths):
        relative = path.relative_to(root).as_posix()
        if relative not in excluded:
            with path.open("rb") as stream:
                result[relative] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


def render(report):
    return "\n".join(["# Accepted-candidate raw content extraction", "", f"Run status: **{report['status']}**.", "",
        "## Counts and descriptive statistics", "", "```json", json.dumps(report["summary"], indent=2), "```", "",
        "## Definitions and scope", "",
        "- The raw CSV is scanned with Polars' streaming engine and strict UTF-8 decoding. Only requested IDs are written to Parquet; the full raw CSV is never collected.",
        "- Original column values, including decoded lyric strings and multiline content, are preserved. CSV quoting is a storage representation, not part of the lyric value. source_row is the 1-based data-record number, excluding the header.",
        "- Hashing reuses 02_prepare_source_tables.py: SHA-256 of the unchanged string encoded as UTF-8. Missing means null; blank means non-null whitespace-only text after strip_chars. Word count uses the identical Polars \\S+ count expression; missing lyrics retain a null count.",
        "- Word and character statistics describe non-null extracted lyrics, including blank strings. Quartiles use linear interpolation. These are extraction checks, not new modelling features.",
        "- Audio and metadata are compared exactly to the index; no disagreements are repaired. All requested IDs must occur exactly once. Missing/duplicate IDs or validation failures cause a nonzero exit after diagnostic reports are saved.",
        "- No complete lyrics appear in JSON, Markdown or CSV reports. Full lyrics appear only in the content Parquet. A failed-run Parquet is diagnostic and must not be used downstream.",
        "- No representative ID selection, audio aggregation, lyric normalization, NLP feature extraction, fuzzy matching or final modelling dataset was performed.", "",
        "## Validation", "", "```json", json.dumps(report["validation"], indent=2), "```", "", "## Outputs", "",
        *[f"- `{p}`" for p in OUTPUTS], "", "## Run", "", "```powershell",
        "uv run python -m unittest discover -s tests -v", "uv run python src/06_extract_candidate_content.py",
        "uv run python -m unittest discover -s tests -v", "```", ""])


def run(root=ROOT):
    start = time.perf_counter()
    before = protected_snapshot(root)
    load = lambda name: pl.read_parquet(root / f"data/interim/{name}.parquet")
    billboard, grammy = load("billboard_spotify_accepted_candidates"), load("grammy_spotify_accepted_candidates")
    ledger = requested_ledger(billboard, grammy)
    full_index = pl.scan_parquet(root / "data/interim/spotify_track_index.parquet")
    index_schema = full_index.collect_schema()
    # Read only requested index records, plus full schema. No lyrics in index.
    index = full_index.filter(pl.col("id").is_in(ledger["id"].implode())).collect(engine="streaming")
    content_path = root / OUTPUTS[0]
    report = {"outputs": OUTPUTS, "summary": {"distinct_requested_ids": ledger.height,
        "billboard_only_ids": ledger.filter(pl.col("requested_by_billboard") & ~pl.col("requested_by_grammy")).height,
        "grammy_only_ids": ledger.filter(pl.col("requested_by_grammy") & ~pl.col("requested_by_billboard")).height,
        "requested_by_both_ids": ledger.filter(pl.col("requested_by_both")).height}, "validation": {}}
    try:
        extraction_start = time.perf_counter()
        extract(root / "data/raw/songs_with_attributes_and_lyrics.csv", ledger, index_schema, content_path)
        report["summary"]["streaming_extraction_seconds"] = time.perf_counter() - extraction_start
        content = pl.read_parquet(content_path)  # accepted subset only
        metadata = validation_metadata(content)
        final_ledger, failures = validate(ledger, metadata, index)
        # Round-trip raw records through Parquet serialization in memory, avoiding
        # a second raw scan or any extra durable output.
        import io
        buffer = io.BytesIO()
        content.write_parquet(buffer)
        buffer.seek(0)
        roundtrip = pl.read_parquet(buffer)
        roundtrip_ok = content.schema == roundtrip.schema and content.equals(roundtrip)
        words, chars = metadata["lyric_word_count"], metadata["raw_character_length"]
        found = set(content["id"])
        references_missing = sum(frame.filter(~pl.col("spotify_id").is_in(list(found))).height for frame in (billboard, grammy))
        report["summary"].update(extracted_records=content.height, extracted_distinct_ids=content["id"].n_unique(),
            missing_ids=final_ledger.filter(~pl.col("found_in_raw")).height,
            duplicate_raw_ids=final_ledger.filter(pl.col("duplicate_raw_records")).height,
            missing_lyrics=int(metadata["lyrics_missing"].sum()), blank_lyrics=int(metadata["lyrics_blank"].sum()),
            lyric_word_count={"non_null_count": len(words) - words.null_count(), "mean": words.mean(), "median": words.median(),
                "min": words.min(), "max": words.max(), "p25": words.quantile(.25, interpolation="linear"), "p75": words.quantile(.75, interpolation="linear")},
            raw_character_length={"mean": chars.mean(), "median": chars.median()},
            index_validation_disagreements=failures.filter(pl.col("reason").is_in(["index_disagreement", "index_source_row_not_unique_or_absent", "index_id_not_unique_or_absent"])).height,
            validation_failure_rows=failures.height, accepted_relationships_missing_content=references_missing)
        report["validation"].update(parquet_roundtrip_passed=roundtrip_ok,
            extracted_ids_equal_requested=set(ledger["id"]) == found,
            requested_ids_found_exactly_once=final_ledger.filter(pl.col("raw_record_count") != 1).height == 0,
            all_accepted_relationships_have_content=references_missing == 0)
    except Exception as exc:
        # Never echo parser exception text: it may contain a complete lyric cell.
        failures = pl.DataFrame([{"id": None, "source_row": None, "field": "extraction",
            "reason": type(exc).__name__, "raw_value": None, "index_value": None}], schema=FAILURE_SCHEMA)
        final_ledger = ledger.with_columns(pl.lit("extraction_failed").alias("validation_status"))
        report["validation"]["exception_type"] = type(exc).__name__
        report["validation"]["exception_note"] = "Extraction or validation failed; diagnostic source values suppressed to prevent lyric disclosure. No malformed records ignored."
    after = protected_snapshot(root)
    report["integrity"] = {"before": before, "after": after}
    report["validation"]["protected_files_unchanged"] = before == after
    good = failures.is_empty() and all(report["validation"].get(k, False) for k in (
        "parquet_roundtrip_passed", "extracted_ids_equal_requested", "requested_ids_found_exactly_once",
        "all_accepted_relationships_have_content", "protected_files_unchanged"))
    report["status"] = "passed" if good else "failed"
    report["summary"]["output_parquet_bytes"] = content_path.stat().st_size if content_path.exists() else None
    report["summary"]["total_runtime_seconds"] = time.perf_counter() - start
    final_ledger.write_csv(root / OUTPUTS[1])
    failures.write_csv(root / OUTPUTS[4])
    (root / OUTPUTS[3]).write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (root / OUTPUTS[2]).write_text(render(report), encoding="utf-8")
    print(f"Extraction {report['status']}: {ledger.height} requested IDs; diagnostics saved. No lyrics printed.")
    return report, 0 if good else 1


if __name__ == "__main__":
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Python 3.12 is required")
    _, code = run()
    raise SystemExit(code)
