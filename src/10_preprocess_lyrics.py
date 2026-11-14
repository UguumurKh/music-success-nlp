"""Conservative Stage 10: preserve all source columns/rows; append text and review flags."""
from collections import Counter, defaultdict
import hashlib
import random
import re
import unicodedata
from pathlib import Path

import polars as pl
from langdetect import DetectorFactory, detect_langs, LangDetectException

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/processed/billboard_analysis_2000_2022.parquet'
OUTPUT = ROOT / 'data/processed/billboard_lyrics_preprocessed_2000_2022.parquet'
REPORT = ROOT / 'reports/lyric_preprocessing_2000_2022.md'
SEED = 20261020
DetectorFactory.seed = SEED
# Only whole-line labels observed during inspection; never strip arbitrary brackets.
SECTION = re.compile(r'\[(?:Intro|Reversed Intro|Verse [123](?:: Bow Wow)?|Chorus(?: 2X|:)?|Hook: Kamaiyah \+ YG)\]', re.I)
NOTES = re.compile(r'[♪♫\s]+')
MOJIBAKE = re.compile(r'â(?:\?|[\x80-\x9f])|Ã[\x80-\xbf]|\ufffd')
WEB = re.compile(r'https?://|www\.|you might also like|\b\d+\s+contributors?\b|\d+Embed\s*$', re.I)


def clean_lyrics(text):
    """NFC preserves compatibility distinctions; retain case, apostrophes and repetition."""
    if text is None:
        return None
    text = unicodedata.normalize('NFC', text)
    lines = []
    for line in text.splitlines():
        line = re.sub(r'[^\S\n]+', ' ', line).strip()
        if SECTION.fullmatch(line) or (line and NOTES.fullmatch(line)):
            continue
        # Retain stanza boundaries, but collapse multiple blank lines.
        if line or (lines and lines[-1]):
            lines.append(line)
    return '\n'.join(lines).strip()


def comparison_key(text):
    return ' '.join((text or '').casefold().split())


def mixed_script_token(text):
    """Flag Latin plus Greek/Cyrillic within a word; do not guess transliterations."""
    for token in re.findall(r'[^\W\d_]+', text or '', re.UNICODE):
        names = [unicodedata.name(c, '') for c in token]
        if any('LATIN' in name for name in names) and any(
                'GREEK' in name or 'CYRILLIC' in name for name in names):
            return True
    return False


def language_guess(text):
    try:
        result = detect_langs(text)
        return result[0].lang, float(result[0].prob)
    except LangDetectException:
        return 'und', 0.0


