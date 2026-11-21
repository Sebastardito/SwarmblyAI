"""Circle relay (3.5, WP3 / D-016, D-023).

The end-to-end tests import the umbrella's real prototype relay from the
directory named by ``SWARMBLY_UMBRELLA`` or, when the App is the umbrella's
``SwarmblyApp/`` subtree, from the umbrella root, and skip with a clear reason
when that package is not importable. Everything else (manifest fields,
pins, publishing, wrong-pin refusal) runs on the App alone.
"""

from __future__ import annotations

import asyncio
import itertools
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from swarmbly_app import egress
from swarmbly_app.p2p import transport
from swarmbly_app.p2p.circles import (
    E_CIRCLE_RELAY_PIN,
    CircleError,
    build_manifest,
    decode_invitation,
    validate_invitation,
    validate_manifest,
)
from swarmbly_app.p2p.messages import WIRE_VERSION, verify_signed
from swarmbly_app.p2p.relay_client import (
    RelayAddress as AppRelayAddress,
    RelayClient as AppRelayClient,
)
from swarmbly_app.state import AppState

from conftest import FakeBackend

def _umbrella_root() -> Path | None:
    """Where the umbrella's ``relay`` package lives, if anywhere."""
    import os
    configured = os.environ.get("SWARMBLY_UMBRELLA", "").strip()
    if configured:
        return Path(configured)
    parent = Path(__file__).resolve().parents[2]   # umbrella/SwarmblyApp/tests
    return parent if (parent / "relay" / "server.py").is_file() else None


UMBRELLA = _umbrella_root()
RELAY_IMPORT_ERROR = ""
try:
    if UMBRELLA is None:
        raise ImportError("set SWARMBLY_UMBRELLA to the umbrella checkout")
    if str(UMBRELLA) not in sys.path:
        sys.path.insert(0, str(UMBRELLA))
    from relay.client import RelayAddress, RelayClient
    from relay.server import RelayConfig, RelayServer
    from relay.tests.support import make_cert
    RELAY_AVAILABLE = True
except Exception as exc:  # pragma: no cover - exercised only without umbrella
    RELAY_AVAILABLE = False
    RELAY_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

relay_required = pytest.mark.skipif(
    not RELAY_AVAILABLE,
    reason=("umbrella relay package not importable from "
            f"{UMBRELLA}: {RELAY_IMPORT_ERROR}"))

_ports = itertools.count(20600)
TEST_PROMPT = (
    "Extract one key fact per item from the following list of five items: "
    "apples, bridges, comets, drums, electrons. List 5 bullet points, one per "
    "item, separately."
)
CANARY = "RELAY-PLAINTEXT-CANARY-9f3a"


def wait_for(predicate, timeout=20.0, step=0.1):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return False


def make_node(tmp_path, name, *, worker=False, extra=None):
    state = AppState(str(tmp_path / name))
    cfg = {"swarm": {"p2p_port": next(_ports), "p2p_host": "127.0.0.1",
                     "lan_enabled": False, "worker_enabled": worker,
                     "worker_max_concurrent": 2, "timeout_ms": 8000},
           "circle": {"admission_mode": "circle", "node_name": name},
           "privacy": {"tier": "GLOBAL"},
           "model": {"model_name": "fake-model:1b"}}
    for section, values in (extra or {}).items():
        cfg.setdefault(section, {}).update(values)
    state.config.update(cfg)
    fake = FakeBackend(f"Apples are fruit. Bridges span rivers. {CANARY}")
    state.backends.resolve = lambda cfg=None: fake  # type: ignore[method-assign]
    state.start_p2p()
    return state, fake


@pytest.fixture()
def nodes(tmp_path):
    created = []

    def factory(name, **kw):
        state, fake = make_node(tmp_path, name, **kw)
        created.append(state)
        return state, fake

    yield factory
    for state in created:
        state.stop()


def join_circle(owner, member):
    circle = owner.circles.create_circle("Relay circle")
    invite = owner.circles.invite(
        circle["circle_id"],
        endpoints=[f"127.0.0.1:{owner.nodes.listen_port}"])
    member.circles.accept_invitation(
        invite["code"],
        endpoints=[f"127.0.0.1:{member.nodes.listen_port}"])
    assert wait_for(lambda: owner.circles.list_payload()["circles"][0]
                    ["pending_joins"])
    owner.circles.approve(circle["circle_id"], member.identity.node_id)
    assert wait_for(lambda: member.circles.list_payload()["circles"])
    assert wait_for(lambda: member.nodes.available_workers())
    return circle


