"""What the terminal shows: network outcomes, not every connection attempt.

Two sources used to flood the terminal (reported 17 October 2026):

1. **A browser tab from an earlier launch.** The session token changes at
   every launch; an open tab kept the old one and its WebSocket reconnected
   every two seconds, each attempt logged twice by uvicorn ("WebSocket
   /ws?token=… 403", "connection rejected") — with the token in clear text.
   :class:`QuietFilter` drops those lines, redacts ``token=`` everywhere, and
   says once a minute what is happening. The web client now reloads itself
   when its token is stale (``web/js/api.js``).
2. **Discovery chatter.** :class:`ConsoleReporter` turns the P2P events into
   a few lines: a node found, a node connected and authenticated, a node
   lost, an authentication failure (once per address), and — after a full
   search with no answer — a single "no nodes found" line that says how to
   search again.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, Callable

LOGGER_NAME = "swarmbly.console"
NO_NODES_AFTER_S = 20.0
STALE_TAB_NOTICE_EVERY_S = 60.0
HANDSHAKE_NOTICE_EVERY_S = 300.0

_TOKEN = re.compile(r"(token=)[^&\s\"']+", re.I)
_WS_NOISE = re.compile(r'"WebSocket /ws|connection (rejected|open|closed)', re.I)

log = logging.getLogger(LOGGER_NAME)


class QuietFilter(logging.Filter):
    """uvicorn handler filter: no per-connection WebSocket lines, no tokens."""

    def __init__(self, name: str = "") -> None:
        super().__init__(name)
        self._last_notice = 0.0

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if _WS_NOISE.search(message):
            if " 403" in message or "rejected" in message:
                now = time.monotonic()
                if now - self._last_notice >= STALE_TAB_NOTICE_EVERY_S:
                    self._last_notice = now
                    log.info("A browser tab from an earlier session is trying to "
                             "reconnect (the session token changes at every "
                             "launch). Reload that tab; this note repeats at most "
                             "once a minute.")
            return False
        if "token=" in message.lower():
            record.msg, record.args = _TOKEN.sub(r"\1[redacted]", message), ()
        return True


def uvicorn_log_config() -> dict[str, Any]:
    """uvicorn's default logging, with :class:`QuietFilter` on its console
    handler and the ``swarmbly.console`` logger printed the same way."""
    import copy

    from uvicorn.config import LOGGING_CONFIG
    cfg = copy.deepcopy(LOGGING_CONFIG)
    cfg.setdefault("filters", {})["quiet"] = {"()": "swarmbly_app.console.QuietFilter"}
    cfg["handlers"]["default"]["filters"] = ["quiet"]
    cfg["loggers"][LOGGER_NAME] = {"handlers": ["default"], "level": "INFO",
                                   "propagate": False}
    return cfg


class ConsoleReporter:
    """Summarises P2P events on the terminal (bus subscriber)."""

    def __init__(self, bus, peers_getter: Callable[[], dict[str, Any]],
                 no_nodes_after_s: float = NO_NODES_AFTER_S,
                 emit: Callable[[str], None] | None = None) -> None:
        self._peers = peers_getter
        self._delay = no_nodes_after_s
        self._emit = emit or log.info
        self._lock = threading.Lock()
        self._found: set[str] = set()
        self._handshake_noted: dict[str, float] = {}
        self._timer: threading.Timer | None = None
        bus.subscribe(self._on_event)

    # -- events --------------------------------------------------------------------
    def _on_event(self, event: dict[str, Any]) -> None:
        kind, p = event.get("type", ""), event.get("payload") or {}
        if kind == "node.discovery":
            if p.get("state") == "on":
                self._emit("Searching for Swarmbly nodes on the local network…")
                self._arm()
            else:
                self._disarm()
        elif kind == "node.discovered":
            key = p.get("node_hint") or f"{p.get('address')}:{p.get('port')}"
            with self._lock:
                new = key not in self._found
                self._found.add(key)
            if new:
                self._emit(f"Found node {key or '?'} at {p.get('address')}:{p.get('port')} "
                           f"({p.get('source', 'mdns')})")
        elif kind == "node.connected":
            role = "worker" if p.get("worker") else "peer"
            self._emit(f"Connected and authenticated: node {p.get('short_id', '?')} at "
                       f"{p.get('address')} ({role})")
        elif kind in ("node.disconnected", "node.goodbye"):
            key = p.get("node_hint") or (p.get("node_id") or "")[:12]
            with self._lock:
                self._found.discard(key)
            self._emit(f"Node {key or p.get('address', '?')} left the network")
        elif kind == "node.handshake_failed":
            address = str(p.get("address", "?"))
            now = time.monotonic()
            with self._lock:
                due = now - self._handshake_noted.get(address, -1e9) >= HANDSHAKE_NOTICE_EVERY_S
                if due:
                    self._handshake_noted[address] = now
            if due:
                self._emit(f"Could not authenticate {address}: "
                           f"{p.get('reason') or p.get('detail') or 'handshake failed'}")

    # -- "no nodes" summary --------------------------------------------------------
    def _arm(self) -> None:
        self._disarm()
        timer = threading.Timer(self._delay, self._check_empty)
        timer.daemon = True
        self._timer = timer
        timer.start()

    def _disarm(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _connected(self) -> int:
        try:
            return sum(1 for peer in self._peers().values() if getattr(peer, "connected", False))
        except Exception:
            return 0

    def _check_empty(self) -> None:
        with self._lock:
            found = len(self._found)
        if not found and not self._connected():
            self._emit("No Swarmbly nodes found on the local network. Discovery keeps "
                       "listening; use “Search again” in the Monitor (or POST "
                       "/api/swarm/rescan) to search now.")

    def scan_finished(self, result: dict[str, Any]) -> None:
        """Called after an explicit search (``/api/swarm/rescan``)."""
        if result.get("discovery") == "off":
            self._emit("Search skipped: local-network discovery is off.")
        elif not result.get("answered") and not self._connected():
            self._emit("Search finished: no Swarmbly node answered on the local "
                       "network. Discovery keeps listening.")
        else:
            self._emit(f"Search finished: {result.get('answered', 0)} node(s) answered.")

    def stop(self) -> None:
        self._disarm()
