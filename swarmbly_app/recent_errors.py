"""A small, privacy-safe ring of recent error *codes* for the doctor export.

The App's events carry human messages, hosts and sometimes paths. None of that
belongs in a file a volunteer sends to a maintainer. This recorder keeps only
the stable event type (``node.handshake_failed``, ``relay.push_refused``, …)
and its timestamp; the failed-request rows in SQLite contribute ``request.failed``.
The full error stays in the local log and in the UI, never in the export.
"""

from __future__ import annotations

import re
import threading
import time
from collections import deque
from typing import Any

#: Event types that describe a failure or a security warning.
ERROR_SUFFIXES = ("_failed", "_error", "_refused", "_rejected", "_down",
                  "_warning")
_SAFE_CODE = re.compile(r"^(?:E_[A-Z0-9_]{2,40}|[a-z][a-z0-9_.-]{2,80})$")


def _iso(timestamp: float) -> str:
    import datetime
    return datetime.datetime.fromtimestamp(
        timestamp, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_code(value: Any) -> str:
    text = str(value or "").strip()
    return text if _SAFE_CODE.match(text) else ""


def _event_code(event: dict[str, Any]) -> str:
    event_type = str(event.get("type") or "")
    payload = event.get("payload") or {}
    if event_type == "sandbox.prepare":
        status = str(payload.get("status") or "")
        if status == "failed":
            return "sandbox.prepare_failed"
        if status == "refused":
            return "sandbox.prepare_refused"
        return ""
    if event_type.endswith(ERROR_SUFFIXES):
        return _safe_code(event_type)
    return ""


class RecentErrors:
    """Subscribes to the bus and answers ``snapshot()`` with codes and times."""

    def __init__(self, bus: Any = None, db: Any = None, limit: int = 25) -> None:
        self.db = db
        self._items: deque[dict[str, Any]] = deque(maxlen=limit)
        self._lock = threading.Lock()
        if bus is not None:
            bus.subscribe(self._on_event)

    def _on_event(self, event: dict[str, Any]) -> None:
        code = _event_code(event)
        if not code:
            return
        self.add(code, float(event.get("ts") or time.time()))

    def add(self, code: str, timestamp: float | None = None) -> None:
        safe = _safe_code(code)
        if not safe:
            return
        with self._lock:
            self._items.append({"at": _iso(timestamp or time.time()), "code": safe})

    def snapshot(self, limit: int = 10) -> list[dict[str, str]]:
        """The newest codes, merged with failed requests from the local DB."""
        items: list[dict[str, Any]] = []
        with self._lock:
            items.extend(dict(item) for item in self._items)
        try:
            for row in (self.db.recent_failures(limit) if self.db is not None else []):
                when = float(row.get("finished_at") or row.get("started_at") or 0)
                if when:
                    items.append({"at": _iso(when), "code": "request.failed"})
        except Exception:
            pass
        items.sort(key=lambda item: str(item.get("at") or ""))
        return items[-max(1, int(limit)):][::-1]
