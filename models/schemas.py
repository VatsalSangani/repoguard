from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, ValidationError


class FileList(BaseModel):
    """Strict output format for the Parser Agent."""

    paths: List[str] = Field(
        ...,
        description="A list of valid file paths found in the directory.",
    )


class Finding(BaseModel):
    """One issue reported by a language-specific MCP tool.

    Every sub-agent (Python/SQL/JS/JSON) normalizes its underlying tool's
    raw output into a list of these before writing to
    `state["tool_results"][<language>]`, so the aggregator has one uniform
    shape to read regardless of which tool produced the finding.
    """

    file: str
    line: int
    rule: str
    severity: Literal["high", "medium", "low", "info"]
    message: str
    tool: str  # which MCP tool produced this (e.g. "lint_sql", "ruff-check")


class RunMetadata(BaseModel):
    """Identity of one scan run, threaded through state and LangSmith config."""

    run_id: str
    repo_name: str
    commit_sha: str
    timestamp: Optional[str] = None
    tool_versions: Dict[str, str] = Field(default_factory=dict)


def validate_state_slice(state: Dict[str, Any], model: type[BaseModel], keys: Optional[List[str]] = None) -> None:
    """Validate a subset of graph state against a Pydantic model at a node's
    entry/exit boundary. Raises `pydantic.ValidationError` immediately (with
    the exact field, expected type, and received type) rather than letting a
    malformed state update silently propagate downstream.

    `keys` restricts validation to those fields only (useful when `state`
    carries many keys the model doesn't declare); when omitted, every field
    the model declares is pulled from `state` if present.
    """
    field_names = keys if keys is not None else list(model.model_fields.keys())
    payload = {k: state[k] for k in field_names if k in state}
    try:
        model.model_validate(payload)
    except ValidationError:
        raise
