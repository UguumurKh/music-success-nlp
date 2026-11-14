# Match-policy and candidate-consolidation audit

Accepted relationships are sets of candidate IDs, not selected recordings.

## Billboard accepted coverage

| Group | Total | Exact accepted | Added safe Tier 1 | Accepted total | Coverage % | Still unmatched |
|---|---:|---:|---:|---:|---:|---:|
| All | 11008 | 5886 | 753 | 6639 | 60.31 | 4369 |
| Top 10 | 1433 | 802 | 198 | 1000 | 69.78 | 433 |
| Non-Top-10 | 9575 | 5084 | 555 | 5639 | 58.89 | 3936 |

### Consolidation (all accepted records)

```json
{
  "single_spotify_id": 3719,
  "multiple_ids_identical_lyrics_and_audio": 261,
  "multiple_ids_identical_lyrics_different_audio": 1285,
  "multiple_ids_different_lyrics_identical_audio": 88,
  "multiple_ids_different_lyrics_and_audio": 1286,
  "missing_lyrics_information": 0
}
```

### Quarantine and manual review

```json
{
  "exact_candidate_rows_quarantined": 2,
  "exact_source_records_quarantined": 2,
  "tier1_rows_accepted": 1031,
  "tier1_rows_manual_review": 3,
  "tier1_manual_review_sources": 1,
  "tier1_manual_reasons": [
    {
      "policy_reason": "source_normalization_collision",
      "len": 3
    }
  ],
  "title_version_candidate_rows_not_accepted": 2097,
  "exact_collision_source_rows": 2,
  "tier1_collision_source_rows": 6
}
```

### Coverage comparison

```json
{
  "group1_accepted": 1000,
  "group1_n": 1433,
  "group2_accepted": 5639,
  "group2_n": 9575,
  "group1_coverage_pct": 69.78367062107466,
  "group2_coverage_pct": 58.8929503916449,
  "difference_percentage_points": 10.890720229429762,
  "risk_ratio": 1.184924004605054,
  "difference_95pct_ci_percentage_points": [
    8.271913381445328,
    13.414555313329934
  ],
  "ci_method": "Newcombe hybrid score (independent Wilson intervals, no continuity correction)",
  "z_statistic": 7.858885148202821,
  "two_sided_p_value": 3.875673914914118e-15,
  "null_hypothesis": "equal coverage proportions",
  "test_method": "pooled two-sample proportion z-test, no continuity correction",
  "group1_label": "Top 10",
  "group2_label": "Non-Top-10"
}
```
## Grammy accepted coverage

| Group | Total | Exact accepted | Added safe Tier 1 | Accepted total | Coverage % | Still unmatched |
|---|---:|---:|---:|---:|---:|---:|
| All | 150 | 105 | 6 | 111 | 74.00 | 39 |
| Winners | 25 | 17 | 1 | 18 | 72.00 | 7 |
| Non-winning nominees | 125 | 88 | 5 | 93 | 74.40 | 32 |

### Consolidation (all accepted records)

```json
{
  "single_spotify_id": 29,
  "multiple_ids_identical_lyrics_and_audio": 6,
  "multiple_ids_identical_lyrics_different_audio": 25,
  "multiple_ids_different_lyrics_identical_audio": 2,
  "multiple_ids_different_lyrics_and_audio": 49,
  "missing_lyrics_information": 0
}
```

### Quarantine and manual review

```json
{
  "exact_candidate_rows_quarantined": 0,
  "exact_source_records_quarantined": 0,
  "tier1_rows_accepted": 9,
  "tier1_rows_manual_review": 0,
  "tier1_manual_review_sources": 0,
  "tier1_manual_reasons": [],
  "title_version_candidate_rows_not_accepted": 27,
  "exact_collision_source_rows": 0,
  "tier1_collision_source_rows": 0
}
```

### Coverage comparison

```json
{
  "group1_accepted": 18,
  "group1_n": 25,
  "group2_accepted": 93,
  "group2_n": 125,
  "group1_coverage_pct": 72.0,
  "group2_coverage_pct": 74.4,
  "difference_percentage_points": -2.400000000000002,
  "risk_ratio": 0.9677419354838709,
  "difference_95pct_ci_percentage_points": [
    -23.138228732301965,
    13.631038250313013
  ],
  "ci_method": "Newcombe hybrid score (independent Wilson intervals, no continuity correction)",
  "group1_label": "Winners",
  "group2_label": "Non-winning nominees"
}
```

## Billboard–Grammy

