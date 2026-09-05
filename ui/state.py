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
    "run_metadata": None,       # {run_id, repo_name, commit_sha}
    "node_progress": {},        # {node_name: "pending" | "running" | "done"}
    "scan_start_time": None,    # time.perf_counter() when scanning began
    "scan_history": [],         # list of {repo_name, run_id, finding_count, timestamp}
    "final_state": None,        # full final pipeline state dict (for results page)
}


def init_state() -> None:
    for key, value in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


def cleanup_tmp() -> None:
    if st.session_state.tmp_dir and os.path.exists(st.session_state.tmp_dir):
        shutil.rmtree(
            st.session_state.tmp_dir,
            onexc=lambda func, path, exc: (os.chmod(path, 0o777), func(path)),
        )
        st.session_state.tmp_dir = None


def record_scan_history(finding_count: int) -> None:
    import datetime

    meta = st.session_state.run_metadata or {}
    st.session_state.scan_history.insert(0, {
        "repo_name": meta.get("repo_name", "unknown"),
        "run_id": meta.get("run_id", "unknown"),
        "finding_count": finding_count,
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
    })
    st.session_state.scan_history = st.session_state.scan_history[:10]


def reset() -> None:
    cleanup_tmp()
    history = st.session_state.scan_history
    for key in _DEFAULTS:
        if key in st.session_state:
            del st.session_state[key]
    init_state()
    st.session_state.scan_history = history
    st.rerun()
