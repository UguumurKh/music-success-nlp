"""Outcome-independent Stage 14 cleaning and fixed lyric measurements.

Original columns are never changed. No corpus statistics are learned here.
"""
import math
import re
import unicodedata

APOSTROPHES = str.maketrans({c: "'" for c in "\u2018\u2019\u02bc\uff07"})
TOKEN_PATTERN = r"(?u)\b(?:\w+(?:'\w+)+|\w{2,})\b"


def normalize_apostrophes(text):
    return text.translate(APOSTROPHES)


def tfidf_preprocessor(text):
    # Supplying a preprocessor replaces sklearn's default lowercase step.
    return normalize_apostrophes(text).lower()


def repair_observed_encoding(text):
    # Observed in ID 5916: UTF-8 bytes E2 80 98 decoded as Latin-1.
    # This exact reversible signature is recoverable; lossy 'â?' is not guessed.
    if text is None:
        return None, 0
    signature = '\u00e2\u0080\u0098'
    return text.replace(signature, '\u2018'), text.count(signature)


def normalized_lines(text):
    return [' '.join(line.casefold().split()) for line in (text or '').splitlines() if line.strip()]


def comparison_text(text):
    # Exact normalized equality only; blank text is never a duplicate link.
    return ' '.join(unicodedata.normalize('NFC', text or '').casefold().split())


def normalize_whole_repeat(text):
    """Keep the original first block of an exactly tiled normalized line sequence.

    Detection ignores case, within-line whitespace and blank lines, preserving
    punctuation. Retention preserves original case, internal spacing/blank lines.
    Only trailing newline separators at a block boundary are removed.
    Short smallest periods are retained; we do not invent a larger base to pass.
    """
    if not text or not text.strip():
        return text, 'retained_by_policy', 'empty_or_missing', 1
    original = text.splitlines(keepends=True)
    positions = [i for i, line in enumerate(original) if line.strip()]
    normalized = normalized_lines(text)
    for size in range(1, len(normalized) // 2 + 1):
        if len(normalized) % size or normalized != normalized[:size] * (len(normalized) // size):
            continue
        repeats = len(normalized) // size
        base = ''.join(original[:positions[size]]).rstrip('\r\n')
        if size < 12 or len(base.split()) < 100 or len(set(normalized[:size])) < 6:
            return text, 'retained_by_policy', 'small_or_low_diversity_base', repeats
        return base, 'normalized', 'exact_normalized_whole_text_tiling', repeats
    return text, 'unchanged', 'no_whole_text_repeat', 1


def simple_features(text, analyzer):
    """No truncation: score each nonblank natural line, weighted by whitespace words.

    VADER has no transformer token cap. Any failed/nonfinite line makes the song
    measurement missing, never a neutral zero. Neutral successful scores stay zero.
    Apostrophe variants are normalized only for scoring/tokenization.
    """
    words = len((text or '').split())
    lines = [line for line in (text or '').splitlines() if line.strip()]
    normalized = normalized_lines(text)
    result = dict(word_count=words, log_word_count=math.log1p(words),
                  line_repetition=(len(lines)-len(set(normalized)))/len(lines) if lines else None,
                  sentiment=None, sentiment_status='missing_text', sentiment_lines=len(lines))
    if not lines:
        return result
    try:
        values = [float(analyzer.polarity_scores(normalize_apostrophes(line))['compound']) for line in lines]
        if not all(math.isfinite(v) and -1 <= v <= 1 for v in values):
            raise ValueError('invalid polarity')
        result['sentiment'] = sum(v * len(line.split()) for v, line in zip(values, lines)) / words
        result['sentiment_status'] = 'ok'
    except Exception as exc:
        result['sentiment_status'] = 'failed_' + type(exc).__name__
    return result


def prepare(source, analyzer):
    """Idempotently add versioned fields from immutable Stage 11 input columns."""
    import polars as pl
    source = source.drop([c for c in source.columns if c.startswith('p2_')])
    ids = source['billboard_source_row']
    if ids.null_count() or ids.n_unique() != source.height:
        raise ValueError('Require unique non-null stable IDs')
    rows = []
    for r in source.iter_rows(named=True):
        original = r['lyrics_deduplicated']
        revised, decision, reason, repeats = normalize_whole_repeat(original)
        if r['full_block_dedup_applied']:
            decision, reason = 'previous_correction_preserved', 'retain_supported_stage11_correction'
        revised, encoding_replacements = repair_observed_encoding(revised)
        f = simple_features(revised, analyzer)
        rows.append(dict(p2_lyrics_original=original, p2_lyrics_revised=revised,
            p2_decision=decision, p2_reason=reason, p2_repeat_count=repeats,
            p2_encoding_replacements=encoding_replacements,
            p2_words_before=len((original or '').split()), p2_words_removed=len((original or '').split())-f['word_count'],
            p2_text_changed=original != revised, p2_eligible=r['lyric_language'] == 'en',
            **{'p2_'+k: v for k,v in f.items()}))
    return source.hstack(pl.DataFrame(rows, infer_schema_length=None))
