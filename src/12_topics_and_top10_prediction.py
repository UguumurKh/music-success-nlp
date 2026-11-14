"""Fixed-specification Stage 12: grouped validation, then separate descriptive NMF.

Run: uv run python src/12_topics_and_top10_prediction.py
No upstream stage is run or modified. All ML uses scikit-learn; no tuning/search.
Full texts, vocabulary, fitted models and row-level predictions stay Git-ignored.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import warnings

import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import sklearn
from sklearn.decomposition import NMF
from sklearn.dummy import DummyClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/processed/billboard_lyrics_corrected_2000_2022.parquet'
AUDIT = ROOT / 'reports/stage10_11_repetition_audit.md'
AUDIT_METRICS = ROOT / 'data/processed/stage10_11_audit/audit_metrics.json'
PRIVATE = ROOT / 'data/processed/stage12_modelling'
REPORT = ROOT / 'reports/topics_and_top10_prediction.md'
FIGURES = ROOT / 'reports/figures'
SAMPLE = ROOT / 'reports/preprocessing_I_sample.csv'
AUDIO = [f'{name}_median' for name in (
    'danceability', 'energy', 'loudness', 'speechiness', 'acousticness',
    'instrumentalness', 'liveness', 'valence', 'tempo', 'duration_ms')]
TEXT = 'lyrics_deduplicated'
MODELS = ['Dummy', 'Audio', 'Topics', 'Audio + topics']
# A version-locked sklearn list, with explicit negation retention. Apostrophe-aware
# word unigrams preserve don't / can't / isn't as tokens, with straight or curly quotes.
NEGATION = {'no', 'nor', 'not', 'never', 'neither', 'none', 'nobody', 'nothing',
            'nowhere', 'without', 'cannot', 'cant', 'dont', 'doesnt', 'didnt',
            'isnt', 'arent', 'wasnt', 'werent', 'wont', 'wouldnt', 'shouldnt',
            'couldnt', 'hasnt', 'havent', 'hadnt', 'mustnt', 'neednt'}
STOPWORDS = sorted(ENGLISH_STOP_WORDS - NEGATION)
TOKEN_PATTERN = r"(?u)\b\w\w+(?:['’]\w+)*\b"
KNOWN_LINKS = [(4480, 4481)]  # Existing Stage 10 report: shared-text/cover candidate.


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def md_table(headers, rows):
    def cell(x):
        return str(x).replace('|', '\\|').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |',
                      *['| ' + ' | '.join(map(cell, r)) + ' |' for r in rows]])


def make_groups(source):
    """Outcome-blind connected components over existing links, across all source rows.

    This uses no artist-name parsing, fuzzy matching, or newly inferred cover links.
    Building groups before language screening preserves known connecting records.
    """
    ids = source['billboard_source_row'].to_list()
    parent = {i: i for i in ids}
    merges = Counter()

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b, reason):
        a, b = find(a), find(b)
        if a != b:
            parent[max(a, b)] = min(a, b)
            merges[reason] += 1

    # Existing duplicate group IDs are all null in this snapshot, but use them
    # if populated in future inputs. Equality hashes identify shared source texts.
    for field in ['artist_norm', 'lyrics_compare_sha256', 'raw_lyric_sha256', 'lyric_duplicate_group_id']:
        seen = {}
        for song_id, value in source.select('billboard_source_row', field).iter_rows():
            if value is None or value == '':
                continue
            if value in seen:
                union(song_id, seen[value], field)
            else:
                seen[value] = song_id
    for a, b in KNOWN_LINKS:
        assert a in parent and b in parent
        union(a, b, 'documented_shared_text_pair')
    mapping = {i: find(i) for i in ids}
    return mapping, dict(merges)


def new_vectorizer():
    return TfidfVectorizer(analyzer='word', ngram_range=(1, 1), lowercase=True,
        token_pattern=TOKEN_PATTERN, stop_words=STOPWORDS, min_df=5, max_df=.95,
        max_features=None, sublinear_tf=False, norm='l2', dtype=np.float64,
        use_idf=True, smooth_idf=True, binary=False)


def fit_nmf(matrix):
    """One numerical convergence retry, never selected using held-out scores."""
    attempts = []
    for limit in (500, 1000):
        model = NMF(n_components=10, init='nndsvda', random_state=42, max_iter=limit)
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter('always')
            weights = model.fit_transform(matrix)
        messages = [str(w.message) for w in captured]
        converged = not any(issubclass(w.category, ConvergenceWarning) for w in captured)
        attempts.append(dict(max_iter=limit, n_iter=int(model.n_iter_), converged=converged, warnings=messages))
        if converged:
            break
    assert np.isfinite(weights).all()
    return model, weights, attempts


def transform_nmf(model, matrix):
    attempts = []
    # A transform-only retry changes its optimization budget, never topic components.
    limits = [model.max_iter] + ([1000] if model.max_iter < 1000 else [])
    for limit in limits:
        model.set_params(max_iter=limit)
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter('always')
            result = model.transform(matrix)
        converged = not any(issubclass(w.category, ConvergenceWarning) for w in captured)
        attempts.append(dict(max_iter=limit, converged=converged, warnings=[str(w.message) for w in captured]))
        if converged:
            break
    return result, attempts


def classifier():
    # sklearn 1.9: l1_ratio=0 is pure L2; penalty='l2' is deprecated.
    return make_pipeline(SimpleImputer(strategy='median', keep_empty_features=True),
                         StandardScaler(),
                         LogisticRegression(C=1, l1_ratio=0, class_weight=None,
                                            max_iter=2000, solver='lbfgs', random_state=42))


def focused_contract_checks():
    """Small synthetic holdout check complements actual-fold runtime assertions."""
    vectorizer = new_vectorizer()
    training = ['common apple not never', 'common apple no', 'common apple nor',
                'common apple without', "common apple don't", 'common orange cannot']
    x = vectorizer.fit_transform(training)
    vocabulary = dict(vectorizer.vocabulary_)
    vectorizer.transform(['validationonly apple'])
    assert vectorizer.vocabulary_ == vocabulary and 'validationonly' not in vocabulary
    tokens = new_vectorizer().build_analyzer()("no nor not never neither without cannot don't can't isn’t")
    assert all(word in tokens for word in ['no', 'nor', 'not', 'never', 'neither', 'without', 'cannot', "don't", "can't", 'isn’t'])
    imputer = SimpleImputer(strategy='median').fit([[1.], [3.], [np.nan]])
    assert imputer.transform([[np.nan], [10000.]])[0, 0] == 2.
    scaler = StandardScaler().fit([[1.], [3.]])
    scaler.transform([[10000.]])
    assert scaler.mean_[0] == 2 and scaler.n_samples_seen_ == 2
    assert len(AUDIO) == 10 and len(set(AUDIO)) == 10
    assert not any(any(bad in name for bad in ['rank', 'chart', 'grammy', 'top10', 'artist', 'lyric']) for name in AUDIO)


def topic_label(terms):
    """Conservative descriptive labels from exported words, never outcome scores."""
    if terms[0] == 'love':
        return 'Love / attachment (provisional)'
    if terms[0] == 'baby':
        return 'Affectionate address (provisional)'
    if terms[0] in {'oh', 'ooh', 'na', 'la', 'yeah'}:
        return 'Vocal syllables / interjections; theme unclear'
    if len(set(terms[:6]) & {'bitch', 'shit', 'fuck'}) >= 2:
        return 'Profanity / colloquial diction; theme unclear'
    if terms[0] == "don't" and 'wanna' in terms[:5]:
        return 'Negation / desire language; theme unclear'
    return 'Mixed general language; theme unclear'


def figures(scores, topics):
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.titleweight': 'bold', 'savefig.facecolor': 'white'})
    colors = ['#7a7a7a', '#31688e', '#bc7c22', '#4b6850']
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), layout='constrained')
    for ax, metric, label in zip(axes, ['ap', 'roc_auc'], ['Average precision (primary)', 'ROC-AUC']):
        for index, name in enumerate(MODELS):
            values = [r[metric] for r in scores if r['model'] == name]
            ax.scatter(index + np.linspace(-.11, .11, 5), values, color=colors[index], s=35, alpha=.8)
            ax.plot([index-.2, index+.2], [np.mean(values)]*2, color=colors[index], lw=3)
            ax.text(index, max(values)+.025, f'{np.mean(values):.3f}', ha='center', fontsize=11)
        ax.set_xticks(range(4), ['Dummy', 'Audio', 'Topics', 'Audio +\ntopics'])
        ax.set_ylim(0, min(1, max(r[metric] for r in scores) + .10))
        ax.set_ylabel(label)
        ax.grid(axis='y', alpha=.18)
    fig.suptitle('Top-10 prediction: identical five grouped validation folds', fontsize=16)
    fig.supxlabel('Dots = fold scores; horizontal marks = unweighted fold means. Variation is descriptive.', fontsize=10)
    fig.savefig(FIGURES / 'top10_model_comparison.png', dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(2, 5, figsize=(20, 12), layout='constrained')
    # Within-topic normalization makes labels legible, not topic prevalence.
    common_max = max(max(t['term_weights']) / sum(t['term_weights']) for t in topics) * 1.08
    for ax, topic in zip(axes.flat, topics):
        terms, values = topic['terms'], np.array(topic['term_weights'])
        values = values / values.sum()
        ax.barh(np.arange(15), values[::-1], color='#31688e')
        ax.set_yticks(np.arange(15), terms[::-1], fontsize=11)
        ax.set_title(f"Topic {topic['topic']:02d}")
        ax.set_xlim(0, common_max)
        ax.set_xlabel('Share of top-15 loading')
        ax.grid(axis='x', alpha=.15)
    fig.suptitle('Descriptive NMF: 15 strongest terms per topic\nAll eligible records; separate from cross-validation', fontsize=18)
    fig.savefig(FIGURES / 'nmf_topic_terms.png', dpi=160)
    plt.close(fig)


def write_report(result, scores, topics):
    means = result['model_means']
    folds = result['folds']
    mean_delta = float(np.mean(result['paired_ap_differences']))
    lines = ['# Preliminary topics and Top-10 prediction', '',
        f"Executed 2026-11-01. Automated English screening retains **{result['eligible']:,} songs**, "
        f"including **{result['positive']:,} Top-10** and **{result['negative']:,} non-Top-10** records "
        f"({result['prevalence']:.2%} positive). Audio + topics has mean average precision (AP) "
        f"**{means['Audio + topics']['ap']:.4f}**, versus **{means['Audio']['ap']:.4f}** for audio; "
        f"the paired mean difference is **{mean_delta:+.4f}**. These are preliminary associations, "
        'with descriptive fold variation and no significance or causal claim.', '',
        '## Sample and preprocessing', '',
        f"Source: `{SOURCE.relative_to(ROOT).as_posix()}` ({result['source_records']:,} records). "
        f"The existing `lyric_language == 'en'` rule removes {result['excluded_language']} records from modelling only. "
        'This is automated English screening, not verified English-only text; slang and code-switching remain. '
        '`lyrics_deduplicated` is used after checking the existing repetition audit and its source hash; '
        'the audit, integration and manual review were not rerun. Every source row/column and file is preserved. '
        'Unresolved repetitions stay unchanged and eligible; flags are retained for inspection, never predictors.', '',
        md_table(['Eligible-sample attribute', 'Records'], list(result['sample_flags'].items())), '',
        f"Main outcome: `peak_rank <= 10` versus `> 10`, verified against `top10`. An **illustrative, "
        f"not professor-confirmed** gap excluding ranks 11–15 would remove {result['gap_removed']} negatives "
        f"and leave {result['gap_remaining']} records ({result['positive']} positive / "
        f"{result['negative']-result['gap_removed']} negative). This is a count only: no gap-outcome models or extra searches were run.", '',
        'The ten audio predictors are the existing medians: ' + ', '.join(f'`{x}`' for x in AUDIO) + '. '
        f"Missing/nonfinite cells: {result['missing_audio_cells']}; affected records: {result['missing_audio_records']}. "
        'Numerical inputs receive training-only median imputation (all-missing training columns retain a zero fallback) '
        'and standard scaling. Duration is an audio duration field, not a lyric-length feature. No lyric length, '
        'lexical diversity, repetition, sentiment, chart history, Grammy outcome, identifier, artist-name or quality-flag predictor is used.', '',
        '## Validation design and leakage boundaries', '',
        f"Five `StratifiedGroupKFold` folds, shuffle=True, random_state=42, are materialized once and reused "
        f"for every model. {result['groups']} connected groups cover the eligible records; group-size "
        f"min/median/p95/max = {result['group_size_summary']}; {result['singleton_groups']} are singletons. "
        f"Largest-group share = {result['largest_group_share']:.2%}. Groups use existing `artist_norm` "
        '(the entire normalized credit, with featured artists/order retained), existing text hashes/duplicate-group IDs, '
        'and the documented shared-text candidate 4480/4481 (Glee Cast / Katy Perry, “I Kissed A Girl”). '
        'Connected components are formed on all source rows before the language filter. The candidate pair is a '
        'conservative leakage constraint, not a newly confirmed cover classification.', '',
        'Complete-credit grouping can place a performer’s solo and collaborative credits in different folds. '
        'Undetected covers/shared texts, punctuation-normalization collisions and temporal shifts remain possible. '
        'This is **not fully unseen-performer evaluation**, nor a future-year forecasting test. Known group links '
        'are used only for partitioning; they are not features. No elaborate artist parser or new cover search was used.', '',
        md_table(['Fold','Train n','Train +','Validation n','Validation +','Val. prevalence','Train groups','Val. groups','Overlap'],
                 [[f['fold'],f['train_n'],f['train_positive'],f['validation_n'],f['validation_positive'],
                   f"{f['validation_prevalence']:.4f}",f['train_groups'],f['validation_groups'],f['group_overlap']] for f in folds]), '',
        'Each fold fits a fresh vocabulary, IDF and NMF using only training lyrics. The same training-fitted topics '
        'feed L and A+L. Each numerical pipeline separately fits its imputer, scaler and classifier on training rows; '
        'held-out rows only pass through `transform` / `predict_proba`. No setting is selected from validation scores.', '',
        f"TF-IDF: word unigrams, lowercase=True, min_df=5, max_df=0.95, max_features=None, "
        'sublinear_tf=False, norm="l2", smooth_idf=True, use_idf=True, binary=False. '
        f"Stopwords: the fixed scikit-learn {sklearn.__version__} `ENGLISH_STOP_WORDS` list minus "
        f"{', '.join(sorted(NEGATION & ENGLISH_STOP_WORDS))}; the exact {len(STOPWORDS)}-word list and its hash "
        'are stored privately. No data-driven stopwords or lemmatization. The apostrophe-aware Unicode token pattern '
        f'`{TOKEN_PATTERN}` retains contractions such as negated auxiliaries as single word tokens; one-character '
        'tokens are omitted. Explicit tests verify negation retention.', '',
        'NMF: 10 components, init="nndsvda", random_state=42, max_iter=500, solver="cd", '
        'beta_loss="frobenius", tol=1e-4, no additional regularization. A convergence warning permits one '
        'numerical-budget increase to 1,000 iterations, without tuning against scores. Logistic regression: '
        'pure L2 (`l1_ratio=0` in installed sklearn), C=1, class_weight=None, max_iter=2000, solver="lbfgs". '
        'DummyClassifier(strategy="prior") predicts the training prevalence.', '',
        '## Executed model comparison', '',
        md_table(['Model','Mean fold AP','Mean fold ROC-AUC'],
                 [[name,f"{means[name]['ap']:.4f}",f"{means[name]['roc_auc']:.4f}"] for name in MODELS]), '',
        md_table(['Fold','Model','Average precision','ROC-AUC'],
                 [[r['fold'],r['model'],f"{r['ap']:.4f}",f"{r['roc_auc']:.4f}"] for r in scores]), '',
        md_table(['Fold','Paired AP: combined minus audio'],
                 [[i+1,f'{d:+.4f}'] for i,d in enumerate(result['paired_ap_differences'])] + [['Mean',f'{mean_delta:+.4f}']]), '',
        'AP is **average precision**, not trapezoidal PR-AUC. Means weight the five folds equally. '
        'A constant-score dummy has fold AP equal to validation prevalence and ROC-AUC 0.5, although its '
        'predicted probability is training prevalence. Fold differences share training records and are not '
        'independent replicates; no confidence interval, p-value or significance claim is made.', '',
        '![Model comparison](figures/top10_model_comparison.png)', '',
        '## Convergence and empty vectors', '',
        md_table(['Fit','Vocabulary','NMF train iterations','Train converged','Transform converged','Empty train','Empty held-out'],
                 [[f"Fold {f['fold']}",f['vocabulary'],f['nmf_fit'][-1]['n_iter'],f['nmf_fit'][-1]['converged'],
                   f['nmf_transform'][-1]['converged'],f['empty_train'],f['empty_validation']] for f in folds] +
                 [['All-data descriptive',result['descriptive_vocabulary'],result['descriptive_nmf'][-1]['n_iter'],
                   result['descriptive_nmf'][-1]['converged'],'N/A',result['descriptive_empty'],'N/A']]), '',
        f"NMF training retries: {sum(len(f['nmf_fit'])-1 for f in folds)+len(result['descriptive_nmf'])-1}; "
        f"validation-transform retries: {sum(len(f['nmf_transform'])-1 for f in folds)}. "
        f"Logistic fits with convergence warnings: {result['logistic_nonconverged']}/15. "
        'Empty text vectors are retained with zero topic weights; none are silently dropped. '
        'Their stable IDs, fold assignments and predictions are recorded in the private OOF file. '
        'Convergence warning details and iteration budgets are preserved in the private run manifest.', '',
        '## Separate descriptive topics', '',
        'After validation, a new TF-IDF/NMF model is fitted on all eligible records with the same fixed settings. '
        'It is never used to produce the validation scores above. Topic indices are local to this descriptive fit, '
        'not aligned to fold-specific topics. Top terms are ordered by component loading; representatives are '
        'the three songs with largest raw topic weights (ties broken by stable ID). Loadings are not probabilities. '
        'Topic labels remain provisional; unclear components are explicitly left uninterpreted.', '',
        md_table(['Topic','Provisional label','Top 15 terms','Representative IDs / titles'],
                 [[t['topic'],t.get('label','Unclear; inspect terms'),', '.join(t['terms']),
                   '; '.join(f"{s['id']}: {s['title']}" for s in t['representatives'])] for t in topics]), '',
        'Five components are dominated by vocal syllables/interjections (2, 4, 5, 6, 7), while topic 8 supports '
        'a provisional love/attachment label. These are not ten distinct semantic themes. Profanity/colloquial '
        'diction in topic 3 describes vocabulary, not performer identity. Fragments such as `ll` and `ve` remain '
        'where source contractions are separated; no extra cleaning or stopword changes were chosen after seeing results.', '',
        '![Topic terms](figures/nmf_topic_terms.png)', '',
        '## Preprocessing I implications and eight-slide outline', '',
        'Conservative cleaning preserves within-song structure. The existing repetition audit supports normalized '
        'linear unigram TF-IDF invariance for exact full-block repeats, so unresolved songs need not be shortened '
        'to run this representation. It does not establish that the source text is correct. Tokenization, negation '
        'retention, automated language screening and grouped evaluation are substantive preprocessing choices. '
        'These observational matched Billboard records cannot establish that lyrics cause success; matching, '
        'language-detection and text/audio-version uncertainty remain. Ten coarse topics may reflect vocal '
        'fragments or genre-associated diction as well as themes. Improving or declining AP in these folds alone '
        'does not justify searching settings on the same held-out results.', '',
        '1. **Question and unit:** do lyric topics add to audio for Top-10 classification? One song–artist record; observational scope.',
        f"2. **Prepared sample:** {result['source_records']:,} source records → {result['eligible']:,} automated-English records; {result['positive']} / {result['negative']} classes.",
        '3. **Cleaning decisions:** use Stage 11 text; preserve negation, unresolved repetitions and flags; show the metadata-only sample.',
        '4. **Text representation:** fixed unigram TF-IDF → 10-component NMF; distinguish fold-fitted representation from descriptive topics.',
        '5. **Leakage controls:** complete-credit groups plus documented shared-text links; show group sizes/fold counts and residual collaboration risk.',
        '6. **Prediction comparison:** dummy / audio / topics / combined; show the model figure, AP and ROC-AUC.',
        f"7. **Results and topic examples:** paired AP mean {mean_delta:+.4f}; display top-term figure and provisional labels, without significance claims.",
        '8. **Limits and next decisions:** automated language errors, topic ambiguity, version uncertainty, descriptive fold variation; rank-11–15 gap remains illustrative only.', '',
        '## Cleaned-data sample and column guide', '',
        'The 25-row [sample CSV](preprocessing_I_sample.csv) is a deterministic class-stratified metadata extract '
        '(seed 42; 4 Top-10 and 21 other songs), not representative evidence for prevalence. All values in source '
        'columns are copied unchanged; no full lyrics or comparison strings are exported.', '',
        md_table(['Columns','Meaning / modelling role'], [
            ['billboard_source_row; lyric_representative_spotify_id','Stable source/representative IDs; never predictors.'],
            ['Song; Artist; first_chart_date','Original title, full credit and first observed chart date; context only.'],
            ['peak_rank; top10','Observed outcome and binary label; never input features.'],
            ['artist_norm; evaluation_group; validation_fold','Existing complete-credit key, connected group and assigned fold; partitioning only.'],
            ['lyric_language; lyric_language_score','Existing top detector label/score; score is not calibrated correctness probability.'],
            ['lyric_language_uncertain; lyric_language_mixed_candidate; lyric_language_short','Retained language-screen flags; not features.'],
            ['lyric_full_block_repeats; full_block_dedup_status; full_block_dedup_applied','Historical repetition multiplicity and correction evidence status; not features.'],
            ['lyric_encoding_review; lyric_near_duplicate_candidate','Existing quality/shared-text flags; not features.'],
            ['lyric_resolution_confidence; audio_resolution_confidence; any_missing_audio_value','Consolidation diagnostics; not features.'],
            [', '.join(AUDIO),'Only the ten whitelisted audio medians enter A and A+L. Duration is milliseconds; tempo is BPM; loudness is dB; other fields retain source scales.']]), '',
        '## Reproducibility and focused checks', '',
        f"Environment: Python {sys.version.split()[0]}, scikit-learn {sklearn.__version__}, NumPy {np.__version__}, "
        f"Polars {pl.__version__}; dependencies managed with `uv` and locked in `uv.lock`. "
        'Run `uv run python src/12_topics_and_top10_prediction.py`. No other modelling work was found to reuse. '
        'No AGENTS.md was found in the repository or parent directories; README preservation rules were followed.', '',
        'Passed checks: source SHA-256 and prior-audit hash match; unique IDs and exact target agreement; '
        'one held-out prediction per eligible row in original order for each model; both classes in every fold; '
        'zero group overlap; known cover pair stays together; actual train-only IDF formula and document-frequency '
        'thresholds; unchanged vocabulary/IDF/NMF components after held-out transforms; training-only imputer medians '
        'and scaler sample counts; predictor whitelist and 10/10/20 model dimensions; negation retention; '
        'synthetic held-out-only token/imputation/scaling checks; finite probabilities and retained zero-vector rows. '
        'Input hashing after execution verifies the dataset and previous audit remained unchanged.', '',
        'Private, Git-ignored outputs under `data/processed/stage12_modelling/`: '
        '`out_of_fold_predictions.csv` (all models, stable IDs, groups, folds, target, zero-vector indicator), '
        '`run_manifest.json` (scores, provenance, settings, convergence and fit-ID fingerprints), '
        '`descriptive_topics.csv` (ranked terms/loadings and representative metadata), '
        '`descriptive_model.joblib` (fitted vocabulary, IDF, NMF and exact stopwords). '
        'Public figures contain only requested top-term summaries and aggregate scores; no lyric passages. '
        'Nothing was published or pushed.', '']
    REPORT.write_text('\n'.join(lines), encoding='utf-8')


def main():
    focused_contract_checks()
    source_hash, audit_hash = sha(SOURCE), sha(AUDIT)
    audit_metrics = json.loads(AUDIT_METRICS.read_text(encoding='utf-8'))
    assert source_hash == audit_metrics['source_sha256'][str(SOURCE.relative_to(ROOT))]
    source = pl.read_parquet(SOURCE)
    assert all(c in source.columns for c in AUDIO + [TEXT, 'lyric_language', 'artist_norm', 'top10', 'peak_rank'])
    assert source['billboard_source_row'].n_unique() == source.height
    assert source['billboard_source_row'].null_count() == 0
    groups_all, merge_counts = make_groups(source)
    frame = source.filter(pl.col('lyric_language') == 'en')
    assert frame['top10'].null_count() == frame['peak_rank'].null_count() == 0
    y = (frame['peak_rank'].to_numpy() <= 10).astype(int)
    np.testing.assert_array_equal(y, frame['top10'].to_numpy())
    ids = frame['billboard_source_row'].to_numpy()
    groups = np.array([groups_all[int(i)] for i in ids])
    texts = frame[TEXT].to_numpy()
    assert all(isinstance(t, str) and t.strip() for t in texts)
    audio = frame.select(AUDIO).to_numpy().astype(float)
    audio[~np.isfinite(audio)] = np.nan
    group_sizes = np.array(list(Counter(groups).values()))
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    splits = list(splitter.split(np.zeros(len(y)), y, groups))
    oof = {name: np.full(len(y), np.nan) for name in MODELS}
    assigned_fold = np.zeros(len(y), dtype=int)
    empty_oof = np.zeros(len(y), dtype=bool)
    folds, scores = [], []
    PRIVATE.mkdir(exist_ok=True)
    FIGURES.mkdir(exist_ok=True)
    for fold, (train, validation) in enumerate(splits, 1):
        assert not set(groups[train]) & set(groups[validation])
        assert len(np.unique(y[train])) == len(np.unique(y[validation])) == 2
        assert (assigned_fold[validation] == 0).all()
        assigned_fold[validation] = fold
        vectorizer = new_vectorizer()
        x_train = vectorizer.fit_transform(texts[train])
        idf_before = vectorizer.idf_.copy()
        vocab_before = dict(vectorizer.vocabulary_)
        x_validation = vectorizer.transform(texts[validation])
        # DF from training nonzeros independently verifies the training-only IDF.
        df = np.asarray(x_train.getnnz(axis=0)).ravel()
        np.testing.assert_allclose(vectorizer.idf_, np.log((1+len(train))/(1+df))+1)
        assert (df >= 5).all() and (df <= .95*len(train)).all()
        assert vectorizer.vocabulary_ == vocab_before
        np.testing.assert_array_equal(vectorizer.idf_, idf_before)
        nmf, topics_train, nmf_fit = fit_nmf(x_train)
        components_before = nmf.components_.copy()
        topics_validation, nmf_transform = transform_nmf(nmf, x_validation)
        np.testing.assert_array_equal(nmf.components_, components_before)
        empty_train = x_train.getnnz(axis=1) == 0
        empty_validation = x_validation.getnnz(axis=1) == 0
        assert np.allclose(topics_train[empty_train], 0) and np.allclose(topics_validation[empty_validation], 0)
        empty_oof[validation] = empty_validation
        info = dict(fold=fold, train_n=len(train), train_positive=int(y[train].sum()),
            validation_n=len(validation), validation_positive=int(y[validation].sum()),
            train_prevalence=float(y[train].mean()), validation_prevalence=float(y[validation].mean()),
            train_groups=len(set(groups[train])), validation_groups=len(set(groups[validation])), group_overlap=0,
            fit_ids_sha256=fingerprint(ids[train].tolist()), validation_ids_sha256=fingerprint(ids[validation].tolist()),
            vocabulary=len(vectorizer.vocabulary_), vocabulary_sha256=fingerprint(sorted(vectorizer.vocabulary_)),
            nmf_fit=nmf_fit, nmf_transform=nmf_transform, empty_train=int(empty_train.sum()),
            empty_validation=int(empty_validation.sum()), logistic={})
        dummy = DummyClassifier(strategy='prior').fit(np.zeros((len(train), 1)), y[train])
        oof['Dummy'][validation] = dummy.predict_proba(np.zeros((len(validation), 1)))[:, 1]
        assert np.allclose(oof['Dummy'][validation], y[train].mean())
        inputs = {'Audio': (audio[train], audio[validation]),
                  'Topics': (topics_train, topics_validation),
                  'Audio + topics': (np.column_stack([audio[train], topics_train]),
                                     np.column_stack([audio[validation], topics_validation]))}
        for name, (training_inputs, heldout_inputs) in inputs.items():
            assert training_inputs.shape[1] == (20 if name == 'Audio + topics' else 10)
            pipeline = classifier()
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter('always')
                pipeline.fit(training_inputs, y[train])
            imputer, scaler, model = pipeline.steps[0][1], pipeline.steps[1][1], pipeline.steps[2][1]
            medians = np.nanmedian(training_inputs, axis=0)
            medians[np.isnan(medians)] = 0
            np.testing.assert_allclose(imputer.statistics_, medians)
            assert scaler.n_samples_seen_ == len(train)
            assert model.n_features_in_ == training_inputs.shape[1]
            scaler_before = scaler.mean_.copy()
            oof[name][validation] = pipeline.predict_proba(heldout_inputs)[:, 1]
            np.testing.assert_array_equal(scaler.mean_, scaler_before)
            info['logistic'][name] = dict(iterations=model.n_iter_.tolist(),
                converged=not any(issubclass(w.category, ConvergenceWarning) for w in captured),
                warnings=[str(w.message) for w in captured])
        for name in MODELS:
            scores.append(dict(fold=fold, model=name,
                ap=float(average_precision_score(y[validation], oof[name][validation])),
                roc_auc=float(roc_auc_score(y[validation], oof[name][validation]))))
        folds.append(info)
        print(f'Fold {fold}/5: train={len(train)}, validation={len(validation)}, vocab={x_train.shape[1]}, '
              f'NMF iterations={nmf.n_iter_}, empty validation={empty_validation.sum()}', flush=True)
    assert (assigned_fold > 0).all()
    for probabilities in oof.values():
        assert np.isfinite(probabilities).all() and ((probabilities >= 0) & (probabilities <= 1)).all()
    assert len(set(assigned_fold[np.isin(ids, [4480, 4481])])) == 1
    prediction_frame = frame.select('billboard_source_row', 'top10').with_columns(
        pl.Series('evaluation_group', groups), pl.Series('validation_fold', assigned_fold),
        pl.Series('empty_text_vector', empty_oof),
        *[pl.Series(name.lower().replace(' + ', '_plus_').replace(' ', '_') + '_probability', oof[name]) for name in MODELS])
    prediction_frame.write_csv(PRIVATE / 'out_of_fold_predictions.csv')
    saved_predictions = pl.read_csv(PRIVATE / 'out_of_fold_predictions.csv')
    np.testing.assert_array_equal(saved_predictions['billboard_source_row'].to_numpy(), ids)
    np.testing.assert_array_equal(saved_predictions['top10'].to_numpy(), y)
    for name in MODELS:
        column = name.lower().replace(' + ', '_plus_').replace(' ', '_') + '_probability'
        np.testing.assert_allclose(saved_predictions[column].to_numpy(), oof[name], rtol=1e-14)
    print('Validation complete. Fitting separate all-data descriptive topics.', flush=True)
    descriptive_vectorizer = new_vectorizer()
    x_all = descriptive_vectorizer.fit_transform(texts)
    descriptive_nmf, weights, descriptive_attempts = fit_nmf(x_all)
    vocabulary = descriptive_vectorizer.get_feature_names_out()
    topics, topic_rows = [], []
    metadata = frame.select('billboard_source_row', 'Song').to_dicts()
    for component in range(10):
        indices = np.argsort(-descriptive_nmf.components_[component], kind='stable')[:15]
        representative_indices = sorted(range(len(ids)), key=lambda i: (-weights[i, component], int(ids[i])))[:3]
        representatives = [dict(id=int(ids[i]), title=metadata[i]['Song'], weight=float(weights[i, component])) for i in representative_indices]
        topic = dict(topic=component+1, terms=vocabulary[indices].tolist(),
                     term_weights=descriptive_nmf.components_[component, indices].tolist(), representatives=representatives,
                     label=topic_label(vocabulary[indices].tolist()))
        topics.append(topic)
        for rank, (term, value) in enumerate(zip(topic['terms'], topic['term_weights']), 1):
            topic_rows.append(dict(topic=component+1, term_rank=rank, term=term, loading=value,
                representative_ids='; '.join(str(r['id']) for r in representatives),
                representative_titles='; '.join(r['title'] for r in representatives)))
    pl.DataFrame(topic_rows).write_csv(PRIVATE / 'descriptive_topics.csv')
    joblib.dump(dict(vectorizer=descriptive_vectorizer, nmf=descriptive_nmf,
                     stopwords=STOPWORDS, training_ids=ids, weights=weights), PRIVATE / 'descriptive_model.joblib')
    rng = np.random.default_rng(42)
    sample_indices = np.sort(np.concatenate([rng.choice(np.flatnonzero(y == 1), 4, replace=False),
                                             rng.choice(np.flatnonzero(y == 0), 21, replace=False)]))
    sample_columns = ['billboard_source_row','lyric_representative_spotify_id','Song','Artist','first_chart_date',
                     'peak_rank','top10','artist_norm','lyric_language','lyric_language_score',
                     'lyric_language_uncertain','lyric_language_mixed_candidate','lyric_language_short',
                     'lyric_full_block_repeats','full_block_dedup_status','full_block_dedup_applied',
                     'lyric_encoding_review','lyric_near_duplicate_candidate','lyric_resolution_confidence',
                     'audio_resolution_confidence','any_missing_audio_value',*AUDIO]
    sample = frame[sample_indices].select(sample_columns).with_columns(
        pl.Series('evaluation_group', groups[sample_indices]), pl.Series('validation_fold', assigned_fold[sample_indices]))
    assert sample.select(sample_columns).equals(frame[sample_indices].select(sample_columns))
    assert not any(c in sample.columns for c in ['lyrics', 'lyrics_clean', TEXT, 'lyrics_compare_norm'])
    sample.write_csv(SAMPLE)
    means = {name: {metric: float(np.mean([r[metric] for r in scores if r['model'] == name]))
                    for metric in ['ap','roc_auc']} for name in MODELS}
    differences = [next(r['ap'] for r in scores if r['fold'] == fold and r['model'] == 'Audio + topics') -
                   next(r['ap'] for r in scores if r['fold'] == fold and r['model'] == 'Audio') for fold in range(1, 6)]
    result = dict(source_records=source.height, eligible=frame.height, excluded_language=source.height-frame.height,
        positive=int(y.sum()), negative=int((1-y).sum()), prevalence=float(y.mean()),
        gap_removed=frame.filter(pl.col('peak_rank').is_between(11,15)).height,
        gap_remaining=frame.filter(~pl.col('peak_rank').is_between(11,15)).height,
        sample_flags={c:int(frame[c].sum()) for c in ['lyric_language_uncertain','lyric_language_mixed_candidate',
            'lyric_language_short','lyric_encoding_review','lyric_near_duplicate_candidate','full_block_dedup_applied']},
        missing_audio_cells=int(np.isnan(audio).sum()), missing_audio_records=int(np.isnan(audio).any(axis=1).sum()),
        missing_audio_by_column={c:int(np.isnan(audio[:,i]).sum()) for i,c in enumerate(AUDIO)},
        groups=len(group_sizes), group_merge_counts=merge_counts,
        group_size_summary=[float(x) for x in [group_sizes.min(),np.median(group_sizes),np.quantile(group_sizes,.95),group_sizes.max()]],
        singleton_groups=int((group_sizes==1).sum()), largest_group_share=float(group_sizes.max()/len(y)),
        folds=folds, fold_scores=scores, model_means=means, paired_ap_differences=differences,
        descriptive_vocabulary=len(vocabulary), descriptive_empty=int((x_all.getnnz(axis=1)==0).sum()),
        descriptive_nmf=descriptive_attempts, topics=topics,
        logistic_nonconverged=sum(not c['converged'] for f in folds for c in f['logistic'].values()),
        source_sha256=source_hash, audit_sha256=audit_hash, script_sha256=sha(Path(__file__)), lock_sha256=sha(ROOT/'uv.lock'),
        sklearn_version=sklearn.__version__, stopwords=STOPWORDS, stopwords_sha256=fingerprint(STOPWORDS),
        audio_predictor_whitelist=AUDIO, topic_predictors=[f'fold_fitted_nmf_{i+1}' for i in range(10)])
    result['sample_flags']['full-block flagged'] = frame.filter(pl.col('lyric_full_block_repeats') > 1).height
    result['sample_flags']['unresolved full-block flags retained'] = frame.filter(
        (pl.col('lyric_full_block_repeats') > 1) & ~pl.col('full_block_dedup_applied')).height
    figures(scores, topics)
    assert sha(SOURCE) == source_hash and sha(AUDIT) == audit_hash
    (PRIVATE / 'run_manifest.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    write_report(result, scores, topics)
    print(json.dumps(dict(sample=frame.height, positive=int(y.sum()), means=means,
                          paired_ap_differences=differences, checks='passed'), indent=2), flush=True)


def render_saved_results():
    """Recheck saved outputs and update presentation only; no models are refitted."""
    result = json.loads((PRIVATE / 'run_manifest.json').read_text(encoding='utf-8'))
    assert sha(SOURCE) == result['source_sha256'] and sha(AUDIT) == result['audit_sha256']
    source = pl.read_parquet(SOURCE).filter(pl.col('lyric_language') == 'en')
    predictions = pl.read_csv(PRIVATE / 'out_of_fold_predictions.csv')
    assert predictions.height == source.height == result['eligible']
    assert predictions['billboard_source_row'].to_list() == source['billboard_source_row'].to_list()
    assert predictions['top10'].to_list() == source['top10'].to_list()
    assert predictions.group_by('evaluation_group').agg(pl.col('validation_fold').n_unique())['validation_fold'].max() == 1
    for score in result['fold_scores']:
        rows = predictions.filter(pl.col('validation_fold') == score['fold'])
        column = score['model'].lower().replace(' + ', '_plus_').replace(' ', '_') + '_probability'
        assert np.isclose(average_precision_score(rows['top10'], rows[column]), score['ap'])
        assert np.isclose(roc_auc_score(rows['top10'], rows[column]), score['roc_auc'])
    sample = pl.read_csv(SAMPLE)
    assert sample.height == 25 and sample['billboard_source_row'].n_unique() == 25
    assert sample['top10'].sum() == 4
    assert not any(c in sample.columns for c in ['lyrics', 'lyrics_clean', TEXT, 'lyrics_compare_norm'])
    for topic in result['topics']:
        topic['label'] = topic_label(topic['terms'])
    result['presentation_script_sha256'] = sha(Path(__file__))
    result['saved_output_checks'] = 'passed: OOF row alignment, groups, all saved AP/AUC scores, sample size/class/privacy'
    (PRIVATE / 'run_manifest.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    figures(result['fold_scores'], result['topics'])
    write_report(result, result['fold_scores'], result['topics'])
    print('Saved output checks passed; figures/report refreshed without refitting.', flush=True)


if __name__ == '__main__':
    # Avoid small BLAS operations spawning excessive threads; this does not alter settings.
    with threadpool_limits(limits=2):
        if '--render-only' in sys.argv:
            render_saved_results()
        else:
            main()
