import sys

from mcp_drivers.base_driver import BaseMCPDriver


class JsonMCPDriver(BaseMCPDriver):
    server_name = "ajv-spectral"
    command = sys.executable
    args = ["-m", "mcp_servers.json_server"]

    async def validate(self, path: str, schema_path: str | None = None) -> list:
        return await self.call_tool("validate_json", {"path": path, "schema_path": schema_path})

    async def validate_in_session(self, path: str, schema_path: str | None = None) -> list:
        return await self.call_tool_in_session("validate_json", {"path": path, "schema_path": schema_path})
