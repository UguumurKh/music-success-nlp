# Conservative match-expansion audit

Candidate generation only; no candidates accepted or selected.

## Three-way overlap (existing exact candidates)

```json
{
  "billboard_songs_matched_to_spotify": 5888,
  "billboard_songs_matched_to_grammy": 125,
  "billboard_songs_matched_to_both": 96,
  "pair_counts": {
    "billboard_grammy_pairs": 125,
    "no_spotify_candidate": 29,
    "one_spotify_candidate": 23,
    "multiple_spotify_candidates": 73,
    "distinct_billboard_songs_with_both": 96
  },
  "winners": {
    "billboard_grammy_pairs": 20,
    "no_spotify_candidate": 3,
    "one_spotify_candidate": 3,
    "multiple_spotify_candidates": 14,
    "distinct_billboard_songs_with_both": 17
  },
  "non_winning_nominees": {
    "billboard_grammy_pairs": 105,
    "no_spotify_candidate": 26,
    "one_spotify_candidate": 20,
    "multiple_spotify_candidates": 59,
    "distinct_billboard_songs_with_both": 79
  },
  "definition": "Existing exact candidates only; distinct shared Spotify IDs per Billboard–Grammy pair, not cross-products of different track IDs."
}
```

## Unmatched diagnoses

```json
{
  "billboard": {
    "all": {
      "exact_title_exists_artist_differs": 2461,
      "exact_artist_exists_title_differs": 805,
      "title_and_artist_exist_separately": 1012,
      "neither_exact_title_nor_artist_exists": 842,
      "unusable_or_blank_key": 0
    },
    "subgroups": {
      "Top 10": {
        "exact_title_exists_artist_differs": 407,
        "exact_artist_exists_title_differs": 69,
        "title_and_artist_exist_separately": 94,
        "neither_exact_title_nor_artist_exists": 61,
        "unusable_or_blank_key": 0
      },
      "Non-Top-10": {
        "exact_title_exists_artist_differs": 2054,
        "exact_artist_exists_title_differs": 736,
        "title_and_artist_exist_separately": 918,
        "neither_exact_title_nor_artist_exists": 781,
        "unusable_or_blank_key": 0
      }
    }
  },
  "grammy": {
    "all": {
      "exact_title_exists_artist_differs": 20,
      "exact_artist_exists_title_differs": 9,
      "title_and_artist_exist_separately": 14,
      "neither_exact_title_nor_artist_exists": 2,
      "unusable_or_blank_key": 0
    },
    "subgroups": {
      "Winners": {
        "exact_title_exists_artist_differs": 2,
        "exact_artist_exists_title_differs": 2,
        "title_and_artist_exist_separately": 4,
        "neither_exact_title_nor_artist_exists": 0,
        "unusable_or_blank_key": 0
      },
      "Non-winning nominees": {
        "exact_title_exists_artist_differs": 18,
        "exact_artist_exists_title_differs": 7,
        "title_and_artist_exist_separately": 10,
        "neither_exact_title_nor_artist_exists": 2,
        "unusable_or_blank_key": 0
      }
    }
  }
}
```

## Variant collision counts

```json
[
  {
    "tier": 1,
    "variant_keys": 844978,
    "raw_text_collision_keys": 13866,
    "new_collision_keys": 761,
    "multiple_spotify_id_keys": 85496,
    "multiple_billboard_record_keys": 3,
    "multiple_grammy_record_keys": 0
  },
  {
    "tier": 2,
    "variant_keys": 803876,
    "raw_text_collision_keys": 42293,
    "new_collision_keys": 31386,
    "multiple_spotify_id_keys": 103231,
    "multiple_billboard_record_keys": 44,
    "multiple_grammy_record_keys": 0
  },
  {
    "tier": 3,
    "variant_keys": 803027,
    "raw_text_collision_keys": 42994,
    "new_collision_keys": 32092,
    "multiple_spotify_id_keys": 103237,
    "multiple_billboard_record_keys": 49,
    "multiple_grammy_record_keys": 0
  }
]
```

## billboard–spotify

