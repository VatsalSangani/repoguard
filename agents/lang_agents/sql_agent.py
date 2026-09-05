"""SQL sub-agent: lints every .sql file in `file_manifest["sql"]` via the
sqlfluff MCP server, on one reused session.

Writes exclusively to `tool_results["sql"]`.
"""

import asyncio
from typing import Any, Dict, List

from agents.lang_agents._shared import from_mcp_findings, parse_mcp_text_content
from mcp_drivers.sql_driver import SqlMCPDriver
from observability.run_context import current_run_id
from observability.tracing import traced_node
from state import AgentState


async def _scan_all(files: List[str]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    async with SqlMCPDriver() as driver:
        for file_path in files:
            try:
                content = await driver.lint_in_session(file_path)
                parsed = parse_mcp_text_content(content)
                findings.extend(from_mcp_findings("lint_sql", parsed))
            except Exception as e:
                findings.append({
                    "file": file_path, "line": 1, "rule": "SQL_SCAN_ERROR",
                    "severity": "medium", "message": str(e), "tool": "lint_sql",
                })
    return findings


@traced_node("sql_agent")
def sql_agent_node(state: AgentState) -> dict:
    print("\n--- 🗄️ SQL Agent ---")
    current_run_id.set((state.get("run_metadata") or {}).get("run_id", "unknown"))
    files = state.get("file_manifest", {}).get("sql", [])
    findings = asyncio.run(_scan_all(files)) if files else []
    print(f"   {len(findings)} finding(s) across {len(files)} file(s)")
    return {"tool_results": {"sql": findings}}
