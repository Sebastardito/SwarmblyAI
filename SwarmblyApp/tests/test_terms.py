"""Search terms as concepts (3.1, after the sixth hands-on test). Fictitious
data; network replaced by a fake fetch."""

from __future__ import annotations

from conftest import FakeBackend
from swarmbly_app import memory_capture as M
from swarmbly_app import terms as T
from swarmbly_app import web_search as W


def fake_fetch(sent):
    def fetch(url, timeout, ua):
        from swarmbly_app import egress          # the real _get records every request
        egress.record_public_query(url, provider="test")
        sent.append(url)
        if "wbsearchentities" in url:
            if "endogamia" in url:
                return {"search": [{"id": "Q1"}, {"id": "Q2"}]}
            return {"search": []}
        if "wbgetentities" in url:
            return {"entities": {
                "Q1": {"labels": {"en": {"value": "inbreeding"}, "es": {"value": "endogamia"}},
                       "descriptions": {"es": {"value": "apareamiento entre individuos emparentados"}},
                       "claims": {"P486": [{"mainsnak": {"datavalue": {"value": "D007205"}}}]}},
                "Q2": {"labels": {"en": {"value": "endogamy"}, "es": {"value": "endogamia"}},
                       "descriptions": {"es": {"value": "matrimonio dentro de un grupo social"}},
                       "claims": {}}}}
        if "gbif" in url:
            if "cucuve" in url:
                return {"results": [{"key": 7, "canonicalName": "Mimus", "rank": "GENUS",
                                     "family": "Mimidae", "kingdom": "Animalia",
                                     "vernacularNames": [{"vernacularName": "cucuve", "language": "spa"}]}]}
            return {"results": []}
        return {}
    return fetch


def test_homonyms_come_back_as_concepts_with_descriptions():
    sent = []
    out = T.resolve(["endogamia", "cucuve"], "es", fetch=fake_fetch(sent))
    endo = out[0]["candidates"]
    assert [c["label_en"] for c in endo] == ["inbreeding", "endogamy"]
    assert "emparentados" in endo[0]["description"] and endo[0]["mesh"] == "D007205"
    cucuve = out[1]["candidates"][0]
    assert cucuve["source"] == "gbif" and cucuve["scientific"] == "Mimus" and "Mimidae" in cucuve["description"]
    assert T.concept_terms(endo[0]) == ["inbreeding"] and T.concept_terms(cucuve) == ["Mimus"]
    assert all("endogamia" in u or "cucuve" in u or "ids=" in u for u in sent)   # only the words


def test_glossary_concepts_come_first_and_offline_sends_nothing():
    sent = []
    out = T.resolve(["endogamia"], "es", glossary=[("endogamia", "inbreeding")],
                    meta={"endogamia": {"wd": ["Q1"]}}, fetch=fake_fetch(sent), online=False)
    assert out[0]["candidates"][0] == {"source": "glossary", "id": "Q1", "label": "endogamia",
                                       "label_en": "inbreeding", "description": "inbreeding",
                                       "scientific": "", "mesh": "", "url": ""}
    assert sent == []


