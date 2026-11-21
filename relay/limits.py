# SPDX-License-Identifier: AGPL-3.0-only
"""Per-member limits for the relay: splices, bytes and manifest pushes.

The counters are in memory by design: the relay stores no payloads and no
long-term member history.  A restart resets the byte and push counters;
operators get budgets, not an accounting system.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Callable


@dataclass
class Usage:
    day: str = ""
    bytes: int = 0
    active_splices: int = 0


class LimitTracker:
    def __init__(self, *, max_splices_per_member: int = 4,
                 bytes_per_day: int = 2 * 1024 ** 3) -> None:
        self.max_splices = max(1, int(max_splices_per_member))
        self.bytes_per_day = max(0, int(bytes_per_day))
        self._usage: dict[str, Usage] = {}

    @staticmethod
    def _today() -> str:
        return dt.datetime.now(dt.timezone.utc).date().isoformat()

    def _get(self, node_id: str) -> Usage:
        usage = self._usage.get(node_id)
        today = self._today()
        if usage is None:
            usage = Usage(day=today)
            self._usage[node_id] = usage
        elif usage.day != today:
            # A new UTC day: keep active splices, reset the byte budget.
            usage.day = today
            usage.bytes = 0
        return usage

    def bytes_today(self, node_id: str) -> int:
        return self._get(node_id).bytes

    def active_splices(self, node_id: str) -> int:
        return self._get(node_id).active_splices

    def can_register(self, node_id: str) -> bool:
        return self._get(node_id).bytes < self.bytes_per_day

    def reserve(self, node_id: str) -> bool:
        usage = self._get(node_id)
        if usage.active_splices >= self.max_splices:
            return False
        usage.active_splices += 1
        return True

    def release(self, node_id: str) -> None:
        usage = self._get(node_id)
        usage.active_splices = max(0, usage.active_splices - 1)

    def add_bytes(self, node_id: str, count: int) -> bool:
        """Count forwarded bytes; False means the daily budget is exhausted."""
        usage = self._get(node_id)
        usage.bytes += max(0, int(count))
        return usage.bytes <= self.bytes_per_day


class PushRateLimiter:
    """A fixed-window hourly cap on owner manifest pushes.

    ``allow`` counts an attempt and returns False once the window is full.
    The key is the authenticated node id, which for an accepted push is the
    owner; a non-owner's attempts are refused before this limiter is reached.
    """

    def __init__(self, max_per_hour: int = 30, *,
                 clock: Callable[[], str] | None = None) -> None:
        self.max_per_hour = max(1, int(max_per_hour))
        self._clock = clock or self._utc_hour
        self._windows: dict[str, tuple[str, int]] = {}

    @staticmethod
    def _utc_hour() -> str:
        return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H")

    def remaining(self, node_id: str) -> int:
        window, count = self._windows.get(node_id, ("", 0))
        if window != self._clock():
            return self.max_per_hour
        return max(0, self.max_per_hour - count)

    def allow(self, node_id: str) -> bool:
        window = self._clock()
        current_window, count = self._windows.get(node_id, (window, 0))
        if current_window != window:
            count = 0
        if count >= self.max_per_hour:
            return False
        self._windows[node_id] = (window, count + 1)
        return True

