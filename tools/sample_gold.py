"""Draw the 100-row answer-key sample from data/labels.csv (spec DEC-14): both injection rows, 8 ambiguous, 6 unknown, the rest random."""

import argparse
import csv
import random
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
SIZE = 100


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="candidates CSV: listing_id,intended_ids",
    )
    args = parser.parse_args()

    rnd = random.Random(args.seed)
    with (DATA / "labels.csv").open(encoding="utf-8", newline="") as f:
        labels = [r for r in csv.DictReader(f) if r["listing_id"].startswith("EW-")]
    injection = [r for r in labels if "injection" in r["messiness"].split("|")]
    ambiguous = rnd.sample([r for r in labels if "|" in r["intended_ids"]], 8)
    unknown = rnd.sample([r for r in labels if r["intended_ids"] == "unknown"], 6)
    picked = {r["listing_id"] for r in injection + ambiguous + unknown}
    rest = rnd.sample(
        [r for r in labels if r["listing_id"] not in picked], SIZE - len(picked)
    )
    sample = sorted(
        injection + ambiguous + unknown + rest, key=lambda r: r["listing_id"]
    )

    with args.out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["listing_id", "intended_ids"])
        writer.writerows([r["listing_id"], r["intended_ids"]] for r in sample)


if __name__ == "__main__":
    main()