def test_a_chosen_concept_is_kept_and_the_next_query_uses_it(app_state, tmp_path, monkeypatch):
    fake = FakeBackend(reply="Respuesta.")
    app_state.backends.resolve = lambda config=None: fake      # type: ignore[method-assign]
    app_state.config.update({"evidence": {"enabled": True}})
    p = app_state.projects.create("A", parent=tmp_path / "p")
    conv = app_state.chat.create_conversation(mode="local", project_id=p.id)
    app_state.chat.send(conv["id"], "Busca artículos recientes sobre endogamia en aves",
                        mode="local", run_async=False)
    msg = app_state.chat.get_messages(conv["id"])[-1]
    sent = []
    monkeypatch.setattr(T, "_get", fake_fetch(sent))
    from fastapi.testclient import TestClient

    from swarmbly_app.api import create_app
    from swarmbly_app.api.security import ApiGuard
    guard = ApiGuard()
    c = TestClient(create_app(app_state, guard), base_url="http://127.0.0.1:8765")
    h = {"X-Swarmbly-Token": guard.token}
    res = c.post(f"/api/conversations/{conv['id']}/messages/{msg['id']}/terms",
                 json={"words": ["endogamia"], "lang": "es"}, headers=h).json()
    inbreeding = res["terms"][0]["candidates"][0]
    assert inbreeding["label_en"] == "inbreeding" and res["sends"]
    lookups = app_state.chat.get_messages(conv["id"])[-1]["meta"]["term_lookups"]
    assert lookups[0]["words"] == ["endogamia"]                       # recorded with the message
    saved = c.post(f"/api/conversations/{conv['id']}/messages/{msg['id']}/terms/save",
                   json={"choices": [{"word": "endogamia", "concept": inbreeding}]}, headers=h).json()
    assert saved["saved"] == ["endogamia = inbreeding | wd: Q1"]
    pairs = app_state.lce.glossary_entries(roots=p.roots())
    assert W.propose_query("Busca artículos sobre endogamia en aves", "endogamy, birds", pairs) \
        .startswith("inbreeding")                                    # not "endogamy" any more


def test_distinct_concepts_are_kept_and_mix_ups_are_flagged(app_state, tmp_path):
    t = "Cucujo no es un nombre de los cucuves; los cucujos (cucuyos) son Elateridae, género Pyrophorus."
    prop = M.propose(t)
    lines = [M.glossary_line(g) for g in prop["glossary"]]
    assert "Cucujo = cucuyos, Elateridae, Pyrophorus | distinto: cucuves" in lines
    fake = FakeBackend(reply="Endogamia en cucuves, que pertenecen a la familia Elateridae, puede "
                             "tener efectos negativos. Los cucujos no son cucuves.")
    app_state.backends.resolve = lambda config=None: fake      # type: ignore[method-assign]
    p = app_state.projects.create("A", parent=tmp_path / "p")
    app_state.save_memory(p.id, [], prop["glossary"])
    conv = app_state.chat.create_conversation(mode="local", project_id=p.id)
    app_state.chat.send(conv["id"], "¿Qué se sabe de la endogamia en cucuves?", mode="local",
                        run_async=False)
    meta = app_state.chat.get_messages(conv["id"])[-1]["meta"]
    assert len(meta["term_conflicts"]) == 1                     # the negated sentence is not flagged
    assert meta["term_conflicts"][0]["traits"] == "Elateridae"
    system = " ".join(m["content"] for m in fake.calls[-1]["messages"] if m["role"] == "system")
    assert "es otra cosa que «cucuves»" in system


def test_a_rate_limited_service_is_retried_once_and_named_when_it_fails(monkeypatch):
    import urllib.error
    from swarmbly_app import terms as T
    monkeypatch.setattr(T.time, "sleep", lambda s: None)
    calls = []

    def busy_then_ok(url, timeout, ua):
        calls.append(url)
        if len(calls) == 1:
            raise urllib.error.HTTPError(url, 429, "Too Many Requests", {"Retry-After": "1"}, None)
        if "wbsearchentities" in url:
            return {"search": [{"id": "Q38978"}]}
        if "wbgetentities" in url:
            return {"entities": {"Q38978": {"labels": {"en": {"value": "inbreeding"}},
                                            "descriptions": {"es": {"value": "cruce entre parientes"}}}}}
        return {"results": []}

    out = T.resolve(["endogamia"], "es", fetch=busy_then_ok)
    assert out[0]["candidates"][0]["label_en"] == "inbreeding" and not out[0]["errors"]

    def always_busy(url, timeout, ua):
        raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)

    out = T.resolve(["endogamia"], "es", fetch=always_busy)
    assert out[0]["candidates"] == [] and out[0]["errors"] == ["wikidata: 429", "gbif: 429"]


def test_each_term_gets_the_scientific_name_of_its_own_clause():
    t = ("Recuerda que el cucujo no es un nombre de los cucuves: los cucujos son escarabajos de "
         "la familia Elateridae y los cucuves son aves del género Mimus.")
    lines = sorted(M.glossary_line(g) for g in M.propose(t)["glossary"])
    assert lines == ["cucujo = Elateridae | distinto: cucuves", "cucuves = Mimus | distinto: cucujo"]


