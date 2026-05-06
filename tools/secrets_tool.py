import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict

from langchain.tools import tool

from config import MAX_SECRETS_ISSUES, SECRETS_EXCLUDE_REGEX, SECRETS_SCAN_TIMEOUT


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


def _find_detect_secrets() -> str | None:
    path = shutil.which("detect-secrets")
    if path:
        return path
    for candidate in [
        Path(sys.prefix) / "Scripts" / "detect-secrets.exe",
        Path(sys.prefix) / "bin" / "detect-secrets",
    ]:
        if candidate.exists():
            return str(candidate)
    return None


@tool("SecretsValidator")
def secrets_scan_impl(target: str) -> Dict[str, Any]:
    """Scan for secrets using detect-secrets."""
    start = time.time()
    p = Path(target)

    detect_secrets_path = _find_detect_secrets()
    if not detect_secrets_path:
        return _build_error_response(
            "SecretsValidator", target,
            "DETECT_SECRETS_NOT_INSTALLED", "detect-secrets not found.", start
        )

    cmd = [
        detect_secrets_path, "scan",
        "--all-files",
        "--exclude-files", SECRETS_EXCLUDE_REGEX,
        str(p.resolve()),
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.getcwd(),
            timeout=SECRETS_SCAN_TIMEOUT,
            check=False,
        )

        if proc.returncode != 0 and not proc.stdout:
            return _build_error_response(
                "SecretsValidator", target,
                "DETECT_SECRETS_FAILED", (proc.stderr or "Unknown error").strip(), start
            )

        baseline = json.loads(proc.stdout) if proc.stdout else {}
        results = baseline.get("results", {})

        issues = [
            {
                "severity": "critical",
                "code": finding.get("type", "SECRET"),
                "message": "Potential secret detected",
                "file": file_path,
                "line": finding.get("line_number"),
            }
            for file_path, findings in results.items()
            for finding in findings
        ]

        summary = f"Found {len(issues)} potential secrets."
        truncated = issues[:MAX_SECRETS_ISSUES]
        if len(issues) > MAX_SECRETS_ISSUES:
            summary += f" (Displaying first {MAX_SECRETS_ISSUES} samples)"

        return {
            "tool": "SecretsValidator",
            "target": target,
            "ok": len(issues) == 0,
            "summary": summary,
            "issues": truncated,
            "meta": {"duration_ms": int((time.time() - start) * 1000), "files_checked": 1},
        }

    except Exception as e:
        return _build_error_response(
            "SecretsValidator", target, "SECRETS_RUNTIME_ERROR", str(e), start
        )
