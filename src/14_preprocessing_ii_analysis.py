"""Preprocessing II: immutable inputs, frozen population, shared grouped evaluation.

Run with --output NEW_DIRECTORY; an existing run is never overwritten.
Use --verify RUN_DIRECTORY to independently verify saved predictions and samples.
All row-level outputs remain in Git-ignored data/processed/.
"""
import argparse
from collections import Counter, defaultdict
import importlib.util
from importlib.metadata import version
import json
from pathlib import Path
import shutil
import sys
import warnings

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from sklearn.decomposition import TruncatedSVD
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import average_precision_score, roc_auc_score, precision_recall_fscore_support
from sklearn.model_selection import StratifiedGroupKFold
from threadpoolctl import threadpool_limits
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import vaderSentiment.vaderSentiment as vader_module
from music_success_nlp.preprocessing_ii import (prepare, comparison_text, TOKEN_PATTERN, tfidf_preprocessor, normalize_whole_repeat)

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('historical_stage12', ROOT/'src/12_topics_and_top10_prediction.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
ID = 'billboard_source_row'
MODEL_BLOCKS = {
    'Dummy': (), 'Audio': ('audio',), 'Simple lyrics': ('simple',),
    'Audio + simple lyrics': ('audio','simple'), 'NMF': ('nmf',),
    'Audio + NMF': ('audio','nmf'), 'SVD': ('svd',), 'Audio + SVD': ('audio','svd'),
    'Audio + simple lyrics + NMF': ('audio','simple','nmf')}
PRIORITIES = [('Audio + simple lyrics','Audio'), ('Audio + NMF','Audio'),
              ('Audio + SVD','Audio'), ('Audio + simple lyrics + NMF','Audio + NMF')]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True), encoding='utf-8')


def vectorizer():
    return old.new_vectorizer().set_params(token_pattern=TOKEN_PATTERN, preprocessor=tfidf_preprocessor)


def metrics(y, p):
    predicted = p >= .5
    precision, recall, f1, _ = precision_recall_fscore_support(y, predicted, average='binary', zero_division=0)
    return dict(ap=float(average_precision_score(y,p)), roc_auc=float(roc_auc_score(y,p)),
                precision=float(precision), recall=float(recall), f1=float(f1),
                predicted_positive=int(predicted.sum()))


def partition(source, frame, historical):
    """Preserve historical groups, adding only nonblank exact revised-text links."""
    original, _ = old.make_groups(source)
    parent = {g:g for g in original.values()}
    def find(g):
        while parent[g] != g:
            parent[g] = parent[parent[g]]
            g = parent[g]
        return g
    def union(a,b):
        a,b = find(a),find(b)
        parent[max(a,b)] = min(a,b)
    seen, links = {}, []
    hist_folds = dict(historical.select(ID,'validation_fold').iter_rows())
    for r in source.iter_rows(named=True):
        key = comparison_text(r['p2_lyrics_revised'])
        if not key:
            continue
        i = r[ID]
        if key in seen:
            j = seen[key]
            links.append(dict(id_a=j, id_b=i, cross_historical_fold=bool(j in hist_folds and i in hist_folds and hist_folds[j] != hist_folds[i])))
            union(original[i],original[j])
        else:
            seen[key] = i
    groups = np.array([find(original[i]) for i in frame[ID]])
    folds = np.array([hist_folds[i] for i in frame[ID]])
    crossing = any(len(set(folds[groups == g])) > 1 for g in set(groups))
    if crossing:
        for fold, (_, test) in enumerate(StratifiedGroupKFold(5,shuffle=True,random_state=42).split(np.zeros(frame.height),frame['top10'],groups),1):
            folds[test] = fold
    for g in set(groups):
        assert len(set(folds[groups == g])) == 1
    return groups,folds,links,crossing


