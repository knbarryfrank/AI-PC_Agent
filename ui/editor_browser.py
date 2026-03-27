from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPlainTextEdit, QTextBrowser, QPushButton, QLineEdit, QLabel, QFrame,
    QSizePolicy
)
from PySide6.QtCore import Signal, QTimer, Qt, QSize
import markdown2

# Fixed resolution that AI agent will always see
AI_BROWSER_WIDTH  = 1280
AI_BROWSER_HEIGHT = 720

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineSettings
    from PySide6.QtCore import QUrl
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False


class BrowserWidget(QWidget):
    """In-app Chromium browser with fixed AI viewport + Takeover Mode."""
    page_text_ready = Signal(str)

    def __init__(self):
        super().__init__()
        self.takeover_active = False
        self._overlay_opacity = 1.0
        self._overlay_dir = -1
        self._overlay_anim_timer = QTimer(self)
        self._overlay_anim_timer.timeout.connect(self._pulse_overlay)
        
        self.is_thread_locked = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Toolbar ─────────────────────────────────────────────────────────
        toolbar = QWidget()
        toolbar.setObjectName("browser_toolbar")
        toolbar.setFixedHeight(48)
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(8, 6, 8, 6)
        tl.setSpacing(5)

        self.btn_back    = self._nav_btn("\u25c4", "Back")
        self.btn_forward = self._nav_btn("\u25ba", "Forward")
        self.btn_reload  = self._nav_btn("\u21bb", "Reload")
        self.btn_home    = self._nav_btn("\u2302", "Home")

        self.url_bar = QLineEdit()
        self.url_bar.setObjectName("url_bar")
        self.url_bar.setPlaceholderText("Enter URL or search\u2026")

        self.go_btn = QPushButton("Go")
        self.go_btn.setObjectName("go_btn")
        self.go_btn.setFixedWidth(52)

        # Resolution badge
        self.res_badge = QLabel(f"{AI_BROWSER_WIDTH}\xd7{AI_BROWSER_HEIGHT}")
        self.res_badge.setObjectName("res_badge")
        self.res_badge.setToolTip("Fixed AI viewport resolution")
        self.res_badge.setFixedWidth(78)

        self.takeover_btn = QPushButton("\u26a1 AI Takeover")
        self.takeover_btn.setObjectName("takeover_btn")
        self.takeover_btn.setCheckable(True)
        self.takeover_btn.setFixedWidth(130)
        self.takeover_btn.setFixedHeight(34)
        self.takeover_btn.clicked.connect(self._toggle_takeover)

        tl.addWidget(self.btn_back)
        tl.addWidget(self.btn_forward)
        tl.addWidget(self.btn_reload)
        tl.addWidget(self.btn_home)
        tl.addWidget(self.url_bar, stretch=1)
        tl.addWidget(self.go_btn)
        tl.addWidget(self.res_badge)
        tl.addWidget(self.takeover_btn)
        layout.addWidget(toolbar)

        # ── Takeover Overlay Banner ──────────────────────────────────────────
        self.overlay_banner = QLabel("\u26a1  AI IS IN CONTROL  \u26a1")
        self.overlay_banner.setObjectName("overlay_banner")
        self.overlay_banner.setAlignment(Qt.AlignCenter)
        self.overlay_banner.setFixedHeight(32)
        self.overlay_banner.hide()
        layout.addWidget(self.overlay_banner)

        # ── WebView container (fixed size for consistent AI screenshots) ─────
        self.webview_container = QWidget()
        self.webview_container.setStyleSheet("background:#000;")
        container_layout = QVBoxLayout(self.webview_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.webview_container, stretch=1)

        if HAS_WEBENGINE:
            self.webview = QWebEngineView()
            # Fix viewport so AI always sees exactly 1280x720
            self.webview.setMinimumSize(AI_BROWSER_WIDTH, AI_BROWSER_HEIGHT)
            self.webview.setMaximumSize(AI_BROWSER_WIDTH, AI_BROWSER_HEIGHT)
            self.webview.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

            # Enable JavaScript and useful features
            settings = self.webview.page().settings()
            settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)

            self.webview.setUrl(QUrl("https://google.com"))
            container_layout.addWidget(self.webview)

            self.go_btn.clicked.connect(self.navigate)
            self.url_bar.returnPressed.connect(self.navigate)
            self.btn_back.clicked.connect(self.webview.back)
            self.btn_forward.clicked.connect(self.webview.forward)
            self.btn_reload.clicked.connect(self.webview.reload)
            self.btn_home.clicked.connect(lambda: self.navigate_to("https://google.com"))
            self.webview.urlChanged.connect(
                lambda url: self.url_bar.setText(url.toString())
            )
        else:
            err = QTextBrowser()
            err.setHtml(
                "<h2 style='color:#e05c5c'>PySide6-WebEngine is missing</h2>"
                "<p>Run: <code>pip install PySide6-WebEngine</code></p>"
            )
            container_layout.addWidget(err)

    def _nav_btn(self, symbol, tip):
        b = QPushButton(symbol)
        b.setObjectName("nav_btn")
        b.setFixedSize(32, 32)
        b.setToolTip(tip)
        return b

    # ── Navigation ────────────────────────────────────────────────────────────
    def navigate(self):
        if HAS_WEBENGINE:
            url = self.url_bar.text().strip()
            if not url.startswith("http"):
                url = "https://" + url
            self.webview.setUrl(QUrl(url))

    # ── AI Control API ────────────────────────────────────────────────────────
    def navigate_to(self, url: str):
        if not HAS_WEBENGINE:
            return "Browser not available."
        if not url.startswith("http"):
            url = "https://" + url
        self.url_bar.setText(url)
        self.webview.setUrl(QUrl(url))
        return f"Navigating to {url}"

    def click_element(self, selector: str):
        if not HAS_WEBENGINE:
            return "Browser not available."
        safe_sel = selector.replace("'", "\\'")
        js = (
            "(function(){"
            f"var el=document.querySelector('{safe_sel}');"
            "if(el){"
            "  var rect = el.getBoundingClientRect();"
            "  var c = document.getElementById('aipc-cursor');"
            "  if(!c){"
            "    c = document.createElement('div');"
            "    c.id = 'aipc-cursor';"
            "    c.style.cssText = 'position:fixed;width:20px;height:20px;background:rgba(255,50,50,0.8);border-radius:50%;z-index:999999;transition:all 0.5s cubic-bezier(0.25, 1, 0.5, 1);pointer-events:none;box-shadow:0 0 10px rgba(255,0,0,0.5);';"
            "    document.body.appendChild(c);"
            "  }"
            "  c.style.left = (rect.left + rect.width/2 - 10) + 'px';"
            "  c.style.top = (rect.top + rect.height/2 - 10) + 'px';"
            f" setTimeout(() => {{ el.dispatchEvent(new MouseEvent('mousedown',{{bubbles:true}})); el.dispatchEvent(new MouseEvent('mouseup',{{bubbles:true}})); el.click(); }}, 600);"
            "  return 'clicked';"
            "}"
            "return 'element not found';"
            "})();"
        )
        self.webview.page().runJavaScript(js)
        return f"Clicked: {selector}"

    def type_text(self, selector: str, text: str):
        if not HAS_WEBENGINE:
            return "Browser not available."
        safe_sel = selector.replace("'", "\\'")
        safe_text = text.replace("'", "\\'")
        js = (
            "(function(){"
            f"var el=document.querySelector('{safe_sel}');"
            "if(el){"
            "  var rect = el.getBoundingClientRect();"
            "  var c = document.getElementById('aipc-cursor');"
            "  if(!c){"
            "    c = document.createElement('div');"
            "    c.id = 'aipc-cursor';"
            "    c.style.cssText = 'position:fixed;width:20px;height:20px;background:rgba(255,50,50,0.8);border-radius:50%;z-index:999999;transition:all 0.5s cubic-bezier(0.25, 1, 0.5, 1);pointer-events:none;box-shadow:0 0 10px rgba(255,0,0,0.5);';"
            "    document.body.appendChild(c);"
            "  }"
            "  c.style.left = (rect.left + rect.width/2 - 10) + 'px';"
            "  c.style.top = (rect.top + rect.height/2 - 10) + 'px';"
            f" setTimeout(() => {{ el.focus(); el.value='{safe_text}'; el.dispatchEvent(new Event('input',{{bubbles:true}})); el.dispatchEvent(new Event('change',{{bubbles:true}})); }}, 600);"
            "  return 'typed';"
            "}"
            "return 'element not found';"
            "})();"
        )
        self.webview.page().runJavaScript(js)
        return f"Typed into {selector}: {text}"

    def press_enter_in(self, selector: str):
        if not HAS_WEBENGINE:
            return "Browser not available."
        safe_sel = selector.replace("'", "\\'")
        js = (
            "(function(){"
            f"var el=document.querySelector('{safe_sel}');"
            "if(el){"
            "el.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13,bubbles:true}));"
            "el.dispatchEvent(new KeyboardEvent('keyup',{key:'Enter',keyCode:13,bubbles:true}));"
            "return 'enter pressed';"
            "}"
            "return 'element not found';"
            "})();"
        )
        self.webview.page().runJavaScript(js)
        return f"Pressed Enter in {selector}"

    def smart_search(self, query: str):
        """Unified search logic that finds a box and submits."""
        if not HAS_WEBENGINE:
            return "Browser not available."
        js = (
            "(function(){"
            "  var selectors = ['input[name=\"q\"]', 'input[type=\"search\"]', 'input[placeholder*=\"Search\"]', 'input[type=\"text\"]', 'textarea'];"
            "  for(var s of selectors){"
            "    var el = document.querySelector(s);"
            "    if(el && el.offsetParent !== null){"
            "      el.focus();"
            "      el.value = '" + query.replace("'", "\\'") + "';"
            "      el.dispatchEvent(new Event('input', {bubbles:true}));"
            "      el.dispatchEvent(new Event('change', {bubbles:true}));"
            "      setTimeout(() => {"
            "        el.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', keyCode:13, bubbles:true}));"
            "        el.dispatchEvent(new KeyboardEvent('keyup', {key:'Enter', keyCode:13, bubbles:true}));"
            "      }, 100);"
            "      return 'found and submitted';"
            "    }"
            "  }"
            "  return 'no search box found';"
            "})();"
        )
        self.webview.page().runJavaScript(js)
        return f"Search for '{query}' initiated."

    def capture_screenshot(self):
        """Capture fixed-resolution browser screenshot for AI vision."""
        if not HAS_WEBENGINE:
            return None
        return self.webview.grab()

    def get_page_text(self):
        if not HAS_WEBENGINE:
            self.page_text_ready.emit("Browser not available.")
            return
        js = "document.body ? document.body.innerText.substring(0,5000) : '';"
        self.webview.page().runJavaScript(js, lambda r: self.page_text_ready.emit(r or ""))

    def set_thread_lock(self, locked: bool):
        """Called by MainWindow when the AI is thinking to prevent user clicks."""
        self.is_thread_locked = locked
        self._update_interaction_state()

    def _update_interaction_state(self):
        """Centralized logic to decide if the browser should be locked for the user."""
        # Lock if either AI is thinking OR Takeover (auto-approve) mode is active
        should_lock = self.is_thread_locked or self.takeover_active
        
        if should_lock:
            self.webview.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self.webview.setFocusPolicy(Qt.NoFocus)
        else:
            self.webview.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            self.webview.setFocusPolicy(Qt.StrongFocus)

    # ── Takeover Mode ─────────────────────────────────────────────────────────
    def _toggle_takeover(self):
        self.takeover_active = self.takeover_btn.isChecked()
        self._update_interaction_state()
        if self.takeover_active:
            self.takeover_btn.setText("\U0001f6d1 Stop Takeover")
            self.overlay_banner.show()
            self._overlay_anim_timer.start(80)
        else:
            self.takeover_btn.setText("\u26a1 AI Takeover")
            self.overlay_banner.hide()
            self._overlay_anim_timer.stop()

    def _pulse_overlay(self):
        self._overlay_opacity += self._overlay_dir * 0.05
        if self._overlay_opacity <= 0.3:
            self._overlay_dir = 1
        elif self._overlay_opacity >= 1.0:
            self._overlay_dir = -1
        op = max(0.3, min(1.0, self._overlay_opacity))
        self.overlay_banner.setStyleSheet(
            f"background: rgba(158,42,42,{op:.2f}); color: #ff9090; "
            "font-weight: bold; font-size: 12px; letter-spacing: 3px;"
        )


