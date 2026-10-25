"""Task Projection onto Γ and double privacy classification (SPEC 8).

The projection is the only way personal state enters the network: the
minimal, task-relevant information, expressed in fields the protocol's global
contract already defines (``audience``, ``register``, ``lexicon``,
``entities``, ``style_seed``). No new message type.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable

from .claims import Claim, ClaimType, Status
from .params import DEFAULT, Params
from .retrieval import BM25Retriever

__all__ = ["Lane", "PrivacyClassifier", "HeuristicClassifier", "TaskProjection", "Projector", "ProjectionResult"]


class Lane(IntEnum):
    """Sensitivity lanes of the protocol, ordered so that max() raises."""

    PUBLIC = 0
    SANITISABLE = 1
    SENSITIVE = 2


class PrivacyClassifier:
    def classify(self, text: str) -> Lane:  # pragma: no cover - interface
        raise NotImplementedError


_SENSITIVE = re.compile(
    r"\b(diagn[oó]stic|diagnos|salud|health|m[eé]dic|medical|legal|abogado|lawyer|salario|salary|deuda|debt|"
    r"contraseña|password|tarjeta|credit card|iban|ssn|pasaporte|passport)\w*", re.I)
_SANITISABLE = re.compile(
    r"(\b[\w.+-]+@[\w-]+\.[\w.]+\b|\+?\d[\d\s().-]{7,}\d|\b(mi jefe|my boss|mi esposa|my wife|mi hijo|my son|"
    r"vivo en|i live in|mi dirección|my address|nombre completo|full name)\b)", re.I)


@dataclass
class HeuristicClassifier(PrivacyClassifier):
    """Conservative regex baseline. Its error rate is an object of measurement (C3)."""

    def classify(self, text: str) -> Lane:
        if _SENSITIVE.search(text):
            return Lane.SENSITIVE
        if _SANITISABLE.search(text):
            return Lane.SANITISABLE
        return Lane.PUBLIC


@dataclass
class TaskProjection:
    audience: str = ""
    register: str = ""
    lexicon: dict[str, str] = field(default_factory=dict)
    entities: dict[str, str] = field(default_factory=dict)
    style_seed: str = ""
    sources: list[str] = field(default_factory=list)  # claim ids used (local only, never sent)

    def gamma_fields(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.audience:
            out["audience"] = self.audience
        if self.register:
            out["register"] = self.register
        if self.lexicon:
            out["lexicon"] = dict(sorted(self.lexicon.items()))
        if self.entities:
            out["entities"] = dict(sorted(self.entities.items()))
        if self.style_seed:
            out["style_seed"] = self.style_seed
        return out

    def size_bytes(self) -> int:
        return len(json.dumps(self.gamma_fields(), ensure_ascii=False, sort_keys=True).encode("utf-8"))

    def as_text(self) -> str:
        g = self.gamma_fields()
        return " ".join(f"{k}: {v}" for k, v in g.items())


@dataclass
class ProjectionResult:
    projection: TaskProjection
    lane_initial: Lane
    lane_final: Lane
    dropped: list[str]

    @property
    def local_only(self) -> bool:
        return self.lane_final == Lane.SENSITIVE


_EXCLUDED = frozenset({ClaimType.EXPERIENCE, ClaimType.USER_CLAIM, ClaimType.OPINION, ClaimType.BELIEF,
                       ClaimType.HYPOTHESIS, ClaimType.FACT})
_LEX = re.compile(r"(?:t[eé]rmino|term)\s+['\"«]?([\w\s-]{2,60}?)['\"»]?\s+(?:en lugar de|instead of)\s+['\"«]?([\w\s-]{2,60}?)['\"»]?[.,;]", re.I)
_REG = re.compile(r"registro\s+([\w\s]+?)(?:[.,;]|$)|(\w+(?:\s\w+)?)\s+register", re.I)


@dataclass
class Projector:
    """Builds a projection from retrieved behavioural claims (SPEC 8.2)."""

    classifier: PrivacyClassifier = field(default_factory=HeuristicClassifier)
    params: Params = DEFAULT
    k: int = 8
    audience: str = ""
    entities: dict[str, str] = field(default_factory=dict)
    # Optional reader of a claim's anchored span. When given, lexicon and register are
    # read from the user's own anchored words rather than from the digester's paraphrase.
    span_text: Callable[[Claim], str] | None = None

    def project(self, request: str, claims: list[Claim]) -> ProjectionResult:
        lane0 = self.classifier.classify(request)
        usable = [c for c in claims if c.type not in _EXCLUDED and c.anchored and c.status != Status.RETRACTED]
        hits = BM25Retriever().index(usable).search(request, k=self.k) if usable else []
        if not hits:
            # Behavioural traits apply broadly; fall back to the most mature ones.
            hits_claims = sorted(usable, key=lambda c: (-c.maturity.rank, c.claim_id))[: self.k]
        else:
            hits_claims = [h.claim for h in hits]
        proj = TaskProjection(audience=self.audience, entities=dict(self.entities))
        dropped: list[str] = []
        for c in hits_claims:
            src = c.text
            if self.span_text is not None:
                try:
                    src = self.span_text(c) or c.text
                except (OSError, ValueError, KeyError):
                    src = c.text
            m = _LEX.search(src)
            if m:
                proj.lexicon[m.group(1).strip()] = "preferred"
                proj.lexicon[m.group(2).strip()] = "avoid"
                proj.sources.append(c.claim_id)
                continue
            m = _REG.search(src)
            if m and not proj.register:
                proj.register = (m.group(1) or m.group(2) or "").strip()
                proj.sources.append(c.claim_id)
                continue
            if c.type == ClaimType.STYLE and not proj.style_seed:
                # A short descriptor, never the user's literal text.
                words = c.text.split()
                proj.style_seed = "style: " + " ".join(words[: min(12, len(words))])
                proj.sources.append(c.claim_id)
            else:
                dropped.append(c.claim_id)
        # Byte cap: drop lowest-priority fields until within budget (SPEC 8.2.3).
        for fld in ("style_seed", "entities", "lexicon", "register", "audience"):
            if proj.size_bytes() <= self.params.projection_max_bytes:
                break
            setattr(proj, fld, {} if isinstance(getattr(proj, fld), dict) else "")
            dropped.append(f"field:{fld}")
        lane1 = max(lane0, self.classifier.classify(request + " " + proj.as_text()))
        return ProjectionResult(projection=proj, lane_initial=lane0, lane_final=Lane(lane1), dropped=dropped)
