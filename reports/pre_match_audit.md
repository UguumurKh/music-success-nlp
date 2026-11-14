# Pre-matching audit

Read-only audit; no records merged and no dataset matching performed.

## Billboard: Glee Cast collision

| Song | Artist | First date | Last date | Weeks | Peak | Top 10 | No. 1 | Raw records | After dedup |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| Sing! | Glee Cast | 2010-10-27 | 2010-10-27 | 1 | 87 | 0 | 0 | 1 | 1 |
| Sing | Glee Cast | 2011-03-02 | 2011-03-02 | 1 | 49 | 0 | 0 | 1 | 1 |

Sing! → Sing: **gap**, 126 days between the earlier last date and later first date. These appear to be distinct chart histories; title similarity alone does not establish the same recording. No merge is recommended from this audit alone.

## Grammy performer parsing

Audited 150 records: **150 successful**, **0 failed**, **0 blank** extracted performers. Success verifies the pattern only, not performer identity.

Raw year–title–performer duplicate groups: 0. Normalized duplicate groups before title-label removal: 0; after: 0. New duplicate groups introduced: 0.

## Candidate title variant

**4 titles changed** by removing the exact trailing `(Single)` label. Original titles and title_norm remain intact; meaningful parentheses and version words are preserved. The CSV contains every original title, title_match_norm and title_match_changed.

### Solo-style performers

```json
[
  {
    "source_row": 13531,
    "year": 2000,
    "song_or_album": "Say My Name (Single)",
    "performer_extracted": "Destiny's Child",
    "performer_norm": "destiny s child"
  },
  {
    "source_row": 13532,
    "year": 2000,
    "song_or_album": "I Try (Single)",
    "performer_extracted": "Macy Gray",
    "performer_norm": "macy gray"
  },
  {
    "source_row": 13533,
    "year": 2000,
    "song_or_album": "I Hope You Dance (Single)",
    "performer_extracted": "Lee Ann Womack",
    "performer_norm": "lee ann womack"
  },
  {
    "source_row": 13534,
    "year": 2000,
    "song_or_album": "Breathe (Single)",
    "performer_extracted": "Faith Hill",
    "performer_norm": "faith hill"
  },
  {
    "source_row": 13535,
    "year": 2000,
    "song_or_album": "Beautiful Day",
    "performer_extracted": "U2",
    "performer_norm": "u2"
  }
]
```

### Featuring

```json
[
  {
    "source_row": 17268,
    "year": 2007,
    "song_or_album": "Umbrella",
    "performer_extracted": "Rihanna Featuring Jay-Z",
    "performer_norm": "rihanna featuring jay z"
  },
  {
    "source_row": 17824,
    "year": 2008,
    "song_or_album": "American Boy",
    "performer_extracted": "Estelle Featuring Kanye West",
    "performer_norm": "estelle featuring kanye west"
  },
  {
    "source_row": 18838,
    "year": 2010,
    "song_or_album": "Love The Way You Lie",
    "performer_extracted": "Eminem Featuring Rihanna",
    "performer_norm": "eminem featuring rihanna"
  },
  {
    "source_row": 19711,
    "year": 2012,
    "song_or_album": "We Are Young",
    "performer_extracted": "Fun. Featuring Janelle Monáe",
    "performer_norm": "fun featuring janelle monae"
  },
  {
    "source_row": 20117,
    "year": 2013,
    "song_or_album": "Same Love",
    "performer_extracted": "Macklemore & Ryan Lewis Featuring Mary Lambert",
    "performer_norm": "macklemore ryan lewis featuring mary lambert"
  }
]
```

### Ampersand collaborators

```json
[
  {
    "source_row": 19272,
    "year": 2011,
    "song_or_album": "The Cave",
    "performer_extracted": "Mumford & Sons",
    "performer_norm": "mumford sons"
  },
  {
    "source_row": 19273,
    "year": 2011,
    "song_or_album": "All Of The Lights",
    "performer_extracted": "Kanye West; Rihanna; Kid Cudi & Fergie",
    "performer_norm": "kanye west rihanna kid cudi fergie"
  },
  {
    "source_row": 20117,
    "year": 2013,
    "song_or_album": "Same Love",
    "performer_extracted": "Macklemore & Ryan Lewis Featuring Mary Lambert",
    "performer_norm": "macklemore ryan lewis featuring mary lambert"
  },
  {
    "source_row": 21796,
    "year": 2017,
    "song_or_album": "1-800-273-8255",
    "performer_extracted": "Logic Featuring Alessia Cara & Khalid",
    "performer_norm": "logic featuring alessia cara khalid"
  },
  {
    "source_row": 21799,
    "year": 2017,
    "song_or_album": "Despacito",
    "performer_extracted": "Luis Fonsi & Daddy Yankee Featuring Justin Bieber",
    "performer_norm": "luis fonsi daddy yankee featuring justin bieber"
  }
]
```

### And collaborators

```json
[
  {
    "source_row": 18841,
    "year": 2010,
    "song_or_album": "Beg Steal Or Borrow",
    "performer_extracted": "Ray LaMontagne And The Pariah Dogs",
    "performer_norm": "ray lamontagne and the pariah dogs"
  }
]
```

### Semicolon collaborators

```json
[
  {
    "source_row": 19273,
    "year": 2011,
    "song_or_album": "All Of The Lights",
    "performer_extracted": "Kanye West; Rihanna; Kid Cudi & Fergie",
    "performer_norm": "kanye west rihanna kid cudi fergie"
  },
  {
    "source_row": 22231,
    "year": 2018,
    "song_or_album": "The Middle",
    "performer_extracted": "Zedd; Maren Morris & Grey",
    "performer_norm": "zedd maren morris grey"
  },
  {
    "source_row": 24043,
    "year": 2022,
    "song_or_album": "GOD DID",
    "performer_extracted": "DJ Khaled Featuring Rick Ross; Lil Wayne; Jay-Z; John Legend & Fridayy",
    "performer_norm": "dj khaled featuring rick ross lil wayne jay z john legend fridayy"
  }
]
```

## Unresolved records and limits

- Glee Cast collision remains unresolved as musical identity; the two raw title histories must remain separate.
- 0 extracted performers contain an existing Unicode replacement character (U+FFFD). Extraction succeeds structurally, but damaged names and their normalized keys need review; no encoding repair was attempted.
- Parser failures and empty normalized performers, if any, are listed below. Collaborator order and Featuring labels remain unchanged.
- title_match_norm is for future candidate generation only. No dataset matching or automatic record merging was performed.

```json
[]
```

Solo examples are heuristic: no Featuring, ampersand, word And or semicolon. A band name may appear in this group. Collaborator strings are preserved, not split or matched.

## Integrity

SHA-256 verified 37 existing files before and after: unchanged = True. JSON contains per-file hashes. Raw CSVs, existing Parquet tables, prior reports, existing scripts/tests and README were not modified.

## Rerun

```powershell
uv run python -m unittest discover -s tests -v
uv run python src/02b_pre_match_audit.py
```
