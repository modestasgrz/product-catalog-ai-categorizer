import csv
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SAMPLER = REPO / "tools" / "sample_gold.py"
DATA = REPO / "data"


def run_sampler(out: Path, seed: int) -> list[dict[str, str]]:
    subprocess.run(
        [sys.executable, str(SAMPLER), "--seed", str(seed), "--out", str(out)],
        check=True,
        capture_output=True,
    )
    with out.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@pytest.mark.parametrize("seed", [0, 1, 7, 42, 123])
def test_sample_is_100_unique_sorted_web_rows_with_the_stratum_minimums(
    tmp_path: Path, seed: int
) -> None:
    sample = run_sampler(tmp_path / "c.csv", seed)
    ids = [r["listing_id"] for r in sample]
    assert len(ids) == 100
    assert len(set(ids)) == 100
    assert ids == sorted(ids)
    assert all(i.startswith("EW-") for i in ids)
    assert sum("|" in r["intended_ids"] for r in sample) >= 8
    assert sum(r["intended_ids"] == "unknown" for r in sample) >= 6


@pytest.mark.parametrize("seed", [0, 7, 123])
def test_sample_always_contains_both_injection_rows_and_matches_labels(
    tmp_path: Path, seed: int
) -> None:
    sample = run_sampler(tmp_path / "c.csv", seed)
    with (DATA / "labels.csv").open(encoding="utf-8", newline="") as f:
        labels = {r["listing_id"]: r for r in csv.DictReader(f)}
    injection = {
        i for i, r in labels.items() if "injection" in r["messiness"].split("|")
    }
    assert len(injection) == 2
    assert injection <= {r["listing_id"] for r in sample}
    assert all(
        labels[r["listing_id"]]["intended_ids"] == r["intended_ids"] for r in sample
    )


def test_different_seeds_pick_different_rows(tmp_path: Path) -> None:
    a = run_sampler(tmp_path / "a.csv", 1)
    b = run_sampler(tmp_path / "b.csv", 2)
    assert a != b


def test_missing_out_folder_fails_without_creating_it(tmp_path: Path) -> None:
    out = tmp_path / "nope" / "c.csv"
    result = subprocess.run(
        [sys.executable, str(SAMPLER), "--out", str(out)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert not out.exists()


def test_out_flag_is_required(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SAMPLER)], capture_output=True, text=True
    )
    assert result.returncode == 2
