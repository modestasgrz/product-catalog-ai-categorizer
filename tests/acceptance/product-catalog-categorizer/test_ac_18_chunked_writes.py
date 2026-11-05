from pathlib import Path

import anthropic
import pytest
from fakes import (
    LISTING_HEADER,
    FakeClient,
    answer,
    listing_rows,
    outputs,
    patch_client,
    read_csv,
    status_error,
    title_of,
    write_csv,
)


def test_ac_18_chunked_writes(
    tmp_path: Path, tree_file: Path, monkeypatch: pytest.MonkeyPatch, api_key: None
) -> None:
    """AC-18: 120 rows, AuthenticationError on row 75 -> exit 3 and the categorized CSV already holds exactly rows 1-50."""
    from categorizer.cli import main

    def respond(call: dict) -> object:
        if title_of(call) == "Listing 75":
            raise status_error(anthropic.AuthenticationError, 401, "invalid x-api-key")
        return answer("balloon")

    patch_client(monkeypatch, FakeClient(respond))
    src = write_csv(tmp_path / "listings.csv", LISTING_HEADER, listing_rows(120))

    assert main([str(src), "--tree", str(tree_file), "--out-dir", str(tmp_path)]) == 3
    _, rows = read_csv(outputs(tmp_path, "listings")[0])
    assert [r["listing_id"] for r in rows] == [f"L{i:03d}" for i in range(1, 51)]
