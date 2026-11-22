# Reconciliation with the supplied 17 November presentation

Read all 19 pages of `D:/Projects/music-success-nlp/reports/preprocessing_ii_pca_20261115/Preprocessing_II_Presentation_17Nov2026.pdf`; title page visually inspected. The supplied reference was left unchanged and is not bundled into this submission.

- Pages 3–5: sample and whole-text normalization counts agree with the frozen manifests (6,546 master, 6,385 eligible, 984 Top-10; 947 new normalizations, one preserved correction, seven retained).
- Pages 8–9: word-weighted line sentiment and natural-text scoring agree with the implementation. Analysis 1 clarifies that it was already a mean, and adds only cumulative-mean SD.
- Pages 10–12 and 19: 10-dimensional NMF/SVD/PCA context, predictor counts and grouped evaluation agree. SVD/PCA are not rerun here. Complete-credit groups can still share individual performers across solo/collaborative credits.
- Pages 14–16: reference AP 0.2334 / 0.2637 / 0.2870 and historical 11 true positives from 21 predicted positives reconcile with saved predictions.
- Page 18: simple-feature contributions and component interpretation are addressed. The proposed random-noise diagnostic is deferred under the current task's priority instructions.
- Several slide footers say 15 November although the title is dated 17 November; this is a presentation-date distinction, not an analysis discrepancy. The new analysis/report is dated 21 November 2026.

The new twelve-minute outline is the authoritative timing plan for Analysis 1, replacing the previous preprocessing-focused sequence. Keep the historical slides as context and do not describe the tiny cumulative-SD increment as a substantial improvement.
