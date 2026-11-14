import importlib.util
from pathlib import Path
import unittest
import polars as pl

spec=importlib.util.spec_from_file_location('stage11',Path(__file__).resolve().parents[1]/'src/11_review_and_correct_full_block_repetition.py')
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def base():
    return '\n'.join(f"Line {i} I don't agree, and I can’t change this!" for i in range(12))

def review(text,status='extraction duplication'):
    return [dict(status=status,notes='Reviewer checked the recording.',clean=text)]

class CorrectionTests(unittest.TestCase):
    def test_exact_whole_blocks_preserve_choruses(self):
        block=base()+"\nRepeated chorus!\nRepeated chorus!"
        text='\n'.join([block]*3)
        self.assertEqual(m.correct_record(text,3,review(text)),(block,'corrected'))
        self.assertEqual(m.stage10_repeat_count(block),1)

    def test_genuine_partial_choruses_not_removed(self):
        text='Verse one\nChorus\nChorus\nVerse two\nChorus\nChorus'
        self.assertEqual(m.stage10_repeat_count(text),1)
        self.assertEqual(m.correct_record(text,1,review(text)),(text,'not_applicable'))

    def test_short_refrain_is_ambiguous(self):
        text='No, no!\nNo, no!'
        self.assertEqual(m.correct_record(text,2,review(text)),(text,'uncertain'))

    def test_likely_uncertain_unclassified_not_corrected(self):
        text=base()+'\n'+base()
        for status in ['likely source duplication','unsure','']:
            result=m.correct_record(text,2,review(text,status))
            self.assertEqual(result[0],text)
            self.assertNotEqual(result[1],'corrected')
        self.assertEqual(m.correct_record(text,2,[]),(text,'suspected'))

    def test_case_layout_and_stale_evidence_rejected(self):
        text=base()+'\n'+base().upper()
        self.assertEqual(m.stage10_repeat_count(text),2)
        self.assertEqual(m.correct_record(text,2,review(text))[1],'uncertain')
        text=base()+'\n'+base()
        self.assertEqual(m.correct_record(text,2,review('stale'))[1],'uncertain')
        altered=base()+'\n'+base().replace('\n','\n\n',1)
        self.assertEqual(m.correct_record(altered,2,review(altered))[1],'uncertain')

    def test_non_repeated_and_null(self):
        for text in [base(),'',None]:
            self.assertEqual(m.correct_record(text,1,[]),(text,'not_applicable'))

    def test_metadata_preservation_and_idempotence(self):
        text=base()+'\n'+base()
        source=pl.DataFrame(dict(billboard_source_row=[1,2],lyrics=['raw','raw2'],lyrics_clean=[text,base()],
            lyric_full_block_repeats=[2,1],top10=[1,0],energy_median=[.4,.7]))
        evidence={1:review(text)}
        output=m.prepare(source,evidence)
        m.validate_preservation(source,output)
        self.assertTrue(output.equals(m.prepare(output,evidence)))
        self.assertEqual(output['lyric_dedup_words_removed'][0],len(base().split()))
        with self.assertRaises(ValueError):
            m.validate_preservation(source,output.with_columns(pl.lit(0).alias('top10')))

if __name__=='__main__':
    unittest.main()
