"""Small-fixture sparse/dense equivalence and held-out centering checks."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.decomposition import PCA

spec=importlib.util.spec_from_file_location('pca_extension',Path(__file__).resolve().parents[1]/'src/16_centered_pca_extension.py')
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class CenteredPCATests(unittest.TestCase):
    def test_sparse_matches_dense_centered_fixture(self):
        rng=np.random.default_rng(42)
        x=rng.normal(size=(60,18))*np.arange(1,19)+np.arange(18)*5
        heldout=rng.normal(size=(7,18))+1000
        sparse,train,test,warnings=m.fit_centered(csr_matrix(x),csr_matrix(heldout))
        dense=PCA(n_components=10,svd_solver='full').fit(x)
        np.testing.assert_allclose(sparse.explained_variance_ratio_,dense.explained_variance_ratio_,rtol=1e-10)
        np.testing.assert_allclose(sparse.components_.T@sparse.components_,dense.components_.T@dense.components_,atol=1e-10)
        np.testing.assert_allclose(sparse.mean_,x.mean(axis=0))
        self.assertFalse(np.allclose(sparse.mean_,np.vstack([x,heldout]).mean(axis=0)))
        np.testing.assert_allclose(test,(heldout-x.mean(axis=0))@sparse.components_.T,atol=1e-10)
        self.assertEqual(sparse.svd_solver,'arpack')
        self.assertFalse(sparse.whiten)
        self.assertEqual(warnings,[])

    def test_training_only_vocabulary(self):
        v=m.m.vectorizer()
        v.fit_transform(['common apple']*5+['common orange']*5)
        before=v.idf_.copy()
        v.transform(['heldoutonly apple'])
        self.assertNotIn('heldoutonly',v.vocabulary_)
        np.testing.assert_array_equal(v.idf_,before)


if __name__=='__main__': unittest.main()
