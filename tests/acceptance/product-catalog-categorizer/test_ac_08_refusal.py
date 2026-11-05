from pathlib import Path

from fakes import (
    LISTING_HEADER,
    FakeClient,
    FakeResponse,
    outputs,
    read_csv,
    run_file,
    write_csv,
)


async def test_ac_08_refusal(tmp_path: Path, tree_file: Path) -> None:
    """AC-08: stop_reason refusal -> error, unknown, 'model refused'."""
    src = write_csv(
        tmp_path / "listings.csv", LISTING_HEADER, [["L1", "Spa", "d", "Vilnius", "1"]]
    )
    client = FakeClient(
        lambda call: FakeResponse(parsed_output=None, stop_reason="refusal")
    )

    await run_file(src, tree_file, tmp_path, client)

    row = read_csv(outputs(tmp_path, "listings")[0])[1][0]
    assert row["status"] == "error"
    assert row["category_id"] == "unknown"
    assert row["reason"] == "model refused"
