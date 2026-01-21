import sys
from pathlib import Path
from langchain.tools import tool
from schemas import (
    ProcessingInput, ProcessingOutput, PlannedToolCall
)

# Add parent directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Import the Real Tools (Ruff, Secrets, Markdown)
from tools.tools import markdownlint_impl, secrets_scan_impl, ruff_lint_impl

# ALIAS MAPPING
markdown_validator_tool = markdownlint_impl
secrets_validator_tool = secrets_scan_impl
python_validator_tool = ruff_lint_impl

@tool(args_schema=ProcessingInput)
def processing_agent(scan_result: any) -> str:
    """
    Converts the Parser's task list into a Tool Execution Plan.
    """
    if hasattr(scan_result, "tasks"):
        tasks = scan_result.tasks
    else:
        tasks = scan_result.get("tasks", [])
    
    plan = []
    
    for task in tasks:
        t_type = getattr(task, "type", None) or task.get("type")
        target = getattr(task, "target", None) or task.get("target")
        
        if t_type == "markdown_validate":
            plan.append(PlannedToolCall(
                tool="MarkdownValidator",
                args={"target": target},
                reason=f"Scan {Path(target).name} for markdown issues"
            ))
        elif t_type == "python_validate":
            plan.append(PlannedToolCall(
                tool="PythonCodeValidator",
                args={"target": target},
                reason=f"Lint {Path(target).name} with Ruff (MCP)"
            ))
        elif t_type == "secrets_scan":
            plan.append(PlannedToolCall(
                tool="SecretsValidator",
                args={"target": target},
                reason=f"Scan {Path(target).name} for secrets"
            ))

    return ProcessingOutput(plan=plan).model_dump_json()