# Conservative exact-match audit

Candidate generation only; no selection, merging or fuzzy matching.

## Billboard–Spotify

| Group | Source records | At least one | One ID | Multiple IDs | Unmatched | Coverage % |
|---|---:|---:|---:|---:|---:|---:|
| All | 11008 | 5888 | 3160 | 2728 | 5120 | 53.49 |
| Top 10 | 1433 | 802 | 256 | 546 | 631 | 55.97 |
| Non-Top-10 | 9575 | 5086 | 2904 | 2182 | 4489 | 53.12 |

### Candidate-count distribution

```json
[
  {
    "distinct_spotify_ids": 0,
    "source_records": 5120
  },
  {
    "distinct_spotify_ids": 1,
    "source_records": 3160
  },
  {
    "distinct_spotify_ids": 2,
    "source_records": 1700
  },
  {
    "distinct_spotify_ids": 3,
    "source_records": 603
  },
  {
    "distinct_spotify_ids": 4,
    "source_records": 233
  },
  {
    "distinct_spotify_ids": 5,
    "source_records": 69
  },
  {
    "distinct_spotify_ids": 6,
    "source_records": 43
  },
  {
    "distinct_spotify_ids": 7,
    "source_records": 30
  },
  {
    "distinct_spotify_ids": 8,
    "source_records": 12
  },
  {
    "distinct_spotify_ids": 9,
    "source_records": 13
  },
  {
    "distinct_spotify_ids": 10,
    "source_records": 6
  },
  {
    "distinct_spotify_ids": 11,
    "source_records": 1
  },
  {
    "distinct_spotify_ids": 12,
    "source_records": 5
  },
  {
    "distinct_spotify_ids": 14,
    "source_records": 1
  },
  {
    "distinct_spotify_ids": 15,
    "source_records": 2
  },
  {
    "distinct_spotify_ids": 16,
    "source_records": 1
  },
  {
    "distinct_spotify_ids": 17,
    "source_records": 1
  },
  {
    "distinct_spotify_ids": 18,
    "source_records": 2
  },
  {
    "distinct_spotify_ids": 22,
    "source_records": 1
  },
  {
    "distinct_spotify_ids": 23,
    "source_records": 1
  },
  {
    "distinct_spotify_ids": 24,
    "source_records": 1
  },
  {
    "distinct_spotify_ids": 27,
    "source_records": 1
  },
  {
    "distinct_spotify_ids": 30,
    "source_records": 1
  },
  {
    "distinct_spotify_ids": 32,
    "source_records": 1
  }
]
```

### Ambiguity diagnostics

```json
{
  "same_known_lyric_hash": 1472,
  "different_known_lyric_hashes": 1256,
  "any_unknown_lyric_hash": 0,
  "same_audio_combination": 332,
  "different_audio_combinations": 2396,
  "any_missing_or_blank_lyrics": 0,
  "any_conflicting_spotify_id": 0
}
```

### Ambiguous examples

```json
[
  {
    "source_row": 5449,
    "Song": "Let It Snow! Let It Snow! Let It Snow!",
    "Artist": "Dean Martin",
    "match_status": "multiple_exact_candidates",
    "distinct_spotify_ids": 32,
    "candidate_rows": 32,
    "distinct_lyric_sha256": 4,
    "distinct_audio_combinations": 6,
    "any_missing_or_blank_lyrics": false
  },
  {
    "source_row": 6249,
    "Song": "Mistletoe",
    "Artist": "Justin Bieber",
    "match_status": "multiple_exact_candidates",
    "distinct_spotify_ids": 30,
    "candidate_rows": 30,
    "distinct_lyric_sha256": 1,
    "distinct_audio_combinations": 2,
    "any_missing_or_blank_lyrics": false
  },
  {
    "source_row": 5354,
    "Song": "Last Last",
    "Artist": "Burna Boy",
    "match_status": "multiple_exact_candidates",
    "distinct_spotify_ids": 27,
    "candidate_rows": 27,
    "distinct_lyric_sha256": 4,
    "distinct_audio_combinations": 2,
    "any_missing_or_blank_lyrics": false
  },
  {
    "source_row": 2061,
    "Song": "Cozy Little Christmas",
    "Artist": "Katy Perry",
    "match_status": "multiple_exact_candidates",
    "distinct_spotify_ids": 24,
    "candidate_rows": 24,
    "distinct_lyric_sha256": 1,
    "distinct_audio_combinations": 2,
    "any_missing_or_blank_lyrics": false
  },
  {
    "source_row": 3139,
    "Song": "First Class",
    "Artist": "Jack Harlow",
    "match_status": "multiple_exact_candidates",
    "distinct_spotify_ids": 23,
    "candidate_rows": 23,
    "distinct_lyric_sha256": 2,
    "distinct_audio_combinations": 2,
    "any_missing_or_blank_lyrics": false
  }
]
```

