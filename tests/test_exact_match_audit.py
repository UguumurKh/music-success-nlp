import importlib.util
from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import polars as pl

spec = importlib.util.spec_from_file_location("exact_audit", Path(__file__).resolve().parents[1] / "src/03_exact_match_audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def sources():
    return pl.DataFrame({"source_row": [1, 2, 3, 4], "Song": ["Sing", "Sing!", "Other", "Absent"],
        "Artist": ["Glee Cast"] * 4, "title_norm": ["sing", "sing", "other", "absent"],
        "artist_norm": ["glee cast"] * 4, "top10": [0, 0, 1, 0]})


def spotify():
    return pl.DataFrame({"source_row": [1, 2, 3, 4], "id": ["a", "a", "b", "c"],
        "title_norm": ["sing", "sing", "sing", "other"], "artist_norm": ["glee cast"] * 4,
        "lyric_sha256": ["hash1", "hash2", "hash1", None], "energy": [.5, .6, .5, .4],
        "lyrics_missing": [False, False, False, True], "lyrics_blank": [False] * 4,
        "duplicate_id_conflict": [True, True, False, False]})


class EnrichmentTests(unittest.TestCase):
    def test_all_150_original_records_and_values_preserved(self):
        root = Path(__file__).resolve().parents[1]
        original = pl.read_parquet(root / "data/interim/grammy_soty_2000_2024.parquet")
        parsed = pl.read_csv(root / "reports/grammy_performer_parse_audit.csv", infer_schema_length=None).reverse()
        enriched = audit.enrich_grammy(original, parsed)
        self.assertEqual(enriched.height, 150)
        self.assertTrue(enriched.select(original.columns).equals(original))
        self.assertTrue(set(audit.ENRICHMENT).issubset(enriched.columns))

    def test_duplicate_missing_or_altered_audit_records_rejected(self):
        root = Path(__file__).resolve().parents[1]
        original = pl.read_parquet(root / "data/interim/grammy_soty_2000_2024.parquet")
        parsed = pl.read_csv(root / "reports/grammy_performer_parse_audit.csv", infer_schema_length=None)
        bad = [pl.concat([parsed, parsed.head(1)]), parsed.slice(1),
               parsed.with_columns(pl.lit("changed").alias("song_or_album"))]
        for frame in bad:
            with self.assertRaises(ValueError):
                audit.enrich_grammy(original, frame)


class CandidateTests(unittest.TestCase):
    def test_exhaustive_mutually_exclusive_distinct_id_counts(self):
        candidates, status = audit.spotify_matches(sources(), spotify(), "billboard", "title_norm", "artist_norm")
        self.assertEqual(status.height, 4)
        self.assertEqual(status["distinct_spotify_ids"].to_list(), [2, 2, 1, 0])
        self.assertEqual(status["candidate_rows"].to_list(), [3, 3, 1, 0])
        self.assertEqual(status["match_status"].to_list(), [audit.STATUSES[2], audit.STATUSES[2], audit.STATUSES[1], audit.STATUSES[0]])
        self.assertEqual(candidates.height, 7)
        self.assertEqual(sum(audit.coverage(status)[s] for s in audit.STATUSES), status.height)

    def test_exact_keys_all_rows_and_sing_records_separate(self):
        candidates, status = audit.spotify_matches(sources(), spotify(), "billboard", "title_norm", "artist_norm")
        for row in candidates.iter_rows(named=True):
            self.assertEqual(row["billboard_title_norm"], row["spotify_title_norm"])
            self.assertEqual(row["billboard_artist_norm"], row["spotify_artist_norm"])
        sing = status.filter(pl.col("title_norm") == "sing")
        self.assertEqual(set(sing["Song"]), {"Sing", "Sing!"})
        self.assertEqual(sing["source_row"].n_unique(), 2)
        self.assertEqual(candidates.filter(pl.col("billboard_title_norm") == "sing").height, 6)

    def test_no_selection_even_when_candidates_identical_or_outcomes_change(self):
        sp = spotify().with_columns(pl.lit("same").alias("lyric_sha256"), pl.lit(.5).alias("energy"))
        candidates, status = audit.spotify_matches(sources(), sp, "billboard", "title_norm", "artist_norm")
        self.assertEqual(candidates.height, 7)
        self.assertEqual(status["distinct_spotify_ids"][0], 2)
        self.assertEqual(status["distinct_lyric_sha256"][0], 1)
        self.assertEqual(status["distinct_audio_combinations"][0], 1)
        flipped = sources().with_columns((1 - pl.col("top10")).alias("top10"))
        other, _ = audit.spotify_matches(flipped, sp, "billboard", "title_norm", "artist_norm")
        keys = ["billboard_source_row", "spotify_source_row", "spotify_id"]
        self.assertTrue(candidates.select(keys).equals(other.select(keys)))

    def test_missing_lyrics_and_audio_ambiguity(self):
        _, status = audit.spotify_matches(sources(), spotify(), "billboard", "title_norm", "artist_norm")
        self.assertEqual(status["distinct_lyric_sha256"][0], 2)
        self.assertEqual(status["distinct_audio_combinations"][0], 2)
        self.assertTrue(status["any_missing_or_blank_lyrics"][2])
        self.assertTrue(status["any_missing_lyric_hash"][2])

    def test_near_matches_are_not_fuzzy_matched(self):
        sp = spotify().with_columns(pl.lit("sing live").alias("title_norm"))
        candidates, status = audit.spotify_matches(sources(), sp, "billboard", "title_norm", "artist_norm")
        self.assertEqual(candidates.height, 0)
        self.assertEqual(set(status["match_status"]), {audit.STATUSES[0]})

    def test_missing_keys_and_invalid_ids_do_not_match(self):
        left = sources().with_columns(pl.lit("").alias("title_norm"))
        right = spotify().with_columns(pl.lit("").alias("title_norm"))
        candidates, status = audit.spotify_matches(left, right, "billboard", "title_norm", "artist_norm")
        self.assertEqual(candidates.height, 0)
        self.assertEqual(status.height, left.height)
        candidates, _ = audit.spotify_matches(sources(), spotify().with_columns(pl.lit(None, dtype=pl.String).alias("id")), "billboard", "title_norm", "artist_norm")
        self.assertEqual(candidates.height, 0)

    def test_grammy_source_records_not_lost(self):
        source = sources().rename({"title_norm": "title_match_norm", "artist_norm": "performer_norm"})
        _, status = audit.spotify_matches(source, spotify(), "grammy", "title_match_norm", "performer_norm")
        self.assertEqual(status["source_row"].to_list(), source["source_row"].to_list())
        self.assertEqual(status.height, source.height)

    def test_year_gap_no_year_filter_and_many_to_many_pairs_retained(self):
        b = sources().head(2).with_columns(pl.lit(date(2010, 10, 27)).alias("first_chart_date"))
        g = pl.DataFrame({"source_row": [9, 10, 11], "title_match_norm": ["sing"] * 3,
                          "performer_norm": ["glee cast"] * 3, "year": [2009, 2012, 2020]})
        pairs = audit.billboard_grammy_matches(b, g)
        self.assertEqual(pairs.height, 6)
        self.assertEqual(pairs["year_gap"].to_list(), [-1, 2, 10, -1, 2, 10])
        self.assertEqual(pairs["year_gap_provisionally_plausible"].sum(), 4)

    def test_parquet_roundtrip_rows_and_schema(self):
        pairs, _ = audit.spotify_matches(sources(), spotify(), "billboard", "title_norm", "artist_norm")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "data/interim").mkdir(parents=True)
            with patch.object(audit, "ROOT", root):
                audit.save_parquet(pairs, "test")
            loaded = pl.read_parquet(root / "data/interim/test.parquet")
            self.assertEqual(loaded.schema, pairs.schema)
            self.assertTrue(loaded.equals(pairs))


if __name__ == "__main__":
    unittest.main()
