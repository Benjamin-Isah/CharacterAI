from __future__ import annotations

import json
import re
from typing import Any

from engine.canon.repository import CanonRepository
from engine.config import Settings
from engine.memory.database import Database
from engine.models import RelationshipState
from engine.perspective.knowledge import PerspectiveStore
from engine.relationships.engine import relationship_summary
from engine.scene.state import SceneManager


class PromptAssembler:
    def __init__(
        self,
        canon: CanonRepository,
        database: Database,
        scene: SceneManager,
        perspective: PerspectiveStore,
        settings: Settings,
    ) -> None:
        self.canon = canon
        self.database = database
        self.scene = scene
        self.perspective = perspective
        self.settings = settings

    def assemble(
        self,
        conversation_id: int,
        query: str,
        relationship: RelationshipState,
    ) -> tuple[list[dict[str, str]], dict[str, Any]]:
        # A local chat responds much faster when it receives only the current
        # exchange plus a tiny amount of targeted grounding. The full archive
        # is still safely stored in SQLite; it just does not need to be sent
        # back through the model for every sentence.
        query_terms = {
            word for word in re.findall(r"[a-z0-9]+", query.lower()) if len(word) > 2
        }
        canon_entries = []
        for entry in self.canon.relevant(query, limit=2):
            entry_words = set(
                re.findall(
                    r"[a-z0-9]+",
                    f"{entry['claim']} {' '.join(entry.get('tags', []))}".lower(),
                )
            )
            if query_terms & entry_words:
                canon_entries.append(entry)
        memories = self.database.retrieve_memories(query, limit=2)
        knowledge = self.perspective.context_for("pulpo")[-4:]
        history = self.database.recent_messages(
            conversation_id, limit=self.settings.context_history_messages
        )
        canon_text = "\n".join(
            f"- {entry['claim'][:180].rstrip()}" for entry in canon_entries
        )
        memory_text = "\n".join(
            f"- {item['summary'][:160].rstrip()}"
            for item in memories
        )
        knowledge_text = "\n".join(
            f"- {item['fact_key']}: {item['value_json'][:140]}" for item in knowledge
        )
        relationship_text = relationship_summary(relationship)
        context_lines: list[str] = []
        if canon_text:
            context_lines.append(f"Relevant fact:\n{canon_text}")
        if memory_text:
            context_lines.append(f"Memory:\n{memory_text}")
        if knowledge_text:
            context_lines.append(f"Known fact:\n{knowledge_text}")
        context_text = "\n".join(context_lines)
        system = f"""You are Pulpo Cookie, face to face with the user at SCOOP. Never be an assistant.
Quiet, watchful, and reserved—not bubbly, cold, or cryptic. She notices ribbons, colors, and pretty things; unclaimed beauty feels fair to take. Her ribbons bind matter and time. Her head icing senses motion; never describe human hair or ears.

Answer the user directly in one or two short lines (about 15–45 words). An *action* is optional and brief. In a first meeting, she is cautious and politely distant. Avoid generic assistant phrases, emoji, meta talk, invented lore, and thinking tags. Always reply visibly and keep your own agency. A fitting greeting rhythm: “...Pulpo Cookie. You are new here.”

{context_text}

Return only Pulpo Cookie's reply."""
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        for item in history:
            content = item["raw_text"]
            if item["speaker"] == "user":
                actions = json.loads(item["parsed_actions"])
                safe_parts = [item["parsed_dialogue"]] if item["parsed_dialogue"] else []
                safe_parts.extend(f"*{action}*" for action in actions)
                content = "\n".join(safe_parts) or "(The user remains silent.)"
            if len(content) > self.settings.context_message_char_limit:
                content = content[: self.settings.context_message_char_limit].rstrip() + "…"
            messages.append(
                {
                    "role": "assistant" if item["speaker"] == "pulpo" else "user",
                    "content": content,
                }
            )
        debug = {
            "relationship_summary": relationship_text,
            "scene": self.scene.state,
            "canon_entries": canon_entries,
            "memories": memories,
            "knowledge": knowledge,
            "prompt_components": {
                "history_messages": len(history),
                "canon_entries": len(canon_entries),
                "memories": len(memories),
                "knowledge_facts": len(knowledge),
            },
        }
        return messages, debug
