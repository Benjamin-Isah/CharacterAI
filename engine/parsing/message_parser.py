from __future__ import annotations

import re

from engine.models import ParsedMessage


ACTION_PATTERN = re.compile(r"\*([^*]+)\*", re.DOTALL)
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0000FE0F"
    "\U0000200D"
    "]+",
    flags=re.UNICODE,
)

FORCED_PULPO_STATE = re.compile(
    r"\bpulpo\b.{0,80}\b(?:thinks?|feels?|forgives?|decides?|becomes?|loves?|hates?|"
    r"trusts?|remembers?|agrees?|wants?|is now|must|has to)\b",
    re.IGNORECASE,
)


def strip_emojis(text: str) -> str:
    return EMOJI_PATTERN.sub("", text)


def parse_message(text: str) -> ParsedMessage:
    clean_semantic = strip_emojis(text).strip()
    all_actions = [match.strip() for match in ACTION_PATTERN.findall(clean_semantic) if match.strip()]
    rejected = [action for action in all_actions if FORCED_PULPO_STATE.search(action)]
    accepted = [action for action in all_actions if action not in rejected]
    dialogue = ACTION_PATTERN.sub(" ", clean_semantic)
    dialogue = re.sub(r"[ \t]+", " ", dialogue)
    dialogue = re.sub(r" *\n *", "\n", dialogue).strip()
    semantic_parts = []
    if dialogue:
        semantic_parts.append(f"Spoken dialogue: {dialogue}")
    semantic_parts.extend(f"User action: {action}" for action in accepted)
    if rejected:
        semantic_parts.append(
            "Agency note: attempted narration of Pulpo Cookie was ignored; Pulpo Cookie determines her own state."
        )
    return ParsedMessage(
        raw_text=text,
        dialogue=dialogue,
        actions=accepted,
        rejected_controls=rejected,
        semantic_text="\n".join(semantic_parts),
    )