def verify(run):
    """Recompute every metric from saved private probabilities, not in-memory scores."""
    manifest = json.loads((run/'run_manifest.json').read_text())
    source = pl.read_parquet(manifest['source_path'])
    master = pl.read_parquet(run/'master.parquet')
    assert old.sha(Path(manifest['source_path'])) == manifest['source_sha256']
    assert master.select(source.columns).equals(source)
    assert master.height == manifest['master_n'] and master[ID].n_unique() == master.height
    eligible = master.filter('p2_eligible')
    assert eligible[ID].to_list() == source.filter(pl.col('lyric_language') == 'en')[ID].to_list()
    saved_ids = pl.read_csv(run/'eligible_ids.csv')[ID].to_list()
    assert saved_ids == eligible[ID].to_list()
    p = pl.read_csv(run/'predictions.csv')
    scores = pl.read_csv(run/'fold_metrics.csv')
    for name in MODEL_BLOCKS:
        rows = p.filter(pl.col('model') == name)
        assert rows[ID].to_list() == saved_ids and rows[ID].n_unique() == len(saved_ids)
        assert rows['top10'].to_list() == eligible['top10'].to_list()
        assert rows.group_by('group').agg(pl.col('fold').n_unique())['fold'].max() == 1
        assert rows.select(ID,'group','fold').equals(p.filter(pl.col('model') == 'Dummy').select(ID,'group','fold'))
        for fold in range(1,6):
            subset = rows.filter(pl.col('fold') == fold)
            actual = metrics(subset['top10'].to_numpy(),subset['probability'].to_numpy())
            expected = scores.filter((pl.col('model') == name)&(pl.col('fold') == fold)).row(0,named=True)
            for key,value in actual.items():
                assert np.isclose(value,expected[key],rtol=1e-12,atol=1e-12), (name,fold,key)
    sample = pl.read_parquet(run/'submission/cleaned_sample.parquet')
    assert sample.height == manifest['sample_n']
    assert sample.equals(master.filter(pl.col(ID).is_in(sample[ID].to_list())).select(sample.columns))
    assert dict(Counter(master['p2_decision'])) == manifest['decisions']
    assert [normalize_whole_repeat(t)[3] for t in source['lyrics_clean']] == source['lyric_full_block_repeats'].to_list()
    assert master['p2_text_changed'].sum() == manifest['changed_since_stage11']
    audit = pl.read_csv(run/'decision_audit.csv')
    assert audit.height == master.height and audit[ID].to_list() == master[ID].to_list()
    assert audit['p2_words_removed'].sum() == manifest['words_removed_since_stage11']
    for rel, digest in manifest['code_sha256'].items():
        assert old.sha(run/'submission/code'/rel) == digest
    print('Saved-data verification passed: source preservation, population, shared folds, all metrics, sample, audit, code hashes.',flush=True)


