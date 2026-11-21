"""Owner manifest push over the real relay (3.5, D-023).

These tests use the umbrella relay via ``SWARMBLY_UMBRELLA`` (or the umbrella
root when this App is its ``SwarmblyApp/`` subtree). The relay's first version
of a circle is the operator's bootstrap file; after that every new version is
pushed by the owner's App over a registered connection. No App publish file is
copied into the relay directory during these tests.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_relay import (  # noqa: E402
    RELAY_AVAILABLE,
    RelayHarness,
    free_port,
    join_circle,
    make_node,
    relay_required,
    wait_for,
)
if RELAY_AVAILABLE:
    from test_relay import make_cert  # noqa: E402
else:  # pragma: no cover - collection remains importable without the umbrella
    make_cert = None

from swarmbly_app.p2p.relay_client import (  # noqa: E402
    RelayAddress,
    RelayClient,
    RelayRefused,
)

PUSH_FAST = {
    "relay_push_backoff_s": 0.2,
    "relay_push_backoff_max_s": 1.0,
    "relay_push_refusal_retry_s": 5.0,
}


def bootstrap(spool: Path, manifest: dict[str, Any]) -> None:
    """Operator installs the first signed manifest of a circle."""
    spool.mkdir(parents=True, exist_ok=True)
    (spool / f"{manifest['circle_id']}.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


@pytest.fixture()
def app_nodes(tmp_path):
    created = []

    def factory(name, **kw):
        kw.setdefault("extra", {})
        kw["extra"].setdefault("circle", {}).update(PUSH_FAST)
        state, fake = make_node(tmp_path, name, **kw)
        created.append(state)
        return state, fake

    yield factory
    for state in created:
        state.stop()


def push_state(state, circle_id: str) -> dict[str, Any]:
    status = state.nodes.relay_status(circle_id)
    return (status.get("push") or {}).get("current") or {}


def relay_manifest(harness: RelayHarness, circle_id: str):
    if harness.server is None:
        return None
    return harness.server.store.get(circle_id)


@relay_required
class TestOwnerPush:
    def test_approval_is_pushed_and_acknowledged(self, tmp_path, app_nodes):
        owner, _ = app_nodes("push_approve_owner", worker=True)
        member, _ = app_nodes("push_approve_member")
        circle = owner.circles.create_circle("Push family")
        cid = circle["circle_id"]
        invite = owner.circles.invite(
            cid, endpoints=[f"127.0.0.1:{owner.nodes.listen_port}"])
        member.circles.accept_invitation(
            invite["code"],
            endpoints=[f"127.0.0.1:{member.nodes.listen_port}"])
        assert wait_for(lambda: owner.circles.list_payload()["circles"][0]
                        ["pending_joins"])

        spool = tmp_path / "relay-approval"
        bootstrap(spool, owner.circles.manifests[cid])       # v1, operator
        harness = RelayHarness(tmp_path, spool,
                               cert_name="relay-approval").start()
        try:
            owner.circles.set_relay(cid, harness.address)    # v2
            assert wait_for(lambda: (relay_manifest(harness, cid)
                                     and relay_manifest(harness, cid).version == 2))
            owner.circles.approve(cid, member.identity.node_id)  # v3
            assert wait_for(lambda: (relay_manifest(harness, cid)
                                     and relay_manifest(harness, cid).version == 3))
            held = relay_manifest(harness, cid)
            assert held.contains(member.identity.node_id)
            state = push_state(owner, cid)
            assert state["acknowledged_version"] == 3
            assert int(state["pending_version"]) == 0
            assert not state["last_refusal"]
        finally:
            harness.stop()

    def test_revocation_is_pushed_and_cuts_an_open_relay_session(
            self, tmp_path, app_nodes):
        owner, _ = app_nodes("push_revoke_owner", worker=True)
        member, _ = app_nodes("push_revoke_member")
        circle = join_circle(owner, member)                   # v2
        cid = circle["circle_id"]
        spool = tmp_path / "relay-revoke"
        bootstrap(spool, owner.circles.manifests[cid])
        harness = RelayHarness(tmp_path, spool,
                               cert_name="relay-revoke").start()
        try:
            owner.circles.set_relay(cid, harness.address)    # v3
            assert wait_for(lambda: member.nodes.relay_status(cid)["status"]
                            == "connected", timeout=20)
            owner.circles.revoke(cid, member.identity.node_id)  # v4
            assert wait_for(lambda: (relay_manifest(harness, cid)
                                     and relay_manifest(harness, cid).version == 4))
            held = relay_manifest(harness, cid)
            assert not held.contains(member.identity.node_id)
            # The network push (not a file copy) persisted the new version.
            on_disk = json.loads((spool / f"{cid}.json").read_text(
                encoding="utf-8"))
            assert int(on_disk["version"]) == 4
            assert member.identity.node_id not in {
                str(m.get("node_id")) for m in on_disk["members"]}

            # The member's registered session through the relay is cut.
            assert wait_for(lambda: member.nodes.relay_status(cid)["status"]
                            != "connected", timeout=15)

            async def register_revoked():
                client = RelayClient(
                    RelayAddress("127.0.0.1", harness.port, harness.pin),
                    cid, member.identity.node_id,
                    member.identity_manager.sign, timeout=5.0)
                try:
                    with pytest.raises(RelayRefused) as exc:
                        await client.connect()
                    return exc.value.code
                finally:
                    await client.close()

            assert asyncio.run(register_revoked()) == "not_a_member"

            async def pair_revoked():
                client = RelayClient(
                    RelayAddress("127.0.0.1", harness.port, harness.pin),
                    cid, owner.identity.node_id,
                    owner.identity_manager.sign, timeout=5.0)
                try:
                    await client.connect()
                    with pytest.raises(RelayRefused) as exc:
                        await client.pair(member.identity.node_id)
                    return exc.value.code
                finally:
                    await client.close()

            assert asyncio.run(pair_revoked()) == "not_a_member"
            state = push_state(owner, cid)
            assert state["acknowledged_version"] == 4
        finally:
            harness.stop()

    def test_a_push_before_bootstrap_is_unknown_circle_and_shown(
            self, tmp_path, app_nodes):
        owner, _ = app_nodes("push_unknown_owner", worker=True)
        member, _ = app_nodes("push_unknown_member")
        circle = join_circle(owner, member)                   # v2
        cid = circle["circle_id"]
        spool = tmp_path / "relay-unknown"
        spool.mkdir(parents=True, exist_ok=True)
        harness = RelayHarness(tmp_path, spool,
                               cert_name="relay-unknown").start()
        try:
            owner.circles.set_relay(cid, harness.address)    # v3, no bootstrap
            assert wait_for(lambda: push_state(owner, cid).get("last_refusal")
                            == "unknown_circle", timeout=15)
            state = push_state(owner, cid)
            assert state["last_refusal"] == "unknown_circle"
            assert int(state["pending_version"]) == 3

            # The operator installs the first manifest; a new version then
            # replaces the queued one and is pushed without any file copy.
            bootstrap(spool, owner.circles.manifests[cid])   # operator's v3
            owner.circles.renew(cid)                         # v4
            assert wait_for(lambda: (relay_manifest(harness, cid)
                                     and relay_manifest(harness, cid).version == 4),
                            timeout=20)
            state = push_state(owner, cid)
            assert state["acknowledged_version"] == 4
            assert not state["last_refusal"]
        finally:
            harness.stop()

    def test_relay_down_then_up_delivers_only_the_newest_version(
            self, tmp_path, app_nodes):
        owner, _ = app_nodes("push_down_owner", worker=True)
        member, _ = app_nodes("push_down_member")
        circle = join_circle(owner, member)                   # v2
        cid = circle["circle_id"]
        port = free_port()
        cert, key, pin = make_cert(tmp_path, "relay-down")
        spool = tmp_path / "relay-down"
        bootstrap(spool, owner.circles.manifests[cid])       # v2 on disk
        harness = RelayHarness(tmp_path, spool, port=port,
                               certfile=cert, keyfile=key)
        try:
            owner.circles.set_relay(cid, {
                "host": "127.0.0.1", "port": port,
                "tls_cert_sha256": pin})                      # v3 queued
            owner.circles.renew(cid)                         # v4 replaces v3
            state = push_state(owner, cid)
            assert int(state["pending_version"]) == 4
            assert state["status"] in ("queued", "pushing", "unreachable")

            harness.start()
            assert wait_for(lambda: (relay_manifest(harness, cid)
                                     and relay_manifest(harness, cid).version == 4),
                            timeout=25)
            held = relay_manifest(harness, cid)
            assert held.version == 4
            assert wait_for(lambda: push_state(owner, cid).get(
                "acknowledged_version") == 4, timeout=10)
            state = push_state(owner, cid)
            assert int(state["pending_version"]) == 0
        finally:
            harness.stop()

    def test_a_relay_change_pushes_the_same_version_to_old_and_new(
            self, tmp_path, app_nodes):
        owner, _ = app_nodes("push_change_owner", worker=True)
        member, _ = app_nodes("push_change_member")
        circle = join_circle(owner, member)                   # v2
        cid = circle["circle_id"]
        old_spool = tmp_path / "relay-old"
        new_spool = tmp_path / "relay-new"
        bootstrap(old_spool, owner.circles.manifests[cid])
        bootstrap(new_spool, owner.circles.manifests[cid])
        old = RelayHarness(tmp_path, old_spool,
                           cert_name="relay-old").start()
        new = RelayHarness(tmp_path, new_spool,
                           cert_name="relay-new").start()
        try:
            owner.circles.set_relay(cid, old.address)        # v3 -> old
            assert wait_for(lambda: (relay_manifest(old, cid)
                                     and relay_manifest(old, cid).version == 3))
            owner.circles.revoke(cid, member.identity.node_id)  # v4 -> old
            assert wait_for(lambda: (relay_manifest(old, cid)
                                     and relay_manifest(old, cid).version == 4))
            assert not relay_manifest(old, cid).contains(member.identity.node_id)

            owner.circles.set_relay(cid, new.address)        # v5 -> old + new
            assert wait_for(lambda: (relay_manifest(old, cid)
                                     and relay_manifest(old, cid).version == 5),
                            timeout=20)
            assert wait_for(lambda: (relay_manifest(new, cid)
                                     and relay_manifest(new, cid).version == 5),
                            timeout=20)
            assert not relay_manifest(old, cid).contains(member.identity.node_id)
            assert not relay_manifest(new, cid).contains(member.identity.node_id)
            assert wait_for(lambda: all(
                s.get("acknowledged_version") == 5
                for s in (owner.nodes.relay_status(cid)["push"] or {})
                .get("targets", [])), timeout=15)
        finally:
            old.stop()
            new.stop()

    def test_a_non_owner_never_pushes(self, tmp_path, app_nodes):
        owner, _ = app_nodes("push_owner_only", worker=True)
        member, _ = app_nodes("push_member_only")
        circle = join_circle(owner, member)                   # v2
        cid = circle["circle_id"]
        spool = tmp_path / "relay-owner-only"
        bootstrap(spool, owner.circles.manifests[cid])
        harness = RelayHarness(tmp_path, spool,
                               cert_name="relay-owner-only").start()
        try:
            owner.circles.set_relay(cid, harness.address)    # v3 by owner
            assert wait_for(lambda: (relay_manifest(harness, cid)
                                     and relay_manifest(harness, cid).version == 3))
            current = owner.circles.manifests[cid]
            queued = member.nodes.queue_relay_push(
                cid, current, [harness.address])
            assert queued == 0
            assert not any(str(q.get("circle_id")) == cid
                           for q in member.nodes._relay_push_queue.values())

            async def member_pushes():
                client = RelayClient(
                    RelayAddress("127.0.0.1", harness.port, harness.pin),
                    cid, member.identity.node_id,
                    member.identity_manager.sign, timeout=5.0)
                try:
                    await client.connect()
                    with pytest.raises(RelayRefused) as exc:
                        await client.push_manifest(current)
                    return exc.value.code
                finally:
                    await client.close()

            assert asyncio.run(member_pushes()) == "not_owner"
            assert relay_manifest(harness, cid).version == 3
        finally:
            harness.stop()
