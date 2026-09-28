from __future__ import annotations

import html
import json
import re

from PySide6.QtCore import QEvent, QObject, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QKeyEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.ui.styles import APP_STYLESHEET
from engine.canon.repository import CanonRepository
from engine.config import Settings
from engine.llm.backend import LlamaBackend
from engine.llm.client import LlamaClient
from engine.memory.database import Database
from engine.parsing.message_parser import parse_message
from engine.parsing.output_filter import is_instruction_echo
from engine.perspective.knowledge import PerspectiveStore
from engine.prompts.assembler import PromptAssembler
from engine.relationships.engine import RelationshipEngine
from engine.scene.state import SceneManager
from engine.services.chat import ChatService, PROMPT_LEAK_FALLBACK


FIRST_MEETING_OPENING = (
    "*Late-afternoon light falls across a quiet observation room inside SCOOP. "
    "Colorful ribbons rest in careful coils along the table. This is the first "
    "time you and Pulpo Cookie have met.*\n\n"
    "*Her tentacle-like head icing turns toward you before the rest of her does.*\n\n"
    "...This is SCOOP. ...I'm Pulpo Cookie."
)

LEGACY_NEW_SCENE_OPENING = (
    "*A quiet side room inside SCOOP. Pulpo Cookie sits near the window, winding "
    "a ribbon around two fingers. Her head icing angles toward the doorway.*\n\n"
    "...You came."
)

LEGACY_FIRST_MEETING_OPENING = (
    "*Late-afternoon light falls across a quiet observation room inside SCOOP. "
    "Colorful ribbons rest in careful coils along the table. This is the first "
    "time you and Pulpo Cookie have met.*\n\n"
    "*Her tentacle-like head icing turns toward you before the rest of her does.*\n\n"
    "...Who?"
)


def message_html(text: str) -> str:
    escaped = html.escape(text).replace("\n", "<br>")
    escaped = re.sub(r"\*([^*]+)\*", r"<i style='color:#9bb2b4'>*\1*</i>", escaped)
    return f"<div style='line-height:1.42'>{escaped}</div>"


class ComposerKeyFilter(QObject):
    submit = Signal()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
                event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            ):
                self.submit.emit()
                return True
        return super().eventFilter(watched, event)


class StartupWorker(QThread):
    ready = Signal()
    failed = Signal(str)

    def __init__(self, backend: LlamaBackend) -> None:
        super().__init__()
        self.backend = backend

    def run(self) -> None:
        try:
            self.backend.start()
            self.ready.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


class ChatWorker(QThread):
    token = Signal(str)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, service: ChatService, text: str) -> None:
        super().__init__()
        self.service = service
        self.text = text

    def run(self) -> None:
        chunks: list[str] = []
        try:
            for chunk in self.service.generate(self.text):
                chunks.append(chunk)
                self.token.emit(chunk)
            self.completed.emit(self.service.last_visible_response or "".join(chunks))
        except Exception as exc:
            self.failed.emit(str(exc))


