from typing import Any, Dict, List

from langchain_openai import ChatOpenAI
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

from config import DEFAULT_MODEL, LLM_TEMPERATURE
from observability.run_context import current_run_id
from observability.tracing import traced_node
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


def _finding_count(details: Dict[str, Any]) -> int:
    issues = details.get("issues") if isinstance(details, dict) else None
    return len(issues) if isinstance(issues, list) else 0


@traceable(name="scan_file", run_type="tool")
def _run_tool_traced(tool_name: str, file_path: str, executor) -> Dict[str, Any]:
    """One child span per (file, tool) invocation, tagged with the file
    path, tool name, and finding count so each file's scan is individually
    inspectable in the LangSmith trace waterfall under `processor`."""
    try:
        details = executor(file_path)
        error = None
    except Exception as e:
        details = {"error": str(e)}
        error = str(e)

    finding_count = _finding_count(details)

    run_tree = get_current_run_tree()
    if run_tree is not None:
        run_tree.tags = list(set((run_tree.tags or []) + [
            f"tool:{tool_name}",
            f"file:{file_path}",
        ]))
        run_tree.extra = {
            **(run_tree.extra or {}),
            "metadata": {
                **((run_tree.extra or {}).get("metadata") or {}),
                "file_path": file_path,
                "tool_name": tool_name,
                "finding_count": finding_count,
                "error": error,
            },
        }

    return details


@traced_node("processor")
def processing_node(state: AgentState) -> dict:
    print("\n--- 🛠️ Step 2: Processing Agent (Multi-Tool Capable) ---")
    current_run_id.set((state.get("run_metadata") or {}).get("run_id", "unknown"))
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
            scan_results.append({
                "file": file_path,
                "tool_used": tool_name,
                "details": _run_tool_traced(tool_name, file_path, executor),
            })

    return {"raw_scan_results": scan_results}
