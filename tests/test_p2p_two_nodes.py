"""Multi-node integration tests (real TLS, real handshake, real mDNS).

Several AppStates on one machine, each with its own data directory, identity
and P2P port. Workers run a fake backend (no model download); everything else
— discovery, channel-bound handshake, SPEC v0.2 packets, signatures,
scheduling, consensus, assembly and metadata — is the production code path.
"""

from __future__ import annotations

import itertools
import time

import pytest

from swarmbly_app.state import AppState

from conftest import FakeBackend

TEST_PROMPT = (
    "Extract one key fact per item from the following list of five items: "
    "apples, bridges, comets, drums, electrons. List 5 bullet points, one per "
    "item, separately."
)
_ports = itertools.count(19800)


def make_node(tmp_path, name, *, worker=False, model="fake-model:1b",
              lan=False, reply="fragment answer with key facts.", delay=0.0,
              fail=False, concurrent=2, extra=None):
    state = AppState(str(tmp_path / name))
    cfg = {"swarm": {"p2p_port": next(_ports), "lan_enabled": lan,
                     "worker_enabled": worker, "worker_max_concurrent": concurrent,
                     "timeout_ms": 8000, "hedge_fallback_ms": 3000},
           "privacy": {"tier": "GLOBAL"},
           "model": {"model_name": model}}
    for section, values in (extra or {}).items():
        cfg.setdefault(section, {}).update(values)
    state.config.update(cfg)
    fake = FakeBackend(reply, delay=delay, fail=fail)
    state.backends.resolve = lambda cfg=None: fake  # type: ignore[method-assign]
    state.start_p2p()
    return state, fake


def wait_for(predicate, timeout=10.0, step=0.1):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return False


def connect(client, worker):
    client.nodes.connect_manual("127.0.0.1", worker.nodes.listen_port, wait=True)
    assert wait_for(lambda: worker.identity.node_id in
                    {w.node_id for w in client.nodes.available_workers()}), \
        "worker not available after handshake"


def send(state, mode="lan"):
    conv = state.chat.create_conversation(mode=mode)
    state.chat.send(conv["id"], TEST_PROMPT, mode=mode, run_async=False)
    return state.chat.get_messages(conv["id"])[-1]


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


class TestDiscoveryWithoutIPs:
    def test_mdns_discovery_and_handshake(self, nodes):
        """The v0.1 acceptance path: no IP is typed anywhere."""
        worker, _ = nodes("W", worker=True, lan=True)
        client, _ = nodes("C", lan=True)
        assert wait_for(lambda: client.nodes.available_workers(), timeout=20), \
            client.nodes.status()
        peer = client.nodes.available_workers()[0]
        assert peer.node_id == worker.identity.node_id
        assert peer.authenticated
        status = client.nodes.status()
        assert status["discovery"]["announcing"] and status["discovery"]["browsing"]
        # never connected to itself, exactly one session per pair
        assert client.identity.node_id not in client.nodes.peers
        assert wait_for(lambda: len(worker.nodes.peers) == 1)

    def test_discovery_toggles_at_runtime(self, nodes):
        state, _ = nodes("T", lan=False)
        assert state.nodes.status()["discovery"]["enabled"] is False
        state.config.update({"swarm": {"lan_enabled": True}})
        state.on_config_changed()
        assert state.nodes.status()["discovery"]["announcing"] is True
        state.config.update({"swarm": {"lan_enabled": False}})
        state.on_config_changed()
        assert state.nodes.status()["discovery"]["enabled"] is False


    def test_long_or_accented_computer_name_still_announces(self, nodes, monkeypatch):
        """Regression: macOS CI runners (and some managed Macs) have names
        longer than a DNS label allows; zeroconf then refused to announce."""
        import socket as _socket
        monkeypatch.setattr(_socket, "gethostname", lambda: (
            "Sebastián's MacBook Pro-1760258312345-runner-with-a-very-long-name.local"))
        worker, _ = nodes("LW", worker=True, lan=True)
        client, _ = nodes("LC", lan=True)
        assert worker.nodes.status()["discovery"]["announcing"] is True, \
            worker.nodes.status()["discovery"]
        assert wait_for(lambda: client.nodes.available_workers(), timeout=20)


class TestMdnsHostLabel:
    def test_label_is_valid_dns(self):
        from swarmbly_app.p2p.discovery import mdns_host_label
        cases = ["Sebastián's MacBook Pro.local", "x" * 200, "", "...",
                 "Mac-1760258312345-runner-very-long-hostname-from-ci-abcdefghij.local",
                 "日本語のマック", "host_with_underscores"]
        for name in cases:
            label = mdns_host_label(name, "Ab_c-D9xyz")
            assert 1 <= len(label.encode()) <= 63, (name, label)
            assert all(c.isascii() and (c.isalnum() or c == "-") for c in label), label
            assert not label.startswith("-") and not label.endswith("-")
        assert mdns_host_label("Sebastián's MacBook Pro", "Ab_c-D9").startswith("sebastian-s-macbook-pro-")


