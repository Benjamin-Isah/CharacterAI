from __future__ import annotations

from engine.memory.database import Database


class MemoryRetriever:
    def __init__(self, database: Database) -> None:
        self.database = database

    def relevant(self, query: str, limit: int = 6) -> list[dict]:
        return self.database.retrieve_memories(query, limit)

