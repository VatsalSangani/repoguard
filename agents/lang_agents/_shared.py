"""Helpers shared by the per-language sub-agents for normalizing whatever
shape their underlying tool returns into `list[Finding]`-compatible dicts.

Two shapes exist today:
  - Legacy tools (Ruff/secrets/markdown, from before Phase 1) return
    `{"issues": [{"severity", "code", "message", "file", "line"}], ...}`.
  - New MCP tools (sql/js/json, Phase 1) already return
    `{"findings": [{"file", "line", "rule", "severity", "message"}]}`.
Both get normalized here to the exact `Finding` field set (adding the
`tool` name, which neither shape carries on its own) before being written
to `state["tool_results"][<language>]`.
"""

from typing import Any, Dict, List

_LEGACY_SEVERITY_MAP = {
    "critical": "high",
    "error": "high",
    "warning": "medium",
    "info": "info",
}


def from_legacy_issues(tool_name: str, legacy_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize a legacy `{tool, issues: [...]}` result into Finding dicts."""
    issues = legacy_result.get("issues") if isinstance(legacy_result, dict) else None
    if not isinstance(issues, list):
        return []
    return [
        {
            "file": issue.get("file") or legacy_result.get("target") or "unknown",
            "line": issue.get("line") or 1,
            "rule": issue.get("code", "UNKNOWN"),
            "severity": _LEGACY_SEVERITY_MAP.get(issue.get("severity", "info"), "info"),
            "message": issue.get("message", ""),
            "tool": tool_name,
        }
        for issue in issues
    ]


def from_mcp_findings(tool_name: str, mcp_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize a `{"findings": [...]}` MCP tool result into Finding dicts."""
    findings = mcp_result.get("findings") if isinstance(mcp_result, dict) else None
    if not isinstance(findings, list):
        return []
    return [{**f, "tool": tool_name} for f in findings]


def parse_mcp_text_content(content: list) -> Dict[str, Any]:
    """MCP tool results arrive as a list of TextContent-like objects whose
    `.text` is a JSON string; extract and parse the first one."""
    import json

    for item in content:
        text = getattr(item, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"findings": [], "error": f"unparseable tool output: {text[:500]}"}
    return {"findings": []}
