# Analysis 1: do lyrics add predictive information?

**Human-review draft, 21 November 2026.** Uguumur and Nafees must review the interpretation and private cases before submission. This is an observational predictive analysis among matched Billboard-charting records, not a causal study or a predictor of whether an arbitrary song will chart.

**Answer:** lyric features improve observed ranking beyond audio in these saved grouped folds: AP rises from 0.2334 to 0.2637 with the three simple features, and to 0.2870 with NMF added. The new cumulative SD contributes very little: +0.000117 AP without NMF and +0.000290 with NMF. Its ROC-AUC differences are slightly negative. This does not establish a meaningful or statistically reliable additional benefit from cumulative SD.

## Research question and historical context

Do lyric-derived features improve Billboard Top-10 prediction beyond audio characteristics among the matched Billboard-charting records?

The frozen master has 6,546 records. The automated English-labelled sample has 6,385 records, including 984 Top-10 outcomes (15.41%). Historical preprocessing retained the population and normalized 947 whole-text repetitions, preserved one supported earlier correction, and retained seven repeats under the policy. No new matching, language threshold, target, or lyric cleaning was introduced. The historical NMF/SVD/centered-PCA comparisons remain context; only the requested comparisons are added here.

Five saved grouped folds are shared by every model. There are 2,159 groups (size minimum 1, median 1, maximum 134). The same ten audio medians and regularized logistic regression (C=1, L2, no class weights, threshold 0.5) are used. Imputation and scaling fit on training records only. The necessary NMF representations were reconstructed within training folds because reusable fitted NMF objects were not saved. Historical reference probabilities were reused unchanged. No full-data descriptive representation enters prediction.

## Teacher feedback and operational response

The teacher requested cumulative sentiment with a dispersion measure, feature importance, and inspection of misclassifications. Code inspection established that the existing sentiment was already a **word-weighted mean**, not a sum. For ordered nonblank natural lines, let s_j be the VADER compound score and w_j the whitespace word count:

    c_j = sum(i=1..j, w_i * s_i) / sum(i=1..j, w_i)
    sentiment_mean = c_L
    cumulative_mean_sd = sqrt(mean(j=1..L, (c_j - mean(c))^2))

This is our operational interpretation of the feedback, not a teacher-specified or validated measure of song emotion. The terminal mean equals the existing weighted polarity within 1e-12 tolerance; it is not added twice. The only new predictor is cumulative_mean_sd. Population SD uses ddof=0 and equal weight for each cumulative endpoint, a project choice. A single valid line has SD=0. Missing or failed scoring is explicitly distinct from valid neutral zero and would use training-only imputation, without excluding eligible records.

The same revised natural text, line order, apostrophe normalization, VADER 3.3.2 and lexicon were used. Negation and punctuation were preserved. No stopword-filtered text or truncated text was scored. Compatible line-score caches were not available, so all lines were rescored and cached privately. Status counts across the master: {'ok': 6546}. There are 0 missing numeric predictor cells in the eligible analysis.

The new feature depends on order and line boundaries. Cumulative averaging smooths later changes; early lines and lyric length can strongly influence it. It is not direct line-score volatility, emotional complexity, or lyric quality. Figure 02 separates actual outcome distributions from explicitly synthetic trajectories with equal final means. Private actual trajectories use deterministic extremes within each outcome and normalized original line position for plotting only; the feature uses all original cumulative endpoints.

## Predictive comparison

Primary metric: equal-fold mean AP. Secondary: ROC-AUC. Pooled metrics are separate in `tables/pooled_metrics.csv`; they are not averages of fold scores. All fold values and paired differences are supplied. Predictor counts exclude the intercept.

