from typing import Dict, List

import pandas as pd
import streamlit as st

_LANGUAGE_LABELS = {
    "py": "🐍 Python", "sql": "🗄️ SQL", "js": "📜 JavaScript/TypeScript",
    "json": "🧾 JSON", "secrets": "🔑 Secrets (all languages)",
}

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
_SEVERITY_LABELS = {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low", "info": "Info"}


def severity_pill(severity: str) -> str:
    sev = (severity or "info").lower()
    label = _SEVERITY_LABELS.get(sev, sev.title())
    return f"<span class='rg-pill rg-pill-{sev}'>{label}</span>"


def count_by_severity(tool_results: Dict[str, List[dict]]) -> Dict[str, int]:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for findings in tool_results.values():
        for f in findings:
            sev = (f.get("severity") or "info").lower()
            counts[sev] = counts.get(sev, 0) + 1
    return counts


def render_summary_cards(
    total_files: int, tool_results: Dict[str, List[dict]], clean_files: int
) -> None:
    severity_counts = count_by_severity(tool_results)
    total_findings = sum(severity_counts.values())

    row1 = st.columns(3)
    row1[0].metric("Total Files Scanned", total_files)
    row1[1].metric("Total Findings", total_findings)
    row1[2].metric("Clean Files", clean_files)

    row2 = st.columns(4)
    row2[0].metric("🔴 Critical/High", severity_counts["critical"] + severity_counts["high"])
    row2[1].metric("🟠 Medium", severity_counts["medium"])
    row2[2].metric("🔵 Low", severity_counts["low"])
    row2[3].metric("⚪ Info", severity_counts["info"])


def render_findings_by_language(tool_results: Dict[str, List[dict]]) -> None:
    for lang, findings in tool_results.items():
        if not findings:
            continue
        label = _LANGUAGE_LABELS.get(lang, lang)
        with st.expander(f"{label} — {len(findings)} finding(s)", expanded=False):
            sorted_findings = sorted(
                findings, key=lambda f: _SEVERITY_ORDER.get((f.get("severity") or "info").lower(), 9)
            )
            for f in sorted_findings:
                cols = st.columns([3, 1, 2, 1])
                cols[0].markdown(f"**{f.get('file', 'unknown')}**  \nLine {f.get('line', '?')}")
                cols[1].markdown(severity_pill(f.get("severity", "info")), unsafe_allow_html=True)
                cols[2].markdown(f"`{f.get('rule', 'unknown')}`  \n{f.get('message', '')}")
                cols[3].caption(f.get("tool", "unknown"))
                st.divider()

    if not any(tool_results.values()):
        st.success("✅ No findings across any language — repository looks clean.")
