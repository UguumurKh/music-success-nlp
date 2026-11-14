# Conservative lyric preprocessing: 2000–2022

Prepared for the 20 October 2026 presentation. No modelling or language exclusions.

Source: `data/processed/billboard_analysis_2000_2022.parquet`; SHA-256 `0e6dc7f1c7c38b0b68728630bc9ed9599d5a302e216b013cbada1cdde0d2d104`.
Output: `data/processed/billboard_lyrics_preprocessed_2000_2022.parquet`. All 6,546 songs and every original column are preserved, including raw lyrics, outcomes and audio. New columns only; local Parquet remains ignored by Git.

## Inspection and observed issues

Seed 20261020: five shortest, five longest, five around median word length, ten per lyric-confidence group, and fifteen random records, deduplicated to 60 records. Beginning, middle and ending snippets were inspected locally, alongside all 21 records with square brackets and targeted encoding/metadata hits. This is a varied diagnostic sample, not a representative prevalence estimator; frequencies below use the whole corpus.
Inspection IDs: 268, 522, 577, 634, 676, 724, 1045, 1087, 1274, 1275, 1438, 1600, 1696, 1919, 2083, 2174, 2193, 2575, 2610, 2862, 2969, 3720, 3785, 3842, 4130, 4441, 4684, 5054, 5198, 5258, 5432, 5580, 5616, 5671, 6114, 6372, 6405, 6532, 6566, 6645, 7158, 7542, 7764, 7951, 8060, 8108, 8341, 8417, 8498, 8572, 9491, 9870, 10018, 10051, 10123, 10726, 10741, 10851, 10914, 10973.

Observed shortest lyrics include instrumental-like repeated vocal fragments; longest texts contain substantial repetition. Bracketed ad-libs and missing-word placeholders contain potentially meaningful information. Broad searches for “lyrics”, “copyright” and “embed” hit actual lyrical words, so those terms are never deleted. Two clear mojibake cases (IDs 1919 and 5916) are flagged rather than guessed. Spanish text was observed directly (e.g. ID 10051).

| Song-level flag | Count | % of songs |
| --- | --- | --- |
| lyric_text_changed | 6546 | 100.00 |
| lyric_whitespace_issue | 6546 | 100.00 |
| lyric_nfc_changed | 1 | 0.02 |
| lyric_residual_brackets | 16 | 0.24 |
| lyric_encoding_review | 2 | 0.03 |
| lyric_mixed_script_token_review | 67 | 1.02 |
| lyric_invisible_review | 1 | 0.02 |
| lyric_web_metadata_review | 1 | 0.02 |
| lyric_blank | 0 | 0.00 |
| lyric_extreme_length | 156 | 2.38 |
| lyric_language_short | 11 | 0.17 |
| lyric_language_uncertain | 115 | 1.76 |
| lyric_language_mixed_candidate | 36 | 0.55 |

| Raw text feature (not necessarily a defect) | Songs |
| --- | --- |
| Square brackets | 21 |
| CR line endings | 0 |
| LF line breaks | 6546 |
| ASCII apostrophe | 6481 |
| Curly apostrophe | 1 |
| Non-ASCII characters | 3833 |

Unchanged lyrics: 0. Section-label lines removed: 13 across 5 songs. Music-note-only lines removed: 10,017 across 3,516 songs.

Flags overlap. Encoding/invisible/web flags are pattern-based review candidates, not verified error counts. Extreme length means <50 or >2,000 cleaned whitespace tokens, a review threshold rather than an exclusion rule.

## Before / after lengths

Words are whitespace tokens (punctuation-only tokens included); characters are Unicode code points including whitespace. Mean is arithmetic average; median and linear-interpolated percentiles describe the distribution, not uncertainty. Blank strings count as zero; nulls are excluded. Removing note markers can reduce “word” counts without removing words.