def test_an_explicit_remember_also_proposes_the_glossary_and_notes_stay_apart(app_state, tmp_path):
    fake = FakeBackend(reply="Entendido.")
    app_state.backends.resolve = lambda config=None: fake      # type: ignore[method-assign]
    p = app_state.projects.create("B", parent=tmp_path / "p")
    (p.memory).mkdir(parents=True, exist_ok=True)
    (p.memory / "notas.md").write_text("# Memoria\n\n2026-11-07 · Nota editada a mano.", encoding="utf-8")
    conv = app_state.chat.create_conversation(mode="local", project_id=p.id)
    app_state.chat.send(conv["id"], "Recuerda que el cucujo no es un nombre de los cucuves: los "
                        "cucujos son escarabajos de la familia Elateridae y los cucuves son aves "
                        "del género Mimus.", mode="local", run_async=False)
    meta = app_state.chat.get_messages(conv["id"])[-1]["meta"]
    assert meta["memory_saved"]["scope"] == "project"
    prop = meta["memory_proposals"]
    assert prop["notes"] == [] and {g["term"] for g in prop["glossary"]} == {"cucujo", "cucuves"}
    notes = (p.memory / "notas.md").read_text(encoding="utf-8")
    assert "a mano.\n\n20" in notes                              # not glued to the edited line


def test_a_plural_falls_back_to_the_singular_and_a_shared_genus_comes_first():
    from swarmbly_app import terms as T
    seen = []

    def fetch(url, timeout, ua):
        seen.append(url)
        if "wikidata" in url:
            return {"search": []}
        if "q=cucuves" in url:
            return {"results": []}
        return {"results": [
            {"key": 1, "canonicalName": "Mimus parvulus", "rank": "SPECIES", "genus": "Mimus",
             "genusKey": 9, "family": "Mimidae", "kingdom": "Animalia",
             "vernacularNames": [{"vernacularName": "Cucuve de Galápagos"}]},
            {"key": 2, "canonicalName": "Mimus trifasciatus", "rank": "SPECIES", "genus": "Mimus",
             "genusKey": 9, "family": "Mimidae", "kingdom": "Animalia", "vernacularNames": []}]}

    out = T.resolve(["cucuves"], "es", fetch=fetch)
    cands = out[0]["candidates"]
    assert cands[0]["label_en"] == "Mimus" and cands[0]["description"].startswith("genus")
    assert any("q=cucuve&" in u for u in seen)


def test_a_long_query_needs_two_of_its_words_in_a_result():
    terms = W.topic_terms("inbreeding Mimus Galapagos")
    assert not W.relevant({"title": "Galápagos tortoise", "provider": "wikipedia-en",
                           "snippet": "The Galápagos tortoise is the largest living tortoise."}, terms)
    assert W.relevant({"title": "Genomes of Galápagos Mockingbirds Reveal the Impact of Island "
                                "Size and Past Demography on Inbreeding", "provider": "pubmed"}, terms)
    assert W.relevant({"title": "Cucujos", "provider": "pubmed"}, W.topic_terms("cucujos"))


def test_the_english_common_name_of_a_genus_reaches_the_glossary():
    c = {"source": "gbif", "id": "9", "label_en": "Mimus", "scientific": "Mimus",
         "common_en": "mockingbird", "description": "genus · Mimidae · Animalia"}
    assert T.glossary_entry("cucuve", c)["equivalents"] == ["Mimus", "mockingbird"]


def test_a_glossary_request_is_not_kept_in_the_note():
    p = M.propose("Agrega a tu glosario: ROH (runs of homozygosity) son segmentos largos de homocigosis.")
    assert p["notes"] == ["ROH (runs of homozygosity) son segmentos largos de homocigosis."]
    assert p["glossary"][0]["equivalents"] == ["runs of homozygosity"]


