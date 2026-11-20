"""One entry point for every tool call.

The broker is intentionally small: it knows tool specs, the user's per-project
approvals and one-time approval tokens; it validates arguments against the
strict schema subset in :mod:`swarmbly_app.tools.schema`; and it sends every
remote call through :mod:`swarmbly_app.egress`. A handler never receives a
token or an approval store, only a :class:`ToolContext` whose ``http_get`` and
``http_post`` helpers call ``egress.check_call`` before sending.

Text returned by a tool is data. It is never executed and never parsed for
instructions; :func:`as_quoted_block` labels its source and hash and caps its
size. The broker never calls another tool on its own.
"""

from __future__ import annotations

import contextlib
import hashlib
import inspect
import json
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

import httpx

from .. import egress, test_hosts
from .approvals import ApprovalError, ApprovalStore
from .schema import (SchemaError, canonical_json, sha256_canonical,
                     validate_arguments, validate_schema)

PROVIDER_KINDS = frozenset({"builtin", "mcp_local", "mcp_remote", "author", "sandbox"})
DEFAULT_TOKEN_TTL = 60.0
DEFAULT_MAX_RESULT_CHARS = 8000
_ID_RE = re.compile(r"([a-z][a-z0-9_]*)/([A-Za-z0-9][A-Za-z0-9._-]{0,127})")
_MCP_ID_RE = re.compile(r"mcp:([a-z0-9][a-z0-9._-]{0,63})/([A-Za-z0-9][A-Za-z0-9._-]{0,127})")


class ToolDenied(egress.EgressDenied):
    """A tool call was refused before its handler ran.

    It subclasses :class:`egress.EgressDenied` so callers that already catch
    the app's egress denial also catch a refused tool.
    """

    def __init__(self, reason: str, spec_id: str = "",
                 destination: str = "", kind: str = ""):
        super().__init__(reason, destination=destination, kind=kind)
        self.reason = reason
        self.spec_id = spec_id


def approval_hash_for(spec_id: str, description: str, input_schema: dict[str, Any],
                      destination: str) -> str:
    """Hash of exactly what the user approves; changing any field invalidates it."""
    return sha256_canonical({"id": spec_id, "description": description,
                             "input_schema": input_schema, "destination": destination})


@dataclass(frozen=True, init=False)
class ToolSpec:
    """A tool's public contract, including the hash the user approved."""

    id: str
    provider: str
    destination: str
    input_schema: dict[str, Any]
    description: str
    approval_hash: str = ""

    def __init__(self, id: str, provider: str | None = None,
                 destination: str = "local", input_schema: dict[str, Any] | None = None,
                 description: str = "", approval_hash: str = "", *,
                 kind: str | None = None) -> None:
        # ``kind`` is accepted as a synonym for ``provider`` so a caller can
        # name the provider kind directly.
        if provider is None:
            provider = kind
        if provider is None:
            raise TypeError("provider (or kind) is required")
        if kind is not None and kind != provider:
            raise ValueError("provider and kind disagree")
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "destination", destination)
        object.__setattr__(self, "input_schema", {} if input_schema is None else input_schema)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "approval_hash", approval_hash)
        self.__post_init__()

    def __post_init__(self) -> None:
        if not isinstance(self.provider, str) or self.provider not in PROVIDER_KINDS:
            raise ValueError(f"provider must be one of {sorted(PROVIDER_KINDS)}")
        if not isinstance(self.id, str):
            raise ValueError("id must be a string")
        mcp_match = _MCP_ID_RE.fullmatch(self.id)
        if mcp_match is not None:
            # MCP tools keep the server in their id: mcp:<server>/<tool>. The
            # provider still says where it runs (mcp_local or mcp_remote).
            if self.provider not in ("mcp_local", "mcp_remote"):
                raise ValueError("an id of the form 'mcp:<server>/<tool>' needs an MCP provider")
        else:
            match = _ID_RE.fullmatch(self.id)
            if match is None or match.group(1) != self.provider:
                raise ValueError("id must be '<provider>/<name>' and match the provider")
        if not isinstance(self.description, str):
            raise ValueError("description must be a string")
        destination = self.destination
        if not isinstance(destination, str):
            raise ValueError("destination must be an http(s) URL or 'local'")
        if destination != "local":
            parts = urlsplit(destination)
            if parts.scheme not in ("http", "https") or not parts.hostname:
                raise ValueError("destination must be an http(s) URL or 'local'")
        # Validate the schema, but keep the contract exactly as supplied: the
        # approval hash is defined over the input_schema dict, not over this
        # module's normalised copy (additionalProperties defaults are applied
        # by validate_arguments).
        validate_schema(self.input_schema, root=True)
        digest = approval_hash_for(self.id, self.description, self.input_schema, destination)
        if self.approval_hash and self.approval_hash != digest:
            raise ValueError("approval_hash does not match this tool contract")
        object.__setattr__(self, "approval_hash", digest)

    def current_hash(self) -> str:
        """The hash of the contract as it is now (a mutated dict cannot hide)."""
        return approval_hash_for(self.id, self.description, self.input_schema, self.destination)

    @property
    def kind(self) -> str:
        return self.provider

    @property
    def name(self) -> str:
        return self.id.split("/", 1)[1]

    @property
    def requires_token(self) -> bool:
        return self.provider in ("sandbox", "author")

    @property
    def is_remote(self) -> bool:
        return self.destination != "local"


