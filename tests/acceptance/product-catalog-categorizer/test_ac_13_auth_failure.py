from pathlib import Path

import anthropic
import pytest
from fakes import (
    LISTING_HEADER,
    FakeClient,
    listing_rows,
    patch_client,
    status_error,
    write_csv,
)


def test_ac_13_auth_failure(
    tmp_path: Path,
    tree_file: Path,
    monkeypatch: pytest.MonkeyPatch,
    api_key: None,
    logs,
) -> None:
    """AC-13: AuthenticationError (401) on the first call -> exit 3, 'Anthropic API key rejected'."""
    from categorizer.cli import main

    def respond(call: dict) -> object:
        raise status_error(anthropic.AuthenticationError, 401, "invalid x-api-key")

    patch_client(monkeypatch, FakeClient(respond))
    src = write_csv(tmp_path / "listings.csv", LISTING_HEADER, listing_rows(3))

    assert main([str(src), "--tree", str(tree_file), "--out-dir", str(tmp_path)]) == 3
    assert "Anthropic API key rejected" in logs()
