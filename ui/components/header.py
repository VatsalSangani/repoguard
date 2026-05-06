import streamlit as st


def render_header() -> None:
    st.markdown("# 🛡️ RepoGuard")
    st.markdown("**LangGraph Multi-Agent Code Security Scanner**")
    st.caption("Parser → Guardrails → Human Approval → Processor → Aggregator")
    st.divider()

    with st.expander("🏗️ Agent Architecture", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown("**🔍 Parser**")
            st.caption("Discovers files, filters by type, builds task list")
        with col2:
            st.markdown("**🛡️ Guardrails**")
            st.caption("Detects sensitive files, assesses risk level")
        with col3:
            st.markdown("**✋ Human Approval**")
            st.caption("You review scan plan before execution")
        with col4:
            st.markdown("**📊 Aggregator**")
            st.caption("GPT-4o-mini generates security report")

    st.divider()
