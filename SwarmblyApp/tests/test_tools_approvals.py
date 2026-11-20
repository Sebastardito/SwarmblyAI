"""Per-project tool approvals, atomic writes and revocation."""

from __future__ import annotations

import json
from pathlib import Path

from swarmbly_app.tools import ApprovalStore, ToolSpec
from swarmbly_app.tools.approvals import APPROVALS_SCHEMA


def _spec(description="Echo"):
    return ToolSpec("builtin/echo", "builtin", "local",
                    {"type": "object", "properties": {"text": {"type": "string"}}},
                    description)


def test_approval_is_per_project_and_contains_only_the_contract(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    store = ApprovalStore(tmp_path / "data",
                          project_path=lambda pid: project if pid == "p1" else None)
    spec = _spec()
    record = store.approve(spec.id, spec.approval_hash, "p1")
    assert record["spec_id"] == spec.id and record["approval_hash"] == spec.approval_hash
    assert record["granted_at"]

    path = project / "settings" / "tools.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema"] == APPROVALS_SCHEMA
    assert data["approvals"] == [record]
    assert "arguments" not in path.read_text(encoding="utf-8")
    assert "token" not in path.read_text(encoding="utf-8")
    assert store.is_approved(spec, "p1") is True

    personal = tmp_path / "data" / "settings" / "tools.json"
    assert not personal.exists()
    assert store.get(spec.id) is None


def test_personal_store_and_revoke(tmp_path):
    store = ApprovalStore(tmp_path / "data")
    spec = _spec()
    store.approve(spec.id, spec.approval_hash)
    assert (tmp_path / "data" / "settings" / "tools.json").is_file()
    assert store.is_approved(spec) is True
    assert store.revoke(spec.id) is True
    assert store.is_approved(spec) is False
    assert store.revoke(spec.id) is False


def test_a_changed_description_or_schema_breaks_the_approval(tmp_path):
    store = ApprovalStore(tmp_path / "data")
    original = _spec("Echo")
    store.approve(original.id, original.approval_hash)
    changed = ToolSpec("builtin/echo", "builtin", "local",
                       {"type": "object", "properties": {"text": {"type": "string"}}},
                       "Echo, now with a different promise")
    assert changed.approval_hash != original.approval_hash
    assert store.is_approved(changed) is False

    mutated_schema = ToolSpec("builtin/echo", "builtin", "local",
                              {"type": "object", "properties": {}}, "Echo")
    store.approve(mutated_schema.id, mutated_schema.approval_hash)
    mutated_schema.input_schema["properties"]["extra"] = {"type": "string"}
    assert store.is_approved(mutated_schema) is False


def test_unknown_project_fails_closed(tmp_path):
    store = ApprovalStore(tmp_path / "data", project_path=lambda pid: None)
    spec = _spec()
    try:
        store.approve(spec.id, spec.approval_hash, "p1")
    except Exception as exc:  # ApprovalError
        assert "unknown" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("an unknown project must not receive an approval")
    assert not (tmp_path / "data" / "settings" / "tools.json").exists()
