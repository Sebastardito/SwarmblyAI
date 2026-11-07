"""Projects (3.1): own folder, isolation, chats in the folder, .swarmbly packages.

All data is fictitious (Ana Pérez, AcmeLabs). "Another computer" is a second
AppState with its own data folder and its own projects folder.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from swarmbly_app import projects as P
from swarmbly_app.state import AppState

from conftest import FakeBackend

DOC_A = ("# Informe AcmeLabs\n\nEl lote AB1 de semillas de quinua se secuenció en marzo de 2025 "
         "con una cobertura de 30x en AcmeLabs.\n")
DOC_B = ("# Notas del huerto\n\nLas lechugas del huerto comunitario se riegan los martes y los "
         "viernes por la mañana.\n")
PERSONAL = ("# CV de Ana Pérez\n\nAna Pérez coordina la calidad de datos en AcmeLabs desde "
            "agosto de 2022.\n")


def _fake(state: AppState) -> FakeBackend:
    fake = FakeBackend(reply="Respuesta [1].")
    state.backends.resolve = lambda config=None: fake      # type: ignore[method-assign]
    return fake


def _project(state: AppState, name: str, doc: str, tmp_path: Path, **kw) -> P.Project:
    project = state.projects.create(name, parent=tmp_path / "proyectos", **kw)
    (project.sources / "doc.md").write_text(doc, encoding="utf-8")
    return project


def test_create_lays_out_the_folder_and_warns_about_cloud_sync(app_state, tmp_path):
    project = app_state.projects.create("Quinua AB1", parent=tmp_path / "Dropbox" / "Swarmbly")
    assert project.path.name == "Quinua AB1"
    for sub in ("sources", "memory", "chats", "exports"):
        assert (project.path / sub).is_dir()
    data = json.loads((project.path / P.PROJECT_FILE).read_text(encoding="utf-8"))
    assert data["schema"] == P.PROJECT_SCHEMA and data["id"] == project.id
    assert "Dropbox" in project.describe()["cloud_warning"]
    assert P.cloud_sync(tmp_path / "plain") == ""
    again = app_state.projects.create("Quinua AB1", parent=tmp_path / "Dropbox" / "Swarmbly")
    assert again.path.name == "Quinua AB1 (2)" and again.id != project.id


def test_two_projects_and_the_personal_space_stay_apart(app_state, tmp_path):
    app_state.lce.activate("C1")
    app_state.config.update({"lce": {"enabled": True, "level": "C1", "dense_retrieval": False}})
    (app_state.dirs.sources / "cv.md").write_text(PERSONAL, encoding="utf-8")
    a = _project(app_state, "A", DOC_A, tmp_path)
    b = _project(app_state, "B", DOC_B, tmp_path)

    def sources(project_id, q):
        return {Path(h.get("rel", h["source"])).name
                for h in app_state.chat.retriever(q, "", project_id)}
    q = "lote AB1 quinua lechugas huerto Ana Pérez calidad de datos"
    assert sources(a.id, q) == {"doc.md"} and "quinua" in app_state.chat.retriever(q, "", a.id)[0]["text"]
    assert "lechugas" in app_state.chat.retriever(q, "", b.id)[0]["text"]
    assert sources("", q) == {"cv.md"}                       # personal never reads a project
    app_state.projects.update(a.id, include_personal=True)
    assert sources(a.id, q) == {"doc.md", "cv.md"}           # only when the project says so
    assert all("lechugas" not in h["text"] for h in app_state.chat.retriever(q, "", a.id))


def test_chats_are_kept_in_the_project_folder(app_state, tmp_path):
    fake = _fake(app_state)
    a = _project(app_state, "A", DOC_A, tmp_path)
    conv = app_state.chat.create_conversation(mode="local", project_id=a.id)
    app_state.chat.send(conv["id"], "¿Con qué cobertura se secuenció el lote AB1?",
                        mode="local", run_async=False)
    data = json.loads(a.chat_file(conv["id"]).read_text(encoding="utf-8"))
    assert data["schema"] == P.CHAT_SCHEMA and data["project_id"] == a.id
    assert [m["role"] for m in data["messages"]] == ["user", "assistant"]
    answer = data["messages"][-1]
    assert answer["content"] == "Respuesta [1]." and answer["meta"]["status"] == "done"
    cited = answer["meta"]["lce"]["sources"][0]
    assert cited["rel"] == "doc.md" and cited["cite"].startswith("doc:")
    assert answer["meta"]["receipt"]["ambito"] == {"tipo": "proyecto", "id": a.id, "nombre": "A"}
    assert "quinua" in fake.calls[-1]["messages"][0]["content"]
    assert app_state.chat.list_conversations(a.id)[0]["id"] == conv["id"]
    assert app_state.chat.list_conversations("") == []
    app_state.chat.delete_conversation(conv["id"])
    assert not a.chat_file(conv["id"]).exists()


def test_export_and_restore_on_another_computer_keeps_chats_sources_and_citations(
        app_state, tmp_path):
    _fake(app_state)
    a = _project(app_state, "Quinua AB1", DOC_A, tmp_path)
    (a.memory / "glosario.md").write_text("quinua = Chenopodium quinoa\n", encoding="utf-8")
    conv = app_state.chat.create_conversation(mode="local", project_id=a.id)
    app_state.chat.send(conv["id"], "¿Qué cobertura tuvo el lote AB1?", mode="local",
                        run_async=False)
    cite = app_state.chat.get_messages(conv["id"])[-1]["meta"]["lce"]["sources"][0]["cite"]
    out = P.export_package(a, app_version="test")
    package = Path(out["path"])
    assert package.parent == a.exports and package.suffix == ".swarmbly"
    with zipfile.ZipFile(package) as zf:
        names = set(zf.namelist())
        manifest = json.loads(zf.read("manifest.json"))
    assert {"swarmbly-project.json", "sources/doc.md", "memory/glosario.md",
            f"chats/{conv['id']}.json"} <= names
    assert not any(n.startswith("exports/") for n in names)
    assert all(len(f["sha256"]) == 64 for f in manifest["files"])

    other = AppState(str(tmp_path / "otra_computadora" / "datos"))
    try:
        project, renamed = P.import_package(package, other.projects,
                                            parent=tmp_path / "otra_computadora" / "Documentos")
        assert not renamed and project.id == a.id and project.path != a.path
        assert other.sync_projects(project.id)[project.id] == 1
        msgs = other.chat.get_messages(conv["id"])
        assert [m["content"] for m in msgs] == [m["content"]
                                                for m in app_state.chat.get_messages(conv["id"])]
        found = other.lce.resolve(cite, roots=project.roots())
        assert found and "cobertura de 30x" in found["text"] and found["rel"] == "doc.md"
        assert other.lce.glossary_terms("quinua", roots=project.roots()) == "Chenopodium quinoa"
        # a second restore on the same computer is a copy: new ids, nothing merged
        copy, renamed = P.import_package(package, other.projects,
                                         parent=tmp_path / "otra_computadora" / "Documentos")
        assert copy.id != project.id and renamed and conv["id"] in renamed
        other.sync_projects(copy.id)
        assert len(other.chat.list_conversations(copy.id)) == 1
        assert len(other.chat.list_conversations(project.id)) == 1
    finally:
        other.stop()


def test_damaged_or_unsafe_packages_are_refused(app_state, tmp_path):
    a = _project(app_state, "A", DOC_A, tmp_path)
    package = Path(P.export_package(a)["path"])

    def rewrite(name: str, change) -> Path:
        out = tmp_path / name
        with zipfile.ZipFile(package) as src, zipfile.ZipFile(out, "w") as dst:
            for item in src.namelist():
                data = src.read(item)
                data, extra = change(item, data)
                dst.writestr(item, data)
                for extra_name, extra_data in extra:
                    dst.writestr(extra_name, extra_data)
        return out
    edited = rewrite("edited.swarmbly", lambda n, d: (d + b"x" if n == "sources/doc.md" else d, []))
    with pytest.raises(P.ProjectError, match="hash differs"):
        P.inspect_package(edited)
    extra = rewrite("extra.swarmbly", lambda n, d: (d, [("sources/nuevo.md", b"?")]
                                                     if n == "manifest.json" else []))
    with pytest.raises(P.ProjectError, match="does not list"):
        P.inspect_package(extra)

    def traversal(n, d):
        if n != "manifest.json":
            return d, []
        m = json.loads(d)
        m["files"].append({"path": "../fuera.md", "sha256": "0" * 64, "bytes": 1})
        return json.dumps(m).encode(), [("../fuera.md", b"x")]
    with pytest.raises(P.ProjectError, match="unsafe path"):
        P.inspect_package(rewrite("evil.swarmbly", traversal))
    assert not (tmp_path / "fuera.md").exists()


def test_a_package_never_carries_an_api_key(app_state, tmp_path):
    a = _project(app_state, "A", DOC_A, tmp_path)
    (a.memory / "notas.md").write_text("clave: sk-ficticia-1234567890\n", encoding="utf-8")
    with pytest.raises(P.ProjectError, match="API"):
        P.export_package(a, secrets=["sk-ficticia-1234567890"])
    assert not list(a.exports.glob("*.swarmbly"))


def test_forget_keeps_the_folder_and_open_brings_the_chats_back(app_state, tmp_path):
    _fake(app_state)
    a = _project(app_state, "A", DOC_A, tmp_path)
    conv = app_state.chat.create_conversation(mode="local", project_id=a.id)
    app_state.chat.send(conv["id"], "Hola", mode="local", run_async=False)
    app_state.projects.forget(a.id)
    for c in app_state.chat.list_conversations(a.id):
        app_state.db.delete_conversation(c["id"])
    assert a.chat_file(conv["id"]).exists() and app_state.projects.get(a.id) is None
    app_state.projects.open(a.path)
    assert app_state.sync_projects(a.id)[a.id] == 1
    assert len(app_state.chat.get_messages(conv["id"])) == 2


def test_projects_api(app_state, tmp_path):
    from fastapi.testclient import TestClient

    from swarmbly_app.api import create_app
    from swarmbly_app.api.security import ApiGuard
    guard = ApiGuard()
    client = TestClient(create_app(app_state, guard), base_url="http://127.0.0.1:8765")
    h = {"X-Swarmbly-Token": guard.token}
    made = client.post("/api/projects", json={"name": "Huerto", "parent": str(tmp_path / "p")},
                       headers=h).json()
    assert made["name"] == "Huerto" and made["available"]
    listing = client.get("/api/projects", headers=h).json()
    assert listing["active"] == made["id"] and listing["items"][0]["id"] == made["id"]
    conv = client.post("/api/conversations", json={"project_id": made["id"]}, headers=h).json()
    assert conv["project_id"] == made["id"]
    assert [c["id"] for c in client.get(f"/api/conversations?project={made['id']}",
                                        headers=h).json()] == [conv["id"]]
    assert client.get("/api/conversations?project=", headers=h).json() == []
    exported = client.post(f"/api/projects/{made['id']}/export", headers=h).json()
    name = Path(exported["path"]).name
    blob = client.get(f"/api/projects/{made['id']}/export/{name}", headers=h).content
    info = client.post("/api/projects/inspect", content=blob, headers=h).json()
    assert info["project"]["id"] == made["id"] and info["chats"] == 1
    restored = client.post(f"/api/projects/import?parent={tmp_path / 'r'}", content=blob,
                           headers=h).json()
    assert restored["restored_as_copy"] and restored["chats_added"] == 1
    assert client.put("/api/config", json={"projects": {"active": ""}},
                      headers=h).status_code == 400
