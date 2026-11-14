# Yearly Billboard–Spotify matching coverage

Matching coverage falls from 55.65% in 2022 to 13.39% in 2023 and 1.96% in 2024. The much lower representation of the original Billboard cohorts supports excluding 2023–2024 from the analysis. Coverage alone does not establish the cause of missing matches or prove that earlier cohorts are unbiased.

**Definition:** matched integrated song–artist records / original Billboard song–artist records × 100. Each record is assigned to the calendar year of `first_chart_date` in both datasets; this is not Spotify release year or the year of each weekly chart appearance. Percentages are rounded to two decimals.

**Denominator:** `data/interim/billboard_song_level_2000_2024.parquet` (11,008 records), the project's original prepared, pre-matching Billboard cohort. This contains distinct original `Song`/`Artist` pairs first charting in 2000–2024 after the existing source preparation quarantines; it is not a count of raw weekly rows. Source preparation computes first chart date across the full available chart history before the period filter.

**Numerator:** `data/interim/billboard_song_level_consolidated.parquet` (6,639 records). Verified to have exactly the same song–artist/date records as `data/processed/billboard_model_base.parquet`. Includes all consolidated matches, without strict-consistency, language, lyric-quality, or 2000–2022 filters.

| Year | Original Billboard song–artist records | Matched integrated records | Matching coverage |
|---|---:|---:|---:|
| 2000 | 311 | 223 | 71.70% |
| 2001 | 288 | 191 | 66.32% |
| 2002 | 302 | 200 | 66.23% |
| 2003 | 313 | 225 | 71.88% |
| 2004 | 301 | 212 | 70.43% |
| 2005 | 340 | 249 | 73.24% |
| 2006 | 366 | 253 | 69.13% |
| 2007 | 352 | 259 | 73.58% |
| 2008 | 418 | 270 | 64.59% |
| 2009 | 428 | 295 | 68.93% |
| 2010 | 478 | 297 | 62.13% |
| 2011 | 474 | 342 | 72.15% |
| 2012 | 363 | 240 | 66.12% |
| 2013 | 381 | 269 | 70.60% |
| 2014 | 372 | 286 | 76.88% |
| 2015 | 390 | 288 | 73.85% |
| 2016 | 401 | 318 | 79.30% |
| 2017 | 453 | 330 | 72.85% |
| 2018 | 591 | 389 | 65.82% |
| 2019 | 518 | 337 | 65.06% |
| 2020 | 686 | 441 | 64.29% |
| 2021 | 644 | 287 | 44.57% |
| 2022 | 620 | 345 | 55.65% |
| 2023 | 605 | 81 | 13.39% |
| 2024 | 613 | 12 | 1.96% |

**Overall:** 6,639 / 11,008 = 60.31% (ratio of totals).

**Validation:** no duplicate song–artist keys or missing keys/dates in the three inputs; every matched record belongs to the original cohort with the identical first chart date; yearly counts reconcile to source totals. Inputs were read only; no earlier stages were rerun.

**Reproduce:** `.venv/Scripts/python.exe src/report_yearly_matching_coverage.py`.
