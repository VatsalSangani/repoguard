import os
from typing import List

from langchain_openai import ChatOpenAI

from config import DEFAULT_MODEL, IGNORED_DIRS, LLM_TEMPERATURE, MAX_FILES_LIMIT, SUPPORTED_EXTENSIONS
from models.schemas import FileList
from observability.run_metadata import build_run_metadata
from observability.tracing import traced_node
from state import AgentState


def _walk_directory(root_dir: str) -> List[str]:
    found: List[str] = []
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for file in files:
            if file.endswith(SUPPORTED_EXTENSIONS):
                found.append(os.path.join(root, file))
    return found


def _resolve_path(path: str) -> List[str]:
    if os.path.isdir(path):
        return _walk_directory(path)
    if os.path.isfile(path):
        return [path]
    return []


@traced_node("parser")
def parser_node(state: AgentState) -> dict:
    print("\n--- 🔍 Step 1: Parser Agent ---")
    user_input = state["user_input"].strip()
    run_metadata = state.get("run_metadata") or build_run_metadata(user_input)

    # Hard logic: try direct filesystem resolution first
    files = _resolve_path(user_input)

    # LLM fallback: ask model to interpret the input as a path
    if not files:
        llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=LLM_TEMPERATURE)
        structured_llm = llm.with_structured_output(FileList)
        system_text = (
            "You are a file system assistant. The user will give you a path or a request.\n"
            "1. If it looks like a relative path (e.g. 'test_repo', 'src'), return it EXACTLY.\n"
            "2. Do NOT add '/path/to/' or make up folders."
        )
        response: FileList = structured_llm.invoke([
            ("system", system_text),
            ("user", user_input),
        ])

        cwd = os.getcwd()
        for path in response.paths:
            files.extend(_resolve_path(path) or _resolve_path(os.path.join(cwd, path)))

    # Deduplicate and cap
    files = list(set(files))
    if len(files) > MAX_FILES_LIMIT:
        print(f"   ⚠️ Repo too large. Truncating to {MAX_FILES_LIMIT} files.")
        files = files[:MAX_FILES_LIMIT]

    print(f"   Targeting {len(files)} files.")
    return {"target_files": files, "run_metadata": run_metadata, "repo_path": user_input}