```json
{
  "all_tiers_combined": {
    "previously_unmatched": 5120,
    "with_variant_candidates": 1046,
    "one_candidate": 669,
    "multiple_candidates": 377,
    "still_without_candidate": 4074,
    "pct_of_previously_unmatched": 20.4296875
  },
  "tiers": [
    {
      "tier": 1,
      "candidate_rows": 1034,
      "source_records_with_candidates": 754,
      "one_candidate": 561,
      "multiple_candidates": 193,
      "newly_covered_after_earlier_tiers": 754,
      "incremental_percentage_points_of_all_source": 6.849563953488372,
      "examples": [
        {
          "billboard_source_row": 13,
          "billboard_raw_title": "\"Beamer, Benz, Or Bentley\"",
          "billboard_raw_artist": "Lloyd Banks Featuring Juelz Santana",
          "spotify_id": "1GPG59ArrhLpnR8AqxMz2X",
          "candidate_tier": 1
        },
        {
          "billboard_source_row": 49,
          "billboard_raw_title": "\"Hold On, We're Going Home\"",
          "billboard_raw_artist": "Drake Featuring Majid Jordan",
          "spotify_id": "0FyBloIEdLS3f3SodFiju1",
          "candidate_tier": 1
        },
        {
          "billboard_source_row": 49,
          "billboard_raw_title": "\"Hold On, We're Going Home\"",
          "billboard_raw_artist": "Drake Featuring Majid Jordan",
          "spotify_id": "14Rcq31SafFBHNEwXrtR2B",
          "candidate_tier": 1
        },
        {
          "billboard_source_row": 49,
          "billboard_raw_title": "\"Hold On, We're Going Home\"",
          "billboard_raw_artist": "Drake Featuring Majid Jordan",
          "spotify_id": "6jdOi5U5LBzQrc4c1VT983",
          "candidate_tier": 1
        },
        {
          "billboard_source_row": 67,
          "billboard_raw_title": "\"Lean Wit It, Rock Wit It\"",
          "billboard_raw_artist": "Dem Franchize Boyz Featuring Lil Peanut & Charlay",
          "spotify_id": "7cVmKBwzPsh4Fmb6SplfEm",
          "candidate_tier": 1
        }
      ]
    },
    {
      "tier": 2,
      "candidate_rows": 363,
      "source_records_with_candidates": 210,
      "one_candidate": 119,
      "multiple_candidates": 91,
      "newly_covered_after_earlier_tiers": 210,
      "incremental_percentage_points_of_all_source": 1.907703488372093,
      "examples": [
        {
          "billboard_source_row": 44,
          "billboard_raw_title": "\"Hello, I Love You\"",
          "billboard_raw_artist": "Glee Cast",
          "spotify_id": "5xQDTc1hpyHPbdUQP2sWyB",
          "candidate_tier": 2
        },
        {
          "billboard_source_row": 60,
          "billboard_raw_title": "\"It's A Man's, Man's Man's World\"",
          "billboard_raw_artist": "Glee Cast",
          "spotify_id": "79MUzUStA60r6XweR9T4iP",
          "candidate_tier": 2
        },
        {
          "billboard_source_row": 153,
          "billboard_raw_title": "(You Want To) Make A Memory",
          "billboard_raw_artist": "Bon Jovi",
          "spotify_id": "09ln4QumFqjIkfCFiW9aRk",
          "candidate_tier": 2
        },
        {
          "billboard_source_row": 205,
          "billboard_raw_title": "22 (Taylor's Version)",
          "billboard_raw_artist": "Taylor Swift",
          "spotify_id": "1mQRQlbf1nXbazPEuSyij8",
          "candidate_tier": 2
        },
        {
          "billboard_source_row": 205,
          "billboard_raw_title": "22 (Taylor's Version)",
          "billboard_raw_artist": "Taylor Swift",
          "spotify_id": "2ULNeSomDxVNmdDy8VxEBU",
          "candidate_tier": 2
        }
      ]
    },
    {
      "tier": 3,
      "candidate_rows": 1734,
      "source_records_with_candidates": 1046,
      "one_candidate": 669,
      "multiple_candidates": 377,
      "newly_covered_after_earlier_tiers": 82,
      "incremental_percentage_points_of_all_source": 0.7449127906976745,
      "examples": [
        {
          "billboard_source_row": 13,
          "billboard_raw_title": "\"Beamer, Benz, Or Bentley\"",
          "billboard_raw_artist": "Lloyd Banks Featuring Juelz Santana",
          "spotify_id": "1GPG59ArrhLpnR8AqxMz2X",
          "candidate_tier": 3
        },
        {
          "billboard_source_row": 44,
          "billboard_raw_title": "\"Hello, I Love You\"",
          "billboard_raw_artist": "Glee Cast",
          "spotify_id": "5xQDTc1hpyHPbdUQP2sWyB",
          "candidate_tier": 3
        },
        {
          "billboard_source_row": 49,
          "billboard_raw_title": "\"Hold On, We're Going Home\"",
          "billboard_raw_artist": "Drake Featuring Majid Jordan",
          "spotify_id": "0FyBloIEdLS3f3SodFiju1",
          "candidate_tier": 3
        },
        {
          "billboard_source_row": 49,
          "billboard_raw_title": "\"Hold On, We're Going Home\"",
          "billboard_raw_artist": "Drake Featuring Majid Jordan",
          "spotify_id": "14Rcq31SafFBHNEwXrtR2B",
          "candidate_tier": 3
        },
        {
          "billboard_source_row": 49,
          "billboard_raw_title": "\"Hold On, We're Going Home\"",
          "billboard_raw_artist": "Drake Featuring Majid Jordan",
          "spotify_id": "6jdOi5U5LBzQrc4c1VT983",
          "candidate_tier": 3
        }
      ]
    }
  ],
  "additional_percentage_points_of_all_source": 9.502180232558139,
  "subgroups": {
    "Top 10": {
      "combined": {
        "previously_unmatched": 631,
        "with_variant_candidates": 239,
        "one_candidate": 115,
        "multiple_candidates": 124,
        "still_without_candidate": 392,
        "pct_of_previously_unmatched": 37.87638668779715
      },
      "per_tier": [
        {
          "tier": 1,
          "source_records_with_candidates": 198
        },
        {
          "tier": 2,
          "source_records_with_candidates": 18
        },
        {
          "tier": 3,
          "source_records_with_candidates": 239
        }
      ]
    },
    "Non-Top-10": {
      "combined": {
        "previously_unmatched": 4489,
        "with_variant_candidates": 807,
        "one_candidate": 554,
        "multiple_candidates": 253,
        "still_without_candidate": 3682,
        "pct_of_previously_unmatched": 17.97727779015371
      },
      "per_tier": [
        {
          "tier": 1,
          "source_records_with_candidates": 556
        },
        {
          "tier": 2,
          "source_records_with_candidates": 192
        },
        {
          "tier": 3,
          "source_records_with_candidates": 807
        }
      ]
    }
  },
  "candidate_rows_including_repeated_tiers": 3131,
  "distinct_source_target_pairs": 1734
}
```

