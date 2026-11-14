"""Phase 8A: diagnostic similarity shortlist; never accept relationships."""
import hashlib
import json
from pathlib import Path
import re
from collections import Counter

import polars as pl
import rapidfuzz
from rapidfuzz.fuzz import ratio
from music_success_nlp.normalization import normalize_text

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ["reports/grammy_billboard_manual_review.csv",
           "reports/grammy_billboard_manual_review_guide.md",
           "reports/grammy_billboard_candidate_audit.md",
           "reports/grammy_billboard_candidate_audit.json"]
CODE = ["src/08a_prepare_grammy_billboard_review.py", "tests/test_grammy_billboard_review.py"]
FEATURE = re.compile(r"(?<!\S)(?:featuring|feat\.?|ft\.?)(?=\s|$)", re.I)
G_FIELDS = ["source_row", "year", "song_or_album", "performer_extracted", "title_norm", "title_match_norm", "performer_norm"]
B_FIELDS = ["source_row", "Song", "Artist", "first_chart_date", "title_norm", "artist_norm"]
RULES = """All similarity scores are RapidFuzz fuzz.ratio (normalized Indel similarity), 0–100,
with processor=None and no token sorting or partial matching. Blank inputs score zero.
Title scoring uses the existing Grammy title_match_norm (only the trailing source
(Single) label was removed) and Billboard title_norm; original title_norm is also
retained. Full artists use performer_norm and artist_norm. Primary artists use the
existing conservative normalization after splitting only explicit Featuring/feat/ft
markers. Ampersands, And, semicolons and group names are not split. Version words stay.

Combined score = 0.60 * title + 0.25 * full artist + 0.15 * primary artist.
A plausible candidate requires title >= 65, max(full artist, primary artist) >= 65,
and combined >= 70. Strong requires title >= 90, max(artist scores) >= 90 and
combined >= 90. Possible means plausible but not strong; all others are weak.
These heuristic thresholds are uncalibrated review guidance, not match probabilities
or acceptance criteria. Rounded scores (six decimals) are used consistently.

Initially consider Grammy year minus first-chart year in {0, 1}. Only if no plausible
candidate exists in that full initial pool, search {-1, 0, 1, 2}. The whole shortlist
then carries widened_minus1_to2, even if an individual candidate has gap 0 or 1.
Rank plausible candidates first, then combined, title, full-artist and primary-artist
scores descending, then Billboard source_row ascending. Keep at most five. Weak
suggestions may fill remaining slots and are retained even when none is plausible.
If the entire widened pool is empty, retain one no_candidate placeholder with null
Billboard fields, rank and scores; this is not counted as a candidate or strength.
Billboard IDs are the original Parquet row position plus one, as in Phase 3.

The prior variant manual-review file supplies provenance only (deduplicated tiers).
It never affects ranking. Already accepted Grammy source records are excluded using
distinct Grammy IDs, not relationship row counts. No success outcomes, lyrics or
Spotify content enter scoring, ranking or these reports. No new outcome labels,
acceptance decisions, NLP features or models are created.
"""


def primary(value):
    marker = FEATURE.search(value or "")
    return normalize_text(value[:marker.start()] if marker else value)


def similarity(a, b):
    return round(ratio(a, b, processor=None), 6) if a and b else 0.0


def scores(g, b):
    t = similarity(g["title_match_norm"], b["title_norm"])
    a = similarity(g["performer_norm"], b["artist_norm"])
    p = similarity(primary(g["performer_extracted"]), primary(b["Artist"]))
    combined = round(.60 * t + .25 * a + .15 * p, 6)
    plausible = t >= 65 and max(a, p) >= 65 and combined >= 70
    strong = t >= 90 and max(a, p) >= 90 and combined >= 90
    return dict(title_similarity=t, full_artist_similarity=a, primary_artist_similarity=p,
                combined_diagnostic_score=combined, plausible_candidate=plausible,
                diagnostic_strength="strong" if strong else "possible" if plausible else "weak")


def ranking(row):
    return (not row["plausible_candidate"], -row["combined_diagnostic_score"],
            -row["title_similarity"], -row["full_artist_similarity"],
            -row["primary_artist_similarity"], row["billboard_source_row"])


