# Raw data profile

Read-only profiling for Do Lyrics Matter for Music Success?

## Method

- UTF-8 strict CSV parsing; inference uses the first 10,000 records. Billboard Weeks in Charts is explicitly read as String to preserve the '-' sentinel that failed integer parsing. No ignored errors or discarded malformed rows.
- Missing means a Polars null (including unquoted empty CSV fields). Blank means non-null text empty after whitespace stripping. Percentages use all rows unless labelled otherwise. Literal NA/null strings are not recoded.
- Duplicate count means excess rows beyond one per raw key. Null key combinations are included and reported separately; raw strings are unchanged. Exact rows compare parsed field values.
- Lyric word counts use whitespace-delimited non-empty tokens. Percentiles use linear interpolation on non-empty lyrics only. This is a profiling statistic, not a persisted feature dataset.
- Five examples use source order. All lyric values are omitted, and other text is capped at 200 characters.
- Audio numeric domains follow https://developer.spotify.com/documentation/web-api/reference/get-audio-features. Loudness -60 to 0 dB is a typical range, not a hard validity constraint. Tempo >=0 and positive integer duration are plausibility checks without upper bounds. Text key/mode values are reported, not converted or repaired.
- The intended future period is 2000–2024 and grain is unique song–artist. Raw profiling covers every record; only the requested Grammy period check is filtered.
- Streaming scans validate every column. Spotify full-row duplicates are skipped to avoid retaining long lyrics; exact ID and song–artist counts are computed. Exact key grouping and lyric quantiles still require memory proportional to keys and numeric lengths.

## File inventory

| Dataset | File | Bytes | Parse status | Raw unchanged |
|---|---|---:|---|---|
| Spotify | data/raw/songs_with_attributes_and_lyrics.csv | 1545144675 | passed | True |
| Billboard | data/raw/hot100.csv | 38358645 | passed | True |
| Grammy | data/raw/grammies_v4.csv | 4196575 | passed | True |

## Spotify

There are 955,320 unique non-null track IDs and 853,058 raw song–artist combinations. Median lyric length is 224.0 words; 3,441 non-empty lyrics have fewer than 20 words.

Rows: **955,320**. Columns: **17**. Exact duplicate excess rows: **None** (null = not computed).

### Columns and completeness

| Column | Effective type (see schema notes) | Missing | Missing % | Blank | Blank % |
|---|---|---:|---:|---:|---:|
| id | String | 0 | 0.0 | 0 | 0.0 |
| name | String | 0 | 0.0 | 9 | 0.0009420927019218691 |
| album_name | String | 0 | 0.0 | 569758 | 59.64053929573337 |
| artists | String | 0 | 0.0 | 0 | 0.0 |
| danceability | Float64 | 0 | 0.0 | n/a | n/a |
| energy | Float64 | 0 | 0.0 | n/a | n/a |
| key | String | 0 | 0.0 | 0 | 0.0 |
| loudness | Float64 | 0 | 0.0 | n/a | n/a |
| mode | String | 0 | 0.0 | 0 | 0.0 |
| speechiness | Float64 | 0 | 0.0 | n/a | n/a |
| acousticness | Float64 | 0 | 0.0 | n/a | n/a |
| instrumentalness | Float64 | 0 | 0.0 | n/a | n/a |
| liveness | Float64 | 0 | 0.0 | n/a | n/a |
| valence | Float64 | 0 | 0.0 | n/a | n/a |
| tempo | Float64 | 0 | 0.0 | n/a | n/a |
| duration_ms | Float64 | 0 | 0.0 | n/a | n/a |
| lyrics | String | 0 | 0.0 | 13 | 0.0013608005694427 |

### Dataset-specific checks

