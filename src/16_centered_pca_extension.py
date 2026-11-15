"""Centered PCA extension; reuse immutable v2 predictions and preprocessing.

ARPACK operates on implicitly centered sparse TF-IDF. No real-data dense
conversion, word-column standardization, alternative solver or score tuning.
"""
import argparse
import importlib.util
import inspect
import json
from pathlib import Path
import shutil
import warnings
import numpy as np
import polars as pl
import sklearn
from sklearn.decomposition import PCA
from sklearn.exceptions import ConvergenceWarning
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stage14', ROOT/'src/14_preprocessing_ii_analysis.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
PCA_SETTINGS = dict(n_components=10,svd_solver='arpack',random_state=42,tol=0.0,whiten=False,copy=True)
COMPARISONS = [('PCA','NMF'),('PCA','SVD'),('Audio + PCA','Audio + NMF'),('Audio + PCA','Audio + SVD'),('Audio + PCA','Audio')]


def snapshot(path):
    return {str(p.relative_to(path)):m.old.sha(p) for p in sorted(path.rglob('*')) if p.is_file()}


def fit_centered(training,heldout):
    """Check centering independently without constructing a dense word matrix."""
    model = PCA(**PCA_SETTINGS)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        train_scores = model.fit_transform(training)
    np.testing.assert_allclose(model.mean_,np.asarray(training.mean(axis=0)).ravel(),atol=1e-14)
    np.testing.assert_allclose(train_scores.mean(axis=0),0,atol=1e-12)
    mean,components = model.mean_.copy(),model.components_.copy()
    test_scores = model.transform(heldout)
    # Algebraically equivalent to (X_test - training_mean) @ components.T.
    np.testing.assert_allclose(test_scores,heldout @ components.T - mean @ components.T,atol=1e-12)
    np.testing.assert_array_equal(model.mean_,mean)
    np.testing.assert_array_equal(model.components_,components)
    assert model.n_samples_ == training.shape[0]
    assert np.isfinite(train_scores).all() and np.isfinite(test_scores).all()
    return model,train_scores,test_scores,[str(w.message) for w in caught]


def verify(out):
    manifest=json.loads((out/'run_manifest.json').read_text())
    base=Path(manifest['base_run'])
    assert snapshot(base)==manifest['base_tree_sha256'], 'v2 changed'
    expected=pl.read_csv(base/'fold_assignments.csv')
    predictions=pl.read_csv(out/'predictions.csv')
    scores=pl.read_csv(out/'submission/fold_metrics.csv')
    means=pl.read_csv(out/'submission/model_means.csv')
    pooled=pl.read_csv(out/'submission/pooled_oof_metrics.csv')
    historical=pl.read_csv(base/'predictions.csv')
    assert predictions.filter(~pl.col('model').is_in(['PCA','Audio + PCA'])).equals(historical)
    for name in predictions['model'].unique():
        rows=predictions.filter(pl.col('model')==name)
        assert rows.select(expected.columns).equals(expected)
        assert rows[m.ID].n_unique()==expected.height
        assert rows.group_by('group').agg(pl.col('fold').n_unique())['fold'].max()==1
        assert np.isfinite(rows['probability'].to_numpy()).all()
        assert rows['probability'].min()>=0 and rows['probability'].max()<=1
        for fold in range(1,6):
            r=rows.filter(pl.col('fold')==fold)
            computed=m.metrics(r['top10'].to_numpy(),r['probability'].to_numpy())
            stored=scores.filter((pl.col('model')==name)&(pl.col('fold')==fold)).row(0,named=True)
            for key,value in computed.items():
                assert np.isclose(value,stored[key],atol=1e-12,rtol=1e-12)
        for key,value in m.metrics(rows['top10'].to_numpy(),rows['probability'].to_numpy()).items():
            assert np.isclose(value,pooled.filter(pl.col('model')==name)[key][0])
            assert np.isclose(scores.filter(pl.col('model')==name)[key].mean(),means.filter(pl.col('model')==name)[key][0])
    for rel,digest in manifest['extension_code_sha256'].items():
        assert m.old.sha(out/'submission/code'/rel)==digest
    print('Verified: v2 unchanged; reused predictions identical; all 11 families share IDs/targets/groups/folds; finite predictions and all saved metrics agree.',flush=True)


