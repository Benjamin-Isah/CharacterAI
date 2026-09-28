from collections.abc import Iterator

from engine.config import Settings
from engine.relationships.engine import RelationshipEngine
from engine.scene.state import SceneManager
from engine.services.chat import ChatService, PROMPT_LEAK_FALLBACK


class EchoingClient:
    def stream_chat(self, _messages: list[dict[str, str]]) -> Iterator[str]:
        yield "Quiet, watchful, and reserved—not bubbly, cold, or cryptic. "
        yield "Her head icing senses motion; never describe human hair or ears."


class MinimalAssembler:
    def assemble(self, *_args):
        return [{"role": "system", "content": "private instructions"}], {}


def test_instruction_echo_is_replaced_before_it_reaches_the_chat(database) -> None:
    scene = SceneManager(database)
    service = ChatService(
        Settings(relationship_analysis_enabled=False),
        database,
        EchoingClient(),
        MinimalAssembler(),
        scene,
        RelationshipEngine(database),
    )

    output = "".join(service.generate("Hello."))

    assert output == PROMPT_LEAK_FALLBACK
    assert service.last_visible_response == PROMPT_LEAK_FALLBACK
    assert database.recent_messages(service.conversation_id)[-1]["raw_text"] == PROMPT_LEAK_FALLBACK
