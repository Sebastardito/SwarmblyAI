"""Routing on a heterogeneous swarm (P3b, 21 October 2026)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from swarmbly_app.engine.capability import eligible, model_params_b, rank_params
from swarmbly_app.engine.scheduler import LatencyStats, Scheduler


@pytest.mark.parametrize("tag,size", [
    ("qwen2.5:7b", 7.0), ("phi3.5:3.8b", 3.8), ("llama3.1:8b-instruct-q4_K_M", 8.0),
    ("granite3.1-dense:2b", 2.0), ("qwen2.5:0.5b", 0.5), ("mistral:latest", None),
])
def test_params_from_tag(tag, size):
    assert model_params_b(tag) == size


def test_eligibility_and_rank():
    assert not eligible("qwen2.5:0.5b", 1.5) and eligible("qwen2.5:3b", 1.5)
    assert eligible("mistral:latest", 1.5)               # unknown size: owner's choice
    assert rank_params("llama3.1:8b") > rank_params("llama3.2:1b")


class _Bus:
    def publish(self, *a, **k):
        pass


def _peer(node_id, models, cap=1):
    return SimpleNamespace(node_id=node_id, tasks_inflight=0, rtt_ms=10.0,
                           advertisement={"models": [{"family": f, "version": v}
                                                     for f, v in models],
                                          "policy": {"max_concurrent": cap}})


class _Nodes:
    def __init__(self, peers, replies):
        self.peers = {p.node_id: p for p in peers}
        self.replies = replies            # node_id -> text
        self.sent = []

    def available_workers(self, kind="generate"):
        return list(self.peers.values())

    async def dispatch_async(self, node_id, message, timeout_s):
        self.sent.append((node_id, message))
        return {"type": "result", "attempt_id": message["attempt_id"],
                "text": self.replies[node_id], "profile": {}, "telemetry": {}}


def _scheduler(nodes, k_min=1, k_max=3, min_b=1.5):
    return Scheduler(nodes, _Bus(), "r", k_min=k_min, k_max=k_max, max_concurrency=4,
                     timeout_s=5, hedge_fallback_s=5, latency=LatencyStats(),
                     min_params_b=min_b)


SERVER = _peer("server", [("llama", "llama3.2:1b"), ("llama", "llama3.1:8b"),
                          ("qwen2", "qwen2.5:0.5b"), ("qwen2", "qwen2.5:7b")])
LAPTOP = _peer("laptop", [("qwen2", "qwen2.5:0.5b"), ("qwen2", "qwen2.5:1.5b")])


def test_candidates_take_the_largest_eligible_model_per_family():
    cands = {(p.node_id, f): m for p, f, m in _scheduler(_Nodes([SERVER, LAPTOP], {}))._candidates()}
    assert cands == {("server", "llama"): "llama3.1:8b", ("server", "qwen2"): "qwen2.5:7b",
                     ("laptop", "qwen2"): "qwen2.5:1.5b"}


def test_tiny_only_swarm_still_answers():
    tiny = _peer("tiny", [("qwen2", "qwen2.5:0.5b")])
    cands = _scheduler(_Nodes([tiny], {}))._candidates()
    assert [m for _, _, m in cands] == ["qwen2.5:0.5b"]


def test_echo_is_rejected_and_retried_elsewhere(monkeypatch):
    import swarmbly_app.engine.scheduler as sched
    monkeypatch.setattr(sched, "verify_result", lambda *a: "")
    nodes = _Nodes([SERVER, LAPTOP], {"server": "1. dog\n2. cat", "laptop": "1. perro\n2. gato"})
    s = _scheduler(nodes, k_min=1, k_max=3)
    # make the laptop look best so it is tried first
    s._load["server"] = 5

    def build(n, family, model=None):
        return {"attempt_id": f"a{n}", "constraints": {"model": model}}

    def valid(text):
        return "dog" in text
    replicas = asyncio.run(s.run_task("t0", build, 100, validate=valid))
    assert [r.text for r in replicas] == ["1. dog\n2. cat"]
    assert [a.status for a in s.attempts] == ["rejected", "accepted"]
    assert s.attempts[0].code == "E_QUALITY"
    assert nodes.sent[0][1]["constraints"]["model"] == "qwen2.5:1.5b"


def test_all_rejected_returns_the_degraded_answer(monkeypatch):
    import swarmbly_app.engine.scheduler as sched
    monkeypatch.setattr(sched, "verify_result", lambda *a: "")
    nodes = _Nodes([LAPTOP], {"laptop": "1. perro"})
    s = _scheduler(nodes, k_min=1, k_max=1)
    out = asyncio.run(s.run_task("t0", lambda n, f, m=None: {"attempt_id": f"a{n}"}, 100,
                                 validate=lambda text: False))
    assert [r.text for r in out] == ["1. perro"]


def test_worker_picks_exact_model_then_largest_of_family(app_state, fake_chat):
    from test_worker_policy import make_worker, task_message
    app_state.config.update({"swarm": {"worker_enabled": True,
                                       "worker_models": ["llama3.2:1b", "llama3.1:8b",
                                                         "qwen2.5:3b"]}})
    _, fake = fake_chat
    worker = make_worker(app_state, fake)
    assert worker._pick_model({"constraints": {"model_family": "llama3.2"}}) in (
        "llama3.1:8b", "llama3.2:1b")
    assert worker._pick_model({"constraints": {"model": "qwen2.5:3b"}}) == "qwen2.5:3b"
    assert worker._pick_model({"constraints": {"model_family": "llama"}}) == "llama3.1:8b"


def test_admission_keeps_several_items_per_fragment():
    from swarmbly_app.engine.admission import admit
    prompt = "Para cada país, indica su capital:\n" + "\n".join(
        f"{i}. País {i}" for i in range(1, 9))
    assert admit(prompt, n_max=16, n_workers=8, min_items_per_fragment=3).n_tasks == 3
    assert admit(prompt, n_max=16, n_workers=8).n_tasks >= 3


def test_items_are_normalised_one_per_line():
    from swarmbly_app.engine.orchestrator import _normalise_items
    items = {5: "Pinzón de Darwin", 6: "Tiburón martillo", 7: "Pingüino", 8: "Rana"}
    raw = "```markdown\n5. Ave 6. Pez\n- 7. Ave\n*   #8: anfibio\n```"
    out = _normalise_items(raw, items)
    assert out.splitlines()[:2] == ["5. Ave", "6. Pez"]


def test_rejected_attempt_keeps_a_preview(monkeypatch):
    import swarmbly_app.engine.scheduler as sched
    monkeypatch.setattr(sched, "verify_result", lambda *a: "")
    nodes = _Nodes([LAPTOP, SERVER], {"server": "1. dog", "laptop": "1. perro"})
    s = _scheduler(nodes, k_min=1, k_max=2)
    s._load["server"] = 5
    asyncio.run(s.run_task("t0", lambda n, f, m=None: {"attempt_id": f"a{n}"}, 100,
                           validate=lambda text: "dog" in text))
    rejected = [a.to_dict() for a in s.attempts if a.status == "rejected"]
    assert rejected and rejected[0]["note"] == "1. perro"


def test_hedges_never_queue_on_a_busy_worker():
    s = _scheduler(_Nodes([LAPTOP], {}), k_min=1, k_max=3)
    s._load["laptop"] = 1                                 # its only slot is taken
    assert s._select(set(), set(), set(), free_only=True) is None
    assert s._select(set(), set(), set()) is not None     # retries may still queue


def test_failed_task_falls_back_to_the_local_model(tmp_path):
    """P3b.3: when every remote attempt fails, the section is written locally."""
    from test_p2p_two_nodes import connect, make_node
    worker, _ = make_node(tmp_path, "W", worker=True, fail=True)
    client, fake_c = make_node(tmp_path, "C",
                               reply="1. Quito\n2. Lima\n3. Santiago\n4. Bogotá",
                               extra={"swarm": {"k_min": 1, "k_max": 1}})
    try:
        connect(client, worker)
        conv = client.chat.create_conversation(mode="lan")
        client.chat.send(conv["id"], "Para cada uno de los siguientes países, indica solo "
                         "el nombre de su capital:\n1. Ecuador\n2. Perú\n3. Chile\n"
                         "4. Argentina\n5. Colombia\n6. Uruguay\n7. Paraguay\n8. Venezuela",
                         mode="lan", run_async=False)
        final = client.chat.get_messages(conv["id"])[-1]
        assert final["meta"]["status"] == "done", final["meta"]
        assert final["meta"]["executed"] == "distributed", final["meta"].get("local_reason")
        assert final["meta"]["swarm"]["local_fallback_tasks"]
        assert "Quito" in final["content"]
    finally:
        worker.stop()
        client.stop()


# -- cancellation (P3b.3: workers kept generating after the requester gave up) ----
def test_worker_cancel_stops_the_task(app_state):
    import threading
    from conftest import FakeBackend
    from test_worker_policy import make_worker, task_message
    app_state.config.update({"swarm": {"worker_enabled": True}})
    fake = FakeBackend("1. dog", delay=0.5)
    worker = make_worker(app_state, fake)
    message = task_message()

    async def scenario():
        task = asyncio.ensure_future(worker.handle("peerA", message))
        await asyncio.sleep(0.1)
        assert not worker.cancel("intruder", message["attempt_id"])   # only the sender
        assert worker.cancel("peerA", message["attempt_id"])
        return await task
    reply = asyncio.run(scenario())
    assert reply["type"] == "error" and reply["code"] == "E_DEADLINE"


def test_timeout_sends_cancel_to_the_worker(tmp_path):
    from test_p2p_two_nodes import connect, make_node, wait_for
    from swarmbly_app.p2p.messages import packet
    worker, _ = make_node(tmp_path, "W", worker=True, delay=1.5)
    client, _ = make_node(tmp_path, "C")
    try:
        connect(client, worker)
        msg = packet(attempt_id="a-cancel-1",
                     contract={"v": 1, "objective": "x", "audience": "", "register": "formal",
                               "format": "prose", "target_len": None,
                               "lexicon": {"prefer": [], "forbid": []}, "entities": [],
                               "style_seed": "", "budget": {"max_out_tokens": 50}},
                     predecessors=[], task={"instruction": "hola", "kind": "generate",
                                            "expects": {"format": "prose", "min_tokens": 0,
                                                        "max_tokens": 50}},
                     deadline_ms=10000)
        with pytest.raises(Exception):
            client.nodes.dispatch(worker.identity.node_id, msg, timeout_s=0.3)
        assert wait_for(lambda: any(e.is_set() for e in worker.worker._cancels.values()),
                        timeout=2.0)
    finally:
        worker.stop()
        client.stop()


def test_deadline_keeps_the_slot_for_a_grace_period(monkeypatch):
    import time as _t
    import swarmbly_app.engine.scheduler as sched
    from swarmbly_app.p2p.node import PeerError

    class Slow(_Nodes):
        async def dispatch_async(self, node_id, message, timeout_s):
            raise PeerError("E_DEADLINE", "worker timeout")
    s = _scheduler(Slow([LAPTOP], {}), k_min=1, k_max=1)
    with pytest.raises(sched.TaskFailed):
        asyncio.run(s.run_task("t0", lambda n, f, m=None: {"attempt_id": f"a{n}"}, 100))
    assert s._busy_until["laptop"] > _t.monotonic()
    assert s.attempts[0].note == "worker timeout"


def test_retries_do_not_queue_when_a_local_model_exists(monkeypatch):
    """P3b.3': queued retries waited ~50 s and timed out; fail fast instead."""
    import swarmbly_app.engine.scheduler as sched
    from swarmbly_app.p2p.node import PeerError

    class Busy(_Nodes):
        async def dispatch_async(self, node_id, message, timeout_s):
            raise PeerError("E_DISCONNECTED", "gone")
    s = Scheduler(Busy([LAPTOP], {}), _Bus(), "r", k_min=1, k_max=3, max_concurrency=4,
                  timeout_s=5, hedge_fallback_s=5, latency=LatencyStats(),
                  queue_retries=False)
    s._load["laptop"] = 0
    with pytest.raises(sched.TaskFailed):
        asyncio.run(s.run_task("t0", lambda n, f, m=None: {"attempt_id": f"a{n}"}, 100))
    assert len(s.attempts) == 1                  # no second attempt queued on a busy node


