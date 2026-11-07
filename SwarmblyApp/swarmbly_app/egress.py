"""Where data goes, what may go there, and a record of what actually left.

Every call that can carry data off this computer passes through here:

* **Destination.** A model server, a public source or a peer is classified
  from its address alone: ``local`` (this computer: loopback), ``red_propia``
  (the user's own network: private and link-local addresses, ``.local``,
  single-label names such as a Docker service) or ``terceros`` (any other
  host, i.e. an organisation outside the user's control). A server that
  speaks an "OpenAI-compatible" API is not local for that reason.
* **Policy.** Local is always allowed. The user's own network is allowed and
  recorded. A third party receives nothing unless the user authorised that
  host (``privacy.third_party_models``); passages of the user's documents need
  a second, separate authorisation (``privacy.third_party_passages``); and
  other nodes' fragments are never sent to a third party. A failure never
  widens a destination: callers do not fall back to another server.
* **Ledger.** Each request has a ledger of what left, recorded where the bytes
  are sent (the real query string, not what a step meant to send). The chat
  turns it into a privacy receipt (``swarmbly.privacy_receipt/1.0``).
"""

from __future__ import annotations

import contextlib
import contextvars
import hashlib
import ipaddress
import os
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

LOCAL = "local"
OWN_NETWORK = "red_propia"
THIRD_PARTY = "terceros"

RECEIPT_SCHEMA = "swarmbly.privacy_receipt/1.0"

# What a call carries, from least to most sensitive.
QUESTION = "pregunta"            # the user's question or a rewrite of it
PASSAGES = "pasajes"             # text of the user's documents
FOREIGN = "fragmento_ajeno"      # another node's fragment served by this node
FRAGMENT = "fragmento"           # a fragment of the user's public request
PUBLIC_QUERY = "consulta_publica"  # entity names sent to a public source
UNKNOWN = "desconocido"          # treated as passages

_OWN_SUFFIXES = (".local", ".lan", ".home", ".internal", ".home.arpa", ".localdomain")
_OWN_NAMES = {"host.docker.internal", "gateway.docker.internal"}


class EgressDenied(RuntimeError):
    """A call would send data to a destination the user has not authorised."""

    def __init__(self, message: str, destination: str = "", kind: str = ""):
        super().__init__(message)
        self.destination = destination
        self.kind = kind


# ---------------------------------------------------------------------------
# Destinations
# ---------------------------------------------------------------------------

def host_of(url: str) -> str:
    try:
        return (urllib.parse.urlsplit(url if "//" in url else f"//{url}").hostname or "").lower()
    except ValueError:
        return ""


def _local_names() -> set[str]:
    """Names that are this same computer in a given installation, e.g. the
    Docker services of compose.yaml (``SWARMBLY_LOCAL_HOSTS=ollama,searxng``)."""
    return {h.strip().lower() for h in os.environ.get("SWARMBLY_LOCAL_HOSTS", "").split(",") if h.strip()}


def classify_host(host: str) -> str:
    host = (host or "").strip().lower().strip("[]")
    if not host:
        return THIRD_PARTY
    if host in _local_names():
        return LOCAL
    if host in ("localhost",) or host.endswith(".localhost"):
        return LOCAL
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        if host in _OWN_NAMES or host.endswith(_OWN_SUFFIXES) or "." not in host:
            return OWN_NETWORK
        return THIRD_PARTY
    if ip.is_loopback or ip.is_unspecified:
        return LOCAL
    if ip.is_private or ip.is_link_local or (ip.version == 4 and ip in ipaddress.ip_network("100.64.0.0/10")):
        return OWN_NETWORK
    return THIRD_PARTY


def classify_url(url: str) -> tuple[str, str]:
    """(class, host) of a URL."""
    host = host_of(url)
    return classify_host(host), host


