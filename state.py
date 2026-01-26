import operator
from typing import TypedDict, List, Annotated, Dict, Any

class AgentState(TypedDict):
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