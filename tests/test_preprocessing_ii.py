"""Synthetic contracts; actual-output assertions also run in Stage 14 --verify."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import polars as pl
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from music_success_nlp.preprocessing_ii import *

spec = importlib.util.spec_from_file_location('stage14',Path(__file__).resolve().parents[1]/'src/14_preprocessing_ii_analysis.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def base():
    return '\n'.join(f'Line {i} has enough ordinary words to test the repeated text safely.' for i in range(12))+'\nSame chorus\nSame chorus'


class PreprocessingIITests(unittest.TestCase):
    def test_apostrophes_and_negation(self):
        tokens = m.vectorizer().build_analyzer()("I’ll I’ve can’t don’t I'd not never no a I ll ve")
        for token in ["i'll","i've","can't","don't","i'd",'not','never','no','ll','ve']:
            self.assertIn(token,tokens)
        self.assertNotIn('i',tokens)
        self.assertEqual(normalize_apostrophes('a\u2018b a\u02bcb a\uff07b'),"a'b a'b a'b")

    def test_whole_repeat_and_chorus(self):
        text = base()+'\n\n'+base().upper()
        revised,decision,_,repeat = normalize_whole_repeat(text)
        self.assertEqual((revised,decision,repeat),(base(),'normalized',2))
        self.assertEqual(revised.count('Same chorus'),2)
        self.assertEqual(normalize_whole_repeat(revised)[0],revised)
        self.assertEqual(normalize_whole_repeat(base()+'\n'+base()+'\nextra')[1],'unchanged')
        self.assertEqual(normalize_whole_repeat('yes\nyes')[1],'retained_by_policy')

    def test_features_empty_and_neutral(self):
        analyzer = SentimentIntensityAnalyzer()
        r = simple_features('same line\n SAME  line\nother words',analyzer)
        self.assertEqual(r['word_count'],6)
        self.assertAlmostEqual(r['log_word_count'],np.log1p(6))
        self.assertAlmostEqual(r['line_repetition'],1/3)
        self.assertEqual(simple_features('',analyzer)['sentiment_status'],'missing_text')
        self.assertIsNone(simple_features('',analyzer)['line_repetition'])
        r = simple_features('table',analyzer)
        self.assertEqual((r['sentiment'],r['sentiment_status']),(0,'ok'))

    def test_sentiment_failure_and_long_text(self):
        class Failing:
            def polarity_scores(self,text):
                raise RuntimeError('fixture')
        r = simple_features('natural text',Failing())
        self.assertIsNone(r['sentiment'])
        self.assertEqual(r['sentiment_status'],'failed_RuntimeError')
        class Counting:
            def __init__(self): self.calls = 0
            def polarity_scores(self,text):
                self.calls += 1
                return {'compound':1 if text=='good!' else -1}
        a = Counting()
        r = simple_features(('good!\n'*10001)+'bad ending',a)
        self.assertEqual(a.calls,10002)
        self.assertAlmostEqual(r['sentiment'],(10001-2)/10003)

    def test_preservation_accounting_eligibility(self):
        source = pl.DataFrame(dict(billboard_source_row=[1,2,3],lyrics=['raw1','raw2','raw3'],
            lyrics_deduplicated=[base()+'\n'+base(),base(),'short\nshort'],
            full_block_dedup_applied=[False,True,False],lyric_language=['en','en','es'],
            lyric_language_uncertain=[True,False,True],top10=[1,0,0]))
        analyzer = SentimentIntensityAnalyzer()
        revised = prepare(source,analyzer)
        self.assertTrue(revised.select(source.columns).equals(source))
        self.assertEqual(revised['p2_eligible'].to_list(),[True,True,False])
        self.assertTrue(prepare(revised,analyzer).equals(revised))
        self.assertEqual(revised['p2_words_removed'][0],len(base().split()))
        self.assertEqual(revised.height,source.height)
        with self.assertRaises(ValueError):
            prepare(pl.concat([source,source]),analyzer)

    def test_training_only_vocabulary_and_scaling(self):
        v = m.vectorizer()
        train = ['shared apple']*5+['shared orange']*5
        v.fit_transform(train)
        before = v.idf_.copy()
        v.transform(['heldoutonly apple'])
        self.assertNotIn('heldoutonly',v.vocabulary_)
        np.testing.assert_array_equal(before,v.idf_)
        model = m.old.classifier().fit(np.array([[1.],[3.],[np.nan],[7.]]),[0,1,0,1])
        self.assertEqual(model.steps[0][1].statistics_[0],3)
        mean = model.steps[1][1].mean_.copy()
        model.predict_proba([[10000.]])
        np.testing.assert_array_equal(mean,model.steps[1][1].mean_)

    def test_metrics_threshold_zero_division(self):
        r = m.metrics(np.array([0,1,0,1]),np.array([.1,.2,.3,.4]))
        self.assertEqual(r['predicted_positive'],0)
        self.assertEqual((r['precision'],r['recall'],r['f1']),(0,0,0))
        self.assertAlmostEqual(r['ap'],(1+2/3)/2)

    def test_encoding_repair_is_narrow_and_idempotent(self):
        repaired,count = repair_observed_encoding('text \u00e2\u0080\u0098round and \u00e2?')
        self.assertEqual(count,1)
        self.assertEqual(repaired,'text \u2018round and \u00e2?')
        self.assertEqual(repair_observed_encoding(repaired),(repaired,0))

    def test_grouping_exact_not_blank(self):
        source = pl.DataFrame({ID:[4480,4481,3,4,5,6], 'artist_norm':['a','b','c','d','e','f'],
            'lyrics_compare_sha256':[None]*6,'raw_lyric_sha256':[None]*6,'lyric_duplicate_group_id':[None]*6,
            'p2_lyrics_revised':['cover a','cover b','same text','SAME  text','',''], 'top10':[0,1,0,1,0,1]})
        historical = pl.DataFrame({ID:source[ID],'validation_fold':[1,1,2,2,3,4]})
        groups,folds,links,changed = m.partition(source,source,historical)
        self.assertEqual(groups[0],groups[1])
        self.assertEqual(groups[2],groups[3])
        self.assertNotEqual(groups[4],groups[5])
        self.assertFalse(changed)
        self.assertEqual(len(links),1)


ID = 'billboard_source_row'
if __name__ == '__main__':
    unittest.main()