def main(args):
    out = Path(args.output).resolve()
    # Require ignored output under this repository; never overwrite historical runs.
    out.relative_to(ROOT/'data/processed')
    out.mkdir(parents=True,exist_ok=False)
    pack = out/'submission'
    pack.mkdir()
    source_path = Path(args.source).resolve()
    source_hash = old.sha(source_path)
    source = pl.read_parquet(source_path)
    historical_path = ROOT/'data/processed/stage12_modelling/out_of_fold_predictions.csv'
    historical = pl.read_csv(historical_path)
    historical_manifest = json.loads((historical_path.parent/'run_manifest.json').read_text())
    assert historical_manifest['source_sha256'] == source_hash
    analyzer = SentimentIntensityAnalyzer()
    master = prepare(source, analyzer)
    assert master.select(source.columns).equals(source)
    master.write_parquet(out/'master.parquet')
    frame = master.filter('p2_eligible')
    assert frame[ID].to_list() == historical[ID].to_list()
    assert frame['top10'].to_list() == historical['top10'].to_list()
    y = frame['top10'].to_numpy().astype(int)
    np.testing.assert_array_equal(y,(frame['peak_rank'].to_numpy() <= 10).astype(int))
    assert all(isinstance(t,str) and t.strip() for t in frame['p2_lyrics_revised'])
    frame.select(ID).write_csv(out/'eligible_ids.csv')
    historical.write_csv(out/'historical_predictions_preserved.csv')
    audit_columns = [ID,'lyric_full_block_repeats','full_block_dedup_status','p2_decision','p2_reason',
                     'p2_repeat_count','p2_words_before','p2_word_count','p2_words_removed','p2_text_changed','p2_encoding_replacements','p2_eligible']
    master.select(audit_columns).write_csv(out/'decision_audit.csv')
    groups,folds,links,repartitioned = partition(master,frame,historical)
    write_json(out/'exact_duplicate_links.json',links)
    frame.select(ID,'top10').with_columns(pl.Series('group',groups),pl.Series('fold',folds)).write_csv(out/'fold_assignments.csv')
    # Illustrative deterministic coverage sample: smallest IDs for each decision
    # and each historical language/quality flag, plus 8 seeded random records.
    selected = set()
    for decision in sorted(set(master['p2_decision'])):
        selected.update(master.filter(pl.col('p2_decision') == decision).sort(ID).head(3)[ID])
    for flag in ['lyric_language_uncertain','lyric_language_mixed_candidate','lyric_language_short',
                 'lyric_encoding_review','full_block_dedup_applied']:
        selected.update(master.filter(pl.col(flag)).sort(ID).head(2)[ID])
    selected.update(master.filter(~pl.col('p2_eligible')).sort(ID).head(2)[ID])
    selected.update(np.random.default_rng(42).choice(master[ID].to_numpy(),8,replace=False).tolist())
    sample_columns = [ID,'Song','Artist','lyrics','lyrics_clean','p2_lyrics_original','p2_lyrics_revised',
                      'lyric_language','lyric_language_score','lyric_language_uncertain','lyric_language_mixed_candidate',
                      'lyric_encoding_review',*audit_columns[1:],'p2_log_word_count','p2_line_repetition','p2_sentiment','p2_sentiment_status']
    sample = master.filter(pl.col(ID).is_in(sorted(selected))).select(sample_columns)
    sample.write_parquet(pack/'cleaned_sample.parquet')
    sample.write_csv(pack/'cleaned_sample.csv')
    print(f'Preprocessing saved: {master.height} master; {frame.height} eligible; decisions={dict(Counter(master["p2_decision"]))}; changed folds={repartitioned}',flush=True)
    # Freeze feature definitions and settings before inspecting new scores.
    config = dict(audio=old.AUDIO,simple=['p2_log_word_count','p2_line_repetition','p2_sentiment'],
        token_pattern=TOKEN_PATTERN,stopwords=old.STOPWORDS,tfidf=dict(min_df=5,max_df=.95,ngram_range=[1,1],norm='l2',sublinear_tf=False),
        nmf=dict(n_components=10,init='nndsvda',solver='cd',beta_loss='frobenius',tol=1e-4,alpha_W=0,alpha_H=0,max_iter=[500,1000],random_state=42),
        svd=dict(n_components=10,algorithm='randomized',n_iter=7,n_oversamples=10,power_iteration_normalizer='auto',tol=0,random_state=42),
        classifier=dict(C=1,l1_ratio=0,class_weight=None,solver='lbfgs',tol=1e-4,max_iter=[2000,4000],random_state=42),
        sentiment='VADER 3.3.2; whitespace-word-weighted mean nonblank-line compound; all lines; no truncation',threshold=.5,zero_division=0)
    write_json(out/'configuration.json',config)
    audio = frame.select(old.AUDIO).to_numpy().astype(float)
    audio[~np.isfinite(audio)] = np.nan
    simple = frame.select(config['simple']).to_numpy().astype(float)
    texts = frame['p2_lyrics_revised'].to_numpy()
    ids = frame[ID].to_numpy()
    scores, predictions, fit_log, fold_info = [], [], [], []
    oof = {name:np.full(frame.height,np.nan) for name in MODEL_BLOCKS}
    for fold in range(1,6):
        train,test = np.flatnonzero(folds != fold),np.flatnonzero(folds == fold)
        assert not set(groups[train]) & set(groups[test])
        assert len(set(y[train])) == len(set(y[test])) == 2
        v = vectorizer()
        xt = v.fit_transform(texts[train])
        vocabulary,idf = dict(v.vocabulary_),v.idf_.copy()
        xv = v.transform(texts[test])
        np.testing.assert_allclose(v.idf_,np.log((1+len(train))/(1+xt.getnnz(axis=0)))+1)
        assert v.vocabulary_ == vocabulary
        np.testing.assert_array_equal(v.idf_,idf)
        nmf,nt,nlog = old.fit_nmf(xt)
        before = nmf.components_.copy()
        nv,tlog = old.transform_nmf(nmf,xv)
        np.testing.assert_array_equal(nmf.components_,before)
        svd = TruncatedSVD(**config['svd'])
        st = svd.fit_transform(xt)
        before = svd.components_.copy()
        sv = svd.transform(xv)
        np.testing.assert_array_equal(svd.components_,before)
        blocks = dict(audio=(audio[train],audio[test]),simple=(simple[train],simple[test]),nmf=(nt,nv),svd=(st,sv))
        fold_info.append(dict(fold=fold,train_n=len(train),test_n=len(test),test_positive=int(y[test].sum()),
            train_positive=int(y[train].sum()),train_groups=len(set(groups[train])),test_groups=len(set(groups[test])),
            vocabulary=len(vocabulary),empty_test=int((xv.getnnz(axis=1)==0).sum()),
            fit_ids_sha256=old.fingerprint(ids[train].tolist()),nmf_fit=nlog,nmf_transform=tlog))
        for name,names in MODEL_BLOCKS.items():
            if not names:
                probability = np.full(len(test),y[train].mean())
            else:
                a = np.column_stack([blocks[b][0] for b in names])
                b = np.column_stack([blocks[b][1] for b in names])
                attempts = []
                for limit in [2000,4000]:
                    model = old.classifier()
                    model.steps[-1][1].set_params(max_iter=limit)
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter('always')
                        model.fit(a,y[train])
                    converged = not any(issubclass(w.category,ConvergenceWarning) for w in caught)
                    attempts.append(dict(limit=limit,converged=converged,warnings=[str(w.message) for w in caught]))
                    if converged:
                        break
                imputer,scaler,lr = [step[1] for step in model.steps]
                medians = np.nanmedian(a,axis=0)
                medians[np.isnan(medians)] = 0
                np.testing.assert_allclose(imputer.statistics_,medians)
                assert scaler.n_samples_seen_ == len(train)
                before = scaler.mean_.copy()
                probability = model.predict_proba(b)[:,1]
                np.testing.assert_array_equal(before,scaler.mean_)
                fit_log.append(dict(fold=fold,model=name,dimensions=a.shape[1],coefficients=int(lr.coef_.size),
                                    intercepts=int(lr.intercept_.size),iterations=lr.n_iter_.tolist(),attempts=attempts))
            assert np.isfinite(probability).all() and ((probability>=0)&(probability<=1)).all()
            oof[name][test] = probability
            scores.append(dict(fold=fold,model=name,**metrics(y[test],probability)))
        print(f'Fold {fold}/5 complete; vocabulary={len(vocabulary)}; NMF iterations={nmf.n_iter_}',flush=True)
    for name,p in oof.items():
        predictions.append(pl.DataFrame({ID:ids,'top10':y,'group':groups,'fold':folds,'model':[name]*len(y),'probability':p}))
    pl.concat(predictions).write_csv(out/'predictions.csv')
    pl.DataFrame(scores).write_csv(out/'fold_metrics.csv')
    means = [dict(model=name,**{k:float(np.mean([r[k] for r in scores if r['model']==name])) for k in metrics(y,oof[name])}) for name in MODEL_BLOCKS]
    pl.DataFrame(means).write_csv(pack/'model_means.csv')
    pl.DataFrame([dict(model=name,**metrics(y,p)) for name,p in oof.items()]).write_csv(pack/'pooled_oof_metrics.csv')
    paired = [dict(comparison=a+' minus '+b,fold=f,**{k:next(r[k] for r in scores if r['model']==a and r['fold']==f)-next(r[k] for r in scores if r['model']==b and r['fold']==f) for k in ['ap','roc_auc']}) for a,b in PRIORITIES for f in range(1,6)]
    pl.DataFrame(paired).write_csv(pack/'paired_fold_differences.csv')
    shutil.copy2(out/'fold_metrics.csv',pack/'fold_metrics.csv')
    write_json(out/'fit_log.json',fit_log)
    write_json(out/'fold_details.json',fold_info)
    # Separate all-data descriptive representations; never feed these into CV.
    v = vectorizer()
    x = v.fit_transform(texts)
    nmf,weights,desc_log = old.fit_nmf(x)
    svd = TruncatedSVD(**config['svd'])
    svd_weights = svd.fit_transform(x)
    terms = v.get_feature_names_out()
    components,representatives = [],[]
    for kind,model,w in [('NMF',nmf,weights),('SVD',svd,svd_weights)]:
        for c,loadings in enumerate(model.components_):
            positive = np.array([i for i in np.argsort(-loadings,kind='stable') if loadings[i]>0][:12],dtype=int)
            negative = np.array([i for i in np.argsort(loadings,kind='stable') if loadings[i]<0][:12],dtype=int) if kind == 'SVD' else []
            components.append(dict(method=kind,component=c+1,positive_terms=terms[positive].tolist(),
                positive_loadings=loadings[positive].tolist(),negative_terms=terms[negative].tolist() if len(negative) else [],
                negative_loadings=loadings[negative].tolist() if len(negative) else [],
                provisional_label=old.topic_label(terms[positive].tolist()) if kind=='NMF' else 'Signed lexical contrast; interpret both poles',
                mean_top10=float(w[y==1,c].mean()),mean_other=float(w[y==0,c].mean())))
            for pole,indices in [('positive',np.argsort(-w[:,c])[:3]),('negative',np.argsort(w[:,c])[:3] if kind=='SVD' else [])]:
                for i in indices:
                    representatives.append(dict(method=kind,component=c+1,pole=pole,id=int(ids[i]),title=frame['Song'][int(i)],
                        score=float(w[i,c]),complete_revised_lyrics=texts[i]))
    write_json(pack/'descriptive_components.json',components)
    write_json(out/'private_component_examples.json',representatives)
    summaries = []
    for feature in ['p2_word_count','p2_line_repetition','p2_sentiment']:
        for target in [0,1]:
            z = frame.filter(pl.col('top10')==target)[feature].drop_nulls().to_numpy()
            summaries.append(dict(feature=feature,top10=target,n=len(z),missing=int((y==target).sum()-len(z)),
                mean=float(np.mean(z)),p05=float(np.quantile(z,.05)),p25=float(np.quantile(z,.25)),median=float(np.median(z)),p75=float(np.quantile(z,.75)),p95=float(np.quantile(z,.95))))
    pl.DataFrame(summaries).write_csv(pack/'descriptive_summary.csv')
    make_figures(frame,means,scores,pack)
    code_paths = ['src/14_preprocessing_ii_analysis.py','src/music_success_nlp/preprocessing_ii.py',
                  'src/music_success_nlp/__init__.py','src/12_topics_and_top10_prediction.py',
                  'tests/test_preprocessing_ii.py','pyproject.toml','uv.lock','.python-version']
    hashes = {}
    for rel in code_paths:
        dst = pack/'code'/rel
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/rel,dst)
        hashes[rel] = old.sha(ROOT/rel)
    manifest = dict(source_path=str(source_path),source_sha256=source_hash,
        historical_predictions_sha256=old.sha(historical_path),master_n=master.height,eligible_n=frame.height,
        positive=int(y.sum()),negative=int((1-y).sum()),prevalence=float(y.mean()),sample_n=sample.height,
        decisions=dict(Counter(master['p2_decision'])),historical_flagged=int((master['lyric_full_block_repeats']>1).sum()),
        changed_since_stage11=int(master['p2_text_changed'].sum()),words_removed_since_stage11=int(master['p2_words_removed'].sum()),
        encoding_repaired_records=int((master['p2_encoding_replacements']>0).sum()),encoding_replacements=int(master['p2_encoding_replacements'].sum()),
        sentiment_status_master=dict(Counter(master['p2_sentiment_status'])),sentiment_status_eligible=dict(Counter(frame['p2_sentiment_status'])),
        historical_language_flags={c:int(frame[c].sum()) for c in ['lyric_language_uncertain','lyric_language_mixed_candidate','lyric_language_short']},
        missing_audio_cells=int(np.isnan(audio).sum()),new_exact_links=len(links),repartitioned=repartitioned,
        group_count=len(set(groups)),group_sizes=dict(min=int(min(Counter(groups).values())),median=float(np.median(list(Counter(groups).values()))),max=int(max(Counter(groups).values()))),
        fold_details=fold_info,means=means,descriptive_nmf=desc_log,
        final_classifier_nonconvergence=sum(not log['attempts'][-1]['converged'] for log in fit_log),
        code_sha256=hashes,configuration_sha256=old.sha(out/'configuration.json'),
        software={p:version(p) for p in ['numpy','polars','scikit-learn','scipy','matplotlib','vaderSentiment','langdetect']},
        python=sys.version,lexicon_sha256=old.sha(Path(vader_module.__file__).parent/'vader_lexicon.txt'))
    assert old.sha(source_path) == source_hash
    write_json(out/'run_manifest.json',manifest)
    write_json(pack/'code_manifest.json',hashes)
    verify(out)
    print(json.dumps(dict(means=means,manifest=str(out/'run_manifest.json')),indent=2),flush=True)


