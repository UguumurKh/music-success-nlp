"""Submission documentation and archive checks; never fits research models."""
import hashlib
import json
from pathlib import Path
import re
import tomllib
import zipfile


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reproduction_document(out, manifest):
    return f'''# Reproduction and verification

## Review the upload ZIP (no private data required)

Extract the ZIP and open `Analysis_1/report.md`. The report, aggregate tables,
five figures, outline and commented code are reviewable without private data.
The [submission inventory](submission_manifest.json) lists the exact archive
members and checksums; deliberately excluded artifacts are listed separately.
The [run manifest](run_manifest.json), [output hashes](output_hashes.json), and
[saved verification record](verification.json) are copies **inside this folder**.
Output hashes cover the full local run, including omitted private files: they
are provenance, not a claim that those files are inside the ZIP. Use the
submission inventory, not output_hashes.json, to check archive contents.

The ZIP alone cannot run full saved-data verification. A saved verification
record is evidence of a previous check, not a new verification on your machine.

## Private inputs for reproducing the analysis

Use Python 3.12 and `uv sync --locked` from the repository or extracted `code/`.
The single analysis entry point is `src/17_analysis_1.py`. Required private inputs:

1. The **complete unchanged** `preprocessing_ii_20261115_v2/` directory, including
   master.parquet, predictions.csv, fold_assignments.csv, eligible_ids.csv,
   decision_audit.csv, fold_metrics.csv, configuration.json, run_manifest.json,
   submission/ (including historical code, cleaned sample and descriptive
   components), private_component_examples.json, and every other original file.
   Whole-tree hash validation requires the complete tree, not just this list.
2. The **complete unchanged** `preprocessing_ii_pca_20261115_v3/` directory,
   including predictions, submission, manifest and all other original files.
3. `billboard_lyrics_corrected_2000_2022.parquet`, SHA-256
   `2fae233f34a3c9b45a9f15be65f8d6f11511d812357dbd63be57968602c52e20`.

Raw CSV collections and stage12_modelling are not needed for Stage 17.
Private historical directories must be transferred separately; none is in the ZIP.
Do not change their manifests, filenames, bytes or add sync-conflict files.

From the checkout root (replace paths when relocated):

```powershell
uv sync --locked
uv run python -X utf8 -m unittest discover -s tests -p test_analysis_delivery.py -v
uv run python -X utf8 src/17_analysis_1.py --base "{manifest['base']}" --pca "{manifest['pca']}" --source "{manifest['source']}" --output "{out.parent / 'analysis_1_reproduction_NEW'}"
```

This reproduction command **does fit models**. It was not run for the packaging
revision. Choose a nonexistent output under the chosen code root's data/processed/.
The report renderer is called automatically. Qualitative review notes are human
annotations; computation alone does not reproduce that judgment.

## Full verification of the existing run (no model fitting)

In addition to the complete v2/v3 directories, obtain the **complete existing
Analysis 1 run directory**, not just its upload ZIP. This includes its parent
run_manifest.json, output_hashes.json, execution_manifest.json,
execution_output_hashes.json, and full Analysis_1/ tree: private predictions,
fold assignments, measurement/line-score caches, fitted objects, review cases,
executed_code snapshot, and all other files named by its checksums. Fitted
objects are hashed, not unpickled, by the verifier. The corrected source Parquet
is required for reproduction preflight; the existing-run verifier does not
read it anew. No raw/interim data is required for this verifier.

```powershell
uv run python -X utf8 src/17_analysis_1.py --verify "{out}" --base "{manifest['base']}" --pca "{manifest['pca']}"
```

Both historical path overrides are honored. Keep the transferred run under an
ignored data/processed/ path in the checkout running the verifier. For a standalone
extracted code bundle, initialize a local Git repository in code/ (`git init`);
its included .gitignore excludes data/processed/. Git-ignore checks are required.
The copied code includes README.md because pyproject.toml declares it as metadata.

Historical dependency hashes deliberately require exact bytes. Windows Git
line-ending conversion can trigger a mismatch. Prove any discrepancy is only
LF/CRLF before restoring byte-identical dependencies from v2/submission/code;
never relax the hashes. Original v3 verification has older absolute-path
limitations; Stage 17 supports explicit historical directory overrides.

## Verification scope and provenance

The local verifier checks historical tree hashes, output/code hashes, original
execution evidence, reference prediction identity, IDs/targets/folds/groups,
finite probabilities, saved fold/pooled metrics, equal-fold means and confusion
counts. Training-only and permutation immutability checks were performed during
the original execution; saved-data verification does not repeat model training.

The original 131-test historical suite was run in the original checkout with
its ignored interim fixtures. Four legacy tests cannot run in a fresh worktree
without those fixtures. Focused Analysis 1 tests and packaging checks are separate.

Original execution provenance and private/executed_code remain preserved.
run_manifest.json distinguishes delivery code_sha256 from execution_code_sha256.
Packaging revisions update delivery checksums, never the original execution
hashes or numerical evidence. See [verification results](verification_results.md)
and [packaging checks](packaging_checks.json) for the scope of checks actually run.
'''


