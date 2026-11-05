import json
from pathlib import Path

from fakes import FakeClient, answer, outputs, read_csv, run_file, user_text, write_csv


async def test_ac_09_encoding_fallback(tmp_path: Path, tree_file: Path) -> None:
    """AC-09: cp1257 file decoded correctly (report encoding cp1257); UTF-8 BOM file -> utf-8-sig, first header matched without BOM."""
    header = ["title", "description", "location"]
    legacy = write_csv(
        tmp_path / "legacy.csv",
        header,
        [["SPA diena", "Lepinimas: ąčęėįšųūž", "Šiauliai"]],
        encoding="cp1257",
    )
    client = FakeClient(lambda call: answer("spa-day"))

    await run_file(legacy, tree_file, tmp_path, client)

    sent = user_text(client.messages.calls[0])
    assert "Šiauliai" in sent
    assert "ąčęėįšųūž" in sent
    assert (
        json.loads(outputs(tmp_path, "legacy")[2].read_text(encoding="utf-8"))[
            "encoding"
        ]
        == "cp1257"
    )

    bom = write_csv(
        tmp_path / "bom.csv",
        header,
        [["Spa", "Massage", "Vilnius"]],
        encoding="utf-8-sig",
    )
    bom_client = FakeClient(lambda call: answer("spa-day"))
    await run_file(bom, tree_file, tmp_path, bom_client)

    assert "title: Spa" in user_text(bom_client.messages.calls[0])
    assert (
        json.loads(outputs(tmp_path, "bom")[2].read_text(encoding="utf-8"))["encoding"]
        == "utf-8-sig"
    )
    out_header, _ = read_csv(outputs(tmp_path, "bom")[0])
    assert out_header[6] == "title"
