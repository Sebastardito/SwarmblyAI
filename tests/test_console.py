"""Terminal output: outcomes, not every connection attempt (17 Oct 2026)."""

from __future__ import annotations

import logging
import logging.config
import time

from swarmbly_app.console import ConsoleReporter, QuietFilter, uvicorn_log_config
from swarmbly_app.events import EventBus


def _record(msg, *args):
    return logging.LogRecord("uvicorn.error", logging.INFO, __file__, 1, msg, args, None)


class TestQuietFilter:
    def test_stale_tab_websocket_lines_are_dropped(self):
        f = QuietFilter()
        assert not f.filter(_record('%s - "WebSocket %s" %d', "127.0.0.1:57536",
                                    "/ws?token=SECRET", 403))
        assert not f.filter(_record("connection rejected (403 Forbidden)"))
        assert not f.filter(_record("connection open"))

    def test_tokens_are_redacted_elsewhere(self):
        rec = _record("GET /api/x?token=SECRET123 failed")
        assert QuietFilter().filter(rec)
        assert "SECRET123" not in rec.getMessage() and "[redacted]" in rec.getMessage()

    def test_other_lines_pass(self):
        assert QuietFilter().filter(_record("Uvicorn running on http://127.0.0.1:8765"))

    def test_log_config_installs_the_filter(self):
        cfg = uvicorn_log_config()
        assert cfg["handlers"]["default"]["filters"] == ["quiet"]
        assert "swarmbly.console" in cfg["loggers"]
        logging.config.dictConfig(cfg)       # valid configuration


class _Peer:
    def __init__(self, connected):
        self.connected = connected


class TestConsoleReporter:
    def _reporter(self, peers=None, delay=0.05):
        bus, lines = EventBus(), []
        rep = ConsoleReporter(bus, lambda: peers or {}, no_nodes_after_s=delay,
                              emit=lines.append)
        return bus, rep, lines

    def test_found_once_and_connected(self):
        bus, rep, lines = self._reporter()
        for _ in range(3):
            bus.publish("node.discovered", address="192.168.0.9", port=9765,
                        node_hint="abc123", source="mdns")
        bus.publish("node.connected", short_id="abc123", address="192.168.0.9",
                    worker=True, node_id="abc123xyz", source="mdns")
        found = [l for l in lines if l.startswith("Found node")]
        assert len(found) == 1
        assert any("Connected and authenticated" in l and "worker" in l for l in lines)

    def test_single_no_nodes_message_after_an_empty_search(self):
        bus, rep, lines = self._reporter()
        bus.publish("node.discovery", state="on")
        time.sleep(0.2)
        assert sum("No Swarmbly nodes found" in l for l in lines) == 1
        rep.stop()

    def test_no_message_when_a_node_was_found(self):
        bus, rep, lines = self._reporter()
        bus.publish("node.discovery", state="on")
        bus.publish("node.discovered", address="10.0.0.2", port=9765, node_hint="n1")
        time.sleep(0.2)
        assert not any("No Swarmbly nodes found" in l for l in lines)

    def test_handshake_failures_are_rate_limited(self):
        bus, rep, lines = self._reporter()
        for _ in range(5):
            bus.publish("node.handshake_failed", address="10.0.0.3", port=9765,
                        reason="bad signature")
        assert sum("Could not authenticate" in l for l in lines) == 1

    def test_rescan_summary(self):
        bus, rep, lines = self._reporter(peers={"x": _Peer(False)})
        rep.scan_finished({"queried": 0, "answered": 0})
        rep.scan_finished({"queried": 1, "answered": 1})
        rep.scan_finished({"discovery": "off"})
        assert "no Swarmbly node answered" in lines[0]
        assert lines[1] == "Search finished: 1 node(s) answered."
        assert "discovery is off" in lines[2]
