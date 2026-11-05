from pathlib import Path

from fakes import (
    LISTING_HEADER,
    FakeClient,
    answer,
    outputs,
    read_csv,
    run_file,
    title_of,
    write_csv,
)


async def test_ac_04_empty_row_no_call(tmp_path: Path, tree_file: Path) -> None:
    """AC-04: empty/whitespace title and description -> no model call, unknown, 0.00, 'empty title and description'."""
    rows = [
        ["L1", "Spa", "Massage", "Vilnius", "1"],
        ["L2", "", "", "Kaunas", "2"],
        ["L3", "   ", " \t ", "Riga", "3"],
    ]
    src = write_csv(tmp_path / "listings.csv", LISTING_HEADER, rows)
    client = FakeClient(lambda call: answer("spa-day"))

    await run_file(src, tree_file, tmp_path, client)

    assert [title_of(c) for c in client.messages.calls] == ["Spa"]
    _, out_rows = read_csv(outputs(tmp_path, "listings")[0])
    for row in out_rows[1:]:
        assert row["status"] == "unknown"
        assert row["category_id"] == "unknown"
        assert row["confidence"] == "0.00"
        assert row["reason"] == "empty title and description"
