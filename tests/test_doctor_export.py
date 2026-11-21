"""Doctor export (R-014): allow-list, canaries, schema and exact preview.

The fixture fills a real AppState with private values in every place the App
keeps them. The export must be buildable from that state and contain none of
the canaries, in either the JSON or the readable text.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from swarmbly_app import doctor_export
from test_api_lce import make_client


class FakeNodes:
    """A node manager whose every string is a canary."""

    def __init__(self, canaries: dict[str, str]) -> None:
        self.c = canaries

    def status(self) -> dict:
        return {
            "listening": True,
            "connected_count": 2,
            "listen_error": self.c["host"],
            "peers": [{"node_id": self.c["node_id"],
                       "address": self.c["address"],
                       "port": 9999,
                       "name": self.c["member"]}],
        }

    def relay_status(self) -> list[dict]:
        return [{
            "circle_id": self.c["circle_id"],
            "host": self.c["host"],
            "status": "down",
            "last_error": f"E_RELAY: cannot reach {self.c['host']}",
            "push": {"current": {
                "status": "unreachable",
                "last_refusal": "rate_limited",
                "last_error": f"E_RELAY: {self.c['host']}",
            }, "pending_versions": [3]},
        }]

    def stop(self) -> None:
        pass


class FakeCircles:
    def __init__(self, canaries: dict[str, str]) -> None:
        self.c = canaries

    def summary(self) -> dict:
        return {"circles": 1, "names": [self.c["circle"]]}

    def list_payload(self) -> dict:
        return {"circles": [{
            "circle_id": self.c["circle_id"],
            "name": self.c["circle"],
            "owner": self.c["node_id"],
            "members": [{"node_id": self.c["node_id"],
                         "name": self.c["member"]}],
            "relay": {"host": self.c["host"], "port": 443,
                      "tls_cert_sha256": self.c["pin"]},
        }]}


@pytest.fixture()
def private_state(app_state, tmp_path, monkeypatch):
    """A state with private values in identity, config, projects, chat, LCE,
    errors, peers, circles and relay state."""
    canaries = {
        "node_id": app_state.identity.node_id,
        "key_path": str(app_state.dirs.identity_key_path()),
        "home_path": str(Path.home() / "Documents" / "CANARY-thesis-v7.docx"),
        "project": "CANARY-Project-Quinoa-42",
        "conversation": "CANARY conversation about private rows",
        "prompt": "CANARY-PROMPT: my unpublished field notes",
        "answer": "CANARY-ANSWER: the secret result is 4242",
        "document": "CANARY-document-title.md",
        "document_body": "CANARY-DOCUMENT-BODY paragraph",
        "glossary": "CANARY-GLOSSARY-TERM",
        "memory": "CANARY-MEMORY-note",
        "api_key": "CANARY-API-KEY-0123456789",
        "relay_host": "relay.canary.invalid",
        "host": "peer.canary.invalid",
        "address": "203.0.113.77",
        "circle": "CANARY-Circle-Name",
        "circle_id": "CANARY-CIRCLE-ID",
        "member": "CANARY-Member-Name",
        "pin": "CANARY-PIN-abcdef",
    }
    project = app_state.projects.create(canaries["project"],
                                        parent=tmp_path / "projects")
    (project.sources / canaries["document"]).write_text(
        canaries["document_body"], encoding="utf-8")
    app_state.save_memory("", [canaries["memory"]],
                          [{"term": canaries["glossary"],
                            "definition": "CANARY-GLOSSARY-DEFINITION"}])
    conv = app_state.db.create_conversation(title=canaries["conversation"])
    app_state.db.add_message(conv["id"], "user", canaries["prompt"])
    app_state.db.add_message(conv["id"], "assistant", canaries["answer"])
    request_id = "canary-request"
    app_state.db.add_request(request_id, conv["id"], None, "local", "model")
    app_state.db.finish_request(request_id, "failed",
                                {"error": canaries["prompt"]})
    app_state.config.update({
        "model.api_key": canaries["api_key"],
        "model.backend_url": f"http://{canaries['relay_host']}:11434",
        "swarm.worker_models": ["CANARY-MODEL-TAG"],
    })
    monkeypatch.setattr(app_state, "nodes", FakeNodes(canaries))
    monkeypatch.setattr(app_state, "circles", FakeCircles(canaries))
    # A failed sandbox preparation keeps its raw reason locally; the export
    # must carry only the stable code.
    from swarmbly_app.sandbox import cache as sandbox_cache
    sandbox_cache.write_state(
        app_state.dirs.root / "sandbox", status="failed", stage="failed",
        reason_code="sandbox_compile_failed", reason=canaries["prompt"],
        forced=True, started_free_memory_gb=2.0)
    from swarmbly_app.sandbox import SandboxPreparation
    app_state.sandbox = SandboxPreparation(
        app_state.dirs.root / "sandbox", app_state.bus,
        available_probe=lambda: (True, ""),
        memory_probe=lambda: 8 * 1024 ** 3)
    # The bus recorder sees a failure event whose payload is full of canaries.
    app_state.bus.publish("node.handshake_failed", address=canaries["address"],
                          host=canaries["host"], node_id=canaries["node_id"],
                          reason=canaries["prompt"])
    # Avoid a slow external GPU probe and any local Ollama request in tests.
    monkeypatch.setattr(doctor_export, "_gpu",
                        lambda hardware: {"class": "unified", "count": 1})
    monkeypatch.setattr(doctor_export, "_ollama",
                        lambda url, timeout=2.0: {"reachable": True,
                                                  "model_tags": ["qwen2.5:3b"]})
    return app_state, canaries


def _assert_no_canaries(text: str, canaries: dict[str, str]) -> None:
    for name, value in canaries.items():
        assert value not in text, f"private value leaked: {name}"


def test_export_contains_no_private_values(private_state):
    state, canaries = private_state
    preview = state.doctor_export.preview()
    _assert_no_canaries(preview["json_text"], canaries)
    _assert_no_canaries(preview["text"], canaries)
    # The values are really present in the App, not only in this list.
    assert state.identity.node_id == canaries["node_id"]
    assert state.db.get_conversation(
        state.db.list_conversations()[0]["id"])["title"] == canaries["conversation"]


def test_export_schema_and_no_extra_top_level_keys(private_state):
    state, _ = private_state
    data = doctor_export.build_export(state)
    assert doctor_export.validate_export(data) == []
    assert set(data) == {
        "schema", "generated_at", "app", "lce", "core", "system", "extras",
        "ollama", "sandbox", "p2p", "errors"}
    assert data["schema"] == doctor_export.SCHEMA_VERSION
    assert data["system"]["gpu"] == {"class": "unified", "count": 1}
    assert data["sandbox"]["status"] == "failed"
    assert data["sandbox"]["forced"] is True
    assert data["sandbox"]["last_error_code"] == "sandbox_compile_failed"
    assert data["ollama"] == {"reachable": True, "model_tags": ["qwen2.5:3b"]}
    assert data["p2p"]["peers"] == 2 and data["p2p"]["circles"] == 1
    assert data["p2p"]["relay_configured"] is True
    assert "rate_limited" in data["p2p"]["push_state_codes"]
    assert data["errors"][0]["code"] in {
        "request.failed", "node.handshake_failed"}

    bad = copy.deepcopy(data)
    bad["node_id"] = "not allowed"
    assert any("unexpected key 'node_id'" in error
               for error in doctor_export.validate_export(bad))
    broken = copy.deepcopy(data)
    broken["sandbox"]["status"] = "made_up"
    assert any("not in" in error
               for error in doctor_export.validate_export(broken))


def test_preview_is_byte_for_byte_what_is_saved(private_state, tmp_path):
    state, _ = private_state
    service = state.doctor_export
    preview = service.preview()
    saved = service.save(preview["snapshot_id"], directory=tmp_path / "out")

    assert Path(saved["json_file"]).read_text(encoding="utf-8") == preview["json_text"]
    assert Path(saved["text_file"]).read_text(encoding="utf-8") == preview["text"]
    assert hashlib.sha256(preview["json_text"].encode()).hexdigest() == saved["json_sha256"]
    assert hashlib.sha256(preview["text"].encode()).hexdigest() == saved["text_sha256"]
    assert json.loads(Path(saved["json_file"]).read_text(encoding="utf-8")) == preview["json"]
    with pytest.raises(ValueError):
        service.save("not-the-preview-id")


def test_api_preview_and_save_are_the_same_bytes(private_state):
    state, canaries = private_state
    client = make_client(state)
    preview = client.get("/api/doctor/export/preview")
    assert preview.status_code == 200
    body = preview.json()
    _assert_no_canaries(body["json_text"], canaries)
    _assert_no_canaries(body["text"], canaries)
    saved = client.post("/api/doctor/export",
                        json={"snapshot_id": body["snapshot_id"]})
    assert saved.status_code == 200, saved.text
    assert Path(saved.json()["json_file"]).read_text(encoding="utf-8") == body["json_text"]
    assert Path(saved.json()["text_file"]).read_text(encoding="utf-8") == body["text"]
    refused = client.post("/api/doctor/export", json={"snapshot_id": "expired"})
    assert refused.status_code == 409


def test_doctor_export_cli_writes_both_files(private_state, monkeypatch, tmp_path):
    state, canaries = private_state

    class FakeState:
        doctor_export = state.doctor_export

        def stop(self) -> None:
            pass

    monkeypatch.setattr("swarmbly_app.state.AppState", lambda data_dir: FakeState())
    assert cli_main(["--data-dir", str(tmp_path), "doctor-export"]) == 0
    files = list((state.dirs.root / "output" / "doctor").glob("swarmbly-doctor-*"))
    assert len(files) == 2
    for path in files:
        text = path.read_text(encoding="utf-8")
        _assert_no_canaries(text, canaries)


def cli_main(argv):
    from swarmbly_app.cli import main
    return main(argv)
