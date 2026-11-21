"""Reciprocity credits: signed, non-transferable task receipts (D-020).

A credit is a receipt the **requester** signs for a **worker** after a
verified result is accepted: circle, issuer, worker, a hash of the attempt id
(never task content), tokens out, generation time, model, timestamps. It is
kept in the worker's local wallet and can only be spent by that worker, only
in the same circle, and only when it later sends work to a member of that
circle. There is no transfer API, no export as a token, no market and no
global ledger (SPEC §18, GOVERNANCE).

Three MINOR-safe control messages ride on the existing TLS session (D-021;
older nodes ignore unknown ``type`` values, SPEC §3):

``credit_receipt``
    issuer → worker, carries one signed receipt. Stored only when the
    signature is valid, the receipt is addressed to this node, the issuer and
    this node are listed by a valid manifest of the receipt's circle, it is
    unexpired and its id is new.
``credit_spend``
    spender → worker, carries one receipt and the attempt id it is offered
    for, sent just before the task. The receiver checks the receipt again and
    grants queue priority over an uncredited task **only while busy**. It
    never bypasses admission, the egress gate, lane/tier or any policy.
``credit_spent``
    worker → issuer, carries only the receipt id and the spender. The issuer
    keeps a bounded log of what it issued and what was reported spent; a
    receipt reported twice is flagged. Detection, not prevention; nothing is
    broadcast beyond the circle.

A receipt is one indivisible courtesy unit: spending it grants priority for
one task and consumes the whole receipt. ``tokens_out`` is honest provenance,
not a redeemable fraction. Credits expire (default 90 days).

Balance/earned/spent count whole receipts because a receipt is one indivisible
courtesy unit; ``tokens_out`` is provenance, not a redeemable fraction.

A stolen node key can spend that node's receipts until the owner revokes the
member (R-010): the manifest is the only membership authority in 3.5.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

from .. import egress
from ..identity import IdentityManager, b64url, b64url_decode
from .circles import (CircleError, _valid_circle_id, _valid_node_id)
from .messages import WIRE_VERSION, canonical_bytes, verify_signed

log = logging.getLogger("swarmbly.credits")

# Stable error codes of the credit layer.
E_CREDIT_REQUIRED = "E_CREDIT_REQUIRED"
E_CREDIT_SCHEMA = "E_CREDIT_SCHEMA"
E_CREDIT_SIGNATURE = "E_CREDIT_SIGNATURE"
E_CREDIT_EXPIRED = "E_CREDIT_EXPIRED"
E_CREDIT_DUPLICATE = "E_CREDIT_DUPLICATE"
E_CREDIT_NOT_MEMBER = "E_CREDIT_NOT_MEMBER"
E_CREDIT_WRONG_WORKER = "E_CREDIT_WRONG_WORKER"
E_CREDIT_SPENT = "E_CREDIT_SPENT"
E_CREDIT_WALLET_FULL = "E_CREDIT_WALLET_FULL"
E_CREDIT_UNKNOWN = "E_CREDIT_UNKNOWN"

CREDIT_TYPES = frozenset({"credit_receipt", "credit_spend", "credit_spent"})

DEFAULT_RECEIPT_TTL_DAYS = 90
EXPIRING_SOON_DAYS = 7
MAX_RECEIPT_BYTES = 4096
MAX_CREDIT_MESSAGE_BYTES = 8192
MAX_WALLET_RECEIPTS = 256
MAX_ISSUED_RECEIPTS = 512
MAX_PENDING_REPORTS = 64
MAX_PENDING_PRIORITIES = 64
PRIORITY_TTL_S = 300
MAX_TOKENS_OUT = 10_000_000
MAX_GENERATION_MS = 24 * 60 * 60 * 1000
MAX_MODEL_CHARS = 128
MAX_ATTEMPT_CHARS = 128
MAX_RECEIPT_ID = 64

_ATTEMPT_HASH_RE = re.compile(r"^[0-9a-f]{32}$")
_ATTEMPT_ID_RE = re.compile(r"^[A-Za-z0-9:_.-]{1,128}$")
# The wallet record carries local metadata (received_at, spent_at, ...); only
# these signed fields may ever leave the node.
_RECEIPT_FIELDS = ("v", "type", "receipt_id", "circle_id", "issuer", "worker",
                   "attempt", "tokens_out", "generation_ms", "model",
                   "issued_at", "expires_at", "sig")


def receipt_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in _RECEIPT_FIELDS if key in record}


# -- message builders (the conformance-tested shapes of the appendix) --------
def credit_receipt_message(receipt: dict[str, Any]) -> dict[str, Any]:
    validate_receipt(receipt)
    return {"v": WIRE_VERSION, "type": "credit_receipt", "receipt": receipt}


def credit_spend_message(spender: str, attempt_id: str,
                         receipt: dict[str, Any]) -> dict[str, Any]:
    validate_receipt(receipt)
    if not _valid_node_id(spender) or receipt.get("worker") != spender:
        raise CreditError(E_CREDIT_WRONG_WORKER,
                          "only the named worker can spend the receipt")
    if not _ATTEMPT_ID_RE.fullmatch(str(attempt_id or "")):
        raise CreditError(E_CREDIT_SCHEMA, "invalid attempt_id")
    return {"v": WIRE_VERSION, "type": "credit_spend", "spender": spender,
            "attempt_id": str(attempt_id), "receipt": receipt}


def credit_spent_message(identity_manager: IdentityManager, receipt_id: str,
                         spender: str, *, by: str,
                         reported_at: int | None = None) -> dict[str, Any]:
    if not _valid_receipt_id(receipt_id):
        raise CreditError(E_CREDIT_SCHEMA, "invalid receipt_id")
    if not _valid_node_id(spender) or not _valid_node_id(by):
        raise CreditError(E_CREDIT_SCHEMA, "invalid spender/by node_id")
    return sign_receipt(identity_manager, {
        "v": WIRE_VERSION, "type": "credit_spent", "receipt_id": receipt_id,
        "spender": spender, "by": by,
        "reported_at": int(time.time()) if reported_at is None
        else int(reported_at),
    })


class CreditError(CircleError):
    """A credit operation refused with a stable code."""


def attempt_hash(attempt_id: str) -> str:
    """One-way hash of an attempt id: a receipt never carries task content."""
    return hashlib.blake2b(str(attempt_id).encode("utf-8"),
                           digest_size=16).hexdigest()


def _clean_model(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) > MAX_MODEL_CHARS:
        raise CreditError(E_CREDIT_SCHEMA,
                          f"model must be at most {MAX_MODEL_CHARS} characters")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise CreditError(E_CREDIT_SCHEMA, "model contains control characters")
    return text


def _bounded_int(value: Any, field: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CreditError(E_CREDIT_SCHEMA, f"{field} must be an integer")
    if not low <= value <= high:
        raise CreditError(E_CREDIT_SCHEMA,
                          f"{field} must be between {low} and {high}")
    return value


def _valid_receipt_id(value: Any) -> bool:
    if not isinstance(value, str) or not 8 <= len(value) <= MAX_RECEIPT_ID:
        return False
    try:
        return len(b64url_decode(value)) == 16
    except Exception:
        return False


def sign_receipt(identity_manager: IdentityManager,
                 unsigned: dict[str, Any]) -> dict[str, Any]:
    payload = {k: v for k, v in unsigned.items() if k != "sig"}
    signature = identity_manager.sign(canonical_bytes(payload))
    return {**payload, "sig": b64url(signature)}


def build_receipt(*, identity_manager: IdentityManager, circle_id: str,
                  issuer: str, worker: str, attempt_id: str,
                  tokens_out: int, generation_ms: int, model: str,
                  issued_at: int | None = None,
                  ttl_s: int = DEFAULT_RECEIPT_TTL_DAYS * 86400,
                  ) -> dict[str, Any]:
    """Build and sign one receipt. The signature is the issuer's."""
    now = int(time.time()) if issued_at is None else int(issued_at)
    receipt = sign_receipt(identity_manager, {
        "v": WIRE_VERSION,
        "type": "credit_receipt",
        "receipt_id": b64url(os.urandom(16)),
        "circle_id": circle_id,
        "issuer": issuer,
        "worker": worker,
        "attempt": attempt_hash(attempt_id),
        "tokens_out": int(tokens_out),
        "generation_ms": int(generation_ms),
        "model": _clean_model(model),
        "issued_at": now,
        "expires_at": now + max(1, int(ttl_s)),
    })
    return validate_receipt(receipt)