```json
{
  "track_ids": {
    "unique_combinations_including_null": 955320,
    "duplicate_excess_rows": 0,
    "duplicated_key_groups": 0,
    "rows_in_duplicate_groups": 0,
    "keys": [
      "id"
    ],
    "rows_with_any_null_key": 0,
    "unique_non_null_values": 955320
  },
  "raw_song_artist": {
    "unique_combinations_including_null": 853058,
    "duplicate_excess_rows": 102262,
    "duplicated_key_groups": 76921,
    "rows_in_duplicate_groups": 179183,
    "keys": [
      "name",
      "artists"
    ],
    "rows_with_any_null_key": 0
  },
  "lyric_words": {
    "non_empty_lyrics": 955307,
    "mean": 266.0473575510281,
    "median": 224.0,
    "p25": 152.0,
    "p75": 319.0,
    "min": 1,
    "max": 6129,
    "fewer_than_20": 3441,
    "fewer_than_20_pct_of_non_empty": 0.36019834461591926
  },
  "audio": {
    "danceability": {
      "missing_count": 0,
      "non_numeric_count": 0,
      "non_finite_count": 0,
      "observed_numeric_min": 0.0,
      "observed_numeric_max": 0.993,
      "outside_expected_range_count": 0,
      "expected_lower": 0,
      "expected_upper": 1,
      "rule": "inclusive interval",
      "range_is_typical_not_hard_bound": false
    },
    "energy": {
      "missing_count": 0,
      "non_numeric_count": 0,
      "non_finite_count": 0,
      "observed_numeric_min": 0.0,
      "observed_numeric_max": 1.0,
      "outside_expected_range_count": 0,
      "expected_lower": 0,
      "expected_upper": 1,
      "rule": "inclusive interval",
      "range_is_typical_not_hard_bound": false
    },
    "speechiness": {
      "missing_count": 0,
      "non_numeric_count": 0,
      "non_finite_count": 0,
      "observed_numeric_min": 0.0,
      "observed_numeric_max": 0.966,
      "outside_expected_range_count": 0,
      "expected_lower": 0,
      "expected_upper": 1,
      "rule": "inclusive interval",
      "range_is_typical_not_hard_bound": false
    },
    "acousticness": {
      "missing_count": 0,
      "non_numeric_count": 0,
      "non_finite_count": 0,
      "observed_numeric_min": 0.0,
      "observed_numeric_max": 0.996,
      "outside_expected_range_count": 0,
      "expected_lower": 0,
      "expected_upper": 1,
      "rule": "inclusive interval",
      "range_is_typical_not_hard_bound": false
    },
    "instrumentalness": {
      "missing_count": 0,
      "non_numeric_count": 0,
      "non_finite_count": 0,
      "observed_numeric_min": 0.0,
      "observed_numeric_max": 1.0,
      "outside_expected_range_count": 0,
      "expected_lower": 0,
      "expected_upper": 1,
      "rule": "inclusive interval",
      "range_is_typical_not_hard_bound": false
    },
    "liveness": {
      "missing_count": 0,
      "non_numeric_count": 0,
      "non_finite_count": 0,
      "observed_numeric_min": 0.0,
      "observed_numeric_max": 1.0,
      "outside_expected_range_count": 0,
      "expected_lower": 0,
      "expected_upper": 1,
      "rule": "inclusive interval",
      "range_is_typical_not_hard_bound": false
    },
    "valence": {
      "missing_count": 0,
      "non_numeric_count": 0,
      "non_finite_count": 0,
      "observed_numeric_min": 0.0,
      "observed_numeric_max": 1.0,
      "outside_expected_range_count": 0,
      "expected_lower": 0,
      "expected_upper": 1,
      "rule": "inclusive interval",
      "range_is_typical_not_hard_bound": false
    },
    "loudness": {
      "missing_count": 0,
      "non_numeric_count": 0,
      "non_finite_count": 0,
      "observed_numeric_min": -60.0,
      "observed_numeric_max": 4.882,
      "outside_expected_range_count": 443,
      "expected_lower": -60,
      "expected_upper": 0,
      "rule": "inclusive interval",
      "range_is_typical_not_hard_bound": true
    },
    "tempo": {
      "missing_count": 0,
      "non_numeric_count": 0,
      "non_finite_count": 0,
      "observed_numeric_min": 0.0,
      "observed_numeric_max": 246.13,
      "outside_expected_range_count": 0,
      "expected_lower": 0,
      "expected_upper": null,
      "rule": "inclusive interval",
      "range_is_typical_not_hard_bound": false
    },
    "key": {
      "missing_count": 0,
      "non_numeric_count": 60265,
      "non_finite_count": 0,
      "observed_numeric_min": 0.0,
      "observed_numeric_max": 11.0,
      "outside_expected_range_count": 0,
      "expected_lower": -1,
      "expected_upper": 11,
      "rule": "integer interval",
      "range_is_typical_not_hard_bound": false,
      "raw_value_counts": [
        {
          "key": "0",
          "len": 92882
        },
        {
          "key": "0.0",
          "len": 12497
        },
        {
          "key": "1",
          "len": 69353
        },
        {
          "key": "1.0",
          "len": 10577
        },
        {
          "key": "10",
          "len": 48499
        },
        {
          "key": "10.0",
          "len": 6824
        },
        {
          "key": "11",
          "len": 60750
        },
        {
          "key": "11.0",
          "len": 8786
        },
        {
          "key": "2",
          "len": 86809
        },
        {
          "key": "2.0",
          "len": 11172
        },
        {
          "key": "3",
          "len": 24176
        },
        {
          "key": "3.0",
          "len": 3588
        },
        {
          "key": "4",
          "len": 64616
        },
        {
          "key": "4.0",
          "len": 8476
        },
        {
          "key": "5",
          "len": 62753
        },
        {
          "key": "5.0",
          "len": 8758
        },
        {
          "key": "6",
          "len": 48938
        },
        {
          "key": "6.0",
          "len": 7410
        },
        {
          "key": "7",
          "len": 94773
        },
        {
          "key": "7.0",
          "len": 12324
        },
        {
          "key": "8",
          "len": 46947
        },
        {
          "key": "8.0",
          "len": 7108
        },
        {
          "key": "9",
          "len": 86169
        },
        {
          "key": "9.0",
          "len": 10870
        },
        {
          "key": "A",
          "len": 6131
        },
        {
          "key": "A#",
          "len": 3847
        },
        {
          "key": "B",
          "len": 5109
        },
        {
          "key": "C",
          "len": 7081
        },
        {
          "key": "C#",
          "len": 6001
        },
        {
          "key": "D",
          "len": 5930
        },
        {
          "key": "D#",
          "len": 1742
        },
        {
          "key": "E",
          "len": 4558
        },
        {
          "key": "F",
          "len": 4810
        },
        {
          "key": "F#",
          "len": 4116
        },
        {
          "key": "G",
          "len": 6909
        },
        {
          "key": "G#",
          "len": 4031
        }
      ]
    },
    "mode": {
      "missing_count": 0,
      "non_numeric_count": 60265,
      "non_finite_count": 0,
      "observed_numeric_min": 0.0,
      "observed_numeric_max": 1.0,
      "outside_expected_range_count": 0,
      "expected_lower": 0,
      "expected_upper": 1,
      "rule": "integer interval",
      "range_is_typical_not_hard_bound": false,
      "raw_value_counts": [
        {
          "mode": "0",
          "len": 263274
        },
        {
          "mode": "0.0",
          "len": 38679
        },
        {
          "mode": "1",
          "len": 523391
        },
        {
          "mode": "1.0",
          "len": 69711
        },
        {
          "mode": "Major",
          "len": 39509
        },
        {
          "mode": "Minor",
          "len": 20756
        }
      ]
    },
    "duration_ms": {
      "missing_count": 0,
      "non_numeric_count": 0,
      "non_finite_count": 0,
      "observed_numeric_min": 1586.0,
      "observed_numeric_max": 5764624.0,
      "outside_expected_range_count": 0,
      "expected_lower": 0,
      "expected_upper": null,
      "rule": "positive integer",
      "range_is_typical_not_hard_bound": false
    }
  }
}
```

