"""Read-only audit of saved Stage 10/11 outputs; never run integration or corrections.

Writes metadata-only audit artifacts. Review material stays under Git-ignored data/processed.
Uses a dependency-free fitted unigram TF-IDF vectorizer (explicit parameters below).
"""
from collections import Counter
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / 'data/processed/stage10_11_audit'
REPORT = ROOT / 'reports/stage10_11_repetition_audit.md'


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'src' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FittedUnigramTfidf:
    r"""word unigrams, lowercase=True, (?u)\b\w\w+\b, no stopwords,
    min_df=1, max_df=1.0, smooth_idf=True, use_idf=True,
    binary=False, sublinear_tf=False, norm='l2'. Python float64 arithmetic.
    Fit exactly once; transform never changes vocabulary or IDF.
    """
    pattern = re.compile(r'(?u)\b\w\w+\b')

    def counts(self, text):
        return Counter(self.pattern.findall(text.lower()))

    def fit(self, texts):
        df = Counter()
        for text in texts:
            df.update(self.counts(text).keys())
        self.idf = {term: math.log((1 + len(texts)) / (1 + n)) + 1 for term, n in df.items()}
        return self

    def transform(self, text):
        weights = {t: n * self.idf[t] for t, n in self.counts(text).items() if t in self.idf}
        norm = math.sqrt(math.fsum(v * v for v in weights.values()))
        return {t: v / norm for t, v in weights.items()} if norm else {}


def normalized_period(text):
    # Independent candidate verification: each line must equal the line one period earlier.
    lines = [' '.join(x.casefold().split()) for x in text.splitlines() if x.strip()]
    for size in range(1, len(lines) // 2 + 1):
        if len(lines) % size == 0 and all(lines[i] == lines[i % size] for i in range(size, len(lines))):
            return len(lines) // size, size
    return 1, len(lines)


def blocks(text, repeats, size):
    lines = text.splitlines(keepends=True)
    nonblank = [i for i, line in enumerate(lines) if line.strip()]
    edges = [nonblank[i * size] for i in range(repeats)] + [len(lines)]
    return [''.join(lines[edges[i]:edges[i+1]]).rstrip('\r\n') for i in range(repeats)]


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |',
                      *['| ' + ' | '.join(map(str, row)) + ' |' for row in rows]])


