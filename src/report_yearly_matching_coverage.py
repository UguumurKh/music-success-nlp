"""Report coverage from existing artifacts only; never rerun pipeline stages."""

from pathlib import Path

import polars as pl


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = "data/interim/billboard_song_level_2000_2024.parquet"
MATCHED = "data/interim/billboard_song_level_consolidated.parquet"
INTEGRATED = "data/processed/billboard_model_base.parquet"
KEYS = ["Song", "Artist"]
FIELDS = KEYS + ["first_chart_date"]


def main():
    paths = [ROOT / p for p in (ORIGINAL, MATCHED, INTEGRATED)]
    before = [(p.stat().st_size, p.stat().st_mtime_ns) for p in paths]
    original, matched, integrated = [
        pl.read_parquet(p, columns=FIELDS) for p in paths
    ]
    for frame in (original, matched, integrated):
        assert frame.select(pl.struct(KEYS).n_unique()).item() == frame.height
        assert frame.null_count().row(0) == (0, 0, 0)
        assert frame.schema["first_chart_date"] == pl.Date
    assert matched.join(original, on=FIELDS, how="anti").height == 0
    assert matched.sort(KEYS).equals(integrated.sort(KEYS))
    original = original.with_columns(pl.col("first_chart_date").dt.year().alias("year"))
    matched = matched.with_columns(pl.col("first_chart_date").dt.year().alias("year"))
    assert original["year"].is_between(2000, 2024).all()
    result = (
        pl.DataFrame({"year": list(range(2000, 2025))})
        .join(original.group_by("year").agg(
            pl.len().alias("original_billboard_records")), on="year", how="left")
        .join(matched.group_by("year").agg(
            pl.len().alias("matched_integrated_records")), on="year", how="left")
        .with_columns(pl.col("matched_integrated_records").fill_null(0))
        .with_columns(
            (100 * pl.col("matched_integrated_records")
             / pl.col("original_billboard_records"))
            .round(2).alias("matching_coverage_percentage")
        )
        .sort("year")
    )
    assert result["original_billboard_records"].min() > 0
    assert result["original_billboard_records"].sum() == original.height
    assert result["matched_integrated_records"].sum() == matched.height
    assert result.select(
        (pl.col("matched_integrated_records") <= pl.col("original_billboard_records")).all()
    ).item()
    table = [
        "| Year | Original Billboard song–artist records | Matched integrated records | Matching coverage |",
        "|---|---:|---:|---:|",
    ]
    for year, denominator, numerator, coverage in result.iter_rows():
        table.append(f"| {year} | {denominator:,} | {numerator:,} | {coverage:.2f}% |")
    recent = {r["year"]: r for r in result.filter(pl.col("year") >= 2022).to_dicts()}
    slide = (
        f"Matching coverage falls from {recent[2022]['matching_coverage_percentage']:.2f}% "
        f"in 2022 to {recent[2023]['matching_coverage_percentage']:.2f}% in 2023 and "
        f"{recent[2024]['matching_coverage_percentage']:.2f}% in 2024. "
        "The much lower representation of the original Billboard cohorts supports "
        "excluding 2023–2024 from the analysis. Coverage alone does not establish "
        "the cause of missing matches or prove that earlier cohorts are unbiased."
    )
    summary = "\n".join([
        "# Yearly Billboard–Spotify matching coverage", "",
        slide, "",
        "**Definition:** matched integrated song–artist records / original Billboard "
        "song–artist records × 100. Each record is assigned to the calendar year of "
        "`first_chart_date` in both datasets; this is not Spotify release year or "
        "the year of each weekly chart appearance. Percentages are rounded to two decimals.", "",
        f"**Denominator:** `{ORIGINAL}` ({original.height:,} records), the project's "
        "original prepared, pre-matching Billboard cohort. This contains distinct original "
        "`Song`/`Artist` pairs first charting in 2000–2024 after the existing source preparation "
        "quarantines; it is not a count of raw weekly rows. Source preparation computes "
        "first chart date across the full available chart history before the period filter.", "",
        f"**Numerator:** `{MATCHED}` ({matched.height:,} records). Verified to have exactly "
        f"the same song–artist/date records as `{INTEGRATED}`. Includes all consolidated "
        "matches, without strict-consistency, language, lyric-quality, or 2000–2022 filters.", "",
        *table, "",
        f"**Overall:** {matched.height:,} / {original.height:,} = "
        f"{100 * matched.height / original.height:.2f}% (ratio of totals).", "",
        "**Validation:** no duplicate song–artist keys or missing keys/dates in the three "
        "inputs; every matched record belongs to the original cohort with the identical "
        "first chart date; yearly counts reconcile to source totals. Inputs were read only; "
        "no earlier stages were rerun.", "",
        "**Reproduce:** `.venv/Scripts/python.exe src/report_yearly_matching_coverage.py`.", "",
    ])
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    csv_path = reports / "yearly_matching_coverage.csv"
    result.write_csv(csv_path, float_precision=2)
    (reports / "yearly_matching_coverage.md").write_text(summary, encoding="utf-8")
    assert pl.read_csv(csv_path).equals(result, null_equal=True)
    assert before == [(p.stat().st_size, p.stat().st_mtime_ns) for p in paths]
    print("\n".join(table))
    print("\n" + slide)


if __name__ == "__main__":
    main()