def test_one_glossary_line_per_concept(tmp_path):
    from swarmbly_app.projects import save_glossary
    save_glossary(tmp_path, ["cucuves = Mimus | distinto: cucujo"])
    path = save_glossary(tmp_path, ["cucuve = Mimus, mockingbird", "endogamia = inbreeding | wd: Q38978"])
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if " = " in ln]
    assert lines == ["cucuves = Mimus, mockingbird | distinto: cucujo",
                     "endogamia = inbreeding | wd: Q38978"]


def test_an_answer_that_misses_an_equivalent_in_the_sources_is_flagged(app_state, tmp_path):
    from swarmbly_app.chat import _missed_sources
    pairs = [("endogamia", "inbreeding | wd: Q38978".split(" | ")[0]), ("cucuve", "Mimus, mockingbird")]
    passages = ["Island size shapes inbreeding in Galápagos mockingbirds (Mimus)."]
    out = _missed_sources("Las fuentes no mencionan la endogamia en cucuves.",
                          "¿Qué se sabe de la endogamia en cucuves?", pairs, passages)
    assert [x["found"] for x in out] == ["inbreeding", "Mimus"]
    assert _missed_sources("La endogamia es alta en Pinta.", "¿endogamia?", pairs, passages) == []


def test_two_names_of_one_concept_count_once_and_web_pages_need_the_concepts():
    groups = {"mimus": "cucuve", "mockingbird": "cucuve", "cucuve": "cucuve",
              "inbreeding": "endogamia", "endogamia": "endogamia"}
    terms = W.topic_terms("Mimus inbreeding mockingbird")
    assert not W.relevant({"title": "MockingBird: Context-aware Repository-level Code Translation",
                           "provider": "searxng", "snippet": "LLM code translation"}, terms, groups)
    assert not W.relevant({"title": "Cooper's hawk", "provider": "wikipedia-en",
                           "snippet": "It preys on the northern mockingbird (Mimus polyglottos)."},
                          terms, groups)
    assert W.relevant({"title": "Microsatellite primers for the four Galápagos mockingbird species",
                       "provider": "searxng",
                       "snippet": "useful to study levels of inbreeding in island populations"},
                      terms, groups)
    assert W.relevant({"title": "Genomes of Galápagos Mockingbirds … Inbreeding", "provider": "pubmed"},
                      terms, groups)


def test_spanish_fusion_answers_get_the_spanish_template():
    from swarmbly_app.chat import _lang
    assert _lang("Busca artículos recientes sobre endogamia en cucuves") == "es"


def test_english_equivalents_used_as_spanish_nouns_become_the_users_term():
    from swarmbly_app.chat import _spanish_terms
    text, fixes = _spanish_terms("Hay signos de la inbreeding en Pinta. El artículo «Inbreeding in "
                                 "mockingbirds» trata de inbreeding.",
                                 [("endogamia", "inbreeding"), ("cucuves", "Mimus, mockingbird")])
    assert text.startswith("Hay signos de la endogamia en Pinta.") and "«Inbreeding in mockingbirds»" in text
    assert fixes == [{"wrong": "inbreeding", "right": "endogamia", "count": 1}]


def test_works_are_not_concepts_and_glossary_words_are_not_sent(monkeypatch):
    sent = []

    def fetch(url, timeout, ua):
        sent.append(url)
        if "wbsearchentities" in url:
            return {"search": [{"id": "Q1"}, {"id": "Q2"}]}
        if "wbgetentities" in url:
            return {"entities": {
                "Q1": {"labels": {"en": {"value": "Mockingbird"}}, "descriptions": {"es": {"value": "álbum"}},
                       "claims": {"P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q482994"}}}}]}},
                "Q2": {"labels": {"en": {"value": "Mimus"}}, "descriptions": {"es": {"value": "género de aves"}},
                       "claims": {"P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q16521"}}}}]}}}}
        return {"results": []}
    out = T.resolve(["mockingbird"], "es", fetch=fetch)
    assert [c["label_en"] for c in out[0]["candidates"]] == ["Mimus"]
    sent.clear()
    out = T.resolve(["mockingbird"], "es", glossary=[("cucuves", "Mimus, mockingbird")], fetch=fetch)
    assert sent == [] and out[0]["candidates"][0]["source"] == "glossary"
