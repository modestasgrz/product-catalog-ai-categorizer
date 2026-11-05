from pathlib import Path

from fakes import (
    LISTING_HEADER,
    NEW_COLUMNS,
    FakeClient,
    answer,
    outputs,
    read_csv,
    run_file,
    title_of,
    write_csv,
)


async def test_ac_02_threshold_review(tmp_path: Path, tree_file: Path) -> None:
    """AC-02: confidence 0.69 -> review, 0.70 -> ok; the review CSV holds only the review row."""
    src = write_csv(
        tmp_path / "listings.csv",
        LISTING_HEADER,
        [["L1", "Low", "d", "Vilnius", "1"], ["L2", "Edge", "d", "Kaunas", "2"]],
    )
    client = FakeClient(
        lambda call: answer("spa-day", 0.69 if title_of(call) == "Low" else 0.70)
    )

    await run_file(src, tree_file, tmp_path, client)

    categorized, review, _ = outputs(tmp_path, "listings")
    _, rows = read_csv(categorized)
    assert [r["status"] for r in rows] == ["review", "ok"]
    header, review_rows = read_csv(review)
    assert header == NEW_COLUMNS + LISTING_HEADER
    assert [r["listing_id"] for r in review_rows] == ["L1"]