### Five example records (lyrics omitted; text capped at 200 characters)

```json
[
  {
    "id": "0Prct5TDjAnEgIqbxcldY9",
    "name": "!",
    "album_name": "UNDEN!ABLE",
    "artists": "HELLYEAH",
    "danceability": 0.415,
    "energy": 0.605,
    "key": "7",
    "loudness": -11.157,
    "mode": "1",
    "speechiness": 0.0575,
    "acousticness": 0.00116,
    "instrumentalness": 0.838,
    "liveness": 0.471,
    "valence": 0.193,
    "tempo": 100.059,
    "duration_ms": 79500.0,
    "lyrics": "[lyrics omitted]"
  },
  {
    "id": "2ASl4wirkeYm3OWZxXKYuq",
    "name": "!!",
    "album_name": "",
    "artists": "Yxngxr1",
    "danceability": 0.788,
    "energy": 0.648,
    "key": "7",
    "loudness": -9.135,
    "mode": "0",
    "speechiness": 0.315,
    "acousticness": 0.9,
    "instrumentalness": 0.0,
    "liveness": 0.176,
    "valence": 0.287,
    "tempo": 79.998,
    "duration_ms": 114000.0,
    "lyrics": "[lyrics omitted]"
  },
  {
    "id": "69lcggVPmOr9cvPx9kLiiN",
    "name": "!!! - Interlude",
    "album_name": "Where I Belong EP",
    "artists": "Glowie",
    "danceability": 0.0,
    "energy": 0.0354,
    "key": "7",
    "loudness": -20.151,
    "mode": "0",
    "speechiness": 0.0,
    "acousticness": 0.908,
    "instrumentalness": 0.0,
    "liveness": 0.479,
    "valence": 0.0,
    "tempo": 0.0,
    "duration_ms": 11413.0,
    "lyrics": "[lyrics omitted]"
  },
  {
    "id": "4U7dlZjg1s9pjdppqZy0fm",
    "name": "!!De Repente!!",
    "album_name": "Un Palo Al Agua (20 Grandes Canciones)",
    "artists": "Rosendo",
    "danceability": 0.657,
    "energy": 0.882,
    "key": "5",
    "loudness": -6.34,
    "mode": "1",
    "speechiness": 0.0385,
    "acousticness": 0.0074,
    "instrumentalness": 1.27e-05,
    "liveness": 0.0474,
    "valence": 0.939,
    "tempo": 123.588,
    "duration_ms": 198173.0,
    "lyrics": "[lyrics omitted]"
  },
  {
    "id": "4v1IBp3Y3rpkWmWzIlkYju",
    "name": "!!De Repente!!",
    "album_name": "Fuera De Lugar",
    "artists": "Rosendo",
    "danceability": 0.659,
    "energy": 0.893,
    "key": "5",
    "loudness": -8.531,
    "mode": "1",
    "speechiness": 0.0411,
    "acousticness": 0.0922,
    "instrumentalness": 1.91e-05,
    "liveness": 0.0534,
    "valence": 0.951,
    "tempo": 123.6,
    "duration_ms": 199827.0,
    "lyrics": "[lyrics omitted]"
  }
]
```

### Schema notes