def language_screen(text):
    """Scores are detector outputs, NOT calibrated probabilities of correctness."""
    words = (text or '').split()
    language, score = language_guess(text or '')
    chunks = []
    # Nonoverlapping thirds provide a coarse code-switching screen, not language spans.
    for i in range(3):
        part = words[i * len(words) // 3:(i + 1) * len(words) // 3]
        if len(part) >= 30:
            chunks.append(language_guess(' '.join(part)))
    confident = {lang for lang, p in chunks if p >= .8 and lang != 'und'}
    short = len(words) < 50 or len(set(w.casefold() for w in words)) < 20
    mixed = len(confident) > 1
    return dict(lyric_language=language, lyric_language_score=score,
                lyric_language_chunks=[f'{lang}:{p:.3f}' for lang, p in chunks],
                lyric_language_short=short, lyric_language_mixed_candidate=mixed,
                lyric_language_uncertain=short or score < .9 or mixed or language == 'und')


def text_features(text, clean):
    raw_lines = (text or '').splitlines()
    lines = [comparison_key(line) for line in (clean or '').splitlines() if line.strip()]
    counts = Counter(lines)
    # Extra occurrences, not number of distinct recurring lines.
    repeated = sum(n - 1 for n in counts.values())
    period = next((k for k in range(1, len(lines) // 2 + 1)
                   if len(lines) % k == 0 and lines == lines[:k] * (len(lines) // k)), None)
    return dict(lyrics_clean=clean, lyric_text_changed=text != clean,
                lyric_words_before=len(text.split()) if text is not None else None,
                lyric_words_after=len(clean.split()) if clean is not None else None,
                lyric_chars_before=len(text) if text is not None else None,
                lyric_chars_after=len(clean) if clean is not None else None,
                lyric_nfc_changed=text is not None and unicodedata.normalize('NFC', text) != text,
                lyric_whitespace_issue=any(line != line.strip() or re.search(r'[^\S\n]{2,}', line) for line in raw_lines)
                    or '\r' in (text or '') or '\n\n\n' in (text or ''),
                lyric_section_lines_removed=sum(bool(SECTION.fullmatch(line.strip())) for line in raw_lines),
                lyric_note_lines_removed=sum(bool(line.strip() and NOTES.fullmatch(line.strip())) for line in raw_lines),
                lyric_residual_brackets=bool(re.search(r'[\[\]]', clean or '')),
                lyric_encoding_review=bool(MOJIBAKE.search(text or '')),
                lyric_mixed_script_token_review=mixed_script_token(text),
                lyric_invisible_review=any(unicodedata.category(c) in ('Cf', 'Cc') and c not in '\n\r\t' for c in text or ''),
                lyric_web_metadata_review=bool(WEB.search(text or '')),
                lyric_blank=not (clean or '').strip(),
                lyric_repeated_line_extras=repeated,
                lyric_repeated_line_fraction=repeated / len(lines) if lines else 0.,
                lyric_full_block_repeats=len(lines) // period if period else 1,
                lyric_extreme_length=len((clean or '').split()) < 50 or len((clean or '').split()) > 2000)


def duplicate_screen(texts, ids):
    """Exact groups plus transparent, non-exhaustive near-duplicate retrieval."""
    raw_groups, normalized_groups = defaultdict(list), defaultdict(list)
    shingles = []
    for i, text in enumerate(texts):
        if text:
            raw_groups[text].append(i)
        key = comparison_key(clean_lyrics(text))
        if key:
            normalized_groups[key].append(i)
        words = key.split()
        shingles.append(set(zip(*(words[j:] for j in range(5)))))
    index = defaultdict(list)
    for i, ss in enumerate(shingles):
        for shingle in ss:
            index[shingle].append(i)
    candidates = set()
    for i, ss in enumerate(shingles):
        # Ignore unique shingles: they cannot retrieve another song. Very common
        # shingles mostly retrieve generic refrains; this screen is not exhaustive.
        shared = [s for s in ss if 2 <= len(index[s]) <= 100]
        for shingle in sorted(shared, key=lambda s: (len(index[s]), s))[:5]:
            candidates.update((min(i, j), max(i, j)) for j in index[shingle] if j != i)
    near = []
    keys = [comparison_key(clean_lyrics(t)) for t in texts]
    for i, j in sorted(candidates):
        a, b = shingles[i], shingles[j]
        if keys[i] == keys[j] or min(len(a), len(b)) < 20:
            continue
        similarity = len(a & b) / len(a | b)
        if similarity >= .90:
            near.append((ids[i], ids[j], similarity))
    features = [dict(lyric_raw_duplicate_size=1, lyric_normalized_duplicate_size=1,
                     lyric_duplicate_group_id=None, lyric_near_duplicate_candidate=False) for _ in ids]
    for groups, field in [(raw_groups, 'lyric_raw_duplicate_size'), (normalized_groups, 'lyric_normalized_duplicate_size')]:
        for group in groups.values():
            for i in group:
                features[i][field] = len(group)
                if field == 'lyric_normalized_duplicate_size' and len(group) > 1:
                    features[i]['lyric_duplicate_group_id'] = min(ids[j] for j in group)
    near_ids = {i for a, b, _ in near for i in (a, b)}
    for i, song_id in enumerate(ids):
        features[i]['lyric_near_duplicate_candidate'] = song_id in near_ids
    return features, near, len(candidates)


def inspection_ids(frame):
    """Same deterministic selection used for the initial raw-text inspection."""
    rows = frame.to_dicts()
    ordered = sorted(rows, key=lambda r: len((r['lyrics'] or '').split()))
    chosen = ordered[:5] + ordered[-5:] + ordered[len(rows)//2-2:len(rows)//2+3]
    rng = random.Random(SEED)
    for level in ('high', 'medium', 'low'):
        group = [r for r in rows if r['lyric_resolution_confidence'] == level]
        chosen += rng.sample(group, min(10, len(group)))
    chosen += rng.sample(rows, min(15, len(rows)))
    return sorted({r['billboard_source_row'] for r in chosen})


def validate_preservation(source, output):
    ids = source['billboard_source_row']
    if ids.null_count() or ids.n_unique() != source.height:
        raise ValueError('Source song identifiers must be non-null and unique')
    if not output.select(source.columns).equals(source):
        raise ValueError('Original columns, values, order or record count changed')


def table(headers, rows):
    return ['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |',
            *['| ' + ' | '.join(map(str, row)) + ' |' for row in rows], '']


def report(frame, source_hash, near, candidate_count):
    n = frame.height
    count = lambda c: int(frame[c].sum())
    flags = ['lyric_text_changed', 'lyric_whitespace_issue', 'lyric_nfc_changed', 'lyric_residual_brackets',
             'lyric_encoding_review', 'lyric_mixed_script_token_review', 'lyric_invisible_review', 'lyric_web_metadata_review', 'lyric_blank',
             'lyric_extreme_length', 'lyric_language_short', 'lyric_language_uncertain', 'lyric_language_mixed_candidate']
    lines = ['# Conservative lyric preprocessing: 2000–2022', '',
             'Prepared for the 20 October 2026 presentation. No modelling or language exclusions.', '',
             f'Source: `{SOURCE.relative_to(ROOT).as_posix()}`; SHA-256 `{source_hash}`.',
             f'Output: `{OUTPUT.relative_to(ROOT).as_posix()}`. All {n:,} songs and every original column are preserved, including raw lyrics, outcomes and audio. New columns only; local Parquet remains ignored by Git.', '',
             '## Inspection and observed issues', '',
             f'Seed {SEED}: five shortest, five longest, five around median word length, ten per lyric-confidence group, '
             f'and fifteen random records, deduplicated to {len(inspection_ids(frame))} records. Beginning, middle and ending snippets '
             'were inspected locally, alongside all 21 records with square brackets and targeted encoding/metadata hits. '
             'This is a varied diagnostic sample, not a representative prevalence estimator; frequencies below use the whole corpus.',
             'Inspection IDs: ' + ', '.join(map(str, inspection_ids(frame))) + '.', '',
             'Observed shortest lyrics include instrumental-like repeated vocal fragments; longest texts contain substantial repetition. '
             'Bracketed ad-libs and missing-word placeholders contain potentially meaningful information. Broad searches for “lyrics”, '
             '“copyright” and “embed” hit actual lyrical words, so those terms are never deleted. Two clear mojibake cases '
             '(IDs 1919 and 5916) are flagged rather than guessed. Spanish text was observed directly (e.g. ID 10051).', '']
    lines += table(['Song-level flag', 'Count', '% of songs'], [(c, count(c), f'{100*count(c)/n:.2f}') for c in flags])
    raw_texts = frame['lyrics'].to_list()
    lines += table(['Raw text feature (not necessarily a defect)', 'Songs'], [
        ('Square brackets', sum(bool(re.search(r'[\[\]]', t or '')) for t in raw_texts)),
        ('CR line endings', sum('\r' in (t or '') for t in raw_texts)),
        ('LF line breaks', sum('\n' in (t or '') for t in raw_texts)),
        ('ASCII apostrophe', sum("'" in (t or '') for t in raw_texts)),
        ('Curly apostrophe', sum('’' in (t or '') for t in raw_texts)),
        ('Non-ASCII characters', sum(any(ord(c)>127 for c in t or '') for t in raw_texts)),
    ])
    lines += [f'Unchanged lyrics: {n-count("lyric_text_changed"):,}. '
              f'Section-label lines removed: {count("lyric_section_lines_removed"):,} across '
              f'{frame.filter(pl.col("lyric_section_lines_removed") > 0).height} songs. '
              f'Music-note-only lines removed: {count("lyric_note_lines_removed"):,} across '
              f'{frame.filter(pl.col("lyric_note_lines_removed") > 0).height:,} songs.', '',
              'Flags overlap. Encoding/invisible/web flags are pattern-based review candidates, not verified error counts. '
              'Extreme length means <50 or >2,000 cleaned whitespace tokens, a review threshold rather than an exclusion rule.', '',
              '## Before / after lengths', '',
              'Words are whitespace tokens (punctuation-only tokens included); characters are Unicode code points including whitespace. '
              'Mean is arithmetic average; median and linear-interpolated percentiles describe the distribution, not uncertainty. '
              'Blank strings count as zero; nulls are excluded. Removing note markers can reduce “word” counts without removing words.', '']
    stats = [('mean', None), ('min', None), ('p01', .01), ('p05', .05), ('p25', .25), ('median', .5),
             ('p75', .75), ('p95', .95), ('p99', .99), ('max', None)]
    rows = []
    for label, q in stats:
        values = []
        for c in ('lyric_words_before', 'lyric_words_after', 'lyric_chars_before', 'lyric_chars_after'):
            s = frame[c]
            value = s.quantile(q, interpolation='linear') if q is not None else getattr(s, label)()
            values.append(f'{value:,.2f}' if value is not None else 'NA')
        rows.append((label, *values))
    lines += table(['Statistic', 'Raw words', 'Clean words', 'Raw characters', 'Clean characters'], rows)
    lines += ['## Language screening', '',
              '[langdetect 1.0.9](https://pypi.org/project/langdetect/) runs locally with a fixed seed and its default language profiles. '
              'Top language and score are retained; scores are not calibrated correctness probabilities. '
              'The library defaults to a 10,000-character cap per call; chunk checks cover later portions of long texts too. '
              'Short/repetitive means <50 tokens or <20 unique casefolded whitespace tokens. '
              'Uncertain means short/repetitive, top score <0.90, undetermined, or chunk disagreement. '
              'Three nonoverlapping token thirds (minimum 30 tokens each) are checked; different top languages scoring ≥0.80 '
              'flag possible mixed language. This can both miss code-switching and falsely flag slang, transliteration, '
              'proper names or repeated refrains. No label is a verified language annotation; no songs are excluded.', '']
    lines += table(['Top detector label', 'Songs'], frame.group_by('lyric_language').len().sort('len', descending=True).iter_rows())
    review = frame.filter((pl.col('lyric_language') != 'en') | pl.col('lyric_language_uncertain'))
    lines += [f'Language-review union (non-English top label OR uncertainty): {review.height} songs. '
              'Flags and chunk scores in the local Parquet are the review queue. Targeted inspection confirmed Korean/English '
              'text in DDU-DU DDU-DU (ID 2160), despite an English whole-text label. Daddy (2173) contains Korean/English '
              'but is labelled Welsh, illustrating detector error. Repetitive vocalizations can trigger chunk disagreement '
              '(e.g. 2177); these flags are not a measured mixed-language prevalence.', '']
    lines += table(['ID', 'Song', 'Top label', 'Score', 'Chunk disagreement'],
                   [(r['billboard_source_row'], r['Song'].replace('|', '/'), r['lyric_language'],
                     f"{r['lyric_language_score']:.3f}", r['lyric_language_mixed_candidate'])
                    for r in review.sort('billboard_source_row').head(12).to_dicts()])
    lines += ['## Repetition and duplicate texts', '',
              'Repeated-line extras count occurrences after the first, ignoring case and whitespace but preserving punctuation. '
              'Their fraction divides by nonblank cleaned lines. Repetition is retained; a repeated chorus is not an extraction error.', '']
    for c in ('lyric_raw_duplicate_size', 'lyric_normalized_duplicate_size', 'lyric_full_block_repeats'):
        lines += [f'- {c} > 1: {frame.filter(pl.col(c) > 1).height} songs.']
    groups = frame['lyric_duplicate_group_id'].drop_nulls().n_unique()
    lines += [f'- Normalized duplicate groups: {groups}. Comparison uses NFC-cleaned, casefolded, whitespace-collapsed text; raw duplicates use untouched text.',
              f'- Songs with repeated lines: {frame.filter(pl.col("lyric_repeated_line_extras") > 0).height:,}; '
              f'median repeated-line fraction: {frame["lyric_repeated_line_fraction"].median():.3f}.',
              f'- Near-duplicate candidates: {len(near)} pairs from {candidate_count:,} retrieved pairs; '
              f'{count("lyric_near_duplicate_candidate")} songs flagged. Retrieval shares one of each document’s five rarest '
              'shared 5-token shingles (present in 2–100 songs); acceptance requires ≥20 unique shingles per text and set Jaccard ≥0.90, excluding normalized exact matches. '
              'This is non-exhaustive, insensitive to repeated-block counts, and identifies candidates rather than proven duplicate recordings.',
              '- Full-block repetition means the entire nonblank line sequence repeats exactly after case/whitespace normalization. '
              'This is a stronger review signal but can still reflect intended musical repetition.', '']
    duplicate_rows = frame.filter(pl.col('lyric_normalized_duplicate_size') > 1)
    lines += table(['Normalized duplicate group', 'Song IDs'],
                   [(key[0], ', '.join(map(str, group['billboard_source_row'].to_list())))
                    for key, group in duplicate_rows.group_by('lyric_duplicate_group_id', maintain_order=True)])
    lines += table(['Song IDs (near candidates)', 'Jaccard'], [(f'{a}, {b}', f'{s:.3f}') for a,b,s in near[:10]])
    lines += ['The retrieved near pair 4480 / 4481 is “I Kissed A Girl” credited to Glee Cast / Katy Perry: '
              'shared lyrics across cover versions are plausible, not necessarily a matching defect. '
              'The web-pattern hit (11008, “www.memory”) is lyrical/title-related content, not confirmed extraction metadata; it is retained.', '']
    lines += ['## Small review examples', '',
              'Only non-lyrical marker/whitespace fragments are shown; no full lyrics or lyrical excerpts are exported. '
              'Escapes show line breaks. Contractions and punctuation remain unchanged.', '']
    examples = []
    for song_id in (1498, 676, 724, 1919, 5916):
        r = frame.filter(pl.col('billboard_source_row') == song_id).row(0, named=True)
        before, after = ('[Chorus]', '(line removed)') if song_id == 1498 else (' ♪', '(line removed)') if song_id == 676 else ('[Pt:', '[Pt:') if song_id == 724 else ('â?', 'â?') if song_id == 1919 else (r'â\x80\x98', r'â\x80\x98')
        examples.append((song_id, f'`{before}`', f'`{after}`',
                         f"changed={r['lyric_text_changed']}; brackets={r['lyric_residual_brackets']}; encoding={r['lyric_encoding_review']}"))
    lines += table(['Song ID', 'Raw fragment', 'Clean fragment', 'Record flags'], examples)
    lines += ['## Decisions and next steps', '',
              '- Applied: NFC, consistent newline splitting, trimmed/collapsed horizontal whitespace, at most one blank line, '
              'removal of observed whole-line Intro/Reversed Intro, numbered Verse, Chorus and Hook label forms, and note-only lines. '
              'No broad bracket removal, apostrophe replacement, lowercasing, stopword removal, lemmatization, or deduplication.',
              '- Retained: negation, contractions, punctuation, accents, case, repetitions, ad-libs and uncertain speaker/stage labels. '
              'NFC does not repair mojibake. Review encoding, residual brackets, unusually long texts and repeated full blocks before expanding rules.',
              '- Mixed Latin/Greek/Cyrillic tokens may be look-alike substitutions; genuine multilingual lines also occur. '
              'Review flagged tokens locally before any targeted repair. NFC deliberately does not transliterate them.',
              '- Review language candidates manually before defining an English-only or multilingual population. '
              'Check mixed-language cases and high-confidence matches too; matching confidence is not text-quality assurance.',
              '- Resolve duplicate song relationships and group related texts during future evaluation to avoid leakage. '
              'No observations are merged or removed in this stage.',
              '- Topic modelling later: language-aware tokenization, optional lowercasing/lemmatization and documented stopwords; '
              'compare repetition-preserving versus capped counts. Fit vocabulary on training data where evaluation requires it.',
              '- Sentiment later: retain negation, punctuation and emoji; use language-appropriate methods and inspect slang, irony and repetition. '
              'Do not interpret a detector score as sentiment.',
              '- TF-IDF later: compare word n-grams (including negation phrases) and character n-grams; tune case, stopwords and frequency limits '
              'inside training folds. Avoid automatically dropping negators.',
              '- Transformers later: use the chosen tokenizer on this minimally cleaned text; preserve punctuation/case as appropriate, '
              'and explicitly plan chunking/pooling for long lyrics instead of silent truncation.',
              '- These are observational, matched Billboard songs. Cleaning does not establish causal effects of lyrics on success.', '',
              'Validation: source SHA-256 unchanged; saved output read back and all original columns equal the source, '
              'including IDs, order, outcomes and audio. Focused synthetic tests cover cleaning and preservation.', '']
    return '\n'.join(lines)


def main():
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    source = pl.read_parquet(SOURCE)
    if source.height != 6546:
        raise ValueError('Expected completed Stage 9 with 6,546 songs')
    texts, ids = source['lyrics'].to_list(), source['billboard_source_row'].to_list()
    features = []
    for i, text in enumerate(texts):
        clean = clean_lyrics(text)
        features.append({**text_features(text, clean), **language_screen(clean)})
        if (i + 1) % 1000 == 0:
            print(f'Screened {i+1:,}/{len(texts):,} lyrics', flush=True)
    duplicates, near, candidate_count = duplicate_screen(texts, ids)
    output = source.hstack(pl.DataFrame([{**a, **b} for a,b in zip(features, duplicates)], infer_schema_length=None))
    validate_preservation(source, output)
    output.write_parquet(OUTPUT)
    validate_preservation(source, pl.read_parquet(OUTPUT))
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != source_hash:
        raise RuntimeError('Stage 9 source changed during execution')
    REPORT.write_text(report(output, source_hash, near, candidate_count), encoding='utf-8')
    print(f'Saved {output.height:,} songs; changed {output["lyric_text_changed"].sum():,}; near pairs {len(near)}. Source unchanged.', flush=True)


if __name__ == '__main__':
    main()
