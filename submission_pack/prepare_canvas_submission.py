"""Assemble existing code and genuine cleaned-text previews for Canvas.

Run from the existing project root:
    uv run python submission_pack/prepare_canvas_submission.py

This script never fits models, reruns cleaning, changes source data, or pushes Git.
It writes a NEW private submission folder/ZIP under data/processed/.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import zipfile


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.resolve()
    pack = Path(__file__).resolve().parent
    source = root / 'data/processed/billboard_lyrics_corrected_2000_2022.parquet'
    script_names = [
        '09_prepare_analysis_sample.py',
        '10_preprocess_lyrics.py',
        '11_review_and_correct_full_block_repetition.py',
        '12_topics_and_top10_prediction.py',
    ]
    required = [source, pack / 'NLP_Preprocessing_I.pdf',
                *[root / 'src' / name for name in script_names],
                pack / 'preprocessing_I_metadata_sample.csv']
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise SystemExit('No submission was created. Missing files:\n' + '\n'.join(missing)
                         + '\nRun from the project root or supply --project-root PATH.')

    import polars as pl  # Existing project dependency, no installation required.

    before = sha256(source)
    manifest_path = root / 'data/processed/stage12_modelling/run_manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        expected = manifest.get('source_sha256')
        if expected and expected != before:
            raise SystemExit('Source differs from the analysed snapshot. No files were written.')
    frame = pl.read_parquet(source)
    text_columns = ['lyrics', 'lyrics_clean', 'lyrics_deduplicated']
    required_columns = ['billboard_source_row', 'Song', 'Artist', 'top10',
                        'lyric_language', 'full_block_dedup_status', *text_columns]
    if any(c not in frame.columns for c in required_columns):
        raise SystemExit('Required sample columns are missing. No files were written.')
    assert frame['billboard_source_row'].n_unique() == frame.height
    metadata = pl.read_csv(pack / 'preprocessing_I_metadata_sample.csv')
    selected_ids = set(metadata['billboard_source_row'].to_list())
    # Existing evidence examples include a multilingual song deliberately retained
    # for illustrating cleaning, even though this sample is not the model cohort.
    selected_ids.update([1498, 676, 369, 2160, 1919])
    selected = frame.filter(pl.col('billboard_source_row').is_in(sorted(selected_ids)))
    if selected.height != len(selected_ids):
        raise SystemExit('Some requested sample IDs are missing. No files were written.')
    if any(selected[c].null_count() for c in text_columns):
        raise SystemExit('Missing source/cleaned sample text. No files were written.')

    base_columns = [
        'billboard_source_row', 'Song', 'Artist', 'first_chart_date', 'peak_rank', 'top10',
        'lyric_language', 'lyric_language_score', 'lyric_language_uncertain',
        'lyric_language_mixed_candidate', 'lyric_full_block_repeats',
        'full_block_dedup_status', 'full_block_dedup_applied', 'lyric_encoding_review',
    ]
    base_columns += [c for c in metadata.columns if c.endswith('_median')]
    base_columns = list(dict.fromkeys(c for c in base_columns if c in selected.columns))
    rows = []
    for row in selected.sort('billboard_source_row').to_dicts():
        item = {c: row[c] for c in base_columns}
        item['sample_purpose'] = ('documented_cleaning_example'
                                  if row['billboard_source_row'] in {1498, 676, 369, 2160, 1919}
                                  else 'metadata_sample_record')
        item['eligible_by_english_label'] = row['lyric_language'] == 'en'
        for column, label in [('lyrics', 'raw'), ('lyrics_clean', 'clean'),
                              ('lyrics_deduplicated', 'corrected')]:
            text = row[column]
            item[label + '_whitespace_tokens'] = len(text.split())
            item[label + '_excerpt'] = ' '.join(text.split()[:40])
            item[label + '_excerpt_truncated'] = len(text.split()) > 40
        # A mechanical before/after comparison, not a new correction or review.
        item['cleaning_changed_text'] = row['lyrics'] != row['lyrics_clean']
        item['correction_changed_text'] = row['lyrics_clean'] != row['lyrics_deduplicated']
        raw_lines = [line.strip() for line in row['lyrics'].splitlines() if line.strip()]
        clean_lines = set(line.strip() for line in row['lyrics_clean'].splitlines() if line.strip())
        removed_markers = [line for line in raw_lines if line not in clean_lines
                           and (set(line.replace(' ', '')) <= {'♪', '♫'}
                                or (line.startswith('[') and line.endswith(']')))]
        item['removed_standalone_marker_example'] = removed_markers[0] if removed_markers else ''
        rows.append(item)

    # Every check above precedes the first write. Never overwrite an earlier package.
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    destination = root / 'data/processed' / ('Canvas_Preprocessing_I_' + stamp)
    destination.mkdir(parents=True, exist_ok=False)
    code = destination / 'commented_code'
    code.mkdir()
    for name in script_names:
        shutil.copy2(root / 'src' / name, code / name)
    audit_script = root / 'src/audit_stage10_11_repetition.py'
    if audit_script.exists():
        shutil.copy2(audit_script, code / audit_script.name)
    shutil.copy2(pack / 'NLP_Preprocessing_I.pdf', destination)
    for name in ['NLP_Preprocessing_I.pptx', 'Speaker_notes.txt', 'Submission_checklist.txt']:
        if (pack / name).exists():
            shutil.copy2(pack / name, destination)
    pl.DataFrame(rows).write_csv(destination / 'cleaned_data_sample_PRIVATE.csv', include_bom=True)
    shutil.copy2(pack / 'preprocessing_I_metadata_sample.csv', destination)
    for name in ['analysis_sample_2000_2022.md', 'lyric_preprocessing_2000_2022.md',
                 'full_block_correction_2000_2022.md', 'stage10_11_repetition_audit.md',
                 'topics_and_top10_prediction.md']:
        existing = root / 'reports' / name
        if existing.exists():
            (destination / 'supporting_reports').mkdir(exist_ok=True)
            shutil.copy2(existing, destination / 'supporting_reports' / name)
    guide = '''CLEANED-DATA SAMPLE GUIDE

This is a selected demonstration sample, not a prevalence estimate.
It combines the 25-record metadata sample with five documented cleaning examples.
The multilingual example illustrates preservation and is not an English-model row.
raw/clean/corrected_excerpt: first 40 whitespace tokens of each actual text version.
An excerpt can look unchanged even when cleaning changed text later in the song.
*_whitespace_tokens: counts from the entire corresponding text, not the excerpt.
*_excerpt_truncated: true when the full text exceeds 40 whitespace tokens.
removed_standalone_marker_example: mechanically identified section/note line.
Full source texts remain in the original Parquet file. No new cleaning was run.
Quality flags describe concerns and are not predictor variables.
Source scripts and existing reports document all transformations.

Keep the text sample and course ZIP private. Do not commit them to public GitHub.
The presentation reports the first model run, including its known tokenizer issue.
No corrected-tokenizer models or rank-gap models are claimed.
'''
    (destination / 'sample_column_guide.txt').write_text(guide, encoding='utf-8')
    assert sha256(source) == before, 'Source changed during packaging.'
    receipt = {'source_sha256': before, 'sample_records': len(rows),
               'sample_ids': sorted(selected_ids), 'models_refitted': False,
               'source_modified': False, 'code_files': script_names}
    (destination / 'packaging_receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    archive = destination.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(destination.rglob('*')):
            if path.is_file():
                z.write(path, path.relative_to(destination))
    print('Prepared without refitting or changing source data.')
    print(f'Private cleaned-text sample: {len(rows)} records')
    print(f'Canvas ZIP: {archive}')
    print('If ZIP is not accepted, upload the PDF, commented .py files, sample CSV and its guide separately.')


if __name__ == '__main__':
    main()
