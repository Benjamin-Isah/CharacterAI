from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(slots=True)
class Settings:
    schema_version: int = 2
    model_repo: str = "lmstudio-community/Qwen3.5-9B-GGUF"
    model_quant: str = "Q4_K_M"
    # Pulpo Cookie's live conversation needs a short, quick context—not a large
    # multi-user server window.  This leaves more VRAM bandwidth for generation.
    context_size: int = 3072
    gpu_layers: str = "99"
    generation_threads: int = 8
    prompt_threads: int = 16
    kv_cache_type_k: str = "q4_0"
    kv_cache_type_v: str = "q4_0"
    host: str = "127.0.0.1"
    port: int = 8338
    max_response_tokens: int = 80
    context_history_messages: int = 1
    context_message_char_limit: int = 220
    temperature: float = 0.6
    top_p: float = 0.85
    startup_timeout_seconds: int = 180
    # A second model pass after every reply makes the interface appear to hang.
    # It remains opt-in for anyone who wants experimental auto-analysis.
    relationship_analysis_enabled: bool = False
    relationship_analysis_max_tokens: int = 80
    offline_after_download: bool = True

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def hf_spec(self) -> str:
        return f"{self.model_repo}:{self.model_quant}"

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        settings_path = path or PROJECT_ROOT / "data" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        if not settings_path.exists():
            settings = cls()
            settings.save(settings_path)
            return settings
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
        known = {field: payload[field] for field in cls.__dataclass_fields__ if field in payload}
        return cls(**known)

    def save(self, path: Path | None = None) -> None:
        settings_path = path or PROJECT_ROOT / "data" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
