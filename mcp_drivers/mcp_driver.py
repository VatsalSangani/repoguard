import asyncio
import os
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import MCP_COMMAND, MCP_SERVER, MCP_TOOL_NAME, MCP_TOOL_ARG


class RuffMCPDriver:
    def __init__(self) -> None:
        self.server_params = StdioServerParameters(
            command=MCP_COMMAND,
            args=[MCP_SERVER],
            env=os.environ.copy(),
        )
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()

    async def run_scan(self, code_content: str) -> list:
        """Connect to the MCP server, send code content, return results."""
        try:
            transport = await self.exit_stack.enter_async_context(
                stdio_client(self.server_params)
            )
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(transport[0], transport[1])
            )
            await self.session.initialize()

            result = await self.session.call_tool(
                MCP_TOOL_NAME,
                arguments={MCP_TOOL_ARG: code_content},
            )
            return result.content

        except Exception:
            raise
        finally:
            await self.exit_stack.aclose()