def test_lone_fence_language_line_is_removed():
    from swarmbly_app.engine import composer
    sec = composer.Section("Intro", "x", 100)
    assert composer.clean_section("markdown\nEn el vasto océano.", sec, "") == "En el vasto océano."


def test_unnumbered_answers_in_order_are_accepted_only_when_counts_match():
    """P3c.1: 'Reptil / Ave / Pez' (correct, but unnumbered) was rejected."""
    from swarmbly_app.engine.orchestrator import _parse_items
    items = {4: "Iguana marina", 5: "Pinzón de Darwin", 6: "Tiburón martillo"}
    assert _parse_items("Reptil\nAve\nPez", items) == {4: "Reptil", 5: "Ave", 6: "Pez"}
    assert _parse_items("```\nReptil\nAve\nPez\n```", items) == {4: "Reptil", 5: "Ave",
                                                                 6: "Pez"}
    assert _parse_items("Reptil\nAve", items) == {}      # count mismatch: no guessing


def test_answers_renumbered_from_one_are_mapped_to_their_items():
    """P3c.1: items 19–24 answered as '1. large … 6. river'."""
    from swarmbly_app.engine.orchestrator import _parse_items
    items = {19: "grande", 20: "pequeño", 21: "rápido", 22: "ciudad", 23: "montaña",
             24: "río"}
    out = _parse_items("1. large 2. small 3. fast 4. city 5. mountain 6. river", items)
    assert out == {19: "large", 20: "small", 21: "fast", 22: "city", 23: "mountain",
                   24: "river"}
    assert _parse_items("1. large 2. small", items) == {}        # partial: no guessing


