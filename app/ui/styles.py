APP_STYLESHEET = r"""
* {
    font-family: "Aptos", "Candara", "Segoe UI";
    color: #e9f1ef;
}
QMainWindow, QWidget#Root {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #071216, stop:0.62 #08171b, stop:1 #0a1c20);
}
QFrame#Rail {
    background: #0b1b20;
    border-right: 1px solid #183138;
}
QLabel#Brand {
    font-family: "Palatino Linotype";
    font-size: 22px;
    font-weight: 700;
    letter-spacing: 2px;
    color: #f2eee5;
}
QLabel#Designation {
    color: #78c9bd;
    font-size: 10px;
    letter-spacing: 2px;
}
QLabel#RailNote {
    color: #789096;
    font-size: 11px;
    line-height: 1.4;
}
QPushButton#NewSceneButton {
    background: #d98272;
    color: #102025;
    border: 0;
    border-radius: 10px;
    padding: 11px 14px;
    text-align: left;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
}
QPushButton#NewSceneButton:hover { background: #f09c89; }
QPushButton#NewSceneButton:pressed { background: #bc6e61; }
QPushButton#DeleteSceneButton {
    background: transparent;
    color: #c78378;
    border: 1px solid #55363a;
    border-radius: 9px;
    padding: 8px 11px;
    text-align: left;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.8px;
}
QPushButton#DeleteSceneButton:hover {
    background: #311f24;
    color: #ffc3b7;
    border-color: #b76661;
}
QPushButton#DeleteSceneButton:pressed { background: #512b2f; }
QMenu {
    background: #10242a;
    border: 1px solid #36575d;
    border-radius: 8px;
    padding: 5px;
}
QMenu::item { color: #efc1b8; padding: 8px 28px 8px 12px; border-radius: 5px; }
QMenu::item:selected { background: #452a2d; }
QLabel#SectionLabel {
    color: #5e7b80;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 2px;
    padding-left: 4px;
}
QListWidget#ConversationList {
    background: transparent;
    border: 0;
    outline: 0;
    color: #93a9ac;
    font-size: 12px;
    padding: 2px 0;
}
QListWidget#ConversationList::item {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 9px;
    padding: 9px 10px;
    margin: 1px 0;
}
QListWidget#ConversationList::item:hover {
    background: #10242a;
    color: #dce8e6;
}
QListWidget#ConversationList::item:selected {
    background: #142c32;
    border: 1px solid #285059;
    color: #f3eae2;
}
QPushButton#NavButton {
    background: transparent;
    color: #8ea3a7;
    text-align: left;
    padding: 11px 14px;
    border: 0;
    border-left: 2px solid transparent;
    font-size: 13px;
}
QPushButton#NavButton:hover {
    color: #e9f1ef;
    background: #10242a;
}
QPushButton#NavButton:checked {
    color: #f6d5cd;
    background: #122a30;
    border-left: 2px solid #ee8e7c;
}
QLabel#PageTitle {
    font-family: "Palatino Linotype";
    font-size: 25px;
    font-weight: 600;
    color: #f2eee5;
}
QLabel#PageSubtitle {
    color: #81999e;
    font-size: 12px;
}
QLabel#Status {
    background: #0e2529;
    color: #86d8c8;
    border: 1px solid #1c4244;
    border-radius: 13px;
    padding: 5px 11px;
    font-size: 11px;
}
QScrollArea {
    border: 0;
    background: transparent;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}
QFrame#IntroCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #102328, stop:0.72 #0c1d22, stop:1 #132226);
    border: 1px solid #234149;
    border-left: 3px solid #78c9bd;
    border-radius: 15px;
}
QLabel#IntroKicker {
    color: #ee8e7c;
    font-size: 10px;
    letter-spacing: 2px;
}
QLabel#IntroTitle {
    font-family: "Palatino Linotype";
    font-size: 18px;
    color: #f1ece1;
}
QLabel#IntroBody {
    color: #91a5a8;
    font-size: 12px;
}
QFrame#MessageUser {
    background: #15323a;
    border: 1px solid #224952;
    border-radius: 13px;
}
QFrame#MessagePulpo {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #121f22, stop:1 #0e1c20);
    border: 1px solid #26393c;
    border-left: 3px solid #d98172;
    border-radius: 13px;
}
QLabel#SpeakerUser, QLabel#SpeakerPulpo {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#SpeakerUser { color: #84d2c6; }
QLabel#SpeakerPulpo { color: #ef9c8c; }
QLabel#MessageText {
    background: transparent;
    border: 0;
    color: #e7eeee;
    font-size: 14px;
    padding: 0;
}
QFrame#Composer {
    background: #0d2025;
    border: 1px solid #27464d;
    border-radius: 16px;
}
QFrame#Composer:focus-within { border-color: #5e9d97; }
QPlainTextEdit#MessageInput {
    background: transparent;
    border: 0;
    color: #edf3f1;
    padding: 8px;
    selection-background-color: #27545a;
    font-size: 14px;
}
QPlainTextEdit#MessageInput:disabled { color: #64777a; }
QPushButton#SendButton {
    background: #dd8373;
    color: #102025;
    border: 0;
    border-radius: 11px;
    padding: 10px 19px;
    font-weight: 700;
}
QPushButton#SendButton:hover { background: #f09b89; }
QPushButton#SendButton:disabled { background: #42565a; color: #7f9396; }
QLabel#Hint { color: #597176; font-size: 10px; }
QTextBrowser#DebugText {
    background: #09171b;
    border: 1px solid #1a343a;
    border-radius: 12px;
    color: #bad0cf;
    font-family: "Cascadia Mono", "Consolas";
    font-size: 11px;
    padding: 14px;
}
QPushButton#UtilityButton {
    background: #11282e;
    color: #b8cfcd;
    border: 1px solid #25434a;
    border-radius: 9px;
    padding: 8px 14px;
}
QPushButton#UtilityButton:hover { border-color: #5b9792; color: #eff5f3; }
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 4px 0;
}
QScrollBar::handle:vertical {
    background: #294047;
    min-height: 30px;
    border-radius: 4px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""
