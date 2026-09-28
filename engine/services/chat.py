from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from typing import Any

from engine.config import Settings
from engine.llm.client import LlamaClient
from engine.memory.database import Database
from engine.models import AnalysisResult
from engine.parsing.message_parser import parse_message
from engine.parsing.output_filter import sanitize_complete_response
from engine.prompts.assembler import PromptAssembler
from engine.relationships.analyzer import PostTurnAnalyzer
from engine.relationships.engine import RelationshipEngine
from engine.scene.state import SceneManager


LOGGER = logging.getLogger(__name__)


EMPTY_REPLY_FALLBACK = (
    "*Her head icing tilts toward you; a ribbon settles against the table.*\n\n"
    "...I'm here. Say it again."
)


class ChatService:
    def __init__(
        self,
        settings: Settings,
        database: Database,
        client: LlamaClient,
        assembler: PromptAssembler,
        scene: SceneManager,
        relationships: RelationshipEngine,
        conversation_id: int | None = None,
    ) -> None:
        self.settings = settings
        self.database = database
        self.client = client
        self.assembler = assembler
        self.scene = scene
        self.relationships = relationships
        self.analyzer = PostTurnAnalyzer(client, settings.relationship_analysis_max_tokens)
        self.conversation_id = conversation_id or database.get_or_create_conversation()
        self.last_debug: dict[str, Any] = {}

    def generate(self, user_text: str) -> Iterator[str]:
        parsed_user = parse_message(user_text)
        self.scene.observe_user_message(parsed_user)
        user_message_id = self.database.add_message(
            self.conversation_id, "user", parsed_user, self.scene.scene_id
        )
        self.database.maybe_title_conversation(
            self.conversation_id,
            parsed_user.dialogue or " ".join(parsed_user.actions),
        )
        relationship = self.relationships.current()
        messages, debug = self.assembler.assemble(
            self.conversation_id, parsed_user.semantic_text, relationship
        )
        chunks: list[str] = []
        for chunk in self.client.stream_chat(messages):
            chunks.append(chunk)
            yield chunk
        visible = sanitize_complete_response("".join(chunks))
        if not visible:
            # Some local models can exhaust their output budget inside a
            # hidden-thinking block. Never leave the user facing an empty
            # bubble; a brief in-character acknowledgement is better than
            # making them repeat themselves without explanation.
            LOGGER.warning("Model returned no visible reply; using Pulpo fallback.")
            visible = EMPTY_REPLY_FALLBACK
        parsed_pulpo = parse_message(visible)
        self.database.add_message(
            self.conversation_id, "pulpo", parsed_pulpo, self.scene.scene_id
        )
        self.scene.observe_pulpo_message(parsed_pulpo)
        analysis = AnalysisResult(reason="Post-turn analysis is disabled in settings.")
        changes: dict[str, float] = {}
        if self.settings.relationship_analysis_enabled:
            try:
                analysis = self.analyzer.analyze(
                    parsed_user.semantic_text, visible, relationship
                )
                changes = self.relationships.apply(analysis, user_message_id)
                for memory in analysis.memories:
                    self.database.add_memory(
                        memory["type"],
                        memory["content"],
                        memory["importance"],
                        memory["confidence"],
                        memory["emotional_weight"],
                        memory["tags"],
                    )
            except Exception as exc:  # generation remains usable when analysis fails
                LOGGER.exception("Post-turn analysis failed: %s", exc)
                analysis = AnalysisResult(reason=f"Structured analysis failed: {type(exc).__name__}")
        debug["last_analysis"] = {
            "interaction_type": analysis.interaction_type,
            "intent": analysis.intent,
            "severity": analysis.severity,
            "confidence": analysis.confidence,
            "changes": changes,
            "reason": analysis.reason,
            "memories_created": len(analysis.memories),
        }
        debug["relationship_values"] = self.relationships.current().values
        debug["rejected_user_controls"] = parsed_user.rejected_controls
        self.last_debug = debug
