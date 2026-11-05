from pathlib import Path

from fakes import (
    LISTING_HEADER,
    NEW_COLUMNS,
    TREE_FIXTURE,
    FakeClient,
    answer,
    outputs,
    read_csv,
    run_file,
    title_of,
    write_csv,
)


async def test_ac_01_happy_path_output(tmp_path: Path, tree_file: Path) -> None:
    """AC-01: valid answers at 0.90 -> categorized CSV (UTF-8 BOM, comma, new columns first, input order, tree name/url, originals unchanged)."""
    rows = [
        ["L1", "Balloon over Trakai", "Sunrise flight", "Trakai", "199"],
        ["L2", "Spa diena", "Pirtis ir masažas", "Vilnius", "89"],
        ["L3", "Vīna degustācija", "Pieci vīni", "Rīga", "45"],
    ]
    ids = {
        "Balloon over Trakai": "balloon",
        "Spa diena": "spa-day",
        "Vīna degustācija": "wine-tasting",
    }
    src = write_csv(tmp_path / "listings.csv", LISTING_HEADER, rows)
    client = FakeClient(lambda call: answer(ids[title_of(call)], 0.90))
    out_dir = tmp_path / "out"

    await run_file(src, tree_file, out_dir, client)

    categorized, _, _ = outputs(out_dir, "listings")
    assert categorized.read_bytes().startswith(b"\xef\xbb\xbf")
    first_line = categorized.read_text(encoding="utf-8-sig").splitlines()[0]
    assert first_line == ",".join(NEW_COLUMNS + LISTING_HEADER)
    header, out_rows = read_csv(categorized)
    assert header == NEW_COLUMNS + LISTING_HEADER
    tree = {c["id"]: c for c in TREE_FIXTURE["categories"]}
    assert [r["listing_id"] for r in out_rows] == ["L1", "L2", "L3"]
    for row, original in zip(out_rows, rows, strict=True):
        cat = tree[ids[original[1]]]
        assert row["status"] == "ok"
        assert row["category_id"] == cat["id"]
        assert row["category_name"] == cat["name"]
        assert row["category_url"] == cat["url"]
        assert row["confidence"] == "0.90"
        assert [row[c] for c in LISTING_HEADER] == original
