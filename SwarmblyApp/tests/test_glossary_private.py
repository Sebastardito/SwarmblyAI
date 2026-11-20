"""T9.17: a glossary entry marked private never reaches a public query.

The mark is ``| privado`` (also ``| private``, ``| privado: sí``…), read by the
App because LCE keeps only its own metadata keys.  A local answer still uses
the entry; the public proposal removes the term and its equivalents whole and
reports them, and a public entry keeps today's behaviour.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from swarmbly_app import memory_capture as M
from swarmbly_app import recipes as R
from swarmbly_app import web_search as W
from swarmbly_app.api import create_app
from swarmbly_app.api.security import ApiGuard
from swarmbly_app.projects import save_glossary


def test_the_parser_reads_every_accepted_spelling():
    for mark in ("| privado", "| private", "| PRIVATE", "| Privado: sí",
                 "| privado: SI", "| private: yes", "| privado: true",
                 "| privado: TRUE", "| privada: sí"):
        line = f"QA = Quilén Alto {mark}"
        cleaned, private = M.split_private_mark(line)
        assert private is True, mark
        assert cleaned == "QA = Quilén Alto", mark
        assert M.is_private_glossary_line(line) is True, mark
        assert M.glossary_privacy(mark) is True, mark
    # a line without the mark, and another metadata segment, stay public
    for line in ("QA = Quilén Alto", "QA = Quilén Alto | wd: Q123",
                 "QA = Quilén Alto | no: Quilen Alto",
                 "QA = Quilén Alto | distinto: QB"):
        assert M.split_private_mark(line) == (line, False)
    # an explicit negative is public, and is still removed from the right side
    assert M.split_private_mark("QA = Quilén Alto | privado: no") == \
        ("QA = Quilén Alto", False)


def test_glossary_line_round_trips_the_mark(app_state, tmp_path):
    entry = {"term": "QA", "equivalents": ["Quilén Alto", "upper station"],
             "private": True}
    line = M.glossary_line(entry)
    assert line == "QA = Quilén Alto, upper station | privado"
    assert M.glossary_line({"term": "QA", "equivalents": ["Quilén Alto"]}) == \
        "QA = Quilén Alto"
    save_glossary(tmp_path, [line])
    assert app_state.lce.glossary_entries(roots=[tmp_path]) == \
        [("QA", "Quilén Alto, upper station | privado")]
    assert app_state.lce.glossary_private_terms(roots=[tmp_path]) == ["QA"]
    # a later edit of the same concept keeps the mark (T9.17)
    save_glossary(tmp_path, ["QA = Quilén Alto, Quilén Alto station"])
    text = (tmp_path / "glosario.md").read_text(encoding="utf-8")
    assert "Quilén Alto station" in text and "| privado" in text


def test_a_private_glossary_entry_is_never_a_public_translation():
    private = [("cucuve", "mockingbird, Mimus | privado")]
    detail = W.propose_query_details("¿Cuántos cucuves hay en la isla?",
                                     glossary=private)
    assert "mockingbird" not in detail["query"]
    assert "Mimus" not in detail["query"]
    assert "cucuve" not in detail["query"].casefold()
    assert "cucuve" in [term.casefold() for term in detail["removed_terms"]]
    # the question names the private term: it is reported, not translated
    assert detail["removed_terms"] == ["cucuve"]
    # an unmarked entry keeps today's behaviour: it translates the public query
    public = [("cucuve", "mockingbird, Mimus")]
    detail = W.propose_query_details("¿Cuántos cucuves hay en la isla?",
                                     glossary=public)
    assert "mockingbird" in detail["query"] and "Mimus" in detail["query"]
    assert detail["removed_terms"] == []


def test_a_private_entry_is_removed_and_a_public_one_kept_in_the_question():
    glossary = [("QA", "Quilén Alto | privado"), ("QB", "Quilén Bajo")]
    question = ("Quilén Alto y Quilén Bajo son mis puntos clave: compara el caudal "
                "medio de Quilén Bajo con la red pública.")
    detail = R.propose_query_details(question, glossary)
    assert "Quilén Alto" not in detail["query"]
    assert "Alto" not in detail["query"].split()
    assert "Quilén Bajo" in detail["query"]          # the public entry stays
    assert detail["removed_terms"] == ["Quilén Alto"]
    assert "Quilén" not in detail["removed"] and "Bajo" not in detail["removed"]
    assert W.public_glossary_terms(glossary, question) == ["Quilén Bajo"]
    assert W.private_glossary_terms(glossary) == ["QA", "Quilén Alto"]


def test_a_private_code_is_read_from_the_project_file(app_state, tmp_path):
    project = app_state.projects.create("Cuenca", parent=tmp_path / "p")
    (project.memory / "glosario.md").write_text(
        "- QA = Quilén Alto | privado\n"
        "- QB = Quilén Bajo\n", encoding="utf-8")
    glossary = app_state.lce.glossary_entries(roots=project.roots())
    detail = R.propose_query_details("Quilén Alto y Quilén Bajo, caudal medio", glossary)
    assert "Quilén Bajo" in detail["query"]
    assert "Quilén Alto" not in detail["query"]
    assert detail["removed_terms"] == ["Quilén Alto"]


def test_the_api_saves_the_private_field_and_the_proposal_uses_it(app_state, tmp_path):
    project = app_state.projects.create("Privado", parent=tmp_path / "p")
    conv = app_state.chat.create_conversation(mode="local", project_id=project.id)
    msg = app_state.chat.db.add_message(
        conv["id"], "assistant", "ok",
        meta={"memory_proposals": {"id": "p1", "status": "proposed",
                                   "notes": [], "glossary": []}})
    guard = ApiGuard()
    client = TestClient(create_app(app_state, guard), base_url="http://127.0.0.1:8765")
    headers = {"X-Swarmbly-Token": guard.token}
    saved = client.post(
        f"/api/conversations/{conv['id']}/messages/{msg['id']}/memory",
        json={"glossary": [{"term": "QA", "equivalents": ["Quilén Alto"],
                            "private": True},
                           {"term": "QB", "equivalents": ["Quilén Bajo"]}]},
        headers=headers).json()
    assert saved["status"] == "saved"
    assert saved["saved"]["glossary"] == ["QA = Quilén Alto | privado",
                                          "QB = Quilén Bajo"]
    text = (project.memory / "glosario.md").read_text(encoding="utf-8")
    assert "QA = Quilén Alto | privado" in text and "QB = Quilén Bajo" in text
    body = client.post("/api/recipes/query", json={
        "text": "Quilén Alto y Quilén Bajo, caudal medio",
        "project_id": project.id}, headers=headers).json()
    assert body["removed_terms"] == ["Quilén Alto"]
    assert "Quilén Alto" not in body["query"]


def test_the_glossary_ui_offers_and_shows_the_private_mark():
    base = Path(__file__).resolve().parent.parent / "swarmbly_app" / "web"
    for language, label in (("es", "Privado: no se usa en búsquedas públicas"),
                            ("en", "Private: never used in public searches")):
        data = json.loads((base / "i18n" / f"{language}.json").read_text(encoding="utf-8"))
        assert data["chat"]["memoryPrivate"] == label
        assert data["chat"]["memoryPrivateChip"]
    js = (base / "js" / "chat.js").read_text(encoding="utf-8")
    assert "chat.memoryPrivate" in js and "private: g.priv.checked" in js
