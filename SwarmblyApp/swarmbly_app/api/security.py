"""Local API hardening.

The admin interface listens on loopback, but loopback is reachable from any
web page the user opens: a page can send requests to ``127.0.0.1:8765``, open
WebSockets to it (WebSockets are not covered by CORS), or use DNS rebinding to
make its own origin resolve to 127.0.0.1. Defences, all on by default:

1. **Host allowlist** — requests whose ``Host`` is not a loopback name (or
   the explicitly configured bind address) are refused. Defeats DNS rebinding.
2. **Origin check** — state-changing requests and WebSocket upgrades that
   carry an ``Origin`` must come from this interface's own origin.
3. **Session token** — a random token, created at each launch and injected
   into the page this server serves, is required on ``/api/*`` (header
   ``X-Swarmbly-Token``) and on ``/ws`` (``?token=``). It is also written to
   ``<data>/api_token`` (0600) for local scripts and the CLI.
4. **Security headers** — strict CSP, no framing, no sniffing, no referrer.
"""

from __future__ import annotations

import hmac
import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}
TOKEN_HEADER = "x-swarmbly-token"
OPEN_PATHS = {"/api/health"}
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data:; font-src 'self' data:; "
       "connect-src 'self' ws://127.0.0.1:* ws://localhost:*; "
       "object-src 'none'; base-uri 'none'; form-action 'self'; "
       "frame-ancestors 'none'")


class ApiGuard:
    def __init__(self, token: str | None = None, extra_hosts: set[str] | None = None):
        self.token = token or secrets.token_urlsafe(32)
        self.allowed_hosts = set(LOOPBACK_HOSTS) | {h for h in (extra_hosts or set()) if h}

    def write_token(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(self.token)

    # -- checks ----------------------------------------------------------------
    @staticmethod
    def _hostname(host_header: str) -> str:
        host = (host_header or "").strip().lower()
        if host.startswith("["):
            return host[: host.find("]") + 1] if "]" in host else host
        return host.rsplit(":", 1)[0] if host.count(":") == 1 else host

    def host_ok(self, host_header: str) -> bool:
        return self._hostname(host_header) in self.allowed_hosts

    def origin_ok(self, origin: str | None, host_header: str) -> bool:
        if not origin:
            return True  # non-browser clients (CLI, curl) send no Origin
        try:
            parts = urlsplit(origin)
        except ValueError:
            return False
        if parts.scheme not in ("http", "https"):
            return False
        return parts.netloc.lower() == (host_header or "").lower() and \
            self.host_ok(parts.netloc)

    def token_ok(self, supplied: str | None) -> bool:
        return bool(supplied) and hmac.compare_digest(supplied, self.token)

    def check_websocket(self, headers, query_token: str | None) -> str:
        """Return '' if the upgrade is allowed, else a reason."""
        host = headers.get("host", "")
        if not self.host_ok(host):
            return "host not allowed"
        if not self.origin_ok(headers.get("origin"), host):
            return "origin not allowed"
        if not self.token_ok(query_token):
            return "missing or invalid token"
        return ""

    def inject(self, html: str) -> str:
        meta = f'<meta name="swarmbly-token" content="{self.token}">'
        return html.replace("</head>", f"  {meta}\n</head>", 1)


class GuardMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, guard: ApiGuard):
        super().__init__(app)
        self.guard = guard

    async def dispatch(self, request: Request, call_next):
        host = request.headers.get("host", "")
        if not self.guard.host_ok(host):
            return JSONResponse({"detail": "host not allowed"}, status_code=421)
        path = request.url.path
        if request.method in MUTATING and not self.guard.origin_ok(
                request.headers.get("origin"), host):
            return JSONResponse({"detail": "origin not allowed"}, status_code=403)
        if path.startswith("/api/") and path not in OPEN_PATHS:
            if not self.guard.token_ok(request.headers.get(TOKEN_HEADER)):
                return JSONResponse({"detail": "missing or invalid session token"},
                                    status_code=401)
        response: Response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response