def test_all_rejected_tries_the_local_model_before_degrading(tmp_path):
    """P3c.1: every remote replica echoed its items; the local model did not."""
    from test_p2p_two_nodes import connect, make_node
    worker, _ = make_node(tmp_path, "W", worker=True, reply="No lo sé.")
    client, _ = make_node(tmp_path, "C", reply="1. Quito\n2. Lima\n3. Santiago\n"
                          "4. Buenos Aires\n5. Bogotá\n6. Montevideo\n7. Asunción\n8. Caracas",
                          extra={"swarm": {"k_min": 1, "k_max": 1}})
    try:
        connect(client, worker)
        conv = client.chat.create_conversation(mode="lan")
        client.chat.send(conv["id"], "Para cada uno de los siguientes países, indica solo "
                         "el nombre de su capital:\n1. Ecuador\n2. Perú\n3. Chile\n"
                         "4. Argentina\n5. Colombia\n6. Uruguay\n7. Paraguay\n8. Venezuela",
                         mode="lan", run_async=False)
        final = client.chat.get_messages(conv["id"])[-1]
        assert final["meta"]["status"] == "done", final["meta"]
        assert final["meta"]["swarm"]["local_fallback_tasks"]
        assert "Quito" in final["content"] and "No lo sé" not in final["content"]
    finally:
        worker.stop()
        client.stop()


def test_retry_after_a_rejection_may_queue_on_a_busy_worker(monkeypatch):
    """P3e.1: two echoes, no free worker, so no retry; the local rescue
    echoed too. A quality rejection now retries even if it must wait."""
    import swarmbly_app.engine.scheduler as sched
    monkeypatch.setattr(sched, "verify_result", lambda *a: "")
    echo = _peer("echo", [("phi3", "phi3.5:3.8b")])
    good = _peer("good", [("gemma2", "gemma2:2b")])
    nodes = _Nodes([echo, good], {"echo": "1. perro", "good": "1. dog"})
    s = Scheduler(nodes, _Bus(), "r", k_min=1, k_max=3, max_concurrency=4, timeout_s=5,
                  hedge_fallback_s=5, latency=LatencyStats(), queue_retries=False)
    s._load["good"] = 1           # busy right now (another task of the request)
    out = asyncio.run(s.run_task("t0", lambda n, f, m=None: {"attempt_id": f"a{n}"}, 100,
                                 validate=lambda text: "dog" in text))
    assert [r.text for r in out] == ["1. dog"]
    assert [a.status for a in s.attempts] == ["rejected", "accepted"]
