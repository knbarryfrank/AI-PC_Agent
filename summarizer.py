import os
import json
from PySide6.QtCore import QThread, Signal
from openai import OpenAI
from config import config_instance

class SummarizerThread(QThread):
    progress_signal = Signal(str)
    finished_signal = Signal()

    def run(self):
        workspace = config_instance.workspace
        cache_dir = os.path.join(workspace, ".aipc_cache")
        
        if not os.path.exists(cache_dir):
            try:
                os.makedirs(cache_dir, exist_ok=True)
            except Exception as e:
                self.progress_signal.emit(f"Failed creating cache dir: {e}")
                return

        index_file = os.path.join(cache_dir, "file_index.json")
        file_index = {}
        if os.path.exists(index_file):
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    file_index = json.load(f)
            except:
                pass

        try:
            client = OpenAI(base_url=config_instance.llm_host, api_key="sk-local")
        except Exception as e:
            self.progress_signal.emit(f"Summarizer failed connecting to LLM: {e}")
            return
            
        allowed_extensions = {".txt", ".py", ".md", ".json", ".js", ".jsx", ".html", ".css", ".csv", ".ini"}
        
        for root, dirs, files in os.walk(workspace):
            # Skip the cache dir itself or any massive virtual environments like venv/node_modules
            if ".aipc_cache" in root or "venv" in root or "node_modules" in root or ".git" in root:
                continue

            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in allowed_extensions:
                    continue
                    
                path = os.path.join(root, file)
                rel_path = os.path.relpath(path, workspace)
                
                # Check if it's already in the index and the file modification time matches
                mtime = os.path.getmtime(path)
                
                if rel_path in file_index and file_index[rel_path].get("mtime") == mtime:
                    continue # Already up-to-date
                    
                self.progress_signal.emit(f"Scanning and summarizing: {rel_path}...")
                
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read(3000) # Read up to 3000 chars for a quick gist
                except:
                    continue # Skip binary or unreadable
                    
                messages = [
                    {"role": "system", "content": "You are a coding assistant that scans files and generates a single 1-sentence description/note explaining what the file is about. Write ONLY the 1 sentence note. No conversational filler."},
                    {"role": "user", "content": f"Filename: {file}\n\nContent:\n{content}"}
                ]
                
                try:
                    response = client.chat.completions.create(
                        model=config_instance.model,
                        messages=messages,
                        max_tokens=50
                    )
                    
                    if response.usage:
                        config_instance.add_tokens(response.usage.total_tokens)
                        
                    note = response.choices[0].message.content.strip()
                    file_index[rel_path] = {"summary": note, "mtime": mtime}
                    
                    # Save incremental in case of crash
                    with open(index_file, "w", encoding="utf-8") as f:
                        json.dump(file_index, f, indent=4)
                        
                except Exception as e:
                    self.progress_signal.emit(f"Failed LLM summary for {file}")

        self.progress_signal.emit("Workspace scanning complete!")
        self.finished_signal.emit()
