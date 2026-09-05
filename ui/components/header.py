import streamlit as st


def render_header() -> None:
    st.markdown("# 🛡️ RepoGuard")
    st.markdown("**LangGraph Multi-Agent Code Security Scanner**")
    st.caption("Parser → Guardrails → Human Approval → Router → Sub-Agents → Aggregator")
    st.divider()

    with st.expander("🏗️ Agent Architecture", expanded=False):
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.markdown("**🔍 Parser**")
            st.caption("Discovers files, filters by type")
        with col2:
            st.markdown("**🛡️ Guardrails**")
            st.caption("Detects sensitive files, assesses risk")
        with col3:
            st.markdown("**🧭 Router**")
            st.caption("Groups files by language, dispatches sub-agents")
        with col4:
            st.markdown("**🐍🗄️📜🧾 Sub-Agents**")
            st.caption("Python / SQL / JS / JSON — run in parallel")
        with col5:
            st.markdown("**📊 Aggregator**")
            st.caption("GPT-4o-mini generates the security report")

    st.divider()
