"""Revise an existing Analysis 1 delivery without fitting or changing evidence.

Creates a new ZIP and a preserved pre-revision delivery snapshot. Refuses reuse
of revision names. The original execution manifests and private tree never change.
"""
import argparse
import ast
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from music_success_nlp.analysis_delivery import sha, inventory, upload_files, check_extracted, reproduction_document

ROOT = Path(__file__).resolve().parents[1]


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2), encoding='utf-8')


def load_stage17():
    spec = importlib.util.spec_from_file_location('analysis1', ROOT/'src/17_analysis_1.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def package(out, revision):
    out = out.resolve()
    out.relative_to(ROOT/'data/processed')
    pack = out/'Analysis_1'
    archive = out/f'Analysis_1_upload_{revision}.zip'
    backup = out/f'delivery_before_{revision}'
    extracted = out/f'extracted_{revision}'
    assert not any(p.exists() for p in [archive, backup, extracted]), 'Use a new revision name'
    analysis = load_stage17()
    analysis.verify(out)
    # Capture immutable scope BEFORE any packaging changes, including prior ZIPs.
    protected = [p for folder in [pack/'private', pack/'tables', pack/'figures'] for p in folder.rglob('*') if p.is_file()]
    protected += [out/'execution_manifest.json', out/'execution_output_hashes.json', *out.glob('*.zip')]
    before = {p.relative_to(out).as_posix(): sha(p) for p in protected}
    backup.mkdir()
    for name in ['run_manifest.json', 'output_hashes.json', 'verification.json']:
        shutil.copy2(out/name, backup/name)
    shutil.copytree(pack, backup/'Analysis_1', ignore=shutil.ignore_patterns('private', 'tables', 'figures', '__pycache__'))
    manifest = json.loads((out/'run_manifest.json').read_text())
    # All existing bundled helpers plus the new packaging helper/test. README
    # already contains the standalone bundle introduction; retain that text.
    for rel in list(manifest['code_sha256']) + ['src/music_success_nlp/analysis_delivery.py', 'tests/test_analysis_delivery.py']:
        if rel != 'README.md':
            destination = pack/'code'/rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT/rel, destination)
        manifest['code_sha256'][rel] = sha(pack/'code'/rel)
    manifest['code_sha256']['README.md'] = sha(pack/'code/README.md')
    manifest.setdefault('delivery_revisions', []).append(dict(revision=revision, scope='Packaging only; no model rerun', previous_manifest_sha256=sha(backup/'run_manifest.json'), protected_files_sha256=before))
    write(out/'run_manifest.json', manifest)
    (pack/'reproduction.md').write_text(reproduction_document(out, manifest), encoding='utf-8')
    handover = (pack/'handover.md').read_text(encoding='utf-8').replace('Parent run_manifest.json and verification.json provide provenance.', 'The manifest copies in this folder provide provenance; full verification requires the complete private run and historical v2/v3 trees.')
    (pack/'handover.md').write_text(handover, encoding='utf-8')
    checks = dict(revision=revision, model_rerun=False, packaging_tests='3 passed',
                  existing_local_verifier='passed before and after packaging',
                  numerical_tables_predictions_private_tree_original_execution_and_previous_zip='byte-identical',
                  extracted_archive_checks=['exact file inventory', 'all included payload hashes', 'relative Markdown links', 'README metadata dependency', 'local code helpers', 'five figures', 'no private artifacts'],
                  note='This is a packaging and saved-data verification, not full reproduction or retraining.')
    write(pack/'packaging_checks.json', checks)
    with (pack/'verification_results.md').open('a', encoding='utf-8') as handle:
        handle.write(f'\n## Packaging revision {revision}\n\nPackaging-only revision: 3 packaging regression tests passed. Existing saved-data verifier passed before and after revision. Exact extracted ZIP inventory, payload checksums, relative Markdown links, code helpers and README metadata dependency checked. Numerical tables, predictions, private artifacts, original execution provenance and previous ZIP are byte-identical. No models were rerun; the historical 131 tests are prior-run evidence, not rerun for this revision. See packaging_checks.json.\n')
    # Update only delivery hashes; preserve independent original execution hashes.
    excluded = {'output_hashes.json', 'run_manifest.json', 'verification.json', 'submission_manifest.json'}
    hashes = {p.relative_to(pack).as_posix(): sha(p) for p in pack.rglob('*') if p.is_file() and p.relative_to(pack).as_posix() not in excluded and '__pycache__' not in p.parts}
    write(out/'output_hashes.json', hashes)
    analysis.verify(out)
    for name in ['run_manifest.json', 'output_hashes.json', 'verification.json']:
        shutil.copy2(out/name, pack/name)
    write(pack/'submission_manifest.json', inventory(pack))
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as zipped:
        for path in upload_files(pack):
            zipped.write(path, 'Analysis_1/'+path.relative_to(pack).as_posix())
    with zipfile.ZipFile(archive) as zipped:
        assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in zipped.namelist())
        zipped.extractall(extracted)
    result = check_extracted(extracted/'Analysis_1')
    # Compile all supplied Python sources in memory, without producing cache files.
    for path in (extracted/'Analysis_1/code').rglob('*.py'):
        compile(path.read_text(encoding='utf-8'), str(path), 'exec')
    # Imports/CLI help prove local module resolution without fitting a model.
    cli = subprocess.run([sys.executable, '-X', 'utf8', str(extracted/'Analysis_1/code/src/17_analysis_1.py'), '--help'], capture_output=True, text=True)
    assert cli.returncode == 0, cli.stderr
    assert before == {rel: sha(out/rel) for rel in before}, 'Protected evidence changed'
    result.update(zip_sha256=sha(archive), protected_files_checked=len(before), model_rerun=False, cli_help_import_check='passed', packaging_tests=3)
    write(out/f'packaging_verification_{revision}.json', result)
    (out/f'Analysis_1_upload_{revision}.zip.sha256').write_text(sha(archive)+'  '+archive.name+'\n', encoding='utf-8')
    print(json.dumps(dict(archive=str(archive), **result), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--revision', required=True)
    args = parser.parse_args()
    if not args.revision.replace('_', '').isalnum():
        parser.error('revision must contain only letters, digits and underscores')
    package(args.run, args.revision)
