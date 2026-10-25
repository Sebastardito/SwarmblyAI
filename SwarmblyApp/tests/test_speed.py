"""Speed-aware routing (P3b.3'', 22 Oct 2026: llama3.1:8b on CPU timed out)."""

from __future__ import annotations

from types import SimpleNamespace

from swarmbly_app.engine.scheduler import LatencyStats, Scheduler, SpeedStats


def test_speed_is_learned_and_timeouts_bound_it():
    s = SpeedStats()
    s.observe("n", "m", tokens=200, gen_ms=10000)          # 20 tok/s
    assert s.tokens_per_s("n", "m") == 20
    s.observe_timeout("n", "big", max_tokens=600, timeout_s=60)
    assert s.tokens_per_s("n", "big") == 10
    assert s.estimate_s("n", "big", 600) == 60
    assert s.estimate_s("n", "unknown", 600) is None


class _Bus:
    def publish(self, *a, **k):
        pass


def _peer(node_id, models):
    return SimpleNamespace(node_id=node_id, tasks_inflight=0, rtt_ms=10.0,
                           advertisement={"models": [{"family": f, "version": v}
                                                     for f, v in models],
                                          "policy": {"max_concurrent": 1}})


class _Nodes:
    def __init__(self, peers):
        self.peers = {p.node_id: p for p in peers}

    def available_workers(self, kind="generate"):
        return list(self.peers.values())


def test_a_model_known_to_miss_the_deadline_loses_to_a_smaller_one():
    server = _peer("server", [("llama", "llama3.1:8b")])
    laptop = _peer("laptop", [("phi3", "phi3.5:3.8b")])
    speed = SpeedStats()
    speed.observe_timeout("server", "llama3.1:8b", max_tokens=600, timeout_s=60)
    speed.observe("laptop", "phi3.5:3.8b", tokens=300, gen_ms=15000)   # 20 tok/s
    s = Scheduler(_Nodes([server, laptop]), _Bus(), "r", k_min=1, k_max=2,
                  max_concurrency=4, timeout_s=60, hedge_fallback_s=30,
                  latency=LatencyStats(), speed=speed)
    peer, family, model = s._select(set(), set(), set(), max_tokens=600)
    assert model == "phi3.5:3.8b"
    # with no speed data the larger model still wins
    s2 = Scheduler(_Nodes([server, laptop]), _Bus(), "r", k_min=1, k_max=2,
                   max_concurrency=4, timeout_s=60, hedge_fallback_s=30,
                   latency=LatencyStats())
    assert s2._select(set(), set(), set(), max_tokens=600)[2] == "llama3.1:8b"


def test_app_keeps_speed_across_orchestrator_rebuilds(app_state):
    first = app_state.get_orchestrator()
    first.speed.observe("n", "m", 100, 1000)
    app_state.orchestrator = None
    assert app_state.get_orchestrator().speed.tokens_per_s("n", "m") == 100


def test_a_node_that_just_failed_ranks_below_healthy_ones():
    a = _peer("a", [("phi3", "phi3.5:3.8b")])
    b = _peer("b", [("phi3", "phi3.5:3.8b")])
    speed = SpeedStats()
    speed.record_failure("a")
    s = Scheduler(_Nodes([a, b]), _Bus(), "r", k_min=1, k_max=2, max_concurrency=4,
                  timeout_s=60, hedge_fallback_s=30, latency=LatencyStats(), speed=speed)
    assert s._select(set(), set(), set(), max_tokens=300)[0].node_id == "b"
    speed.record_success("a")
    assert not speed.recently_failed("a")


# -- hedge timer from learned elapsed times (P3d, 22 Oct 2026) ------------------------
def test_hedge_after_uses_learned_elapsed_time():
    import time
    from swarmbly_app.engine.scheduler import Attempt
    speed = SpeedStats()
    key = LatencyStats.key("generate", 400)
    speed.observe_elapsed("fast", "gemma2:2b", key, 2.0)
    s = Scheduler(_Nodes([]), _Bus(), "r", k_min=2, k_max=4, max_concurrency=4,
                  timeout_s=60, hedge_fallback_s=30, latency=LatencyStats(), speed=speed)
    a = Attempt("t0", 0, "fast", "gemma2", "initial", model="gemma2:2b",
                latency_key=key, started_at=time.monotonic())
    b = Attempt("t0", 1, "slow", "llama", "initial", model="llama3.1:8b",
                latency_key=key, started_at=time.monotonic())
    wait, source, late = s._hedge_after([a, b], key)
    assert source == "speed" and late is a and 4.5 < wait <= 5.0      # 2 × 2 s + 1 s
    a.hedged = True                                    # one speed hedge per attempt
    assert s._hedge_after([a, b], key)[:2] == (30, "fallback")
    queued = Attempt("t0", 2, "fast", "gemma2", "initial", model="gemma2:2b",
                     latency_key=key)                  # still in this node's queue
    assert s._hedge_after([queued], key)[1] == "fallback"
    overdue = Attempt("t0", 3, "fast", "gemma2", "initial", model="gemma2:2b",
                      latency_key=key, started_at=time.monotonic() - 60)
    assert s._hedge_after([overdue], key)[0] == 2.0    # never sooner than MIN_HEDGE_S


