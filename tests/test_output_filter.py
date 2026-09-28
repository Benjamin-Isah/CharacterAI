from engine.parsing.output_filter import StreamingResponseFilter, sanitize_complete_response


def test_hidden_reasoning_is_removed_across_chunks() -> None:
    response_filter = StreamingResponseFilter()
    output = "".join(
        response_filter.feed(chunk)
        for chunk in ("<thi", "nk>secret", " plan</th", "ink>... Hi 😊")
    ) + response_filter.finish()
    assert output == "... Hi "


def test_complete_sanitizer_removes_reasoning() -> None:
    assert sanitize_complete_response("[Start thinking]x[End thinking]Visible") == "Visible"

