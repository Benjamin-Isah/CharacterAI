from engine.canon.repository import CanonRepository, VALID_CLASSIFICATIONS


def test_canon_loads_with_valid_classifications() -> None:
    canon = CanonRepository()
    canon.load()
    assert canon.entries
    assert all(item["classification"] in VALID_CLASSIFICATIONS for item in canon.entries)
    assert canon.stats()["DIRECT_CANON_FACT"] > 10
    assert any(item["classification"] == "UNKNOWN" for item in canon.entries)


def test_canon_retrieval_prefers_relevant_entries() -> None:
    canon = CanonRepository()
    canon.load()
    results = canon.relevant("ribbon color")
    assert any("ribbon" in item["claim"].lower() for item in results)

