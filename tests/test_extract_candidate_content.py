import importlib.util
from pathlib import Path
import tempfile
import unittest

import polars as pl

spec = importlib.util.spec_from_file_location("extract_content", Path(__file__).resolve().parents[1] / "src/06_extract_candidate_content.py")
extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extractor)


def raw_frame():
    frame = pl.DataFrame({"id": ["outside", "a", "b", "c"], "name": ["Other", "Title A", "Title B", "Title C"],
        "album_name": ["Album"] * 4, "artists": ["Artist"] * 4,
        "lyrics": ["not requested", 'Été, "quoted"\nSecond line\r\nThird line!', " \t\n", None]})
    return frame.with_columns([pl.lit("C" if c == "key" else "Major").alias(c) if c in ("key", "mode")
                              else pl.lit(.5).alias(c) for c in extractor.AUDIO]).select(extractor.RAW_COLUMNS)


def relationships(ids):
    return pl.DataFrame({"source_row": list(range(1, len(ids) + 1)), "spotify_id": ids},
                        schema={"source_row": pl.Int64, "spotify_id": pl.String})


def fixture(root, requested=None, raw=None):
    for folder in ["data/raw", "data/interim", "reports", "src", "tests"]:
        (root / folder).mkdir(parents=True, exist_ok=True)
    frame = raw if raw is not None else raw_frame()
    frame.write_csv(root / "data/raw/songs_with_attributes_and_lyrics.csv")
    metadata = extractor.validation_metadata(frame.with_row_index("source_row", offset=1))
    metadata.write_parquet(root / "data/interim/spotify_track_index.parquet")
    b = relationships(requested if requested is not None else ["a", "b", "c"])
    g = relationships(["a"])
    b.write_parquet(root / "data/interim/billboard_spotify_accepted_candidates.parquet")
    g.write_parquet(root / "data/interim/grammy_spotify_accepted_candidates.parquet")
    return frame, metadata, b, g


class LedgerTests(unittest.TestCase):
    def test_union_dedup_flags_and_source_counts(self):
        b = relationships(["a", "a", "b"])
        g = relationships(["a", "c"])
        ledger = extractor.requested_ledger(b, g)
        self.assertEqual(ledger["id"].to_list(), ["a", "b", "c"])
        self.assertEqual(ledger["requested_by_both"].to_list(), [True, False, False])
        self.assertEqual(ledger["requested_by_billboard"].to_list(), [True, True, False])
        self.assertEqual(ledger["requested_by_grammy"].to_list(), [True, False, True])
        self.assertEqual(ledger["accepted_billboard_source_records"].to_list(), [2, 1, 0])


