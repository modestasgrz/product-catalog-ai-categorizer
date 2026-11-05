import csv
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VIEWER = REPO / "tools" / "view_results.py"
COLUMNS = [
    "status",
    "category_name",
    "confidence",
    "reason",
    "category_id",
    "category_url",
    "listing_id",
    "title",
    "description",
    "location",
]


def test_page_scores_against_key_and_escapes_listing_text(tmp_path: Path) -> None:
    categorized = tmp_path / "x_categorized.csv"
    with categorized.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        w.writerow(
            [
                "ok",
                "Skydiving",
                "0.95",
                "jump",
                "skydiving",
                "u",
                "EW-1",
                "</script><b>x",
                "",
                "",
            ]
        )
        w.writerow(
            [
                "review",
                "Paragliding",
                "0.50",
                "'=unsure",
                "paragliding",
                "u",
                "EW-2",
                "t",
                "",
                "",
            ]
        )
        w.writerow(
            ["unknown", "", "0.10", "no fit", "unknown", "", "EW-3", "t", "", ""]
        )
    gold = tmp_path / "gold.csv"
    gold.write_text(
        "listing_id,accepted_ids,source,note\nEW-1,skydiving,generator,\nEW-2,skydiving,generator,\nEW-3,unknown,generator,\n",
        encoding="utf-8",
    )
    (tmp_path / "x_run_report.json").write_text(
        json.dumps(
            {
                "estimated_cost_usd": 0.5,
                "duration_seconds": 12,
                "model": "m",
                "encoding": "utf-8",
                "threshold": 0.7,
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "page.html"

    subprocess.run(
        [
            sys.executable,
            str(VIEWER),
            str(categorized),
            "--gold",
            str(gold),
            "--out",
            str(out),
            "--tree",
            str(REPO / "data" / "category_tree.json"),
        ],
        check=True,
        capture_output=True,
    )

    page = out.read_text(encoding="utf-8")
    payload = page.split('id="data">')[1].split("</script>")[0]
    data = json.loads(payload)
    assert "</script><b>" not in payload
    assert data["tiles"][0][1] == "2/3"
    assert [r["key"] for r in data["rows"]] == [True, False, True]
    assert data["rows"][1]["reason"] == "=unsure"
    assert data["rows"][1]["expected"] == "Skydiving"
    assert ["cost", "$0.50", False] in data["tiles"]


def test_later_run_replaces_same_id_and_adds_new_rows(tmp_path: Path) -> None:
    files = []
    for name, rows in (
        (
            "main",
            [
                [
                    "ok",
                    "Skydiving",
                    "0.9",
                    "old",
                    "skydiving",
                    "u",
                    "EW-1",
                    "a",
                    "",
                    "",
                ],
                ["ok", "Golf", "0.9", "g", "golf-lesson", "u", "EW-2", "b", "", ""],
            ],
        ),
        (
            "inj",
            [
                ["ok", "Massage", "0.9", "new", "massage", "u", "EW-1", "a", "", ""],
                ["ok", "Massage", "0.9", "h", "massage", "u", "EW-H1", "c", "", ""],
            ],
        ),
    ):
        path = tmp_path / f"{name}_categorized.csv"
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(COLUMNS)
            w.writerows(rows)
        (tmp_path / f"{name}_run_report.json").write_text(
            json.dumps(
                {
                    "estimated_cost_usd": 1.0,
                    "duration_seconds": 10,
                    "model": "m",
                    "threshold": 0.7,
                }
            ),
            encoding="utf-8",
        )
        files.append(str(path))
    gold = tmp_path / "gold.csv"
    gold.write_text(
        "listing_id,accepted_ids,source,note\nEW-H1,massage,hand,injection: test\n",
        encoding="utf-8",
    )
    out = tmp_path / "page.html"

    subprocess.run(
        [
            sys.executable,
            str(VIEWER),
            *files,
            "--injections",
            str(gold),
            "--out",
            str(out),
            "--tree",
            str(REPO / "data" / "category_tree.json"),
        ],
        check=True,
        capture_output=True,
    )

    data = json.loads(
        out.read_text(encoding="utf-8").split('id="data">')[1].split("</script>")[0]
    )
    assert [(r["listing_id"], r["reason"]) for r in data["rows"]] == [
        ("EW-1", "new"),
        ("EW-2", "g"),
        ("EW-H1", "h"),
    ]
    assert data["rows"][2]["note"] == "injection: test"
    assert data["tiles"][0] == ["injection attacks blocked", "1/1", True]
    assert ["listings (+1 injection tests)", "2", False] in data["tiles"]
    assert ["cost", "$2.00", False] in data["tiles"]
