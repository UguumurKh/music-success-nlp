import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import polars as pl

spec = importlib.util.spec_from_file_location("consolidate_inputs", Path(__file__).resolve().parents[1] / "src/07_consolidate_song_inputs.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def content(texts, ids=None, energies=None, keys=None, modes=None):
    n = len(texts)
    rows = [{"id": (ids or [f"id{i}" for i in range(n)])[i], "source_row": i + 1, "lyrics": text,
             **{c: .5 for c in module.NUMERIC}, "key": (keys or ["C"] * n)[i],
             "mode": (modes or ["Major"] * n)[i]} for i, text in enumerate(texts)]
    if energies is not None:
        for row, energy in zip(rows, energies):
            row["energy"] = energy
    return module.comparison_content(pl.DataFrame(rows, infer_schema_length=None))


def accepted(ids, outcome=1):
    return pl.DataFrame({"source_row": [1] * len(ids), "Song": ["Source Song"] * len(ids), "top10": [outcome] * len(ids),
        "spotify_id": ids, "all_match_methods": [["exact"]] * len(ids), "exact_match": [True] * len(ids),
        "safe_tier1_match": [False] * len(ids), "strongest_match_method": ["exact"] * len(ids)})


class LyricsTests(unittest.TestCase):
    def test_nfkc_casefold_whitespace_only_and_original_preserved(self):
        text = "  ＨＥＬＬＯ!\nStraße\t chorus chorus  "
        frame = content([text, "hello! strasse chorus chorus"])
        self.assertEqual(frame["lyrics"][0], text)
        self.assertEqual(frame["lyrics_compare_norm"].to_list(), ["hello! strasse chorus chorus"] * 2)
        self.assertEqual(frame["lyrics_compare_sha256"].n_unique(), 1)
        self.assertEqual(frame["lyrics_compare_word_count"].to_list(), [4, 4])
        self.assertNotEqual(module.lyrics_compare_norm("hello!"), module.lyrics_compare_norm("hello"))

    def test_single_id_and_identical_content(self):
        for texts in [["Text"], ["Text", "Text"]]:
            result, _ = module.consolidate_records(content(texts).to_dicts())
            self.assertTrue(result["strict_consistency_sample"])
            self.assertTrue(result["lyrics_consistent_across_ids"])
            self.assertTrue(result["audio_consistent_across_ids"])
            self.assertEqual(result["lyric_resolution_confidence"], "high")

    def test_case_whitespace_differences_one_group_raw_hashes_retained(self):
        result, _ = module.consolidate_records(content(["One two", " ONE\nTWO "]).to_dicts())
        self.assertEqual(result["distinct_raw_lyric_hashes"], 2)
        self.assertEqual(result["distinct_comparison_lyric_hashes"], 1)
        self.assertTrue(result["lyrics_consistent_across_ids"])

    def test_majority_group_wins_over_smallest_id(self):
        records = content(["Different", "Majority", "MAJORITY"], ids=["a", "c", "b"]).to_dicts()
        result, ledger = module.consolidate_records(records)
        self.assertEqual(result["lyric_representative_spotify_id"], "b")
        self.assertEqual(result["lyrics"], "MAJORITY")
        self.assertEqual(result["dominant_lyric_group_size"], 2)
        self.assertEqual(result["lyric_resolution_confidence"], "medium")
        self.assertEqual(sum(r["is_lyric_representative"] for r in ledger), 1)

    def test_tied_groups_lexical_break_reproducible(self):
        records = content(["Group B", "Group A", "group b", "group a"], ids=["z", "b", "a", "c"]).to_dicts()
        result, _ = module.consolidate_records(records)
        reverse, _ = module.consolidate_records(list(reversed(records)))
        self.assertEqual(result, reverse)
        self.assertEqual(result["lyric_representative_spotify_id"], "a")
        self.assertTrue(result["lyric_group_tie"])
        self.assertEqual(result["lyric_resolution_confidence"], "low")

    def test_unique_plurality_without_majority_is_flagged(self):
        result, _ = module.consolidate_records(content(["A", "A", "B", "C"]).to_dicts())
        self.assertFalse(result["lyric_group_tie"])
        self.assertTrue(result["lyric_unique_plurality_without_majority"])
        self.assertEqual(result["lyric_resolution_confidence"], "low")


class AudioTests(unittest.TestCase):
    def test_all_ids_contribute_not_selected_lyric_group(self):
        result, _ = module.consolidate_records(content(["Minority", "A", "A"], ids=["a", "b", "c"], energies=[10., 1., 3.]).to_dicts())
        self.assertEqual(result["lyric_representative_spotify_id"], "b")
        self.assertEqual(result["energy_median"], 3.)
        self.assertEqual(result["energy_min"], 1.)
        self.assertEqual(result["energy_max"], 10.)
        self.assertEqual(result["energy_range"], 9.)
        self.assertEqual(result["audio_candidate_id_count"], 3)
        self.assertEqual(result["audio_resolution_confidence"], "medium")

    def test_categorical_unique_mode_and_ties(self):
        unique, _ = module.consolidate_records(content(["A"] * 3, keys=["C", "C", "D"], modes=["Major", "Minor", "Major"]).to_dicts())
        self.assertEqual(unique["key_mode"], "C")
        self.assertEqual(unique["mode_mode"], "Major")
        tied, _ = module.consolidate_records(content(["A"] * 2, keys=["C", "D"], modes=["Major", "Minor"]).to_dicts())
        for c in ["key", "mode"]:
            self.assertIsNone(tied[f"{c}_mode"])
            self.assertTrue(tied[f"{c}_mode_tie"])
        self.assertEqual(tied["audio_resolution_confidence"], "low")
        self.assertFalse(tied["strict_consistency_sample"])

    def test_missing_audio_mode_ignores_null_and_single_strict(self):
        result, _ = module.consolidate_records(content(["A", "A"], energies=[None, 2.], keys=[None, "C"]).to_dicts())
        self.assertEqual(result["energy_median"], 2.)
        self.assertEqual(result["key_mode"], "C")
        self.assertFalse(result["key_mode_tie"])
        self.assertTrue(result["any_missing_audio_value"])
        self.assertEqual(result["audio_resolution_confidence"], "low")
        self.assertFalse(result["strict_consistency_sample"])
        single, _ = module.consolidate_records(content(["A"], energies=[None]).to_dicts())
        self.assertTrue(single["strict_consistency_sample"])
        self.assertIsNone(single["energy_median"])


class IntegrationTests(unittest.TestCase):
    def test_source_once_representative_membership_raw_equality_and_outcome_blind(self):
        data = content(["Raw lyric!", "Other lyric!", "Raw lyric!"], ids=["a", "b", "c"], energies=[1., 2., 8.])
        result, ledger = module.consolidate_source(accepted(["a", "b", "c"]), data, "billboard")
        changed, _ = module.consolidate_source(accepted(["a", "b", "c"], outcome=0), data, "billboard")
        self.assertEqual(result.height, 1)
        self.assertTrue(result.drop("top10").equals(changed.drop("top10")))
        self.assertIn(result["lyric_representative_spotify_id"][0], {"a", "b", "c"})
        self.assertEqual(result["lyrics"][0], "Raw lyric!")
        self.assertEqual(ledger.height, 3)

    def test_reports_have_no_lyric_text_and_roundtrip(self):
        data = content(["SECRET TEXT ONE", "SECRET TEXT TWO"])
        result, ledger = module.consolidate_source(accepted(["id0", "id1"]), data, "grammy")
        safe = module.safe_report_frame(result)
        self.assertNotIn("lyrics", safe.columns)
        self.assertNotIn("lyrics_compare_norm", safe.columns)
        self.assertNotIn("SECRET TEXT", safe.write_csv())
        self.assertNotIn("SECRET TEXT", ledger.write_csv())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "roundtrip.parquet"
            result.write_parquet(path)
            loaded = pl.read_parquet(path)
            self.assertEqual(loaded.schema, result.schema)
            self.assertTrue(loaded.equals(result))

    def test_accepted_input_grains_match_required_output_counts(self):
        root = Path(__file__).resolve().parents[1]
        for kind, expected in [("billboard", 6639), ("grammy", 111)]:
            frame = pl.read_parquet(root / f"data/interim/{kind}_spotify_accepted_candidates.parquet")
            self.assertEqual(frame["source_row"].n_unique(), expected)

    def test_confidences_exhaustive(self):
        for texts, energies, keys in [(["A"], [.5], ["C"]), (["A", "A", "B"], [.5, .6, .7], ["C"] * 3),
                                       (["A", "B"], [None, .5], ["C", "D"])]:
            result, _ = module.consolidate_records(content(texts, energies=energies, keys=keys).to_dicts())
            for field in ["lyric_resolution_confidence", "audio_resolution_confidence"]:
                self.assertIn(result[field], {"high", "medium", "low"})

    def test_existing_file_snapshot_unchanged_and_detects_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ["data/interim", "data/raw", "reports", "src", "tests"]:
                (root / folder).mkdir(parents=True)
            (root / "README.md").write_text("keep")
            (root / "data/interim/existing.parquet").write_bytes(b"protected")
            with patch.object(module, "ROOT", root):
                before = module.snapshot()
                self.assertEqual(before, module.snapshot())
                (root / "data/interim/existing.parquet").write_bytes(b"changed")
                self.assertNotEqual(before, module.snapshot())


if __name__ == "__main__":
    unittest.main()
