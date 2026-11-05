"""Shared fakes and helpers for the product-catalog-categorizer acceptance tests (spec DEC-05, DEC-16). No network, no real key."""

import asyncio
import csv
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import anthropic
import httpx2
import pytest
from pydantic import BaseModel

CANARY = "SECRET_CANARY_7f3a9c"
REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "data"
NEW_COLUMNS = [
    "status",
    "category_name",
    "confidence",
    "reason",
    "category_id",
    "category_url",
]

TREE_FIXTURE = {
    "marketplace": "Test Market",
    "categories": [
        {
            "id": "balloon",
            "name": "Balloon flights",
            "group": "Adventure",
            "url": "https://test.example/c/balloon",
            "description": "Hot-air balloon rides",
        },
        {
            "id": "spa-day",
            "name": "Spa days",
            "group": "Wellness",
            "url": "https://test.example/c/spa-day",
            "description": "Spa and wellness days",
        },
        {
            "id": "wine-tasting",
            "name": "Wine tastings",
            "group": "Food & Drink",
            "url": "https://test.example/c/wine-tasting",
            "description": "Guided wine tastings",
        },
    ],
}


class FakeUsage(BaseModel):
    input_tokens: int = 100
    output_tokens: int = 50
    cache_read_input_tokens: int | None = 1000
    cache_creation_input_tokens: int | None = 0


class FakeResponse(BaseModel):
    parsed_output: Any = None
    stop_reason: str = "end_turn"
    usage: FakeUsage = FakeUsage()


Responder = Callable[[dict[str, Any]], FakeResponse]


class FakeMessages:
    def __init__(self, responder: Responder) -> None:
        self.responder = responder
        self.calls: list[dict[str, Any]] = []
        self.in_flight = 0
        self.max_in_flight = 0

    async def parse(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0.005)
            return self.responder(kwargs)
        finally:
            self.in_flight -= 1


class FakeClient:
    def __init__(self, responder: Responder) -> None:
        self.messages = FakeMessages(responder)


def user_text(call: dict[str, Any]) -> str:
    content = call["messages"][0]["content"]
    return (
        content
        if isinstance(content, str)
        else "".join(block["text"] for block in content)
    )


def system_text(call: dict[str, Any]) -> str:
    return "".join(block["text"] for block in call["system"])


def title_of(call: dict[str, Any]) -> str:
    match = re.search(r"^title: (.*)$", user_text(call), re.MULTILINE)
    assert match, "user message has no 'title:' line"
    return match.group(1)


def answer(
    category_id: str, confidence: float = 0.9, reason: str = "Fits best.", **kwargs: Any
) -> FakeResponse:
    from categorizer.models import Classification

    return FakeResponse(
        parsed_output=Classification(
            category_id=category_id, confidence=confidence, reason=reason
        ),
        **kwargs,
    )


def status_error(
    cls: type[anthropic.APIStatusError], status: int, body_text: str = CANARY
) -> anthropic.APIStatusError:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls(
        f"Error code: {status} - {body_text}",
        response=httpx2.Response(status, request=request),
        body={"error": {"message": body_text}},
    )


def connection_error() -> anthropic.APIConnectionError:
    return anthropic.APIConnectionError(
        request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    )


def write_csv(
    path: Path,
    header: list[str],
    rows: list[list[str]],
    encoding: str = "utf-8",
    delimiter: str = ",",
) -> Path:
    with path.open("w", encoding=encoding, newline="") as f:
        writer = csv.writer(f, delimiter=delimiter)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def listing_rows(n: int) -> list[list[str]]:
    return [
        [f"L{i:03d}", f"Listing {i}", f"Description {i}", "Vilnius", "50"]
        for i in range(1, n + 1)
    ]


LISTING_HEADER = ["listing_id", "title", "description", "location", "price_eur"]


def patch_client(monkeypatch: pytest.MonkeyPatch, client: FakeClient) -> None:
    monkeypatch.setattr("categorizer.cli.AsyncAnthropic", lambda **_kwargs: client)


async def run_file(
    path: Path, tree_file: Path, out_dir: Path, client: FakeClient, **settings: Any
) -> Any:
    from categorizer.models import RunSettings
    from categorizer.pipeline import categorize_file
    from categorizer.tree import load_tree

    return await categorize_file(
        path, load_tree(tree_file), out_dir, client, RunSettings(**settings)
    )


def outputs(out_dir: Path, stem: str) -> tuple[Path, Path, Path]:
    return (
        out_dir / f"{stem}_categorized.csv",
        out_dir / f"{stem}_review.csv",
        out_dir / f"{stem}_run_report.json",
    )


def read_data_csv(name: str, encoding: str = "utf-8") -> list[dict[str, str]]:
    path = DATA / name
    assert path.exists(), f"missing {path}"
    with path.open(encoding=encoding, newline="") as f:
        return list(csv.DictReader(f))


def tree_ids() -> set[str]:
    tree = json.loads((DATA / "category_tree.json").read_text(encoding="utf-8"))
    return {c["id"] for c in tree["categories"]}
