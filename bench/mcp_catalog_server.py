#!/usr/bin/env python3
"""Serve one MCP tool catalogue from ``01_MATERIALES/mcp/<server>.json``.

The blind harness 1.3 turns every catalogue of a sealed v4 bank into a real
MCP server with this script:

* a ``local`` catalogue is served over stdio (the App spawns it);
* a ``remoto`` catalogue is served over Streamable HTTP on ``127.0.0.1``; the
  App is launched with ``--test-host-map`` so it still sees the catalogue's
  declared host, and its policy/receipt use that host (D-013);
* the ``<server>.cambio.json`` catalogue can be swapped in at a stated turn.
  The server answers the next ``tools/list`` with the new manifest and sends
  ``notifications/tools/list_changed``; the App suspends the server when the
  approved manifest hash no longer matches.

Only text is served. A tool answer is chosen from the catalogue's fixed
``respuestas``: the first entry whose ``si`` object equals the call's
arguments, else ``por_defecto``. Nothing here runs a command or reaches the
network. Standard library only.

    mcp_catalog_server.py --catalog planillas.json --stdio
    mcp_catalog_server.py --catalog meteo-austral.json --http 0 \
        --change-catalog meteo-austral.cambio.json --log calls.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import sys
import threading
import uuid
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

PROTOCOL_FALLBACK = "2025-06-18"


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------
class Catalogue:
    """One immutable catalogue file, plus the optional change catalogue."""

    def __init__(self, path: Path, change_path: Path | None = None) -> None:
        self.path = path
        self.change_path = change_path
        self._lock = threading.RLock()
        self._current = self._read(path)
        self._initial = self._current
        self.changed = False

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path}: the catalogue must be a JSON object")
        tools = data.get("herramientas")
        if not isinstance(tools, list) or not tools:
            raise ValueError(f"{path}: 'herramientas' must be a non-empty list")
        names: set[str] = set()
        for tool in tools:
            if not isinstance(tool, dict):
                raise ValueError(f"{path}: every tool must be an object")
            name = str(tool.get("nombre") or "")
            if not name or name in names:
                raise ValueError(f"{path}: tool names must be non-empty and unique")
            names.add(name)
            schema = tool.get("esquema")
            if not isinstance(schema, dict):
                raise ValueError(f"{path}: tool {name!r} needs an 'esquema' object")
            answers = tool.get("respuestas")
            if not isinstance(answers, list) or not answers:
                raise ValueError(f"{path}: tool {name!r} needs non-empty 'respuestas'")
        return data

    @property
    def server(self) -> str:
        with self._lock:
            return str(self._current.get("servidor") or self.path.stem)

    def tools(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._current.get("herramientas") or [])

    def manifest(self) -> list[dict[str, Any]]:
        return [{"name": str(tool["nombre"]),
                 "description": str(tool.get("descripcion") or ""),
                 "inputSchema": tool["esquema"]}
                for tool in self.tools()]

    def call(self, name: str, arguments: dict[str, Any]) -> str:
        with self._lock:
            tools = list(self._current.get("herramientas") or [])
        for tool in tools:
            if str(tool.get("nombre")) != name:
                continue
            for answer in tool.get("respuestas") or []:
                condition = answer.get("si")
                if isinstance(condition, dict) and condition and all(
                        arguments.get(key) == value for key, value in condition.items()):
                    return str(answer.get("texto") or "")
            for answer in tool.get("respuestas") or []:
                if "por_defecto" in answer:
                    return str(answer.get("por_defecto") or "")
            return ""
        raise KeyError(name)

    def change(self) -> bool:
        with self._lock:
            if self.changed or self.change_path is None:
                return False
            self._current = self._read(self.change_path)
            self.changed = True
            return True

    def reset(self) -> None:
        with self._lock:
            self._current = self._initial
            self.changed = False


class CallLog:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self._lock = threading.Lock()

    def add(self, **entry: Any) -> None:
        if self.path is None:
            return
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _arguments(raw: Any) -> dict[str, Any]:
    return dict(raw) if isinstance(raw, dict) else {}


def _rpc_result(catalogue: Catalogue, method: str, params: dict[str, Any]) -> Any:
    if method == "initialize":
        requested = str((params or {}).get("protocolVersion") or PROTOCOL_FALLBACK)
        return {"protocolVersion": requested,
                "capabilities": {"tools": {"listChanged": True}},
                "serverInfo": {"name": catalogue.server, "version": "1.0.0"}}
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": catalogue.manifest()}
    if method == "tools/call":
        name = str((params or {}).get("name") or "")
        arguments = _arguments((params or {}).get("arguments"))
        try:
            text = catalogue.call(name, arguments)
        except KeyError:
            raise ValueError(f"unknown tool {name!r}") from None
        return {"content": [{"type": "text", "text": text}], "isError": False}
    raise ValueError(f"method not found: {method}")


def _error(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id,
            "error": {"code": code, "message": message}}


# ---------------------------------------------------------------------------
# stdio transport
# ---------------------------------------------------------------------------
def serve_stdio(catalogue: Catalogue, log: CallLog) -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except ValueError:
            sys.stdout.write(json.dumps(_error(None, -32700, "parse error")) + "\n")
            sys.stdout.flush()
            continue
        if not isinstance(message, dict):
            continue
        method = str(message.get("method") or "")
        message_id = message.get("id")
        if "id" not in message:              # a notification
            continue
        try:
            result = _rpc_result(catalogue, method, message.get("params") or {})
            response = {"jsonrpc": "2.0", "id": message_id, "result": result}
            if method == "tools/call":
                params = message.get("params") or {}
                log.add(transporte="stdio", servidor=catalogue.server,
                        herramienta=str(params.get("name") or ""),
                        argumentos=_arguments(params.get("arguments")))
        except ValueError as exc:
            response = _error(message_id, -32602, str(exc))
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


# ---------------------------------------------------------------------------
# Streamable HTTP transport
# ---------------------------------------------------------------------------
class _Hub:
    """One SSE subscriber per open GET; a change is broadcast to all of them."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queues: list[queue.Queue] = []

    def subscribe(self) -> queue.Queue:
        item: queue.Queue = queue.Queue()
        with self._lock:
            self._queues.append(item)
        return item

    def unsubscribe(self, item: queue.Queue) -> None:
        with self._lock:
            if item in self._queues:
                self._queues.remove(item)

    def broadcast(self, message: dict[str, Any]) -> None:
        with self._lock:
            queues = list(self._queues)
        for item in queues:
            item.put(message)


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    catalogue: Catalogue
    log: CallLog
    hub: _Hub
    control_token: str

    def log_message(self, *args: Any) -> None:      # silent
        return

    def _json(self, status: int, body: Any, session: str = "") -> None:
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        if session:
            self.send_header("Mcp-Session-Id", session)
        self.end_headers()
        self.wfile.write(raw)

    def _empty(self, status: int) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _sse_open(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        self.wfile.write(b": connected\n\n")
        self.wfile.flush()
        item = self.hub.subscribe()
        try:
            while True:
                try:
                    message = item.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    continue
                data = json.dumps(message, ensure_ascii=False)
                self.wfile.write(f"event: message\ndata: {data}\n\n".encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.hub.unsubscribe(item)

    def _control(self, path: str, body: dict[str, Any]) -> bool:
        if not path.startswith("/__control"):
            return False
        if self.control_token and self.headers.get("X-Control-Token") != self.control_token:
            self._json(403, {"error": "control token required"})
            return True
        action = path.rsplit("/", 1)[-1]
        if action == "change":
            changed = self.catalogue.change()
            if changed:
                self.hub.broadcast({"jsonrpc": "2.0",
                                    "method": "notifications/tools/list_changed"})
            self._json(200, {"changed": changed, "tools": [
                tool["name"] for tool in self.catalogue.manifest()]})
            return True
        if action == "reset":
            self.catalogue.reset()
            self._json(200, {"reset": True, "tools": [
                tool["name"] for tool in self.catalogue.manifest()]})
            return True
        if action == "status":
            self._json(200, {"server": self.catalogue.server,
                             "changed": self.catalogue.changed,
                             "tools": [tool["name"] for tool in self.catalogue.manifest()]})
            return True
        if action == "health":
            self._json(200, {"ok": True})
            return True
        self._json(404, {"error": "unknown control action"})
        return True

    def do_GET(self) -> None:                     # noqa: N802
        parsed = urllib.parse.urlsplit(self.path)
        if self._control(parsed.path, {}):
            return
        accept = str(self.headers.get("Accept") or "")
        if "text/event-stream" in accept:
            self._sse_open()
            return
        self._json(200, {"server": self.catalogue.server,
                         "tools": [tool["name"] for tool in self.catalogue.manifest()]})

    def do_DELETE(self) -> None:                  # noqa: N802
        self._empty(200)

    def do_POST(self) -> None:                    # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        parsed = urllib.parse.urlsplit(self.path)
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            self._json(400, {"error": "parse error"})
            return
        if self._control(parsed.path, body if isinstance(body, dict) else {}):
            return
        if not isinstance(body, dict):
            self._json(400, {"error": "JSON-RPC message must be an object"})
            return
        method = str(body.get("method") or "")
        message_id = body.get("id")
        if "id" not in body:                      # notification
            self._empty(202)
            return
        try:
            result = _rpc_result(self.catalogue, method, body.get("params") or {})
        except ValueError as exc:
            self._json(200, _error(message_id, -32602, str(exc)))
            return
        if method == "tools/call":
            params = body.get("params") or {}
            self.log.add(transporte="http", servidor=self.catalogue.server,
                         herramienta=str(params.get("name") or ""),
                         argumentos=_arguments(params.get("arguments")))
        session = ""
        if method == "initialize":
            session = uuid.uuid4().hex
            self.server.session_id = session  # type: ignore[attr-defined]
        self._json(200, {"jsonrpc": "2.0", "id": message_id, "result": result},
                   session=session)


def serve_http(catalogue: Catalogue, log: CallLog, port: int,
               control_token: str = "") -> tuple[ThreadingHTTPServer, int]:
    handler = type("Handler", (_Handler,), {
        "catalogue": catalogue, "log": log, "hub": _Hub(),
        "control_token": control_token})
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Serve one MCP catalogue (v4 bank harness)")
    ap.add_argument("--catalog", required=True, help="01_MATERIALES/mcp/<server>.json")
    ap.add_argument("--change-catalog", default="", help="<server>.cambio.json for mcp-cambio")
    ap.add_argument("--stdio", action="store_true", help="stdio transport (local server)")
    ap.add_argument("--http", type=int, default=0, metavar="PORT",
                    help="Streamable HTTP transport on 127.0.0.1 (0 = any free port)")
    ap.add_argument("--log", default="", help="append one JSON line per tools/call")
    ap.add_argument("--control-token", default="")
    ap.add_argument("--print-port", action="store_true",
                    help="print the HTTP port on stdout and stay in the foreground")
    args = ap.parse_args(argv)
    path = Path(args.catalog).expanduser().resolve()
    change = Path(args.change_catalog).expanduser().resolve() if args.change_catalog else None
    catalogue = Catalogue(path, change)
    log = CallLog(Path(args.log).expanduser().resolve() if args.log else None)
    if args.stdio:
        return serve_stdio(catalogue, log)
    server, port = serve_http(catalogue, log, args.http, args.control_token)
    if args.print_port:
        print(port, flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
