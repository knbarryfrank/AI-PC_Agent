import os
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QTabWidget, QDialog, QVBoxLayout,
    QLabel, QCheckBox, QPushButton, QHBoxLayout, QMessageBox, QFileDialog,
    QTreeView, QFileSystemModel, QWidget, QLineEdit, QMenu, QAbstractItemView,
    QStyledItemDelegate, QSizePolicy
)
from PySide6.QtCore import Qt, Slot, QSortFilterProxyModel, QModelIndex
from PySide6.QtGui import QPalette, QColor, QFont

from config import config_instance
from ui.chat_widget import ChatWidget
from ui.editor_browser import BrowserWidget, MarkdownEditor, RichTextEditor
from ui.settings_dialog import SettingsDialog
from agent import AgentThread
from summarizer import SummarizerThread


# ---------- File-type Emoji Delegate ----------
FILE_ICONS = {
    ".py":   "🐍",
    ".md":   "📝",
    ".json": "📋",
    ".js":   "🟨",
    ".ts":   "🔷",
    ".html": "🌐",
    ".css":  "🎨",
    ".txt":  "📄",
    ".png":  "🖼️",
    ".jpg":  "🖼️",
    ".exe":  "⚙️",
    ".zip":  "🗜️",
    ".sh":   "💻",
    ".bat":  "💻",
    ".log":  "🗒️",
}

class FileIconDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        if not index.isValid():
            return
        model = index.model()
        source_index = index
        while hasattr(model, 'mapToSource'):
            source_index = model.mapToSource(source_index)
            model = model.sourceModel()
        if hasattr(model, 'fileInfo'):
            info = model.fileInfo(source_index)
            if info.isDir():
                option.text = "📁  " + info.fileName()
            else:
                ext = "." + info.suffix().lower() if info.suffix() else ""
                icon_ch = FILE_ICONS.get(ext, "📄")
                option.text = icon_ch + "  " + info.fileName()


class FileExplorerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("explorer_panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(44)
        hdr.setStyleSheet("background:#0e1018; border-bottom:1px solid #1e2435;")
        hdr_l = QHBoxLayout(hdr)
        hdr_l.setContentsMargins(16, 0, 16, 0)
        title = QLabel("WORKSPACE")
        title.setObjectName("panel_title")
        hdr_l.addWidget(title)
        hdr_l.addStretch()
        
        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setFixedSize(28, 28)
        self.btn_settings.setObjectName("nav_btn")
        self.btn_settings.setToolTip("Change workspace folder")
        self.btn_settings.clicked.connect(self._change_workspace)
        hdr_l.addWidget(self.btn_settings)
        layout.addWidget(hdr)

        # Search
        search_w = QWidget()
        sl = QVBoxLayout(search_w)
        sl.setContentsMargins(12, 12, 12, 6)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Filter files...")
        self.search_bar.setObjectName("file_search_bar")
        self.search_bar.textChanged.connect(self._filter_files)
        sl.addWidget(self.search_bar)
        layout.addWidget(search_w)

        # Tree
        self.source_model = QFileSystemModel()
        self.source_model.setRootPath(config_instance.workspace)

        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.source_model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setRecursiveFilteringEnabled(True)

        self.tree = QTreeView()
        self.tree.setObjectName("file_tree")
        self.tree.setModel(self.proxy_model)
        source_root = self.source_model.index(config_instance.workspace)
        proxy_root = self.proxy_model.mapFromSource(source_root)
        self.tree.setRootIndex(proxy_root)
        self.tree.setColumnHidden(1, True)
        self.tree.setColumnHidden(2, True)
        self.tree.setColumnHidden(3, True)
        self.tree.setHeaderHidden(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(16)
        self.tree.setItemDelegate(FileIconDelegate(self.tree))
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.tree, stretch=1)

        # Scan Button
        btn_w = QWidget()
        btn_w.setStyleSheet("background:#0e1018; border-top:1px solid #1e2435;")
        btn_l = QVBoxLayout(btn_w)
        btn_l.setContentsMargins(12, 10, 12, 10)
        self.btn_scan = QPushButton("🤖 Scan Workspace")
        self.btn_scan.setObjectName("scan_btn")
        self.btn_scan.clicked.connect(self.run_scan)
        btn_l.addWidget(self.btn_scan)
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #6b7280; font-size: 11px;")
        btn_l.addWidget(self.lbl_status)
        layout.addWidget(btn_w)

    def _filter_files(self, text):
        self.proxy_model.setFilterWildcard(f"*{text}*")
        if text:
            self.tree.expandAll()
        else:
            self.tree.collapseAll()

    def _change_workspace(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Workspace Folder")
        if folder:
            config_instance.workspace = folder
            config_instance.save()
            self.source_model.setRootPath(folder)
            source_root = self.source_model.index(folder)
            proxy_root = self.proxy_model.mapFromSource(source_root)
            self.tree.setRootIndex(proxy_root)
            self.lbl_status.setText(f"Workspace updated")

    def _show_context_menu(self, pos):
        proxy_index = self.tree.indexAt(pos)
        if not proxy_index.isValid():
            return
        source_index = self.proxy_model.mapToSource(proxy_index)
        file_path = self.source_model.filePath(source_index)

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#1c2030; color:#e8eaf0; border:1px solid #252b3b; border-radius:6px; }"
            "QMenu::item { padding: 6px 20px; }"
            "QMenu::item:selected { background:#5b8af5; border-radius:4px; }"
        )
        act_rename = menu.addAction("✏️  Rename")
        menu.addSeparator()
        act_delete = menu.addAction("🗑️  Delete")

        action = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if action == act_delete:
            reply = QMessageBox.question(
                self, "Confirm Delete",
                f"Delete: {os.path.basename(file_path)}?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                try:
                    import send2trash
                    send2trash.send2trash(file_path)
                except ImportError:
                    os.remove(file_path) if os.path.isfile(file_path) else os.rmdir(file_path)
        elif action == act_rename:
            from PySide6.QtWidgets import QInputDialog
            new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=os.path.basename(file_path))
            if ok and new_name:
                new_path = os.path.join(os.path.dirname(file_path), new_name)
                os.rename(file_path, new_path)

    def run_scan(self):
        self.btn_scan.setEnabled(False)
        self.lbl_status.setText("Scanning workspace...")
        self.thread = SummarizerThread()
        self.thread.progress_signal.connect(self.lbl_status.setText)
        self.thread.finished_signal.connect(self.scan_finished)
        self.thread.start()

    def scan_finished(self):
        self.btn_scan.setEnabled(True)
        self.lbl_status.setText("Scan complete.")


class ApprovalDialog(QDialog):
    def __init__(self, action_string, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Action Requires Approval")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setObjectName("approval_dialog")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        lbl = QLabel(f"<div style='margin-bottom:8px;color:#9ba3b4'>The AI Agent requests to execute:</div>"
                     f"<div id='approval_action'>{action_string}</div>")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        
        self.chk_auto = QCheckBox("Auto-approve similar actions for 1 minute")
        layout.addWidget(self.chk_auto)
        
        btn_layout = QHBoxLayout()
        self.btn_allow = QPushButton("Allow")
        self.btn_allow.setObjectName("allow_btn")
        self.btn_deny = QPushButton("Deny")
        self.btn_deny.setObjectName("deny_btn")
        self.btn_allow.clicked.connect(self.accept)
        self.btn_deny.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_deny)
        btn_layout.addWidget(self.btn_allow)
        
        layout.addLayout(btn_layout)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AIPC - AI Assistant")
        self.resize(1340, 840)
        
        if config_instance.workspace == os.path.expanduser("~"):
            self.ask_workspace()
            
        self.setup_ui()
        
    def ask_workspace(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Working Folder for AIPC")
        if folder:
            config_instance.workspace = folder
            config_instance.save()
            
    def setup_ui(self):
        # Central widget wrapping header + splitter
        central = QWidget()
        central.setObjectName("central_widget")
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        # Header Title Bar
        header = QWidget()
        header.setObjectName("app_header")
        header.setFixedHeight(52)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)
        hl.setSpacing(12)

        logo_lbl = QLabel("AIPC")
        logo_lbl.setStyleSheet("color: #5b8af5; font-size: 20px; font-weight: 800; font-style: italic;")

        title_lbl = QLabel("Desktop Agent")
        title_lbl.setObjectName("app_title")

        self.lbl_model_badge = QLabel(config_instance.model)
        self.lbl_model_badge.setObjectName("model_badge")

        self.lbl_vision_badge = QLabel()
        self.lbl_vision_badge.setObjectName("vision_badge")
        self._refresh_header_badges()

        self.btn_settings_top = QPushButton("⚙  Settings")
        self.btn_settings_top.setObjectName("header_settings_btn")
        self.btn_settings_top.setFixedHeight(32)
        self.btn_settings_top.clicked.connect(self.open_settings)

        hl.addWidget(logo_lbl)
        hl.addWidget(title_lbl)
        hl.addSpacing(16)
        hl.addWidget(self.lbl_model_badge)
        hl.addWidget(self.lbl_vision_badge)
        hl.addStretch()
        hl.addWidget(self.btn_settings_top)
        central_layout.addWidget(header)

        # Main Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        self.explorer_widget = FileExplorerWidget()
        self.chat_widget = ChatWidget()
        self.chat_widget.send_message_signal.connect(self.on_user_message)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("main_tabs")
        self.browser_tab = BrowserWidget()
        self.md_tab = MarkdownEditor()
        self.rt_tab = RichTextEditor()

        self.tabs.addTab(self.browser_tab, "🌐  Browser")
        self.tabs.addTab(self.md_tab,      "📝  Markdown")
        self.tabs.addTab(self.rt_tab,      "📝  Rich Text")

        splitter.addWidget(self.explorer_widget)
        splitter.addWidget(self.chat_widget)
        splitter.addWidget(self.tabs)
        # Give more space to the browser to ensure the 1280px fixed width fits nicely
        splitter.setSizes([220, 360, 1300])

        central_layout.addWidget(splitter, stretch=1)
        self.setCentralWidget(central)

        self.statusBar().showMessage(f"Workspace: {config_instance.workspace}")

    def _refresh_header_badges(self):
        self.lbl_model_badge.setText(config_instance.model)
        vp = config_instance.vision_provider
        if vp == "google":
            self.lbl_vision_badge.setText("👁️ Gemini Vision")
        elif vp == "openai":
            self.lbl_vision_badge.setText("👁️ OpenAI Vision")
        else:
            self.lbl_vision_badge.setText("Vision OFF")
            self.lbl_vision_badge.setStyleSheet(
                "background: rgba(107,114,128,0.1); color: #6b7280; border: 1px solid rgba(107,114,128,0.3);"
                "border-radius: 12px; padding: 3px 12px; font-size: 11px;"
            )

    @Slot()
    def open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self._refresh_header_badges()
            self.statusBar().showMessage(f"Workspace: {config_instance.workspace}")

    @Slot(str)
    def on_user_message(self, text):
        self.agent_thread = AgentThread(text, browser_widget=self.browser_tab)
        # Lock interaction for this turn
        self.browser_tab.set_thread_lock(True)
        
        # Show specific notice if takeover (auto-approve) is on
        if self.browser_tab.takeover_active:
            self.chat_widget.append_system_message("\u26a1 AI TAKEOVER ACTIVE: Auto-approving all actions.")

        self.agent_thread.chat_response_signal.connect(self.chat_widget.append_ai_message)
        self.agent_thread.system_msg_signal.connect(self.chat_widget.append_system_message)
        self.agent_thread.token_usage_signal.connect(self.chat_widget.update_tokens)
        self.agent_thread.approval_request_signal.connect(self.on_approval_request)
        self.agent_thread.browser_action_signal.connect(self.on_browser_action)
        
        # Unlock thread (but respect Takeover button state) when done
        self.agent_thread.finished.connect(lambda: self.browser_tab.set_thread_lock(False))
        
        self.chat_widget.append_system_message("Thinking...")
        self.agent_thread.start()
        
    @Slot(str, dict)
    def on_browser_action(self, action, args):
        res = "Unknown browser action"
        if action == "navigate":
            res = self.browser_tab.navigate_to(args.get("url"))
        elif action == "click":
            res = self.browser_tab.click_element(args.get("selector"))
        elif action == "type":
            res = self.browser_tab.type_text(args.get("selector"), args.get("text"))
        elif action == "press_enter":
            res = self.browser_tab.press_enter_in(args.get("selector"))
        elif action == "search":
            res = self.browser_tab.smart_search(args.get("query"))
        elif action == "screenshot":
            pixmap = self.browser_tab.capture_screenshot()
            if pixmap:
                import tempfile
                tmp = tempfile.mktemp(suffix=".png")
                pixmap.save(tmp, "PNG")
                res = tmp
            else:
                res = None
        elif action == "read_page":
            self.browser_tab.page_text_ready.connect(self._browser_text_ready)
            self.browser_tab.get_page_text()
            return # exit early, async
            
        if self.agent_thread and self.agent_thread.isRunning():
            self.agent_thread.set_browser_result(res)
            
    def _browser_text_ready(self, text):
        self.browser_tab.page_text_ready.disconnect(self._browser_text_ready)
        if self.agent_thread and self.agent_thread.isRunning():
            self.agent_thread.set_browser_result(text)
        
    @Slot(str)
    def on_approval_request(self, action_string):
        dlg = ApprovalDialog(action_string, self)
        result = dlg.exec()
        approved = (result == QDialog.Accepted)
        dont_ask_again = dlg.chk_auto.isChecked()
        
        if self.agent_thread and self.agent_thread.isRunning():
            self.agent_thread.set_approval_result(approved, dont_ask_again)
