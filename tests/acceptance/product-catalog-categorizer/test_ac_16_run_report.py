import json
from pathlib import Path

import anthropic
from fakes import (
    LISTING_HEADER,
    FakeClient,
    answer,
    outputs,
    run_file,
    status_error,
    title_of,
    write_csv,
)


async def test_ac_16_run_report(tmp_path: Path, tree_file: Path) -> None:
    """AC-16: run report counts, token sums of answered calls, cost formula, model, threshold, encoding, duration."""
    rows = [
        ["L1", "Ok", "d", "Vilnius", "1"],
        ["L2", "Review", "d", "Vilnius", "1"],
        ["L3", "Unknown", "d", "Vilnius", "1"],
        ["L4", "Error", "d", "Vilnius", "1"],
    ]
    src = write_csv(tmp_path / "listings.csv", LISTING_HEADER, rows)

    def respond(call: dict) -> object:
        title = title_of(call)
        if title == "Error":
            raise status_error(anthropic.RateLimitError, 429)
        if title == "Unknown":
            return answer("unknown", 0.3)
        return answer("balloon", 0.90 if title == "Ok" else 0.50)

    await run_file(src, tree_file, tmp_path, FakeClient(respond))

    report = json.loads(outputs(tmp_path, "listings")[2].read_text(encoding="utf-8"))
    assert report["rows_total"] == 4
    assert report["status_counts"] == {"ok": 1, "review": 1, "unknown": 1, "error": 1}
    assert report["input_tokens"] == 300
    assert report["output_tokens"] == 150
    assert report["cache_read_input_tokens"] == 3000
    assert report["cache_creation_input_tokens"] == 0
    assert report["estimated_cost_usd"] == 0.0027
    assert report["model"] == "claude-sonnet-5-5"
    assert report["threshold"] == 0.7
    assert report["encoding"] == "utf-8-sig"
    assert report["duration_seconds"] >= 0
