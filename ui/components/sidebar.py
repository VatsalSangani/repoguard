import streamlit as st


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## 🛡️ RepoGuard")
        st.caption("Multi-Agent Code Security Scanner")
        st.divider()

        meta = st.session_state.get("run_metadata")
        st.markdown("**Current Run**")
        if meta:
            st.code(
                f"run_id     {meta.get('run_id', 'unknown')[:8]}…\n"
                f"repo       {meta.get('repo_name', 'unknown')}\n"
                f"commit     {meta.get('commit_sha', 'unknown')[:12]}",
                language=None,
            )
        else:
            st.caption("No active run yet.")

        st.divider()
        st.markdown("**Scan History**")
        history = st.session_state.get("scan_history") or []
        if not history:
            st.caption("No scans yet this session.")
        else:
            for entry in history:
                st.markdown(
                    f"<div class='rg-history-item'>"
                    f"<b>{entry['repo_name']}</b> — {entry['finding_count']} finding(s)"
                    f"<br/>{entry['timestamp']} · run {entry['run_id'][:8]}…"
                    f"</div>",
                    unsafe_allow_html=True,
                )
