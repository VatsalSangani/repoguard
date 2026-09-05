"""MCP stdio server wrapping ajv-cli (schema validation) and Spectral
(OpenAPI/AsyncAPI linting) for JSON files.

Exposes one tool, `validate_json`. Run directly for manual testing:
`python -m mcp_servers.json_server` (spawned as a subprocess by
`mcp_drivers.json_driver` in normal operation).
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from fastmcp import FastMCP

mcp = FastMCP("JSON Analyzer")

_REPO_ROOT = Path(__file__).resolve().parent.parent
_AJV_BIN = _REPO_ROOT / "node_modules" / ".bin" / ("ajv.cmd" if sys.platform == "win32" else "ajv")
_SPECTRAL_BIN = _REPO_ROOT / "node_modules" / ".bin" / ("spectral.cmd" if sys.platform == "win32" else "spectral")
_SPECTRAL_RULESET = _REPO_ROOT / ".spectral.yaml"

_SPECTRAL_SEVERITY = {0: "high", 1: "medium", 2: "low", 3: "info"}  # error, warn, info, hint


def _is_spec_file(data: Any) -> bool:
    return isinstance(data, dict) and any(k in data for k in ("openapi", "swagger", "asyncapi"))


def _is_circular_ref_error(text: str) -> bool:
    return "circular" in text.lower() and "$ref" in text.lower() or "circular reference" in text.lower()


def _structural_check(file_path: Path) -> tuple[Any, List[Dict[str, Any]]]:
    """Parse the file as JSON. Returns (parsed_data_or_None, findings)."""
    try:
        text = file_path.read_text(encoding="utf-8")
        return json.loads(text), []
    except json.JSONDecodeError as e:
        return None, [{
            "file": str(file_path), "line": e.lineno, "rule": "INVALID_JSON",
            "severity": "high", "message": f"Malformed JSON: {e.msg}",
        }]
    except Exception as e:
        return None, [{
            "file": str(file_path), "line": 1, "rule": "READ_ERROR",
            "severity": "high", "message": str(e),
        }]


def _ajv_validate(file_path: Path, schema_path: str) -> List[Dict[str, Any]]:
    if not _AJV_BIN.exists():
        return [{
            "file": str(file_path), "line": 1, "rule": "AJV_NOT_INSTALLED", "severity": "high",
            "message": "ajv binary not found under node_modules/.bin — run `npm install`.",
        }]
    try:
        proc = subprocess.run(
            [str(_AJV_BIN), "validate", "-s", schema_path, "-d", str(file_path), "--errors=json"],
            # encoding="utf-8" explicitly — see js_server.py._run_eslint for why.
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(_REPO_ROOT), timeout=30, check=False,
        )
    except subprocess.TimeoutExpired:
        return [{"file": str(file_path), "line": 1, "rule": "AJV_TIMEOUT", "severity": "high", "message": "ajv timed out after 30s"}]

    if proc.returncode == 0:
        return []

    combined = f"{proc.stdout}\n{proc.stderr}"
    if _is_circular_ref_error(combined):
        return [{
            "file": str(file_path), "line": 1, "rule": "circular-ref", "severity": "high",
            "message": "Circular $ref detected while compiling schema — validation skipped for this file.",
        }]

    # ajv prints a plain-text status line before the JSON error array.
    bracket = proc.stdout.find("[")
    if bracket == -1:
        return [{
            "file": str(file_path), "line": 1, "rule": "AJV_ERROR", "severity": "high",
            "message": (proc.stderr or proc.stdout or "ajv validation failed").strip()[:1000],
        }]
    try:
        errors = json.loads(proc.stdout[bracket:])
    except json.JSONDecodeError:
        return [{
            "file": str(file_path), "line": 1, "rule": "AJV_PARSE_ERROR", "severity": "high",
            "message": proc.stdout[bracket:][:1000],
        }]

    return [
        {
            "file": str(file_path),
            "line": 1,  # ajv reports JSON-pointer paths, not line numbers
            "rule": err.get("keyword", "schema-violation"),
            "severity": "high",
            "message": f"{err.get('instancePath') or '(root)'}: {err.get('message', 'schema violation')}",
        }
        for err in errors
    ]


def _spectral_lint(file_path: Path) -> List[Dict[str, Any]]:
    if not _SPECTRAL_BIN.exists():
        return [{
            "file": str(file_path), "line": 1, "rule": "SPECTRAL_NOT_INSTALLED", "severity": "high",
            "message": "spectral binary not found under node_modules/.bin — run `npm install`.",
        }]
    try:
        proc = subprocess.run(
            [str(_SPECTRAL_BIN), "lint", str(file_path), "-r", str(_SPECTRAL_RULESET), "-f", "json", "-q"],
            # encoding="utf-8" explicitly — see js_server.py._run_eslint for why.
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(_REPO_ROOT), timeout=30, check=False,
        )
    except subprocess.TimeoutExpired:
        return [{"file": str(file_path), "line": 1, "rule": "SPECTRAL_TIMEOUT", "severity": "high", "message": "spectral timed out after 30s"}]

    if _is_circular_ref_error(proc.stdout + proc.stderr):
        return [{
            "file": str(file_path), "line": 1, "rule": "circular-ref", "severity": "high",
            "message": "Circular $ref detected while resolving spec — lint skipped for this file.",
        }]

    if not proc.stdout.strip():
        return []
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return [{
            "file": str(file_path), "line": 1, "rule": "SPECTRAL_PARSE_ERROR", "severity": "medium",
            "message": (proc.stderr or proc.stdout).strip()[:1000],
        }]

    return [
        {
            "file": str(file_path),
            "line": (r.get("range", {}).get("start", {}).get("line", 0) or 0) + 1,
            "rule": r.get("code", "spectral-rule"),
            "severity": _SPECTRAL_SEVERITY.get(r.get("severity", 1), "medium"),
            "message": r.get("message", "Spectral lint violation"),
        }
        for r in results
    ]


@mcp.tool(
    name="validate_json",
    description=(
        "Validate JSON files for structural correctness (parses as valid JSON) "
        "and, if schema_path is given, JSON Schema compliance via ajv. "
        "Additionally lints OpenAPI/AsyncAPI spec files (detected by an "
        "openapi/swagger/asyncapi top-level key) against best-practice rules "
        "using Spectral. Not for JavaScript/TypeScript or SQL files."
    ),
)
def validate_json(path: str, schema_path: str | None = None) -> Dict[str, Any]:
    """Validate every .json file under `path` (a file or directory)."""
    target = Path(path)
    if not target.exists():
        return {"findings": [{
            "file": path, "line": 1, "rule": "NOT_FOUND", "severity": "high",
            "message": f"Path not found: {path}",
        }]}

    files = [target] if target.is_file() else sorted(target.rglob("*.json"))
    if not files:
        return {"findings": []}

    findings: List[Dict[str, Any]] = []
    for file_path in files:
        data, parse_findings = _structural_check(file_path)
        findings.extend(parse_findings)
        if data is None:
            continue  # malformed JSON — nothing further to validate

        if schema_path:
            findings.extend(_ajv_validate(file_path, schema_path))

        if _is_spec_file(data):
            findings.extend(_spectral_lint(file_path))

    return {"findings": findings}


if __name__ == "__main__":
    mcp.run()
