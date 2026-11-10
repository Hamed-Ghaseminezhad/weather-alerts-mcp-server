"""Tiny client. Usage:
uv run python examples/client.py                      # starts the server itself (stdio)
uv run python examples/client.py http://127.0.0.1:8000/mcp   # connects to a running HTTP server
"""

import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client


async def run(read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        print("Tools:", [t.name for t in tools.tools])
        result = await session.call_tool("get_alerts", {"state": "CA", "limit": 3})
        print("isError:", result.is_error)
        print(result.content[0].text)


async def main():
    if len(sys.argv) > 1:
        async with streamable_http_client(sys.argv[1]) as streams:
            await run(streams[0], streams[1])
    else:
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "weather_alerts_mcp_server"]
        )
        async with stdio_client(params) as (read, write):
            await run(read, write)


asyncio.run(main())