def add_relay(owner, member, circle, address):
    owner.circles.set_relay(circle["circle_id"], {
        "host": address["host"], "port": address["port"],
        "tls_cert_sha256": address["pin"]})
    assert wait_for(lambda: (
        member.circles.manifests[circle["circle_id"]].get("relay") or {}
    ).get("port") == address["port"])


def send_task(state):
    conv = state.chat.create_conversation(mode="lan")
    state.chat.send(conv["id"], TEST_PROMPT, mode="lan", run_async=False)
    return state.chat.get_messages(conv["id"])[-1]


class RelayHarness:
    """Run the umbrella's real relay in a thread with its own event loop."""

    def __init__(self, tmp_path: Path, spool: Path, *, port: int = 0,
                 certfile: Path | None = None, keyfile: Path | None = None,
                 cert_name: str = "relay", **config: Any):
        self.tmp_path = tmp_path
        self.spool = spool
        self.config = config
        self.port_requested = int(port)
        self.certfile = Path(certfile) if certfile else None
        self.keyfile = Path(keyfile) if keyfile else None
        self.cert_name = cert_name
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.ready = threading.Event()
        self.server: Any = None
        self.port = 0
        self.pin = (transport.cert_fingerprint(self.certfile)
                    if self.certfile else "")
        self.error = ""
        self.stopped = False
        self.started = False

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._start())
        except Exception as exc:  # pragma: no cover - fixture failure
            self.error = f"{type(exc).__name__}: {exc}"
            self.ready.set()
            return
        self.ready.set()
        self.loop.run_forever()

    async def _start(self) -> None:
        if self.certfile is not None and self.keyfile is not None:
            cert, key, pin = self.certfile, self.keyfile, self.pin
        else:
            cert, key, pin = make_cert(self.tmp_path, self.cert_name)
            self.pin = pin
        self.spool.mkdir(parents=True, exist_ok=True)
        self.server = _CapturingRelay(RelayConfig(
            manifests=(self.spool,), certfile=cert, keyfile=key,
            host="127.0.0.1", port=self.port_requested, **self.config))
        await self.server.start()
        self.port = self.server.port

    def start(self) -> "RelayHarness":
        if self.started:
            return self
        self.started = True
        self.thread.start()
        assert self.ready.wait(10), "relay did not start"
        if self.error:
            raise RuntimeError(self.error)
        return self

    @property
    def address(self) -> dict[str, Any]:
        return {"host": "127.0.0.1", "port": self.port, "pin": self.pin}

    @property
    def forwarded(self) -> bytes:
        return bytes(self.server.forwarded) if self.server is not None else b""

    def stop(self) -> None:
        if self.stopped or not self.started:
            return
        self.stopped = True
        if self.server is not None:
            try:
                asyncio.run_coroutine_threadsafe(
                    self.server.stop(), self.loop).result(5)
            except Exception:
                pass
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(5)


if RELAY_AVAILABLE:
    class _CapturingRelay(RelayServer):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.forwarded = bytearray()

        def _record_forwarded(self, data: bytes) -> None:
            self.forwarded.extend(data)
else:  # pragma: no cover - collection remains importable without the umbrella
    class _CapturingRelay:  # type: ignore[no-redef]
        pass


@pytest.fixture()
def relay(tmp_path):
    created = []

    def factory(spool: Path, **config) -> RelayHarness:
        harness = RelayHarness(tmp_path, spool, **config).start()
        created.append(harness)
        return harness

    yield factory
    for harness in created:
        harness.stop()


