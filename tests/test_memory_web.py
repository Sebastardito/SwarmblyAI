"""3.1 after the third hands-on test: memory proposals, glossary, approved
online search, citation check. Fictitious data (Ana Pérez, AcmeLabs)."""

from __future__ import annotations

import json

import pytest

from conftest import FakeBackend
from swarmbly_app import memory_capture as M
from swarmbly_app import web_search as W


def _fake(state, reply="Respuesta."):
    fake = FakeBackend(reply=reply)
    state.backends.resolve = lambda config=None: fake      # type: ignore[method-assign]
    return fake


@pytest.mark.parametrize("text", [
    "El cucujo no es un pez, memorízalo.",
    "Necesito que actualices tu memoria, memoriza esta nueva información.",
    "Agrega esto a tu glosario: AB1 es el lote de quinua.",
    "Remember this: the AB1 batch ships in March.",
])
def test_remember_intent_anywhere_in_the_message(text):
    assert M.needs_capture(text) and (M.remember_intent(text) or M.glossary_intent(text))


def test_definitions_are_glossary_candidates_without_being_asked():
    assert M.definition_hint("Los cucujos, también conocidos como cucuyos, son escarabajos.")
    assert M.definition_hint("TRU significa Trial Rearing Unit")
    assert not M.needs_capture("¿Cuál es el estado de conservación de Mimus trifasciatus?")


def test_extraction_is_parsed_and_falls_back_to_the_message():
    raw = 'x {"notes": ["Ana trabaja en AcmeLabs"], "glossary": [{"term": "AB1", ' \
          '"equivalents": ["lote AB1", "AB1"], "definition": "lote de quinua"}]} y'
    out = M.parse_extraction(raw)
    assert out["notes"] == ["Ana trabaja en AcmeLabs"]
    assert out["glossary"][0]["equivalents"] == ["lote AB1"]          # the term itself dropped
    assert M.glossary_line(out["glossary"][0]) == "AB1 = lote AB1"
    prop = M.propose("Memoriza que la reunión es los jueves.")       # no model
    assert prop["asked"] and prop["notes"] == ["Memoriza que la reunión es los jueves."]
    assert M.propose("TRU significa Trial Rearing Unit")["glossary"][0]["term"] == "TRU"


def test_a_remember_request_is_proposed_saved_only_on_yes(app_state, tmp_path):
    reply = json.dumps({"notes": ["El cucujo es un escarabajo luminiscente del género Pyrophorus."],
                        "glossary": [{"term": "cucujo", "equivalents": ["cucuyo", "Pyrophorus",
                                                                        "Elateridae"],
                                      "definition": "escarabajo luminiscente (Elateridae)"}]})
    fake = _fake(app_state, reply)
    p = app_state.projects.create("A", parent=tmp_path / "p")
    conv = app_state.chat.create_conversation(mode="lan", project_id=p.id)
    app_state.chat.send(conv["id"], "El cucujo no es un pez sino un escarabajo de la familia "
                        "Elateridae, género Pyrophorus. Memorízalo y agrégalo a tu glosario.",
                        mode="lan", run_async=False)
    msg = app_state.chat.get_messages(conv["id"])[-1]
    prop = msg["meta"]["memory_proposals"]
    assert prop["status"] == "proposed" and prop["glossary"][0]["term"] == "cucujo"
    assert msg["meta"]["executed"] == "local"                  # never to the swarm
    assert not (p.memory / "notas.md").exists()                # nothing without the yes
    system = " ".join(m["content"] for m in fake.calls[-1]["messages"] if m["role"] == "system")
    assert "No digas que lo memorizaste" in system or "Do not say you memorised" in system

    from fastapi.testclient import TestClient

    from swarmbly_app.api import create_app
    from swarmbly_app.api.security import ApiGuard
    guard = ApiGuard()
    client = TestClient(create_app(app_state, guard), base_url="http://127.0.0.1:8765")
    r = client.post(f"/api/conversations/{conv['id']}/messages/{msg['id']}/memory",
                    json={"notes": prop["notes"], "glossary": prop["glossary"]},
                    headers={"X-Swarmbly-Token": guard.token}).json()
    assert r["status"] == "saved" and r["saved"]["glossary"] == [
        "cucujo = cucuyo, Pyrophorus, Elateridae"]
    assert "Pyrophorus" in (p.memory / "notas.md").read_text(encoding="utf-8")
    assert "cucujo = cucuyo" in (p.memory / "glosario.md").read_text(encoding="utf-8")
    # the glossary now widens the search: "cucuyo" reaches a note that says "cucujo"
    assert "cucujo" in app_state.lce.glossary_terms("¿Qué es un cucuyo?", roots=p.roots())
    saved = app_state.chat.get_messages(conv["id"])[-1]["meta"]["memory_proposals"]
    assert saved["status"] == "saved"


def test_no_search_is_said_and_an_approved_search_is_used(app_state, tmp_path, monkeypatch):
    fake = _fake(app_state, "Según [W1] y [W9]…")
    app_state.config.update({"evidence": {"enabled": True, "providers": ["pubmed", "wikipedia"]}})
    conv = app_state.chat.create_conversation(mode="local")
    q = "Busca artículos recientes sobre la endogamia de los cucuves de Galápagos"
    app_state.chat.send(conv["id"], q, mode="local", run_async=False)
    first = app_state.chat.get_messages(conv["id"])[-1]["meta"]
    assert first["web_offer"]["query"] and "Busca" not in first["web_offer"]["query"]
    system = " ".join(m["content"] for m in fake.calls[-1]["messages"] if m["role"] == "system")
    assert "NO se hizo ninguna búsqueda" in system or "NO internet search" in system
    sent = []

    def fetch(url, timeout, ua):
        sent.append(url)
        if "esearch" in url:
            return {"esearchresult": {"idlist": ["111"]}}
        if "esummary" in url:
            return {"result": {"111": {"title": "Inbreeding in island mockingbirds.",
                                       "authors": [{"name": "Pérez A"}], "pubdate": "2024 Mar",
                                       "fulljournalname": "Journal of Fictitious Birds"}}}
        return {"query": {"search": []}}
    monkeypatch.setattr(W, "_get", fetch)
    app_state.chat.send(conv["id"], q, mode="local", run_async=False,
                        web_query="Galapagos mockingbird inbreeding")
    meta = app_state.chat.get_messages(conv["id"])[-1]["meta"]
    assert meta["web_search"]["results"][0]["label"] == "W1"
    assert "pubmed.ncbi.nlm.nih.gov/111" in meta["web_search"]["results"][0]["url"]
    assert all("Galapagos+mockingbird+inbreeding" in u or "Galapagos%20mockingbird" in u
               or "id=111" in u for u in sent)                # only the approved text left
    system = " ".join(m["content"] for m in fake.calls[-1]["messages"] if m["role"] == "system")
    assert "[W1] Inbreeding in island mockingbirds" in system
    assert meta["citations"]["unknown"] == ["W9"]               # an invented label is flagged
    assert "sort=pub_date" in sent[0]                           # "recientes" → newest first


def test_propose_query_drops_first_person_and_request_words():
    q = W.propose_query("¿Puedes buscar referencias recientes sobre mi tesis de cucuves?",
                        "Galapagos mockingbirds, inbreeding, my thesis")
    assert "mi" not in q.split() and "thesis" not in q and "Galapagos mockingbirds" in q
