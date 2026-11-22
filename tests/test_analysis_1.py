import sys
from pathlib import Path
import unittest
import importlib.util
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from music_success_nlp.cumulative_sentiment import measure, trajectory
from music_success_nlp.preprocessing_ii import simple_features


class Analyzer:
    def polarity_scores(self, text):
        return {'compound': {'good': .8, 'bad bad': -.6, 'neutral': 0}[text]}


class CumulativeTests(unittest.TestCase):
    def test_existing_mean(self):
        text = 'good\n\nbad bad\nneutral'
        self.assertAlmostEqual(measure(text, Analyzer())[0]['sentiment_mean'], simple_features(text, Analyzer())['sentiment'])

    def test_constant_and_single(self):
        self.assertAlmostEqual(trajectory([.6]*4, [1, 2, 3, 4])[2], 0)
        self.assertEqual(trajectory([-.3], [20])[2], 0)

    def test_order(self):
        a = trajectory([1, -1, 0], [1, 1, 1])
        b = trajectory([0, -1, 1], [1, 1, 1])
        self.assertEqual(a[1], b[1])
        self.assertNotAlmostEqual(a[2], b[2])

    def test_missing_failure_zero(self):
        self.assertEqual(measure('', Analyzer())[0]['status'], 'missing_text')
        self.assertTrue(measure('unknown', Analyzer())[0]['status'].startswith('failed'))
        self.assertEqual(measure('neutral', Analyzer())[0]['cumulative_mean_sd'], 0)
        self.assertEqual(measure('neutral', Analyzer())[0]['status'], 'ok')
        class Bad:
            def polarity_scores(self, text):
                return {'compound': float('nan')}
        self.assertIsNone(measure('bad', Bad())[0]['cumulative_mean_sd'])

    def test_permutation_keeps_fitted_pipeline_and_input(self):
        path = Path(__file__).resolve().parents[1] / 'src/17_analysis_1.py'
        spec = importlib.util.spec_from_file_location('analysis1_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        rng = np.random.default_rng(4)
        x = rng.normal(size=(60, 24))
        y = (x[:, 0] + rng.normal(size=60) > .5).astype(int)
        model, _ = module.fit(x[:40], y[:40])
        original = model.predict_proba(x[40:])
        rows = module.permutation(model, x[40:], y[40:], 1)
        self.assertEqual(len(rows), 15*20)
        self.assertEqual(sum(r['feature'] == 'NMF joint (10 columns)' for r in rows), 20)
        np.testing.assert_array_equal(original, model.predict_proba(x[40:]))
        self.assertEqual(rows, module.permutation(model, x[40:], y[40:], 1))


if __name__ == '__main__':
    unittest.main()
