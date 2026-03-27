import os
import time
from bs4 import BeautifulSoup
import httpx
from config import config_instance

class AgentTools:
    def __init__(self, ui_callback):
        self.ui_callback = ui_callback
        self.auto_approve_until = 0

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

    def search_web(self, query: str):
        self.ui_callback("system_msg", f"AI is searching web for: {query}")
        try:
            url = f"https://html.duckduckgo.com/html/?q={query}"
            headers = {"User-Agent": "Mozilla/5.0"}
            res = httpx.get(url, headers=headers)
            soup = BeautifulSoup(res.text, 'html.parser')
            results = []
            for a in soup.find_all('a', class_='result__url'):
                results.append(a.get('href'))
            return f"Top links: {results[:5]}"
        except Exception as e:
            return f"Error searching: {e}"

    def read_webpage(self, url: str):
        self.ui_callback("system_msg", f"AI is reading page: {url}")
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            res = httpx.get(url, headers=headers)
            soup = BeautifulSoup(res.text, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)
            return text[:4000] + "... (truncated)" if len(text) > 4000 else text
        except Exception as e:
            return f"Error reading page: {e}"

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
                    "name": "search_web",
                    "description": "Searches the web via DuckDuckGo and returns top URLs.",
                    "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_webpage",
                    "description": "Reads text content of a webpage.",
                    "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}
                }
            }
        ]
