"""Swarm Monitor: health and contribution (user additions A and B).

Swarm Health is NOT an arbitrary score: it exposes independent, labelled
metrics (availability, family diversity, verified vs announced capacity,
latency where measured). Swarm Contribution aggregates what this node has
actually served and transferred — real counters, never estimates disguised as
measurements.
"""

from __future__ import annotations

from typing import Any


def swarm_health(swarm: dict[str, Any]) -> dict[str, Any]:
    """Independent health indicators for the current swarm view."""
    peers = swarm.get("peers", [])
    discovered = swarm.get("discovered", [])
    connected = [p for p in peers if p.get("connected")]
    verified = [p for p in peers if p.get("verified")]
    families: set[str] = set()
    announced_models = 0
    verified_models = 0
    for peer in peers:
        for model in peer.get("models", []):
            announced_models += 1
            family = model.get("family") or "unknown"
            families.add(family)
            if peer.get("verified"):
                verified_models += 1
    return {
        "availability": {
            "discovered": len(discovered),
            "connected": len(connected),
            "verified": len(verified),
            # announced ≠ reachable; only handshake-verified nodes count as usable
            "value": f"{len(verified)} verified / {len(discovered)} discovered",
            "source": "Ed25519 handshake bound to TLS (identity proven, "
                      "capacity not yet verified by a task)",
        },
        "model_diversity": {
            "families": sorted(families),
            "distinct_families": len(families),
            "value": f"{len(families)} model families",
            "source": "peer advertisements after authenticated handshake",
            "caveat": "family diversity attenuates correlated errors; it does "
                      "not remove them (SwarmblyAI L23)",
        },
        "capacity": {
            "announced_models": announced_models,
            "verified_models": verified_models,
            "value": f"{verified_models} verified / {announced_models} announced models",
            "source": "verified by handshake only, not by task completion",
        },
        "latency": _latency(peers),
        "stability": {
            "value": "not yet measured",
            "source": "no simulated values",
        },
    }


def contribution(stats: list[dict[str, Any]]) -> dict[str, Any]:
    """What this node gave to others (worker role) — never mixed with what it
    consumed locally. All counters are measured, from local SQLite."""
    def total(key: str) -> int:
        return sum(int(s.get(key, 0) or 0) for s in stats)
    return {
        "tasks_served": total("tasks_served"),
        "processing_time_ms": total("served_ms"),
        "tokens_generated": total("served_tokens"),
        "bytes_transferred": {"in": total("bytes_in"), "out": total("bytes_out")},
        "consumed": {"local_requests": total("tasks_requested"),
                     "local_generation_ms": total("gen_ms"),
                     "distributed_requests": total("distributed_requests"),
                     "tasks_dispatched": total("dispatched")},
        "window_days": len(stats),
        "source": "local SQLite counters (measured)",
    }


def _latency(peers: list[dict[str, Any]]) -> dict[str, Any]:
    rtts = sorted(p["rtt_ms"] for p in peers
                  if p.get("connected") and p.get("rtt_ms") is not None)
    if not rtts:
        return {"value": "not measured yet", "source": "ping/pong every 30 s"}
    median = rtts[len(rtts) // 2]
    return {"median_rtt_ms": median, "max_rtt_ms": rtts[-1],
            "value": f"median RTT {median} ms", "source": "ping/pong (measured)"}
