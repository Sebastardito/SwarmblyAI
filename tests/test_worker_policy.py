"""Worker policy tests: every gate refuses in code, not in the UI."""

from __future__ import annotations

import asyncio

import pytest

from swarmbly_app.p2p.messages import packet, WIRE_VERSION
from swarmbly_app.p2p.worker import WorkerService, render_packet_prompt


def make_worker(app_state, fake_backend):
    if not app_state.config.get("model.model_name"):
        app_state.config.update({"model": {"model_name": "fake-model:1b"}})
    return WorkerService(app_state.config, app_state.db, app_state.bus,
                         app_state.identity_manager, app_state.lce,
                         lambda: fake_backend)


def task_message(**overrides):
    message = packet(
        attempt_id="task0:0",
        contract={"v": WIRE_VERSION, "objective": "o", "audience": "a",
                  "register": "neutral", "format": "prose", "target_len": 200,
                  "lexicon": {}, "entities": [], "style_seed": "",
                  "budget": {"max_out_tokens": 300}},
        predecessors=[],
        task={"instruction": "answer this", "kind": "generate",
              "expects": {"format": "prose", "max_tokens": 300}},
        deadline_ms=60000,  # a duration (SPEC §8 example), not an epoch
        lane="PUBLIC", tier="GLOBAL")
    message.update(overrides)
    return message


class TestWorkerPolicy:
    def test_epoch_deadline_rejected_as_schema_error(self, app_state, fake_chat):
        """Absolute timestamps break across unsynchronised clocks."""
        app_state.config.update({"swarm": {"worker_enabled": True}})
        _, fake = fake_chat
        worker = make_worker(app_state, fake)
        reply = asyncio.run(worker.handle(
            "peer", task_message(deadline_ms=int(__import__("time").time() * 1000))))
        assert reply["code"] == "E_SCHEMA"

    def test_disabled_worker_advertises_no_kinds(self, app_state, fake_chat):
        _, fake = fake_chat
        worker = make_worker(app_state, fake)
        assert worker.policy()["kinds"] == []
        app_state.config.update({"swarm": {"worker_enabled": True}})
        assert "generate" in worker.policy()["kinds"]

    def test_model_family_hint_selects_shared_model(self, app_state, fake_chat):
        app_state.config.update({"swarm": {"worker_enabled": True,
                                           "worker_models": ["llama3.2:3b", "qwen2.5:3b"]}})
        _, fake = fake_chat
        worker = make_worker(app_state, fake)
        reply = asyncio.run(worker.handle("peer", task_message(
            constraints={"model_family": "qwen2.5"})))
        assert reply["type"] == "result"
        assert reply["profile"]["model_version"] == "qwen2.5:3b"
        assert fake.calls[-1]["model"] == "qwen2.5:3b"

    def test_paused_worker_refuses(self, app_state, fake_chat):
        app_state.config.update({"swarm": {"worker_enabled": True, "worker_paused": True}})
        _, fake = fake_chat
        worker = make_worker(app_state, fake)
        reply = asyncio.run(worker.handle("peer", task_message()))
        assert reply["code"] == "E_POLICY"

    def test_disabled_worker_refuses(self, app_state, fake_chat):
        _, fake = fake_chat
        worker = make_worker(app_state, fake)
        reply = asyncio.run(worker.handle("peer", task_message()))
        assert reply["type"] == "error"
        assert reply["code"] == "E_POLICY"

    def test_sensitive_lane_refuses(self, app_state, fake_chat):
        app_state.config.update({"swarm": {"worker_enabled": True}})
        _, fake = fake_chat
        worker = make_worker(app_state, fake)
        reply = asyncio.run(worker.handle(
            "peer", task_message(lane="SENSITIVE")))
        assert reply["code"] == "E_LANE_VIOLATION"

    def test_trusted_tier_refuses_without_mtls(self, app_state, fake_chat):
        app_state.config.update({"swarm": {"worker_enabled": True}})
        _, fake = fake_chat
        worker = make_worker(app_state, fake)
        reply = asyncio.run(worker.handle(
            "peer", task_message(tier="TRUSTED", swarm_id="s1")))
        assert reply["code"] == "E_MTLS_REQUIRED"

    def test_budget_exceeded(self, app_state, fake_chat):
        app_state.config.update({"swarm": {"worker_enabled": True,
                                           "worker_max_tokens_per_task": 100}})
        _, fake = fake_chat
        worker = make_worker(app_state, fake)
        reply = asyncio.run(worker.handle("peer", task_message()))
        assert reply["code"] == "E_BUDGET_EXCEEDED"

    def test_unsupported_kind(self, app_state, fake_chat):
        app_state.config.update({"swarm": {"worker_enabled": True}})
        _, fake = fake_chat
        worker = make_worker(app_state, fake)
        message = task_message()
        message["task"]["kind"] = "train"  # never served
        reply = asyncio.run(worker.handle("peer", message))
        assert reply["code"] == "E_KIND_UNSUPPORTED"

    def test_enabled_worker_serves_and_signs(self, app_state, fake_chat):
        app_state.config.update({"swarm": {"worker_enabled": True,
                                           "worker_max_tokens_per_task": 500},
                                 "model": {"model_name": "fake-model:1b"}})
        _, fake = fake_chat
        worker = make_worker(app_state, fake)
        reply = asyncio.run(worker.handle("peer", task_message()))
        assert reply["type"] == "result"
        assert reply["commitment"] is None  # honestly unavailable
        assert reply["sig"]
        from swarmbly_app.p2p.messages import verify_signed
        # the result is signed by THIS node, not the peer
        ident = app_state.identity_manager.load_or_create()
        assert verify_signed(ident.node_id, reply)

    def test_prompt_render_no_session_id(self):
        message = task_message()
        prompt = render_packet_prompt(message)
        assert "[GLOBAL CONTRACT]" in prompt
        assert "[TASK" in prompt
        assert "session_id" not in prompt
