import subprocess
import sys
from pathlib import Path

from fakes import REPO, write_csv


def test_ac_25_eval_missing_predictions(tmp_path: Path) -> None:
    """AC-25: a gold id missing from predictions -> exit 2, 'missing predictions for 1 gold rows', no report."""
    pred = write_csv(
        tmp_path / "pred.csv",
        ["status", "category_id", "listing_id"],
        [["ok", "balloon", "G01"]],
    )
    gold = write_csv(
        tmp_path / "gold.csv",
        ["listing_id", "accepted_ids", "source", "note"],
        [["G01", "balloon", "generator", ""], ["G02", "spa-day", "generator", ""]],
    )
    report = tmp_path / "eval.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "categorizer.evaluate",
            str(pred),
            str(gold),
            "--out",
            str(report),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "missing predictions for 1 gold rows" in result.stdout + result.stderr
    assert not report.exists()