@dataclass
class ToolCall:
    spec_id: str
    arguments: dict[str, Any] = field(default_factory=dict)
    request_id: str = ""
    token: str | None = None
    project_id: str = ""
    purpose: str = ""


@dataclass
class ToolResult:
    spec_id: str
    ok: bool
    content: str = ""
    data: Any = None
    error: str = ""
    source: str = ""
    sha256: str = ""
    truncated: bool = False
    elapsed: float = 0.0
    approved_by: str = ""


@dataclass
class _Token:
    spec_id: str
    args_hash: str
    request_id: str
    expires_at: float
    used: bool = False


def as_quoted_block(result: ToolResult, max_chars: int = DEFAULT_MAX_RESULT_CHARS) -> str:
    """Wrap a result as quoted data with its source and content hash.

    The cap applies to the result text, not to the label. ``truncated`` is set
    on the result when the cap is reached. The hash always covers the full
    content, so a reader can tell that the visible text is incomplete.
    """
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars < 0:
        raise ValueError("max_chars must be a non-negative integer")
    text = result.content or ""
    digest = result.sha256 or hashlib.sha256(text.encode("utf-8")).hexdigest()
    result.sha256 = digest
    full_length = len(text)
    if full_length > max_chars:
        text = text[:max_chars]
        result.truncated = True
    label = (f"[tool result: {result.spec_id}; source={result.source or 'unknown'}; "
             f"sha256={digest}")
    if result.truncated:
        label += f"; truncated={full_length}>{max_chars}"
    label += "]"
    return f"{label}\n<<<\n{text}\n>>>"


@dataclass
class ToolContext:
    """What a handler gets: its spec, its call, and policy-checked HTTP helpers.

    Handlers must use ``http_get``/``http_post`` for network access: they call
    ``egress.check_call`` before a single byte leaves. A handler that imports
    httpx directly would bypass the receipt and the policy, which is forbidden.
    Work handed to a thread must use ``egress.carry(fn)`` so the ledger,
    purpose and author consent travel with it.
    """

    spec: ToolSpec
    call: ToolCall
    approved_by: str
    attempted: bool = False
    denied: egress.EgressDenied | None = None

    def _kind(self) -> str:
        if self.spec.destination == "local":
            return egress.TOOL_LOCAL
        return egress.AUTHOR_QUERY if self.spec.provider == "author" else egress.TOOL_REMOTE

    def _send(self, target: str, nbytes: int, reason: str) -> None:
        self.attempted = True
        try:
            egress.check_call(target, nbytes, reason=reason or f"herramienta {self.spec.id}",
                              kind=self._kind(), spec_id=self.spec.id,
                              aprobado_por=self.approved_by)
        except egress.EgressDenied as exc:
            # Keep the denial even if a handler swallows the exception.
            self.denied = exc
            raise

    @staticmethod
    def _url_bytes(url: str) -> int:
        parts = urlsplit(url)
        return len((parts.path or "").encode("utf-8")) + \
            len((parts.query or "").encode("utf-8"))

    def http_get(self, url: str, *, params: Any = None, headers: dict[str, str] | None = None,
                 reason: str = "", timeout: float = 30.0) -> httpx.Response:
        target = str(httpx.URL(url, params=params)) if params else url
        self._send(target, self._url_bytes(target), reason)
        with test_hosts.httpx_client(timeout=timeout) as client:
            return client.get(target, headers=headers)

    def http_post(self, url: str, *, json: Any = None, data: Any = None,
                  headers: dict[str, str] | None = None, reason: str = "",
                  timeout: float = 30.0) -> httpx.Response:
        body = b""
        if json is not None:
            body = json.dumps(json, ensure_ascii=False, separators=(",", ":"),
                              allow_nan=False).encode("utf-8")
        elif data is not None:
            if isinstance(data, str):
                body = data.encode("utf-8")
            elif isinstance(data, (bytes, bytearray)):
                body = bytes(data)
            elif isinstance(data, dict):
                body = str(httpx.QueryParams(data)).encode("utf-8")
            else:
                body = str(data).encode("utf-8")
        self._send(url, self._url_bytes(url) + len(body), reason)
        with test_hosts.httpx_client(timeout=timeout) as client:
            return client.post(url, json=json, data=data, headers=headers)