```json
{
  "inferred_schema": {
    "id": "String",
    "name": "String",
    "album_name": "String",
    "artists": "String",
    "danceability": "Float64",
    "energy": "Float64",
    "key": "String",
    "loudness": "Float64",
    "mode": "String",
    "speechiness": "Float64",
    "acousticness": "Float64",
    "instrumentalness": "Float64",
    "liveness": "Float64",
    "valence": "Float64",
    "tempo": "Float64",
    "duration_ms": "Float64",
    "lyrics": "String"
  },
  "schema_overrides": {}
}
```

## Billboard

Coverage runs from 1958-07-30 to 2026-09-23 across 3,557 chart weeks. There are 0 ranks outside 1–100 and 13 excess date–song–artist entries. Repeating a song across different chart weeks is expected at this raw grain.

Rows: **355,658**. Columns: **8**. Exact duplicate excess rows: **0** (null = not computed).

### Columns and completeness

| Column | Effective type (see schema notes) | Missing | Missing % | Blank | Blank % |
|---|---|---:|---:|---:|---:|
| Date | String | 0 | 0.0 | 0 | 0.0 |
| Song | String | 0 | 0.0 | 0 | 0.0 |
| Artist | String | 0 | 0.0 | 0 | 0.0 |
| Rank | Int64 | 0 | 0.0 | n/a | n/a |
| Last Week | String | 0 | 0.0 | 0 | 0.0 |
| Peak Position | Int64 | 0 | 0.0 | n/a | n/a |
| Weeks in Charts | String | 0 | 0.0 | 0 | 0.0 |
| Image URL | String | 124215 | 34.92540586743444 | 0 | 0.0 |

### Dataset-specific checks