def validate_receipt(receipt: dict[str, Any], *, verify: bool = True,
                     now: int | None = None) -> dict[str, Any]:
    """Structural, size, signature and (optionally) expiry validation."""
    if not isinstance(receipt, dict):
        raise CreditError(E_CREDIT_SCHEMA, "receipt must be an object")
    try:
        size = len(canonical_bytes(receipt))
    except (TypeError, ValueError) as exc:
        raise CreditError(E_CREDIT_SCHEMA, "receipt is not canonical JSON") from exc
    if size > MAX_RECEIPT_BYTES:
        raise CreditError(E_CREDIT_SCHEMA,
                          f"receipt exceeds {MAX_RECEIPT_BYTES} bytes")
    if receipt.get("type") != "credit_receipt":
        raise CreditError(E_CREDIT_SCHEMA, "not a credit receipt")
    if not _valid_receipt_id(receipt.get("receipt_id")):
        raise CreditError(E_CREDIT_SCHEMA, "invalid receipt_id")
    if not _valid_circle_id(receipt.get("circle_id")):
        raise CreditError(E_CREDIT_SCHEMA, "invalid circle_id")
    issuer = receipt.get("issuer")
    worker = receipt.get("worker")
    if not _valid_node_id(issuer):
        raise CreditError(E_CREDIT_SCHEMA, "invalid issuer node_id")
    if not _valid_node_id(worker):
        raise CreditError(E_CREDIT_SCHEMA, "invalid worker node_id")
    if issuer == worker:
        raise CreditError(E_CREDIT_SCHEMA, "issuer and worker must differ")
    if not isinstance(receipt.get("attempt"), str) \
            or not _ATTEMPT_HASH_RE.fullmatch(str(receipt["attempt"])):
        raise CreditError(E_CREDIT_SCHEMA, "attempt must be a 32-hex hash")
    _bounded_int(receipt.get("tokens_out"), "tokens_out", 0, MAX_TOKENS_OUT)
    _bounded_int(receipt.get("generation_ms"), "generation_ms",
                 0, MAX_GENERATION_MS)
    _clean_model(receipt.get("model"))
    issued = _bounded_int(receipt.get("issued_at"), "issued_at", 0, 2 ** 53 - 1)
    expires = _bounded_int(receipt.get("expires_at"), "expires_at",
                           0, 2 ** 53 - 1)
    if expires <= issued:
        raise CreditError(E_CREDIT_SCHEMA, "expires_at must be after issued_at")
    if expires - issued > 366 * 86400:
        raise CreditError(E_CREDIT_SCHEMA, "receipt lifetime is too long")
    if verify and not verify_signed(issuer, receipt):
        raise CreditError(E_CREDIT_SIGNATURE,
                          "receipt signature is not the issuer's")
    if now is not None and int(now) >= expires:
        raise CreditError(E_CREDIT_EXPIRED, "credit receipt has expired")
    return receipt


