# Preprocessing II: decisions and final population
Prepared 15 November 2026. Draft for project-member review before submission.

All **6,546 records** remain in the 2000–2022 matched master corpus. The primary **automated English-labelled sample** remains exactly **6,385 records**, including **984 Top-10** and **5,401 other charting songs** (15.41% positive). The other 161 records remain in the master but outside primary modelling. No sample exclusions were introduced; all eligible records are usable in every model and descriptive calculation.

## What was already done

Existing stages conservatively matched source song–artist records, selected lyric representatives and audio medians, froze the 2000–2022 analysis period, normalized Unicode/whitespace, removed supported section-label and music-note-only lines, and saved language/quality diagnostics. Stage 11 preserved all source text and shortened one supported full-text repetition. Stage 12 fitted the historical audio/NMF comparison. Those scripts, original inputs and reports remain unchanged. The README's former Phase 2A status was stale, not evidence that matching needed to be repeated.

## What changed since the previous presentation

1. Replaced the manual-evidence gate for substantial exact whole-text repetition with the approved conservative automatic normalization. The thresholds remain at least 12 nonblank lines, 100 whitespace tokens and six distinct normalized lines in the smallest retained unit. They are operational guards, not measured detection accuracy.
2. Repaired single-prefix contraction tokenization and normalized four common apostrophe variants for tokenization and sentiment. No lemmatization or new stopword list was introduced.
3. Added one narrow recoverable encoding repair: the observed Latin-1-decoded UTF-8 sequence U+00E2 U+0080 U+0098 becomes U+2018. It affects 1 record and 2 occurrences. The lossy sequence in record 1919 remains flagged; its missing character cannot be reconstructed safely.
4. Added fixed log length, recurring-line fraction and lexicon polarity features; reran the nine prespecified model families. SVD is the one alternative representation, with ten components like NMF.

## Repetition accounting

| p2_decision | len |
| --- | --- |
| normalized | 947 |
| previous_correction_preserved | 1 |
| retained_by_policy | 7 |
| unchanged | 5591 |

All **955 historical flags** reconcile to **947 newly normalized**, **one previous correction preserved**, and **seven retained by policy**. There are no pending manual-review blockers. Unflagged records number 5,591. Normalization does not establish that every repeated text was an extraction error. The seven small/low-diversity units remain unchanged; individual choruses and repeated lines inside retained blocks remain.

| p2_eligible | p2_decision | len |
| --- | --- | --- |
| False | normalized | 51 |
| False | retained_by_policy | 1 |
| False | unchanged | 109 |
| True | normalized | 896 |
| True | previous_correction_preserved | 1 |
| True | retained_by_policy | 6 |
| True | unchanged | 5482 |

Detection compares the complete nonblank line sequence after casefolding and collapsing within-line whitespace. Blank lines are ignored for comparison; punctuation is retained. Only a period that tiles the whole sequence qualifies. The original first block is retained with its case, punctuation, internal spacing and blank lines; newline separators at its end are removed. Unlike the earlier strict case/layout comparison, detection can normalize case/spacing/layout variants of the same complete normalized block. This is documented and tested. No fuzzy matching, near-verse deletion or global line deduplication occurs.

Revisions remove **800,467 whitespace tokens** relative to Stage 11, in addition to its historical 320-token correction. Text changes since Stage 11 affect 948 records (including the encoding repair; categories may overlap). Whole-text correction and encoding repair are logged separately. Source columns, raw lyrics, Stage 10 text and Stage 11 text remain intact. Original/revised full text and per-record decisions are saved privately.

| version | n | mean | median | minimum | p95 | maximum |
| --- | --- | --- | --- | --- | --- | --- |
| Stage 10 cleaned | 6546 | 533.4720 | 393.0000 | 8 | 1428.0000 | 4995 |
| Stage 11 corrected | 6546 | 533.4232 | 393.0000 | 8 | 1428.0000 | 4995 |
| Preprocessing II | 6546 | 411.1398 | 367.0000 | 8 | 760.0000 | 1677 |

For fixed vocabulary and IDF, exact duplication multiplies all unigram linear term counts by the same constant; L2 normalization cancels it. Thus normalized linear unigram TF-IDF can remain unchanged while word counts and descriptive measures change. This statement does not apply universally to sublinear TF, truncated inputs or differently fitted vocabularies. New model differences also include the tokenizer and encoding changes, so they cannot identify a repetition-only effect.

## Language, quality and usability

Eligibility is frozen from the existing `lyric_language == 'en'` labels and checked against the historical prediction IDs. The saved `eligible_ids.csv` is the authoritative ordered list. No detector rerun, new confidence threshold, translation or line deletion occurred. Detector scores are not calibrated probabilities of correctness. Low-confidence and possibly mixed-language records remain eligible, including the previously observed Korean/English example. Separate emotion categories were not measured.

| historical_flag | master | eligible |
| --- | --- | --- |
| lyric_encoding_review | 2 | 2 |
| lyric_mixed_script_token_review | 67 | 58 |
| lyric_invisible_review | 1 | 1 |
| lyric_web_metadata_review | 1 | 1 |
| lyric_residual_brackets | 16 | 16 |
| lyric_language_uncertain | 115 | 92 |
| lyric_language_mixed_candidate | 36 | 27 |
| lyric_language_short | 11 | 10 |
| any_missing_audio_value | 0 | 0 |

Historical flags are preserved even after a supported repair. The invisible-character flag belongs to the encoding-repaired record; the web-metadata flag is the title-related `www.memory` case and is retained. Mixed-script tokens, residual brackets, source matching/consolidation uncertainty and near-duplicate candidates remain explicit limitations. No raw matching was reopened, records added or period expanded. No missing/blank lyric or nonfinite audio measurement prevents primary analysis. There is no comprehensive manual validation of transcription, language or matching.

## Authoritative input and audit

Source: `D:\Projects\music-success-nlp\data\processed\billboard_lyrics_corrected_2000_2022.parquet`

SHA-256: `2fae233f34a3c9b45a9f15be65f8d6f11511d812357dbd63be57968602c52e20`

Grain: one existing Billboard song–artist record; 6,546 unique, nonnull `billboard_source_row` IDs. Master Top-10 count: 993; other master records: 5553. Target is observed `peak_rank <= 10`, checked against `top10`; no rank-11–15 gap exclusion.

`../decision_audit.csv`, `../master.parquet`, `../eligible_ids.csv` and `../run_manifest.json` preserve the complete audit. No raw input, previous report or historical prediction file was overwritten.
