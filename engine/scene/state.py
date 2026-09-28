from __future__ import annotations

from copy import deepcopy
from typing import Any

from engine.memory.database import Database
from engine.models import ParsedMessage


DEFAULT_SCENE: dict[str, Any] = {
    "schema_version": 1,
    "location": "a quiet SCOOP observation room",
    "time_context": "late afternoon",
    "participants": {
        "user": {"present": True, "location_detail": "nearby"},
        "pulpo": {"present": True, "location_detail": "nearby"},
    },
    "relevant_objects": {},
    "current_activity": "first meeting",
    "recent_actions": [],
}


class SceneManager:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.scene_id, self.state = database.get_active_scene(deepcopy(DEFAULT_SCENE))
        if (
            self.state.get("location") == "Pulpo's quiet sitting room"
            and self.state.get("current_activity") == "conversation"
        ):
            self.state.update(
                {
                    "location": "a quiet SCOOP observation room",
                    "time_context": "late afternoon",
                    "current_activity": "first meeting",
                    "recent_actions": [],
                }
            )
            self.database.save_scene(self.scene_id, self.state)

    def observe_user_message(self, parsed: ParsedMessage) -> None:
        if not parsed.actions:
            return
        recent = list(self.state.get("recent_actions", []))
        recent.extend({"actor": "user", "action": action} for action in parsed.actions)
        self.state["recent_actions"] = recent[-8:]
        self.state["current_activity"] = "conversation with physical interaction"
        self.database.save_scene(self.scene_id, self.state)

    def observe_pulpo_message(self, parsed: ParsedMessage) -> None:
        if parsed.actions:
            recent = list(self.state.get("recent_actions", []))
            recent.extend({"actor": "pulpo", "action": action} for action in parsed.actions)
            self.state["recent_actions"] = recent[-8:]
            self.database.save_scene(self.scene_id, self.state)

    def set_presence(self, participant: str, present: bool) -> None:
        self.state.setdefault("participants", {}).setdefault(participant, {})["present"] = present
        self.database.save_scene(self.scene_id, self.state)
