"""Run-identity helpers shared by the CLI/UI entry points and the parser node.

LangSmith does NOT reliably surface custom fields written onto
`get_current_run_tree().extra` for LangGraph-auto-instrumented nodes (see
`observability/tracing.py` history) — LangGraph's own instrumentation writes
its own `extra`/metadata during the run and can clobber additions made from
inside a node. The documented, reliable way to attach custom metadata to
every node's LangSmith trace in a LangGraph run is to pass it via the
`RunnableConfig` at invocation time: `config={"metadata": {...}}`. LangGraph
propagates `config.metadata` to the LangSmith trace of the run and of every
node inside it automatically.

This means run_id/repo_name/commit_sha must be known *before* the graph is
invoked (not derived inside the parser node as before) — trivial here since
the CLI/UI already has `user_input` (the path) before calling `.stream()`.
"""

import os
import subprocess
import uuid


def commit_sha(repo_path: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def build_run_metadata(user_input: str) -> dict:
    repo_path = user_input.strip() or "."
    return {
        "run_id": str(uuid.uuid4()),
        "repo_name": os.path.basename(os.path.normpath(repo_path)) or "unknown",
        "commit_sha": commit_sha(repo_path),
    }


def as_langgraph_config(run_metadata: dict, thread_id: str) -> dict:
    """Build the `.stream()`/`.invoke()` config: `configurable.thread_id` for
    LangGraph's checkpointer, plus `metadata`/`tags` so LangSmith attaches
    run_id/repo_name/commit_sha to every node's trace in this run."""
    return {
        "configurable": {"thread_id": thread_id},
        "metadata": {
            "run_id": run_metadata["run_id"],
            "repo_name": run_metadata["repo_name"],
            "commit_sha": run_metadata["commit_sha"],
        },
        "tags": [f"run_id:{run_metadata['run_id']}"],
    }
