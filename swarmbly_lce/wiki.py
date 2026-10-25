"""The wiki: layer 1 of the local plane (SPEC 6).

The wiki holds claims, their links and their dependencies. All index,
link, dependency and state-transition logic here is deterministic code; the
model only proposes claims (see ``digest.py``). The store is a single JSON
file, deterministic and diff-friendly, so that a Git history of the wiki
(SPEC 6.8) shows how the user's model's understanding changed.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from .claims import (
    Anchor,
    Claim,
    ClaimType,
    Maturity,
    Status,
    Transmission,
    advance,
    regress,
)
from .canonical import digest16
from .depgraph import DependencyGraph
from .errors import InvariantViolation, TransitionError
from .params import DEFAULT, Params
from .policy import LearningPolicy

__all__ = ["Wiki", "CycleReport"]


@dataclass
class CycleReport:
    advanced: dict[str, str] = field(default_factory=dict)
    blocked: dict[str, str] = field(default_factory=dict)
    stale: set[str] = field(default_factory=set)


@dataclass
class Wiki:
    policy: LearningPolicy = field(default_factory=LearningPolicy)
    params: Params = DEFAULT
    claims: dict[str, Claim] = field(default_factory=dict)
    graph: DependencyGraph = field(default_factory=DependencyGraph)
    source_hashes: dict[str, str] = field(default_factory=dict)
    cycle: int = 0

    # -- registration -----------------------------------------------------------
    def _source_node(self, source: str) -> str:
        return f"source:{source}"

    def _policy_node(self, source: str) -> str:
        return f"policy:{source}:{digest16(self.policy.fingerprint(source))[:12]}"

    def register_source(self, source: str, sha256: str) -> set[str]:
        """Register or refresh a source; a changed hash invalidates descendants."""
        node = self._source_node(source)
        self.graph.add_node(node, "source")
        stale: set[str] = set()
        prev = self.source_hashes.get(source)
        if prev is not None and prev != sha256:
            stale = self.graph.invalidate(node)
            for cid in [n.split(":", 1)[1] for n in stale if n.startswith("claim:")]:
                c = self.claims.get(cid)
                if c is not None:
                    regress(c, "anchor_lost")
        self.source_hashes[source] = sha256
        return stale

    def add(self, claim: Claim) -> Claim:
        """Add a claim, or merge anchors into an existing one with the same id."""
        if claim.type == ClaimType.EXPERIENCE:
            for a in claim.anchors:
                if not self.policy.rule_for(a.source).retain_episodic:
                    raise InvariantViolation("I8", f"source {a.source!r} does not allow retaining episodic memory")
        existing = self.claims.get(claim.claim_id)
        if existing is not None:
            known = {(a.source, a.start, a.end) for a in existing.anchors}
            existing.anchors.extend(a for a in claim.anchors if (a.source, a.start, a.end) not in known)
            existing.updated = time.time()
            claim = existing
        else:
            if claim.maturity == Maturity.RAW:
                claim.maturity = Maturity.DIGESTED
            self.claims[claim.claim_id] = claim
        cnode = f"claim:{claim.claim_id}"
        self.graph.add_node(cnode, "claim")
        for a in claim.anchors:
            if a.source not in self.source_hashes:
                self.register_source(a.source, a.source_hash)
            snode = self._source_node(a.source)
            pnode = self._policy_node(a.source)
            self.graph.add_node(pnode, "policy")
            if cnode not in self.graph.children.get(snode, set()):
                self.graph.add_edge(snode, cnode)
            if cnode not in self.graph.children.get(pnode, set()):
                self.graph.add_edge(pnode, cnode)
        return claim

    def link(self, a: str, b: str) -> None:
        self.claims[a].links.add(b)
        self.claims[b].links.add(a)

    def contest(self, claim_id: str, positions: list) -> None:
        c = self.claims[claim_id]
        regress(c, "contradiction")
        c.positions = list(positions)

    # -- policy -----------------------------------------------------------------
    def policy_allows(self, claim: Claim) -> bool:
        if not claim.behavioural or not claim.anchors:
            return False
        return all(self.policy.rule_for(a.source).allows_type(claim.type.value) for a in claim.anchors)

    def set_policy(self, policy: LearningPolicy) -> set[str]:
        """Change the policy; claims whose effective rule changed become stale (SPEC 5.2.6)."""
        old = self.policy
        self.policy = policy
        stale: set[str] = set()
        for c in self.claims.values():
            if any(old.fingerprint(a.source) != policy.fingerprint(a.source) for a in c.anchors):
                stale |= self.graph.invalidate(f"claim:{c.claim_id}") | {f"claim:{c.claim_id}"}
                if c.maturity == Maturity.TRAINABLE and not self.policy_allows(c):
                    c.maturity = Maturity.CONSOLIDATED
        self.graph.stale |= stale
        return stale

    # -- consolidation ----------------------------------------------------------
    def consolidation_cycle(self) -> CycleReport:
        """Advance every claim as far as its conditions allow (deterministic)."""
        self.cycle += 1
        rep = CycleReport()
        for cid, c in sorted(self.claims.items()):
            if c.status == Status.RETRACTED:
                continue
            if c.behavioural and c.anchored:
                c.cycles_observed += 1
            if c.status == Status.ACTIVE and c.maturity.rank >= Maturity.CORROBORATED.rank:
                c.clean_review_cycles += 1
            start = c.maturity
            while c.maturity != Maturity.TRAINABLE:
                if c.maturity == Maturity.CONSOLIDATED and not c.behavioural:
                    break
                try:
                    advance(c, policy_allows_training=self.policy_allows(c), params=self.params)
                except TransitionError as exc:
                    rep.blocked[cid] = str(exc)
                    break
            if c.maturity != start:
                rep.advanced[cid] = f"{start.value}→{c.maturity.value}"
        rep.stale = set(self.graph.stale)
        return rep

    # -- forgetting -------------------------------------------------------------
    def forget_source(self, source: str) -> set[str]:
        """Remove a source and every claim anchored only to it (SPEC 7.8.1)."""
        node = self._source_node(source)
        stale = self.graph.remove(node) if node in self.graph.kinds else set()
        removed = []
        for cid, c in list(self.claims.items()):
            remaining = [a for a in c.anchors if a.source != source]
            if not remaining:
                removed.append(cid)
                del self.claims[cid]
                self.graph.remove(f"claim:{cid}")
            elif len(remaining) != len(c.anchors):
                c.anchors = remaining
                if c.maturity.rank > Maturity.ANCHORED.rank and c.type == ClaimType.FACT and c.independent_human_sources() < 2:
                    c.maturity = Maturity.CONNECTED
        self.source_hashes.pop(source, None)
        return stale | {f"claim:{r}" for r in removed}

    # -- queries ----------------------------------------------------------------
    def trainable(self) -> list[Claim]:
        return [c for c in self.claims.values()
                if c.maturity == Maturity.TRAINABLE and not self.graph.is_stale(f"claim:{c.claim_id}")]

    def self_space(self) -> list[Claim]:
        return [c for c in self.claims.values() if c.provenance.transmission_path == Transmission.VERTICAL]

    def social_space(self) -> list[Claim]:
        return [c for c in self.claims.values() if c.provenance.transmission_path != Transmission.VERTICAL]

    # -- persistence ------------------------------------------------------------
    def to_json(self) -> str:
        data = {
            "v": "0.1",
            "cycle": self.cycle,
            "source_hashes": dict(sorted(self.source_hashes.items())),
            "claims": [self.claims[k].to_dict() for k in sorted(self.claims)],
            "stale": sorted(self.graph.stale),
        }
        return json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.to_json() + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path, policy: LearningPolicy | None = None, params: Params = DEFAULT) -> "Wiki":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        w = cls(policy=policy or LearningPolicy(), params=params)
        w.cycle = int(data.get("cycle", 0))
        for s, h in data.get("source_hashes", {}).items():
            w.register_source(s, h)
        for d in data.get("claims", []):
            c = Claim.from_dict(d)
            m = c.maturity
            w.add(c)
            c.maturity = m
        w.graph.stale |= set(data.get("stale", []))
        return w

    def export_markdown(self, directory: str | Path) -> list[Path]:
        """Write one Markdown page per claim type; human-readable, not the store."""
        out_dir = Path(directory)
        out_dir.mkdir(parents=True, exist_ok=True)
        written = []
        by_type: dict[str, list[Claim]] = {}
        for c in self.claims.values():
            by_type.setdefault(c.type.value, []).append(c)
        for t, cs in sorted(by_type.items()):
            lines = [f"# {t}", ""]
            for c in sorted(cs, key=lambda x: x.claim_id):
                anchors = "; ".join(f"{a.source}[{a.start}:{a.end}]{'✓' if a.verified else '✗'}" for a in c.anchors)
                lines.append(f"- **{c.maturity.value}** · d={c.provenance.epistemic_distance} · {c.provenance.transmission_path.value} · `{c.claim_id}`")
                lines.append(f"  {c.text}")
                lines.append(f"  anchors: {anchors or '—'}")
            p = out_dir / f"{t}.md"
            p.write_text("\n".join(lines) + "\n", encoding="utf-8")
            written.append(p)
        return written

    def new_anchor(self, source: str, start: int, end: int, *, human_source: str = "self") -> Anchor:
        sha = self.source_hashes.get(source, "")
        return Anchor(source=source, start=start, end=end, source_hash=sha, human_source=human_source)