def free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class TestManifestAndInvitation:
    def test_relay_and_pin_travel_signed_in_manifest_and_invitation(self, tmp_path):
        state, _ = make_node(tmp_path, "manifest", worker=False)
        try:
            circle = state.circles.create_circle("Familia")
            pin = "ab" * 32
            updated = state.circles.set_relay(circle["circle_id"], {
                "host": "relay.example.org", "port": 8765,
                "tls_cert_sha256": pin})
            assert updated["version"] == 2
            assert updated["relay"] == {
                "host": "relay.example.org", "port": 8765,
                "tls_cert_sha256": pin}
            assert verify_signed(updated["owner"], updated)
            validate_manifest(updated)

            invite = state.circles.invite(circle["circle_id"])
            decoded = decode_invitation(invite["code"])
            assert decoded["relay"] == updated["relay"]
            assert verify_signed(decoded["owner"], decoded)
            validate_invitation(decoded)

            tampered = dict(decoded)
            tampered["relay"] = {**decoded["relay"], "port": 9999}
            with pytest.raises(CircleError) as exc:
                validate_invitation(tampered)
            assert exc.value.code == "E_INVITATION_INVALID"
        finally:
            state.stop()

    def test_a_relay_without_a_pin_is_refused(self, tmp_path):
        state, _ = make_node(tmp_path, "pin", worker=False)
        try:
            circle = state.circles.create_circle("Familia")
            with pytest.raises(CircleError) as exc:
                state.circles.set_relay(circle["circle_id"], {
                    "host": "relay.example.org", "port": 8765})
            assert exc.value.code == E_CIRCLE_RELAY_PIN
            with pytest.raises(CircleError) as exc:
                state.circles.set_relay(circle["circle_id"], {
                    "host": "relay.example.org", "port": 8765,
                    "tls_cert_sha256": "not-a-sha256"})
            assert exc.value.code == E_CIRCLE_RELAY_PIN
            with pytest.raises(CircleError):
                build_manifest(
                    identity_manager=state.identity_manager,
                    circle_id=circle["circle_id"], name="Familia",
                    owner=state.identity.node_id,
                    members=[{"node_id": state.identity.node_id,
                              "name": "owner", "endpoints": []}],
                    version=2, issued_at=int(time.time()),
                    expires_at=int(time.time()) + 3600,
                    relay={"host": "relay.example.org", "port": 8765})
            # No address, no relay: removing is explicit, not a silent pin.
            assert state.circles.set_relay(circle["circle_id"], None)["version"] == 1
        finally:
            state.stop()

    def test_owner_pushes_each_signed_version_on_approval_and_revocation(
            self, tmp_path):
        owner, _ = make_node(tmp_path, "pub_owner", worker=False)
        other = AppState(str(tmp_path / "pub_other"))
        try:
            circle = owner.circles.create_circle("Familia")
            owner.circles.set_relay(circle["circle_id"], {
                "host": "127.0.0.1", "port": 8765,
                "tls_cert_sha256": "cd" * 32})
            spool = owner.circles._relay_publish_dir()
            target = spool / f"{circle['circle_id']}.json"
            assert target.exists()

            member_id = other.identity.node_id
            owner.circles.joins[circle["circle_id"]] = [{
                "node_id": member_id, "name": "new member",
                "endpoints": [], "requested_at": int(time.time())}]
            approved = owner.circles.approve(circle["circle_id"], member_id)
            assert approved["version"] == 3
            assert member_id in {m["node_id"] for m in approved["members"]}
            assert _spooled_version(target) == 3
            assert member_id in _spooled_members(target)

            revoked = owner.circles.revoke(circle["circle_id"], member_id)
            assert revoked["version"] == 4
            assert member_id not in {m["node_id"] for m in revoked["members"]}
            assert _spooled_version(target) == 4
            assert member_id not in _spooled_members(target)
        finally:
            owner.stop()
            other.stop()

    @relay_required
    def test_the_prototype_relay_verifies_the_app_manifest(self, tmp_path):
        state, _ = make_node(tmp_path, "parse", worker=False)
        try:
            circle = state.circles.create_circle("Familia")
            state.circles.set_relay(circle["circle_id"], {
                "host": "127.0.0.1", "port": 8765,
                "tls_cert_sha256": "ef" * 32})
            import json
            from relay.manifest import parse_manifest
            path = (state.circles._relay_publish_dir()
                    / f"{circle['circle_id']}.json")
            parsed = parse_manifest(json.loads(path.read_text()))
            assert parsed.circle_id == circle["circle_id"]
            assert parsed.version == 2
            assert parsed.relay is not None
            assert parsed.relay.tls_fingerprint == "ef" * 32
        finally:
            state.stop()


def _spooled_document(path: Path) -> dict[str, Any]:
    import json
    return json.loads(path.read_text(encoding="utf-8"))


def _spooled_version(path: Path) -> int:
    return int(_spooled_document(path)["version"])


