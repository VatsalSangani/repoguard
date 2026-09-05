"""Scan coverage verification: cross-checks `file_manifest` (what the
Router discovered) against `tool_results` (what actually came back from
the sub-agents) so silent skips — a file the Router grouped that never
produced a result of any kind — are caught and surfaced, not lost.

Design note: `tool_results` only ever holds *findings*. A file that was
scanned successfully and is clean produces zero findings, so naively
treating "file absent from tool_results" as "not scanned" would flag every
clean file as skipped — the opposite of useful. Instead, a file counts as
scanned once its language's sub-agent node has completed (see
`completed_languages`, threaded from the scanning page's live node
tracking); within a completed language, a file is "done" unless it has an
error-shaped finding (rule ending in one of `_ERROR_RULE_SUFFIXES`) attached
to it specifically, in which case it's "error". A file whose language never
reaches `completed_languages` at all (e.g. the sub-agent node raised before
returning) is the real, catchable "silent skip" this module exists to
surface — it stays "pending" forever and results_page's coverage summary
below flags it by name.
"""

from typing import Any, Dict, List, Optional, Set

import pandas as pd
import streamlit as st

_LANGUAGE_LABELS = {"py": "🐍 Python", "sql": "🗄️ SQL", "js": "📜 JS/TS", "json": "🧾 JSON"}

# Mirrors agents/router.py LANGUAGE_TO_NODE — kept here too since the UI
# needs it independently of importing agent internals.
LANG_TO_NODE = {"py": "python_agent", "sql": "sql_agent", "js": "js_agent", "json": "json_agent"}
NODE_TO_LANG = {v: k for k, v in LANG_TO_NODE.items()}

# detect-secrets runs once in the Router, across every file regardless of
# language (see agents/router.py `_run_secrets_prescan`) — so it's assigned
# to every row alongside that file's language-specific tool(s).
_LANGUAGE_TOOLS = {
    "py": ["Ruff", "detect-secrets"],
    "sql": ["sqlfluff", "detect-secrets"],
    "js": ["ESLint", "detect-secrets"],
    "json": ["ajv", "Spectral", "detect-secrets"],
}

_ERROR_RULE_SUFFIXES = ("_ERROR", "_TIMEOUT", "_NOT_FOUND", "NOT_FOUND")


def _findings_for_file(file_path: str, lang: str, tool_results: Dict[str, List[dict]]) -> List[dict]:
    own = [f for f in tool_results.get(lang, []) if f.get("file") == file_path]
    secrets = [f for f in tool_results.get("secrets", []) if f.get("file") == file_path]
    return own + secrets


def _is_error_finding(f: dict) -> bool:
    return str(f.get("rule", "")).upper().endswith(_ERROR_RULE_SUFFIXES)


def compute_file_rows(
    file_manifest: Dict[str, List[str]],
    tool_results: Dict[str, List[dict]],
    completed_languages: Set[str],
    running_languages: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """One row per file in the manifest: file, language, tools_assigned,
    status_code ("pending"|"scanning"|"done"|"error"), findings_count,
    reason (error message, only set when status_code == "error")."""
    running_languages = running_languages or set()
    rows: List[Dict[str, Any]] = []

    for lang, files in file_manifest.items():
        for f in files:
            findings = _findings_for_file(f, lang, tool_results)
            error_findings = [x for x in findings if _is_error_finding(x)]

            if lang in completed_languages:
                if error_findings:
                    status_code, reason = "error", error_findings[0].get("message", "Scan failed")
                else:
                    status_code, reason = "done", None
            elif lang in running_languages:
                status_code, reason = "scanning", None
            else:
                status_code, reason = "pending", None

            rows.append({
                "file": f,
                "language": lang,
                "language_label": _LANGUAGE_LABELS.get(lang, lang),
                "tools_assigned": ", ".join(_LANGUAGE_TOOLS.get(lang, [])),
                "status_code": status_code,
                "reason": reason,
                "findings_count": len([x for x in findings if not _is_error_finding(x)]),
            })

    return rows


_STATUS_DISPLAY = {
    "pending": "⏳ Pending",
    "scanning": "🔍 Scanning",
    "done": "✅ Done",
    "error": "❌ Failed",
}


def render_coverage_table(rows: List[Dict[str, Any]]) -> None:
    """Live table for the scanning page: File Path | Language | Tools
    Assigned | Scan Status | Findings."""
    if not rows:
        st.caption("No files to display yet.")
        return

    df = pd.DataFrame([
        {
            "File Path": r["file"],
            "Language": r["language_label"],
            "Tools Assigned": r["tools_assigned"],
            "Scan Status": _STATUS_DISPLAY[r["status_code"]] + (f" — {r['reason']}" if r["reason"] else ""),
            "Findings": r["findings_count"] if r["status_code"] in ("done", "error") else "—",
        }
        for r in rows
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_coverage_summary(rows: List[Dict[str, Any]]) -> None:
    """Results-page section: total manifest files vs. scanned vs. skipped,
    with a green/red badge and the list+reason for anything unscanned."""
    st.markdown("### Scan Coverage")

    total = len(rows)
    scanned = [r for r in rows if r["status_code"] == "done"]
    failed = [r for r in rows if r["status_code"] == "error"]
    unscanned = [r for r in rows if r["status_code"] in ("pending", "scanning")]

    cols = st.columns(3)
    cols[0].metric("Total Files in Manifest", total)
    cols[1].metric("Successfully Scanned", len(scanned))
    cols[2].metric("Skipped / Failed", len(unscanned) + len(failed))

    if total > 0 and not unscanned and not failed:
        st.markdown(
            "<span class='rg-pill' style='background-color:rgba(63,185,80,0.15);"
            "color:#3fb950;border:1px solid rgba(63,185,80,0.4);'>✅ 100% Coverage</span>",
            unsafe_allow_html=True,
        )
        return

    if not total:
        st.caption("No files were in scope for this scan.")
        return

    st.warning(
        f"⚠️ Coverage incomplete: {len(unscanned)} file(s) never scanned, "
        f"{len(failed)} file(s) failed during scanning."
    )

    if unscanned:
        with st.expander(f"🚫 Not scanned ({len(unscanned)})", expanded=True):
            for r in unscanned:
                st.markdown(
                    f"- `{r['file']}` ({r['language_label']}) — "
                    f"reason: sub-agent for this language never completed "
                    f"(likely a node error mid-run)"
                )

    if failed:
        with st.expander(f"❌ Failed while scanning ({len(failed)})", expanded=True):
            for r in failed:
                st.markdown(f"- `{r['file']}` ({r['language_label']}) — reason: {r['reason']}")
