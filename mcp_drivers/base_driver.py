"""Shared base class for MCP stdio driver clients.

Centralizes the connect → initialize → call_tool → teardown lifecycle plus
wire logging and timeout handling, so each language-specific driver only
needs to declare its server params and its own thin call wrapper.
"""

import asyncio
import os
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mcp_drivers.wire_logger import WireLogger
from observability.run_context import current_run_id

DEFAULT_MCP_TIMEOUT: int = 30


class BaseMCPDriver:
    """Base for stdio MCP client drivers with wire logging built in.

    Subclasses set `server_name`, `command`, and `args` (and optionally
    override `timeout_seconds`), then call `self.call_tool(tool_name, args)`
    for a one-shot invocation, or `async with driver:` + repeated
    `call_tool_in_session(...)` to reuse a single subprocess/session across
    many calls (e.g. scanning a batch of files).
    """

    server_name: str = "mcp-server"
    command: str = ""
    args: list[str] = []
    timeout_seconds: int = DEFAULT_MCP_TIMEOUT

    def __init__(self, run_id: str | None = None) -> None:
        self.run_id = run_id if run_id is not None else current_run_id.get()
        # On Windows, a spawned Python subprocess's stdio streams default to
        # the console codepage (cp1252/"charmap") rather than UTF-8 unless
        # told otherwise — any file content containing non-cp1252 characters
        # (emoji, arrows, smart quotes, etc.) then crashes the MCP server
        # with e.g. "'charmap' codec can't encode character '✅'".
        # Forcing UTF-8 mode here fixes it for every driver that spawns a
        # subprocess through this base class (Ruff via uvx, and our own
        # sql/js/json MCP servers), not just Ruff.
        env = os.environ.copy()
        env.setdefault("PYTHONUTF8", "1")
        env.setdefault("PYTHONIOENCODING", "utf-8")
        self.server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=env,
        )
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()
        self._wire = WireLogger(self.run_id, self.server_name)

    async def call_tool(self, tool_name: str, arguments: dict) -> Any:
        """One-shot connect + tools/call + teardown, for callers that only
        need a single invocation (e.g. a tool that scans one file)."""
        try:
            async with self:
                return await self.call_tool_in_session(tool_name, arguments)
        except asyncio.TimeoutError:
            return [_TimeoutContent(f"{self.server_name} timed out after {self.timeout_seconds}s")]

    async def __aenter__(self) -> "BaseMCPDriver":
        """Open one stdio connection + MCP session, reused for every
        subsequent `call_tool_in_session` call until `__aexit__`. Use this
        (`async with driver:`) when scanning multiple files/targets in one
        run so only a single subprocess is spawned instead of one per call.
        """
        transport = await self.exit_stack.enter_async_context(
            stdio_client(self.server_params)
        )
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(transport[0], transport[1])
        )
        await self._wire.logged("initialize", {}, self.session.initialize)
        await self._wire.logged("tools/list", {}, self.session.list_tools)
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.exit_stack.aclose()
        self.session = None

    async def call_tool_in_session(self, tool_name: str, arguments: dict) -> Any:
        """Issue one `tools/call` on the already-open session."""
        if self.session is None:
            raise RuntimeError(
                f"{self.server_name} driver has no open session — use `async with driver:` first"
            )
        result = await asyncio.wait_for(
            self._wire.logged(
                "tools/call",
                {"name": tool_name, "arguments": arguments},
                lambda: self.session.call_tool(tool_name, arguments=arguments),
            ),
            timeout=self.timeout_seconds,
        )
        return result.content


class _TimeoutContent:
    """Minimal stand-in for MCP TextContent, used only for timeout results."""

    def __init__(self, text: str) -> None:
        self.text = text