def _atomic_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    tmp = path.with_name(f".{path.name}.tmp")
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(payload)
    os.replace(tmp, path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


class CreditService:
    """Local wallet, issuer log and the three credit control messages."""

    def __init__(self, identity_manager: IdentityManager, config: Any,
                 dirs: Any, bus: Any, circles: Any = None):
        self.identity_manager = identity_manager
        self.config = config
        self.bus = bus
        root = getattr(dirs, "root", dirs)
        self.root = Path(root) / "credits"
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.root, 0o700)
        except OSError:
            pass
        self.wallet_path = self.root / "wallet.json"
        self.issued_path = self.root / "issued.json"
        self.circles = circles
        self.node = None                  # set with attach()
        self._lock = threading.RLock()
        self._wallet: dict[str, Any] = {
            "version": 1, "receipts": {}, "circles": {},
            "seen_spends": {}, "pending_reports": [],
        }
        self._issued: dict[str, Any] = {"version": 1, "receipts": {}}
        self._priorities: dict[tuple[str, str], float] = {}
        self._load_wallet()
        self._load_issued()
        if circles is not None:
            self.attach(circles)

    # -- wiring -----------------------------------------------------------------
    def attach(self, circles: Any) -> None:
        self.circles = circles
        circles.credits = self
        if getattr(circles, "node", None) is not None:
            self.node = circles.node

    @property
    def node_id(self) -> str:
        return self.identity_manager.load_or_create().node_id

    def enabled(self) -> bool:
        return bool((self.config.all().get("credits") or {}).get("enabled", True))

    def ttl_days(self) -> int:
        try:
            days = int((self.config.all().get("credits") or {})
                       .get("receipt_ttl_days", DEFAULT_RECEIPT_TTL_DAYS))
        except (TypeError, ValueError):
            days = DEFAULT_RECEIPT_TTL_DAYS
        return max(1, min(days, 365))

    # -- persistence ------------------------------------------------------------
    def _load_wallet(self) -> None:
        data = _read_json(self.wallet_path)
        receipts: dict[str, dict[str, Any]] = {}
        raw = data.get("receipts") if isinstance(data.get("receipts"), dict) else {}
        for rid, record in raw.items():
            if not isinstance(record, dict):
                continue
            try:
                validate_receipt(record)
            except CreditError:
                continue
            if record.get("receipt_id") != rid:
                continue
            receipts[rid] = record
        circles: dict[str, dict[str, int]] = {}
        raw_circles = data.get("circles") if isinstance(data.get("circles"), dict) else {}
        for cid, counts in raw_circles.items():
            if not isinstance(counts, dict) or not _valid_circle_id(cid):
                continue
            circles[cid] = {
                "earned": max(0, int(counts.get("earned") or 0)),
                "spent": max(0, int(counts.get("spent") or 0)),
            }
        seen: dict[str, dict[str, Any]] = {}
        raw_seen = data.get("seen_spends") if isinstance(data.get("seen_spends"), dict) else {}
        for rid, item in raw_seen.items():
            if isinstance(item, dict) and _valid_receipt_id(rid):
                seen[rid] = item
        pending = [item for item in (data.get("pending_reports") or [])
                   if isinstance(item, dict) and isinstance(item.get("message"), dict)
                   and isinstance(item.get("to"), str)] if isinstance(
                       data.get("pending_reports"), list) else []
        self._wallet = {"version": 1, "receipts": receipts, "circles": circles,
                        "seen_spends": seen,
                        "pending_reports": pending[-MAX_PENDING_REPORTS:]}
        with self._lock:
            changed = self._prune_wallet_locked(int(time.time()))
            if changed:
                self._save_wallet_locked()

    def _load_issued(self) -> None:
        data = _read_json(self.issued_path)
        receipts: dict[str, dict[str, Any]] = {}
        raw = data.get("receipts") if isinstance(data.get("receipts"), dict) else {}
        for rid, record in raw.items():
            if not isinstance(record, dict):
                continue
            receipt = record.get("receipt")
            if not isinstance(receipt, dict):
                continue
            try:
                validate_receipt(receipt)
            except CreditError:
                continue
            if receipt.get("receipt_id") != rid:
                continue
            reports = [item for item in (record.get("reports") or [])
                       if isinstance(item, dict)] if isinstance(
                           record.get("reports"), list) else []
            receipts[rid] = {
                "receipt": receipt, "reports": reports,
                "flagged": bool(record.get("flagged")),
                "flagged_reason": str(record.get("flagged_reason") or ""),
                "flagged_at": record.get("flagged_at"),
            }
        self._issued = {"version": 1, "receipts": receipts}
        with self._lock:
            if self._prune_issued_locked():
                self._save_issued_locked()

    def _save_wallet_locked(self) -> None:
        _atomic_write(self.wallet_path, self._wallet)

    def _save_issued_locked(self) -> None:
        _atomic_write(self.issued_path, self._issued)

    def _prune_wallet_locked(self, now: int) -> bool:
        """Drop expired and spent records first, then the oldest, bounded."""
        receipts = self._wallet["receipts"]
        changed = False
        if len(receipts) > MAX_WALLET_RECEIPTS:
            spent = sorted(
                (rid for rid, rec in receipts.items()
                 if rec.get("spent_at") or int(rec.get("expires_at") or 0) <= now),
                key=lambda rid: int(receipts[rid].get("received_at")
                                    or receipts[rid].get("issued_at") or 0))
            while len(receipts) > MAX_WALLET_RECEIPTS and spent:
                receipts.pop(spent.pop(0), None)
                changed = True
            if len(receipts) > MAX_WALLET_RECEIPTS:
                oldest = sorted(receipts, key=lambda rid: int(
                    receipts[rid].get("received_at")
                    or receipts[rid].get("issued_at") or 0))
                for rid in oldest[:len(receipts) - MAX_WALLET_RECEIPTS]:
                    receipts.pop(rid, None)
                    changed = True
        return changed

    def _prune_issued_locked(self) -> bool:
        receipts = self._issued["receipts"]
        if len(receipts) <= MAX_ISSUED_RECEIPTS:
            return False
        candidates = sorted(
            (rid for rid, rec in receipts.items() if not rec.get("flagged")),
            key=lambda rid: int(receipts[rid]["receipt"].get("issued_at") or 0))
        while len(receipts) > MAX_ISSUED_RECEIPTS and candidates:
            receipts.pop(candidates.pop(0), None)
        return True

    def _counters_locked(self, circle_id: str) -> dict[str, int]:
        return self._wallet["circles"].setdefault(
            circle_id, {"earned": 0, "spent": 0})

    # -- circle helpers ---------------------------------------------------------
    def _local_circle(self, peer_node_id: str, circle_id: str
                      ) -> dict[str, Any] | None:
        if self.circles is None:
            return None
        try:
            for manifest in self.circles._local_candidates(peer_node_id):
                if str(manifest.get("circle_id")) == circle_id:
                    return manifest
        except Exception:
            return None
        return None

    def _is_member(self, node_id: str, circle_id: str) -> bool:
        try:
            return self.circles is not None and any(
                str(m.get("circle_id")) == circle_id
                and any(str(x.get("node_id")) == node_id
                        for x in m.get("members") or [])
                for m in self.circles._local_candidates(node_id))
        except Exception:
            return False

    # -- issuer: earn -----------------------------------------------------------
    async def issue_for_attempt(self, attempt: Any, replica: Any) -> dict[str, Any] | None:
        """Issue a receipt for an accepted, verified result, or return ``None``.

        The scheduler calls this only after signature and schema verification
        and only for a replica it accepted (never a rejected or degraded one).
        Local-pool attempts, *my own devices* sends and executor results with
        nothing usable never earn a receipt.
        """
        if not self.enabled() or self.circles is None:
            return None
        worker = str(getattr(attempt, "node_id", "") or "")
        if not worker or worker == self.node_id:
            return None
        if str(getattr(attempt, "destination_class", "")) != egress.CIRCLE:
            return None
        circle_id = str(getattr(attempt, "circle_id", "") or "")
        if not circle_id or self._local_circle(worker, circle_id) is None:
            return None
        attempt_id = str(getattr(attempt, "attempt_id", "") or "")
        if not _ATTEMPT_ID_RE.fullmatch(attempt_id):
            return None
        executor = str(getattr(replica, "executor", "") or "")
        if executor:
            sources = getattr(replica, "sources", []) or []
            text = str(getattr(replica, "text", "") or "")
            if not text.strip() or not sources:
                return None
        digest = attempt_hash(attempt_id)
        with self._lock:
            for record in self._issued["receipts"].values():
                receipt = record["receipt"]
                if receipt.get("worker") == worker \
                        and receipt.get("circle_id") == circle_id \
                        and receipt.get("attempt") == digest:
                    return dict(receipt)
        telemetry = getattr(replica, "telemetry", {}) or {}
        tokens = getattr(attempt, "tokens_out", None)
        if not isinstance(tokens, int) or isinstance(tokens, bool):
            tokens = telemetry.get("tokens_out")
        try:
            tokens_out = max(0, int(tokens or 0))
        except (TypeError, ValueError):
            tokens_out = 0
        gen_ms = telemetry.get("gen_ms")
        try:
            generation_ms = max(0, int(gen_ms))
        except (TypeError, ValueError):
            generation_ms = max(0, int(getattr(replica, "elapsed_ms", 0) or 0))
        try:
            receipt = build_receipt(
                identity_manager=self.identity_manager, circle_id=circle_id,
                issuer=self.node_id, worker=worker, attempt_id=attempt_id,
                tokens_out=tokens_out, generation_ms=generation_ms,
                model=str(getattr(replica, "model", "")
                          or getattr(attempt, "model", "") or "unknown"),
                ttl_s=self.ttl_days() * 86400)
        except CreditError:
            return None
        with self._lock:
            if receipt["receipt_id"] in self._issued["receipts"]:
                return dict(receipt)
            self._issued["receipts"][receipt["receipt_id"]] = {
                "receipt": receipt, "reports": [], "flagged": False,
                "flagged_reason": "", "flagged_at": None,
            }
            self._prune_issued_locked()
            self._save_issued_locked()
        sent = await self._send_control(
            worker, credit_receipt_message(receipt))
        self.bus.publish("credit.issued", receipt_id=receipt["receipt_id"],
                         circle_id=circle_id, worker=worker[:12],
                         tokens_out=tokens_out, delivered=bool(sent))
        return dict(receipt)

    # -- worker: receive --------------------------------------------------------
    async def handle_control(self, node_id: str,
                             message: dict[str, Any]) -> dict[str, Any] | None:
        try:
            size = len(canonical_bytes(message))
        except (TypeError, ValueError) as exc:
            raise CreditError(E_CREDIT_SCHEMA, "not canonical JSON") from exc
        if size > MAX_CREDIT_MESSAGE_BYTES:
            raise CreditError(E_CREDIT_SCHEMA,
                              f"credit message exceeds {MAX_CREDIT_MESSAGE_BYTES} bytes")
        mtype = message.get("type")
        if mtype == "credit_receipt":
            self._on_receipt(node_id, message)
            return None
        if mtype == "credit_spend":
            await self._on_spend(node_id, message)
            return None
        if mtype == "credit_spent":
            self._on_spent(node_id, message)
            return None
        return None

    def _on_receipt(self, node_id: str, message: dict[str, Any]) -> None:
        if not self.enabled():
            raise CreditError(E_CREDIT_REQUIRED, "credits are disabled on this node")
        receipt = message.get("receipt")
        if not isinstance(receipt, dict):
            raise CreditError(E_CREDIT_SCHEMA, "receipt missing")
        validate_receipt(receipt, now=int(time.time()))
        if receipt.get("issuer") != node_id:
            # A member cannot forward someone else's receipt to this node.
            raise CreditError(E_CREDIT_SCHEMA,
                              "the receipt was not delivered by its issuer")
        if receipt.get("worker") != self.node_id:
            raise CreditError(E_CREDIT_WRONG_WORKER,
                              "the receipt is addressed to another node")
        circle_id = str(receipt["circle_id"])
        if self._local_circle(node_id, circle_id) is None:
            raise CreditError(E_CREDIT_NOT_MEMBER,
                              "issuer and worker are not in that circle")
        rid = str(receipt["receipt_id"])
        with self._lock:
            if rid in self._wallet["receipts"]:
                raise CreditError(E_CREDIT_DUPLICATE,
                                  "this receipt is already in the wallet")
            self._prune_wallet_locked(int(time.time()))
            if len(self._wallet["receipts"]) >= MAX_WALLET_RECEIPTS:
                raise CreditError(E_CREDIT_WALLET_FULL,
                                  "wallet is full; spend or wait for expiry")
            record = dict(receipt)
            record["received_at"] = int(time.time())
            record["spent_at"] = None
            record["spent_to"] = ""
            record["spent_attempt"] = ""
            self._wallet["receipts"][rid] = record
            self._counters_locked(circle_id)["earned"] += 1
            self._save_wallet_locked()
        self.bus.publish("credit.received", receipt_id=rid,
                         circle_id=circle_id, issuer=node_id[:12],
                         tokens_out=int(receipt["tokens_out"]))

    async def _on_spend(self, node_id: str, message: dict[str, Any]) -> None:
        if not self.enabled():
            raise CreditError(E_CREDIT_REQUIRED, "credits are disabled on this node")
        spender = message.get("spender")
        if spender != node_id:
            raise CreditError(E_CREDIT_WRONG_WORKER,
                              "only the presenting node can spend a receipt")
        receipt = message.get("receipt")
        if not isinstance(receipt, dict):
            raise CreditError(E_CREDIT_SCHEMA, "receipt missing")
        validate_receipt(receipt, now=int(time.time()))
        if receipt.get("worker") != spender:
            raise CreditError(E_CREDIT_WRONG_WORKER,
                              "only the named worker can spend this receipt")
        circle_id = str(receipt["circle_id"])
        manifest = self._local_circle(node_id, circle_id)
        if manifest is None:
            raise CreditError(E_CREDIT_NOT_MEMBER,
                              "the presenter and this node are not in that circle")
        members = {str(m.get("node_id")) for m in manifest.get("members") or []}
        if str(receipt.get("issuer")) not in members:
            raise CreditError(E_CREDIT_NOT_MEMBER,
                              "the receipt's issuer is not a member of that circle")
        attempt_id = str(message.get("attempt_id") or "")
        if not _ATTEMPT_ID_RE.fullmatch(attempt_id):
            raise CreditError(E_CREDIT_SCHEMA, "invalid attempt_id")
        rid = str(receipt["receipt_id"])
        now = int(time.time())
        with self._lock:
            if rid in self._wallet["seen_spends"]:
                raise CreditError(E_CREDIT_SPENT,
                                  "this receipt was already presented here")
            self._wallet["seen_spends"][rid] = {
                "spender": spender, "attempt_id": attempt_id, "at": now}
            # Bound the replay window; the oldest attempts fall out first.
            while len(self._wallet["seen_spends"]) > MAX_WALLET_RECEIPTS:
                oldest = min(self._wallet["seen_spends"],
                             key=lambda key: int(self._wallet["seen_spends"][key]
                                                 .get("at") or 0))
                self._wallet["seen_spends"].pop(oldest, None)
            if len(self._priorities) >= MAX_PENDING_PRIORITIES:
                expired = [key for key, until in self._priorities.items()
                           if until <= now]
                for key in expired:
                    self._priorities.pop(key, None)
                if len(self._priorities) >= MAX_PENDING_PRIORITIES:
                    self._priorities.pop(next(iter(self._priorities)), None)
            self._priorities[(spender, attempt_id)] = now + PRIORITY_TTL_S
            self._save_wallet_locked()
        try:
            await self._report_spent(receipt, spender)
        except Exception:
            # Detection is best effort: a report that cannot be logged must
            # not turn an accepted spend (and its queue marker) into an error.
            pass
        self.bus.publish("credit.spend_received", receipt_id=rid,
                         circle_id=circle_id, spender=spender[:12],
                         attempt_id=attempt_id)

    # -- issuer: double-spend detection ---------------------------------------
    async def _report_spent(self, receipt: dict[str, Any], spender: str) -> None:
        report = credit_spent_message(
            self.identity_manager, receipt["receipt_id"], spender,
            by=self.node_id)
        issuer = str(receipt.get("issuer") or "")
        if issuer == self.node_id:
            # The issuer is also the receiving worker (possible when the
            # requester earned a receipt and the issuer later serves work):
            # record the report locally instead of sending it to ourselves.
            self._on_spent(self.node_id, report)
            return
        sent = await self._send_control(issuer, report)
        if not sent and issuer:
            with self._lock:
                pending = self._wallet["pending_reports"]
                pending.append({"to": issuer, "message": report})
                del pending[:-MAX_PENDING_REPORTS]
                self._save_wallet_locked()

    def _on_spent(self, node_id: str, message: dict[str, Any]) -> None:
        if message.get("by") != node_id or not verify_signed(node_id, message):
            raise CreditError(E_CREDIT_SIGNATURE,
                              "spend report signature is not the reporter's")
        rid = message.get("receipt_id")
        spender = message.get("spender")
        if not _valid_receipt_id(rid):
            raise CreditError(E_CREDIT_SCHEMA, "invalid receipt_id")
        if not _valid_node_id(spender):
            raise CreditError(E_CREDIT_SCHEMA, "invalid spender node_id")
        with self._lock:
            entry = self._issued["receipts"].get(str(rid))
        if entry is None:
            # Never issued here: nothing to log, and no global ledger to ask.
            raise CreditError(E_CREDIT_UNKNOWN, "unknown receipt")
        receipt = entry["receipt"]
        circle_id = str(receipt["circle_id"])
        if not self._is_member(node_id, circle_id):
            raise CreditError(E_CREDIT_NOT_MEMBER,
                              "reporter is not listed by the receipt's circle")
        now = int(time.time())
        reason = ""
        with self._lock:
            reports = list(entry.get("reports") or [])
            if spender != receipt.get("worker"):
                reason = "a node other than the named worker presented the receipt"
            elif any(item.get("by") == node_id for item in reports):
                reason = "the same worker reported this receipt spent twice"
            elif reports:
                reason = "more than one worker reported this receipt spent"
            entry.setdefault("reports", []).append(
                {"by": node_id, "spender": spender, "at": now})
            if reason and not entry.get("flagged"):
                entry["flagged"] = True
                entry["flagged_reason"] = reason
                entry["flagged_at"] = now
            self._save_issued_locked()
        if reason:
            log.warning("credit receipt %s flagged: %s", rid, reason)
            self.bus.publish("credit.double_spend", receipt_id=str(rid),
                             circle_id=circle_id, worker=spender[:12],
                             reason=reason, reports=len(entry.get("reports") or []))
        else:
            self.bus.publish("credit.spent", receipt_id=str(rid),
                             circle_id=circle_id, spender=spender[:12])

    async def on_peer_connected(self, peer: Any) -> None:
        """Retry reports that could not reach their issuer earlier."""
        node_id = str(getattr(peer, "node_id", "") or "")
        if not node_id:
            return
        with self._lock:
            pending = [dict(item) for item in self._wallet["pending_reports"]
                       if item.get("to") == node_id]
        for item in pending:
            if await self._send_control(node_id, item["message"]):
                with self._lock:
                    try:
                        self._wallet["pending_reports"].remove(item)
                    except ValueError:
                        pass
                    self._save_wallet_locked()

    # -- worker: priority -------------------------------------------------------
    def take_priority(self, node_id: str, attempt_id: str) -> bool:
        """Consume a validated spend marker for this exact attempt."""
        key = (str(node_id), str(attempt_id))
        now = time.time()
        with self._lock:
            expired = [k for k, until in self._priorities.items() if until <= now]
            for k in expired:
                self._priorities.pop(k, None)
            return self._priorities.pop(key, None) is not None

    # -- spender ----------------------------------------------------------------
    async def present_spend_async(self, peer_node_id: str, circle_id: str,
                                  attempt_id: str) -> str:
        """Present one unspent receipt just before a task; mark it spent."""
        if not self.enabled() or self.circles is None:
            return ""
        if not circle_id or not _ATTEMPT_ID_RE.fullmatch(str(attempt_id or "")):
            return ""
        now = int(time.time())
        chosen: dict[str, Any] | None = None
        with self._lock:
            candidates = [
                record for record in self._wallet["receipts"].values()
                if str(record.get("circle_id")) == circle_id
                and record.get("worker") == self.node_id
                and not record.get("spent_at")
                and int(record.get("expires_at") or 0) > now]
            if not candidates:
                return ""
            record = min(candidates, key=lambda r: (
                int(r.get("expires_at") or 0), int(r.get("received_at") or 0)))
            # Reserve before the await: two attempts sent at once must never
            # pick the same receipt.
            record["spent_at"] = now
            record["spent_to"] = str(peer_node_id)
            record["spent_attempt"] = str(attempt_id)
            self._counters_locked(circle_id)["spent"] += 1
            self._save_wallet_locked()
            chosen = dict(record)
        sent = await self._send_control(
            peer_node_id,
            credit_spend_message(self.node_id, str(attempt_id),
                                 receipt_payload(chosen)))
        if not sent:
            with self._lock:
                current = self._wallet["receipts"].get(str(chosen["receipt_id"]))
                if current is not None and current.get("spent_attempt") \
                        == str(attempt_id) and current.get("spent_to") \
                        == str(peer_node_id):
                    current["spent_at"] = None
                    current["spent_to"] = ""
                    current["spent_attempt"] = ""
                    self._counters_locked(circle_id)["spent"] = max(
                        0, self._counters_locked(circle_id)["spent"] - 1)
                    self._save_wallet_locked()
            return ""
        self.bus.publish("credit.spent_by_me",
                         receipt_id=str(chosen["receipt_id"]),
                         circle_id=circle_id, peer=peer_node_id[:12],
                         attempt_id=str(attempt_id))
        return str(chosen["receipt_id"])

    # -- transport --------------------------------------------------------------
    async def _send_control(self, node_id: str,
                            message: dict[str, Any]) -> bool:
        node = self.node or getattr(self.circles, "node", None)
        if not node_id or node is None:
            return False
        try:
            return bool(await node.send_control_async(node_id, message))
        except Exception:
            return False

    # -- API payloads -----------------------------------------------------------
    def wallet_summary(self, circle_id: str) -> dict[str, Any]:
        now = int(time.time())
        soon = now + EXPIRING_SOON_DAYS * 86400
        with self._lock:
            records = [dict(r) for r in self._wallet["receipts"].values()
                       if str(r.get("circle_id")) == circle_id]
            counts = dict(self._counters_locked(circle_id))
        unspent = [r for r in records if not r.get("spent_at")
                   and int(r.get("expires_at") or 0) > now]
        expiring = [r for r in unspent if int(r.get("expires_at") or 0) <= soon]
        return {
            "circle_id": circle_id,
            "balance": len(unspent),
            "earned": int(counts.get("earned") or 0),
            "spent": int(counts.get("spent") or 0),
            "expiring_soon": len(expiring),
            "expiring": sorted(
                ({"receipt_id": r["receipt_id"],
                  "expires_at": int(r["expires_at"]),
                  "tokens_out": int(r.get("tokens_out") or 0),
                  "model": str(r.get("model") or "")}
                 for r in expiring),
                key=lambda item: item["expires_at"])[:20],
            "receipts": len(records),
        }

    def flagged(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        with self._lock:
            records = list(self._issued["receipts"].values())
        for record in records:
            if not record.get("flagged"):
                continue
            receipt = record["receipt"]
            out.append({
                "receipt_id": receipt["receipt_id"],
                "circle_id": receipt["circle_id"],
                "worker": receipt["worker"],
                "worker_short": receipt["worker"][:12],
                "reports": len(record.get("reports") or []),
                "reason": str(record.get("flagged_reason") or ""),
                "flagged_at": record.get("flagged_at"),
            })
        out.sort(key=lambda item: int(item.get("flagged_at") or 0), reverse=True)
        return out

    def list_payload(self) -> dict[str, Any]:
        with self._lock:
            manifests = list(getattr(self.circles, "manifests", {}).values()) \
                if self.circles is not None else []
            issued_count = len(self._issued["receipts"])
            pending_reports = len(self._wallet["pending_reports"])
        now = int(time.time())
        circles: list[dict[str, Any]] = []
        for manifest in manifests:
            try:
                if self.circles is not None and not self.circles._valid(
                        manifest, now):
                    continue
            except Exception:
                continue
            members = [str(m.get("node_id")) for m in manifest.get("members") or []]
            if self.node_id not in members:
                continue
            cid = str(manifest["circle_id"])
            summary = self.wallet_summary(cid)
            summary["name"] = str(manifest.get("name") or "")
            circles.append(summary)
        circles.sort(key=lambda item: str(item.get("name") or "").casefold())
        return {
            "enabled": self.enabled(),
            "unit": "receipt",
            "ttl_days": self.ttl_days(),
            "expiring_soon_days": EXPIRING_SOON_DAYS,
            "wallet_max": MAX_WALLET_RECEIPTS,
            "issued_count": issued_count,
            "pending_reports": pending_reports,
            "circles": circles,
            "flagged": self.flagged(),
        }
