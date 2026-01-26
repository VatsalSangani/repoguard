from langchain_openai import ChatOpenAI
from state import AgentState
from tools.tools import markdownlint_impl, secrets_scan_impl, ruff_lint_impl

def processing_node(state: AgentState):
    print("\n--- 🛠️ Step 2: Processing Agent (Multi-Tool Capable) ---")
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    files = state["target_files"]
    scan_results = []
    
    for file_path in files:
        # --- 1. THE MULTI-TOOL PROMPT ---
        prompt = (
            f"File: '{file_path}'\n"
            "Task: Select all applicable tools for this file.\n"
            "Rules:\n"
            "1. 'python' -> Use for .py files.\n"
            "2. 'markdown' -> Use for .md files.\n"
            "3. 'secrets' -> Use for .env, .txt, .json, AND ALL code files (.py, .js) to check for hardcoded keys.\n"
            "Output: Comma-separated list (e.g., 'python, secrets')."
        )
        
        # Get decision (e.g., "python, secrets")
        decision_raw = llm.invoke(prompt).content.lower()
        
        # Clean up string into a list
        selected_tools = [t.strip() for t in decision_raw.split(",") if t.strip()]
        
        print(f"   file: {file_path} -> tools: {selected_tools}")
        
        # --- 2. THE EXECUTION LOOP ---
        for tool_name in selected_tools:
            tool_output = None
            try:
                if "python" in tool_name:
                    tool_output = ruff_lint_impl.invoke({"target": file_path})
                elif "markdown" in tool_name:
                    tool_output = markdownlint_impl.invoke({"target": file_path})
                elif "secrets" in tool_name:
                    tool_output = secrets_scan_impl.invoke({"target": file_path})
                else:
                    continue # Skip invalid tool names
                    
                # Append EACH tool result separately
                scan_results.append({
                    "file": file_path, 
                    "tool_used": tool_name,
                    "details": tool_output
                })

            except Exception as e:
                scan_results.append({
                    "file": file_path,
                    "tool_used": tool_name, 
                    "details": {"error": str(e)}
                })

    return {"raw_scan_results": scan_results}