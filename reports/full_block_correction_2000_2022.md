# Stage 11: evidence-gated full-block correction

Source: `data/processed/billboard_lyrics_preprocessed_2000_2022.parquet`. SHA-256: `809a0873f54795ffe3461599de0d374a46c2ab1ccf87ceb9b0b6ce622d408f88`.
Output: `data/processed/billboard_lyrics_corrected_2000_2022.parquet` (local, Git-ignored).

All 6,546 song–artist records retained. 955 Stage 10 full-block flags verified by recomputation. 6,545 texts untouched (suspected + uncertain + not_applicable).

| Status | Songs |
| --- | --- |
| corrected | 1 |
| suspected | 948 |
| uncertain | 6 |
| not_applicable | 5591 |

## Rule and limits

Stage 10 removes blank lines for detection, casefolds each remaining line, collapses whitespace within lines, and finds the smallest period that tiles the entire nonblank line sequence. Its flag counts copies of that period; it does not establish that the period is one complete musical performance. Refrain-only songs, short vocal fragments, intentional full-song repeats, case differences and stanza-layout differences are false-positive risks.

Automatic correction requires an explicit saved “Extraction duplication” classification, nonempty notes, no conflicting review, and workbook lyrics_clean identical to the current source. “Likely source duplication” is not treated as confirmed. Pasted Genius comparisons alone never authorize correction.

Additionally, every original-case block must match exactly, including internal whitespace and blank-line layout (newline separators at block boundaries are ignored). The retained base must have ≥12 nonblank lines, ≥100 whitespace tokens and ≥6 distinct lines. These are conservative ambiguity guards, not validated duplication classifiers. Only the verbatim first block is retained; its internal choruses, punctuation and languages remain untouched. Partial repeats are never removed. Without explicit confirmation, even strong structural repetition remains unchanged.

Suspected = flagged without a completed classification, or explicitly likely duplication. Uncertain = an unsure, unclassified-with-reference, conflicting or other reviewed case, or a confirmed case failing the structural/staleness gate. Not applicable = no whole-block flag. These statuses concern this correction only, not general text quality.

## Local manual evidence

The 11 repetition-review cases comprise one targeted example and ten fixed-seed sampled flagged records; they are not proof about all 955 flags. Saved notes include listening claims for 369, 9037, 5512 and 8670; 7563 and 9642 assert a retained portion without explicitly documenting listening. Five other cases paste Genius references, including two “unsure” and three blank classifications. These are reviewer-supplied reference evidence, not independently verified ground truth. An additional flagged record, 676, was reviewed for note-marker cleaning, not duplication: its “Correct cleaning” verdict does not authorize shortening its short repeated vocal text. It therefore adds a sixth uncertain case. No reference lyrics or full notes are reproduced here.

| ID | Workbook | Saved classification | Evidence type | Stage 11 status |
| --- | --- | --- | --- | --- |
| 369 | manual_lyric_review.xlsx | extraction duplication | reviewer notes | corrected |
| 676 | manual_lyric_review.xlsx | correct cleaning | reviewer notes | uncertain |
| 910 | full_block_repetition_review.xlsx | unclassified | Genius reference in notes | uncertain |
| 2689 | full_block_repetition_review.xlsx | unclassified | Genius reference in notes | uncertain |
| 3823 | full_block_repetition_review.xlsx | unsure | Genius reference in notes | uncertain |
| 5512 | full_block_repetition_review.xlsx | likely source duplication | reviewer notes | suspected |
| 5723 | full_block_repetition_review.xlsx | unsure | Genius reference in notes | uncertain |
| 7561 | full_block_repetition_review.xlsx | unclassified | Genius reference in notes | uncertain |
| 7563 | full_block_repetition_review.xlsx | likely source duplication | reviewer notes | suspected |
| 8670 | full_block_repetition_review.xlsx | likely source duplication | reviewer notes | suspected |
| 9037 | full_block_repetition_review.xlsx | likely source duplication | reviewer notes | suspected |
| 9642 | full_block_repetition_review.xlsx | likely source duplication | reviewer notes | suspected |

- `manual_lyric_review.xlsx` SHA-256: `f44aaad81456ff38587a97f1a459fd0bb5594216e907c18776beabd5062a21db`.
- `full_block_repetition_review.xlsx` SHA-256: `3e6a8f97dc534b55c41b6482acbbdc92443e9b1fa058e9ebf53c81c2c7923155`.

Other saved reviews: 1498 is uncertain about chorus coverage, 676 and 2160 report correct cleaning, and 1919 reports an encoding problem. These concern Stage 10 or source quality and do not authorize repetition correction; no upstream repairs were made.

## Repetition counts and length impact

| Original whole-block count | Songs |
| --- | --- |
| 1 | 5591 |
| 2 | 460 |
| 3 | 297 |
| 4 | 124 |
| 5 | 52 |
| 6 | 14 |
| 7 | 8 |

| Population | Version | N | Mean | Median | Min | p95 | Max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| All songs | Before | 6546 | 533.47 | 393.00 | 8.00 | 1,428.00 | 4,995.00 |
| All songs | After | 6546 | 533.42 | 393.00 | 8.00 | 1,428.00 | 4,995.00 |
| Flagged | Before | 955 | 1,286.95 | 1,089.00 | 8.00 | 2,696.00 | 4,995.00 |
| Flagged | After | 955 | 1,286.62 | 1,089.00 | 8.00 | 2,696.00 | 4,995.00 |
| Corrected | Before | 1 | 640.00 | 640.00 | 640.00 | 640.00 | 640.00 |
| Corrected | After | 1 | 320.00 | 320.00 | 320.00 | 320.00 | 320.00 |

Total whitespace tokens removed: 320. Means are arithmetic averages; p95 is a linearly interpolated empirical percentile. Before means Stage 10 lyrics_clean, not the raw lyrics.

| Corrected ID | Before words | After words | Removed |
| --- | --- | --- | --- |
| 369 | 640 | 320 | 320 |

## Interpretation and later modelling

- Use lyrics_deduplicated as the minimally corrected primary candidate, retaining lyrics_clean for sensitivity analysis. Only explicitly confirmed, structurally exact cases change; remaining flags are unresolved rather than clean negatives.
- Exact duplication inflates token counts without adding vocabulary, depressing type/token lexical diversity. Removing copies can raise that ratio without changing the song’s unique vocabulary.
- Within-block choruses remain. Whole-block and line-repetition measures should be recomputed from the chosen lyric version later; existing Stage 10 features intentionally remain historical and unchanged.
- Sentiment totals and truncation-sensitive models can change; token-average sentiment may remain unchanged under exact duplication. TF-IDF effects depend on normalization and sublinear term frequency: normalized linear TF may be invariant to uniform repetition. Topic count models can overweight repeated transcriptions. No such models were fitted here.
- Obtain explicit decisions for the five likely and five unsure/unclassified reviewed cases; investigate representative unreviewed flags before broadening correction. Do not infer a population duplication rate from this small, partly targeted review.

Validation: all source columns, dtypes, order and values match after Parquet round-trip; source SHA-256 unchanged. The correction is reversible because lyrics and lyrics_clean are preserved. Reapplication uses immutable lyrics_clean, so the same evidence yields identical output.
