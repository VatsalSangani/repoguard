"""Phase 4 — Display the final security report and offer download."""

import streamlit as st

from ui.state import reset


def render() -> None:
    st.subheader("📊 Security Report")
    st.success("✅ Scan complete!")

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