class MarkdownEditor(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Write Markdown here\u2026")
        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)
        layout.addWidget(self.text_edit)
        layout.addWidget(self.preview)
        self.text_edit.textChanged.connect(self.update_preview)

    def update_preview(self):
        md = self.text_edit.toPlainText()
        html = markdown2.markdown(md, extras=["fenced-code-blocks", "tables"])
        self.preview.setHtml(
            f"<html><body style='color:#c8cfdd;background:#0b0d11;"
            f"font-family:Segoe UI,sans-serif;padding:16px;line-height:1.6'>{html}</body></html>"
        )


class RichTextEditor(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        def mb(label, tip):
            b = QPushButton(label)
            b.setToolTip(tip)
            b.setFixedSize(32, 32)
            return b

        self.btn_bold   = mb("B", "Bold")
        self.btn_italic = mb("I", "Italic")
        self.btn_under  = mb("U", "Underline")
        self.btn_strike = mb("S", "Strikethrough")
        for b in (self.btn_bold, self.btn_italic, self.btn_under, self.btn_strike):
            toolbar.addWidget(b)
        toolbar.addStretch()
        self.editor = QTextEdit()
        self.editor.setPlaceholderText("Rich text document\u2026")
        layout.addLayout(toolbar)
        layout.addWidget(self.editor)

        self.btn_bold.clicked.connect(
            lambda: self.editor.setFontWeight(75 if self.editor.fontWeight() != 75 else 50)
        )
        self.btn_italic.clicked.connect(
            lambda: self.editor.setFontItalic(not self.editor.fontItalic())
        )
        self.btn_under.clicked.connect(
            lambda: self.editor.setFontUnderline(not self.editor.fontUnderline())
        )
        self.btn_strike.clicked.connect(self._toggle_strikeout)

    def _toggle_strikeout(self):
        from PySide6.QtGui import QTextCharFormat
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(not self.editor.currentCharFormat().fontStrikeOut())
        self.editor.mergeCurrentCharFormat(fmt)
