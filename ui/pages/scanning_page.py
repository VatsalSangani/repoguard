"""Scanning Page — resumes the paused graph and streams live per-node
progress: Router -> [language sub-agents] -> Aggregator."""

import time

import streamlit as st

from ui.components.file_manifest import render_file_status_table, render_language_counts
from ui.state import cleanup_tmp, record_scan_history, reset

_NODE_LABELS = {
    "router": "🧭 Router — grouping files by language, running secrets pre-scan",
    "python_agent": "🐍 Python Agent — Ruff + detect-secrets",
    "sql_agent": "🗄️ SQL Agent — sqlfluff",
    "js_agent": "📜 JS/TS Agent — ESLint + eslint-plugin-security",
    "json_agent": "🧾 JSON Agent — ajv + Spectral",
    "aggregator": "📝 Aggregator — generating the security report",
}
_LANG_TO_NODE = {"py": "python_agent", "sql": "sql_agent", "js": "js_agent", "json": "json_agent"}
_NODE_TO_LANG = {v: k for k, v in _LANG_TO_NODE.items()}


def _step_html(node: str, status: str) -> str:
    label = _NODE_LABELS.get(node, node)
    icon = {"done": "✅", "running": "🔄", "pending": "⏳"}[status]
    css_class = f"rg-step-label-{status}"
    return f"<div class='rg-step'>{icon} <span class='{css_class}'>{label}</span></div>"


def render() -> None:
    st.subheader("⚙️ Running Security Scan")

    if st.session_state.scan_start_time is None:
        st.session_state.scan_start_time = time.perf_counter()

    node_progress: dict = dict(st.session_state.node_progress or {"parser": "done", "guardrails": "done"})
    node_progress.setdefault("router", "pending")
    file_manifest: dict = {}
    tool_results: dict = {}
    completed_languages: set = set()

    steps_ph = st.empty()
    manifest_ph = st.empty()
    counters_ph = st.empty()

    def redraw(running_languages: set = frozenset()) -> None:
        with steps_ph.container():
            st.markdown("**Pipeline Progress**")
            st.markdown(_step_html("parser", "done"), unsafe_allow_html=True)
            st.markdown(_step_html("guardrails", "done"), unsafe_allow_html=True)
            for node in ["router"] + [_LANG_TO_NODE[lang] for lang in file_manifest if file_manifest.get(lang)] + ["aggregator"]:
                st.markdown(_step_html(node, node_progress.get(node, "pending")), unsafe_allow_html=True)

        with manifest_ph.container():
            if file_manifest:
                st.markdown("**File Manifest**")
                render_language_counts(file_manifest)
                render_file_status_table(file_manifest, tool_results, completed_languages, running_languages)

        with counters_ph.container():
            elapsed = time.perf_counter() - st.session_state.scan_start_time
            files_scanned = sum(len(file_manifest.get(lang, [])) for lang in completed_languages)
            findings_so_far = sum(len(v) for v in tool_results.values())
            cols = st.columns(3)
            cols[0].metric("Files Scanned", files_scanned)
            cols[1].metric("Findings So Far", findings_so_far)
            cols[2].metric("Elapsed", f"{elapsed:.1f}s")

    redraw()  # initial paint: parser/guardrails done, router about to run

    try:
        node_progress["router"] = "running"
        redraw()

        pending_sub_agents: set = set()
        for update in st.session_state.app_graph.stream(None, st.session_state.thread_config):
            for node_name, state_update in update.items():
                if node_name == "__interrupt__":
                    continue

                if node_name == "router":
                    node_progress["router"] = "done"
                    file_manifest = state_update.get("file_manifest", {}) or file_manifest
                    tool_results.update(state_update.get("tool_results", {}) or {})
                    pending_sub_agents = {
                        _LANG_TO_NODE[lang] for lang, files in file_manifest.items() if files
                    }
                    for node in pending_sub_agents:
                        node_progress.setdefault(node, "pending")
                    node_progress["aggregator"] = "pending"
                    redraw(running_languages=set(_NODE_TO_LANG.get(n) for n in pending_sub_agents))

                elif node_name in _NODE_TO_LANG:
                    node_progress[node_name] = "done"
                    tool_results.update(state_update.get("tool_results", {}) or {})
                    completed_languages.add(_NODE_TO_LANG[node_name])
                    pending_sub_agents.discard(node_name)
                    redraw(running_languages=set(_NODE_TO_LANG.get(n) for n in pending_sub_agents))

                elif node_name == "aggregator":
                    node_progress["aggregator"] = "done"
                    redraw()

        result = st.session_state.app_graph.get_state(st.session_state.thread_config).values
        report = (
            result.get("final_report")
            or result.get("report")
            or result.get("aggregated_report")
            or "Scan complete — no report generated."
        )
        st.session_state.final_report = report
        st.session_state.final_state = result
        st.session_state.node_progress = node_progress

        total_findings = sum(len(v) for v in (result.get("tool_results") or {}).values())
        record_scan_history(total_findings)

        st.session_state.phase = "done"
        cleanup_tmp()
        st.rerun()

    except Exception as e:
        st.error(f"❌ Scan error: {e}")
        st.exception(e)
        if st.button("🔄 Start Over"):
            reset()
