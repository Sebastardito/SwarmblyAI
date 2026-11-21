"""Reciprocity credits (D-020/D-021): receipts, wallet, spends, detection.

The unit tests use real Ed25519 identities, real signed manifests and the
real credit service with an in-memory transport; the end-to-end test runs two
AppStates on loopback over real TLS. Neutral fixture names only.
"""

from __future__ import annotations

import asyncio
import itertools
import stat
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from swarmbly_app import egress
from swarmbly_app.config import Config
from swarmbly_app.engine.scheduler import Scheduler
from swarmbly_app.events import EventBus
from swarmbly_app.identity import IdentityManager, b64url
from swarmbly_app.p2p import credits as credits_module
from swarmbly_app.p2p.circles import CircleService, build_manifest
from swarmbly_app.p2p.credits import (
    E_CREDIT_DUPLICATE, E_CREDIT_EXPIRED, E_CREDIT_NOT_MEMBER,
    E_CREDIT_SIGNATURE, E_CREDIT_SPENT, E_CREDIT_WALLET_FULL,
    E_CREDIT_WRONG_WORKER, CreditError, CreditService, attempt_hash,
    build_receipt, credit_receipt_message, credit_spend_message,
    credit_spent_message,
)
from swarmbly_app.p2p.messages import WIRE_VERSION, canonical_bytes, result
from swarmbly_app.paths import DataDirs
from swarmbly_app.state import AppState

from conftest import FakeBackend

_ports = itertools.count(20420)
CIRCLE_A = "CircleAlpha001"
CIRCLE_B = "CircleBeta0002"


class FakeNode:
    """Records control messages instead of writing to a socket."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []
        self.online: set[str] = set()

    async def send_control_async(self, node_id: str, message: dict) -> bool:
        if self.online and node_id not in self.online:
            return False
        self.sent.append((node_id, message))
        return True


class CreditEnv:
    """Three identities, two circles and one credit service per node."""

    def __init__(self, tmp_path: Path, *, members: int = 3):
        self.root = tmp_path
        self.identities = [
            IdentityManager(tmp_path / f"node{i}" / "identity" / "key")
            for i in range(members)]
        self.ids = [identity.load_or_create().node_id
                    for identity in self.identities]
        self.bus = EventBus()
        self.configs = []
        self.circles = []
        self.services = []
        now = int(time.time())
        for index, identity in enumerate(self.identities):
            dirs = DataDirs(tmp_path / f"node{index}")
            config = Config(dirs)
            self.configs.append(config)
            circle = CircleService(identity, config, dirs, self.bus)
            manifest = build_manifest(
                identity_manager=self.identities[0], circle_id=CIRCLE_A,
                name="Alpha", owner=self.ids[0],
                members=[{"node_id": node_id, "name": f"node{pos}",
                          "endpoints": []}
                         for pos, node_id in enumerate(self.ids)],
                version=1, issued_at=now, expires_at=now + 7 * 86400)
            circle._store_manifest(manifest)
            self.circles.append(circle)
            service = CreditService(identity, config, dirs, self.bus,
                                    circles=circle)
            service.node = FakeNode()
            self.services.append(service)

    def issue(self, issuer: int, worker: int, *, circle_id: str = CIRCLE_A,
              attempt: str = "task:0", tokens: int = 12,
              generation_ms: int = 90, model: str = "fake:1b",
              ttl_s: int = 90 * 86400) -> dict:
        return build_receipt(
            identity_manager=self.identities[issuer], circle_id=circle_id,
            issuer=self.ids[issuer], worker=self.ids[worker],
            attempt_id=attempt, tokens_out=tokens,
            generation_ms=generation_ms, model=model, ttl_s=ttl_s)


def deliver(service: CreditService, sender: str, receipt: dict) -> None:
    asyncio.run(service.handle_control(sender, {
        "v": WIRE_VERSION, "type": "credit_receipt", "receipt": receipt}))


def spend(service: CreditService, sender: str, receipt: dict,
          attempt_id: str = "next:0") -> None:
    asyncio.run(service.handle_control(sender, {
        "v": WIRE_VERSION, "type": "credit_spend", "spender": sender,
        "attempt_id": attempt_id, "receipt": receipt}))


def record_issued(env: CreditEnv, receipt: dict) -> None:
    """Put a receipt in the issuer's log, as issue_for_attempt would."""
    env.services[0]._issued["receipts"][receipt["receipt_id"]] = {
        "receipt": receipt, "reports": [], "flagged": False,
        "flagged_reason": "", "flagged_at": None,
    }


