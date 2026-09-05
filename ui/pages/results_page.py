"""Results Page — summary cards, findings grouped by language, full report."""

import streamlit as st

from ui.components.findings import render_findings_by_language, render_summary_cards
from ui.state import reset


def render() -> None:
    st.subheader("📊 Security Report")
    st.success("✅ Scan complete!")

    final_state = st.session_state.final_state or {}
    file_manifest = final_state.get("file_manifest") or {}
    tool_results = final_state.get("tool_results") or {}

    total_files = sum(len(files) for files in file_manifest.values())
    flagged_files = {f.get("file") for findings in tool_results.values() for f in findings}
    clean_files = max(total_files - len(flagged_files), 0)

    if total_files or tool_results:
        render_summary_cards(total_files, tool_results, clean_files)
        st.divider()
        st.markdown("### Findings by Language")
        render_findings_by_language(tool_results)
        st.divider()

    with st.expander("📄 Full Markdown Report", expanded=not bool(total_files or tool_results)):
        st.markdown(st.session_state.final_report)

    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            "⬇️ Download Report",
            st.session_state.final_report,
            file_name="repoguard_report.md",
            mime="text/markdown",
            use_container_width=True,
        )

    with col2:
        if st.button("🔄 Scan Another Repo", use_container_width=True):
            reset()