def model_destination(cfg: dict[str, Any]) -> dict[str, str]:
    """Where the configured chat model runs: {"clase": …, "host": …}."""
    model = cfg.get("model") or {}
    url = str(model.get("backend_url") or "") or "http://127.0.0.1:11434"
    cls, host = classify_url(url)
    return {"clase": cls, "host": host}


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

@dataclass
class Policy:
    third_party_hosts: tuple[str, ...] = ()
    third_party_passages: bool = False

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "Policy":
        privacy = cfg.get("privacy") or {}
        hosts = tuple(sorted({str(h).strip().lower() for h in privacy.get("third_party_models") or []
                              if str(h).strip()}))
        return cls(hosts, bool(privacy.get("third_party_passages", False)))

    def authorised(self, host: str) -> bool:
        return host.lower() in self.third_party_hosts

    def allows(self, cls: str, host: str, kind: str) -> tuple[bool, str]:
        if cls in (LOCAL, OWN_NETWORK):
            return True, ""
        if kind == FOREIGN:
            return False, (f"{host} is a third-party service: this node never sends other "
                           "nodes' fragments there")
        if kind == PUBLIC_QUERY:
            return True, ""
        if not self.authorised(host):
            return False, (f"{host} is a third-party service and has not been authorised. "
                           "Nothing was sent. Authorise it in Settings → Models, or use a "
                           "model on this computer.")
        if kind in (PASSAGES, UNKNOWN) and not self.third_party_passages:
            return False, (f"{host} is authorised for questions but not for passages of "
                           "your documents; nothing was sent.")
        return True, ""


_config_getter: Callable[[], dict[str, Any]] | None = None


def configure(config_getter: Callable[[], dict[str, Any]]) -> None:
    """Set where the policy is read from (the app's live configuration)."""
    global _config_getter
    _config_getter = config_getter


def policy() -> Policy:
    try:
        return Policy.from_config(_config_getter() if _config_getter else {})
    except Exception:
        return Policy()              # unreadable configuration: the strictest policy


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------

