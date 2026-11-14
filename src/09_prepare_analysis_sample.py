"""Date-only analysis subset and aggregate audit; never alter the assembled source."""
from datetime import date
import hashlib
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/processed/billboard_model_base.parquet"
OUTPUT = ROOT / "data/processed/billboard_analysis_2000_2022.parquet"
REPORT = ROOT / "reports/analysis_sample_2000_2022.md"
START, END = date(2000, 1, 1), date(2022, 12, 31)
NUMERIC = [f"{name}_median" for name in (
    "danceability", "energy", "loudness", "speechiness", "acousticness",
    "instrumentalness", "liveness", "valence", "tempo", "duration_ms")]
AUDIO = NUMERIC + ["key_mode", "mode_mode"]
FLAGS = ["strict_consistency_sample", "lyrics_consistent_across_ids",
         "audio_consistent_across_ids", "any_missing_audio_value",
         "any_missing_or_blank_lyrics", "key_mode_tie", "mode_mode_tie",
         "grammy_soty_eligible", "grammy_soty_nominated", "grammy_soty_winner",
         "grammy_version_ambiguity"]


def validate_unique(frame):
    """Fail rather than silently deduplicate or change the song-level grain."""
    ids = frame["billboard_source_row"]
    if ids.null_count() or ids.n_unique() != frame.height:
        raise ValueError("billboard_source_row must be non-null and unique")


def restrict_dates(frame):
    validate_unique(frame)
    if frame.schema["first_chart_date"] != pl.Date:
        raise ValueError("Expected first_chart_date to have Parquet Date type")
    # Null dates do not qualify. No other selection, cleaning or deduplication.
    return frame.filter(pl.col("first_chart_date").is_between(START, END, closed="both"))


def percent(count, total):
    return 100 * count / total if total else None


def lengths(values):
    """Linear empirical quantiles; missing texts excluded, blank texts retained."""
    s = pl.Series(values, dtype=pl.Int64).drop_nulls()
    return {"n": len(s), "mean": s.mean(), "min": s.min(),
            **{label: s.quantile(q, interpolation="linear") for label, q in
               [("p01", .01), ("p05", .05), ("p25", .25), ("median", .5),
                ("p75", .75), ("p95", .95), ("p99", .99)]}, "max": s.max()}


def summarize(frame):
    validate_unique(frame)
    n = frame.height
    texts = frame["lyrics"].to_list()
    # Python split counts whitespace-delimited tokens, not linguistic words.
    # len counts Unicode code points in untouched raw text (including whitespace).
    audio_masks = [pl.col(c).is_null() | (~pl.col(c).is_finite()) if c in NUMERIC
                   else pl.col(c).is_null() | (pl.col(c).str.strip_chars() == "") for c in AUDIO]
    flags = {c: {"true": frame.filter(pl.col(c) == True).height,
                 "false": frame.filter(pl.col(c) == False).height,
                 "missing": frame[c].null_count()} for c in FLAGS}
    top10 = int((frame["top10"] == 1).sum())
    return {
        "n": n, "artists": frame["Artist"].drop_nulls().n_unique(),
        "normalized_artists": frame["artist_norm"].drop_nulls().n_unique(),
        "missing_artists": frame["Artist"].null_count(),
        "top10": top10, "top10_pct": percent(top10, n),
        "top10_missing": frame["top10"].null_count(),
        "top10_invalid": frame.filter(pl.col("top10").is_not_null() & ~pl.col("top10").is_in([0, 1])).height,
        "top10_peak_disagreement": frame.filter(pl.col("top10") != (pl.col("peak_rank") <= 10).cast(pl.Int8)).height,
        "date_min": frame["first_chart_date"].min(), "date_max": frame["first_chart_date"].max(),
        "date_missing": frame["first_chart_date"].null_count(),
        "yearly": dict(frame.group_by(pl.col("first_chart_date").dt.year().alias("year"))
                       .len().iter_rows()),
        "audio_missing": {c: frame.filter(mask).height for c, mask in zip(AUDIO, audio_masks)},
        "any_audio_missing": frame.filter(pl.any_horizontal(audio_masks)).height,
        "lyrics_missing": sum(t is None for t in texts),
        "lyrics_blank": sum(t is not None and not t.strip() for t in texts),
        "words": lengths([len(t.split()) if t is not None else None for t in texts]),
        "characters": lengths([len(t) if t is not None else None for t in texts]),
        "confidence": dict(frame.group_by("lyric_resolution_confidence").len().iter_rows()),
        "flags": flags,
    }


