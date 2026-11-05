import re

from fakes import DATA


def test_ac_20_category_tree() -> None:
    """AC-20: data/category_tree.json -> Elkwood Experiences, 6 groups, 38-42 categories, unique slug ids, .example URLs."""
    from categorizer.tree import load_tree

    tree = load_tree(DATA / "category_tree.json")
    assert tree.marketplace == "Elkwood Experiences"
    assert len({c.group for c in tree.categories}) == 6
    assert 38 <= len(tree.categories) <= 42
    ids = [c.id for c in tree.categories]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"[a-z0-9-]+", i) for i in ids)
    assert all(c.url.startswith("https://elkwood.example/") for c in tree.categories)
