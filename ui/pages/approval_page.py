"""Approval Page — human review of the scan plan (HITL) before execution."""

from typing import List

import streamlit as st

from config import SAFE_SCAN_EXCLUDES, SENSITIVE_KEYWORDS
from ui.components.file_list import render_file_list
from ui.state import reset


def render() -> None:
    snapshot = st.session_state.snapshot
    values = snapshot.values if hasattr(snapshot, "values") else snapshot

    if values.get("guardrail_status") == "fail":
        st.error(f"❌ Scan aborted by guardrails: {values.get('error', 'No files found to scan.')}")
        if st.button("🔄 Start Over"):
            reset()
        st.stop()

    files: List[str] = values.get("target_files", values.get("files", []))
    risk: str = values.get("risk_level", "normal")
    risk_reason: str = values.get("risk_reason", "")
    sensitive_files = [f for f in files if any(k in str(f) for k in SENSITIVE_KEYWORDS)]

    st.subheader("✋ Human Approval Required")
    st.markdown("Parser and Guardrails have completed. Review the scan plan before the Router dispatches it.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Files", len(files))
    col2.metric("Sensitive Files", len(sensitive_files))
    col3.metric("Risk Level", risk.upper())

    if risk == "high":
        st.warning(f"⚠️ HIGH RISK: {risk_reason}")
        with st.expander(f"🔑 Sensitive files found ({len(sensitive_files)})", expanded=True):
            for f in sensitive_files:
                st.code(str(f), language=None)
    else:
        st.success("✅ Normal risk — no sensitive files detected")

    render_file_list(files)
    st.divider()

    st.markdown("**Choose how to proceed:**")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("✅ Approve Full Scan", type="primary", use_container_width=True):
            st.session_state.phase = "scanning"
            st.rerun()
        st.caption("Scan every file listed above, including any sensitive ones.")

    with col2:
        safe_disabled = risk != "high"
        if st.button("🛡️ Safe Scan (Exclude Sensitive)", use_container_width=True, disabled=safe_disabled):
            safe_files = [f for f in files if not any(x in str(f) for x in SAFE_SCAN_EXCLUDES)]
            st.session_state.app_graph.update_state(
                st.session_state.thread_config,
                {"target_files": safe_files},
            )
            st.session_state.phase = "scanning"
            st.rerun()
        st.caption(
            "Skip .env/secrets-named files entirely, scan the rest."
            if not safe_disabled else
            "No sensitive files detected — nothing to exclude."
        )

    with col3:
        if st.button("❌ Reject (Stop)", use_container_width=True):
            reset()
        st.caption("Cancel the scan and discard this run.")
