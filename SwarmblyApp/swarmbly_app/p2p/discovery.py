"""LAN discovery via mDNS/DNS-SD (zeroconf, asyncio API).

Each node announces a minimal record — service instance, port, protocol
version and its ``node_id`` (the Ed25519 public key, needed to filter its own
announcement and to de-duplicate peers) — and discovers peers without knowing
their IPs in advance (product spec §7.1). The capability profile travels only
after the authenticated handshake. There is no port or host scanning: an
"active search" is a fresh mDNS query for the Swarmbly service type, which only
Swarmbly nodes answer. Manual ``host:port`` connections remain available.

Cache entries carry three timestamps: when the node was first discovered,
when its record was last verified by an mDNS answer, and when the entry
expires. An entry is never refreshed without a real answer.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable

SERVICE_TYPE = "_swarmbly._tcp.local."
DEFAULT_TTL_S = 300.0
RESOLVE_TIMEOUT_MS = 3000


@dataclass
class DiscoveredNode:
    node_id: str                    # node_id announced over mDNS (unverified until handshake)
    address: str
    port: int
    discovered_at: float
    last_seen: float                # last mDNS answer that confirmed the record
    ttl_s: float = DEFAULT_TTL_S
    verified: bool = False          # True once an Ed25519 handshake confirmed node_id
    source: str = "mdns"            # mdns | manual
    addresses: list[str] = field(default_factory=list)
    info: dict[str, Any] = field(default_factory=dict)
    removed: bool = False           # an mDNS goodbye was received

    @property
    def expires_at(self) -> float:
        return self.last_seen + self.ttl_s

    def expired(self, now: float | None = None) -> bool:
        return (now or time.time()) > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {"node_hint": self.node_id[:16], "address": self.address,
                "addresses": list(self.addresses), "port": self.port,
                "source": self.source, "verified": self.verified,
                "discovered_at": self.discovered_at,
                "last_seen": self.last_seen, "expires_at": self.expires_at,
                "removed": self.removed}


def local_ipv4_addresses() -> list[str]:
    """Non-loopback, non-link-local IPv4 addresses of this host."""
    out: list[str] = []
    try:
        import psutil
        for entries in psutil.net_if_addrs().values():
            for entry in entries:
                if entry.family != socket.AF_INET:
                    continue
                try:
                    ip = ipaddress.IPv4Address(entry.address)
                except ValueError:
                    continue
                if ip.is_loopback or ip.is_link_local or ip.is_unspecified:
                    continue
                if entry.address not in out:
                    out.append(entry.address)
    except Exception:
        pass
    if not out:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("192.0.2.1", 80))  # RFC 5737 TEST-NET; no traffic sent
            out.append(sock.getsockname()[0])
            sock.close()
        except Exception:
            pass
    return out


def mdns_host_label(hostname: str, node_id: str) -> str:
    """A valid DNS label for this node's mDNS host record.

    DNS labels are limited to 63 bytes (RFC 1035) and should use letters,
    digits and hyphens. Computer names are often longer (CI runners, some
    managed Macs) or contain spaces, apostrophes and accents ("Sebastián's
    MacBook Pro"), and zeroconf refuses to announce with such a label. The
    computer name is only cosmetic here: identity is the node key.
    """
    raw = unicodedata.normalize("NFKD", (hostname or "").split(".")[0])
    host = re.sub(r"[^a-z0-9-]+", "-", raw.encode("ascii", "ignore").decode().lower())
    host = re.sub(r"-{2,}", "-", host).strip("-")[:48].rstrip("-") or "swarmbly"
    suffix = re.sub(r"[^a-z0-9]", "", node_id.lower())[:6] or "node"
    return f"{host}-{suffix}"


class DiscoveryService:
    """Announces this node and maintains the discovery cache.

    All zeroconf work happens on the asyncio loop that calls :meth:`start`.
    Callbacks (``on_discovered``/``on_removed``) run on that same loop.
    """

    def __init__(self, node_id: str, port: int, version: str,
                 on_discovered: Callable[[DiscoveredNode], None] | None = None,
                 on_removed: Callable[[DiscoveredNode], None] | None = None,
                 ttl_s: float = DEFAULT_TTL_S,
                 addresses: list[str] | None = None,
                 interfaces: Any = None):
        self.node_id = node_id
        self.port = port
        self.version = version
        self.on_discovered = on_discovered
        self.on_removed = on_removed
        self.ttl_s = ttl_s
        self._addresses = addresses
        self._interfaces = interfaces
        self._cache: dict[str, DiscoveredNode] = {}
        self._names: dict[str, str] = {}       # mDNS instance name -> cache key
        self._zc = None
        self._info = None
        self._browser = None
        self._pending: set[asyncio.Task] = set()
        self.announcing = False
        self.browsing = False
        self.last_error: str = ""

    # -- lifecycle -------------------------------------------------------------
    async def start(self, announce: bool = True, browse: bool = True) -> None:
        try:
            from zeroconf import IPVersion
            from zeroconf.asyncio import AsyncZeroconf
        except ImportError as exc:  # declared dependency; degrade honestly
            self.last_error = f"zeroconf unavailable: {exc}"
            return
        if self._zc is None:
            kwargs: dict[str, Any] = {"ip_version": IPVersion.V4Only}
            if self._interfaces is not None:
                kwargs["interfaces"] = self._interfaces
            self._zc = AsyncZeroconf(**kwargs)
        if announce and not self.announcing:
            await self._announce()
        if browse and not self.browsing:
            self._start_browser()

    async def _announce(self) -> None:
        from zeroconf.asyncio import AsyncServiceInfo
        addresses = self._addresses or local_ipv4_addresses() or ["127.0.0.1"]
        props = {"v": self.version, "node": self.node_id, "proto": "swarmbly"}
        instance = f"swarmbly-{self.node_id[:12]}.{SERVICE_TYPE}"
        self._info = AsyncServiceInfo(
            SERVICE_TYPE, instance,
            addresses=[socket.inet_aton(a) for a in addresses],
            port=self.port, properties=props,
            server=mdns_host_label(socket.gethostname(), self.node_id) + ".local.")
        try:
            # The asyncio API returns a task that completes once probing and
            # the announcement are done; awaiting it makes 'announcing' true.
            task = await self._zc.async_register_service(
                self._info, allow_name_change=True)
            await task
            self.announcing = True
        except Exception as exc:
            self.last_error = f"announce failed: {exc}"

    def _start_browser(self) -> None:
        from zeroconf.asyncio import AsyncServiceBrowser
        self._browser = AsyncServiceBrowser(self._zc.zeroconf, SERVICE_TYPE,
                                            handlers=[self._on_change])
        self.browsing = True

    async def stop(self) -> None:
        for task in list(self._pending):
            task.cancel()
        if self._browser is not None:
            try:
                await self._browser.async_cancel()
            except Exception:
                pass
            self._browser = None
        if self._zc is not None:
            if self._info is not None and self.announcing:
                try:  # sends the mDNS goodbye so peers drop us immediately
                    task = await self._zc.async_unregister_service(self._info)
                    await task
                except Exception:
                    pass
            try:
                await self._zc.async_close()
            except Exception:
                pass
        self._zc = None
        self._info = None
        self.announcing = False
        self.browsing = False

    # -- browsing ----------------------------------------------------------------
    def _on_change(self, zeroconf, service_type, name, state_change) -> None:
        """Runs on the zeroconf loop: never block here, resolve in a task."""
        from zeroconf import ServiceStateChange
        if state_change is ServiceStateChange.Removed:
            self._mark_removed(name)
            return
        task = asyncio.ensure_future(self._resolve(service_type, name))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _resolve(self, service_type: str, name: str) -> DiscoveredNode | None:
        from zeroconf.asyncio import AsyncServiceInfo
        if self._zc is None:
            return None
        info = AsyncServiceInfo(service_type, name)
        try:
            ok = await info.async_request(self._zc.zeroconf, RESOLVE_TIMEOUT_MS)
        except Exception as exc:
            self.last_error = f"resolve failed: {exc}"
            return None
        if not ok:
            return None
        return self._record(name, info)

    def _record(self, name: str, info) -> DiscoveredNode | None:
        try:
            props = {(k.decode() if isinstance(k, bytes) else str(k)):
                     (v.decode() if isinstance(v, bytes) else (v or ""))
                     for k, v in (info.properties or {}).items()}
            addresses = [a for a in info.parsed_addresses()
                         if ":" not in a]  # IPv4 only (V4Only zeroconf)
        except Exception:
            return None
        if not addresses or not info.port:
            return None
        node_id = props.get("node", "")
        if node_id and node_id == self.node_id:
            return None  # our own announcement
        key = node_id or f"{addresses[0]}:{info.port}"
        now = time.time()
        existing = self._cache.get(key)
        if existing is not None and not existing.removed:
            existing.last_seen = now
            existing.addresses = addresses
            existing.address = _preferred(addresses, existing.address)
            existing.port = int(info.port)
            existing.info = props
            self._names[name] = key
            return existing
        node = DiscoveredNode(
            node_id=node_id, address=_preferred(addresses, ""),
            port=int(info.port), discovered_at=(existing.discovered_at
                                                if existing else now),
            last_seen=now, ttl_s=self.ttl_s, source="mdns",
            addresses=addresses, info=props)
        self._cache[key] = node
        self._names[name] = key
        if self.on_discovered:
            try:
                self.on_discovered(node)
            except Exception:
                pass
        return node

    def _mark_removed(self, name: str) -> None:
        key = self._names.pop(name, None)
        node = self._cache.get(key) if key else None
        if node is None:
            return
        node.removed = True
        if self.on_removed:
            try:
                self.on_removed(node)
            except Exception:
                pass

    # -- active search -------------------------------------------------------------
    async def refresh(self, wait_s: float = 1.5) -> dict[str, int]:
        """Active search: send a fresh mDNS query and re-verify known records.

        Restarting the browser makes zeroconf send an immediate PTR query for
        the Swarmbly service type (only Swarmbly nodes answer it). Known
        records are re-resolved; an entry's ``last_seen`` moves only when an
        answer arrives.
        """
        if self._zc is None or not self.browsing:
            return {"queried": 0, "answered": 0}
        before = {k: n.last_seen for k, n in self._cache.items()}
        if self._browser is not None:
            try:
                await self._browser.async_cancel()
            except Exception:
                pass
        self._start_browser()
        names = list(self._names.keys())
        if names:
            await asyncio.gather(*(self._resolve(SERVICE_TYPE, n) for n in names),
                                 return_exceptions=True)
        await asyncio.sleep(wait_s)
        answered = sum(1 for k, n in self._cache.items()
                       if n.last_seen > before.get(k, 0.0))
        return {"queried": len(names), "answered": answered}

    # -- manual -----------------------------------------------------------------------
    def add_manual(self, host: str, port: int) -> DiscoveredNode:
        key = f"{host}:{port}"
        now = time.time()
        node = DiscoveredNode(node_id="", address=host, port=port,
                              discovered_at=now, last_seen=now, ttl_s=self.ttl_s,
                              source="manual", addresses=[host])
        self._cache[key] = node
        return node

    def mark_verified(self, node_id: str, address: str | None = None) -> None:
        """Called after a successful handshake with ``node_id``."""
        for node in self._cache.values():
            if node.node_id == node_id or (address and node.address == address
                                           and not node.node_id):
                node.node_id = node_id
                node.verified = True

    def entries(self, prune: bool = True) -> list[DiscoveredNode]:
        if prune:
            now = time.time()
            self._cache = {k: v for k, v in self._cache.items()
                           if not v.expired(now) and not v.removed}
            live = set(self._cache)
            self._names = {n: k for n, k in self._names.items() if k in live}
        return sorted(self._cache.values(), key=lambda n: -n.last_seen)


def _preferred(addresses: list[str], current: str) -> str:
    """Keep the current address if still announced; else prefer private LAN."""
    if current and current in addresses:
        return current
    for addr in addresses:
        try:
            if ipaddress.IPv4Address(addr).is_private:
                return addr
        except ValueError:
            continue
    return addresses[0]
