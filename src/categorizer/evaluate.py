import argparse
import csv
import sys
from pathlib import Path

from loguru import logger
from pydantic import BaseModel

REVIEW_STATUSES = {"review", "unknown", "error"}
STATUSES = {"ok", *REVIEW_STATUSES}
REQUIRED_COLUMNS = {"listing_id", "status", "category_id"}
GOLD_COLUMNS = {"listing_id", "accepted_ids"}


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

    try:
        with args.predictions.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            columns, rows = set(reader.fieldnames or []), list(reader)
        with args.gold.open(encoding="utf-8-sig", newline="") as f:
            gold_reader = csv.DictReader(f)
            gold_columns, gold = set(gold_reader.fieldnames or []), list(gold_reader)
    except (OSError, UnicodeDecodeError) as e:
        logger.error(f"cannot read the input files: {type(e).__name__}")
        return 2
    predictions = {r["listing_id"]: r for r in rows} if "listing_id" in columns else {}
    problem = ""
    if not columns >= REQUIRED_COLUMNS:
        problem = f"predictions need the columns {', '.join(sorted(REQUIRED_COLUMNS))}"
    elif not gold_columns >= GOLD_COLUMNS:
        problem = f"gold file needs the columns {', '.join(sorted(GOLD_COLUMNS))}"
    elif len(predictions) != len(rows) or len({g["listing_id"] for g in gold}) != len(
        gold
    ):
        problem = "duplicate listing_id in the predictions or the gold file"
    elif not gold:
        problem = "gold file has no rows"
    elif bad := sorted({r["status"] for r in rows} - STATUSES):
        problem = f"unknown status values in the predictions: {bad}"
    elif missing := [
        g["listing_id"] for g in gold if g["listing_id"] not in predictions
    ]:
        problem = f"missing predictions for {len(missing)} gold rows"
    if problem:
        logger.error(problem)
        return 2

    picked = [predictions[g["listing_id"]] for g in gold]
    statuses = [p["status"] for p in picked]
    predicted = [
        "unknown" if p["status"] in ("unknown", "error") else p["category_id"]
        for p in picked
    ]
    correct = [
        pred in {i.strip() for i in g["accepted_ids"].split("|")}
        for pred, g in zip(predicted, gold, strict=True)
    ]
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
    try:
        args.out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    except OSError as e:
        logger.error(f"cannot write the report: {type(e).__name__}")
        return 2
    logger.info(
        f"n={report.n} top1_accuracy={report.top1_accuracy} auto_accepted={report.auto_accepted} auto_accepted_accuracy={report.auto_accepted_accuracy} review_rate={report.review_rate}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
