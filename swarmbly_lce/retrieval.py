"""Retrieval over the wiki (stdlib + numpy).

BM25 over claim text, with the rule that attributed claims are rendered with
their attribution (SPEC 6.4) and retracted claims are never returned.
Contested claims are returned with all their positions (SPEC 14.3).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

from .claims import Claim, Status

__all__ = ["BM25Retriever", "Hit"]

_TOKEN = re.compile(r"[\wáéíóúñü]+", re.IGNORECASE)


def _tok(text: str) -> list[str]:
    return [w.lower() for w in _TOKEN.findall(text) if len(w) > 1]


@dataclass
class Hit:
    claim: Claim
    score: float

    @property
    def text(self) -> str:
        base = self.claim.render_for_retrieval()
        if self.claim.status == Status.CONTESTED and self.claim.positions:
            pos = " | ".join(f"{p.stance} ({', '.join(p.families) or 'evidence'})" for p in self.claim.positions)
            return f"[contested] {base} — positions: {pos}"
        return base


@dataclass
class BM25Retriever:
    k1: float = 1.5
    b: float = 0.75
    docs: list[Claim] = field(default_factory=list)
    _tf: list[Counter] = field(default_factory=list)
    _df: Counter = field(default_factory=Counter)
    _avg: float = 0.0

    def index(self, claims: Iterable[Claim]) -> "BM25Retriever":
        self.docs = [c for c in claims if c.status != Status.RETRACTED]
        self._tf = [Counter(_tok(c.text)) for c in self.docs]
        self._df = Counter()
        for tf in self._tf:
            self._df.update(tf.keys())
        self._avg = sum(sum(tf.values()) for tf in self._tf) / max(1, len(self._tf))
        return self

    def search(self, query: str, k: int = 5) -> list[Hit]:
        q = _tok(query)
        n = len(self.docs)
        scores = []
        for i, tf in enumerate(self._tf):
            dl = sum(tf.values()) or 1
            s = 0.0
            for t in q:
                if t not in tf:
                    continue
                idf = math.log(1 + (n - self._df[t] + 0.5) / (self._df[t] + 0.5))
                s += idf * tf[t] * (self.k1 + 1) / (tf[t] + self.k1 * (1 - self.b + self.b * dl / (self._avg or 1)))
            if s > 0:
                scores.append(Hit(self.docs[i], s))
        scores.sort(key=lambda h: (-h.score, h.claim.claim_id))
        return scores[:k]
