# Analysis 1 submission and teammate handover

Final packaging revision: 22 November 2026. The analysis results remain those
executed on 21 November. No models were rerun for packaging.

## Authoritative files

- Public report: [report.md](report.md).
- Timed outline: [presentation_12_minutes.md](presentation_12_minutes.md).
- Interpretation: [component_interpretation.md](component_interpretation.md).
- Original analysis checks: [verification_results.md](verification_results.md).
- Local revised ZIP, relative to this worktree root:
  `data/processed/analysis_1_20261121_v1/Analysis_1_upload_20261122_v2.zip`.
- Local full submission folder: `data/processed/analysis_1_20261121_v1/Analysis_1/`.
- Local packaging verification: `data/processed/analysis_1_20261121_v1/packaging_verification_20261122_v2.json`.

Inside the ZIP, reproduction.md distinguishes public review, reproduction with
private historical inputs, and verification of the complete private run.
submission_manifest.json enumerates actual ZIP members and their hashes;
excluded private artifacts are listed separately. The ZIP has five main figures
and excludes private lyrics, predictions, fitted objects and review cases.
The previous ZIP and original execution evidence are preserved unchanged.

## Checks for this revision

Three packaging regression tests passed. The existing local Analysis 1 verifier
passed before and after delivery updates. The extracted archive was checked
against its exact inventory and hashes, relative documentation links, declared
README metadata dependency, local helper modules, Python source compilation,
and Stage 17 CLI imports. No training command was invoked. Numerical tables,
predictions, private artifacts, original execution manifests and the previous
ZIP were checked byte-for-byte unchanged. Historical v2/v3 tree hashes passed.

## Personal review before submission

Uguumur and Nafees must review the cumulative formula and limitations, error
interpretations, all ten provisional component labels, and presentation timing.
Within the ignored full submission folder, inspect:

- `private/review_notes.md` and `private/error_review_cases.csv`.
- `private/error_review_with_lyrics.json` for the retained texts.
- `private/component_examples.json` for high-score NMF examples.
- `private/actual_trajectory_examples.json` and `private/actual_trajectories.png`.

Do not publish these private files. Full private verification requires a separate
private transfer, not the upload ZIP. This handover is not member sign-off.

## Publishing this branch safely (not performed)

From the analysis-1-update worktree:

1. Review the local commit and confirm the staged/committed file list contains
   code, tests, public documentation and aggregates only. Keep the ignored run
   and ZIP on the private transfer channel.
2. Run `git fetch origin` and inspect
   `git log --oneline --left-right origin/master...HEAD` and
   `git log --oneline --left-right origin/analysis-1-update...HEAD` if that remote
   branch exists. If teammates have advanced the same branch, coordinate before
   changing history; do not force-push. Inspect any default-branch changes before
   deciding how to integrate them.
3. After review, run `git push -u origin analysis-1-update` (ordinary push only).
4. Open a pull request into master for teammate review, identifying the result
   date and packaging-only revision. Do not attach private files or the private
   run to the PR. Review CI and resolve conflicts deliberately before a later
   merge decision.
5. Upload the revised submission ZIP to the course system manually only after
   both members' review. No push, merge, upload or contact was performed here.
