import sys

from mcp_drivers.base_driver import BaseMCPDriver


class JsMCPDriver(BaseMCPDriver):
    server_name = "eslint"
    command = sys.executable
    args = ["-m", "mcp_servers.js_server"]

    async def lint(self, path: str) -> list:
        return await self.call_tool("lint_javascript", {"path": path})

    async def lint_in_session(self, path: str) -> list:
        return await self.call_tool_in_session("lint_javascript", {"path": path})
