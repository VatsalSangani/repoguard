import os
import shutil

import streamlit as st

_DEFAULTS: dict = {
    "phase": "input",
    "app_graph": None,
    "thread_config": None,
    "snapshot": None,
    "tmp_dir": None,
    "final_report": None,
}


def init_state() -> None:
    for key, value in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


def cleanup_tmp() -> None:
    if st.session_state.tmp_dir and os.path.exists(st.session_state.tmp_dir):
        shutil.rmtree(st.session_state.tmp_dir)
        st.session_state.tmp_dir = None


def reset() -> None:
    cleanup_tmp()
    for key in _DEFAULTS:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()
