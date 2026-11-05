import asyncio
import csv
import io
import time
from pathlib import Path

from anthropic import AsyncAnthropic
from loguru import logger

from categorizer.llm import (
    Verdict,
    build_system_prompt,
    build_user_message,
    classify_listing,
)
from categorizer.models import CategoryTree, RunReport, RunSettings

REQUIRED_COLUMNS = ("title", "description", "location")
NEW_COLUMNS = [
    "status",
    "category_name",
    "confidence",
    "reason",
    "category_id",
    "category_url",
]
ENCODINGS = ("utf-8-sig", "cp1257", "latin1")
CHUNK_SIZE = 50
MAX_CELL_CHARS = 16 * 1024 * 1024
PRICE_PER_MTOK = {
    "input": 2.00,
    "output": 10.00,
    "cache_read": 0.20,
    "cache_write": 2.50,
}


class InputError(ValueError):
    pass


def read_csv_rows(path: Path) -> tuple[list[list[str]], str]:
    raw = path.read_bytes()
    for encoding in ENCODINGS[:-1]:
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        encoding = ENCODINGS[-1]
        text = raw.decode(encoding)
    header_line = next((line for line in text.splitlines() if line.strip()), "")
    delimiter = ";" if header_line.count(";") > header_line.count(",") else ","
    csv.field_size_limit(MAX_CELL_CHARS)
    rows = [
        row
        for row in csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
        if any(cell.strip() for cell in row)
    ]
    return rows, encoding


async def categorize_file(
    input_path: Path,
    tree: CategoryTree,
    out_dir: Path,
    client: AsyncAnthropic,
    settings: RunSettings,
) -> RunReport:
    started = time.monotonic()
    rows, encoding = read_csv_rows(input_path)
    header = rows[0] if rows else []
    positions = {name.strip().lower(): i for i, name in enumerate(header)}
    if missing := [name for name in REQUIRED_COLUMNS if name not in positions]:
        message = f"missing required columns: {', '.join(missing)}"
        logger.error(message)
        raise InputError(message)
    title_at, description_at, location_at = (
        positions[name] for name in REQUIRED_COLUMNS
    )
    listings = [row + [""] * (len(header) - len(row)) for row in rows[1:]][
        : settings.limit
    ]

    categories = {c.id: c for c in tree.categories}
    system = build_system_prompt(tree)
    semaphore = asyncio.Semaphore(settings.concurrency)

    async def classify(row: list[str]) -> Verdict:
        if not row[title_at].strip() and not row[description_at].strip():
            return Verdict()
        async with semaphore:
            return await classify_listing(
                client,
                settings.model,
                system,
                build_user_message(
                    row[title_at], row[description_at], row[location_at]
                ),
                set(categories),
            )

    counts = dict.fromkeys(("ok", "review", "unknown", "error"), 0)
    tokens = dict.fromkeys(("input", "output", "cache_read", "cache_write"), 0)
    await asyncio.to_thread(out_dir.mkdir, parents=True, exist_ok=True)
    stem = input_path.stem
    with (
        (out_dir / f"{stem}_categorized.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as categorized_file,
        (out_dir / f"{stem}_review.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as review_file,
    ):
        categorized, review = csv.writer(categorized_file), csv.writer(review_file)
        categorized.writerow(NEW_COLUMNS + header)
        review.writerow(NEW_COLUMNS + header)
        for chunk_start in range(0, len(listings), CHUNK_SIZE):
            chunk = listings[chunk_start : chunk_start + CHUNK_SIZE]
            verdicts = await asyncio.gather(*(classify(row) for row in chunk))
            for row, verdict in zip(chunk, verdicts, strict=True):
                tokens["input"] += verdict.input_tokens
                tokens["output"] += verdict.output_tokens
                tokens["cache_read"] += verdict.cache_read_input_tokens
                tokens["cache_write"] += verdict.cache_creation_input_tokens
                result = verdict.classification
                if verdict.error is not None:
                    status, category_id, confidence, reason = (
                        "error",
                        "unknown",
                        0.0,
                        verdict.error,
                    )
                elif result is None:
                    status, category_id, confidence, reason = (
                        "unknown",
                        "unknown",
                        0.0,
                        "empty title and description",
                    )
                elif result.category_id == "unknown":
                    status, category_id, confidence, reason = (
                        "unknown",
                        "unknown",
                        result.confidence,
                        result.reason,
                    )
                else:
                    category_id, confidence, reason = (
                        result.category_id,
                        round(result.confidence, 2),
                        result.reason,
                    )
                    status = "ok" if confidence >= settings.threshold else "review"
                category = categories.get(category_id)
                line = [
                    status,
                    category.name if category else "",
                    f"{confidence:.2f}",
                    reason,
                    category_id,
                    category.url if category else "",
                    *row,
                ]
                counts[status] += 1
                categorized.writerow(line)
                if status != "ok":
                    review.writerow(line)
            categorized_file.flush()
            review_file.flush()
            logger.info(f"Processed {chunk_start + len(chunk)}/{len(listings)} rows")

    cost = (
        sum(tokens[kind] * price for kind, price in PRICE_PER_MTOK.items()) / 1_000_000
    )
    report = RunReport(
        input_file=input_path.name,
        rows_total=len(listings),
        status_counts=counts,
        model=settings.model,
        threshold=settings.threshold,
        encoding=encoding,
        input_tokens=tokens["input"],
        output_tokens=tokens["output"],
        cache_read_input_tokens=tokens["cache_read"],
        cache_creation_input_tokens=tokens["cache_write"],
        estimated_cost_usd=round(cost, 4),
        duration_seconds=round(time.monotonic() - started, 2),
    )
    (out_dir / f"{stem}_run_report.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    logger.info(
        f"Done: {counts} | est. cost ${report.estimated_cost_usd:.4f} | {report.duration_seconds}s"
    )
    return report
