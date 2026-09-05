"""Python sub-agent: lints every .py file in `file_manifest["py"]` via the
Ruff MCP server, on one reused session (one subprocess for the whole batch).

Writes exclusively to `tool_results["py"]` — no other sub-agent touches this
key, and this agent touches no other key in `tool_results`.
"""

import asyncio
from typing import Any, Dict, List

from agents.lang_agents._shared import parse_mcp_text_content
from mcp_drivers.mcp_driver import RuffMCPDriver
from observability.run_context import current_run_id
from observability.tracing import traced_node
from state import AgentState

_SEVERITY_MAP = {"error": "high", "warning": "medium", "info": "info"}


async def _scan_all(files: List[str]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    async with RuffMCPDriver() as driver:
        for file_path in files:
            try:
                code = open(file_path, "r", encoding="utf-8").read()
                content = await driver.run_scan_in_session(code)
                parsed = parse_mcp_text_content(content)
                if parsed.get("error"):
                    findings.append({
                        "file": file_path, "line": 1, "rule": "RUFF_TOOL_ERROR",
                        "severity": "medium", "message": parsed["error"], "tool": "ruff-check",
                    })
                    continue
                for issue in parsed.get("issues", []):
                    findings.append({
                        "file": file_path,
                        "line": issue.get("line", 1),
                        "rule": issue.get("rule", "UNKNOWN"),
                        "severity": _SEVERITY_MAP.get(issue.get("severity", "info"), "medium"),
                        "message": issue.get("message", ""),
                        "tool": "ruff-check",
                    })
            except Exception as e:
                findings.append({
                    "file": file_path, "line": 1, "rule": "RUFF_SCAN_ERROR",
                    "severity": "medium", "message": str(e), "tool": "ruff-check",
                })
    return findings


@traced_node("python_agent")
def python_agent_node(state: AgentState) -> dict:
    print("\n--- 🐍 Python Agent ---")
    current_run_id.set((state.get("run_metadata") or {}).get("run_id", "unknown"))
    files = state.get("file_manifest", {}).get("py", [])
    findings = asyncio.run(_scan_all(files)) if files else []
    print(f"   {len(findings)} finding(s) across {len(files)} file(s)")
    return {"tool_results": {"py": findings}}