## grammy–spotify

```json
{
  "all_tiers_combined": {
    "previously_unmatched": 45,
    "with_variant_candidates": 10,
    "one_candidate": 5,
    "multiple_candidates": 5,
    "still_without_candidate": 35,
    "pct_of_previously_unmatched": 22.22222222222222
  },
  "tiers": [
    {
      "tier": 1,
      "candidate_rows": 9,
      "source_records_with_candidates": 6,
      "one_candidate": 4,
      "multiple_candidates": 2,
      "newly_covered_after_earlier_tiers": 6,
      "incremental_percentage_points_of_all_source": 4.0,
      "examples": [
        {
          "grammy_source_row": 17268,
          "grammy_raw_title": "Umbrella",
          "grammy_raw_artist": "Rihanna Featuring Jay-Z",
          "spotify_id": "1YiD079ne2nl9TEOrw43Gh",
          "candidate_tier": 1
        },
        {
          "grammy_source_row": 17268,
          "grammy_raw_title": "Umbrella",
          "grammy_raw_artist": "Rihanna Featuring Jay-Z",
          "spotify_id": "2Y2ud3awMZHDxOCpDebiv3",
          "candidate_tier": 1
        },
        {
          "grammy_source_row": 17268,
          "grammy_raw_title": "Umbrella",
          "grammy_raw_artist": "Rihanna Featuring Jay-Z",
          "spotify_id": "49FYlytm3dAAraYgpoJZux",
          "candidate_tier": 1
        },
        {
          "grammy_source_row": 17824,
          "grammy_raw_title": "American Boy",
          "grammy_raw_artist": "Estelle Featuring Kanye West",
          "spotify_id": "6etwirSInfuJrSOlogS6Sh",
          "candidate_tier": 1
        },
        {
          "grammy_source_row": 18838,
          "grammy_raw_title": "Love The Way You Lie",
          "grammy_raw_artist": "Eminem Featuring Rihanna",
          "spotify_id": "15JINEqzVMv3SvJTAXAKED",
          "candidate_tier": 1
        }
      ]
    },
    {
      "tier": 2,
      "candidate_rows": 7,
      "source_records_with_candidates": 3,
      "one_candidate": 1,
      "multiple_candidates": 2,
      "newly_covered_after_earlier_tiers": 3,
      "incremental_percentage_points_of_all_source": 2.0,
      "examples": [
        {
          "grammy_source_row": 20543,
          "grammy_raw_title": "Stay With Me (Darkchild Version)",
          "grammy_raw_artist": "Sam Smith",
          "spotify_id": "31CHJzSweI6r1dk6XrZceK",
          "candidate_tier": 2
        },
        {
          "grammy_source_row": 20543,
          "grammy_raw_title": "Stay With Me (Darkchild Version)",
          "grammy_raw_artist": "Sam Smith",
          "spotify_id": "4qjDMhpqlSQABkLD9lmAxi",
          "candidate_tier": 2
        },
        {
          "grammy_source_row": 20543,
          "grammy_raw_title": "Stay With Me (Darkchild Version)",
          "grammy_raw_artist": "Sam Smith",
          "spotify_id": "5Db9VIdDsN5yu3Eu7CT0i4",
          "candidate_tier": 2
        },
        {
          "grammy_source_row": 20543,
          "grammy_raw_title": "Stay With Me (Darkchild Version)",
          "grammy_raw_artist": "Sam Smith",
          "spotify_id": "5Nm9ERjJZ5oyfXZTECKmRt",
          "candidate_tier": 2
        },
        {
          "grammy_source_row": 22230,
          "grammy_raw_title": "Shallow",
          "grammy_raw_artist": "Lady Gaga & Bradley Cooper",
          "spotify_id": "7ehMJ4S5RF1HWLkyTIxxaO",
          "candidate_tier": 2
        }
      ]
    },
    {
      "tier": 3,
      "candidate_rows": 20,
      "source_records_with_candidates": 10,
      "one_candidate": 5,
      "multiple_candidates": 5,
      "newly_covered_after_earlier_tiers": 1,
      "incremental_percentage_points_of_all_source": 0.6666666666666666,
      "examples": [
        {
          "grammy_source_row": 17268,
          "grammy_raw_title": "Umbrella",
          "grammy_raw_artist": "Rihanna Featuring Jay-Z",
          "spotify_id": "1YiD079ne2nl9TEOrw43Gh",
          "candidate_tier": 3
        },
        {
          "grammy_source_row": 17268,
          "grammy_raw_title": "Umbrella",
          "grammy_raw_artist": "Rihanna Featuring Jay-Z",
          "spotify_id": "2Y2ud3awMZHDxOCpDebiv3",
          "candidate_tier": 3
        },
        {
          "grammy_source_row": 17268,
          "grammy_raw_title": "Umbrella",
          "grammy_raw_artist": "Rihanna Featuring Jay-Z",
          "spotify_id": "49FYlytm3dAAraYgpoJZux",
          "candidate_tier": 3
        },
        {
          "grammy_source_row": 17268,
          "grammy_raw_title": "Umbrella",
          "grammy_raw_artist": "Rihanna Featuring Jay-Z",
          "spotify_id": "0akeTLXxLSGzmKd0nWvAPE",
          "candidate_tier": 3
        },
        {
          "grammy_source_row": 17824,
          "grammy_raw_title": "American Boy",
          "grammy_raw_artist": "Estelle Featuring Kanye West",
          "spotify_id": "6etwirSInfuJrSOlogS6Sh",
          "candidate_tier": 3
        }
      ]
    }
  ],
  "additional_percentage_points_of_all_source": 6.666666666666667,
  "subgroups": {
    "Winners": {
      "combined": {
        "previously_unmatched": 8,
        "with_variant_candidates": 2,
        "one_candidate": 1,
        "multiple_candidates": 1,
        "still_without_candidate": 6,
        "pct_of_previously_unmatched": 25.0
      },
      "per_tier": [
        {
          "tier": 1,
          "source_records_with_candidates": 1
        },
        {
          "tier": 2,
          "source_records_with_candidates": 1
        },
        {
          "tier": 3,
          "source_records_with_candidates": 2
        }
      ]
    },
    "Non-winning nominees": {
      "combined": {
        "previously_unmatched": 37,
        "with_variant_candidates": 8,
        "one_candidate": 4,
        "multiple_candidates": 4,
        "still_without_candidate": 29,
        "pct_of_previously_unmatched": 21.62162162162162
      },
      "per_tier": [
        {
          "tier": 1,
          "source_records_with_candidates": 5
        },
        {
          "tier": 2,
          "source_records_with_candidates": 2
        },
        {
          "tier": 3,
          "source_records_with_candidates": 8
        }
      ]
    }
  },
  "candidate_rows_including_repeated_tiers": 36,
  "distinct_source_target_pairs": 20
}
```

