from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from engine.canon.repository import CanonRepository
from engine.config import Settings
from engine.llm.backend import LlamaBackend
from engine.logging_config import configure_logging
from engine.memory.database import Database
from engine.scene.state import SceneManager


def main() -> int:
    configure_logging()
    settings = Settings.load()
    database = Database()
    database.initialize()
    canon = CanonRepository()
    canon.load()
    scene = SceneManager(database)
    backend = LlamaBackend(settings)

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Pulpo Cookie")
    app.setOrganizationName("Pulpo Cookie")
    window = MainWindow(settings, database, canon, scene, backend)
    window.show()
    return app.exec()
