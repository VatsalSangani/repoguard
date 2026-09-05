from config import MCP_COMMAND, MCP_SERVER, MCP_TOOL_ARG, MCP_TOOL_NAME
from mcp_drivers.base_driver import BaseMCPDriver


class RuffMCPDriver(BaseMCPDriver):
    server_name = "ruff"
    command = MCP_COMMAND
    args = [MCP_SERVER]

    async def run_scan(self, code_content: str) -> list:
        """One-shot: connect, scan a single snippet, disconnect.

        Prefer `async with RuffMCPDriver() as driver:` + `run_scan_in_session`
        when scanning multiple files, so one subprocess is reused instead of
        spawning a new `uvx mcp-server-analyzer` process per file.
        """
        return await self.call_tool(MCP_TOOL_NAME, {MCP_TOOL_ARG: code_content})

    async def run_scan_in_session(self, code_content: str) -> list:
        """Scan a single snippet on the session opened by `async with`."""
        return await self.call_tool_in_session(MCP_TOOL_NAME, {MCP_TOOL_ARG: code_content})
