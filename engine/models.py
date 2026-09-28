from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


RELATIONSHIP_DIMENSIONS = (
    "familiarity",
    "trust",
    "comfort",
    "respect",
    "warmth",
    "attachment",
    "irritation",
    "resentment",
    "suspicion",
    "conflict",
)


@dataclass(slots=True)
class ParsedMessage:
    raw_text: str
    dialogue: str
    actions: list[str] = field(default_factory=list)
    rejected_controls: list[str] = field(default_factory=list)
    semantic_text: str = ""


@dataclass(slots=True)
class RelationshipState:
    values: dict[str, float]
    interaction_count: int = 0

    @classmethod
    def initial(cls) -> "RelationshipState":
        return cls(
            {
                "familiarity": 0.08,
                "trust": 0.08,
                "comfort": 0.06,
                "respect": 0.12,
                "warmth": 0.04,
                "attachment": 0.01,
                "irritation": 0.0,
                "resentment": 0.0,
                "suspicion": 0.08,
                "conflict": 0.0,
            }
        )


@dataclass(slots=True)
class AnalysisResult:
    interaction_type: str = "ordinary_conversation"
    severity: float = 0.0
    intent: str = "unclear"
    confidence: float = 0.0
    relationship_effect: dict[str, float] = field(default_factory=dict)
    reason: str = "No reliable structured interpretation was available."
    memories: list[dict[str, Any]] = field(default_factory=list)

