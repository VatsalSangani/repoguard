import sys

from mcp_drivers.base_driver import BaseMCPDriver


class SqlMCPDriver(BaseMCPDriver):
    server_name = "sqlfluff"
    command = sys.executable
    args = ["-m", "mcp_servers.sql_server"]

    async def lint(self, path: str, dialect: str = "ansi") -> list:
        return await self.call_tool("lint_sql", {"path": path, "dialect": dialect})

    async def lint_in_session(self, path: str, dialect: str = "ansi") -> list:
        return await self.call_tool_in_session("lint_sql", {"path": path, "dialect": dialect})
