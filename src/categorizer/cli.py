import argparse
import asyncio
import os
from pathlib import Path

from anthropic import AsyncAnthropic, AuthenticationError, PermissionDeniedError
from loguru import logger
from pydantic import ValidationError

from categorizer.models import RunSettings
from categorizer.pipeline import InputError, categorize_file
from categorizer.tree import load_tree


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="categorize",
        description="Categorize a product listing CSV onto a marketplace category tree with Claude.",
    )
    parser.add_argument(
        "input",
        type=Path,
        help="listing CSV with title, description and location columns",
    )
    parser.add_argument(
        "--tree",
        type=Path,
        default=Path("data/category_tree.json"),
        help="category tree JSON",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="output folder (default: the input's folder)",
    )
    parser.add_argument(
        "--concurrency", type=int, default=8, help="parallel model calls, 1-32"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.70,
        help="confidence below this goes to review",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="classify only the first N rows"
    )
    parser.add_argument("--model", default="claude-sonnet-5-5")
    args = parser.parse_args(argv)

    try:
        settings = RunSettings(
            model=args.model,
            concurrency=args.concurrency,
            threshold=args.threshold,
            limit=args.limit,
        )
    except ValidationError as e:
        logger.error(
            f"invalid settings: {', '.join(str(err['loc'][0]) for err in e.errors())}"
        )
        return 2
    if not os.environ.get("ANTHROPIC_API_KEY"):
        logger.error("ANTHROPIC_API_KEY is not set")
        return 2
    try:
        tree = load_tree(args.tree)
    except ValueError as e:
        logger.error(str(e))
        return 2

    client = AsyncAnthropic(max_retries=6, timeout=60.0)
    try:
        asyncio.run(
            categorize_file(
                args.input, tree, args.out_dir or args.input.parent, client, settings
            )
        )
    except InputError as e:
        logger.error(str(e))
        return 2
    except OSError as e:
        logger.error(f"cannot read input file: {type(e).__name__}")
        return 2
    except (AuthenticationError, PermissionDeniedError):
        logger.error("Anthropic API key rejected")
        return 3
    return 0
