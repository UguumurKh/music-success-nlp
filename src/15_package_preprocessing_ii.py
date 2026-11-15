"""Create the local Markdown submission from verified Stage 14 outputs.

No model refitting. Full-text samples remain only in the ignored run directory.
Public reports contain aggregate tables, figures and methodological prose only.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stage14',ROOT/'src/14_preprocessing_ii_analysis.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def table(frame, columns=None):
    frame = frame.select(columns) if columns else frame
    def fmt(value):
        return f'{value:.4f}' if isinstance(value,float) else str(value)
    return m.old.md_table(frame.columns,[[fmt(v) for v in row] for row in frame.iter_rows()])


def main(run):
    m.verify(run)
    manifest = json.loads((run/'run_manifest.json').read_text())
    master = pl.read_parquet(run/'master.parquet')
    eligible = master.filter('p2_eligible')
    pack = run/'submission'
    means = pl.read_csv(pack/'model_means.csv')
    scores = pl.read_csv(pack/'fold_metrics.csv')
    paired = pl.read_csv(pack/'paired_fold_differences.csv')
    desc = pl.read_csv(pack/'descriptive_summary.csv')
    components = json.loads((pack/'descriptive_components.json').read_text())
    # Independently reconcile packaged summaries with the saved row predictions.
    predictions = pl.read_csv(run/'predictions.csv')
    pooled = pl.read_csv(pack/'pooled_oof_metrics.csv')
    for name in m.MODEL_BLOCKS:
        rows = predictions.filter(pl.col('model') == name)
        actual = m.metrics(rows['top10'].to_numpy(),rows['probability'].to_numpy())
        for key,value in actual.items():
            assert np.isclose(value,pooled.filter(pl.col('model')==name)[key][0])
            assert np.isclose(scores.filter(pl.col('model')==name)[key].mean(),means.filter(pl.col('model')==name)[key][0])
    sample_csv = pl.read_csv(pack/'cleaned_sample.csv')
    sample_parquet = pl.read_parquet(pack/'cleaned_sample.parquet')
    assert sample_csv.height == sample_parquet.height == manifest['sample_n']
    for col in ['lyrics','lyrics_clean','p2_lyrics_original','p2_lyrics_revised']:
        assert sample_csv[col].to_list() == sample_parquet[col].to_list()
    for row in desc.iter_rows(named=True):
        values = eligible.filter(pl.col('top10') == row['top10'])[row['feature']].drop_nulls().to_numpy()
        assert len(values)==row['n'] and np.isclose(np.median(values),row['median']) and np.isclose(np.mean(values),row['mean'])
    def save(name,text):
        (pack/name).write_text(text.strip()+'\n',encoding='utf-8')
    current = {r['model']:r for r in means.to_dicts()}
    decisions = master.group_by('p2_decision').len().sort('p2_decision')
    language_decisions = master.group_by('p2_eligible','p2_decision').len().sort('p2_eligible','p2_decision')
    length_rows = []
    for label,col in [('Stage 10 cleaned','lyric_words_after'),('Stage 11 corrected','p2_words_before'),('Preprocessing II','p2_word_count')]:
        s=master[col]
        length_rows.append(dict(version=label,n=len(s),mean=s.mean(),median=s.median(),minimum=s.min(),p95=s.quantile(.95,interpolation='linear'),maximum=s.max()))
    flags = [c for c in ['lyric_encoding_review','lyric_mixed_script_token_review','lyric_invisible_review','lyric_web_metadata_review',
                          'lyric_residual_brackets','lyric_language_uncertain','lyric_language_mixed_candidate','lyric_language_short','any_missing_audio_value']]
    flag_table = pl.DataFrame([dict(historical_flag=c,master=int(master[c].sum()),eligible=int(eligible[c].sum())) for c in flags])
    dimensions = {'audio':10,'simple':3,'nmf':10,'svd':10}
    capacity = pl.DataFrame([dict(model=name,predictors=sum(dimensions[b] for b in blocks),
        coefficients=sum(dimensions[b] for b in blocks),intercepts=int(bool(blocks))) for name,blocks in m.MODEL_BLOCKS.items()])
    save('01_preprocessing_summary.md',f'''# Preprocessing II: decisions and final population
Prepared 15 November 2026. Draft for project-member review before submission.

All **{master.height:,} records** remain in the 2000–2022 matched master corpus. The primary **automated English-labelled sample** remains exactly **{eligible.height:,} records**, including **{manifest['positive']:,} Top-10** and **{manifest['negative']:,} other charting songs** ({manifest['prevalence']:.2%} positive). The other 161 records remain in the master but outside primary modelling. No sample exclusions were introduced; all eligible records are usable in every model and descriptive calculation.

## What was already done

Existing stages conservatively matched source song–artist records, selected lyric representatives and audio medians, froze the 2000–2022 analysis period, normalized Unicode/whitespace, removed supported section-label and music-note-only lines, and saved language/quality diagnostics. Stage 11 preserved all source text and shortened one supported full-text repetition. Stage 12 fitted the historical audio/NMF comparison. Those scripts, original inputs and reports remain unchanged. The README's former Phase 2A status was stale, not evidence that matching needed to be repeated.

## What changed since the previous presentation

1. Replaced the manual-evidence gate for substantial exact whole-text repetition with the approved conservative automatic normalization. The thresholds remain at least 12 nonblank lines, 100 whitespace tokens and six distinct normalized lines in the smallest retained unit. They are operational guards, not measured detection accuracy.
2. Repaired single-prefix contraction tokenization and normalized four common apostrophe variants for tokenization and sentiment. No lemmatization or new stopword list was introduced.
3. Added one narrow recoverable encoding repair: the observed Latin-1-decoded UTF-8 sequence U+00E2 U+0080 U+0098 becomes U+2018. It affects {manifest['encoding_repaired_records']} record and {manifest['encoding_replacements']} occurrences. The lossy sequence in record 1919 remains flagged; its missing character cannot be reconstructed safely.
4. Added fixed log length, recurring-line fraction and lexicon polarity features; reran the nine prespecified model families. SVD is the one alternative representation, with ten components like NMF.

## Repetition accounting

{table(decisions)}

All **955 historical flags** reconcile to **947 newly normalized**, **one previous correction preserved**, and **seven retained by policy**. There are no pending manual-review blockers. Unflagged records number 5,591. Normalization does not establish that every repeated text was an extraction error. The seven small/low-diversity units remain unchanged; individual choruses and repeated lines inside retained blocks remain.

{table(language_decisions)}

Detection compares the complete nonblank line sequence after casefolding and collapsing within-line whitespace. Blank lines are ignored for comparison; punctuation is retained. Only a period that tiles the whole sequence qualifies. The original first block is retained with its case, punctuation, internal spacing and blank lines; newline separators at its end are removed. Unlike the earlier strict case/layout comparison, detection can normalize case/spacing/layout variants of the same complete normalized block. This is documented and tested. No fuzzy matching, near-verse deletion or global line deduplication occurs.

Revisions remove **{manifest['words_removed_since_stage11']:,} whitespace tokens** relative to Stage 11, in addition to its historical 320-token correction. Text changes since Stage 11 affect {manifest['changed_since_stage11']} records (including the encoding repair; categories may overlap). Whole-text correction and encoding repair are logged separately. Source columns, raw lyrics, Stage 10 text and Stage 11 text remain intact. Original/revised full text and per-record decisions are saved privately.

{table(pl.DataFrame(length_rows))}

For fixed vocabulary and IDF, exact duplication multiplies all unigram linear term counts by the same constant; L2 normalization cancels it. Thus normalized linear unigram TF-IDF can remain unchanged while word counts and descriptive measures change. This statement does not apply universally to sublinear TF, truncated inputs or differently fitted vocabularies. New model differences also include the tokenizer and encoding changes, so they cannot identify a repetition-only effect.

## Language, quality and usability

Eligibility is frozen from the existing `lyric_language == 'en'` labels and checked against the historical prediction IDs. The saved `eligible_ids.csv` is the authoritative ordered list. No detector rerun, new confidence threshold, translation or line deletion occurred. Detector scores are not calibrated probabilities of correctness. Low-confidence and possibly mixed-language records remain eligible, including the previously observed Korean/English example. Separate emotion categories were not measured.

{table(flag_table)}

Historical flags are preserved even after a supported repair. The invisible-character flag belongs to the encoding-repaired record; the web-metadata flag is the title-related `www.memory` case and is retained. Mixed-script tokens, residual brackets, source matching/consolidation uncertainty and near-duplicate candidates remain explicit limitations. No raw matching was reopened, records added or period expanded. No missing/blank lyric or nonfinite audio measurement prevents primary analysis. There is no comprehensive manual validation of transcription, language or matching.

## Authoritative input and audit

Source: `{manifest['source_path']}`

SHA-256: `{manifest['source_sha256']}`

Grain: one existing Billboard song–artist record; {master[ m.ID ].n_unique():,} unique, nonnull `billboard_source_row` IDs. Master Top-10 count: {int(master['top10'].sum())}; other master records: {master.height-int(master['top10'].sum())}. Target is observed `peak_rank <= 10`, checked against `top10`; no rank-11–15 gap exclusion.

`../decision_audit.csv`, `../master.parquet`, `../eligible_ids.csv` and `../run_manifest.json` preserve the complete audit. No raw input, previous report or historical prediction file was overwritten.
''')
    save('02_methods_and_reproduction.md',f'''# Methods and reproduction

## Fixed measurements

Word count is the number of whitespace-delimited tokens, including punctuation-only tokens. Raw count is retained for description; the predictor is `log(1 + count)`. Recurring-line fraction is `(nonblank lines - distinct normalized nonblank lines) / nonblank lines`, after whole-text normalization. Lines are casefolded and whitespace-collapsed, punctuation retained. It measures legitimate choruses as well as other recurring lines; the original extraction flag is never a predictor. Empty text gives zero word count but missing repetition and polarity, not fabricated zeros. There are no empty eligible texts in this run.

Sentiment uses **VADER 3.3.2**, a fixed English lexicon/rule system selected before scoring model performance. It offers inexpensive reproducible exploratory polarity with negation, punctuation and informal-text rules. Each nonblank natural-text line is scored with `compound`; song polarity is the mean weighted by each line's whitespace word count. Every line is scored, without truncation or a transformer length cap. This reduces whole-song compound saturation, but line boundaries lose cross-line context and word weighting is a project aggregation choice, not a validated song-level sentiment estimator. Case/punctuation/negation remain; only common apostrophe variants are normalized for scoring. TF-IDF tokens are not sentiment input.

Any failed or nonfinite line makes the song score missing with a failure status; neutral successful measurements remain valid zero. All {manifest['master_n']:,} master scores completed, including {manifest['eligible_n']:,} primary scores. Non-English-labelled scores are diagnostic only and are not interpreted as valid non-English sentiment. Mixed-language primary records may have poorly measured polarity. Slang, irony, profanity, narrative perspective, metaphor and cross-line negation are limitations. Polarity is neither emotional-category annotation nor lyrical quality. Scoring rules were not revised based on held-out results.

Primary source: [VADER authors' documentation](https://github.com/cjhutto/vaderSentiment), consulted 15 November 2026. Cite Hutto & Gilbert (2014), *VADER: A Parsimonious Rule-based Model for Sentiment Analysis of Social Media Text*, ICWSM. Package and lexicon hashes are recorded in the private run manifest. The line-weighted aggregation is our documented adaptation, not a claim from that paper.

## Text representation and classifier

The historical regex required two word characters before a contraction, yielding `ll` and `ve` from `I'll` and `I've`. Revised outputs are `i'll`, `i've`, `can't`, `don't`, including curly-apostrophe input. Standalone one-character tokens remain omitted; `I'd` is retained without guessing its expansion. Existing bare `ll`/`ve` tokens are not blindly deleted.

TF-IDF retains word unigrams, min_df=5, max_df=0.95, no max_features cap, linear term counts, smooth IDF, L2 normalization and the same sklearn stopword list with negators removed. Lowercasing now occurs explicitly in the apostrophe-normalizing preprocessor. No lemmatization or extra vocabulary filtering. See `../configuration.json` for exact token regex, stopwords and all settings.

NMF uses ten nonnegative components, NNDSVDa initialization, coordinate descent, Frobenius loss, tolerance 1e-4, no added factor penalty, seed 42 and max_iter 500 with one convergence-only retry at 1,000. Its additive nonnegative weights support a provisional lexical interpretation and preserve the historical reference.

Truncated SVD/latent semantic analysis uses the same sparse TF-IDF and ten components, randomized algorithm, seed 42, seven power iterations, ten oversamples and automatic power normalization. Sparse TF-IDF motivates SVD because it does not center the matrix; ordinary PCA centers and can destroy sparsity. This is not centered PCA. SVD loadings can be positive or negative; sign orientation is arbitrary across separate fits. See the [scikit-learn TruncatedSVD documentation](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.TruncatedSVD.html).

Regularized logistic regression gives a compact, interpretable binary prediction baseline without a broad algorithm search. Every numerical input uses training-only median imputation (zero fallback for an all-missing training column) and standard scaling. Logistic settings: L2 (`l1_ratio=0`), C=1, no class weighting, lbfgs, tolerance 1e-4, seed 42, 2,000 iterations; retry at 4,000 only on a convergence warning. None of the settings or threshold is selected from held-out scores. Final nonconverged classifier fits: {manifest['final_classifier_nonconvergence']}. Per-attempt NMF/classifier warnings and iterations are saved in the run logs.

The ten audio fields are: {', '.join(m.old.AUDIO)}. They are source medians; duration is milliseconds, tempo BPM and loudness dB. No chart history, artist ID, target proxy or quality flag enters any predictor matrix.

## Shared validation and capacity

Five historical grouped folds are reused unchanged after checking nonblank exact normalized revised-text links: {manifest['new_exact_links']} new links; repartitioned={manifest['repartitioned']}. Groups retain complete normalized artist credits, existing duplicate links and the documented cover candidate. There are {manifest['group_count']:,} eligible groups; sizes min/median/max {manifest['group_sizes']}. Solo and collaborative credits can still share an individual performer across folds. This is not fully unseen-artist evaluation and not a future-year forecast. No artist names are split on punctuation.

Each fold learns vocabulary, IDF, NMF/SVD, imputation, scaling and regression exclusively from training songs. The same training-fitted representations feed all relevant families. Deterministic cleaning and external fixed sentiment are allowed before splitting. All-data component fits are descriptive only. A saved historical validation set has already informed project development; repeated use limits claims of final unbiased generalization.

{table(capacity)}

Dummy has no regression coefficients and predicts the training prevalence. All other binary classifiers have one coefficient per predictor plus one intercept. Equal component counts control one aspect of dimensionality, not full pipeline capacity: factor constraints, fitted vocabulary, parameter counts and predictor correlations differ. More predictors do not guarantee better held-out performance.

## Metrics

Primary metric is **average precision (AP)**, not trapezoidal PR-AUC. Also report ROC-AUC and precision, recall, F1 and predicted-positive counts at fixed probability 0.5, with zero_division=0. Equal-fold means are primary; pooled OOF metrics are separately labelled. The 0.5 threshold yields low recall under 15.41% prevalence. It was not optimized. Paired fold differences are descriptive; overlapping training sets invalidate an ordinary independent-sample test on these five scores. No significance or causal claim is made.

## Reproduction

From the repository root in PowerShell:

```powershell
uv sync --locked
uv run python -m unittest discover -s tests -v
uv run python src/14_preprocessing_ii_analysis.py --output data/processed/preprocessing_ii_reproduction
uv run python src/15_package_preprocessing_ii.py --run data/processed/preprocessing_ii_reproduction
uv run python src/14_preprocessing_ii_analysis.py --verify data/processed/preprocessing_ii_reproduction
```

Use a new output directory: existing runs are never overwritten by Stage 14. The existing Stage 11 input and Stage 12 saved predictions/manifest must be present. `--source` supports an explicit source path, while historical predictions remain under the project root. The delivered code directory mirrors the tested relative paths and includes the README build metadata; to reproduce from that copy, place the private historical inputs under its `data/processed` directory. The authoritative environment is this repository with the locked dependencies. Do not run upstream scripts just to reproduce this submission.

Software: {json.dumps(manifest['software'],sort_keys=True)}. Python: {manifest['python'].split()[0]}. Run manifest records exact source, configuration, lexicon and code hashes. `code_manifest.json` identifies submitted file bytes. No upload or network scoring is required after dependencies are installed.
''')
    # Tables deliberately separate equal-fold averages from pooled threshold counts.
    delta_summary = paired.group_by('comparison',maintain_order=True).agg(pl.col('ap').mean().alias('mean_AP_difference'),pl.col('ap').min().alias('minimum_fold_difference'),pl.col('ap').max().alias('maximum_fold_difference'))
    fold_table = pl.DataFrame(manifest['fold_details']).select('fold','train_n','train_positive','test_n','test_positive','train_groups','test_groups','vocabulary','empty_test')
    comp_rows = [dict(method=c['method'],component=c['component'],positive=', '.join(c['positive_terms'][:6]),negative=', '.join(c['negative_terms'][:6]) or '(none)',interpretation=c['provisional_label']) for c in components]
    save('04_analysis_update.md',f'''# Do lyric-derived features add predictive information?
Exploratory 2000–2022 matched Billboard corpus update · 15 November 2026

## Main findings

Adding length, recurring-line repetition and polarity to audio increases equal-fold mean AP from **{current['Audio']['ap']:.4f}** to **{current['Audio + simple lyrics']['ap']:.4f}**. The prespecified audio + simple lyrics + NMF family reaches **{current['Audio + simple lyrics + NMF']['ap']:.4f}**, compared with **{current['Audio + NMF']['ap']:.4f}** for audio + NMF. All four priority AP differences are positive in each of the five common folds. This supports incremental predictive information in this selected corpus, not causality, significance, better lyrical quality, or an isolated benefit from sentiment alone.

The primary sample has 6,385 songs: 984 Top-10 and 5,401 others. The dummy AP is {current['Dummy']['ap']:.4f}. Simple lyrics alone outperform audio on mean AP here; NMF versus SVD differences are small and do not justify a general superiority claim. The final NMF family was specified before these results, not selected as a winner afterward.

![All model families: fold AP and equal-fold mean](model_ap.png)

## Actual model scores

{table(means)}

Above: all columns are equal-fold means, including `predicted_positive` (mean count per fold). Exact per-fold counts appear below; pooled counts and pooled metrics are in `pooled_oof_metrics.csv`. Averaged precision is not the same as pooled precision, particularly when some folds predict no positives. Low recall at 0.5 is a major practical limitation; these results are not a ready-to-use hit-song classifier.

{table(delta_summary)}

{table(paired)}

## Sample and fold accounting

{table(fold_table)}

All models use the same IDs and folds. Group overlap is zero, but individual performers may still cross folds through differing complete credits. No new exact revised-text links were found; historical folds therefore remain directly comparable. No eligible records were dropped for feature computation. Missing/failed sentiment measurements: 0/0 among 6,385 eligible songs (and 0/0 among all 6,546 master records). Valid neutral-zero scores in the eligible sample: {eligible.filter(pl.col('p2_sentiment')==0).height}.

## Lyric distributions by outcome

![Cumulative distributions with sample sizes](lyric_distributions.png)

Top-10 lyrics have median length 431 whitespace words versus 357 for other songs, and median recurring-line fraction 0.3652 versus 0.3265. Their polarity medians are 0.0632 versus 0.0568, with substantial overlap. Length/repetition differences are descriptive associations within this matched corpus; artist, era, style and source transcription can confound them. The nine families assess the three simple features jointly, so no individual-feature contribution is established.

{table(desc)}

ECDFs show full distributions and group sizes; length has a labelled logarithmic axis. Quantiles in the table use linear interpolation. The absence of scoring failures is not evidence that sentiment is accurate.

## Provisional component interpretation

{table(pl.DataFrame(comp_rows))}

Five of ten descriptive NMF components remain led by vocal syllables/interjections: oh, ooh, na, la and yeah. The tokenizer repair did not remove these stylistic signals. Love/attachment and affectionate-address labels are tentative lexical summaries; other components capture general language, negation/desire and profanity/colloquial diction. Profanity is not a genre label. Representative examples were inspected privately for the oh, na, love and baby components; the examples support recurring vocabulary, not coherent semantic topics for every component. Full text remains in `../private_component_examples.json`.

SVD component 1 has no negative loadings in this fit; its smallest positive terms must not be called a negative pole. Other SVD components show signed contrasts such as vocal/affectionate language against profanity/colloquial language. Both poles are provided in `descriptive_components.json` with actual loadings. Sign direction and component numbers are fit-specific. Do not align historical, descriptive and fold-specific component numbers without an explicit alignment.

One exploratory descriptive comparison: NMF's oh-led component has mean weight {components[1]['mean_top10']:.4f} in Top-10 songs versus {components[1]['mean_other']:.4f} in other songs. These are unnormalized component scores, not topic percentages; the comparison was selected for illustration and is not a significance test.

## Historical comparability and limits

Historical audio AP was 0.2334 and audio + NMF AP 0.2527; the new values are {current['Audio']['ap']:.4f} and {current['Audio + NMF']['ap']:.4f}. Audio agrees because its input and folds are unchanged. Text results include changed preprocessing and tokenization; they cannot isolate an effect of one correction. No new partition was required. All data-driven transformations remain training-only, but repeated inspection of these folds across project stages means this is a development update, not an untouched final external test.

The corpus conditions on having charted and been matched to usable source data. Results do not generalize automatically to all released songs. Complete-credit grouping, possible undetected covers, uncertain matching/transcription, automated language labels, lyric sentiment domain mismatch and temporal shifts remain limitations. The polarity method can score breakup language positively and miss expressive slang; see the private sanity-check note. No comprehensive manual validation or causal identification was performed. Optional random-noise and stricter-language sensitivity analyses were deferred to keep the mandatory comparison focused.

## Complete fold metrics

{table(scores)}

Evidence: saved private predictions are independently reloaded to recompute each metric; aggregate CSVs, configuration, source/code hashes and convergence logs are in this run. See `02_methods_and_reproduction.md` for the methodological rationale and primary sentiment documentation.
''')
    save('03_cleaned_sample_guide.md',f'''# Cleaned-data sample guide

`cleaned_sample.csv` and `cleaned_sample.parquet` contain the same **{manifest['sample_n']} complete records**, selected deterministically for illustration, not as a representative corpus sample. CSV text fields are quoted and may contain embedded newlines. The Parquet copy preserves types. No lyric field is truncated or presented as an excerpt.

Selection: up to three smallest stable IDs per repetition decision; up to two smallest IDs for each of historical language uncertainty, mixed-language, short-language, encoding and previous-correction flags; two smallest non-English-labelled IDs; eight uniformly sampled master IDs with NumPy seed 42. Take the union and preserve master order. Selection is independent of model results. The sample's class balance is not a prevalence estimate.

| Fields | Meaning |
| --- | --- |
| billboard_source_row; Song; Artist | Stable record ID and original metadata; never predictors |
| lyrics | Complete untouched source lyric text |
| lyrics_clean | Complete Stage 10 cleaned text |
| p2_lyrics_original | Complete Stage 11 text entering this update |
| p2_lyrics_revised | Complete text after this update |
| lyric_language; lyric_language_score | Historical label and uncalibrated detector score |
| lyric_language_uncertain; lyric_language_mixed_candidate; lyric_encoding_review | Preserved historical flags, not manual verification |
| lyric_full_block_repeats; full_block_dedup_status | Historical repeat flag and evidence-gated decision |
| p2_decision; p2_reason; p2_repeat_count | New structural decision, rationale and multiplicity in Stage 11 input; prior-corrected record has repeat count 1 here and historical count 2 |
| p2_words_before; p2_word_count; p2_words_removed | Whitespace words before/after and difference |
| p2_text_changed; p2_encoding_replacements | Any text change since Stage 11; separate exact encoding replacement count |
| p2_eligible | Frozen historical English-label eligibility |
| p2_log_word_count; p2_line_repetition | Primary length predictor; within-text recurring-line fraction |
| p2_sentiment; p2_sentiment_status | Weighted-line VADER polarity; successful zero is distinct from missing/failed |

The full audit has one row per master record and is separate from this selected sample. Complete lyric files and row-level outputs are Git-ignored. Project members must inspect the complete sample privately before deciding what to upload.
''')
    save('05_presentation_12_minutes.md','''# Twelve-minute presentation outline

Total: **720 seconds = 12:00**. One speaker can deliver it, or split after section 5.

| Elapsed time | Duration | Content and visual |
| --- | --- | --- |
| 0:00–0:30 | 0:30 | Research question: incremental lyric information beyond audio among charting songs. Avoid claims about all released songs. |
| 0:30–1:30 | 1:00 | Actual sample: 6,546 master, 6,385 automated English-labelled, 984 Top-10. Frozen IDs; 161 retained outside modelling. |
| 1:30–3:10 | 1:40 | Repetition decisions: 947 normalized, one previous correction preserved, seven retained by policy. Show a personally reviewed private before/after sample. Explain structural thresholds, within-block chorus preservation and reversibility. |
| 3:10–4:10 | 1:00 | Tokenizer repair and narrow encoding repair. Show synthetic I'll / I've / can't / don't examples. Explain TF-IDF invariance under exact uniform repetition. |
| 4:10–5:40 | 1:30 | Three simple features and VADER limitations. Use lyric_distributions.png; length and repetition differ more visibly than polarity. No emotion categories or quality measurement. |
| 5:40–7:20 | 1:40 | Shared five grouped folds and training-only fitting. Explain complete-credit limitation, fixed logistic settings, NMF versus sparse uncentered SVD and predictor dimensions. |
| 7:20–8:40 | 1:20 | Main results using model_ap.png: audio 0.2334; audio + simple 0.2637; audio + NMF 0.2540; audio + SVD 0.2526; full prespecified family 0.2870. AP is average precision. |
| 8:40–10:00 | 1:20 | Four paired AP comparisons are positive in all folds, without a significance claim. Mention very low recall at 0.5 and distinguish fold means from pooled counts. |
| 10:00–11:00 | 1:00 | Component interpretation: five vocal-syllable-led NMF components remain. Show selected top terms, inspect signed SVD poles, and avoid topic-percentage claims. |
| 11:00–12:00 | 1:00 | Conclusion and limitations: incremental prediction in this corpus; no causality or lyrical-quality claim. Matching/language/sentiment/grouping uncertainty and reused development folds. State human review before upload. |

Personally review before presenting: the cleaned sample and seven retained-policy cases; the one encoding repair; the two figures and every quoted metric; sentiment sanity examples (especially breakup-positive and neutral slang cases); representative songs supporting component labels; sample selection and the limits of performer grouping. Confirm both speakers can explain each transformation and why it remains inside the training fold where required. Do not display complete copyrighted lyrics publicly.
''')
    save('06_review_and_handover.md',f'''# Review and local handover

The official requested pieces are present: preprocessing summary, commented tested code, and cleaned-data sample. Analysis tables/figures and a 12-minute outline are included. This is an AI-assisted draft requiring project-member validation; nothing has been uploaded to Canvas.

## Human review before submission

- Read `01_preprocessing_summary.md`; approve the automatic structural rule and distinguish normalized texts from verified extraction errors.
- Open the 26-record private cleaned sample and inspect the encoding repair, preserved choruses and retained-policy cases.
- Check `04_analysis_update.md` and the figures against CSVs; use AP terminology and disclose low threshold recall.
- Review the sentiment and component examples privately; do not claim manual corpus validation, emotion measurement or causal effects.
- Confirm the final explanatory wording, names, course requirements and which private sample files may be uploaded; then submit manually.

## Code and evidence

`code/` mirrors the authoritative tested sources and dependency lock. `code_manifest.json` lists SHA-256 values. The analysis imports only pure helper definitions from preserved Stage 12 code; it does not execute or overwrite that historical stage. `../run_manifest.json` records the executed analysis version, input hashes, package versions and configuration. `../verification.json` records final checks. `../private_sanity_review.md` records bounded diagnostic inspection, not validation accuracy.

Branch: `preprocessing-ii-update`, based on `1e76786` (fetched origin/master). The initial worktree was clean, no local-only commits existed, and only remote master was accessible. No AGENTS.md was found in the repository or its parent directories. No worktree was needed because there was no conflicting work to protect; ignored inputs remain in their existing location. Default branch and historical results were not modified. No merge, push, stash or reset occurred.

Optional random-noise and stricter-language sensitivity runs are deferred. Mandatory nine-family comparison, sentiment, descriptive analysis, audit, sample and presentation outline are complete. Remaining uncertainty is methodological and data-quality uncertainty, not a missing model run.
''')
    save('README.md','''# Local Preprocessing II submission

Start with [preprocessing summary](01_preprocessing_summary.md), then [analysis update](04_analysis_update.md).

- [Methods, dependencies and reproduction](02_methods_and_reproduction.md)
- [Complete cleaned-data sample guide](03_cleaned_sample_guide.md) and `cleaned_sample.csv` / `.parquet`
- [Twelve-minute outline](05_presentation_12_minutes.md)
- [Human review and handover](06_review_and_handover.md)
- `code/` and `code_manifest.json`: authoritative submission code copies
- Metric CSVs, descriptive component JSON and two PNG figures: supporting evidence

This folder contains complete private lyrics. Keep it out of Git and review it before any manual Canvas upload. The parent run directory holds the full private master, row-level audit, predictions, folds, configuration and provenance.
''')
    # Complete reproduction pack, including packaging code and README build metadata.
    hashes = json.loads((pack/'code_manifest.json').read_text())
    for rel in ['src/15_package_preprocessing_ii.py','README.md']:
        dst = pack/'code'/rel
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/rel,dst)
        hashes[rel] = m.old.sha(ROOT/rel)
    m.write_json(pack/'code_manifest.json',hashes)
    # Only aggregate, lyric-free reports/figures are copied to tracked paths.
    public = ROOT/'reports/preprocessing_ii_20261115'
    public.mkdir(exist_ok=True)
    for name in ['01_preprocessing_summary.md','02_methods_and_reproduction.md','04_analysis_update.md','05_presentation_12_minutes.md',
                 'model_ap.png','lyric_distributions.png','model_means.csv','fold_metrics.csv','pooled_oof_metrics.csv','paired_fold_differences.csv','descriptive_summary.csv']:
        shutil.copy2(pack/name,public/name)
    # Markdown relative links are checked after writing; public copies point readers
    # to the private submission for intentionally unavailable row-level evidence.
    for name in ['model_ap.png','lyric_distributions.png']:
        assert (pack/name).is_file()
    check = subprocess.run(['git','check-ignore',str(pack/'cleaned_sample.csv'),str(run/'predictions.csv')],cwd=ROOT,capture_output=True,text=True)
    assert check.returncode == 0 and len(check.stdout.strip().splitlines())==2
    staged = subprocess.check_output(['git','diff','--cached','--name-only'],cwd=ROOT,text=True).splitlines()
    assert not any(p.startswith('data/') or 'cleaned_sample' in p for p in staged)
    m.write_json(run/'verification.json',dict(saved_output_checks='passed',private_outputs_ignored=True,
        staged_private_data=False,code_copy_hashes_checked=True,image_links_checked=True))
    for rel,digest in hashes.items():
        assert m.old.sha(pack/'code'/rel)==digest==m.old.sha(ROOT/rel)
    print(f'Packaged: {pack}',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,default=ROOT/'data/processed/preprocessing_ii_20261115_v2')
    main(parser.parse_args().run.resolve())
