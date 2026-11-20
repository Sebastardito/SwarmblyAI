"""A real MCP stdio server that changes its list and notifies the client."""

from __future__ import annotations

import asyncio

from mcp.server.lowlevel import Server
from mcp.server.lowlevel.server import NotificationOptions
from mcp.server.stdio import stdio_server
from mcp_types import CallToolResult, ListToolsResult, TextContent, Tool

description = "Ping version 1."


async def list_tools(_ctx, _params):
    return ListToolsResult(tools=[
        Tool(name="ping", description=description,
             inputSchema={"type": "object", "properties": {}}),
        Tool(name="bump", description="Change the list and notify.",
             inputSchema={"type": "object", "properties": {}}),
    ])


async def call_tool(ctx, params):
    global description
    if params.name == "bump":
        description = "Ping version 2."
        await ctx.session.send_tool_list_changed()
        return CallToolResult(content=[TextContent(type="text", text="bumped")])
    return CallToolResult(content=[TextContent(type="text", text="pong")])


server = Server("swarmbly-notify", on_list_tools=list_tools, on_call_tool=call_tool)


async def main() -> None:
    options = server.create_initialization_options(
        NotificationOptions(tools_changed=True))
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options)


if __name__ == "__main__":
    asyncio.run(main())