| model | predictors | ap | roc_auc | precision | recall | f1 | predicted_positive |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Audio | 10 | 0.2334 | 0.6281 | 0.2000 | 0.0010 | 0.0020 | 0.6000 |
| Audio + simple lyrics | 13 | 0.2637 | 0.6639 | 0.5000 | 0.0061 | 0.0120 | 2.2000 |
| Audio + simple lyrics + NMF | 23 | 0.2870 | 0.6814 | 0.4667 | 0.0111 | 0.0217 | 4.2000 |
| Audio + simple lyrics + cumulative SD | 14 | 0.2638 | 0.6636 | 0.5000 | 0.0061 | 0.0120 | 2.4000 |
| Audio + simple lyrics + cumulative SD + NMF | 24 | 0.2873 | 0.6813 | 0.4467 | 0.0111 | 0.0216 | 4.2000 |
| Without p2_log_word_count | 12 | 0.2532 | 0.6543 | 0.3667 | 0.0050 | 0.0099 | 1.8000 |
| Without p2_line_repetition | 12 | 0.2501 | 0.6429 | 0.2000 | 0.0010 | 0.0020 | 0.2000 |
| Without p2_sentiment | 12 | 0.2608 | 0.6625 | 0.3333 | 0.0050 | 0.0099 | 2.2000 |

The predicted-positive count in this table is an equal-fold mean; exact pooled counts appear below and in the pooled table. Classification uses the fixed 0.5 threshold. No threshold or hyperparameter was selected on held-out results.

### Paired differences (equal-fold means)

| comparison | ap_difference | roc_auc_difference |
| --- | --- | --- |
| Audio + simple lyrics minus Audio | 0.0303 | 0.0358 |
| Audio + simple lyrics + NMF minus Audio + simple lyrics | 0.0234 | 0.0176 |
| Audio + simple lyrics + cumulative SD minus Audio + simple lyrics | 0.0001 | -0.0003 |
| Audio + simple lyrics + cumulative SD + NMF minus Audio + simple lyrics + NMF | 0.0003 | -0.0001 |
| Audio + simple lyrics minus Without p2_log_word_count | 0.0104 | 0.0096 |
| Audio + simple lyrics minus Without p2_line_repetition | 0.0136 | 0.0209 |
| Audio + simple lyrics minus Without p2_sentiment | 0.0029 | 0.0014 |

Differences are descriptive, not evidence of statistical significance. Training sets overlap; an ordinary test treating these five folds as independent is inappropriate. The held-out folds also do not constitute independent external validation after repeated project development.

The cumulative feature has positive AP differences in four of five folds in each comparison, but the increments are tiny. For the full model, pooled AP actually changes from 0.280365 to 0.280251 while equal-fold mean AP rises slightly. These are different summaries; neither supports a strong improvement claim. The observed cumulative-SD distributions overlap closely (medians 0.06024 for Top-10 versus 0.06376 for other charting records).

## Feature contributions

The three `Without ...` models are independently retrained leave-one-feature-out ablations from Audio + the original three simple features. Positive full-minus-removed AP differences indicate incremental predictive contribution in this fixed specification. These answer a different question from model reliance.

Removing repetition reduces mean AP by 0.01361 (positive full-minus-removed difference in all five folds); removing length reduces it by 0.01044 (four of five folds); removing existing sentiment reduces it by 0.00291 (four of five folds). Length and repetition therefore carry more incremental evidence than mean sentiment in this reference model.

Held-out permutation importance uses the prespecified 24-predictor model, irrespective of which model scores best. Each final raw numeric column was shuffled before the fitted imputer/scaler/classifier, using 20 reproducible permutations per feature per fold. The ten NMF score columns were shuffled jointly with one shared row permutation. Models were not refit, and input arrays and fitted models were checked unchanged. Fold-specific component numbers were not averaged as if aligned topics.

| feature | ap_drop | shuffle_and_fold_sd |
| --- | --- | --- |
| p2_log_word_count | 0.0694 | 0.0234 |
| NMF joint (10 columns) | 0.0620 | 0.0253 |
| p2_line_repetition | 0.0293 | 0.0174 |
| danceability_median | 0.0281 | 0.0141 |
| energy_median | 0.0147 | 0.0128 |
| loudness_median | 0.0113 | 0.0096 |
| valence_median | 0.0062 | 0.0048 |
| acousticness_median | 0.0049 | 0.0049 |
| duration_ms_median | 0.0003 | 0.0035 |
| speechiness_median | 0.0003 | 0.0037 |
| liveness_median | 0.0002 | 0.0012 |
| cumulative_mean_sd | 0.0001 | 0.0009 |
| instrumentalness_median | 0.0001 | 0.0013 |
| p2_sentiment | 0.0000 | 0.0008 |
| tempo_median | -0.0001 | 0.0013 |

