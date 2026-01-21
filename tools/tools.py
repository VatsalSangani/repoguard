import time
import json
import subprocess
import os
import sys
import shutil
import asyncio
from pathlib import Path
from typing import Any, Dict, List

from langchain.tools import tool
from pymarkdown.api import PyMarkdownApi

# Import the Custom MCP Driver
from mcp_drivers.mcp_driver import RuffMCPDriver

# --- HELPER: ERROR RESPONSE ---
def _build_error_response(tool_name, target, code, msg, start_time):
    return {
        "tool": tool_name,
        "target": target,
        "ok": False,
        "summary": f"Error: {msg}",
        "issues": [{
            "severity": "error",
            "code": code,
            "message": msg,
            "file": None,
            "line": None
        }],
        "meta": {"duration_ms": int((time.time() - start_time) * 1000)},
    }

def _lint_file(api: PyMarkdownApi, file_path: Path) -> List[Dict[str, Any]]:
    """Internal helper to lint a single Markdown file."""
    issues = []
    try:
        result = api.scan_path(str(file_path))
        for f in result.scan_failures:
            issues.append({
                "severity": "warning",
                "code": f.rule_id,
                "message": f.rule_description,
                "file": str(file_path),
                "line": f.line_number,
            })
    except Exception as e:
        issues.append({
            "severity": "error",
            "code": "MARKDOWN_FILE_ERROR",
            "message": str(e),
            "file": str(file_path),
            "line": None
        })
    return issues

# -------------------------
# Tool 1: Markdown Validator (Local)
# -------------------------
@tool("MarkdownValidator")
def markdownlint_impl(target: str) -> Dict[str, Any]:
    """Lint Markdown files. Returns a summary to save tokens."""
    start = time.time()
    p = Path(target)

    if not p.exists():
        return _build_error_response("MarkdownValidator", target, "TARGET_NOT_FOUND", f"Target not found: {target}", start)

    api = PyMarkdownApi()
    issues = []
    files_checked = 0

    try:
        if p.is_file():
            if p.suffix.lower() not in {".md", ".mdx"}:
                return _build_error_response("MarkdownValidator", target, "NOT_MARKDOWN", f"File is not .md/.mdx: {p.name}", start)
            issues.extend(_lint_file(api, p))
            files_checked = 1
        else:
            md_files = list(p.rglob("*.md")) + list(p.rglob("*.mdx"))
            for fpath in md_files:
                issues.extend(_lint_file(api, fpath))
            files_checked = len(md_files)

        MAX_ISSUES = 10
        summary_msg = f"Scanned {files_checked} files. Found {len(issues)} issues."
        if len(issues) > MAX_ISSUES:
            truncated_issues = issues[:MAX_ISSUES]
            summary_msg += f" (Showing first {MAX_ISSUES} only)"
        else:
            truncated_issues = issues

        return {
            "tool": "MarkdownValidator",
            "target": target,
            "ok": len(issues) == 0,
            "summary": summary_msg,
            "issues": truncated_issues,
            "meta": {
                "duration_ms": int((time.time() - start) * 1000),
                "files_checked": files_checked,
            },
        }

    except Exception as e:
        return _build_error_response("MarkdownValidator", target, "UNKNOWN_ERROR", str(e), start)


# -------------------------
# Tool 2: Secrets Validator (Local)
# -------------------------
@tool("SecretsValidator")
def secrets_scan_impl(target: str) -> Dict[str, Any]:
    """Scan for secrets using detect-secrets."""
    start = time.time()
    p = Path(target)
    
    detect_secrets_path = shutil.which("detect-secrets")
    if not detect_secrets_path:
        possible_paths = [
            Path(sys.prefix) / "Scripts" / "detect-secrets.exe",
            Path(sys.prefix) / "bin" / "detect-secrets"
        ]
        for path in possible_paths:
            if path.exists():
                detect_secrets_path = str(path)
                break
    
    if not detect_secrets_path:
        return _build_error_response("SecretsValidator", target, "DETECT_SECRETS_NOT_INSTALLED", "detect-secrets not found.", start)

    exclude_regex = r"(\.git/|\.venv/|venv/|node_modules/|dist/|build/|__pycache__/)"
    cmd = [
        detect_secrets_path, "scan",
        "--all-files",
        "--exclude-files", exclude_regex,
        str(p.resolve()),
    ]

    issues = []
    try:
        proc = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True, 
            cwd=os.getcwd(), 
            timeout=45,
            check=False
        )

        if proc.returncode != 0 and not proc.stdout:
            return _build_error_response("SecretsValidator", target, "DETECT_SECRETS_FAILED", (proc.stderr or "Unknown error").strip(), start)

        baseline = json.loads(proc.stdout) if proc.stdout else {}
        results = baseline.get("results", {})

        for file_path, findings in results.items():
            for f in findings:
                issues.append({
                    "severity": "critical",
                    "code": f.get("type", "SECRET"),
                    "message": "Potential secret detected",
                    "file": file_path,
                    "line": f.get("line_number"),
                })

        MAX_ISSUES = 5
        summary_msg = f"Found {len(issues)} potential secrets."
        if len(issues) > MAX_ISSUES:
            truncated_issues = issues[:MAX_ISSUES]
            summary_msg += f" (Displaying first {MAX_ISSUES} samples)"
        else:
            truncated_issues = issues

        return {
            "tool": "SecretsValidator",
            "target": target,
            "ok": len(issues) == 0,
            "summary": summary_msg,
            "issues": truncated_issues,
            "meta": {"duration_ms": int((time.time() - start) * 1000), "files_checked": 1},
        }

    except Exception as e:
        return _build_error_response("SecretsValidator", target, "SECRETS_RUNTIME_ERROR", str(e), start)


