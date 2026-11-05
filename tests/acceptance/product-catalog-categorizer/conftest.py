"""Fixtures for the product-catalog-categorizer acceptance tests; helpers and fakes are in fakes.py (spec DEC-16)."""

import json
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fakes import TREE_FIXTURE
from loguru import logger


@pytest.fixture
def tree_file(tmp_path: Path) -> Path:
    path = tmp_path / "tree.json"
    path.write_text(json.dumps(TREE_FIXTURE), encoding="utf-8")
    return path


@pytest.fixture
def logs() -> Iterator[Callable[[], str]]:
    lines: list[str] = []
    sink = logger.add(
        lambda message: lines.append(str(message)),
        level=0,
        format="{message} | {extra} | {exception}",
        backtrace=True,
        diagnose=True,
    )
    yield lambda: "\n".join(lines)
    logger.remove(sink)


@pytest.fixture
def api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
