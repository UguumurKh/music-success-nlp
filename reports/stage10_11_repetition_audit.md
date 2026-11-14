# Stage 10–11 repeated-block audit

Audit date: 2026-11-01. **Complete within the requested local-output scope; interpretation remains unresolved.** Existing outputs were reused. No integration, correction, exclusion or source rewrite was performed. No lyrics, token vocabulary or private review notes are included in this report.

## Verified detection and correction

**Yes:** Stage 10 requires the entire nonblank line sequence to equal an integer number (≥2) of copies of a shorter sequence. It casefolds and collapses within-line whitespace, discards blank lines, then finds the smallest period dividing the line count. `lyric_full_block_repeats` is the resulting multiplicity, otherwise 1. It is not a partial-chorus detector and does not prove extraction duplication. All 6,546 multiplicities were independently recomputed and agree.

Stage 11 requires every saved review to say “extraction duplication”, nonempty notes, review text equal to current `lyrics_clean`, and verbatim blocks (ignoring newline separators at boundaries). Its base must have ≥12 nonblank lines, ≥100 whitespace tokens and ≥6 distinct lines. These are ambiguity guards, not proof of a complete performance. No saved review, “likely source duplication”, blank classifications, or uncertainty authorizes shortening.

| Stage 11 status | Records |
| --- | --- |
| corrected | 1 |
| not_applicable | 5591 |
| suspected | 948 |
| uncertain | 6 |

**Text completeness:** `lyrics_deduplicated` is non-null and nonblank for all 6,546 records. All 6,545 uncorrected records equal `lyrics_clean` exactly. The existing correction is ID 369 (640 → 320 whitespace tokens). All 954 unresolved flags remain unchanged. Recomputing Stage 11 in memory with saved reviews reproduces the complete saved output.

**Preservation:** Stage 9’s 94 columns survive unchanged in Stage 10’s 124; all 124 Stage 10 columns survive unchanged in Stage 11’s 130. Record count, order, schema/dtypes and every source value agree; IDs are unique and non-null. SHA-256 checks confirm all three input datasets, both review workbooks and both prior reports stayed unchanged. The prior report source/workbook hashes match the observed inputs. The latest processed dataset is `data/processed/billboard_lyrics_corrected_2000_2022.parquet`. README phase descriptions are stale.

## Flagged-case distribution (955 records)

| Multiplicity | Records | Median unit lines | Median unit words | Median total words |
| --- | --- | --- | --- | --- |
| 2 | 460 | 54.00 | 375.50 | 751.00 |
| 3 | 297 | 65.00 | 471.00 | 1,413.00 |
| 4 | 124 | 61.00 | 424.00 | 1,696.00 |
| 5 | 52 | 69.50 | 476.50 | 2,382.50 |
| 6 | 14 | 50.00 | 359.50 | 2,157.00 |
| 7 | 8 | 68.00 | 398.50 | 2,789.50 |

| Length measure | Min | Mean | Median | p95 | Max |
| --- | --- | --- | --- | --- | --- |
| unit_nonblank_lines | 1.00 | 61.97 | 59.00 | 105.00 | 193.00 |
| unit_words | 4.00 | 447.92 | 411.00 | 781.60 | 1,565.00 |
| unit_chars | 26.00 | 2,237.54 | 2,046.00 | 3,906.10 | 7,747.00 |
| total_nonblank_lines | 2.00 | 178.08 | 150.00 | 364.00 | 651.00 |
| total_words | 8.00 | 1,286.95 | 1,089.00 | 2,696.00 | 4,995.00 |
| total_chars | 53.00 | 6,431.63 | 5,496.00 | 13,415.20 | 25,393.00 |