def make_figures(frame,means,scores,pack):
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes = plt.subplots(1,3,figsize=(13,4.5),layout='constrained')
    for ax,col,label in zip(axes,['p2_word_count','p2_line_repetition','p2_sentiment'],['Lyric length (whitespace words)','Recurring-line fraction','VADER polarity (weighted lines)']):
        for target,name in [(0,'Other'),(1,'Top-10')]:
            z = np.sort(frame.filter(pl.col('top10')==target)[col].drop_nulls().to_numpy())
            ax.step(z,np.arange(1,len(z)+1)/len(z),where='post',label=f'{name} (n={len(z):,})')
        if col=='p2_word_count':
            ax.set_xscale('log')
            label += '; log axis'
        ax.set_xlabel(label)
        ax.set_ylabel('Cumulative fraction of songs')
        ax.legend(fontsize=8)
        ax.grid(alpha=.2)
    fig.suptitle('Distributions within the automated English-labelled sample')
    fig.savefig(pack/'lyric_distributions.png',dpi=170)
    plt.close(fig)
    fig,ax = plt.subplots(figsize=(10,6),layout='constrained')
    for i,r in enumerate(means):
        values = [s['ap'] for s in scores if s['model']==r['model']]
        ax.scatter(values,np.full(5,i)+np.linspace(-.1,.1,5),s=22,color='#426a8c')
        ax.scatter(r['ap'],i,marker='|',s=200,color='black')
        ax.text(max(values)+.004,i,f"{r['ap']:.4f}",va='center',fontsize=9)
    ax.set_yticks(range(len(means)),[r['model'] for r in means])
    ax.invert_yaxis()
    ax.set_xlim(0,max(s['ap'] for s in scores)+.06)
    ax.set_xlabel('Average precision (AP); dots = folds, black mark = equal-fold mean')
    ax.set_title('Fixed model families on identical grouped folds')
    ax.grid(axis='x',alpha=.2)
    fig.savefig(pack/'model_ap.png',dpi=170)
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',default=str(old.SOURCE))
    parser.add_argument('--output',default=str(ROOT/'data/processed/preprocessing_ii_20261115_v2'))
    parser.add_argument('--verify',type=Path)
    args = parser.parse_args()
    with threadpool_limits(limits=2):
        if args.verify:
            verify(args.verify)
        else:
            main(args)
