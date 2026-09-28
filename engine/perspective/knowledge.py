from __future__ import annotations

from typing import Any

from engine.memory.database import Database


class PerspectiveStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    def record_fact(
        self,
        key: str,
        value: Any,
        observers: set[str],
        source: str = "scene",
        confidence: float = 1.0,
    ) -> None:
        self.database.upsert_knowledge(key, value, "world", confidence, source)
        for observer in observers:
            self.database.upsert_knowledge(key, value, observer, confidence, source)

    def set_object_location(
        self, object_name: str, location: str, present_participants: set[str]
    ) -> None:
        self.record_fact(
            f"object_location:{object_name}",
            location,
            observers=present_participants,
            source="observed scene event",
        )

    def known_value(self, key: str, knower: str) -> Any | None:
        entries = self.database.knowledge_for(knower)
        for entry in reversed(entries):
            if entry["fact_key"] == key:
                import json

                return json.loads(entry["value_json"])
        return None

    def context_for(self, knower: str = "pulpo") -> list[dict]:
        return self.database.knowledge_for(knower)