def upload_files(pack):
    """Explicitly omit private trees and Python interpreter caches."""
    return sorted(p for p in pack.rglob('*') if p.is_file()
                  and 'private' not in p.relative_to(pack).parts
                  and '__pycache__' not in p.parts and p.suffix != '.pyc')


def inventory(pack):
    files = upload_files(pack)
    names = [p.relative_to(pack).as_posix() for p in files]
    if 'submission_manifest.json' not in names:
        names.append('submission_manifest.json')
    return dict(archive_root='Analysis_1/', included_files=sorted(names),
                included_sha256={p.relative_to(pack).as_posix(): sha(p) for p in files if p.name != 'submission_manifest.json'},
                self_checksum='submission_manifest.json is listed but not self-hashed; ZIP checksum is external',
                deliberately_excluded_private_files=sorted(p.relative_to(pack).as_posix() for p in (pack/'private').rglob('*') if p.is_file() and '__pycache__' not in p.parts),
                other_exclusions=['Python caches', 'historical v2/v3 directories', 'corrected source Parquet', 'master corpus'],
                review_status='Uguumur and Nafees must personally review private examples before submission')


def check_extracted(pack):
    """Validate actual inventory, hashes, Markdown links and code dependencies."""
    data = json.loads((pack/'submission_manifest.json').read_text())
    actual = {p.relative_to(pack).as_posix() for p in pack.rglob('*') if p.is_file()}
    assert actual == set(data['included_files']), 'Archive inventory mismatch'
    assert not any('private' in Path(name).parts or name.endswith(('.pkl', '.parquet')) for name in actual)
    assert set(data['included_sha256']) == actual - {'submission_manifest.json'}
    for rel, digest in data['included_sha256'].items():
        assert sha(pack/rel) == digest, rel
    links = 0
    for path in pack.glob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
            if '://' in target or target.startswith('#'):
                continue
            target = target.split('#')[0]
            assert (path.parent/target).exists(), (path.name, target)
            links += 1
    code = pack/'code'
    project = tomllib.loads((code/'pyproject.toml').read_text(encoding='utf-8'))
    assert (code/project['project']['readme']).is_file()
    manifest = json.loads((pack/'run_manifest.json').read_text())
    for rel, digest in manifest['code_sha256'].items():
        assert sha(code/rel) == digest, rel
    for rel in ['src/17_analysis_1.py', 'src/18_analysis_1_report.py', 'src/12_topics_and_top10_prediction.py', 'src/14_preprocessing_ii_analysis.py', 'src/music_success_nlp/preprocessing_ii.py', 'src/music_success_nlp/analysis_delivery.py', 'uv.lock', '.python-version', '.gitignore']:
        assert (code/rel).is_file(), rel
    assert len(list((pack/'figures').glob('*.png'))) == 5
    return dict(passed=True, archive_files=len(actual), relative_markdown_links_checked=links, main_figures=5, private_artifacts_in_archive=False)
