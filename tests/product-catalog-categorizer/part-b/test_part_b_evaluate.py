import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from categorizer.evaluate import main

REPO = Path(__file__).resolve().parents[3]
PRED_HEADER = ["listing_id", "status", "category_id"]
GOLD_HEADER = ["listing_id", "accepted_ids", "source", "note"]


def write(path: Path, header: list[str], rows: list[list[str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def gold_file(tmp_path: Path, rows: list[tuple[str, str]]) -> Path:
    return write(
        tmp_path / "g.csv", GOLD_HEADER, [[i, a, "generator", ""] for i, a in rows]
    )


def cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "categorizer.evaluate", *args],
        capture_output=True,
        text=True,
        cwd=REPO,
    )


def test_gold_row_with_two_ids_accepts_either_and_rejects_others(
    tmp_path: Path,
) -> None:
    pred = write(
        tmp_path / "p.csv",
        PRED_HEADER,
        [["A", "ok", "spa-day"], ["B", "ok", "balloon"], ["C", "ok", "golf"]],
    )
    gold = gold_file(
        tmp_path,
        [("A", "balloon|spa-day"), ("B", "balloon|spa-day"), ("C", "balloon|spa-day")],
    )
    out = tmp_path / "r.json"
    assert main([str(pred), str(gold), "--out", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["top1_accuracy"] == pytest.approx(0.6667)
    assert report["auto_accepted_accuracy"] == pytest.approx(0.6667)


def test_prediction_equal_to_the_joined_string_is_not_a_match(tmp_path: Path) -> None:
    pred = write(tmp_path / "p.csv", PRED_HEADER, [["A", "ok", "a|b"]])
    gold = gold_file(tmp_path, [("A", "a|b")])
    out = tmp_path / "r.json"
    assert main([str(pred), str(gold), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["top1_accuracy"] == 0.0


def test_extra_prediction_rows_not_in_gold_are_ignored(tmp_path: Path) -> None:
    pred = write(
        tmp_path / "p.csv",
        PRED_HEADER,
        [["A", "ok", "x"], ["Z1", "ok", "y"], ["Z2", "review", "y"]],
    )
    gold = gold_file(tmp_path, [("A", "x")])
    out = tmp_path / "r.json"
    assert main([str(pred), str(gold), "--out", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert (report["n"], report["auto_accepted"], report["review_rate"]) == (1, 1, 0.0)


def test_unknown_and_error_rows_predict_unknown_whatever_category_id_says(
    tmp_path: Path,
) -> None:
    pred = write(
        tmp_path / "p.csv",
        PRED_HEADER,
        [["A", "error", ""], ["B", "unknown", "spa-day"]],
    )
    gold = gold_file(tmp_path, [("A", "unknown"), ("B", "unknown")])
    out = tmp_path / "r.json"
    assert main([str(pred), str(gold), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["top1_accuracy"] == 1.0


def test_missing_ids_exit_2_and_leave_no_report(tmp_path: Path) -> None:
    pred = write(tmp_path / "p.csv", PRED_HEADER, [["A", "ok", "x"]])
    gold = gold_file(tmp_path, [("A", "x"), ("B", "x"), ("C", "x")])
    out = tmp_path / "r.json"
    result = cli(str(pred), str(gold), "--out", str(out))
    assert result.returncode == 2
    assert "missing predictions for 2 gold rows" in result.stderr
    assert not out.exists()


def test_report_is_the_exact_five_keys_and_rounded_to_four_decimals(
    tmp_path: Path,
) -> None:
    pred = write(
        tmp_path / "p.csv",
        PRED_HEADER,
        [["A", "ok", "x"], ["B", "ok", "y"], ["C", "review", "x"]],
    )
    gold = gold_file(tmp_path, [(i, "x") for i in "ABC"])
    out = tmp_path / "r.json"
    assert main([str(pred), str(gold), "--out", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert list(report) == [
        "n",
        "top1_accuracy",
        "auto_accepted",
        "auto_accepted_accuracy",
        "review_rate",
    ]
    assert report["top1_accuracy"] == 0.6667
    assert report["review_rate"] == 0.3333


def test_cli_exit_code_is_0_on_success(tmp_path: Path) -> None:
    pred = write(tmp_path / "p.csv", PRED_HEADER, [["A", "ok", "x"]])
    gold = gold_file(tmp_path, [("A", "x")])
    out = tmp_path / "r.json"
    result = cli(str(pred), str(gold), "--out", str(out))
    assert result.returncode == 0
    assert json.loads(out.read_text(encoding="utf-8"))["n"] == 1


def test_cli_without_out_exits_2(tmp_path: Path) -> None:
    pred = write(tmp_path / "p.csv", PRED_HEADER, [["A", "ok", "x"]])
    gold = gold_file(tmp_path, [("A", "x")])
    assert cli(str(pred), str(gold)).returncode == 2


def test_existing_report_is_overwritten(tmp_path: Path) -> None:
    pred = write(tmp_path / "p.csv", PRED_HEADER, [["A", "ok", "x"]])
    gold = gold_file(tmp_path, [("A", "x")])
    out = tmp_path / "r.json"
    out.write_text("stale and much longer than the new report " * 100, encoding="utf-8")
    assert main([str(pred), str(gold), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["n"] == 1


def test_non_ascii_listing_ids_and_crlf_files_are_read(tmp_path: Path) -> None:
    pred = tmp_path / "p.csv"
    pred.write_bytes(
        "listing_id,status,category_id\r\nĖ-1,ok,x\r\n".encode("utf-8-sig")
    )
    gold = tmp_path / "g.csv"
    gold.write_bytes(
        "listing_id,accepted_ids,source,note\r\nĖ-1,x,generator,\r\n".encode()
    )
    out = tmp_path / "r.json"
    assert main([str(pred), str(gold), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["top1_accuracy"] == 1.0


def test_whitespace_around_accepted_ids_is_ignored(tmp_path: Path) -> None:
    pred = write(tmp_path / "p.csv", PRED_HEADER, [["A", "ok", "b"]])
    gold = gold_file(tmp_path, [("A", "a | b ")])
    out = tmp_path / "r.json"
    assert main([str(pred), str(gold), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["top1_accuracy"] == 1.0


def test_review_status_with_a_correct_id_counts_for_top1_but_not_auto_accepted(
    tmp_path: Path,
) -> None:
    pred = write(tmp_path / "p.csv", PRED_HEADER, [["A", "review", "x"]])
    gold = gold_file(tmp_path, [("A", "x")])
    out = tmp_path / "r.json"
    assert main([str(pred), str(gold), "--out", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert (report["top1_accuracy"], report["auto_accepted"]) == (1.0, 0)
    assert report["auto_accepted_accuracy"] is None
    assert report["review_rate"] == 1.0


def reject_case(tmp_path: Path, case: str) -> tuple[list[str], str]:
    pred = write(tmp_path / "p.csv", PRED_HEADER, [["A", "ok", "x"], ["B", "ok", "x"]])
    gold = gold_file(tmp_path, [("A", "x")])
    out = str(tmp_path / "r.json")
    if case == "dup_pred":
        pred = write(
            tmp_path / "p.csv", PRED_HEADER, [["A", "ok", "x"], ["A", "ok", "y"]]
        )
        return [str(pred), str(gold), "--out", out], "duplicate listing_id"
    if case == "dup_gold":
        gold = gold_file(tmp_path, [("A", "x"), ("A", "x")])
        return [str(pred), str(gold), "--out", out], "duplicate listing_id"
    if case == "bad_status":
        pred = write(tmp_path / "p.csv", PRED_HEADER, [["A", "pending", "x"]])
        return [str(pred), str(gold), "--out", out], "unknown status values"
    if case == "upper_status":
        pred = write(tmp_path / "p.csv", PRED_HEADER, [["A", "OK", "x"]])
        return [str(pred), str(gold), "--out", out], "unknown status values"
    if case == "blank_status":
        pred = write(tmp_path / "p.csv", PRED_HEADER, [["A", "", "x"]])
        return [str(pred), str(gold), "--out", out], "unknown status values"
    if case == "missing_columns":
        pred = write(tmp_path / "p.csv", ["listing_id", "title"], [["A", "t"]])
        return [str(pred), str(gold), "--out", out], "predictions need the columns"
    if case == "empty_predictions_file":
        (tmp_path / "p.csv").write_text("", encoding="utf-8")
        return [
            str(tmp_path / "p.csv"),
            str(gold),
            "--out",
            out,
        ], "predictions need the columns"
    if case == "empty_gold":
        gold = gold_file(tmp_path, [])
        return [str(pred), str(gold), "--out", out], "gold file has no rows"
    if case == "missing_pred_file":
        return [
            str(tmp_path / "absent.csv"),
            str(gold),
            "--out",
            out,
        ], "cannot read the input files"
    if case == "missing_gold_file":
        return [
            str(pred),
            str(tmp_path / "absent.csv"),
            "--out",
            out,
        ], "cannot read the input files"
    if case == "directory_as_input":
        return [str(tmp_path), str(gold), "--out", out], "cannot read the input files"
    if case == "missing_out_folder":
        return [
            str(pred),
            str(gold),
            "--out",
            str(tmp_path / "nope" / "r.json"),
        ], "cannot write the report"
    if case == "out_is_a_directory":
        return [str(pred), str(gold), "--out", str(tmp_path)], "cannot write the report"
    raise AssertionError(case)


@pytest.mark.parametrize(
    "case",
    [
        "dup_pred",
        "dup_gold",
        "bad_status",
        "upper_status",
        "blank_status",
        "missing_columns",
        "empty_predictions_file",
        "empty_gold",
        "missing_pred_file",
        "missing_gold_file",
        "directory_as_input",
        "missing_out_folder",
        "out_is_a_directory",
    ],
)
def test_bad_input_exits_2_with_a_message_and_writes_no_report(
    tmp_path: Path, case: str
) -> None:
    args, message = reject_case(tmp_path, case)
    result = cli(*args)
    assert result.returncode == 2, result.stderr
    assert message in result.stderr
    assert "Traceback" not in result.stderr
    assert not (tmp_path / "r.json").exists()
    assert not (tmp_path / "nope").exists()


def test_gold_without_required_columns_fails_cleanly(tmp_path: Path) -> None:
    pred = write(tmp_path / "p.csv", PRED_HEADER, [["A", "ok", "x"]])
    gold = write(tmp_path / "g.csv", ["listing_id", "note"], [["A", "n"]])
    result = cli(str(pred), str(gold), "--out", str(tmp_path / "r.json"))
    assert result.returncode == 2, result.stderr
    assert "Traceback" not in result.stderr
    assert not (tmp_path / "r.json").exists()


def test_non_utf8_input_fails_cleanly(tmp_path: Path) -> None:
    pred = tmp_path / "p.csv"
    pred.write_bytes("listing_id,status,category_id\nĖ,ok,x\n".encode("cp1257"))
    gold = gold_file(tmp_path, [("Ė", "x")])
    result = cli(str(pred), str(gold), "--out", str(tmp_path / "r.json"))
    assert result.returncode == 2, result.stderr
    assert "Traceback" not in result.stderr
    assert not (tmp_path / "r.json").exists()


def test_failed_run_keeps_a_pre_existing_report_untouched(tmp_path: Path) -> None:
    pred = write(tmp_path / "p.csv", PRED_HEADER, [["A", "ok", "x"]])
    gold = gold_file(tmp_path, [("A", "x"), ("B", "x")])
    out = tmp_path / "r.json"
    out.write_text("previous", encoding="utf-8")
    assert main([str(pred), str(gold), "--out", str(out)]) == 2
    assert out.read_text(encoding="utf-8") == "previous"
