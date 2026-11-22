"""Analysis 1: frozen grouped comparisons, cumulative sentiment and diagnostics.

Single entry point. Requires explicit immutable v2/v3 paths and NEW output.
Use --verify OUTPUT to check saved results without fitting. No public writes.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
from importlib.metadata import version
import json
from pathlib import Path
import pickle
import shutil
import subprocess
import warnings

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from scipy.stats import spearmanr
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import average_precision_score, confusion_matrix
from threadpoolctl import threadpool_limits
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import vaderSentiment.vaderSentiment as vader_module
from music_success_nlp.cumulative_sentiment import measure, trajectory

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stage14', ROOT/'src/14_preprocessing_ii_analysis.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
ID = m.ID
AUDIO = m.old.AUDIO
SIMPLE = ['p2_log_word_count', 'p2_line_repetition', 'p2_sentiment']
NUMERIC = AUDIO + SIMPLE + ['cumulative_mean_sd']
REF = ['Audio', 'Audio + simple lyrics', 'Audio + simple lyrics + NMF']
NEW = ['Audio + simple lyrics + cumulative SD', 'Audio + simple lyrics + cumulative SD + NMF']
ABL = ['Without ' + col for col in SIMPLE]
COUNTS = dict(zip(REF + NEW + ABL, [10, 13, 23, 14, 24, 12, 12, 12]))


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=True), encoding='utf-8')


def snapshot(path):
    return {p.relative_to(path).as_posix(): m.old.sha(p) for p in sorted(path.rglob('*')) if p.is_file()}


def frozen_check(base, pca, source):
    """Explicit source override supports relocation without editing old evidence."""
    manifest = json.loads((base/'run_manifest.json').read_text())
    assert m.old.sha(source) == manifest['source_sha256']
    master = pl.read_parquet(base/'master.parquet')
    original = pl.read_parquet(source)
    assert master.select(original.columns).equals(original)
    assert master.height == manifest['master_n']
    assert dict(Counter(master['p2_decision'])) == manifest['decisions']
    assert master['p2_text_changed'].sum() == manifest['changed_since_stage11']
    assert master['p2_words_removed'].sum() == manifest['words_removed_since_stage11']
    assert pl.read_csv(base/'decision_audit.csv')[ID].to_list() == master[ID].to_list()
    sample = pl.read_parquet(base/'submission/cleaned_sample.parquet')
    assert sample.height == manifest['sample_n']
    assert sample.equals(master.filter(pl.col(ID).is_in(sample[ID].to_list())).select(sample.columns))
    for rel, digest in manifest['code_sha256'].items():
        assert m.old.sha(base/'submission/code'/rel) == digest
        assert m.old.sha(ROOT/rel) == digest, ('dependency changed', rel)
    for package, expected in manifest['software'].items():
        assert version(package) == expected, package
    assert m.old.sha(Path(vader_module.__file__).parent/'vader_lexicon.txt') == manifest['lexicon_sha256']
    assert m.old.sha(base/'configuration.json') == manifest['configuration_sha256']
    frame = master.filter('p2_eligible')
    assert frame[ID].to_list() == original.filter(pl.col('lyric_language') == 'en')[ID].to_list()
    assert frame[ID].to_list() == pl.read_csv(base/'eligible_ids.csv')[ID].to_list()
    assignments = pl.read_csv(base/'fold_assignments.csv')
    assert frame.select(ID, 'top10').equals(assignments.select(ID, 'top10'))
    np.testing.assert_array_equal(frame['top10'], frame['peak_rank'].to_numpy() <= 10)
    predictions = pl.read_csv(base/'predictions.csv')
    check_predictions(predictions, pl.read_csv(base/'fold_metrics.csv'), assignments)
    pca_manifest = json.loads((pca/'run_manifest.json').read_text())
    # Older snapshots use Windows separators; normalize keys only, never digests.
    assert snapshot(base) == {k.replace('\\', '/'): v for k, v in pca_manifest['base_tree_sha256'].items()}
    pca_predictions = pl.read_csv(pca/'predictions.csv')
    assert pca_predictions.filter(~pl.col('model').is_in(['PCA', 'Audio + PCA'])).equals(predictions)
    check_predictions(pca_predictions, pl.read_csv(pca/'submission/fold_metrics.csv'), assignments)
    for rel, digest in pca_manifest['extension_code_sha256'].items():
        assert m.old.sha(pca/'submission/code'/rel) == digest
    return master, frame, assignments, manifest


def check_predictions(predictions, scores, assignments):
    for name in predictions['model'].unique():
        rows = predictions.filter(pl.col('model') == name)
        assert rows.select(assignments.columns).equals(assignments)
        assert rows[ID].n_unique() == assignments.height
        assert rows.group_by('group').agg(pl.col('fold').n_unique())['fold'].max() == 1
        p = rows['probability'].to_numpy()
        assert np.isfinite(p).all() and ((p >= 0) & (p <= 1)).all()
        for fold in range(1, 6):
            r = rows.filter(pl.col('fold') == fold)
            expected = scores.filter((pl.col('model') == name) & (pl.col('fold') == fold)).row(0, named=True)
            for key, value in m.metrics(r['top10'].to_numpy(), r['probability'].to_numpy()).items():
                assert np.isclose(value, expected[key], atol=1e-12, rtol=1e-12)


def fit(a, y):
    attempts = []
    for limit in [2000, 4000]:
        model = m.old.classifier()
        model.steps[-1][1].set_params(max_iter=limit)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            model.fit(a, y)
        converged = not any(issubclass(w.category, ConvergenceWarning) for w in caught)
        attempts.append(dict(limit=limit, converged=converged, warnings=[str(w.message) for w in caught]))
        if converged:
            break
    assert converged, 'Classifier did not converge; no silent acceptance'
    imputer, scaler, _ = [s[1] for s in model.steps]
    medians = np.nanmedian(a, axis=0)
    medians[np.isnan(medians)] = 0
    np.testing.assert_allclose(imputer.statistics_, medians)
    assert scaler.n_samples_seen_ == len(y)
    return model, attempts


def permutation(model, x, y, fold):
    """Shuffle raw numeric columns, before the fitted imputer/scaler; no refit."""
    frozen_x = x.copy()
    model_bytes = pickle.dumps(model)
    baseline = average_precision_score(y, model.predict_proba(x)[:, 1])
    rows = []
    for j, name in enumerate(NUMERIC + ['NMF joint (10 columns)']):
        columns = [j] if j < 14 else list(range(14, 24))
        for repeat in range(20):
            seed = 20261121 + fold*10000 + j*100 + repeat
            order = np.random.default_rng(seed).permutation(len(y))
            shuffled = x.copy()
            shuffled[:, columns] = x[order][:, columns]
            score = average_precision_score(y, model.predict_proba(shuffled)[:, 1])
            rows.append(dict(fold=fold, feature=name, repeat=repeat, seed=seed, ap_drop=float(baseline-score)))
    np.testing.assert_array_equal(x, frozen_x)
    assert pickle.dumps(model) == model_bytes
    return rows


def run(args):
    base, pca, out, source = map(lambda p: Path(p).resolve(), [args.base, args.pca, args.output, args.source])
    out.relative_to(ROOT/'data/processed')
    if out.exists():
        raise FileExistsError('Choose a new versioned output; existing runs are immutable')
    before = dict(v2=snapshot(base), v3=snapshot(pca))
    master, frame, assignments, historical_manifest = frozen_check(base, pca, source)
    out.mkdir(parents=True)
    pack = out/'Analysis_1'
    private = pack/'private'
    private.mkdir(parents=True)
    tables = pack/'tables'
    tables.mkdir()
    figures = pack/'figures'
    figures.mkdir()
    analyzer = SentimentIntensityAnalyzer()
    measurements, line_cache = [], []
    for row in master.iter_rows(named=True):
        result, scores, cumulative = measure(row['p2_lyrics_revised'], analyzer)
        if result['status'] == 'ok':
            assert row['p2_sentiment_status'] == 'ok'
            assert np.isclose(result['sentiment_mean'], row['p2_sentiment'], atol=1e-12, rtol=1e-12)
        else:
            assert row['p2_sentiment_status'] != 'ok'
        measurements.append({ID: row[ID], **result})
        line_cache.append({ID: row[ID], 'line_scores': scores, 'cumulative': cumulative})
    measurement = pl.DataFrame(measurements)
    measurement.write_csv(private/'cumulative_measurements.csv')
    dump(private/'line_score_cache.json', line_cache)
    frame = frame.join(measurement.select(ID, 'cumulative_mean_sd'), on=ID, how='left', maintain_order='left')
    assignments.write_csv(private/'fold_assignments.csv')
    y = frame['top10'].to_numpy().astype(int)
    folds, groups = assignments['fold'].to_numpy(), assignments['group'].to_numpy()
    numeric = frame.select(NUMERIC).to_numpy().astype(float)
    numeric[~np.isfinite(numeric)] = np.nan
    texts, ids = frame['p2_lyrics_revised'].to_numpy(), frame[ID].to_numpy()
    historical = pl.read_csv(base/'predictions.csv').filter(pl.col('model').is_in(REF))
    oof = {name: np.full(len(y), np.nan) for name in NEW + ABL}
    logs, permutations, coefficients, intercepts = [], [], [], []
    for fold in range(1, 6):
        train, test = np.flatnonzero(folds != fold), np.flatnonzero(folds == fold)
        assert not set(groups[train]) & set(groups[test])
        v = m.vectorizer()
        xt = v.fit_transform(texts[train])
        vocab, idf = dict(v.vocabulary_), v.idf_.copy()
        xv = v.transform(texts[test])
        assert v.vocabulary_ == vocab
        np.testing.assert_array_equal(v.idf_, idf)
        np.testing.assert_allclose(idf, np.log((1+len(train))/(1+xt.getnnz(axis=0)))+1)
        expected = historical_manifest['fold_details'][fold-1]
        assert expected['fit_ids_sha256'] == m.old.fingerprint(ids[train].tolist())
        assert expected['vocabulary'] == xt.shape[1]
        nmf, nt, nlog = m.old.fit_nmf(xt)
        components = nmf.components_.copy()
        nv, tlog = m.old.transform_nmf(nmf, xv)
        np.testing.assert_array_equal(components, nmf.components_)
        assert nlog[-1]['converged'] and tlog[-1]['converged']
        all_train, all_test = np.column_stack([numeric[train], nt]), np.column_stack([numeric[test], nv])
        all_names = NUMERIC + [f'fold_specific_NMF_{i+1}' for i in range(10)]
        models = {}
        for name in NEW + ABL:
            cols = list(range(14)) if name == NEW[0] else list(range(24))
            if name in ABL:
                omitted = SIMPLE[ABL.index(name)]
                cols = [i for i in range(13) if NUMERIC[i] != omitted]
                assert omitted not in [all_names[i] for i in cols]
            a, b = all_train[:, cols], all_test[:, cols]
            assert a.shape[1] == COUNTS[name]
            model, attempts = fit(a, y[train])
            oof[name][test] = model.predict_proba(b)[:, 1]
            lr = model.steps[-1][1]
            coefficients.extend(dict(fold=fold, model=name, feature=all_names[j], standardized_coefficient=float(coef)) for j, coef in zip(cols, lr.coef_[0]))
            intercepts.append(dict(fold=fold, model=name, intercept=float(lr.intercept_[0])))
            models[name] = model
            logs.append(dict(fold=fold, model=name, predictors=[all_names[j] for j in cols], dimensions=len(cols), attempts=attempts, train_n=len(train), training_ids_sha256=expected['fit_ids_sha256']))
            if name == NEW[1]:
                permutations.extend(permutation(model, b, y[test], fold))
        # Save fitted state privately, so verification need not rerun NMF.
        with (private/f'fold_{fold}_models.pkl').open('wb') as handle:
            pickle.dump(dict(vectorizer=v, nmf=nmf, classifiers=models, training_ids=ids[train], test_ids=ids[test], nmf_fit=nlog, nmf_transform=tlog), handle)
        print(f'Fold {fold}/5: new models, retrained ablations, 300 permutations complete', flush=True)
    predictions = pl.concat([historical, *[assignments.with_columns(pl.lit(name).alias('model'), pl.Series('probability', p)).select(historical.columns) for name, p in oof.items()]])
    predictions.write_csv(private/'predictions.csv')
    metrics = []
    pooled = []
    for name in REF + NEW + ABL:
        rows = predictions.filter(pl.col('model') == name)
        pooled.append(dict(model=name, predictors=COUNTS[name], **m.metrics(y, rows['probability'].to_numpy())))
        for fold in range(1, 6):
            r = rows.filter(pl.col('fold') == fold)
            metrics.append(dict(model=name, fold=fold, predictors=COUNTS[name], **m.metrics(r['top10'].to_numpy(), r['probability'].to_numpy())))
    scores = pl.DataFrame(metrics)
    scores.write_csv(tables/'fold_metrics.csv')
    means = scores.group_by('model', maintain_order=True).agg(pl.col('predictors').first(), *[pl.col(c).mean() for c in m.metrics(y, np.zeros(len(y)))])
    means.write_csv(tables/'model_means.csv')
    pl.DataFrame(pooled).write_csv(tables/'pooled_metrics.csv')
    contrasts = [(REF[1], REF[0]), (REF[2], REF[1]), (NEW[0], REF[1]), (NEW[1], REF[2])] + [(REF[1], name) for name in ABL]
    paired = []
    for a, b in contrasts:
        for fold in range(1, 6):
            ra = scores.filter((pl.col('model') == a) & (pl.col('fold') == fold)).row(0, named=True)
            rb = scores.filter((pl.col('model') == b) & (pl.col('fold') == fold)).row(0, named=True)
            paired.append(dict(comparison=a+' minus '+b, fold=fold, ap_difference=ra['ap']-rb['ap'], roc_auc_difference=ra['roc_auc']-rb['roc_auc']))
    pl.DataFrame(paired).write_csv(tables/'paired_differences.csv')
    pl.DataFrame(paired).group_by('comparison', maintain_order=True).agg(pl.col('ap_difference').mean(), pl.col('roc_auc_difference').mean()).write_csv(tables/'paired_means.csv')
    perm = pl.DataFrame(permutations)
    perm.write_csv(tables/'permutation_repeats.csv')
    perm.group_by('feature', maintain_order=True).agg(pl.col('ap_drop').mean(), pl.col('ap_drop').std(ddof=0).alias('shuffle_and_fold_sd')).write_csv(tables/'permutation_summary.csv')
    perm.group_by('feature', 'fold', maintain_order=True).agg(pl.col('ap_drop').mean(), pl.col('ap_drop').std(ddof=0).alias('shuffle_sd')).write_csv(tables/'permutation_by_fold.csv')
    pl.DataFrame(coefficients).write_csv(tables/'coefficients.csv')
    pl.DataFrame(intercepts).write_csv(tables/'intercepts.csv')
    dump(private/'fit_log.json', logs)
    diagnostics(frame, predictions, numeric, line_cache, tables, private, figures, means, perm)
    # Reuse the specific historical all-data descriptive fit; no additional fit.
    components = json.loads((base/'submission/descriptive_components.json').read_text())
    dump(private/'descriptive_components.json', [c for c in components if c['method'] == 'NMF'])
    examples = json.loads((base/'private_component_examples.json').read_text())
    dump(private/'component_examples.json', [e for e in examples if e['method'] == 'NMF'])
    assert snapshot(base) == before['v2'] and snapshot(pca) == before['v3']
    code_files = ['src/17_analysis_1.py', 'src/18_analysis_1_report.py', 'src/music_success_nlp/analysis_delivery.py', 'src/music_success_nlp/cumulative_sentiment.py', 'tests/test_analysis_1.py', 'tests/test_analysis_delivery.py', 'tests/test_preprocessing_ii.py', 'src/14_preprocessing_ii_analysis.py', 'src/12_topics_and_top10_prediction.py', 'src/music_success_nlp/preprocessing_ii.py', 'src/music_success_nlp/__init__.py', 'README.md', 'pyproject.toml', 'uv.lock', '.python-version', '.gitignore']
    for rel in code_files:
        dst = pack/'code'/rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/rel, dst)
    manifest = dict(base=str(base), pca=str(pca), source=str(source), frozen_trees=before,
        master_n=master.height, eligible_n=len(y), positive=int(y.sum()), measurement_status=dict(Counter(measurement['status'])),
        group_count=len(set(groups)), group_sizes=dict(min=min(Counter(groups).values()), median=float(np.median(list(Counter(groups).values()))), max=max(Counter(groups).values())),
        software=historical_manifest['software'], lexicon_sha256=historical_manifest['lexicon_sha256'],
        source_sha256=m.old.sha(source), configuration_sha256=m.old.sha(base/'configuration.json'),
        coefficients_note='standardized coefficients; NMF axes specific to each fold; intercept separate',
        permutation_repeats=20, permutation_seed_formula='20261121 + fold*10000 + feature_index*100 + repeat',
        code_sha256={rel: m.old.sha(ROOT/rel) for rel in code_files},
        measurement_definition='word-weighted cumulative line means; population SD, equal endpoint weights',
        primary_metric='equal-fold mean AP', threshold=.5, historical_predictions_reused=REF,
        missing_numeric_cells=int(np.isnan(numeric).sum()))
    dump(out/'run_manifest.json', manifest)
    dump(out/'output_hashes.json', snapshot(pack))
    verify(out)
    # CSV is plain text and works on Windows consoles without box-drawing glyphs.
    print(means.write_csv(), flush=True)


def diagnostics(frame, predictions, numeric, line_cache, tables, private, figures, means, perm):
    pairs = []
    matrix = np.eye(14)
    counts = np.zeros((14, 14), int)
    for i, a in enumerate(NUMERIC):
        for j, b in enumerate(NUMERIC):
            valid = np.isfinite(numeric[:, i]) & np.isfinite(numeric[:, j])
            counts[i, j] = int(valid.sum())
            matrix[i, j] = spearmanr(numeric[valid, i], numeric[valid, j]).statistic
            if i < j:
                pairs.append(dict(feature_a=a, feature_b=b, rho=float(matrix[i, j]), pair_n=int(valid.sum())))
    pl.DataFrame({'feature': NUMERIC, **{c: matrix[:, j] for j, c in enumerate(NUMERIC)}}).write_csv(tables/'spearman_matrix.csv')
    pl.DataFrame({'feature': NUMERIC, **{c: counts[:, j] for j, c in enumerate(NUMERIC)}}).write_csv(tables/'spearman_pair_counts.csv')
    pl.DataFrame(pairs).with_columns(pl.col('rho').abs().alias('absolute_rho')).sort('absolute_rho', descending=True).write_csv(tables/'correlation_pairs.csv')
    distribution = []
    for target in [0, 1]:
        z = frame.filter(pl.col('top10') == target)['cumulative_mean_sd'].drop_nulls().to_numpy()
        distribution.append(dict(top10=target, n=len(z), mean=float(z.mean()), median=float(np.median(z)), p25=float(np.quantile(z, .25)), p75=float(np.quantile(z, .75))))
    pl.DataFrame(distribution).write_csv(tables/'cumulative_distribution.csv')
    confusions, summary, reviews = [], [], []
    audit = [c for c in frame.columns if c.startswith('lyric_') and any(k in c for k in ['review', 'uncertain', 'mixed_candidate', 'short', 'extreme', 'near_duplicate'])]
    audit += ['full_block_dedup_applied', 'p2_decision', 'lyric_resolution_confidence', 'audio_resolution_confidence']
    for name in [REF[2], NEW[1]]:
        rows = predictions.filter(pl.col('model') == name).join(frame.select(ID, 'Song', 'Artist', 'peak_rank', *NUMERIC, *audit, 'p2_lyrics_revised'), on=ID, maintain_order='left')
        rows = rows.with_columns(pl.when((pl.col('top10') == 1) & (pl.col('probability') >= .5)).then(pl.lit('TP')).when((pl.col('top10') == 0) & (pl.col('probability') >= .5)).then(pl.lit('FP')).when(pl.col('top10') == 1).then(pl.lit('FN')).otherwise(pl.lit('TN')).alias('category'))
        tn, fp, fn, tp = confusion_matrix(rows['top10'], rows['probability'].to_numpy() >= .5, labels=[0, 1]).ravel()
        fps = rows.filter(pl.col('category') == 'FP')
        confusions.append(dict(model=name, TP=int(tp), FP=int(fp), TN=int(tn), FN=int(fn), fp_peak_11_20=fps.filter(pl.col('peak_rank') <= 20).height, fp_peak_21_100=fps.filter(pl.col('peak_rank') > 20).height, **m.metrics(rows['top10'].to_numpy(), rows['probability'].to_numpy())))
        for category in ['FP', 'FN', 'TP', 'TN']:
            r = rows.filter(pl.col('category') == category)
            sizes = list(Counter(r['group']).values())
            for feature in NUMERIC:
                z = r[feature].drop_nulls().to_numpy()
                summary.append(dict(model=name, category=category, n=r.height, groups=r['group'].n_unique(), max_records_per_group=max(sizes) if sizes else 0, feature=feature, median=float(np.median(z)) if len(z) else None, p25=float(np.quantile(z, .25)) if len(z) else None, p75=float(np.quantile(z, .75)) if len(z) else None))
            selected = r.sort(['probability', ID], descending=[category in ['FP', 'TP'], False]).head(5)
            reviews.append(selected)
    pl.concat(reviews).drop('p2_lyrics_revised').write_csv(private/'error_review_cases.csv')
    pl.concat(reviews).write_json(private/'error_review_with_lyrics.json')
    pl.DataFrame(confusions).write_csv(tables/'confusion_metrics.csv')
    pl.DataFrame(summary).write_csv(tables/'error_category_features.csv')
    plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, ax = plt.subplots(figsize=(10, 5), layout='constrained')
    selected_means = means.filter(pl.col('model').is_in(REF + NEW))
    ax.barh(selected_means['model'].to_list(), selected_means['ap'].to_list())
    ax.invert_yaxis(); ax.set_xlabel('Average precision: equal-fold mean'); ax.set_title('Fixed grouped comparisons (not significance tests)')
    for i, value in enumerate(selected_means['ap']): ax.text(value+.002, i, f'{value:.4f}', va='center')
    ax.set_xlim(0, .35); fig.savefig(figures/'01_model_ap.png', dpi=180); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    for target in [0, 1]:
        z = np.sort(frame.filter(pl.col('top10') == target)['cumulative_mean_sd'].drop_nulls().to_numpy())
        axes[0].step(z, np.arange(1, len(z)+1)/len(z), label=f'Top-10={target}, n={len(z)}')
    axes[0].set(xlabel='Cumulative mean SD', ylabel='Empirical cumulative fraction', title='Observed distribution'); axes[0].legend()
    for s in [[1, -1, 0], [0, -1, 1], [0, 0, 0]]:
        c, mean, sd = trajectory(s, [1, 1, 1])
        axes[1].plot([0, .5, 1], c, marker='o', label=f'{s}: final={mean:.1f}, SD={sd:.3f}')
    axes[1].set(xlabel='Normalized nonblank line position', ylabel='Cumulative weighted mean', title='Synthetic illustrations; equal line weights'); axes[1].legend(fontsize=7)
    fig.savefig(figures/'02_sentiment.png', dpi=180); plt.close(fig)
    ps = perm.group_by('feature').agg(pl.col('ap_drop').mean()).sort('ap_drop')
    fig, ax = plt.subplots(figsize=(9, 6), layout='constrained')
    ax.barh(ps['feature'].to_list(), ps['ap_drop'].to_list()); ax.axvline(0, color='black', linewidth=.8)
    ax.set(xlabel='AP(original) - AP(permuted), mean over folds and 20 shuffles', title='Prespecified 24-predictor model: held-out reliance')
    fig.savefig(figures/'03_permutation.png', dpi=180); plt.close(fig)
    fig, ax = plt.subplots(figsize=(11, 9), layout='constrained')
    image = ax.imshow(matrix, vmin=-1, vmax=1, cmap='coolwarm')
    ax.set_xticks(range(14), NUMERIC, rotation=70, ha='right'); ax.set_yticks(range(14), NUMERIC)
    ax.set_title('Descriptive Spearman correlations; eligible sample, pairwise complete')
    fig.colorbar(image, ax=ax, label='Spearman rho'); fig.savefig(figures/'04_correlations.png', dpi=180); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout='constrained')
    for ax, row in zip(axes, confusions):
        data = np.array([[row['TN'], row['FP']], [row['FN'], row['TP']]])
        ax.imshow(data, cmap='Blues')
        for i in range(2):
            for j in range(2): ax.text(j, i, str(data[i, j]), ha='center', va='center', color='white' if data[i, j] > data.max()/2 else 'black', fontsize=15)
        ax.set(xticks=[0, 1], yticks=[0, 1], xlabel='Predicted Top-10', ylabel='Actual Top-10', title=('Historical 23 predictors' if row['model'] == REF[2] else 'New 24 predictors')+'; threshold 0.5')
    fig.savefig(figures/'05_errors.png', dpi=180); plt.close(fig)
    # Deterministic private actual trajectories: smallest ID within each outcome
    # at lowest/highest dispersion. Feature uses original endpoints, not this axis.
    chosen = set()
    for target in [0, 1]:
        r = frame.filter(pl.col('top10') == target)
        for descending in [False, True]:
            chosen.add(r.sort(['cumulative_mean_sd', ID], descending=[descending, False])[ID][0])
    cache = {r[ID]: r for r in line_cache}
    fig, ax = plt.subplots(figsize=(9, 4), layout='constrained')
    for i in sorted(chosen):
        c = cache[i]['cumulative']; row = frame.filter(pl.col(ID) == i).row(0, named=True)
        ax.plot(np.linspace(0, 1, len(c)), c, label=f'ID {i}: {row["Song"]}; SD={row["cumulative_mean_sd"]:.3f}')
    ax.legend(fontsize=7); ax.set(xlabel='Normalized original nonblank line position', ylabel='Cumulative mean', title='Private deterministic extreme examples; not representative')
    fig.savefig(private/'actual_trajectories.png', dpi=180); plt.close(fig)
    frame.filter(pl.col(ID).is_in(sorted(chosen))).select(ID, 'Song', 'Artist', 'top10', 'cumulative_mean_sd', 'p2_lyrics_revised').write_json(private/'actual_trajectory_examples.json')


def verify(out, base_override=None, pca_override=None):
    out = Path(out)
    manifest = json.loads((out/'run_manifest.json').read_text())
    for key, override in [('v2', base_override), ('v3', pca_override)]:
        path = Path(override or manifest['base' if key == 'v2' else 'pca'])
        assert snapshot(path) == manifest['frozen_trees'][key], f'{key} tree changed'
    pack, private = out/'Analysis_1', out/'Analysis_1/private'
    for rel, digest in json.loads((out/'output_hashes.json').read_text()).items():
        assert m.old.sha(pack/rel) == digest, rel
    for rel, digest in manifest['code_sha256'].items():
        assert m.old.sha(pack/'code'/rel) == digest
    # If packaging was completed after execution, retain and check the exact
    # executed code and original evidence hashes, separately from delivery code.
    if (out/'execution_output_hashes.json').exists():
        for rel, digest in json.loads((out/'execution_output_hashes.json').read_text()).items():
            path = private/'executed_code'/rel.removeprefix('code/') if rel.startswith('code/') else pack/rel
            assert m.old.sha(path) == digest, ('executed evidence changed', rel)
    predictions = pl.read_csv(private/'predictions.csv')
    scores = pl.read_csv(pack/'tables/fold_metrics.csv')
    assignments = pl.read_csv(private/'fold_assignments.csv')
    check_predictions(predictions, scores, assignments)
    base = Path(base_override or manifest['base'])
    assert predictions.filter(pl.col('model').is_in(REF)).equals(pl.read_csv(base/'predictions.csv').filter(pl.col('model').is_in(REF)))
    for row in pl.read_csv(pack/'tables/confusion_metrics.csv').iter_rows(named=True):
        r = predictions.filter(pl.col('model') == row['model'])
        tn, fp, fn, tp = confusion_matrix(r['top10'], r['probability'].to_numpy() >= .5, labels=[0, 1]).ravel()
        assert [tn, fp, fn, tp] == [row[k] for k in ['TN', 'FP', 'FN', 'TP']]
    for table in ['model_means.csv', 'pooled_metrics.csv']:
        for row in pl.read_csv(pack/'tables'/table).iter_rows(named=True):
            r = predictions.filter(pl.col('model') == row['model'])
            actual = m.metrics(r['top10'].to_numpy(), r['probability'].to_numpy()) if table.startswith('pooled') else {k: scores.filter(pl.col('model') == row['model'])[k].mean() for k in m.metrics(r['top10'].to_numpy(), r['probability'].to_numpy())}
            for k, v in actual.items(): assert np.isclose(v, row[k], atol=1e-12, rtol=1e-12)
    for rel in ['private/predictions.csv', 'private/error_review_with_lyrics.json', 'private/component_examples.json']:
        result = subprocess.run(['git', 'check-ignore', str(pack/rel)], cwd=ROOT, capture_output=True)
        assert result.returncode == 0, f'Private output not ignored: {rel}'
    dump(out/'verification.json', dict(passed=True, checks=['frozen v2/v3 hashes', 'output/code hashes', 'reference prediction identity', 'IDs/targets/folds/groups', 'finite probabilities', 'fold and pooled metrics', 'equal-fold means', 'confusion counts', 'Git ignore'], runtime_checks=['terminal cumulative equality for all scored records', 'training-only vocabulary/IDF/NMF/imputation/scaling', 'no group overlap', 'ablation feature removal and independent refit', 'permutation input/model immutability']))
    print('Analysis 1 saved-data verification PASSED', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path)
    parser.add_argument('--pca', type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--verify', type=Path)
    args = parser.parse_args()
    with threadpool_limits(limits=2):
        if args.verify:
            verify(args.verify, args.base, args.pca)
        else:
            if not all([args.base, args.pca, args.source, args.output]): parser.error('--base --pca --source --output required')
            run(args)
            # Reporting never refits or changes the measurement/prediction evidence.
            report_spec = importlib.util.spec_from_file_location('analysis_report', ROOT/'src/18_analysis_1_report.py')
            report = importlib.util.module_from_spec(report_spec)
            report_spec.loader.exec_module(report)
            report.render(args.output.resolve())
