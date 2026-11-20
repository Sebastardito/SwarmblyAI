"""A real MCP stdio server for result mapping: text, image, resource, error, size."""

from __future__ import annotations

import asyncio

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp_types import (CallToolResult, EmbeddedResource, ImageContent,
                       ListToolsResult, TextContent, TextResourceContents, Tool)


async def list_tools(_ctx, _params):
    names = ("mixed", "fail", "big", "slow")
    return ListToolsResult(tools=[
        Tool(name=name, description=f"Result fixture {name}.",
             inputSchema={"type": "object", "properties": {}})
        for name in names
    ])


async def call_tool(_ctx, params):
    if params.name == "mixed":
        return CallToolResult(
            content=[
                TextContent(type="text", text="hello"),
                ImageContent(type="image", data="aGVsbG8=", mimeType="image/png"),
                EmbeddedResource(
                    type="resource",
                    resource=TextResourceContents(uri="file:///tmp/x.txt", text="hi"),
                ),
            ],
            structuredContent={"answer": 42},
        )
    if params.name == "fail":
        return CallToolResult(
            content=[TextContent(type="text", text="boom")], isError=True)
    if params.name == "big":
        return CallToolResult(content=[TextContent(type="text", text="x" * 9000)])
    if params.name == "slow":
        await asyncio.sleep(1.0)
        return CallToolResult(content=[TextContent(type="text", text="late")])
    return CallToolResult(content=[TextContent(type="text", text="?")])


server = Server("swarmbly-results", on_list_tools=list_tools, on_call_tool=call_tool)


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
