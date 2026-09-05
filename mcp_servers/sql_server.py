"""MCP stdio server wrapping sqlfluff for SQL linting.

Exposes one tool, `lint_sql`, with a description specific enough that an
LLM (or the router) won't confuse it with the Python/JS/JSON tools.

Run directly for manual testing: `python -m mcp_servers.sql_server`
(reads/writes MCP JSON-RPC over stdio, so it isn't meant to be run
interactively — it's spawned as a subprocess by `mcp_drivers.sql_driver`).
"""

from pathlib import Path
from typing import Any, Dict, List

import sqlfluff
from fastmcp import FastMCP

mcp = FastMCP("SQL Analyzer")

_SEVERITY_MAP = {True: "info", False: "medium"}  # sqlfluff's `warning` flag


def _lint_one_file(path: Path, dialect: str) -> List[Dict[str, Any]]:
    sql = path.read_text(encoding="utf-8", errors="replace")
    try:
        violations = sqlfluff.lint(sql, dialect=dialect)
    except Exception as e:
        return [{
            "file": str(path),
            "line": 1,
            "rule": "SQLFLUFF_ERROR",
            "severity": "high",
            "message": f"sqlfluff failed to lint this file: {e}",
        }]

    return [
        {
            "file": str(path),
            "line": v.get("start_line_no", 1),
            "rule": v.get("code", "UNKNOWN"),
            "severity": _SEVERITY_MAP.get(v.get("warning", False), "medium"),
            "message": v.get("description", v.get("name", "SQL lint violation")),
        }
        for v in violations
    ]


@mcp.tool(
    name="lint_sql",
    description=(
        "Lint SQL files for syntax errors, anti-patterns, and style violations "
        "using sqlfluff. Supports multiple SQL dialects (ansi, postgres, mysql, "
        "bigquery, snowflake, etc). Use this for .sql files only — not for SQL "
        "embedded as strings inside application code."
    ),
)
def lint_sql(path: str, dialect: str = "ansi") -> Dict[str, Any]:
    """Lint every .sql file under `path` (a file or directory).

    Args:
        path: File or directory to scan.
        dialect: SQL dialect sqlfluff should parse against (default "ansi").
    """
    target = Path(path)
    if not target.exists():
        return {"findings": [{
            "file": path, "line": 1, "rule": "NOT_FOUND", "severity": "high",
            "message": f"Path not found: {path}",
        }]}

    files = [target] if target.is_file() else sorted(target.rglob("*.sql"))
    if not files:
        return {"findings": []}

    findings: List[Dict[str, Any]] = []
    for file_path in files:
        findings.extend(_lint_one_file(file_path, dialect))
    return {"findings": findings}


if __name__ == "__main__":
    mcp.run()
