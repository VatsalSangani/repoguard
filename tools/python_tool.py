import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List

from langchain.tools import tool

from mcp_drivers.mcp_driver import RuffMCPDriver


def _build_error_response(
    tool_name: str, target: str, code: str, msg: str, start_time: float
) -> Dict[str, Any]:
    return {
        "tool": tool_name,
        "target": target,
        "ok": False,
        "summary": f"Error: {msg}",
        "issues": [{"severity": "error", "code": code, "message": msg, "file": None, "line": None}],
        "meta": {"duration_ms": int((time.time() - start_time) * 1000)},
    }


def _parse_mcp_output(text_out: str, file_name: str) -> str | None:
    """Return a formatted issue string if issues found, else None."""
    try:
        data = json.loads(text_out)
        if isinstance(data, dict) and "total_issues" in data:
            if data["total_issues"] > 0:
                return f"File: {file_name} | Issues: {data['total_issues']}\n{json.dumps(data['issues'], indent=2)}"
            return None
        return f"File: {file_name}\n{text_out}"
    except json.JSONDecodeError:
        if text_out.strip() and "No issues found" not in text_out:
            return f"File: {file_name}\n{text_out}"
        return None


@tool("PythonCodeValidator")
def ruff_lint_impl(target: str) -> Dict[str, Any]:
    """Validate Python code quality via the Ruff MCP server."""
    start = time.time()
    p = Path(target)

    if not p.exists():
        return _build_error_response("PythonCodeValidator", target, "NOT_FOUND", "Path not found", start)

    files_to_scan: List[Path] = [p] if p.is_file() else list(p.rglob("*.py"))

    if not files_to_scan:
        return {
            "tool": "PythonCodeValidator",
            "target": target,
            "ok": True,
            "summary": "No Python files found.",
            "issues": [],
            "meta": {"files_checked": 0},
        }

    reports: List[str] = []

    try:
        for file_path in files_to_scan:
            try:
                code_content = file_path.read_text(encoding="utf-8")
                driver = RuffMCPDriver()
                mcp_results = asyncio.run(driver.run_scan(code_content))
                text_out = "\n".join(c.text for c in mcp_results if hasattr(c, "text"))
                result = _parse_mcp_output(text_out, file_path.name)
                if result:
                    reports.append(result)
            except Exception as e:
                reports.append(f"File: {file_path.name} - Error scanning: {e}")

    except Exception as e:
        return _build_error_response("PythonCodeValidator", target, "MCP_LOOP_ERROR", str(e), start)

    is_ok = len(reports) == 0
    summary = f"Scanned {len(files_to_scan)} Python files. "
    summary += "No issues found." if is_ok else f"Found issues in {len(reports)} files."

    return {
        "tool": "PythonCodeValidator",
        "target": target,
        "ok": is_ok,
        "summary": summary,
        "issues": [
            {"severity": "warning", "code": "MCP_REPORT", "message": r[:1000], "file": "Batch Scan", "line": None}
            for r in reports
        ],
        "meta": {
            "duration_ms": int((time.time() - start) * 1000),
            "files_checked": len(files_to_scan),
        },
    }
