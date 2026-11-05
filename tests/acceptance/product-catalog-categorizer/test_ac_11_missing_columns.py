from pathlib import Path

import pytest
from fakes import FakeClient, answer, outputs, patch_client, write_csv


def test_ac_11_missing_columns(
    tmp_path: Path,
    tree_file: Path,
    monkeypatch: pytest.MonkeyPatch,
    api_key: None,
    logs,
) -> None:
    """AC-11: missing description column -> exit 2, 'missing required columns: description', no files, no calls; headers matched after strip+lower."""
    from categorizer.cli import main

    client = FakeClient(lambda call: answer("spa-day"))
    patch_client(monkeypatch, client)
    bad = write_csv(tmp_path / "bad.csv", ["title", "location"], [["Spa", "Vilnius"]])
    out_dir = tmp_path / "out"

    assert main([str(bad), "--tree", str(tree_file), "--out-dir", str(out_dir)]) == 2
    assert "missing required columns: description" in logs()
    assert not any(p.exists() for p in outputs(out_dir, "bad"))
    assert client.messages.calls == []

    loose = write_csv(
        tmp_path / "loose.csv",
        [" Title ", "DESCRIPTION", "location"],
        [["Spa", "Massage", "Vilnius"]],
    )
    assert main([str(loose), "--tree", str(tree_file), "--out-dir", str(out_dir)]) == 0
    assert len(client.messages.calls) == 1
