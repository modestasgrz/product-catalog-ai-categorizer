"""ADAPT: wire the kit's security tests (test_security.py) to this app. Owner-only, locked like tests/acceptance/.

Fill every function and constant marked ADAPT. A check that genuinely doesn't apply goes in NOT_APPLICABLE with
the reason; it then shows as skipped with that reason. Never use NOT_APPLICABLE to silence a failing check; a real hole the owner accepts
for now goes in KNOWN_OPEN (shows as xfail with the reason).
Check names: pii_logs, prompt_injection, model_output, step_skip, xff_spoof, cors, provider_error, body_cap, image_lock.
`make security` fails when a test listed in tests/security/EXPECTED_TESTS isn't collected by the full test run.
After adapting: uv run pytest tests/security --collect-only -q | grep '::' > tests/security/EXPECTED_TESTS
"""

import asyncio
import json
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import anthropic
import httpx2
import pytest
from anthropic import AsyncAnthropic
from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.testclient import TestClient

from categorizer.models import Classification, RunSettings
from categorizer.pipeline import categorize_file
from categorizer.tree import load_tree

if TYPE_CHECKING:
    from kit_security import FakeLLM

REPO = Path(__file__).resolve().parents[2]

NOT_APPLICABLE: dict[str, str] = {
    "step_skip": "CLI batch tool: one command, no multi-step workflow and no server-held state",
    "xff_spoof": "CLI batch tool: no HTTP endpoint, nothing rate-limited per client",
    "cors": "CLI batch tool: no HTTP endpoint, no browser caller",
    "body_cap": "CLI batch tool: no HTTP body; each listing field is cut to 4,000 chars before the prompt (spec AC-14)",
    "image_lock": "no deploy image: runs locally with uv from the lockfile",
    "provider_error": "CLI batch tool: a provider error never fails the run or reaches an HTTP client; it becomes row status=error with error class + status code only (spec AC-07)",
}
# A real hole the owner accepts for now (shows as xfail with the reason, listed in the PR). Fix it, then remove the entry.
KNOWN_OPEN: dict[str, str] = {}

RATE_LIMIT = 5  # n/a: no HTTP endpoint
CORS_PATH = "/n-a"  # n/a: no HTTP endpoint
ALLOWED_ORIGIN = "https://n-a.example"  # n/a: no HTTP endpoint
BODY_CAP_PATH = "/n-a"  # n/a: no HTTP endpoint
REQUEST_ID_HEADER = "x-request-id"
USER_INPUT_TAG = "listing"
IMAGE_FILES: list[Path] = []

TREE = {
    "marketplace": "Security Test Market",
    "categories": [
        {
            "id": "spa-day",
            "name": "Spa days",
            "group": "Wellness",
            "url": "https://security.example/c/spa-day",
            "description": "Spa and wellness days",
        }
    ],
}


class FakeUsage(BaseModel):
    input_tokens: int = 10
    output_tokens: int = 5
    cache_read_input_tokens: int | None = 0
    cache_creation_input_tokens: int | None = 0


class FakeResponse(BaseModel):
    parsed_output: Any = None
    stop_reason: str = "end_turn"
    usage: FakeUsage = FakeUsage()


class FakeMessages:
    def __init__(self, llm: "FakeLLM") -> None:
        self.llm = llm

    async def parse(self, **kwargs: Any) -> FakeResponse:
        system = "".join(block["text"] for block in kwargs["system"])
        return FakeResponse(
            parsed_output=self.llm.respond(system, kwargs["messages"][0]["content"])
        )


class FakeClient:
    def __init__(self, llm: "FakeLLM") -> None:
        self.messages = FakeMessages(llm)


class RunResult(BaseModel):
    text: str
    status_code: int = 200
    headers: dict[str, str] = {}


FAKES: dict[str, Any] = {}


def app() -> Any:
    """CLI tool, no web app: an empty ASGI app keeps the kit's `http` fixture working; the flow runs in send_visitor_text."""
    return Starlette()


def install_fakes(monkeypatch: pytest.MonkeyPatch, llm: "FakeLLM") -> None:
    """The pipeline takes its client as an argument; send_visitor_text hands it a fake that routes every call to llm.respond."""
    FAKES["llm"] = llm


def good_reply() -> Any:
    return Classification(
        category_id="spa-day", confidence=0.9, reason="Spa day listing."
    )


def invalid_reply(canary: str) -> Any:
    """An id that is not in the tree (the schema can't express the tree's ids), with canary in every field."""
    return Classification(category_id=canary, confidence=0.9, reason=canary)


def provider_error(canary: str) -> Exception:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.InternalServerError(
        f"provider 500: {canary}",
        response=httpx2.Response(500, request=request),
        body={"error": {"message": canary}},
    )


def send_visitor_text(http: TestClient, text: str, email: str) -> Any:
    """Runs the CLI pipeline on a one-row CSV with text in title, description and location (+ email), and returns every output file as text."""
    work = Path(tempfile.mkdtemp(prefix="security-adapter-"))
    tree_path = work / "tree.json"
    tree_path.write_text(json.dumps(TREE), encoding="utf-8")
    source = work / "listings.csv"
    source.write_text(
        "title,description,location,contact\n"
        + ",".join(json.dumps(v) for v in (text, text, text, email))
        + "\n",
        encoding="utf-8",
    )
    asyncio.run(
        categorize_file(
            source,
            load_tree(tree_path),
            work / "out",
            cast(AsyncAnthropic, FakeClient(FAKES["llm"])),
            RunSettings(),
        )
    )
    return RunResult(
        text="\n".join(
            p.read_text(encoding="utf-8-sig") for p in sorted((work / "out").iterdir())
        )
    )


def skip_step(http: TestClient) -> Any:
    """n/a: no multi-step workflow."""
    raise NotImplementedError("n/a: step_skip")


def writes() -> list[Any]:
    """n/a: the CLI writes only local files of the user's own run."""
    return []


def call_rate_limited(http: TestClient, headers: dict[str, str]) -> Any:
    """n/a: no HTTP endpoint."""
    raise NotImplementedError("n/a: xff_spoof")


BREAK_DEPENDENCY: dict[str, Callable[[pytest.MonkeyPatch], None]] = {}
"""No outside service besides the model; the model failure path is the kit's built-in `model_error` case."""
