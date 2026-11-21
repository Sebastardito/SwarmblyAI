# SPDX-License-Identifier: AGPL-3.0-only
"""Per-member limits for the relay: concurrent splices and bytes per day.

The counters are in memory by design: the relay stores no payloads and no
long-term member history.  A restart resets the byte counter; operators get a
daily budget, not an accounting system.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


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
