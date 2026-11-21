"""Node roles (3.5, D-018): schema, advertisement, placement and execution.

These are *node* roles (what a machine offers), not the per-answer model roles
in :mod:`swarmbly_app.roles`.
"""

from __future__ import annotations

import asyncio
import itertools
import time
from types import SimpleNamespace

import pytest

from swarmbly_app import egress
from swarmbly_app.chat import ActiveRequest
from swarmbly_app.engine.directory import Directory
from swarmbly_app.engine.scheduler import (LatencyStats, RoleStats, Scheduler,
                                           TaskFailed)
from swarmbly_app.inference.base import GenerationResult
from swarmbly_app.node_roles import (clean_roles, derive_roles, models_for_role,
                                     normalise_advertisement)
from swarmbly_app.p2p.handshake import validate_advertisement
from swarmbly_app.p2p.messages import WIRE_VERSION, packet
from swarmbly_app.p2p.worker import E_ROLE_UNAVAILABLE
from swarmbly_app.state import AppState, _build_advertisement

from conftest import FakeBackend

_ports = itertools.count(20780)
MODELS = [{"family": "llama", "version": "llama3.1:8b"},
          {"family": "qwen2", "version": "qwen2.5:3b"}]


def wait_for(predicate, timeout=10.0, step=0.1):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return False


def make_node(tmp_path, name, *, worker=False, models=None, roles_cfg=None,
              mode="own_devices", reply="a useful fragment answer", fail=False,
              port=None):
    state = AppState(str(tmp_path / name))
    models = list(models or ["fake-model:1b"])
    cfg = {
        "swarm": {"p2p_port": port or next(_ports), "p2p_host": "127.0.0.1",
                  "lan_enabled": False, "worker_enabled": worker,
                  "worker_models": models, "worker_max_concurrent": 2,
                  "timeout_ms": 8000, "hedge_fallback_ms": 3000},
        "circle": {"admission_mode": mode, "node_name": name},
        "privacy": {"tier": "GLOBAL"},
        "model": {"model_name": models[0]},
    }
    if roles_cfg is not None:
        cfg["node_roles"] = roles_cfg
    state.config.update(cfg)
    fake = FakeBackend(reply, fail=fail)
    state.backends.resolve = lambda cfg=None: fake  # type: ignore[method-assign]
    state.start_p2p()
    return state, fake


@pytest.fixture()
def nodes(tmp_path):
    created = []

    def factory(*args, **kw):
        state, fake = make_node(tmp_path, *args, **kw)
        created.append(state)
        return state, fake

    yield factory
    for state in created:
        state.stop()


def add_to_circle(owner, member, circle=None):
    if circle is None:
        circle = owner.circles.create_circle("Nodos")
    invite = owner.circles.invite(
        circle["circle_id"],
        endpoints=[f"127.0.0.1:{owner.nodes.listen_port}"])
    member.circles.accept_invitation(
        invite["code"], endpoints=[f"127.0.0.1:{member.nodes.listen_port}"])
    assert wait_for(lambda: any(
        r["node_id"] == member.identity.node_id
        for r in owner.circles.list_payload()["circles"][0]["pending_joins"]))
    owner.circles.approve(circle["circle_id"], member.identity.node_id)
    assert wait_for(lambda: member.identity.node_id in owner.nodes.peers
                    and owner.nodes.peers[member.identity.node_id].admitted)
    assert wait_for(lambda: owner.identity.node_id in member.nodes.peers
                    and member.nodes.peers[owner.identity.node_id].admitted)
    return circle


def task_message(attempt="role:0", *, role=None, think=None, model=None):
    constraints = {"temperature": 0.2}
    if role:
        constraints["role"] = role
    if think is not None:
        constraints["think"] = think
    if model:
        constraints["model"] = model
    return packet(
        attempt_id=attempt,
        contract={"v": WIRE_VERSION, "objective": "o", "audience": "a",
                  "register": "neutral", "format": "prose", "target_len": 100,
                  "lexicon": {}, "entities": [], "style_seed": "",
                  "budget": {"max_out_tokens": 300}},
        predecessors=[],
        task={"instruction": "answer", "kind": "generate",
              "expects": {"format": "prose", "max_tokens": 300}},
        deadline_ms=60000, lane="PUBLIC", tier="GLOBAL", constraints=constraints)


