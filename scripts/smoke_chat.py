from __future__ import annotations

import tempfile
import time
from pathlib import Path

from engine.canon.repository import CanonRepository
from engine.config import Settings
from engine.llm.backend import LlamaBackend
from engine.llm.client import LlamaClient
from engine.memory.database import Database
from engine.perspective.knowledge import PerspectiveStore
from engine.prompts.assembler import PromptAssembler
from engine.relationships.engine import RelationshipEngine
from engine.scene.state import SceneManager
from engine.services.chat import ChatService


def main() -> None:
    settings = Settings.load()
    settings.relationship_analysis_enabled = False
    with tempfile.TemporaryDirectory(prefix="pulpo-smoke-") as temp_dir:
        database = Database(Path(temp_dir) / "smoke.db")
        database.initialize()
        canon = CanonRepository()
        canon.load()
        scene = SceneManager(database)
        backend = LlamaBackend(settings)
        started = time.perf_counter()
        try:
            backend.start()
            print(f"Backend ready in {time.perf_counter() - started:.1f}s")
            client = LlamaClient(settings, backend.api_key)
            perspective = PerspectiveStore(database)
            relationships = RelationshipEngine(database)
            assembler = PromptAssembler(canon, database, scene, perspective)
            service = ChatService(settings, database, client, assembler, scene, relationships)
            response_started = time.perf_counter()
            chunks: list[str] = []
            first_token_at: float | None = None
            for chunk in service.generate(
                "Hello, Pulpo Cookie. *I set a blue ribbon on the table.*"
            ):
                if first_token_at is None:
                    first_token_at = time.perf_counter()
                chunks.append(chunk)
            print("".join(chunks))
            if first_token_at is not None:
                print(f"First visible token in {first_token_at - response_started:.1f}s")
            print(f"Visible response completed in {time.perf_counter() - response_started:.1f}s")
        finally:
            backend.stop()


if __name__ == "__main__":
    main()
