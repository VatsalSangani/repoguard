"""JSON sub-agent: validates every .json file in `file_manifest["json"]`
via the ajv/Spectral MCP server, on one reused session.

Writes exclusively to `tool_results["json"]`.
"""

import asyncio
from typing import Any, Dict, List

from agents.lang_agents._shared import from_mcp_findings, parse_mcp_text_content
from mcp_drivers.json_driver import JsonMCPDriver
from observability.run_context import current_run_id
from observability.tracing import traced_node
from state import AgentState


async def _scan_all(files: List[str]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    async with JsonMCPDriver() as driver:
        for file_path in files:
            try:
                content = await driver.validate_in_session(file_path)
                parsed = parse_mcp_text_content(content)
                findings.extend(from_mcp_findings("validate_json", parsed))
            except Exception as e:
                findings.append({
                    "file": file_path, "line": 1, "rule": "JSON_SCAN_ERROR",
                    "severity": "medium", "message": str(e), "tool": "validate_json",
                })
    return findings


@traced_node("json_agent")
def json_agent_node(state: AgentState) -> dict:
    print("\n--- 🧾 JSON Agent ---")
    current_run_id.set((state.get("run_metadata") or {}).get("run_id", "unknown"))
    files = state.get("file_manifest", {}).get("json", [])
    findings = asyncio.run(_scan_all(files)) if files else []
    print(f"   {len(findings)} finding(s) across {len(files)} file(s)")
    return {"tool_results": {"json": findings}}
