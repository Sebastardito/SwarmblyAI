"""Launch-time test seam: a declared host reaches a loopback stand-in.

Decision D-013. The sealed-bank harness needs to exercise a remote MCP server
whose name ends in ``.test`` and the fixed author services (ORCID, OpenAlex,
PubMed) without leaving the machine and without teaching the app that a
``.test`` name or ``127.0.0.1`` is a third party. This module redirects only
the TCP connection:

* policy and receipts are computed on the **declared** host, exactly as before
  (``egress.check_call`` / ``classify_url`` / ``privacy.tool_hosts`` /
  ``AUTHOR_QUERY``);
* only a host listed in the map is redirected;
* every mapped target must be loopback (``127.0.0.0/8``, ``::1`` or
  ``localhost``), and a map with any other target is refused at startup;
* the map comes from ``swarmbly-app serve --test-host-map FILE`` or from
  ``SWARMBLY_TEST_HOST_MAP=FILE`` read once at process start. It is never read
  from the config file, the settings API or the UI, and it cannot be changed
  while the process runs.

Receipt entries whose connection was redirected carry ``simulado: true`` (see
``egress.check_call`` and ``egress.build_receipt``). The startup log prints the
map and the UI shows a persistent "Test mode" banner.

The HTTP helpers here are the single place where the redirect happens:

* ``httpx_client`` / ``httpx2_async_client`` wrap the library transport (the
  request URL keeps its path and query; the original ``Host`` header is sent);
* ``urlopen`` uses an ``urllib`` opener whose connection classes connect to
  the mapped address while ``http.client`` still writes the declared ``Host``.

Nothing here runs unless :func:`load` was called at process start. In map mode
the helper clients ignore proxy environment variables, so a mapped loopback
connection is direct rather than handed to a proxy; this is a test-only
behaviour, never part of a normal launch.
"""

from __future__ import annotations

import http.client
import ipaddress
import json
import os
import ssl
import threading
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import httpx

ENV_VAR = "SWARMBLY_TEST_HOST_MAP"

_lock = threading.RLock()
_map: dict[str, str] = {}
_source = ""
_opener: urllib.request.OpenerDirector | None = None


class TestHostMapError(ValueError):
    """The test host map is invalid; the app must refuse to start."""


