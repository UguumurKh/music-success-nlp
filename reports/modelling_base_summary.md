# Modelling base summary

Output: `data/processed/billboard_model_base.parquet`

| Measure | Count |
|---|---:|
| Rows | 6,639 |
| Top-10 songs | 1,000 |
| Grammy-eligible songs (2000-2023) | 6,627 |
| Grammy SOTY nominees | 106 |
| Grammy SOTY winners | 19 |
| Strict-consistency songs | 3,981 |

Combined the 125 existing accepted relationships with nine manually verified pairs in memory. 4 manual mappings are represented in the consolidated sample; 5 are outside it.
Mappings outside the sample (Grammy ID, Billboard ID): (14043, 2671), (18840, 2915), (23570, 5406), (24537, 2194), (24541, 10377).

One row per Billboard song. Original consolidated fields, raw lyrics and audio are retained; `source_row` is renamed `billboard_source_row`. `peak_rank` is peak position. `grammy_source_rows` retains matching nomination IDs. Multiple nominations collapse using any nomination/winner and any version-ambiguity flag.

Eligible unmatched songs have false Grammy outcomes; 2024 nomination and winner outcomes are null. Version ambiguity records the supplied mapping flag and defaults to false where no pair exists.

All six requested checks passed. Existing input files and accepted relationships were not modified. No NLP features, train/test splits or models were created.