## billboard–grammy

```json
{
  "all_tiers_combined": {
    "previously_unmatched": 25,
    "with_variant_candidates": 1,
    "one_candidate": 1,
    "multiple_candidates": 0,
    "still_without_candidate": 24,
    "pct_of_previously_unmatched": 4.0
  },
  "tiers": [
    {
      "tier": 1,
      "candidate_rows": 0,
      "source_records_with_candidates": 0,
      "one_candidate": 0,
      "multiple_candidates": 0,
      "newly_covered_after_earlier_tiers": 0,
      "incremental_percentage_points_of_all_source": 0.0,
      "examples": []
    },
    {
      "tier": 2,
      "candidate_rows": 1,
      "source_records_with_candidates": 1,
      "one_candidate": 1,
      "multiple_candidates": 0,
      "newly_covered_after_earlier_tiers": 1,
      "incremental_percentage_points_of_all_source": 0.6666666666666666,
      "examples": [
        {
          "grammy_source_row": 20543,
          "grammy_raw_title": "Stay With Me (Darkchild Version)",
          "grammy_raw_artist": "Sam Smith",
          "billboard_source_row": 8750,
          "candidate_tier": 2
        }
      ]
    },
    {
      "tier": 3,
      "candidate_rows": 1,
      "source_records_with_candidates": 1,
      "one_candidate": 1,
      "multiple_candidates": 0,
      "newly_covered_after_earlier_tiers": 0,
      "incremental_percentage_points_of_all_source": 0.0,
      "examples": [
        {
          "grammy_source_row": 20543,
          "grammy_raw_title": "Stay With Me (Darkchild Version)",
          "grammy_raw_artist": "Sam Smith",
          "billboard_source_row": 8750,
          "candidate_tier": 3
        }
      ]
    }
  ],
  "additional_percentage_points_of_all_source": 0.6666666666666666,
  "subgroups": {
    "Winners": {
      "combined": {
        "previously_unmatched": 5,
        "with_variant_candidates": 1,
        "one_candidate": 1,
        "multiple_candidates": 0,
        "still_without_candidate": 4,
        "pct_of_previously_unmatched": 20.0
      },
      "per_tier": [
        {
          "tier": 1,
          "source_records_with_candidates": 0
        },
        {
          "tier": 2,
          "source_records_with_candidates": 1
        },
        {
          "tier": 3,
          "source_records_with_candidates": 1
        }
      ]
    },
    "Non-winning nominees": {
      "combined": {
        "previously_unmatched": 20,
        "with_variant_candidates": 0,
        "one_candidate": 0,
        "multiple_candidates": 0,
        "still_without_candidate": 20,
        "pct_of_previously_unmatched": 0.0
      },
      "per_tier": [
        {
          "tier": 1,
          "source_records_with_candidates": 0
        },
        {
          "tier": 2,
          "source_records_with_candidates": 0
        },
        {
          "tier": 3,
          "source_records_with_candidates": 0
        }
      ]
    }
  },
  "candidate_rows_including_repeated_tiers": 2,
  "distinct_source_target_pairs": 1,
  "year_gap_distribution_distinct_pairs": [
    {
      "year_gap": 0,
      "len": 1
    }
  ],
  "unusual_year_gap_distinct_pairs": 0
}
```