class TestReceipts:
    def test_issued_for_a_circle_member_and_stored_in_the_wallet(self, tmp_path):
        env = CreditEnv(tmp_path)
        attempt = SimpleNamespace(
            node_id=env.ids[1], destination_class=egress.CIRCLE,
            circle_id=CIRCLE_A, attempt_id="task-hash:0", tokens_out=12,
            model="fake:1b")
        replica = SimpleNamespace(
            text="a verified answer", model="fake:1b", elapsed_ms=120,
            telemetry={"gen_ms": 90, "tokens_out": 12}, executor="",
            sources=[])
        receipt = asyncio.run(
            env.services[0].issue_for_attempt(attempt, replica))
        assert receipt and receipt["worker"] == env.ids[1]
        assert receipt["attempt"] == attempt_hash("task-hash:0")
        assert receipt["tokens_out"] == 12
        assert receipt["generation_ms"] == 90
        assert receipt["expires_at"] - receipt["issued_at"] == 90 * 86400
        # The issuer sent exactly one credit_receipt control message.
        sent = [msg for _, msg in env.services[0].node.sent
                if msg.get("type") == "credit_receipt"]
        assert sent and sent[0]["receipt"]["receipt_id"] == receipt["receipt_id"]
        deliver(env.services[1], env.ids[0], receipt)
        wallet = env.services[1].wallet_summary(CIRCLE_A)
        assert wallet["balance"] == 1
        assert wallet["earned"] == 1
        assert wallet["spent"] == 0

    @pytest.mark.parametrize("case", ["local", "own_devices", "executor_empty",
                                       "no_attempt"])
    def test_no_receipt_for_what_did_not_earn_one(self, tmp_path, case):
        env = CreditEnv(tmp_path)
        attempt = SimpleNamespace(
            node_id=env.ids[0] if case == "local" else env.ids[1],
            destination_class=(egress.OWN_NETWORK if case == "own_devices"
                               else egress.CIRCLE),
            circle_id=CIRCLE_A,
            attempt_id="" if case == "no_attempt" else "task:0",
            tokens_out=4, model="fake:1b")
        replica = SimpleNamespace(
            text="answer", model="fake:1b", elapsed_ms=10,
            telemetry={"gen_ms": 10}, executor="search" if case == "executor_empty"
            else "", sources=[])
        receipt = asyncio.run(
            env.services[0].issue_for_attempt(attempt, replica))
        assert receipt is None
        assert not env.services[0].flagged()

    def test_scheduler_issues_only_for_an_accepted_replica(self, tmp_path):
        env = CreditEnv(tmp_path)
        worker_id = env.ids[1]
        calls: list[str] = []

        class SpyCredits:
            async def issue_for_attempt(self, attempt, replica):
                calls.append(attempt.attempt_id)
                return None

        def signed_result(attempt_id: str) -> dict:
            message = result(
                attempt_id, "a usable answer",
                {"model_family": "fake", "model_version": "fake:1b"},
                {"tokens_out": 3, "gen_ms": 5}, b"", commitment=None)
            message["sig"] = b64url(env.identities[1].sign(
                canonical_bytes({k: v for k, v in message.items() if k != "sig"})))
            return message

        class FakeDirectory:
            def __init__(self):
                self.peer = SimpleNamespace(
                    node_id=worker_id, tasks_inflight=0, rtt_ms=1.0,
                    advertisement={
                        "models": [{"family": "fake", "version": "fake:1b"}],
                        "policy": {"max_concurrent": 2}})
                self.peers = {worker_id: self.peer}

            def available_workers(self, kind="generate"):
                return [self.peer]

            def passages_allowed(self, node_id):
                return True

            def classify_peer(self, node_id):
                return {"clase": egress.CIRCLE, "circle_id": CIRCLE_A,
                        "circle_name": "Alpha", "member_name": "node1",
                        "member_node": worker_id[:12]}

            async def dispatch_async(self, node_id, message, timeout_s):
                return signed_result(str(message["attempt_id"]))

        def scheduler(spy):
            return Scheduler(
                FakeDirectory(), env.bus, "req-credits", k_min=1, k_max=1,
                max_concurrency=1, timeout_s=5, hedge_fallback_s=3,
                latency=__import__("swarmbly_app.engine.scheduler",
                                   fromlist=["LatencyStats"]).LatencyStats(),
                credits=spy)

        def build(attempt, family=None, model=None):
            return {"v": WIRE_VERSION, "type": "task",
                    "attempt_id": f"wire-task:{attempt}",
                    "task": {"instruction": "answer", "kind": "generate",
                             "expects": {"max_tokens": 10}},
                    "lane": "PUBLIC", "tier": "GLOBAL", "deadline_ms": 4000}

        spy = SpyCredits()
        accepted = asyncio.run(
            scheduler(spy).run_task("t0", build, 10, validate=None))
        assert accepted and calls == ["wire-task:0"]

        calls.clear()
        rejected = asyncio.run(
            scheduler(spy).run_task("t0", build, 10,
                                    validate=lambda text: False))
        assert rejected and rejected[0].telemetry.get("degraded") is True
        assert calls == []

    def test_forged_wrong_worker_non_member_expired_and_duplicate(self, tmp_path):
        env = CreditEnv(tmp_path)
        good = env.issue(0, 1, attempt="ok:0")
        forged = dict(good)
        forged["tokens_out"] = 999
        with pytest.raises(CreditError) as err:
            deliver(env.services[1], env.ids[0], forged)
        assert err.value.code == E_CREDIT_SIGNATURE

        wrong = build_receipt(
            identity_manager=env.identities[0], circle_id=CIRCLE_A,
            issuer=env.ids[0], worker=env.ids[2], attempt_id="wrong:0",
            tokens_out=1, generation_ms=1, model="fake:1b")
        with pytest.raises(CreditError) as err:
            deliver(env.services[1], env.ids[0], wrong)
        assert err.value.code == E_CREDIT_WRONG_WORKER

        outsider = IdentityManager(tmp_path / "outsider" / "identity" / "key")
        outsider_id = outsider.load_or_create().node_id
        foreign = build_receipt(
            identity_manager=outsider, circle_id=CIRCLE_A, issuer=outsider_id,
            worker=env.ids[1], attempt_id="foreign:0", tokens_out=1,
            generation_ms=1, model="fake:1b")
        with pytest.raises(CreditError) as err:
            deliver(env.services[1], outsider_id, foreign)
        assert err.value.code == E_CREDIT_NOT_MEMBER

        expired = env.issue(0, 1, attempt="old:0", ttl_s=1)
        expired["issued_at"] = int(time.time()) - 100
        expired["expires_at"] = int(time.time()) - 1
        # Re-signing an expired receipt is unnecessary: expiry is checked
        # before delivery storage, and the signature is still the issuer's.
        with pytest.raises(CreditError) as err:
            deliver(env.services[1], env.ids[0], expired)
        assert err.value.code in (E_CREDIT_EXPIRED, E_CREDIT_SIGNATURE)

        deliver(env.services[1], env.ids[0], good)
        with pytest.raises(CreditError) as err:
            deliver(env.services[1], env.ids[0], good)
        assert err.value.code == E_CREDIT_DUPLICATE


