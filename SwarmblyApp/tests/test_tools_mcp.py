"""3.4 MCP client core: real SDK servers, approvals, suspension and policy."""

from __future__ import annotations

import builtins
import contextlib
import json
import os
import socket
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path

import psutil
import pytest
import uvicorn

pytest.importorskip("mcp", reason="needs the [tools] extra (mcp)")
from mcp.server.mcpserver import MCPServer  # noqa: E402

from swarmbly_app import egress
from swarmbly_app.tools import (MCPApprovalError, MCPClient, MCPNotRunning,
                                MCPUnavailable, ServerConfig, ServerRegistry,
                                ToolBroker, ToolCall, ToolDenied)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ECHO = FIXTURES / "mcp_echo_server.py"
RUGPULL = FIXTURES / "mcp_rugpull_server.py"
PAGED = FIXTURES / "mcp_paged_server.py"
NOTIFY = FIXTURES / "mcp_notify_server.py"
BADSCHEMA = FIXTURES / "mcp_badschema_server.py"
RESULTS = FIXTURES / "mcp_results_server.py"


def _stdio(tmp_path: Path, script: Path, server_id: str = "fixture",
           *, env: tuple[str, ...] = ()) -> ServerConfig:
    return ServerConfig(
        id=server_id, kind="local_stdio",
        command=sys.executable, args=[str(script)], cwd=str(tmp_path),
        env_allowlist=env,
    )


def _remote(url: str, server_id: str = "remote") -> ServerConfig:
    return ServerConfig(id=server_id, kind="remote_http", url=url)


@pytest.fixture()
def mcp_factory(tmp_path: Path):
    """Broker + client with every started process closed at the end."""
    clients: list[MCPClient] = []

    def make(*, max_result_chars: int = 8000, call_timeout: float = 30.0,
             init_timeout: float = 15.0):
        broker = ToolBroker(tmp_path / "data", max_result_chars=max_result_chars)
        client = MCPClient(broker, data_root=tmp_path / "data",
                           init_timeout=init_timeout, call_timeout=call_timeout)
        clients.append(client)
        return broker, client

    yield make
    for client in clients:
        client.close()


def _wait_for(predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return predicate()


@contextlib.contextmanager
def _remote_server():
    """A real Streamable HTTP MCP server on loopback, stopped after the test."""
    server = MCPServer("swarmbly-remote-test")

    @server.tool()
    def echo(text: str) -> str:
        """Echo the text."""
        return text

    @server.tool()
    def add(a: int, b: int) -> int:
        """Add two integers."""
        return a + b

    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    app = server.streamable_http_app(host="127.0.0.1")
    config = uvicorn.Config(app, host="127.0.0.1", port=port,
                            log_level="error", access_log=False, lifespan="on")
    uv = uvicorn.Server(config)
    thread = threading.Thread(target=uv.run, name="mcp-test-http", daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), 0.2):
                    break
            except OSError:
                time.sleep(0.05)
        else:
            raise AssertionError("the in-process MCP HTTP server did not start")
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        uv.should_exit = True
        thread.join(timeout=10)


def _policy(monkeypatch, *, tool_hosts=(), passages: bool = False):
    cfg = {"privacy": {"tool_hosts": list(tool_hosts),
                       "third_party_passages": passages}}
    monkeypatch.setattr(egress, "_config_getter", lambda: cfg)
    return cfg


def _force_third_party(monkeypatch):
    monkeypatch.setattr(egress, "classify_url",
                        lambda url: (egress.THIRD_PARTY, "mcp.example.test"))


# -- registry and configuration --------------------------------------------

