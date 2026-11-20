"""D-013: the launch-time test host map redirects only the TCP connection.

The map is never a setting: it is read from ``--test-host-map`` or
``SWARMBLY_TEST_HOST_MAP`` at process start. These tests exercise the seam with
real loopback servers, so they cover the transport/connect step rather than a
mock of the HTTP library.
"""

from __future__ import annotations

import contextlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swarmbly_app import cli, egress, test_hosts
from swarmbly_app.api import create_app
from swarmbly_app.state import AppState
from swarmbly_app.tools import ToolBroker, ToolCall, register_author_tools
from swarmbly_app.tools.mcp import MCPClient
from swarmbly_app.tools.mcp_registry import ServerConfig


@pytest.fixture(autouse=True)
def clean_map(monkeypatch):
    monkeypatch.delenv(test_hosts.ENV_VAR, raising=False)
    test_hosts.reset()
    yield
    test_hosts.reset()


def write_map(tmp_path: Path, mapping: dict[str, str]) -> Path:
    path = tmp_path / "host-map.json"
    path.write_text(json.dumps(mapping), encoding="utf-8")
    test_hosts.load(path)
    return path


def _policy(monkeypatch, tool_hosts=()):
    cfg = {"privacy": {"tool_hosts": list(tool_hosts)}}
    monkeypatch.setattr(egress, "_config_getter", lambda: cfg)
    return cfg


@contextlib.contextmanager
def serve(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", handler
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def _mcp_handler():
    class MCPHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        requests: list[dict] = []

        def log_message(self, *args):
            pass

        def _send(self, status: int, body: bytes = b"",
                  content_type: str = "application/json") -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

        def do_GET(self):
            self._send(405)

        def do_DELETE(self):
            self._send(200)

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length)
            message = json.loads(raw or b"{}")
            self.requests.append({"headers": {k.lower(): v for k, v in self.headers.items()},
                                  "path": self.path,
                                  "message": message})
            if "id" not in message:                 # notifications/initialized
                self._send(202)
                return
            method = message.get("method")
            if method == "initialize":
                result = {
                    "protocolVersion": message["params"]["protocolVersion"],
                    "capabilities": {},
                    "serverInfo": {"name": "fixture", "version": "1"},
                }
            elif method == "tools/list":
                result = {"tools": [{
                    "name": "echo", "description": "Echo the text",
                    "inputSchema": {"type": "object",
                                    "properties": {"text": {"type": "string"}},
                                    "required": ["text"]},
                }]}
            elif method == "tools/call":
                text = str(message["params"]["arguments"].get("text", ""))
                result = {"content": [{"type": "text", "text": f"echo:{text}"}],
                          "isError": False}
            else:
                result = {}
            body = json.dumps({"jsonrpc": "2.0", "id": message.get("id"),
                               "result": result}).encode("utf-8")
            self._send(200, body)

    return MCPHandler