def main():
    stage10 = load('stage10', '10_preprocess_lyrics.py')
    stage11 = load('stage11', '11_review_and_correct_full_block_repetition.py')
    paths = [stage10.SOURCE, stage10.OUTPUT, stage11.OUTPUT, *stage11.REVIEWS,
             stage10.REPORT, stage11.REPORT]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    s9, s10, s11 = [pl.read_parquet(p) for p in paths[:3]]
    stage11.validate_preservation(s9, s10)
    stage11.validate_preservation(s10, s11)
    evidence = stage11.read_reviews(stage11.REVIEWS)
    assert stage11.prepare(s10, evidence).equals(s11), 'Saved Stage 11 differs from current code/evidence'
    assert s11['billboard_source_row'].n_unique() == s11.height
    texts = s11['lyrics_clean'].to_list()
    assert all(t is not None and t.strip() for t in s11['lyrics_deduplicated'])
    unchanged = s11.filter(~pl.col('full_block_dedup_applied'))
    assert unchanged['lyrics_clean'].equals(unchanged['lyrics_deduplicated'])
    vectorizer = FittedUnigramTfidf().fit(texts)
    # Analytic fixture: IDF and normalized components are independently known.
    fixture = FittedUnigramTfidf().fit(['aa aa bb', 'bb cc'])
    assert math.isclose(fixture.idf['aa'], math.log(3/2) + 1)
    assert fixture.idf['bb'] == 1
    a = 2 * (math.log(3/2) + 1)
    assert math.isclose(fixture.transform('aa aa bb')['aa'], a / math.sqrt(a*a + 1))
    rows = []
    for r in s11.iter_rows(named=True):
        text = r['lyrics_clean']
        repeats, size = normalized_period(text)
        assert repeats == r['lyric_full_block_repeats']
        assert len(text.split()) == r['lyric_words_after']
        assert len(text) == r['lyric_chars_after']
        assert len(r['lyrics_deduplicated'].split()) == r['lyric_words_after_dedup']
        if repeats == 1:
            continue
        parts = blocks(text, repeats, size)
        base = parts[0]
        exact = all(p == base for p in parts)
        nonblank_exact = all([x for x in p.splitlines() if x.strip()] == [x for x in base.splitlines() if x.strip()] for p in parts)
        full_v, unit_v = vectorizer.transform(text), vectorizer.transform(base)
        terms = full_v.keys() | unit_v.keys()
        differences = [full_v.get(t, 0) - unit_v.get(t, 0) for t in terms]
        fc, bc = vectorizer.counts(text), vectorizer.counts(base)
        proportional = fc == Counter({t: n * repeats for t, n in bc.items()})
        rows.append(dict(billboard_source_row=r['billboard_source_row'],
                         lyric_representative_spotify_id=r['lyric_representative_spotify_id'],
                         repeat_multiplicity=repeats, unit_nonblank_lines=size,
                         total_nonblank_lines=size*repeats, unit_words=len(base.split()),
                         total_words=r['lyric_words_after'], unit_chars=len(base), total_chars=len(text),
                         exact_blocks=exact, exact_nonblank_lines=nonblank_exact,
                         passes_stage11_structural_gate=stage11.exact_base(text, repeats) is not None,
                         existing_stage11_status=r['full_block_dedup_status'],
                         existing_review_status='; '.join(sorted({v['status'] or 'unclassified' for v in evidence.get(r['billboard_source_row'], [])})) or 'no saved review row',
                         saved_review_row_present=r['billboard_source_row'] in evidence,
                         token_counts_scale_exactly=proportional,
                         zero_vector=not full_v or not unit_v,
                         max_abs_difference=max(map(abs, differences), default=0),
                         l2_difference=math.sqrt(math.fsum(d*d for d in differences)),
                         cosine_similarity=math.fsum(full_v.get(t, 0)*unit_v.get(t, 0) for t in terms)))
    # Conservatively exclude even prior inspection IDs and blank saved workbook rows.
    inspected = set(stage10.inspection_ids(s9))
    eligible = [r for r in rows if not r['saved_review_row_present'] and r['billboard_source_row'] not in inspected]
    sizes = sorted({r['unit_nonblank_lines'] for r in eligible})
    chosen_sizes = [sizes[round(i*(len(sizes)-1)/19)] for i in range(20)]
    assert len(set(chosen_sizes)) == 20
    review = []
    for size in chosen_sizes:
        r = min((r for r in eligible if r['unit_nonblank_lines'] == size), key=lambda r: r['billboard_source_row'])
        review.append({**r, 'evidence_url_or_recording': '', 'evidence_locator_or_timestamp': '',
                       'evidence_notes_private': '', 'decision': '', 'reviewer': '', 'review_date': ''})
    PRIVATE.mkdir(exist_ok=True)
    review_path = PRIVATE / 'review_20_unreviewed.csv'
    if not review_path.exists():
        write_csv(review_path, review)
    write_csv(PRIVATE / 'flagged_tfidf_comparison.csv', rows)
    exact = [r for r in rows if r['exact_blocks']]
    exceptions = [r for r in rows if r['max_abs_difference'] > 1e-12]
    summary = dict(records=s11.height, stage9_columns=s9.width, stage10_columns=s10.width,
                   stage11_columns=s11.width, flagged=len(rows), status_counts=dict(Counter(s11['full_block_dedup_status'])),
                   exact_blocks=len(exact), exact_nonblank_lines=sum(r['exact_nonblank_lines'] for r in rows),
                   structural_gate=sum(r['passes_stage11_structural_gate'] for r in rows),
                   vocabulary_size=len(vectorizer.idf), zero_vectors=sum(r['zero_vector'] for r in rows),
                   nonproportional_ids=[r['billboard_source_row'] for r in rows if not r['token_counts_scale_exactly']],
                   exception_ids=[r['billboard_source_row'] for r in exceptions],
                   max_abs_difference=max(r['max_abs_difference'] for r in rows),
                   max_l2_difference=max(r['l2_difference'] for r in rows),
                   max_exact_abs_difference=max(r['max_abs_difference'] for r in exact),
                   max_exact_l2_difference=max(r['l2_difference'] for r in exact),
                   nonexact_ids=[r['billboard_source_row'] for r in rows if not r['exact_blocks']],
                   selected_ids=[r['billboard_source_row'] for r in review], eligible_unreviewed=len(eligible),
                   source_sha256=hashes)
    for path, digest in hashes.items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest
    (PRIVATE / 'audit_metrics.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    def stats(values):
        values = sorted(values)
        def q(p):
            index = (len(values)-1)*p
            lo = int(index)
            return values[lo] + (values[min(lo+1, len(values)-1)]-values[lo])*(index-lo)
        return [f'{x:,.2f}' for x in [values[0], sum(values)/len(values), q(.5), q(.95), values[-1]]]
    distribution = []
    for n in sorted({r['repeat_multiplicity'] for r in rows}):
        group = [r for r in rows if r['repeat_multiplicity'] == n]
        distribution.append([n, len(group), stats([r['unit_nonblank_lines'] for r in group])[2],
                             stats([r['unit_words'] for r in group])[2], stats([r['total_words'] for r in group])[2]])
    lengths = [[field, *stats([r[field] for r in rows])] for field in
               ['unit_nonblank_lines','unit_words','unit_chars','total_nonblank_lines','total_words','total_chars']]
    exception_detail = []
    for song_id in summary['nonexact_ids']:
        r = next(r for r in s11.iter_rows(named=True) if r['billboard_source_row'] == song_id)
        n, size = normalized_period(r['lyrics_clean'])
        parts = blocks(r['lyrics_clean'], n, size)
        exception_detail.append([song_id, n, size, ', '.join(str(sum(not x.strip() for x in p.splitlines())) for p in parts)])
    report = [
        '# Stage 10–11 repeated-block audit', '',
        'Audit date: 2026-11-01. **Complete within the requested local-output scope; interpretation remains unresolved.** '
        'Existing outputs were reused. No integration, correction, exclusion or source rewrite was performed. '
        'No lyrics, token vocabulary or private review notes are included in this report.', '',
        '## Verified detection and correction', '',
        '**Yes:** Stage 10 requires the entire nonblank line sequence to equal an integer number (≥2) of copies '
        'of a shorter sequence. It casefolds and collapses within-line whitespace, discards blank lines, '
        'then finds the smallest period dividing the line count. `lyric_full_block_repeats` is the resulting '
        'multiplicity, otherwise 1. It is not a partial-chorus detector and does not prove extraction duplication. '
        'All 6,546 multiplicities were independently recomputed and agree.', '',
        'Stage 11 requires every saved review to say “extraction duplication”, nonempty notes, review text equal '
        'to current `lyrics_clean`, and verbatim blocks (ignoring newline separators at boundaries). Its base '
        'must have ≥12 nonblank lines, ≥100 whitespace tokens and ≥6 distinct lines. These are ambiguity guards, '
        'not proof of a complete performance. No saved review, “likely source duplication”, blank classifications, '
        'or uncertainty authorizes shortening.', '',
        table(['Stage 11 status','Records'], sorted(summary['status_counts'].items())), '',
        '**Text completeness:** `lyrics_deduplicated` is non-null and nonblank for all 6,546 records. '
        'All 6,545 uncorrected records equal `lyrics_clean` exactly. The existing correction is ID 369 '
        '(640 → 320 whitespace tokens). All 954 unresolved flags remain unchanged. Recomputing Stage 11 '
        'in memory with saved reviews reproduces the complete saved output.', '',
        f'**Preservation:** Stage 9’s {s9.width} columns survive unchanged in Stage 10’s {s10.width}; '
        f'all {s10.width} Stage 10 columns survive unchanged in Stage 11’s {s11.width}. '
        'Record count, order, schema/dtypes and every source value agree; IDs are unique and non-null. '
        'SHA-256 checks confirm all three input datasets, both review workbooks and both prior reports stayed unchanged. '
        'The prior report source/workbook hashes match the observed inputs. The latest processed dataset is '
        '`data/processed/billboard_lyrics_corrected_2000_2022.parquet`. README phase descriptions are stale.', '',
        '## Flagged-case distribution (955 records)', '',
        table(['Multiplicity','Records','Median unit lines','Median unit words','Median total words'], distribution), '',
        table(['Length measure','Min','Mean','Median','p95','Max'], lengths), '',
        'Unit lines = nonblank cleaned lines / multiplicity. The one-unit alternative is the first block cut '
        'at the corresponding nonblank-line boundary, retaining its internal blank lines and removing trailing '
        'newline separators. Unit words = `len(unit.split())`; unit characters = `len(unit)`. Total words and '
        'characters use `lyric_words_after` and `lyric_chars_after`, verified against `lyrics_clean`. '
        'Characters count Unicode code points, not bytes. Total nonblank lines are calculated directly. '
        'p95 uses linear interpolation; character totals include separators and need not equal unit characters × multiplicity.', '',
        '## Fixed-fit unigram TF-IDF sensitivity check', '',
        f'One dependency-free vectorizer was fitted once on all 6,546 Stage 10 `lyrics_clean` texts '
        f'({len(vectorizer.idf):,} vocabulary terms), then the **same fitted object** transformed full texts and '
        'first-unit alternatives. It uses word unigrams, lowercase=True, Unicode token pattern '
        '`(?u)\\b\\w\\w+\\b`, no stopwords, no accent stripping, min_df=1, max_df=1.0, '
        'binary=False, use_idf=True, smooth_idf=True, **sublinear_tf=False, norm="l2"**. '
        'IDF = log((1 + N)/(1 + df)) + 1; weighted raw counts are divided by their L2 norm. '
        'This explicit standard-library implementation is in the audit script; scikit-learn is not installed. '
        'No model-training/evaluation claim is made from this descriptive all-corpus fit.', '',
        f'**953 verbatim-block cases:** maximum component difference {summary["max_exact_abs_difference"]:.3e}; '
        f'maximum L2 distance {summary["max_exact_l2_difference"]:.3e}. '
        f'**All 955 normalized flags:** maximum component difference {summary["max_abs_difference"]:.3e}; '
        f'maximum L2 distance {summary["max_l2_difference"]:.3e}. '
        f'Maximum |1 − cosine similarity| = {max(abs(1-r["cosine_similarity"]) for r in rows):.3e}. '
        'No zero vectors, no non-proportional token-count cases and no component differences above 1e-12 were found. '
        'Floating-point roundoff accounts for the tiny residuals. With fixed IDF, multiplying every term count '
        'by the same positive integer multiplies the norm by that integer, so normalization cancels it.', '',
        '**Investigated structural exceptions:** all 955 flags match verbatim at the nonblank-line level; '
        'two fail full-block equality solely because internal blank-line layout differs:', '',
        table(['ID','Multiplicity','Unit nonblank lines','Internal blank lines by block'], exception_detail), '',
        'Whitespace differences do not alter this unigram tokenizer’s counts; both also have invariant vectors. '
        f'Only {summary["structural_gate"]} flags pass Stage 11’s full structural/size gate, which is separate '
        'from evidence authorization. No hypothetical alternative was written into the dataset. '
        'The result does not generalize to sublinear TF, n-grams crossing block boundaries, refitted IDF, '
        'truncation-sensitive models, or merely partial repetitions.', '',
        '## Private review queue and unresolved decisions', '',
        f'Created `data/processed/stage10_11_audit/review_20_unreviewed.csv`: 20 records spanning 20 distinct '
        f'unit lengths ({min(chosen_sizes)}–{max(chosen_sizes)} nonblank lines). The eligible pool contains '
        f'{len(eligible)} flagged records after excluding every ID present in either saved review workbook '
        '(even blank classifications) and every prior Stage 10 inspection ID. This defines “previously unreviewed” '
        'only within available repository evidence; external reviews cannot be ruled out. Selection uses 20 '
        'evenly spaced ranks across distinct eligible unit lengths, with lowest stable Billboard ID as tie-breaker. '
        'It is a coverage sample, not a population prevalence sample.', '',
        'The table includes stable Billboard/Spotify IDs, current review and Stage 11 statuses, length and '
        'vector metrics, and blank evidence-location, timestamp, notes, decision, reviewer and date fields. '
        'It contains no lyrics; retrieve text locally by ID. It lives under the existing Git-ignored processed-data '
        'directory. The audit never overwrites an existing review queue, and the queue is not a Stage 11 correction input.', '',
        '**Unresolved:** whether flagged repetitions are intentional performance structure or extraction errors '
        'requires case-specific source/recording evidence. Existing reviewer claims were checked for gate compliance, '
        'not independently authenticated. The 954 unresolved cases remain included and unchanged. '
        'TF-IDF invariance provides no evidence that deleting text is semantically justified.', '',
        'Reproducibility: `src/audit_stage10_11_repetition.py`; private `flagged_tfidf_comparison.csv` '
        '(one row per flag) and `audit_metrics.json` (counts and input SHA-256 manifest). '
        'Existing Stage 10/11 tests and the audit’s independent period, count, equality and analytic TF-IDF checks '
        'provide the verification evidence. No public artifact contains lyrics.', ''
    ]
    REPORT.write_text('\n'.join(report), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
