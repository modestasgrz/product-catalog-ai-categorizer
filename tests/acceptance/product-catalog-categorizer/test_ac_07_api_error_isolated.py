from pathlib import Path

import anthropic
from fakes import (
    CANARY,
    LISTING_HEADER,
    FakeClient,
    answer,
    connection_error,
    outputs,
    read_csv,
    run_file,
    status_error,
    title_of,
    write_csv,
)


async def test_ac_07_api_error_isolated(tmp_path: Path, tree_file: Path, logs) -> None:
    """AC-07: an API error on one row -> only that row is error with class + status; provider body in no file and no log."""
    rows = [
        ["L1", "One", "d", "Vilnius", "1"],
        ["L2", "Two", "d", "Kaunas", "2"],
        ["L3", "Three", "d", "Riga", "3"],
    ]
    src = write_csv(tmp_path / "listings.csv", LISTING_HEADER, rows)

    def respond(call: dict) -> object:
        if title_of(call) == "Two":
            raise status_error(anthropic.RateLimitError, 429)
        return answer("balloon")

    await run_file(src, tree_file, tmp_path, FakeClient(respond))

    out_rows = read_csv(outputs(tmp_path, "listings")[0])[1]
    assert [r["status"] for r in out_rows] == ["ok", "error", "ok"]
    assert out_rows[1]["category_id"] == "unknown"
    assert out_rows[1]["reason"] == "model call failed: RateLimitError 429"
    for path in outputs(tmp_path, "listings"):
        assert CANARY not in path.read_text(encoding="utf-8-sig")
    assert CANARY not in logs()

    conn_dir = tmp_path / "conn"

    def respond_conn(call: dict) -> object:
        if title_of(call) == "Two":
            raise connection_error()
        return answer("balloon")

    await run_file(src, tree_file, conn_dir, FakeClient(respond_conn))
    assert (
        read_csv(outputs(conn_dir, "listings")[0])[1][1]["reason"]
        == "model call failed: APIConnectionError"
    )
