"""Secrets (API keys) outside the configuration file.

Keys live in the system keychain (macOS Keychain, Windows Credential Manager,
Secret Service on Linux) through ``keyring``. Where no keychain exists
(headless Linux, Docker) or ``SWARMBLY_KEYRING=off``, they go to
``<data>/secrets.json`` with permissions 0600. The configuration only knows
whether a key is set; ``GET /api/config`` never returns it, and a project
folder or an exported configuration never carries it.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

SERVICE = "Swarmbly"
SECRET_KEYS = ("model.api_key", "evidence.google_cse_key")

_lock = threading.Lock()
_fallback_path: Path | None = None


def configure(data_root: str | Path) -> None:
    global _fallback_path
    _fallback_path = Path(data_root) / "secrets.json"


def _keyring():
    if os.environ.get("SWARMBLY_KEYRING", "").lower() in ("off", "0", "false", "no"):
        return None
    try:
        import keyring
        from keyring.backends import fail
        backend = keyring.get_keyring()
        if isinstance(backend, fail.Keyring) or "fail" in type(backend).__module__ \
                or "null" in type(backend).__module__:
            return None
        return keyring
    except Exception:
        return None


def _read_file() -> dict[str, str]:
    if _fallback_path is None or not _fallback_path.is_file():
        return {}
    try:
        return json.loads(_fallback_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_file(data: dict[str, str]) -> None:
    if _fallback_path is None:
        raise RuntimeError("keystore not configured")
    _fallback_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(_fallback_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh)


def set_secret(name: str, value: str) -> str:
    """Store a secret; returns where it was stored ("keychain" or "file")."""
    with _lock:
        kr = _keyring()
        if kr is not None:
            try:
                kr.set_password(SERVICE, name, value)
                if kr.get_password(SERVICE, name) == value:
                    data = _read_file()
                    if data.pop(name, None) is not None:
                        _write_file(data)
                    return "keychain"
            except Exception:
                pass
        data = _read_file()
        data[name] = value
        _write_file(data)
        return "file"


def get_secret(name: str) -> str:
    kr = _keyring()
    if kr is not None:
        try:
            value = kr.get_password(SERVICE, name)
            if value:
                return value
        except Exception:
            pass
    return _read_file().get(name, "")


def delete_secret(name: str) -> None:
    with _lock:
        kr = _keyring()
        if kr is not None:
            try:
                kr.delete_password(SERVICE, name)
            except Exception:
                pass
        data = _read_file()
        if data.pop(name, None) is not None:
            _write_file(data)


def storage(name: str) -> str:
    """"keychain", "file" or "" (not set)."""
    kr = _keyring()
    if kr is not None:
        try:
            if kr.get_password(SERVICE, name):
                return "keychain"
        except Exception:
            pass
    return "file" if _read_file().get(name) else ""


def _get(cfg: dict[str, Any], dotted: str) -> Any:
    node: Any = cfg
    for part in dotted.split("."):
        node = node.get(part) if isinstance(node, dict) else None
    return node


def migrate(config: Any) -> list[str]:
    """Move keys still written in config.json into the keystore (3.0.1)."""
    moved = []
    data = config.all()
    for key in SECRET_KEYS:
        value = _get(data, key)
        if isinstance(value, str) and value:
            set_secret(key, value)
            config.update({key: ""})
            moved.append(key)
    return moved


def redact(cfg: dict[str, Any]) -> dict[str, Any]:
    """A copy of the configuration without secrets, saying which are set."""
    import copy
    out = copy.deepcopy(cfg)
    flags = {}
    for key in SECRET_KEYS:
        section, _, leaf = key.partition(".")
        if isinstance(out.get(section), dict):
            out[section][leaf] = ""
        flags[key] = storage(key)
    out["_secrets"] = flags
    return out
