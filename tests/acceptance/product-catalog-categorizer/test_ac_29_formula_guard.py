from pathlib import Path

from fakes import FakeClient, answer, outputs, read_csv, run_file, title_of, write_csv

REASONS = {
    "eq": '=HYPERLINK("https://evil.example")',
    "plus": "+1 looks like a spa",
    "minus": "-spa day, runner-up balloon",
    "at": "@SUM(1)",
    "plain": "Spa day with massage.",
}


async def test_ac_29_formula_guard(tmp_path: Path, tree_file: Path) -> None:
    """AC-29: model reasons starting with = + - @ get a leading ' ; other reasons and input cells are unchanged."""
    rows = [[key, "description", "Vilnius"] for key in REASONS]
    rows.append(["=SUM(A1:A9)", "description", "Vilnius"])
    src = write_csv(
        tmp_path / "listings.csv", ["title", "description", "location"], rows
    )
    client = FakeClient(
        lambda call: answer(
            "spa-day", 0.9, REASONS.get(title_of(call), "Plain reason.")
        )
    )

    await run_file(src, tree_file, tmp_path, client)

    out = {r["title"]: r for r in read_csv(outputs(tmp_path, "listings")[0])[1]}
    for key in ("eq", "plus", "minus", "at"):
        assert out[key]["reason"] == "'" + REASONS[key]
    assert out["plain"]["reason"] == REASONS["plain"]
    assert out["=SUM(A1:A9)"]["title"] == "=SUM(A1:A9)"
    assert out["=SUM(A1:A9)"]["reason"] == "Plain reason."
