"""Ordered, word-weighted VADER cumulative means; no fitted corpus statistics."""
import numpy as np
from music_success_nlp.preprocessing_ii import normalize_apostrophes


def trajectory(scores, weights):
    """Equal weight per cumulative endpoint, population SD (ddof=0)."""
    scores, weights = np.asarray(scores, float), np.asarray(weights, float)
    if not len(scores) or scores.shape != weights.shape:
        raise ValueError('nonempty aligned scores and weights required')
    if not np.isfinite(scores).all() or not np.isfinite(weights).all() or (weights <= 0).any() or (abs(scores) > 1).any():
        raise ValueError('invalid scores or weights')
    c = np.cumsum(scores * weights) / np.cumsum(weights)
    return c, float(c[-1]), float(np.std(c, ddof=0))


def measure(text, analyzer):
    lines = [line for line in (text or '').splitlines() if line.strip()]
    result = dict(sentiment_mean=None, cumulative_mean_sd=None, status='missing_text', line_count=len(lines))
    if not lines:
        return result, [], []
    try:
        scores = [float(analyzer.polarity_scores(normalize_apostrophes(line))['compound']) for line in lines]
        weights = [len(line.split()) for line in lines]
        c, mean, sd = trajectory(scores, weights)
        result.update(sentiment_mean=mean, cumulative_mean_sd=sd, status='ok')
        return result, scores, c.tolist()
    except Exception as exc:
        result['status'] = 'failed_' + type(exc).__name__
        return result, [], []
