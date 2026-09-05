import streamlit as st

_CSS = """
<style>
:root {
    --rg-bg: #0d1117;
    --rg-surface: #161b22;
    --rg-border: #30363d;
    --rg-text: #c9d1d9;
    --rg-text-dim: #8b949e;
    --rg-accent: #58a6ff;
    --rg-green: #3fb950;
    --rg-red: #f85149;
    --rg-orange: #d29922;
    --rg-yellow: #e3b341;
    --rg-blue: #58a6ff;
}

body, .stApp { background-color: var(--rg-bg); color: var(--rg-text); }

/* Buttons */
.stButton>button {
    background-color: #21262d;
    color: var(--rg-text);
    border: 1px solid var(--rg-border);
    border-radius: 8px;
    font-weight: 500;
    transition: border-color 0.15s ease, background-color 0.15s ease;
}
.stButton>button:hover { border-color: var(--rg-accent); background-color: #262c36; }
.stButton>button[kind="primary"] {
    background-color: var(--rg-green); color: white; border: none;
}
.stButton>button[kind="primary"]:hover { background-color: #56d364; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: var(--rg-surface);
    border-right: 1px solid var(--rg-border);
}

/* Cards */
.rg-card {
    background-color: var(--rg-surface);
    border: 1px solid var(--rg-border);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
}
.rg-card h4 { margin-top: 0; }

/* Language badges */
.rg-badge-row { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 0.75rem 0 1rem 0; }
.rg-badge {
    display: inline-flex; align-items: center; gap: 0.4rem;
    background-color: #1c2128; border: 1px solid var(--rg-border);
    border-radius: 999px; padding: 0.3rem 0.85rem;
    font-size: 0.85rem; color: var(--rg-text);
}

/* Severity pills */
.rg-pill {
    display: inline-block; border-radius: 999px; padding: 0.15rem 0.65rem;
    font-size: 0.78rem; font-weight: 600; letter-spacing: 0.02em; text-transform: uppercase;
}
.rg-pill-critical, .rg-pill-high { background-color: rgba(248,81,73,0.15); color: var(--rg-red); border: 1px solid rgba(248,81,73,0.4); }
.rg-pill-medium { background-color: rgba(210,153,34,0.15); color: var(--rg-orange); border: 1px solid rgba(210,153,34,0.4); }
.rg-pill-low, .rg-pill-info { background-color: rgba(88,166,255,0.15); color: var(--rg-blue); border: 1px solid rgba(88,166,255,0.4); }

/* Status icons row for file manifest */
.rg-status-pending { color: var(--rg-text-dim); }
.rg-status-scanning { color: var(--rg-yellow); }
.rg-status-done { color: var(--rg-green); }
.rg-status-error { color: var(--rg-red); }

/* Sidebar scan history entries */
.rg-history-item {
    border-left: 2px solid var(--rg-border); padding: 0.35rem 0 0.35rem 0.6rem;
    margin-bottom: 0.4rem; font-size: 0.82rem; color: var(--rg-text-dim);
}
.rg-history-item b { color: var(--rg-text); }

/* Progress step list */
.rg-step { display: flex; align-items: center; gap: 0.6rem; padding: 0.3rem 0; font-size: 0.95rem; }
.rg-step-label-done { color: var(--rg-green); }
.rg-step-label-running { color: var(--rg-yellow); font-weight: 600; }
.rg-step-label-pending { color: var(--rg-text-dim); }
</style>
"""


def inject() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
