# Billboard analysis sample: 2000–2022

Source: `data/processed/billboard_model_base.parquet` (authoritative assembled sample).
Source SHA-256: `f0e178f2d2bcb6dbf4392295fd4fd3e6e609f128a8d16809d4e593a9c439fc69`.
Output: `data/processed/billboard_analysis_2000_2022.parquet`.

One observation is one Billboard song identified by `billboard_source_row`. Keep first_chart_date from 2000-01-01 through 2022-12-31 inclusive; preserve every column and value. Both source and subset have unique, non-null identifiers. No language or content filtering is applied.

## Population and comparison

Retained 6,546 (98.60%); excluded 93 songs. Before 2000: 0; after 2022: 93; missing dates: 0.

| Metric | Full | 2000–2022 | Excluded |
| --- | --- | --- | --- |
| Observations | 6,639 | 6,546 | 93 |
| Unique artist credits (raw Artist) | 2,283 | 2,253 | 66 |
| Unique normalized artist credits | 2,283 | 2,253 | 66 |
| Missing artist credits | 0 | 0 | 0 |
| Top-10 songs | 1,000 | 993 | 7 |
| Top-10 % of all songs | 15.06 | 15.17 | 7.53 |
| Missing Top-10 labels | 0 | 0 | 0 |
| Invalid Top-10 labels | 0 | 0 | 0 |
| Top-10 / peak-rank disagreements | 0 | 0 | 0 |
| Earliest first chart date | 2000-01-05 | 2000-01-05 | 2023-01-04 |
| Latest first chart date | 2024-09-18 | 2022-12-28 | 2024-09-18 |
| Missing selected lyrics | 0 | 0 | 0 |
| Blank selected lyrics | 0 | 0 | 0 |

Artist counts are distinct credited strings, not resolved individual performers: collaborations count as credits. The normalized count uses existing artist_norm without further normalization. Top-10 prevalence is the share with existing top10=1 (ever reaching peak rank ≤10); the denominator includes all songs, and missing/invalid labels are separately reported. Artist counts across subsets need not add because artists can occur in both.

Top-10 prevalence changes by 0.11 percentage points versus the full assembled sample. This describes a date-selected cohort, not a causal effect.

## Yearly song counts

Counts refer to first chart appearance, not chart activity in that year. Zero-count analysis years are included.

| Year | Full | 2000–2022 |
| --- | --- | --- |
| 2000 | 223 | 223 |
| 2001 | 191 | 191 |
| 2002 | 200 | 200 |
| 2003 | 225 | 225 |
| 2004 | 212 | 212 |
| 2005 | 249 | 249 |
| 2006 | 253 | 253 |
| 2007 | 259 | 259 |
| 2008 | 270 | 270 |
| 2009 | 295 | 295 |
| 2010 | 297 | 297 |
| 2011 | 342 | 342 |
| 2012 | 240 | 240 |
| 2013 | 269 | 269 |
| 2014 | 286 | 286 |
| 2015 | 288 | 288 |
| 2016 | 318 | 318 |
| 2017 | 330 | 330 |
| 2018 | 389 | 389 |
| 2019 | 337 | 337 |
| 2020 | 441 | 441 |
| 2021 | 287 | 287 |
| 2022 | 345 | 345 |
| 2023 | 81 | 0 |
| 2024 | 12 | 0 |

## Missing audio predictors

Counts and percentages use all songs in the corresponding population. Numeric predictors are the existing candidate medians; key_mode and mode_mode are categorical modes. Missing means null, nonfinite numeric, or blank categorical value. Zero is a valid value. Any-missing counts songs once, not missing cells.

| Predictor | Full missing | 2000–2022 missing |
| --- | --- | --- |
| danceability_median | 0 (0.00%) | 0 (0.00%) |
| energy_median | 0 (0.00%) | 0 (0.00%) |
| loudness_median | 0 (0.00%) | 0 (0.00%) |
| speechiness_median | 0 (0.00%) | 0 (0.00%) |
| acousticness_median | 0 (0.00%) | 0 (0.00%) |
| instrumentalness_median | 0 (0.00%) | 0 (0.00%) |
| liveness_median | 0 (0.00%) | 0 (0.00%) |
| valence_median | 0 (0.00%) | 0 (0.00%) |
| tempo_median | 0 (0.00%) | 0 (0.00%) |
| duration_ms_median | 0 (0.00%) | 0 (0.00%) |
| key_mode | 761 (11.46%) | 756 (11.55%) |
| mode_mode | 709 (10.68%) | 704 (10.75%) |
| Any predictor | 762 (11.48%) | 757 (11.56%) |

## Raw lyric length

Words are whitespace-delimited tokens in selected raw lyrics; characters are Unicode code points including spaces and line breaks. Missing lyrics are excluded from length statistics; blanks are included. Mean is arithmetic average; median is the 50th percentile; min/max are observed extremes. Percentiles use linear interpolation and describe the lower tail (1/5%), middle (25/75%) and upper tail (95/99%). These are descriptive lengths, not cleaned NLP features. No lyric text is printed.

