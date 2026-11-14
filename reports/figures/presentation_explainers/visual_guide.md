# Presentation visual guide

All images are 1920×1080 PNG plus editable-text SVG, in this directory. Run `python src/13_presentation_explainers.py` using the existing project environment to reproduce them. No upstream cleaning, review, integration or project model fitting is run. Existing inputs and results are read-only.

For a 12-minute main presentation, use 01, 02, 03 and 06 (sample → representation → evaluation → findings). Keep 02b, 04 and 05 as appendix material.

## 01_sample_selection

**Actual data.** Which records enter the analysis?

**Read it:** Arrows show selection and outcome branches; boxes contain record counts, not proportional areas.

**For a beginner:** A language detector supplies a provisional label. Retained songs are divided by their observed best chart rank.

**Say:** “We started with 6,546 prepared records and retained 6,385 under automated English screening. Of these, 984 reached the Top 10 and 5,401 did not.”

**Limitation:** The detector can retain multilingual songs; this is not verified English-only text.

**Sources:** `data/processed/billboard_lyrics_corrected_2000_2022.parquet`; `data/processed/stage12_modelling/run_manifest.json`; `reports/topics_and_top10_prediction.md`.

## 02_lyrics_to_numbers

**Invented teaching example, with actual calculations.** How is text encoded?

**Read it:** Rows are invented songs; columns are words. Left cells are counts (0–2); right cells are TF-IDF weights (0–1); each matrix has its own color scale.

**For a beginner:** Document frequency counts how many documents contain a word. Linear TF uses the count without logarithmic compression; smoothed IDF is 1 + ln((1+n)/(1+df)); L2 normalization divides by the square root of the sum of squared weights. The common word “day” receives less IDF weight. Rows have unit length, not a sum of one.

**Say:** “We first count each word in each song. TF-IDF then reduces the relative influence of words found across many songs and normalizes each song’s vector.”

**Limitation:** This toy uses no stopwords and retains every word (min_df=1, max_df=1); the project uses min_df=5, max_df=0.95 and a fixed stopword list. Word order is lost.

**Sources:** `src/13_presentation_explainers.py` (invented text and explicit NumPy calculation); `src/12_topics_and_top10_prediction.py` (project representation settings).

## 02b_nmf_representation

**Conceptual schematic.** What does NMF change?

**Read it:** Boxes show matrix shapes; the arrow reduces many word columns to ten component-weight columns while preserving song rows. No numerical weights are illustrated.

**For a beginner:** NMF approximates the word matrix with non-negative song weights and component word patterns. A song can have several nonzero weights, without those weights summing to one.

**Say:** “NMF summarizes the large word table using ten component weights per song. These components can capture repeated vocal sounds as well as recognizable vocabulary themes.”

**Limitation:** A component need not be a coherent theme; its weight is not a probability.

**Sources:** `src/12_topics_and_top10_prediction.py`; `reports/topics_and_top10_prediction.md`; `data/processed/stage12_modelling/run_manifest.json`.

## 03_cross_validation

**Actual evaluation design shown schematically.** How do we test on songs not used for fitting?

**Read it:** Rows are validation rounds; columns are fixed partitions with saved song counts. Navy cells are held out and light cells train the model; text also identifies each role.

**For a beginner:** Each song receives a prediction from a model fitted without its partition. Vocabulary, IDF, NMF, numerical preprocessing and the classifier are learned only on training records. All models use the same saved partitions (StratifiedGroupKFold, shuffle=True, random_state=42).

**Say:** “Each round trains on four partitions and predicts the fifth. Every model gets the same partitions, so comparisons use the same held-out songs.”

**Limitation:** Complete-credit groups can separate a performer’s solo and collaboration credits; unknown shared texts and temporal shifts also remain possible.

**Sources:** `data/processed/stage12_modelling/out_of_fold_predictions.csv`; `data/processed/stage12_modelling/run_manifest.json`; `src/12_topics_and_top10_prediction.py`; `reports/topics_and_top10_prediction.md`.

## 04_selected_lyric_components

**Actual descriptive model output.** Which words characterize three selected components?

