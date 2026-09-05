"""Input Page — repo URL/path input, supported-language overview."""

import tempfile
import uuid
from pathlib import Path
from typing import List, Tuple

import streamlit as st

from config import SUPPORTED_EXTENSIONS
from observability.run_metadata import as_langgraph_config, build_run_metadata
from ui.components.badges import render_language_badges, render_language_tools_table


def _clone_repo(url: str) -> Tuple[str, List[str]]:
    """Clone `url` into a temp dir and return (tmp_dir, preview_files).

    `preview_files` is ONLY for the "Cloned! Found N files" message shown
    right after cloning — the actual scan re-derives the file list from
    `tmp_dir` itself via the real parser walk (see `_run_phase1`), so this
    preview uses the same SUPPORTED_EXTENSIONS the parser will actually use
    instead of a separate, easily-drifting extension list.
    """
    import git
    tmp_dir = tempfile.mkdtemp()
    git.Repo.clone_from(url, tmp_dir)
    files: List[str] = [
        str(p) for p in Path(tmp_dir).rglob("*")
        if p.is_file() and p.name.endswith(SUPPORTED_EXTENSIONS) and ".git" not in str(p)
    ]
    return tmp_dir, files


def _run_phase1(files: List[str], scan_path: str) -> None:
    from graph.builder import build_graph
    from state import AgentState

    app = build_graph()

    if scan_path:
        # GitHub URL mode: hand the parser the real directory so it does
        # its own recursive walk (respecting IGNORED_DIRS/SUPPORTED_EXTENSIONS
        # and reporting file_discovery_stats) instead of guessing a path
        # from a mangled, space-joined string of every file we pre-found.
        user_input = scan_path
        initial_target_files: List[str] = []
        run_metadata = build_run_metadata(scan_path)
    else:
        # File List mode: the user already gave us the exact files to scan
        # — there's no single directory to walk, so pass them through
        # as-is; parser_node trusts a pre-populated target_files list
        # instead of trying to resolve one from user_input.
        user_input = ""
        initial_target_files = files
        run_metadata = build_run_metadata(files[0] if files else "manual-file-list")

    config = as_langgraph_config(run_metadata, thread_id=str(uuid.uuid4()))
    initial_state = AgentState(
        user_input=user_input,
        target_files=initial_target_files,
        raw_scan_results=[],
        final_report="",
        risk_level="normal",
        risk_reason="",
        guardrail_status="",
        error="",
        run_metadata=run_metadata,
    )

    for _ in app.stream(initial_state, config=config):
        pass

    snapshot = app.get_state(config)
    st.session_state.app_graph = app
    st.session_state.thread_config = config
    st.session_state.snapshot = snapshot
    st.session_state.run_metadata = run_metadata
    st.session_state.node_progress = {"parser": "done", "guardrails": "done"}
    st.session_state.phase = "approval"
    st.rerun()


def render() -> None:
    st.markdown(
        "<div class='rg-card'>"
        "<h4>📁 Scan a Repository</h4>"
        "<p style='color:#8b949e;margin-bottom:0.25rem;'>"
        "RepoGuard checks for hardcoded secrets &amp; credentials, code-quality issues, "
        "and language-specific security vulnerabilities — dispatched automatically to the "
        "right tool for each file type."
        "</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("**Supported languages**")
    render_language_badges()
    with st.expander("Which tool scans which language?", expanded=False):
        render_language_tools_table()

    st.divider()

    input_mode = st.radio("Input Mode", ["GitHub URL", "File List"], horizontal=True)

    repo_url = ""
    files_input = ""

    if input_mode == "GitHub URL":
        repo_url = st.text_input(
            "GitHub Repository URL",
            placeholder="https://github.com/username/repo",
        )
        if repo_url:
            st.info("⚠️ Repository will be cloned temporarily for scanning")
    else:
        files_input = st.text_area(
            "Enter file paths (one per line)",
            placeholder="src/main.py\nREADME.md\nconfig.py",
            height=150,
        )

    if st.button("🚀 Start Security Scan", type="primary", use_container_width=True):
        files: List[str] = []
        scan_path = ""

        if input_mode == "GitHub URL":
            if not repo_url.strip():
                st.error("Please enter a GitHub URL")
                st.stop()
            with st.spinner("📥 Cloning repository..."):
                try:
                    tmp_dir, files = _clone_repo(repo_url.strip())
                    st.session_state.tmp_dir = tmp_dir
                    scan_path = tmp_dir
                    st.success(f"✅ Cloned! Found {len(files)} files")
                except Exception as e:
                    st.error(f"❌ Clone failed: {e}")
                    st.stop()
        else:
            if not files_input.strip():
                st.error("Please enter at least one file path")
                st.stop()
            files = [f.strip() for f in files_input.strip().split("\n") if f.strip()]

        with st.spinner("🔍 Running Parser + Guardrails..."):
            try:
                _run_phase1(files, scan_path)
            except Exception as e:
                st.error(f"❌ Error: {e}")
                st.exception(e)
