# Grammy–Billboard manual review guide

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

## Reviewer workflow

Inspect the raw titles, performer names, dates, all similarity components and prior-variant provenance. Check version qualifiers and collaborator differences explicitly. A first-chart year is not a release year, and the available Billboard table is restricted to its existing 2000–2024 cohort. Missing candidates do not prove a song never charted. The stored Grammy year is used as supplied.

Leave manual_decision and reviewer_note blank until a human reviews the evidence. Suggested human entries are accept, reject, or uncertain; record reasoning and supporting sources in reviewer_note. Neither this script nor these columns apply a decision to any relationship table. Save a reviewed copy separately before rerunning this generator, which recreates blank review columns.