class TestDistributed:
    def test_end_to_end(self, nodes):
        worker, fake_w = nodes("W", worker=True)
        client, _ = nodes("C")
        connect(client, worker)
        final = send(client)
        assert final["meta"]["status"] == "done", final["meta"]
        assert final["meta"]["executed"] == "distributed"
        swarm = final["meta"]["swarm"]
        assert swarm["n_tasks"] >= 2 and swarm["n_levels"] >= 1
        for key in ("rho_achieved", "rho_floor", "rho_target", "rho_reachable",
                    "coherence", "routing", "consensus", "coverage", "seams"):
            assert key in swarm  # SPEC §19
        assert swarm["verification"]["commitments_checked"] == 0
        assert swarm["verification"]["commitment"] == "not_available"
        assert swarm["consensus"] is None
        assert swarm["consensus_waived_reason"] == "k_min=1_requested"
        assert swarm["nodes"] and swarm["nodes"][0]["role"] == "worker"
        stages = {s["stage"]: s["status"] for s in final["stages"]}
        assert stages["VERIFICATION"] == "partial"   # signatures yes, Layer 1 no
        assert stages["CONSENSUS / ALIGNMENT"] == "skipped"
        assert stages["FINAL RESPONSE"] == "completed"
        assert worker.worker.status()["tasks_served_today"] >= 2

    def test_workers_never_see_session_or_whole_request(self, nodes):
        worker, fake_w = nodes("W", worker=True)
        client, _ = nodes("C")
        connect(client, worker)
        send(client)
        from swarmbly_v0 import planner
        from swarmbly_app.engine.admission import admit
        prompts = [c["messages"][-1]["content"] for c in fake_w.calls]
        assert prompts
        session = planner.global_contract(
            admit(TEST_PROMPT, n_max=4, n_workers=1).prompt).session_id
        for prompt in prompts:
            assert "session" not in prompt.lower()
            assert session not in prompt
            assert TEST_PROMPT not in prompt
            # each worker sees the operation and only its own items
            assert sum(item in prompt for item in
                       ("apples", "bridges", "comets", "drums", "electrons")) < 5

    def test_parallel_not_sequential(self, nodes):
        worker, _ = nodes("W", worker=True, delay=0.6, concurrent=4)
        client, _ = nodes("C", extra={"swarm": {"max_concurrency": 4,
                                                "min_items_per_fragment": 1}})
        connect(client, worker)
        started = time.time()
        final = send(client)
        elapsed = time.time() - started
        n = final["meta"]["swarm"]["n_tasks"]
        assert n >= 3
        # sequential dispatch would take ≥ n × 0.6 s
        assert elapsed < n * 0.6 - 0.4, f"{elapsed:.2f}s for {n} tasks"

    def test_family_diverse_consensus(self, nodes):
        w1, _ = nodes("W1", worker=True, model="llama3.2:3b",
                      reply="Apples are fruit. Bridges span rivers.")
        w2, _ = nodes("W2", worker=True, model="qwen2.5:3b",
                      reply="Apples are fruit. Bridges cross water.")
        client, _ = nodes("C", extra={"swarm": {"k_min": 2, "k_max": 2}})
        connect(client, w1)
        connect(client, w2)
        final = send(client)
        swarm = final["meta"]["swarm"]
        assert final["meta"]["status"] == "done", final["meta"]
        assert swarm["consensus"] is not None
        assert set(swarm["consensus"]["families"]) == {"llama3.2", "qwen2.5"}
        assert "not accuracy" in swarm["consensus"]["interpretation"]
        per_task_families = [set(b["families"]) for b in
                             swarm["consensus"]["per_task"].values()]
        assert all(len(f) == 2 for f in per_task_families)  # replicas never share a family

    def test_failed_worker_is_retried_elsewhere(self, nodes):
        bad, _ = nodes("BAD", worker=True, model="llama3.2:3b", fail=True)
        good, _ = nodes("GOOD", worker=True, model="qwen2.5:3b")
        client, _ = nodes("C", extra={"swarm": {"k_min": 1, "k_max": 2}})
        connect(client, bad)
        connect(client, good)
        final = send(client)
        assert final["meta"]["status"] == "done", final["meta"]
        attempts = final["meta"]["swarm"]["attempts"]
        assert any(a["status"] == "failed" for a in attempts)
        assert final["meta"]["swarm"]["retries"] >= 1

    def test_privacy_local_never_egresses(self, nodes):
        worker, fake_w = nodes("W", worker=True)
        client, _ = nodes("C")
        connect(client, worker)
        client.config.update({"privacy": {"tier": "LOCAL"}})
        client.on_config_changed()
        final = send(client)
        assert final["meta"]["status"] == "done"
        assert final["meta"]["executed"] == "local"
        assert fake_w.calls == []
        stages = {s["stage"]: s["status"] for s in final["stages"]}
        assert stages["DISPATCHING"] == "skipped"
        assert stages["VERIFICATION"] == "skipped"

    def test_sensitive_content_stays_local(self, nodes):
        worker, fake_w = nodes("W", worker=True)
        client, _ = nodes("C")
        connect(client, worker)
        conv = client.chat.create_conversation(mode="lan")
        client.chat.send(conv["id"], "Summarize the following:\n1. my diagnosis\n"
                         "2. my medical history\n3. my salary", mode="lan",
                         run_async=False)
        final = client.chat.get_messages(conv["id"])[-1]
        assert final["meta"]["executed"] == "local"
        assert fake_w.calls == []

    def test_no_workers_answers_locally_with_reason(self, nodes):
        client, fake = nodes("SOLO")
        final = send(client)
        assert final["meta"]["status"] == "done"
        assert final["meta"]["executed"] == "local"
        assert "no connected worker" in final["meta"]["local_reason"]

    def test_unstructured_prose_is_not_fragmented(self, nodes):
        worker, fake_w = nodes("W", worker=True)
        client, _ = nodes("C")
        connect(client, worker)
        conv = client.chat.create_conversation(mode="lan")
        client.chat.send(conv["id"], "Write a reflective essay about how rivers "
                         "shape the cities that grow around them, and why.",
                         mode="lan", run_async=False)
        final = client.chat.get_messages(conv["id"])[-1]
        assert final["meta"]["executed"] == "local"
        assert fake_w.calls == []


