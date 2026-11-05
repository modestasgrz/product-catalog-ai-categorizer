from collections import Counter

from fakes import read_data_csv, tree_ids

TAGS = [
    "typo",
    "no_diacritics",
    "empty_description",
    "empty_location",
    "mixed_language",
    "html",
    "all_caps",
    "truncated",
]


def test_ac_22_messiness_mix() -> None:
    """AC-22: listings.csv carries the required mix of messy, ambiguous, unknown, injection, empty and per-language rows."""
    listings = {r["listing_id"]: r for r in read_data_csv("listings.csv")}
    labels = [r for r in read_data_csv("labels.csv") if r["listing_id"] in listings]
    assert len(labels) == 1000
    tags = {
        r["listing_id"]: set(filter(None, r["messiness"].split("|"))) for r in labels
    }
    counts = Counter(t for ts in tags.values() for t in ts)
    for tag in TAGS:
        assert counts[tag] >= 40, f"{tag}: {counts[tag]}"
    for lid, ts in tags.items():
        row = listings[lid]
        if "html" in ts:
            assert any(ch in row["title"] + row["description"] for ch in "<&"), lid
        if "all_caps" in ts:
            assert row["title"] == row["title"].upper(), lid
        if "empty_description" in ts:
            assert row["description"] == "", lid
        if "empty_location" in ts:
            assert row["location"] == "", lid
    intended = {r["listing_id"]: r["intended_ids"].split("|") for r in labels}
    assert sum(len(ids) == 2 for ids in intended.values()) >= 20
    assert sum(ids == ["unknown"] for ids in intended.values()) >= 10
    assert counts["injection"] == 2
    assert (
        sum(
            not r["title"].strip() and not r["description"].strip()
            for r in listings.values()
        )
        >= 5
    )
    languages = Counter(r["language"] for r in labels)
    for lang in ("lt", "lv", "pl", "en"):
        assert languages[lang] >= 150, f"{lang}: {languages[lang]}"
    valid = tree_ids() | {"unknown"}
    assert all(i in valid for ids in intended.values() for i in ids)
