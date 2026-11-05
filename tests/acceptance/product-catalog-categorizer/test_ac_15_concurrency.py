from pathlib import Path

import pytest
from fakes import (
    LISTING_HEADER,
    FakeClient,
    answer,
    listing_rows,
    outputs,
    patch_client,
    read_csv,
    run_file,
    write_csv,
)


async def test_ac_15_concurrency(tmp_path: Path, tree_file: Path) -> None:
    """AC-15: concurrency=4 -> at most 4 calls in flight; output keeps input order."""
    src = write_csv(tmp_path / "listings.csv", LISTING_HEADER, listing_rows(40))
    client = FakeClient(lambda call: answer("balloon"))

    await run_file(src, tree_file, tmp_path, client, concurrency=4)

    assert len(client.messages.calls) == 40
    assert 1 < client.messages.max_in_flight <= 4
    _, rows = read_csv(outputs(tmp_path, "listings")[0])
    assert [r["listing_id"] for r in rows] == [f"L{i:03d}" for i in range(1, 41)]


@pytest.mark.parametrize("value", ["0", "33"])
def test_ac_15_concurrency_bounds(
    tmp_path: Path,
    tree_file: Path,
    monkeypatch: pytest.MonkeyPatch,
    api_key: None,
    value: str,
) -> None:
    """AC-15: --concurrency outside 1-32 -> exit 2 without any model call."""
    from categorizer.cli import main

    client = FakeClient(lambda call: answer("balloon"))
    patch_client(monkeypatch, client)
    src = write_csv(tmp_path / "listings.csv", LISTING_HEADER, listing_rows(2))

    assert (
        main(
            [
                str(src),
                "--tree",
                str(tree_file),
                "--out-dir",
                str(tmp_path),
                "--concurrency",
                value,
            ]
        )
        == 2
    )
    assert client.messages.calls == []
