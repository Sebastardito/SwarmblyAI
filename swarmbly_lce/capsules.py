"""Cognitive capsules (SWIP 9–13, SPEC 12).

A capsule is a small signed object carrying generalisable written knowledge.
It is not a model, an adapter, a transcript or a proof of truth: a valid
signature proves only who signed. Version ``0.2`` adds anchoring, epistemic
distance, transmission path, anchored lineage and preservation.

Rules enforced here:

* bounds (16 KiB total, topic/statement/example limits) → ``E_CAPSULE_TOO_LARGE``;
* identifier = BLAKE2b-128 over canonical JSON of all fields but ``capsule_id``/``sig``;
* Ed25519 signature over canonical JSON of all fields but ``sig``;
* ``epistemic_distance > 1`` → no redistribution, no training (I3) → ``E_CAPSULE_DISTANCE``;
* a descendant without ``delta_evidence`` is a paraphrase → ``E_CAPSULE_NO_DELTA`` (I4);
* ``v: "0.1"`` capsules are treated as distance 2: local cache only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any

from . import CAPSULE_VERSION
from .canonical import canonical_bytes, digest16
from .crypto import Keypair, sign as ed_sign, verify as ed_verify
from .errors import CapsuleCode, CapsuleError
from .params import DEFAULT, Params

__all__ = [
    "KINDS",
    "Capsule",
    "DeltaEvidence",
    "CapsuleRequest",
    "CapsuleResponse",
    "Manifest",
    "CapsuleStore",
    "make_capsule",
    "make_descendant",
    "paraphrase_distance",
]

KINDS = frozenset({"term", "concept", "procedure", "style_pattern", "training_pattern"})
ANCHOR_KINDS = frozenset({"user_source", "public_source", "native_speaker_note"})
DELTA_KINDS = frozenset({"human_correction", "new_source", "native_speaker_note"})
PATHS = frozenset({"horizontal", "oblique"})


@dataclass(frozen=True)
class DeltaEvidence:
    kind: str
    digest: str

    def __post_init__(self) -> None:
        if self.kind not in DELTA_KINDS:
            raise CapsuleError(CapsuleCode.UNSUPPORTED, f"delta_evidence.kind {self.kind!r} not in {sorted(DELTA_KINDS)}")


@dataclass
class Capsule:
    origin_node: str
    kind: str
    topics: list[str]
    statement: str
    examples: list[str] = field(default_factory=list)
    anchor: dict[str, str] | None = None  # {"kind": ..., "digest": ...}
    epistemic_distance: int = 1
    transmission_path: str = "horizontal"
    parent_id: str | None = None
    revision: int = 0
    delta_evidence: DeltaEvidence | None = None
    preserve: bool = False
    permissions: dict[str, bool] = field(default_factory=lambda: {"cache": False, "redistribute": False, "train": False})
    expires_at: str | None = None
    v: str = CAPSULE_VERSION
    capsule_id: str = ""
    sig: str = ""

    # -- wire form --------------------------------------------------------------
    def _body(self) -> dict[str, Any]:
        lineage = {"parent_id": self.parent_id, "revision": self.revision,
                   "delta_evidence": None if self.delta_evidence is None else asdict(self.delta_evidence)}
        body: dict[str, Any] = {
            "v": self.v,
            "origin_node": self.origin_node,
            "kind": self.kind,
            "topics": list(self.topics),
            "statement": self.statement,
            "examples": list(self.examples),
            "permissions": {k: bool(self.permissions.get(k, False)) for k in ("cache", "redistribute", "train")},
            "expires_at": self.expires_at,
            "lineage": lineage,
        }
        if self.v == "0.2":
            body.update({
                "anchor": self.anchor,
                "epistemic_distance": self.epistemic_distance,
                "transmission_path": self.transmission_path,
                "preserve": self.preserve,
            })
        return body

    def compute_id(self) -> str:
        return digest16(self._body())

    def signing_payload(self) -> bytes:
        body = self._body()
        body["capsule_id"] = self.capsule_id
        return canonical_bytes(body)

    def to_dict(self) -> dict[str, Any]:
        d = self._body()
        d["capsule_id"] = self.capsule_id
        d["sig"] = self.sig
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def size_bytes(self) -> int:
        return len(self.to_json().encode("utf-8"))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Capsule":
        v = str(d.get("v", ""))
        if v not in {"0.1", "0.2"}:
            raise CapsuleError(CapsuleCode.UNSUPPORTED, f"capsule version {v!r}")
        lin = d.get("lineage") or {}
        de = lin.get("delta_evidence")
        c = cls(
            origin_node=d["origin_node"], kind=d["kind"], topics=list(d.get("topics", [])), statement=d["statement"],
            examples=list(d.get("examples", [])), permissions=dict(d.get("permissions", {})),
            expires_at=d.get("expires_at"), parent_id=lin.get("parent_id"), revision=int(lin.get("revision", 0)),
            delta_evidence=DeltaEvidence(**de) if de else None, v=v,
            capsule_id=d.get("capsule_id", ""), sig=d.get("sig", ""),
        )
        if v == "0.2":
            c.anchor = d.get("anchor")
            c.epistemic_distance = int(d.get("epistemic_distance", 2))
            c.transmission_path = d.get("transmission_path", "horizontal")
            c.preserve = bool(d.get("preserve", False))
        else:
            # SPEC 12.1.5: a v0.1 capsule is local cache only.
            c.epistemic_distance, c.delta_evidence = 2, None
        return c

    # -- validation -------------------------------------------------------------
    def validate(self, params: Params = DEFAULT) -> None:
        if self.kind not in KINDS:
            raise CapsuleError(CapsuleCode.UNSUPPORTED, f"kind {self.kind!r}")
        if self.v == "0.2":
            if self.transmission_path not in PATHS:
                raise CapsuleError(CapsuleCode.UNSUPPORTED, f"transmission_path {self.transmission_path!r}")
            if not self.anchor or self.anchor.get("kind") not in ANCHOR_KINDS or not self.anchor.get("digest"):
                raise CapsuleError(CapsuleCode.UNSUPPORTED, "v0.2 capsules require an anchor {kind, digest}")
            if self.epistemic_distance < 0:
                raise CapsuleError(CapsuleCode.UNSUPPORTED, "negative epistemic distance")
        b = lambda s: len(s.encode("utf-8"))  # noqa: E731
        if len(self.topics) > params.capsule_max_topics or any(b(t) > params.capsule_topic_max_bytes for t in self.topics):
            raise CapsuleError(CapsuleCode.TOO_LARGE, "topics exceed bounds")
        if b(self.statement) > params.capsule_statement_max_bytes:
            raise CapsuleError(CapsuleCode.TOO_LARGE, "statement exceeds 8192 bytes")
        if len(self.examples) > params.capsule_max_examples or any(b(e) > params.capsule_example_max_bytes for e in self.examples):
            raise CapsuleError(CapsuleCode.TOO_LARGE, "examples exceed bounds")
        if self.size_bytes() > params.capsule_max_bytes:
            raise CapsuleError(CapsuleCode.TOO_LARGE, "capsule exceeds 16384 bytes")
        if self.capsule_id and self.capsule_id != self.compute_id():
            raise CapsuleError(CapsuleCode.BAD_SIGNATURE, "capsule_id does not match content")
        if self.parent_id is not None and self.delta_evidence is not None and self.epistemic_distance != 1:
            raise CapsuleError(CapsuleCode.DISTANCE, "an anchored variant must have epistemic_distance = 1")

    # -- signatures -------------------------------------------------------------
    def sign_with(self, keypair: Keypair) -> "Capsule":
        if keypair.public != self.origin_node:
            raise CapsuleError(CapsuleCode.BAD_SIGNATURE, "signing key does not match origin_node")
        self.capsule_id = self.compute_id()
        self.sig = ed_sign(keypair, self.signing_payload())
        return self

    def verify_signature(self) -> None:
        if not self.sig or self.capsule_id != self.compute_id():
            raise CapsuleError(CapsuleCode.BAD_SIGNATURE, "missing signature or identifier mismatch")
        if not ed_verify(self.origin_node, self.signing_payload(), self.sig):
            raise CapsuleError(CapsuleCode.BAD_SIGNATURE, "Ed25519 verification failed")

    # -- permissions under the invariants ---------------------------------------
    @property
    def is_descendant(self) -> bool:
        return self.parent_id is not None

    def check_redistributable(self) -> None:
        if not self.permissions.get("redistribute", False):
            raise CapsuleError(CapsuleCode.FORBIDDEN, "redistribute permission is false")
        self._check_lineage_and_distance()

    def check_trainable(self) -> None:
        if not self.permissions.get("train", False):
            raise CapsuleError(CapsuleCode.FORBIDDEN, "train permission is false")
        self._check_lineage_and_distance()

    def _check_lineage_and_distance(self) -> None:
        if self.epistemic_distance > DEFAULT.epistemic_max_share_train:
            raise CapsuleError(CapsuleCode.DISTANCE, f"epistemic distance {self.epistemic_distance} > 1")
        if self.is_descendant and self.delta_evidence is None:
            raise CapsuleError(CapsuleCode.NO_DELTA, "descendant without new human evidence is a paraphrase")


def make_capsule(keypair: Keypair, *, kind: str, topics: list[str], statement: str, anchor_kind: str, anchor_digest: str,
                 examples: list[str] | None = None, permissions: dict[str, bool] | None = None, preserve: bool = False,
                 transmission_path: str = "horizontal", params: Params = DEFAULT) -> Capsule:
    c = Capsule(origin_node=keypair.public, kind=kind, topics=topics, statement=statement, examples=examples or [],
                anchor={"kind": anchor_kind, "digest": anchor_digest}, epistemic_distance=1,
                transmission_path=transmission_path, preserve=preserve,
                permissions=permissions or {"cache": False, "redistribute": False, "train": False})
    c.validate(params)
    return c.sign_with(keypair)


def make_descendant(parent: Capsule, keypair: Keypair, *, statement: str, delta: DeltaEvidence,
                    examples: list[str] | None = None, params: Params = DEFAULT) -> Capsule:
    """An anchored variant (SPEC 12.6): new human evidence, signed by the modifier, d = 1."""
    if delta is None:
        raise CapsuleError(CapsuleCode.NO_DELTA, "anchored variants require delta_evidence")
    c = Capsule(origin_node=keypair.public, kind=parent.kind, topics=list(parent.topics), statement=statement,
                examples=examples if examples is not None else list(parent.examples),
                anchor={"kind": delta.kind if delta.kind in ANCHOR_KINDS else "user_source", "digest": delta.digest},
                epistemic_distance=1, transmission_path="horizontal", parent_id=parent.capsule_id,
                revision=parent.revision + 1, delta_evidence=delta, preserve=parent.preserve,
                permissions=dict(parent.permissions))
    c.validate(params)
    return c.sign_with(keypair)


def paraphrase_distance(parent: Capsule) -> int:
    """Distance of a model-made reformulation kept locally (SPEC 12.5)."""
    return parent.epistemic_distance + 1


@dataclass
class CapsuleRequest:
    topics: list[str]
    kind: str | None = None
    max_bytes: int = 16_384
    request_id: str = ""

    def validate(self, params: Params = DEFAULT) -> None:
        if not params.request_min_topics <= len(self.topics) <= params.request_max_topics:
            raise CapsuleError(CapsuleCode.TOO_LARGE, "a request must carry 1–8 topics")
        if any(len(t.encode("utf-8")) > params.capsule_topic_max_bytes for t in self.topics):
            raise CapsuleError(CapsuleCode.TOO_LARGE, "topic exceeds 64 bytes")
        if not params.request_min_bytes <= self.max_bytes <= params.capsule_max_bytes:
            raise CapsuleError(CapsuleCode.TOO_LARGE, "max_bytes outside [512, 16384]")
        if self.kind is not None and self.kind not in KINDS:
            raise CapsuleError(CapsuleCode.UNSUPPORTED, f"kind {self.kind!r}")


@dataclass
class CapsuleResponse:
    request_id: str
    capsules: list[Capsule] = field(default_factory=list)
    error: CapsuleCode | None = None


@dataclass
class Manifest:
    node: str
    topics: set[str] = field(default_factory=set)
    capsule_ids: set[str] = field(default_factory=set)


@dataclass
class CapsuleStore:
    """Local capsule store: origin capsules, cached copies, and serving."""

    node: str
    params: Params = DEFAULT
    capsules: dict[str, Capsule] = field(default_factory=dict)
    origin_ids: set[str] = field(default_factory=set)
    served_bytes: int = 0
    received_bytes: int = 0

    def add_origin(self, c: Capsule) -> None:
        c.validate(self.params)
        self.capsules[c.capsule_id] = c
        self.origin_ids.add(c.capsule_id)

    def receive(self, c: Capsule, *, verify: bool = True) -> bool:
        """Validate and cache a received capsule if its permissions allow caching."""
        c.validate(self.params)
        if verify:
            c.verify_signature()
        self.received_bytes += c.size_bytes()
        if c.permissions.get("cache", False):
            self.capsules[c.capsule_id] = c
            return True
        return False

    def manifest(self) -> Manifest:
        servable = [c for c in self.capsules.values() if self._servable(c)]
        return Manifest(node=self.node, topics={t for c in servable for t in c.topics}, capsule_ids={c.capsule_id for c in servable})

    def _servable(self, c: Capsule) -> bool:
        if c.capsule_id in self.origin_ids:
            return True
        try:
            c.check_redistributable()
            return True
        except CapsuleError:
            return False

    def serve(self, req: CapsuleRequest) -> CapsuleResponse:
        try:
            req.validate(self.params)
        except CapsuleError as exc:
            return CapsuleResponse(req.request_id, [], exc.code)
        want = set(req.topics)
        matches = sorted((c for c in self.capsules.values()
                          if self._servable(c) and want & set(c.topics) and (req.kind is None or c.kind == req.kind)),
                         key=lambda c: c.capsule_id)
        out, total = [], 0
        limit = min(req.max_bytes, self.params.capsule_max_bytes)
        for c in matches:
            if len(out) >= self.params.response_max_capsules:
                break
            if total + c.size_bytes() > limit:
                continue
            out.append(c)
            total += c.size_bytes()
        if not out:
            return CapsuleResponse(req.request_id, [], CapsuleCode.NOT_FOUND)
        self.served_bytes += total
        return CapsuleResponse(req.request_id, out, None)
