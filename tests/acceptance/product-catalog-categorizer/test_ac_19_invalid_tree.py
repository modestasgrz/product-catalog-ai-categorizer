import json
from pathlib import Path

import pytest
from fakes import (
    LISTING_HEADER,
    TREE_FIXTURE,
    FakeClient,
    answer,
    listing_rows,
    patch_client,
    write_csv,
)


@pytest.mark.parametrize("problem", ["duplicate", "reserved"])
def test_ac_19_invalid_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, api_key: None, logs, problem: str
) -> None:
    """AC-19: duplicate id or id 'unknown' in the tree -> exit 2, 'invalid category tree', no model call."""
    from categorizer.cli import main

    categories = [dict(c) for c in TREE_FIXTURE["categories"]]
    if problem == "duplicate":
        categories.append(dict(categories[0]))
    else:
        categories[0]["id"] = "unknown"
    tree = tmp_path / "tree.json"
    tree.write_text(
        json.dumps({"marketplace": "Test Market", "categories": categories}),
        encoding="utf-8",
    )
    client = FakeClient(lambda call: answer("balloon"))
    patch_client(monkeypatch, client)
    src = write_csv(tmp_path / "listings.csv", LISTING_HEADER, listing_rows(2))

    assert (
        main([str(src), "--tree", str(tree), "--out-dir", str(tmp_path / "out")]) == 2
    )
    assert "invalid category tree" in logs()
    assert client.messages.calls == []
