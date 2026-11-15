# Preprocessing II: final teammate handover

Use branch `preprocessing-ii-update`. The completed v2 and centered-PCA v3 runs
are immutable evidence; do not edit their manifests or rerun into their folders.
Human review remains required before Canvas submission.

## Authoritative presentation material

The current eleven-model comparison is
[`reports/preprocessing_ii_pca_20261115/04_analysis_update.md`](reports/preprocessing_ii_pca_20261115/04_analysis_update.md),
with `model_ap.png` in the same directory. Its five CSV tables are authoritative:
`model_means.csv`, `fold_metrics.csv`, `pooled_oof_metrics.csv`,
`pca_paired_fold_differences.csv` and `pca_explained_variance.csv`.
All seven files are tracked on this branch and contain aggregate evidence only.
SVD/LSA remains uncentered; PCA is centered. “Simple lyrics” means log word count,
recurring-line fraction and VADER polarity.

For the full local submission, use
`data/processed/preprocessing_ii_pca_20261115_v3/submission/`:

- `04_analysis_update.md` and `model_ap.png`: current comparison and feature mapping.
- `02_methods_and_reproduction.md`: base methods plus the centered-PCA extension.
- `05_presentation_12_minutes.md`: timed outline; use the updated eleven-model
  figure and PCA comparison within its existing results segment.
- `01_preprocessing_summary.md`, `03_cleaned_sample_guide.md`, and
  `06_review_and_handover.md`: unchanged preprocessing decisions, sample guidance
  and required member review.

`04_v2_analysis_update.md` and `v2_model_ap.png` are historical references, not
the current eleven-model comparison. The v2 `fold_details.json` describes its
NMF/logistic fits; the v3 `fold_details.json` contains the new PCA fit details.

## Private OneDrive transfer and extraction

Share these **two complete folders**, including every file and `submission/`
subfolder, through the group's private OneDrive:

1. `D:\Projects\music-success-nlp\data\processed\preprocessing_ii_20261115_v2\`
2. `D:\Projects\music-success-nlp\data\processed\preprocessing_ii_pca_20261115_v3\`

Extract them into `<teammate-repository>\data\processed\`, retaining these exact
folder names. Do not introduce an extra nesting level. Keep archives outside the
extracted run folders: v3 verifies the entire v2 file tree, including filenames
and bytes. Do not let spreadsheet editors or sync conflict resolution rewrite
CSV files or add files inside the frozen v2 tree. Download all files locally.
Preserve any existing teammate copies separately rather than overwriting them.

The folders contain full lyrics, private samples, predictions and fitted
vocabularies: **do not add them to Git**. The tracked reports do not replace this
private transfer. Use the task-branch code separately; no `.git`, `.venv`, raw
dataset collection or superseded v1 run is needed in these two folder transfers.

For a **new PCA run**, also transfer this private preflight dependency if the
teammate does not already have the identical file:
`data/processed/billboard_lyrics_corrected_2000_2022.parquet`.
Its expected SHA-256 is
`2fae233f34a3c9b45a9f15be65f8d6f11511d812357dbd63be57968602c52e20`.

## Existing-run verification is currently path-dependent

The existing v3 verifier reads the absolute `base_run` in its manifest:
`D:\Projects\music-success-nlp\data\processed\preprocessing_ii_20261115_v2`.
Passing `--base` alongside `--verify` does **not** override that path; the
verification branch ignores `--base`. On a different machine, the unchanged v2
tree must also be accessible at that recorded location, through an appropriate
local path arrangement that does not overwrite existing work. Otherwise this
verification command cannot resolve the transferred base. This is a current
portability limitation, not evidence that the transferred results are wrong.
Do not edit historical manifests to pretend the run occurred elsewhere.

```powershell
uv run python src/16_centered_pca_extension.py --verify data/processed/preprocessing_ii_pca_20261115_v3
```

## Reproduce a NEW PCA run later

From the teammate's checkout of this task branch, after `uv sync --locked`, use
their actual local v2 path and a **new, nonexistent** output directory under
that checkout's `data/processed/`. For example, replace `C:\Work\music-success-nlp`
below with the teammate's repository path:

```powershell
uv run python src/16_centered_pca_extension.py --base "C:\Work\music-success-nlp\data\processed\preprocessing_ii_20261115_v2" --output "C:\Work\music-success-nlp\data\processed\preprocessing_ii_pca_teammate_run"
```

This reuses v2 predictions and fits only the two PCA families. It creates a new
manifest recording the new base location; it does not relocate the historical
run. **Additional current prerequisite:** new-run preflight calls the v2
verifier, which reads v2's absolute `source_path`:
`D:\Projects\music-success-nlp\data\processed\billboard_lyrics_corrected_2000_2022.parquet`.
The identical source file must be accessible there too. `--base` alone does not
remove this dependency. Resolve the filesystem layout without overwriting
teammate files or changing historical manifests; no code/path workaround was
implemented during this documentation-only handover.

Preflight also requires the v2 dependency code bytes and sklearn version to match
the recorded hashes/version. Keep the supplied code copies and lockfile; if a
checkout changes line endings or code, inspect the mismatch rather than weakening
the checks. The script currently refreshes the public PCA report directory for a
new run, so use an isolated clean checkout to avoid overwriting teammate report
edits. Do not run `--render-only` merely to verify a transferred run.

## Final check performed locally

Fetched `origin`; its default is `master` at `1e76786`. The task branch contained
the v2 and PCA commits `c7a876b` and `ab74156`; the starting working tree and index
were clean. The complete branch diff covers code/tests, dependency additions,
README documentation and aggregate reports; no private run files are included.
The seven public PCA files were inspected and were already committed.

```powershell
uv run python -m unittest discover -s tests -v
uv run python src/16_centered_pca_extension.py --verify data/processed/preprocessing_ii_pca_20261115_v3
```

Results: **131 tests passed**; existing v3 verification passed, including the
unchanged v2 tree, identical reused predictions, shared IDs/targets/groups/folds,
finite predictions and recomputed saved metrics. Test-fixture extraction-failure
messages are expected negative tests. No research models were rerun, no results
or historical manifests were changed, and nothing was pushed or merged.