def fmt(value):
    if value is None:
        return "NA"
    return f"{value:,.2f}" if isinstance(value, float) else f"{value:,}" if isinstance(value, int) else str(value)


def rate(count, total):
    return f"{count:,} ({fmt(percent(count, total))}%)"


def table(headers, rows):
    return ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |",
            *["| " + " | ".join(map(str, row)) + " |" for row in rows], ""]


def render_report(full, sample, source_hash):
    a, b = summarize(full), summarize(sample)
    excluded = full.filter(~pl.col("billboard_source_row").is_in(sample["billboard_source_row"].implode()))
    e = summarize(excluded)
    lines = ["# Billboard analysis sample: 2000–2022", "",
             "Source: `data/processed/billboard_model_base.parquet` (authoritative assembled sample).",
             f"Source SHA-256: `{source_hash}`.",
             "Output: `data/processed/billboard_analysis_2000_2022.parquet`.", "",
             "One observation is one Billboard song identified by `billboard_source_row`. "
             "Keep first_chart_date from 2000-01-01 through 2022-12-31 inclusive; preserve every column and value. "
             "Both source and subset have unique, non-null identifiers. No language or content filtering is applied.", "",
             "## Population and comparison", "",
             f"Retained {rate(b['n'], a['n'])}; excluded {e['n']:,} songs. "
             f"Before 2000: {full.filter(pl.col('first_chart_date') < START).height:,}; "
             f"after 2022: {full.filter(pl.col('first_chart_date') > END).height:,}; "
             f"missing dates: {a['date_missing']:,}.", ""]
    metrics = [("Observations", "n"), ("Unique artist credits (raw Artist)", "artists"),
               ("Unique normalized artist credits", "normalized_artists"),
               ("Missing artist credits", "missing_artists"), ("Top-10 songs", "top10"),
               ("Top-10 % of all songs", "top10_pct"), ("Missing Top-10 labels", "top10_missing"),
               ("Invalid Top-10 labels", "top10_invalid"), ("Top-10 / peak-rank disagreements", "top10_peak_disagreement"),
               ("Earliest first chart date", "date_min"), ("Latest first chart date", "date_max"),
               ("Missing selected lyrics", "lyrics_missing"), ("Blank selected lyrics", "lyrics_blank")]
    lines += table(["Metric", "Full", "2000–2022", "Excluded"],
                   [(label, *(fmt(s[key]) for s in (a, b, e))) for label, key in metrics])
    lines += ["Artist counts are distinct credited strings, not resolved individual performers: collaborations count as credits. "
              "The normalized count uses existing artist_norm without further normalization. "
              "Top-10 prevalence is the share with existing top10=1 (ever reaching peak rank ≤10); "
              "the denominator includes all songs, and missing/invalid labels are separately reported. "
              "Artist counts across subsets need not add because artists can occur in both.", "",
              f"Top-10 prevalence changes by {fmt(b['top10_pct'] - a['top10_pct']) if b['n'] and a['n'] else 'NA'} "
              "percentage points versus the full assembled sample. This describes a date-selected cohort, not a causal effect.", "",
              "## Yearly song counts", "",
              "Counts refer to first chart appearance, not chart activity in that year. Zero-count analysis years are included.", ""]
    years = sorted(set(range(2000, 2023)) | {y for y in a["yearly"] if y is not None})
    lines += table(["Year", "Full", "2000–2022"],
                   [(y, a["yearly"].get(y, 0), b["yearly"].get(y, 0)) for y in years])
    lines += ["## Missing audio predictors", "",
              "Counts and percentages use all songs in the corresponding population. Numeric predictors are the existing "
              "candidate medians; key_mode and mode_mode are categorical modes. Missing means null, nonfinite numeric, "
              "or blank categorical value. Zero is a valid value. Any-missing counts songs once, not missing cells.", ""]
    lines += table(["Predictor", "Full missing", "2000–2022 missing"],
                   [(c, rate(a["audio_missing"][c], a["n"]), rate(b["audio_missing"][c], b["n"])) for c in AUDIO] +
                   [("Any predictor", rate(a["any_audio_missing"], a["n"]), rate(b["any_audio_missing"], b["n"]))])
    lines += ["## Raw lyric length", "",
              "Words are whitespace-delimited tokens in selected raw lyrics; characters are Unicode code points including "
              "spaces and line breaks. Missing lyrics are excluded from length statistics; blanks are included. "
              "Mean is arithmetic average; median is the 50th percentile; min/max are observed extremes. "
              "Percentiles use linear interpolation and describe the lower tail (1/5%), middle (25/75%) and upper tail "
              "(95/99%). These are descriptive lengths, not cleaned NLP features. No lyric text is printed.", ""]
    lines += table(["Statistic", "Full words", "Sample words", "Full characters", "Sample characters"],
                   [(key, fmt(a['words'][key]), fmt(b['words'][key]), fmt(a['characters'][key]),
                     fmt(b['characters'][key])) for key in b['words']])
    lines += ["## Lyric confidence", "",
              "Existing confidence measures agreement among matched Spotify candidates, not semantic accuracy or language. "
              "High: single candidate or consistent lyrics; medium: differing lyrics with a strict-majority group; "
              "low: missing/blank candidates, tied groups or a plurality without majority.", ""]
    levels = sorted(set(a['confidence']) | set(b['confidence']), key=str)
    lines += table(["Confidence", "Full", "2000–2022"],
                   [(str(c) if c is not None else "Missing", rate(a['confidence'].get(c, 0), a['n']),
                     rate(b['confidence'].get(c, 0), b['n'])) for c in levels])
    lines += ["## Consistency and available Grammy outcomes", "",
              "Each cell shows true / false / missing counts; percentages refer to true / all songs. "
              "These flags overlap and must not be added together.", ""]
    lines += table(["Flag", "Full true / false / missing", "Sample true / false / missing", "Sample true %"],
                   [(c, ' / '.join(fmt(v) for v in a['flags'][c].values()),
                     ' / '.join(fmt(v) for v in b['flags'][c].values()),
                     fmt(percent(b['flags'][c]['true'], b['n']))) for c in FLAGS])
    lines += ["Strict consistency means a single Spotify candidate OR agreement of both lyrics and audio across candidates; "
              "it does not guarantee completeness for single-candidate songs. any_missing_audio_value and "
              "any_missing_or_blank_lyrics describe any original candidate, whereas the tables above describe consolidated "
              "predictors and selected lyrics. Categorical mode ties can yield missing predictors even with complete candidates.", "",
              "Grammy fields cover Song of the Year only. Eligibility is the existing coverage flag, not a new rule inferred "
              "from chart dates. Per reports/modelling_base_summary.md, eligible unmatched songs have false outcomes and "
              "2024 outcomes are null. A false nomination label therefore means no accepted link in this assembly, "
              "not proof of no nomination. Winners are a subset of nominees; version ambiguity flags uncertain versions.", "",
              "## Research decisions before modelling", "",
              f"- Missing consolidated audio affects {rate(b['any_audio_missing'], b['n'])}. Decide imputation versus "
              "complete-case analysis; dropping rows changes the population. Mode ties and candidate missingness are distinct causes.",
              f"- Low-confidence lyrics affect {rate(b['confidence'].get('low', 0), b['n'])}; "
              f"strict consistency retains {rate(b['flags']['strict_consistency_sample']['true'], b['n'])}. "
              "Choose the primary inclusion rule and a sensitivity analysis; neither flag is a guarantee of correct matching.",
              "- Inspect unusually short/long lyric lengths before choosing later cleaning rules; repetition, annotations and "
              "non-English text may remain. No such diagnosis or exclusions are made here.",
              "- Grammy positives are sparse and depend on matching coverage; decide how to treat version ambiguity and "
              "unmatched negatives before using these secondary outcomes.",
              "- This is the assembled matched Billboard population, not all released songs or all Billboard entries. "
              "The restriction changes era composition. Artist repetition and time-dependent coverage require consideration "
              "in later evaluation design; chart success is observational and does not identify a causal lyric effect.",
              "- Peak rank and chart weeks use available chart history, not a fixed follow-up period. Check comparable "
              "follow-up and Grammy coverage before interpreting outcome differences across years.", ""]
    return '\n'.join(lines)


def main():
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    full = pl.read_parquet(SOURCE)
    sample = restrict_dates(full)
    report = render_report(full, sample, source_hash)
    # Only these new stage-09 outputs are written; no upstream imports or execution.
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    sample.write_parquet(OUTPUT)
    if not pl.read_parquet(OUTPUT).equals(sample):
        raise RuntimeError("Saved subset differs from the date-filtered source")
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != source_hash:
        raise RuntimeError("Authoritative source changed during execution")
    REPORT.write_text(report, encoding="utf-8")
    s = summarize(sample)
    print(f"Saved {s['n']:,} songs; {s['artists']:,} artist credits; Top-10 {rate(s['top10'], s['n'])}.")
    print(f"Report: {REPORT.relative_to(ROOT)}; source SHA-256 unchanged: {source_hash}")


if __name__ == "__main__":
    main()
