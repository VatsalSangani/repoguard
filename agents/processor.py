from typing import Any, Dict, List

from langchain_openai import ChatOpenAI

from config import DEFAULT_MODEL, LLM_TEMPERATURE
from state import AgentState
from tools.markdown_tool import markdownlint_impl
from tools.python_tool import ruff_lint_impl
from tools.secrets_tool import secrets_scan_impl

_TOOL_SELECTION_PROMPT = """\
File: '{file_path}'
Task: Select all applicable tools for this file.
Rules:
1. 'python' -> Use for .py files.
2. 'markdown' -> Use for .md files.
3. 'secrets' -> Use for .env, .txt, .json, AND ALL code files (.py, .js) to check for hardcoded keys.
Output: Comma-separated list (e.g., 'python, secrets').\
"""

_TOOL_MAP = {
    "python": lambda path: ruff_lint_impl.invoke({"target": path}),
    "markdown": lambda path: markdownlint_impl.invoke({"target": path}),
    "secrets": lambda path: secrets_scan_impl.invoke({"target": path}),
}


def processing_node(state: AgentState) -> dict:
    print("\n--- 🛠️ Step 2: Processing Agent (Multi-Tool Capable) ---")
    llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=LLM_TEMPERATURE)
    scan_results: List[Dict[str, Any]] = []

    for file_path in state["target_files"]:
        prompt = _TOOL_SELECTION_PROMPT.format(file_path=file_path)
        decision = llm.invoke(prompt).content.lower()
        selected_tools = [t.strip() for t in decision.split(",") if t.strip()]

        print(f"   file: {file_path} -> tools: {selected_tools}")

        for tool_name in selected_tools:
            executor = _TOOL_MAP.get(tool_name)
            if not executor:
                continue
            try:
                scan_results.append({
                    "file": file_path,
                    "tool_used": tool_name,
                    "details": executor(file_path),
                })
            except Exception as e:
                scan_results.append({
                    "file": file_path,
                    "tool_used": tool_name,
                    "details": {"error": str(e)},
                })

    return {"raw_scan_results": scan_results}
