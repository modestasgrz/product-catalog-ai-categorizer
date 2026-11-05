import argparse
import csv
import sys
from pathlib import Path

from loguru import logger
from pydantic import BaseModel

REVIEW_STATUSES = {"review", "unknown", "error"}


class EvalReport(BaseModel):
    n: int
    top1_accuracy: float
    auto_accepted: int
    auto_accepted_accuracy: float | None
    review_rate: float


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m categorizer.evaluate",
        description="Score a categorized CSV against the gold answer key.",
    )
    parser.add_argument(
        "predictions",
        type=Path,
        help="<stem>_categorized.csv from the categorize command",
    )
    parser.add_argument(
        "gold", type=Path, help="gold CSV: listing_id,accepted_ids,source,note"
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="where to write the eval report JSON"
    )
    args = parser.parse_args(argv)

    with args.predictions.open(encoding="utf-8-sig", newline="") as f:
        predictions = {r["listing_id"]: r for r in csv.DictReader(f)}
    with args.gold.open(encoding="utf-8-sig", newline="") as f:
        gold = list(csv.DictReader(f))
    if missing := [g["listing_id"] for g in gold if g["listing_id"] not in predictions]:
        logger.error(f"missing predictions for {len(missing)} gold rows")
        return 2

    correct = [
        predictions[g["listing_id"]]["category_id"] in g["accepted_ids"].split("|")
        for g in gold
    ]
    statuses = [predictions[g["listing_id"]]["status"] for g in gold]
    accepted = [
        ok for ok, status in zip(correct, statuses, strict=True) if status == "ok"
    ]
    report = EvalReport(
        n=len(gold),
        top1_accuracy=round(sum(correct) / len(gold), 4),
        auto_accepted=len(accepted),
        auto_accepted_accuracy=round(sum(accepted) / len(accepted), 4)
        if accepted
        else None,
        review_rate=round(sum(s in REVIEW_STATUSES for s in statuses) / len(gold), 4),
    )
    args.out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    logger.info(
        f"n={report.n} top1_accuracy={report.top1_accuracy} auto_accepted={report.auto_accepted} auto_accepted_accuracy={report.auto_accepted_accuracy} review_rate={report.review_rate}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
