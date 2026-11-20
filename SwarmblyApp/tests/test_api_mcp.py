"""3.4 Settings → Tools: MCP servers and author search over the local API."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import psutil
import pytest
from fastapi.testclient import TestClient

pytest.importorskip("mcp", reason="needs the [tools] extra (mcp)")

from swarmbly_app.api import create_app

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ECHO = FIXTURES / "mcp_echo_server.py"
RUGPULL = FIXTURES / "mcp_rugpull_server.py"


def _app(app_state):
    app = create_app(app_state)
    client = TestClient(app, base_url="http://127.0.0.1:8765")
    client.headers["X-Swarmbly-Token"] = app.state.guard.token
    return client


@pytest.fixture()
def api(app_state):
    client = _app(app_state)
    yield client
    mcp = getattr(app_state, "_mcp_client", None)
    if mcp is not None:
        mcp.close()
        try:
            delattr(app_state, "_mcp_client")
        except AttributeError:
            pass


def _local(tmp_path: Path, server_id: str = "echo", *, env=()) -> dict:
    return {
        "id": server_id, "kind": "local_stdio",
        "command": sys.executable, "args": [str(ECHO)],
        "cwd": str(tmp_path), "env_allowlist": list(env),
    }


def _wait_for(predicate, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return predicate()


def test_mcp_routes_require_the_launch_token(app_state):
    app = create_app(app_state)
    raw = TestClient(app, base_url="http://127.0.0.1:8765")
    assert raw.get("/api/mcp/servers").status_code == 401
    assert raw.post("/api/mcp/servers", json={}).status_code == 401
    good = TestClient(app, base_url="http://127.0.0.1:8765")
    good.headers["X-Swarmbly-Token"] = app.state.guard.token
    assert good.get("/api/mcp/servers").status_code == 200


def test_add_list_and_env_names_only(api, app_state, tmp_path, monkeypatch):
    secret = "ENV-VALUE-MUST-NOT-LEAK"
    pid_file = tmp_path / "server.pid"
    monkeypatch.setenv("MCP_CANARY", secret)
    monkeypatch.setenv("MCP_PID_FILE", str(pid_file))
    body = _local(tmp_path, env=("MCP_CANARY", "MCP_PID_FILE"))
    resp = api.post("/api/mcp/servers", json=body)
    assert resp.status_code == 200, resp.text
    server = resp.json()
    assert server["id"] == "echo" and server["status"] == "unapproved"
    assert server["running"] is False
    assert server["cwd"] == str(tmp_path)
    assert server["command_line"].startswith(sys.executable)
    assert server["env"] == {"MCP_CANARY": True, "MCP_PID_FILE": True}
    assert secret not in resp.text
    assert "not sandboxed" in server["rights_note"]
    assert not pid_file.exists()                    # adding never starts it

    listing = api.get("/api/mcp/servers").json()
    assert listing["project_id"] == ""
    assert [item["id"] for item in listing["servers"]] == ["echo"]
    assert secret not in json.dumps(listing)
    registry = app_state.dirs.root / "settings" / "mcp_servers.json"
    assert registry.is_file() and secret not in registry.read_text(encoding="utf-8")

    status = api.get("/api/mcp/servers/echo/status").json()
    assert status["running"] is False and status["status"] == "unapproved"


def test_env_values_are_rejected(api):
    base = {"id": "bad", "kind": "local_stdio", "command": sys.executable,
            "cwd": "/tmp"}
    for bad in (
        {**base, "env": {"MCP_CANARY": "secret"}},
        {**base, "env_values": {"MCP_CANARY": "secret"}},
        {**base, "environment": ["MCP_CANARY"]},
        {**base, "env_allowlist": [{"name": "MCP_CANARY", "value": "secret"}]},
    ):
        resp = api.post("/api/mcp/servers", json=bad)
        assert resp.status_code == 400, resp.text
        assert "secret" not in resp.text
    assert api.get("/api/mcp/servers").json()["servers"] == []


def test_add_start_propose_approve_stop_and_cleanup(api, app_state, tmp_path, monkeypatch):
    pid_file = tmp_path / "server.pid"
    monkeypatch.setenv("MCP_PID_FILE", str(pid_file))
    assert api.post("/api/mcp/servers", json=_local(tmp_path, env=("MCP_PID_FILE",))).status_code == 200
    assert api.get("/api/mcp/servers/echo/status").json()["running"] is False
    assert api.post("/api/mcp/servers/echo/propose").status_code == 409   # explicit start first
    assert not pid_file.exists()

    started = api.post("/api/mcp/servers/echo/start")
    assert started.status_code == 200, started.text
    assert started.json()["running"] is True
    assert _wait_for(pid_file.exists)
    pid = int(pid_file.read_text())
    assert psutil.pid_exists(pid)

    proposal = api.post("/api/mcp/servers/echo/propose")
    assert proposal.status_code == 200, proposal.text
    data = proposal.json()
    assert data["manifest_hash"]
    assert [tool["name"] for tool in data["tools"]] == ["add", "diagnostics"]
    assert "description" in data["tools"][0]

    approved = api.post("/api/mcp/servers/echo/approve", json={"tools": ["add"]})
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["status"] == "approved" and body["approved_tools"] == ["add"]
    assert app_state.tools.spec("mcp:echo/add") is not None
    assert app_state.tools.spec("mcp:echo/diagnostics") is None

    stopped = api.post("/api/mcp/servers/echo/stop")
    assert stopped.status_code == 200 and stopped.json()["stopped"] is True
    assert stopped.json()["running"] is False
    assert _wait_for(lambda: not psutil.pid_exists(pid))

    assert api.delete("/api/mcp/servers/echo").status_code == 200
    assert api.get("/api/mcp/servers").json()["servers"] == []
    assert api.delete("/api/mcp/servers/echo").status_code == 404


def test_suspension_is_visible_and_reapproval_clears_it(api, app_state, tmp_path, monkeypatch):
    desc = tmp_path / "description.txt"
    desc.write_text("Version one.", encoding="utf-8")
    monkeypatch.setenv("MCP_DESC_FILE", str(desc))
    body = _local(tmp_path, "rug")
    body["args"] = [str(RUGPULL)]
    body["env_allowlist"] = ["MCP_DESC_FILE"]
    assert api.post("/api/mcp/servers", json=body).status_code == 200
    assert api.post("/api/mcp/servers/rug/start").status_code == 200
    proposal = api.post("/api/mcp/servers/rug/propose").json()
    assert proposal["tools"][0]["description"] == "Version one."
    assert api.post("/api/mcp/servers/rug/approve",
                    json={"tools": ["ping"]}).status_code == 200
    assert api.post("/api/mcp/servers/rug/stop").status_code == 200

    desc.write_text("Version two, with a different promise.", encoding="utf-8")
    restarted = api.post("/api/mcp/servers/rug/start")
    assert restarted.status_code == 200, restarted.text
    suspended = restarted.json()
    assert suspended["status"] == "suspended"
    assert "manifest changed" in suspended["suspension_reason"]
    assert app_state.tools.spec("mcp:rug/ping") is None
    status = api.get("/api/mcp/servers/rug/status").json()
    assert status["status"] == "suspended" and status["running"] is True

    proposal = api.post("/api/mcp/servers/rug/propose").json()
    assert proposal["status"] == "suspended"
    assert proposal["tools"][0]["description"].startswith("Version two")
    again = api.post("/api/mcp/servers/rug/approve", json={"tools": ["ping"]})
    assert again.status_code == 200 and again.json()["status"] == "approved"
    assert api.post("/api/mcp/servers/rug/stop").status_code == 200


def test_tool_description_is_returned_as_plain_text_and_ui_does_not_inject_html(api, tmp_path, monkeypatch):
    desc = tmp_path / "description.txt"
    payload = '<script>alert("x")</script> [not](https://example.test)'
    desc.write_text(payload, encoding="utf-8")
    monkeypatch.setenv("MCP_DESC_FILE", str(desc))
    body = _local(tmp_path, "rug")
    body["args"] = [str(RUGPULL)]
    body["env_allowlist"] = ["MCP_DESC_FILE"]
    api.post("/api/mcp/servers", json=body)
    api.post("/api/mcp/servers/rug/start")
    proposal = api.post("/api/mcp/servers/rug/propose")
    assert proposal.status_code == 200
    assert proposal.json()["tools"][0]["description"] == payload
    assert "<script>alert" in proposal.text              # JSON string, not HTML
    source = (Path(__file__).resolve().parent.parent / "swarmbly_app" / "web" / "js" / "settings.js")
    js = source.read_text(encoding="utf-8")
    assert 'h("blockquote.tool-desc", tool.description)' in js
    assert "innerHTML" not in js
    api.post("/api/mcp/servers/rug/stop")


def test_remote_server_view_host_and_authorisations(api, app_state):
    body = {"id": "remote", "kind": "remote_http",
            "url": "https://mcp.example.test/mcp"}
    added = api.post("/api/mcp/servers", json=body)
    assert added.status_code == 200, added.text
    server = added.json()
    assert server["third_party"] is True and server["host"] == "mcp.example.test"
    assert server["host_authorised"] is False
    assert server["passages_authorised"] is False
    assert server["running"] is False
    blocked = api.post("/api/mcp/servers/remote/start")
    assert blocked.status_code == 403
    assert "not an authorised tool host" in blocked.json()["detail"]
    assert api.get("/api/mcp/servers/remote/status").json()["running"] is False

    assert api.put("/api/config", json={"privacy": {"tool_hosts": ["mcp.example.test"]}}).status_code == 200
    server = api.get("/api/mcp/servers/remote/status").json()
    assert server["host_authorised"] is True
    assert api.put("/api/config", json={"privacy": {"third_party_passages": True}}).status_code == 200
    server = api.get("/api/mcp/servers/remote/status").json()
    assert server["passages_authorised"] is True
    assert server["running"] is False


def test_author_switch_defaults_off_and_can_be_enabled(api):
    cfg = api.get("/api/config").json()
    assert cfg["tools"]["author"]["enabled"] is False
    resp = api.put("/api/config", json={"tools": {"author": {"enabled": True}}})
    assert resp.status_code == 200, resp.text
    assert resp.json()["tools"]["author"]["enabled"] is True
    assert api.get("/api/mcp/servers").json()["author_enabled"] is True


def test_servers_are_per_project(api, app_state, tmp_path):
    project = app_state.projects.create("MCP project", parent=tmp_path)
    personal = _local(tmp_path, "personal")
    in_project = _local(tmp_path, "inside")
    assert api.post("/api/mcp/servers", json=personal).status_code == 200
    assert api.post("/api/mcp/servers", json={**in_project, "project_id": project.id}).status_code == 200
    assert [s["id"] for s in api.get("/api/mcp/servers?project=").json()["servers"]] == ["personal"]
    project_list = api.get(f"/api/mcp/servers?project={project.id}").json()
    assert project_list["project_id"] == project.id
    assert [s["id"] for s in project_list["servers"]] == ["inside"]
    assert api.get("/api/mcp/servers?project=missing").status_code == 404


def test_env_set_from_the_keychain_is_a_boolean_only(api, tmp_path):
    from swarmbly_app.keystore import delete_secret, set_secret

    set_secret("mcp.echo.MCP_TOKEN", "KEYCHAIN-VALUE-MUST-NOT-LEAK")
    try:
        body = _local(tmp_path, env=("MCP_TOKEN",))
        added = api.post("/api/mcp/servers", json=body)
        assert added.status_code == 200, added.text
        assert added.json()["env"] == {"MCP_TOKEN": True}
        assert "KEYCHAIN-VALUE-MUST-NOT-LEAK" not in added.text
        listing = api.get("/api/mcp/servers").text
        assert "KEYCHAIN-VALUE-MUST-NOT-LEAK" not in listing
    finally:
        delete_secret("mcp.echo.MCP_TOKEN")



def test_tools_ui_strings_are_in_english_and_spanish():
    base = Path(__file__).resolve().parent.parent / "swarmbly_app" / "web" / "i18n"
    for language in ("en", "es"):
        data = json.loads((base / f"{language}.json").read_text(encoding="utf-8"))
        assert data["settings"]["tab"]["tools"]
        assert data["tools"]["author"]
        assert data["tools"]["authorBody"]
        assert data["tools"]["kind"]["local_stdio"]
        assert data["tools"]["kind"]["remote_http"]
        assert data["tools"]["status"]["suspended"]
        assert data["tools"]["hostAuth"]
        assert data["tools"]["passagesAuth"]
        assert data["tools"]["start"] and data["tools"]["stop"]
