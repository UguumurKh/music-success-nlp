import importlib.util
from datetime import date
from pathlib import Path
import tempfile
import unittest

import polars as pl

from music_success_nlp.normalization import add_normalized_fields, normalize_text

spec = importlib.util.spec_from_file_location("prepare_sources", Path(__file__).resolve().parents[1] / "src/02_prepare_source_tables.py")
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def weekly(rows):
    return pl.DataFrame(rows, schema=["Date", "Song", "Artist", "Rank"], orient="row").with_row_index("source_row", offset=1)


class NormalizationTests(unittest.TestCase):
    def test_unicode_punctuation_whitespace_and_quotes(self):
        self.assertEqual(normalize_text('  Beyoncé\t &  Sigur Rós — “Don’t”\n'), "beyonce sigur ros don t")
        self.assertEqual(normalize_text("L'été"), normalize_text("L’été"))
        self.assertEqual(normalize_text("AC/DC"), "ac dc")
        self.assertEqual(normalize_text("  \t"), "")
        self.assertEqual(normalize_text("!!!"), "")
        self.assertIsNone(normalize_text(None))

    def test_version_words_and_original_text_preserved(self):
        title = "Song (Live) [Remix] - Remastered Radio Edit Acoustic"
        artist = "Beyoncé & JAY-Z"
        frame = add_normalized_fields(pl.DataFrame({"title": [title], "artist": [artist]}), "title", "artist")
        self.assertEqual(frame["title"][0], title)
        self.assertEqual(frame["artist"][0], artist)
        self.assertEqual(frame["title_norm"][0], "song live remix remastered radio edit acoustic")
        self.assertEqual(frame["artist_norm"][0], "beyonce jay z")
        self.assertEqual(normalize_text(frame["title_norm"][0]), frame["title_norm"][0])


class BillboardTests(unittest.TestCase):
    def test_peak_top10_distinct_weeks_and_exact_removal(self):
        raw = weekly([("2000-01-01", "Original!", "Ártist", 20),
                      ("2000-01-08", "Original!", "Ártist", 10),
                      ("2000-01-08", "Original!", "Ártist", 10),
                      ("2000-01-01", "Eleven", "A", 11),
                      ("2000-01-01", "Winner", "A", 1)])
        songs, review, excluded, stats = prepare.prepare_billboard(raw)
        song = songs.filter(pl.col("Song") == "Original!").row(0, named=True)
        self.assertEqual(song["Artist"], "Ártist")
        self.assertEqual(song["peak_rank"], 10)
        self.assertEqual(song["top10"], 1)
        self.assertEqual(song["chart_weeks"], 2)
        self.assertEqual(song["raw_weekly_records"], 3)
        self.assertEqual(song["weekly_records_after_exact_dedup"], 2)
        self.assertEqual(stats["exact_duplicates_removed"], 1)
        self.assertEqual(review.height, 0)
        self.assertEqual(excluded["reason"].to_list(), ["exact_duplicate"])
        self.assertEqual(songs.filter(pl.col("Song") == "Eleven")["top10"][0], 0)
        self.assertEqual(songs.filter(pl.col("Song") == "Winner")["number_one"][0], 1)

    def test_filter_uses_full_history_first_date_and_inclusive_boundaries(self):
        raw = weekly([("1999-12-31", "Old", "A", 20), ("2000-01-07", "Old", "A", 1),
                      ("2000-01-01", "Start", "A", 50), ("2024-12-31", "End", "A", 40),
                      ("2025-01-07", "End", "A", 2), ("2025-01-01", "New", "A", 3)])
        songs, _, _, _ = prepare.prepare_billboard(raw)
        self.assertEqual(set(songs["Song"]), {"Start", "End"})
        end = songs.filter(pl.col("Song") == "End").row(0, named=True)
        self.assertEqual(end["last_chart_date"], date(2025, 1, 7))
        self.assertEqual(end["peak_rank"], 2)

    def test_conflict_quarantines_whole_song_not_just_week(self):
        raw = weekly([("1999-12-31", "Conflict", "A", 10), ("1999-12-31", "Conflict", "A", 20),
                      ("2000-01-07", "Conflict", "A", 5), ("2001-01-01", "Safe", "A", 2)])
        songs, review, excluded, stats = prepare.prepare_billboard(raw)
        self.assertEqual(songs["Song"].to_list(), ["Safe"])
        self.assertEqual(review.height, 2)
        self.assertEqual(excluded.height, 3)
        self.assertEqual(stats["unresolved_duplicate_groups"], 1)

    def test_normalized_equality_never_combines_raw_songs(self):
        raw = weekly([("2001-01-01", "Song!", "A", 10), ("2001-01-01", "Song", "A", 20)])
        songs, _, _, _ = prepare.prepare_billboard(raw)
        self.assertEqual(songs.height, 2)
        with tempfile.TemporaryDirectory() as directory:
            result = prepare.collision_reports(songs, "Song", "Artist", "test", Path(directory))
            self.assertEqual(result["title_artist"]["collision_groups"], 1)


