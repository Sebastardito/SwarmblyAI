# SPDX-License-Identifier: AGPL-3.0-only
"""Swarmbly circle relay: register, pair, splice.  Asyncio, standard library.

The relay is a dumb, stateless-in-content byte pump between two circle
members.  It authenticates each member with an Ed25519 challenge, checks the
pair against the signed circle manifest it holds, and then copies bytes in
both directions.  The nodes' own TLS 1.3 session runs *through* that copy, so
the relay forwards ciphertext it cannot read.

Wire before the splice: 4-byte big-endian length + compact JSON.
Wire after the splice: the two peers' bytes, unchanged.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import secrets
import signal
import ssl
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .limits import LimitTracker
from .manifest import ManifestStore
from .protocol import (MAX_FRAME_BYTES, RelayError, challenge_frame, error_frame,
                       read_frame, registered_frame, verify_register_proof,
                       write_frame)

log = logging.getLogger("swarmbly.relay")

# The relay only needs to see control frames; payload is spliced, never parsed.
PUMP_CHUNK = 64 * 1024


@dataclass
class RelayConfig:
    manifests: tuple[Path, ...] = ()
    certfile: Path | None = None
    keyfile: Path | None = None
    host: str = "0.0.0.0"
    port: int = 8765
    max_frame_bytes: int = MAX_FRAME_BYTES
    register_timeout: float = 10.0
    pair_timeout: float = 30.0
    idle_timeout: float = 300.0
    max_splices_per_member: int = 4
    bytes_per_day: int = 2 * 1024 ** 3
    max_connections: int = 1024
    logger: logging.Logger | None = None


@dataclass(eq=False)
class Session:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    peer: str
    circle_id: str = ""
    node_id: str = ""
    authenticated: bool = False
    challenge: bytes | None = None
    pair: "PairState | None" = None
    in_splice: bool = False
    closed: bool = False


@dataclass
class PairState:
    pair_id: str
    initiator: Session
    responder: Session
    accepted: asyncio.Event = field(default_factory=asyncio.Event)
    started: asyncio.Event = field(default_factory=asyncio.Event)
    failed: bool = False
    error: str = ""
    idle: bool = False
    limit_hit: bool = False
    bytes: int = 0
    last_activity: float = 0.0


class RelayServer:
    def __init__(self, config: RelayConfig, store: ManifestStore | None = None) -> None:
        self.config = config
        self.log = config.logger or log
        self.store = store or ManifestStore(list(config.manifests))
        self.limits = LimitTracker(
            max_splices_per_member=config.max_splices_per_member,
            bytes_per_day=config.bytes_per_day)
        self.port = config.port
        self._server: asyncio.Server | None = None
        self._sessions: set[Session] = set()
        self._by_node: dict[tuple[str, str], set[Session]] = defaultdict(set)
        self._pairs: dict[str, PairState] = {}
        self._tasks: set[asyncio.Task] = set()

    # -- lifecycle ---------------------------------------------------------
    async def start(self) -> None:
        if self.config.certfile is None or self.config.keyfile is None:
            raise ValueError("the relay requires a TLS certificate and key")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.load_cert_chain(str(self.config.certfile), str(self.config.keyfile))
        if not self.store.all():
            self.store.reload(force=True)
        self._server = await asyncio.start_server(
            self._handle, self.config.host, self.config.port, ssl=context,
            ssl_handshake_timeout=max(1.0, self.config.register_timeout),
            reuse_address=True)
        sockets = self._server.sockets or []
        if sockets:
            self.port = sockets[0].getsockname()[1]
        self.log.info("relay listening host=%s port=%d circles=%d",
                      self.config.host, self.port, len(self.store.all()))

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            with contextlib.suppress(Exception):
                await self._server.wait_closed()
            self._server = None
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        for session in list(self._sessions):
            await self._close_session(session)
        self._pairs.clear()
        self.log.info("relay stopped")

    async def __aenter__(self) -> "RelayServer":
        await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.stop()

    # -- connections -------------------------------------------------------
    async def _handle(self, reader: asyncio.StreamReader,
                      writer: asyncio.StreamWriter) -> None:
        peer = self._peer_name(writer)
        if len(self._sessions) >= self.config.max_connections:
            self.log.warning("connection refused: relay busy peer=%s", peer)
            writer.close()
            return
        session = Session(reader=reader, writer=writer, peer=peer)
        self._sessions.add(session)
        try:
            await self._register(session)
            await self._control_loop(session)
        except RelayError as exc:
            self.log.info("relay error peer=%s code=%s", peer, exc.code)
            await self._safe_error(session, exc.code, exc.message)
        except (asyncio.IncompleteReadError, asyncio.TimeoutError,
                ConnectionError, ssl.SSLError) as exc:
            self.log.debug("connection ended peer=%s reason=%s", peer, exc)
        except asyncio.CancelledError:
            raise
        except Exception:  # never take the listener down for one connection
            self.log.exception("unexpected relay error peer=%s", peer)
        finally:
            if not session.in_splice:
                await self._close_session(session)

    async def _register(self, session: Session) -> None:
        frame = await read_frame(session.reader, max_bytes=self.config.max_frame_bytes,
                                 timeout=self.config.register_timeout)
        if frame.get("type") != "register":
            raise RelayError("expected_register")
        circle_id = str(frame.get("circle_id") or "")
        node_id = str(frame.get("node_id") or "")
        self.store.reload()
        manifest = self.store.get(circle_id)
        if manifest is None:
            raise RelayError("unknown_circle")
        if not manifest.contains(node_id):
            raise RelayError("not_a_member")
        if manifest.expired():
            raise RelayError("manifest_expired")
        if not self.limits.can_register(node_id):
            raise RelayError("limit_bytes")

        nonce = secrets.token_bytes(32)
        session.circle_id = circle_id
        session.node_id = node_id
        session.challenge = nonce
        await write_frame(session.writer, challenge_frame(nonce))

        proof = await read_frame(session.reader, max_bytes=self.config.max_frame_bytes,
                                 timeout=self.config.register_timeout)
        if proof.get("type") != "register_proof":
            raise RelayError("expected_register_proof")
        if session.challenge is None:
            raise RelayError("challenge_reused")
        signature = proof.get("signature") or proof.get("sig")
        if not isinstance(signature, str) or not verify_register_proof(
                circle_id, node_id, session.challenge, signature):
            raise RelayError("bad_register_proof")
        session.challenge = None
        session.authenticated = True
        self._by_node[(circle_id, node_id)].add(session)
        await write_frame(session.writer, registered_frame(circle_id, node_id))
        self.log.info("register circle=%s node=%s peer=%s",
                      self._short(circle_id), self._short(node_id), session.peer)

    async def _control_loop(self, session: Session) -> None:
        while not session.in_splice and not session.closed:
            try:
                frame = await read_frame(
                    session.reader, max_bytes=self.config.max_frame_bytes,
                    timeout=max(self.config.idle_timeout,
                                self.config.pair_timeout + 5.0, 30.0))
            except asyncio.TimeoutError:
                return
            kind = frame.get("type")
            if kind == "pair":
                await self._request_pair(session, frame)
            elif kind == "pair_accept":
                await self._accept_pair(session, frame)
            elif kind == "ping":
                await write_frame(session.writer, {"type": "pong"})
            elif kind == "close":
                return
            else:
                raise RelayError("unknown_message", str(kind))

    # -- pairing -----------------------------------------------------------
    def _idle_session(self, circle_id: str, node_id: str) -> Session | None:
        for candidate in self._by_node.get((circle_id, node_id), ()):
            if (candidate.authenticated and not candidate.in_splice
                    and candidate.pair is None and not candidate.closed):
                return candidate
        return None

    async def _request_pair(self, session: Session, frame: dict[str, Any]) -> None:
        peer_id = str(frame.get("peer_node_id") or "")
        circle_id = str(frame.get("circle_id") or session.circle_id)
        if not peer_id:
            raise RelayError("invalid_pair", "peer_node_id is required")
        if circle_id != session.circle_id:
            raise RelayError("circle_mismatch")
        self.store.reload()
        manifest = self.store.get(session.circle_id)
        if (manifest is None or not manifest.contains(session.node_id)
                or not manifest.contains(peer_id)):
            raise RelayError("not_a_member", "both nodes must be in this circle")
        if peer_id == session.node_id:
            raise RelayError("self_pair")
        responder = self._idle_session(session.circle_id, peer_id)
        if responder is None:
            raise RelayError("peer_not_connected")
        if not self.limits.reserve(session.node_id):
            raise RelayError("limit_splices", "concurrent splice limit reached")
        if not self.limits.reserve(peer_id):
            self.limits.release(session.node_id)
            raise RelayError("limit_splices", "concurrent splice limit reached")

        pair = PairState(pair_id=uuid.uuid4().hex, initiator=session, responder=responder)
        self._pairs[pair.pair_id] = pair
        session.pair = pair
        responder.pair = pair
        await write_frame(responder.writer, {
            "type": "pair_incoming", "pair_id": pair.pair_id,
            "from_node_id": session.node_id, "circle_id": session.circle_id})
        await write_frame(session.writer, {
            "type": "pair_wait", "pair_id": pair.pair_id,
            "peer_node_id": peer_id})
        try:
            await asyncio.wait_for(pair.accepted.wait(), self.config.pair_timeout)
        except asyncio.TimeoutError:
            await self._fail_pair(pair, "pair_timeout")
        if pair.failed:
            return

        await write_frame(session.writer, {
            "type": "paired", "pair_id": pair.pair_id, "role": "initiator",
            "peer_node_id": peer_id})
        await write_frame(responder.writer, {
            "type": "paired", "pair_id": pair.pair_id, "role": "responder",
            "peer_node_id": session.node_id})
        session.in_splice = True
        responder.in_splice = True
        pair.started.set()
        self._detach(session)
        self._detach(responder)
        task = asyncio.create_task(self._splice(pair))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _accept_pair(self, session: Session, frame: dict[str, Any]) -> None:
        pair = self._pairs.get(str(frame.get("pair_id") or ""))
        if pair is None or pair.responder is not session:
            raise RelayError("unknown_pair")
        if pair.failed:
            return
        if pair.accepted.is_set():
            raise RelayError("duplicate_pair_accept")
        pair.accepted.set()
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(pair.started.wait(), self.config.pair_timeout + 5.0)

    async def _fail_pair(self, pair: PairState, code: str) -> None:
        if pair.failed:
            return
        pair.failed = True
        pair.error = code
        self._pairs.pop(pair.pair_id, None)
        pair.accepted.set()
        pair.started.set()
        pair.initiator.pair = None
        pair.responder.pair = None
        self.limits.release(pair.initiator.node_id)
        self.limits.release(pair.responder.node_id)
        for target in (pair.initiator, pair.responder):
            await self._safe_error(target, code, "pair failed")
        self.log.info("pair failed pair=%s code=%s", pair.pair_id[:8], code)

    # -- splice ------------------------------------------------------------
    async def _splice(self, pair: PairState) -> None:
        first, second = pair.initiator, pair.responder
        pair.last_activity = asyncio.get_running_loop().time()
        self.log.info("splice start pair=%s a=%s b=%s",
                      pair.pair_id[:8], self._short(first.node_id),
                      self._short(second.node_id))
        tasks = [
            asyncio.create_task(
                self._pump(first.reader, second.writer, pair,
                           first.node_id, second.node_id)),
            asyncio.create_task(
                self._pump(second.reader, first.writer, pair,
                           second.node_id, first.node_id)),
        ]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self._pairs.pop(pair.pair_id, None)
            first.pair = None
            second.pair = None
            self.limits.release(first.node_id)
            self.limits.release(second.node_id)
            await self._close_session(first)
            await self._close_session(second)
            self.log.info(
                "splice end pair=%s bytes=%d idle=%s limit=%s",
                pair.pair_id[:8], pair.bytes, pair.idle, pair.limit_hit)

    async def _pump(self, source: asyncio.StreamReader,
                    sink: asyncio.StreamWriter, pair: PairState,
                    from_node: str, to_node: str) -> None:
        loop = asyncio.get_running_loop()
        while True:
            remaining = self.config.idle_timeout - (loop.time() - pair.last_activity)
            if remaining <= 0:
                pair.idle = True
                return
            try:
                data = await asyncio.wait_for(source.read(PUMP_CHUNK), remaining)
            except asyncio.TimeoutError:
                if loop.time() - pair.last_activity < self.config.idle_timeout:
                    continue
                pair.idle = True
                return
            if not data:
                return
            pair.last_activity = loop.time()
            # Count before forwarding so a budget is a hard stop, not a report.
            if (not self.limits.add_bytes(from_node, len(data))
                    or not self.limits.add_bytes(to_node, len(data))):
                pair.limit_hit = True
                return
            self._record_forwarded(data)
            try:
                sink.write(data)
                await sink.drain()
            except (ConnectionError, RuntimeError):
                return
            pair.bytes += len(data)

    def _record_forwarded(self, data: bytes) -> None:
        """Test hook only; production intentionally keeps no payload bytes."""
        return None

    # -- cleanup -----------------------------------------------------------
    def _detach(self, session: Session) -> None:
        self._by_node.get((session.circle_id, session.node_id), set()).discard(session)

    async def _close_session(self, session: Session) -> None:
        if session.closed:
            return
        session.closed = True
        if session.pair is not None and not session.pair.failed:
            await self._fail_pair(session.pair, "peer_disconnected")
        self._sessions.discard(session)
        self._detach(session)
        with contextlib.suppress(Exception):
            session.writer.close()
        with contextlib.suppress(Exception):
            await session.writer.wait_closed()

    async def _safe_error(self, session: Session, code: str, message: str = "") -> None:
        if session.closed:
            return
        with contextlib.suppress(Exception):
            await write_frame(session.writer, error_frame(code, message))

    @staticmethod
    def _peer_name(writer: asyncio.StreamWriter) -> str:
        try:
            sock = writer.get_extra_info("peername")
            if sock:
                return f"{sock[0]}:{sock[1]}"
        except Exception:
            pass
        return "?"

    @staticmethod
    def _short(value: str) -> str:
        return value[:12]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="swarmbly-relay",
        description="Swarmbly circle relay (AGPL-3.0-only)")
    parser.add_argument("--manifest", action="append", required=True,
                        metavar="PATH",
                        help="signed manifest JSON, or a directory of *.json (repeatable)")
    parser.add_argument("--cert", required=True, metavar="PEM",
                        help="TLS certificate for the node-to-relay leg")
    parser.add_argument("--key", required=True, metavar="PEM",
                        help="TLS private key")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--max-splices", type=int, default=4,
                        help="concurrent splices per member (default 4)")
    parser.add_argument("--bytes-per-day", type=int, default=2 * 1024 ** 3,
                        help="forwarded bytes per member per UTC day")
    parser.add_argument("--idle-timeout", type=float, default=300.0,
                        help="seconds without bytes before a splice closes")
    parser.add_argument("--pair-timeout", type=float, default=30.0)
    parser.add_argument("--register-timeout", type=float, default=10.0)
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


async def _serve(config: RelayConfig, stop: asyncio.Event) -> None:
    async with RelayServer(config) as server:
        loop = asyncio.get_running_loop()
        for signum in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(signum, stop.set)
        await stop.wait()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr)
    config = RelayConfig(
        manifests=tuple(Path(path) for path in args.manifest),
        certfile=Path(args.cert),
        keyfile=Path(args.key),
        host=args.host,
        port=args.port,
        max_splices_per_member=args.max_splices,
        bytes_per_day=args.bytes_per_day,
        idle_timeout=args.idle_timeout,
        pair_timeout=args.pair_timeout,
        register_timeout=args.register_timeout,
        logger=logging.getLogger("swarmbly.relay"))
    try:
        asyncio.run(_serve(config, asyncio.Event()))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
