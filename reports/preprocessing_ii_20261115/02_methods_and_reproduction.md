# Methods and reproduction

## Fixed measurements

Word count is the number of whitespace-delimited tokens, including punctuation-only tokens. Raw count is retained for description; the predictor is `log(1 + count)`. Recurring-line fraction is `(nonblank lines - distinct normalized nonblank lines) / nonblank lines`, after whole-text normalization. Lines are casefolded and whitespace-collapsed, punctuation retained. It measures legitimate choruses as well as other recurring lines; the original extraction flag is never a predictor. Empty text gives zero word count but missing repetition and polarity, not fabricated zeros. There are no empty eligible texts in this run.

Sentiment uses **VADER 3.3.2**, a fixed English lexicon/rule system selected before scoring model performance. It offers inexpensive reproducible exploratory polarity with negation, punctuation and informal-text rules. Each nonblank natural-text line is scored with `compound`; song polarity is the mean weighted by each line's whitespace word count. Every line is scored, without truncation or a transformer length cap. This reduces whole-song compound saturation, but line boundaries lose cross-line context and word weighting is a project aggregation choice, not a validated song-level sentiment estimator. Case/punctuation/negation remain; only common apostrophe variants are normalized for scoring. TF-IDF tokens are not sentiment input.

Any failed or nonfinite line makes the song score missing with a failure status; neutral successful measurements remain valid zero. All 6,546 master scores completed, including 6,385 primary scores. Non-English-labelled scores are diagnostic only and are not interpreted as valid non-English sentiment. Mixed-language primary records may have poorly measured polarity. Slang, irony, profanity, narrative perspective, metaphor and cross-line negation are limitations. Polarity is neither emotional-category annotation nor lyrical quality. Scoring rules were not revised based on held-out results.

Primary source: [VADER authors' documentation](https://github.com/cjhutto/vaderSentiment), consulted 15 November 2026. Cite Hutto & Gilbert (2014), *VADER: A Parsimonious Rule-based Model for Sentiment Analysis of Social Media Text*, ICWSM. Package and lexicon hashes are recorded in the private run manifest. The line-weighted aggregation is our documented adaptation, not a claim from that paper.

## Text representation and classifier

The historical regex required two word characters before a contraction, yielding `ll` and `ve` from `I'll` and `I've`. Revised outputs are `i'll`, `i've`, `can't`, `don't`, including curly-apostrophe input. Standalone one-character tokens remain omitted; `I'd` is retained without guessing its expansion. Existing bare `ll`/`ve` tokens are not blindly deleted.

TF-IDF retains word unigrams, min_df=5, max_df=0.95, no max_features cap, linear term counts, smooth IDF, L2 normalization and the same sklearn stopword list with negators removed. Lowercasing now occurs explicitly in the apostrophe-normalizing preprocessor. No lemmatization or extra vocabulary filtering. See `../configuration.json` for exact token regex, stopwords and all settings.

NMF uses ten nonnegative components, NNDSVDa initialization, coordinate descent, Frobenius loss, tolerance 1e-4, no added factor penalty, seed 42 and max_iter 500 with one convergence-only retry at 1,000. Its additive nonnegative weights support a provisional lexical interpretation and preserve the historical reference.

Truncated SVD/latent semantic analysis uses the same sparse TF-IDF and ten components, randomized algorithm, seed 42, seven power iterations, ten oversamples and automatic power normalization. Sparse TF-IDF motivates SVD because it does not center the matrix; ordinary PCA centers and can destroy sparsity. This is not centered PCA. SVD loadings can be positive or negative; sign orientation is arbitrary across separate fits. See the [scikit-learn TruncatedSVD documentation](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.TruncatedSVD.html).

Regularized logistic regression gives a compact, interpretable binary prediction baseline without a broad algorithm search. Every numerical input uses training-only median imputation (zero fallback for an all-missing training column) and standard scaling. Logistic settings: L2 (`l1_ratio=0`), C=1, no class weighting, lbfgs, tolerance 1e-4, seed 42, 2,000 iterations; retry at 4,000 only on a convergence warning. None of the settings or threshold is selected from held-out scores. Final nonconverged classifier fits: 0. Per-attempt NMF/classifier warnings and iterations are saved in the run logs.

The ten audio fields are: danceability_median, energy_median, loudness_median, speechiness_median, acousticness_median, instrumentalness_median, liveness_median, valence_median, tempo_median, duration_ms_median. They are source medians; duration is milliseconds, tempo BPM and loudness dB. No chart history, artist ID, target proxy or quality flag enters any predictor matrix.

## Shared validation and capacity

Five historical grouped folds are reused unchanged after checking nonblank exact normalized revised-text links: 0 new links; repartitioned=False. Groups retain complete normalized artist credits, existing duplicate links and the documented cover candidate. There are 2,159 eligible groups; sizes min/median/max {'min': 1, 'median': 1.0, 'max': 134}. Solo and collaborative credits can still share an individual performer across folds. This is not fully unseen-artist evaluation and not a future-year forecast. No artist names are split on punctuation.

Each fold learns vocabulary, IDF, NMF/SVD, imputation, scaling and regression exclusively from training songs. The same training-fitted representations feed all relevant families. Deterministic cleaning and external fixed sentiment are allowed before splitting. All-data component fits are descriptive only. A saved historical validation set has already informed project development; repeated use limits claims of final unbiased generalization.

| model | predictors | coefficients | intercepts |
| --- | --- | --- | --- |
| Dummy | 0 | 0 | 0 |
| Audio | 10 | 10 | 1 |
| Simple lyrics | 3 | 3 | 1 |
| Audio + simple lyrics | 13 | 13 | 1 |
| NMF | 10 | 10 | 1 |
| Audio + NMF | 20 | 20 | 1 |
| SVD | 10 | 10 | 1 |
| Audio + SVD | 20 | 20 | 1 |
| Audio + simple lyrics + NMF | 23 | 23 | 1 |

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

Software: {"langdetect": "1.0.9", "matplotlib": "3.11.2", "numpy": "2.5.4", "polars": "2.0.0", "scikit-learn": "1.9.1", "scipy": "1.18.1", "vaderSentiment": "3.3.2"}. Python: 3.12.14. Run manifest records exact source, configuration, lexicon and code hashes. `code_manifest.json` identifies submitted file bytes. No upload or network scoring is required after dependencies are installed.