## Methodological limitations

- All outputs are unaccepted candidates. No exact candidate files or earlier reports are changed. No fuzzy similarity, Spotify ID selection or final modelling dataset is used.
- Tier 1 compares original title keys plus primary artists; tier 2 base titles plus original artists; tier 3 both variants. Every matching pair/tier is retained. Incremental coverage counts new source records after earlier tiers for reporting only, never as a selection rule.
- Grammy original matching keys are audited title_match_norm and performer_norm; variant functions operate on song_or_album and performer_extracted. Billboard uses Song/Artist; Spotify uses name/artists. Existing normalization fields remain intact.
- The identical title-base function does not strip '(Single)' because it is not an authorized version term. The four already-audited Grammy Single-label removals remain in original_title_key for tier 1; tiers 2/3 use raw-title version stripping only.
- Featuring/feat/ft removal requires a separate explicit marker followed by an artist suffix. Commas, ampersands, and, x and semicolons are not split. Removing featured artists can create false candidates.
- Version suffix removal is lexical, not semantic verification. Explicit keywords in meaningful trailing descriptions can still trigger removal. Unrecognized version labels are retained; hyphen separators require surrounding spaces. Review all expansions.
- Diagnosis counts Spotify IDs by title and artist separately with at most three sorted ID examples per field, not title-only or artist-only Cartesian candidates. Separately-existing keys take precedence over title-only and artist-only reasons. Blank keys take precedence over all other reasons.
- variant_collision_review.csv contains EVERY usable tier/key, not only flagged keys. New collision means distinct original normalized title–artist keys collapse into one tier/key across the three sources. Counts per tier overlap and should not be summed as unique identities. Missing/empty tier keys never match.
- Billboard–Grammy expansion applies only to Grammy records with no prior Billboard–Grammy exact pair (independent of Spotify status). Year gaps 0 or 1 are flagged plausible but never accepted automatically; all other gaps remain.
- Outcome columns are used only to report coverage, never to rank or choose candidates. Coverage differences can create selection bias. No candidate does not establish absence from Spotify; multiple IDs may be releases or distinct recordings.
- Sing and Sing! retain separate Billboard source-row IDs. Normalized-key equality, lyric equality and audio equality do not establish identity.

## Validation

```json
{
  "protected_files_unchanged": true,
  "protected_file_count": 52,
  "exact_candidates_unchanged": true,
  "unmatched_only": true,
  "tier_keys_validated": true,
  "original_columns_unchanged": true,
  "sing_records_separate": true,
  "parquet_roundtrips_passed": true,
  "no_fuzzy_matching": true,
  "no_candidate_selection": true,
  "no_final_modelling_dataset": true
}
```

## Outputs

- `data/interim/billboard_spotify_variant_candidates.parquet`
- `data/interim/grammy_spotify_variant_candidates.parquet`
- `data/interim/billboard_grammy_variant_candidates.parquet`
- `reports/billboard_spotify_variant_review.csv`
- `reports/grammy_spotify_variant_review.csv`
- `reports/billboard_grammy_variant_review.csv`
- `reports/billboard_unmatched_diagnosis.csv`
- `reports/grammy_unmatched_diagnosis.csv`
- `reports/variant_collision_review.csv`
- `reports/match_expansion_audit.md`
- `reports/match_expansion_audit.json`

## Run

```powershell
uv run python -m unittest discover -s tests -v
uv run python src/04_match_expansion_audit.py
uv run python -m unittest discover -s tests -v
```
