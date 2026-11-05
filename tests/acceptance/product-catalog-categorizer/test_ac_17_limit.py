import json
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
    write_csv,
)


def test_ac_17_limit(
    tmp_path: Path, tree_file: Path, monkeypatch: pytest.MonkeyPatch, api_key: None
) -> None:
    """AC-17: --limit 3 on 10 rows -> only the first 3 rows classified and written."""
    from categorizer.cli import main

    client = FakeClient(lambda call: answer("balloon"))
    patch_client(monkeypatch, client)
    src = write_csv(tmp_path / "listings.csv", LISTING_HEADER, listing_rows(10))

    assert (
        main(
            [
                str(src),
                "--tree",
                str(tree_file),
                "--out-dir",
                str(tmp_path),
                "--limit",
                "3",
            ]
        )
        == 0
    )

    categorized, _, report = outputs(tmp_path, "listings")
    assert [r["listing_id"] for r in read_csv(categorized)[1]] == [
        "L001",
        "L002",
        "L003",
    ]
    assert len(client.messages.calls) == 3
    assert json.loads(report.read_text(encoding="utf-8"))["rows_total"] == 3