def test_registry_is_per_project_and_stores_names_not_values(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("MCP_CANARY", "VALUE-MUST-NOT-BE-STORED")
    registry = ServerRegistry(tmp_path / "data",
                              project_path=lambda pid: project if pid == "p1" else None)
    broker = ToolBroker(tmp_path / "data")
    client = MCPClient(broker, registry)
    config = _stdio(tmp_path, ECHO, "echo", env=("MCP_CANARY",))
    stored = client.add_server(config, "p1")

    path = project / "settings" / "mcp_servers.json"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "VALUE-MUST-NOT-BE-STORED" not in text
    data = json.loads(text)
    assert data["schema"] == "swarmbly.mcp_servers/1"
    assert data["servers"][0]["env_allowlist"] == ["MCP_CANARY"]
    assert data["servers"][0]["status"] == "unapproved"
    assert stored.command_hash == stored.computed_command_hash()
    assert client.server("echo", "p1").status == "unapproved"
    assert not (tmp_path / "data" / "settings" / "mcp_servers.json").exists()
    shown = client.describe("echo", "p1")
    assert shown["env_values_visible"] is False
    assert shown["env_allowlist"] == ["MCP_CANARY"]
    assert "not sandboxed" in shown["rights_note"]
    assert "untrusted" in shown["untrusted_note"]


def test_a_command_change_resets_the_approval(tmp_path):
    registry = ServerRegistry(tmp_path / "data")
    config = _stdio(tmp_path, ECHO, "echo")
    registry.put(config)
    approved = replace(config, status="approved",
                       approved_manifest_hash="a" * 64, approved_tools=("add",))
    registry.put(approved)
    assert registry.get("echo").status == "approved"

    changed = replace(approved, command=str(Path(sys.executable)))
    changed.command = sys.executable + "-different"
    stored = registry.put(changed)
    assert stored.status == "unapproved"
    assert stored.approved_manifest_hash == ""
    assert stored.approved_tools == ()
    assert stored.command_hash != approved.command_hash


def test_bad_configuration_is_refused(tmp_path):
    with pytest.raises(Exception, match="lowercase"):
        ServerConfig("Not Valid", "local_stdio", command=sys.executable)
    with pytest.raises(Exception, match="needs a command"):
        ServerConfig("ok", "local_stdio")
    with pytest.raises(Exception, match="http"):
        ServerConfig("ok", "remote_http", url="file:///tmp/x")
    with pytest.raises(Exception, match="credentials"):
        ServerConfig("ok", "remote_http", url="https://user:pass@example.com/mcp")
    with pytest.raises(Exception, match="environment variable"):
        ServerConfig("ok", "local_stdio", command=sys.executable,
                     env_allowlist=("BAD-NAME",))


# -- local lifecycle, env and cleanup --------------------------------------

def test_start_is_explicit_and_env_is_not_inherited(tmp_path, monkeypatch, mcp_factory):
    pid_file = tmp_path / "server.pid"
    monkeypatch.setenv("MCP_PID_FILE", str(pid_file))
    monkeypatch.setenv("MCP_CANARY", "DO-NOT-INHERIT")
    broker, client = mcp_factory()
    config = _stdio(tmp_path, ECHO, "echo", env=("MCP_PID_FILE",))
    client.add_server(config)

    assert not pid_file.exists()
    assert client.is_running("echo") is False
    with pytest.raises(MCPNotRunning):
        client.propose("echo")

    started = client.start("echo")
    assert started.status == "unapproved"
    assert _wait_for(pid_file.exists)
    pid = int(pid_file.read_text())
    assert psutil.pid_exists(pid)

    manifest = client.propose("echo")
    assert [tool.name for tool in manifest.tools] == ["add", "diagnostics"]
    client.approve("echo", tools=["diagnostics"])
    canary = broker.invoke(ToolCall("mcp:echo/diagnostics",
                                    {"name": "MCP_CANARY"}, "r"))
    assert canary.ok and canary.content == ""

    assert client.stop("echo") is True
    assert client.is_running("echo") is False
    assert _wait_for(lambda: not psutil.pid_exists(pid))


def test_env_values_are_read_at_start_only_when_allowlisted(tmp_path, monkeypatch, mcp_factory):
    pid_file = tmp_path / "server.pid"
    monkeypatch.setenv("MCP_PID_FILE", str(pid_file))
    monkeypatch.setenv("MCP_CANARY", "approved-value")
    broker, client = mcp_factory()
    client.add_server(_stdio(tmp_path, ECHO, "echo",
                             env=("MCP_CANARY", "MCP_PID_FILE")))
    assert not pid_file.exists()
    client.start("echo")
    client.approve("echo", tools=["diagnostics"])
    result = broker.invoke(ToolCall("mcp:echo/diagnostics",
                                    {"name": "MCP_CANARY"}, "r"))
    assert result.ok and result.content == "approved-value"


# -- manifest, approvals, schema and calls ---------------------------------

def test_approve_registers_only_the_selected_subset(tmp_path, mcp_factory):
    broker, client = mcp_factory()
    client.add_server(_stdio(tmp_path, ECHO, "echo"))
    client.start("echo")
    manifest = client.propose("echo")
    assert manifest.hash == client.propose("echo").hash
    config = client.approve("echo", tools=["add"])

    assert config.status == "approved"
    assert config.approved_tools == ("add",)
    assert config.approved_manifest_hash == manifest.hash
    spec = broker.spec("mcp:echo/add")
    assert spec is not None
    assert spec.provider == "mcp_local" and spec.destination == "local"
    assert "title" not in json.dumps(spec.input_schema)
    assert broker.spec("mcp:echo/diagnostics") is None
    approved_ids = {record["spec_id"] for record in broker.approvals.records()}
    assert "mcp:echo/add" in approved_ids
    assert "mcp:echo/diagnostics" not in approved_ids

    result = broker.invoke(ToolCall("mcp:echo/add", {"a": 2, "b": 3}, "r"))
    assert result.ok and result.content == "5"
    with pytest.raises(ToolDenied, match="unknown tool"):
        broker.invoke(ToolCall("mcp:echo/diagnostics", {"name": "X"}, "r"))


def test_argument_schema_violation_is_refused_before_the_server(tmp_path, mcp_factory):
    broker, client = mcp_factory()
    client.add_server(_stdio(tmp_path, ECHO, "echo"))
    client.start("echo")
    client.approve("echo", tools=["add"])
    with pytest.raises(ToolDenied, match="invalid arguments"):
        broker.invoke(ToolCall("mcp:echo/add", {"a": "not-an-int", "b": 2}, "r"))
    with pytest.raises(ToolDenied, match="invalid arguments"):
        broker.invoke(ToolCall("mcp:echo/add", {"a": 1}, "r"))


def test_unsupported_schema_keyword_cannot_be_approved(tmp_path, mcp_factory):
    broker, client = mcp_factory()
    client.add_server(_stdio(tmp_path, BADSCHEMA, "bad"))
    client.start("bad")
    assert [tool.name for tool in client.propose("bad").tools] == ["bad"]
    with pytest.raises(MCPApprovalError, match="pattern"):
        client.approve("bad", tools=["bad"])
    assert broker.spec("mcp:bad/bad") is None
    assert client.server("bad").status == "unapproved"


def test_reconnect_with_changed_manifest_suspends_and_unregisters(tmp_path, monkeypatch, mcp_factory):
    desc = tmp_path / "description.txt"
    desc.write_text("Version one.", encoding="utf-8")
    monkeypatch.setenv("MCP_DESC_FILE", str(desc))
    broker, client = mcp_factory()
    client.add_server(_stdio(tmp_path, RUGPULL, "rug",
                             env=("MCP_DESC_FILE",)))
    client.start("rug")
    assert client.propose("rug").tools[0].description == "Version one."
    client.approve("rug", tools=["ping"])
    assert broker.invoke(ToolCall("mcp:rug/ping", {}, "r")).content == "pong:ping"
    client.stop("rug")

    desc.write_text("Version two, with a wider promise.", encoding="utf-8")
    config = client.start("rug")
    assert config.status == "suspended"
    assert "manifest changed" in config.suspension_reason
    assert broker.spec("mcp:rug/ping") is None
    assert client.propose("rug").tools[0].description.startswith("Version two")

    client.approve("rug", tools=["ping"])
    assert client.server("rug").status == "approved"
    assert broker.invoke(ToolCall("mcp:rug/ping", {}, "r")).content == "pong:ping"


def test_restart_with_same_manifest_reregisters_without_reapproval(tmp_path, mcp_factory):
    broker, client = mcp_factory()
    client.add_server(_stdio(tmp_path, ECHO, "echo"))
    client.start("echo")
    first = client.approve("echo", tools=["add"])
    client.stop("echo")
    assert broker.spec("mcp:echo/add") is None
    second = client.start("echo")
    assert second.status == "approved"
    assert second.approved_manifest_hash == first.approved_manifest_hash
    assert broker.spec("mcp:echo/add") is not None
    assert broker.invoke(ToolCall("mcp:echo/add", {"a": 7, "b": 1}, "r")).content == "8"


def test_tools_list_changed_notification_suspends(tmp_path, mcp_factory):
    broker, client = mcp_factory()
    client.add_server(_stdio(tmp_path, NOTIFY, "notify"))
    client.start("notify")
    client.approve("notify", tools=["ping", "bump"])
    assert broker.invoke(ToolCall("mcp:notify/ping", {}, "r")).content == "pong"
    assert broker.invoke(ToolCall("mcp:notify/bump", {}, "r")).content == "bumped"

    assert _wait_for(lambda: client.server("notify").status == "suspended")
    assert "tools/list_changed" in client.server("notify").suspension_reason
    assert broker.spec("mcp:notify/ping") is None
    assert broker.spec("mcp:notify/bump") is None
    with pytest.raises(ToolDenied, match="unknown tool"):
        broker.invoke(ToolCall("mcp:notify/ping", {}, "r"))

    client.approve("notify", tools=["ping"])
    assert client.server("notify").status == "approved"
    assert broker.invoke(ToolCall("mcp:notify/ping", {}, "r")).content == "pong"


def test_tools_list_pagination_is_followed(tmp_path, mcp_factory):
    broker, client = mcp_factory()
    client.add_server(_stdio(tmp_path, PAGED, "paged"))
    client.start("paged")
    manifest = client.propose("paged")
    assert [tool.name for tool in manifest.tools] == ["alpha", "beta", "gamma"]
    client.approve("paged", tools=["beta"])
    assert broker.invoke(ToolCall("mcp:paged/beta", {}, "r")).content == "called:beta"


def test_results_are_mapped_as_data_and_omissions(tmp_path, mcp_factory):
    broker, client = mcp_factory(max_result_chars=20)
    client.add_server(_stdio(tmp_path, RESULTS, "results"))
    client.start("results")
    client.approve("results", tools=["mixed", "fail", "big", "slow"])

    mixed = broker.invoke(ToolCall("mcp:results/mixed", {}, "r"))
    assert mixed.ok is True
    assert "hello" in mixed.content
    assert "omitted: image" in mixed.content
    assert "omitted: resource" in mixed.content
    assert mixed.data == {"answer": 42}

    failed = broker.invoke(ToolCall("mcp:results/fail", {}, "r"))
    assert failed.ok is False and "boom" in failed.error

    big = broker.invoke(ToolCall("mcp:results/big", {}, "r"))
    assert big.truncated is True
    assert len(big.content) <= 20

    client.call_timeout = 0.2
    slow = broker.invoke(ToolCall("mcp:results/slow", {}, "r"))
    assert slow.ok is False
    assert "MCPTimeout" in slow.error


# -- remote HTTP, policy and passages guard --------------------------------

def test_remote_http_needs_tool_hosts_and_then_works(monkeypatch, tmp_path, mcp_factory):
    _force_third_party(monkeypatch)
    cfg = _policy(monkeypatch)
    broker, client = mcp_factory()
    with _remote_server() as url:
        client.add_server(_remote(url))
        with pytest.raises(egress.EgressDenied, match="not an authorised tool host"):
            client.start("remote")
        assert client.is_running("remote") is False

        cfg["privacy"]["tool_hosts"] = ["mcp.example.test"]
        assert client.start("remote").status == "unapproved"
        manifest = client.propose("remote")
        assert [tool.name for tool in manifest.tools] == ["add", "echo"]
        client.approve("remote", tools=["echo"])
        result = broker.invoke(ToolCall("mcp:remote/echo", {"text": "hola"}, "r"))
        assert result.ok and result.content == "hola"


def test_remote_passages_guard_size_and_shingles(monkeypatch, tmp_path, mcp_factory):
    _force_third_party(monkeypatch)
    cfg = _policy(monkeypatch, tool_hosts=["mcp.example.test"])
    broker, client = mcp_factory()
    with _remote_server() as url:
        client.add_server(_remote(url))
        client.start("remote")
        client.approve("remote", tools=["echo"])

        assert broker.invoke(ToolCall("mcp:remote/echo", {"text": "short"}, "r")).ok

        long_text = "z" * 1300
        with pytest.raises(ToolDenied, match="third_party_passages"):
            broker.invoke(ToolCall("mcp:remote/echo", {"text": long_text}, "r"))

        passage = "the quick brown fox jumps over the lazy dog"
        with pytest.raises(ToolDenied, match="third_party_passages"):
            with client.passages([passage]):
                broker.invoke(ToolCall(
                    "mcp:remote/echo",
                    {"text": "prefix " + passage + " suffix"}, "r"))

        cfg["privacy"]["third_party_passages"] = True
        assert broker.invoke(ToolCall("mcp:remote/echo",
                                      {"text": long_text}, "r")).ok
        with client.passages([passage]):
            allowed = broker.invoke(ToolCall(
                "mcp:remote/echo",
                {"text": "prefix " + passage + " suffix"}, "r"))
        assert allowed.ok and "quick brown fox" in allowed.content


def test_missing_sdk_gives_a_clear_optional_extra_error(monkeypatch):
    import swarmbly_app.tools.mcp as mcp_module

    monkeypatch.setattr(mcp_module, "_sdk_cache", None)
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "mcp" or name.startswith("mcp.") or name == "mcp_types":
            raise ImportError("simulated missing MCP SDK")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(MCPUnavailable, match="tools"):
        mcp_module._sdk()
