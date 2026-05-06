"""Phase 2 — Human review of scan plan before execution."""

from typing import List

import streamlit as st

from ui.components.file_list import render_file_list
from ui.state import reset

_SAFE_EXCLUDES = [".env", "secret", "key", "password"]


def render() -> None:
    snapshot = st.session_state.snapshot
    values = snapshot.values if hasattr(snapshot, "values") else snapshot

    if values.get("guardrail_status") == "blocked":
        st.error(f"❌ Scan blocked by guardrails: {values.get('risk_reason', 'Unknown reason')}")
        if st.button("🔄 Start Over"):
            reset()
        st.stop()

    files: List[str] = values.get("target_files", values.get("files", []))
    risk: str = values.get("risk_level", "normal")
    risk_reason: str = values.get("risk_reason", "")

    st.subheader("✋ Human Approval Required")
    st.markdown("Parser Agent has completed. Review before proceeding.")

    py_files = [f for f in files if str(f).endswith(".py")]
    md_files = [f for f in files if str(f).endswith(".md")]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Files", len(files))
    col2.metric("Python Files", len(py_files))
    col3.metric("Markdown Files", len(md_files))
    col4.metric("Risk Level", risk.upper())

    if risk == "high":
        st.warning(f"⚠️ HIGH RISK: {risk_reason}")
    else:
        st.success("✅ Normal risk — no sensitive files detected")

    render_file_list(files)
    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("✅ Approve Full Scan", type="primary", use_container_width=True):
            st.session_state.phase = "scanning"
            st.rerun()

    with col2:
        if risk == "high":
            if st.button("🛡️ Safe Mode (Skip Secrets)", use_container_width=True):
                safe_files = [
                    f for f in files
                    if not any(x in str(f) for x in _SAFE_EXCLUDES)
                ]
                st.session_state.app_graph.update_state(
                    st.session_state.thread_config,
                    {"target_files": safe_files},
                )
                st.session_state.phase = "scanning"
                st.rerun()

    with col3:
        if st.button("❌ Cancel", use_container_width=True):
            reset()
