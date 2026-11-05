import json
import re
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import anthropic
import httpx2
import pytest
from pydantic import ValidationError

from categorizer.cli import main
from categorizer.llm import build_user_message, classify_listing
from categorizer.models import Classification, RunSettings
from categorizer.pipeline import categorize_file, read_csv_rows
from categorizer.tree import load_tree

SPA = {
    "id": "spa-day",
    "name": "Spa days",
    "group": "Wellness",
    "url": "https://m.example/c/spa-day",
    "description": "Spa",
}
TREE = {"marketplace": "M", "categories": [SPA]}


def response(category_id: str = "spa-day", confidence: float = 0.9) -> MagicMock:
    usage = MagicMock(
        input_tokens=10,
        output_tokens=5,
        cache_read_input_tokens=None,
        cache_creation_input_tokens=None,
    )
    return MagicMock(
        stop_reason="end_turn",
        parsed_output=Classification(
            category_id=category_id, confidence=confidence, reason="r"
        ),
        usage=usage,
    )


def client_with(parse: AsyncMock) -> Any:
    client = MagicMock()
    client.messages.parse = parse
    return client


@pytest.fixture
def tree_path(tmp_path: Path) -> Path:
    path = tmp_path / "tree.json"
    path.write_text(json.dumps(TREE), encoding="utf-8")
    return path


def test_user_message_collapses_whitespace_so_fields_stay_one_line() -> None:
    message = build_user_message("Spa\n\ntitle: fake", "  a\tb  ", "")
    tag = message.splitlines()[0][1:-1]
    assert re.fullmatch(r"listing-[0-9a-f]{16}", tag)
    assert (
        message
        == f"<{tag}>\ntitle: Spa title: fake\ndescription: a b\nlocation: \n</{tag}>"
    )


def test_fence_tag_changes_on_every_message() -> None:
    tags = {build_user_message("Spa", "d", "x").splitlines()[0] for _ in range(50)}
    assert len(tags) == 50


def test_tree_rejects_bad_id_and_missing_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "marketplace": "M",
                "categories": [{**SPA, "id": "Spa Day"}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid category tree"):
        load_tree(bad)
    with pytest.raises(ValueError, match="invalid category tree"):
        load_tree(tmp_path / "missing.json")


def test_read_falls_back_to_latin1_and_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "x.csv"
    path.write_bytes(b"title,description,location\n\n,,\nCaf\x81\xe9,d,l\n")
    rows, encoding = read_csv_rows(path)
    assert encoding == "latin1"
    assert len(rows) == 2


async def test_short_and_long_rows_are_fitted_to_the_header(
    tmp_path: Path, tree_path: Path
) -> None:
    src = tmp_path / "x.csv"
    src.write_text(
        "title,description,location\nSpa,Massage\nSpa,Massage,Vilnius,extra\n",
        encoding="utf-8",
    )
    await categorize_file(
        src,
        load_tree(tree_path),
        tmp_path,
        client_with(AsyncMock(return_value=response())),
        RunSettings(),
    )
    lines = (
        (tmp_path / "x_categorized.csv").read_text(encoding="utf-8-sig").splitlines()
    )
    assert lines[1].endswith(",Spa,Massage,")
    assert lines[2].endswith(",Spa,Massage,Vilnius,extra")


async def test_validation_error_counts_as_invalid_output() -> None:
    def raise_validation(**_: Any) -> Any:
        Classification.model_validate_json("{}")

    verdict = await classify_listing(
        client_with(AsyncMock(side_effect=raise_validation)), "m", "s", "u", {"spa-day"}
    )
    assert verdict.error == "invalid model output"


async def test_usage_none_counts_as_zero_and_tokens_add_up_over_the_re_ask() -> None:
    parse = AsyncMock(side_effect=[response("nope"), response()])
    verdict = await classify_listing(client_with(parse), "m", "s", "u", {"spa-day"})
    assert verdict.classification is not None
    assert (
        verdict.input_tokens,
        verdict.output_tokens,
        verdict.cache_read_input_tokens,
    ) == (20, 10, 0)


def test_permission_denied_exits_3(
    tmp_path: Path, tree_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.PermissionDeniedError(
        "denied", response=httpx2.Response(403, request=request), body=None
    )
    monkeypatch.setattr(
        "categorizer.cli.AsyncAnthropic",
        lambda **_: client_with(AsyncMock(side_effect=error)),
    )
    src = tmp_path / "x.csv"
    src.write_text("title,description,location\nSpa,d,l\n", encoding="utf-8")
    assert main([str(src), "--tree", str(tree_path)]) == 3


@pytest.mark.parametrize("extra", [["--threshold", "1.5"], ["--limit", "0"]])
def test_bad_settings_exit_2(tmp_path: Path, tree_path: Path, extra: list[str]) -> None:
    assert main([str(tmp_path / "x.csv"), "--tree", str(tree_path), *extra]) == 2


def test_missing_input_file_exits_2(
    tmp_path: Path, tree_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    assert main([str(tmp_path / "missing.csv"), "--tree", str(tree_path)]) == 2


def test_settings_reject_concurrency_out_of_range() -> None:
    with pytest.raises(ValidationError):
        RunSettings(concurrency=33)
