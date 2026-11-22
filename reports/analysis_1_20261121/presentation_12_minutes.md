# 12-minute presentation outline

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
