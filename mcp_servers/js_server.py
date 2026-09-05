"""MCP stdio server wrapping ESLint (+ eslint-plugin-security) for JS/TS linting.

Exposes one tool, `lint_javascript`. Run directly for manual testing:
`python -m mcp_servers.js_server` (spawned as a subprocess by
`mcp_drivers.js_driver` in normal operation).
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from fastmcp import FastMCP

mcp = FastMCP("JS/TS Analyzer")

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ESLINT_BIN = _REPO_ROOT / "node_modules" / ".bin" / ("eslint.cmd" if sys.platform == "win32" else "eslint")
_ESLINT_CONFIG = _REPO_ROOT / "eslint.config.js"
_JS_EXTENSIONS = (".js", ".jsx", ".ts", ".tsx")

_SEVERITY_MAP = {2: "high", 1: "medium"}  # ESLint: 2 = error, 1 = warn


def _run_eslint(paths: List[str], cwd: str) -> subprocess.CompletedProcess:
    # ESLint's flat config refuses to lint files outside its "base path",
    # which defaults to the process cwd — NOT the config file's own
    # directory. Since RepoGuard scans arbitrary target repos that live
    # outside this project entirely, we always launch eslint with cwd set
    # to the target's own directory (passing the config by absolute path
    # still works regardless of cwd).
    return subprocess.run(
        [str(_ESLINT_BIN), "--no-config-lookup", "-c", str(_ESLINT_CONFIG), "--format", "json", *paths],
        capture_output=True, text=True, cwd=cwd, timeout=30, check=False,
    )


def _to_findings(eslint_json: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for file_result in eslint_json:
        file_path = file_result.get("filePath", "unknown")
        for msg in file_result.get("messages", []):
            rule_id = msg.get("ruleId")
            if rule_id is None:
                # Config/parser-level notices (e.g. "file ignored", parse
                # errors) rather than a rule violation — still surface them,
                # but as low-severity info instead of a fabricated rule name.
                findings.append({
                    "file": file_path,
                    "line": msg.get("line", 1) or 1,
                    "rule": "eslint-notice",
                    "severity": "info",
                    "message": msg.get("message", "ESLint notice"),
                })
                continue
            findings.append({
                "file": file_path,
                "line": msg.get("line", 1) or 1,
                "rule": rule_id,
                "severity": _SEVERITY_MAP.get(msg.get("severity", 1), "medium"),
                "message": msg.get("message", ""),
            })
    return findings


@mcp.tool(
    name="lint_javascript",
    description=(
        "Lint JavaScript and TypeScript files for code quality issues and "
        "security vulnerabilities (unsafe eval, non-literal child_process "
        "calls, unsafe regex, etc) using ESLint with eslint-plugin-security. "
        "Handles .js, .jsx, .ts, and .tsx files."
    ),
)
def lint_javascript(path: str) -> Dict[str, Any]:
    """Lint every .js/.jsx/.ts/.tsx file under `path` (a file or directory)."""
    if not _ESLINT_BIN.exists():
        return {"findings": [{
            "file": path, "line": 1, "rule": "ESLINT_NOT_INSTALLED", "severity": "high",
            "message": "eslint binary not found under node_modules/.bin — run `npm install`.",
        }]}

    target = Path(path)
    if not target.exists():
        return {"findings": [{
            "file": path, "line": 1, "rule": "NOT_FOUND", "severity": "high",
            "message": f"Path not found: {path}",
        }]}

    files = [target] if target.is_file() else sorted(
        p for p in target.rglob("*") if p.suffix in _JS_EXTENSIONS
    )
    if not files:
        return {"findings": []}

    target_dir = str(target if target.is_dir() else target.parent)
    try:
        proc = _run_eslint([str(f) for f in files], cwd=target_dir)
    except subprocess.TimeoutExpired:
        return {"findings": [{
            "file": path, "line": 1, "rule": "ESLINT_TIMEOUT", "severity": "high",
            "message": "eslint timed out after 30s",
        }]}
    except Exception as e:
        return {"findings": [{
            "file": path, "line": 1, "rule": "ESLINT_RUNTIME_ERROR", "severity": "high",
            "message": str(e),
        }]}

    # ESLint exits non-zero when it finds lint errors (not just on crash) —
    # only treat it as a hard failure if stdout isn't parseable JSON.
    try:
        eslint_json = json.loads(proc.stdout) if proc.stdout else []
    except json.JSONDecodeError:
        return {"findings": [{
            "file": path, "line": 1, "rule": "ESLINT_PARSE_ERROR", "severity": "high",
            "message": (proc.stderr or proc.stdout or "eslint produced no parseable output").strip()[:1000],
        }]}

    return {"findings": _to_findings(eslint_json)}


if __name__ == "__main__":
    mcp.run()