| Statistic | Full words | Sample words | Full characters | Sample characters |
| --- | --- | --- | --- | --- |
| n | 6,639 | 6,546 | 6,639 | 6,546 |
| mean | 532.69 | 535.01 | 2,729.12 | 2,740.83 |
| min | 10 | 10 | 62 | 62 |
| p01 | 142.00 | 142.00 | 741.04 | 741.60 |
| p05 | 206.00 | 206.00 | 1,053.80 | 1,051.25 |
| p25 | 295.00 | 295.00 | 1,506.00 | 1,507.00 |
| median | 392.00 | 394.00 | 2,009.00 | 2,018.00 |
| p75 | 592.00 | 595.75 | 3,032.00 | 3,047.75 |
| p95 | 1,420.00 | 1,432.50 | 7,346.40 | 7,365.25 |
| p99 | 2,509.86 | 2,511.55 | 12,826.20 | 12,852.00 |
| max | 5,000 | 5,000 | 26,023 | 26,023 |

## Lyric confidence

Existing confidence measures agreement among matched Spotify candidates, not semantic accuracy or language. High: single candidate or consistent lyrics; medium: differing lyrics with a strict-majority group; low: missing/blank candidates, tied groups or a plurality without majority.

| Confidence | Full | 2000–2022 |
| --- | --- | --- |
| high | 5,330 (80.28%) | 5,239 (80.03%) |
| low | 827 (12.46%) | 827 (12.63%) |
| medium | 482 (7.26%) | 480 (7.33%) |

## Consistency and available Grammy outcomes

Each cell shows true / false / missing counts; percentages refer to true / all songs. These flags overlap and must not be added together.

| Flag | Full true / false / missing | Sample true / false / missing | Sample true % |
| --- | --- | --- | --- |
| strict_consistency_sample | 3,981 / 2,658 / 0 | 3,900 / 2,646 / 0 | 59.58 |
| lyrics_consistent_across_ids | 5,330 / 1,309 / 0 | 5,239 / 1,307 / 0 | 80.03 |
| audio_consistent_across_ids | 4,068 / 2,571 / 0 | 3,987 / 2,559 / 0 | 60.91 |
| any_missing_audio_value | 0 / 6,639 / 0 | 0 / 6,546 / 0 | 0.00 |
| any_missing_or_blank_lyrics | 0 / 6,639 / 0 | 0 / 6,546 / 0 | 0.00 |
| key_mode_tie | 761 / 5,878 / 0 | 756 / 5,790 / 0 | 11.55 |
| mode_mode_tie | 709 / 5,930 / 0 | 704 / 5,842 / 0 | 10.75 |
| grammy_soty_eligible | 6,627 / 12 / 0 | 6,546 / 0 / 0 | 100.00 |
| grammy_soty_nominated | 106 / 6,521 / 12 | 105 / 6,441 / 0 | 1.60 |
| grammy_soty_winner | 19 / 6,608 / 12 | 19 / 6,527 / 0 | 0.29 |
| grammy_version_ambiguity | 2 / 6,637 / 0 | 2 / 6,544 / 0 | 0.03 |

Strict consistency means a single Spotify candidate OR agreement of both lyrics and audio across candidates; it does not guarantee completeness for single-candidate songs. any_missing_audio_value and any_missing_or_blank_lyrics describe any original candidate, whereas the tables above describe consolidated predictors and selected lyrics. Categorical mode ties can yield missing predictors even with complete candidates.

Grammy fields cover Song of the Year only. Eligibility is the existing coverage flag, not a new rule inferred from chart dates. Per reports/modelling_base_summary.md, eligible unmatched songs have false outcomes and 2024 outcomes are null. A false nomination label therefore means no accepted link in this assembly, not proof of no nomination. Winners are a subset of nominees; version ambiguity flags uncertain versions.

## Research decisions before modelling

- Missing consolidated audio affects 757 (11.56%). Decide imputation versus complete-case analysis; dropping rows changes the population. Mode ties and candidate missingness are distinct causes.
- Low-confidence lyrics affect 827 (12.63%); strict consistency retains 3,900 (59.58%). Choose the primary inclusion rule and a sensitivity analysis; neither flag is a guarantee of correct matching.
- Inspect unusually short/long lyric lengths before choosing later cleaning rules; repetition, annotations and non-English text may remain. No such diagnosis or exclusions are made here.
- Grammy positives are sparse and depend on matching coverage; decide how to treat version ambiguity and unmatched negatives before using these secondary outcomes.
- This is the assembled matched Billboard population, not all released songs or all Billboard entries. The restriction changes era composition. Artist repetition and time-dependent coverage require consideration in later evaluation design; chart success is observational and does not identify a causal lyric effect.
- Peak rank and chart weeks use available chart history, not a fixed follow-up period. Check comparable follow-up and Grammy coverage before interpreting outcome differences across years.