**Read it:** Three panels show components 2, 8 and 9; rows are the seven strongest saved words and bars are their raw NMF loadings. All panels share the same zero-based loading scale; teal is a visual accent here.

**For a beginner:** A larger loading makes a word more prominent within that component. These are provisional patterns from a separate model fitted on all 6,385 eligible records, never used for validation scoring. No displayed loading normalization is applied.

**Say:** “One component emphasizes vocal syllables, while two others suggest attachment and affectionate address. These labels are provisional interpretations of the highest-loading words.”

**Limitation:** Loadings are not song percentages, component prevalence or causal effects; component numbers cannot be linked to classifier coefficients from other fits.

**Sources:** `data/processed/stage12_modelling/descriptive_topics.csv`; `reports/topics_and_top10_prediction.md`; `src/12_topics_and_top10_prediction.py`.

## 05_actual_cleaning_examples

**Documented historical examples; block notation is schematic.** What changed, and what was preserved?

**Read it:** Each panel lists raw → clean → corrected whitespace-token counts. These include punctuation-only markers and differ from model tokenizer counts. Marker arrows show removal; [block A] denotes an entire block, not literal source text.

**For a beginner:** Bring Out The Freak In You: 386→375→375 (seven structural lines removed). Animals: 10→8→8 (two note-only lines removed; uncertain repetition preserved). A.M.: 642→640→320 (two note lines, then one supported duplicated block removed). DDU-DU DDU-DU: 316→314→314 (two note lines removed; Korean/Latin content retained). Local text was read only to verify counts, markers and preservation; no lyric excerpts are exported.

**Say:** “Cleaning removed documented markers while preserving potentially meaningful text. Only A.M. received the supported whole-block correction, and the multilingual BLACKPINK example remained eligible because its detector label was en.”

**Limitation:** Four selected cases do not estimate error prevalence; unresolved encoding issues were not repaired, and structural-label removal does not establish complete chorus coverage.

**Sources:** `reports/lyric_preprocessing_presentation_evidence.csv`; `reports/lyric_preprocessing_2000_2022.md`; `reports/full_block_correction_2000_2022.md`; read-only `data/processed/billboard_lyrics_corrected_2000_2022.parquet`.

## 06_paired_fold_results

**Actual evaluation results recomputed from saved predictions.** Does combined beat audio on the same held-out songs?

**Read it:** Rows are folds; x is average precision. Blue circles are audio; teal diamonds are audio plus ten lyric components. A connector pairs the scores; right labels are combined minus audio. The axis is deliberately focused at 0.195–0.280.

**For a beginner:** AP rewards placing Top-10 songs high in the score ranking: it sums precision weighted by increases in recall. It is not classification accuracy or trapezoidal PR-AUC. Means weight the five folds equally, rather than pooling all predictions. fold 1: 0.237464 → 0.260329 (Δ +0.022865); fold 2: 0.235667 → 0.245359 (Δ +0.009692); fold 3: 0.248306 → 0.269336 (Δ +0.021030); fold 4: 0.237197 → 0.264937 (Δ +0.027740); fold 5: 0.208190 → 0.223608 (Δ +0.015417).

**Say:** “The combined model had higher average precision in all five saved folds. Its mean AP was 0.2527 versus 0.2334 for audio, a paired mean difference of 0.0193.”

**Limitation:** Folds share training songs and are not independent replicates for a simple significance test; this is neither a significance nor a causal claim.

**Sources:** `data/processed/stage12_modelling/out_of_fold_predictions.csv`; verified to the reported precision against `reports/topics_and_top10_prediction.md`; `src/13_presentation_explainers.py` uses `sklearn.metrics.average_precision_score` without refitting.

## Verification

The script checks sample counts against saved metadata and the corrected corpus, unique OOF records and targets, saved partition sizes and group separation, all displayed AP values/differences against the existing report, and four cleaning examples against local text. Toy TF-IDF is explicitly calculated with unit-length rows. Input hashes are unchanged before/after generation. PNG and SVG use the same fixed 16:9 layout; text extents are checked against the canvas.
