"""Render the human-review submission from saved aggregate evidence; never refit."""
import json
from pathlib import Path
import shutil
import polars as pl


def markdown(frame, decimals=4):
    def cell(x):
        return f'{x:.{decimals}f}' if isinstance(x, float) else str(x).replace('|', '/')
    return '\n'.join(['| ' + ' | '.join(frame.columns) + ' |', '| ' + ' | '.join(['---']*frame.width) + ' |'] + ['| ' + ' | '.join(cell(x) for x in row) + ' |' for row in frame.iter_rows()])


def render(out):
    pack = out/'Analysis_1'
    tables = pack/'tables'
    manifest = json.loads((out/'run_manifest.json').read_text())
    means = pl.read_csv(tables/'model_means.csv')
    paired = pl.read_csv(tables/'paired_means.csv')
    correlations = pl.read_csv(tables/'correlation_pairs.csv')
    permutation = pl.read_csv(tables/'permutation_summary.csv').sort('ap_drop', descending=True)
    confusion = pl.read_csv(tables/'confusion_metrics.csv')
    main = means.filter(~pl.col('model').str.starts_with('Without'))
    base_ap, simple_ap, full_ap, sd_ap, sd_full_ap = main['ap'].to_list()
    component_notes = [
        ('Broad conversational language; unclear theme', 'Contractions and common relational words dominate. Representatives concern presence, reassurance and independence; a single theme is not supported.'),
        ('Vocal-syllable dominated: oh/whoa', 'Repeated oh/whoa passages occur in the representatives, alongside otherwise varied narrative content.'),
        ('Explicit street/status vocabulary', 'Top terms include profanity, a racial slur, money and colloquial forms. Representatives contain conflict/status language. This is a lexical pattern, not a validated genre or demographic label.'),
        ('Vocal-syllable dominated: ooh/ah', 'Representatives have repeated ooh passages despite different narrative contexts; avoid calling this a coherent emotional theme.'),
        ('Vocal-syllable dominated: na', 'Repeated na refrains link representatives whose other content differs; retained performance syllables are not cleaning errors.'),
        ('Vocal-syllable dominated: la/da', 'Repeated la refrains dominate representative texts. A numeric token among top terms makes a broad thematic label especially uncertain.'),
        ('Interjections/ad-libs: yeah/uh', 'Representatives range from party wording to searching and self-reflection; shared yeah repetitions do not establish one theme.'),
        ('Love/affection vocabulary', 'Love, heart and need recur in the top terms and representative relationship wording. Repeated love hooks may drive weights; this is not a topic percentage.'),
        ('Affection/address: baby/girl', 'Representatives repeatedly address baby/girl. Overlaps lexically with love vocabulary; this is not an exclusive category.'),
        ('Negation/desire/knowing; broad lexical pattern', 'Repeated do-not/know/want wording links secrecy and conversational desire in representatives. Not a direct measure of negative emotion.')]
    components = json.loads((pack/'private/descriptive_components.json').read_text())
    component_table = pl.DataFrame([dict(component=c['component'], top_words=', '.join(c['positive_terms']), provisional_label=component_notes[c['component']-1][0], evidence_and_limitations=component_notes[c['component']-1][1]) for c in components])
    component_table.write_csv(tables/'component_interpretation.csv')
    (pack/'component_interpretation.md').write_text('# Descriptive NMF interpretation\n\nReuses the frozen v2 all-data fit. Three saved high-score representative records per component were inspected in a bounded text review. Their identities and full texts remain in private/component_examples.json. Component numbers belong only to this fit, not the fold-specific predictive representations. Labels remain provisional and require member review.\n\n'+markdown(component_table)+'\n\nFor the presentation contrast components 2 (vocal syllables), 8 (love vocabulary), and 1 (broad/unclear). This makes the limits of thematic interpretation visible without forcing all axes into topics.\n', encoding='utf-8')
    report = f'''# Analysis 1: do lyrics add predictive information?

**Human-review draft, 21 November 2026.** Uguumur and Nafees must review the interpretation and private cases before submission. This is an observational predictive analysis among matched Billboard-charting records, not a causal study or a predictor of whether an arbitrary song will chart.

**Answer:** lyric features improve observed ranking beyond audio in these saved grouped folds: AP rises from {base_ap:.4f} to {simple_ap:.4f} with the three simple features, and to {full_ap:.4f} with NMF added. The new cumulative SD contributes very little: {sd_ap-simple_ap:+.6f} AP without NMF and {sd_full_ap-full_ap:+.6f} with NMF. Its ROC-AUC differences are slightly negative. This does not establish a meaningful or statistically reliable additional benefit from cumulative SD.

## Research question and historical context

Do lyric-derived features improve Billboard Top-10 prediction beyond audio characteristics among the matched Billboard-charting records?

The frozen master has {manifest['master_n']:,} records. The automated English-labelled sample has {manifest['eligible_n']:,} records, including {manifest['positive']:,} Top-10 outcomes (15.41%). Historical preprocessing retained the population and normalized 947 whole-text repetitions, preserved one supported earlier correction, and retained seven repeats under the policy. No new matching, language threshold, target, or lyric cleaning was introduced. The historical NMF/SVD/centered-PCA comparisons remain context; only the requested comparisons are added here.

Five saved grouped folds are shared by every model. There are {manifest['group_count']:,} groups (size minimum {manifest['group_sizes']['min']}, median {manifest['group_sizes']['median']:.0f}, maximum {manifest['group_sizes']['max']}). The same ten audio medians and regularized logistic regression (C=1, L2, no class weights, threshold 0.5) are used. Imputation and scaling fit on training records only. The necessary NMF representations were reconstructed within training folds because reusable fitted NMF objects were not saved. Historical reference probabilities were reused unchanged. No full-data descriptive representation enters prediction.

## Teacher feedback and operational response

The teacher requested cumulative sentiment with a dispersion measure, feature importance, and inspection of misclassifications. Code inspection established that the existing sentiment was already a **word-weighted mean**, not a sum. For ordered nonblank natural lines, let s_j be the VADER compound score and w_j the whitespace word count:

    c_j = sum(i=1..j, w_i * s_i) / sum(i=1..j, w_i)
    sentiment_mean = c_L
    cumulative_mean_sd = sqrt(mean(j=1..L, (c_j - mean(c))^2))

This is our operational interpretation of the feedback, not a teacher-specified or validated measure of song emotion. The terminal mean equals the existing weighted polarity within 1e-12 tolerance; it is not added twice. The only new predictor is cumulative_mean_sd. Population SD uses ddof=0 and equal weight for each cumulative endpoint, a project choice. A single valid line has SD=0. Missing or failed scoring is explicitly distinct from valid neutral zero and would use training-only imputation, without excluding eligible records.

The same revised natural text, line order, apostrophe normalization, VADER 3.3.2 and lexicon were used. Negation and punctuation were preserved. No stopword-filtered text or truncated text was scored. Compatible line-score caches were not available, so all lines were rescored and cached privately. Status counts across the master: {manifest['measurement_status']}. There are {manifest['missing_numeric_cells']} missing numeric predictor cells in the eligible analysis.

The new feature depends on order and line boundaries. Cumulative averaging smooths later changes; early lines and lyric length can strongly influence it. It is not direct line-score volatility, emotional complexity, or lyric quality. Figure 02 separates actual outcome distributions from explicitly synthetic trajectories with equal final means. Private actual trajectories use deterministic extremes within each outcome and normalized original line position for plotting only; the feature uses all original cumulative endpoints.

## Predictive comparison

Primary metric: equal-fold mean AP. Secondary: ROC-AUC. Pooled metrics are separate in `tables/pooled_metrics.csv`; they are not averages of fold scores. All fold values and paired differences are supplied. Predictor counts exclude the intercept.

{markdown(means.select('model', 'predictors', 'ap', 'roc_auc', 'precision', 'recall', 'f1', 'predicted_positive'))}

The predicted-positive count in this table is an equal-fold mean; exact pooled counts appear below and in the pooled table. Classification uses the fixed 0.5 threshold. No threshold or hyperparameter was selected on held-out results.

### Paired differences (equal-fold means)

{markdown(paired)}

Differences are descriptive, not evidence of statistical significance. Training sets overlap; an ordinary test treating these five folds as independent is inappropriate. The held-out folds also do not constitute independent external validation after repeated project development.

The cumulative feature has positive AP differences in four of five folds in each comparison, but the increments are tiny. For the full model, pooled AP actually changes from 0.280365 to 0.280251 while equal-fold mean AP rises slightly. These are different summaries; neither supports a strong improvement claim. The observed cumulative-SD distributions overlap closely (medians 0.06024 for Top-10 versus 0.06376 for other charting records).

## Feature contributions

The three `Without ...` models are independently retrained leave-one-feature-out ablations from Audio + the original three simple features. Positive full-minus-removed AP differences indicate incremental predictive contribution in this fixed specification. These answer a different question from model reliance.

Removing repetition reduces mean AP by 0.01361 (positive full-minus-removed difference in all five folds); removing length reduces it by 0.01044 (four of five folds); removing existing sentiment reduces it by 0.00291 (four of five folds). Length and repetition therefore carry more incremental evidence than mean sentiment in this reference model.

Held-out permutation importance uses the prespecified 24-predictor model, irrespective of which model scores best. Each final raw numeric column was shuffled before the fitted imputer/scaler/classifier, using 20 reproducible permutations per feature per fold. The ten NMF score columns were shuffled jointly with one shared row permutation. Models were not refit, and input arrays and fitted models were checked unchanged. Fold-specific component numbers were not averaged as if aligned topics.

{markdown(permutation)}

The reported spread combines shuffle and fold variation; within-fold shuffle SDs are separately supplied. Neither is a population confidence interval. Correlated predictors can share importance, shuffled values can form unrealistic combinations, and negative importances are possible. Coefficients are supplied for the newly fitted models on standardized scales, with intercepts in a separate table. They describe model reliance, not causal effects. Reference coefficient values were not stored historically; no unnecessary reference classifier refits were made merely to reconstruct them. No ordinary regression p-values are reported.

In the 24-predictor model, the largest mean permutation drops are length (0.06938), the joint NMF block (0.06205), repetition (0.02927), and danceability (0.02813). Existing sentiment (0.000006) and cumulative SD (0.000149) have very small drops. This is not inconsistent with the sentiment ablation: the ablation refits a different, 13-predictor reference model, whereas permutation freezes the 24-predictor model and its correlated alternatives.

## Predictor correlations

One descriptive Spearman matrix covers the 14 audio/simple/cumulative predictors on the eligible sample. Pairwise finite complete observations are used; pair counts are saved in a separate matrix. The target, IDs, flags, and fold-specific components are excluded. No feature was removed in response to correlations.

Strongest absolute correlations:

{markdown(correlations.head(8))}

New measure versus length, repetition and existing sentiment:

{markdown(correlations.filter((pl.col('feature_b') == 'cumulative_mean_sd') & pl.col('feature_a').is_in(['p2_log_word_count', 'p2_line_repetition', 'p2_sentiment'])))}

Correlations complicate individual attribution: a model can substitute one associated predictor for another, and an ablation can allow coefficients on the retained predictors to change.

Energy and loudness have the strongest correlation (rho=0.708), followed by speechiness and lyric length (0.603). Cumulative SD has weak rank correlations with length (-0.017), repetition (-0.115), and existing mean sentiment (0.073). Thus its small incremental performance cannot simply be attributed to strong pairwise redundancy with these three features. Every pair has 6,385 observations; no pairwise rows were lost.

## Held-out error analysis

Both the historical 23-predictor and new 24-predictor configurations were examined, without selecting a winner for error review. Confusion counts were recomputed from saved out-of-fold predictions:

{markdown(confusion.select('model', 'TP', 'FP', 'TN', 'FN', 'precision', 'recall', 'f1', 'predicted_positive', 'fp_peak_11_20', 'fp_peak_21_100'))}

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
'''
    (pack/'report.md').write_text(report, encoding='utf-8')
    outline = '''# 12-minute presentation outline

Times total exactly 12:00. Figure paths are relative to this Analysis_1 folder.

| Time | Topic and speaking points | Figure |
| --- | --- | --- |
| 0:00-1:00 | Research question; matched charting population; 6,385 records, 984 positives; five grouped folds. | None |
| 1:00-3:00 | Existing sentiment is a weighted mean. Explain c_j and endpoint SD; identical terminal means can hide different trajectories. Explain order and early-line sensitivity. | figures/02_sentiment.png |
| 3:00-5:00 | AP: audio 0.2334, simple 0.2637, simple+NMF 0.2870. Cumulative SD gives only +0.000117 / +0.000290. Pooled full-model AP falls slightly. No significance claim. | figures/01_model_ap.png |
| 5:00-6:30 | Ablation AP losses: repetition 0.01361, length 0.01044, sentiment 0.00291. Fixed-model permutation relies most on length, joint NMF, repetition and danceability. | figures/03_permutation.png |
| 6:30-7:30 | Strong correlations and cumulative SD versus length/repetition; no post-hoc feature deletion. | figures/04_correlations.png |
| 7:30-9:00 | Exact out-of-fold confusion counts; fixed threshold predicts few positives; FP ranks 11-20 versus 21-100. Mention one reviewed private case verbally only after member approval. | figures/05_errors.png |
| 9:00-10:15 | Contrast descriptive components 2 (oh/whoa syllables), 8 (love vocabulary) and 1 (broad/unclear); lexical labels, not topic percentages. | None |
| 10:15-11:15 | Additional preprocessing: verified checks, limitations, optional future sensitivity; no outcome-driven cleaning. | None |
| 11:15-12:00 | Main answer, uncertainty, and questions for class. | None |

Use the report's saved numeric tables for speaking notes; do not substitute pooled AP for the plotted equal-fold values. Private trajectories and full-text reviews are discussion preparation, not additional public main figures.
'''
    (pack/'presentation_12_minutes.md').write_text(outline, encoding='utf-8')
    from music_success_nlp.analysis_delivery import reproduction_document
    reproduction = reproduction_document(out, manifest)
    (pack/'reproduction.md').write_text(reproduction, encoding='utf-8')
    (pack/'handover.md').write_text('''# Teammate handover

Authoritative new analysis: this Analysis_1/report.md and tables/. The five main figures and exact 12-minute outline are alongside it. Code entry point is code/src/17_analysis_1.py. The run_manifest.json and verification.json copies in this folder provide provenance; full verification also requires the complete private run. Historical v2/v3 remain unchanged and authoritative for their original comparisons.

Uguumur and Nafees must personally review the formulas and teacher-feedback interpretation, actual comparisons and uncertainty wording, private error/trajectory examples, all ten component labels and representative records, the preprocessing assessment, and the presentation timing. Review the supplied 17 November presentation reconciliation notes. Do not describe review as completed until both members have actually reviewed it.

The private/ subfolder contains full lyrics, per-record predictions, fitted objects and case lists: keep it private. For the assignment upload, use the report, code, tables, five figures, outline and reproduction/verification materials; exclude private/. No master corpus is bundled. Nothing was pushed, merged, uploaded or sent to anyone.
''', encoding='utf-8')
    for name in ['run_manifest.json', 'verification.json', 'output_hashes.json']:
        shutil.copy2(out/name, pack/name)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    render(parser.parse_args().run.resolve())