class MessageCard(QFrame):
    def __init__(self, speaker: str, text: str = "") -> None:
        super().__init__()
        is_user = speaker == "user"
        self.setObjectName("MessageUser" if is_user else "MessagePulpo")
        self.setMaximumWidth(720)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 11, 15, 12)
        layout.setSpacing(4)
        name = QLabel("YOU" if is_user else "PULPO COOKIE")
        name.setObjectName("SpeakerUser" if is_user else "SpeakerPulpo")
        layout.addWidget(name)
        self.text_view = QLabel()
        self.text_view.setObjectName("MessageText")
        self.text_view.setTextFormat(Qt.TextFormat.RichText)
        self.text_view.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.text_view.setWordWrap(True)
        self.text_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.text_view)
        self.raw_text = ""
        self.set_text(text)

    def set_text(self, text: str) -> None:
        self.raw_text = text
        self.text_view.setText(message_html(text or "…"))
        self.text_view.updateGeometry()
        self.updateGeometry()
        if self.parentWidget() and self.parentWidget().layout():
            self.parentWidget().layout().activate()

    def append_text(self, chunk: str) -> None:
        self.set_text(self.raw_text + chunk)


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: Settings,
        database: Database,
        canon: CanonRepository,
        scene: SceneManager,
        backend: LlamaBackend,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.database = database
        self.canon = canon
        self.scene = scene
        self.backend = backend
        self.service: ChatService | None = None
        self.startup_worker: StartupWorker | None = None
        self.chat_worker: ChatWorker | None = None
        self.active_pulpo_card: MessageCard | None = None
        self._stream_buffer: list[str] = []
        self._stream_flush_timer = QTimer(self)
        self._stream_flush_timer.setInterval(33)
        self._stream_flush_timer.timeout.connect(self._flush_stream_buffer)
        self._closing = False
        self._populating_conversations = False
        self.database.ensure_first_meeting_conversation()
        self.conversation_id = self.database.get_or_create_conversation()
        for conversation in self.database.list_conversations():
            self._seed_opening_if_needed(int(conversation["id"]))
        self._replace_instruction_echoes()
        self.setWindowTitle("Pulpo Cookie")
        self.resize(1220, 800)
        self.setMinimumSize(980, 660)
        self.setStyleSheet(APP_STYLESHEET)
        self._build_ui()
        self._load_history()
        QTimer.singleShot(150, self._start_backend)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        rail = QFrame()
        rail.setObjectName("Rail")
        rail.setFixedWidth(268)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(22, 27, 18, 23)
        rail_layout.setSpacing(7)
        brand = QLabel("PULPO COOKIE")
        brand.setObjectName("Brand")
        rail_layout.addWidget(brand)
        designation = QLabel("SCOOP—3333 / LOCAL")
        designation.setObjectName("Designation")
        rail_layout.addWidget(designation)
        rail_layout.addSpacing(20)

        new_scene = QPushButton("＋  NEW SCENE")
        new_scene.setObjectName("NewSceneButton")
        new_scene.clicked.connect(self._new_conversation)
        rail_layout.addWidget(new_scene)
        rail_layout.addSpacing(18)

        saved_label = QLabel("SAVED SCENES")
        saved_label.setObjectName("SectionLabel")
        rail_layout.addWidget(saved_label)
        self.conversation_list = QListWidget()
        self.conversation_list.setObjectName("ConversationList")
        self.conversation_list.setSpacing(3)
        self.conversation_list.setWordWrap(True)
        self.conversation_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.conversation_list.currentItemChanged.connect(self._conversation_selected)
        self.conversation_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.conversation_list.customContextMenuRequested.connect(
            self._conversation_context_menu
        )
        rail_layout.addWidget(self.conversation_list, 1)
        rail_layout.addSpacing(12)

        delete_scene = QPushButton("⌫  DELETE SELECTED CHAT")
        delete_scene.setObjectName("DeleteSceneButton")
        delete_scene.setToolTip("Delete the selected chat after confirmation")
        delete_scene.clicked.connect(self._delete_active_conversation)
        rail_layout.addWidget(delete_scene)
        rail_layout.addSpacing(9)

        self.chat_nav = QPushButton("Conversation")
        self.debug_nav = QPushButton("Diagnostics")
        group = QButtonGroup(self)
        group.setExclusive(True)
        for index, button in enumerate((self.chat_nav, self.debug_nav)):
            button.setObjectName("NavButton")
            button.setCheckable(True)
            group.addButton(button, index)
            rail_layout.addWidget(button)
        self.chat_nav.setChecked(True)
        group.idClicked.connect(self._switch_page)
        note = QLabel("Private by design.\nInference and memory stay\non this machine.")
        note.setObjectName("RailNote")
        rail_layout.addWidget(note)
        root_layout.addWidget(rail)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_chat_page())
        self.pages.addWidget(self._build_debug_page())
        root_layout.addWidget(self.pages, 1)
        self._refresh_conversation_list()

    def _header(self, title: str, subtitle: str) -> QHBoxLayout:
        layout = QHBoxLayout()
        text = QVBoxLayout()
        text.setSpacing(2)
        self.page_title = QLabel(title)
        self.page_title.setObjectName("PageTitle")
        self.page_subtitle = QLabel(subtitle)
        self.page_subtitle.setObjectName("PageSubtitle")
        text.addWidget(self.page_title)
        text.addWidget(self.page_subtitle)
        layout.addLayout(text)
        layout.addStretch()
        self.status_label = QLabel("●  Starting Pulpo Cookie…")
        self.status_label.setObjectName("Status")
        layout.addWidget(self.status_label)
        return layout

    def _build_chat_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(42, 30, 42, 24)
        layout.setSpacing(18)
        layout.addLayout(
            self._header("Pulpo Cookie", "First meeting · SCOOP observation room")
        )

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.messages_layout = QVBoxLayout(self.scroll_content)
        self.messages_layout.setContentsMargins(2, 4, 12, 8)
        self.messages_layout.setSpacing(12)
        self._add_intro_card()
        self.messages_layout.addStretch()
        self.scroll.setWidget(self.scroll_content)
        layout.addWidget(self.scroll, 1)

        composer = QFrame()
        composer.setObjectName("Composer")
        composer_layout = QHBoxLayout(composer)
        composer_layout.setContentsMargins(9, 7, 8, 7)
        self.input = QPlainTextEdit()
        self.input.setObjectName("MessageInput")
        self.input.setPlaceholderText("Say something…  Use *asterisks* for physical actions.")
        self.input.setFixedHeight(66)
        self.input.setEnabled(False)
        self.key_filter = ComposerKeyFilter(self)
        self.key_filter.submit.connect(self._send)
        self.input.installEventFilter(self.key_filter)
        composer_layout.addWidget(self.input, 1)
        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("SendButton")
        self.send_button.setEnabled(False)
        self.send_button.clicked.connect(self._send)
        composer_layout.addWidget(self.send_button, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(composer)
        hint = QLabel(
            "Enter to send  ·  Shift + Enter for a new line  ·  Pulpo Cookie controls Pulpo Cookie"
        )
        hint.setObjectName("Hint")
        layout.addWidget(hint)
        return page

    def _add_intro_card(self) -> None:
        card = QFrame()
        card.setObjectName("IntroCard")
        card.setMaximumWidth(720)
        box = QVBoxLayout(card)
        box.setContentsMargins(17, 14, 17, 15)
        self.scene_kicker = QLabel()
        self.scene_kicker.setObjectName("IntroKicker")
        self.scene_title = QLabel()
        self.scene_title.setObjectName("IntroTitle")
        self.scene_body = QLabel()
        self.scene_body.setObjectName("IntroBody")
        self.scene_body.setWordWrap(True)
        box.addWidget(self.scene_kicker)
        box.addWidget(self.scene_title)
        box.addWidget(self.scene_body)
        self.messages_layout.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
        self._update_scene_copy()

    def _build_debug_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(38, 28, 38, 30)
        layout.setSpacing(18)
        header = QHBoxLayout()
        text = QVBoxLayout()
        title = QLabel("Diagnostics")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Model, scene, memory retrieval, and relationship evidence")
        subtitle.setObjectName("PageSubtitle")
        text.addWidget(title)
        text.addWidget(subtitle)
        header.addLayout(text)
        header.addStretch()
        layout.addLayout(header)
        self.debug_text = QTextBrowser()
        self.debug_text.setObjectName("DebugText")
        layout.addWidget(self.debug_text, 1)
        actions = QHBoxLayout()
        refresh = QPushButton("Refresh")
        backup = QPushButton("Create database backup")
        export = QPushButton("Export local data")
        for button in (refresh, backup, export):
            button.setObjectName("UtilityButton")
            actions.addWidget(button)
        actions.addStretch()
        refresh.clicked.connect(self._refresh_debug)
        backup.clicked.connect(self._backup)
        export.clicked.connect(self._export)
        layout.addLayout(actions)
        self._refresh_debug()
        return page

    def _switch_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        if index == 1:
            self._refresh_debug()

    def _seed_opening_if_needed(self, conversation_id: int) -> None:
        messages = self.database.recent_messages(conversation_id, limit=100)
        if not messages:
            self.database.add_message(
                conversation_id,
                "pulpo",
                parse_message(FIRST_MEETING_OPENING),
                self.scene.scene_id,
            )
            return
        if (
            messages[0]["speaker"] == "pulpo"
            and messages[0]["raw_text"]
            in {LEGACY_NEW_SCENE_OPENING, LEGACY_FIRST_MEETING_OPENING}
        ):
            self.database.update_message(
                int(messages[0]["id"]),
                parse_message(FIRST_MEETING_OPENING),
                self.scene.scene_id,
            )

    def _replace_instruction_echoes(self) -> None:
        """Remove any private instruction echo saved by an earlier model turn."""
        for conversation in self.database.list_conversations():
            for message in self.database.recent_messages(int(conversation["id"]), limit=100):
                if message["speaker"] == "pulpo" and is_instruction_echo(message["raw_text"]):
                    self.database.update_message(
                        int(message["id"]),
                        parse_message(PROMPT_LEAK_FALLBACK),
                        self.scene.scene_id,
                    )

    def _is_first_encounter(self) -> bool:
        messages = self.database.recent_messages(self.conversation_id, limit=100)
        return bool(messages and "This is the first time you and Pulpo Cookie have met." in messages[0]["raw_text"])

    def _update_scene_copy(self) -> None:
        if not hasattr(self, "scene_kicker"):
            return
        is_first = self._is_first_encounter()
        if is_first:
            self.scene_kicker.setText("FIRST ENCOUNTER  /  LATE AFTERNOON")
            self.scene_title.setText("You have just met Pulpo Cookie.")
            self.scene_body.setText(
                "SCOOP observation room · Ribbons lie across the table · "
                "Spoken words are plain text; actions go between *asterisks*."
            )
            if hasattr(self, "page_subtitle"):
                self.page_subtitle.setText("First meeting · SCOOP observation room")
        else:
            self.scene_kicker.setText("SAVED SCENE  /  LOCAL MEMORY")
            self.scene_title.setText("A separate scene with Pulpo Cookie.")
            self.scene_body.setText(
                "This conversation is saved independently. Long-term memories and your "
                "relationship with Pulpo Cookie can still carry across scenes."
            )
            if hasattr(self, "page_subtitle"):
                self.page_subtitle.setText("Saved locally · persistent continuity")

    def _refresh_conversation_list(self) -> None:
        self._populating_conversations = True
        self.conversation_list.clear()
        selected_item: QListWidgetItem | None = None
        for conversation in self.database.list_conversations():
            count = int(conversation["message_count"])
            suffix = "message" if count == 1 else "messages"
            item = QListWidgetItem(f"{conversation['title']}\n{count} saved {suffix}")
            item.setData(Qt.ItemDataRole.UserRole, int(conversation["id"]))
            item.setToolTip(conversation["title"])
            self.conversation_list.addItem(item)
            if int(conversation["id"]) == self.conversation_id:
                selected_item = item
        if selected_item:
            self.conversation_list.setCurrentItem(selected_item)
        self._populating_conversations = False

    def _new_conversation(self) -> None:
        if self.chat_worker and self.chat_worker.isRunning():
            QMessageBox.information(
                self,
                "Pulpo Cookie is answering",
                "Wait for the current reply before starting another scene.",
            )
            return
        conversation_id = self.database.create_conversation()
        self._seed_opening_if_needed(conversation_id)
        self._set_active_conversation(conversation_id)

    def _delete_active_conversation(self) -> None:
        self._delete_conversation(self.conversation_id)

    def _conversation_context_menu(self, position) -> None:
        item = self.conversation_list.itemAt(position)
        if item is None:
            return
        self.conversation_list.setCurrentItem(item)
        conversation_id = int(item.data(Qt.ItemDataRole.UserRole))
        menu = QMenu(self)
        delete_action = menu.addAction("Delete this chat")
        selected_action = menu.exec(self.conversation_list.mapToGlobal(position))
        if selected_action == delete_action:
            self._delete_conversation(conversation_id)

    def _delete_conversation(self, conversation_id: int) -> None:
        if self.chat_worker and self.chat_worker.isRunning():
            QMessageBox.information(
                self,
                "Pulpo Cookie is answering",
                "Wait for the current reply before deleting this chat.",
            )
            return
        current = next(
            (
                item
                for item in self.database.list_conversations()
                if int(item["id"]) == conversation_id
            ),
            None,
        )
        if current is None:
            return
        title = str(current["title"])
        choice = QMessageBox.question(
            self,
            "Delete this chat?",
            f"Delete “{title}” and its {int(current['message_count'])} saved messages?\n\n"
            "This cannot be undone. Other chats stay saved. Shared memories are kept.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        if not self.database.delete_conversation(conversation_id):
            QMessageBox.warning(self, "Chat not found", "This chat was already removed.")
            self._refresh_conversation_list()
            return
        remaining = self.database.list_conversations()
        replacement = (
            int(remaining[0]["id"])
            if remaining
            else self.database.ensure_first_meeting_conversation()
        )
        self._set_active_conversation(replacement)
        self.status_label.setText("●  Chat deleted")

    def _conversation_selected(
        self, current: QListWidgetItem | None, previous: QListWidgetItem | None
    ) -> None:
        if self._populating_conversations or current is None:
            return
        conversation_id = int(current.data(Qt.ItemDataRole.UserRole))
        if conversation_id == self.conversation_id:
            return
        if self.chat_worker and self.chat_worker.isRunning():
            self._refresh_conversation_list()
            return
        self._set_active_conversation(conversation_id)

    def _set_active_conversation(self, conversation_id: int) -> None:
        self.database.activate_conversation(conversation_id)
        self.conversation_id = conversation_id
        self._seed_opening_if_needed(conversation_id)
        if self.service:
            self.service.conversation_id = conversation_id
            self.service.last_debug = {}
        self._load_history()
        self._update_scene_copy()
        self._refresh_conversation_list()
        self.pages.setCurrentIndex(0)
        self.chat_nav.setChecked(True)

    def _load_history(self) -> None:
        if hasattr(self, "messages_layout"):
            while self.messages_layout.count():
                item = self.messages_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self._add_intro_card()
            self.messages_layout.addStretch()
        for item in self.database.recent_messages(self.conversation_id, limit=100):
            self._add_message_card(item["speaker"], item["raw_text"])

    def _add_message_card(self, speaker: str, text: str) -> MessageCard:
        card = MessageCard(speaker, text)
        alignment = Qt.AlignmentFlag.AlignRight if speaker == "user" else Qt.AlignmentFlag.AlignLeft
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, card, 0, alignment)
        QTimer.singleShot(0, self._scroll_bottom)
        return card

    def _scroll_bottom(self) -> None:
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _start_backend(self) -> None:
        self.status_label.setText("●  Loading Pulpo Cookie’s memory…")
        self.startup_worker = StartupWorker(self.backend)
        self.startup_worker.ready.connect(self._backend_ready)
        self.startup_worker.failed.connect(self._backend_failed)
        self.startup_worker.start()

    def _backend_ready(self) -> None:
        client = LlamaClient(self.settings, self.backend.api_key)
        perspective = PerspectiveStore(self.database)
        relationships = RelationshipEngine(self.database)
        assembler = PromptAssembler(
            self.canon, self.database, self.scene, perspective, self.settings
        )
        self.service = ChatService(
            self.settings,
            self.database,
            client,
            assembler,
            self.scene,
            relationships,
            conversation_id=self.conversation_id,
        )
        self.status_label.setText("●  Pulpo Cookie · Ready")
        self.input.setEnabled(True)
        self.send_button.setEnabled(True)
        self.input.setFocus()
        self._refresh_debug()

    def _backend_failed(self, message: str) -> None:
        if self._closing:
            return
        self.status_label.setText("●  Backend unavailable")
        QMessageBox.critical(self, "Pulpo Cookie could not start", message)
        self._refresh_debug()

    def _send(self) -> None:
        if not self.service or (self.chat_worker and self.chat_worker.isRunning()):
            return
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.input.clear()
        self._stream_buffer.clear()
        self._stream_flush_timer.stop()
        self._add_message_card("user", text)
        self.active_pulpo_card = self._add_message_card("pulpo", "")
        self.input.setEnabled(False)
        self.send_button.setEnabled(False)
        self.status_label.setText("●  Pulpo Cookie is thinking…")
        self.chat_worker = ChatWorker(self.service, text)
        self.chat_worker.token.connect(self._stream_token)
        self.chat_worker.completed.connect(self._chat_complete)
        self.chat_worker.failed.connect(self._chat_failed)
        self.chat_worker.start()

    def _stream_token(self, token: str) -> None:
        self._stream_buffer.append(token)
        # Reveal the first words immediately, then paint at a steady 30 FPS.
        # This prevents each tiny model token from forcing a complete bubble
        # relayout, which made long messages feel slower than generation.
        if not self._stream_flush_timer.isActive():
            self._flush_stream_buffer()
            self._stream_flush_timer.start()

    def _flush_stream_buffer(self) -> None:
        if self.active_pulpo_card and self._stream_buffer:
            self.active_pulpo_card.append_text("".join(self._stream_buffer))
            self._stream_buffer.clear()
            self._scroll_bottom()
        if not self._stream_buffer:
            self._stream_flush_timer.stop()

    def _chat_complete(self, final_text: str) -> None:
        self._flush_stream_buffer()
        if self.active_pulpo_card and final_text:
            # Replace the streamed draft with the final safe, sanitized text.
            # This also clears any late-detected private-instruction echo.
            self.active_pulpo_card.set_text(final_text)
        self.status_label.setText("●  Pulpo Cookie · Ready")
        self.input.setEnabled(True)
        self.send_button.setEnabled(True)
        self.input.setFocus()
        self.active_pulpo_card = None
        self._refresh_conversation_list()
        self._refresh_debug()

    def _chat_failed(self, message: str) -> None:
        self._flush_stream_buffer()
        if self._closing:
            return
        if self.active_pulpo_card and not self.active_pulpo_card.raw_text:
            self.active_pulpo_card.set_text("…")
        self.status_label.setText("●  Generation failed")
        self.input.setEnabled(True)
        self.send_button.setEnabled(True)
        QMessageBox.warning(self, "Pulpo Cookie could not answer", message)
        self._refresh_debug()

    def _refresh_debug(self) -> None:
        relationship = self.database.get_relationship()
        last_event = self.database.last_relationship_event()
        payload = {
            "model": {
                "status": self.backend.status,
                "model": self.settings.hf_spec,
                "context": self.settings.context_size,
                "gpu_layers": self.settings.gpu_layers,
                "reasoning": "disabled; reasoning fields filtered",
            },
            "canon": self.canon.stats(),
            "scene": self.scene.state,
            "relationship": relationship.values,
            "relationship_interactions": relationship.interaction_count,
            "last_relationship_event": last_event,
            "last_generation": self.service.last_debug if self.service else {},
        }
        self.debug_text.setPlainText(json.dumps(payload, indent=2, ensure_ascii=False))

    def _backup(self) -> None:
        try:
            path = self.database.backup()
            QMessageBox.information(self, "Backup created", f"Saved safely to:\n{path}")
        except Exception as exc:
            QMessageBox.warning(self, "Backup failed", str(exc))

    def _export(self) -> None:
        try:
            path = self.database.export_json()
            QMessageBox.information(self, "Export created", f"Exported local data to:\n{path}")
        except Exception as exc:
            QMessageBox.warning(self, "Export failed", str(exc))

    def closeEvent(self, event: QCloseEvent) -> None:
        self._closing = True
        try:
            self.database.backup()
        finally:
            self.backend.stop()
            if self.chat_worker and self.chat_worker.isRunning():
                self.chat_worker.wait(10_000)
            if self.startup_worker and self.startup_worker.isRunning():
                self.startup_worker.wait(10_000)
        event.accept()
