import os
from typing import List

from langchain_openai import ChatOpenAI

from config import DEFAULT_MODEL, IGNORED_DIRS, LLM_TEMPERATURE, MAX_FILES_LIMIT, SUPPORTED_EXTENSIONS
from models.schemas import FileList
from observability.run_metadata import build_run_metadata
from observability.tracing import traced_node
from state import AgentState


def _walk_directory(root_dir: str) -> tuple[List[str], int]:
    """Returns (matched_files, total_files_seen) — total_files_seen counts
    every file under root_dir regardless of extension, so callers can
    report how many were dropped for not matching SUPPORTED_EXTENSIONS."""
    found: List[str] = []
    total = 0
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for file in files:
            total += 1
            if file.endswith(SUPPORTED_EXTENSIONS):
                found.append(os.path.join(root, file))
    return found, total


def _resolve_path(path: str) -> tuple[List[str], int]:
    if os.path.isdir(path):
        return _walk_directory(path)
    if os.path.isfile(path):
        return [path], 1
    return [], 0


@traced_node("parser")
def parser_node(state: AgentState) -> dict:
    print("\n--- 🔍 Step 1: Parser Agent ---")
    user_input = state["user_input"].strip()
    run_metadata = state.get("run_metadata") or build_run_metadata(user_input)

    # Hard logic: try direct filesystem resolution first
    files, total_found = _resolve_path(user_input)

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
            matched, seen = _resolve_path(path)
            if not matched:
                matched, seen = _resolve_path(os.path.join(cwd, path))
            files.extend(matched)
            total_found += seen

    # Deduplicate and cap — sorted() (not a bare set()) so the same files
    # survive every run in the same order, instead of whichever 30 a
    # non-deterministic set iteration happens to slice off.
    matched_extensions = len(set(files))
    files = sorted(set(files))
    dropped_by_limit = max(matched_extensions - MAX_FILES_LIMIT, 0)
    if dropped_by_limit:
        files = files[:MAX_FILES_LIMIT]

    discovery_stats = {
        "total_found": total_found,
        "matched_extensions": matched_extensions,
        "scanning": len(files),
        "dropped_by_limit": dropped_by_limit,
    }
    print(
        f"   Found {total_found} files, {matched_extensions} matched supported "
        f"extensions, scanning {len(files)}"
        + (f" ({dropped_by_limit} dropped by MAX_FILES_LIMIT)" if dropped_by_limit else "")
    )
    return {
        "target_files": files,
        "run_metadata": run_metadata,
        "repo_path": user_input,
        "file_discovery_stats": discovery_stats,
    }