def _spooled_members(path: Path) -> set[str]:
    return {str(m.get("node_id")) for m in _spooled_document(path)["members"]}


class TestWrongPin:
    def test_registration_refuses_a_wrong_pin_before_any_frame(self, tmp_path):
        async def run():
            cert = tmp_path / "node.crt"
            key = tmp_path / "node.key"
            transport.generate_cert(cert, key)
            seen = bytearray()

            async def handle(reader, writer):
                try:
                    data = await asyncio.wait_for(reader.read(4096), 1.0)
                except asyncio.TimeoutError:
                    data = b""
                seen.extend(data)
                writer.close()

            server = await asyncio.start_server(
                handle, "127.0.0.1", 0,
                ssl=transport.server_ssl_context(cert, key))
            port = server.sockets[0].getsockname()[1]
            identity = AppState(str(tmp_path / "pin_state")).identity_manager
            node_id = identity.load_or_create().node_id
            client = AppRelayClient(
                AppRelayAddress("127.0.0.1", port, "00" * 32),
                "circle-12345678", node_id, identity.sign, timeout=5.0)
            try:
                with pytest.raises(Exception) as exc:
                    await client.connect()
                assert getattr(exc.value, "code", "") == \
                    "relay_certificate_mismatch"
                await asyncio.sleep(0.2)
                assert bytes(seen) == b"", (
                    "the client sent a frame before checking the pin")
            finally:
                await client.close()
                server.close()
                await server.wait_closed()

        asyncio.run(run())