def run(base,out):
    base,out=base.resolve(),out.resolve()
    out.relative_to(ROOT/'data/processed')
    original_hashes=snapshot(base)
    m.verify(base)
    old_manifest=json.loads((base/'run_manifest.json').read_text())
    for rel,digest in old_manifest['code_sha256'].items():
        assert m.old.sha(ROOT/rel)==digest, f'Changed v2 dependency: {rel}'
    assert sklearn.__version__==old_manifest['software']['scikit-learn']
    out.mkdir(parents=True,exist_ok=False)
    config=dict(pca=PCA_SETTINGS,word_column_standardization=False,dense_conversion=False,
        classifier=json.loads((base/'configuration.json').read_text())['classifier'],
        numerical_failure_policy='Abort on ARPACK error; no fallback or held-out tuning',
        base_configuration_sha256=m.old.sha(base/'configuration.json'))
    m.write_json(out/'configuration.json',config)
    (out/'installed_pca_documentation.txt').write_text(PCA.__doc__+'\n\n'+inspect.getsource(PCA._fit_truncated),encoding='utf-8')
    frame=pl.read_parquet(base/'master.parquet').filter('p2_eligible')
    assignments=pl.read_csv(base/'fold_assignments.csv')
    assert frame.select(m.ID,'top10').equals(assignments.select(m.ID,'top10'))
    assert frame[m.ID].to_list()==pl.read_csv(base/'eligible_ids.csv')[m.ID].to_list()
    y=frame['top10'].to_numpy().astype(int)
    np.testing.assert_array_equal(y,(frame['peak_rank'].to_numpy()<=10).astype(int))
    folds=assignments['fold'].to_numpy()
    groups=assignments['group'].to_numpy()
    texts=frame['p2_lyrics_revised'].to_numpy()
    audio=frame.select(m.old.AUDIO).to_numpy().astype(float)
    audio[~np.isfinite(audio)]=np.nan
    oof={name:np.full(frame.height,np.nan) for name in ['PCA','Audio + PCA']}
    logs,scores=[],[]
    for fold in range(1,6):
        train,test=np.flatnonzero(folds!=fold),np.flatnonzero(folds==fold)
        assert not set(groups[train]) & set(groups[test])
        v=m.vectorizer()
        xt=v.fit_transform(texts[train])
        idf,vocab=v.idf_.copy(),dict(v.vocabulary_)
        xv=v.transform(texts[test])
        np.testing.assert_array_equal(v.idf_,idf)
        assert v.vocabulary_==vocab
        np.testing.assert_allclose(idf,np.log((1+len(train))/(1+xt.getnnz(axis=0)))+1)
        historical=old_manifest['fold_details'][fold-1]
        assert historical['vocabulary']==xt.shape[1]
        assert historical['fit_ids_sha256']==m.old.fingerprint(frame[m.ID].to_numpy()[train].tolist())
        # Estimates before PCA; no call to toarray, todense or dense covariance.
        memory=dict(training_csr_bytes=int(xt.data.nbytes+xt.indices.nbytes+xt.indptr.nbytes),
            hypothetical_dense_training_bytes=int(xt.shape[0]*xt.shape[1]*8),
            hypothetical_dense_covariance_bytes=int(xt.shape[1]**2*8),
            components_bytes=int(10*xt.shape[1]*8),note='Array sizes only, not peak process memory; solver workspace additional')
        print(f'Fold {fold}: shape={xt.shape}, CSR={memory["training_csr_bytes"]/2**20:.1f} MiB, hypothetical dense={memory["hypothetical_dense_training_bytes"]/2**20:.1f} MiB; sparse ARPACK selected.',flush=True)
        pca,pt,pv,pca_warnings=fit_centered(xt,xv)
        np.savez_compressed(out/f'pca_fold_{fold}.npz',mean=pca.mean_,components=pca.components_,
            idf=idf,vocabulary=v.get_feature_names_out(),training_ids=frame[m.ID].to_numpy()[train],
            explained_variance_ratio=pca.explained_variance_ratio_,singular_values=pca.singular_values_)
        log=dict(fold=fold,training_n=len(train),validation_n=len(test),vocabulary=xt.shape[1],memory=memory,
            solver=pca._fit_svd_solver,seed=42,tolerance=0.0,converged=True,warnings=pca_warnings,
            convergence_evidence='ARPACK returned without error; iteration count not exposed by sklearn PCA',
            explained_variance_ratio=pca.explained_variance_ratio_.tolist(),explained_variance_ratio_sum=float(pca.explained_variance_ratio_.sum()),
            training_only_checks='training means, zero-mean training scores, held-out projection equation and frozen state passed',classifier={})
        for name,a,b in [('PCA',pt,pv),('Audio + PCA',np.column_stack([audio[train],pt]),np.column_stack([audio[test],pv]))]:
            attempts=[]
            for limit in [2000,4000]:
                model=m.old.classifier()
                model.steps[-1][1].set_params(max_iter=limit)
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    model.fit(a,y[train])
                converged=not any(issubclass(w.category,ConvergenceWarning) for w in caught)
                attempts.append(dict(max_iter=limit,converged=converged,warnings=[str(w.message) for w in caught]))
                if converged: break
            imputer,scaler,lr=[s[1] for s in model.steps]
            np.testing.assert_allclose(imputer.statistics_,np.nanmedian(a,axis=0))
            assert scaler.n_samples_seen_==len(train)
            scaler_mean=scaler.mean_.copy()
            oof[name][test]=model.predict_proba(b)[:,1]
            np.testing.assert_array_equal(scaler.mean_,scaler_mean)
            log['classifier'][name]=dict(dimensions=a.shape[1],coefficients=lr.coef_.size,intercepts=1,iterations=lr.n_iter_.tolist(),attempts=attempts)
            scores.append(dict(fold=fold,model=name,**m.metrics(y[test],oof[name][test])))
        logs.append(log)
    historical=pl.read_csv(base/'predictions.csv')
    predictions=pl.concat([historical,*[assignments.with_columns(pl.lit(name).alias('model'),pl.Series('probability',p)).select(historical.columns) for name,p in oof.items()]])
    predictions.write_csv(out/'predictions.csv')
    all_scores=pl.concat([pl.read_csv(base/'fold_metrics.csv'),pl.DataFrame(scores)],how='vertical_relaxed')
    pack=out/'submission'
    shutil.copytree(base/'submission',pack)
    # Preserve v2 narrative as explicitly historical reference in the new pack.
    (pack/'04_analysis_update.md').rename(pack/'04_v2_analysis_update.md')
    (pack/'model_ap.png').rename(pack/'v2_model_ap.png')
    reference=pack/'04_v2_analysis_update.md'
    reference.write_text(reference.read_text(encoding='utf-8').replace('(model_ap.png)','(v2_model_ap.png)'),encoding='utf-8')
    names=list(m.MODEL_BLOCKS)+['PCA','Audio + PCA']
    mean_rows=[dict(model=name,**{k:float(all_scores.filter(pl.col('model')==name)[k].mean()) for k in m.metrics(y,oof['PCA'])}) for name in names]
    all_scores.write_csv(pack/'fold_metrics.csv')
    pl.DataFrame(mean_rows).write_csv(pack/'model_means.csv')
    pl.DataFrame([dict(model=name,**m.metrics(y,predictions.filter(pl.col('model')==name)['probability'].to_numpy())) for name in names]).write_csv(pack/'pooled_oof_metrics.csv')
    paired=[dict(comparison=a+' minus '+b,fold=f,**{k:float(all_scores.filter((pl.col('model')==a)&(pl.col('fold')==f))[k][0]-all_scores.filter((pl.col('model')==b)&(pl.col('fold')==f))[k][0]) for k in ['ap','roc_auc']}) for a,b in COMPARISONS for f in range(1,6)]
    pl.DataFrame(paired).write_csv(pack/'pca_paired_fold_differences.csv')
    m.make_figures(frame,mean_rows,all_scores.to_dicts(),pack)
    m.write_json(out/'fold_details.json',logs)
    hashes={}
    for rel in ['src/16_centered_pca_extension.py','tests/test_centered_pca.py']:
        dst=pack/'code'/rel
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/rel,dst)
        hashes[rel]=m.old.sha(ROOT/rel)
    code_manifest=json.loads((pack/'code_manifest.json').read_text())
    code_manifest.update(hashes)
    m.write_json(pack/'code_manifest.json',code_manifest)
    m.write_json(out/'run_manifest.json',dict(base_run=str(base),base_tree_sha256=original_hashes,
        extension_code_sha256=hashes,configuration_sha256=m.old.sha(out/'configuration.json'),
        sklearn_version=sklearn.__version__,pca_source_path=inspect.getfile(PCA),pca_source_sha256=m.old.sha(Path(inspect.getfile(PCA))),
        eligible=frame.height,positive=int(y.sum()),reused_models=list(m.MODEL_BLOCKS),new_models=['PCA','Audio + PCA'],
        preprocessing_changes=False,new_exclusions=0,folds_reused=True))
    report(pack,base,mean_rows,all_scores,paired,logs)
    verify(out)
    print(json.dumps(mean_rows[-2:],indent=2),flush=True)