### Unmatched examples

```json
[
  {
    "source_row": 3,
    "Song": "\"1, 2 Step\"",
    "Artist": "Ciara Featuring Missy Elliott",
    "match_status": "no_exact_candidate",
    "distinct_spotify_ids": 0,
    "candidate_rows": 0,
    "distinct_lyric_sha256": 0,
    "distinct_audio_combinations": 0,
    "any_missing_or_blank_lyrics": false
  },
  {
    "source_row": 7,
    "Song": "\"Angel, Pt. 1\"",
    "Artist": "\"Kodak Black, NLE Choppa, Jimin, JVKE & Muni Long\"",
    "match_status": "no_exact_candidate",
    "distinct_spotify_ids": 0,
    "candidate_rows": 0,
    "distinct_lyric_sha256": 0,
    "distinct_audio_combinations": 0,
    "any_missing_or_blank_lyrics": false
  },
  {
    "source_row": 10,
    "Song": "\"Baby, Come Over (This Is Our Night)\"",
    "Artist": "Samantha Mumba",
    "match_status": "no_exact_candidate",
    "distinct_spotify_ids": 0,
    "candidate_rows": 0,
    "distinct_lyric_sha256": 0,
    "distinct_audio_combinations": 0,
    "any_missing_or_blank_lyrics": false
  },
  {
    "source_row": 11,
    "Song": "\"Baby, I'm Jealous\"",
    "Artist": "Bebe Rexha Featuring Doja Cat",
    "match_status": "no_exact_candidate",
    "distinct_spotify_ids": 0,
    "candidate_rows": 0,
    "distinct_lyric_sha256": 0,
    "distinct_audio_combinations": 0,
    "any_missing_or_blank_lyrics": false
  },
  {
    "source_row": 12,
    "Song": "\"Baby, It's Cold Outside\"",
    "Artist": "Glee Cast",
    "match_status": "no_exact_candidate",
    "distinct_spotify_ids": 0,
    "candidate_rows": 0,
    "distinct_lyric_sha256": 0,
    "distinct_audio_combinations": 0,
    "any_missing_or_blank_lyrics": false
  }
]
```
## Grammy–Spotify

| Group | Source records | At least one | One ID | Multiple IDs | Unmatched | Coverage % |
|---|---:|---:|---:|---:|---:|---:|
| All | 150 | 105 | 25 | 80 | 45 | 70.00 |
| Winners | 25 | 17 | 3 | 14 | 8 | 68.00 |
| Non-winning nominees | 125 | 88 | 22 | 66 | 37 | 70.40 |

### Candidate-count distribution

```json
[
  {
    "distinct_spotify_ids": 0,
    "source_records": 45
  },
  {
    "distinct_spotify_ids": 1,
    "source_records": 25
  },
  {
    "distinct_spotify_ids": 2,
    "source_records": 30
  },
  {
    "distinct_spotify_ids": 3,
    "source_records": 21
  },
  {
    "distinct_spotify_ids": 4,
    "source_records": 13
  },
  {
    "distinct_spotify_ids": 5,
    "source_records": 3
  },
  {
    "distinct_spotify_ids": 6,
    "source_records": 3
  },
  {
    "distinct_spotify_ids": 7,
    "source_records": 5
  },
  {
    "distinct_spotify_ids": 8,
    "source_records": 1
  },
  {
    "distinct_spotify_ids": 9,
    "source_records": 1
  },
  {
    "distinct_spotify_ids": 10,
    "source_records": 1
  },
  {
    "distinct_spotify_ids": 16,
    "source_records": 1
  },
  {
    "distinct_spotify_ids": 18,
    "source_records": 1
  }
]
```

