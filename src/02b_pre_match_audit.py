"""Read-only Phase 2B audit. Writes only four explicitly named audit reports."""
from datetime import date
import hashlib
from itertools import combinations
import json
from pathlib import Path
import re
import sys

import polars as pl

from music_success_nlp.normalization import normalize_text

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ["billboard_sing_collision_detail.csv", "grammy_performer_parse_audit.csv",
           "pre_match_audit.md", "pre_match_audit.json"]
MARKER = re.compile(r">\s*songwriters?\b", re.IGNORECASE)


def parse_performer(value):
    """Extract the final balanced parenthetical group after one writer marker.

    Parentheses before the marker belong to writer information. Nested performer
    parentheses are preserved. Trailing non-whitespace or unbalanced parentheses
    fail explicitly rather than guessing. Success means syntactic extraction,
    not verification of performer identity or text encoding.
    """
    if value is None:
        return None, False, "missing_producers"
    if not value.strip():
        return None, False, "blank_producers"
    markers = list(MARKER.finditer(value))
    if not markers:
        return None, False, "missing_songwriter_marker"
    if len(markers) != 1:
        return None, False, "ambiguous_multiple_markers"
    suffix = value[markers[0].end():].strip()
    if not suffix.endswith(")"):
        return None, False, "missing_final_parentheses_or_trailing_text"
    depth, start, groups = 0, None, []
    for i, char in enumerate(suffix):
        if char == "(":
            if depth == 0:
                start = i
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return None, False, "unbalanced_parentheses"
            if depth == 0:
                groups.append((start, i))
    if depth or not groups:
        return None, False, "unbalanced_parentheses"
    start, end = groups[-1]
    performer = suffix[start + 1:end].strip()
    if not performer:
        return "", False, "blank_performer"
    return performer, True, "extracted_final_parentheses_after_songwriter_marker"


def title_match_norm(title):
    """Remove only the exact case-sensitive trailing source label '(Single)'."""
    if title is None:
        return None
    text = title.rstrip()
    if text.endswith("(Single)"):
        text = text[:-len("(Single)")].rstrip()
    return normalize_text(text)


def audit_grammy(frame):
    parsed = [parse_performer(value) for value in frame["producers"]]
    audited = frame.with_columns(
        pl.Series("performer_extracted", [p[0] for p in parsed], dtype=pl.String),
        pl.Series("performer_parse_success", [p[1] for p in parsed], dtype=pl.Boolean),
        pl.Series("performer_parse_reason", [p[2] for p in parsed], dtype=pl.String),
        pl.Series("title_match_norm", [title_match_norm(t) for t in frame["song_or_album"]], dtype=pl.String),
    ).with_columns(pl.col("performer_extracted").map_elements(normalize_text, return_dtype=pl.String).alias("performer_norm"))
    return audited.with_columns(
        (~pl.col("title_match_norm").eq_missing(pl.col("title_norm"))).alias("title_match_changed"),
        pl.col("performer_extracted").str.contains("\ufffd", literal=True).fill_null(False).alias("performer_contains_replacement_character"),
    )


def duplicate_keys(frame, title, performer):
    valid = frame.filter(pl.col("performer_parse_success") & pl.col(performer).is_not_null()
                         & (pl.col(performer) != "") & pl.col(title).is_not_null() & (pl.col(title) != ""))
    groups = valid.group_by(["year", title, performer]).agg(
        pl.len().alias("records"), pl.col("source_row").sort().alias("source_rows"))
    return groups.filter(pl.col("records") > 1).sort(["year", title, performer]).to_dicts()


def compare_periods(records):
    comparisons = []
    for left, right in combinations(records, 2):
        a, b = sorted([left, right], key=lambda x: x["first_chart_date"])
        days = (b["first_chart_date"] - a["last_chart_date"]).days
        relation = "overlapping date ranges" if days <= 0 else "consecutive weekly dates" if days == 7 else "gap" if days > 7 else "non-overlapping, less than one week apart"
        comparisons.append({"earlier_song": a["Song"], "later_song": b["Song"],
            "days_between_earlier_last_and_later_first": days,
            "relationship": relation, "distinct_histories_indicated": days > 7,
            "note": "Date ranges describe chart histories, not proof of different musical works. No merge performed."})
    return comparisons


