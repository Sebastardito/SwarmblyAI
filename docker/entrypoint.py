#!/usr/bin/env python3
"""Entry point of the Swarmbly AI container.

    serve                     configure from the environment, then run the app
                              headless (the interface is opened from the host's
                              browser at http://localhost:8765)
    searxng-settings <dir>    write SearXNG's settings.yml into <dir> once
                              (used by the optional ``search`` profile)
    anything else             passed to ``swarmbly-app`` (status, config get…)

Environment (all optional):

    SWARMBLY_OLLAMA_URL     Ollama server             (default http://ollama:11434)
    SWARMBLY_MODEL          chat model on first start (default: none, the
                            first-run assistant proposes one)
    SWARMBLY_EMBED_MODEL    embedding model           (default nomic-embed-text)
    SWARMBLY_SEARXNG_URL    local SearXNG             (default http://searxng:8080,
                            used only if that server answers)
    SWARMBLY_BIND           interface bind address    (default 0.0.0.0 inside the
                            container; compose publishes it on 127.0.0.1 only)
    SWARMBLY_DOCUMENTS      folder read as your sources (default /documents)

Only the settings that depend on the container are applied on every start
(server addresses). Everything else is applied once, on the first start, so
what you change later in the interface is kept.
"""

from __future__ import annotations

import os
import secrets
import socket
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

DATA = Path(os.environ.get("SWARMBLY_DATA_DIR", "/data"))
MARKER = DATA / ".docker-initialized"


def _say(msg: str) -> None:
    print(f"[swarmbly] {msg}", flush=True)


def _resolves(url: str) -> bool:
    host = urllib.parse.urlsplit(url).hostname or ""
    try:
        socket.getaddrinfo(host, None)
        return True
    except OSError:
        return False


def _searxng_ready(url: str, wait_s: float = 30.0) -> bool:
    """True when SearXNG answers a JSON search. Waits only if its name resolves,
    that is, only when the ``search`` profile is running."""
    if not url or not _resolves(url):
        return False
    from swarmbly_app.searxng import healthy
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        if healthy(url, timeout=4.0):
            return True
        time.sleep(2)
    return False


def configure() -> None:
    from swarmbly_app.config import Config
    from swarmbly_app.paths import DataDirs

    dirs = DataDirs(DATA)
    dirs.ensure()
    cfg = Config(dirs)
    current = cfg.all()
    changes: dict = {}

    ollama = os.environ.get("SWARMBLY_OLLAMA_URL", "http://ollama:11434").rstrip("/")
    if ollama:
        changes["model.backend"] = "ollama"
        changes["model.backend_url"] = ollama

    first = not MARKER.exists()
    if first:
        model = os.environ.get("SWARMBLY_MODEL", "").strip()
        if model and not (current.get("model") or {}).get("model_name"):
            changes["model.model_name"] = model
        embed = os.environ.get("SWARMBLY_EMBED_MODEL", "nomic-embed-text").strip()
        if embed:
            changes["model.embed_model"] = embed
        docs = Path(os.environ.get("SWARMBLY_DOCUMENTS", "/documents"))
        if docs.is_dir():
            lce = current.get("lce") or {}
            folders = list(lce.get("sources_dirs") or [])
            if str(docs) not in folders:
                folders.append(str(docs))
            changes.update({"lce.enabled": True, "lce.level": "C1",
                            "lce.sources_dirs": folders})

    searx = os.environ.get("SWARMBLY_SEARXNG_URL", "http://searxng:8080").rstrip("/")
    if _searxng_ready(searx):
        providers = list((current.get("evidence") or {}).get("providers") or [])
        if "web" not in providers:
            providers.append("web")
        changes["evidence.searxng_url"] = searx
        changes["evidence.providers"] = providers
        _say(f"local web search: {searx}")

    if changes:
        cfg.update(changes)
    if first:
        MARKER.write_text("configured from the container environment\n", encoding="utf-8")
        _say(f"first start: data in {DATA}, models from {ollama}")


def searxng_settings(target: str) -> int:
    """Write SearXNG's settings once, with a random secret, in SearXNG's own
    format (the same file the app writes for its Docker install)."""
    from swarmbly_app.searxng import settings_yaml

    folder = Path(target)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "settings.yml"
    if path.exists():
        _say(f"SearXNG settings already present: {path}")
        return 0
    path.write_text(settings_yaml(8080, secrets.token_hex(32), docker=True), encoding="utf-8")
    _say(f"SearXNG settings written: {path}")
    return 0


def main(argv: list[str]) -> int:
    command = argv[0] if argv else "serve"
    if command == "searxng-settings":
        return searxng_settings(argv[1] if len(argv) > 1 else "/etc/searxng")
    if command == "serve":
        configure()
        bind = os.environ.get("SWARMBLY_BIND", "0.0.0.0")
        args = ["swarmbly-app", "headless", "--host", bind, "--port", "8765",
                "--data-dir", str(DATA)]
        _say("interface: http://localhost:8765 (published on this computer only)")
    else:
        args = ["swarmbly-app", *argv]
        if "--data-dir" not in argv:
            args += ["--data-dir", str(DATA)]
    os.execvp(args[0], args)
    return 0  # not reached


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