def build_packet(attempt, family=None, model=None):
    return task_message(f"p:{attempt}", model=model)


# -- schema and validation -----------------------------------------------------------

@pytest.mark.parametrize("roles", [
    "not-a-list",
    [{"role": "large_model", "model": "llama3.1:8b", "params_b": 8}] * 9,
    [{"role": "large_model", "model": "llama3.1:8b"}],
    [{"role": "large_model", "model": "llama3.1:8b", "params_b": True}],
    [{"role": "large_model", "model": "llama3.1:8b", "params_b": 0}],
    [{"role": "large_model", "model": "llama3.1:8b", "params_b": 20000}],
    [{"role": "large_model", "model": "<bad>", "params_b": 8}],
    [{"role": "reasoner", "model": "llama3.1:8b", "think": False}],
    [{"role": "reasoner", "model": "llama3.1:8b"}],
    [{"role": "search", "engines": ["a", "b", "c", "d", "e"]}],
    [{"role": "search", "engines": ["<script>"]}],
    [{"role": "corpus", "name": "x" * 41, "size": "S"}],
    [{"role": "corpus", "name": "../secret", "size": "S"}],
    [{"role": "corpus", "name": "docs", "size": "XL"}],
    [{"role": "corpus", "name": " leading", "size": "S"}],
    [{"role": "corpus", "name": "ok", "size": "M"}, {"role": "search", "engines": []},
     "not-an-object"],
])
def test_roles_validation_rejects(roles):
    problems = validate_advertisement(
        {"node_id": "x", "models": MODELS, "roles": roles})
    assert problems


def test_all_four_roles_are_valid_and_normalised():
    roles = [
        {"role": "large_model", "model": "llama3.1:8b", "params_b": 8,
         "unexpected": "ignored"},
        {"role": "reasoner", "model": "qwen2.5:3b", "think": True},
        {"role": "search", "engines": ["searxng", "wikipedia"]},
        {"role": "corpus", "name": "Lab papers", "size": "M"},
    ]
    assert validate_advertisement({"node_id": "x", "models": MODELS,
                                   "roles": roles}) == []
    problems, clean = clean_roles(roles, MODELS)
    assert problems == []
    assert [entry["role"] for entry in clean] == [
        "large_model", "reasoner", "search", "corpus"]
    assert "unexpected" not in clean[0]
    assert clean[2]["engines"] == ["searxng", "wikipedia"]


def test_unknown_roles_and_models_not_advertised_are_dropped():
    roles = [{"role": "future_role", "anything": 1},
             {"role": "large_model", "model": "other:1b", "params_b": 2},
             {"role": "search", "engines": ["searxng"]}]
    problems, clean = clean_roles(roles, MODELS)
    assert problems == []
    assert clean == [{"role": "search", "engines": ["searxng"]}]
    # The stored advertisement keeps only accepted entries.
    adv = normalise_advertisement({"node_id": "x", "models": MODELS, "roles": roles})
    assert adv["roles"] == clean


def test_at_most_eight_accepted_entries():
    roles = [{"role": "search", "engines": [f"e{i}"]} for i in range(8)]
    assert validate_advertisement({"node_id": "x", "models": MODELS,
                                   "roles": roles}) == []
    roles.append({"role": "search", "engines": ["extra"]})
    assert validate_advertisement({"node_id": "x", "models": MODELS,
                                   "roles": roles})


# -- derivation ----------------------------------------------------------------------

def test_derivation_uses_shared_models_threshold_and_reasoner_list():
    cfg = {"node_roles": {"large_model_min_b": 7.0,
                          "reasoner_models": ["qwen2.5:3b"]}}
    roles = derive_roles(["llama3.1:8b", "qwen2.5:3b", "tiny:0.5b"], cfg)
    assert {"role": "large_model", "model": "llama3.1:8b", "params_b": 8.0} in roles
    assert {"role": "reasoner", "model": "qwen2.5:3b", "think": True} in roles
    assert all(entry.get("model") != "tiny:0.5b" for entry in roles)
    # A higher threshold and an unmarked model remove both.
    other = derive_roles(["llama3.1:8b", "qwen2.5:3b"],
                         {"node_roles": {"large_model_min_b": 10.0,
                                         "reasoner_models": []}})
    assert other == []
    # A tag without a size is never guessed into large_model.
    assert derive_roles(["mystery:latest"], cfg) == []
    # Worker role off: nothing is announced.
    assert derive_roles(["llama3.1:8b"], cfg, announce=False) == []


