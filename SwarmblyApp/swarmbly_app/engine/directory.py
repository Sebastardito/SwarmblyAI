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
                 parallel: int = 1):
        self.worker = worker
        self.models = list(models)
        self.peer = LocalPeer(
            node_id=node_id,
            advertisement={"models": [{"family": families.get(m) or m.split(":")[0],
                                       "version": m} for m in self.models],
                           "policy": {"kinds": ["generate"], "max_concurrent": max(1, parallel)}})

    async def dispatch(self, message: dict[str, Any], timeout_s: float) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        try:
            reply = await asyncio.wait_for(
                loop.run_in_executor(None, self.worker.execute_local, message,
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
            out.extend(self.nodes.available_workers(kind))
        if self.local is not None:
            out.append(self.local.peer)
        return out

    def capacity(self) -> int:
        return sum(max(1, int((w.advertisement.get("policy") or {})
                              .get("max_concurrent") or 1))
                   for w in self.available_workers())

    async def dispatch_async(self, node_id: str, message: dict[str, Any],
                             timeout_s: float) -> dict[str, Any]:
        if self.local is not None and node_id == self.local.peer.node_id:
            return await self.local.dispatch(message, timeout_s)
        if not self.remote_allowed or self.nodes is None:
            raise PeerError("E_TIER_VIOLATION", "remote dispatch not allowed")
        return await self.nodes.dispatch_async(node_id, message, timeout_s)