def _orcid_handler():
    class OrcidHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        requests: list[dict] = []

        def log_message(self, *args):
            pass

        def _send(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self.requests.append({"headers": {k.lower(): v for k, v in self.headers.items()},
                                  "path": self.path})
            if "expanded-search" in self.path:
                self._send(200, {"expanded-result": [{
                    "orcid-id": "0000-0002-1825-0097",
                    "given-names": "Ada", "family-names": "Lovelace",
                    "institution-name": ["Analytical Engine"],
                }]})
                return
            self._send(200, {"group": [{"work-summary": [{
                "title": {"title": {"value": "Notes on the Analytical Engine"}},
                "publication-date": {"year": {"value": "1843"}},
                "journal-title": {"value": "Scientific Memoirs"},
                "external-ids": {"external-id": []},
            }]}]})

    return OrcidHandler


def _echo_handler():
    class EchoHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        requests: list[dict] = []

        def log_message(self, *args):
            pass

        def do_GET(self):
            self.requests.append({"headers": {k.lower(): v for k, v in self.headers.items()},
                                  "path": self.path})
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return EchoHandler


def _receipt(ledger) -> dict:
    return egress.build_receipt(ledger, lane="local", route="local", answer="ok",
                                consent={})


def test_shared_httpx_factory_redirects_only_the_connection(tmp_path):
    handler = _echo_handler()
    with serve(handler) as (base, _handler):
        write_map(tmp_path, {"api.example.test": base})
        with test_hosts.httpx_client(timeout=5.0) as client:
            response = client.get("https://api.example.test/probe?q=1")
        assert response.status_code == 200 and response.text == "ok"
    assert len(handler.requests) == 1
    assert handler.requests[0]["path"] == "/probe?q=1"
    assert handler.requests[0]["headers"]["host"] == "api.example.test"


def test_remote_mcp_declared_test_host_reaches_loopback_with_simulado(
        tmp_path, monkeypatch):
    handler = _mcp_handler()
    with serve(handler) as (base, _handler):
        write_map(tmp_path, {"api.example.test": base})
        _policy(monkeypatch, ["api.example.test"])
        broker = ToolBroker(tmp_path / "data")
        client = MCPClient(broker, data_root=tmp_path / "data")
        client.add_server(ServerConfig(
            id="fixture", kind="remote_http", url="https://api.example.test/mcp"))
        try:
            client.start("fixture")
            client.approve("fixture")
            with egress.request_ledger("r-mcp") as ledger:
                result = broker.invoke(ToolCall("mcp:fixture/echo", {"text": "hola"}))
            assert result.ok, result.error
            assert result.content == "echo:hola"
        finally:
            client.close()

    assert handler.requests, "the loopback fixture was not reached"
    first = handler.requests[0]
    assert first["path"] == "/mcp"
    assert first["headers"]["host"] == "api.example.test"
    receipt = _receipt(ledger)
    sent = [e for e in receipt["envios"] if e["destino"] == "api.example.test"]
    assert sent, receipt
    assert sent[-1]["clase"] == egress.THIRD_PARTY
    assert sent[-1]["simulado"] is True
    assert sent[-1]["bytes"] > 0
    tools = [t for t in receipt["tools"] if t["destino"] == "api.example.test"]
    assert tools and tools[-1]["simulado"] is True and tools[-1]["bytes"] > 0


def test_remote_mcp_without_tool_hosts_is_refused_before_any_request(
        tmp_path, monkeypatch):
    handler = _mcp_handler()
    with serve(handler) as (base, _handler):
        write_map(tmp_path, {"api.example.test": base})
        _policy(monkeypatch, [])
        broker = ToolBroker(tmp_path / "data")
        client = MCPClient(broker, data_root=tmp_path / "data")
        client.add_server(ServerConfig(
            id="fixture", kind="remote_http", url="https://api.example.test/mcp"))
        try:
            with pytest.raises(egress.EgressDenied, match="not an authorised tool host"):
                client.start("fixture")
        finally:
            client.close()
    assert handler.requests == []


def test_author_tool_keeps_declared_host_name_and_simulado(tmp_path, monkeypatch):
    handler = _orcid_handler()
    with serve(handler) as (base, _handler):
        write_map(tmp_path, {"pub.orcid.org": base})
        broker = ToolBroker(tmp_path / "data")
        register_author_tools(broker, {"tools": {"author": {"enabled": True}}},
                              services=["orcid"], approve=True)
        args = {"name": "Ada Lovelace", "max_results": 2}
        token = broker.issue_token(ToolCall("author/orcid", args, "r-author"))
        with egress.request_ledger("r-author") as ledger:
            result = broker.invoke(ToolCall("author/orcid", args, "r-author",
                                            token=token))
        assert result.ok, result.error
        assert result.data["works"][0]["title"] == "Notes on the Analytical Engine"

    assert handler.requests
    assert all(r["headers"]["host"] == "pub.orcid.org" for r in handler.requests)
    receipt = _receipt(ledger)
    sent = [e for e in receipt["envios"] if e["destino"] == "pub.orcid.org"]
    assert sent, receipt
    assert sent[0]["clase"] == egress.THIRD_PARTY
    assert sent[0]["personal_name"] is True
    assert sent[0]["simulado"] is True
    assert sent[0]["bytes"] > 0


def test_mapped_host_is_still_refused_without_tool_hosts(tmp_path, monkeypatch):
    write_map(tmp_path, {"api.example.test": "http://127.0.0.1:9003"})
    _policy(monkeypatch, [])
    with egress.request_ledger("blocked") as ledger:
        with pytest.raises(egress.EgressDenied, match="not an authorised tool host"):
            egress.check_call("https://api.example.test/tool", 11, "blocked call",
                              kind=egress.TOOL_REMOTE)
    receipt = _receipt(ledger)
    blocked = [e for e in receipt["bloqueados"] if e["destino"] == "api.example.test"]
    assert blocked, receipt
    assert blocked[0]["clase"] == egress.THIRD_PARTY
    assert blocked[0]["bytes"] == 0
    assert "simulado" not in blocked[0]


def test_without_map_nothing_is_marked_simulated(tmp_path, monkeypatch):
    _policy(monkeypatch, ["api.example.test"])
    assert test_hosts.active() is False
    with egress.request_ledger("plain") as ledger:
        egress.check_call("https://api.example.test/tool", 7, "plain call",
                          kind=egress.TOOL_REMOTE)
    assert "simulado" not in ledger.events[0]
    receipt = _receipt(ledger)
    assert "simulado" not in receipt["envios"][0]


def test_environment_map_is_read_at_startup(tmp_path, monkeypatch, capsys):
    path = tmp_path / "env-map.json"
    path.write_text(json.dumps({"api.example.test": "http://127.0.0.1:9002"}),
                    encoding="utf-8")
    monkeypatch.setenv(test_hosts.ENV_VAR, str(path))
    code = cli.main(["init", "--data-dir", str(tmp_path / "data")])
    assert code == 0
    out = capsys.readouterr().out
    assert "api.example.test -> http://127.0.0.1:9002" in out
    assert test_hosts.active() is True


def test_non_loopback_target_refuses_startup(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"api.example.test": "http://192.0.2.10:9000"}),
                    encoding="utf-8")
    code = cli.main(["init", "--data-dir", str(tmp_path / "data"),
                     "--test-host-map", str(path)])
    assert code == 2
    assert "must be loopback" in capsys.readouterr().err
    assert test_hosts.active() is False