def test_derivation_respects_the_advertisement_cap():
    models = [f"m{i}:8b" for i in range(9)]
    roles = derive_roles(models, {"node_roles": {"large_model_min_b": 7.0}})
    assert len(roles) == 8


def test_advertisement_roles_follow_worker_and_shared_models(app_state):
    app_state.config.update({
        "swarm": {"worker_enabled": False,
                  "worker_models": ["llama3.1:8b", "qwen2.5:3b"]},
        "node_roles": {"large_model_min_b": 7.0,
                       "reasoner_models": ["qwen2.5:3b"]},
    })
    app_state.start_p2p()
    assert _build_advertisement(app_state)["roles"] == []
    app_state.config.update({"swarm": {"worker_enabled": True}})
    roles = _build_advertisement(app_state)["roles"]
    assert [entry["role"] for entry in roles] == ["large_model", "reasoner"]
    assert {entry["model"] for entry in roles} == {"llama3.1:8b", "qwen2.5:3b"}
    # A reasoning model that is not shared is never advertised.
    app_state.config.update({"swarm": {"worker_models": ["llama3.1:8b"]}})
    roles = _build_advertisement(app_state)["roles"]
    assert [entry["role"] for entry in roles] == ["large_model"]


def test_local_pool_advertises_its_models_roles(app_state):
    app_state.config.update({
        "swarm": {"worker_enabled": False},
        "model": {"multi_model": True,
                  "local_models": ["llama3.1:8b", "qwen2.5:7b"]},
        "node_roles": {"large_model_min_b": 7.0,
                       "reasoner_models": ["qwen2.5:7b"]},
    })
    app_state.start_p2p()
    pool = app_state._local_pool()
    assert pool is not None
    roles = pool.peer.advertisement["roles"]
    assert {"role": "large_model", "model": "llama3.1:8b", "params_b": 8.0} in roles
    assert {"role": "large_model", "model": "qwen2.5:7b", "params_b": 7.0} in roles
    assert {"role": "reasoner", "model": "qwen2.5:7b", "think": True} in roles


# -- worker execution ----------------------------------------------------------------

class ThinkBackend:
    name = "fake"
    accepts_think = True

    def __init__(self):
        self.calls: list[dict] = []

    def available(self):
        return True

    def list_models(self):
        return ["llama3.1:8b", "qwen2.5:7b"]

    def stream_chat(self, messages, *, model, max_tokens=1024, temperature=0.2,
                    on_delta=None, interrupt=None, system=None, **kw):
        self.calls.append({"model": model, **kw})
        return GenerationResult(text="thoughtful answer", model=model,
                                completion_tokens=3, total_ms=5)


def test_reasoner_think_reaches_a_supporting_backend(nodes):
    state, _ = nodes("R", worker=True,
                     models=["llama3.1:8b", "qwen2.5:7b"],
                     roles_cfg={"large_model_min_b": 7.0,
                                "reasoner_models": ["qwen2.5:7b"]})
    backend = ThinkBackend()
    state.backends.resolve = lambda cfg=None: backend  # type: ignore[method-assign]
    reply = asyncio.run(state.worker.handle(
        "peer", task_message(role="reasoner", think=True)))
    assert reply["type"] == "result", reply
    # The role's model wins over the largest shared model, and think reaches
    # a backend that accepts it.
    assert backend.calls and backend.calls[0]["model"] == "qwen2.5:7b"
    assert backend.calls[0]["think"] is True
    assert reply["profile"]["think"] is True


def test_think_is_not_claimed_when_the_backend_cannot_take_it(nodes):
    state, _ = nodes("R2", worker=True, models=["qwen2.5:7b"],
                     roles_cfg={"large_model_min_b": 7.0,
                                "reasoner_models": ["qwen2.5:7b"]})
    # FakeBackend accepts **kw but does not advertise accepts_think.
    reply = asyncio.run(state.worker.handle(
        "peer", task_message(role="reasoner", think=True)))
    assert reply["type"] == "result", reply
    assert "think" not in reply["profile"]


