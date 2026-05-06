import time
from pathlib import Path
from typing import Any, Dict, List

from langchain.tools import tool
from pymarkdown.api import PyMarkdownApi

from config import MAX_MARKDOWN_ISSUES


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


def _lint_file(api: PyMarkdownApi, file_path: Path) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
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
            "line": None,
        })
    return issues


@tool("MarkdownValidator")
def markdownlint_impl(target: str) -> Dict[str, Any]:
    """Lint Markdown files. Returns a summary to save tokens."""
    start = time.time()
    p = Path(target)

    if not p.exists():
        return _build_error_response(
            "MarkdownValidator", target, "TARGET_NOT_FOUND", f"Target not found: {target}", start
        )

    api = PyMarkdownApi()
    issues: List[Dict[str, Any]] = []
    files_checked = 0

    try:
        if p.is_file():
            if p.suffix.lower() not in {".md", ".mdx"}:
                return _build_error_response(
                    "MarkdownValidator", target, "NOT_MARKDOWN",
                    f"File is not .md/.mdx: {p.name}", start
                )
            issues.extend(_lint_file(api, p))
            files_checked = 1
        else:
            md_files = list(p.rglob("*.md")) + list(p.rglob("*.mdx"))
            for fpath in md_files:
                issues.extend(_lint_file(api, fpath))
            files_checked = len(md_files)

        summary = f"Scanned {files_checked} files. Found {len(issues)} issues."
        truncated = issues[:MAX_MARKDOWN_ISSUES]
        if len(issues) > MAX_MARKDOWN_ISSUES:
            summary += f" (Showing first {MAX_MARKDOWN_ISSUES} only)"

        return {
            "tool": "MarkdownValidator",
            "target": target,
            "ok": len(issues) == 0,
            "summary": summary,
            "issues": truncated,
            "meta": {
                "duration_ms": int((time.time() - start) * 1000),
                "files_checked": files_checked,
            },
        }

    except Exception as e:
        return _build_error_response("MarkdownValidator", target, "UNKNOWN_ERROR", str(e), start)