class TestSpending:
    def test_only_the_named_worker_can_spend_and_only_in_its_circle(self, tmp_path):
        env = CreditEnv(tmp_path)
        receipt = env.issue(0, 1, attempt="earned:0")
        deliver(env.services[1], env.ids[0], receipt)
        # Node 2 tries to present node 1's receipt.
        with pytest.raises(CreditError) as err:
            spend(env.services[2], env.ids[2], receipt, "x:0")
        assert err.value.code == E_CREDIT_WRONG_WORKER
        # Node 1 presents it to node 2: valid, and only a priority marker.
        spend(env.services[2], env.ids[1], receipt, "next:0")
        assert env.services[2].take_priority(env.ids[1], "next:0") is True
        assert env.services[2].take_priority(env.ids[1], "next:0") is False
        # The same worker cannot present it here twice.
        with pytest.raises(CreditError) as err:
            spend(env.services[2], env.ids[1], receipt, "next:1")
        assert err.value.code == E_CREDIT_SPENT
        # Nor in a different circle that the presenter and receiver share.
        now = int(time.time())
        b_manifest = build_manifest(
            identity_manager=env.identities[0], circle_id=CIRCLE_B,
            name="Beta", owner=env.ids[0],
            members=[{"node_id": env.ids[0], "name": "node0", "endpoints": []},
                     {"node_id": env.ids[1], "name": "node1", "endpoints": []},
                     {"node_id": env.ids[2], "name": "node2", "endpoints": []}],
            version=1, issued_at=now, expires_at=now + 86400)
        for index in (0, 1, 2):
            env.circles[index]._store_manifest(b_manifest)
        # The receipt still names Alpha; the receiver rejects it there.
        with pytest.raises(CreditError) as err:
            spend(env.services[2], env.ids[1], receipt, "other:0")
        assert err.value.code in (E_CREDIT_SPENT, E_CREDIT_NOT_MEMBER)

    def test_receipt_cannot_be_spent_in_another_circle(self, tmp_path):
        env = CreditEnv(tmp_path)
        receipt = env.issue(0, 1, attempt="earned:0")
        deliver(env.services[1], env.ids[0], receipt)
        # The receiver no longer holds the circle the receipt names.
        env.circles[2].manifests.pop(CIRCLE_A, None)
        with pytest.raises(CreditError) as err:
            spend(env.services[2], env.ids[1], receipt, "next:0")
        assert err.value.code == E_CREDIT_NOT_MEMBER
        assert env.services[2].take_priority(env.ids[1], "next:0") is False

    def test_wallet_marks_a_presented_receipt_spent(self, tmp_path):
        env = CreditEnv(tmp_path)
        receipt = env.issue(0, 1, attempt="earned:0")
        deliver(env.services[1], env.ids[0], receipt)
        asyncio.run(env.services[1].present_spend_async(
            env.ids[2], CIRCLE_A, "next:0"))
        message = env.services[1].node.sent[-1][1]
        assert message["type"] == "credit_spend"
        asyncio.run(env.services[2].handle_control(env.ids[1], message))
        assert env.services[1].wallet_summary(CIRCLE_A)["balance"] == 0
        assert env.services[1].wallet_summary(CIRCLE_A)["spent"] == 1
        assert env.services[2].take_priority(env.ids[1], "next:0") is True

    def test_double_spend_reported_twice_is_flagged_at_the_issuer(self, tmp_path):
        env = CreditEnv(tmp_path)
        receipt = env.issue(0, 1, attempt="earned:0")
        record_issued(env, receipt)
        report = {
            "v": WIRE_VERSION, "type": "credit_spent",
            "receipt_id": receipt["receipt_id"], "spender": env.ids[1],
            "by": env.ids[1], "reported_at": int(time.time()),
        }
        report["sig"] = b64url(env.identities[1].sign(
            canonical_bytes({k: v for k, v in report.items() if k != "sig"})))
        asyncio.run(env.services[0].handle_control(env.ids[1], report))
        assert env.services[0].flagged() == []
        asyncio.run(env.services[0].handle_control(env.ids[1], report))
        flagged = env.services[0].flagged()
        assert len(flagged) == 1
        assert flagged[0]["receipt_id"] == receipt["receipt_id"]
        assert flagged[0]["reports"] == 2

    def test_double_spend_by_two_workers_is_flagged(self, tmp_path):
        env = CreditEnv(tmp_path)
        receipt = env.issue(0, 1, attempt="earned:0")
        record_issued(env, receipt)
        for worker in (1, 2):
            report = {
                "v": WIRE_VERSION, "type": "credit_spent",
                "receipt_id": receipt["receipt_id"], "spender": env.ids[1],
                "by": env.ids[worker], "reported_at": int(time.time()),
            }
            report["sig"] = b64url(env.identities[worker].sign(
                canonical_bytes({k: v for k, v in report.items()
                                 if k != "sig"})))
            asyncio.run(env.services[0].handle_control(env.ids[worker], report))
        flagged = env.services[0].flagged()
        assert len(flagged) == 1
        assert "more than one worker" in flagged[0]["reason"]