The reported spread combines shuffle and fold variation; within-fold shuffle SDs are separately supplied. Neither is a population confidence interval. Correlated predictors can share importance, shuffled values can form unrealistic combinations, and negative importances are possible. Coefficients are supplied for the newly fitted models on standardized scales, with intercepts in a separate table. They describe model reliance, not causal effects. Reference coefficient values were not stored historically; no unnecessary reference classifier refits were made merely to reconstruct them. No ordinary regression p-values are reported.

In the 24-predictor model, the largest mean permutation drops are length (0.06938), the joint NMF block (0.06205), repetition (0.02927), and danceability (0.02813). Existing sentiment (0.000006) and cumulative SD (0.000149) have very small drops. This is not inconsistent with the sentiment ablation: the ablation refits a different, 13-predictor reference model, whereas permutation freezes the 24-predictor model and its correlated alternatives.

## Predictor correlations

One descriptive Spearman matrix covers the 14 audio/simple/cumulative predictors on the eligible sample. Pairwise finite complete observations are used; pair counts are saved in a separate matrix. The target, IDs, flags, and fold-specific components are excluded. No feature was removed in response to correlations.

Strongest absolute correlations:

| feature_a | feature_b | rho | pair_n | absolute_rho |
| --- | --- | --- | --- | --- |
| energy_median | loudness_median | 0.7077 | 6385 | 0.7077 |
| speechiness_median | p2_log_word_count | 0.6030 | 6385 | 0.6030 |
| energy_median | acousticness_median | -0.4698 | 6385 | 0.4698 |
| danceability_median | p2_log_word_count | 0.4533 | 6385 | 0.4533 |
| energy_median | valence_median | 0.4297 | 6385 | 0.4297 |
| danceability_median | speechiness_median | 0.3497 | 6385 | 0.3497 |
| loudness_median | acousticness_median | -0.3340 | 6385 | 0.3340 |
| loudness_median | valence_median | 0.3077 | 6385 | 0.3077 |

New measure versus length, repetition and existing sentiment:

| feature_a | feature_b | rho | pair_n | absolute_rho |
| --- | --- | --- | --- | --- |
| p2_line_repetition | cumulative_mean_sd | -0.1148 | 6385 | 0.1148 |
| p2_sentiment | cumulative_mean_sd | 0.0734 | 6385 | 0.0734 |
| p2_log_word_count | cumulative_mean_sd | -0.0167 | 6385 | 0.0167 |

Correlations complicate individual attribution: a model can substitute one associated predictor for another, and an ablation can allow coefficients on the retained predictors to change.

Energy and loudness have the strongest correlation (rho=0.708), followed by speechiness and lyric length (0.603). Cumulative SD has weak rank correlations with length (-0.017), repetition (-0.115), and existing mean sentiment (0.073). Thus its small incremental performance cannot simply be attributed to strong pairwise redundancy with these three features. Every pair has 6,385 observations; no pairwise rows were lost.

## Held-out error analysis

Both the historical 23-predictor and new 24-predictor configurations were examined, without selecting a winner for error review. Confusion counts were recomputed from saved out-of-fold predictions:

| model | TP | FP | TN | FN | precision | recall | f1 | predicted_positive | fp_peak_11_20 | fp_peak_21_100 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Audio + simple lyrics + NMF | 11 | 10 | 5391 | 973 | 0.5238 | 0.0112 | 0.0219 | 21 | 3 | 7 |
| Audio + simple lyrics + cumulative SD + NMF | 11 | 10 | 5391 | 973 | 0.5238 | 0.0112 | 0.0219 | 21 | 3 | 7 |