def fingerprints():
    paths = set((ROOT / "data/raw").glob("*.csv")) | set(ROOT.rglob("*.parquet"))
    paths |= {p for p in (ROOT / "reports").glob("*") if p.is_file() and p.name not in OUTPUTS}
    paths |= {p for folder in ("src", "tests") for p in (ROOT / folder).rglob("*.py")
              if p.name not in {"02b_pre_match_audit.py", "test_pre_match_audit.py"}}
    paths.add(ROOT / "README.md")
    result = {}
    for path in sorted(paths):
        with path.open("rb") as stream:
            result[path.relative_to(ROOT).as_posix()] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


def render(report):
    lines = ["# Pre-matching audit", "", "Read-only audit; no records merged and no dataset matching performed.", "",
             "## Billboard: Glee Cast collision", "",
             "| Song | Artist | First date | Last date | Weeks | Peak | Top 10 | No. 1 | Raw records | After dedup |",
             "|---|---|---|---|---:|---:|---:|---:|---:|---:|"]
    fields = ["Song", "Artist", "first_chart_date", "last_chart_date", "chart_weeks", "peak_rank", "top10", "number_one", "raw_weekly_records", "weekly_records_after_exact_dedup"]
    for row in report["billboard"]["records"]:
        lines.append("| " + " | ".join(str(row[k]) for k in fields) + " |")
    for pair in report["billboard"]["period_comparisons"]:
        lines += ["", f"{pair['earlier_song']} → {pair['later_song']}: **{pair['relationship']}**, "
                  f"{pair['days_between_earlier_last_and_later_first']} days between the earlier last date and later first date. "
                  "These appear to be distinct chart histories; title similarity alone does not establish the same recording. No merge is recommended from this audit alone."]
    g = report["grammy"]
    lines += ["", "## Grammy performer parsing", "",
        f"Audited {g['records']} records: **{g['successful_extractions']} successful**, **{g['failed_extractions']} failed**, "
        f"**{g['blank_extracted_performers']} blank** extracted performers. Success verifies the pattern only, not performer identity.", "",
        f"Raw year–title–performer duplicate groups: {len(g['raw_duplicate_keys'])}. "
        f"Normalized duplicate groups before title-label removal: {len(g['normalized_duplicate_keys_before'])}; "
        f"after: {len(g['normalized_duplicate_keys_after'])}. "
        f"New duplicate groups introduced: {len(g['new_duplicate_keys_after_label_removal'])}.", "",
        "## Candidate title variant", "",
        f"**{g['titles_changed']} titles changed** by removing the exact trailing `(Single)` label. "
        "Original titles and title_norm remain intact; meaningful parentheses and version words are preserved. "
        "The CSV contains every original title, title_match_norm and title_match_changed.", ""]
    for label, rows in g["examples"].items():
        lines += [f"### {label}", "", "```json", json.dumps(rows, ensure_ascii=False, indent=2), "```", ""]
    lines += ["## Unresolved records and limits", "", *[f"- {risk}" for risk in report["risks"]], "",
        "```json", json.dumps(g["unresolved_records"], ensure_ascii=False, indent=2), "```", "",
        "Solo examples are heuristic: no Featuring, ampersand, word And or semicolon. A band name may appear in this group. "
        "Collaborator strings are preserved, not split or matched.", "", "## Integrity", "",
        f"SHA-256 verified {len(report['integrity']['before'])} existing files before and after: "
        f"unchanged = {report['integrity']['all_unchanged']}. JSON contains per-file hashes. "
        "Raw CSVs, existing Parquet tables, prior reports, existing scripts/tests and README were not modified.", "",
        "## Rerun", "", "```powershell", "uv run python -m unittest discover -s tests -v",
        "uv run python src/02b_pre_match_audit.py", "```", ""]
    return "\n".join(lines)


