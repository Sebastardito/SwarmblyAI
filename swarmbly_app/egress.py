"""Where data goes, what may go there, and a record of what actually left.

Every call that can carry data off this computer passes through here:

* **Destination.** A model server, a public source or a peer is classified
  from its address alone: ``local`` (this computer: loopback), ``red_propia``
  (the user's own network: private and link-local addresses, ``.local``,
  single-label names such as a Docker service) or ``terceros`` (any other
  host, i.e. an organisation outside the user's control). A peer send is
  classified by transport instead (D-017): ``circulo`` when the peer is a
  member of one of this node's trusted circles, ``red_propia`` in the
  explicit *my own devices* mode, and refused otherwise. A server that speaks
  an "OpenAI-compatible" API is not local for that reason.
* **Policy.** Local is always allowed. The user's own network is allowed and
  recorded, and so is a member of a trusted circle (the circle setting
  ``circle_passages`` decides separately whether document passages may go
  there). A third party receives nothing unless the user authorised that
  host (``privacy.third_party_models``); passages of the user's documents need
  a second, separate authorisation (``privacy.third_party_passages``); and
  other nodes' fragments are never sent to a third party. Tool calls are
  separate: a non-local ``TOOL_REMOTE`` needs its host in
  ``privacy.tool_hosts``, and ``AUTHOR_QUERY`` needs one of the fixed author
  hosts plus the broker's per-call consent. A failure never widens a
  destination: callers do not fall back to another server.
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

from . import test_hosts

LOCAL = "local"
OWN_NETWORK = "red_propia"
CIRCLE = "circulo"
THIRD_PARTY = "terceros"

RECEIPT_SCHEMA = "swarmbly.privacy_receipt/1.0"

# What a call carries, from least to most sensitive.
QUESTION = "pregunta"            # the user's question or a rewrite of it
PASSAGES = "pasajes"             # text of the user's documents
FOREIGN = "fragmento_ajeno"      # another node's fragment served by this node
FRAGMENT = "fragmento"           # a fragment of the user's public request
PUBLIC_QUERY = "consulta_publica"  # entity names sent to a public source
UNKNOWN = "desconocido"          # treated as passages
TOOL_REMOTE = "herramienta_remota"  # a tool call to a remote service
TOOL_LOCAL = "herramienta_local"    # a tool call that runs on this computer
AUTHOR_QUERY = "consulta_autor"     # an author name sent to an author source

# Author search is a short, fixed set of public scholarly sources. A call also
# needs the broker's per-call consent (see ``author_consent``); the allowlist
# alone is not permission.
AUTHOR_HOSTS = ("pub.orcid.org", "api.openalex.org", "eutils.ncbi.nlm.nih.gov")
AUTHOR_ALLOWLIST = AUTHOR_HOSTS
TOOL_KINDS = frozenset({TOOL_REMOTE, TOOL_LOCAL, AUTHOR_QUERY})

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


OLLAMA_CLOUD = "ollama.com"


def cloud_host_by_name(model: str) -> str:
    """An Ollama cloud model by its name ("deepseek-v4-pro:cloud",
    "gpt-oss:120b-cloud"): the local Ollama forwards it to ollama.com, so the
    address the app connects to (127.0.0.1) is not where the text goes."""
    tag = (model or "").strip().lower().rpartition(":")[2] if ":" in (model or "") else ""
    return OLLAMA_CLOUD if tag == "cloud" or tag.endswith("-cloud") else ""


def model_destination(cfg: dict[str, Any]) -> dict[str, str]:
    """Where the configured chat model runs: {"clase": …, "host": …}. An
    Ollama cloud model runs at ollama.com even when Ollama is on this computer
    ("via" names the local address)."""
    model = cfg.get("model") or {}
    url = str(model.get("backend_url") or "") or "http://127.0.0.1:11434"
    cls, host = classify_url(url)
    remote = cloud_host_by_name(str(model.get("model_name") or "")) \
        if str(model.get("backend", "auto")) in ("auto", "ollama") else ""
    if remote:
        return {"clase": THIRD_PARTY, "host": remote, "via": host}
    return {"clase": cls, "host": host}


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

@dataclass
class Policy:
    third_party_hosts: tuple[str, ...] = ()
    third_party_passages: bool = False
    tool_hosts: tuple[str, ...] = ()

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "Policy":
        privacy = cfg.get("privacy") or {}
        hosts = tuple(sorted({str(h).strip().lower() for h in privacy.get("third_party_models") or []
                              if str(h).strip()}))
        tool_hosts = tuple(sorted({str(h).strip().lower() for h in privacy.get("tool_hosts") or []
                                   if str(h).strip()}))
        return cls(hosts, bool(privacy.get("third_party_passages", False)), tool_hosts)

    def authorised(self, host: str) -> bool:
        return host.lower() in self.third_party_hosts

    def tool_authorised(self, host: str) -> bool:
        return host.lower() in self.tool_hosts

    def allows(self, cls: str, host: str, kind: str) -> tuple[bool, str]:
        if kind == AUTHOR_QUERY:
            if host.lower() not in AUTHOR_HOSTS:
                return False, (f"{host} is not one of the approved author sources "
                               f"({', '.join(AUTHOR_HOSTS)}). Nothing was sent.")
            if not _author_consent.get():
                return False, (f"{host} is an approved author source, but this call has no "
                               "per-call consent. Nothing was sent.")
            return True, ""
        if kind == TOOL_REMOTE:
            if cls == LOCAL:
                return True, ""
            if not self.tool_authorised(host):
                return False, (f"{host} is not an authorised tool host. Add it to "
                               "privacy.tool_hosts in Settings, or use a local tool. "
                               "Nothing was sent.")
            return True, ""
        if not cls:
            return False, ("this peer is not in a valid, unexpired trusted circle; "
                           "nothing was sent.")
        if cls in (LOCAL, OWN_NETWORK):
            return True, ""
        if cls == CIRCLE:
            # D-017: a peer is CIRCLE only after the circle service has found
            # a shared, valid manifest; the class itself is the authorisation.
            # Passages to it are a separate per-circle switch, checked before
            # a recipe attaches them (``circle_passages``).
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
_author_consent: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "swarmbly_author_consent", default=False)


@contextlib.contextmanager
def author_consent() -> Iterator[None]:
    """The broker's yes for one author lookup; scoped to this call/context.

    The fixed allowlist is not permission by itself. The broker enters this
    block only after a one-time token has been checked, and resets it when the
    call ends. Threads must use :func:`carry` to inherit it.
    """
    token = _author_consent.set(True)
    try:
        yield
    finally:
        _author_consent.reset(token)


def author_consent_granted() -> bool:
    return bool(_author_consent.get())


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


def carry(fn: Callable[..., Any]) -> Callable[..., Any]:
    """``fn`` bound to the caller's request (ledger and purpose).

    Context variables do not cross into ``ThreadPoolExecutor`` workers or
    ``loop.run_in_executor``; without this, a public query or a model call made
    from a worker thread would leave the computer without reaching the
    request's receipt. Call ``carry`` in the requesting thread and hand the
    result to the pool; each call runs in its own copy of that context.
    """
    captured = contextvars.copy_context()

    def run(*args: Any, **kwargs: Any) -> Any:
        return captured.copy().run(fn, *args, **kwargs)

    return run


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


def check_call(url: str, nbytes: int, reason: str, kind: str | None = None,
               *, destination_class: str | None = None,
               destination_label: str | None = None,
               **extra: Any) -> None:
    """Enforce the policy for one call that carries ``kind`` to ``url``, and
    record it when it leaves this computer. Raises :class:`EgressDenied`.

    A peer send passes ``destination_class=CIRCLE`` (or ``OWN_NETWORK`` in the
    explicit *my own devices* mode): the class comes from the circle service,
    not from an address, as D-017 requires. ``extra`` is copied into the
    ledger event (the broker uses it for the tool id and the approval kind;
    a peer send adds the circle and the member). A local tool call is recorded
    too, with class ``local`` and type ``herramienta_local``.
    """
    if destination_class is None:
        cls, host = classify_url(url)
    else:
        cls, host = destination_class, host_of(url)
    label = destination_label or host
    kind = kind or current_purpose()
    # D-013: the map is known before the call; policy still sees only the
    # declared host. A blocked call never opens the mapped connection, so it
    # carries no ``simulado`` flag.
    simulated = test_hosts.target_for(host) is not None
    if cls == LOCAL and kind != AUTHOR_QUERY:
        if kind in TOOL_KINDS:
            event: dict[str, Any] = {"destino": "local", "clase": LOCAL, "tipo": kind,
                                     "bytes": 0, "motivo": reason}
            if simulated:
                event["simulado"] = True
            record(**event, **extra)
        return
    ok, why = policy().allows(cls, host, kind)
    if not ok:
        record(destino=label, clase=cls, tipo=kind, bytes=0, motivo=reason,
               bloqueado=True, **extra)
        raise EgressDenied(why, host, kind)
    event = {"destino": label, "clase": cls, "tipo": kind, "bytes": int(nbytes),
             "motivo": reason}
    if simulated:
        event["simulado"] = True
    record(**event, **extra)


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

def _relay_hops(sends: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Distinct relay transport hops named by this receipt's sends."""
    seen: dict[tuple[str, int], dict[str, Any]] = {}
    for entry in sends:
        relay = entry.get("relay")
        if not isinstance(relay, dict) or not relay.get("host"):
            continue
        key = (str(relay.get("host")), int(relay.get("port") or 0))
        seen[key] = {"host": key[0], "port": key[1], "metadata_only": True,
                     "saw": ["who", "when", "bytes"], "content": False}
    return [seen[key] for key in sorted(seen)]


