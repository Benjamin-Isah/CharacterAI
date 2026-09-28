from engine.relationships.analyzer import validate_analysis_json


def test_malformed_llm_json_falls_back_safely() -> None:
    result = validate_analysis_json("not json at all")
    assert result.confidence == 0
    assert result.relationship_effect == {}


def test_analysis_clamps_values_and_rejects_unknown_dimensions() -> None:
    result = validate_analysis_json(
        '{"confidence": 4, "severity": -1, "relationship_effect": {"trust": 9, "romance": 1}}'
    )
    assert result.confidence == 1
    assert result.severity == 0
    assert result.relationship_effect == {"trust": 0.2}