# -------------------------
# Tool 3: Ruff (via mcp-server-analyzer)
# -------------------------
@tool("PythonCodeValidator")
def ruff_lint_impl(target: str) -> Dict[str, Any]:
    """
    Validates Python code via MCP Protocol.
    Reads file content and sends it to 'mcp-server-analyzer'.
    """
    start = time.time()
    p = Path(target)
    
    if not p.exists():
         return _build_error_response("PythonCodeValidator", target, "NOT_FOUND", "Path not found", start)

    # 1. Identify Files
    files_to_scan = [p] if p.is_file() else list(p.rglob("*.py"))

    if not files_to_scan:
        return {
            "tool": "PythonCodeValidator",
            "target": target,
            "ok": True,
            "summary": "No Python files found.",
            "issues": [],
            "meta": {"files_checked": 0}
        }

    all_reports = []
    issues_count = 0

    # 2. Iterate and Scan
    try:
        for file_path in files_to_scan:
            try:
                # Read Content
                with open(file_path, "r", encoding="utf-8") as f:
                    code_content = f.read()

                # New Driver per file (Safe)
                driver = RuffMCPDriver()
                mcp_results = asyncio.run(driver.run_scan(code_content))
                
                # Process Output
                text_out = "\n".join([c.text for c in mcp_results if hasattr(c, 'text')])
                
                # --- FIX: SMART JSON PARSING ---
                # The MCP server returns a JSON string. We parse it to see if there are real errors.
                try:
                    data = json.loads(text_out)
                    # If it's the specific JSON format with "total_issues"
                    if isinstance(data, dict) and "total_issues" in data:
                        if data["total_issues"] > 0:
                            issues_count += 1
                            # Format it nicely for the report
                            formatted_msg = f"File: {file_path.name} | Issues: {data['total_issues']}\n{json.dumps(data['issues'], indent=2)}"
                            all_reports.append(formatted_msg)
                        else:
                            # It's 0 issues, so we ignore it (Success!)
                            pass
                    else:
                        # Fallback for unexpected JSON
                        issues_count += 1
                        all_reports.append(f"File: {file_path.name}\n{text_out}")

                except json.JSONDecodeError:
                    # If it's NOT JSON (raw text error), flag it
                    if text_out.strip() and "No issues found" not in text_out:
                        issues_count += 1
                        all_reports.append(f"File: {file_path.name}\n{text_out}")

            except Exception as e:
                all_reports.append(f"File: {file_path.name} - Error scanning: {str(e)}")

    except Exception as e:
         return _build_error_response("PythonCodeValidator", target, "MCP_LOOP_ERROR", str(e), start)

    # 3. Summarize
    is_ok = len(all_reports) == 0
    summary_msg = f"Scanned {len(files_to_scan)} Python files. "
    
    if is_ok:
        summary_msg += "No issues found."
    else:
        summary_msg += f"Found issues in {issues_count} files."

    return {
        "tool": "PythonCodeValidator",
        "target": target,
        "ok": is_ok, 
        "summary": summary_msg,
        "issues": [{
            "severity": "warning",
            "code": "MCP_REPORT",
            "message": report[:1000], 
            "file": "Batch Scan",
            "line": None
        } for report in all_reports], 
        "meta": {
            "duration_ms": int((time.time() - start) * 1000),
            "files_checked": len(files_to_scan)
        }
    }