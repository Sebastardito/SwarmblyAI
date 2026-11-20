"""Per-project approvals for tool specs.

An approval is the user's yes to one exact tool contract: its id, description,
input schema and destination. It is stored as ``{spec_id, approval_hash,
granted_at}`` in ``<project>/settings/tools.json`` (or the personal data
directory's ``settings/tools.json`` when no project is active). No arguments,
API keys or approval tokens are ever written here.

Writes go through a temporary file in the same directory and ``os.replace``,
so a crash cannot leave half a file. A missing or unreadable store means "no
approvals"; it never means "allow".
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

APPROVALS_SCHEMA = "swarmbly.tool_approvals/1"
SETTINGS_DIR = "settings"
APPROVALS_FILE = "tools.json"


class ApprovalError(ValueError):
    """An approval store cannot be read or addressed."""


class ApprovalStore:
    """Approvals in a personal data directory and, optionally, per project."""

    def __init__(self, data_root: str | Path,
                 project_path: Callable[[str], Path | None] | None = None):
        self.data_root = Path(data_root)
        self._project_path = project_path

    def path_for(self, project_id: str = "") -> Path:
        if project_id:
            if self._project_path is None:
                raise ApprovalError("this approval store has no project resolver")
            path = self._project_path(project_id)
            if path is None:
                raise ApprovalError(f"unknown or unavailable project {project_id!r}")
            return Path(path) / SETTINGS_DIR / APPROVALS_FILE
        return self.data_root / SETTINGS_DIR / APPROVALS_FILE

    def _load(self, project_id: str = "") -> dict[str, Any]:
        path = self.path_for(project_id)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"schema": APPROVALS_SCHEMA, "approvals": []}
        except (OSError, ValueError):
            # Fail closed: a corrupt store grants nothing.
            return {"schema": APPROVALS_SCHEMA, "approvals": []}
        if not isinstance(raw, dict):
            return {"schema": APPROVALS_SCHEMA, "approvals": []}
        records = raw.get("approvals")
        if not isinstance(records, list):
            records = []
        clean: list[dict[str, str]] = []
        for item in records:
            if not isinstance(item, dict):
                continue
            spec_id = str(item.get("spec_id") or "")
            approval_hash = str(item.get("approval_hash") or "")
            if spec_id and approval_hash:
                clean.append({"spec_id": spec_id, "approval_hash": approval_hash,
                              "granted_at": str(item.get("granted_at") or "")})
        return {"schema": APPROVALS_SCHEMA, "approvals": clean}

    def records(self, project_id: str = "") -> list[dict[str, str]]:
        return list(self._load(project_id)["approvals"])

    def get(self, spec_id: str, project_id: str = "") -> dict[str, str] | None:
        for record in self._load(project_id)["approvals"]:
            if record["spec_id"] == spec_id:
                return dict(record)
        return None

    def approve(self, spec_or_id: Any, approval_hash: str | None = None,
                project_id: str = "", granted_at: str | None = None) -> dict[str, str]:
        """Record an approval from a spec or from ``(spec_id, approval_hash)``."""
        if approval_hash is None:
            spec = spec_or_id
            spec_id = str(getattr(spec, "id", "") or "")
            current = getattr(spec, "current_hash", None)
            approval_hash = (current() if callable(current)
                             else str(getattr(spec, "approval_hash", "") or ""))
        else:
            spec_id = str(spec_or_id)
        if not spec_id or not approval_hash:
            raise ApprovalError("spec_id and approval_hash are required")
        data = self._load(project_id)
        stamp = granted_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        record = {"spec_id": spec_id, "approval_hash": str(approval_hash),
                  "granted_at": stamp}
        data["approvals"] = [r for r in data["approvals"] if r["spec_id"] != spec_id]
        data["approvals"].append(record)
        data["approvals"].sort(key=lambda r: r["spec_id"])
        self._write(self.path_for(project_id), data)
        return dict(record)

    def revoke(self, spec_id: str, project_id: str = "") -> bool:
        if not isinstance(spec_id, str):
            spec_id = str(getattr(spec_id, "id", "") or "")
        data = self._load(project_id)
        kept = [r for r in data["approvals"] if r["spec_id"] != spec_id]
        if len(kept) == len(data["approvals"]):
            return False
        data["approvals"] = kept
        self._write(self.path_for(project_id), data)
        return True

    def is_approved(self, spec: Any, project_id: str = "") -> bool:
        record = self.get(getattr(spec, "id", ""), project_id)
        if record is None:
            return False
        current = getattr(spec, "current_hash", None)
        try:
            expected = current() if callable(current) else getattr(spec, "approval_hash", "")
        except Exception:
            return False
        return bool(expected) and record.get("approval_hash") == expected

    def _write(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".tools.", suffix=".tmp",
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