def prepare(grammy, billboard, accepted, previous):
    # Explicit allowlists keep outcomes and any text content out of all decisions.
    gs = grammy.select(G_FIELDS)
    bs = billboard.select(B_FIELDS)
    for frame in (gs, bs):
        if frame["source_row"].null_count() or frame["source_row"].n_unique() != frame.height:
            raise ValueError("Source IDs must be non-null and unique")
    accepted_ids = set(accepted["grammy_source_row"])
    if not accepted_ids <= set(gs["source_row"]):
        raise ValueError("Accepted Grammy ID absent from source")
    prior = {}
    for r in previous.select("grammy_source_row", "billboard_source_row", "candidate_tier").iter_rows(named=True):
        prior.setdefault((r["grammy_source_row"], r["billboard_source_row"]), set()).add(r["candidate_tier"])
    rows, coverage = [], []
    for g in gs.sort("source_row").iter_rows(named=True):
        if g["source_row"] in accepted_ids:
            continue
        base = dict(grammy_source_row=g["source_row"], grammy_year=g["year"],
                    grammy_title=g["song_or_album"], grammy_performer=g["performer_extracted"],
                    grammy_title_norm=g["title_norm"], grammy_title_match_norm=g["title_match_norm"],
                    grammy_performer_norm=g["performer_norm"],
                    grammy_primary_artist_norm=primary(g["performer_extracted"]))
        pool = []
        for b in bs.iter_rows(named=True):
            year = b["first_chart_date"].year if b["first_chart_date"] else None
            gap = g["year"] - year if g["year"] is not None and year is not None else None
            if gap not in (-1, 0, 1, 2):
                continue
            pool.append(dict(**base, billboard_source_row=b["source_row"], billboard_title=b["Song"],
                billboard_artist=b["Artist"], billboard_first_chart_year=year, year_gap=gap,
                billboard_title_norm=b["title_norm"], billboard_artist_norm=b["artist_norm"],
                billboard_primary_artist_norm=primary(b["Artist"]), **scores(g, b),
                prior_variant_review_tiers=" | ".join(map(str, sorted(prior.get((g["source_row"], b["source_row"]), set()))))))
        initial = [r for r in pool if r["year_gap"] in (0, 1)]
        widened = not any(r["plausible_candidate"] for r in initial)
        selected_pool = pool if widened else initial
        window = "widened_minus1_to2" if widened else "initial_0_to1"
        shortlisted = sorted(selected_pool, key=ranking)[:5]
        coverage.append(dict(**base, search_window=window, candidate_count=len(shortlisted),
                             has_plausible_candidate=any(r["plausible_candidate"] for r in selected_pool)))
        if not shortlisted:
            rows.append(dict(**base, search_window=window, candidate_status="no_candidate",
                             manual_decision="", reviewer_note=""))
        for rank, row in enumerate(shortlisted, 1):
            rows.append(dict(**row, candidate_rank=rank, search_window=window,
                             candidate_status="candidate", manual_decision="", reviewer_note=""))
    # Stable schema even when every record has no candidates, or all are accepted.
    string_fields = ["grammy_title", "grammy_performer", "grammy_title_norm", "grammy_title_match_norm",
        "grammy_performer_norm", "grammy_primary_artist_norm", "billboard_title", "billboard_artist",
        "billboard_title_norm", "billboard_artist_norm", "billboard_primary_artist_norm",
        "diagnostic_strength", "prior_variant_review_tiers", "search_window", "candidate_status", "manual_decision", "reviewer_note"]
    schema = {c: pl.Int64 for c in ["grammy_source_row", "grammy_year", "billboard_source_row", "billboard_first_chart_year", "year_gap", "candidate_rank"]}
    schema.update({c: pl.String for c in string_fields})
    schema.update({c: pl.Float64 for c in ["title_similarity", "full_artist_similarity", "primary_artist_similarity", "combined_diagnostic_score"]})
    schema["plausible_candidate"] = pl.Boolean
    return pl.DataFrame(rows, schema=schema).sort("grammy_source_row", "candidate_rank"), coverage


