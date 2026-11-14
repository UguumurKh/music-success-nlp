"""Conservative text keys, never an instruction to merge records."""
import re
import string
import unicodedata

import polars as pl
from unidecode import unidecode

_QUOTES = str.maketrans({c: "'" for c in "‘’‚‛`´"} | {c: '"' for c in '“”„‟«»'})


def normalize_text(value: str | None) -> str | None:
    """Null stays null; blank/punctuation-only input becomes an empty key.

    Version words, featured artists and artist-list ordering are preserved.
    Punctuation separates words (e.g. don't -> don t); it is not deleted.
    """
    if value is None:
        return None
    text = unidecode(value.lower().translate(_QUOTES)).lower()
    text = "".join(" " if c in string.punctuation or unicodedata.category(c).startswith("P")
                   else c for c in text)
    return re.sub(r"\s+", " ", text).strip()


def add_normalized_fields(frame, title: str, artist: str):
    """Append keys without altering any original columns (eager or lazy)."""
    return frame.with_columns(
        pl.col(title).map_elements(normalize_text, return_dtype=pl.String).alias("title_norm"),
        pl.col(artist).map_elements(normalize_text, return_dtype=pl.String).alias("artist_norm"),
    )