def test_stuck_fast_node_is_hedged_long_before_the_fallback(monkeypatch):
    import asyncio
    import time
    import swarmbly_app.engine.scheduler as sched
    monkeypatch.setattr(sched, "verify_result", lambda *a: "")
    monkeypatch.setattr(sched, "MIN_HEDGE_S", 0.1)

    class Nodes(_Nodes):
        async def dispatch_async(self, node_id, message, timeout_s):
            if node_id == "stuck":
                await asyncio.sleep(5)
            return {"type": "result", "attempt_id": message["attempt_id"],
                    "text": f"answer from {node_id}", "profile": {}, "telemetry": {}}

    stuck = _peer("stuck", [("llama", "llama3.1:8b")])     # larger: chosen first
    spare = _peer("spare", [("gemma2", "gemma2:2b")])
    speed = SpeedStats()
    key = LatencyStats.key("generate", 100)
    speed.observe_elapsed("stuck", "llama3.1:8b", key, 0.1)
    s = Scheduler(Nodes([stuck, spare]), _Bus(), "r", k_min=1, k_max=2,
                  max_concurrency=4, timeout_s=10, hedge_fallback_s=30,
                  latency=LatencyStats(), speed=speed)
    started = time.monotonic()
    out = asyncio.run(s.run_task("t0", lambda n, f, m=None: {"attempt_id": f"a{n}"}, 100))
    assert out[0].text == "answer from spare"
    assert time.monotonic() - started < 2.0
    assert s.hedges == 1 and "speed" in s.hedge_timer_source


def test_a_worker_still_busy_is_skipped_by_hedges_and_ranked_last():
    """P3e.1: after a deadline the old Mac refused five tries in a row."""
    a = _peer("a", [("phi3", "phi3.5:3.8b"), ("llama", "llama3.2:3b")])
    b = _peer("b", [("gemma2", "gemma2:2b")])
    speed = SpeedStats()
    speed.record_busy("a")
    s = Scheduler(_Nodes([a, b]), _Bus(), "r", k_min=1, k_max=3, max_concurrency=4,
                  timeout_s=60, hedge_fallback_s=30, latency=LatencyStats(), speed=speed)
    assert s._select(set(), set(), set(), max_tokens=300)[0].node_id == "b"
    assert s._select({("b", "gemma2")}, {"gemma2"}, {"b"}, free_only=True,
                     max_tokens=300) is None
    speed.record_busy("a", 0)
    assert not speed.busy("a")


def test_concurrency_refusal_marks_the_worker_busy(monkeypatch):
    import asyncio
    import swarmbly_app.engine.scheduler as sched

    class Refused(Exception):
        code, detail = "E_POLICY", "worker at concurrency limit"

    class Nodes(_Nodes):
        async def dispatch_async(self, node_id, message, timeout_s):
            if node_id == "a":
                raise Refused()
            return {"type": "result", "attempt_id": message["attempt_id"], "text": "ok",
                    "profile": {}, "telemetry": {}}

    monkeypatch.setattr(sched, "verify_result", lambda *x: "")
    a = _peer("a", [("phi3", "phi3.5:3.8b"), ("llama", "llama3.2:3b"),
                    ("qwen2", "qwen2.5:3b")])
    b = _peer("b", [("gemma2", "gemma2:2b")])
    speed = SpeedStats()
    s = Scheduler(Nodes([a, b]), _Bus(), "r", k_min=1, k_max=4, max_concurrency=4,
                  timeout_s=5, hedge_fallback_s=5, latency=LatencyStats(), speed=speed)
    out = asyncio.run(s.run_task("t0", lambda n, f, m=None: {"attempt_id": f"a{n}"}, 100))
    assert out[0].text == "ok" and speed.busy("a")
    assert [x.node_id for x in s.attempts] == ["a", "b"]      # not a, a, a, b


