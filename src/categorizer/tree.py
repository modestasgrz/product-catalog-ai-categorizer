import re
from pathlib import Path

from pydantic import ValidationError

from categorizer.models import CategoryTree

ID_PATTERN = re.compile(r"[a-z0-9-]+")


def load_tree(path: Path) -> CategoryTree:
    try:
        tree = CategoryTree.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as e:
        raise ValueError(f"invalid category tree: {type(e).__name__}") from e
    ids = [c.id for c in tree.categories]
    if len(ids) != len(set(ids)):
        raise ValueError("invalid category tree: duplicate id")
    if "unknown" in ids:
        raise ValueError("invalid category tree: id 'unknown' is reserved")
    if bad := [i for i in ids if not ID_PATTERN.fullmatch(i)]:
        raise ValueError(f"invalid category tree: bad ids {bad}")
    return tree
