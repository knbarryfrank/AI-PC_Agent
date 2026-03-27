from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
    QPlainTextEdit, QTextBrowser, QPushButton, QLineEdit
)
import markdown2

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtCore import QUrl
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

class BrowserWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.nav_layout = QHBoxLayout()
        self.url_bar = QLineEdit()
        self.go_btn = QPushButton("Go")
        self.nav_layout.addWidget(self.url_bar)
        self.nav_layout.addWidget(self.go_btn)
        
        layout.addLayout(self.nav_layout)
        
        if HAS_WEBENGINE:
            self.webview = QWebEngineView()
            self.webview.setUrl(QUrl("https://google.com"))
            layout.addWidget(self.webview)
            
            self.go_btn.clicked.connect(self.navigate)
            self.url_bar.returnPressed.connect(self.navigate)
        else:
            self.error_label = QTextBrowser()
            self.error_label.setHtml("<h1>PySide6-WebEngine is missing</h1><p>Please install it via <code>pip install PySide6-WebEngine</code>.</p>")
            layout.addWidget(self.error_label)

    def navigate(self):
        if HAS_WEBENGINE:
            url = self.url_bar.text()
            if not url.startswith("http"):
                url = "https://" + url
            self.webview.setUrl(QUrl(url))

class MarkdownEditor(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.text_edit = QPlainTextEdit()
        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)
        
        layout.addWidget(self.text_edit)
        layout.addWidget(self.preview)
        
        self.text_edit.textChanged.connect(self.update_preview)
        
    def update_preview(self):
        md = self.text_edit.toPlainText()
        html = markdown2.markdown(md)
        self.preview.setHtml(f"<html><body style='color:#e0e0e0; background-color:#1a1a1a;'>{html}</body></html>")

class RichTextEditor(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.toolbar_layout = QHBoxLayout()
        self.btn_bold = QPushButton("B")
        self.btn_bold.clicked.connect(self.make_bold)
        self.btn_italic = QPushButton("I")
        self.btn_italic.clicked.connect(self.make_italic)
        
        self.toolbar_layout.addWidget(self.btn_bold)
        self.toolbar_layout.addWidget(self.btn_italic)
        self.toolbar_layout.addStretch()
        
        self.editor = QTextEdit()
        
        layout.addLayout(self.toolbar_layout)
        layout.addWidget(self.editor)
        
    def make_bold(self):
        self.editor.setFontWeight(75 if self.editor.fontWeight() != 75 else 50)
        
    def make_italic(self):
        self.editor.setFontItalic(not self.editor.fontItalic())