### Ambiguity diagnostics

```json
{
  "same_known_lyric_hash": 30,
  "different_known_lyric_hashes": 50,
  "any_unknown_lyric_hash": 0,
  "same_audio_combination": 8,
  "different_audio_combinations": 72,
  "any_missing_or_blank_lyrics": 0,
  "any_conflicting_spotify_id": 0
}
```

### Ambiguous examples

```json
[
  {
    "source_row": 24049,
    "song_or_album": "About Damn Time",
    "performer_extracted": "Lizzo",
    "match_status": "multiple_exact_candidates",
    "distinct_spotify_ids": 18,
    "candidate_rows": 18,
    "distinct_lyric_sha256": 3,
    "distinct_audio_combinations": 2,
    "any_missing_or_blank_lyrics": false
  },
  {
    "source_row": 18371,
    "song_or_album": "Poker Face",
    "performer_extracted": "Lady Gaga",
    "match_status": "multiple_exact_candidates",
    "distinct_spotify_ids": 16,
    "candidate_rows": 16,
    "distinct_lyric_sha256": 2,
    "distinct_audio_combinations": 7,
    "any_missing_or_blank_lyrics": false
  },
  {
    "source_row": 24050,
    "song_or_album": "abcdefu",
    "performer_extracted": "GAYLE",
    "match_status": "multiple_exact_candidates",
    "distinct_spotify_ids": 10,
    "candidate_rows": 10,
    "distinct_lyric_sha256": 2,
    "distinct_audio_combinations": 1,
    "any_missing_or_blank_lyrics": false
  },
  {
    "source_row": 22662,
    "song_or_album": "Truth Hurts",
    "performer_extracted": "Lizzo",
    "match_status": "multiple_exact_candidates",
    "distinct_spotify_ids": 9,
    "candidate_rows": 9,
    "distinct_lyric_sha256": 2,
    "distinct_audio_combinations": 6,
    "any_missing_or_blank_lyrics": false
  },
  {
    "source_row": 22669,
    "song_or_album": "Bad Guy",
    "performer_extracted": "Billie Eilish",
    "match_status": "multiple_exact_candidates",
    "distinct_spotify_ids": 8,
    "candidate_rows": 8,
    "distinct_lyric_sha256": 3,
    "distinct_audio_combinations": 3,
    "any_missing_or_blank_lyrics": false
  }
]
```

### Unmatched examples

```json
[
  {
    "source_row": 14566,
    "song_or_album": "The Rising",
    "performer_extracted": "Bruce Springsteen",
    "match_status": "no_exact_candidate",
    "distinct_spotify_ids": 0,
    "candidate_rows": 0,
    "distinct_lyric_sha256": 0,
    "distinct_audio_combinations": 0,
    "any_missing_or_blank_lyrics": false
  },
  {
    "source_row": 15097,
    "song_or_album": "Lose Yourself",
    "performer_extracted": "Eminem",
    "match_status": "no_exact_candidate",
    "distinct_spotify_ids": 0,
    "candidate_rows": 0,
    "distinct_lyric_sha256": 0,
    "distinct_audio_combinations": 0,
    "any_missing_or_blank_lyrics": false
  },
  {
    "source_row": 15638,
    "song_or_album": "Daughters",
    "performer_extracted": "John Mayer",
    "match_status": "no_exact_candidate",
    "distinct_spotify_ids": 0,
    "candidate_rows": 0,
    "distinct_lyric_sha256": 0,
    "distinct_audio_combinations": 0,
    "any_missing_or_blank_lyrics": false
  },
  {
    "source_row": 16179,
    "song_or_album": "Devils & Dust",
    "performer_extracted": "Bruce Springsteen",
    "match_status": "no_exact_candidate",
    "distinct_spotify_ids": 0,
    "candidate_rows": 0,
    "distinct_lyric_sha256": 0,
    "distinct_audio_combinations": 0,
    "any_missing_or_blank_lyrics": false
  },
  {
    "source_row": 17268,
    "song_or_album": "Umbrella",
    "performer_extracted": "Rihanna Featuring Jay-Z",
    "match_status": "no_exact_candidate",
    "distinct_spotify_ids": 0,
    "candidate_rows": 0,
    "distinct_lyric_sha256": 0,
    "distinct_audio_combinations": 0,
    "any_missing_or_blank_lyrics": false
  }
]
```

