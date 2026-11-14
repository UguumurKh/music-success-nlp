# Grammy–Billboard candidate audit

Manual-review support only; no relationships accepted or rejected.

```json
{
  "grammy_records": 150,
  "accepted_relationships": 125,
  "grammy_records_already_accepted": 125,
  "still_unmatched": 25,
  "unmatched_with_at_least_one_candidate": 25,
  "unmatched_with_plausible_candidate": 2,
  "unmatched_without_plausible_candidate": 23,
  "unmatched_with_no_candidate": 0,
  "widened_search_records": 23,
  "candidate_rows": 125,
  "review_rows": 125,
  "candidate_counts_by_strength": {
    "strong": 1,
    "possible": 1,
    "weak": 123
  },
  "year_gap_distribution": {
    "-1": 39,
    "0": 39,
    "1": 25,
    "2": 22
  },
  "prior_variant_input_rows": 2,
  "prior_variant_distinct_pairs": 1,
  "rapidfuzz_version": "3.14.6",
  "outputs": [
    "reports/grammy_billboard_manual_review.csv",
    "reports/grammy_billboard_manual_review_guide.md",
    "reports/grammy_billboard_candidate_audit.md",
    "reports/grammy_billboard_candidate_audit.json",
    "src/08a_prepare_grammy_billboard_review.py",
    "tests/test_grammy_billboard_review.py"
  ],
  "validation": {
    "all_unmatched_represented": true,
    "csv_roundtrip_passed": true,
    "outcomes_excluded": true,
    "no_automatic_decisions": true,
    "no_outcome_labels_created": true,
    "no_lyrics": true,
    "no_nlp_or_modelling": true,
    "protected_files_unchanged": true
  }
}
```

## Method

All similarity scores are RapidFuzz fuzz.ratio (normalized Indel similarity), 0–100,
with processor=None and no token sorting or partial matching. Blank inputs score zero.
Title scoring uses the existing Grammy title_match_norm (only the trailing source
(Single) label was removed) and Billboard title_norm; original title_norm is also
retained. Full artists use performer_norm and artist_norm. Primary artists use the
existing conservative normalization after splitting only explicit Featuring/feat/ft
markers. Ampersands, And, semicolons and group names are not split. Version words stay.

Combined score = 0.60 * title + 0.25 * full artist + 0.15 * primary artist.
A plausible candidate requires title >= 65, max(full artist, primary artist) >= 65,
and combined >= 70. Strong requires title >= 90, max(artist scores) >= 90 and
combined >= 90. Possible means plausible but not strong; all others are weak.
These heuristic thresholds are uncalibrated review guidance, not match probabilities
or acceptance criteria. Rounded scores (six decimals) are used consistently.

Initially consider Grammy year minus first-chart year in {0, 1}. Only if no plausible
candidate exists in that full initial pool, search {-1, 0, 1, 2}. The whole shortlist
then carries widened_minus1_to2, even if an individual candidate has gap 0 or 1.
Rank plausible candidates first, then combined, title, full-artist and primary-artist
scores descending, then Billboard source_row ascending. Keep at most five. Weak
suggestions may fill remaining slots and are retained even when none is plausible.
If the entire widened pool is empty, retain one no_candidate placeholder with null
Billboard fields, rank and scores; this is not counted as a candidate or strength.
Billboard IDs are the original Parquet row position plus one, as in Phase 3.

The prior variant manual-review file supplies provenance only (deduplicated tiers).
It never affects ranking. Already accepted Grammy source records are excluded using
distinct Grammy IDs, not relationship row counts. No success outcomes, lyrics or
Spotify content enter scoring, ranking or these reports. No new outcome labels,
acceptance decisions, NLP features or models are created.

## Unmatched record coverage

| Grammy ID | Year | Title | Candidates | Plausible | Window |
|---|---|---|---:|---|---|
| 13531 | 2000 | Say My Name (Single) | 5 | False | widened_minus1_to2 |
| 13534 | 2000 | Breathe (Single) | 5 | False | widened_minus1_to2 |
| 14043 | 2001 | Drops Of Jupiter | 5 | True | initial_0_to1 |
| 15098 | 2003 | Keep Me In Your Heart | 5 | False | widened_minus1_to2 |
| 18840 | 2010 | Fuck You | 5 | False | widened_minus1_to2 |
| 18841 | 2010 | Beg Steal Or Borrow | 5 | False | widened_minus1_to2 |
| 19270 | 2011 | Holocene | 5 | False | widened_minus1_to2 |
| 19273 | 2011 | All Of The Lights | 5 | False | widened_minus1_to2 |
| 20120 | 2013 | Just Give Me A Reason | 5 | True | initial_0_to1 |
| 20543 | 2014 | Stay With Me (Darkchild Version) | 5 | False | widened_minus1_to2 |
| 22232 | 2018 | The Joke | 5 | False | widened_minus1_to2 |
| 22664 | 2019 | Norman F***ing Rockwell | 5 | False | widened_minus1_to2 |
| 22666 | 2019 | Hard Place | 5 | False | widened_minus1_to2 |
| 22667 | 2019 | Bring My Flowers Now | 5 | False | widened_minus1_to2 |
| 23103 | 2020 | I Can't Breathe | 5 | False | widened_minus1_to2 |
| 23561 | 2021 | Right On Time | 5 | False | widened_minus1_to2 |
| 23566 | 2021 | Fight For You | 5 | False | widened_minus1_to2 |
| 23568 | 2021 | A Beautiful Noise | 5 | False | widened_minus1_to2 |
| 23570 | 2021 | Leave The Door Open | 5 | False | widened_minus1_to2 |
| 24048 | 2022 | All Too Well (10 Minute Version) (The Short Film) | 5 | False | widened_minus1_to2 |
| 24051 | 2022 | Just Like That | 5 | False | widened_minus1_to2 |
| 24537 | 2023 | Dance The Night (From Barbie The Album) | 5 | False | widened_minus1_to2 |
| 24538 | 2023 | Butterfly | 5 | False | widened_minus1_to2 |
| 24540 | 2023 | A&W | 5 | False | widened_minus1_to2 |
| 24541 | 2023 | What Was I Made For? [From The Motion Picture   Barbie  ] | 5 | False | widened_minus1_to2 |

Integrity: 102 protected files unchanged. Raw CSVs checked by size/mtime without opening; other protected files checked by SHA256.
