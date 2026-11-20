"""Standing approvals for local MCP tools, per project (D-011).

A standing approval is the user's "don't ask again in this project" for one
local MCP tool. It is *not* a tool approval: the tool still needs its contract
approved in Settings (``settings/tools.json``), and the broker still checks
that approval and the argument schema on every call. It only lets the agent
policy skip the per-call approval card for that tool in that project.

Each record carries the hash of the tool contract it was granted for. A
manifest change (a new description or schema) invalidates it: the user may
approve the new contract in Settings, but the next call asks again until a new
standing yes is given.

Only a local MCP tool can be marked this way. Remote MCP tools, the sandbox and
author search always ask. That rule is enforced twice: :meth:`StandingStore.grant`
refuses anything else, and the agent policy checks the live spec's provider
before it consults this store, so a hand-edited file cannot widen permissions.

The store lives in ``<project>/settings/agent_standing.json`` (or the personal
data directory when no project is active), follows the same fail-closed
convention as the approval store, and holds no arguments, tokens or secrets.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from .approvals import SETTINGS_DIR

STANDING_SCHEMA = "swarmbly.agent_standing/2"
STANDING_FILE = "agent_standing.json"


class StandingError(ValueError):
    """A standing approval cannot be read, addressed or granted."""


class StandingStore:
    """Per-project "don't ask again" flags for local MCP tools."""

    def __init__(self, data_root: str | Path,
                 project_path: Callable[[str], Path | None] | None = None):
        self.data_root = Path(data_root)
        self._project_path = project_path

    def path_for(self, project_id: str = "") -> Path:
        if project_id:
            if self._project_path is None:
                raise StandingError("this standing store has no project resolver")
            path = self._project_path(project_id)
            if path is None:
                raise StandingError(f"unknown or unavailable project {project_id!r}")
            return Path(path) / SETTINGS_DIR / STANDING_FILE
        return self.data_root / SETTINGS_DIR / STANDING_FILE

    def _load(self, project_id: str = "") -> list[dict[str, str]]:
        try:
            raw = json.loads(self.path_for(project_id).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (OSError, ValueError):
            # Fail closed: a corrupt file grants nothing.
            return []
        records = raw.get("standing") if isinstance(raw, dict) else None
        if not isinstance(records, list):
            return []
        clean: list[dict[str, str]] = []
        for item in records:
            if not isinstance(item, dict):
                continue
            spec_id = str(item.get("spec_id") or "")
            if spec_id:
                clean.append({"spec_id": spec_id,
                              "approval_hash": str(item.get("approval_hash") or ""),
                              "granted_at": str(item.get("granted_at") or "")})
        clean.sort(key=lambda item: item["spec_id"])
        return clean

    def records(self, project_id: str = "") -> list[dict[str, str]]:
        return list(self._load(project_id))

    def is_standing(self, spec_id: str, project_id: str = "",
                    approval_hash: str | None = None) -> bool:
        """Whether this exact tool contract has a standing approval.

        ``approval_hash`` is the live spec's current hash. When it is given, a
        record for another contract (or a legacy record without a hash) does
        not count: a manifest change invalidates the standing yes even after
        the user approves the new contract.
        """
        for item in self._load(project_id):
            if item["spec_id"] != spec_id:
                continue
            if approval_hash is None or item.get("approval_hash") == approval_hash:
                return True
        return False

    def grant(self, spec: Any, project_id: str = "",
              granted_at: str | None = None) -> dict[str, str]:
        """Mark a local MCP tool as "don't ask again" in this project.

        ``spec`` is the live :class:`~swarmbly_app.tools.broker.ToolSpec`. The
        check uses the spec itself, not a caller-supplied provider string.
        """
        if getattr(spec, "provider", "") != "mcp_local" \
                or getattr(spec, "destination", "") != "local":
            raise StandingError(
                "only a local MCP tool can be set to \"don't ask again in this "
                "project\"; remote MCP tools, the sandbox and author search "
                "always ask")
        spec_id = str(getattr(spec, "id", "") or "")
        if not spec_id:
            raise StandingError("a standing approval needs a tool id")
        try:
            approval_hash = spec.current_hash()
        except Exception as exc:
            raise StandingError(
                f"cannot read the current contract of {spec_id}: {exc}") from exc
        records = self._load(project_id)
        stamp = granted_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        record = {"spec_id": spec_id, "approval_hash": approval_hash,
                  "granted_at": stamp}
        records = [item for item in records if item["spec_id"] != spec_id]
        records.append(record)
        records.sort(key=lambda item: item["spec_id"])
        self._write(self.path_for(project_id), records)
        return dict(record)

    def revoke(self, spec_id: str, project_id: str = "") -> bool:
        spec_id = str(spec_id or "")
        records = self._load(project_id)
        kept = [item for item in records if item["spec_id"] != spec_id]
        if len(kept) == len(records):
            return False
        self._write(self.path_for(project_id), kept)
        return True

    def _write(self, path: Path, records: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema": STANDING_SCHEMA, "standing": records}
        fd, temp_name = tempfile.mkstemp(prefix=".standing.", suffix=".tmp",
                                         dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
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