def test_startup_log_prints_the_map(tmp_path, capsys):
    path = tmp_path / "map.json"
    path.write_text(json.dumps({"api.example.test": "http://127.0.0.1:9000"}),
                    encoding="utf-8")
    code = cli.main(["init", "--data-dir", str(tmp_path / "data"),
                     "--test-host-map", str(path)])
    assert code == 0
    out = capsys.readouterr().out
    assert "Test host map (D-013" in out
    assert "api.example.test -> http://127.0.0.1:9000" in out


def test_map_cannot_be_set_from_the_config_file_or_the_api(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    (data / "config.json").write_text(json.dumps({
        "test_host_map": {"api.example.test": "http://127.0.0.1:9000"},
        "test_hosts": {"pub.orcid.org": "http://127.0.0.1:9001"},
    }), encoding="utf-8")
    state = AppState(str(data))
    try:
        assert test_hosts.active() is False
        assert test_hosts.target_for("api.example.test") is None
        app = create_app(state)
        client = TestClient(app, base_url="http://127.0.0.1:8765")
        headers = {"x-swarmbly-token": app.state.guard.token}
        for body in (
            {"test_host_map": {"api.example.test": "http://127.0.0.1:9000"}},
            {"test_hosts": {"pub.orcid.org": "http://127.0.0.1:9001"}},
            {"privacy": {"test_host_map": {"api.example.test": "http://127.0.0.1:9000"}}},
        ):
            response = client.put("/api/config", json=body, headers=headers)
            assert response.status_code == 400, response.text
        # The harness note said "/api/settings"; the app has no such surface.
        assert client.put("/api/settings",
                          json={"test_host_map": {"api.example.test": "http://127.0.0.1:9000"}},
                          headers=headers).status_code in (404, 405)
        assert test_hosts.active() is False
        health = client.get("/api/health").json()
        assert "test_mode" not in health
    finally:
        state.stop()


def test_health_and_banner_report_an_active_map(tmp_path):
    write_map(tmp_path, {"api.example.test": "http://127.0.0.1:9000"})
    state = AppState(str(tmp_path / "data"))
    try:
        assert state.health()["test_mode"]["active"] is True
        assert state.health()["test_mode"]["hosts"] == {
            "api.example.test": "http://127.0.0.1:9000"}
        app = create_app(state)
        client = TestClient(app, base_url="http://127.0.0.1:8765")
        page = client.get("/").text
        assert 'id="test-mode-banner"' in page
        assert "Test mode: some services are simulated" in page
    finally:
        state.stop()