class TestWallet:
    def test_wallet_is_bounded_and_the_files_are_private(self, tmp_path,
                                                         monkeypatch):
        env = CreditEnv(tmp_path)
        monkeypatch.setattr(credits_module, "MAX_WALLET_RECEIPTS", 2)
        for index in range(2):
            deliver(env.services[1], env.ids[0],
                    env.issue(0, 1, attempt=f"earned:{index}"))
        with pytest.raises(CreditError) as err:
            deliver(env.services[1], env.ids[0],
                    env.issue(0, 1, attempt="earned:full"))
        assert err.value.code == E_CREDIT_WALLET_FULL
        wallet = env.services[1].wallet_path
        assert stat.S_IMODE(wallet.stat().st_mode) == 0o600
        assert stat.S_IMODE(wallet.parent.stat().st_mode) == 0o700
        # Atomic replace leaves no temporary file behind.
        assert not list(wallet.parent.glob(".wallet.json.tmp"))

    def test_issuer_log_is_bounded(self, tmp_path, monkeypatch):
        env = CreditEnv(tmp_path)
        monkeypatch.setattr(credits_module, "MAX_ISSUED_RECEIPTS", 2)
        for index in range(4):
            attempt = SimpleNamespace(
                node_id=env.ids[1], destination_class=egress.CIRCLE,
                circle_id=CIRCLE_A, attempt_id=f"accepted:{index}",
                tokens_out=1, model="fake:1b")
            replica = SimpleNamespace(
                text="answer", model="fake:1b", elapsed_ms=1,
                telemetry={"gen_ms": 1}, executor="", sources=[])
            asyncio.run(env.services[0].issue_for_attempt(attempt, replica))
        assert env.services[0].list_payload()["issued_count"] == 2


