# Verification results

- Original v3 saved-run verifier: passed before analysis.
- New preflight: frozen source, v2/v3 trees, dependency bytes, software versions, VADER lexicon, IDs, labels and fold metrics passed.
- All 6,546 master records scored successfully. All terminal cumulative means matched the existing weighted means within 1e-12 tolerance. No eligible records dropped; no missing numeric predictors.
- Five folds: training-only vocabulary/IDF/NMF, imputation/scaling, no group overlap, independently refitted feature removals and fixed prediction dimensions passed.
- 1,500 held-out permutations: 15 predictor groups x 20 repeats x 5 folds. Input/model immutability checks passed.
- Five focused unit tests passed, including repeated-seed permutation equality and unchanged fitted predictions.
- Original 131 historical tests passed in the original checkout with its private interim fixtures. Full worktree discovery initially had four missing-fixture errors; no checks were disabled.
- Saved prediction identity, probabilities, fold/pooled metrics, equal-fold means, confusion counts, private Git-ignore behavior, original numerical hashes, and frozen v2/v3 trees verified.
- Five main figures visually inspected. All 19 presentation pages read; title page rendered and inspected.

The first execution completed numerical verification before a Windows console box-character printing error interrupted report rendering. No model rerun was necessary. The delivered code uses CSV for console output; the original executed code and hashes are archived privately. Report/code packaging completion is recorded in the manifest. The line-ending hash mismatch during initial preflight was resolved by proving LF/CRLF-only differences and restoring exact historical dependency bytes, not by relaxing checks.

No verified modelling/data bug requiring a fair comparison rerun was found. This does not certify every raw match or lyric source. Human interpretation and case review remain for Uguumur and Nafees.
