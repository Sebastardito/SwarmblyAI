"""Node manager: P2P lifecycle, peer registry, message routing.

Runs its own asyncio event loop in a background thread so the synchronous
chat/engine threads can dispatch via ``run_coroutine_threadsafe``. Ties
together discovery (mDNS), transport (TLS 1.3) and the channel-bound Ed25519
handshake.

Design rules:

- A node's identity is its Ed25519 key, never its IP address.
- One live session per peer. When two nodes dial each other at once, both
  keep the session initiated by the lower ``node_id`` (deterministic).
- Incoming tasks never run inside the read loop: each one is its own task,
  so a node keeps receiving results and pings while it serves.
- Discovery starts and stops at runtime when the configuration changes.
"""

from __future__ import annotations

import asyncio
import collections
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from .. import egress
from ..config import Config
from ..db import Database
from ..events import EventBus
from ..identity import IdentityManager
from .discovery import DiscoveredNode, DiscoveryService
from .circles import CONTROL_TYPES, CircleError
from .handshake import (Handshake, HandshakeResult, sign_advertisement_update,
                        validate_advertisement, verify_advertisement_update)
from ..node_roles import normalise_advertisement
from .messages import HELLO_TIMEOUT_S, WIRE_VERSION, error
from .relay_client import (RelayAddress, RelayClient, RelayError,
                           RelayRefused)
from .transport import (PeerSession, TLSServer, accept_over_stream,
                        cert_fingerprint, dial, dial_over_stream, generate_cert,
                        read_frame, read_frame_with_timeout, write_frame)

DEFAULT_P2P_PORT = 9765
MAX_PEERS = 64
KEEPALIVE_S = 30.0
DEAD_AFTER_S = 95.0
DIAL_BACKOFF_S = 4.0          # higher node_id waits this long before dialing
REPLAY_WINDOW = 4096          # attempt_ids remembered per peer
MAX_QUEUED_TASKS_PER_PEER = 8
# 3.5, WP3 / D-023: bounded relay connections. One idle acceptor per
# (circle, relay); a few short-lived initiators while direct paths fail.
MAX_RELAY_CONNECTIONS = 4
RELAY_BACKOFF_S = 1.0
RELAY_BACKOFF_MAX_S = 30.0
RELAY_REACH_TIMEOUT_S = 15.0


@dataclass
class Peer:
    node_id: str
    address: str
    port: int                         # the peer's listening port (dial target)
    advertisement: dict[str, Any] = field(default_factory=dict)
    connected: bool = False
    authenticated: bool = False       # Ed25519 handshake bound to TLS succeeded
    admitted: bool = True             # circle admission (False: join bootstrap)
    source: str = "manual"            # mdns | manual | inbound
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    rtt_ms: float | None = None       # measured by ping/pong
    session: PeerSession | None = None
    adv_seq: int = 0
    tasks_inflight: int = 0
    # 3.5, WP3 / D-016: how this peer is reached. The relay is a transport
    # hop, never a different authorisation: admission and egress are unchanged.
    transport: str = "direct"         # direct | relayed
    relay: dict[str, Any] | None = None
    seen_attempts: collections.OrderedDict = field(
        default_factory=collections.OrderedDict)

    @property
    def is_worker(self) -> bool:
        policy = self.advertisement.get("policy") or {}
        return bool(policy.get("kinds"))

    @property
    def roles(self) -> list[dict[str, Any]]:
        """Node roles this peer advertises (3.5, D-018), already normalised."""
        return list(self.advertisement.get("roles") or [])

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "short_id": self.node_id[:12],
            "address": self.address,
            "port": self.port,
            "connected": self.connected,
            # "verified" kept for API compatibility: it means *authenticated*
            # (identity proven), not "capability verified by a task".
            "verified": self.authenticated,
            "authenticated": self.authenticated,
            "admitted": self.admitted,
            "worker": self.is_worker,
            "source": self.source,
            "models": self.advertisement.get("models", []),
            "roles": self.roles,
            "policy": self.advertisement.get("policy", {}),
            "resources": self.advertisement.get("resources", {}),
            "rtt_ms": self.rtt_ms,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "tasks_inflight": self.tasks_inflight,
            "transport": self.transport,
            "relay": dict(self.relay) if self.relay else None,
        }