def test_a_role_it_does_not_advertise_is_refused_before_anything_runs(nodes):
    state, fake = nodes("N", worker=True, models=["llama3.1:8b"],
                        roles_cfg={"large_model_min_b": 7.0})
    reply = asyncio.run(state.worker.handle(
        "peer", task_message(role="search")))
    assert reply["type"] == "error"
    assert reply["code"] == E_ROLE_UNAVAILABLE
    assert fake.calls == []
    assert state.worker.status()["tasks_served_today"] == 0


# -- placement -----------------------------------------------------------------------

class _Bus:
    def publish(self, *a, **k):
        pass


def _peer(node_id, models, roles=None):
    return SimpleNamespace(
        node_id=node_id, tasks_inflight=0, rtt_ms=10.0,
        advertisement={"models": [{"family": f, "version": v} for f, v in models],
                       "roles": list(roles or []),
                       "policy": {"max_concurrent": 1}})


ROLE = [{"role": "large_model", "model": "llama3.1:8b", "params_b": 8}]


class _Nodes:
    def __init__(self, peers, replies):
        self.peers = {peer.node_id: peer for peer in peers}
        self.replies = replies
        self.sent = []

    def available_workers(self, kind="generate"):
        return list(self.peers.values())

    async def dispatch_async(self, node_id, message, timeout_s):
        self.sent.append((node_id, message))
        reply = self.replies[node_id]
        if isinstance(reply, Exception):
            raise reply
        return {"type": "result", "attempt_id": message["attempt_id"],
                "text": reply, "profile": {}, "telemetry": {}}


def _scheduler(peers, replies, *, role_stats=None, k_min=1, k_max=1):
    return Scheduler(_Nodes(peers, replies), _Bus(), "r", k_min=k_min,
                     k_max=k_max, max_concurrency=4, timeout_s=5,
                     hedge_fallback_s=5, latency=LatencyStats(),
                     min_params_b=1.5, role_stats=role_stats)


def _fake_verify(monkeypatch):
    import swarmbly_app.engine.scheduler as sched
    monkeypatch.setattr(sched, "verify_result", lambda *a: "")


def test_role_placement_ignores_workers_without_the_role(monkeypatch):
    _fake_verify(monkeypatch)
    role_peer = _peer("role", [("llama", "llama3.1:8b")], ROLE)
    plain = _peer("plain", [("qwen2", "qwen2.5:3b")])
    nodes = _Nodes([plain, role_peer], {"role": "role answer", "plain": "generic"})
    scheduler = Scheduler(nodes, _Bus(), "r", k_min=1, k_max=1,
                          max_concurrency=2, timeout_s=5, hedge_fallback_s=5,
                          latency=LatencyStats(), min_params_b=1.5)
    replicas = asyncio.run(scheduler.run_task(
        "t0", build_packet, 100, role="large_model"))
    assert [replica.node_id for replica in replicas] == ["role"]
    assert nodes.sent[0][0] == "role"
    assert nodes.sent[0][1]["constraints"]["role"] == "large_model"
    assert scheduler.attempts[0].role == "large_model"
    assert scheduler.attempts[0].role_fallback is False
    outcomes = scheduler.role_stats.snapshot()
    assert outcomes and outcomes[0]["role"] == "large_model"
    assert outcomes[0]["ok"] == 1 and outcomes[0]["failed"] == 0


def test_no_role_worker_falls_back_generically_and_says_so(monkeypatch):
    _fake_verify(monkeypatch)
    plain = _peer("plain", [("qwen2", "qwen2.5:3b")])
    nodes = _Nodes([plain], {"plain": "generic"})
    scheduler = Scheduler(nodes, _Bus(), "r", k_min=1, k_max=1,
                          max_concurrency=2, timeout_s=5, hedge_fallback_s=5,
                          latency=LatencyStats(), min_params_b=1.5)
    replicas = asyncio.run(scheduler.run_task(
        "t0", build_packet, 100, role="reasoner"))
    assert replicas and replicas[0].node_id == "plain"
    # No role claim is sent to a worker that never advertised it.
    assert "role" not in nodes.sent[0][1]["constraints"]
    attempt = scheduler.attempts[0]
    assert attempt.role == "reasoner" and attempt.role_fallback is True
    assert "role reasoner unavailable" in attempt.note
    assert attempt.to_dict()["role_fallback"] is True