class GrammyTests(unittest.TestCase):
    def test_exact_dedup_period_flags_and_no_inference(self):
        row = {"year": 2000, "award": "Song Of The Year", "song_or_album": "Été!",
               "artist": None, "producers": "Writer (Possible Performer)", "winner": True}
        raw = pl.DataFrame([row, row, dict(row, year=1999), dict(row, year=2025),
                            dict(row, year=2024, winner=False, artist="  ")]).with_row_index("source_row", offset=1)
        output, review, excluded, stats = prepare.prepare_grammy(raw)
        self.assertEqual(output.height, 2)
        self.assertEqual(stats["exact_duplicates_removed"], 1)
        self.assertEqual(stats["winner_records"], 1)
        self.assertEqual(output["grammy_nominated"].to_list(), [1, 1])
        self.assertEqual(output["artist_norm"].null_count(), 2)
        self.assertEqual(output["song_or_album"][0], "Été!")
        self.assertEqual(output["producers"][0], row["producers"])
        self.assertEqual(review.height + excluded.height, raw.height)


class SpotifyTests(unittest.TestCase):
    def test_equivalent_duplicates_only_and_conflicting_lyrics_retained(self):
        row = {"id": "same", "name": "Song!", "artists": "Ártist", "album_name": "Album",
               "energy": 0.5, "key": "C", "lyrics": "one two"}
        raw = pl.DataFrame([row, row, dict(row, lyrics="one new"), dict(row, id="blank", lyrics="  "),
                            dict(row, id="missing", lyrics=None)]).with_row_index("source_row", offset=1)
        output, review, excluded, stats = prepare.prepare_spotify(raw.lazy())
        self.assertEqual(output.height, 4)
        self.assertEqual(stats["exact_duplicates_removed"], 1)
        self.assertEqual(stats["unresolved_duplicate_id_groups"], 1)
        self.assertEqual(stats["unresolved_duplicate_id_rows"], 2)
        self.assertEqual(review.height, 3)
        self.assertNotIn("lyrics", output.columns)
        self.assertNotIn("lyrics", review.columns)
        self.assertEqual(output["name"].to_list(), ["Song!"] * 4)
        self.assertEqual(output.filter(pl.col("id") == "blank")["lyric_word_count"][0], 0)
        self.assertTrue(output.filter(pl.col("id") == "missing")["lyrics_missing"][0])
        self.assertEqual(output.filter(pl.col("id") == "same")["lyric_sha256"].n_unique(), 2)
        self.assertEqual(excluded["source_row"].to_list(), [2])

    def test_hash_equality_does_not_authorize_deletion(self):
        from unittest.mock import patch
        raw = pl.DataFrame({"id": ["a", "a"], "name": ["X", "X"], "artists": ["Y", "Y"],
                            "lyrics": ["same length", "diff lyrics"]}).with_row_index("source_row", offset=1)
        with patch.object(prepare, "lyric_hash", return_value="deliberate collision"):
            output, _, _, stats = prepare.prepare_spotify(raw.lazy())
        self.assertEqual(output.height, 2)
        self.assertEqual(stats["exact_duplicates_removed"], 0)


if __name__ == "__main__":
    unittest.main()
