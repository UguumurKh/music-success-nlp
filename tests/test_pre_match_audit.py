import importlib.util
from datetime import date
from pathlib import Path
import unittest

import polars as pl

spec = importlib.util.spec_from_file_location("pre_match_audit", Path(__file__).resolve().parents[1] / "src/02b_pre_match_audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class PerformerTests(unittest.TestCase):
    def test_expected_patterns(self):
        for text, expected in [
            ("Adele & Eg White > songwriters (Adele)", "Adele"),
            ("Tom Higgenson > songwriter (Plain White T's)", "Plain White T's"),
            ("Shawn Carter ... > songwriters (Rihanna Featuring Jay-Z)", "Rihanna Featuring Jay-Z"),
            ("U2 (Bono; Adam Clayton; Edge & Larry Mullen Jr.) > songwriters (U2)", "U2"),
            ("Writer > songwriters (Lady Gaga & Bruno Mars)", "Lady Gaga & Bruno Mars"),
            ("Writer > songwriter (A And B; C)", "A And B; C"),
            ("Writer > songwriter (Name (Alias))", "Name (Alias)"),
            ("Writer > songwriter (credit) (Final Performer)", "Final Performer"),
        ]:
            with self.subTest(text=text):
                performer, success, _ = audit.parse_performer(text)
                self.assertTrue(success)
                self.assertEqual(performer, expected)

    def test_missing_malformed_or_ambiguous_patterns(self):
        for value in [None, "", "Writer (Artist)", "Writer > songwriter", "Writer > songwriter (A",
                      "Writer > songwriter (A))", "Writer > songwriter (A) trailing",
                      "Writer > songwriter ( )", "X > songwriter (A) > songwriters (B)"]:
            with self.subTest(value=value):
                self.assertFalse(audit.parse_performer(value)[1])
        self.assertEqual(audit.parse_performer(None)[2], "missing_producers")
        self.assertEqual(audit.parse_performer("X > songwriter ()"), ("", False, "blank_performer"))

    def test_original_columns_and_encoding_flags(self):
        frame = pl.DataFrame({"producers": ["Writer > songwriters (Beyonc\ufffd)"],
                              "artist": ["Original"], "song_or_album": ["X (Single)"], "title_norm": ["x single"]})
        result = audit.audit_grammy(frame)
        self.assertTrue(result.select(frame.columns).equals(frame))
        self.assertTrue(result["performer_contains_replacement_character"][0])
        self.assertEqual(result["title_match_norm"][0], "x")


class TitleTests(unittest.TestCase):
    def test_only_exact_trailing_single_label(self):
        for title, expected in [("Say My Name (Single)", "say my name"), ("I Try (Single)", "i try"),
            ("X (Single)   ", "x"), ("X (single)", "x single"), ("X (Single) Remix", "x single remix"),
            ("Single Ladies (Put A Ring On It)", "single ladies put a ring on it"),
            ("Montero (Call Me By Your Name)", "montero call me by your name"),
            ("A Bar Song (Tipsy)", "a bar song tipsy")]:
            self.assertEqual(audit.title_match_norm(title), expected)
        self.assertIsNone(audit.title_match_norm(None))

    def test_new_duplicate_key_detected(self):
        frame = pl.DataFrame({"source_row": [1, 2], "year": [2000, 2000], "producers": ["W > songwriter (A)"] * 2,
            "song_or_album": ["Song (Single)", "Song"], "title_norm": ["song single", "song"]})
        result = audit.audit_grammy(frame)
        self.assertEqual(audit.duplicate_keys(result, "title_norm", "performer_norm"), [])
        self.assertEqual(len(audit.duplicate_keys(result, "title_match_norm", "performer_norm")), 1)


class ChartTests(unittest.TestCase):
    def test_gap_overlap_and_consecutive_week(self):
        for day, expected in [(1, "overlapping date ranges"), (8, "consecutive weekly dates"), (15, "gap")]:
            rows = [{"Song": "A", "first_chart_date": date(2000, 1, 1), "last_chart_date": date(2000, 1, 1)},
                    {"Song": "B", "first_chart_date": date(2000, 1, day), "last_chart_date": date(2000, 1, day)}]
            self.assertEqual(audit.compare_periods(rows)[0]["relationship"], expected)


if __name__ == "__main__":
    unittest.main()