def test_search_without_its_executor_fails_honestly(monkeypatch):
    _fake_verify(monkeypatch)
    plain = _peer("plain", [("qwen2", "qwen2.5:3b")])
    scheduler = _scheduler([plain], {"plain": "generic"})
    with pytest.raises(TaskFailed, match="role 'search' unavailable"):
        asyncio.run(scheduler.run_task("t0", build_packet, 100, role="search"))


def test_a_role_failure_deprioritises_that_node(monkeypatch):
    _fake_verify(monkeypatch)
    from swarmbly_app.p2p.node import PeerError
    first = _peer("a", [("llama", "llama3.1:8b")], ROLE)
    second = _peer("b", [("llama", "llama3.1:8b")], ROLE)
    stats = RoleStats()
    nodes = _Nodes([first, second],
                   {"a": PeerError("E_EXECUTION", "simulated role failure"),
                    "b": "role answer"})
    scheduler = Scheduler(nodes, _Bus(), "r", k_min=1, k_max=2,
                          max_concurrency=2, timeout_s=5, hedge_fallback_s=5,
                          latency=LatencyStats(), min_params_b=1.5,
                          role_stats=stats)
    replicas = asyncio.run(scheduler.run_task(
        "t0", build_packet, 100, role="large_model"))
    assert replicas[0].node_id == "b"
    assert stats.recently_failed("a", "large_model")
    assert not stats.recently_failed("b", "large_model")
    assert stats.snapshot()[0]["role"] == "large_model"


def test_no_role_packets_are_unchanged(monkeypatch):
    _fake_verify(monkeypatch)
    plain = _peer("plain", [("qwen2", "qwen2.5:3b")],
                  [{"role": "corpus", "name": "docs", "size": "S"}])
    nodes = _Nodes([plain], {"plain": "generic"})
    scheduler = Scheduler(nodes, _Bus(), "r", k_min=1, k_max=1,
                          max_concurrency=4, timeout_s=5, hedge_fallback_s=5,
                          latency=LatencyStats(), min_params_b=1.5)
    asyncio.run(scheduler.run_task("t0", build_packet, 100))
    assert "role" not in nodes.sent[0][1]["constraints"]
    assert "think" not in nodes.sent[0][1]["constraints"]
    assert scheduler.attempts[0].role == ""
    assert "role_fallback" not in scheduler.attempts[0].to_dict()


# -- real nodes in a shared circle ---------------------------------------------------

def test_role_task_runs_on_a_real_circle_worker_and_reannounces(nodes):
    owner, _ = nodes("owner", worker=False, models=["owner-model:1b"],
                     mode="circle")
    role_worker, fake_role = nodes(
        "role", worker=True, models=["llama3.1:8b"], mode="circle",
        roles_cfg={"large_model_min_b": 7.0})
    plain_worker, fake_plain = nodes(
        "plain", worker=True, models=["qwen2.5:3b"], mode="circle")
    circle = add_to_circle(owner, role_worker)
    add_to_circle(owner, plain_worker, circle)
    assert wait_for(lambda: "large_model" in {
        entry["role"] for entry in owner.nodes.peers[
            role_worker.identity.node_id].advertisement.get("roles", [])})

    directory = Directory(owner.nodes, None, remote_allowed=True)
    scheduler = Scheduler(directory, _Bus(), "r", k_min=1, k_max=1,
                          max_concurrency=2, timeout_s=8, hedge_fallback_s=4,
                          latency=LatencyStats(), min_params_b=1.5,
                          role_stats=owner.role_stats)
    replicas = asyncio.run(scheduler.run_task(
        "t0", build_packet, 100, role="large_model"))
    assert [replica.node_id for replica in replicas] == [role_worker.identity.node_id]
    assert fake_role.calls and fake_plain.calls == []
    assert fake_role.calls[0]["model"] == "llama3.1:8b"
    attempt = scheduler.attempts[0]
    assert attempt.role == "large_model"
    assert attempt.destination_class == egress.CIRCLE

    # A settings change re-announces through the signed advertisement_update.
    role_worker.config.update({"node_roles": {
        "large_model_min_b": 7.0,
        "reasoner_models": ["llama3.1:8b"]}})
    role_worker.on_config_changed()
    assert wait_for(lambda: "reasoner" in {
        entry["role"] for entry in owner.nodes.peers[
            role_worker.identity.node_id].advertisement.get("roles", [])})


