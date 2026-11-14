import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import polars as pl

spec = importlib.util.spec_from_file_location("expansion_audit", Path(__file__).resolve().parents[1] / "src/04_match_expansion_audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def make_source(titles, artists, ids=None):
    frame = pl.DataFrame({"source_row": list(range(1, len(titles) + 1)), "title": titles, "artist": artists,
        "title_norm": [audit.normalize_text(t) for t in titles],
        "artist_norm": [audit.normalize_text(a) for a in artists]})
    if ids is not None:
        frame = frame.with_columns(pl.Series("id", ids))
    return audit.variants(frame, "title", "artist", "title_norm", "artist_norm")


class VariantTests(unittest.TestCase):
    def test_explicit_collaboration_markers(self):
        for marker in ["Featuring", "FEATURING", "feat.", "feat", "ft.", "FT"]:
            self.assertEqual(audit.primary_artist_norm(f"Ciara {marker} Missy Elliott"), "ciara")
        self.assertEqual(audit.primary_artist_norm("Rihanna Featuring Jay-Z"), "rihanna")
        self.assertIsNone(audit.primary_artist_norm(None))
        self.assertEqual(audit.primary_artist_norm("Little Feat"), "little feat")

    def test_group_names_not_split(self):
        for name in ["Earth, Wind & Fire", "Simon and Garfunkel", "A x B", "A; B", "A, B"]:
            self.assertEqual(audit.primary_artist_norm(name), audit.normalize_text(name))

    def test_version_suffixes(self):
        for title in ["Song (Radio Edit)", "Song - 2011 Remaster", "Song [Acoustic]", "Song (Live)",
                      "Song (Remix)", "Song [Instrumental]", "Song - Mono", "Song (Stereo)",
                      "Song [Soundtrack Version]", "Song (Remastered)", "Song (Edit)",
                      "Song (Live (London))", "Song (Remix) [Radio Edit]"]:
            with self.subTest(title=title):
                self.assertEqual(audit.title_base_norm(title), "song")

    def test_meaningful_parentheses_and_nonterminal_text_preserved(self):
        for title in ["Single Ladies (Put A Ring On It)", "Montero (Call Me By Your Name)",
                      "A Bar Song (Tipsy)", "Song (Single)", "Song (Live) Forever", "Re-Edit", "Live Forever"]:
            self.assertEqual(audit.title_base_norm(title), audit.normalize_text(title))
        self.assertIsNone(audit.title_base_norm(None))

    def test_original_fields_unchanged(self):
        frame = pl.DataFrame({"title": ["Song (Remix)"], "artist": ["A feat. B"],
                              "title_norm": ["song remix"], "artist_norm": ["a feat b"]})
        result = audit.variants(frame, "title", "artist", "title_norm", "artist_norm")
        self.assertTrue(result.select(frame.columns).equals(frame))


class ExpansionTests(unittest.TestCase):
    def test_only_previously_unmatched_and_exact_input_unchanged(self):
        source = make_source(["Exact", "Other"], ["A", "B"])
        exact = pl.DataFrame({"billboard_source_row": [1], "spotify_id": ["id1"]})
        before = exact.clone()
        left = audit.unmatched(source, exact, "billboard")
        right = make_source(["Exact", "Other"], ["A", "B"], ["id1", "id2"])
        pairs = audit.generate_candidates(left, right, "billboard", "spotify")
        self.assertEqual(set(pairs["billboard_source_row"]), {2})
        self.assertTrue(before.equals(exact))

    def test_all_tiers_satisfy_keys_and_no_id_selected(self):
        left = make_source(["Song (Remix)"], ["A Featuring B"])
        right = make_source(["Song (Remix)", "Song", "Song"], ["A", "A Featuring B", "A"], ["x", "y", "z"])
        pairs = audit.generate_candidates(left, right, "billboard", "spotify")
        self.assertEqual(set(pairs["candidate_tier"]), {1, 2, 3})
        self.assertEqual(set(pairs["spotify_id"]), {"x", "y", "z"})
        self.assertGreater(pairs.height, 3)  # a pair may legitimately appear in several tiers
        for row in pairs.iter_rows(named=True):
            for key in audit.TIERS[row["candidate_tier"]]:
                self.assertEqual(row[f"billboard_{key}"], row[f"spotify_{key}"])

    def test_sing_punctuation_records_separate(self):
        left = make_source(["Sing", "Sing!"], ["Glee Cast"] * 2)
        right = make_source(["Sing"], ["Glee Cast"], ["x"])
        pairs = audit.generate_candidates(left, right, "billboard", "spotify")
        self.assertEqual(pairs["billboard_source_row"].n_unique(), 2)
        self.assertEqual(set(pairs["billboard_title"]), {"Sing", "Sing!"})

    def test_no_fuzzy_near_match_or_blank_key_join(self):
        left = make_source(["Snog", ""], ["A", "A"])
        right = make_source(["Song", ""], ["A", "A"], ["x", "y"])
        self.assertEqual(audit.generate_candidates(left, right, "b", "s").height, 0)

    def test_incremental_counts_do_not_select_first_tier(self):
        left = make_source(["Song (Remix)"], ["A Featuring B"]).with_columns(pl.lit(1).alias("top10"))
        right = make_source(["Song (Remix)", "Song"], ["A", "A Featuring B"], ["x", "y"])
        pairs = audit.generate_candidates(left, right, "billboard", "spotify")
        stats = audit.summarize_candidates(pairs, left, "billboard", "spotify_id", 10, "top10", [(1, "Top 10")])
        self.assertEqual(stats["all_tiers_combined"]["multiple_candidates"], 1)
        self.assertEqual(sum(t["newly_covered_after_earlier_tiers"] for t in stats["tiers"]), 1)
        self.assertEqual(stats["additional_percentage_points_of_all_source"], 10)

    def test_diagnosis_exclusive_and_examples_bounded(self):
        s = make_source(["Song A", "Song B", "Song A", "Song A", "Song A"],
                        ["Artist A", "Artist B", "Artist C", "Artist D", "Artist E"], ["1", "2", "3", "4", "5"])
        left = make_source(["Song A", "New", "Song A", "New", ""],
                           ["New", "Artist A", "Artist B", "Unknown", "Artist A"])
        result = audit.diagnose(left, s)
        self.assertEqual(result["unmatched_reason"].to_list(), audit.REASONS)
        self.assertEqual(result.height, 5)
        self.assertEqual(result["spotify_ids_with_exact_title"][0], 4)
        self.assertEqual(len(result["title_example_ids"][0].split(" | ")), 3)

    def test_collision_created_and_multiple_sources_flagged(self):
        b = make_source(["Song", "Song!"], ["A", "A"])
        g = make_source(["Song"], ["A"])
        s = make_source(["Song", "Song (Remix)"], ["A", "A"], ["x", "y"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "collisions.csv"
            stats = audit.collision_tables(b, g, s, path)
            review = pl.read_csv(path)
            self.assertEqual(stats[1]["new_collision_keys"], 1)
            self.assertTrue(review.filter(pl.col("candidate_tier") == 2)["multiple_billboard_records"].all())
            self.assertEqual(review.filter(pl.col("candidate_tier") == 2)["spotify_ids"][0], 2)

    def test_parquet_roundtrip(self):
        pairs = audit.generate_candidates(make_source(["Song"], ["A"]), make_source(["Song"], ["A"], ["x"]), "b", "s")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pairs.parquet"
            pairs.write_parquet(path)
            loaded = pl.read_parquet(path)
            self.assertEqual(loaded.schema, pairs.schema)
            self.assertTrue(loaded.equals(pairs))

    def test_existing_files_fingerprinted_new_outputs_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ["data/raw", "data/interim", "reports", "src", "tests"]:
                (root / folder).mkdir(parents=True)
            (root / "README.md").write_text("existing")
            (root / "data/interim/billboard_spotify_exact_candidates.parquet").write_bytes(b"exact")
            (root / "reports/exact_match_audit.json").write_text("{}")
            (root / "reports/match_expansion_audit.json").write_text("new")
            with patch.object(audit, "ROOT", root):
                before = audit.protected_hashes()
                (root / "reports/match_expansion_audit.json").write_text("rerun")
                self.assertEqual(before, audit.protected_hashes())
            self.assertIn("data/interim/billboard_spotify_exact_candidates.parquet", before)
            self.assertIn("reports/exact_match_audit.json", before)


if __name__ == "__main__":
    unittest.main()
