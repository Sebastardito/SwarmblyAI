# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from relay.limits import PushRateLimiter


def test_push_rate_limit_is_per_node_and_per_hour():
    window = ["2026-11-21T10"]
    limiter = PushRateLimiter(2, clock=lambda: window[0])
    assert limiter.allow("owner-a")
    assert limiter.allow("owner-a")
    assert not limiter.allow("owner-a")
    assert limiter.remaining("owner-a") == 0
    # Another owner has its own window.
    assert limiter.allow("owner-b")
    # A new UTC hour resets the window.
    window[0] = "2026-11-21T11"
    assert limiter.remaining("owner-a") == 2
    assert limiter.allow("owner-a")


def test_push_rate_limit_never_drops_below_one():
    limiter = PushRateLimiter(0)
    assert limiter.allow("owner")
    assert not limiter.allow("owner")