def test_local_pool_runs_a_role_task_on_one_node(app_state):
    app_state.config.update({
        "swarm": {"worker_enabled": False},
        "model": {"multi_model": True,
                  "local_models": ["llama3.1:8b", "qwen2.5:3b"]},
        "node_roles": {"large_model_min_b": 7.0},
        "privacy": {"tier": "GLOBAL"},
    })
    fake = FakeBackend("1. apples\n2. bridges\n3. comets\n4. drums\n5. electrons")
    app_state.backends.resolve = lambda cfg=None: fake  # type: ignore[method-assign]
    app_state.start_p2p()
    result = app_state.get_orchestrator().run(
        TEST_PROMPT, mode="local", task_roles={"t0": "large_model"})
    assert result["routed"] == "distributed", result
    attempt = next(a for a in result["metadata"]["attempts"] if a["task"] == "t0")
    assert attempt["role"] == "large_model"
    assert "llama3.1:8b" in {call["model"] for call in fake.calls}
    assert result["metadata"]["role_fallbacks"] == []


TEST_PROMPT = (
    "Extract one key fact per item from the following list of five items: "
    "apples, bridges, comets, drums, electrons. List 5 bullet points, one per "
    "item, separately."
)


def test_a_plan_task_can_carry_a_role(nodes):
    worker, fake = nodes("RW", worker=True, models=["llama3.1:8b"],
                         roles_cfg={"large_model_min_b": 7.0})
    client, _ = nodes("RC", worker=False, models=["fake-model:1b"])
    peer = client.nodes.connect_manual("127.0.0.1", worker.nodes.listen_port,
                                       wait=True)
    assert peer is not None and wait_for(
        lambda: worker.identity.node_id in {w.node_id for w in
                                            client.nodes.available_workers()})
    result = client.get_orchestrator().run(
        TEST_PROMPT, mode="lan", task_roles={"t0": "large_model"})
    assert result["routed"] == "distributed", result
    attempts = result["metadata"]["attempts"]
    role_attempts = [a for a in attempts if a.get("role") == "large_model"]
    assert role_attempts
    assert all(not a.get("role_fallback") for a in role_attempts)
    assert any(call["model"] == "llama3.1:8b" for call in fake.calls)


def test_missing_role_worker_is_reported_in_metadata_and_stages(nodes):
    numbered = "1. apples\n2. bridges\n3. comets\n4. drums\n5. electrons"
    worker, _ = nodes("GW", worker=True, models=["qwen2.5:3b"], reply=numbered)
    client, _ = nodes("GC", worker=False, models=["fake-model:1b"], reply=numbered)
    assert client.nodes.connect_manual("127.0.0.1", worker.nodes.listen_port,
                                       wait=True) is not None
    assert wait_for(lambda: client.nodes.available_workers())
    result = client.get_orchestrator().run(
        TEST_PROMPT, mode="lan", task_roles={"t0": "reasoner"})
    assert result["routed"] == "distributed", result
    fallbacks = result["metadata"]["role_fallbacks"]
    assert any(item["task"] == "t0" and item["role"] == "reasoner"
               for item in fallbacks)
    dispatching = next(stage for stage in result["stages"]
                       if stage["stage"] == "DISPATCHING")
    assert dispatching["role_fallbacks"] == fallbacks
    role_attempt = next(a for a in result["metadata"]["attempts"]
                        if a["task"] == "t0")
    assert role_attempt["role"] == "reasoner"
    assert role_attempt["role_fallback"] is True


def test_receipt_entry_names_the_requested_role(app_state):
    request = ActiveRequest(request_id="r", conversation_id="c", message_id="m")
    request.ledger = egress.Ledger()
    meta: dict = {}
    app_state.chat._attach_receipt(
        request, meta, "answer",
        {"n_tasks": 1, "attempts": [{
            "task": "t0", "node": "peer-node", "destination_class": egress.CIRCLE,
            "circle_id": "c1", "circle_name": "Nodos", "member_name": "worker",
            "bytes_out": 42, "passages": 0, "role": "reasoner"}]})
    entry = meta["receipt"]["envios"][0]
    assert entry["role"] == "reasoner"
    assert entry["circle_name"] == "Nodos"
