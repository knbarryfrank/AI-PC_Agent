import json
import os

CONFIG_FILE = "aipc_config.json"

class Config:
    def __init__(self):
        self.workspace = os.path.expanduser("~")
        self.custom_instructions = "You are a helpful AI assistant running on my PC."
        self.llm_host = "http://localhost:11434/v1"  # Default Ollama OpenAI compatibility
        self.model = "llama3" # Default model
        self.total_tokens_used = 0
        self.load()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    self.workspace = data.get("workspace", self.workspace)
                    self.custom_instructions = data.get("custom_instructions", self.custom_instructions)
                    self.llm_host = data.get("llm_host", self.llm_host)
                    self.model = data.get("model", self.model)
                    self.total_tokens_used = data.get("total_tokens_used", 0)
            except Exception as e:
                print("Failed to load config:", e)

    def save(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump({
                "workspace": self.workspace,
                "custom_instructions": self.custom_instructions,
                "llm_host": self.llm_host,
                "model": self.model,
                "total_tokens_used": self.total_tokens_used
            }, f, indent=4)

    def add_tokens(self, count):
        self.total_tokens_used += count
        self.save()

config_instance = Config()