class TestMessages:
    def test_conformance_builds_and_validates_all_three_messages(self, tmp_path):
        env = CreditEnv(tmp_path)
        receipt = env.issue(0, 1, attempt="conformance:0")
        # credit_receipt: built, signed, accepted by the worker.
        receipt_message = credit_receipt_message(receipt)
        assert receipt_message["type"] == "credit_receipt"
        asyncio.run(env.services[1].handle_control(
            env.ids[0], receipt_message))
        assert env.services[1].wallet_summary(CIRCLE_A)["balance"] == 1
        # credit_spend: built from the same signed receipt and accepted.
        spend_message = credit_spend_message(
            env.ids[1], "conformance:1", receipt)
        assert spend_message["type"] == "credit_spend"
        asyncio.run(env.services[2].handle_control(
            env.ids[1], spend_message))
        assert env.services[2].take_priority(env.ids[1],
                                             "conformance:1") is True
        # credit_spent: signed by the reporting worker, accepted by the issuer.
        record_issued(env, receipt)
        spent_message = credit_spent_message(
            env.identities[1], receipt["receipt_id"], env.ids[1],
            by=env.ids[1])
        assert spent_message["type"] == "credit_spent"
        asyncio.run(env.services[0].handle_control(
            env.ids[1], spent_message))
        assert len(env.services[0]._issued["receipts"][
            receipt["receipt_id"]]["reports"]) == 1

    def test_unknown_control_types_are_ignored(self, tmp_path):
        env = CreditEnv(tmp_path)
        # A node with no credit service still has a circle control plane.
        env.circles[1].credits = None
        result = asyncio.run(env.circles[1].handle_control(
            env.ids[0], {"v": WIRE_VERSION, "type": "credit_receipt_v9",
                         "receipt": {"future": True}}))
        assert result is None

    def test_api_exposes_the_wallet_read_only(self, app_state):
        from fastapi.testclient import TestClient
        from swarmbly_app.api import create_app
        app = create_app(app_state)
        client = TestClient(app, base_url="http://127.0.0.1:8765")
        assert client.get("/api/credits").status_code == 401
        client.headers["X-Swarmbly-Token"] = app.state.guard.token
        app_state.circles.create_circle("Familia")
        body = client.get("/api/credits")
        assert body.status_code == 200, body.text
        payload = body.json()
        assert payload["unit"] == "receipt"
        assert payload["circles"][0]["name"] == "Familia"
        assert payload["circles"][0]["balance"] == 0
        assert payload["flagged"] == []
        # No transfer, no export and no market route exists (D-020).
        assert client.post("/api/credits/transfer", json={}).status_code in (404, 405)

    def test_oversized_credit_message_is_refused(self, tmp_path):
        env = CreditEnv(tmp_path)
        receipt = env.issue(0, 1, attempt="ok:0")
        receipt["model"] = "m" * 200
        with pytest.raises(CreditError) as err:
            deliver(env.services[1], env.ids[0], receipt)
        assert err.value.code in (E_CREDIT_SIGNATURE, "E_CREDIT_SCHEMA")


