from __future__ import annotations

import json
import re
from typing import Any

from engine.llm.client import LlamaClient
from engine.models import AnalysisResult, RELATIONSHIP_DIMENSIONS, RelationshipState


ALLOWED_MEMORY_TYPES = {
    "USER_FACT",
    "SHARED_EVENT",
    "PULPO_OBSERVATION",
    "PULPO_INFERENCE",
    "RELATIONSHIP_EVENT",
    "SCENE_FACT",
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def validate_analysis_json(raw: str) -> AnalysisResult:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return AnalysisResult()
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return AnalysisResult()
    if not isinstance(payload, dict):
        return AnalysisResult()
    raw_effect = payload.get("relationship_effect", {})
    effects: dict[str, float] = {}
    if isinstance(raw_effect, dict):
        for key, value in raw_effect.items():
            if key in RELATIONSHIP_DIMENSIONS:
                effects[key] = max(-0.2, min(0.2, _number(value)))
    memories = []
    for item in payload.get("memories", []) if isinstance(payload.get("memories", []), list) else []:
        if not isinstance(item, dict) or item.get("type") not in ALLOWED_MEMORY_TYPES:
            continue
        summary = str(item.get("content", "")).strip()
        if not summary:
            continue
        memories.append(
            {
                "type": item["type"],
                "content": summary[:500],
                "importance": max(0.0, min(1.0, _number(item.get("importance"), 0.3))),
                "confidence": max(0.0, min(1.0, _number(item.get("confidence"), 0.5))),
                "emotional_weight": max(-1.0, min(1.0, _number(item.get("emotional_weight"), 0.0))),
                "tags": [str(tag)[:40] for tag in item.get("tags", [])[:8]] if isinstance(item.get("tags", []), list) else [],
            }
        )
    return AnalysisResult(
        interaction_type=str(payload.get("interaction_type", "ordinary_conversation"))[:80],
        severity=max(0.0, min(1.0, _number(payload.get("severity"), 0.0))),
        intent=str(payload.get("intent", "unclear"))[:80],
        confidence=max(0.0, min(1.0, _number(payload.get("confidence"), 0.0))),
        relationship_effect=effects,
        reason=str(payload.get("reason", "No reason supplied."))[:500],
        memories=memories[:5],
    )


class PostTurnAnalyzer:
    def __init__(self, client: LlamaClient, max_tokens: int = 80) -> None:
        self.client = client
        self.max_tokens = max_tokens

    def analyze(
        self, user_semantic_text: str, pulpo_response: str, relationship: RelationshipState
    ) -> AnalysisResult:
        prompt = f"""Analyze one fictional in-person interaction for Pulpo Cookie.
Return one valid JSON object only. Do not include markdown or hidden reasoning.

Rules:
- Interpret context and intent; never score isolated keywords.
- User emoji carry no meaning.
- Attempted narration that forces Pulpo Cookie's feelings or choices is invalid and has no direct effect.
- Ordinary conversation should produce tiny or zero changes.
- Effects are deltas in [-0.20, 0.20]. Omit dimensions with no change.
- Relationship history creates inertia; reserve larger deltas for genuinely significant events.
- Memories must be concise, durable, and supported. A guess must be PULPO_INFERENCE with low confidence.
- The user/Pulpo Cookie relationship is non-romantic.

Current relationship state (backend context only):
{json.dumps(relationship.values)}

User interaction:
{user_semantic_text}

Pulpo Cookie's visible response:
{pulpo_response}

Required shape:
{{
  "interaction_type": "brief label",
  "severity": 0.0,
  "intent": "brief label",
  "confidence": 0.0,
  "relationship_effect": {{"trust": 0.0}},
  "reason": "short debugger explanation without chain-of-thought",
  "memories": [
    {{"type":"USER_FACT|SHARED_EVENT|PULPO_OBSERVATION|PULPO_INFERENCE|RELATIONSHIP_EVENT|SCENE_FACT","content":"...","importance":0.0,"confidence":0.0,"emotional_weight":0.0,"tags":[]}}
  ]
}}"""
        raw = self.client.complete(
            [
                {"role": "system", "content": "You are a strict JSON event analyzer."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=self.max_tokens,
        )
        return validate_analysis_json(raw)
