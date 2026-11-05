from pathlib import Path

from fakes import (
    NEW_COLUMNS,
    FakeClient,
    answer,
    outputs,
    read_csv,
    run_file,
    write_csv,
)


async def test_ac_10_semicolon_delimiter(tmp_path: Path, tree_file: Path) -> None:
    """AC-10: header with more ';' than ',' -> split on ';', all rows classified, output comma-delimited."""
    header = ["title", "description", "location"]
    rows = [["Spa, sauna", "Massage, pool", "Vilnius"], ["Balloon", "Flight", "Trakai"]]
    src = write_csv(tmp_path / "export.csv", header, rows, delimiter=";")
    client = FakeClient(lambda call: answer("spa-day"))

    await run_file(src, tree_file, tmp_path, client)

    assert len(client.messages.calls) == 2
    categorized = outputs(tmp_path, "export")[0]
    assert categorized.read_text(encoding="utf-8-sig").splitlines()[0] == ",".join(
        NEW_COLUMNS + header
    )
    _, out_rows = read_csv(categorized)
    assert [r["title"] for r in out_rows] == ["Spa, sauna", "Balloon"]
    assert all(r["status"] == "ok" for r in out_rows)
