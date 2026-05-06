import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

st.set_page_config(page_title="RepoGuard", page_icon="🛡️", layout="wide")

from ui.styles import inject
from ui.state import init_state
from ui.components.header import render_header
from ui.pages import input_page, approval_page, scanning_page, results_page

inject()
init_state()
render_header()

_PAGES = {
    "input":    input_page.render,
    "approval": approval_page.render,
    "scanning": scanning_page.render,
    "done":     results_page.render,
}
_PAGES.get(st.session_state.phase, input_page.render)()

st.divider()
st.caption("**RepoGuard** — LangGraph Multi-Agent Security Scanner | GPT-4o-mini | AWS EC2")
