from __future__ import annotations

import re

from engine.parsing.message_parser import strip_emojis


START_MARKERS = ("<think>", "[Start thinking]", "[Start Thinking]")
END_MARKERS = ("</think>", "[End thinking]", "[End Thinking]")

# These phrases belong only to Pulpo Cookie's private instruction sheet.  They
# are deliberately specific enough that ordinary in-character dialogue will
# not be mistaken for an echo.
INSTRUCTION_ECHO_MARKERS = (
    "quiet watchful and reserved",
    "guarded observant and quietly curious",
    "answer the user directly",
    "head icing senses motion never",
    "avoid generic assistant phrases",
)


def _normalized(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def starts_with_instruction_echo(text: str) -> bool:
    """Detect a response beginning to repeat private character instructions."""
    candidate = _normalized(text)
    if len(candidate) < 12:
        return False
    return any(
        marker.startswith(candidate) or candidate.startswith(marker)
        for marker in INSTRUCTION_ECHO_MARKERS
    )


def is_instruction_echo(text: str) -> bool:
    """Detect a completed response that exposes multiple private directives."""
    candidate = _normalized(text)
    return sum(marker in candidate for marker in INSTRUCTION_ECHO_MARKERS) >= 2


class StreamingResponseFilter:
    """Drops hidden-reasoning regions without leaking partial marker text."""

    def __init__(self) -> None:
        self.pending = ""
        self.in_reasoning = False

    @staticmethod
    def _longest_marker_prefix_suffix(text: str, markers: tuple[str, ...]) -> int:
        longest = 0
        for marker in markers:
            for length in range(1, min(len(text), len(marker) - 1) + 1):
                if text.endswith(marker[:length]):
                    longest = max(longest, length)
        return longest

    def feed(self, chunk: str) -> str:
        self.pending += chunk
        visible: list[str] = []
        while self.pending:
            markers = END_MARKERS if self.in_reasoning else START_MARKERS
            found = [(self.pending.find(marker), marker) for marker in markers if marker in self.pending]
            if found:
                index, marker = min(found, key=lambda item: item[0])
                if not self.in_reasoning:
                    visible.append(self.pending[:index])
                self.pending = self.pending[index + len(marker):]
                self.in_reasoning = not self.in_reasoning
                continue
            keep = self._longest_marker_prefix_suffix(self.pending, markers)
            if self.in_reasoning:
                self.pending = self.pending[-keep:] if keep else ""
                break
            emit_to = len(self.pending) - keep
            visible.append(self.pending[:emit_to])
            self.pending = self.pending[emit_to:]
            break
        return strip_emojis("".join(visible))

    def finish(self) -> str:
        if self.in_reasoning:
            self.pending = ""
            return ""
        tail = strip_emojis(self.pending)
        self.pending = ""
        return tail


def sanitize_complete_response(text: str) -> str:
    for start, end in zip(START_MARKERS, END_MARKERS):
        text = re.sub(re.escape(start) + r".*?" + re.escape(end), "", text, flags=re.DOTALL)
    text = re.sub(r"\[(?:Start|End) [Tt]hinking\]", "", text)
    text = re.sub(r"</?think>", "", text, flags=re.IGNORECASE)
    return strip_emojis(text).strip()
