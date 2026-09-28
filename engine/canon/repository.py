from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from engine.config import PROJECT_ROOT


VALID_CLASSIFICATIONS = {
    "DIRECT_CANON_FACT",
    "CANON_SUPPORTED_INFERENCE",
    "USER_REPORTED_INGAME",
    "INTERPRETATION",
    "UNKNOWN",
}


class CanonRepository:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or PROJECT_ROOT / "characters" / "pulpo"
        self.entries: list[dict[str, Any]] = []
        self.sources: dict[str, dict[str, Any]] = {}

    def load(self) -> None:
        self.entries.clear()
        self.sources.clear()
        for path in sorted(self.root.rglob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            for source in payload.get("sources", []):
                self.sources[source["id"]] = source
            for entry in payload.get("entries", []):
                classification = entry.get("classification", "UNKNOWN")
                if classification not in VALID_CLASSIFICATIONS:
                    raise ValueError(f"Invalid canon classification in {path}: {classification}")
                item = dict(entry)
                item["file"] = str(path.relative_to(self.root))
                self.entries.append(item)

    def core(self) -> list[dict[str, Any]]:
        return [entry for entry in self.entries if "core" in entry.get("tags", [])]

    def relevant(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        terms = {word for word in re.findall(r"[a-z0-9]+", query.lower()) if len(word) > 2}
        scored: list[tuple[float, dict[str, Any]]] = []
        for entry in self.entries:
            if entry.get("classification") == "INTERPRETATION":
                base = 0.02
            elif entry.get("classification") == "UNKNOWN":
                base = 0.0
            else:
                base = float(entry.get("confidence", 0.0)) * 0.25
            haystack = " ".join(
                [entry.get("claim", ""), *entry.get("tags", [])]
            ).lower()
            overlap = sum(1 for term in terms if term in haystack)
            tags = set(entry.get("tags", []))
            if "core" in tags:
                base += 0.9
            named_relationship_tags = {
                "time_shadow", "ovenhead", "cutter_circuit", "mochaccino", "mycookie"
            }
            relationship_terms = {
                "relationship", "friend", "friends", "team", "scoop", "contact", "contacts"
            }
            named_words = {
                word for tag in (tags & named_relationship_tags) for word in tag.split("_")
            }
            if tags & named_relationship_tags and not (
                terms & relationship_terms or terms & named_words
            ):
                base -= 0.8
            scored.append((base + overlap * 0.35, entry))
        return [entry for score, entry in sorted(scored, key=lambda pair: pair[0], reverse=True)[:limit] if score > 0]

    def stats(self) -> dict[str, int]:
        result = {classification: 0 for classification in VALID_CLASSIFICATIONS}
        for entry in self.entries:
            result[entry["classification"]] += 1
        result["sources"] = len(self.sources)
        result["total"] = len(self.entries)
        return result
