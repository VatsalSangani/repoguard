"""Router Agent: groups guardrail-approved files by language and fans out
to the relevant per-language sub-agent(s).

Runs after Guardrails, before the language sub-agents. Two responsibilities:
  1. Build `file_manifest` — files grouped by extension.
  2. Run detect-secrets once, since it's language-agnostic and should cover
     every file type, not just Python. Runs here (not per sub-agent) to
     avoid rescanning the same files multiple times, and scans exactly
     `target_files` (not the raw repo path) so it still honors whatever the
     Guardrails HITL step decided (e.g. Safe Scan excluding .env files).
"""

from typing import Any, Dict, List

from agents.lang_agents._shared import from_legacy_issues
from observability.tracing import traced_node
from state import AgentState
from tools.secrets_tool import secrets_scan_impl

_EXTENSION_TO_LANGUAGE = {
    ".py": "py",
    ".sql": "sql",
    ".js": "js",
    ".jsx": "js",
    ".ts": "js",
    ".tsx": "js",
    ".json": "json",
}

# Sub-agent node names, in the order `route_after_router` should list them.
LANGUAGE_TO_NODE = {
    "py": "python_agent",
    "sql": "sql_agent",
    "js": "js_agent",
    "json": "json_agent",
}


def _build_file_manifest(target_files: List[str]) -> Dict[str, List[str]]:
    manifest: Dict[str, List[str]] = {lang: [] for lang in LANGUAGE_TO_NODE}
    for f in target_files:
        for ext, lang in _EXTENSION_TO_LANGUAGE.items():
            if f.endswith(ext):
                manifest[lang].append(f)
                break
    return manifest


def _run_secrets_prescan(target_files: List[str]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for file_path in target_files:
        try:
            result = secrets_scan_impl.invoke({"target": file_path})
            findings.extend(from_legacy_issues("detect-secrets", result))
        except Exception as e:
            findings.append({
                "file": file_path, "line": 1, "rule": "SECRETS_SCAN_ERROR",
                "severity": "medium", "message": str(e), "tool": "detect-secrets",
            })
    return findings


@traced_node("router")
def router_node(state: AgentState) -> dict:
    print("\n--- 🧭 Step 2: Router Agent ---")
    target_files = state.get("target_files", [])
    file_manifest = _build_file_manifest(target_files)
    secrets_findings = _run_secrets_prescan(target_files)

    counts = {lang: len(files) for lang, files in file_manifest.items()}
    print(f"   file_manifest: {counts}")
    print(f"   secrets pre-scan: {len(secrets_findings)} finding(s)")

    return {
        "file_manifest": file_manifest,
        "tool_results": {"secrets": secrets_findings},
    }


def route_after_router(state: AgentState) -> List[str]:
    """Fan out only to sub-agents whose language has ≥1 file. LangGraph only
    waits on edges actually traversed, so `aggregator` fires once exactly
    once every dispatched sub-agent below has completed."""
    file_manifest = state.get("file_manifest", {})
    active = [LANGUAGE_TO_NODE[lang] for lang, files in file_manifest.items() if files]
    return active or ["aggregator"]