| Statistic | Raw words | Clean words | Raw characters | Clean characters |
| --- | --- | --- | --- | --- |
| mean | 535.01 | 533.47 | 2,740.83 | 2,660.91 |
| min | 10.00 | 8.00 | 62.00 | 53.00 |
| p01 | 142.00 | 141.00 | 741.60 | 710.05 |
| p05 | 206.00 | 204.00 | 1,051.25 | 1,011.00 |
| p25 | 295.00 | 294.00 | 1,507.00 | 1,454.00 |
| median | 394.00 | 393.00 | 2,018.00 | 1,956.00 |
| p75 | 595.75 | 594.75 | 3,047.75 | 2,963.75 |
| p95 | 1,432.50 | 1,428.00 | 7,365.25 | 7,162.75 |
| p99 | 2,511.55 | 2,509.65 | 12,852.00 | 12,530.25 |
| max | 5,000.00 | 4,995.00 | 26,023.00 | 25,393.00 |

## Language screening

[langdetect 1.0.9](https://pypi.org/project/langdetect/) runs locally with a fixed seed and its default language profiles. Top language and score are retained; scores are not calibrated correctness probabilities. The library defaults to a 10,000-character cap per call; chunk checks cover later portions of long texts too. Short/repetitive means <50 tokens or <20 unique casefolded whitespace tokens. Uncertain means short/repetitive, top score <0.90, undetermined, or chunk disagreement. Three nonoverlapping token thirds (minimum 30 tokens each) are checked; different top languages scoring ≥0.80 flag possible mixed language. This can both miss code-switching and falsely flag slang, transliteration, proper names or repeated refrains. No label is a verified language annotation; no songs are excluded.

| Top detector label | Songs |
| --- | --- |
| en | 6385 |
| es | 137 |
| ko | 6 |
| pt | 3 |
| id | 3 |
| it | 2 |
| cy | 2 |
| so | 2 |
| tl | 2 |
| fr | 1 |
| sq | 1 |
| ja | 1 |
| af | 1 |

Language-review union (non-English top label OR uncertainty): 253 songs. Flags and chunk scores in the local Parquet are the review queue. Targeted inspection confirmed Korean/English text in DDU-DU DDU-DU (ID 2160), despite an English whole-text label. Daddy (2173) contains Korean/English but is labelled Welsh, illustrating detector error. Repetitive vocalizations can trigger chunk disagreement (e.g. 2177); these flags are not a measured mixed-language prevalence.

| ID | Song | Top label | Score | Chunk disagreement |
| --- | --- | --- | --- | --- |
| 9 | "Ay, Dios Mio!" | es | 1.000 | False |
| 17 | "Bon, Bon" | es | 1.000 | False |
| 114 | "What A Catch, Donnie" | en | 0.857 | False |
| 296 | 8 | en | 0.857 | False |
| 314 | A Bay Bay | en | 0.857 | False |
| 331 | A La Primera Persona | es | 1.000 | False |
| 408 | Adicto | es | 1.000 | False |
| 414 | Adrenalina | es | 1.000 | False |
| 435 | Agosto | es | 1.000 | False |
| 436 | Aguacero | es | 1.000 | False |
| 438 | Ai Se Eu Te Pego | pt | 1.000 | False |
| 647 | Amor Genuino | es | 1.000 | False |

## Repetition and duplicate texts

Repeated-line extras count occurrences after the first, ignoring case and whitespace but preserving punctuation. Their fraction divides by nonblank cleaned lines. Repetition is retained; a repeated chorus is not an extraction error.

- lyric_raw_duplicate_size > 1: 0 songs.
- lyric_normalized_duplicate_size > 1: 0 songs.
- lyric_full_block_repeats > 1: 955 songs.
- Normalized duplicate groups: 0. Comparison uses NFC-cleaned, casefolded, whitespace-collapsed text; raw duplicates use untouched text.
- Songs with repeated lines: 6,475; median repeated-line fraction: 0.360.
- Near-duplicate candidates: 1 pairs from 25,520 retrieved pairs; 2 songs flagged. Retrieval shares one of each document’s five rarest shared 5-token shingles (present in 2–100 songs); acceptance requires ≥20 unique shingles per text and set Jaccard ≥0.90, excluding normalized exact matches. This is non-exhaustive, insensitive to repeated-block counts, and identifies candidates rather than proven duplicate recordings.
- Full-block repetition means the entire nonblank line sequence repeats exactly after case/whitespace normalization. This is a stronger review signal but can still reflect intended musical repetition.

| Normalized duplicate group | Song IDs |
| --- | --- |

| Song IDs (near candidates) | Jaccard |
| --- | --- |
| 4480, 4481 | 0.938 |

The retrieved near pair 4480 / 4481 is “I Kissed A Girl” credited to Glee Cast / Katy Perry: shared lyrics across cover versions are plausible, not necessarily a matching defect. The web-pattern hit (11008, “www.memory”) is lyrical/title-related content, not confirmed extraction metadata; it is retained.

## Small review examples

Only non-lyrical marker/whitespace fragments are shown; no full lyrics or lyrical excerpts are exported. Escapes show line breaks. Contractions and punctuation remain unchanged.

| Song ID | Raw fragment | Clean fragment | Record flags |
| --- | --- | --- | --- |
| 1498 | `[Chorus]` | `(line removed)` | changed=True; brackets=False; encoding=False |
| 676 | ` ♪` | `(line removed)` | changed=True; brackets=False; encoding=False |
| 724 | `[Pt:` | `[Pt:` | changed=True; brackets=True; encoding=False |
| 1919 | `â?` | `â?` | changed=True; brackets=False; encoding=True |
| 5916 | `â\x80\x98` | `â\x80\x98` | changed=True; brackets=False; encoding=True |

## Decisions and next steps

- Applied: NFC, consistent newline splitting, trimmed/collapsed horizontal whitespace, at most one blank line, removal of observed whole-line Intro/Reversed Intro, numbered Verse, Chorus and Hook label forms, and note-only lines. No broad bracket removal, apostrophe replacement, lowercasing, stopword removal, lemmatization, or deduplication.
- Retained: negation, contractions, punctuation, accents, case, repetitions, ad-libs and uncertain speaker/stage labels. NFC does not repair mojibake. Review encoding, residual brackets, unusually long texts and repeated full blocks before expanding rules.
- Mixed Latin/Greek/Cyrillic tokens may be look-alike substitutions; genuine multilingual lines also occur. Review flagged tokens locally before any targeted repair. NFC deliberately does not transliterate them.
- Review language candidates manually before defining an English-only or multilingual population. Check mixed-language cases and high-confidence matches too; matching confidence is not text-quality assurance.
- Resolve duplicate song relationships and group related texts during future evaluation to avoid leakage. No observations are merged or removed in this stage.
- Topic modelling later: language-aware tokenization, optional lowercasing/lemmatization and documented stopwords; compare repetition-preserving versus capped counts. Fit vocabulary on training data where evaluation requires it.
- Sentiment later: retain negation, punctuation and emoji; use language-appropriate methods and inspect slang, irony and repetition. Do not interpret a detector score as sentiment.
- TF-IDF later: compare word n-grams (including negation phrases) and character n-grams; tune case, stopwords and frequency limits inside training folds. Avoid automatically dropping negators.
- Transformers later: use the chosen tokenizer on this minimally cleaned text; preserve punctuation/case as appropriate, and explicitly plan chunking/pooling for long lyrics instead of silent truncation.
- These are observational, matched Billboard songs. Cleaning does not establish causal effects of lyrics on success.

Validation: source SHA-256 unchanged; saved output read back and all original columns equal the source, including IDs, order, outcomes and audio. Focused synthetic tests cover cleaning and preservation.
