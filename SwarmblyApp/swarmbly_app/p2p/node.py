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

from ..config import Config
from ..db import Database
from ..events import EventBus
from ..identity import IdentityManager
from .discovery import DiscoveredNode, DiscoveryService
from .handshake import (Handshake, HandshakeResult, sign_advertisement_update,
                        validate_advertisement, verify_advertisement_update)
from .messages import WIRE_VERSION, error
from .transport import (PeerSession, TLSServer, cert_fingerprint, dial,
                        generate_cert, read_frame, read_frame_with_timeout,
                        write_frame)

DEFAULT_P2P_PORT = 9765
MAX_PEERS = 64
KEEPALIVE_S = 30.0
DEAD_AFTER_S = 95.0
DIAL_BACKOFF_S = 4.0          # higher node_id waits this long before dialing
REPLAY_WINDOW = 4096          # attempt_ids remembered per peer
MAX_QUEUED_TASKS_PER_PEER = 8


@dataclass
class Peer:
    node_id: str
    address: str
    port: int                         # the peer's listening port (dial target)
    advertisement: dict[str, Any] = field(default_factory=dict)
    connected: bool = False
    authenticated: bool = False       # Ed25519 handshake bound to TLS succeeded
    source: str = "manual"            # mdns | manual | inbound
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    rtt_ms: float | None = None       # measured by ping/pong
    session: PeerSession | None = None
    adv_seq: int = 0
    tasks_inflight: int = 0
    seen_attempts: collections.OrderedDict = field(
        default_factory=collections.OrderedDict)

    @property
    def is_worker(self) -> bool:
        policy = self.advertisement.get("policy") or {}
        return bool(policy.get("kinds"))

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
            "worker": self.is_worker,
            "source": self.source,
            "models": self.advertisement.get("models", []),
            "policy": self.advertisement.get("policy", {}),
            "resources": self.advertisement.get("resources", {}),
            "rtt_ms": self.rtt_ms,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "tasks_inflight": self.tasks_inflight,
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
    async def _connect(self, host: str, port: int, source: str = "manual") -> Peer | None:
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
            hello_msg, nonce = self.handshake.build_hello()
            try:
                session, ack_message, observed = await dial(host, port, hello_msg)
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
                                 listen_port=_listen_port(result.advertisement))
        except Exception as exc:
            session.close()
            self.bus.publish("node.handshake_failed", address=session.address,
                             reason=str(exc)[:120])

    async def _register(self, result: HandshakeResult, session: PeerSession,
                        source: str, listen_port: int | None) -> Peer | None:
        node_id = result.node_id
        advertisement = result.advertisement
        problems = validate_advertisement(advertisement, expected_node_id=node_id)
        if problems:
            session.close()
            self.bus.publish("node.rejected", node_id=node_id[:12],
                             reason="; ".join(problems[:2]))
            return None
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
        peer.last_seen = time.time()
        peer.session = session
        if self.discovery is not None:
            self.discovery.mark_verified(node_id, session.address)
        self.db.upsert_node(node_id, peer.address, peer.port,
                            verified=True, profile=advertisement)
        self.bus.publish("node.connected", node_id=node_id,
                         short_id=node_id[:12], address=peer.address,
                         source=source, worker=peer.is_worker)
        self._spawn(self._read_loop(session, node_id))
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
            peer.advertisement = adv
            self.bus.publish("node.updated", node_id=node_id,
                             short_id=node_id[:12], worker=peer.is_worker)
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

    # -- dispatch API (called from engine threads) ---------------------------------------
    def dispatch(self, node_id: str, packet_message: dict[str, Any],
                 timeout_s: float = 120.0) -> dict[str, Any]:
        return self._call(self.dispatch_async(node_id, packet_message, timeout_s),
                          timeout=timeout_s + 10)

    async def dispatch_async(self, node_id: str, packet_message: dict[str, Any],
                             timeout_s: float) -> dict[str, Any]:
        """Send one packet and await its result (must run on the P2P loop)."""
        peer = self.peers.get(node_id)
        if peer is None or not peer.connected or peer.session is None:
            raise PeerError("E_DISCONNECTED", f"node {node_id[:12]} not connected")
        attempt_id = str(packet_message.get("attempt_id", ""))
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
            "unreachable_count": sum(1 for p in peers if not p.connected),
        }

    def available_workers(self, kind: str = "generate") -> list[Peer]:
        """Connected, authenticated peers whose *current* advertisement says
        they serve ``kind``. A peer with the worker role off advertises no
        kinds and is never offered a task."""
        out = []
        for peer in self.peers.values():
            if not (peer.connected and peer.authenticated and peer.session):
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