def _name_parts(name: str) -> list[str]:
    return [w.lower() for w in name.replace(",", " ").split() if len(w) >= 3]


def build_receipt(ledger: Ledger | None, *, lane: str, route: str, answer: str,
                  consent: dict[str, Any], passages: list[str] | None = None,
                  personal_names: list[str] | None = None,
                  fragments: int = 0, extra_sends: list[dict[str, Any]] | None = None,
                  model_destination: dict[str, Any] | None = None,
                  ignore_ledger_fragments: bool = False) -> dict[str, Any]:
    """The privacy receipt of one answer, from what was recorded as sent.

    ``passages`` (texts given to the model) and ``personal_names`` let the
    receipt flag a sent value that contains a passage or the user's name.
    """
    events = list(ledger.events) if ledger is not None else []
    if ignore_ledger_fragments:
        # A peer send is also in the ledger (the egress gate records it where
        # the bytes are written). ``extra_sends`` carries the attempt's
        # per-destination passage count, so use that one entry, not both.
        events = [e for e in events
                  if not (not e.get("bloqueado") and e.get("tipo") == FRAGMENT
                          and e.get("clase") in (CIRCLE, OWN_NETWORK))]
    events += list(extra_sends or [])
    shingles: set[str] = set()
    for text in passages or []:
        words = text.lower().split()
        shingles |= {" ".join(words[i:i + 8]) for i in range(max(0, len(words) - 7))}
    names = [_name_parts(n) for n in personal_names or [] if n]
    sends, blocked, tools = [], [], []
    for ev in events:
        value = str(ev.get("valor", ""))
        kind = ev.get("tipo", UNKNOWN)
        is_tool = kind in TOOL_KINDS or bool(ev.get("spec_id"))
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
        personal_name = bool(ev.get("personal_name"))
        simulated = bool(ev.get("simulado"))
        entry = {"destino": ev.get("destino", ""), "clase": ev.get("clase", ""),
                 "tipo": kind_out, "valor": value if kind == PUBLIC_QUERY else f"({kind})",
                 "bytes": int(ev.get("bytes", 0) or 0), "motivo": ev.get("motivo", "")}
        # D-017: a peer send names the circle and the member; a list wave that
        # carried document passages says how many reached this destination.
        for key in ("circle_id", "circle_name", "member_name", "role", "executor"):
            if ev.get(key):
                entry[key] = str(ev[key])
        # 3.5, WP3 / D-016: the transport hop is part of the receipt. The
        # relay saw who, when and how many bytes; never content.
        if ev.get("transport"):
            entry["transport"] = str(ev["transport"])
        if isinstance(ev.get("relay"), dict):
            entry["relay"] = {
                "host": str(ev["relay"].get("host") or ""),
                "port": int(ev["relay"].get("port") or 0),
                "metadata_only": True,
                "saw": ["who", "when", "bytes"],
                "content": False,
            }
        for key in ("role_fallback", "on_behalf", "engine_unverified"):
            if ev.get(key):
                # D-018/WP4b: a generic fallback for a role, or a public search
                # a member ran on the requester's behalf whose engine the
                # requester cannot verify.
                entry[key] = True
        if ev.get("passages") not in (None, ""):
            try:
                entry["pasajes"] = int(ev.get("passages") or 0)
            except (TypeError, ValueError):
                entry["pasajes"] = 0
        if personal_name:
            # An author lookup carries a person's name as its payload. The
            # egress kind stays AUTHOR_QUERY; this flag is what the UI and the
            # receipt use, the same way a detected personal name already is.
            entry["personal_name"] = True
        if simulated:
            # D-013: the declared host in the receipt was reached through the
            # launch-time loopback map; the app says so instead of pretending
            # the connection went to the real service.
            entry["simulado"] = True
        was_blocked = bool(ev.get("bloqueado"))
        if was_blocked:
            blocked.append(entry)
        elif not (is_tool and ev.get("clase") == LOCAL):
            # A local tool is activity, not an outbound send. Remote tool
            # sends are ordinary sends as well as tool entries.
            sends.append(entry)
        if is_tool:
            tool_entry = {
                "spec_id": str(ev.get("spec_id") or ""),
                "destino": ev.get("destino", ""),
                "clase": ev.get("clase", ""),
                "tipo": kind_out,
                "bytes": 0 if was_blocked else int(ev.get("bytes", 0) or 0),
                "allowed": not was_blocked,
                "blocked": was_blocked,
                "approved_by": str(ev.get("aprobado_por") or ""),
                "motivo": ev.get("motivo", ""),
            }
            if personal_name:
                tool_entry["personal_name"] = True
            if simulated:
                tool_entry["simulado"] = True
            tools.append(tool_entry)
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
        "tools": tools,
        "pasajes_enviados": sum(
            int(s.get("pasajes") or 0) + (1 if s["tipo"] == "pasaje" else 0)
            for s in sends),
        "nombres_personales_enviados": sum(
            1 for s in sends if s["tipo"] == "nombre_personal" or s.get("personal_name")),
        "bytes_salientes": sum(s["bytes"] for s in sends),
        "fragmentos_creados": int(fragments),
        "saltos_relay": _relay_hops(sends),
        "respuesta_sintetica": answer,
        "hash_respuesta_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
        "origen": "registrado por la app en el punto de envío",
    }