class TestRelayEndToEnd:
    @relay_required
    def test_two_nodes_with_no_direct_path_connect_through_a_real_relay(
            self, tmp_path, nodes, relay, monkeypatch):
        owner, _ = nodes("relay_owner", worker=True)
        member, _ = nodes("relay_member")
        harness = relay(owner.circles._relay_publish_dir())
        try:
            circle = join_circle(owner, member)
            add_relay(owner, member, circle, harness.address)
            cid = circle["circle_id"]
            assert wait_for(lambda: owner.nodes.relay_status(cid)["status"]
                            == "connected")
            assert wait_for(lambda: member.nodes.relay_status(cid)["status"]
                            == "connected")

            attempts: list[tuple[str, int]] = []

            async def no_direct(host, port, *args, **kwargs):
                attempts.append((host, int(port)))
                return None

            monkeypatch.setattr(member.nodes, "_connect", no_direct)
            member.nodes.drop_peer(owner.identity.node_id, "test: no direct path")
            owner.nodes.drop_peer(member.identity.node_id, "test: no direct path")
            assert wait_for(lambda: not any(
                p.connected for p in member.nodes.peers.values()))

            final = send_task(member)
            assert final["meta"]["status"] == "done", final["meta"]
            assert final["meta"]["executed"] == "distributed", final["meta"]
            assert attempts, "direct addresses were not tried first"
            peer = member.nodes.peers[owner.identity.node_id]
            assert peer.transport == "relayed"
            assert peer.relay and peer.relay["host"] == "127.0.0.1"
            assert peer.session is not None
            assert peer.session.tls_version == "TLSv1.3"

            swarm = final["meta"]["swarm"]
            relayed = [a for a in swarm["attempts"] if a.get("relay")]
            assert relayed, swarm["attempts"]
            assert all(a["relay"]["host"] == "127.0.0.1" for a in relayed)
            receipt = final["meta"]["receipt"]
            assert receipt["saltos_relay"] == [{
                "host": "127.0.0.1", "port": harness.port,
                "metadata_only": True, "saw": ["who", "when", "bytes"],
                "content": False}]
            hops = [e for e in receipt["envios"] if e.get("transport") == "relayed"]
            assert hops and all(e["relay"]["content"] is False for e in hops)

            forwarded = harness.forwarded
            assert forwarded, "the relay did not forward the end-to-end session"
            assert CANARY.encode() not in forwarded
            assert b"hello_ack" not in forwarded
        finally:
            harness.stop()

    @relay_required
    def test_direct_addresses_are_tried_first_even_with_a_relay(self, tmp_path,
                                                                nodes, relay):
        owner, _ = nodes("direct_owner", worker=True)
        member, _ = nodes("direct_member")
        harness = relay(owner.circles._relay_publish_dir())
        try:
            circle = join_circle(owner, member)
            add_relay(owner, member, circle, harness.address)
            cid = circle["circle_id"]
            assert wait_for(lambda: member.nodes.relay_status(cid)["status"]
                            == "connected")
            final = send_task(member)
            assert final["meta"]["status"] == "done", final["meta"]
            peer = member.nodes.peers[owner.identity.node_id]
            assert peer.transport == "direct"
            assert harness.forwarded == b"", (
                "the relay carried bytes although a direct path existed")
        finally:
            harness.stop()

    @relay_required
    def test_a_revoked_member_can_no_longer_register_or_pair(self, tmp_path,
                                                             nodes, relay,
                                                             monkeypatch):
        owner, _ = nodes("revoke_owner", worker=True)
        member, _ = nodes("revoke_member")
        harness = relay(owner.circles._relay_publish_dir())
        try:
            circle = join_circle(owner, member)
            add_relay(owner, member, circle, harness.address)
            cid = circle["circle_id"]
            assert wait_for(lambda: member.nodes.relay_status(cid)["status"]
                            == "connected")
            revoked = owner.circles.revoke(cid, member.identity.node_id)
            assert revoked["version"] == 4
            spool = owner.circles._relay_publish_dir() / f"{cid}.json"
            assert wait_for(lambda: _spooled_version(spool) == 4)
            assert member.identity.node_id not in _spooled_members(spool)
            # The revoked node still holds its old manifest; the relay's
            # current signed version is what stops it.

            # The relay itself reloads the spool before registration and
            # refuses the removed key: revocation reached it with the push.
            async def register_revoked():
                client = RelayClient(
                    RelayAddress("127.0.0.1", harness.port, harness.pin),
                    cid, member.identity.node_id, member.identity_manager.sign,
                    timeout=5.0)
                try:
                    with pytest.raises(Exception) as exc:
                        await client.connect()
                    return getattr(exc.value, "code", "")
                finally:
                    await client.close()

            assert asyncio.run(register_revoked()) == "not_a_member"

            async def no_direct(*args, **kwargs):
                return None

            monkeypatch.setattr(member.nodes, "_connect", no_direct)
            member.nodes.drop_peer(owner.identity.node_id, "test")
            assert member.nodes._call(
                member.nodes.ensure_peer(owner.identity.node_id),
                timeout=20) is None
        finally:
            harness.stop()

    @relay_required
    def test_a_non_member_cannot_register_with_the_relay(self, tmp_path, nodes,
                                                         relay):
        owner, _ = nodes("nonmember_owner", worker=True)
        stranger, _ = nodes("nonmember_stranger")
        harness = relay(owner.circles._relay_publish_dir())
        try:
            member = _second_member(nodes)
            circle = join_circle(owner, member)
            add_relay(owner, member, circle, harness.address)
            cid = circle["circle_id"]

            async def register_stranger():
                client = RelayClient(
                    RelayAddress("127.0.0.1", harness.port, harness.pin),
                    cid, stranger.identity.node_id,
                    stranger.identity_manager.sign, timeout=5.0)
                try:
                    with pytest.raises(Exception) as exc:
                        await client.connect()
                    return getattr(exc.value, "code", "")
                finally:
                    await client.close()

            assert asyncio.run(register_stranger()) == "not_a_member"
        finally:
            harness.stop()

    @relay_required
    def test_a_wrong_pin_stops_that_relay_with_a_security_warning(
            self, tmp_path, nodes, relay):
        owner, _ = nodes("pin_owner", worker=True)
        member, _ = nodes("pin_member")
        harness = relay(owner.circles._relay_publish_dir())
        try:
            circle = join_circle(owner, member)
            cid = circle["circle_id"]
            owner.circles.set_relay(cid, {
                "host": "127.0.0.1", "port": harness.port,
                "tls_cert_sha256": "11" * 32})
            assert wait_for(lambda: owner.nodes.relay_status(cid).get(
                "security_warning"), timeout=15)
            state = owner.nodes.relay_status(cid)
            assert state["status"] == "security_warning"
            assert "certificate" in state["last_error"] or "pin" in state["last_error"]
            warnings = [e for e in owner.bus.recent(50)
                        if e["type"] == "relay.security_warning"]
            assert warnings
        finally:
            harness.stop()

    @relay_required
    def test_a_relay_refusal_is_surfaced_in_the_circle_card(self, tmp_path,
                                                            nodes, relay,
                                                            monkeypatch):
        owner, _ = nodes("refuse_owner", worker=True)
        member, _ = nodes("refuse_member")
        harness = relay(owner.circles._relay_publish_dir())
        try:
            circle = join_circle(owner, member)
            add_relay(owner, member, circle, harness.address)
            cid = circle["circle_id"]
            assert wait_for(lambda: member.nodes.relay_status(cid)["status"]
                            == "connected")
            # Remove the owner's acceptor: the relay now answers a pair from
            # the member with peer_not_connected, which must be visible.
            owner.nodes._relay_stopping = True
            for task in list(owner.nodes._relay_tasks.values()):
                task.cancel()
            # Let the cancellation close the registered acceptor.
            time.sleep(1.0)

            async def no_direct(*args, **kwargs):
                return None

            monkeypatch.setattr(member.nodes, "_connect", no_direct)
            member.nodes.drop_peer(owner.identity.node_id, "test")
            owner.nodes.drop_peer(member.identity.node_id, "test")
            assert member.nodes._call(
                member.nodes.ensure_peer(owner.identity.node_id),
                timeout=20) is None
            state = member.nodes.relay_status(cid)
            assert "peer_not_connected" in state["last_error"], state
            refusals = [e for e in member.bus.recent(50)
                        if e["type"] in ("relay.pair_failed", "relay.refused")]
            assert any("peer_not_connected" in str(e["payload"].get("reason", ""))
                       for e in refusals)
        finally:
            harness.stop()

    def test_relay_down_leaves_direct_lan_peers_working(self, tmp_path, nodes):
        owner, _ = nodes("down_owner", worker=True)
        member, _ = nodes("down_member")
        try:
            circle = join_circle(owner, member)
            cid = circle["circle_id"]
            port = free_port()
            owner.circles.set_relay(cid, {
                "host": "127.0.0.1", "port": port,
                "tls_cert_sha256": "22" * 32})
            assert wait_for(lambda: (
                member.circles.manifests[cid].get("relay") or {}
            ).get("port") == port)
            final = send_task(member)
            assert final["meta"]["status"] == "done", final["meta"]
            assert final["meta"]["executed"] == "distributed", final["meta"]
            peer = member.nodes.peers[owner.identity.node_id]
            assert peer.transport == "direct"
            receipt = final["meta"]["receipt"]
            assert receipt["saltos_relay"] == []
        finally:
            for state in (owner, member):
                try:
                    state.stop()
                except Exception:
                    pass


