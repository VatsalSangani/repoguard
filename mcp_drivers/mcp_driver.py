import asyncio
import os
from contextlib import AsyncExitStack

# Official MCP SDK imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class RuffMCPDriver:
    def __init__(self):
        # We use 'uvx' to run 'mcp-server-analyzer' without global install
        self.server_params = StdioServerParameters(
            command="uvx",
            args=["mcp-server-analyzer"], 
            env=os.environ.copy()
        )
        self.session = None
        self.exit_stack = AsyncExitStack()

    async def run_scan(self, code_content: str):
        """
        Connects to server, sends CODE CONTENT (string), returns results.
        """
        try:
            # 1. Start Server Process
            transport = await self.exit_stack.enter_async_context(
                stdio_client(self.server_params)
            )
            # 2. Start Session (Handshake)
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(transport[0], transport[1])
            )
            await self.session.initialize()

            # 3. Call Tool 
            # Note: This specific server expects 'code', not 'path'
            result = await self.session.call_tool(
                "ruff-check", 
                arguments={"code": code_content}
            )
            return result.content
            
        except Exception as e:
            raise e
        finally:
            # IMPORTANT: Cleanly close connection to prevent asyncio RuntimeErrors
            await self.close()

    async def close(self):
        await self.exit_stack.aclose()