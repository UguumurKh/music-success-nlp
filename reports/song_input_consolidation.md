# Song-level input consolidation

Outcome-blind lyric selection and independent audio aggregation.

## Billboard

**6,639 source records**; **3,981** in the strict-consistency sample.

```json
{
  "source_records": 6639,
  "single_id": 3719,
  "multi_id": 2920,
  "lyrics_consistent": 5330,
  "audio_consistent": 4068,
  "strict_consistency_sample_size": 3981,
  "lyric_confidence": {
    "high": 5330,
    "medium": 482,
    "low": 827
  },
  "audio_confidence": {
    "high": 4068,
    "medium": 1809,
    "low": 762
  },
  "lyric_group_ties": 776,
  "unique_plurality_without_majority": 51,
  "key_ties": 761,
  "mode_ties": 709,
  "any_missing_audio": 0,
  "candidate_id_count_distribution": [
    {
      "lyric_candidate_id_count": 1,
      "len": 3719
    },
    {
      "lyric_candidate_id_count": 2,
      "len": 1841
    },
    {
      "lyric_candidate_id_count": 3,
      "len": 637
    },
    {
      "lyric_candidate_id_count": 4,
      "len": 244
    },
    {
      "lyric_candidate_id_count": 5,
      "len": 69
    },
    {
      "lyric_candidate_id_count": 6,
      "len": 46
    },
    {
      "lyric_candidate_id_count": 7,
      "len": 32
    },
    {
      "lyric_candidate_id_count": 8,
      "len": 12
    },
    {
      "lyric_candidate_id_count": 9,
      "len": 13
    },
    {
      "lyric_candidate_id_count": 10,
      "len": 7
    },
    {
      "lyric_candidate_id_count": 11,
      "len": 1
    },
    {
      "lyric_candidate_id_count": 12,
      "len": 5
    },
    {
      "lyric_candidate_id_count": 14,
      "len": 1
    },
    {
      "lyric_candidate_id_count": 15,
      "len": 2
    },
    {
      "lyric_candidate_id_count": 16,
      "len": 1
    },
    {
      "lyric_candidate_id_count": 17,
      "len": 1
    },
    {
      "lyric_candidate_id_count": 18,
      "len": 2
    },
    {
      "lyric_candidate_id_count": 22,
      "len": 1
    },
    {
      "lyric_candidate_id_count": 23,
      "len": 1
    },
    {
      "lyric_candidate_id_count": 24,
      "len": 1
    },
    {
      "lyric_candidate_id_count": 27,
      "len": 1
    },
    {
      "lyric_candidate_id_count": 30,
      "len": 1
    },
    {
      "lyric_candidate_id_count": 32,
      "len": 1
    }
  ],
  "dominant_lyric_group_share": {
    "median": 1.0,
    "max": 1.0
  },
  "audio_range_summaries": {
    "danceability": {
      "mean": 0.008471456544660342,
      "median": 0.0,
      "max": 0.305,
      "nonzero_records": 2018
    },
    "energy": {
      "mean": 0.007735577647236031,
      "median": 0.0,
      "max": 0.6890000000000001,
      "nonzero_records": 2000
    },
    "loudness": {
      "mean": 0.18768157855098663,
      "median": 0.0,
      "max": 12.721,
      "nonzero_records": 2003
    },
    "speechiness": {
      "mean": 0.004304488627805393,
      "median": 0.0,
      "max": 0.506,
      "nonzero_records": 2082
    },
    "acousticness": {
      "mean": 0.007395873239945777,
      "median": 0.0,
      "max": 0.968483,
      "nonzero_records": 2066
    },
    "instrumentalness": {
      "mean": 0.0015661381593613498,
      "median": 0.0,
      "max": 0.95,
      "nonzero_records": 1011
    },
    "liveness": {
      "mean": 0.01296559722849827,
      "median": 0.0,
      "max": 0.8854,
      "nonzero_records": 1958
    },
    "valence": {
      "mean": 0.010162178038861274,
      "median": 0.0,
      "max": 0.636,
      "nonzero_records": 2111
    },
    "tempo": {
      "mean": 2.1863386052116285,
      "median": 0.0,
      "max": 104.10300000000001,
      "nonzero_records": 2174
    },
    "duration_ms": {
      "mean": 947.8880855550535,
      "median": 0.0,
      "max": 599960.0,
      "nonzero_records": 1641
    }
  },
  "outcome_field": "top10",
  "full_sample_outcomes": {
    "positive": 1000,
    "negative": 5639
  },
  "strict_sample_outcomes": {
    "positive": 416,
    "negative": 3565
  },
  "low_confidence_review_records": 1309
}
```

