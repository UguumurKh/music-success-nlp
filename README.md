# Do Lyrics Matter for Music Success?

## Current update: Preprocessing II (15 November 2026)

The project now includes matched 2000–2022 data and an executed nine-family
grouped prediction analysis. The Phase 2A documentation below is historical.
The current question is whether lyric-derived features improve Billboard
Top-10 prediction beyond audio among Billboard-charting songs.

- Branch: `preprocessing-ii-update`; no push or merge is part of this update.
- [Preprocessing summary](reports/preprocessing_ii_20261115/01_preprocessing_summary.md)
- [Actual analysis results](reports/preprocessing_ii_20261115/04_analysis_update.md)
- [Methods and reproduction](reports/preprocessing_ii_20261115/02_methods_and_reproduction.md)
- [Twelve-minute presentation outline](reports/preprocessing_ii_20261115/05_presentation_12_minutes.md)
- Private submission: `data/processed/preprocessing_ii_20261115_v2/submission/`.
  Contains complete lyrics and must remain Git-ignored. Project members must
  review explanatory materials and the sample before manually uploading.

```powershell
uv sync --locked
uv run python -m unittest discover -s tests -v
uv run python src/14_preprocessing_ii_analysis.py --output data/processed/preprocessing_ii_reproduction
uv run python src/15_package_preprocessing_ii.py --run data/processed/preprocessing_ii_reproduction
```

Existing inputs, historical results, language eligibility and folds are preserved.
Stage 14 refuses to overwrite an existing run. No upstream matching stage needs
to be rerun. Stage 15 packages verified outputs without refitting models.

## Historical Phase 2A documentation

An NLP group project investigating whether lyrics help explain music success.
The eventual analysis period is 2000–2024, with one unique song–artist combination
as the intended unit of analysis. The current stage is **Phase 2A: separate,
standardized source tables**. No dataset matching or modelling has been done.

## Datasets

- `grammies_v4.csv`: Grammy award nomination records, categories, award years,
  winners, titles, artists and producer/contributor information.
- `hot100.csv`: Billboard Hot 100 weekly song–artist chart entries, ranks and
  chart-history fields. Repeated songs across weeks are expected.
- `songs_with_attributes_and_lyrics.csv`: Spotify track IDs, titles, artists,
  audio attributes and lyrics; approximately 1.55 GB.

**Never modify or overwrite raw datasets, and never commit them to Git.**
Place the three supplied CSVs in `data/raw/`. They are intentionally excluded
from version control, along with interim and processed data.

## Structure

```text
data/
  raw/          # original CSVs, read-only inputs
  interim/      # three source Parquet tables; ignored by Git
  processed/    # reserved; no prepared data yet
notebooks/
src/
  01_profile_raw_data.py
  02_prepare_source_tables.py
  music_success_nlp/
    normalization.py
reports/
  raw_profile.md
  raw_profile.json
  preparation_summary.md
  preparation_summary.json
  *_review.csv  # conflict, performer and version review evidence; no lyrics
  *_exclusions.csv
  *_normalization_collisions.csv
tests/
pyproject.toml
uv.lock
.python-version
```

## Setup and run

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and run
these commands from the project folder in PowerShell:

```powershell
uv python install 3.12
uv sync --locked
uv run python src/01_profile_raw_data.py
```

`.python-version` selects Python 3.12; the script also enforces it. `uv.lock`
records the dependency versions. Profiling uses Polars, never pandas.
The script locates inputs relative to its own project root and replaces only
the two generated reports on each run. A failure is recorded in both reports
and produces a nonzero exit status while other files are still profiled.

The reports contain file sizes and SHA-256 checksums before/after execution,
inferred schemas, completeness, duplicates, dataset-specific checks and five
bounded examples. Lyric values are omitted entirely. Missing and blank values
are reported separately; no sentinel recoding or key normalization is applied.
Strict UTF-8 parsing never ignores errors. Parser source-value quotations are
redacted in errors to prevent accidental lyric disclosure.
Billboard's `Weeks in Charts` is explicitly read as text because a full strict
scan found `-` after the inference sample. The override preserves that sentinel
and all records; the original error is documented in the reports.

Spotify scans use the streaming engine, with projected key sets and numeric
lyric lengths retained for exact counts and quantiles. Full-row Spotify
duplicates are intentionally not calculated because of long lyric payloads.
The profiling script itself produces no prepared data.

## Phase 2A: standardized source tables

```powershell
uv run python -m unittest discover -s tests -v
uv run python src/02_prepare_source_tables.py
```

This creates these Parquet files in `data/interim/`:

- `billboard_song_level_2000_2024.parquet`: aggregate original `Song`/`Artist`
  combinations over the full chart history, then select first chart dates in
  2000–2024. Chart outcomes include later observed weeks, including after 2024.
  Entire song histories with unresolved weekly conflicts are quarantined.
- `grammy_soty_2000_2024.parquet`: deduplicated Song of the Year nominations
  during 2000–2024. Original contributors remain intact; performers are not inferred.
- `spotify_track_index.parquet`: original metadata/audio fields plus normalized
  keys, lyric missing/blank flags, word count and stable SHA-256. No full lyrics
  and no year filter. Conflicting duplicate IDs remain flagged; only exact
  equivalent records can be removed, with actual lyric equality verified.

Original titles and artists are preserved. Conservative keys retain version
words and artist ordering; normalization never merges records. Collision and
multiple-version review CSVs expose ambiguous keys. Exclusion ledgers identify
each removed source record by its 1-based CSV record number, excluding the header.
The preparation summary records counts, decisions, risks and raw-file SHA-256
checks against the original profiling report and before/after preparation.
Re-running replaces the generated Phase 2A outputs. Review files can be large;
they contain metadata only. No fuzzy matching, NLP modelling features or models
are produced. Stop here until the next phase is authorized.
