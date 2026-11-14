import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import polars as pl

spec = importlib.util.spec_from_file_location("match_policy", Path(__file__).resolve().parents[1] / "src/05_apply_match_policy.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


def source(titles=None, artists=None):
    titles, artists = titles or ["Song"], artists or ["Artist Featuring Guest"]
    return pl.DataFrame({"source_row": list(range(1, len(titles) + 1)), "Song": titles, "Artist": artists,
        "title_norm": [policy.normalize_text(t) for t in titles],
        "artist_norm": [policy.normalize_text(a) for a in artists], "top10": [1] * len(titles)})


def candidates(src, titles=None, artists=None, tiers=None):
    n = len(titles or src["Song"].to_list())
    frame = pl.DataFrame({"billboard_source_row": [src["source_row"][i % src.height] for i in range(n)],
        "billboard_title_norm": [src["title_norm"][i % src.height] for i in range(n)],
        "billboard_artist_norm": [src["artist_norm"][i % src.height] for i in range(n)],
        "billboard_Artist": [src["Artist"][i % src.height] for i in range(n)],
        "spotify_id": [f"id{i}" for i in range(n)],
        "spotify_title_norm": [policy.normalize_text(t) for t in (titles or src["Song"].to_list())],
        "spotify_artist_norm": [policy.normalize_text(a) for a in (artists or src["Artist"].to_list())],
        "spotify_artists": artists or src["Artist"].to_list()})
    return frame.with_columns(pl.Series("candidate_tier", tiers)) if tiers is not None else frame


def empty_variant(src):
    return candidates(src, tiers=[1] * src.height).head(0)


class ArtistPolicyTests(unittest.TestCase):
    def test_one_marker_and_both_agree(self):
        for marker in ["Featuring", "feat.", "feat", "ft.", "FT"]:
            self.assertTrue(policy.safe_artist_rule(f"Artist {marker} Guest", "Artist")[0])
            self.assertTrue(policy.safe_artist_rule("Artist", f"Artist {marker} Guest")[0])
            self.assertTrue(policy.safe_artist_rule("Artist Featuring Guest", f"Artist {marker} Guest")[0])

    def test_conflicts_missing_and_unusable_suffix(self):
        for left, right in [("Artist Featuring A", "Artist feat. B"), ("Artist feat.", "Artist"),
                            ("Artist feat. !!!", "Artist"), (None, "Artist"), ("Featuring Guest", "Artist")]:
            self.assertFalse(policy.safe_artist_rule(left, right)[0])

    def test_group_delimiters_never_feature_markers(self):
        for name in ["Earth, Wind & Fire", "Simon and Garfunkel", "A x B", "A; B", "A, B"]:
            c = policy.artist_components(name)
            self.assertFalse(c["has_feature_marker"])
            self.assertEqual(c["primary_artist_norm"], policy.normalize_text(name))
            self.assertFalse(policy.safe_artist_rule(name, "A")[0])


class RelationshipTests(unittest.TestCase):
    def test_only_exact_and_safe_tier1_are_accepted(self):
        src = source()
        ex = candidates(src)
        var = candidates(src, titles=["Song"] * 3, artists=["Artist", "Artist", "Artist"], tiers=[1, 2, 3])
        accepted, manual, versions, *_ = policy.apply_policy(src, ex, var, "billboard")
        self.assertEqual(accepted.height, 1)
        self.assertEqual(accepted["all_match_methods"][0].to_list(), ["exact", policy.EN])
        self.assertTrue(accepted["exact_match"][0])
        self.assertTrue(accepted["safe_tier1_match"][0])
        self.assertEqual(manual.height, 0)
        self.assertEqual(versions.height, 2)

    def test_conflicting_featured_artist_goes_to_review(self):
        src = source()
        variant = candidates(src, artists=["Artist Featuring Other Guest"], tiers=[1])
        accepted, review, *_ = policy.apply_policy(src, candidates(src).head(0), variant, "billboard")
        self.assertEqual(accepted.height, 0)
        self.assertEqual(review["policy_reason"][0], "conflicting_featured_artists")

    def test_versions_cannot_be_accepted_as_base_recordings(self):
        for title in ["22 (Taylor's Version)", "All Too Well (Taylor’s Version)", "Song (Artist's Version)",
                      "Song (Remix)", "Song (Live)", "Song (Acoustic)", "Song (Instrumental)"]:
            with self.subTest(title=title):
                src = source([title])
                base = title.split(" (")[0]
                # Even a mislabeled Tier-1 relationship cannot bypass full-title equality.
                var = candidates(src, titles=[base] * 3, artists=["Artist"] * 3, tiers=[1, 2, 3])
                accepted, manual, versions, *_ = policy.apply_policy(src, candidates(src).head(0), var, "billboard")
                self.assertEqual(accepted.height, 0)
                self.assertEqual(manual.height, 1)
                self.assertEqual(versions.height, 2)

    def test_sing_and_sing_punctuation_both_quarantined(self):
        src = source(["Sing", "Sing!"], ["Glee Cast", "Glee Cast"])
        accepted, _, _, review, coll, _ = policy.apply_policy(src, candidates(src), empty_variant(src), "billboard")
        self.assertEqual(accepted.height, 0)
        self.assertEqual(coll["exact"], {1, 2})
        self.assertEqual(set(review["Song"]), {"Sing", "Sing!"})

    def test_tier1_source_collision_blocks_safe_pair(self):
        src = source(["Song", "Song"], ["Artist Featuring A", "Artist Featuring B"])
        accepted, review, *_ = policy.apply_policy(src, candidates(src).head(0),
            candidates(src, artists=["Artist", "Artist"], tiers=[1, 1]), "billboard")
        self.assertEqual(accepted.height, 0)
        self.assertEqual(review.height, 2)
        self.assertEqual(set(review["policy_reason"]), {"source_normalization_collision"})

    def test_pair_dedup_retains_every_id_and_method(self):
        result = policy.deduplicate_methods([(1, "x", "exact"), (1, "x", "exact"),
            (1, "x", policy.EN), (1, "y", policy.EN)], source())
        self.assertEqual(result.height, 2)
        self.assertEqual(set(result["spotify_id"]), {"x", "y"})
        self.assertEqual(result["strongest_match_method"].to_list(), ["exact", policy.EN])

    def test_all_125_bg_pairs_unchanged_variant_remains_review(self):
        root = Path(__file__).resolve().parents[1]
        exact = pl.read_parquet(root / "data/interim/billboard_grammy_exact_candidates.parquet")
        variant = pl.read_parquet(root / "data/interim/billboard_grammy_variant_candidates.parquet")
        accepted, review = policy.billboard_grammy_policy(exact, variant)
        self.assertEqual(accepted.height, 125)
        self.assertTrue(accepted.equals(exact))
        self.assertTrue(review.select(variant.columns).equals(variant))
        self.assertEqual(review.select("billboard_source_row", "grammy_source_row").unique().height, 1)


class ConsolidationTests(unittest.TestCase):
    def build(self):
        src = source([f"Song {i}" for i in range(6)], ["A"] * 6)
        rows, methods = [], []
        for source_id in range(1, 7):
            for j in range(1 if source_id == 1 else 2):
                track = f"{source_id}-{j}"
                row = {"source_row": len(rows) + 1, "id": track, "album_name": f"album{j}",
                    "lyric_sha256": f"hash{j}" if source_id in (4, 5) else "hash",
                    "lyrics_missing": source_id == 6, "lyrics_blank": False,
                    **{c: .5 for c in policy.AUDIO}}
                row["energy"] = float(j) if source_id in (3, 5) else .5
                rows.append(row)
                methods.append((source_id, track, "exact"))
        return src, policy.deduplicate_methods(methods, src), pl.DataFrame(rows)

    def test_categories_exhaustive_and_all_ids_retained(self):
        src, accepted, sp = self.build()
        stats = policy.consolidate(accepted, src, sp)
        self.assertEqual(stats["consolidation_status"].to_list(), policy.STATUSES)
        self.assertEqual(stats["distinct_spotify_ids"].sum(), accepted.height)
        self.assertEqual(stats["source_row"].n_unique(), stats.height)

    def test_outcome_never_changes_acceptance_or_consolidation(self):
        src, accepted, sp = self.build()
        changed = src.with_columns(pl.lit(0).alias("top10"))
        original = policy.consolidate(accepted, src, sp)
        revised = policy.consolidate(accepted, changed, sp)
        self.assertTrue(original.drop("top10").equals(revised.drop("top10")))
        a = source()
        b = a.with_columns(pl.lit(0).alias("top10"))
        for frame in [a, b]:
            result, *_ = policy.apply_policy(frame, candidates(frame), empty_variant(frame), "billboard")
            self.assertEqual(result["spotify_id"].to_list(), ["id0"])

    def test_missing_hash_overrides_single_id(self):
        src, accepted, sp = self.build()
        sp = sp.with_columns(pl.lit(None, dtype=pl.String).alias("lyric_sha256"))
        result = policy.consolidate(accepted, src, sp)
        self.assertEqual(set(result["consolidation_status"]), {"missing_lyrics_information"})

    def test_parquet_roundtrip(self):
        _, accepted, _ = self.build()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "accepted.parquet"
            accepted.write_parquet(path)
            loaded = pl.read_parquet(path)
            self.assertEqual(loaded.schema, accepted.schema)
            self.assertTrue(loaded.equals(accepted))


class StatisticsAndIntegrityTests(unittest.TestCase):
    def test_equal_proportions_and_direction(self):
        equal = policy.compare_coverage(50, 100, 50, 100)
        self.assertEqual(equal["z_statistic"], 0)
        self.assertEqual(equal["two_sided_p_value"], 1)
        positive = policy.compare_coverage(80, 100, 50, 100)
        self.assertAlmostEqual(positive["difference_percentage_points"], 30)
        self.assertAlmostEqual(positive["risk_ratio"], 1.6)
        self.assertGreater(positive["difference_95pct_ci_percentage_points"][0], 0)
        self.assertLess(positive["two_sided_p_value"], .001)
        self.assertNotIn("z_statistic", policy.compare_coverage(17, 25, 88, 125, test=False))

    def test_raw_csvs_never_opened_and_protected_file_changes_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ["data/raw", "data/interim", "reports", "src", "tests"]:
                (root / folder).mkdir(parents=True)
            raw = root / "data/raw/lyrics.csv"
            raw.write_text("do not read")
            (root / "README.md").write_text("old")
            actual_open = Path.open
            def guarded(path, *args, **kwargs):
                if path == raw:
                    raise AssertionError("Raw CSV was opened")
                return actual_open(path, *args, **kwargs)
            with patch.object(policy, "ROOT", root), patch.object(Path, "open", guarded):
                before = policy.protected_snapshot()
                self.assertEqual(before, policy.protected_snapshot())
                (root / "README.md").write_text("changed")
                self.assertNotEqual(before, policy.protected_snapshot())


if __name__ == "__main__":
    unittest.main()