```json
{
  "min_chart_date": "1958-07-30",
  "max_chart_date": "2026-09-23",
  "distinct_chart_weeks": 3557,
  "invalid_date_count": 0,
  "min_rank": 1,
  "max_rank": 100,
  "invalid_rank_count": 0,
  "raw_song_artist": {
    "unique_combinations_including_null": 32677,
    "duplicate_excess_rows": 322981,
    "duplicated_key_groups": 28924,
    "rows_in_duplicate_groups": 351905,
    "keys": [
      "Song",
      "Artist"
    ],
    "rows_with_any_null_key": 0
  },
  "date_song_artist": {
    "unique_combinations_including_null": 355645,
    "duplicate_excess_rows": 13,
    "duplicated_key_groups": 13,
    "rows_in_duplicate_groups": 26,
    "keys": [
      "Date",
      "Song",
      "Artist"
    ],
    "rows_with_any_null_key": 0
  },
  "weeks_in_charts_dtype": "String",
  "weeks_in_charts_values": [
    "-",
    "1",
    "10",
    "100",
    "101",
    "102",
    "103",
    "104",
    "105",
    "106",
    "107",
    "108",
    "109",
    "11",
    "110",
    "111",
    "112",
    "12",
    "13",
    "14",
    "15",
    "16",
    "17",
    "18",
    "19",
    "2",
    "20",
    "21",
    "22",
    "23",
    "24",
    "25",
    "26",
    "27",
    "28",
    "29",
    "3",
    "30",
    "31",
    "32",
    "33",
    "34",
    "35",
    "36",
    "37",
    "38",
    "39",
    "4",
    "40",
    "41",
    "42",
    "43",
    "44",
    "45",
    "46",
    "47",
    "48",
    "49",
    "5",
    "50",
    "51",
    "52",
    "53",
    "54",
    "55",
    "56",
    "57",
    "58",
    "59",
    "6",
    "60",
    "61",
    "62",
    "63",
    "64",
    "65",
    "66",
    "67",
    "68",
    "69",
    "7",
    "70",
    "71",
    "72",
    "73",
    "74",
    "75",
    "76",
    "77",
    "78",
    "79",
    "8",
    "80",
    "81",
    "82",
    "83",
    "84",
    "85",
    "86",
    "87",
    "88",
    "89",
    "9",
    "90",
    "91",
    "92",
    "93",
    "94",
    "95",
    "96",
    "97",
    "98",
    "99"
  ],
  "weeks_in_charts_value_counts": [
    {
      "Weeks in Charts": "-",
      "len": 200
    },
    {
      "Weeks in Charts": "1",
      "len": 32670
    },
    {
      "Weeks in Charts": "10",
      "len": 15715
    },
    {
      "Weeks in Charts": "100",
      "len": 1
    },
    {
      "Weeks in Charts": "101",
      "len": 1
    },
    {
      "Weeks in Charts": "102",
      "len": 1
    },
    {
      "Weeks in Charts": "103",
      "len": 1
    },
    {
      "Weeks in Charts": "104",
      "len": 1
    },
    {
      "Weeks in Charts": "105",
      "len": 1
    },
    {
      "Weeks in Charts": "106",
      "len": 1
    },
    {
      "Weeks in Charts": "107",
      "len": 1
    },
    {
      "Weeks in Charts": "108",
      "len": 1
    },
    {
      "Weeks in Charts": "109",
      "len": 1
    },
    {
      "Weeks in Charts": "11",
      "len": 14411
    },
    {
      "Weeks in Charts": "110",
      "len": 1
    },
    {
      "Weeks in Charts": "111",
      "len": 1
    },
    {
      "Weeks in Charts": "112",
      "len": 1
    },
    {
      "Weeks in Charts": "12",
      "len": 13107
    },
    {
      "Weeks in Charts": "13",
      "len": 11940
    },
    {
      "Weeks in Charts": "14",
      "len": 10818
    },
    {
      "Weeks in Charts": "15",
      "len": 9747
    },
    {
      "Weeks in Charts": "16",
      "len": 8781
    },
    {
      "Weeks in Charts": "17",
      "len": 7887
    },
    {
      "Weeks in Charts": "18",
      "len": 7148
    },
    {
      "Weeks in Charts": "19",
      "len": 6438
    },
    {
      "Weeks in Charts": "2",
      "len": 28923
    },
    {
      "Weeks in Charts": "20",
      "len": 5820
    },
    {
      "Weeks in Charts": "21",
      "len": 3288
    },
    {
      "Weeks in Charts": "22",
      "len": 2796
    },
    {
      "Weeks in Charts": "23",
      "len": 2399
    },
    {
      "Weeks in Charts": "24",
      "len": 2082
    },
    {
      "Weeks in Charts": "25",
      "len": 1839
    },
    {
      "Weeks in Charts": "26",
      "len": 1594
    },
    {
      "Weeks in Charts": "27",
      "len": 1392
    },
    {
      "Weeks in Charts": "28",
      "len": 1220
    },
    {
      "Weeks in Charts": "29",
      "len": 1086
    },
    {
      "Weeks in Charts": "3",
      "len": 26822
    },
    {
      "Weeks in Charts": "30",
      "len": 964
    },
    {
      "Weeks in Charts": "31",
      "len": 857
    },
    {
      "Weeks in Charts": "32",
      "len": 774
    },
    {
      "Weeks in Charts": "33",
      "len": 694
    },
    {
      "Weeks in Charts": "34",
      "len": 630
    },
    {
      "Weeks in Charts": "35",
      "len": 579
    },
    {
      "Weeks in Charts": "36",
      "len": 533
    },
    {
      "Weeks in Charts": "37",
      "len": 479
    },
    {
      "Weeks in Charts": "38",
      "len": 447
    },
    {
      "Weeks in Charts": "39",
      "len": 413
    },
    {
      "Weeks in Charts": "4",
      "len": 25196
    },
    {
      "Weeks in Charts": "40",
      "len": 364
    },
    {
      "Weeks in Charts": "41",
      "len": 334
    },
    {
      "Weeks in Charts": "42",
      "len": 304
    },
    {
      "Weeks in Charts": "43",
      "len": 267
    },
    {
      "Weeks in Charts": "44",
      "len": 244
    },
    {
      "Weeks in Charts": "45",
      "len": 228
    },
    {
      "Weeks in Charts": "46",
      "len": 208
    },
    {
      "Weeks in Charts": "47",
      "len": 192
    },
    {
      "Weeks in Charts": "48",
      "len": 179
    },
    {
      "Weeks in Charts": "49",
      "len": 161
    },
    {
      "Weeks in Charts": "5",
      "len": 23656
    },
    {
      "Weeks in Charts": "50",
      "len": 148
    },
    {
      "Weeks in Charts": "51",
      "len": 141
    },
    {
      "Weeks in Charts": "52",
      "len": 132
    },
    {
      "Weeks in Charts": "53",
      "len": 87
    },
    {
      "Weeks in Charts": "54",
      "len": 75
    },
    {
      "Weeks in Charts": "55",
      "len": 65
    },
    {
      "Weeks in Charts": "56",
      "len": 60
    },
    {
      "Weeks in Charts": "57",
      "len": 52
    },
    {
      "Weeks in Charts": "58",
      "len": 45
    },
    {
      "Weeks in Charts": "59",
      "len": 42
    },
    {
      "Weeks in Charts": "6",
      "len": 22103
    },
    {
      "Weeks in Charts": "60",
      "len": 39
    },
    {
      "Weeks in Charts": "61",
      "len": 35
    },
    {
      "Weeks in Charts": "62",
      "len": 32
    },
    {
      "Weeks in Charts": "63",
      "len": 28
    },
    {
      "Weeks in Charts": "64",
      "len": 27
    },
    {
      "Weeks in Charts": "65",
      "len": 26
    },
    {
      "Weeks in Charts": "66",
      "len": 22
    },
    {
      "Weeks in Charts": "67",
      "len": 21
    },
    {
      "Weeks in Charts": "68",
      "len": 19
    },
    {
      "Weeks in Charts": "69",
      "len": 15
    },
    {
      "Weeks in Charts": "7",
      "len": 20459
    },
    {
      "Weeks in Charts": "70",
      "len": 13
    },
    {
      "Weeks in Charts": "71",
      "len": 12
    },
    {
      "Weeks in Charts": "72",
      "len": 11
    },
    {
      "Weeks in Charts": "73",
      "len": 10
    },
    {
      "Weeks in Charts": "74",
      "len": 10
    },
    {
      "Weeks in Charts": "75",
      "len": 10
    },
    {
      "Weeks in Charts": "76",
      "len": 10
    },
    {
      "Weeks in Charts": "77",
      "len": 9
    },
    {
      "Weeks in Charts": "78",
      "len": 7
    },
    {
      "Weeks in Charts": "79",
      "len": 7
    },
    {
      "Weeks in Charts": "8",
      "len": 18817
    },
    {
      "Weeks in Charts": "80",
      "len": 5
    },
    {
      "Weeks in Charts": "81",
      "len": 5
    },
    {
      "Weeks in Charts": "82",
      "len": 5
    },
    {
      "Weeks in Charts": "83",
      "len": 5
    },
    {
      "Weeks in Charts": "84",
      "len": 5
    },
    {
      "Weeks in Charts": "85",
      "len": 5
    },
    {
      "Weeks in Charts": "86",
      "len": 5
    },
    {
      "Weeks in Charts": "87",
      "len": 5
    },
    {
      "Weeks in Charts": "88",
      "len": 4
    },
    {
      "Weeks in Charts": "89",
      "len": 4
    },
    {
      "Weeks in Charts": "9",
      "len": 17169
    },
    {
      "Weeks in Charts": "90",
      "len": 3
    },
    {
      "Weeks in Charts": "91",
      "len": 2
    },
    {
      "Weeks in Charts": "92",
      "len": 1
    },
    {
      "Weeks in Charts": "93",
      "len": 1
    },
    {
      "Weeks in Charts": "94",
      "len": 1
    },
    {
      "Weeks in Charts": "95",
      "len": 1
    },
    {
      "Weeks in Charts": "96",
      "len": 1
    },
    {
      "Weeks in Charts": "97",
      "len": 1
    },
    {
      "Weeks in Charts": "98",
      "len": 1
    },
    {
      "Weeks in Charts": "99",
      "len": 1
    }
  ]
}
```

