import importlib.util
from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import polars as pl

spec = importlib.util.spec_from_file_location("review8a", Path(__file__).resolve().parents[1] / "src/08a_prepare_grammy_billboard_review.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def grammy():
    return pl.DataFrame({"source_row": [10], "year": [2020], "song_or_album": ["Our Song"],
        "performer_extracted": ["Singer"], "title_norm": ["our song"], "title_match_norm": ["our song"],
        "performer_norm": ["singer"]})


def billboard(years, titles=None, artists=None):
    titles = titles or ["Our Song"] * len(years)
    artists = artists or ["Singer"] * len(years)
    return pl.DataFrame({"source_row": list(range(1, len(years) + 1)), "Song": titles, "Artist": artists,
        "title_norm": [m.normalize_text(s) for s in titles], "artist_norm": [m.normalize_text(s) for s in artists],
        "first_chart_date": [date(y, 1, 1) for y in years]})


def run(b, g=None, accepted=None):
    return m.prepare(grammy() if g is None else g, b,
        pl.DataFrame({"grammy_source_row": []}, schema={"grammy_source_row": pl.Int64}) if accepted is None else accepted,
        pl.DataFrame(schema={"grammy_source_row": pl.Int64, "billboard_source_row": pl.Int64, "candidate_tier": pl.Int64}))


class ReviewTests(unittest.TestCase):
    def test_initial_window_excludes_even_perfect_outside_years(self):
        out, coverage = run(billboard([2017, 2018, 2019, 2020, 2021, 2022]))
        self.assertEqual(out["billboard_source_row"].to_list(), [3, 4])
        self.assertEqual(coverage[0]["search_window"], "initial_0_to1")

    def test_widen_only_without_plausible_initial_and_boundaries(self):
        out, coverage = run(billboard([2017, 2018, 2020, 2021, 2022],
            titles=["Our Song", "Our Song", "Zzzzz", "Our Song", "Our Song"]))
        self.assertEqual(out["billboard_source_row"].to_list(), [2, 4, 3])
        self.assertEqual(set(out["search_window"]), {"widened_minus1_to2"})
        self.assertTrue(coverage[0]["has_plausible_candidate"])

    def test_ranking_prefers_similarity_and_limits_five(self):
        b = billboard([2020] * 7, titles=["Zzzz", "Our Songs", "Our Song", "Our Song!", "Our Song?", "Our Song.", "Our Song"])
        out, _ = run(b)
        self.assertEqual(out.height, 5)
        self.assertEqual(out["billboard_source_row"].to_list(), [3, 4, 5, 6, 7])
        self.assertEqual(out["candidate_rank"].to_list(), [1, 2, 3, 4, 5])

    def test_deterministic_ties_and_source_permutations(self):
        b = billboard([2020] * 7)
        first, _ = run(b)
        second, _ = run(b.reverse())
        self.assertTrue(first.equals(second))
        self.assertEqual(first["billboard_source_row"].to_list(), [1, 2, 3, 4, 5])

    def test_exclusion_uses_distinct_accepted_grammy_ids(self):
        g = pl.concat([grammy(), grammy().with_columns(pl.lit(11, dtype=pl.Int64).alias("source_row"))])
        out, _ = run(billboard([2020]), g=g, accepted=pl.DataFrame({"grammy_source_row": [10, 10]}))
        self.assertEqual(out["grammy_source_row"].to_list(), [11])

    def test_outcomes_and_lyrics_never_enter_output_or_ranking(self):
        b = billboard([2020, 2020]).with_columns(pl.Series("top10", [1, 0]), pl.Series("peak_rank", [1, 100]),
            pl.Series("chart_weeks", [100, 1]), pl.lit("PRIVATE").alias("lyrics"))
        g = grammy().with_columns(pl.lit(1).alias("grammy_winner"))
        one, _ = run(b, g=g)
        two, _ = run(b.with_columns(pl.col("top10").reverse(), pl.col("peak_rank").reverse(), pl.col("chart_weeks").reverse()),
                     g=g.with_columns(pl.lit(0).alias("grammy_winner")))
        self.assertTrue(one.equals(two))
        self.assertFalse(set(one.columns) & {"top10", "peak_rank", "chart_weeks", "grammy_winner", "lyrics"})
        self.assertNotIn("PRIVATE", str(one.to_dicts()))
        self.assertEqual(one["manual_decision"].to_list(), ["", ""])

    def test_primary_artist_keeps_groups_and_splits_only_explicit_features(self):
        for name in ["Earth, Wind & Fire", "Simon And Garfunkel", "A; B"]:
            self.assertEqual(m.primary(name), m.normalize_text(name))
        for name in ["Singer Featuring Guest", "Singer feat. Guest", "Singer ft Guest"]:
            self.assertEqual(m.primary(name), "singer")

    def test_scores_formula_and_strength_and_blanks(self):
        g, b = grammy().to_dicts()[0], billboard([2020]).to_dicts()[0]
        s = m.scores(g, b)
        self.assertEqual(s["combined_diagnostic_score"], 100)
        self.assertEqual(s["diagnostic_strength"], "strong")
        b["title_norm"] = "our songs"
        s = m.scores(g, b)
        self.assertAlmostEqual(s["combined_diagnostic_score"], round(.6 * m.ratio("our song", "our songs") + 40, 6), places=5)
        b["title_norm"] = "our song darkchild version"
        self.assertEqual(m.scores(g, b)["diagnostic_strength"], "weak")
        self.assertEqual(m.similarity(None, None), 0)
        self.assertEqual(m.similarity("", ""), 0)

    def test_weak_candidates_and_empty_pool_are_not_acceptance(self):
        out, coverage = run(billboard([2020], titles=["Zzzz"]))
        self.assertFalse(coverage[0]["has_plausible_candidate"])
        self.assertEqual(out["diagnostic_strength"][0], "weak")
        out, coverage = run(billboard([2010]))
        self.assertEqual(out.height, 1)
        self.assertEqual(out["candidate_status"][0], "no_candidate")
        self.assertIsNone(out["billboard_source_row"][0])
        self.assertIsNone(out["candidate_rank"][0])
        self.assertEqual(coverage[0]["candidate_count"], 0)

    def test_all_accepted_yields_empty_typed_review(self):
        out, coverage = run(billboard([2020]), accepted=pl.DataFrame({"grammy_source_row": [10]}))
        self.assertEqual(out.height, 0)
        self.assertEqual(coverage, [])
        self.assertIn("manual_decision", out.columns)

    def test_csv_roundtrip_candidates_and_empty_pool_preserve_blank_review_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            for year in [2020, 2010]:
                out, _ = run(billboard([year]))
                path = Path(directory) / "review.csv"
                m.save_review(out, path)
                loaded = pl.read_csv(path, empty_string_is_null=False)
                self.assertEqual(loaded["manual_decision"].to_list(), [""])
                self.assertEqual(loaded["reviewer_note"].to_list(), [""])

    def test_prior_review_provenance_not_ranking(self):
        previous = pl.DataFrame({"grammy_source_row": [10, 10], "billboard_source_row": [2, 2], "candidate_tier": [2, 3]})
        out, _ = m.prepare(grammy(), billboard([2020, 2020]), pl.DataFrame({"grammy_source_row": []}), previous)
        self.assertEqual(out["billboard_source_row"].to_list(), [1, 2])
        self.assertEqual(out["prior_variant_review_tiers"].to_list(), ["", "2 | 3"])

    def test_snapshot_protects_existing_files_without_opening_raw_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data/raw").mkdir(parents=True)
            (root / "reports").mkdir()
            raw = root / "data/raw/raw.csv"
            raw.write_text("private")
            protected = root / "reports/old.md"
            protected.write_text("original")
            opener = Path.open
            def guarded(path, *args, **kwargs):
                if path == raw:
                    raise AssertionError("raw opened")
                return opener(path, *args, **kwargs)
            with patch.object(Path, "open", guarded):
                before = m.snapshot(root)
                (root / m.OUTPUTS[0]).write_text("allowed")
                self.assertEqual(before, m.verify_protected(before, root))
                protected.write_text("altered")
                with self.assertRaisesRegex(AssertionError, "old.md"):
                    m.verify_protected(before, root)


if __name__ == "__main__":
    unittest.main()