class ExtractionTests(unittest.TestCase):
    def test_multiline_commas_quotes_unicode_preservation_and_row_tracking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frame, index, b, g = fixture(root)
            ledger = extractor.requested_ledger(b, g)
            path = root / extractor.OUTPUTS[0]
            extractor.extract(root / "data/raw/songs_with_attributes_and_lyrics.csv", ledger, index.schema, path)
            content = pl.read_parquet(path)
            expected = frame.with_row_index("source_row", offset=1).filter(pl.col("id") != "outside")
            self.assertEqual(content.schema, expected.schema)
            self.assertTrue(content.equals(expected))
            self.assertEqual(content["source_row"].to_list(), [2, 3, 4])
            self.assertEqual(content["lyrics"][0], 'Été, "quoted"\nSecond line\r\nThird line!')
            self.assertNotIn("outside", content["id"].to_list())

    def test_strict_utf8_rejects_invalid_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, index, b, g = fixture(root)
            path = root / "data/raw/songs_with_attributes_and_lyrics.csv"
            data = path.read_bytes().replace(b"Second line", b"Second\xffline")
            path.write_bytes(data)
            with self.assertRaises(pl.exceptions.ComputeError):
                extractor.extract(path, extractor.requested_ledger(b, g), index.schema, root / extractor.OUTPUTS[0])

    def test_blank_missing_lyrics_and_identical_preparation_definitions(self):
        frame = raw_frame().with_row_index("source_row", offset=1)
        meta = extractor.validation_metadata(frame)
        self.assertEqual(meta["lyrics_missing"].to_list(), [False, False, False, True])
        self.assertEqual(meta["lyrics_blank"].to_list(), [False, False, True, False])
        self.assertEqual(meta["lyric_word_count"].to_list(), [2, 6, 0, None])
        self.assertEqual(meta["lyric_sha256"][1], extractor.PREP.lyric_hash(frame["lyrics"][1]))
        self.assertIsNone(meta["lyric_sha256"][3])

    def test_all_fields_agree_empty_failures(self):
        metadata = extractor.validation_metadata(raw_frame().with_row_index("source_row", offset=1))
        ledger = extractor.requested_ledger(relationships(["a", "b", "c"]), relationships([]))
        final, failures = extractor.validate(ledger, metadata.filter(pl.col("id") != "outside"), metadata)
        self.assertEqual(failures.height, 0)
        self.assertEqual(set(final["validation_status"]), {"validated"})

    def test_hash_word_count_audio_title_and_source_row_disagreements(self):
        meta = extractor.validation_metadata(raw_frame().with_row_index("source_row", offset=1)).filter(pl.col("id") == "a")
        ledger = extractor.requested_ledger(relationships(["a"]), relationships([]))
        bad_index = meta.with_columns(pl.lit("wrong").alias("lyric_sha256"), pl.lit(99).alias("lyric_word_count"),
                                      pl.lit(.9).alias("energy"), pl.lit("changed").alias("name"))
        _, failures = extractor.validate(ledger, meta, bad_index)
        self.assertEqual(set(failures["field"]), {"lyric_sha256", "lyric_word_count", "energy", "name"})
        _, failures = extractor.validate(ledger, meta, meta.with_columns(pl.lit(99).alias("source_row")))
        self.assertIn("index_source_row_not_unique_or_absent", failures["reason"].to_list())

    def test_missing_and_duplicate_ids_fail_and_preserve_diagnostics(self):
        for duplicate in [False, True]:
            with self.subTest(duplicate=duplicate), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                frame = raw_frame()
                if duplicate:
                    frame = pl.concat([frame, frame.filter(pl.col("id") == "a")])
                fixture(root, requested=["a"] if duplicate else ["a", "missing"], raw=frame)
                report, code = extractor.run(root)
                self.assertEqual(code, 1)
                self.assertEqual(report["status"], "failed")
                self.assertEqual(report["summary"]["duplicate_raw_ids" if duplicate else "missing_ids"], 1)
                failures = pl.read_csv(root / extractor.OUTPUTS[4])
                self.assertIn("duplicate_raw_id" if duplicate else "missing_requested_id", failures["reason"].to_list())
                self.assertTrue(all((root / p).exists() for p in extractor.OUTPUTS))

    def test_unexpected_extracted_id_validation(self):
        metadata = extractor.validation_metadata(raw_frame().with_row_index("source_row", offset=1))
        ledger = extractor.requested_ledger(relationships(["a"]), relationships([]))
        _, failures = extractor.validate(ledger, metadata, metadata)
        self.assertEqual(failures.filter(pl.col("reason") == "unexpected_extracted_id").height, 3)

    def test_successful_run_privacy_roundtrip_and_existing_files_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frame, _, _, _ = fixture(root)
            before = extractor.protected_snapshot(root)
            report, code = extractor.run(root)
            self.assertEqual(code, 0)
            self.assertEqual(before, extractor.protected_snapshot(root))
            self.assertTrue(report["validation"]["parquet_roundtrip_passed"])
            self.assertEqual(report["summary"]["extracted_distinct_ids"], 3)
            for file in extractor.OUTPUTS[1:]:
                text = (root / file).read_text(encoding="utf-8")
                self.assertNotIn('Second line', text)
                if file.endswith(".csv"):
                    self.assertNotIn("lyrics", pl.read_csv(root / file).columns)
            content = pl.read_parquet(root / extractor.OUTPUTS[0])
            self.assertTrue(content.drop("source_row").equals(frame.filter(pl.col("id") != "outside")))


if __name__ == "__main__":
    unittest.main()
