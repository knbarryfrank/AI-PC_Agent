
import markdown2
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QLineEdit, QPushButton, QLabel, QFrame
)
from PySide6.QtCore import Signal, Qt
from config import config_instance


class ChatWidget(QWidget):
    send_message_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("chat_panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(44)
        hdr.setStyleSheet("background:#0e1018; border-bottom:1px solid #1e2435;")
        hdr_l = QHBoxLayout(hdr)
        hdr_l.setContentsMargins(16, 0, 16, 0)
        title = QLabel("CHAT")
        title.setObjectName("panel_title")
        hdr_l.addWidget(title)
        hdr_l.addStretch()
        layout.addWidget(hdr)

        # Chat history
        self.chat_history = QTextBrowser()
        self.chat_history.setObjectName("chat_history")
        self.chat_history.setOpenExternalLinks(True)
        self.chat_history.document().setDefaultStyleSheet(
            "body { margin: 0; padding: 0; }"
            ".user-msg { background: rgba(91,138,245,0.12); border-left: 3px solid #5b8af5;"
            "  border-radius: 8px; padding: 10px 14px; margin: 6px 0; }"
            ".ai-msg { background: rgba(255,255,255,0.04); border-left: 3px solid #252b3b;"
            "  border-radius: 8px; padding: 10px 14px; margin: 6px 0; }"
            ".sys-msg { color: #3a4055; font-size: 11px; padding: 4px 14px; }"
            "code { background: #1c2030; border-radius: 4px; padding: 1px 5px; font-family: monospace; }"
            "pre { background: #141720; border-radius: 6px; padding: 10px; overflow-x: auto; }"
            "b { color: #9ba3b4; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; }"
        )
        layout.addWidget(self.chat_history, stretch=1)

        # Token bar
        token_bar = QWidget()
        token_bar.setObjectName("token_bar")
        token_bar.setFixedHeight(32)
        tl = QHBoxLayout(token_bar)
        tl.setContentsMargins(14, 0, 14, 0)
        self.token_lbl = QLabel(f"Tokens: {config_instance.total_tokens_used:,}")
        self.token_lbl.setObjectName("token_lbl")
        tl.addWidget(self.token_lbl)
        tl.addStretch()
        layout.addWidget(token_bar)

        # Input area
        input_area = QWidget()
        input_area.setStyleSheet("background:#0e1018; border-top:1px solid #1e2435;")
        il = QHBoxLayout(input_area)
        il.setContentsMargins(12, 10, 12, 10)
        il.setSpacing(8)

        self.input_field = QLineEdit()
        self.input_field.setObjectName("chat_input")
        self.input_field.setPlaceholderText("Message AIPC Agent...")
        self.input_field.returnPressed.connect(self.send_message)

        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("send_btn")
        self.send_btn.setFixedHeight(42)
        self.send_btn.clicked.connect(self.send_message)

        il.addWidget(self.input_field)
        il.addWidget(self.send_btn)
        layout.addWidget(input_area)

    def send_message(self):
        msg = self.input_field.text().strip()
        if msg:
            self.append_user_message(msg)
            self.send_message_signal.emit(msg)
            self.input_field.clear()

    def append_user_message(self, text):
        safe = text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        html = (f"<div class='user-msg'>"
                f"<b>YOU</b><br>"
                f"<span style='color:#e8eaf0;font-size:13px;'>{safe}</span></div>")
        self.chat_history.append(html)

    def append_ai_message(self, text):
        md = markdown2.markdown(text, extras=["fenced-code-blocks","tables"])
        html = (f"<div class='ai-msg'>"
                f"<b>AIPC</b><br>"
                f"<span style='color:#c8cfdd;font-size:13px;'>{md}</span></div>")
        self.chat_history.append(html)

    def append_system_message(self, text):
        safe = text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        html = f"<div class='sys-msg'>&#x25B7; {safe}</div>"
        self.chat_history.append(html)

    def update_tokens(self, count):
        self.token_lbl.setText(f"Tokens: {count:,}")
