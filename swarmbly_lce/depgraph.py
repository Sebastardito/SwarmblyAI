"""Dependency graph with build-system semantics (SPEC 6.7).

Nodes are typed (``source``, ``policy``, ``claim``, ``concept``, ``example``,
``adapter``); edges point from a dependency to what depends on it. When a node
changes, every descendant is marked ``stale``; an adapter with any stale
ancestor is ``affected`` and must be regenerated (SPEC 7.8).
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Iterable

from .errors import CycleError

__all__ = ["DependencyGraph", "NODE_KINDS"]

NODE_KINDS = frozenset({"source", "policy", "claim", "concept", "example", "adapter"})


@dataclass
class DependencyGraph:
    kinds: dict[str, str] = field(default_factory=dict)
    children: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    parents: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    stale: set[str] = field(default_factory=set)

    def add_node(self, node: str, kind: str) -> None:
        if kind not in NODE_KINDS:
            raise ValueError(f"unknown node kind {kind!r}")
        prev = self.kinds.get(node)
        if prev is not None and prev != kind:
            raise ValueError(f"node {node!r} already registered as {prev!r}")
        self.kinds[node] = kind

    def add_edge(self, dependency: str, dependent: str) -> None:
        for n in (dependency, dependent):
            if n not in self.kinds:
                raise KeyError(f"unknown node {n!r}")
        if dependency == dependent or self._reaches(dependent, dependency):
            raise CycleError(f"edge {dependency!r} → {dependent!r} would create a cycle")
        self.children[dependency].add(dependent)
        self.parents[dependent].add(dependency)

    def _reaches(self, start: str, goal: str) -> bool:
        seen, queue = {start}, deque([start])
        while queue:
            n = queue.popleft()
            if n == goal:
                return True
            for c in self.children.get(n, ()):
                if c not in seen:
                    seen.add(c)
                    queue.append(c)
        return False

    def descendants(self, node: str) -> set[str]:
        out: set[str] = set()
        queue = deque(self.children.get(node, ()))
        while queue:
            n = queue.popleft()
            if n in out:
                continue
            out.add(n)
            queue.extend(self.children.get(n, ()))
        return out

    def ancestors(self, node: str) -> set[str]:
        out: set[str] = set()
        queue = deque(self.parents.get(node, ()))
        while queue:
            n = queue.popleft()
            if n in out:
                continue
            out.add(n)
            queue.extend(self.parents.get(n, ()))
        return out

    def invalidate(self, node: str) -> set[str]:
        """Mark every descendant of ``node`` stale; return the newly stale set."""
        newly = self.descendants(node) - self.stale
        self.stale |= newly
        return newly

    def remove(self, node: str) -> set[str]:
        """Remove ``node`` (e.g. a forgotten source); descendants become stale."""
        newly = self.invalidate(node)
        for c in self.children.pop(node, set()):
            self.parents[c].discard(node)
        for p in self.parents.pop(node, set()):
            self.children[p].discard(node)
        self.kinds.pop(node, None)
        self.stale.discard(node)
        return newly

    def clear(self, nodes: Iterable[str]) -> None:
        """Clear the stale mark after a rebuild."""
        self.stale -= set(nodes)

    def affected_adapters(self) -> set[str]:
        return {n for n in self.stale if self.kinds.get(n) == "adapter"}

    def is_stale(self, node: str) -> bool:
        return node in self.stale
