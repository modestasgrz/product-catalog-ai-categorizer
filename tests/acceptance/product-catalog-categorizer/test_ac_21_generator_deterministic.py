import csv
import subprocess
import sys
from pathlib import Path

import pytest
from fakes import DATA, REPO

FILES = ["listings.csv", "listings_legacy_cp1257.csv", "labels.csv"]


def generate(out_dir: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(REPO / "tools" / "generate_listings.py"),
            "--seed",
            "42",
            "--out-dir",
            str(out_dir),
        ],
        check=True,
        cwd=REPO,
    )


def count_rows(path: Path, encoding: str, delimiter: str = ",") -> int:
    with path.open(encoding=encoding, newline="") as f:
        return sum(1 for _ in csv.DictReader(f, delimiter=delimiter))


def test_ac_21_generator_deterministic(tmp_path: Path) -> None:
    """AC-21: seed 42 twice -> byte-identical files with the right sizes/encodings; committed data/ equals the seed-42 output."""
    first, second = tmp_path / "a", tmp_path / "b"
    generate(first)
    generate(second)
    for name in FILES:
        assert (first / name).read_bytes() == (second / name).read_bytes(), name
        assert (first / name).read_bytes() == (DATA / name).read_bytes(), (
            f"data/{name} differs from seed-42 output"
        )

    assert count_rows(first / "listings.csv", "utf-8") == 1000
    legacy = first / "listings_legacy_cp1257.csv"
    with pytest.raises(UnicodeDecodeError):
        legacy.read_bytes().decode("utf-8")
    assert legacy.read_text(encoding="cp1257").splitlines()[0].count(";") >= 2
    assert count_rows(legacy, "cp1257", ";") == 40
    with (first / "labels.csv").open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == [
            "listing_id",
            "intended_ids",
            "language",
            "messiness",
        ]
        assert sum(1 for _ in reader) == 1040