Unit lines = nonblank cleaned lines / multiplicity. The one-unit alternative is the first block cut at the corresponding nonblank-line boundary, retaining its internal blank lines and removing trailing newline separators. Unit words = `len(unit.split())`; unit characters = `len(unit)`. Total words and characters use `lyric_words_after` and `lyric_chars_after`, verified against `lyrics_clean`. Characters count Unicode code points, not bytes. Total nonblank lines are calculated directly. p95 uses linear interpolation; character totals include separators and need not equal unit characters × multiplicity.

## Fixed-fit unigram TF-IDF sensitivity check

One dependency-free vectorizer was fitted once on all 6,546 Stage 10 `lyrics_clean` texts (35,620 vocabulary terms), then the **same fitted object** transformed full texts and first-unit alternatives. It uses word unigrams, lowercase=True, Unicode token pattern `(?u)\b\w\w+\b`, no stopwords, no accent stripping, min_df=1, max_df=1.0, binary=False, use_idf=True, smooth_idf=True, **sublinear_tf=False, norm="l2"**. IDF = log((1 + N)/(1 + df)) + 1; weighted raw counts are divided by their L2 norm. This explicit standard-library implementation is in the audit script; scikit-learn is not installed. No model-training/evaluation claim is made from this descriptive all-corpus fit.

**953 verbatim-block cases:** maximum component difference 2.220e-16; maximum L2 distance 2.777e-16. **All 955 normalized flags:** maximum component difference 2.220e-16; maximum L2 distance 2.777e-16. Maximum |1 − cosine similarity| = 3.331e-16. No zero vectors, no non-proportional token-count cases and no component differences above 1e-12 were found. Floating-point roundoff accounts for the tiny residuals. With fixed IDF, multiplying every term count by the same positive integer multiplies the norm by that integer, so normalization cancels it.

**Investigated structural exceptions:** all 955 flags match verbatim at the nonblank-line level; two fail full-block equality solely because internal blank-line layout differs:

| ID | Multiplicity | Unit nonblank lines | Internal blank lines by block |
| --- | --- | --- | --- |
| 5054 | 2 | 4 | 1, 0 |
| 6456 | 2 | 7 | 1, 0 |

Whitespace differences do not alter this unigram tokenizer’s counts; both also have invariant vectors. Only 948 flags pass Stage 11’s full structural/size gate, which is separate from evidence authorization. No hypothetical alternative was written into the dataset. The result does not generalize to sublinear TF, n-grams crossing block boundaries, refitted IDF, truncation-sensitive models, or merely partial repetitions.

## Private review queue and unresolved decisions

Created `data/processed/stage10_11_audit/review_20_unreviewed.csv`: 20 records spanning 20 distinct unit lengths (7–193 nonblank lines). The eligible pool contains 928 flagged records after excluding every ID present in either saved review workbook (even blank classifications) and every prior Stage 10 inspection ID. This defines “previously unreviewed” only within available repository evidence; external reviews cannot be ruled out. Selection uses 20 evenly spaced ranks across distinct eligible unit lengths, with lowest stable Billboard ID as tie-breaker. It is a coverage sample, not a population prevalence sample.

The table includes stable Billboard/Spotify IDs, current review and Stage 11 statuses, length and vector metrics, and blank evidence-location, timestamp, notes, decision, reviewer and date fields. It contains no lyrics; retrieve text locally by ID. It lives under the existing Git-ignored processed-data directory. The audit never overwrites an existing review queue, and the queue is not a Stage 11 correction input.

**Unresolved:** whether flagged repetitions are intentional performance structure or extraction errors requires case-specific source/recording evidence. Existing reviewer claims were checked for gate compliance, not independently authenticated. The 954 unresolved cases remain included and unchanged. TF-IDF invariance provides no evidence that deleting text is semantically justified.

Reproducibility: `src/audit_stage10_11_repetition.py`; private `flagged_tfidf_comparison.csv` (one row per flag) and `audit_metrics.json` (counts and input SHA-256 manifest). Existing Stage 10/11 tests and the audit’s independent period, count, equality and analytic TF-IDF checks provide the verification evidence. No public artifact contains lyrics.
