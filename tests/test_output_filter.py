from engine.parsing.output_filter import (
    StreamingResponseFilter,
    is_instruction_echo,
    sanitize_complete_response,
    starts_with_instruction_echo,
)


def test_hidden_reasoning_is_removed_across_chunks() -> None:
    response_filter = StreamingResponseFilter()
    output = "".join(
        response_filter.feed(chunk)
        for chunk in ("<thi", "nk>secret", " plan</th", "ink>... Hi 😊")
    ) + response_filter.finish()
    assert output == "... Hi "


def test_complete_sanitizer_removes_reasoning() -> None:
    assert sanitize_complete_response("[Start thinking]x[End thinking]Visible") == "Visible"


def test_instruction_echo_is_detected_without_blocking_normal_dialogue() -> None:
    leaked = (
        "Quiet, watchful, and reserved—not bubbly, cold, or cryptic. "
        "Her head icing senses motion; never describe human hair or ears. "
        "Avoid generic assistant phrases."
    )
    assert starts_with_instruction_echo("Quiet, watchful, and reserved")
    assert is_instruction_echo(leaked)
    assert not is_instruction_echo("...Pulpo Cookie. I noticed the color of your ribbon.")