## Grammy

**111 source records**; **35** in the strict-consistency sample.

```json
{
  "source_records": 111,
  "single_id": 29,
  "multi_id": 82,
  "lyrics_consistent": 62,
  "audio_consistent": 37,
  "strict_consistency_sample_size": 35,
  "lyric_confidence": {
    "high": 62,
    "medium": 30,
    "low": 19
  },
  "audio_confidence": {
    "high": 37,
    "medium": 61,
    "low": 13
  },
  "lyric_group_ties": 16,
  "unique_plurality_without_majority": 3,
  "key_ties": 13,
  "mode_ties": 12,
  "any_missing_audio": 0,
  "candidate_id_count_distribution": [
    {
      "lyric_candidate_id_count": 1,
      "len": 29
    },
    {
      "lyric_candidate_id_count": 2,
      "len": 31
    },
    {
      "lyric_candidate_id_count": 3,
      "len": 22
    },
    {
      "lyric_candidate_id_count": 4,
      "len": 13
    },
    {
      "lyric_candidate_id_count": 5,
      "len": 3
    },
    {
      "lyric_candidate_id_count": 6,
      "len": 3
    },
    {
      "lyric_candidate_id_count": 7,
      "len": 5
    },
    {
      "lyric_candidate_id_count": 8,
      "len": 1
    },
    {
      "lyric_candidate_id_count": 9,
      "len": 1
    },
    {
      "lyric_candidate_id_count": 10,
      "len": 1
    },
    {
      "lyric_candidate_id_count": 16,
      "len": 1
    },
    {
      "lyric_candidate_id_count": 18,
      "len": 1
    }
  ],
  "dominant_lyric_group_share": {
    "median": 1.0,
    "max": 1.0
  },
  "audio_range_summaries": {
    "danceability": {
      "mean": 0.02494594594594593,
      "median": 0.001000000000000112,
      "max": 0.21000000000000002,
      "nonzero_records": 65
    },
    "energy": {
      "mean": 0.02245045045045045,
      "median": 0.0030000000000000027,
      "max": 0.41500000000000004,
      "nonzero_records": 66
    },
    "loudness": {
      "mean": 0.5946756756756756,
      "median": 0.01399999999999979,
      "max": 12.721,
      "nonzero_records": 63
    },
    "speechiness": {
      "mean": 0.009163063063063064,
      "median": 0.00030000000000000165,
      "max": 0.21900000000000003,
      "nonzero_records": 64
    },
    "acousticness": {
      "mean": 0.022483783783783778,
      "median": 0.002,
      "max": 0.595,
      "nonzero_records": 66
    },
    "instrumentalness": {
      "mean": 0.0012226374774774779,
      "median": 0.0,
      "max": 0.0539,
      "nonzero_records": 35
    },
    "liveness": {
      "mean": 0.019327927927927927,
      "median": 0.0010000000000000009,
      "max": 0.5603,
      "nonzero_records": 61
    },
    "valence": {
      "mean": 0.021991891891891897,
      "median": 0.0030000000000000027,
      "max": 0.4939999999999999,
      "nonzero_records": 67
    },
    "tempo": {
      "mean": 6.178810810810812,
      "median": 0.010000000000005116,
      "max": 89.98100000000001,
      "nonzero_records": 68
    },
    "duration_ms": {
      "mean": 1271.1801801801803,
      "median": 0.0,
      "max": 24843.0,
      "nonzero_records": 52
    }
  },
  "outcome_field": "grammy_winner",
  "full_sample_outcomes": {
    "positive": 18,
    "negative": 93
  },
  "strict_sample_outcomes": {
    "positive": 4,
    "negative": 31
  },
  "low_confidence_review_records": 28
}
```

