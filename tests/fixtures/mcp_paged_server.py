"""A real MCP stdio server that paginates ``tools/list`` one tool per page."""

from __future__ import annotations

import asyncio

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp_types import CallToolResult, ListToolsResult, TextContent, Tool

NAMES = ("alpha", "beta", "gamma")


async def list_tools(_ctx, params):
    index = int(params.cursor) if params is not None and params.cursor else 0
    if index >= len(NAMES):
        return ListToolsResult(tools=[])
    name = NAMES[index]
    return ListToolsResult(
        tools=[Tool(
            name=name,
            description=f"Tool {name}.",
            inputSchema={"type": "object", "properties": {}},
        )],
        nextCursor=str(index + 1) if index + 1 < len(NAMES) else None,
    )


async def call_tool(_ctx, params):
    return CallToolResult(content=[TextContent(type="text", text=f"called:{params.name}")])


server = Server("swarmbly-paged", on_list_tools=list_tools, on_call_tool=call_tool)


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