class NodeManager:
    def __init__(self, identity: IdentityManager, config: Config, db: Database,
                 bus: EventBus, advertisement_builder, dirs=None):
        self.identity_manager = identity
        self.config = config
        self.db = db
        self.bus = bus
        self.build_advertisement = advertisement_builder
        self._dirs = dirs
        self.handshake = Handshake(identity, {})
        self.circles = None               # set by AppState after construction
        self.peers: dict[str, Peer] = {}
        self._pending: dict[str, asyncio.Future] = {}
        self._pending_lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._tasks: set[asyncio.Task] = set()
        self._dialing: set[str] = set()
        self.server: TLSServer | None = None
        self.discovery: DiscoveryService | None = None
        self._task_handler = None
        self._cancel_handler = None
        self._started = False
        self._ready = threading.Event()
        self._adv_seq = 0
        self.listen_port: int | None = None
        self.listen_error: str = ""
        self.node_id = identity.load_or_create().node_id
        # 3.5, WP3: relay registrations and their visible state.
        self._relay_tasks: dict[str, asyncio.Task] = {}
        self._relay_state: dict[str, dict[str, Any]] = {}
        self._relay_clients: set[RelayClient] = set()
        self._relay_event: asyncio.Event | None = None
        self._relay_stopping = False
        # 3.5, WP3 / D-023 owner push: the newest unacknowledged version per
        # (circle, relay) target. The file spool remains the operator's
        # bootstrap copy and the fallback.
        self._relay_push_lock = threading.RLock()
        self._relay_push_queue: dict[str, dict[str, Any]] = {}
        self._relay_push_tasks: dict[str, asyncio.Task] = {}
        self._relay_push_state: dict[str, dict[str, Any]] = {}
        self._relay_push_event: asyncio.Event | None = None

    # -- lifecycle ---------------------------------------------------------------
    def start(self, task_handler=None, cancel_handler=None) -> None:
        if self._started:
            return
        self._started = True
        self._task_handler = task_handler
        self._cancel_handler = cancel_handler
        self._thread = threading.Thread(target=self._run_loop,
                                        name="swarmbly-p2p", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=10)

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_start())
        except Exception as exc:  # port in use, etc.: report, keep loop alive
            self.listen_error = str(exc)[:200]
            self.bus.publish("node.listen_failed", reason=self.listen_error)
        finally:
            self._ready.set()
        try:
            self._loop.run_forever()
        finally:
            try:
                self._loop.close()
            except Exception:
                pass

    async def _async_start(self) -> None:
        cfg = self.config.all()["swarm"]
        port = int(cfg.get("p2p_port") or DEFAULT_P2P_PORT)
        host = cfg.get("p2p_host") or "0.0.0.0"
        cert_dir = self._data_dirs().cache / "tls"
        generate_cert(cert_dir / "node.crt", cert_dir / "node.key")
        self.handshake.tls_fingerprint = cert_fingerprint(cert_dir / "node.crt")
        self.server = TLSServer(host, port, cert_dir / "node.crt",
                                cert_dir / "node.key", self._on_session)
        await self.server.start()
        self.listen_port = port
        self._spawn(self._keepalive_loop())
        await self._apply_discovery()
        # 3.5, WP3: start relay supervision only when a circle manifest names
        # a relay. Off by default: no manifest, no connection.
        self._relay_stopping = False
        self._relay_event = asyncio.Event()
        self._relay_push_event = asyncio.Event()
        self._spawn(self._relay_supervisor())
        self._spawn(self._relay_push_supervisor())
        self.bus.publish("node.listening", port=port)

    def _data_dirs(self):
        if self._dirs is not None:
            return self._dirs
        from ..paths import DataDirs
        return DataDirs(self.config.get("data_dir") or None)

    def _spawn(self, coro) -> asyncio.Task:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def stop(self) -> None:
        """Graceful shutdown: goodbye on mDNS, close sessions, stop the loop."""
        if not self._started or self._loop is None:
            return
        self._started = False

        async def _shutdown() -> None:
            if self.discovery is not None:
                try:
                    await asyncio.wait_for(self.discovery.stop(), timeout=3)
                except Exception:
                    pass
            # Close sessions *before* waiting on the server: since Python 3.12
            # Server.wait_closed() waits for every open connection.
            for peer in list(self.peers.values()):
                if peer.session is not None:
                    peer.session.close()
            self._relay_stopping = True
            if self._relay_push_event is not None:
                self._relay_push_event.set()
            for task in list(self._relay_push_tasks.values()):
                task.cancel()
            for client in list(self._relay_clients):
                try:
                    await client.close()
                except Exception:
                    pass
            self._relay_clients.clear()
            current = asyncio.current_task()
            for task in list(self._tasks):
                if task is not current:
                    task.cancel()
            await asyncio.gather(*[t for t in self._tasks if t is not current],
                                 return_exceptions=True)
            if self.server is not None:
                try:
                    await asyncio.wait_for(self.server.stop(), timeout=3)
                except Exception:
                    pass

        try:
            asyncio.run_coroutine_threadsafe(_shutdown(), self._loop).result(timeout=8)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _call(self, coro, timeout: float = 10.0):
        """Run a coroutine on the P2P loop from another thread."""
        if self._loop is None or not self._loop.is_running():
            coro.close()
            raise RuntimeError("P2P node not started")
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    # -- configuration changes (runtime) ------------------------------------------
    def apply_config(self) -> None:
        """React to configuration changes without restart: start/stop mDNS and
        re-announce our advertisement to connected peers."""
        if self._loop is None or not self._loop.is_running():
            return
        try:
            self._call(self._apply_discovery(), timeout=15)
            self._call(self._broadcast_advertisement(), timeout=10)
        except Exception:
            pass

    async def _apply_discovery(self) -> None:
        full = self.config.all()
        cfg = full["swarm"]
        # An explicit "no" in the permission step always wins; enabling LAN in
        # the configuration (UI toggle or CLI on a headless worker) is consent.
        refused = (full.get("permissions") or {}).get("lan_discovery") is False
        want = bool(cfg.get("lan_enabled")) and not refused
        if want and self.discovery is None and self.listen_port:
            self.discovery = DiscoveryService(
                self.node_id, self.listen_port, WIRE_VERSION,
                on_discovered=self._on_discovered, on_removed=self._on_removed,
                ttl_s=float(cfg.get("discovery_ttl_s", 300)))
            await self.discovery.start(announce=True, browse=True)
            self.bus.publish("node.discovery", state="on",
                             error=self.discovery.last_error)
        elif not want and self.discovery is not None:
            await self.discovery.stop()
            self.discovery = None
            self.bus.publish("node.discovery", state="off")

    def rescan(self, wait_s: float = 1.5) -> dict[str, int]:
        """Active mDNS search (blocking up to ``wait_s``)."""
        if self.discovery is None:
            return {"queried": 0, "answered": 0, "discovery": "off"}
        return self._call(self.discovery.refresh(wait_s), timeout=wait_s + 10)

    # -- advertisement --------------------------------------------------------------
    def _advertisement(self) -> dict[str, Any]:
        adv = self.build_advertisement()
        adv["v"] = WIRE_VERSION
        return adv

    async def _broadcast_advertisement(self) -> None:
        self._adv_seq += 1
        message = sign_advertisement_update(self.identity_manager,
                                            self._advertisement(), self._adv_seq)
        for peer in list(self.peers.values()):
            if peer.connected and peer.session is not None:
                try:
                    await self._write(peer.session, message)
                except Exception:
                    pass

    # -- discovery callbacks (run on the P2P loop) ------------------------------------
    def _on_discovered(self, node: DiscoveredNode) -> None:
        self.bus.publish("node.discovered", address=node.address, port=node.port,
                         node_hint=node.node_id[:12], source=node.source)
        if node.node_id and node.node_id in self.peers and self.peers[node.node_id].connected:
            return
        # Tie-break: the lower node_id dials now; the other waits, then dials
        # only if no session exists (covers a firewalled lower node).
        delay = 0.0
        if node.node_id and node.node_id < self.node_id:
            delay = DIAL_BACKOFF_S
        self._spawn(self._dial_later(node, delay))

    def _on_removed(self, node: DiscoveredNode) -> None:
        self.bus.publish("node.goodbye", node_hint=node.node_id[:12],
                         address=node.address)

    async def _dial_later(self, node: DiscoveredNode, delay: float) -> None:
        if delay:
            await asyncio.sleep(delay)
        peer = self.peers.get(node.node_id) if node.node_id else None
        if peer is not None and peer.connected:
            return
        await self._connect(node.address, node.port, source="mdns")

    # -- connections -----------------------------------------------------------------
    async def _connect(self, host: str, port: int, source: str = "manual",
                       *, timeout: float | None = None) -> Peer | None:
        key = f"{host}:{port}"
        if key in self._dialing:
            return None
        if port == self.listen_port and host in ("127.0.0.1", "localhost", "::1"):
            return None
        if len([p for p in self.peers.values() if p.connected]) >= MAX_PEERS:
            self.bus.publish("node.rejected", address=host, reason="max peers")
            return None
        self._dialing.add(key)
        try:
            self.handshake.advertisement = self._advertisement()
            self.handshake.join_token = ""
            if self.circles is not None:
                try:
                    self.handshake.join_token = self.circles.pending_join_token(
                        host, port)
                except Exception:
                    self.handshake.join_token = ""
            hello_msg, nonce = self.handshake.build_hello()
            try:
                # The short direct-probe timeout applies only when a caller
                # asks for it (``ensure_peer`` before a relay fallback). A
                # manual or discovered connection keeps the handshake
                # timeout: a first TLS connection on a slow or cold machine
                # (the Windows CI runner) takes longer than two seconds.
                session, ack_message, observed = await dial(
                    host, port, hello_msg,
                    timeout=float(timeout or HELLO_TIMEOUT_S))
            except Exception as exc:
                self.bus.publish("node.handshake_failed", address=host, port=port,
                                 reason=f"unreachable: {str(exc)[:80]}")
                return None
            try:
                result = self.handshake.verify_ack(ack_message, nonce, observed)
                if result.node_id == self.node_id:
                    raise ValueError("connected to ourselves")
                final_ack = self.handshake.build_final_ack(
                    _nonce_bytes(ack_message.get("nonce", "")), observed,
                    self.handshake.advertisement)
                await write_frame(session.writer, final_ack)
            except Exception as exc:
                session.close()
                self.bus.publish("node.handshake_failed", address=host, port=port,
                                 reason=str(exc)[:120])
                return None
            session.port = port
            return await self._register(result, session, source=source,
                                        listen_port=port)
        finally:
            self.handshake.join_token = ""
            self._dialing.discard(key)

    def connect_manual(self, host: str, port: int, wait: bool = False):
        if self._loop is None:
            return None
        if self.discovery is not None:
            self.discovery.add_manual(host, port)
        future = asyncio.run_coroutine_threadsafe(
            self._connect(host, port, source="manual"), self._loop)
        if wait:
            peer = future.result(timeout=20)
            return peer.to_dict() if peer else None
        return None

    async def _on_session(self, session: PeerSession,
                          hello_message: dict[str, Any]) -> None:
        """Inbound session: continue the handshake from hello_ack."""
        try:
            if len([p for p in self.peers.values() if p.connected]) >= MAX_PEERS:
                raise ValueError("max peers")
            self.handshake.advertisement = self._advertisement()
            ack_message, own_nonce = self.handshake.build_hello_ack(hello_message)
            await write_frame(session.writer, ack_message)
            final_ack = await read_frame_with_timeout(session.reader, 10.0)
            result = self.handshake.verify_final_ack(
                final_ack, str(hello_message.get("node_id", "")), own_nonce)
            if result.node_id == self.node_id:
                raise ValueError("connected to ourselves")
            await self._register(result, session, source="inbound",
                                 listen_port=_listen_port(result.advertisement),
                                 join_token=str(hello_message.get("join_token") or ""))
        except Exception as exc:
            session.close()
            self.bus.publish("node.handshake_failed", address=session.address,
                             reason=str(exc)[:120])

    async def _register(self, result: HandshakeResult, session: PeerSession,
                        source: str, listen_port: int | None,
                        join_token: str = "") -> Peer | None:
        node_id = result.node_id
        advertisement = result.advertisement
        problems = validate_advertisement(advertisement, expected_node_id=node_id)
        if problems:
            session.close()
            self.bus.publish("node.rejected", node_id=node_id[:12],
                             reason="; ".join(problems[:2]))
            return None
        # Unknown roles and roles naming a model this peer does not offer are
        # dropped after the signature check: they must reach neither placement
        # nor the UI (forward compatibility, D-018).
        advertisement = normalise_advertisement(advertisement)
        admitted = True
        if self.circles is not None:
            ok, code, detail = self.circles.admit(node_id, advertisement)
            if not ok:
                # A valid invitation (or a pending join addressed to this
                # owner) opens a control-only bootstrap session. It is never
                # an admitted peer: dispatch skips it and the worker gate
                # refuses every task until a manifest lists both nodes.
                bootstrap = self.circles.bootstrap_allowed(
                    node_id, join_token) or self.circles.stale_bootstrap_allowed(
                    node_id, advertisement)
                if not bootstrap:
                    try:
                        await self._write(session, error(code, detail, None))
                    except Exception:
                        pass
                    session.close()
                    self.bus.publish(
                        "node.rejected", node_id=node_id[:12],
                        reason=f"{code}: {detail}")
                    return None
                admitted = False
                self.bus.publish("node.bootstrap", node_id=node_id,
                                 short_id=node_id[:12],
                                 address=session.address, source=source)
        session.node_id = node_id
        session.write_lock = asyncio.Lock()
        session.connected_at = time.time()
        peer = self.peers.get(node_id)
        if peer is not None and peer.connected and peer.session is not None \
                and peer.session is not session:
            # Duplicate session: keep the one initiated by the lower node_id.
            new_by_lower = (session.initiator and self.node_id < node_id) or \
                           (not session.initiator and node_id < self.node_id)
            if not new_by_lower:
                session.close()
                return peer
            old = peer.session
            peer.session = None
            old.close()
        if peer is None:
            peer = Peer(node_id=node_id, address=session.address,
                        port=listen_port or session.port, source=source)
            self.peers[node_id] = peer
        peer.address = session.address
        if listen_port:
            peer.port = listen_port
        peer.advertisement = advertisement
        peer.connected = True
        peer.authenticated = True
        peer.admitted = admitted
        peer.last_seen = time.time()
        peer.session = session
        # D-016: a relayed session is admitted by exactly the same manifest
        # gate as a direct one; only its transport hop is recorded here.
        hop = getattr(session, "relay_hop", None)
        peer.transport = "relayed" if hop else "direct"
        peer.relay = dict(hop) if hop else None
        if self.discovery is not None and admitted:
            self.discovery.mark_verified(node_id, session.address)
        self.db.upsert_node(node_id, peer.address, peer.port,
                            verified=True, profile=advertisement)
        self.bus.publish("node.connected", node_id=node_id,
                         short_id=node_id[:12], address=peer.address,
                         source=source, worker=peer.is_worker,
                         admitted=admitted, transport=peer.transport,
                         relay=peer.relay)
        self._spawn(self._read_loop(session, node_id))
        if self.circles is not None:
            self._spawn(self.circles.on_peer_connected(peer))
        return peer

    async def _read_loop(self, session: PeerSession, node_id: str) -> None:
        try:
            while True:
                message = await read_frame(session.reader)
                peer = self.peers.get(node_id)
                if peer is not None:
                    peer.last_seen = time.time()
                await self._route(node_id, session, message)
        except (asyncio.CancelledError, GeneratorExit):
            pass
        except Exception:
            pass
        finally:
            peer = self.peers.get(node_id)
            if peer and peer.session is session:
                peer.connected = False
                peer.session = None
                self._fail_pending_for(node_id)
                self.bus.publish("node.disconnected", node_id=node_id,
                                 short_id=node_id[:12])
            session.close()

    async def _write(self, session: PeerSession, message: dict[str, Any]) -> None:
        lock = session.write_lock
        if lock is None:
            await write_frame(session.writer, message)
            return
        async with lock:
            await write_frame(session.writer, message)

    async def _route(self, node_id: str, session: PeerSession,
                     message: dict[str, Any]) -> None:
        mtype = message.get("type")
        if mtype == "task":
            # Never serve inside the read loop: results and pings must keep flowing.
            self._spawn(self._handle_task(node_id, session, message))
        elif mtype in ("result", "error"):
            attempt_id = str(message.get("attempt_id", ""))
            with self._pending_lock:
                future = self._pending.pop(attempt_id, None)
            if future is not None and not future.done():
                if mtype == "result":
                    future.set_result(message)
                else:
                    future.set_exception(PeerError(
                        str(message.get("code", "")), str(message.get("detail", ""))))
        elif mtype == "cancel":
            # The requester no longer waits for this attempt (app extension;
            # older nodes ignore unknown types, SPEC §3).
            if self._cancel_handler is not None:
                try:
                    self._cancel_handler(node_id, str(message.get("attempt_id", "")))
                except Exception:
                    pass
        elif mtype == "ping":
            await self._write(session, {"v": WIRE_VERSION, "type": "pong",
                                        "echo": message.get("ts")})
        elif mtype == "pong":
            peer = self.peers.get(node_id)
            try:
                sent = float(message.get("echo"))
                if peer is not None:
                    peer.rtt_ms = round((time.monotonic() - sent) * 1000, 1)
            except (TypeError, ValueError):
                pass
        elif mtype == "advertisement_update":
            peer = self.peers.get(node_id)
            if peer is None or not verify_advertisement_update(node_id, message):
                return
            seq = int(message.get("seq", 0) or 0)
            adv = message.get("advertisement") or {}
            if seq <= peer.adv_seq or validate_advertisement(adv, node_id):
                return
            peer.adv_seq = seq
            peer.advertisement = normalise_advertisement(adv)
            self.bus.publish("node.updated", node_id=node_id,
                             short_id=node_id[:12], worker=peer.is_worker)
        elif mtype in CONTROL_TYPES:
            # D-021: circle control rides on the same TLS session; older
            # nodes ignore an unknown type (SPEC §3).
            if self.circles is not None:
                try:
                    reply = await self.circles.handle_control(node_id, message)
                    if reply is not None:
                        await self._write(session, reply)
                except CircleError as exc:
                    try:
                        await self._write(session, error(
                            exc.code, exc.detail, message.get("attempt_id")))
                    except Exception:
                        pass
                except Exception as exc:
                    try:
                        await self._write(session, error(
                            "E_CIRCLE_SCHEMA", str(exc)[:160],
                            message.get("attempt_id")))
                    except Exception:
                        pass
        # Unknown types are ignored (SPEC §3: MINOR additions are tolerated).

    async def _handle_task(self, node_id: str, session: PeerSession,
                           message: dict[str, Any]) -> None:
        attempt_id = str(message.get("attempt_id", ""))
        peer = self.peers.get(node_id)
        reply: dict[str, Any]
        if peer is None:
            return
        if attempt_id in peer.seen_attempts:
            reply = error("E_DUPLICATE", "attempt_id already received", attempt_id)
        elif peer.tasks_inflight >= MAX_QUEUED_TASKS_PER_PEER:
            reply = error("E_POLICY", "too many tasks queued from this peer",
                          attempt_id)
        elif self._task_handler is None:
            reply = error("E_POLICY", "worker role disabled", attempt_id)
        else:
            peer.seen_attempts[attempt_id] = time.time()
            while len(peer.seen_attempts) > REPLAY_WINDOW:
                peer.seen_attempts.popitem(last=False)
            peer.tasks_inflight += 1
            try:
                reply = await self._task_handler(node_id, message)
            except Exception as exc:
                reply = error("E_POLICY", f"worker error: {str(exc)[:120]}",
                              attempt_id)
            finally:
                peer.tasks_inflight -= 1
        try:
            await self._write(session, reply)
        except Exception:
            pass

    async def _keepalive_loop(self) -> None:
        while True:
            await asyncio.sleep(KEEPALIVE_S)
            now = time.time()
            for peer in list(self.peers.values()):
                if not peer.connected or peer.session is None:
                    continue
                if now - peer.last_seen > DEAD_AFTER_S:
                    peer.session.close()
                    continue
                try:
                    await self._write(peer.session, {"v": WIRE_VERSION, "type": "ping",
                                                     "ts": time.monotonic()})
                except Exception:
                    peer.session.close()

    def _fail_pending_for(self, node_id: str) -> None:
        with self._pending_lock:
            items = [(a, f) for a, f in self._pending.items()
                     if getattr(f, "node_id", None) == node_id]
            for attempt_id, _ in items:
                self._pending.pop(attempt_id, None)
        for _, future in items:
            if not future.done():
                future.set_exception(PeerError("E_DISCONNECTED",
                                               "peer disconnected"))

    # -- relay registration and pairing (3.5, WP3 / D-016, D-023) -----------------
    @staticmethod
    def _relay_key(circle_id: str, relay: dict[str, Any]) -> str:
        return (f"{circle_id}|{relay.get('host')}|{relay.get('port')}|"
                f"{relay.get('tls_cert_sha256')}")

    def _relay_max_connections(self) -> int:
        try:
            value = int(self.config.get("circle.relay_max_connections") or 4)
        except (TypeError, ValueError):
            value = 4
        return max(1, min(value, 16))

    def _relay_timeout_s(self) -> float:
        try:
            value = float(self.config.get("circle.relay_timeout_s") or 8.0)
        except (TypeError, ValueError):
            value = 8.0
        return max(3.0, min(value, 30.0))

    def _direct_timeout_s(self) -> float:
        try:
            value = float(self.config.get("circle.reach_timeout_s") or 2.0)
        except (TypeError, ValueError):
            value = 2.0
        return max(0.5, min(value, 15.0))

    def _desired_relays(self) -> dict[str, dict[str, Any]]:
        """Relays this node should keep an acceptor connection for.

        Off by default: a circle without a relay contributes nothing. Only a
        current, unexpired manifest that lists this node counts.
        """
        if self.circles is None:
            return {}
        out: dict[str, dict[str, Any]] = {}
        for circle_id, manifest in list(self.circles.manifests.items()):
            try:
                if not self.circles._valid(manifest):
                    continue
                if not self.circles._is_member(manifest, self.node_id):
                    continue
            except Exception:
                continue
            relay = manifest.get("relay")
            if not isinstance(relay, dict):
                continue
            try:
                from .circles import normalise_relay
                clean = normalise_relay(relay)
            except Exception:
                clean = None
            if clean:
                out[str(circle_id)] = clean
        return out

    def refresh_relays(self) -> None:
        """Wake the supervisor after a manifest change (thread-safe)."""
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(self._wake_relay_supervisor)

    def _wake_relay_supervisor(self) -> None:
        if self._relay_event is not None:
            self._relay_event.set()

    async def _relay_wait(self, timeout: float = 5.0) -> None:
        if self._relay_event is None:
            await asyncio.sleep(timeout)
            return
        try:
            await asyncio.wait_for(self._relay_event.wait(), timeout)
        except asyncio.TimeoutError:
            pass
        self._relay_event.clear()

    async def _relay_supervisor(self) -> None:
        """Keep exactly the relay acceptors the current manifests ask for."""
        while not self._relay_stopping:
            try:
                desired = self._desired_relays()
                wanted = {self._relay_key(cid, relay)
                          for cid, relay in desired.items()}
                for key, task in list(self._relay_tasks.items()):
                    if key not in wanted:
                        task.cancel()
                        self._relay_tasks.pop(key, None)
                for cid, relay in desired.items():
                    key = self._relay_key(cid, relay)
                    task = self._relay_tasks.get(key)
                    if task is not None and not task.done():
                        continue
                    if len(self._relay_tasks) >= self._relay_max_connections():
                        self._relay_state[cid] = {
                            "circle_id": cid, "status": "limited",
                            "host": relay.get("host", ""),
                            "port": relay.get("port", 0),
                            "last_error": ("too many relay circles; raise "
                                           "circle.relay_max_connections"),
                            "security_warning": False,
                        }
                        continue
                    task = self._spawn(self._relay_acceptor_loop(cid, relay))
                    self._relay_tasks[key] = task
                    task.add_done_callback(
                        lambda _t, k=key: self._relay_tasks.pop(k, None))
                for cid in list(self._relay_state):
                    if cid not in desired:
                        self._relay_state.pop(cid, None)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # one bad manifest never kills the loop
                self.bus.publish("relay.supervisor_error",
                                 reason=str(exc)[:160])
            await self._relay_wait()
        for task in list(self._relay_tasks.values()):
            task.cancel()
        self._relay_tasks.clear()

    def _relay_state_for(self, circle_id: str, relay: dict[str, Any]) -> dict[str, Any]:
        return self._relay_state.setdefault(circle_id, {
            "circle_id": circle_id, "status": "off",
            "host": relay.get("host", ""), "port": relay.get("port", 0),
            "last_error": "", "security_warning": False,
        })

    async def _relay_acceptor_loop(self, circle_id: str,
                                   relay: dict[str, Any]) -> None:
        """One idle registered connection per (circle, relay), reconnecting.

        The prototype can accept one incoming splice per connection, so after
        a pair the loop opens a fresh registered connection immediately. A
        pin mismatch stops this relay and stays visible until the manifest
        changes; a transient failure backs off.
        """
        backoff = RELAY_BACKOFF_S
        address = RelayAddress(str(relay["host"]), int(relay["port"]),
                               str(relay["tls_cert_sha256"]))
        while not self._relay_stopping:
            if self._desired_relays().get(circle_id) != relay:
                return
            state = self._relay_state_for(circle_id, relay)
            state.update(host=str(relay["host"]), port=int(relay["port"]))
            if state.get("security_warning"):
                await self._relay_wait(15.0)
                continue
            client = RelayClient(
                address, circle_id, self.node_id, self.identity_manager.sign,
                timeout=self._relay_timeout_s(),
                pair_timeout=60.0)
            self._relay_clients.add(client)
            try:
                await client.connect()
            except RelayError as exc:
                await client.close()
                self._relay_clients.discard(client)
                if exc.code == "relay_certificate_mismatch":
                    state.update(status="security_warning",
                                 security_warning=True,
                                 last_error=f"{exc.code}: {exc.message}")
                    self.bus.publish("relay.security_warning",
                                     circle_id=circle_id,
                                     host=address.host, port=address.port,
                                     reason=exc.message,
                                     code=exc.code)
                    await self._relay_wait(15.0)
                    continue
                state.update(status="down",
                             last_error=f"{exc.code}: {exc.message}")
                self.bus.publish("relay.down", circle_id=circle_id,
                                 host=address.host, port=address.port,
                                 code=exc.code, reason=exc.message)
                await asyncio.sleep(backoff)
                backoff = min(RELAY_BACKOFF_MAX_S, backoff * 2)
                continue
            except asyncio.CancelledError:
                await client.close()
                self._relay_clients.discard(client)
                raise
            except Exception as exc:
                await client.close()
                self._relay_clients.discard(client)
                state.update(status="down", last_error=str(exc)[:160])
                self.bus.publish("relay.down", circle_id=circle_id,
                                 host=address.host, port=address.port,
                                 code="E_RELAY_UNREACHABLE",
                                 reason=str(exc)[:160])
                await asyncio.sleep(backoff)
                backoff = min(RELAY_BACKOFF_MAX_S, backoff * 2)
                continue

            backoff = RELAY_BACKOFF_S
            state.update(status="connected", last_error="",
                         security_warning=False)
            self.bus.publish("relay.connected", circle_id=circle_id,
                             host=address.host, port=address.port)
            handed = False
            try:
                stream = await client.accept_pair(
                    check=lambda peer_id, pair_circle: self._relay_pair_allowed(
                        circle_id, peer_id, pair_circle))
            except asyncio.CancelledError:
                await client.close()
                self._relay_clients.discard(client)
                raise
            except RelayRefused as exc:
                state.update(status="refused",
                             last_error=f"{exc.code}: {exc.message}")
                self.bus.publish("relay.refused", circle_id=circle_id,
                                 host=address.host, code=exc.code,
                                 reason=exc.message)
                await client.close()
                self._relay_clients.discard(client)
                await asyncio.sleep(0.2)
                continue
            except RelayError as exc:
                state.update(status="error",
                             last_error=f"{exc.code}: {exc.message}")
                self.bus.publish("relay.error", circle_id=circle_id,
                                 host=address.host, code=exc.code,
                                 reason=exc.message)
                await client.close()
                self._relay_clients.discard(client)
                continue
            except Exception as exc:
                state.update(status="error", last_error=str(exc)[:160])
                await client.close()
                self._relay_clients.discard(client)
                await asyncio.sleep(0.2)
                continue
            if stream is not None:
                handed = True
                self._spawn(self._handle_relayed_incoming(
                    stream, circle_id, relay, client))
            if not handed:
                await client.close()
                self._relay_clients.discard(client)

    def _relay_pair_allowed(self, circle_id: str, peer_node_id: str,
                            pair_circle_id: str = "") -> bool:
        """The App's own admission check before an explicit ``pair_accept``."""
        if not peer_node_id or peer_node_id == self.node_id:
            return False
        if pair_circle_id and pair_circle_id != circle_id:
            return False
        if self.circles is None:
            return False
        manifest = self.circles.manifests.get(circle_id)
        if manifest is None or not self.circles._valid(manifest):
            return False
        if not self.circles._is_member(manifest, self.node_id):
            return False
        if not self.circles._is_member(manifest, peer_node_id):
            return False
        ok, _code, _detail = self.circles.admits_local(peer_node_id)
        return bool(ok)

    async def _handle_relayed_incoming(self, stream: Any, circle_id: str,
                                       relay: dict[str, Any],
                                       client: RelayClient) -> None:
        session = None
        try:
            cert_dir = self._data_dirs().cache / "tls"
            session, hello = await accept_over_stream(
                stream, cert_dir / "node.crt", cert_dir / "node.key",
                address=f"relay:{relay['host']}", timeout=30.0)
            session.relay_hop = {
                "kind": "relayed", "host": str(relay["host"]),
                "port": int(relay["port"]), "metadata_only": True,
            }
            await self._on_session(session, hello)
            peer = self.peers.get(session.node_id)
            if peer is None or peer.session is not session:
                session.close()
        except asyncio.CancelledError:
            if session is not None:
                session.close()
            raise
        except Exception as exc:
            if session is not None:
                session.close()
            self.bus.publish("relay.handshake_failed", circle_id=circle_id,
                             host=str(relay.get("host") or ""),
                             reason=str(exc)[:160])
        finally:
            self._relay_clients.discard(client)
            peer = self.peers.get(session.node_id) if session is not None else None
            if peer is None or peer.session is not session:
                await client.close()

    def _direct_candidates(self, node_id: str) -> list[tuple[str, int]]:
        out: list[tuple[str, int]] = []
        peer = self.peers.get(node_id)
        if peer is not None and peer.address and peer.transport == "direct":
            out.append((peer.address, int(peer.port or 0)))
        if self.discovery is not None:
            for node in self.discovery.entries():
                if node.node_id == node_id:
                    for addr in (node.addresses or [node.address]):
                        out.append((addr, int(node.port or 0)))
        if self.circles is not None:
            for manifest in list(self.circles.manifests.values()):
                try:
                    if not self.circles._valid(manifest):
                        continue
                    if not self.circles._is_member(manifest, self.node_id):
                        continue
                except Exception:
                    continue
                member = self.circles._member(manifest, node_id)
                for endpoint in (member or {}).get("endpoints") or []:
                    try:
                        from .circles import endpoint_host_port
                        out.append(endpoint_host_port(endpoint))
                    except Exception:
                        continue
        clean: list[tuple[str, int]] = []
        for host, port in out:
            if not host or not 0 < port < 65536:
                continue
            if port == self.listen_port and host in (
                    "127.0.0.1", "localhost", "::1", "0.0.0.0", "::"):
                continue
            if (host, port) not in clean:
                clean.append((host, port))
        return clean

    def _relay_candidates(self, node_id: str) -> list[tuple[str, dict[str, Any]]]:
        if self.circles is None:
            return []
        out: list[tuple[str, dict[str, Any]]] = []
        for circle_id, manifest in list(self.circles.manifests.items()):
            try:
                if not self.circles._valid(manifest):
                    continue
                if not self.circles._is_member(manifest, self.node_id):
                    continue
                if not self.circles._is_member(manifest, node_id):
                    continue
            except Exception:
                continue
            relay = manifest.get("relay")
            if isinstance(relay, dict) and relay.get("host") \
                    and relay.get("tls_cert_sha256"):
                out.append((str(circle_id), {
                    "host": str(relay["host"]), "port": int(relay["port"]),
                    "tls_cert_sha256": str(relay["tls_cert_sha256"])}))
        out.sort(key=lambda item: str(
            self.circles.manifests[item[0]].get("name") or "").casefold())
        return out

    async def _dial_via_relay(self, node_id: str, circle_id: str,
                              relay: dict[str, Any], timeout: float
                              ) -> Peer | None:
        address = RelayAddress(str(relay["host"]), int(relay["port"]),
                               str(relay["tls_cert_sha256"]))
        client = RelayClient(
            address, circle_id, self.node_id, self.identity_manager.sign,
            timeout=min(max(3.0, timeout), 15.0),
            pair_timeout=max(10.0, timeout))
        self._relay_clients.add(client)
        session = None
        try:
            await client.connect()
            stream = await client.pair(node_id)
            self.handshake.advertisement = self._advertisement()
            self.handshake.join_token = ""
            hello_msg, nonce = self.handshake.build_hello()
            session, ack_message, observed = await dial_over_stream(
                stream, hello_msg, address=f"relay:{address.host}",
                timeout=timeout)
            result = self.handshake.verify_ack(ack_message, nonce, observed)
            if result.node_id == self.node_id:
                raise ValueError("connected to ourselves")
            if result.node_id != node_id:
                # The relay splices whoever it chooses; the end-to-end
                # handshake says who is really there. A different member is
                # not the one this node asked for, so the session is dropped
                # instead of being registered under a wrong expectation.
                raise ValueError("the relay paired this node with another node")
            final_ack = self.handshake.build_final_ack(
                _nonce_bytes(ack_message.get("nonce", "")), observed,
                self.handshake.advertisement)
            await write_frame(session.writer, final_ack)
            session.relay_hop = {
                "kind": "relayed", "host": address.host,
                "port": address.port, "metadata_only": True,
            }
            return await self._register(
                result, session, source="relay",
                listen_port=_listen_port(result.advertisement))
        except Exception as exc:
            state = self._relay_state_for(circle_id, relay)
            state.update(status="error", last_error=str(exc)[:160])
            if isinstance(exc, RelayRefused):
                self.bus.publish("relay.refused", circle_id=circle_id,
                                 host=address.host, code=exc.code,
                                 reason=exc.message)
            self.bus.publish("relay.pair_failed", circle_id=circle_id,
                             host=address.host, peer_node=node_id[:12],
                             reason=f"{type(exc).__name__}: "
                                    f"{getattr(exc, 'code', 'E_RELAY')}: "
                                    f"{getattr(exc, 'message', str(exc))}"[:160])
            if session is not None:
                session.close()
            return None
        finally:
            self.handshake.join_token = ""
            self._relay_clients.discard(client)
            peer = self.peers.get(session.node_id) if session is not None else None
            if peer is None or peer.session is not session:
                await client.close()

    def ensure_circle_peers(self, limit: int = 8) -> int:
        """Before planning, reach members of circles that have a relay.

        Placement only sees connected workers. This makes a relay-reachable
        circle member visible *before* the plan is built, while direct
        addresses are still tried first inside :meth:`ensure_peer`. Circles
        without a relay are left to discovery/manual connection.
        """
        if self.circles is None:
            return 0
        wanted: set[str] = set()
        for circle_id, manifest in list(self.circles.manifests.items()):
            try:
                relay = manifest.get("relay")
                if not isinstance(relay, dict) or not relay.get("host"):
                    continue
                if not self.circles._valid(manifest):
                    continue
                if not self.circles._is_member(manifest, self.node_id):
                    continue
            except Exception:
                continue
            for member in manifest.get("members") or []:
                node_id = str(member.get("node_id") or "")
                if node_id and node_id != self.node_id:
                    wanted.add(node_id)
        if not wanted:
            return 0
        try:
            return int(self._call(
                self._ensure_circle_peers_async(sorted(wanted), limit),
                timeout=20.0 + 20.0 * min(limit, 8)))
        except Exception:
            return 0

    async def _ensure_circle_peers_async(self, node_ids: list[str],
                                         limit: int) -> int:
        sem = asyncio.Semaphore(max(1, limit))

        async def one(node_id: str) -> int:
            peer = self.peers.get(node_id)
            if peer is not None and peer.connected:
                return 0
            async with sem:
                got = await self.ensure_peer(node_id)
            return 1 if got is not None and got.connected else 0

        results = await asyncio.gather(*(one(nid) for nid in node_ids),
                                       return_exceptions=True)
        return sum(1 for item in results if item == 1)

    async def ensure_peer(self, node_id: str) -> Peer | None:
        """Reach a circle member: direct addresses first, then its relay.

        The direct attempts are short and bounded. A relay that is down or
        refuses never affects peers that are already reachable directly.
        """
        peer = self.peers.get(node_id)
        if peer is not None and peer.connected:
            return peer
        direct_timeout = self._direct_timeout_s()
        for host, port in self._direct_candidates(node_id):
            try:
                candidate = await self._connect(host, port, source="manual",
                                                timeout=direct_timeout)
            except Exception:
                candidate = None
            if candidate is not None and candidate.node_id == node_id \
                    and candidate.connected:
                return candidate
        last_error = ""
        for circle_id, relay in self._relay_candidates(node_id):
            state = self._relay_state_for(circle_id, relay)
            state.update(host=str(relay["host"]), port=int(relay["port"]))
            if state.get("security_warning"):
                last_error = "relay stopped after a certificate pin mismatch"
                continue
            got = await self._dial_via_relay(
                node_id, circle_id, relay, timeout=self._relay_timeout_s())
            if got is not None and got.connected:
                return got
            last_error = str(state.get("last_error") or "")
        if last_error:
            self.bus.publish("node.reach_failed", node_id=node_id[:12],
                             reason=last_error[:160])
        return None

    # -- owner manifest push (3.5, D-023) -------------------------------------
    @staticmethod
    def _relay_push_key(circle_id: str, relay: dict[str, Any]) -> str:
        return (f"{circle_id}|{relay.get('host')}|{relay.get('port')}|"
                f"{relay.get('tls_cert_sha256')}")

    def _relay_push_backoff(self) -> float:
        try:
            value = float(self.config.get("circle.relay_push_backoff_s") or 1.0)
        except (TypeError, ValueError):
            value = 1.0
        return max(0.1, min(value, 30.0))

    def _relay_push_backoff_max(self) -> float:
        try:
            value = float(self.config.get(
                "circle.relay_push_backoff_max_s") or 30.0)
        except (TypeError, ValueError):
            value = 30.0
        return max(self._relay_push_backoff(), min(value, 300.0))

    def _relay_push_refusal_retry(self) -> float:
        try:
            value = float(self.config.get(
                "circle.relay_push_refusal_retry_s") or 300.0)
        except (TypeError, ValueError):
            value = 300.0
        return max(5.0, min(value, 3600.0))

    def _relay_push_state_for(self, key: str, circle_id: str,
                              relay: dict[str, Any]) -> dict[str, Any]:
        with self._relay_push_lock:
            state = self._relay_push_state.setdefault(key, {
                "circle_id": circle_id,
                "host": str(relay.get("host") or ""),
                "port": int(relay.get("port") or 0),
                "tls_cert_sha256": str(relay.get("tls_cert_sha256") or ""),
                "status": "queued",
                "acknowledged_version": 0,
                "pending_version": 0,
                "last_refusal": "",
                "last_error": "",
                "updated_at": time.time(),
            })
            state.update(host=str(relay.get("host") or ""),
                         port=int(relay.get("port") or 0),
                         tls_cert_sha256=str(
                             relay.get("tls_cert_sha256") or ""))
            return state

    def queue_relay_push(self, circle_id: str, manifest: dict[str, Any],
                         relays: list[dict[str, Any]] | None = None) -> int:
        """Queue the newest signed manifest for one or more relay targets.

        Owner-only by construction: a node that is not the manifest's owner
        never queues or sends a push, and the relay would refuse it anyway.
        ``relays`` lets a relay change push the same new version to the old
        relay first, then the new one. Only the newest version per target is
        kept; a newer version replaces an older pending one.
        """
        if self.circles is None:
            return 0
        if str(manifest.get("owner") or "") != self.node_id:
            return 0
        try:
            version = int(manifest.get("version") or 0)
        except (TypeError, ValueError):
            return 0
        if version <= 0:
            return 0
        from .circles import normalise_relay
        targets: list[dict[str, Any]] = []
        for relay in relays if relays is not None else [manifest.get("relay")]:
            try:
                clean = normalise_relay(relay)
            except Exception:
                clean = None
            if clean and clean not in targets:
                targets.append(clean)
        queued = 0
        with self._relay_push_lock:
            for relay in targets:
                key = self._relay_push_key(circle_id, relay)
                state = self._relay_push_state_for(key, circle_id, relay)
                current = self._relay_push_queue.get(key)
                if current is not None and int(current.get("version") or 0) >= version:
                    continue
                if int(state.get("acknowledged_version") or 0) >= version:
                    continue
                self._relay_push_queue[key] = {
                    "circle_id": circle_id,
                    "relay": dict(relay),
                    "manifest": manifest,
                    "version": version,
                    "queued_at": time.time(),
                }
                state.update(status="queued", pending_version=version,
                             last_refusal="", last_error="",
                             updated_at=time.time())
                queued += 1
        if queued:
            self.bus.publish("relay.push_queued", circle_id=circle_id,
                             version=version, targets=len(targets))
            self.refresh_relay_pushes()
        return queued

    def refresh_relay_pushes(self) -> None:
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(self._wake_relay_push)

    def _wake_relay_push(self) -> None:
        if self._relay_push_event is not None:
            self._relay_push_event.set()

    async def _relay_push_wait(self, timeout: float = 5.0) -> None:
        if self._relay_push_event is None:
            await asyncio.sleep(timeout)
            return
        try:
            await asyncio.wait_for(self._relay_push_event.wait(), timeout)
        except asyncio.TimeoutError:
            pass
        self._relay_push_event.clear()

    async def _relay_push_supervisor(self) -> None:
        while not self._relay_stopping:
            try:
                with self._relay_push_lock:
                    keys = list(self._relay_push_queue)
                for key in keys:
                    task = self._relay_push_tasks.get(key)
                    if task is not None and not task.done():
                        continue
                    task = self._spawn(self._relay_push_loop(key))
                    self._relay_push_tasks[key] = task
                    task.add_done_callback(
                        lambda _t, k=key: self._relay_push_tasks.pop(k, None))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.bus.publish("relay.push_supervisor_error",
                                 reason=str(exc)[:160])
            await self._relay_push_wait()
        for task in list(self._relay_push_tasks.values()):
            task.cancel()
        self._relay_push_tasks.clear()

    async def _relay_push_pause(self, seconds: float, key: str,
                                version: int) -> None:
        """Sleep, but wake early when a newer version replaces this one."""
        deadline = asyncio.get_running_loop().time() + max(0.0, seconds)
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return
            await asyncio.sleep(min(1.0, remaining))
            with self._relay_push_lock:
                current = self._relay_push_queue.get(key)
            if current is None or int(current.get("version") or 0) != version:
                return

    def _drop_relay_push(self, key: str, version: int) -> None:
        with self._relay_push_lock:
            current = self._relay_push_queue.get(key)
            if current is not None and int(current.get("version") or 0) <= version:
                self._relay_push_queue.pop(key, None)

    async def _relay_push_loop(self, key: str) -> None:
        """Push the newest queued version, with backoff while unreachable."""
        base = self._relay_push_backoff()
        maximum = self._relay_push_backoff_max()
        backoff = base
        last_version = 0
        while not self._relay_stopping:
            with self._relay_push_lock:
                item = dict(self._relay_push_queue.get(key) or {})
            if not item:
                return
            circle_id = str(item["circle_id"])
            relay = dict(item["relay"])
            manifest = item["manifest"]
            version = int(item["version"])
            if version != last_version:
                last_version = version
                backoff = base
            state = self._relay_push_state_for(key, circle_id, relay)
            with self._relay_push_lock:
                state.update(status="pushing", pending_version=version,
                             updated_at=time.time())
            address = RelayAddress(str(relay["host"]), int(relay["port"]),
                                   str(relay["tls_cert_sha256"]))
            client = RelayClient(
                address, circle_id, self.node_id, self.identity_manager.sign,
                timeout=max(3.0, self._relay_timeout_s()))
            self._relay_clients.add(client)
            try:
                await client.connect()
                ack = await client.push_manifest(manifest)
            except RelayRefused as exc:
                code = exc.code
                with self._relay_push_lock:
                    state.update(status="refused", last_refusal=code,
                                 last_error=exc.message,
                                 pending_version=version,
                                 updated_at=time.time())
                self.bus.publish("relay.push_refused", circle_id=circle_id,
                                 host=address.host, port=address.port,
                                 code=code, reason=exc.message,
                                 version=version)
                if code in ("unknown_circle", "rate_limited", "persist_failed",
                            "not_a_member"):
                    await self._relay_push_pause(
                        self._relay_push_refusal_retry(), key, version)
                    continue
                self._drop_relay_push(key, version)
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                with self._relay_push_lock:
                    state.update(status="unreachable",
                                 last_error=f"{getattr(exc, 'code', 'E_RELAY')}: "
                                            f"{getattr(exc, 'message', str(exc))}"[:160],
                                 pending_version=version,
                                 updated_at=time.time())
                self.bus.publish("relay.push_unreachable", circle_id=circle_id,
                                 host=address.host, port=address.port,
                                 code=str(getattr(exc, "code", "E_RELAY")),
                                 reason=str(exc)[:160], version=version)
                await self._relay_push_pause(backoff, key, version)
                backoff = min(maximum, max(base, backoff * 2))
                continue
            finally:
                self._relay_clients.discard(client)
                try:
                    await client.close()
                except Exception:
                    pass
            ack_version = int(ack.get("version") or version)
            with self._relay_push_lock:
                state.update(status="acknowledged",
                             acknowledged_version=max(
                                 int(state.get("acknowledged_version") or 0),
                                 ack_version),
                             pending_version=0, last_refusal="",
                             last_error="", updated_at=time.time())
                current = self._relay_push_queue.get(key)
                if current is not None and int(
                        current.get("version") or 0) <= ack_version:
                    self._relay_push_queue.pop(key, None)
            self.bus.publish("relay.push_ack", circle_id=circle_id,
                             host=address.host, port=address.port,
                             version=ack_version,
                             member_count=int(ack.get("member_count") or 0))
            backoff = base

    def relay_push_status(self, circle_id: str) -> dict[str, Any]:
        with self._relay_push_lock:
            states = [dict(s) for s in self._relay_push_state.values()
                      if str(s.get("circle_id") or "") == circle_id]
            pending = [dict(q) for q in self._relay_push_queue.values()
                       if str(q.get("circle_id") or "") == circle_id]
        states.sort(key=lambda item: (str(item.get("host") or ""),
                                      int(item.get("port") or 0)))
        current: dict[str, Any] | None = None
        if self.circles is not None:
            manifest = self.circles.manifests.get(circle_id) or {}
            relay = manifest.get("relay") or {}
            for state in states:
                if (str(state.get("host") or "") == str(relay.get("host") or "")
                        and int(state.get("port") or 0)
                        == int(relay.get("port") or 0)
                        and str(state.get("tls_cert_sha256") or "")
                        == str(relay.get("tls_cert_sha256") or "")):
                    current = state
                    break
        if current is None and states:
            current = states[-1]
        pending_versions = sorted({int(q.get("version") or 0) for q in pending
                                   if int(q.get("version") or 0) > 0})
        return {"current": current, "targets": states,
                "pending_versions": pending_versions}

    def transport_hop(self, node_id: str) -> dict[str, Any]:
        """The receipt's transport hop for a peer send."""
        peer = self.peers.get(node_id)
        if peer is not None and peer.transport == "relayed" and peer.relay:
            return {"transport": "relayed", "relay": {
                "host": str(peer.relay.get("host") or ""),
                "port": int(peer.relay.get("port") or 0),
                "metadata_only": True,
                "saw": ["who", "when", "bytes"],
                "content": False,
            }}
        return {"transport": "direct"}

    def relay_status(self, circle_id: str | None = None) -> Any:
        if circle_id is not None:
            state = dict(self._relay_state.get(circle_id) or {
                "circle_id": circle_id, "status": "off",
                "last_error": "", "security_warning": False})
            state["push"] = self.relay_push_status(circle_id)
            return state
        out = []
        for state in sorted(self._relay_state.values(),
                            key=lambda item: str(item.get("circle_id") or "")):
            item = dict(state)
            item["push"] = self.relay_push_status(str(state.get("circle_id") or ""))
            out.append(item)
        return out

    # -- dispatch API (called from engine threads) ---------------------------------------
    def classify_peer(self, node_id: str) -> dict[str, Any]:
        """The destination class of a peer send (D-017), from the circle service."""
        if self.circles is None:
            raise CircleError(E_CIRCLE_REQUIRED,
                              "circle service is not available")
        return self.circles.classify_peer(node_id)

    def dispatch(self, node_id: str, packet_message: dict[str, Any],
                 timeout_s: float = 120.0, *,
                 offer_credit: bool = False) -> dict[str, Any]:
        return self._call(self.dispatch_async(node_id, packet_message, timeout_s,
                                              offer_credit=offer_credit),
                          timeout=timeout_s + 10)

    async def dispatch_async(self, node_id: str, packet_message: dict[str, Any],
                             timeout_s: float, *,
                             offer_credit: bool = False) -> dict[str, Any]:
        """Send one packet and await its result (must run on the P2P loop)."""
        peer = self.peers.get(node_id)
        if peer is None or not peer.connected or peer.session is None:
            # D-016: direct addresses first, then the circle relay. This is
            # deliberately done here, so dispatch and placement keep using the
            # normal Peer object, admission and egress gate once connected.
            peer = await self.ensure_peer(node_id)
        if peer is None or not peer.connected or peer.session is None:
            raise PeerError("E_DISCONNECTED",
                            f"node {node_id[:12]} not connected directly or "
                            "through a circle relay")
        if not peer.admitted:
            raise PeerError("E_CIRCLE_REQUIRED",
                            f"node {node_id[:12]} is not admitted to a circle")
        attempt_id = str(packet_message.get("attempt_id", ""))
        # D-017: every peer send passes the egress gate before a byte is
        # written. The class comes from the circle service, not from the
        # address: a shared circle is CIRCLE, the explicit my-own-devices mode
        # is OWN_NETWORK, and anything else is refused. A refusal raises before
        # ``_write`` below, so no packet reaches the peer.
        refusal: CircleError | None = None
        try:
            destination = self.classify_peer(node_id)
        except CircleError as exc:
            refusal = exc
            destination = {"clase": "", "circle_id": "", "circle_name": "",
                           "member_name": "", "member_node": node_id[:12]}
        carries_passages = bool((packet_message.get("constraints") or {})
                                .get("carries_passages"))
        try:
            egress.check_call(
                f"peer://{node_id}", len(str(packet_message)),
                f"{'pasajes' if carries_passages else 'fragmento'} {attempt_id}",
                kind=(egress.PASSAGES if carries_passages else egress.FRAGMENT),
                destination_class=str(destination.get("clase") or ""),
                destination_label=f"nodo {node_id[:12]}",
                circle_id=destination.get("circle_id", ""),
                circle_name=destination.get("circle_name", ""),
                member_name=destination.get("member_name", ""),
                peer_node=node_id[:12],
                **({"circle_required": True} if refusal is not None else {}))
        except egress.EgressDenied as exc:
            if refusal is not None:
                raise PeerError(refusal.code, refusal.detail) from exc
            raise PeerError("E_EGRESS_DENIED", str(exc)) from exc
        # 3.5, D-020: only after admission and the egress gate accepted the
        # send may this node offer one earned receipt for this exact attempt.
        # The credit can change queue order while the worker is busy; it can
        # never bypass a gate (this line runs after all of them). It is
        # offered only when the caller knows the worker is busy (it refused a
        # task as at its concurrency limit, or missed a deadline): a receipt
        # spent on an idle worker buys nothing.
        credits = getattr(self.circles, "credits", None) if self.circles else None
        if offer_credit and credits is not None \
                and str(destination.get("clase") or "") \
                == egress.CIRCLE and str(destination.get("circle_id") or ""):
            try:
                await credits.present_spend_async(
                    node_id, str(destination["circle_id"]), attempt_id)
            except Exception:
                pass
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        future.node_id = node_id  # type: ignore[attr-defined]
        with self._pending_lock:
            self._pending[attempt_id] = future
        try:
            await self._write(peer.session, packet_message)
            return await asyncio.wait_for(future, timeout=timeout_s)
        except asyncio.TimeoutError:
            self._send_cancel(peer, attempt_id)
            raise PeerError("E_DEADLINE", "worker timeout") from None
        except asyncio.CancelledError:
            self._send_cancel(peer, attempt_id)   # a hedge won, or the user stopped
            raise
        finally:
            with self._pending_lock:
                self._pending.pop(attempt_id, None)

    def _send_cancel(self, peer, attempt_id: str) -> None:
        """Best effort: tell the worker to stop generating for this attempt."""
        session = getattr(peer, "session", None)
        if session is None or not getattr(peer, "connected", False):
            return
        try:
            self._spawn(self._write(session, {"v": WIRE_VERSION, "type": "cancel",
                                              "attempt_id": attempt_id}))
        except Exception:
            pass

    # -- control plane (circles) -------------------------------------------------
    async def send_control_async(self, node_id: str,
                                 message: dict[str, Any]) -> bool:
        peer = self.peers.get(node_id)
        if peer is None or not peer.connected or peer.session is None:
            return False
        await self._write(peer.session, message)
        return True

    def send_control(self, node_id: str, message: dict[str, Any]) -> bool:
        """Send one control message from a non-P2P thread."""
        try:
            return bool(self._call(self.send_control_async(node_id, message),
                                   timeout=10))
        except Exception:
            return False

    async def drop_peer_async(self, node_id: str, reason: str = "") -> None:
        peer = self.peers.get(node_id)
        session = getattr(peer, "session", None)
        if peer is None or session is None:
            return
        try:
            await self._write(session, error(
                "E_CIRCLE_REMOVED", reason or "removed from the circle"))
        except Exception:
            pass
        peer.admitted = False
        session.close()

    def drop_peer(self, node_id: str, reason: str = "") -> None:
        try:
            self._call(self.drop_peer_async(node_id, reason), timeout=10)
        except Exception:
            peer = self.peers.get(node_id)
            session = getattr(peer, "session", None)
            if session is not None:
                session.close()

    def mark_admitted(self, node_id: str) -> None:
        """A manifest now lists both nodes: a bootstrap session becomes a
        normal admitted peer."""
        peer = self.peers.get(node_id)
        if peer is not None and not peer.admitted:
            peer.admitted = True
            self.bus.publish("node.admitted", node_id=node_id,
                             short_id=node_id[:12])

    @property
    def loop(self) -> asyncio.AbstractEventLoop | None:
        return self._loop

    # -- introspection ------------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        cfg = self.config.all()["swarm"]
        peers = list(self.peers.values())
        discovered = self.discovery.entries() if self.discovery else []
        return {
            "started": self._started,
            "listening": self.listen_port is not None,
            "listen_error": self.listen_error,
            "port": self.listen_port or cfg.get("p2p_port") or DEFAULT_P2P_PORT,
            "discovery": {"enabled": self.discovery is not None,
                          "announcing": bool(self.discovery and self.discovery.announcing),
                          "browsing": bool(self.discovery and self.discovery.browsing),
                          "error": self.discovery.last_error if self.discovery else ""},
            "peers": [p.to_dict() for p in peers],
            "discovered": [n.to_dict() for n in discovered],
            "connected_count": sum(1 for p in peers if p.connected),
            "verified_count": sum(1 for p in peers if p.authenticated),
            "authenticated_count": sum(1 for p in peers if p.authenticated and p.connected),
            "admitted_count": sum(1 for p in peers if p.admitted and p.connected),
            "unreachable_count": sum(1 for p in peers if not p.connected),
            "circles": self.circles.summary() if self.circles is not None else None,
            "relays": self.relay_status(),
        }

    def available_workers(self, kind: str = "generate") -> list[Peer]:
        """Connected, authenticated peers whose *current* advertisement says
        they serve ``kind``. A peer with the worker role off advertises no
        kinds and is never offered a task."""
        out = []
        for peer in self.peers.values():
            if not (peer.connected and peer.authenticated and peer.admitted
                    and peer.session):
                continue
            kinds = (peer.advertisement.get("policy") or {}).get("kinds") or []
            if kind not in kinds:
                continue
            out.append(peer)
        return out


class PeerError(RuntimeError):
    """A remote error (SPEC §20 code or app extension) or a transport failure."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _listen_port(advertisement: dict[str, Any]) -> int | None:
    try:
        port = int((advertisement.get("endpoint") or {}).get("port") or 0)
        return port if 0 < port < 65536 else None
    except (TypeError, ValueError):
        return None


def _nonce_bytes(text: str) -> bytes:
    import base64
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