class ToolBroker:
    """Registers tools, checks approvals and tokens, and invokes handlers."""

    def __init__(self, data_root: str | Path | None = None, *,
                 project_path: Callable[[str], Path | None] | None = None,
                 approvals: ApprovalStore | None = None,
                 token_ttl: float = DEFAULT_TOKEN_TTL,
                 max_result_chars: int = DEFAULT_MAX_RESULT_CHARS,
                 clock: Callable[[], float] | None = None):
        if approvals is None:
            if data_root is None:
                raise ValueError("data_root or approvals is required")
            approvals = ApprovalStore(data_root, project_path=project_path)
        self.approvals = approvals
        self.token_ttl = float(token_ttl)
        self.max_result_chars = int(max_result_chars)
        self._clock = clock or time.monotonic
        self._specs: dict[str, ToolSpec] = {}
        self._handlers: dict[str, Callable[[ToolCall, ToolContext], Any]] = {}
        self._tokens: dict[str, _Token] = {}
        self._lock = threading.RLock()

    @property
    def approval_store(self) -> ApprovalStore:
        return self.approvals

    # -- registration and approvals -----------------------------------------
    def register(self, spec: ToolSpec,
                 handler: Callable[[ToolCall, ToolContext], Any]) -> ToolSpec:
        if not isinstance(spec, ToolSpec):
            raise TypeError("spec must be a ToolSpec")
        if not callable(handler):
            raise TypeError("handler must be callable")
        with self._lock:
            self._specs[spec.id] = spec
            self._handlers[spec.id] = self._adapt_handler(handler)
            self._drop_tokens(spec.id)
        return spec

    def unregister(self, spec_id: str) -> bool:
        """Remove a tool and its handler (MCP suspension uses this).

        The approval record is left alone so a later re-registration is still
        checked against the same contract; callers that want to revoke it use
        :meth:`revoke` first or afterwards.
        """
        with self._lock:
            existed = self._specs.pop(spec_id, None) is not None
            self._handlers.pop(spec_id, None)
            self._drop_tokens(spec_id)
            return existed

    def _drop_tokens(self, spec_id: str) -> None:
        with self._lock:
            for token, record in list(self._tokens.items()):
                if record.spec_id == spec_id:
                    del self._tokens[token]

    @staticmethod
    def _adapt_handler(handler: Callable[..., Any]) -> Callable[[ToolCall, ToolContext], Any]:
        """Accept ``handler(call, ctx)``, ``handler(call)`` or ``handler()``."""
        try:
            parameters = list(inspect.signature(handler).parameters.values())
        except (TypeError, ValueError):
            return handler
        positional = [p for p in parameters
                      if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        varargs = any(p.kind == p.VAR_POSITIONAL for p in parameters)
        if varargs or len(positional) >= 2:
            return handler
        if len(positional) == 1:
            return lambda call, ctx: handler(call)
        return lambda call, ctx: handler()

    def spec(self, spec_id: str) -> ToolSpec | None:
        with self._lock:
            return self._specs.get(spec_id)

    def specs(self) -> dict[str, ToolSpec]:
        with self._lock:
            return dict(self._specs)

    def approve(self, spec_id: str | ToolSpec, project_id: str = "") -> dict[str, str]:
        if isinstance(spec_id, ToolSpec):
            spec_id = spec_id.id
        spec = self._known(spec_id)
        try:
            current = spec.current_hash()
        except SchemaError as exc:
            raise self._denied(spec, f"tool contract is invalid: {exc}") from exc
        try:
            record = self.approvals.approve(spec.id, current, project_id)
        except ApprovalError as exc:
            raise self._denied(spec, str(exc)) from exc
        self._drop_tokens(spec.id)
        return record

    def revoke(self, spec_id: str | ToolSpec, project_id: str = "") -> bool:
        if isinstance(spec_id, ToolSpec):
            spec_id = spec_id.id
        try:
            removed = self.approvals.revoke(spec_id, project_id)
        except ApprovalError as exc:
            raise ToolDenied(str(exc), spec_id) from exc
        self._drop_tokens(spec_id)
        return removed

    # -- tokens --------------------------------------------------------------
    def issue_token(self, call: ToolCall | str, *args: Any,
                    ttl: float | None = None) -> str:
        """Issue one one-time token for this call.

        ``call`` is normally a :class:`ToolCall`; ``(spec_id, arguments,
        request_id)`` is accepted too. A numeric second positional argument is
        read as the TTL for convenience.
        """
        if isinstance(call, ToolCall):
            if args:
                if len(args) == 1 and isinstance(args[0], (int, float)) \
                        and not isinstance(args[0], bool) and ttl is None:
                    ttl = float(args[0])
                else:
                    raise TypeError("issue_token(call, ttl=...) takes one optional TTL")
        else:
            if len(args) > 2:
                raise TypeError("issue_token(spec_id, arguments, request_id)")
            arguments = args[0] if args else {}
            request_id = args[1] if len(args) > 1 else ""
            call = ToolCall(str(call), arguments, str(request_id))
        spec = self._known(call.spec_id)
        arguments = self._arguments(spec, call)
        self._validate(spec, arguments)
        token = secrets.token_urlsafe(32)
        lifetime = self.token_ttl if ttl is None else float(ttl)
        record = _Token(spec.id, sha256_canonical(arguments), call.request_id,
                        self._clock() + lifetime)
        with self._lock:
            self._tokens[token] = record
        return token

    def _consume_token(self, spec: ToolSpec, call: ToolCall,
                       arguments: dict[str, Any]) -> None:
        token = call.token
        if not token:
            raise self._denied(spec, f"tool {spec.id} needs a one-time approval token")
        with self._lock:
            record = self._tokens.get(token)
            if record is None:
                raise self._denied(spec, "approval token is unknown")
            if record.used:
                raise self._denied(spec, "approval token was already used")
            if self._clock() >= record.expires_at:
                raise self._denied(spec, "approval token has expired")
            if record.spec_id != spec.id:
                raise self._denied(spec, "approval token is bound to a different tool")
            if record.args_hash != sha256_canonical(arguments):
                raise self._denied(spec, "approval token is bound to different arguments")
            if record.request_id != call.request_id:
                raise self._denied(spec, "approval token is bound to a different request")
            record.used = True

    # -- invoke --------------------------------------------------------------
    def invoke(self, call: ToolCall) -> ToolResult:
        spec = self._known(call.spec_id)
        arguments = self._arguments(spec, call)
        self._require_approval(spec, call.project_id)
        self._validate(spec, arguments)

        approved_by = "approval"
        if spec.requires_token or call.token:
            self._consume_token(spec, call, arguments)
            approved_by = "token"

        context = ToolContext(spec, call, approved_by)
        started = self._clock()
        kind = context._kind()
        result: ToolResult
        try:
            with contextlib.ExitStack() as stack:
                stack.enter_context(egress.purpose(kind))
                if kind == egress.AUTHOR_QUERY:
                    stack.enter_context(egress.author_consent())
                raw = self._handlers[spec.id](call, context)
            if context.denied is not None:
                raise context.denied
            result = self._coerce(spec, raw, started, approved_by)
        except ToolDenied:
            raise
        except egress.EgressDenied as exc:
            # check_call already recorded the blocked attempt; do not add a
            # second event.
            raise ToolDenied(str(exc), spec.id, destination=exc.destination,
                             kind=exc.kind) from exc
        except Exception as exc:
            result = ToolResult(
                spec_id=spec.id, ok=False, error=f"{type(exc).__name__}: {exc}",
                source=self._source(spec), sha256=hashlib.sha256(b"").hexdigest(),
                elapsed=max(0.0, self._clock() - started), approved_by=approved_by)
        finally:
            if spec.destination == "local":
                self._record(spec, blocked=False, nbytes=0, approved_by=approved_by,
                             reason=f"herramienta {spec.id}", kind=egress.TOOL_LOCAL)
            elif not context.attempted:
                # A remote handler that answered without a request still shows
                # up in the receipt, with zero bytes.
                self._record(spec, blocked=False, nbytes=0, approved_by=approved_by,
                             reason=f"herramienta {spec.id} (sin envío)", kind=kind)
        return result

    def as_quoted_block(self, result: ToolResult,
                        max_chars: int | None = None) -> str:
        return as_quoted_block(result, self.max_result_chars if max_chars is None else max_chars)

    # -- helpers -------------------------------------------------------------
    def _known(self, spec_id: str) -> ToolSpec:
        with self._lock:
            spec = self._specs.get(spec_id)
        if spec is None:
            raise ToolDenied(f"unknown tool {spec_id!r}", spec_id)
        return spec

    def _arguments(self, spec: ToolSpec, call: ToolCall) -> dict[str, Any]:
        arguments = call.arguments
        if not isinstance(arguments, dict):
            raise self._denied(spec, f"arguments for {spec.id} must be an object")
        return arguments

    def _require_approval(self, spec: ToolSpec, project_id: str) -> None:
        try:
            record = self.approvals.get(spec.id, project_id)
        except ApprovalError as exc:
            raise self._denied(spec, str(exc)) from exc
        if record is None:
            raise self._denied(spec, f"tool {spec.id} has not been approved")
        try:
            current = spec.current_hash()
        except SchemaError as exc:
            raise self._denied(spec, f"tool contract is invalid: {exc}") from exc
        if record.get("approval_hash") != current:
            raise self._denied(
                spec, f"approval for {spec.id} no longer matches its description or "
                      "schema; re-approve it (rug-pull protection)")

    def _validate(self, spec: ToolSpec, arguments: dict[str, Any]) -> None:
        try:
            validate_arguments(spec.input_schema, arguments)
        except SchemaError as exc:
            raise self._denied(spec, f"invalid arguments for {spec.id}: {exc}") from exc

    def _coerce(self, spec: ToolSpec, raw: Any, started: float,
                approved_by: str) -> ToolResult:
        if isinstance(raw, ToolResult):
            result = raw
            result.spec_id = result.spec_id or spec.id
            result.source = result.source or self._source(spec)
            result.content = str(result.content or "")
        elif raw is None:
            result = ToolResult(spec_id=spec.id, ok=True, content="",
                                source=self._source(spec))
        elif isinstance(raw, str):
            result = ToolResult(spec_id=spec.id, ok=True, content=raw,
                                source=self._source(spec))
        elif isinstance(raw, (dict, list, int, float, bool)):
            text = json.dumps(raw, ensure_ascii=False, sort_keys=True, allow_nan=False) \
                if isinstance(raw, (dict, list)) else str(raw)
            result = ToolResult(spec_id=spec.id, ok=True, content=text,
                                data=raw, source=self._source(spec))
        else:
            result = ToolResult(spec_id=spec.id, ok=True, content=str(raw),
                                source=self._source(spec))
        result.source = result.source or self._source(spec)
        result.approved_by = approved_by
        result.sha256 = hashlib.sha256(result.content.encode("utf-8")).hexdigest()
        result.elapsed = max(0.0, self._clock() - started)
        return result

    @staticmethod
    def _source(spec: ToolSpec) -> str:
        return spec.id if spec.destination == "local" else spec.destination

    def _denied(self, spec: ToolSpec, reason: str) -> ToolDenied:
        self._record(spec, blocked=True, nbytes=0, approved_by="",
                     reason=reason, kind=self._kind(spec))
        if spec.destination == "local":
            destination = "local"
        else:
            _, destination = egress.classify_url(spec.destination)
        return ToolDenied(reason, spec.id, destination=destination,
                          kind=self._kind(spec))

    @staticmethod
    def _kind(spec: ToolSpec) -> str:
        if spec.destination == "local":
            return egress.TOOL_LOCAL
        return egress.AUTHOR_QUERY if spec.provider == "author" else egress.TOOL_REMOTE

    def _record(self, spec: ToolSpec, *, blocked: bool, nbytes: int,
                approved_by: str, reason: str, kind: str) -> None:
        if spec.destination == "local":
            destination, class_ = "local", egress.LOCAL
        else:
            class_, destination = egress.classify_url(spec.destination)
        egress.record(destino=destination, clase=class_, tipo=kind, bytes=int(nbytes),
                      motivo=reason, bloqueado=bool(blocked), spec_id=spec.id,
                      aprobado_por=approved_by)
