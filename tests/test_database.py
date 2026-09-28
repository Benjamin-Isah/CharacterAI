from engine.models import ParsedMessage


def test_sqlite_message_and_memory_writes(database) -> None:
    conversation = database.get_or_create_conversation()
    message_id = database.add_message(
        conversation,
        "user",
        ParsedMessage("Hello", "Hello", [], [], "Spoken dialogue: Hello"),
        None,
    )
    memory_id = database.add_memory("USER_FACT", "The user likes blue.", 0.6, 0.9, tags=["color"])
    assert message_id > 0
    assert memory_id > 0
    assert database.recent_messages(conversation)[0]["raw_text"] == "Hello"
    assert database.retrieve_memories("blue")[0]["memory_type"] == "USER_FACT"


def test_backup_is_valid_sqlite(database, tmp_path) -> None:
    destination = tmp_path / "backup.db"
    database.backup(destination)
    assert destination.exists() and destination.stat().st_size > 0


def test_saved_conversations_can_be_created_and_switched(database) -> None:
    first = database.get_or_create_conversation()
    second = database.create_conversation()
    assert second != first
    assert database.list_conversations()[0]["id"] == second
    database.activate_conversation(first)
    active = [item for item in database.list_conversations() if item["active"]]
    assert [item["id"] for item in active] == [first]


def test_delete_conversation_removes_only_its_transcript(database) -> None:
    first = database.get_or_create_conversation()
    database.add_message(
        first,
        "user",
        ParsedMessage("First", "First", [], [], "First"),
        None,
    )
    second = database.create_conversation()
    database.add_message(
        second,
        "user",
        ParsedMessage("Second", "Second", [], [], "Second"),
        None,
    )

    assert database.delete_conversation(first) is True
    assert database.delete_conversation(first) is False
    assert database.recent_messages(second)[0]["raw_text"] == "Second"
    assert [item["id"] for item in database.list_conversations()] == [second]


def test_new_scene_gets_title_from_first_user_message(database) -> None:
    conversation = database.create_conversation()
    database.add_message(
        conversation,
        "user",
        ParsedMessage(
            "Do you want to see the roadster?",
            "Do you want to see the roadster?",
            [],
            [],
            "Spoken dialogue: Do you want to see the roadster?",
        ),
        None,
    )
    database.maybe_title_conversation(conversation, "Do you want to see the roadster?")
    titled = next(item for item in database.list_conversations() if item["id"] == conversation)
    assert titled["title"] == "Do you want to see the…"


def test_first_meeting_migration_preserves_earlier_chat(database) -> None:
    older = database.get_or_create_conversation()
    database.add_message(
        older,
        "user",
        ParsedMessage("Hello", "Hello", [], [], "Spoken dialogue: Hello"),
        None,
    )
    first_meeting = database.ensure_first_meeting_conversation()
    assert first_meeting != older
    conversations = {item["id"]: item for item in database.list_conversations()}
    assert conversations[older]["title"] == "Earlier conversation"
    assert conversations[older]["message_count"] == 1
    assert conversations[first_meeting]["active"] == 1
