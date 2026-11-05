import json
import subprocess
import sys
from pathlib import Path

from fakes import REPO, write_csv

PRED = [
    ("G01", "ok", "balloon"),
    ("G02", "ok", "balloon"),
    ("G03", "ok", "spa-day"),
    ("G04", "ok", "spa-day"),
    ("G05", "ok", "wine-tasting"),
    ("G06", "ok", "wine-tasting"),
    ("G07", "ok", "balloon"),
    ("G08", "review", "spa-day"),
    ("G09", "error", "unknown"),
    ("G10", "unknown", "unknown"),
]
GOLD = [
    ("G01", "balloon"),
    ("G02", "balloon|spa-day"),
    ("G03", "spa-day"),
    ("G04", "spa-day"),
    ("G05", "wine-tasting"),
    ("G06", "wine-tasting"),
    ("G07", "spa-day"),
    ("G08", "spa-day"),
    ("G09", "balloon"),
    ("G10", "unknown"),
]


def test_ac_24_eval_metrics(tmp_path: Path) -> None:
    """AC-24: 10-row fixture -> n=10, top1 0.8, auto_accepted 7, auto_accepted_accuracy 0.8571, review_rate 0.3."""
    pred = write_csv(
        tmp_path / "pred.csv",
        [
            "status",
            "category_name",
            "confidence",
            "reason",
            "category_id",
            "category_url",
            "listing_id",
        ],
        [[s, "", "0.90", "r", c, "", lid] for lid, s, c in PRED],
    )
    gold = write_csv(
        tmp_path / "gold.csv",
        ["listing_id", "accepted_ids", "source", "note"],
        [[lid, a, "generator", ""] for lid, a in GOLD],
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
        check=False,
    )

    assert result.returncode == 0
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["n"] == 10
    assert data["top1_accuracy"] == 0.8
    assert data["auto_accepted"] == 7
    assert data["auto_accepted_accuracy"] == 0.8571
    assert data["review_rate"] == 0.3
