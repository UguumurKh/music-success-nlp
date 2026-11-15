# Twelve-minute presentation outline

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
