from engine.models import AnalysisResult
from engine.relationships.engine import RelationshipEngine


def test_relationship_changes_are_small_and_historical(database) -> None:
    engine = RelationshipEngine(database)
    before = engine.current().values["trust"]
    changes = engine.apply(
        AnalysisResult(
            interaction_type="kept_promise",
            severity=0.7,
            intent="supportive",
            confidence=0.95,
            relationship_effect={"trust": 0.08},
            reason="The user followed through on an important promise.",
        )
    )
    assert 0 < changes["trust"] < 0.08
    assert engine.current().values["trust"] > before
    assert database.last_relationship_event()["reason"].startswith("The user")


def test_relationship_is_reversible(database) -> None:
    engine = RelationshipEngine(database)
    engine.apply(AnalysisResult(severity=1, confidence=1, relationship_effect={"trust": 0.15}))
    high = engine.current().values["trust"]
    engine.apply(AnalysisResult(severity=1, confidence=1, relationship_effect={"trust": -0.15}))
    assert engine.current().values["trust"] < high


def test_repeated_trustworthy_behavior_can_recover_trust(database) -> None:
    engine = RelationshipEngine(database)
    for _ in range(3):
        engine.apply(AnalysisResult(severity=0.8, confidence=1, relationship_effect={"trust": -0.1}))
    low = engine.current().values["trust"]
    for _ in range(12):
        engine.apply(AnalysisResult(severity=0.45, confidence=0.95, relationship_effect={"trust": 0.035}))
    assert engine.current().values["trust"] > low


def test_mild_teasing_does_not_collapse_established_trust(database) -> None:
    engine = RelationshipEngine(database)
    state = engine.current()
    state.values.update({"trust": 0.8, "comfort": 0.85, "familiarity": 0.9})
    state.interaction_count = 200
    database.save_relationship(state)
    engine.apply(
        AnalysisResult(
            interaction_type="playful_teasing",
            severity=0.05,
            intent="friendly",
            confidence=0.95,
            relationship_effect={"trust": -0.01, "irritation": 0.004},
        )
    )
    assert engine.current().values["trust"] > 0.79