## Decisions and interpretation

- Comparison text applies only Unicode NFKC, casefold, whitespace collapse and trim. Punctuation, words and repetitions remain. Original raw lyrics are never modified; their original UTF-8 hash is retained.
- IDs vote equally for comparison-lyric groups. Choose the largest group; break group ties with the lexicographically smallest ID across tied groups. Within the selected group choose its smallest ID. The ID is a reproducible technical tie-breaker, not evidence of the historically correct chart recording.
- A unique largest group without a strict majority (e.g. 2–1–1) has low lyric confidence and an explicit unique-plurality flag. Medium requires >50% support. Missing/blank comparison lyrics are also low confidence. This closes the unspecified non-majority case without changing the requested selection rule.
- Audio medians/minima/maxima/ranges use all distinct accepted IDs, never only the lyric group or representative. Missing/nonfinite numeric values are excluded per variable and flagged; all missing yields null. Key/mode are unique modes of original non-null values, with null on ties. Mixed named/numeric text encodings remain distinct; no recoding is performed.
- Audio confidence is low for any missing audio or categorical tie, even for one ID; otherwise high for one ID or identical audio, and medium for differing audio. Complete audio consistency requires all fields observed. Full-tuple distinct counts and complete-only distinct counts are both reported.
- Strict consistency is one ID OR identical comparison lyrics and one complete audio combination. Thus a single-ID row remains in the strict sample even if its audio is missing, as explicitly specified. The same output rows and flags support later lyrics-only, audio-only and combined models; no model-specific sample is created here.
- Metadata/outcomes are attached after content-only consolidation. Outcomes are used only in post-consolidation descriptive counts. All accepted match methods are retained as source-level indicators; no outcome influences an ID vote, tie-break or audio aggregate.
- Low-confidence review CSVs contain rows with low lyric OR low audio confidence. The per-candidate lyric ledger and all reports omit both raw lyrics and comparison text; only Parquet contains text. Earlier inputs/reports/code are hashed unchanged, while raw CSVs are not opened and are checked by size/mtime.
- No fuzzy matching, NLP feature extraction or model training was performed. Comparison hashes/counts are consolidation diagnostics only. Outputs are consolidated song inputs, not a final joined modelling dataset.

## Validation

```json
{
  "unique_source_grains_verified": true,
  "accepted_sets_fully_represented": true,
  "raw_lyrics_preserved": true,
  "comparison_did_not_change_original_content": true,
  "prior_candidate_counts_agree": true,
  "parquet_roundtrips_passed": true,
  "protected_files_unchanged": true,
  "protected_file_count": 85,
  "outcomes_used_only_for_reporting": true,
  "no_fuzzy_matching": true,
  "no_nlp_feature_extraction": true,
  "no_modelling": true
}
```

## Files

- `data/interim/billboard_song_level_consolidated.parquet`
- `data/interim/grammy_song_level_consolidated.parquet`
- `reports/song_input_consolidation.md`
- `reports/song_input_consolidation.json`
- `reports/billboard_low_confidence_consolidation.csv`
- `reports/grammy_low_confidence_consolidation.csv`
- `reports/lyric_selection_ledger.csv`

## Run

```powershell
uv run python -m unittest discover -s tests -v
uv run python src/07_consolidate_song_inputs.py
uv run python -m unittest discover -s tests -v
```