def snapshot(root=ROOT):
    """Project method: raw CSV size/mtime; SHA256 of protected artifacts/code."""
    paths = {p for folder in ("data/interim", "data/processed", "reports", "src", "tests", "notebooks")
             for p in (root / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    paths |= {p for p in root.iterdir() if p.is_file()}
    result = {p.relative_to(root).as_posix(): {"bytes": p.stat().st_size, "mtime_ns": p.stat().st_mtime_ns}
              for p in (root / "data/raw").glob("*.csv")}
    for path in sorted(paths):
        name = path.relative_to(root).as_posix()
        if name not in OUTPUTS:
            with path.open("rb") as stream:
                result[name] = {"sha256": hashlib.file_digest(stream, "sha256").hexdigest()}
    return result


def verify_protected(before, root=ROOT):
    after = snapshot(root)
    if before != after:
        changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
        raise AssertionError(f"Protected files changed: {changed}")
    return after


def save_review(review, path):
    review.write_csv(path)
    loaded = pl.read_csv(path, schema_overrides=review.schema, empty_string_is_null=False)
    expected = review.with_columns([pl.col(c).fill_null("") for c, dtype in review.schema.items() if dtype == pl.String])
    assert loaded.equals(expected)


def main():
    before = snapshot()
    g = pl.read_parquet(ROOT / "data/interim/grammy_soty_enriched_2000_2024.parquet")
    b = pl.read_parquet(ROOT / "data/interim/billboard_song_level_2000_2024.parquet").with_row_index("source_row", offset=1)
    a = pl.read_parquet(ROOT / "data/interim/billboard_grammy_accepted_pairs.parquet")
    previous = pl.read_csv(ROOT / "reports/billboard_grammy_variant_manual_review.csv")
    assert g.height == 150 and a.height == 125
    # Confirm that restored Billboard row identifiers agree with prior relationships.
    check = a.select("billboard_source_row", "billboard_Song", "billboard_Artist").join(
        b.select("source_row", "Song", "Artist"), left_on="billboard_source_row", right_on="source_row", how="left", validate="m:1")
    assert check.select(((pl.col("billboard_Song") == pl.col("Song")) & (pl.col("billboard_Artist") == pl.col("Artist"))).all()).item()
    review, coverage = prepare(g, b, a, previous)
    unmatched = set(g["source_row"]) - set(a["grammy_source_row"])
    assert set(review["grammy_source_row"]) == unmatched
    candidates = review.filter(pl.col("candidate_status") == "candidate")
    assert candidates.select("grammy_source_row", "billboard_source_row").is_duplicated().sum() == 0
    assert all(r["manual_decision"] == r["reviewer_note"] == "" for r in review.iter_rows(named=True))
    save_review(review, ROOT / OUTPUTS[0])
    guide = "# Grammy–Billboard manual review guide\n\n" + RULES + "\n## Reviewer workflow\n\n" + (
        "Inspect the raw titles, performer names, dates, all similarity components and prior-variant provenance. "
        "Check version qualifiers and collaborator differences explicitly. A first-chart year is not a release year, "
        "and the available Billboard table is restricted to its existing 2000–2024 cohort. "
        "Missing candidates do not prove a song never charted. The stored Grammy year is used as supplied.\n\n"
        "Leave manual_decision and reviewer_note blank until a human reviews the evidence. "
        "Suggested human entries are accept, reject, or uncertain; record reasoning and supporting sources in reviewer_note. "
        "Neither this script nor these columns apply a decision to any relationship table. "
        "Save a reviewed copy separately before rerunning this generator, which recreates blank review columns.\n")
    (ROOT / OUTPUTS[1]).write_text(guide, encoding="utf-8")
    report = dict(grammy_records=g.height, accepted_relationships=a.height,
        grammy_records_already_accepted=a["grammy_source_row"].n_unique(), still_unmatched=len(unmatched),
        unmatched_with_at_least_one_candidate=sum(r["candidate_count"] > 0 for r in coverage),
        unmatched_with_plausible_candidate=sum(r["has_plausible_candidate"] for r in coverage),
        unmatched_without_plausible_candidate=sum(not r["has_plausible_candidate"] for r in coverage),
        unmatched_with_no_candidate=sum(r["candidate_count"] == 0 for r in coverage),
        widened_search_records=sum(r["search_window"] == "widened_minus1_to2" for r in coverage),
        candidate_rows=candidates.height, review_rows=review.height,
        candidate_counts_by_strength={s: candidates["diagnostic_strength"].to_list().count(s) for s in ("strong", "possible", "weak")},
        year_gap_distribution=dict(sorted(Counter(map(str, candidates["year_gap"].to_list())).items())),
        prior_variant_input_rows=previous.height, prior_variant_distinct_pairs=previous.select("grammy_source_row", "billboard_source_row").unique().height,
        rapidfuzz_version=rapidfuzz.__version__, rules=RULES, unmatched_coverage=coverage,
        outputs=OUTPUTS + CODE, validation=dict(all_unmatched_represented=True, csv_roundtrip_passed=True,
        outcomes_excluded=True, no_automatic_decisions=True, no_outcome_labels_created=True,
        no_lyrics=True, no_nlp_or_modelling=True, protected_files_unchanged=True))
    after = verify_protected(before)
    report["integrity"] = dict(protected_file_count=len(before), before=before, after=after)
    (ROOT / OUTPUTS[3]).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    compact = {k: v for k, v in report.items() if k not in ("integrity", "rules", "unmatched_coverage")}
    md = "# Grammy–Billboard candidate audit\n\nManual-review support only; no relationships accepted or rejected.\n\n"
    md += "```json\n" + json.dumps(compact, indent=2) + "\n```\n\n## Method\n\n" + RULES
    md += "\n## Unmatched record coverage\n\n| Grammy ID | Year | Title | Candidates | Plausible | Window |\n|---|---|---|---:|---|---|\n"
    for r in coverage:
        title = (r["grammy_title"] or "").replace("|", "\\|").replace("\n", " ")
        md += f"| {r['grammy_source_row']} | {r['grammy_year']} | {title} | {r['candidate_count']} | {r['has_plausible_candidate']} | {r['search_window']} |\n"
    md += f"\nIntegrity: {len(before)} protected files unchanged. Raw CSVs checked by size/mtime without opening; other protected files checked by SHA256.\n"
    (ROOT / OUTPUTS[2]).write_text(md, encoding="utf-8")
    verify_protected(before)
    print(json.dumps(compact, indent=2))


if __name__ == "__main__":
    main()
