import re
from pathlib import Path

from loguru import logger
from pydantic import ValidationError

from categorizer.models import CategoryTree

ID_PATTERN = re.compile(r"[a-z0-9-]+")


def load_tree(path: Path) -> CategoryTree:
    try:
        tree = CategoryTree.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as e:
        problem = type(e).__name__
        logger.error(f"invalid category tree: {problem}")
        raise ValueError(f"invalid category tree: {problem}") from e
    ids = [c.id for c in tree.categories]
    problem = ""
    if len(ids) != len(set(ids)):
        problem = "duplicate id"
    elif "unknown" in ids:
        problem = "id 'unknown' is reserved"
    elif bad := [i for i in ids if not ID_PATTERN.fullmatch(i)]:
        problem = f"ids must match [a-z0-9-]+: {bad}"
    if problem:
        logger.error(f"invalid category tree: {problem}")
        raise ValueError(f"invalid category tree: {problem}")
    return tree
