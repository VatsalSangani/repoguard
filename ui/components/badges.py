import streamlit as st

# One entry per language RepoGuard's Router Agent dispatches to a sub-agent
# for (see agents/router.py LANGUAGE_TO_NODE) — kept in sync manually since
# this is presentation-only metadata, not derived from the graph.
SUPPORTED_LANGUAGES = [
    {"icon": "🐍", "label": "Python", "tools": "Ruff + detect-secrets"},
    {"icon": "🗄️", "label": "SQL", "tools": "sqlfluff"},
    {"icon": "📜", "label": "JavaScript / TypeScript", "tools": "ESLint + eslint-plugin-security"},
    {"icon": "🧾", "label": "JSON", "tools": "ajv + Spectral"},
]


def render_language_badges() -> None:
    badges_html = "".join(
        f"<span class='rg-badge'>{lang['icon']} {lang['label']}</span>"
        for lang in SUPPORTED_LANGUAGES
    )
    st.markdown(f"<div class='rg-badge-row'>{badges_html}</div>", unsafe_allow_html=True)


def render_language_tools_table() -> None:
    for lang in SUPPORTED_LANGUAGES:
        st.markdown(f"- {lang['icon']} **{lang['label']}** → {lang['tools']}")
