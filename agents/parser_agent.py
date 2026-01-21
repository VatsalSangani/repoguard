import shlex
from pathlib import Path
from langchain.tools import tool
from schemas import ParserInput, ParserOutput, Task

@tool(args_schema=ParserInput)
def parser_agent(paths_str: str) -> str:
    """
    Analyzes input paths and groups them into efficient batch tasks.
    """
    try:
        raw_paths = shlex.split(paths_str)
    except ValueError:
        raw_paths = paths_str.split()

    tasks = []
    errors = []

    for raw_path in raw_paths:
        p = Path(raw_path).resolve()

        if not p.exists():
            errors.append(f"Path not found: {raw_path}")
            continue

        if p.is_dir():
            # Batch Mode: Scan whole folder
            tasks.append(Task(type="secrets_scan", target=str(p)))
            if any(p.rglob("*.py")):
                tasks.append(Task(type="python_validate", target=str(p)))
            if any(p.rglob("*.md")) or any(p.rglob("*.mdx")):
                tasks.append(Task(type="markdown_validate", target=str(p)))

        elif p.is_file():
            # Single File Mode
            tasks.append(Task(type="secrets_scan", target=str(p)))
            if p.suffix.lower() == ".py":
                tasks.append(Task(type="python_validate", target=str(p)))
            elif p.suffix.lower() in {".md", ".mdx"}:
                tasks.append(Task(type="markdown_validate", target=str(p)))

    return ParserOutput(
        tasks=tasks,
        error="; ".join(errors) if errors else None
    ).model_dump_json()