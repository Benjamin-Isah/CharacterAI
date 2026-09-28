from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx

from engine.config import Settings
from engine.parsing.output_filter import StreamingResponseFilter


class LlamaClient:
    def __init__(self, settings: Settings, api_key: str) -> None:
        self.settings = settings
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def stream_chat(self, messages: list[dict[str, str]]) -> Iterator[str]:
        payload = {
            "model": "local",
            "messages": messages,
            "stream": True,
            "temperature": self.settings.temperature,
            "top_p": self.settings.top_p,
            "max_tokens": self.settings.max_response_tokens,
            # Qwen supports this OpenAI-compatible request field.  Combined
            # with the server setting, it keeps private reasoning out of the
            # response path so the first visible words arrive sooner.
            "reasoning_effort": "none",
        }
        response_filter = StreamingResponseFilter()
        with httpx.stream(
            "POST",
            f"{self.settings.base_url}/v1/chat/completions",
            headers=self.headers,
            json=payload,
            timeout=httpx.Timeout(180, connect=10),
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                packet = json.loads(data)
                delta = packet.get("choices", [{}])[0].get("delta", {})
                # reasoning_content is deliberately ignored even if a model/server emits it.
                content = delta.get("content") or ""
                if content:
                    visible = response_filter.feed(content)
                    if visible:
                        yield visible
        tail = response_filter.finish()
        if tail:
            yield tail

    def complete(self, messages: list[dict[str, str]], max_tokens: int = 420) -> str:
        payload = {
            "model": "local",
            "messages": messages,
            "stream": False,
            "temperature": 0.12,
            "top_p": 0.8,
            "max_tokens": max_tokens,
        }
        response = httpx.post(
            f"{self.settings.base_url}/v1/chat/completions",
            headers=self.headers,
            json=payload,
            timeout=httpx.Timeout(180, connect=10),
        )
        response.raise_for_status()
        message: dict[str, Any] = response.json()["choices"][0]["message"]
        return str(message.get("content") or "")
