from __future__ import annotations

from engine.memory.database import Database
from engine.models import AnalysisResult, RELATIONSHIP_DIMENSIONS, RelationshipState


def relationship_summary(state: RelationshipState) -> str:
    v = state.values
    parts: list[str] = []
    if v["familiarity"] < 0.2:
        parts.append("Pulpo Cookie is still getting used to the user.")
    elif v["comfort"] > 0.68 and v["trust"] > 0.62:
        parts.append("Pulpo Cookie is very comfortable with the user and generally trusts them.")
    elif v["trust"] > 0.4:
        parts.append("Pulpo Cookie has a measured but real trust in the user.")
    else:
        parts.append("Pulpo Cookie remains reserved and cautious around the user.")
    if v["warmth"] > 0.55:
        parts.append("Her warmth is more likely to show through small actions than long explanations.")
    if v["irritation"] > 0.25:
        parts.append("She is currently irritated, though that does not erase the wider history.")
    if v["suspicion"] > 0.35:
        parts.append("She is watching the user's intentions carefully.")
    if v["conflict"] > 0.45:
        parts.append("There is unresolved conflict between them.")
    return " ".join(parts)


class RelationshipEngine:
    def __init__(self, database: Database) -> None:
        self.database = database

    def current(self) -> RelationshipState:
        return self.database.get_relationship()

    def apply(self, analysis: AnalysisResult, source_message_id: int | None = None) -> dict[str, float]:
        state = self.current()
        inertia = max(0.25, 1.0 / (1.0 + state.interaction_count / 80.0))
        significance = 0.35 + 0.65 * max(0.0, min(1.0, analysis.severity))
        applied: dict[str, float] = {}
        for dimension in RELATIONSHIP_DIMENSIONS:
            proposed = max(-0.2, min(0.2, float(analysis.relationship_effect.get(dimension, 0.0))))
            delta = proposed * inertia * significance * max(0.2, analysis.confidence)
            old = float(state.values.get(dimension, 0.0))
            new = max(0.0, min(1.0, old + delta))
            state.values[dimension] = new
            if abs(new - old) >= 0.00005:
                applied[dimension] = round(new - old, 5)
        state.interaction_count += 1
        self.database.save_relationship(state)
        self.database.add_relationship_event(
            analysis.interaction_type,
            analysis.intent,
            analysis.severity,
            analysis.confidence,
            applied,
            analysis.reason,
            source_message_id,
        )
        return applied
