from typing import Dict, List, Optional, Set

import pandas as pd
import streamlit as st

_LANGUAGE_LABELS = {"py": "Python", "sql": "SQL", "js": "JavaScript/TypeScript", "json": "JSON"}
_LANGUAGE_ICONS = {"py": "🐍", "sql": "🗄️", "js": "📜", "json": "🧾"}

_ERROR_RULE_SUFFIXES = ("_ERROR", "_TIMEOUT", "_NOT_FOUND", "NOT_FOUND")


def render_language_counts(file_manifest: Dict[str, List[str]]) -> None:
    """Compact 'Python: 3 files, SQL: 2 files, ...' summary row."""
    active = {lang: files for lang, files in file_manifest.items() if files}
    if not active:
        st.caption("No files matched a supported language.")
        return
    cols = st.columns(len(active))
    for col, (lang, files) in zip(cols, active.items()):
        col.metric(f"{_LANGUAGE_ICONS.get(lang, '📄')} {_LANGUAGE_LABELS.get(lang, lang)}", len(files))


def _file_has_error(file_path: str, tool_results: Dict[str, List[dict]], lang: str) -> bool:
    for finding in tool_results.get(lang, []):
        if finding.get("file") == file_path and str(finding.get("rule", "")).upper().endswith(_ERROR_RULE_SUFFIXES):
            return True
    return False


def render_file_status_table(
    file_manifest: Dict[str, List[str]],
    tool_results: Dict[str, List[dict]],
    completed_languages: Set[str],
    running_languages: Optional[Set[str]] = None,
) -> None:
    """Per-file status table: ⏳ pending -> 🔍 scanning -> ✅ done / ❌ error."""
    running_languages = running_languages or set()
    rows = []
    for lang, files in file_manifest.items():
        for f in files:
            if lang in completed_languages:
                status = "❌ Error" if _file_has_error(f, tool_results, lang) else "✅ Done"
            elif lang in running_languages:
                status = "🔍 Scanning"
            else:
                status = "⏳ Pending"
            rows.append({
                "File": f,
                "Language": f"{_LANGUAGE_ICONS.get(lang, '📄')} {_LANGUAGE_LABELS.get(lang, lang)}",
                "Status": status,
            })

    if not rows:
        st.caption("No files to display yet.")
        return

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