### Five example records (lyrics omitted; text capped at 200 characters)

```json
[
  {
    "Date": "1958-07-30",
    "Song": "Poor Little Fool",
    "Artist": "Ricky Nelson",
    "Rank": 1,
    "Last Week": "-",
    "Peak Position": 1,
    "Weeks in Charts": "1",
    "Image URL": null
  },
  {
    "Date": "1958-07-30",
    "Song": "Patricia",
    "Artist": "Perez Prado And His Orchestra",
    "Rank": 2,
    "Last Week": "-",
    "Peak Position": 2,
    "Weeks in Charts": "1",
    "Image URL": null
  },
  {
    "Date": "1958-07-30",
    "Song": "Splish Splash",
    "Artist": "Bobby Darin",
    "Rank": 3,
    "Last Week": "-",
    "Peak Position": 3,
    "Weeks in Charts": "1",
    "Image URL": null
  },
  {
    "Date": "1958-07-30",
    "Song": "Hard Headed Woman",
    "Artist": "Elvis Presley With The Jordanaires",
    "Rank": 4,
    "Last Week": "-",
    "Peak Position": 4,
    "Weeks in Charts": "1",
    "Image URL": "https://charts-static.billboard.com/img/1958/08/elvis-presley-7uo-180x180.jpg"
  },
  {
    "Date": "1958-07-30",
    "Song": "When",
    "Artist": "Kalin Twins",
    "Rank": 5,
    "Last Week": "-",
    "Peak Position": 5,
    "Weeks in Charts": "1",
    "Image URL": null
  }
]
```

### Schema notes

```json
{
  "inferred_schema": {
    "Date": "String",
    "Song": "String",
    "Artist": "String",
    "Rank": "Int64",
    "Last Week": "String",
    "Peak Position": "Int64",
    "Weeks in Charts": "Int64",
    "Image URL": "String"
  },
  "schema_overrides": {
    "Weeks in Charts": "String"
  }
}
```

## Grammy

Award years span 1958–2026. There are 4,914 winners (19.24% of nomination records). Song of the Year has 150 nomination records including 25 winners during 2000–2024. Nominee counts are records, not unique people.

Rows: **25,535**. Columns: **9**. Exact duplicate excess rows: **14** (null = not computed).

### Columns and completeness

| Column | Effective type (see schema notes) | Missing | Missing % | Blank | Blank % |
|---|---|---:|---:|---:|---:|
| annual_edition | Int64 | 0 | 0.0 | n/a | n/a |
| year | Int64 | 0 | 0.0 | n/a | n/a |
| award | String | 0 | 0.0 | 0 | 0.0 |
| artist | String | 11713 | 45.87037399647543 | 0 | 0.0 |
| artist_link | String | 11712 | 45.86645780301547 | 0 | 0.0 |
| producers | String | 14196 | 55.594282357548465 | 0 | 0.0 |
| song_or_album | String | 22 | 0.08615625611905228 | 0 | 0.0 |
| url | String | 0 | 0.0 | 0 | 0.0 |
| winner | Boolean | 0 | 0.0 | n/a | n/a |

