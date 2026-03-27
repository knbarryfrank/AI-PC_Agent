import json
from PySide6.QtCore import QThread, Signal
from openai import OpenAI
from config import config_instance
from tools import AgentTools

class AgentThread(QThread):
    chat_response_signal = Signal(str)
    system_msg_signal = Signal(str)
    token_usage_signal = Signal(int)
    approval_request_signal = Signal(str)
    
    def __init__(self, prompt):
        super().__init__()
        self.prompt = prompt
        self.client = None
        self.agent_tools = AgentTools(self.handle_ui_callback)

    def handle_ui_callback(self, action_type, payload):
        if action_type == "system_msg":
            self.system_msg_signal.emit(payload)
            return None, False
        if action_type == "approval_request":
            # Real application: Since this is inside a QThread, we should ideally emit the signal
            # and block here using an Event, waiting for the main thread to set the result.
            # To keep it simple but thread-safe, we'll implement a blocking event.
            self.user_choice = None
            self.dont_ask_again = False
            self.waiting_for_user = True
            
            self.approval_request_signal.emit(payload)
            
            while self.waiting_for_user:
                self.msleep(100) # Wait until the UI slot gives us an answer via set_approval_result
                
            return self.user_choice, self.dont_ask_again
            
        return None, False

    def set_approval_result(self, approved, dont_ask_again):
        self.user_choice = approved
        self.dont_ask_again = dont_ask_again
        self.waiting_for_user = False

    def run(self):
        try:
            self.client = OpenAI(base_url=config_instance.llm_host, api_key="sk-local")
            
            system_msg = {"role": "system", "content": config_instance.custom_instructions + f"\nYour working directory is {config_instance.workspace}. Tools are provided."}
            messages = [system_msg, {"role": "user", "content": self.prompt}]

            # Make the API call with tools
            response = self.client.chat.completions.create(
                model=config_instance.model,
                messages=messages,
                tools=self.agent_tools.get_tool_definitions(),
                tool_choice="auto"
            )

            msg = response.choices[0].message
            
            # Record tokens
            if response.usage:
                tokens = response.usage.total_tokens
                config_instance.add_tokens(tokens)
                self.token_usage_signal.emit(config_instance.total_tokens_used)

            # Check if there are tool calls
            if msg.tool_calls:
                self.system_msg_signal.emit(f"AI requested {len(msg.tool_calls)} tools.")
                messages.append(msg)
                
                for tool_call in msg.tool_calls:
                    func_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    
                    self.system_msg_signal.emit(f"Executing {func_name}...")
                    
                    result_content = ""
                    if func_name == "list_files":
                        result_content = self.agent_tools.list_files()
                    elif func_name == "read_file":
                        result_content = self.agent_tools.read_file(args.get("filename", ""))
                    elif func_name == "write_file":
                        result_content = self.agent_tools.write_file(args.get("filename", ""), args.get("content", ""))
                    elif func_name == "search_web":
                        result_content = self.agent_tools.search_web(args.get("query", ""))
                    elif func_name == "read_webpage":
                        result_content = self.agent_tools.read_webpage(args.get("url", ""))
                        
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": func_name,
                        "content": result_content
                    })
                    
                # Second response after tool execution
                final_res = self.client.chat.completions.create(
                    model=config_instance.model,
                    messages=messages
                )
                
                if final_res.usage:
                    tokens = final_res.usage.total_tokens
                    config_instance.add_tokens(tokens)
                    self.token_usage_signal.emit(config_instance.total_tokens_used)
                    
                self.chat_response_signal.emit(final_res.choices[0].message.content)
            else:
                self.chat_response_signal.emit(msg.content)
                
        except Exception as e:
            self.chat_response_signal.emit(f"**Error connection to LLM**: {e}")
