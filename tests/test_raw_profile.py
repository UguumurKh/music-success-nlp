"""Small boundary checks for profiling definitions; no access to real raw data."""
import importlib.util
from pathlib import Path
import unittest
import tempfile

import polars as pl

spec = importlib.util.spec_from_file_location("profile_raw", Path(__file__).resolve().parents[1] / "src/01_profile_raw_data.py")
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)


class ProfileTests(unittest.TestCase):
    def test_strict_parse_failure_and_lossless_override(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "chart.csv"
            path.write_text("Weeks in Charts\n1\n-\n3\n", encoding="utf-8")
            frame = pl.scan_csv(path, infer_schema_length=1, ignore_errors=False)
            with self.assertRaises(pl.exceptions.ComputeError):
                profile.general(frame, frame.collect_schema(), "Billboard")
            corrected = pl.scan_csv(path, infer_schema_length=1, ignore_errors=False,
                                    schema_overrides=profile.OVERRIDES["Billboard"])
            self.assertEqual(profile.collect(corrected).to_series().to_list(), ["1", "-", "3"])

    def test_null_blank_and_duplicate_semantics(self):
        frame = pl.DataFrame({"title": [None, "", " ", "a", "a"]}).lazy()
        result = profile.general(frame, frame.collect_schema(), "Billboard")
        self.assertEqual(result["columns"][0]["missing_count"], 1)
        self.assertEqual(result["columns"][0]["blank_count"], 2)
        self.assertEqual(result["exact_duplicate_excess_rows"], 1)
        counts = profile.duplicates(frame, ["title"])
        self.assertEqual(counts["duplicate_excess_rows"], 1)
        self.assertEqual(counts["rows_in_duplicate_groups"], 2)
        self.assertEqual(counts["unique_non_null_values"], 3)

    def test_lyrics_never_disclosed_and_other_text_bounded(self):
        frame = pl.DataFrame({"lyrics": ["a complete short lyric"], "title": ["x" * 1000]}).lazy()
        row = profile.examples(frame, frame.collect_schema())[0]
        self.assertEqual(row["lyrics"], "[lyrics omitted]")
        self.assertEqual(len(row["title"]), 200)

    def test_word_denominator_quantiles_and_audio_invalid_values(self):
        frame = pl.DataFrame({"id": ["a", "b", "c", "d"], "name": ["a"] * 4,
            "artists": ["b"] * 4, "lyrics": [None, " ", "a b", " ".join(["a"] * 20)],
            "energy": [0.0, 1.0, 2.0, float("nan")], "key": ["C", "-1", "12", None]}).lazy()
        result = profile.spotify(frame, frame.collect_schema())
        words = result["lyric_words"]
        self.assertEqual(words["non_empty_lyrics"], 2)
        self.assertEqual(words["fewer_than_20_pct_of_non_empty"], 50)
        self.assertEqual(words["median"], 11)
        self.assertEqual(words["p25"], 6.5)
        self.assertEqual(result["audio"]["energy"]["outside_expected_range_count"], 1)
        self.assertEqual(result["audio"]["energy"]["non_finite_count"], 1)
        self.assertEqual(result["audio"]["key"]["non_numeric_count"], 1)
        self.assertEqual(result["audio"]["key"]["outside_expected_range_count"], 1)


if __name__ == "__main__":
    unittest.main()