def main():
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Python 3.12 is required")
    before = fingerprints()
    billboard = pl.read_parquet(ROOT / "data/interim/billboard_song_level_2000_2024.parquet").filter(
        (pl.col("title_norm") == "sing") & (pl.col("artist_norm") == "glee cast")).sort("first_chart_date", "Song")
    original = pl.read_parquet(ROOT / "data/interim/grammy_soty_2000_2024.parquet")
    if original.height != 150:
        raise ValueError(f"Expected 150 Grammy records; found {original.height}")
    audited = audit_grammy(original)
    assert audited.select(original.columns).equals(original), "Original columns changed in audit"
    g = {"records": audited.height, "successful_extractions": int(audited["performer_parse_success"].sum()),
         "failed_extractions": int((~audited["performer_parse_success"]).sum()),
         "blank_extracted_performers": audited.filter(pl.col("performer_extracted").str.strip_chars() == "").height,
         "titles_changed": int(audited["title_match_changed"].sum()),
         "raw_duplicate_keys": duplicate_keys(audited, "song_or_album", "performer_extracted"),
         "normalized_duplicate_keys_before": duplicate_keys(audited, "title_norm", "performer_norm"),
         "normalized_duplicate_keys_after": duplicate_keys(audited, "title_match_norm", "performer_norm")}
    old_groups = [set(row["source_rows"]) for row in g["normalized_duplicate_keys_before"]]
    g["new_duplicate_keys_after_label_removal"] = [row for row in g["normalized_duplicate_keys_after"]
        if not any(set(row["source_rows"]).issubset(old) for old in old_groups)]
    columns = ["source_row", "year", "song_or_album", "title_norm", "producers", "performer_extracted",
               "performer_norm", "performer_parse_success", "performer_parse_reason", "winner",
               "grammy_nominated", "grammy_winner", "title_match_norm", "title_match_changed",
               "performer_contains_replacement_character"]
    view = audited.select(columns)
    g["changed_titles"] = view.filter(pl.col("title_match_changed")).select(
        "source_row", "song_or_album", "title_norm", "title_match_norm").to_dicts()
    text = pl.col("performer_extracted")
    featuring = text.str.contains(r"(?i)\bfeaturing\b")
    collaborators = text.str.contains(r"(?i)&|\band\b|;")
    solo = ~featuring & ~collaborators
    example_cols = ["source_row", "year", "song_or_album", "performer_extracted", "performer_norm"]
    g["examples"] = {label: view.filter(pl.col("performer_parse_success") & expression).head(5).select(example_cols).to_dicts()
        for label, expression in [("Solo-style performers", solo), ("Featuring", featuring),
                                  ("Ampersand collaborators", text.str.contains("&", literal=True)),
                                  ("And collaborators", text.str.contains(r"(?i)\band\b")),
                                  ("Semicolon collaborators", text.str.contains(";", literal=True))]}
    g["unresolved_records"] = view.filter(~pl.col("performer_parse_success")
        | pl.col("performer_contains_replacement_character")
        | pl.col("performer_norm").is_null() | (pl.col("performer_norm") == "")).to_dicts()
    g["replacement_character_records"] = int(view["performer_contains_replacement_character"].sum())
    report = {"billboard": {"records": billboard.to_dicts(), "period_comparisons": compare_periods(billboard.to_dicts())},
        "grammy": g, "risks": [
            "Glee Cast collision remains unresolved as musical identity; the two raw title histories must remain separate.",
            f"{g['replacement_character_records']} extracted performers contain an existing Unicode replacement character (U+FFFD). Extraction succeeds structurally, but damaged names and their normalized keys need review; no encoding repair was attempted.",
            "Parser failures and empty normalized performers, if any, are listed below. Collaborator order and Featuring labels remain unchanged.",
            "title_match_norm is for future candidate generation only. No dataset matching or automatic record merging was performed."],
        "integrity": {"before": before}}
    reports = ROOT / "reports"
    billboard.write_csv(reports / OUTPUTS[0])
    view.write_csv(reports / OUTPUTS[1])
    after = fingerprints()
    report["integrity"].update(after=after, all_unchanged=before == after)
    if before != after:
        raise RuntimeError("An existing protected file changed during the audit")
    (reports / OUTPUTS[3]).write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    (reports / OUTPUTS[2]).write_text(render(report), encoding="utf-8")
    print(f"Billboard: {billboard.height} records. Grammy: {g['successful_extractions']} success, {g['failed_extractions']} failed; {g['titles_changed']} title variants changed.")
    print(f"Verified {len(before)} existing files unchanged. No matching performed.")


if __name__ == "__main__":
    main()
