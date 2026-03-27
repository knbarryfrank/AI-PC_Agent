import markdown2
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser, QLineEdit, QPushButton, QHBoxLayout, QLabel
from PySide6.QtCore import Signal
from config import config_instance

class ChatWidget(QWidget):
    send_message_signal = Signal(str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with Token Counter
        header_layout = QHBoxLayout()
        title_lbl = QLabel("<b>AIPC Chat</b>")
        self.token_lbl = QLabel(f"Tokens Used: {config_instance.total_tokens_used}")
        self.token_lbl.setStyleSheet("color: #4A90E2;")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        header_layout.addWidget(self.token_lbl)

        # Chat History
        self.chat_history = QTextBrowser()
        self.chat_history.setOpenExternalLinks(True)
        
        # Input Area
        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type a message to AIPC...")
        self.input_field.returnPressed.connect(self.send_message)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_message)

        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_btn)

        layout.addLayout(header_layout)
        layout.addWidget(self.chat_history)
        layout.addLayout(input_layout)

    def send_message(self):
        msg = self.input_field.text().strip()
        if msg:
            self.append_user_message(msg)
            self.send_message_signal.emit(msg)
            self.input_field.clear()

    def append_user_message(self, text):
        html = f"<div style='margin-bottom: 10px; color:#4A90E2;'><b>You:</b> {text}</div>"
        self.chat_history.append(html)

    def append_ai_message(self, text):
        md_text = markdown2.markdown(text)
        html = f"<div style='margin-bottom: 10px; color:#E0E0E0;'><b>AIPC:</b><br>{md_text}</div>"
        self.chat_history.append(html)

    def append_system_message(self, text):
        html = f"<div style='margin-bottom: 5px; color:#888888; font-style: italic;'>[System]: {text}</div>"
        self.chat_history.append(html)

    def update_tokens(self, count):
        self.token_lbl.setText(f"Tokens Used: {count}")
