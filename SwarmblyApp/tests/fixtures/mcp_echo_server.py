"""A tiny real MCP stdio server used by the client tests.

Two tools only: ``add`` and ``diagnostics``. The process records its own PID
when ``MCP_PID_FILE`` is set, which lets a test prove cleanup; ``diagnostics``
returns an environment value so a test can prove the canary is not inherited.
"""

from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer

server = MCPServer("swarmbly-test")


@server.tool()
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


@server.tool()
def diagnostics(name: str) -> str:
    """Return one environment variable, or an empty string when unset."""
    return os.environ.get(name, "")


if __name__ == "__main__":
    pid_file = os.environ.get("MCP_PID_FILE")
    if pid_file:
        with open(pid_file, "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
    server.run("stdio")
