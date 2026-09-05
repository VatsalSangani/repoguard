import operator
from typing import TypedDict, List, Annotated, Dict, Any, Optional

class AgentState(TypedDict, total=False):
    # User Input
    user_input: str

    # Pipeline Data
    target_files: List[str]                          # List of files to scan
    raw_scan_results: Annotated[List[Dict[str, Any]], operator.add] # Accumulates tool logs
    final_report: str                                # Markdown output

    # Safety & Control Flags
    risk_level: str       # "normal" or "high"
    risk_reason: str      # e.g. "Found .env file"
    guardrail_status: str # "pass" or "fail"
    error: str            # Error message if blocked

    # Observability (Phase 0)
    run_metadata: Dict[str, Any]  # run_id, repo_name, commit_sha, timestamp, tool_versions

    # Router architecture (Phase 1)
    repo_path: str
    file_manifest: Dict[str, List[str]]         # {"py": [...], "sql": [...], "js": [...], "json": [...]}
    guardrail_decisions: Dict[str, List[str]]   # {"safe_scan": [...], "excluded": [...]}
    tool_results: Dict[str, List[Dict[str, Any]]]  # findings keyed by language
    aggregated_report: Optional[Dict[str, Any]]