### Dataset-specific checks

```json
{
  "min_award_year": 1958,
  "max_award_year": 2026,
  "distinct_award_categories": 766,
  "nomination_records": 25535,
  "winners": 4914,
  "winners_pct_of_all_records": 19.244174662228314,
  "song_of_the_year_records": 372,
  "song_of_the_year_2000_2024": {
    "nominee_records_including_winners": 150,
    "winner_records": 25,
    "non_winning_nominee_records": 125
  },
  "song_of_the_year_examples": [
    {
      "annual_edition": 1,
      "year": 1958,
      "award": "Song Of The Year",
      "artist": null,
      "artist_link": null,
      "producers": "Cy Coleman & Carolyn Leigh > songwriters (Frank Sinatra)",
      "song_or_album": "Witchcraft (Single)",
      "url": "/awards/1st-annual-grammy-awards",
      "winner": false
    },
    {
      "annual_edition": 1,
      "year": 1958,
      "award": "Song Of The Year",
      "artist": null,
      "artist_link": null,
      "producers": "Alan J. Lerner & Frederick Loewe > songwriters (Vic Damone)",
      "song_or_album": "Gigi (Single)",
      "url": "/awards/1st-annual-grammy-awards",
      "winner": false
    },
    {
      "annual_edition": 1,
      "year": 1958,
      "award": "Song Of The Year",
      "artist": null,
      "artist_link": null,
      "producers": "Eddie Cooley & Johnny Davenport > songwriters (Peggy Lee)",
      "song_or_album": "Fever",
      "url": "/awards/1st-annual-grammy-awards",
      "winner": false
    },
    {
      "annual_edition": 1,
      "year": 1958,
      "award": "Song Of The Year",
      "artist": null,
      "artist_link": null,
      "producers": "Lee Pockriss & Paul Vance > songwriters (Perry Como)",
      "song_or_album": "Catch A Falling Star",
      "url": "/awards/1st-annual-grammy-awards",
      "winner": false
    },
    {
      "annual_edition": 1,
      "year": 1958,
      "award": "Song Of The Year",
      "artist": null,
      "artist_link": null,
      "producers": "Domenico Modugno > songwriter (Domenico Modugno)",
      "song_or_album": "Nel Blu Dipinto Di Blu (Volare)",
      "url": "/awards/1st-annual-grammy-awards",
      "winner": true
    }
  ],
  "year_artist_title_award": {
    "unique_combinations_including_null": 25512,
    "duplicate_excess_rows": 23,
    "duplicated_key_groups": 10,
    "rows_in_duplicate_groups": 33,
    "keys": [
      "year",
      "artist",
      "song_or_album",
      "award"
    ],
    "rows_with_any_null_key": 11713
  }
}
```

### Five example records (lyrics omitted; text capped at 200 characters)

```json
[
  {
    "annual_edition": 1,
    "year": 1958,
    "award": "Album Of The Year",
    "artist": "Van Cliburn",
    "artist_link": "/artists/van-cliburn/16525",
    "producers": null,
    "song_or_album": "Tchaikovsky: Concerto No. 1, In B-Flat Minor, Op.23 (Album)",
    "url": "/awards/1st-annual-grammy-awards",
    "winner": false
  },
  {
    "annual_edition": 1,
    "year": 1958,
    "award": "Album Of The Year",
    "artist": "Frank Sinatra",
    "artist_link": "/artists/frank-sinatra/6581",
    "producers": null,
    "song_or_album": "Only The Lonely (Album)",
    "url": "/awards/1st-annual-grammy-awards",
    "winner": false
  },
  {
    "annual_edition": 1,
    "year": 1958,
    "award": "Album Of The Year",
    "artist": "Ella Fitzgerald",
    "artist_link": "/artists/ella-fitzgerald/16685",
    "producers": null,
    "song_or_album": "Ella Fitzgerald Sings The Irving Berlin Song Book (Album)",
    "url": "/awards/1st-annual-grammy-awards",
    "winner": false
  },
  {
    "annual_edition": 1,
    "year": 1958,
    "award": "Album Of The Year",
    "artist": "Frank Sinatra",
    "artist_link": "/artists/frank-sinatra/6581",
    "producers": null,
    "song_or_album": "Come Fly With Me (Album)",
    "url": "/awards/1st-annual-grammy-awards",
    "winner": false
  },
  {
    "annual_edition": 1,
    "year": 1958,
    "award": "Album Of The Year",
    "artist": "Henry Mancini",
    "artist_link": "/artists/henry-mancini/11935",
    "producers": null,
    "song_or_album": "The Music From Peter Gunn",
    "url": "/awards/1st-annual-grammy-awards",
    "winner": true
  }
]
```

### Schema notes

```json
{
  "inferred_schema": {
    "annual_edition": "Int64",
    "year": "Int64",
    "award": "String",
    "artist": "String",
    "artist_link": "String",
    "producers": "String",
    "song_or_album": "String",
    "url": "String",
    "winner": "Boolean"
  },
  "schema_overrides": {}
}
```