class TestConsensusReuse:
    def test_upstream_consensus_resolves_replicas(self, app_state):
        from swarmbly_app.engine.orchestrator import Orchestrator
        from swarmbly_app.engine.scheduler import Replica
        from swarmbly_v0 import HashEmbedder, planner
        orch = Orchestrator(app_state.nodes, app_state.bus, None, app_state.config.all)
        contract = planner.global_contract("List facts.")
        out = orch._resolve("t0", [
            Replica("alpha beta gamma.", "n1", "llama", "llama3.2:3b", 10),
            Replica("alpha beta gamma.", "n2", "qwen2", "qwen2.5:3b", 12)],
            contract, HashEmbedder())
        assert out["text"].strip()
        assert out["consensus"]["k"] == 2
        assert out["consensus"]["units"][0]["label"] in ("HIGH", "MEDIUM", "LOW")


class TestLocalMultiModel:
    def _multi(self, extra=None):
        cfg = {"model": {"multi_model": True,
                         "local_models": ["llama3.2:3b", "qwen2.5:3b"],
                         "local_parallel": 2}}
        for k, v in (extra or {}).items():
            cfg.setdefault(k, {}).update(v)
        return cfg

    def test_local_tier_uses_local_models_never_the_network(self, nodes):
        worker, fake_w = nodes("W", worker=True)
        client, fake_c = nodes("C", extra=self._multi({"privacy": {"tier": "LOCAL"}}))
        connect(client, worker)
        final = send(client)
        swarm = final["meta"]["swarm"]
        assert final["meta"]["executed"] == "distributed", final["meta"]
        assert fake_w.calls == []                      # nothing left the device
        assert {n["role"] for n in swarm["nodes"]} == {"local model"}
        assert {c["model"] for c in fake_c.calls} >= {"llama3.2:3b", "qwen2.5:3b"}
        assert swarm["routing"]["remote_allowed"] is False

    def test_prose_with_k2_gets_whole_request_consensus_locally(self, nodes):
        client, fake_c = nodes("C", extra=self._multi({"swarm": {"k_min": 2,
                                                                  "k_max": 2}}))
        conv = client.chat.create_conversation(mode="local")
        client.chat.send(conv["id"], "Write a short reflection on rivers and cities.",
                         mode="local", run_async=False)
        final = client.chat.get_messages(conv["id"])[-1]
        swarm = final["meta"]["swarm"]
        assert final["meta"]["executed"] == "distributed", final["meta"]
        assert swarm["router"]["whole_request_replicas"] is True
        assert swarm["n_tasks"] == 1
        assert set(swarm["consensus"]["families"]) == {"llama3.2", "qwen2.5"}

    def test_prose_with_k1_streams_locally(self, nodes):
        client, _ = nodes("C", extra=self._multi())
        conv = client.chat.create_conversation(mode="local")
        client.chat.send(conv["id"], "Write a short reflection on rivers and cities.",
                         mode="local", run_async=False)
        final = client.chat.get_messages(conv["id"])[-1]
        assert final["meta"]["executed"] == "local"

    def test_lan_mode_combines_remote_workers_and_local_pool(self, nodes):
        worker, fake_w = nodes("W", worker=True, model="phi3.5:3.8b")
        client, fake_c = nodes("C", extra=self._multi({"swarm": {"k_min": 2,
                                                                  "k_max": 3}}))
        connect(client, worker)
        final = send(client)
        roles = {n["role"] for n in final["meta"]["swarm"]["nodes"]}
        assert roles == {"local model", "worker"}, final["meta"]["swarm"]["nodes"]
        assert fake_w.calls
