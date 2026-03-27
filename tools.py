import os
import time
from bs4 import BeautifulSoup
import httpx
from config import config_instance

class AgentTools:
    def __init__(self, ui_callback, browser_widget=None):
        self.ui_callback = ui_callback
        self.auto_approve_until = 0
        self.browser_widget = browser_widget  # BrowserWidget reference for AI control

    def get_workspace(self):
        return config_instance.workspace

    def check_approval(self, action_string):
        if time.time() < self.auto_approve_until:
            return True, "Auto-approved due to active 1-minute timeout."
        
        # This will block until user clicks Accept/Reject
        approved, dont_ask_again = self.ui_callback("approval_request", action_string)
        if approved and dont_ask_again:
            self.auto_approve_until = time.time() + 60
        return approved, ""

    def list_files(self):
        try:
            workspace = self.get_workspace()
            items = os.listdir(workspace)
            summary_path = os.path.join(workspace, ".aipc_cache", "file_index.json")
            cache = {}
            if os.path.exists(summary_path):
                import json
                try:
                    with open(summary_path, "r", encoding="utf-8") as f:
                        cache = json.load(f)
                except Exception:
                    pass
                    
            output = []
            for item in items:
                if item == ".aipc_cache" or item == "venv":
                    continue
                if item in cache:
                    output.append(f"{item} (Summary: {cache[item].get('summary')})")
                else:
                    output.append(item)
                    
            return f"Files in {workspace}:\n" + "\n".join(output)
        except Exception as e:
            return f"Error listing directory: {e}"

    def read_file(self, filename: str):
        path = os.path.join(self.get_workspace(), filename)
        if not path.startswith(self.get_workspace()):
            return "Error: Path escapes workspace."
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error reading file {filename}: {e}"

    def write_file(self, filename: str, content: str):
        path = os.path.join(self.get_workspace(), filename)
        if not path.startswith(self.get_workspace()):
            return "Error: Path escapes workspace."
        
        approved, msg = self.check_approval(f"Modify file: {filename}")
        if not approved:
            return "Execution rejected by user."

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Success. Wrote to {filename}"
        except Exception as e:
            return f"Error writing file {filename}: {e}"



    # --- Browser Control Tools ---
    def browser_navigate(self, url: str):
        """Navigate the in-app browser to a URL."""
        if not self.browser_widget:
            return "Browser widget not connected."
        self.ui_callback("system_msg", f"AI navigating browser to: {url}")
        return self.ui_callback("browser_action", {"action": "navigate", "args": {"url": url}})

    def browser_click(self, selector: str):
        """Click an element in the browser by CSS selector."""
        if not self.browser_widget:
            return "Browser widget not connected."
        if getattr(self.browser_widget, "takeover_active", False) == False:
            approved, _ = self.check_approval(f"Browser click: {selector}")
            if not approved:
                return "Rejected by user."
        self.ui_callback("system_msg", f"AI clicking browser element: {selector}")
        return self.ui_callback("browser_action", {"action": "click", "args": {"selector": selector}})

    def browser_type(self, selector: str, text: str):
        """Type text into a browser element by CSS selector."""
        if not self.browser_widget:
            return "Browser widget not connected."
        if getattr(self.browser_widget, "takeover_active", False) == False:
            approved, _ = self.check_approval(f"Browser type into {selector}: {text[:40]}")
            if not approved:
                return "Rejected by user."
        self.ui_callback("system_msg", f"AI typing into browser element: {selector}")
        return self.ui_callback("browser_action", {"action": "type", "args": {"selector": selector, "text": text}})

    def browser_press_enter(self, selector: str):
        """Press Enter in a browser element."""
        if not self.browser_widget:
            return "Browser widget not connected."
        if getattr(self.browser_widget, "takeover_active", False) == False:
            approved, _ = self.check_approval(f"Browser press Enter in: {selector}")
            if not approved:
                return "Rejected by user."
        self.ui_callback("system_msg", f"AI pressing Enter in: {selector}")
        return self.ui_callback("browser_action", {"action": "press_enter", "args": {"selector": selector}})

    def browser_read_page(self):
        """Read the current browser page text."""
        if not self.browser_widget:
            return "Browser widget not connected."
        self.ui_callback("system_msg", "AI reading current browser page...")
        return self.ui_callback("browser_action", {"action": "read_page", "args": {}})

    def browser_screenshot(self):
        """Take a screenshot of the current browser page. Returns base64 PNG string."""
        if not self.browser_widget:
            return "Browser widget not connected."
        self.ui_callback("system_msg", "AI capturing browser screenshot...")
        tmp = self.ui_callback("browser_action", {"action": "screenshot", "args": {}})
        if not tmp:
            return "Screenshot failed (browser unavailable)."
        import base64, os as _os
        try:
            with open(tmp, "rb") as f:
                data = base64.b64encode(f.read()).decode()
            return f"Screenshot captured. base64_png_length={len(data)}"
        finally:
            try:
                _os.remove(tmp)
            except Exception:
                pass

    def browser_vision_query(self, query: str):
        """Take a browser screenshot and ask the vision model about it.
        Uses Google Gemini (or OpenAI-compatible vision) to analyze the page image."""
        if not self.browser_widget:
            return "Browser widget not connected."
        self.ui_callback("system_msg", f"AI vision query: {query[:60]}...")
        tmp = self.ui_callback("browser_action", {"action": "screenshot", "args": {}})
        if not tmp:
            return "Screenshot failed."
        import os as _os
        try:
            return self._run_vision_query(tmp, query)
        finally:
            try:
                _os.remove(tmp)
            except Exception:
                pass

    def _run_vision_query(self, image_path: str, query: str) -> str:
        """Send image + query to the configured vision model and return the response."""
        provider = config_instance.vision_provider
        if provider == "google":
            try:
                import google.generativeai as genai
                from PIL import Image
                if not config_instance.api_key:
                    return "Google API key not set. Please configure it in AI Settings."
                genai.configure(api_key=config_instance.api_key)
                model = genai.GenerativeModel(config_instance.vision_model or "gemini-1.5-flash")
                img = Image.open(image_path)
                response = model.generate_content([query, img])
                return response.text
            except ImportError:
                return "google-generativeai or Pillow not installed. Run: pip install google-generativeai Pillow"
            except Exception as e:
                return f"Gemini vision error: {e}"
        elif provider == "openai":
            try:
                import base64, httpx as _httpx
                with open(image_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                payload = {
                    "model": config_instance.vision_model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": query},
                            {"type": "image_url",
                             "image_url": {"url": f"data:image/png;base64,{b64}"}}
                        ]
                    }]
                }
                headers = {"Content-Type": "application/json"}
                if config_instance.api_key:
                    headers["Authorization"] = f"Bearer {config_instance.api_key}"
                res = _httpx.post(
                    config_instance.llm_host.rstrip("/") + "/chat/completions",
                    json=payload, headers=headers, timeout=60
                )
                return res.json()["choices"][0]["message"]["content"]
            except Exception as e:
                return f"OpenAI vision error: {e}"
        else:
            return "Vision provider not configured. Please set it in AI Settings."

    def get_tool_definitions(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "Lists files in the user's workspace directory.",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Reads contents of a local file in the workspace.",
                    "parameters": {"type": "object", "properties": {"filename": {"type": "string"}}, "required": ["filename"]}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Writes or overwrites content to a file in the workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {"filename": {"type": "string"}, "content": {"type": "string"}},
                        "required": ["filename", "content"]
                    }
                }
            },

            {
                "type": "function",
                "function": {
                    "name": "browser_navigate",
                    "description": "Navigate the in-app browser to a URL.",
                    "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_click",
                    "description": "Click an element in the browser by CSS selector (e.g. 'input[name=q]').",
                    "parameters": {"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_type",
                    "description": "Type text into a browser element by CSS selector.",
                    "parameters": {
                        "type": "object",
                        "properties": {"selector": {"type": "string"}, "text": {"type": "string"}},
                        "required": ["selector", "text"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_press_enter",
                    "description": "Press Enter key in a browser element (e.g. to submit a search).",
                    "parameters": {"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_read_page",
                    "description": "Read visible text from the current browser page (up to 5000 chars).",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_screenshot",
                    "description": "Take a screenshot of the current browser page. Useful before a vision query.",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_vision_query",
                    "description": "Take a screenshot of the browser and ask a vision model (Google Gemini or OpenAI) about it. Use this to find UI elements, read page content visually, or understand page layout.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string", "description": "Question or instruction about the page screenshot."}},
                        "required": ["query"]
                    }
                }
            }
        ]
