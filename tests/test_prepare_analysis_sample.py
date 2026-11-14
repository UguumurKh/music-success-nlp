"""Focused date, song-grain and aggregate-calculation tests (synthetic text only)."""
import importlib.util
from datetime import date
from pathlib import Path
import unittest

import polars as pl

spec = importlib.util.spec_from_file_location(
    "analysis_sample", Path(__file__).resolve().parents[1] / "src/09_prepare_analysis_sample.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    frame = pl.DataFrame({
        "billboard_source_row": [1, 2, 3, 4],
        "first_chart_date": [date(2000, 1, 1), date(2022, 12, 31), date(2023, 1, 1), None],
        "Artist": ["A", "A", "B", None], "artist_norm": ["a", "a", "b", None],
        "top10": [1, 0, 1, None], "peak_rank": [1, 20, 10, None],
        "lyrics": ["one two", " x\ny ", "", None],
        "lyric_resolution_confidence": ["high", "low", "medium", None],
        **{c: [True, False, False, None] for c in module.FLAGS},
        **{c: [0.0, 1.0, None, float('nan')] for c in module.NUMERIC},
        "key_mode": ["C", None, "D", " "], "mode_mode": ["Major", "Minor", "Major", None],
    })
    return frame


class AnalysisSampleTests(unittest.TestCase):
    def test_inclusive_boundaries_nulls_and_source_preservation(self):
        frame = pl.DataFrame({"billboard_source_row": list(range(6)),
                              "first_chart_date": [date(1999, 12, 31), date(2000, 1, 1),
                                                   date(2010, 6, 1), date(2022, 12, 31),
                                                   date(2023, 1, 1), None],
                              "untouched": ["a", "b", "c", "d", "e", "f"]})
        original = frame.clone()
        result = module.restrict_dates(frame)
        self.assertEqual(result['billboard_source_row'].to_list(), [1, 2, 3])
        self.assertEqual(result.schema, frame.schema)
        self.assertTrue(frame.equals(original))
        self.assertEqual(result['untouched'].to_list(), ['b', 'c', 'd'])

    def test_duplicate_or_null_identifier_rejected(self):
        for ids in ([1, 1, 3, 4], [1, 2, 3, None]):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                module.restrict_dates(fixture().with_columns(pl.Series('billboard_source_row', ids)))

    def test_date_type_not_silently_coerced(self):
        with self.assertRaises(ValueError):
            module.restrict_dates(fixture().with_columns(pl.col('first_chart_date').cast(pl.String)))

    def test_population_outcomes_and_yearly_counts(self):
        s = module.summarize(fixture())
        self.assertEqual((s['n'], s['artists'], s['normalized_artists']), (4, 2, 2))
        self.assertEqual((s['top10'], s['top10_pct'], s['top10_missing']), (2, 50, 1))
        self.assertEqual(s['yearly'], {2000: 1, 2022: 1, 2023: 1, None: 1})
        self.assertEqual(s['flags']['grammy_soty_nominated'], {'true': 1, 'false': 2, 'missing': 1})
        self.assertEqual(s['confidence'], {'high': 1, 'low': 1, 'medium': 1, None: 1})
        self.assertEqual(s['top10_peak_disagreement'], 0)

    def test_audio_missingness_counts_rows_not_cells(self):
        s = module.summarize(fixture())
        self.assertEqual(s['audio_missing']['energy_median'], 2)
        self.assertEqual(s['audio_missing']['key_mode'], 2)
        self.assertEqual(s['any_audio_missing'], 3)
        changed = fixture().with_columns(pl.Series('energy_median', [0., float('inf'), None, float('-inf')]))
        self.assertEqual(module.summarize(changed)['audio_missing']['energy_median'], 3)

    def test_raw_lengths_and_linear_percentiles(self):
        s = module.summarize(fixture())
        self.assertEqual((s['lyrics_missing'], s['lyrics_blank']), (1, 1))
        self.assertEqual(s['words']['n'], 3)
        self.assertAlmostEqual(s['words']['mean'], 4 / 3)
        self.assertEqual((s['words']['min'], s['words']['median'], s['words']['max']), (0, 2, 2))
        self.assertAlmostEqual(s['words']['p05'], .2)
        self.assertEqual(s['characters']['median'], 5)
        self.assertEqual(s['characters']['max'], 7)

    def test_report_matches_subset_and_contains_no_lyrics(self):
        frame = fixture()
        text = module.render_report(frame, module.restrict_dates(frame), 'testhash')
        self.assertIn('Retained 2 (50.00%)', text)
        self.assertIn('| Top-10 songs | 2 | 1 | 1 |', text)
        self.assertIn('| 2001 | 0 | 0 |', text)
        self.assertNotIn('one two', text)

    def test_empty_population_has_undefined_rates(self):
        s = module.summarize(fixture().head(0))
        self.assertEqual(s['n'], 0)
        self.assertIsNone(s['top10_pct'])
        self.assertIsNone(s['words']['mean'])
        self.assertIn('NA', module.render_report(fixture().head(0), fixture().head(0), 'empty'))


if __name__ == '__main__':
    unittest.main()
