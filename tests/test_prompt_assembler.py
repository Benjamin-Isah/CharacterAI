from engine.canon.repository import CanonRepository
from engine.config import Settings
from engine.models import ParsedMessage
from engine.perspective.knowledge import PerspectiveStore
from engine.prompts.assembler import PromptAssembler
from engine.relationships.engine import RelationshipEngine
from engine.scene.state import SceneManager


def test_prompt_is_compact_and_keeps_only_recent_history(database) -> None:
    canon = CanonRepository()
    canon.load()
    scene = SceneManager(database)
    conversation_id = database.get_or_create_conversation()
    database.add_message(
        conversation_id,
        "user",
        ParsedMessage("A" * 80, "A" * 80, [], [], "A" * 80),
        scene.scene_id,
    )
    database.add_message(
        conversation_id,
        "pulpo",
        ParsedMessage("B" * 80, "B" * 80, [], [], "B" * 80),
        scene.scene_id,
    )
    settings = Settings(context_history_messages=1, context_message_char_limit=20)
    assembler = PromptAssembler(
        canon, database, scene, PerspectiveStore(database), settings
    )

    messages, debug = assembler.assemble(
        conversation_id, "hello", RelationshipEngine(database).current()
    )

    assert "Pulpo Cookie" in messages[0]["content"]
    assert debug["prompt_components"]["history_messages"] == 1
    assert len(messages) == 2
    assert messages[-1]["content"] == "B" * 20 + "…"
