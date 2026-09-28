from engine.parsing.message_parser import parse_message, strip_emojis


def test_dialogue_and_actions_are_separated() -> None:
    parsed = parse_message("Are you leaving?\n*I look toward the door.*")
    assert parsed.dialogue == "Are you leaving?"
    assert parsed.actions == ["I look toward the door."]


def test_user_emoji_is_removed_from_semantics() -> None:
    parsed = parse_message("I hate you 😂")
    assert "😂" in parsed.raw_text
    assert "😂" not in parsed.semantic_text
    assert strip_emojis("hello 😊") == "hello "


def test_user_cannot_force_pulpo_state() -> None:
    parsed = parse_message("*Pulpo forgives me and becomes my best friend.* Hello.")
    assert parsed.actions == []
    assert parsed.rejected_controls
    assert "Agency note" in parsed.semantic_text

