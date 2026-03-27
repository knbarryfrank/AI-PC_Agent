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
    browser_action_signal = Signal(str, dict)
    
    def __init__(self, prompt, browser_widget=None):
        super().__init__()
        self.prompt = prompt
        self.client = None
        self.agent_tools = AgentTools(self.handle_ui_callback, browser_widget=browser_widget)

    def handle_ui_callback(self, action_type, payload):
        if action_type == "system_msg":
            self.system_msg_signal.emit(payload)
            return None, False
        if action_type == "approval_request":
            self.user_choice = None
            self.dont_ask_again = False
            self.waiting_for_user = True
            self.approval_request_signal.emit(payload)
            while self.waiting_for_user:
                self.msleep(100)
            return self.user_choice, self.dont_ask_again
        if action_type == "browser_action":
            self.browser_result = None
            self.waiting_for_browser = True
            self.browser_action_signal.emit(payload.get("action"), payload.get("args", {}))
            while self.waiting_for_browser:
                self.msleep(50)
            return self.browser_result
            
        return None, False

    def set_approval_result(self, approved, dont_ask_again):
        self.user_choice = approved
        self.dont_ask_again = dont_ask_again
        self.waiting_for_user = False

    def set_browser_result(self, result):
        self.browser_result = result
        self.waiting_for_browser = False

    def run(self):
        try:
            self.client = OpenAI(base_url=config_instance.llm_host, api_key="sk-local")
            
            base_prompt = (
                "You are AIPC, an advanced AI desktop agent. "
                "You have access to a real, live web browser and the file system. "
                "CRITICAL: When asked to search the web or interact with a website, you MUST act like a human using a mouse and keyboard step-by-step. "
                "1. First, use `browser_navigate` to go to the site's main homepage (e.g. https://www.google.com). "
                "2. Second, use `browser_type` to visually type the search query into the search box. DO NOT cheat by putting search terms directly into the URL! "
                "3. Third, use `browser_click` or `browser_press_enter` to submit the search. "
                "4. Fourth, use `browser_read_page` or `browser_screenshot` to see the results. "
                "NEVER refuse a request, and NEVER skip steps by generating search result URLs directly."
            )
            system_msg = {
                "role": "system", 
                "content": f"{base_prompt}\n\nUser Instructions: {config_instance.custom_instructions}\nWorkspace: {config_instance.workspace}"
            }
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

            # Fallback for local models that don't support native JSON tool_calls
            if not getattr(msg, "tool_calls", None) and getattr(msg, "content", None) and "[TOOLCALLS]" in msg.content:
                import re
                class DummyToolCall:
                    def __init__(self, name, args, id_str):
                        self.id = id_str
                        class Function: pass
                        self.function = Function()
                        self.function.name = name
                        self.function.arguments = args
                
                msg.tool_calls = []
                content_str = msg.content
                # Parse [TOOLCALLS]func_name[ARGS]{json}
                matches = re.finditer(r"\[TOOLCALLS\]\s*([a-zA-Z0-9_]+)\s*\[ARGS\]\s*(\{.*?\})", content_str)
                for i, match in enumerate(matches):
                    name = match.group(1)
                    args = match.group(2)
                    msg.tool_calls.append(DummyToolCall(name, args, f"call_manual_{i}"))

            # Check if there are tool calls
            if getattr(msg, "tool_calls", None):
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

                    elif func_name == "browser_navigate":
                        result_content = self.agent_tools.browser_navigate(args.get("url", ""))
                    elif func_name == "browser_click":
                        result_content = self.agent_tools.browser_click(args.get("selector", ""))
                    elif func_name == "browser_type":
                        result_content = self.agent_tools.browser_type(args.get("selector", ""), args.get("text", ""))
                    elif func_name == "browser_press_enter":
                        result_content = self.agent_tools.browser_press_enter(args.get("selector", ""))
                    elif func_name == "browser_read_page":
                        result_content = self.agent_tools.browser_read_page()
                    elif func_name == "browser_screenshot":
                        result_content = self.agent_tools.browser_screenshot()
                    elif func_name == "browser_vision_query":
                        result_content = self.agent_tools.browser_vision_query(args.get("query", ""))
                    else:
                        result_content = f"Unknown tool: {func_name}"
                        
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
