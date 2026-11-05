from pathlib import Path

import pytest
from fakes import (
    CANARY,
    LISTING_HEADER,
    FakeClient,
    FakeResponse,
    answer,
    outputs,
    read_csv,
    run_file,
    write_csv,
)


@pytest.mark.parametrize("bad", ["canary_id", "none"])
async def test_ac_06_invalid_twice_error(
    tmp_path: Path, tree_file: Path, bad: str
) -> None:
    """AC-06: two invalid answers (id not in tree, or parsed_output None) -> error 'invalid model output'; the bad id is in no output file."""
    src = write_csv(
        tmp_path / "listings.csv",
        LISTING_HEADER,
        [["L1", "Odd thing", "Something", "Vilnius", "1"]],
    )
    client = FakeClient(
        lambda call: (
            answer(CANARY, 0.99, CANARY)
            if bad == "canary_id"
            else FakeResponse(parsed_output=None)
        )
    )

    await run_file(src, tree_file, tmp_path, client)

    assert len(client.messages.calls) == 2
    row = read_csv(outputs(tmp_path, "listings")[0])[1][0]
    assert row["status"] == "error"
    assert row["category_id"] == "unknown"
    assert row["reason"] == "invalid model output"
    for path in outputs(tmp_path, "listings"):
        assert CANARY not in path.read_text(encoding="utf-8-sig")
