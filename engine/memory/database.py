from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from engine.config import PROJECT_ROOT
from engine.models import ParsedMessage, RelationshipState


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    speaker TEXT NOT NULL CHECK (speaker IN ('user', 'pulpo')),
    timestamp TEXT NOT NULL,
    scene_id INTEGER,
    raw_text TEXT NOT NULL,
    parsed_dialogue TEXT NOT NULL,
    parsed_actions TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, id);
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    importance REAL NOT NULL,
    confidence REAL NOT NULL,
    emotional_weight REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    last_recalled_at TEXT,
    tags TEXT NOT NULL DEFAULT '[]',
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS relationship_state (
    subject TEXT PRIMARY KEY,
    values_json TEXT NOT NULL,
    interaction_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS relationship_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    interaction_type TEXT NOT NULL,
    intent TEXT NOT NULL,
    severity REAL NOT NULL,
    confidence REAL NOT NULL,
    changes_json TEXT NOT NULL,
    reason TEXT NOT NULL,
    source_message_id INTEGER
);
CREATE TABLE IF NOT EXISTS scenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_key TEXT NOT NULL,
    value_json TEXT NOT NULL,
    known_by TEXT NOT NULL,
    confidence REAL NOT NULL,
    source TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(fact_key, known_by)
);
"""


class Database:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or PROJECT_ROOT / "data" / "pulpo.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = FULL")
        try:
            yield conn
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            with conn:
                conn.executescript(SCHEMA)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', '2')"
                )
                # v0.1 used a visible default title that shortened her actual name.
                conn.execute(
                    "UPDATE conversations SET title = 'First meeting' WHERE title = 'Pulpo'"
                )

    def get_or_create_conversation(self) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id FROM conversations WHERE active = 1 ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row:
                return int(row["id"])
            now = utc_now()
            with conn:
                cursor = conn.execute(
                    "INSERT INTO conversations(title, created_at, updated_at) VALUES(?, ?, ?)",
                    ("First meeting", now, now),
                )
                return int(cursor.lastrowid)

    def ensure_first_meeting_conversation(self) -> int:
        """Create the one-time first-meeting scene without discarding older chats."""
        with self.connect() as conn:
            marker = conn.execute(
                "SELECT value FROM schema_meta WHERE key = 'first_meeting_conversation_id'"
            ).fetchone()
            if marker:
                marked_conversation = conn.execute(
                    "SELECT id FROM conversations WHERE id = ?", (int(marker["value"]),)
                ).fetchone()
                if marked_conversation:
                    return int(marked_conversation["id"])
                replacement = conn.execute(
                    "SELECT id FROM conversations WHERE active = 1 ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if replacement:
                    return int(replacement["id"])
            active = conn.execute(
                "SELECT id, title FROM conversations WHERE active = 1 ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not active:
            conversation_id = self.get_or_create_conversation()
        elif self.conversation_message_count(int(active["id"])) == 0:
            conversation_id = int(active["id"])
            with self.connect() as conn, conn:
                conn.execute(
                    "UPDATE conversations SET title = 'First meeting' WHERE id = ?",
                    (conversation_id,),
                )
        else:
            with self.connect() as conn, conn:
                if active["title"] in {"Pulpo", "First meeting"}:
                    conn.execute(
                        "UPDATE conversations SET title = 'Earlier conversation' WHERE id = ?",
                        (int(active["id"]),),
                    )
            conversation_id = self.create_conversation("First meeting")
        with self.connect() as conn, conn:
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES(?, ?)",
                ("first_meeting_conversation_id", str(conversation_id)),
            )
        return conversation_id

    def create_conversation(self, title: str = "New scene") -> int:
        now = utc_now()
        with self.connect() as conn, conn:
            conn.execute("UPDATE conversations SET active = 0")
            cursor = conn.execute(
                "INSERT INTO conversations(title, created_at, updated_at, active) VALUES(?, ?, ?, 1)",
                (title, now, now),
            )
            return int(cursor.lastrowid)

    def activate_conversation(self, conversation_id: int) -> None:
        with self.connect() as conn, conn:
            exists = conn.execute(
                "SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if not exists:
                raise ValueError(f"Conversation {conversation_id} does not exist")
            conn.execute("UPDATE conversations SET active = 0")
            conn.execute(
                "UPDATE conversations SET active = 1, updated_at = ? WHERE id = ?",
                (utc_now(), conversation_id),
            )

    def delete_conversation(self, conversation_id: int) -> bool:
        """Permanently remove one saved chat and its transcript.

        Long-term memories are shared across scenes, so they are intentionally
        not erased here. Relationship events that point at the deleted chat's
        messages are removed to avoid leaving dangling history behind.
        """
        with self.connect() as conn, conn:
            exists = conn.execute(
                "SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if not exists:
                return False
            conn.execute(
                """DELETE FROM relationship_events
                WHERE source_message_id IN (
                    SELECT id FROM messages WHERE conversation_id = ?
                )""",
                (conversation_id,),
            )
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        return True

    def list_conversations(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT c.id, c.title, c.created_at, c.updated_at, c.active,
                          COUNT(m.id) AS message_count
                   FROM conversations c
                   LEFT JOIN messages m ON m.conversation_id = c.id
                   GROUP BY c.id
                   ORDER BY c.updated_at DESC, c.id DESC"""
            ).fetchall()
        return [dict(row) for row in rows]

    def total_conversations(self) -> int:
        with self.connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0])

    def conversation_message_count(self, conversation_id: int) -> int:
        with self.connect() as conn:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM messages WHERE conversation_id = ?",
                    (conversation_id,),
                ).fetchone()[0]
            )

    def maybe_title_conversation(self, conversation_id: int, text: str) -> None:
        cleaned = " ".join(text.replace("\n", " ").split()).strip(" .!?*\"'")
        if not cleaned:
            return
        with self.connect() as conn:
            row = conn.execute(
                "SELECT title FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            user_messages = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE conversation_id = ? AND speaker = 'user'",
                (conversation_id,),
            ).fetchone()[0]
        if not row or row["title"] != "New scene" or user_messages > 1:
            return
        words = cleaned.split()
        title = " ".join(words[:6])
        if len(title) > 42:
            title = title[:39].rstrip() + "…"
        elif len(words) > 6:
            title += "…"
        with self.connect() as conn, conn:
            conn.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title, utc_now(), conversation_id),
            )

    def add_message(
        self,
        conversation_id: int,
        speaker: str,
        parsed: ParsedMessage,
        scene_id: int | None,
    ) -> int:
        now = utc_now()
        with self.connect() as conn, conn:
            cursor = conn.execute(
                """INSERT INTO messages(
                    conversation_id, speaker, timestamp, scene_id, raw_text,
                    parsed_dialogue, parsed_actions
                ) VALUES(?, ?, ?, ?, ?, ?, ?)""",
                (
                    conversation_id,
                    speaker,
                    now,
                    scene_id,
                    parsed.raw_text,
                    parsed.dialogue,
                    json.dumps(parsed.actions, ensure_ascii=False),
                ),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id)
            )
            return int(cursor.lastrowid)

    def update_message(self, message_id: int, parsed: ParsedMessage, scene_id: int | None) -> None:
        """Update an app-authored seed message without changing user conversation content."""
        with self.connect() as conn, conn:
            conn.execute(
                """UPDATE messages
                SET scene_id = ?, raw_text = ?, parsed_dialogue = ?, parsed_actions = ?
                WHERE id = ?""",
                (
                    scene_id,
                    parsed.raw_text,
                    parsed.dialogue,
                    json.dumps(parsed.actions, ensure_ascii=False),
                    message_id,
                ),
            )

    def recent_messages(self, conversation_id: int, limit: int = 18) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT id, speaker, timestamp, raw_text, parsed_dialogue, parsed_actions
                FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?""",
                (conversation_id, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def add_memory(
        self,
        memory_type: str,
        summary: str,
        importance: float,
        confidence: float,
        emotional_weight: float = 0.0,
        tags: list[str] | None = None,
    ) -> int:
        with self.connect() as conn, conn:
            cursor = conn.execute(
                """INSERT INTO memories(
                    memory_type, summary, importance, confidence, emotional_weight,
                    created_at, tags
                ) VALUES(?, ?, ?, ?, ?, ?, ?)""",
                (
                    memory_type,
                    summary,
                    max(0.0, min(1.0, importance)),
                    max(0.0, min(1.0, confidence)),
                    max(-1.0, min(1.0, emotional_weight)),
                    utc_now(),
                    json.dumps(tags or [], ensure_ascii=False),
                ),
            )
            return int(cursor.lastrowid)

    def retrieve_memories(self, query: str, limit: int = 6) -> list[dict[str, Any]]:
        query_terms = {word.lower().strip(".,!?*\"'") for word in query.split() if len(word) > 2}
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE active = 1 ORDER BY importance DESC, id DESC LIMIT 100"
            ).fetchall()
        scored: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            item = dict(row)
            haystack = f"{item['summary']} {item['tags']}".lower()
            overlap = sum(1 for term in query_terms if term in haystack)
            score = float(item["importance"]) * 0.55 + float(item["confidence"]) * 0.25
            score += min(overlap, 4) * 0.15
            scored.append((score, item))
        selected = [item for _, item in sorted(scored, key=lambda pair: pair[0], reverse=True)[:limit]]
        if selected:
            ids = [item["id"] for item in selected]
            placeholders = ",".join("?" for _ in ids)
            with self.connect() as conn, conn:
                conn.execute(
                    f"UPDATE memories SET last_recalled_at = ? WHERE id IN ({placeholders})",
                    (utc_now(), *ids),
                )
        return selected

    def get_relationship(self, subject: str = "user") -> RelationshipState:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT values_json, interaction_count FROM relationship_state WHERE subject = ?",
                (subject,),
            ).fetchone()
        if not row:
            state = RelationshipState.initial()
            self.save_relationship(state, subject)
            return state
        return RelationshipState(json.loads(row["values_json"]), int(row["interaction_count"]))

    def save_relationship(self, state: RelationshipState, subject: str = "user") -> None:
        with self.connect() as conn, conn:
            conn.execute(
                """INSERT INTO relationship_state(subject, values_json, interaction_count, updated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(subject) DO UPDATE SET
                    values_json = excluded.values_json,
                    interaction_count = excluded.interaction_count,
                    updated_at = excluded.updated_at""",
                (subject, json.dumps(state.values), state.interaction_count, utc_now()),
            )

    def add_relationship_event(
        self,
        interaction_type: str,
        intent: str,
        severity: float,
        confidence: float,
        changes: dict[str, float],
        reason: str,
        source_message_id: int | None,
    ) -> int:
        with self.connect() as conn, conn:
            cursor = conn.execute(
                """INSERT INTO relationship_events(
                    created_at, interaction_type, intent, severity, confidence,
                    changes_json, reason, source_message_id
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    utc_now(), interaction_type, intent, severity, confidence,
                    json.dumps(changes), reason, source_message_id,
                ),
            )
            return int(cursor.lastrowid)

    def last_relationship_event(self) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM relationship_events ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def get_active_scene(self, default_state: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute("SELECT id, state_json FROM scenes WHERE active = 1 ORDER BY id DESC LIMIT 1").fetchone()
            if row:
                return int(row["id"]), json.loads(row["state_json"])
        now = utc_now()
        with self.connect() as conn, conn:
            cursor = conn.execute(
                "INSERT INTO scenes(state_json, created_at, updated_at) VALUES(?, ?, ?)",
                (json.dumps(default_state), now, now),
            )
            return int(cursor.lastrowid), default_state

    def save_scene(self, scene_id: int, state: dict[str, Any]) -> None:
        with self.connect() as conn, conn:
            conn.execute(
                "UPDATE scenes SET state_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(state), utc_now(), scene_id),
            )

    def upsert_knowledge(
        self, fact_key: str, value: Any, known_by: str, confidence: float, source: str
    ) -> None:
        with self.connect() as conn, conn:
            conn.execute(
                """INSERT INTO knowledge(fact_key, value_json, known_by, confidence, source, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(fact_key, known_by) DO UPDATE SET
                    value_json = excluded.value_json,
                    confidence = excluded.confidence,
                    source = excluded.source,
                    updated_at = excluded.updated_at""",
                (fact_key, json.dumps(value), known_by, confidence, source, utc_now()),
            )

    def knowledge_for(self, knower: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM knowledge WHERE known_by IN (?, 'everyone') ORDER BY id", (knower,)
            ).fetchall()
        return [dict(row) for row in rows]

    def backup(self, destination: Path | None = None) -> Path:
        backup_dir = PROJECT_ROOT / "data" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        target = destination or backup_dir / f"pulpo-{datetime.now():%Y%m%d-%H%M%S}.db"
        with self.connect() as source, sqlite3.connect(target) as dest:
            source.backup(dest)
        return target

    def export_json(self, destination: Path | None = None) -> Path:
        export_dir = PROJECT_ROOT / "data" / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        target = destination or export_dir / f"pulpo-export-{datetime.now():%Y%m%d-%H%M%S}.json"
        tables = ("conversations", "messages", "memories", "relationship_state", "relationship_events", "scenes", "knowledge")
        payload: dict[str, Any] = {"schema_version": 2, "exported_at": utc_now()}
        with self.connect() as conn:
            for table in tables:
                payload[table] = [dict(row) for row in conn.execute(f"SELECT * FROM {table}").fetchall()]
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return target