## Billboard–Grammy

```json
{
  "candidate_pairs": 125,
  "distinct_billboard_songs": 125,
  "distinct_grammy_records": 125,
  "year_gap_distribution": [
    {
      "year_gap": 0,
      "candidate_pairs": 91
    },
    {
      "year_gap": 1,
      "candidate_pairs": 34
    }
  ],
  "inside_provisional_range": 125,
  "outside_provisional_range": 0,
  "billboard_songs_with_multiple_grammy_records": 0,
  "grammy_records_with_multiple_billboard_songs": 0,
  "ambiguous_pair_count": 0,
  "many_to_many_pair_count": 0,
  "ambiguous_examples": []
}
```

## Methodological warnings

- Exact-match coverage is not final match coverage. Unmatched does not mean the song is absent from Spotify.
- Artist formatting, collaborations, featured artists and version labels can prevent exact matches. Existing normalization rules were not changed; blank/null keys never match.
- Several Spotify IDs may represent releases, remasters, albums or duplicates of the same recording. All candidate rows are retained, even when lyrics or audio agree. One exact ID is a candidate, not a verified recording match.
- Match rates may differ between successful and less-successful songs, creating selection bias in the final analytical sample. Top 10 and Grammy winner variables are used only for coverage diagnostics; no outcome variable may be used to choose among candidates.
- Distinct ID counts determine status, not joined row counts. Conflicting records sharing an ID remain present and flagged. Spotify rows with missing/blank IDs cannot count as track candidates and are explicitly counted as excluded.
- Lyric hash counts exclude nulls; any missing hash is reported separately. Same known hash means identical hashed content, not verified song identity. Audio combinations compare all available original values, including text key/mode and null patterns, without tolerance or recoding.
- Billboard source_row is a new 1-based position in the unchanged source Parquet. It is not a raw weekly CSV row number. Sing and Sing! remain distinct source records even though their normalized keys collide.
- Billboard–Grammy candidates have no year restriction. Gaps -1 through +2 are only provisionally plausible; other pairs remain in the complete candidate table and are exported for review.
- No fuzzy matching, automatic candidate selection, record merging or final modelling dataset was created.

## Validation

```json
{
  "grammy_rows_preserved": 150,
  "grammy_original_values_unchanged": true,
  "all_source_records_classified": true,
  "distinct_id_counts_validated": true,
  "exact_keys_validated": true,
  "all_candidate_rows_retained": true,
  "parquet_roundtrips_passed": true,
  "sing_records_separate": true,
  "spotify_rows_excluded_missing_or_blank_id": 0,
  "available_audio_variables": [
    "danceability",
    "energy",
    "key",
    "loudness",
    "mode",
    "speechiness",
    "acousticness",
    "instrumentalness",
    "liveness",
    "valence",
    "tempo",
    "duration_ms"
  ],
  "fuzzy_matching_performed": false,
  "automatic_candidate_selection_performed": false,
  "protected_files_unchanged": true,
  "protected_file_count": 39
}
```

Every Billboard and Grammy source record has a match status in the JSON report. Candidate Parquet files contain every matching pair with source-prefixed columns, including both matching keys. Unmatched/ambiguous CSVs contain complete source metadata and counts; no full lyrics are included.

## New outputs

- `data/interim/grammy_soty_enriched_2000_2024.parquet`
- `data/interim/billboard_spotify_exact_candidates.parquet`
- `data/interim/grammy_spotify_exact_candidates.parquet`
- `data/interim/billboard_grammy_exact_candidates.parquet`
- `reports/billboard_spotify_unmatched.csv`
- `reports/billboard_spotify_ambiguous.csv`
- `reports/grammy_spotify_unmatched.csv`
- `reports/grammy_spotify_ambiguous.csv`
- `reports/billboard_grammy_year_gap_review.csv`
- `reports/exact_match_audit.md`
- `reports/exact_match_audit.json`

## Run

```powershell
uv run python -m unittest discover -s tests -v
uv run python src/03_exact_match_audit.py
uv run python -m unittest discover -s tests -v
```
