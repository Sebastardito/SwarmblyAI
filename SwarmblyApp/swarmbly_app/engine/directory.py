"""Worker directory: remote peers plus this device's own model pool.

The scheduler asks a directory for candidate workers and dispatches through
it. Remote peers are offered only when the request may leave the device
(tier GLOBAL, lane PUBLIC, a swarm mode); the local pool — several local
models of different families — is offered whenever multi-model processing is
on, at any tier, because nothing leaves the device. Both paths use the same
SPEC §8 packets, signatures and verification, so local results are checked
exactly like remote ones.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from .. import egress
from ..models import family_for
from ..p2p.node import PeerError


@dataclass
class LocalPeer:
    """Pseudo-peer for the local model pool (looks like a Peer to the scheduler)."""

    node_id: str
    advertisement: dict[str, Any]
    tasks_inflight: int = 0
    rtt_ms: float | None = 0.0
    source: str = "local"
    authenticated: bool = True
    connected: bool = True

    @property
    def is_local(self) -> bool:
        return True


class LocalPool:
    def __init__(self, node_id: str, worker, models: list[str], families: dict[str, str],
                 parallel: int = 1, roles: list[dict[str, Any]] | None = None):
        self.worker = worker
        self.models = list(models)
        self.peer = LocalPeer(
            node_id=node_id,
            advertisement={"models": [{"family": families.get(m) or family_for(m),
                                       "version": m} for m in self.models],
                           # 3.5, D-018: same node-role derivation as a remote
                           # worker, without the "shared" condition.
                           "roles": list(roles or []),
                           "policy": {"kinds": ["generate"], "max_concurrent": max(1, parallel)}})

    async def dispatch(self, message: dict[str, Any], timeout_s: float) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        try:
            reply = await asyncio.wait_for(
                loop.run_in_executor(None, egress.carry(self.worker.execute_local), message,
                                     self.models, timeout_s), timeout_s + 5)
        except asyncio.TimeoutError:
            raise PeerError("E_DEADLINE", "local model timeout") from None
        if reply.get("type") == "error":
            raise PeerError(str(reply.get("code")), str(reply.get("detail")))
        return reply


@dataclass
class Directory:
    nodes: Any                      # NodeManager (remote peers) or None
    local: LocalPool | None = None
    remote_allowed: bool = True
    # D-017: when a list wave carries document passages, only peers whose
    # circle switch is on may receive it. ``None`` means no filter.
    allowed_remote: set[str] | None = None
    peers: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.nodes is not None:
            self.peers = self.nodes.peers
        if self.local is not None:
            self.peers = dict(self.peers)
            self.peers[self.local.peer.node_id] = self.local.peer

    def available_workers(self, kind: str = "generate") -> list[Any]:
        out = []
        if self.remote_allowed and self.nodes is not None:
            out.extend(peer for peer in self.nodes.available_workers(kind)
                       if self.allowed_remote is None
                       or peer.node_id in self.allowed_remote)
        if self.local is not None:
            out.append(self.local.peer)
        return out

    def capacity(self) -> int:
        return sum(max(1, int((w.advertisement.get("policy") or {})
                              .get("max_concurrent") or 1))
                   for w in self.available_workers())

    def passages_allowed(self, node_id: str) -> bool:
        """Whether document passages may be sent to this worker (WP4b).

        The local pool is always allowed (nothing leaves the computer). A
        remote peer needs a shared circle with ``circle_passages`` on, or the
        explicit my-own-devices switch. Corpus results are treated as the
        requester's passages, so this is the gate that stops forwarding them
        to a node that is not allowed to receive passages.
        """
        if self.local is not None and node_id == self.local.peer.node_id:
            return True
        if not self.remote_allowed or self.nodes is None:
            return False
        if self.allowed_remote is not None and node_id not in self.allowed_remote:
            return False
        circles = getattr(self.nodes, "circles", None)
        if circles is None:
            return False
        try:
            ok, _why = circles.peer_passages_allowed(node_id)
            return bool(ok)
        except Exception:
            return False

    def transport_hop(self, node_id: str) -> dict[str, Any]:
        """The transport hop for a send (3.5, WP3 / D-016)."""
        if self.local is not None and node_id == self.local.peer.node_id:
            return {"transport": "direct"}
        if self.nodes is None:
            return {"transport": "direct"}
        try:
            return self.nodes.transport_hop(node_id)
        except Exception:
            return {"transport": "direct"}

    def classify_peer(self, node_id: str) -> dict[str, Any]:
        """Destination class for a send (D-017): local pool, circle, own network."""
        if self.local is not None and node_id == self.local.peer.node_id:
            return {"clase": egress.LOCAL, "circle_id": "", "circle_name": "",
                    "member_name": "", "member_node": ""}
        if not self.remote_allowed or self.nodes is None:
            raise PeerError("E_TIER_VIOLATION", "remote dispatch not allowed")
        return self.nodes.classify_peer(node_id)

    async def dispatch_async(self, node_id: str, message: dict[str, Any],
                             timeout_s: float, *,
                             offer_credit: bool = False) -> dict[str, Any]:
        if self.local is not None and node_id == self.local.peer.node_id:
            return await self.local.dispatch(message, timeout_s)
        if not self.remote_allowed or self.nodes is None:
            raise PeerError("E_TIER_VIOLATION", "remote dispatch not allowed")
        if offer_credit:
            # D-020: a credit is offered only to a worker known to be busy.
            return await self.nodes.dispatch_async(node_id, message, timeout_s,
                                                   offer_credit=True)
        return await self.nodes.dispatch_async(node_id, message, timeout_s)