The two FP peak columns partition each model's full FP denominator. Thus errors near rank 10 are distinguished from lower chart positions without changing the target. Most positives are false negatives at this threshold because few records are predicted positive. A false negative is not automatically a confidently wrong prediction: the private list deliberately selects the lowest-probability false negatives, whereas the aggregate category contains many less extreme cases.

Both models predict 21/6,385 positives and recover 11/984 true positives (recall 1.118%). Of 10 false positives per model, 3/10 peaked at 11-20 and 7/10 at 21-100. Equal confusion totals hide two changed classifications among actual negatives; the true-positive set is unchanged. FP and TP groups are small (10 and 11 records respectively). In the historical model, median recurring-line fraction is about 0.552 in both FP and TP groups, versus 0.364 in FN and 0.327 in TN. Historical group counts are FP 10, TP 10, FN 547 and TN 1,871; category group counts can overlap. These descriptive patterns do not explain individual errors causally.

Private review lists contain up to five highest-probability FPs, lowest-probability FNs, highest-probability TPs and lowest-probability TNs per model, breaking ties by stable ID. They include credit, peak rank, features and existing flags. Category sample sizes, unique groups, maximum within-category group size and feature quartiles are supplied in `error_category_features.csv`. Tiny FP/TP categories are not a sound basis for broad genre or language claims. Detailed observed properties and unresolved explanations belong in `private/review_notes.md`; full lyrics remain private.

## Qualitative component interpretation

The existing all-data descriptive NMF fit is reused unchanged. See `component_interpretation.md` for all ten components and bounded review evidence. Labels are provisional lexical summaries, not validated themes. Component numbers identify only this fit. Weights are not topic percentages, and these numbers are not equated with fold-specific axes. Representative full text is confined to the private folder.

## Does the analysis indicate additional preprocessing is needed?

**Verified implementation/data errors:** the checks passed for immutable source preservation, unique IDs, outcome agreement with peak rank, saved fold and group consistency, historical prediction identity, VADER version/lexicon, terminal-mean agreement, finite probabilities, training-only transforms, and saved metrics. No correction is justified by those checks. Review of selected texts and flags is documented separately; these checks are not proof that all source records are error-free.

**Measurement limitations to document:** automated language decisions, residual encoding or mixed-language flags, lyric line boundaries, sentiment lexicon coverage and slang, artist/group concentration, matching ambiguity and the early-line sensitivity of cumulative averages. No difficult records were deleted and vocal syllables were retained.

The bounded private review found repeated ideas expressed with different parenthetical ad-libs that are not identical normalized lines; this explains why an intuitively repetitive text can have a zero exact recurring-line fraction. It is a definition limitation, not proof of a counting bug. Very short texts with valid all-zero VADER scores also occur; these remain distinct from failed scoring. Low lyric/audio resolution confidence occurs in both correct and incorrect selected cases and does not by itself establish a wrong match. No verified source correction emerged from this bounded review; exhaustive source adjudication was not performed.

**Optional future sensitivity studies:** alternative line segmentation, language or matching-confidence sensitivity, and prospective threshold/calibration evaluation under a separate validation plan. None was selected using this outer evaluation. No rolling-window model, new sentiment tool, classifier search or random-noise extension is needed for this submission.

## Questions and problems for class

1. Does equal weighting of cumulative endpoints match the teacher's intended operational interpretation?
2. How should we communicate small AP increments and fold variation without claiming significance?
3. Is the 0.5 threshold useful for this imbalanced task, and what future validation would justify an operational threshold?
4. How much should lexical/vocal-syllable components be interpreted as themes?
5. Which source ambiguities warrant future sensitivity analysis while preserving this frozen primary sample?

## Limitations and review status

The analysis concerns matched charting records with automated English labels, not all released music. Predictive associations are not causal. Generalization across time, platforms, genres or future artists remains uncertain. Groups use complete artist credits and text links: individual performers can still overlap between solo and collaborative credits. Matching and text-source issues remain possible. Public aggregates contain no full lyrics or detailed private cases. This folder is a local human-review draft, not an upload or a completed human sign-off.
