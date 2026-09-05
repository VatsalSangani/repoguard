"""Explicit LangSmith tagging for LangGraph nodes.

LangGraph already auto-creates one LangSmith span per node execution
(LangSmith env-var tracing auto-instruments the graph runner), so wrapping a
node in a *second* `@traceable` span of the same name only produces a
confusing duplicate nested span with no new information. Instead, this
module reaches into the span LangGraph already created via
`get_current_run_tree()` and enriches it in place: adds run-level tags
(run_id, repo_name, commit_sha), and attaches duration/diff/token-usage as
extra metadata — all on the *same* span, not a child of it.
"""

import time
from functools import wraps
from typing import Any, Callable, Dict

from langsmith.run_helpers import get_current_run_tree


def _diff_state(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """Return only the keys `after` added or changed relative to `before`."""
    diff = {}
    for key, value in after.items():
        if key not in before or before[key] != value:
            diff[key] = value
    return diff


def _run_tags(state: Dict[str, Any]) -> Dict[str, Any]:
    meta = state.get("run_metadata") or {}
    return {
        "run_id": meta.get("run_id", "unknown"),
        "repo_name": meta.get("repo_name", "unknown"),
        "commit_sha": meta.get("commit_sha", "unknown"),
    }


def traced_node(name: str) -> Callable:
    """Enrich the LangSmith span LangGraph auto-creates for this node.

    Tags the current run with run_id/repo_name/commit_sha and attaches
    duration/state-diff/token-usage as metadata on that same span — no new
    child span is created, avoiding the duplicate-nesting LangGraph's own
    auto-tracing would otherwise produce.
    """

    def decorator(node_fn: Callable[[Dict[str, Any]], Dict[str, Any]]) -> Callable:
        @wraps(node_fn)
        def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
            start = time.perf_counter()
            result = node_fn(state)
            duration_ms = int((time.perf_counter() - start) * 1000)

            # The node that creates run_metadata (parser) won't have it in
            # its own input state — fall back to the value it just returned
            # so that span still gets tagged with the real run_id.
            tags = _run_tags(state)
            if tags["run_id"] == "unknown" and isinstance(result, dict) and result.get("run_metadata"):
                tags = _run_tags(result)

            token_usage = None
            if isinstance(result, dict):
                for value in result.values():
                    usage = getattr(value, "response_metadata", {}) if hasattr(value, "response_metadata") else None
                    if usage and "token_usage" in usage:
                        token_usage = usage["token_usage"]
                        break

            run_tree = get_current_run_tree()
            if run_tree is not None:
                run_tree.tags = list(set((run_tree.tags or []) + [
                    f"run_id:{tags['run_id']}",
                    f"repo_name:{tags['repo_name']}",
                    f"commit_sha:{tags['commit_sha']}",
                ]))
                # LangSmith's UI reads the "Metadata" panel from extra["metadata"],
                # not from top-level keys on `extra` — nest it there.
                run_tree.extra = {
                    **(run_tree.extra or {}),
                    "metadata": {
                        **((run_tree.extra or {}).get("metadata") or {}),
                        "node": name,
                        "duration_ms": duration_ms,
                        "diff_keys": list(_diff_state(state, result or {}).keys()),
                        "token_usage": token_usage,
                        **tags,
                    },
                }

            print(
                f"   [trace] node={name} duration_ms={duration_ms} "
                f"diff_keys={list(_diff_state(state, result or {}).keys())} "
                f"token_usage={token_usage} "
                f"run_id={tags['run_id']} repo={tags['repo_name']} commit={tags['commit_sha']}"
            )
            return result

        return wrapper

    return decorator