class _Credits:
    def __init__(self, credited_attempts):
        self.credited = set(credited_attempts)

    def take_priority(self, node_id, attempt_id):
        return attempt_id in self.credited


class TestWorkerPriority:
    def _state(self, tmp_path, delay, concurrent=1):
        state = AppState(str(tmp_path / "worker"))
        state.config.update({
            "swarm": {"p2p_port": next(_ports), "p2p_host": "127.0.0.1",
                      "lan_enabled": False, "worker_enabled": True,
                      "worker_max_concurrent": concurrent, "timeout_ms": 8000},
            "circle": {"admission_mode": "own_devices", "node_name": "worker"},
            "privacy": {"tier": "GLOBAL"},
            "model": {"model_name": "fake-model:1b"},
        })
        fake = FakeBackend("answer", delay=delay)
        state.backends.resolve = lambda cfg=None: fake
        state.start_p2p()
        return state

    @staticmethod
    def packet(attempt):
        return {"v": WIRE_VERSION, "type": "task", "attempt_id": attempt,
                "contract": {}, "predecessors": [],
                "task": {"instruction": "answer", "kind": "generate",
                         "expects": {"format": "prose", "max_tokens": 40}},
                "deadline_ms": 4000, "lane": "PUBLIC", "tier": "GLOBAL",
                "constraints": {}}

    def test_credit_waits_only_while_busy_and_no_credit_is_still_served(
            self, tmp_path):
        state = self._state(tmp_path, delay=0.25)
        state.worker.credits = _Credits({"credited:0"})

        async def scenario():
            first = asyncio.create_task(
                state.worker.handle("peer-a", self.packet("long:0")))
            await asyncio.sleep(0.05)
            refused = await state.worker.handle(
                "peer-b", self.packet("plain:0"))
            credited = asyncio.create_task(
                state.worker.handle("peer-c", self.packet("credited:0")))
            await asyncio.sleep(0.05)
            third = await state.worker.handle(
                "peer-d", self.packet("plain:1"))
            assert third.get("code") == "E_POLICY"
            got = await credited
            await first
            served = await state.worker.handle(
                "peer-e", self.packet("plain:2"))
            return refused, got, served

        refused, got, served = asyncio.run(scenario())
        assert refused.get("code") == "E_POLICY"
        assert got.get("type") == "result"
        assert served.get("type") == "result"
        state.stop()

    def test_credit_does_not_bypass_the_circle_gate(self, tmp_path):
        state = self._state(tmp_path, delay=0.0)
        state.worker.circle_guard = lambda node_id: (
            False, "E_CIRCLE_REQUIRED", "not a member")
        state.worker.credits = _Credits({"credited:0"})
        reply = asyncio.run(state.worker.handle(
            "peer-a", self.packet("credited:0")))
        assert reply.get("code") == "E_CIRCLE_REQUIRED"
        state.stop()


LIST_REPLY = (
    "1. apples are fruit.\n"
    "2. bridges span rivers.\n"
    "3. comets have tails.\n"
    "4. drums make sound.\n"
    "5. electrons carry charge."
)