## Errors and warnings

- Spotify exact full-row duplicates not computed (1.5 GB source with long lyrics).
- Billboard Weeks in Charts requires a lossless String override; '-' is retained, not recoded as missing.
- Spotify loudness: 0 non-numeric, 0 non-finite, 443 outside numeric expectations; inspect raw coding before use.
- Spotify key: 60265 non-numeric, 0 non-finite, 0 outside numeric expectations; inspect raw coding before use.
- Spotify mode: 60265 non-numeric, 0 non-finite, 0 outside numeric expectations; inspect raw coding before use.

## Initial data-quality risks

- High: Spotify has no release-date column, so its 2000–2024 eligibility cannot be established from this file alone.
- High: Grammy title fields cover songs and albums, while artist and contributor fields have different roles; direct title–artist joins could misidentify works.
- Medium: Spotify key/mode mix numeric codes and named musical categories. Non-numeric counts describe coding differences, not automatically invalid music values.
- Medium: Empty or very short lyrics may be unusable for NLP; no language, content validity or placeholder classification has been performed.
- Spotify.name: 0 missing (0.00%), 9 blank; assess suitability before downstream use.
- Spotify.album_name: 0 missing (0.00%), 569758 blank; assess suitability before downstream use.
- Spotify.lyrics: 0 missing (0.00%), 13 blank; assess suitability before downstream use.
- Spotify raw_song_artist: 102262 excess raw-key rows; repeated source grain must be understood before matching.
- Billboard.Image URL: 124215 missing (34.93%), 0 blank; assess suitability before downstream use.
- Billboard raw_song_artist: 322981 excess raw-key rows; repeated source grain must be understood before matching.
- Billboard date_song_artist: 13 excess raw-key rows; repeated source grain must be understood before matching.
- Grammy.artist: 11713 missing (45.87%), 0 blank; assess suitability before downstream use.
- Grammy.artist_link: 11712 missing (45.87%), 0 blank; assess suitability before downstream use.
- Grammy.producers: 14196 missing (55.59%), 0 blank; assess suitability before downstream use.
- Grammy.song_or_album: 22 missing (0.09%), 0 blank; assess suitability before downstream use.
- Grammy year_artist_title_award: 23 excess raw-key rows; repeated source grain must be understood before matching.

## Recommended next preparation steps

- Agree on song–artist identity rules and the 2000–2024 eligibility date for each source before preparing data.
- Review missing titles, artists, lyrics, short lyrics, and audio coding against the source documentation before choosing handling rules.
- Plan how chart-week records and award nomination records will map to the future song–artist grain; no such aggregation or matching has been performed.

### Errors

```json
[]
```

### Resolved initial parsing failure

```json
[
  {
    "dataset": "Billboard",
    "type": "ComputeError",
    "exact_original_message": "could not parse `-` as dtype `i64` at column 'Weeks in Charts' (column number 7)\n\nThe current offset in the file is 516466 bytes.\n\nYou might want to try:\n- increasing `infer_schema_length` (e.g. `infer_schema_length=10000`),\n- increasing `infer_schema_files` (e.g. `infer_schema_files=50`),\n- specifying correct dtype with the `schema_overrides` argument\n- setting `ignore_errors` to `True`,\n- adding `-` to the `null_values` list.\n\nOriginal error: ```invalid primitive value found during CSV parsing```",
    "resolution": "Explicit Weeks in Charts String override preserves all values, including '-'. The failed scan was stopped; the corrected scan is a separate run."
  }
]
```

### Reproducibility and source integrity

```json
{
  "runtime": {
    "python": "3.12.14",
    "polars": "2.0.0"
  },
  "files": {
    "Spotify": {
      "before": {
        "size_bytes": 1545144675,
        "sha256": "698efaddfa802e1ba60010eaabcbb138bc017291f34bebaddb22f33ff490bd63"
      },
      "after": {
        "size_bytes": 1545144675,
        "sha256": "698efaddfa802e1ba60010eaabcbb138bc017291f34bebaddb22f33ff490bd63"
      },
      "raw_unchanged": true
    },
    "Billboard": {
      "before": {
        "size_bytes": 38358645,
        "sha256": "d34b5b480cad9836e8d74e7dcc6408c814387c378d4e5ffa5ded4406700190c4"
      },
      "after": {
        "size_bytes": 38358645,
        "sha256": "d34b5b480cad9836e8d74e7dcc6408c814387c378d4e5ffa5ded4406700190c4"
      },
      "raw_unchanged": true
    },
    "Grammy": {
      "before": {
        "size_bytes": 4196575,
        "sha256": "6211e1a9292eaabc454b77e83e8ad2d016df311f2a21ccc00c051d7885c2e803"
      },
      "after": {
        "size_bytes": 4196575,
        "sha256": "6211e1a9292eaabc454b77e83e8ad2d016df311f2a21ccc00c051d7885c2e803"
      },
      "raw_unchanged": true
    }
  }
}
```
