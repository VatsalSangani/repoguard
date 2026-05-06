"""Phase 3 — Invoke the processing + aggregator pipeline and wait for results."""

import streamlit as st

from ui.state import cleanup_tmp, reset


def render() -> None:
    st.subheader("⚙️ Running Security Scan...")

    with st.spinner("Processing Agent running tools (Ruff + Secrets + Markdown)..."):
        try:
            result = st.session_state.app_graph.invoke(
                None,
                st.session_state.thread_config,
            )
            report = (
                result.get("final_report")
                or result.get("report")
                or result.get("aggregated_report")
                or "Scan complete — no report generated."
            )
            st.session_state.final_report = report
            st.session_state.phase = "done"
            cleanup_tmp()
            st.rerun()
        except Exception as e:
            st.error(f"❌ Scan error: {e}")
            st.exception(e)
            if st.button("🔄 Start Over"):
                reset()