def _second_member(nodes):
    member, _ = nodes("nonmember_member")
    return member


class TestRelayAPI:
    def test_the_owner_sets_and_removes_the_relay(self, app_state):
        from fastapi.testclient import TestClient
        from swarmbly_app.api import create_app
        app = create_app(app_state)
        client = TestClient(app, base_url="http://127.0.0.1:8765")
        client.headers["X-Swarmbly-Token"] = app.state.guard.token
        circle = client.post("/api/circles", json={"name": "Relay API"})
        assert circle.status_code == 200, circle.text
        cid = circle.json()["circle_id"]
        pin = "ab" * 32
        set_relay = client.post(f"/api/circles/{cid}/relay", json={
            "host": "relay.example.org", "port": 8765,
            "tls_cert_sha256": pin})
        assert set_relay.status_code == 200, set_relay.text
        assert set_relay.json()["relay"] == {
            "host": "relay.example.org", "port": 8765,
            "tls_cert_sha256": pin}
        missing_pin = client.post(f"/api/circles/{cid}/relay", json={
            "host": "relay.example.org", "port": 8765})
        assert missing_pin.status_code == 400
        assert E_CIRCLE_RELAY_PIN in missing_pin.text
        removed = client.post(f"/api/circles/{cid}/relay", json={"relay": None})
        assert removed.status_code == 200, removed.text
        assert "relay" not in removed.json()


class TestRelayStatus:
    def test_off_by_default_without_a_relay(self, tmp_path, nodes):
        owner, _ = nodes("off_owner", worker=True)
        member, _ = nodes("off_member")
        try:
            circle = join_circle(owner, member)
            assert owner.circles.manifests[circle["circle_id"]].get("relay") is None
            assert owner.nodes.relay_status(circle["circle_id"])["status"] == "off"
            assert owner.nodes.status()["relays"] == []
        finally:
            pass
