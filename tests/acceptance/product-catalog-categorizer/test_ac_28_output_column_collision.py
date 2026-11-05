from pathlib import Path

import pytest
from fakes import FakeClient, answer, outputs, patch_client, write_csv


def test_ac_28_output_column_collision(
    tmp_path: Path,
    tree_file: Path,
    monkeypatch: pytest.MonkeyPatch,
    api_key: None,
    logs,
) -> None:
    """AC-28: input columns that collide with the new output columns -> exit 2, 'input already has output columns: status, category_id', no files, no calls."""
    from categorizer.cli import main

    client = FakeClient(lambda call: answer("spa-day"))
    patch_client(monkeypatch, client)
    src = write_csv(
        tmp_path / "clash.csv",
        ["category_id", "title", "description", "location", " Status "],
        [["P-7", "Spa", "Massage", "Vilnius", "active"]],
    )
    out_dir = tmp_path / "out"

    assert main([str(src), "--tree", str(tree_file), "--out-dir", str(out_dir)]) == 2
    assert "input already has output columns: status, category_id" in logs()
    assert not any(p.exists() for p in outputs(out_dir, "clash"))
    assert client.messages.calls == []