def test_cancelled_slow_attempts_teach_a_floor_and_rank_the_node_lower(monkeypatch):
    """P3f.1: the old Mac's attempts were always cancelled, never learned."""
    import asyncio
    import swarmbly_app.engine.scheduler as sched
    monkeypatch.setattr(sched, "verify_result", lambda *x: "")
    monkeypatch.setattr(sched, "MIN_HEDGE_S", 0.05)

    class Nodes(_Nodes):
        async def dispatch_async(self, node_id, message, timeout_s):
            await asyncio.sleep(3 if node_id == "old" else 0.0)
            return {"type": "result", "attempt_id": message["attempt_id"], "text": "ok",
                    "profile": {}, "telemetry": {}}

    old = _peer("old", [("phi3", "phi3.5:3.8b")])
    new = _peer("new", [("gemma2", "gemma2:2b")])
    speed = SpeedStats()
    s = Scheduler(Nodes([old, new]), _Bus(), "r", k_min=1, k_max=2, max_concurrency=4,
                  timeout_s=10, hedge_fallback_s=0.2, latency=LatencyStats(), speed=speed)
    asyncio.run(s.run_task("t0", lambda n, f, m=None: {"attempt_id": f"a{n}"}, 100))
    assert [a.status for a in s.attempts] == ["cancelled_slow", "accepted"]
    key = LatencyStats.key("generate", 100)
    assert speed.expected_elapsed("old", "phi3.5:3.8b", key) >= 0.2
    assert speed.busy("old")
    s2 = Scheduler(Nodes([old, new]), _Bus(), "r", k_min=1, k_max=2, max_concurrency=4,
                   timeout_s=10, hedge_fallback_s=0.2, latency=LatencyStats(), speed=speed)
    speed.record_busy("old", 0)
    assert s2._select(set(), set(), set(), max_tokens=100)[0].node_id == "new"


def test_a_worker_without_backend_is_a_last_resort():
    """P3f.1: the old Mac had no reachable Ollama and was picked first anyway."""
    a = _peer("a", [("phi3", "phi3.5:3.8b")])
    b = _peer("b", [("gemma2", "gemma2:2b")])
    speed = SpeedStats()
    speed.record_unavailable("a")
    s = Scheduler(_Nodes([a, b]), _Bus(), "r", k_min=2, k_max=3, max_concurrency=4,
                  timeout_s=60, hedge_fallback_s=30, latency=LatencyStats(), speed=speed)
    # even with "b" already used for this task, "a" stays last
    assert s._select(set(), set(), set(), max_tokens=300)[0].node_id == "b"
    assert s._select({("b", "gemma2")}, {"gemma2"}, {"b"}, max_tokens=300)[0].node_id == "a"
    speed.record_success("a")
    assert not speed.unavailable("a")


def test_cold_model_load_is_not_generation_speed(monkeypatch):
    """P3k.1: a 25 s cold load made the largest models look too slow."""
    import asyncio
    import swarmbly_app.engine.scheduler as sched
    monkeypatch.setattr(sched, "verify_result", lambda *x: "")

    class Nodes(_Nodes):
        async def dispatch_async(self, node_id, message, timeout_s):
            return {"type": "result", "attempt_id": message["attempt_id"], "text": "ok",
                    "profile": {"model_version": "llama3.1:8b"},
                    "telemetry": {"tokens_out": 100, "gen_ms": 25000, "load_ms": 20000}}

    speed = SpeedStats()
    s = Scheduler(Nodes([_peer("srv", [("llama", "llama3.1:8b")])]), _Bus(), "r", k_min=1,
                  k_max=1, max_concurrency=4, timeout_s=60, hedge_fallback_s=30,
                  latency=LatencyStats(), speed=speed)
    asyncio.run(s.run_task("t0", lambda n, f, m=None: {"attempt_id": f"a{n}"}, 400))
    assert speed.tokens_per_s("srv", "llama3.1:8b") == 20        # 100 tokens in 5 s


def test_a_model_rejected_in_this_request_ranks_after_the_others():
    a = _peer("a", [("phi3", "phi3.5:3.8b")])
    b = _peer("b", [("gemma2", "gemma2:2b")])
    s = Scheduler(_Nodes([a, b]), _Bus(), "r", k_min=1, k_max=3, max_concurrency=4,
                  timeout_s=60, hedge_fallback_s=30, latency=LatencyStats())
    assert s._select(set(), set(), set(), max_tokens=100)[2] == "phi3.5:3.8b"
    s.rejected_models.add("phi3.5:3.8b")
    assert s._select(set(), set(), set(), max_tokens=100)[2] == "gemma2:2b"
