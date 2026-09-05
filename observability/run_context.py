"""Ambient run_id for code paths that can't take it as an explicit argument.

MCP driver instances (e.g. `RuffMCPDriver()`) are constructed deep inside
LangChain `@tool`-decorated functions that only accept `target: str` — there
is no clean way to thread `run_id` through that call signature. Nodes set
the current run's id here once at the start of a graph invocation; drivers
read it as their default so wire logs land in the correct `logs/{run_id}/`
directory without changing any tool signatures.
"""

from contextvars import ContextVar

current_run_id: ContextVar[str] = ContextVar("current_run_id", default="unknown")
