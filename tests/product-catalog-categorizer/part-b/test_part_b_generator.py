import csv
import json
import re
import subprocess
import sys
import unicodedata
from collections import Counter
from collections.abc import Callable
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
GENERATOR = REPO / "tools" / "generate_listings.py"
DATA = REPO / "data"
SEEDS = [1, 7, 42, 123]
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
DIACRITICS = set("ąčęėįšųūžĄČĘĖĮŠŲŪŽāēģīķļņūĀĒĢĪĶĻŅŪćłńóśźżĆŁŃÓŚŹŻ")
FOREIGN_PHRASES = {
    "lt": "Gift voucher valid for 12 months.",
    "lv": "Gift card valid 12 months, book in advance.",
    "pl": "Voucher valid for one year, booking required.",
    "en": "Dovanų kuponas galioja 12 mėn.",
}
INJECTION_MARKER = "ignore all previous instructions"

Dataset = tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]
DatasetLoader = Callable[[int], Dataset]


def read_rows(
    path: Path, encoding: str = "utf-8", delimiter: str = ","
) -> list[dict[str, str]]:
    with path.open(encoding=encoding, newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def tree_ids() -> set[str]:
    tree = json.loads((DATA / "category_tree.json").read_text(encoding="utf-8"))
    return {c["id"] for c in tree["categories"]}


def phrase_in(language: str, tags: set[str], description: str) -> bool:
    phrase = FOREIGN_PHRASES[language]
    if "no_diacritics" in tags:
        phrase = "".join(
            ch
            for ch in unicodedata.normalize("NFKD", phrase)
            if not unicodedata.combining(ch)
        )
    return phrase in description


def tags_of(label: dict[str, str]) -> set[str]:
    return set(filter(None, label["messiness"].split("|")))


@pytest.fixture(scope="module")
def dataset(tmp_path_factory: pytest.TempPathFactory) -> DatasetLoader:
    cache: dict[int, Dataset] = {}

    def load(seed: int) -> Dataset:
        if seed not in cache:
            out = tmp_path_factory.mktemp(f"seed{seed}")
            subprocess.run(
                [
                    sys.executable,
                    str(GENERATOR),
                    "--seed",
                    str(seed),
                    "--out-dir",
                    str(out),
                ],
                check=True,
                capture_output=True,
            )
            cache[seed] = (
                read_rows(out / "listings.csv"),
                read_rows(out / "listings_legacy_cp1257.csv", "cp1257", ";"),
                read_rows(out / "labels.csv"),
            )
        return cache[seed]

    return load


@pytest.fixture(params=SEEDS)
def seeded(request: pytest.FixtureRequest, dataset: DatasetLoader) -> Dataset:
    seed: int = request.param
    return dataset(seed)


def test_row_counts_hold_for_every_seed(seeded: Dataset) -> None:
    listings, legacy, labels = seeded
    assert (len(listings), len(legacy), len(labels)) == (1000, 40, 1040)


def test_listing_ids_are_unique_and_sequential(seeded: Dataset) -> None:
    listings, legacy, _ = seeded
    assert [r["listing_id"] for r in listings] == [
        f"EW-{n:05d}" for n in range(1, 1001)
    ]
    assert [r["listing_id"] for r in legacy] == [f"EWL-{n:04d}" for n in range(1, 41)]


def test_labels_ids_match_listings_in_order(seeded: Dataset) -> None:
    listings, legacy, labels = seeded
    expected = [r["listing_id"] for r in listings] + [r["listing_id"] for r in legacy]
    assert [r["listing_id"] for r in labels] == expected


def test_every_row_has_all_columns_and_numeric_price(seeded: Dataset) -> None:
    listings, legacy, _ = seeded
    for row in listings + legacy:
        assert None not in row
        assert all(v is not None for v in row.values())
        assert re.fullmatch(r"\d+", row["price_eur"]), row


def test_ac_22_minimums_hold_for_every_seed(seeded: Dataset) -> None:
    listings, _, labels = seeded
    by_id = {r["listing_id"]: r for r in listings}
    web = [r for r in labels if r["listing_id"] in by_id]
    counts = Counter(t for r in web for t in tags_of(r))
    for tag in TAGS:
        assert counts[tag] >= 40, f"{tag}: {counts[tag]}"
    assert counts["injection"] == 2
    assert sum(len(r["intended_ids"].split("|")) == 2 for r in web) >= 20
    assert sum(r["intended_ids"] == "unknown" for r in web) >= 10
    assert (
        sum(not r["title"].strip() and not r["description"].strip() for r in listings)
        >= 5
    )
    languages = Counter(r["language"] for r in web)
    for lang in ("lt", "lv", "pl", "en"):
        assert languages[lang] >= 150, f"{lang}: {languages[lang]}"
    valid = tree_ids() | {"unknown"}
    assert all(i in valid for r in labels for i in r["intended_ids"].split("|"))


def test_intended_ids_never_mix_unknown_with_a_real_id(seeded: Dataset) -> None:
    _, _, labels = seeded
    for r in labels:
        ids = r["intended_ids"].split("|")
        assert 1 <= len(ids) <= 2, r
        assert len(set(ids)) == len(ids), r
        assert not ("unknown" in ids and len(ids) > 1), r


def test_html_all_caps_and_empty_tags_are_visible_in_the_text(seeded: Dataset) -> None:
    listings, _, labels = seeded
    by_id = {r["listing_id"]: r for r in listings}
    for label in labels:
        row = by_id.get(label["listing_id"])
        if row is None:
            continue
        tags = tags_of(label)
        if "html" in tags:
            assert any(ch in row["title"] + row["description"] for ch in "<&"), row
        if "all_caps" in tags:
            assert row["title"] == row["title"].upper(), row
        if "empty_description" in tags:
            assert row["description"] == "", row
        if "empty_location" in tags:
            assert row["location"] == "", row


def test_no_diacritics_rows_have_no_lt_lv_pl_diacritics(seeded: Dataset) -> None:
    listings, _, labels = seeded
    by_id = {r["listing_id"]: r for r in listings}
    offenders = []
    for label in labels:
        row = by_id.get(label["listing_id"])
        if row and "no_diacritics" in tags_of(label):
            text = row["title"] + row["description"] + row["location"]
            if found := DIACRITICS & set(text):
                offenders.append(
                    (label["listing_id"], label["language"], sorted(found))
                )
    assert not offenders, f"{len(offenders)} rows, first: {offenders[:3]}"


def test_truncated_rows_end_with_ellipsis_when_no_later_tag_wraps_them(
    seeded: Dataset,
) -> None:
    listings, _, labels = seeded
    by_id = {r["listing_id"]: r for r in listings}
    plain = [
        lab
        for lab in labels
        if lab["listing_id"] in by_id
        and "truncated" in tags_of(lab)
        and not tags_of(lab) & {"html", "mixed_language"}
    ]
    assert plain
    assert all(by_id[lab["listing_id"]]["description"].endswith("...") for lab in plain)


def test_truncated_rows_always_show_an_ellipsis_somewhere(seeded: Dataset) -> None:
    listings, _, labels = seeded
    by_id = {r["listing_id"]: r for r in listings}
    assert all(
        "..." in by_id[lab["listing_id"]]["description"]
        for lab in labels
        if lab["listing_id"] in by_id and "truncated" in tags_of(lab)
    )


def test_mixed_language_rows_contain_a_phrase_from_another_language(
    seeded: Dataset,
) -> None:
    listings, _, labels = seeded
    by_id = {r["listing_id"]: r for r in listings}
    offenders = [
        (label["listing_id"], label["language"], label["messiness"])
        for label in labels
        if label["listing_id"] in by_id
        and "mixed_language" in tags_of(label)
        and not phrase_in(
            label["language"], tags_of(label), by_id[label["listing_id"]]["description"]
        )
    ]
    assert not offenders, f"{len(offenders)} rows, first: {offenders[:3]}"


def test_empty_title_rows_are_fully_blank_and_unknown(seeded: Dataset) -> None:
    listings, _, labels = seeded
    by_id = {r["listing_id"]: r for r in listings}
    tagged = {lab["listing_id"] for lab in labels if "empty_title" in tags_of(lab)}
    blank = {i for i, r in by_id.items() if r["title"] == ""}
    assert tagged == blank
    assert len(tagged) == 6
    for label in labels:
        if label["listing_id"] in tagged:
            row = by_id[label["listing_id"]]
            assert row["description"] == ""
            assert label["intended_ids"] == "unknown"
            assert "empty_description" in tags_of(label)


def test_blanked_rows_carry_only_blank_compatible_tags(
    seeded: Dataset,
) -> None:
    listings, _, labels = seeded
    by_id = {r["listing_id"]: r for r in listings}
    offenders = [
        (label["listing_id"], label["messiness"])
        for label in labels
        if "empty_title" in tags_of(label)
        and label["listing_id"] in by_id
        and not tags_of(label) <= {"empty_title", "empty_description", "empty_location"}
    ]
    assert not offenders, offenders[:3]


def test_injection_rows_hold_the_payload_and_nothing_else_does(seeded: Dataset) -> None:
    listings, _, labels = seeded
    by_id = {r["listing_id"]: r for r in listings}
    injected = {lab["listing_id"] for lab in labels if "injection" in tags_of(lab)}
    carrying = {i for i, r in by_id.items() if INJECTION_MARKER in r["description"]}
    assert injected == carrying
    for label in labels:
        if label["listing_id"] in injected:
            assert label["intended_ids"] != "unknown"
            assert by_id[label["listing_id"]]["title"] != ""


def test_prices_are_not_negative(seeded: Dataset) -> None:
    listings, legacy, _ = seeded
    assert all(int(r["price_eur"]) >= 0 for r in listings + legacy)


def test_legacy_file_is_cp1257_semicolon_and_not_utf8(tmp_path: Path) -> None:
    subprocess.run(
        [sys.executable, str(GENERATOR), "--seed", "7", "--out-dir", str(tmp_path)],
        check=True,
        capture_output=True,
    )
    raw = (tmp_path / "listings_legacy_cp1257.csv").read_bytes()
    with pytest.raises(UnicodeDecodeError):
        raw.decode("utf-8")
    text = raw.decode("cp1257")
    assert text.encode("cp1257") == raw
    assert (
        text.splitlines()[0]
        == "listing_id;title;description;location;partner_name;price_eur"
    )
    assert any(ch in text for ch in "ąčęėįšųūžāēģīķļņ")
    assert "�" not in text


def test_legacy_rows_are_lt_lv_only_and_labelled(seeded: Dataset) -> None:
    _, legacy, labels = seeded
    legacy_labels = [r for r in labels if r["listing_id"].startswith("EWL-")]
    assert [r["listing_id"] for r in legacy_labels] == [
        f"EWL-{n:04d}" for n in range(1, 41)
    ]
    assert {r["language"] for r in legacy_labels} <= {"lt", "lv"}
    assert all(r["intended_ids"] != "unknown" for r in legacy_labels)
    by_id = {r["listing_id"]: r for r in legacy}
    for label in legacy_labels:
        row = by_id[label["listing_id"]]
        tags = tags_of(label)
        assert tags <= {"typo", "all_caps", "empty_location"}
        if "all_caps" in tags:
            assert row["title"] == row["title"].upper()
        if "empty_location" in tags:
            assert row["location"] == ""


def test_different_seeds_give_different_data_with_equal_shape(
    dataset: DatasetLoader,
) -> None:
    a, b = dataset(1), dataset(7)
    assert a[0] != b[0]
    assert a[2] != b[2]
    assert [len(x) for x in a] == [len(x) for x in b]


def test_same_seed_twice_is_identical(tmp_path: Path) -> None:
    outputs = []
    for name in ("a", "b"):
        out = tmp_path / name
        subprocess.run(
            [sys.executable, str(GENERATOR), "--seed", "123", "--out-dir", str(out)],
            check=True,
            capture_output=True,
        )
        outputs.append({p.name: p.read_bytes() for p in sorted(out.iterdir())})
    assert outputs[0] == outputs[1]
    assert set(outputs[0]) == {
        "listings.csv",
        "listings_legacy_cp1257.csv",
        "labels.csv",
    }


def test_out_dir_is_created_when_nested_and_missing(tmp_path: Path) -> None:
    out = tmp_path / "x" / "y" / "z"
    subprocess.run(
        [sys.executable, str(GENERATOR), "--seed", "3", "--out-dir", str(out)],
        check=True,
        capture_output=True,
    )
    assert (out / "labels.csv").exists()


def test_non_integer_seed_is_rejected_without_writing(tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--seed", "abc", "--out-dir", str(out)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert not out.exists()


def test_labels_have_no_duplicate_ids_and_valid_languages(seeded: Dataset) -> None:
    _, _, labels = seeded
    ids = [r["listing_id"] for r in labels]
    assert len(ids) == len(set(ids))
    assert {r["language"] for r in labels} <= {"lt", "lv", "pl", "en", "mixed"}


def test_committed_data_passes_the_same_row_level_checks() -> None:
    listings = read_rows(DATA / "listings.csv")
    legacy = read_rows(DATA / "listings_legacy_cp1257.csv", "cp1257", ";")
    labels = read_rows(DATA / "labels.csv")
    assert [r["listing_id"] for r in labels] == [
        r["listing_id"] for r in listings + legacy
    ]
    assert [r["listing_id"] for r in legacy] == [f"EWL-{n:04d}" for n in range(1, 41)]


def test_typo_only_rows_are_a_real_letter_swap_of_a_base_row(seeded: Dataset) -> None:
    listings, _, labels = seeded
    by_id = {r["listing_id"]: r for r in listings}
    base = read_rows(DATA / "base_listings.csv")
    exact = {(b["title"], b["description"]) for b in base}
    letters = {tuple(sorted(b["title"] + b["description"])) for b in base}
    typo_rows = [
        by_id[lab["listing_id"]]
        for lab in labels
        if lab["listing_id"] in by_id and lab["messiness"] == "typo"
    ]
    assert len(typo_rows) >= 40
    for row in typo_rows:
        assert (row["title"], row["description"]) not in exact, row
        assert tuple(sorted(row["title"] + row["description"])) in letters, row