```json
{
  "accepted_exact_pairs": 125,
  "manual_variant_rows": 2,
  "manual_distinct_variant_pairs": 1
}
```

## Decisions and limitations

- Exact relationships are accepted only outside source-key collisions. Collision identity is the raw title plus raw artist/parsed performer, within each source. Grammy year alone does not make a new identity. Exact keys and Tier-1 title/primary keys are audited across all source records, including records already exact-matched.
- Exact source collisions block both exact and Tier-1 acceptance. Tier-1 source collisions block Tier 1 only. The collision CSV lists all flagged source/rule rows, even where no candidate is available; candidate impact counts are separately reported. Sing and Sing! stay separate and both are quarantined.
- Safe Tier 1 requires complete normalized title equality and either one usable explicit feature suffix with primary equal to the other complete artist, or equal primary and featured suffixes on both sides. No comma, ampersand, and, x or semicolon splitting is used.
- All Tier 2/3 evidence is rejected from the primary candidate set. Taylor's Version, other possessive version labels, remixes, live/acoustic/instrumental and other versions remain part of complete accepted title keys. Earlier variant files are unchanged.
- Accepted Parquets contain one source–Spotify-ID relationship per row, original source fields, all methods, strongest method and exact/safe-Tier-1 indicators. They intentionally do not select a metadata row from Spotify. Diagnostics join every indexed metadata row for every accepted ID. Exact is the strongest METHOD, never a preference for one track ID.
- Consolidation missing-lyrics status takes precedence, including for a single ID, when any lyric flag is missing/blank or hash is null/empty. Otherwise single ID precedes the four multiple-ID categories. Known lyric-hash distinct counts exclude nulls. Audio comparison uses all 12 original fields as a tuple, including null patterns if present; missing audio is separately flagged. Equality of missing patterns is not proof of measured audio equality. Album counts exclude null but preserve literal blanks.
- All 125 existing Billboard–Grammy exact rows are copied unchanged. All additional variant evidence stays in manual review with both full source records, years, gaps, tiers and keys.
- Coverage outcomes are used only after relationship acceptance and consolidation, never to select, rank or reject Spotify candidates. Statistical significance does not measure the practical size of selection bias. These source tables are not random population samples; independence assumptions may fail for repeated artists/works, so inference is exploratory.
- Grammy winner comparisons are descriptive with a difference confidence interval; only 25 winner records make precision limited. No formal winner/non-winner z-test is reported.
- Raw CSVs are never opened. Their size/mtime are checked, not rehashed; all existing non-raw data/report/code inputs are SHA-256 checked before/after. No raw lyrics extraction, fuzzy matching, representative ID selection, audio aggregation or final modelling dataset is performed.

Statistical definitions: [NIST two-proportion z-test](https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/diffprci.htm) and [Newcombe difference-interval documentation](https://www.statsmodels.org/dev/generated/statsmodels.stats.proportion.confint_proportions_2indep.html). Formulas are implemented with the Python standard library; no additional package is required.

## Validation

```json
{
  "protected_files_unchanged": true,
  "protected_file_count": 65,
  "raw_files_not_opened": true,
  "raw_metadata_unchanged": true,
  "all_nonraw_protected_hashes_unchanged": true,
  "parquet_roundtrips": {
    "billboard_spotify_accepted_candidates": 11758,
    "grammy_spotify_accepted_candidates": 338,
    "billboard_grammy_accepted_pairs": 125
  },
  "billboard_grammy_exact_unchanged": true,
  "sing_quarantined": true,
  "no_fuzzy_matching": true,
  "no_representative_id_selection": true,
  "no_audio_aggregation": true,
  "no_raw_lyrics_extraction": true,
  "no_final_modelling_dataset": true
}
```

## Files

- `data/interim/billboard_spotify_accepted_candidates.parquet`
- `data/interim/grammy_spotify_accepted_candidates.parquet`
- `data/interim/billboard_grammy_accepted_pairs.parquet`
- `reports/tier1_manual_review.csv`
- `reports/title_version_candidates_not_accepted.csv`
- `reports/source_normalization_collision_quarantine.csv`
- `reports/billboard_grammy_variant_manual_review.csv`
- `reports/billboard_spotify_consolidation_status.csv`
- `reports/grammy_spotify_consolidation_status.csv`
- `reports/match_policy_audit.md`
- `reports/match_policy_audit.json`

## Run

```powershell
uv run python -m unittest discover -s tests -v
uv run python src/05_apply_match_policy.py
uv run python -m unittest discover -s tests -v
```
