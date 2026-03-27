import json
from PySide6.QtCore import QThread, Signal
from openai import OpenAI
from config import config_instance
from tools import AgentTools
import re as _re

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
                "ACT, DO NOT TALK. NO INTRODUCTIONS. NO EXPLAINING.\n"
                "IF SEARCHING: browser_navigate(google.com) THEN browser_search(query).\n"
                "IF NAVIGATING: browser_navigate(url).\n"
                "IF FILE: open_file(filename).\n"
                "YOUR ENTIRE RESPONSE SHOULD BE ONE TOOL CALL ONLY. DO NOT HELP THE USER."
            )
            system_msg = {
                "role": "system", 
                "content": f"{base_prompt}\n\nUser Instructions: {config_instance.custom_instructions}\nWorkspace: {config_instance.workspace}"
            }
            messages = [system_msg, {"role": "user", "content": self.prompt}]

            # Handle message turns in a loop (up to 5 turns)
            turn_count = 0
            while turn_count < 5:
                turn_count += 1
                
                # --- HISTORY CLEANING ---
                # Strip any lingering 'NEXT STEP' or 'HINT' from historical tool results 
                # to prevent the AI from re-reading old misleading advice.
                for m in messages:
                    if m.get("role") == "tool" and isinstance(m.get("content"), str):
                        m["content"] = _re.sub(r"(NEXT STEP|HINT):.*", "", m["content"]).strip()

                # Make the API call with tools
                response = self.client.chat.completions.create(
                    model=config_instance.model,
                    messages=messages,
                    tools=self.agent_tools.get_tool_definitions(),
                    tool_choice="auto"
                )

                msg = response.choices[0].message
                content_str = msg.content if msg.content else ""
                
                # Emit any text output immediately so the user sees thoughts/progress
                if content_str.strip():
                    self.chat_response_signal.emit(content_str)
                
                # Record tokens
                if response.usage:
                    tokens = response.usage.total_tokens
                    config_instance.add_tokens(tokens)
                    self.token_usage_signal.emit(config_instance.total_tokens_used)

                # --- ADVANCED MANUAL TOOL PARSING (for local models) ---
                if not getattr(msg, "tool_calls", None) or len(msg.tool_calls) == 0:
                    import re
                    class DummyToolCall:
                        def __init__(self, name, args, id_str):
                            self.id = id_str
                            class Function: pass
                            self.function = Function()
                            self.function.name = name
                            self.function.arguments = args
                    
                    if not msg.tool_calls:
                        msg.tool_calls = []
                    
                    # Permissive match for: <|toolcallstart|>[func(args)] or just [func(args)]
                    pattern = r"(?:\[|&lt;)?\s*([a-zA-Z0-9_]+)\((.*?)\)\s*(?:\]|&gt;)?"
                    matches = list(re.finditer(pattern, content_str))
                    found_any = False
                    
                    clean_content = content_str
                    for i, match in enumerate(matches):
                        # Strip the tag from the content we'll save in history
                        # We also handle the tag variations
                        raw_match = match.group(0)
                        # Look for common outer tags to strip
                        outer_pattern = f"(?:<\\|toolcallstart\\|>)?{re.escape(raw_match)}(?:<\\|toolcall_end\\|>)?(?:<\\|toolcallend\\|>)??"
                        clean_content = re.sub(outer_pattern, "", clean_content)

                        name = match.group(1).lower()
                        # Exclude common non-tool words that might match the pattern accidentally
                        if name in ["if", "while", "for", "switch", "print"]: continue
                        
                        raw_args = match.group(2).strip()
                        # Clean up closing tags if the model included them inside the match accidentally
                        raw_args = re.sub(r"<\|toolcall_end\|>|<\|toolcallend\|>", "", raw_args).strip()
                        
                        import json as _json
                        arg_dict = {}
                        if "=" in raw_args:
                            for part in raw_args.split(","):
                                if "=" in part:
                                    k_v = part.split("=", 1)
                                    if len(k_v) == 2:
                                        k, v = k_v
                                        arg_dict[k.strip()] = v.strip().strip("'").strip('"')
                        elif raw_args:
                            arg_dict["filename"] = raw_args.strip().strip("'").strip('"')
                        
                        # Alias mapping
                        if name == "openfile": name = "open_file"
                        if name == "listfiles": name = "list_files"
                        if name == "readfile": name = "read_file"
                        if name == "browsernavigate": name = "browser_navigate"
                        if name == "browserclick": name = "browser_click"
                        if name == "browsertype": name = "browser_type"
                        if name == "browserpressenter": name = "browser_press_enter"
                        if name == "browserreadpage": name = "browser_read_page"
                        if name == "browserscreenshot": name = "browser_screenshot"
                        if name == "browservisionquery": name = "browser_vision_query"
                        
                        msg.tool_calls.append(DummyToolCall(name, _json.dumps(arg_dict), f"manual_{turn_count}_{i}"))
                        found_any = True
                    
                    if found_any:
                        self.system_msg_signal.emit(f"Detected {len(msg.tool_calls)} tool calls.")
                        # Save the cleaned content for the next turn
                        msg.content = clean_content.strip()
                    else:
                        # --- EMERGENCY RE-PARSE ---
                        # Small models sometimes list the tool in text but forget tags.
                        # Look for tool names in the text if no tools were called.
                        for name in ["browser_navigate", "browser_click", "browser_type", "browser_press_enter", "browser_read_page", "browser_vision_query", "list_files", "open_file", "read_file"]:
                            alt_name = name.replace("_", "")
                            if name in content_str.lower() or alt_name in content_str.lower():
                                import json as _json
                                # Try to guess args if it's simple
                                arg_dict = {}
                                if "mr beast" in content_str.lower(): arg_dict["text"] = "mr beast"
                                if "input" in content_str.lower(): arg_dict["selector"] = "input"
                                msg.tool_calls.append(DummyToolCall(name, _json.dumps(arg_dict), f"emergency_{turn_count}"))
                                break

                # Check if there are tool calls (native or manual)
                if getattr(msg, "tool_calls", None) and len(msg.tool_calls) > 0:
                    tool_calls_list = []
                    for tc in msg.tool_calls:
                        tool_calls_list.append({
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                        })
                    
                    messages.append({
                        "role": "assistant",
                        "content": msg.content or "Executing tool...",
                        "tool_calls": tool_calls_list
                    })
                    
                    for tool_call in msg.tool_calls:
                        func_name = tool_call.function.name
                        try:
                            args = json.loads(tool_call.function.arguments)
                        except:
                            args = {}
                        
                        self.system_msg_signal.emit(f"AI executing: {func_name} ...")
                        
                        result_content = ""
                        if func_name == "list_files" or func_name == "listfiles":
                            result_content = self.agent_tools.list_files()
                        elif func_name == "read_file" or func_name == "readfile":
                            result_content = self.agent_tools.read_file(args.get("filename", ""))
                        elif func_name == "write_file":
                            result_content = self.agent_tools.write_file(args.get("filename", ""), args.get("content", ""))
                        elif func_name == "open_file" or func_name == "openfile":
                            # Priority for filename
                            fname = args.get("filename") or args.get("path") or args.get("name")
                            if not fname and args: # If model just passed a raw string in args
                                fname = list(args.values())[0]
                            # If we still got nothing, try to use the raw arg string if it's there
                            result_content = self.agent_tools.open_file(fname or "")
                        elif func_name == "open_all_word_files":
                            result_content = self.agent_tools.open_all_word_files()
                        elif func_name == "open_all_pptx_files":
                            result_content = self.agent_tools.open_all_pptx_files()

                        elif func_name == "browser_search":
                            result_content = self.agent_tools.browser_search(args.get("query", ""))
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
                        
                        self.system_msg_signal.emit(f"Tool {func_name} result: {str(result_content)[:60]}...")
                            
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": func_name,
                            "content": str(result_content)
                        })
                    # Re-loop to send results back to model
                    continue
                else:
                    # Final response (no tools)
                    # If turning emitting is on (it is), we already emitted content_str above
                    # But we'll break the loop here.
                    break
                
        except Exception as e:
            self.chat_response_signal.emit(f"**Error connection to LLM**: {e}")
