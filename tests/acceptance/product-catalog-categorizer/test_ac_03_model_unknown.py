from pathlib import Path

from fakes import (
    LISTING_HEADER,
    FakeClient,
    answer,
    outputs,
    read_csv,
    run_file,
    write_csv,
)


async def test_ac_03_model_unknown(tmp_path: Path, tree_file: Path) -> None:
    """AC-03: model answers unknown -> status unknown, empty name/url, reason kept, row in review CSV."""
    src = write_csv(
        tmp_path / "listings.csv",
        LISTING_HEADER,
        [["L1", "Tyre change voucher", "Winter tyres", "Kaunas", "30"]],
    )
    client = FakeClient(lambda call: answer("unknown", 0.40, "No category fits"))

    await run_file(src, tree_file, tmp_path, client)

    categorized, review, _ = outputs(tmp_path, "listings")
    _, rows = read_csv(categorized)
    row = rows[0]
    assert row["status"] == "unknown"
    assert row["category_id"] == "unknown"
    assert row["category_name"] == ""
    assert row["category_url"] == ""
    assert row["reason"] == "No category fits"
    assert [r["listing_id"] for r in read_csv(review)[1]] == ["L1"]
