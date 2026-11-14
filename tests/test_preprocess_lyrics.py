"""Small synthetic tests; no copyrighted lyric fixtures."""
import importlib.util
from pathlib import Path
import unittest

import polars as pl

spec = importlib.util.spec_from_file_location('preprocess', Path(__file__).resolve().parents[1] / 'src/10_preprocess_lyrics.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CleaningTests(unittest.TestCase):
    def test_negation_contractions_punctuation_and_repetition(self):
        text = "I don't agree!\nI can’t agree—no.\nI don't agree!"
        self.assertEqual(module.clean_lyrics(text), text)
        flags = module.text_features(text, text)
        self.assertEqual(flags['lyric_repeated_line_extras'], 1)

    def test_unicode_and_whitespace(self):
        self.assertEqual(module.clean_lyrics('  Cafe\u0301\t here\r\n\r\n\r\n No!  '), 'Café here\n\nNo!')
        self.assertEqual(module.clean_lyrics('Ａ ﬁ “yes”'), 'Ａ ﬁ “yes”')  # NFC, not NFKC.
        self.assertTrue(module.mixed_script_token('hеllo'))  # Cyrillic e.
        self.assertFalse(module.mixed_script_token('hello мир'))

    def test_confirmed_markers_only(self):
        text = '[Intro]\n[Verse 1: Bow Wow]\nNo!\n[Chorus 2X]\n ♪\n[Hook: Kamaiyah + YG]\n[Outro]\n[Pt:\n[hey]\nword [Chorus]'
        self.assertEqual(module.clean_lyrics(text), 'No!\n[Outro]\n[Pt:\n[hey]\nword [Chorus]')
        # Unobserved generic labels and lyrical brackets are intentionally retained.

    def test_null_blank_and_marker_only(self):
        self.assertIsNone(module.clean_lyrics(None))
        for value in ('', ' \t\r\n ', '[Chorus]\n♪'):
            self.assertEqual(module.clean_lyrics(value), '')
        self.assertTrue(module.text_features(None, None)['lyric_blank'])

    def test_idempotence_and_encoding_flag_without_guessed_repair(self):
        text = ' [Intro]\r\n Cafe\u0301\t x\n\n\n â? no'
        clean = module.clean_lyrics(text)
        self.assertEqual(module.clean_lyrics(clean), clean)
        self.assertIn('â?', clean)
        self.assertTrue(module.text_features(text, clean)['lyric_encoding_review'])

    def test_full_block_repetition_is_only_flagged(self):
        text = 'alpha\nbeta\nalpha\nbeta'
        self.assertEqual(module.clean_lyrics(text), text)
        self.assertEqual(module.text_features(text, text)['lyric_full_block_repeats'], 2)

    def test_exact_duplicate_groups(self):
        flags, near, _ = module.duplicate_screen(['Hello there', 'Hello there', ' HELLO  there ', 'different'], [10,20,30,40])
        self.assertEqual([f['lyric_raw_duplicate_size'] for f in flags], [2,2,1,1])
        self.assertEqual([f['lyric_normalized_duplicate_size'] for f in flags], [3,3,3,1])
        self.assertEqual(flags[2]['lyric_duplicate_group_id'], 10)
        self.assertEqual(near, [])

    def test_near_duplicate_retrieval_ignores_unique_shingles(self):
        words = [f'token{i}' for i in range(100)]
        a = ' '.join(words)
        b = ' '.join(['changed'] + words[1:])
        flags, near, candidates = module.duplicate_screen([a,b], [1,2])
        self.assertEqual(candidates, 1)
        self.assertEqual(len(near), 1)
        self.assertTrue(all(f['lyric_near_duplicate_candidate'] for f in flags))

    def test_preservation_of_all_source_fields(self):
        source = pl.DataFrame({'billboard_source_row': [1,2], 'lyrics': [' x ', 'y'], 'top10': [1,0], 'energy_median': [.2,.8]})
        output = source.with_columns(pl.Series('lyrics_clean', ['x','y']))
        module.validate_preservation(source, output)
        with self.assertRaises(ValueError):
            module.validate_preservation(source, output.with_columns(pl.lit(0).alias('top10')))
        with self.assertRaises(ValueError):
            module.validate_preservation(source, output.head(1))


if __name__ == '__main__':
    unittest.main()