def report(pack,base,means,scores,paired,logs):
    table=m.old.md_table
    fmt=lambda x:f'{x:.4f}' if isinstance(x,float) else str(x)
    as_table=lambda df:table(df.columns,[[fmt(v) for v in row] for row in df.iter_rows()])
    methods='''## Centered PCA extension

PCA uses the same revised word-unigram TF-IDF as v2, with **10 components**, `svd_solver="arpack"`, seed 42, tolerance 0 (machine precision), `whiten=False`, `copy=True`. The installed sklearn 1.9.1 documentation and `_fit_truncated` source were inspected and saved in the extension directory. ARPACK uses an implicit column-mean offset on sparse input. No dense real-data word matrix or covariance matrix was constructed, and no alternative solver or component count was selected against scores. ARPACK exceptions abort rather than substitute uncentered SVD. Its iteration count is not exposed; successful return and captured warnings are recorded.

PCA subtracts **training-set TF-IDF column means**. Individual word columns are **not standardized**: we retain TF-IDF's weighting geometry rather than giving every rare/low-variance word unit variance. This differs from the training-only standard scaling of the final 10 or 20 classifier inputs. The final imputation/scaling and logistic settings exactly match v2: median imputation, standard scaling, L2 C=1, no class weighting, lbfgs, tolerance 1e-4, seed 42, max_iter 2000 (4000 only for a convergence warning). PCA alone has 10 coefficients plus intercept; Audio + PCA has 20 plus intercept.

Each fold fits vocabulary, IDF and PCA only on its training songs. Checks compare the stored PCA mean with the independent training sparse-column mean, verify zero-mean training component scores, and verify held-out scores equal `X_test @ components.T - training_mean @ components.T`, without changing fitted state. Synthetic sparse PCA is also checked against dense centered PCA on a small fixture. Saved means/components and fit IDs remain private.

**NMF** is nonnegative additive factorization. **SVD/LSA** is uncentered TruncatedSVD. **PCA** here is genuinely centered, with signed orthogonal axes. All have 10 components but differ in objectives and constraints; equal counts do not equalize complete pipeline capacity. Explained variance ratios measure training TF-IDF variance captured, not predictive accuracy or proportions of lyrical topics.

Source: installed `sklearn.decomposition.PCA` documentation and implementation (path/hash and exact text saved in the extension manifest and `installed_pca_documentation.txt`).
'''
    mapping=table(['Family','Classifier inputs'],[
        ['Dummy','Training prevalence; no predictors'],['Audio','10 audio medians'],
        ['Simple lyrics','log(1 + whitespace word count), recurring-line fraction, VADER polarity'],
        ['Audio + simple lyrics','10 audio medians + the 3 simple lyric features'],
        ['NMF / SVD / PCA','10 corresponding fold-fitted component scores'],
        ['Audio + NMF / SVD / PCA','10 audio medians + 10 corresponding component scores'],
        ['Audio + simple lyrics + NMF','10 audio medians + 3 simple lyric features + 10 NMF scores']])
    deltas=pl.DataFrame(paired).group_by('comparison',maintain_order=True).agg(pl.col('ap').mean().alias('mean_AP_difference'),pl.col('ap').min().alias('min_fold_AP_difference'),pl.col('ap').max().alias('max_fold_AP_difference'))
    evr=pl.DataFrame([dict(fold=l['fold'],**{f'PC{i+1}':v for i,v in enumerate(l['explained_variance_ratio'])},total=l['explained_variance_ratio_sum']) for l in logs])
    evr.write_csv(pack/'pca_explained_variance.csv')
    memory=pl.DataFrame([dict(fold=l['fold'],vocabulary=l['vocabulary'],training_CSR_MiB=l['memory']['training_csr_bytes']/2**20,hypothetical_dense_training_MiB=l['memory']['hypothetical_dense_training_bytes']/2**20,hypothetical_dense_covariance_MiB=l['memory']['hypothetical_dense_covariance_bytes']/2**20) for l in logs])
    text=f'''# Preprocessing II v3: centered PCA extension

This extension adds PCA and Audio + PCA to the completed v2 analysis. All nine v2 prediction sets are reused unchanged after verification. All eleven families share the exact **6,385 eligible IDs, 984 positives, targets, groups and five saved folds**. No preprocessing, sentiment, language eligibility or exclusions changed. The completed v2 tree is hash-checked before and after execution.

## Actual comparison

{as_table(pl.DataFrame(means))}

All columns above are **equal-fold means**; predicted_positive is the mean count per fold. `fold_metrics.csv` contains exact fold counts; `pooled_oof_metrics.csv` separately reports pooled scores and total predicted positives. AP means average precision, not trapezoidal PR-AUC. Precision/recall/F1 use fixed threshold 0.5 and zero_division=0, as in v2. No threshold was optimized.

![Eleven fixed model families on the same folds](model_ap.png)

{as_table(deltas)}

These paired differences describe the same held-out songs in each fold. A small numeric lead does not establish a meaningful winner. The five training sets overlap, so no independent-sample significance test is applied. Representation explained variance does not identify which model predicts Top-10 status best. Complete-credit grouping still permits performers shared between solo and collaborative credits; reused development folds and selected matched charting songs limit generalization. Human review remains required before Canvas submission.

## Feature-set mapping

{mapping}

{methods}

## Memory and numerical results

{as_table(memory)}

These are array-size estimates, not measured peak process memory. Dense estimates exclude copies and solver workspace. Sparse ARPACK was used throughout; its dense outputs are only 10-dimensional scores, component loadings and column means. All five PCA calls returned successfully. Captured warnings, classifier convergence and iteration details are in `../fold_details.json`.

{as_table(evr)}

Ratios above concern each training fold only. No all-data PCA interpretation fit was needed for this predictive extension.

## Paired fold results

{as_table(pl.DataFrame(paired))}

## All fold metrics

{as_table(scores)}

## Provenance and reproduction

Immutable base: `{base}`. The extension manifest records SHA-256 hashes for every v2 file, configuration, inspected PCA implementation and extension code. The existing cleaned sample is copied byte-for-byte into this new submission. `04_v2_analysis_update.md` retains the historical nine-model narrative; the current table and figure above supersede its comparison for this extension. The old nine-model figure is preserved as `v2_model_ap.png`.

```powershell
uv run python -m unittest discover -s tests -v
uv run python src/16_centered_pca_extension.py --output data/processed/preprocessing_ii_pca_reproduction
uv run python src/16_centered_pca_extension.py --verify data/processed/preprocessing_ii_pca_reproduction
```

Use a new output directory. No upstream preprocessing or v2 model refitting is necessary. Private prediction rows and PCA vocabulary/loadings stay Git-ignored. Nothing is pushed, merged or uploaded.
'''
    (pack/'04_analysis_update.md').write_text(text,encoding='utf-8')
    # Point inherited audit references back to the immutable base, not nonexistent
    # files in the extension. Start from base documents to make rendering idempotent.
    for name in ['01_preprocessing_summary.md','02_methods_and_reproduction.md','06_review_and_handover.md']:
        inherited=(base/'submission'/name).read_text(encoding='utf-8')
        for artifact in ['decision_audit.csv','master.parquet','eligible_ids.csv','run_manifest.json','configuration.json','private_sanity_review.md','verification.json']:
            inherited=inherited.replace('../'+artifact,(base/artifact).as_posix())
        if name=='02_methods_and_reproduction.md':
            inherited+='\n\n'+methods+'\n'+mapping+'\n\nFor v3 extension commands see `04_analysis_update.md`; earlier commands reproduce the historical v2 base.\n'
        if name=='06_review_and_handover.md':
            inherited='# V3 extension review\n\nReview the centered-PCA solver/centering explanation, feature mapping, updated eleven-model table and figure, paired fold differences and explained variance before Canvas submission. All prior human-review requirements remain. The following handover is the preserved v2 base context; the extension manifest is in the parent directory.\n\n'+inherited
        (pack/name).write_text(inherited,encoding='utf-8')
    (pack/'README.md').write_text('# Preprocessing II v3 submission: centered PCA extension\n\nStart with [updated comparison and feature mapping](04_analysis_update.md) and [methods](02_methods_and_reproduction.md).\n\nThe preprocessing summary, complete 26-record sample and column guide are unchanged copies from v2. V2 remains intact. See `04_v2_analysis_update.md` for its historical results. Code and checksums include the extension. Human review remains required; nothing was uploaded.\n',encoding='utf-8')
    (pack/'LOCAL_VERIFICATION.md').write_text('# PCA extension verification\n\nShared IDs/targets/groups/folds, train-only centering, finite predictions, metrics recomputed from saved predictions and v2 tree preservation passed. See the parent run manifest and fold_details.json. This does not establish predictive superiority or fully unseen-artist evaluation.\n',encoding='utf-8')
    path=pack/'05_presentation_12_minutes.md'
    path.write_text(path.read_text(encoding='utf-8').replace('NMF versus sparse uncentered SVD','NMF versus sparse uncentered SVD versus centered PCA')+'\nFor the existing results segment, use the updated eleven-family figure and PCA pairwise table. Keep the 12-minute timing; avoid calling tiny PCA/SVD/NMF differences meaningful winners.\n',encoding='utf-8')
    public=ROOT/'reports/preprocessing_ii_pca_20261115'
    public.mkdir(exist_ok=True)
    for name in ['04_analysis_update.md','model_ap.png','model_means.csv','fold_metrics.csv','pooled_oof_metrics.csv','pca_paired_fold_differences.csv','pca_explained_variance.csv']:
        shutil.copy2(pack/name,public/name)


