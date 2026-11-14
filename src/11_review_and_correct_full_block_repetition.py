"""Evidence-gated whole-transcription correction; no upstream stages are imported."""
from collections import Counter, defaultdict
import hashlib
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/processed/billboard_lyrics_preprocessed_2000_2022.parquet'
OUTPUT = ROOT / 'data/processed/billboard_lyrics_corrected_2000_2022.parquet'
REPORT = ROOT / 'reports/full_block_correction_2000_2022.md'
REVIEWS = [ROOT / 'reports/manual_lyric_review.xlsx', ROOT / 'reports/full_block_repetition_review.xlsx']
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
NEW_COLUMNS = ['lyrics_deduplicated', 'full_block_dedup_status', 'full_block_dedup_applied',
               'full_block_repeat_count_original', 'lyric_words_after_dedup', 'lyric_dedup_words_removed']


def read_reviews(paths):
    """Read saved cells only. Never copy notes or reference lyrics into public reports."""
    evidence = defaultdict(list)
    for path in paths:
        if not path.exists():
            continue
        with ZipFile(path) as archive:
            strings = [''.join(si.itertext()) for si in ET.fromstring(archive.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in archive.namelist() else []
            for name in archive.namelist():
                if not name.startswith('xl/worksheets/sheet') or not name.endswith('.xml'):
                    continue
                rows = []
                for row in ET.fromstring(archive.read(name)).findall('.//s:sheetData/s:row', NS):
                    values = {}
                    for cell in row.findall('s:c', NS):
                        if cell.find('s:f', NS) is not None:
                            raise ValueError('Review evidence must contain saved literal cells, not formulas')
                        value = cell.find('s:v', NS)
                        text = value.text if value is not None else ''
                        if cell.get('t') == 's':
                            text = strings[int(text)]
                        elif cell.get('t') == 'inlineStr':
                            text = ''.join(cell.find('s:is', NS).itertext())
                        values[''.join(c for c in cell.get('r') if c.isalpha())] = text or ''
                    rows.append(values)
                if not rows or 'manual_review_status' not in rows[0].values():
                    continue
                headers = rows[0]
                for row in rows[1:]:
                    record = {label: row.get(col, '') for col, label in headers.items()}
                    if not record.get('billboard_source_row'):
                        continue
                    song_id = int(record['billboard_source_row'])
                    evidence[song_id].append(dict(
                        status=record.get('manual_review_status', '').strip().casefold(),
                        notes=record.get('manual_review_notes', ''),
                        clean=record.get('lyrics_clean', ''), workbook=path.name))
    return evidence


def stage10_repeat_count(text):
    """Audit Stage 10's smallest period of casefolded, whitespace-collapsed nonblank lines."""
    lines = [' '.join(line.casefold().split()) for line in (text or '').splitlines() if line.strip()]
    for k in range(1, len(lines) // 2 + 1):
        if len(lines) % k == 0 and lines == lines[:k] * (len(lines) // k):
            return len(lines) // k
    return 1


def exact_base(text, repeats):
    """Return a verbatim first block only if every block matches, including case/spacing.

    Ignore newline separators at block boundaries only. Preserve internal blank lines,
    punctuation and natural chorus repetition. Small bases remain ambiguous.
    """
    if not text or repeats < 2:
        return None
    lines = text.splitlines(keepends=True)
    nonblank = [i for i, line in enumerate(lines) if line.strip()]
    if len(nonblank) % repeats:
        return None
    size = len(nonblank) // repeats
    if size < 12:
        return None
    boundaries = [nonblank[i * size] for i in range(repeats)] + [len(lines)]
    blocks = [''.join(lines[boundaries[i]:boundaries[i+1]]).rstrip('\r\n') for i in range(repeats)]
    base = blocks[0]
    if len(base.split()) < 100 or len(set(base.splitlines())) < 6:
        return None
    if any(block != base for block in blocks[1:]):
        return None
    return base


def correct_record(text, repeats, reviews):
    """Explicit extraction-duplication verdict AND unchanged review text AND exact structure."""
    if repeats <= 1:
        return text, 'not_applicable'
    statuses = {r['status'] for r in reviews}
    if reviews and statuses == {'extraction duplication'}:
        if all(r['notes'].strip() and r['clean'] == text for r in reviews):
            base = exact_base(text, repeats)
            if base is not None:
                return base, 'corrected'
        return text, 'uncertain'
    if reviews and statuses != {'likely source duplication'}:
        return text, 'uncertain'
    return text, 'suspected'


def prepare(source, evidence):
    # Re-applying to this stage's output recomputes from immutable lyrics_clean,
    # replacing only our six columns, so it cannot repeatedly shorten the text.
    original = source.drop([c for c in NEW_COLUMNS if c in source.columns])
    ids = original['billboard_source_row']
    if ids.null_count() or ids.n_unique() != original.height:
        raise ValueError('Require unique non-null song identifiers')
    rows = []
    for row in original.iter_rows(named=True):
        text, repeats = row['lyrics_clean'], row['lyric_full_block_repeats']
        if stage10_repeat_count(text) != repeats:
            raise ValueError(f"Stage 10 flag disagreement for ID {row['billboard_source_row']}")
        corrected, status = correct_record(text, repeats, evidence.get(row['billboard_source_row'], []))
        after = len(corrected.split()) if corrected is not None else None
        removed = len(text.split()) - after if text is not None else 0
        rows.append(dict(lyrics_deduplicated=corrected, full_block_dedup_status=status,
                         full_block_dedup_applied=status == 'corrected', full_block_repeat_count_original=repeats,
                         lyric_words_after_dedup=after, lyric_dedup_words_removed=removed))
    output = original.hstack(pl.DataFrame(rows, infer_schema_length=None))
    validate_preservation(original, output)
    return output


def validate_preservation(source, output):
    if output.height != source.height or output.select(source.columns).schema != source.schema or not output.select(source.columns).equals(source):
        raise ValueError('Original rows, schema, order or values changed')


def table(headers, rows):
    return ['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |',
            *['| ' + ' | '.join(map(str, row)) + ' |' for row in rows], '']


def make_report(output, evidence, source_hash):
    flagged = output.filter(pl.col('lyric_full_block_repeats') > 1)
    counts = Counter(output['full_block_dedup_status'].to_list())
    corrected = output.filter(pl.col('full_block_dedup_applied'))
    lines = ['# Stage 11: evidence-gated full-block correction', '',
             f'Source: `{SOURCE.relative_to(ROOT).as_posix()}`. SHA-256: `{source_hash}`.',
             f'Output: `{OUTPUT.relative_to(ROOT).as_posix()}` (local, Git-ignored).', '',
             f'All {output.height:,} song–artist records retained. {flagged.height:,} Stage 10 full-block flags verified by recomputation. '
             f'{output.height-corrected.height:,} texts untouched (suspected + uncertain + not_applicable).', '']
    lines += table(['Status', 'Songs'], [(status, counts[status]) for status in ['corrected','suspected','uncertain','not_applicable']])
    lines += ['## Rule and limits', '',
              'Stage 10 removes blank lines for detection, casefolds each remaining line, collapses whitespace within lines, '
              'and finds the smallest period that tiles the entire nonblank line sequence. Its flag counts copies of that period; '
              'it does not establish that the period is one complete musical performance. Refrain-only songs, short vocal fragments, '
              'intentional full-song repeats, case differences and stanza-layout differences are false-positive risks.', '',
              'Automatic correction requires an explicit saved “Extraction duplication” classification, nonempty notes, '
              'no conflicting review, and workbook lyrics_clean identical to the current source. “Likely source duplication” '
              'is not treated as confirmed. Pasted Genius comparisons alone never authorize correction.', '',
              'Additionally, every original-case block must match exactly, including internal whitespace and blank-line layout '
              '(newline separators at block boundaries are ignored). The retained base must have ≥12 nonblank lines, ≥100 whitespace '
              'tokens and ≥6 distinct lines. These are conservative ambiguity guards, not validated duplication classifiers. '
              'Only the verbatim first block is retained; its internal choruses, punctuation and languages remain untouched. '
              'Partial repeats are never removed. Without explicit confirmation, even strong structural repetition remains unchanged.', '',
              'Suspected = flagged without a completed classification, or explicitly likely duplication. Uncertain = an unsure, '
              'unclassified-with-reference, conflicting or other reviewed case, or a confirmed case failing the structural/staleness gate. '
              'Not applicable = no whole-block flag. These statuses concern this correction only, not general text quality.', '',
              '## Local manual evidence', '',
              'The 11 repetition-review cases comprise one targeted example and ten fixed-seed sampled flagged records; '
              'they are not proof about all 955 flags. Saved notes include listening claims for 369, 9037, 5512 and 8670; '
              '7563 and 9642 assert a retained portion without explicitly documenting listening. Five other cases paste Genius '
              'references, including two “unsure” and three blank classifications. These are reviewer-supplied reference evidence, '
              'not independently verified ground truth. An additional flagged record, 676, was reviewed for note-marker cleaning, '
              'not duplication: its “Correct cleaning” verdict does not authorize shortening its short repeated vocal text. '
              'It therefore adds a sixth uncertain case. No reference lyrics or full notes are reproduced here.', '']
    rows = []
    for row in flagged.iter_rows(named=True):
        song_id = row['billboard_source_row']
        for ev in evidence.get(song_id, []):
            # Public report uses only bounded classification labels, never reference text.
            label = ev['status'] if ev['status'] in {'extraction duplication','likely source duplication','unsure','uncertain','correct cleaning','incorrect cleaning',''} else 'other reviewed classification'
            rows.append((song_id, ev['workbook'], label or 'unclassified',
                         'Genius reference in notes' if 'genius' in ev['notes'].casefold() else 'reviewer notes', row['full_block_dedup_status']))
    lines += table(['ID','Workbook','Saved classification','Evidence type','Stage 11 status'], rows)
    for path in REVIEWS:
        lines.append(f'- `{path.name}` SHA-256: `{hashlib.sha256(path.read_bytes()).hexdigest()}`.' if path.exists() else f'- `{path.name}` missing; no conclusions inferred.')
    lines += ['', 'Other saved reviews: 1498 is uncertain about chorus coverage, 676 and 2160 report correct cleaning, '
              'and 1919 reports an encoding problem. These concern Stage 10 or source quality and do not authorize repetition correction; '
              'no upstream repairs were made.', '', '## Repetition counts and length impact', '']
    lines += table(['Original whole-block count','Songs'], output.group_by('lyric_full_block_repeats').len().sort('lyric_full_block_repeats').iter_rows())
    stats = []
    for label, subset in [('All songs',output),('Flagged',flagged),('Corrected',corrected)]:
        for version,column in [('Before','lyric_words_after'),('After','lyric_words_after_dedup')]:
            s=subset[column]
            values=[s.mean(),s.median(),s.min(),s.quantile(.95,interpolation='linear'),s.max()]
            stats.append((label,version,len(s),*[f'{v:,.2f}' if v is not None else 'NA' for v in values]))
    lines += table(['Population','Version','N','Mean','Median','Min','p95','Max'],stats)
    lines += [f'Total whitespace tokens removed: {output["lyric_dedup_words_removed"].sum():,}. '
              'Means are arithmetic averages; p95 is a linearly interpolated empirical percentile. '
              'Before means Stage 10 lyrics_clean, not the raw lyrics.', '']
    lines += table(['Corrected ID','Before words','After words','Removed'],corrected.select('billboard_source_row','lyric_words_after','lyric_words_after_dedup','lyric_dedup_words_removed').iter_rows())
    lines += ['## Interpretation and later modelling', '',
              '- Use lyrics_deduplicated as the minimally corrected primary candidate, retaining lyrics_clean for sensitivity analysis. '
              'Only explicitly confirmed, structurally exact cases change; remaining flags are unresolved rather than clean negatives.',
              '- Exact duplication inflates token counts without adding vocabulary, depressing type/token lexical diversity. '
              'Removing copies can raise that ratio without changing the song’s unique vocabulary.',
              '- Within-block choruses remain. Whole-block and line-repetition measures should be recomputed from the chosen lyric version '
              'later; existing Stage 10 features intentionally remain historical and unchanged.',
              '- Sentiment totals and truncation-sensitive models can change; token-average sentiment may remain unchanged under exact duplication. '
              'TF-IDF effects depend on normalization and sublinear term frequency: normalized linear TF may be invariant to uniform repetition. '
              'Topic count models can overweight repeated transcriptions. No such models were fitted here.',
              '- Obtain explicit decisions for the five likely and five unsure/unclassified reviewed cases; investigate representative unreviewed '
              'flags before broadening correction. Do not infer a population duplication rate from this small, partly targeted review.', '',
              'Validation: all source columns, dtypes, order and values match after Parquet round-trip; source SHA-256 unchanged. '
              'The correction is reversible because lyrics and lyrics_clean are preserved. Reapplication uses immutable lyrics_clean, '
              'so the same evidence yields identical output.', '']
    return '\n'.join(lines)


def main():
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    source = pl.read_parquet(SOURCE)
    if source.height != 6546:
        raise ValueError('Expected 6,546 Stage 10 records')
    evidence = read_reviews(REVIEWS)
    output = prepare(source, evidence)
    output.write_parquet(OUTPUT)
    validate_preservation(source, pl.read_parquet(OUTPUT))
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != source_hash:
        raise RuntimeError('Source changed')
    REPORT.write_text(make_report(output,evidence,source_hash),encoding='utf-8')
    print(dict(Counter(output['full_block_dedup_status'].to_list())))
    print('Corrected IDs:', output.filter(pl.col('full_block_dedup_applied'))['billboard_source_row'].to_list())
    print('Words removed:', output['lyric_dedup_words_removed'].sum())
    print('Source unchanged:', source_hash)


if __name__ == '__main__':
    main()
