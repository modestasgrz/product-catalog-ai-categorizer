from fakes import read_data_csv, tree_ids


def test_ac_23_gold_set() -> None:
    """AC-23: gold.csv = 100 unique listings from listings.csv, 1-2 valid accepted ids, valid source, required coverage."""
    gold = read_data_csv("gold.csv")
    listing_ids = {r["listing_id"] for r in read_data_csv("listings.csv")}
    labels = {r["listing_id"]: r for r in read_data_csv("labels.csv")}
    assert len(gold) == 100
    assert list(gold[0].keys()) == ["listing_id", "accepted_ids", "source", "note"]
    ids = [r["listing_id"] for r in gold]
    assert len(set(ids)) == 100
    assert set(ids) <= listing_ids
    valid = tree_ids() | {"unknown"}
    accepted = [r["accepted_ids"].split("|") for r in gold]
    assert all(1 <= len(a) <= 2 and all(i in valid for i in a) for a in accepted)
    assert all(r["source"] in {"generator", "settled"} for r in gold)
    assert sum(bool(labels[i]["messiness"].strip()) for i in ids) >= 15
    assert sum(len(a) == 2 for a in accepted) >= 5
    assert sum("unknown" in a for a in accepted) >= 3
    injection = {
        lid for lid, r in labels.items() if "injection" in r["messiness"].split("|")
    }
    assert len(injection) == 2
    assert injection <= set(ids)
