from pathlib import Path

import pytest
from fakes import (
    LISTING_HEADER,
    FakeClient,
    answer,
    listing_rows,
    outputs,
    patch_client,
    write_csv,
)


@pytest.mark.parametrize("key", [None, ""])
def test_ac_12_missing_api_key(
    tmp_path: Path,
    tree_file: Path,
    monkeypatch: pytest.MonkeyPatch,
    logs,
    key: str | None,
) -> None:
    """AC-12: ANTHROPIC_API_KEY unset or empty -> exit 2, 'ANTHROPIC_API_KEY is not set', no files."""
    from categorizer.cli import main

    if key is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", key)
    client = FakeClient(lambda call: answer("spa-day"))
    patch_client(monkeypatch, client)
    src = write_csv(tmp_path / "listings.csv", LISTING_HEADER, listing_rows(2))

    assert (
        main([str(src), "--tree", str(tree_file), "--out-dir", str(tmp_path / "out")])
        == 2
    )
    assert "ANTHROPIC_API_KEY is not set" in logs()
    assert not any(p.exists() for p in outputs(tmp_path / "out", "listings"))
    assert client.messages.calls == []
