from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QWidget, QListWidget,
    QListWidgetItem, QStackedWidget, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QComboBox, QFormLayout, QFileDialog, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QSize
from config import config_instance
import httpx


def _section_title(text):
    lbl = QLabel(text)
    lbl.setObjectName("settings_section_title")
    return lbl


def _divider():
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setObjectName("settings_divider")
    return line


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AIPC Settings")
        self.setMinimumSize(780, 600)
        self.setModal(True)
        self.setObjectName("settings_dialog")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("settings_sidebar")
        self.sidebar.setFixedWidth(200)
        self.sidebar.setSpacing(2)

        pages = [
            ("\u2699\ufe0f", "General"),
            ("\ud83e\udde0", "AI Engine"),
            ("\ud83d\udc41\ufe0f", "Vision AI"),
            ("\ud83d\udcca", "Statistics"),
        ]
        for emoji, name in pages:
            item = QListWidgetItem(f"  {emoji}   {name}")
            item.setSizeHint(QSize(180, 48))
            self.sidebar.addItem(item)
        self.sidebar.setCurrentRow(0)

        # Pages
        self.stack = QStackedWidget()
        self.stack.addWidget(self._page_general())
        self.stack.addWidget(self._page_ai_engine())
        self.stack.addWidget(self._page_vision())
        self.stack.addWidget(self._page_stats())
        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)

        # Right panel
        right_panel = QWidget()
        right_panel.setObjectName("settings_right")
        rl = QVBoxLayout(right_panel)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(self.stack, stretch=1)

        btn_bar = QWidget()
        btn_bar.setObjectName("settings_btn_bar")
        bl = QHBoxLayout(btn_bar)
        bl.setContentsMargins(20, 12, 20, 12)
        bl.setSpacing(10)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("secondary_btn")
        self.btn_cancel.setFixedWidth(100)
        self.btn_save = QPushButton("\u2714  Save Settings")
        self.btn_save.setObjectName("primary_btn")
        self.btn_save.setFixedWidth(150)
        bl.addStretch()
        bl.addWidget(self.btn_cancel)
        bl.addWidget(self.btn_save)
        rl.addWidget(btn_bar)

        root.addWidget(self.sidebar)
        root.addWidget(right_panel, stretch=1)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self._save_and_close)
        self._load_config()

    def _page_general(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)
        layout.addWidget(_section_title("General Configuration"))
        layout.addWidget(_divider())

        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignRight)

        workspace_row = QHBoxLayout()
        self.inp_workspace = QLineEdit()
        self.inp_workspace.setPlaceholderText("/path/to/workspace")
        btn_browse = QPushButton("\ud83d\udcc2  Browse")
        btn_browse.setFixedWidth(110)
        btn_browse.clicked.connect(self._browse_workspace)
        workspace_row.addWidget(self.inp_workspace)
        workspace_row.addWidget(btn_browse)
        workspace_w = QWidget()
        workspace_w.setLayout(workspace_row)
        form.addRow("Workspace:", workspace_w)

        self.inp_instructions = QPlainTextEdit()
        self.inp_instructions.setPlaceholderText("System instructions for the AI agent...")
        self.inp_instructions.setFixedHeight(140)
        form.addRow("Custom\nInstructions:", self.inp_instructions)

        layout.addLayout(form)
        layout.addStretch()
        return w

    def _page_ai_engine(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)
        layout.addWidget(_section_title("AI Engine & Models"))
        layout.addWidget(_divider())

        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignRight)

        self.inp_llm_host = QLineEdit()
        self.inp_llm_host.setPlaceholderText("http://localhost:11434/v1")
        form.addRow("LLM Host URL:", self.inp_llm_host)
        self.inp_api_key = QLineEdit()
        self.inp_api_key.setPlaceholderText("sk-... or AIza...")
        self.inp_api_key.setEchoMode(QLineEdit.Password)
        form.addRow("API Key:", self.inp_api_key)

        # Model Input & Scanner
        model_row = QHBoxLayout()
        self.inp_model = QLineEdit()
        self.inp_model.setPlaceholderText("llama3, mistral, gemma3, etc.")
        self.btn_scan_models = QPushButton("\ud83d\udd0d Scan Server")
        self.btn_scan_models.setObjectName("scan_server_btn")
        self.btn_scan_models.clicked.connect(self._scan_models)
        model_row.addWidget(self.inp_model)
        model_row.addWidget(self.btn_scan_models)
        mw = QWidget()
        mw.setLayout(model_row)
        form.addRow("Model Name:", mw)

        layout.addLayout(form)

        # List of models found
        list_lbl = QLabel("Available models on server:")
        list_lbl.setStyleSheet("color:#9ba3b4; font-size:12px; margin-top:10px;")
        layout.addWidget(list_lbl)

        self.model_list = QListWidget()
        self.model_list.setObjectName("model_list")
        self.model_list.setFixedHeight(120)
        self.model_list.itemClicked.connect(
            lambda item: self.inp_model.setText(item.text().split(" ")[0])
        )
        layout.addWidget(self.model_list)

        hint = QLabel("API Key is used for cloud models (Google Gemini, OpenAI). Leave blank for local Ollama.")
        hint.setObjectName("settings_hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()
        return w

    def _page_vision(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)
        layout.addWidget(_section_title("Vision AI (Image Detection)"))
        layout.addWidget(_divider())

        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignRight)

        self.combo_vision_provider = QComboBox()
        self.combo_vision_provider.addItems(["google", "openai", "none"])
        form.addRow("Vision Provider:", self.combo_vision_provider)

        self.inp_vision_model = QLineEdit()
        self.inp_vision_model.setPlaceholderText("gemini-1.5-flash  or  llava")
        form.addRow("Vision Model:", self.inp_vision_model)

        hint = QLabel(
            "google  -> Google Gemini API (API Key required above).\n"
            "openai  -> OpenAI-compatible vision model on your LLM host (e.g. llava via Ollama).\n"
            "none    -> Disables vision / screenshot tools."
        )
        hint.setObjectName("settings_hint")
        hint.setWordWrap(True)

        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addStretch()
        return w

    def _page_stats(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)
        layout.addWidget(_section_title("Token Usage Statistics"))
        layout.addWidget(_divider())

        self.lbl_tokens = QLabel()
        self.lbl_tokens.setObjectName("token_stat")
        self.lbl_tokens.setAlignment(Qt.AlignCenter)
        self._refresh_token_label()

        btn_reset = QPushButton("\ud83d\uddd1\ufe0f  Reset Token Counter")
        btn_reset.setObjectName("danger_btn")
        btn_reset.setFixedWidth(220)
        btn_reset.clicked.connect(self._reset_tokens)

        layout.addStretch()
        layout.addWidget(self.lbl_tokens, alignment=Qt.AlignCenter)
        layout.addSpacing(24)
        layout.addWidget(btn_reset, alignment=Qt.AlignCenter)
        layout.addStretch()
        return w

    def _scan_models(self):
        self.btn_scan_models.setText("Scanning...")
        self.btn_scan_models.setEnabled(False)
        self.model_list.clear()
        import threading
        def _fetch():
            host = self.inp_llm_host.text().strip()
            # If standard OpenAI compat URL, derive base
            if host.endswith("/v1"):
                base = host[:-3]
            else:
                base = host
            try:
                # specifically target Ollama tags endpoint
                res = httpx.get(f"{base}/api/tags", timeout=5)
                res.raise_for_status()
                models = [m["name"] for m in res.json().get("models", [])]
                self._populate_list(models)
            except Exception as e:
                self._populate_list([f"Error: {e}"])
        threading.Thread(target=_fetch, daemon=True).start()

    def _populate_list(self, items):
        def _update():
            self.model_list.clear()
            self.model_list.addItems(items)
            self.btn_scan_models.setText("\ud83d\udd0d Scan Server")
            self.btn_scan_models.setEnabled(True)
        # Assuming QMetaObject.invokeMethod handles cross-thread UI
        from PySide6.QtCore import QMetaObject, Q_ARG
        QMetaObject.invokeMethod(self, "_trigger_list_update", Qt.QueuedConnection, Q_ARG(list, items))

    from PySide6.QtCore import Slot
    @Slot(list)
    def _trigger_list_update(self, items):
        self.model_list.clear()
        self.model_list.addItems(items)
        self.btn_scan_models.setText("\ud83d\udd0d Scan Server")
        self.btn_scan_models.setEnabled(True)

    def _browse_workspace(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Workspace Folder")
        if folder:
            self.inp_workspace.setText(folder)

    def _refresh_token_label(self):
        n = config_instance.total_tokens_used
        self.lbl_tokens.setText(f"Total tokens used\n\n{n:,}")

    def _reset_tokens(self):
        config_instance.reset_tokens()
        self._refresh_token_label()

    def _load_config(self):
        self.inp_workspace.setText(config_instance.workspace)
        self.inp_instructions.setPlainText(config_instance.custom_instructions)
        self.inp_llm_host.setText(config_instance.llm_host)
        self.inp_model.setText(config_instance.model)
        self.inp_api_key.setText(config_instance.api_key)
        idx = self.combo_vision_provider.findText(config_instance.vision_provider)
        if idx >= 0:
            self.combo_vision_provider.setCurrentIndex(idx)
        self.inp_vision_model.setText(config_instance.vision_model)

    def _save_and_close(self):
        config_instance.workspace           = self.inp_workspace.text().strip()
        config_instance.custom_instructions = self.inp_instructions.toPlainText().strip()
        config_instance.llm_host            = self.inp_llm_host.text().strip()
        config_instance.model               = self.inp_model.text().strip()
        config_instance.api_key             = self.inp_api_key.text().strip()
        config_instance.vision_provider     = self.combo_vision_provider.currentText()
        config_instance.vision_model        = self.inp_vision_model.text().strip()
        config_instance.save()
        self.accept()
