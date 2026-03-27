import os
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QTabWidget, QDialog, QVBoxLayout,
    QLabel, QCheckBox, QPushButton, QHBoxLayout, QMessageBox, QFileDialog,
    QTreeView, QFileSystemModel, QWidget
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl

from config import config_instance
from ui.chat_widget import ChatWidget
from ui.editor_browser import BrowserWidget, MarkdownEditor, RichTextEditor
from agent import AgentThread
from summarizer import SummarizerThread

class FileExplorerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.tree = QTreeView()
        self.model = QFileSystemModel()
        self.model.setRootPath(config_instance.workspace)
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(config_instance.workspace))
        
        # Hide extra columns for a cleaner look
        self.tree.setColumnHidden(1, True)
        self.tree.setColumnHidden(2, True)
        self.tree.setColumnHidden(3, True)
        self.tree.setHeaderHidden(True)
        
        self.btn_scan = QPushButton("Scan Workspace (AI)")
        
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #888; font-size: 11px;")
        
        layout.addWidget(self.tree)
        layout.addWidget(self.btn_scan)
        layout.addWidget(self.lbl_status)
        
        self.btn_scan.clicked.connect(self.run_scan)
        
    def run_scan(self):
        self.btn_scan.setEnabled(False)
        self.lbl_status.setText("Scanning...")
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
        
        layout = QVBoxLayout(self)
        
        lbl = QLabel(f"<b>The AI Agent wants to execute:</b><br><br>{action_string}")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        
        self.chk_auto = QCheckBox("Do not ask for confirmation for 1 minute")
        layout.addWidget(self.chk_auto)
        
        btn_layout = QHBoxLayout()
        self.btn_allow = QPushButton("Allow")
        self.btn_deny = QPushButton("Deny")
        self.btn_allow.clicked.connect(self.accept)
        self.btn_deny.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_allow)
        btn_layout.addWidget(self.btn_deny)
        
        layout.addLayout(btn_layout)
        self.setStyleSheet("QDialog { background-color: #1a1a1a; color: white; }")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AIPC - AI Assistant")
        self.resize(1200, 800)
        
        if config_instance.workspace == os.path.expanduser("~"):
            self.ask_workspace()
            
        self.setup_ui()
        
    def ask_workspace(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Working Folder for AIPC")
        if folder:
            config_instance.workspace = folder
            config_instance.save()
            
    def setup_ui(self):
        splitter = QSplitter(Qt.Horizontal)
        
        # Far Left Panel (Files)
        self.explorer_widget = FileExplorerWidget()
        
        # Left Panel (Chat)
        self.chat_widget = ChatWidget()
        self.chat_widget.send_message_signal.connect(self.on_user_message)
        
        # Right Panel (Tabs)
        self.tabs = QTabWidget()
        self.browser_tab = BrowserWidget()
        self.md_tab = MarkdownEditor()
        self.rt_tab = RichTextEditor()
        
        self.tabs.addTab(self.browser_tab, "Browser")
        self.tabs.addTab(self.md_tab, "Markdown Editor")
        self.tabs.addTab(self.rt_tab, "Word/Rich Text")
        
        splitter.addWidget(self.explorer_widget)
        splitter.addWidget(self.chat_widget)
        splitter.addWidget(self.tabs)
        splitter.setSizes([200, 400, 600])
        
        self.setCentralWidget(splitter)
        
        self.statusBar().showMessage(f"Working Folder: {config_instance.workspace}")

    @Slot(str)
    def on_user_message(self, text):
        self.agent_thread = AgentThread(text)
        self.agent_thread.chat_response_signal.connect(self.chat_widget.append_ai_message)
        self.agent_thread.system_msg_signal.connect(self.chat_widget.append_system_message)
        self.agent_thread.token_usage_signal.connect(self.chat_widget.update_tokens)
        self.agent_thread.approval_request_signal.connect(self.on_approval_request)
        
        self.chat_widget.append_system_message("Thinking...")
        self.agent_thread.start()
        
    @Slot(str)
    def on_approval_request(self, action_string):
        dlg = ApprovalDialog(action_string, self)
        result = dlg.exec()
        approved = (result == QDialog.Accepted)
        dont_ask_again = dlg.chk_auto.isChecked()
        
        if self.agent_thread and self.agent_thread.isRunning():
            self.agent_thread.set_approval_result(approved, dont_ask_again)
