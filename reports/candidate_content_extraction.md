# Accepted-candidate raw content extraction

Run status: **passed**.

## Counts and descriptive statistics

```json
{
  "distinct_requested_ids": 11780,
  "billboard_only_ids": 11442,
  "grammy_only_ids": 22,
  "requested_by_both_ids": 316,
  "streaming_extraction_seconds": 1.688603200018406,
  "extracted_records": 11780,
  "extracted_distinct_ids": 11780,
  "missing_ids": 0,
  "duplicate_raw_ids": 0,
  "missing_lyrics": 0,
  "blank_lyrics": 0,
  "lyric_word_count": {
    "non_null_count": 11780,
    "mean": 528.6354838709677,
    "median": 389.0,
    "min": 10,
    "max": 5000,
    "p25": 295.0,
    "p75": 590.0
  },
  "raw_character_length": {
    "mean": 2710.7682512733445,
    "median": 1999.5
  },
  "index_validation_disagreements": 0,
  "validation_failure_rows": 0,
  "accepted_relationships_missing_content": 0,
  "output_parquet_bytes": 4617849,
  "total_runtime_seconds": 5.186806599987904
}
```

## Definitions and scope

- The raw CSV is scanned with Polars' streaming engine and strict UTF-8 decoding. Only requested IDs are written to Parquet; the full raw CSV is never collected.
- Original column values, including decoded lyric strings and multiline content, are preserved. CSV quoting is a storage representation, not part of the lyric value. source_row is the 1-based data-record number, excluding the header.
- Hashing reuses 02_prepare_source_tables.py: SHA-256 of the unchanged string encoded as UTF-8. Missing means null; blank means non-null whitespace-only text after strip_chars. Word count uses the identical Polars \S+ count expression; missing lyrics retain a null count.
- Word and character statistics describe non-null extracted lyrics, including blank strings. Quartiles use linear interpolation. These are extraction checks, not new modelling features.
- Audio and metadata are compared exactly to the index; no disagreements are repaired. All requested IDs must occur exactly once. Missing/duplicate IDs or validation failures cause a nonzero exit after diagnostic reports are saved.
- No complete lyrics appear in JSON, Markdown or CSV reports. Full lyrics appear only in the content Parquet. A failed-run Parquet is diagnostic and must not be used downstream.
- No representative ID selection, audio aggregation, lyric normalization, NLP feature extraction, fuzzy matching or final modelling dataset was performed.

## Validation

```json
{
  "parquet_roundtrip_passed": true,
  "extracted_ids_equal_requested": true,
  "requested_ids_found_exactly_once": true,
  "all_accepted_relationships_have_content": true,
  "protected_files_unchanged": true
}
```

## Outputs

- `data/interim/spotify_accepted_candidate_content.parquet`
- `reports/candidate_id_extraction_ledger.csv`
- `reports/candidate_content_extraction.md`
- `reports/candidate_content_extraction.json`
- `reports/candidate_content_validation_failures.csv`

## Run

```powershell
uv run python -m unittest discover -s tests -v
uv run python src/06_extract_candidate_content.py
uv run python -m unittest discover -s tests -v
```