@dataclass
class Ledger:
    request_id: str = ""
    events: list[dict[str, Any]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, **event: Any) -> None:
        event.setdefault("t", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        with self._lock:
            self.events.append(event)


_ledger: contextvars.ContextVar[Ledger | None] = contextvars.ContextVar("swarmbly_ledger", default=None)
_purpose: contextvars.ContextVar[str] = contextvars.ContextVar("swarmbly_purpose", default=UNKNOWN)


@contextlib.contextmanager
def request_ledger(request_id: str = "") -> Iterator[Ledger]:
    ledger = Ledger(request_id)
    token = _ledger.set(ledger)
    try:
        yield ledger
    finally:
        _ledger.reset(token)


def current_ledger() -> Ledger | None:
    return _ledger.get()


@contextlib.contextmanager
def purpose(kind: str) -> Iterator[None]:
    """What the calls inside this block carry (question, passages, …)."""
    token = _purpose.set(kind)
    try:
        yield
    finally:
        _purpose.reset(token)


def current_purpose() -> str:
    return _purpose.get()


def record(**event: Any) -> None:
    ledger = _ledger.get()
    if ledger is not None:
        ledger.add(**event)


def check_call(url: str, nbytes: int, reason: str, kind: str | None = None) -> None:
    """Enforce the policy for one call that carries ``kind`` to ``url``, and
    record it when it leaves this computer. Raises :class:`EgressDenied`."""
    cls, host = classify_url(url)
    if cls == LOCAL:
        return
    kind = kind or current_purpose()
    ok, why = policy().allows(cls, host, kind)
    if not ok:
        record(destino=host, clase=cls, tipo=kind, bytes=0, motivo=reason, bloqueado=True)
        raise EgressDenied(why, host, kind)
    record(destino=host, clase=cls, tipo=kind, bytes=int(nbytes), motivo=reason)


_QUERY_KEYS = ("q", "search", "srsearch", "term", "titles", "query", "ids", "id", "page")


def record_public_query(url: str, provider: str, via: str = "") -> None:
    """A lookup in a public source: records the values actually sent."""
    parts = urllib.parse.urlsplit(url)
    params = urllib.parse.parse_qs(parts.query)
    values = [v for key in _QUERY_KEYS for v in params.get(key, [])]
    if not values and parts.path:
        values = [urllib.parse.unquote(parts.path.rsplit("/", 1)[-1])]
    value = " | ".join(values)[:300]
    cls, host = classify_url(url)
    if not via and cls != THIRD_PARTY:
        # a local metasearch engine (SearXNG) forwards the query to public engines
        via = f"{host} (reenvía a buscadores públicos)"
    record(destino=via or host, clase=THIRD_PARTY, tipo=PUBLIC_QUERY, valor=value,
           bytes=len(value.encode("utf-8")), motivo=f"evidencia pública ({provider})")


# ---------------------------------------------------------------------------
# Receipt
# ---------------------------------------------------------------------------

def _name_parts(name: str) -> list[str]:
    return [w.lower() for w in name.replace(",", " ").split() if len(w) >= 3]


def build_receipt(ledger: Ledger | None, *, lane: str, route: str, answer: str,
                  consent: dict[str, Any], passages: list[str] | None = None,
                  personal_names: list[str] | None = None,
                  fragments: int = 0, extra_sends: list[dict[str, Any]] | None = None,
                  model_destination: dict[str, Any] | None = None) -> dict[str, Any]:
    """The privacy receipt of one answer, from what was recorded as sent.

    ``passages`` (texts given to the model) and ``personal_names`` let the
    receipt flag a sent value that contains a passage or the user's name.
    """
    events = list(ledger.events) if ledger is not None else []
    events += list(extra_sends or [])
    shingles: set[str] = set()
    for text in passages or []:
        words = text.lower().split()
        shingles |= {" ".join(words[i:i + 8]) for i in range(max(0, len(words) - 7))}
    names = [_name_parts(n) for n in personal_names or [] if n]
    sends, blocked = [], []
    for ev in events:
        value = str(ev.get("valor", ""))
        kind = ev.get("tipo", UNKNOWN)
        folded = " ".join(value.lower().split())
        if kind == PUBLIC_QUERY:
            if any(s in folded for s in shingles):
                kind_out = "pasaje"
            elif any(len(p) >= 2 and sum(1 for w in p if w in folded.split()) >= 2 for p in names):
                kind_out = "nombre_personal"
            else:
                kind_out = "entidad_publica"
        elif kind == PASSAGES:
            kind_out = "pasaje"
        elif kind in (FRAGMENT, FOREIGN):
            kind_out = "fragmento"
        else:
            kind_out = kind
        entry = {"destino": ev.get("destino", ""), "clase": ev.get("clase", ""),
                 "tipo": kind_out, "valor": value if kind == PUBLIC_QUERY else f"({kind})",
                 "bytes": int(ev.get("bytes", 0) or 0), "motivo": ev.get("motivo", "")}
        (blocked if ev.get("bloqueado") else sends).append(entry)
    answer = answer or ""
    destinations = ["local"] + sorted({s["destino"] for s in sends if s["destino"]})
    return {
        "schema": RECEIPT_SCHEMA,
        "recibo_id": "R-" + hashlib.sha256(f"{ledger.request_id if ledger else ''}{answer}".encode()).hexdigest()[:12],
        "fecha_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "carril": lane,
        "ruta": route,
        "destinos_declarados": destinations,
        "destino_modelo": model_destination or {"clase": LOCAL, "host": ""},
        "consentimiento": consent,
        "envios": sends,
        "bloqueados": blocked,
        "pasajes_enviados": sum(1 for s in sends if s["tipo"] == "pasaje"),
        "nombres_personales_enviados": sum(1 for s in sends if s["tipo"] == "nombre_personal"),
        "bytes_salientes": sum(s["bytes"] for s in sends),
        "fragmentos_creados": int(fragments),
        "respuesta_sintetica": answer,
        "hash_respuesta_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
        "origen": "registrado por la app en el punto de envío",
    }
