"""Security regressions for the local API (findings H7, H8 of the Phase 0 audit)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from swarmbly_app.api import create_app


@pytest.fixture()
def app(app_state):
    return create_app(app_state)


def ui_client(app):
    c = TestClient(app, base_url="http://127.0.0.1:8765")
    c.headers["X-Swarmbly-Token"] = app.state.guard.token
    return c


class TestHostAndOrigin:
    def test_dns_rebinding_host_refused(self, app):
        c = TestClient(app, base_url="http://attacker.example")
        c.headers["X-Swarmbly-Token"] = app.state.guard.token
        assert c.get("/api/config").status_code == 421

    def test_cross_origin_mutation_refused(self, app, app_state):
        c = ui_client(app)
        r = c.put("/api/config", json={"privacy": {"tier": "GLOBAL"}},
                  headers={"Origin": "http://attacker.example"})
        assert r.status_code == 403
        assert app_state.config.get("privacy.tier") == "LOCAL"

    def test_missing_token_refused(self, app):
        c = TestClient(app, base_url="http://127.0.0.1:8765")
        assert c.get("/api/conversations").status_code == 401
        assert c.get("/api/health").status_code == 200  # harmless, open

    def test_same_origin_with_token_allowed(self, app):
        c = ui_client(app)
        r = c.put("/api/config", json={"language": "es"},
                  headers={"Origin": "http://127.0.0.1:8765"})
        assert r.status_code == 200

    def test_token_injected_into_page_and_headers_set(self, app):
        c = TestClient(app, base_url="http://localhost:8765")
        r = c.get("/")
        assert r.status_code == 200
        assert app.state.guard.token in r.text
        assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
        assert r.headers["x-frame-options"] == "DENY"

    def test_token_file_is_private(self, app, app_state):
        import os
        import stat
        path = app_state.dirs.root / "api_token"
        assert path.read_text() == app.state.guard.token
        if os.name == "posix":
            assert stat.S_IMODE(path.stat().st_mode) == 0o600


class TestWebSocket:
    def test_foreign_origin_websocket_refused(self, app):
        c = TestClient(app, base_url="http://127.0.0.1:8765")
        with pytest.raises(WebSocketDisconnect):
            with c.websocket_connect(f"/ws?token={app.state.guard.token}",
                                     headers={"Origin": "http://attacker.example",
                                              "Host": "127.0.0.1:8765"}) as ws:
                ws.receive_text()

    def test_websocket_without_token_refused(self, app):
        c = TestClient(app, base_url="http://127.0.0.1:8765")
        with pytest.raises(WebSocketDisconnect):
            with c.websocket_connect("/ws", headers={"Host": "127.0.0.1:8765"}) as ws:
                ws.receive_text()

    def test_websocket_with_token_receives_events(self, app, app_state):
        c = TestClient(app, base_url="http://127.0.0.1:8765")
        with c.websocket_connect(f"/ws?token={app.state.guard.token}",
                                 headers={"Origin": "http://127.0.0.1:8765",
                                          "Host": "127.0.0.1:8765"}) as ws:
            app_state.bus.publish("probe", n=1)
            assert ws.receive_json()["type"] == "probe"


class TestConfigValidation:
    @pytest.mark.parametrize("body", [
        {"api": {"host": "0.0.0.0"}},           # locked: CLI only
        {"swarm": {"k_min": 0}},                # out of range
        {"privacy": {"tier": "EVERYONE"}},      # not an enum value
        {"swarm": {"lan_enabled": "yes"}},      # wrong type
        {"nonsense": 1},                         # unknown key
    ])
    def test_invalid_changes_refused(self, app, body):
        assert ui_client(app).put("/api/config", json=body).status_code == 400

    def test_k_max_never_below_k_min(self, app):
        cfg = ui_client(app).put("/api/config",
                                 json={"swarm": {"k_min": 3, "k_max": 1}}).json()
        assert cfg["swarm"]["k_max"] >= cfg["swarm"]["k_min"]

    def test_report_format_validated(self, app):
        assert ui_client(app).get("/api/requests/x/report?format=exe").status_code in (400, 404)


class TestEventsFromOtherLoops:
    def test_p2p_thread_events_reach_the_ui(self, app, app_state):
        """H16: events published on the P2P loop must reach the WebSocket."""
        import asyncio
        import threading
        c = TestClient(app, base_url="http://127.0.0.1:8765")
        with c.websocket_connect(f"/ws?token={app.state.guard.token}",
                                 headers={"Host": "127.0.0.1:8765"}) as ws:
            app_state.bus.publish("probe.before")
            assert ws.receive_json()["type"] == "probe.before"

            def other_loop():
                async def go():
                    app_state.bus.publish("node.connected", short_id="x")
                asyncio.run(go())
            t = threading.Thread(target=other_loop)
            t.start()
            t.join()
            assert ws.receive_json()["type"] == "node.connected"
