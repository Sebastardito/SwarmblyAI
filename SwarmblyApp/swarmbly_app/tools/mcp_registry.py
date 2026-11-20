"""Per-project MCP server settings.

A server entry is configuration only: it never starts a process. The fields the
user sees before approving are the exact ``command``, ``args``, ``cwd`` and
``env_allowlist`` (names, never values) of a local server, or the ``url`` of a
remote one. ``settings/mcp_servers.json`` follows the same per-project
convention as tool approvals (``settings/tools.json``) and, like them, holds
no secret.

``command_hash`` covers the command, arguments, working directory, environment
names and (for remote servers) the URL. A change invalidates the previous
approval: status goes back to ``unapproved`` and the approved manifest is
forgotten. The manifest hash itself lives in ``approved_manifest_hash`` and is
checked against the live ``tools/list`` on every reconnect.

A local MCP server runs with the user's own rights: this module does not
sandbox it, and the app must say so. Names, descriptions and results coming
from any server are untrusted data.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlsplit

from .approvals import SETTINGS_DIR
from .schema import sha256_canonical

MCP_SERVERS_FILE = "mcp_servers.json"
MCP_SERVERS_SCHEMA = "swarmbly.mcp_servers/1"
KINDS = ("local_stdio", "remote_http")
STATUSES = ("unapproved", "approved", "suspended")

_SERVER_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

LOCAL_RIGHTS_NOTE = (
    "A local MCP server runs as your user, with your files and your network "
    "access. It is not sandboxed by Swarmbly."
)
REMOTE_HOST_NOTE = (
    "A remote MCP server is a third party. Its host must be listed in "
    "privacy.tool_hosts and every connect is checked by egress."
)
UNTRUSTED_NOTE = (
    "Tool names, descriptions and results from an MCP server are untrusted "
    "data. They cannot change permissions or tools."
)


class MCPError(ValueError):
    """Base class for MCP configuration, approval and lifecycle errors."""


class MCPRegistryError(MCPError):
    """The per-project MCP server store cannot be read or addressed."""


class MCPConfigError(MCPError):
    """A server configuration is invalid."""


class MCPNotFound(MCPError):
    """No server with that id exists in this project."""


class MCPNotRunning(MCPError):
    """The server is not running; the user must call ``start`` first."""


class MCPUnavailable(MCPError):
    """The optional MCP SDK is not installed."""


class MCPApprovalError(MCPError):
    """A tool or manifest cannot be approved as requested."""


class MCPTimeout(MCPError):
    """An MCP initialize, list or call exceeded its timeout."""


class MCPProtocolError(MCPError):
    """The server returned something the client cannot safely use."""


def _text_list(value: Any, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        raise MCPConfigError(f"{name} must be a list of strings")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise MCPConfigError(f"{name} must contain non-empty strings")
        if "\x00" in item:
            raise MCPConfigError(f"{name} must not contain NUL")
        out.append(item)
    return tuple(out)


@dataclass
class ServerConfig:
    """One MCP server, as configured by the user. No secret values live here."""

    id: str
    kind: str
    command: str = ""
    args: tuple[str, ...] = ()
    cwd: str = ""
    env_allowlist: tuple[str, ...] = ()
    url: str = ""
    approved_manifest_hash: str = ""
    approved_tools: tuple[str, ...] = ()
    status: str = "unapproved"
    command_hash: str = ""
    suspension_reason: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not _SERVER_ID_RE.match(self.id):
            raise MCPConfigError(
                "server id must be 1-64 lowercase letters, digits, '.', '_' or '-', "
                "starting with a letter or digit"
            )
        if self.kind not in KINDS:
            raise MCPConfigError(f"kind must be one of {', '.join(KINDS)}")
        self.args = _text_list(self.args, "args")
        self.approved_tools = tuple(sorted(set(_text_list(self.approved_tools, "approved_tools"))))
        names = [name.strip() for name in _text_list(self.env_allowlist, "env_allowlist")]
        for name in names:
            if not _ENV_NAME_RE.match(name):
                raise MCPConfigError(f"invalid environment variable name {name!r}")
        self.env_allowlist = tuple(sorted(set(names)))
        if self.status not in STATUSES:
            raise MCPConfigError(f"status must be one of {', '.join(STATUSES)}")
        if self.status == "approved" and not self.approved_manifest_hash:
            raise MCPConfigError("an approved server needs an approved manifest hash")
        if "\x00" in self.command or "\x00" in self.cwd or "\x00" in self.url:
            raise MCPConfigError("command, cwd and url must not contain NUL")

        if self.kind == "local_stdio":
            if self.url:
                raise MCPConfigError("a local stdio server must not have a url")
            if not self.command.strip():
                raise MCPConfigError("a local stdio server needs a command")
            self.command = self.command.strip()
            if self.cwd:
                self.cwd = str(Path(self.cwd).expanduser().resolve())
        else:
            if self.command or self.args or self.cwd:
                raise MCPConfigError("a remote HTTP server must not have command, args or cwd")
            self.url = str(self.url).strip()
            parts = urlsplit(self.url)
            if parts.scheme not in ("http", "https") or not parts.hostname:
                raise MCPConfigError("a remote HTTP server needs an http(s) url with a host")
            if parts.username or parts.password:
                raise MCPConfigError("credentials must not be embedded in the server url")

        current = self.computed_command_hash()
        if not self.command_hash:
            self.command_hash = current

    def computed_command_hash(self) -> str:
        """Hash of everything the user approved about how the server starts."""
        return sha256_canonical({
            "id": self.id,
            "kind": self.kind,
            "command": self.command,
            "args": list(self.args),
            "cwd": self.cwd,
            "env_allowlist": list(self.env_allowlist),
            "url": self.url,
        })

    def is_current(self) -> bool:
        return bool(self.command_hash) and self.command_hash == self.computed_command_hash()

    def describe(self) -> dict[str, Any]:
        """What the user is shown before approving. Never includes env values."""
        data = self.to_dict()
        data["env_values_visible"] = False
        data["rights_note"] = LOCAL_RIGHTS_NOTE if self.kind == "local_stdio" else REMOTE_HOST_NOTE
        data["environment_note"] = (
            "The approved names are the only values this app adds. The SDK also "
            "passes its minimal platform defaults (PATH, HOME, USER, …); no other "
            "environment variable is inherited."
        ) if self.kind == "local_stdio" else "Remote servers receive no local environment."
        data["untrusted_note"] = UNTRUSTED_NOTE
        return data

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "command": self.command,
            "args": list(self.args),
            "cwd": self.cwd,
            "env_allowlist": list(self.env_allowlist),
            "url": self.url,
            "approved_manifest_hash": self.approved_manifest_hash,
            "approved_tools": list(self.approved_tools),
            "status": self.status,
            "command_hash": self.computed_command_hash(),
            "suspension_reason": self.suspension_reason,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "ServerConfig":
        if not isinstance(data, dict):
            raise MCPConfigError("a server entry must be an object")
        try:
            return cls(
                id=str(data.get("id") or ""),
                kind=str(data.get("kind") or ""),
                command=str(data.get("command") or ""),
                args=data.get("args") or (),
                cwd=str(data.get("cwd") or ""),
                env_allowlist=data.get("env_allowlist") or (),
                url=str(data.get("url") or ""),
                approved_manifest_hash=str(data.get("approved_manifest_hash") or ""),
                approved_tools=data.get("approved_tools") or (),
                status=str(data.get("status") or "unapproved"),
                command_hash=str(data.get("command_hash") or ""),
                suspension_reason=str(data.get("suspension_reason") or ""),
            )
        except MCPConfigError:
            raise
        except (TypeError, ValueError) as exc:
            raise MCPConfigError(str(exc)) from None


class ServerRegistry:
    """MCP server entries in a personal data directory and, optionally, per project."""

    def __init__(self, data_root: str | Path,
                 project_path: Callable[[str], Path | None] | None = None):
        self.data_root = Path(data_root)
        self._project_path = project_path

    def path_for(self, project_id: str = "") -> Path:
        if project_id:
            if self._project_path is None:
                raise MCPRegistryError("this MCP registry has no project resolver")
            path = self._project_path(project_id)
            if path is None:
                raise MCPRegistryError(f"unknown or unavailable project {project_id!r}")
            return Path(path) / SETTINGS_DIR / MCP_SERVERS_FILE
        return self.data_root / SETTINGS_DIR / MCP_SERVERS_FILE

    def _load(self, project_id: str = "") -> list[ServerConfig]:
        path = self.path_for(project_id)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (OSError, ValueError):
            return []                 # fail closed: no servers, no approvals
        if not isinstance(raw, dict) or not isinstance(raw.get("servers"), list):
            return []
        out: list[ServerConfig] = []
        for item in raw["servers"]:
            try:
                config = ServerConfig.from_dict(item)
            except MCPConfigError:
                continue
            current = config.computed_command_hash()
            if config.command_hash != current:
                # The file was edited or moved: the old approval no longer
                # describes how this server would start.
                config.status = "unapproved"
                config.approved_manifest_hash = ""
                config.approved_tools = ()
                config.suspension_reason = "configuration changed; approve the server again"
                config.command_hash = current
            out.append(config)
        out.sort(key=lambda item: item.id)
        return out

    def servers(self, project_id: str = "") -> list[ServerConfig]:
        return list(self._load(project_id))

    def get(self, server_id: str, project_id: str = "") -> ServerConfig | None:
        for config in self._load(project_id):
            if config.id == server_id:
                return config
        return None

    def require(self, server_id: str, project_id: str = "") -> ServerConfig:
        config = self.get(server_id, project_id)
        if config is None:
            raise MCPNotFound(f"unknown MCP server {server_id!r}")
        return config

    def put(self, config: ServerConfig, project_id: str = "") -> ServerConfig:
        if not isinstance(config, ServerConfig):
            raise TypeError("config must be a ServerConfig")
        current = config.computed_command_hash()
        existing = self.get(config.id, project_id)
        reset = False
        if existing is not None:
            reset = existing.command_hash != current
        if config.command_hash and config.command_hash != current:
            reset = True
        if reset:
            config = replace(
                config, status="unapproved", approved_manifest_hash="",
                approved_tools=(), suspension_reason="configuration changed; approve the server again",
                command_hash=current,
            )
        else:
            config.command_hash = current
        if config.status == "approved" and not config.approved_manifest_hash:
            raise MCPConfigError("an approved server needs an approved manifest hash")

        records = [item for item in self._load(project_id) if item.id != config.id]
        records.append(config)
        records.sort(key=lambda item: item.id)
        self._write(self.path_for(project_id), records)
        return config

    # The common verbs read naturally at call sites.
    add = put
    save = put

    def remove(self, server_id: str, project_id: str = "") -> bool:
        records = self._load(project_id)
        kept = [item for item in records if item.id != server_id]
        if len(kept) == len(records):
            return False
        self._write(self.path_for(project_id), kept)
        return True

    def _write(self, path: Path, records: Iterable[ServerConfig]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"schema": MCP_SERVERS_SCHEMA,
                "servers": [item.to_dict() for item in records]}
        fd, temp_name = tempfile.mkstemp(prefix=".mcp_servers.", suffix=".tmp",
                                         dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        except Exception:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise
