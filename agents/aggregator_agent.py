from langchain.tools import tool
from schemas import AggregatorInput, FinalReport
import json

@tool(args_schema=AggregatorInput)
def aggregator_agent(parser_summary: dict, results: list) -> str:
    """
    Compiles validation results into a Final Report with a human-readable summary.
    """
    findings = []
    critical_issues = []
    
    total_files_scanned = 0
    total_issues_found = 0
    
    # 1. Process Results
    for r in results:
        if hasattr(r, "dict"): r = r.dict()
        
        tool_name = r.get("tool", "Unknown Tool")
        is_ok = r.get("ok", True)
        summary_text = r.get("summary", "No summary.")
        issues = r.get("issues", [])
        meta = r.get("meta", {})

        files_count = meta.get("files_checked", 0)
        total_files_scanned += files_count
        total_issues_found += len(issues)

        findings.append(f"[{tool_name}] {summary_text}")

        if not is_ok:
            for issue in issues:
                line_num = issue.get('line')
                line_str = f" at Line {line_num}" if line_num is not None else ""
                
                # Truncate overly long messages from MCP
                raw_msg = issue.get('message', 'Unknown Error')
                if len(raw_msg) > 300:
                    raw_msg = raw_msg[:300] + "..."
                
                msg = f"[{tool_name}] {raw_msg}{line_str}"
                critical_issues.append(msg)

    # 2. Generate Next Steps
    next_steps = []
    if critical_issues:
        next_steps.append("Review the critical findings listed above.")
        
        tools_used = [r.get("tool") for r in results]
        
        # Specific Secret Logic
        if "SecretsValidator" in tools_used and any("Secret" in i for i in critical_issues):
            next_steps.append("URGENT: Rotate exposed secrets and add them to `.gitignore`.")
            
        # Specific Python Logic
        if "PythonCodeValidator" in tools_used:
            next_steps.append("Run `ruff check .` locally to fix any linting errors.")
    else:
        next_steps.append("No critical issues found. Code is safe to merge.")

    # 3. Build Data Objects
    final_summary = {
        "scan_target": parser_summary.get("scan_target", "Dynamic Batch Scan"),
        "total_files_scanned": total_files_scanned,
        "total_issues_found": total_issues_found,
        "tools_executed": len(results)
    }

    report_obj = FinalReport(
        summary=final_summary,
        critical_findings=critical_issues, 
        next_steps=next_steps
    )
    
    json_output = report_obj.model_dump_json(indent=2)

    # 4. Construct Human-Readable Markdown Output
    # This matches the style you requested
    markdown_report = f"""
### Key Findings:
- **Total Files Scanned:** {total_files_scanned}
- **Total Issues Found:** {total_issues_found}
- **Tools Executed:** {len(results)}

### Critical Findings:
"""
    if critical_issues:
        for issue in critical_issues:
            markdown_report += f"- {issue}\n"
    else:
        markdown_report += "- None. Great job!\n"

    markdown_report += "\n### Recommended Next Steps:\n"
    for idx, step in enumerate(next_steps, 1):
        markdown_report += f"{idx}. {step}\n"

    # Append the JSON block so the Main Agent can still save it to a file
    markdown_report += f"\n```json\n{json_output}\n```"
    
    return markdown_report