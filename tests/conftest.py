from __future__ import annotations

from pathlib import Path

import pytest

from engine.memory.database import Database


@pytest.fixture
def database(tmp_path: Path) -> Database:
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db

