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


async def test_ac_05_invalid_then_valid(tmp_path: Path, tree_file: Path) -> None:
    """AC-05: first answer has an id outside the tree, second is valid -> exactly 2 calls, second answer used."""
    src = write_csv(
        tmp_path / "listings.csv",
        LISTING_HEADER,
        [["L1", "Wine evening", "Five wines", "Riga", "40"]],
    )
    replies = iter(
        [
            answer("not-a-category", 0.95),
            answer("wine-tasting", 0.88, "Wine tasting event."),
        ]
    )
    client = FakeClient(lambda call: next(replies))

    await run_file(src, tree_file, tmp_path, client)

    assert len(client.messages.calls) == 2
    row = read_csv(outputs(tmp_path, "listings")[0])[1][0]
    assert row["status"] == "ok"
    assert row["category_id"] == "wine-tasting"
    assert row["confidence"] == "0.88"
    assert row["reason"] == "Wine tasting event."
