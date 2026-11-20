"""A real MCP stdio server with a schema the broker's subset cannot approve."""

from __future__ import annotations

import asyncio

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp_types import CallToolResult, ListToolsResult, TextContent, Tool


async def list_tools(_ctx, _params):
    return ListToolsResult(tools=[Tool(
        name="bad",
        description="A tool with a pattern keyword.",
        inputSchema={
            "type": "object",
            "properties": {"x": {"type": "string", "pattern": "^a"}},
        },
    )])


async def call_tool(_ctx, _params):
    return CallToolResult(content=[TextContent(type="text", text="never")])


server = Server("swarmbly-badschema", on_list_tools=list_tools, on_call_tool=call_tool)


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