def _declared_host(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TestHostMapError("test host map keys must be non-empty host names")
    text = value.strip().lower()
    if "://" in text or any(ch in text for ch in "/?#@") or text.startswith("."):
        raise TestHostMapError(
            f"test host map key {value!r} must be a bare host name, not a URL")
    if text.startswith("["):
        if "]" not in text:
            raise TestHostMapError(f"test host map key {value!r} is not a valid host")
        text = text[1:text.index("]")]
    elif text.count(":") == 1:
        raise TestHostMapError(
            f"test host map key {value!r} must not include a port")
    try:
        parts = urllib.parse.urlsplit("//" + text)
    except ValueError as exc:
        raise TestHostMapError(f"test host map key {value!r} is not a valid host") from exc
    host = (parts.hostname or "").strip().lower().strip(".")
    if not host:
        raise TestHostMapError(f"test host map key {value!r} has no host")
    if host != "localhost":
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if any(not part or len(part) > 63 or part.startswith("-") or part.endswith("-")
                   or not all(ch.isalnum() or ch == "-" for ch in part)
                   for part in host.split(".")):
                raise TestHostMapError(
                    f"test host map key {value!r} is not a valid host name") from None
    return host


def _loopback_target(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TestHostMapError("test host map targets must be non-empty URLs")
    text = value.strip()
    try:
        parts = urllib.parse.urlsplit(text)
    except ValueError as exc:
        raise TestHostMapError(f"test host map target {value!r} is not a URL") from exc
    if parts.scheme not in ("http", "https"):
        raise TestHostMapError(
            f"test host map target {value!r} must use http or https")
    if not parts.hostname:
        raise TestHostMapError(f"test host map target {value!r} has no host")
    if parts.username or parts.password:
        raise TestHostMapError(
            f"test host map target {value!r} must not contain credentials")
    if parts.path not in ("", "/") or parts.query or parts.fragment:
        raise TestHostMapError(
            f"test host map target {value!r} must be an origin, without a path or query")
    host = parts.hostname.strip().lower().strip("[]")
    if host != "localhost":
        try:
            ip = ipaddress.ip_address(host)
        except ValueError as exc:
            raise TestHostMapError(
                f"test host map target {value!r} must be loopback "
                "(127.0.0.1, ::1 or localhost)") from exc
        if not ip.is_loopback:
            raise TestHostMapError(
                f"test host map target {value!r} must be loopback "
                "(127.0.0.1, ::1 or localhost)")
    try:
        port = parts.port
    except ValueError as exc:
        raise TestHostMapError(f"test host map target {value!r} has an invalid port") from exc
    if port is not None and not 1 <= port <= 65535:
        raise TestHostMapError(f"test host map target {value!r} has an invalid port")
    netloc = f"[{host}]" if ":" in host else host
    if port is not None:
        netloc = f"{netloc}:{port}"
    return f"{parts.scheme}://{netloc}"


def load_file(path: str | Path) -> dict[str, str]:
    """Parse and validate one map file. Raises :class:`TestHostMapError`."""
    filename = Path(path).expanduser()
    try:
        raw = filename.read_text(encoding="utf-8")
    except OSError as exc:
        raise TestHostMapError(f"cannot read test host map {str(filename)!r}: {exc}") from exc
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise TestHostMapError(
            f"test host map {str(filename)!r} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise TestHostMapError(
            f"test host map {str(filename)!r} must be a JSON object "
            '{"declared.host": "http://127.0.0.1:PORT"}')
    mapping: dict[str, str] = {}
    for declared, target in data.items():
        host = _declared_host(declared)
        if host in mapping:
            raise TestHostMapError(
                f"test host map lists {host!r} more than once")
        mapping[host] = _loopback_target(target)
    return mapping


def load(path: str | Path | None = None) -> dict[str, str]:
    """Load the map for this process. Only the CLI calls this, at startup.

    ``path`` comes from ``--test-host-map``; when it is absent the environment
    variable ``SWARMBLY_TEST_HOST_MAP`` is read. With neither, the seam stays
    off and every client is the plain one.
    """
    global _map, _source
    requested = str(path) if path else (os.environ.get(ENV_VAR, "") or "")
    if not requested:
        with _lock:
            _map = {}
            _source = ""
        return {}
    mapping = load_file(requested)
    with _lock:
        _map = dict(mapping)
        _source = str(Path(requested).expanduser())
    return dict(mapping)


def reset() -> None:
    """Turn the seam off (tests only; the app never calls this)."""
    global _map, _source
    with _lock:
        _map = {}
        _source = ""


def active() -> bool:
    with _lock:
        return bool(_map)


def mapping() -> dict[str, str]:
    with _lock:
        return dict(_map)


def target_for(host: str) -> str | None:
    """The loopback origin mapped to ``host``, or ``None``."""
    key = (host or "").strip().lower().strip("[]").rstrip(".")
    with _lock:
        return _map.get(key)


def describe() -> dict[str, Any]:
    with _lock:
        return {"active": bool(_map), "source": _source, "hosts": dict(_map)}


def startup_line() -> str:
    items = "; ".join(f"{host} -> {target}" for host, target in sorted(mapping().items()))
    return f"Test host map (D-013, simulated connections): {items or '(empty)'}"


# ---------------------------------------------------------------------------
# httpx: rewrite the connection, keep the declared URL/Host in the receipt
# ---------------------------------------------------------------------------

def _redirect(request: Any) -> bool:
    """Point one httpx request at its mapped origin, keeping the Host header."""
    target = target_for(request.url.host)
    if target is None:
        return False
    declared_host = request.headers.get("host") or request.url.netloc.decode("ascii")
    declared_name = request.url.host
    parts = urllib.parse.urlsplit(target)
    request.url = request.url.copy_with(
        scheme=parts.scheme, host=parts.hostname, port=parts.port)
    request.headers["host"] = declared_host
    # An https target must still present the declared name in SNI and verify
    # its certificate against that name, not against the loopback address.
    request.extensions["sni_hostname"] = declared_name
    return True


class _MappedTransport(httpx.BaseTransport):
    def __init__(self, inner: httpx.BaseTransport | None = None):
        self._inner = inner or httpx.HTTPTransport()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        _redirect(request)
        return self._inner.handle_request(request)

    def close(self) -> None:
        self._inner.close()


def httpx_client(**kwargs: Any) -> httpx.Client:
    """An ``httpx.Client`` that honours the map when it is active."""
    if not active():
        return httpx.Client(**kwargs)
    inner = kwargs.pop("transport", None)
    kwargs["transport"] = _MappedTransport(inner)
    # A proxy would defeat "only the TCP connection is redirected".
    kwargs["trust_env"] = False
    return httpx.Client(**kwargs)


def httpx2_async_client(**kwargs: Any) -> Any:
    """An ``httpx2.AsyncClient`` (the MCP SDK's client) that honours the map."""
    import httpx2

    if not active():
        return httpx2.AsyncClient(**kwargs)
    inner = kwargs.pop("transport", None)

    class _MappedAsyncTransport(httpx2.AsyncBaseTransport):
        def __init__(self) -> None:
            self._inner = inner or httpx2.AsyncHTTPTransport()

        async def handle_async_request(self, request: Any) -> Any:
            _redirect(request)
            return await self._inner.handle_async_request(request)

        async def aclose(self) -> None:
            await self._inner.aclose()

    kwargs["transport"] = _MappedAsyncTransport()
    kwargs["trust_env"] = False
    return httpx2.AsyncClient(**kwargs)


# ---------------------------------------------------------------------------
# urllib: connect to the target while http.client writes the declared Host
# ---------------------------------------------------------------------------

class _MappedConnection:
    """Mix-in: keep ``self.host`` for the Host header, connect to the target."""

    def connect(self) -> None:  # type: ignore[override]
        target = target_for(self.host)
        if target is None:
            return super().connect()  # type: ignore[misc]
        parts = urllib.parse.urlsplit(target)
        host = parts.hostname or ""
        port = parts.port or (443 if parts.scheme == "https" else 80)
        self.sock = self._create_connection(  # type: ignore[attr-defined]
            (host, port), self.timeout, self.source_address)  # type: ignore[attr-defined]
        if parts.scheme == "https":
            context = getattr(self, "_context", None) or ssl.create_default_context()
            # SNI and certificate verification remain the declared host.
            self.sock = context.wrap_socket(self.sock, server_hostname=self.host)


class _MappedHTTPConnection(_MappedConnection, http.client.HTTPConnection):
    pass


class _MappedHTTPSConnection(_MappedConnection, http.client.HTTPSConnection):
    pass


class _MappedHTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req: urllib.request.Request) -> Any:
        return self.do_open(_MappedHTTPConnection, req)


class _MappedHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req: urllib.request.Request) -> Any:
        # Only the SSL context: Python 3.12 removed HTTPSHandler's
        # ``_check_hostname`` and HTTPSConnection's ``check_hostname`` argument;
        # host-name checking lives on the context in every supported version.
        return self.do_open(_MappedHTTPSConnection, req, context=self._context)


def _mapped_opener() -> urllib.request.OpenerDirector:
    global _opener
    if _opener is None:
        _opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            _MappedHTTPHandler(),
            _MappedHTTPSHandler(),
        )
    return _opener


def urlopen(req: Any, timeout: float | None = None) -> Any:
    """``urllib.request.urlopen`` with the map applied to listed hosts only."""
    if not active():
        return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310
    return _mapped_opener().open(req, timeout=timeout)