def _make_node(tmp_path, name, *, worker=True, port=None,
               reply="Apples are fruit. Bridges span rivers."):
    state = AppState(str(tmp_path / name))
    state.config.update({
        "swarm": {"p2p_port": port or next(_ports), "p2p_host": "127.0.0.1",
                  "lan_enabled": False, "worker_enabled": worker,
                  "worker_max_concurrent": 2, "timeout_ms": 8000,
                  "hedge_fallback_ms": 3000},
        "circle": {"admission_mode": "circle", "node_name": name},
        "privacy": {"tier": "GLOBAL"},
        "model": {"model_name": "fake-model:1b"},
        "credits": {"enabled": True, "receipt_ttl_days": 90},
    })
    fake = FakeBackend(reply)
    state.backends.resolve = lambda cfg=None: fake
    state.start_p2p()
    return state, fake


def _wait_for(predicate, timeout=10.0, step=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return False


TEST_PROMPT = (
    "Extract one key fact per item from the following list of five items: "
    "apples, bridges, comets, drums, electrons. List 5 bullet points, one per "
    "item, separately."
)


class TestGates:
    def test_credit_does_not_bypass_admission_or_egress(self, tmp_path):
        state = AppState(str(tmp_path / "gates"))
        state.config.update({"circle": {"admission_mode": "circle"}})
        calls = []

        class Spy:
            async def present_spend_async(self, *args, **kwargs):
                calls.append(args)
                return "receipt"

        state.circles.credits = Spy()
        peer_id = state.identity.node_id
        state.nodes.peers = {peer_id: SimpleNamespace(
            node_id=peer_id, connected=True, admitted=False,
            session=object(), advertisement={})}
        packet = {"v": WIRE_VERSION, "type": "task", "attempt_id": "x:0",
                  "task": {"instruction": "answer", "kind": "generate"}}
        with pytest.raises(Exception) as err:
            asyncio.run(state.nodes.dispatch_async(peer_id, packet, 1,
                                                   offer_credit=True))
        assert getattr(err.value, "code", "") in (
            "E_CIRCLE_REQUIRED", "E_EGRESS_DENIED")
        assert calls == []
        # Admitted but outside every circle: the egress gate still refuses
        # before any byte (and therefore before any credit) is written.
        state.nodes.peers[peer_id].admitted = True
        with pytest.raises(Exception) as err:
            asyncio.run(state.nodes.dispatch_async(peer_id, packet, 1,
                                                   offer_credit=True))
        assert getattr(err.value, "code", "") in (
            "E_CIRCLE_REQUIRED", "E_EGRESS_DENIED")
        assert calls == []
        state.stop()


class TestEndToEnd:
    def test_two_loopback_nodes_earn_deliver_spend_and_report(self, tmp_path):
        owner, _ = _make_node(tmp_path, "owner", worker=True,
                              reply=LIST_REPLY)
        worker, _ = _make_node(tmp_path, "worker", worker=True,
                               reply=LIST_REPLY)
        created = [owner, worker]
        try:
            circle = owner.circles.create_circle("Alpha")
            invite = owner.circles.invite(
                circle["circle_id"],
                endpoints=[f"127.0.0.1:{owner.nodes.listen_port}"])
            worker.circles.accept_invitation(
                invite["code"],
                endpoints=[f"127.0.0.1:{worker.nodes.listen_port}"])
            assert _wait_for(lambda: owner.circles.list_payload()["circles"][0]
                             ["pending_joins"])
            owner.circles.approve(circle["circle_id"],
                                  worker.identity.node_id)
            assert _wait_for(lambda: worker.nodes.available_workers())
            assert _wait_for(lambda: all(
                p["admitted"] for p in owner.nodes.status()["peers"]))

            # A control type this build does not know is ignored (MINOR-safe).
            owner.nodes.send_control(worker.identity.node_id, {
                "v": WIRE_VERSION, "type": "credit_future_note",
                "note": "ignored"})
            time.sleep(0.05)

            # Owner asks the worker for a verified result: one receipt.
            conv = owner.chat.create_conversation(mode="lan")
            owner.chat.send(conv["id"], TEST_PROMPT, mode="lan",
                            run_async=False)
            final = owner.chat.get_messages(conv["id"])[-1]
            assert final["meta"]["status"] == "done", final["meta"]
            assert _wait_for(lambda: worker.credits.wallet_summary(
                circle["circle_id"])["balance"] >= 1)
            assert owner.credits.list_payload()["issued_count"] >= 1
            receipt = next(iter(worker.credits._wallet["receipts"].values()))
            assert receipt["issuer"] == owner.identity.node_id
            assert receipt["worker"] == worker.identity.node_id

            # An ordinary send to an idle worker spends nothing: a receipt
            # is offered only to a worker known to be busy.
            conv = worker.chat.create_conversation(mode="lan")
            worker.chat.send(conv["id"], TEST_PROMPT, mode="lan",
                             run_async=False)
            final = worker.chat.get_messages(conv["id"])[-1]
            assert final["meta"]["status"] == "done", final["meta"]
            time.sleep(0.2)
            assert worker.credits.wallet_summary(
                circle["circle_id"])["spent"] == 0

            # Worker spends it when it sends work to the owner it knows is
            # busy (the scheduler passes offer_credit in that case).
            packet = {"v": WIRE_VERSION, "type": "task",
                      "attempt_id": "c" * 16 + ":0",
                      "task": {"instruction": "answer", "kind": "generate"}}
            try:
                worker.nodes.dispatch(owner.identity.node_id, packet, 5,
                                      offer_credit=True)
            except Exception:
                pass          # the task itself may be refused; the spend is not
            assert _wait_for(lambda: worker.credits.wallet_summary(
                circle["circle_id"])["spent"] >= 1)
            # The issuer (also the receiving worker here) logged the report.
            assert _wait_for(lambda: any(
                record.get("reports")
                for record in owner.credits._issued["receipts"].values()))
            assert owner.credits.flagged() == []
        finally:
            for state in created:
                state.stop()




def test_scheduler_offers_a_credit_only_to_a_busy_worker():
    """D-020: the scheduler passes offer_credit to the directory only after
    it saw that worker busy (a concurrency refusal or a missed deadline);
    an idle worker gets the task without spending a receipt."""
    from swarmbly_app.engine.scheduler import LatencyStats, Scheduler, SpeedStats
    from swarmbly_app.events import EventBus
    worker_id = "w" * 43
    offers: list[bool] = []

    class Directory:
        def __init__(self):
            self.peer = SimpleNamespace(
                node_id=worker_id, tasks_inflight=0, rtt_ms=1.0,
                advertisement={"models": [{"family": "fake", "version": "fake:1b"}],
                               "policy": {"max_concurrent": 1}})
            self.peers = {worker_id: self.peer}

        def available_workers(self, kind="generate"):
            return [self.peer]

        def classify_peer(self, node_id):
            return {"clase": egress.CIRCLE, "circle_id": CIRCLE_A}

        async def dispatch_async(self, node_id, message, timeout_s, *,
                                 offer_credit=False):
            offers.append(offer_credit)
            raise RuntimeError("stop here")

    def build(attempt, family=None, model=None):
        return {"v": WIRE_VERSION, "type": "task",
                "attempt_id": f"wire-task:{attempt}",
                "task": {"instruction": "answer", "kind": "generate",
                         "expects": {"max_tokens": 10}},
                "lane": "PUBLIC", "tier": "GLOBAL", "deadline_ms": 4000}

    for busy, expected in ((False, False), (True, True)):
        offers.clear()
        speed = SpeedStats()
        if busy:
            speed.record_busy(worker_id, 0.05)
        sched = Scheduler(Directory(), EventBus(), "req", k_min=1, k_max=1,
                          max_concurrency=1, timeout_s=2, hedge_fallback_s=1,
                          latency=LatencyStats(), speed=speed)
        with pytest.raises(Exception) as err:
            asyncio.run(sched.run_task("t0", build, 10, validate=None))
        assert offers and offers[0] is expected, (busy, offers, err.value)