def render_saved(out):
    """Refresh explanatory documents only; preserve executed-code provenance."""
    verify(out)
    manifest=json.loads((out/'run_manifest.json').read_text())
    pack=out/'submission'
    report(pack,Path(manifest['base_run']),pl.read_csv(pack/'model_means.csv').to_dicts(),
        pl.read_csv(pack/'fold_metrics.csv'),pl.read_csv(pack/'pca_paired_fold_differences.csv').to_dicts(),
        json.loads((out/'fold_details.json').read_text()))
    rel='src/16_centered_pca_extension.py'
    if 'executed_extension_sha256' not in manifest:
        manifest['executed_extension_sha256']=manifest['extension_code_sha256'][rel]
        shutil.copy2(pack/'code'/rel,out/'executed_extension.py')
    shutil.copy2(ROOT/rel,pack/'code'/rel)
    manifest['extension_code_sha256'][rel]=m.old.sha(ROOT/rel)
    manifest['render_update']='Documentation links/render-only support; model calculations unchanged'
    m.write_json(out/'run_manifest.json',manifest)
    code=json.loads((pack/'code_manifest.json').read_text())
    code[rel]=m.old.sha(ROOT/rel)
    m.write_json(pack/'code_manifest.json',code)
    verify(out)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,default=ROOT/'data/processed/preprocessing_ii_20261115_v2')
    parser.add_argument('--output',type=Path,default=ROOT/'data/processed/preprocessing_ii_pca_20261115_v3')
    parser.add_argument('--verify',type=Path)
    parser.add_argument('--render-only',type=Path)
    args=parser.parse_args()
    with threadpool_limits(limits=2):
        if args.verify: verify(args.verify)
        elif args.render_only: render_saved(args.render_only)
        else: run(args.base,args.output)
