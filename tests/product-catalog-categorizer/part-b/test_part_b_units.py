import csv
import json
import subprocess
import sys
from pathlib import Path

from categorizer.evaluate import main

REPO = Path(__file__).resolve().parents[3]


def write(path: Path, header: list[str], rows: list[list[str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def test_no_ok_rows_gives_null_auto_accepted_accuracy(tmp_path: Path) -> None:
    pred = write(
        tmp_path / "p.csv",
        ["status", "category_id", "listing_id"],
        [["review", "spa-day", "A"], ["error", "unknown", "B"]],
    )
    gold = write(
        tmp_path / "g.csv",
        ["listing_id", "accepted_ids", "source", "note"],
        [["A", "spa-day", "generator", ""], ["B", "unknown", "generator", ""]],
    )
    out = tmp_path / "r.json"
    assert main([str(pred), str(gold), "--out", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report == {
        "n": 2,
        "top1_accuracy": 1.0,
        "auto_accepted": 0,
        "auto_accepted_accuracy": None,
        "review_rate": 1.0,
    }


def test_reads_bom_predictions_written_by_the_cli(tmp_path: Path) -> None:
    pred = tmp_path / "p.csv"
    pred.write_text(
        "status,category_id,listing_id\nok,spa-day,A\n", encoding="utf-8-sig"
    )
    gold = write(
        tmp_path / "g.csv",
        ["listing_id", "accepted_ids", "source", "note"],
        [["A", "balloon|spa-day", "settled", "both fit"]],
    )
    out = tmp_path / "r.json"
    assert main([str(pred), str(gold), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["top1_accuracy"] == 1.0


def test_gold_sample_is_reproducible_and_stratified(tmp_path: Path) -> None:
    runs = []
    for name in ("a.csv", "b.csv"):
        subprocess.run(
            [
                sys.executable,
                str(REPO / "tools" / "sample_gold.py"),
                "--seed",
                "42",
                "--out",
                str(tmp_path / name),
            ],
            check=True,
        )
        runs.append((tmp_path / name).read_bytes())
    assert runs[0] == runs[1]
    with (tmp_path / "a.csv").open(encoding="utf-8", newline="") as f:
        sample = list(csv.DictReader(f))
    assert len(sample) == 100
    assert sum("|" in r["intended_ids"] for r in sample) >= 8
    assert sum(r["intended_ids"] == "unknown" for r in sample) >= 6
