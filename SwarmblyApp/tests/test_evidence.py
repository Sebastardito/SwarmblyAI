"""Public evidence for batch items (on by default since P2e round 12)."""

from __future__ import annotations

from swarmbly_app.engine import evidence as ev


def _page(title, extract):
    return {"query": {"pages": {"1": {"title": title, "extract": extract}}}}


def test_which_items_are_looked_up():
    assert ev.qualifies("Piquero de patas azules") and ev.qualifies("Ecuador")
    assert not ev.qualifies("perro") and not ev.qualifies("1500 m")


def test_lookup_keeps_relevant_results_and_attribution():
    seen = []

    def fetch(url, timeout, ua):
        seen.append((url, ua))
        return _page("Sula nebouxii piquero", "El piquero patiazul (Sula nebouxii) es una "
                     "especie de ave suliforme de la familia Sulidae. Vive en el Pacífico.")
    hit = ev.WikipediaEvidence(lang="es", fetch=fetch).lookup("Piquero de patas azules")
    assert hit["text"].startswith("El piquero patiazul") and "es.wikipedia.org" in hit["url"]
    assert "gsrsearch=Piquero+de+patas+azules" in seen[0][0] and "SwarmblyApp" in seen[0][1]


def test_scientific_title_is_accepted_and_disambiguation_dropped():
    sula = lambda url, t, ua: _page("Sula nebouxii", "El pájaro bobo de patas azules "  # noqa
                                    "(Sula nebouxii) es una especie de ave Suliforme.")
    assert ev.WikipediaEvidence(fetch=sula).lookup("Piquero de patas azules")
    lobo = lambda url, t, ua: _page("Lobo marino",                                      # noqa
                                    "El término lobo marino puede referirse a:")
    assert ev.WikipediaEvidence(fetch=lobo).lookup("Lobo marino") is None


def test_irrelevant_title_is_dropped():
    fetch = lambda url, t, ua: _page("Fútbol", "El fútbol es un deporte.")     # noqa: E731
    assert ev.WikipediaEvidence(fetch=fetch).lookup("Piquero de patas azules") is None


def test_long_extract_is_cut_at_a_word():
    fetch = lambda url, t, ua: _page("Ecuador", "Ecuador es un país " + "muy " * 100)  # noqa: E731
    hit = ev.WikipediaEvidence(fetch=fetch, max_chars=60).lookup("Ecuador")
    assert len(hit["text"]) <= 62 and hit["text"].endswith("…")


def test_gather_reports_queries_use_and_errors():
    def fetch(url, t, ua):
        if "Iguana" in url:
            raise TimeoutError()
        return _page("Ecuador", "Ecuador es un país de América del Sur; su capital es Quito.")
    found, report = ev.gather({1: "Ecuador", 2: "Iguana marina", 3: "perro"},
                              ev.WikipediaEvidence(fetch=fetch))
    assert list(found) == [1] and report["queried"] == ["Ecuador", "Iguana marina"]
    assert report["used"] == 1 and report["errors"] == ["TimeoutError"]
    block = ev.render(found, "es")
    assert block.splitlines()[0].startswith("Contexto público (Wikipedia)")
    assert block.splitlines()[1].startswith("- Ecuador: Ecuador es un país")


def test_orchestrator_adds_evidence_only_when_enabled_and_public(tmp_path, monkeypatch):
    from test_p2p_two_nodes import connect, make_node
    monkeypatch.setattr(ev, "_http_get_json", lambda url, t, ua: _page(
        "Ecuador", "Ecuador es un país de América del Sur; su capital es Quito."))
    worker, wfake = make_node(tmp_path, "W", worker=True,
                              reply="1. Quito\n2. Lima\n3. Santiago\n4. Buenos Aires\n"
                                    "5. Bogotá\n6. Montevideo\n7. Asunción\n8. Caracas")
    client, _ = make_node(tmp_path, "C", extra={
        "swarm": {"k_min": 1, "k_max": 1, "min_items_per_fragment": 4},
        "evidence": {"enabled": True}})
    try:
        connect(client, worker)
        conv = client.chat.create_conversation(mode="lan")
        client.chat.send(conv["id"], "Para cada uno de los siguientes países, indica solo "
                         "el nombre de su capital:\n1. Ecuador\n2. Perú\n3. Chile\n"
                         "4. Argentina\n5. Colombia\n6. Uruguay\n7. Paraguay\n8. Venezuela",
                         mode="lan", run_async=False)
        final = client.chat.get_messages(conv["id"])[-1]
        assert final["meta"].get("swarm"), final["meta"]
        report = final["meta"]["swarm"]["evidence"]
        assert report["used"] >= 1 and report["queried"][0] == "Ecuador"
        prompts = [m["content"] for call in wfake.calls for m in call["messages"]]
        assert any("Contexto público (Wikipedia)" in p and "su capital es Quito" in p
                   for p in prompts)
        assert not any("Para cada uno de los siguientes países, indica solo el nombre de su "
                       "capital:\n1. Ecuador\n2. Perú\n3. Chile\n4. Argentina\n5. Colombia" in p
                       for p in prompts)          # the request itself never travels
    finally:
        worker.stop()
        client.stop()


# -- operation-aware lookups (P2d) ----------------------------------------------------
ANIMALS = ("Para cada uno de los siguientes animales, indica en una sola palabra si es "
           "mamífero, ave, reptil, anfibio o pez:")


def _pages(mapping):
    """Fake fetch: the search query (gsrsearch) → (title, lead)."""
    import urllib.parse

    def fetch(url, t, ua):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["gsrsearch"][0]
        title, lead = mapping.get(q, ("", ""))
        return _page(title, lead) if title else {}
    return fetch


def test_profile_of_a_batch_operation():
    p = ev.operation_profile(ANIMALS)
    assert p.query_topic == "animal" and "anfibio" in p.focus and "ave" in p.focus
    p = ev.operation_profile("Para cada uno de los siguientes elementos químicos, indica "
                             "solo su símbolo químico:")
    assert p.focus == ["simbolo"] and p.query_topic == "elemento químico"
    p = ev.operation_profile("Para cada uno de los siguientes países, indica solo el "
                             "nombre de su capital:")
    assert p.query_topic == "país" and p.focus == ["capital"]
    assert ev.operation_profile("Para cada una de las siguientes frases en español, da "
                                "solo su traducción al inglés:").translation


def test_homonym_is_rejected_and_the_search_retried_with_the_topic():
    fetch = _pages({
        "Cecilia": ("Cecilia", "Cecilia es un nombre propio femenino de origen latino."),
        "Cecilia animal": ("Gymnophiona", "Los gimnofiones o cecilias son anfibios grandes "
                                          "sin patas, con forma de lombriz."),
    })
    hit = ev.WikipediaEvidence(fetch=fetch).lookup("Cecilia", ev.operation_profile(ANIMALS))
    assert hit["title"] == "Gymnophiona" and hit["query"] == "Cecilia animal"
    assert "anfibios" in hit["text"]


def test_snippet_takes_the_sentence_with_the_asked_fact():
    profile = ev.operation_profile("Para cada uno de los siguientes países, indica solo el "
                                   "nombre de su capital:")
    fetch = _pages({"Nigeria": ("Nigeria", "Nigeria es un país de África occidental. Lagos "
                                           "es su ciudad más poblada. Su capital es Abuya.")})
    hit = ev.WikipediaEvidence(fetch=fetch).lookup("Nigeria", profile)
    assert hit["text"] == "Nigeria es un país de África occidental. Su capital es Abuya."


def test_neighbouring_fact_does_not_pass_as_the_focus():
    profile = ev.operation_profile("Para cada uno de los siguientes elementos químicos, "
                                   "indica solo su símbolo químico:")
    fetch = _pages({"Plomo": ("Plomo", "El plomo es un elemento químico de número atómico "
                                       "82. Su símbolo es Pb, del latín plumbum.")})
    hit = ev.WikipediaEvidence(fetch=fetch).lookup("Plomo", profile)
    assert "Su símbolo es Pb" in hit["text"]


def test_implicit_disambiguation_and_translation_are_skipped():
    profile = ev.operation_profile("Para cada uno de los siguientes elementos químicos, "
                                   "indica solo su símbolo químico:")
    fetch = _pages({
        "Mercurio": ("Mercurio", "El término mercurio puede hacer referencia a: Mercurio "
                                 "(elemento), Mercurio (planeta)."),
        "Mercurio elemento químico": ("Mercurio (elemento)", "El mercurio es un elemento "
                                      "químico con el símbolo Hg y número atómico 80."),
    })
    hit = ev.WikipediaEvidence(fetch=fetch).lookup("Mercurio", profile)
    assert hit["title"] == "Mercurio (elemento)"
    found, report = ev.gather({1: "Buenos días"}, ev.WikipediaEvidence(fetch=fetch), 24,
                              ev.operation_profile("Para cada una de las siguientes frases "
                                                   "en español, da solo su traducción al "
                                                   "inglés:"))
    assert found == {} and report["skipped"].startswith("translation")


def test_unasked_figures_are_dropped_from_the_snippet():
    """P2d: 'cuyo símbolo es Pb … y su número atómico es 82' → answers 82, 80, 50."""
    e3 = ev.operation_profile("Para cada uno de los siguientes elementos químicos, indica "
                              "solo su símbolo químico:")
    assert ev.drop_unasked_numbers(
        e3, "El mercurio es un elemento químico con el símbolo Hg y número atómico 80."
    ) == "El mercurio es un elemento químico con el símbolo Hg."
    e2 = ev.operation_profile("Para cada uno de los siguientes países, indica solo el "
                              "nombre de su capital:")
    assert ev.drop_unasked_numbers(e2, "Nigeria tiene 220 millones de habitantes. Su capital "
                                       "es Abuya, y Lagos tiene 15 millones.") == "Su capital es Abuya."
    e5 = ev.operation_profile("Para cada uno de los siguientes acontecimientos históricos, "
                              "indica solo el año en que ocurrió:")
    text = "La batalla ocurrió el 24 de mayo de 1822."
    assert ev.drop_unasked_numbers(e5, text) == text          # a year is what is asked
    e4 = ev.operation_profile("Para cada una de las siguientes obras literarias, indica solo "
                              "el nombre de su autor:")
    text = "Huasipungo es una novela publicada en 1934 por el escritor Jorge Icaza."
    assert ev.drop_unasked_numbers(e4, text) == text          # the clause carries the author


def test_english_fallback_when_the_local_article_lacks_the_fact():
    es_article = "Mimus melanotis es una especie de ave de la familia Mimidae. Es endémica de San Cristóbal."
    en_article = ("The San Cristóbal mockingbird (Mimus melanotis) is a bird. It lives on one island. "
                  "Its song is loud. The IUCN has assessed it as Near Threatened. Prior to 2020 it "
                  "was classified as Endangered.")

    def fetch(url, timeout, ua):
        text = en_article if "en.wikipedia" in url else es_article
        return {"query": {"pages": {"1": {"title": "Mimus melanotis", "extract": text}}}}
    provider = ev.WikipediaEvidence(lang="es", fetch=fetch,
                                    fallback=ev.WikipediaEvidence(lang="en", fetch=fetch, max_chars=800))
    profile = ev.operation_profile("Para cada una de las siguientes especies de Galápagos, indica "
                                   "solo su categoría actual en la Lista Roja de la UICN:")
    hit = provider.lookup("Mimus melanotis", profile)
    assert hit and "Near Threatened" in hit["text"] and hit.get("fallback") == "en"


def test_local_batch_evidence_sends_only_items():
    sent = []

    def fetch(url, timeout, ua):
        sent.append(url)
        return {"query": {"pages": {}}}
    import swarmbly_app.engine.evidence as mod
    real = mod._http_get_json
    mod._http_get_json = fetch
    try:
        block, report = ev.local_batch("Para cada uno de los siguientes países, indica solo su "
                                       "capital:\n1. Australia\n2. Canadá\n3. Nigeria",
                                       {"evidence": {"enabled": True, "providers": ["wikipedia"]}}, "es")
    finally:
        mod._http_get_json = real
    assert report["local_batch"] and report["queried"] == ["Australia", "Canadá", "Nigeria"]
    assert all("capital" not in u.split("gsrsearch=")[1].split("&")[0].lower() or "Nigeria" in u
               or "Australia" in u or "Canad" in u for u in sent)


def test_event_items_get_year_sentences_from_the_english_article():
    en = ("Project Isabela was an environmental restoration project in the Galápagos Islands. "
          "It aimed at goats. It was initiated by the Charles Darwin Foundation. "
          "The initiative began in 1997, and by 2006, 150,000 goats were eradicated. "
          "In 1835 Darwin visited the islands.")

    def fetch(url, timeout, ua):
        if "en.wikipedia" in url:
            return {"query": {"pages": {"1": {"title": "Project Isabela", "extract": en}}}}
        return {"query": {"pages": {}}}
    provider = ev.WikipediaEvidence(lang="es", fetch=fetch,
                                    fallback=ev.WikipediaEvidence(lang="en", fetch=fetch, max_chars=800))
    profile = ev.operation_profile("Para cada uno de los siguientes acontecimientos de Galápagos, "
                                   "indica solo el año en que ocurrió:")
    hit = provider.lookup("Inicio del Proyecto Isabela", profile)
    assert hit and "1997" in hit["text"] and "1835" not in hit["text"] and hit["fallback"] == "en"
    assert provider.lookup("Proyecto Isabela", profile) is None     # no event word: no guess


def _wiki_fetch(es_pages, en_pages):
    """es: search query → (title, intro, english title); en: title → article."""
    import urllib.parse as up

    def fetch(url, timeout, ua):
        q = up.parse_qs(up.urlparse(url).query)
        term = q.get("gsrsearch", [""])[0]
        if "es.wikipedia" in url:
            for key, (title, intro, en) in es_pages.items():
                if key.lower() in term.lower():
                    return {"query": {"pages": {"1": {"title": title, "extract": intro,
                                                      "langlinks": [{"lang": "en", "*": en}]}}}}
            return {"query": {"pages": {}}}
        for title, text in en_pages.items():
            if term.lower() in title.lower() or title.lower() in term.lower():
                return {"query": {"pages": {"1": {"title": title, "extract": text}}}}
        return {"query": {"pages": {}}}
    return fetch


def test_event_subject_is_found_through_the_local_search_and_its_english_link():
    assert ev.event_subjects("Inicio de la protección legal del lobo peletero de Galápagos en "
                             "Ecuador") == ["lobo peletero de Galápagos"]
    assert ev.event_subjects("Extirpación del cucuve de Floreana en la isla Floreana") == \
        ["cucuve de Floreana"]
    es_pages = {"cucuve de Floreana": ("Mimus trifasciatus", "El cucuve de Floreana es un ave.",
                                       "Floreana mockingbird"),
                "lobo peletero": ("Arctocephalus galapagoensis",
                                  "El lobo peletero de Galápagos es un otárido.", "Galápagos fur seal")}
    en_pages = {
        "Floreana mockingbird": "The Floreana mockingbird is a bird. It lives on two islets. "
                                "== Distribution == It was abundant on Floreana Island but had been "
                                "extirpated from there by 1888. Darwin visited in 1835.",
        "Galápagos fur seal": "The Galápagos fur seal is a seal. It is the smallest eared seal. "
                              "It has been protected by the Ecuadorian government since 1934. "
                              "Starting in 1959, Ecuador established strict laws to protect these animals.",
        "Floreana Island": "Floreana Island is an island. In 2026 goats were extirpated again.",
        "Galápagos Islands": "The islands were protected in 2018 by a new law.",
    }
    fetch = _wiki_fetch(es_pages, en_pages)
    provider = ev.WikipediaEvidence(lang="es", fetch=fetch,
                                    fallback=ev.WikipediaEvidence(lang="en", fetch=fetch, max_chars=800))
    profile = ev.operation_profile("Para cada uno de los siguientes acontecimientos de Galápagos, "
                                   "indica solo el año en que ocurrió:")
    hit = provider._fallback_year("Extirpación del cucuve de Floreana en la isla Floreana", profile)
    assert hit and "1888" in hit["text"] and "1835" not in hit["text"]
    assert hit["title"] == "Floreana mockingbird" and "==" not in hit["text"]
    hit = provider._fallback_year("Inicio de la protección legal del lobo peletero de Galápagos "
                                  "en Ecuador", profile)
    # the event word nearest the subject ("protección") decides, the first such sentence wins
    assert hit and "1934" in hit["text"] and "1959" not in hit["text"]


def test_event_year_prefers_the_lead_sentence():
    en = {"Project Isabela": "The Project Isabela was a restoration project in the Galápagos "
                             "Islands that took place between 1997 and 2006, initiated by the "
                             "Charles Darwin Foundation. Goats were introduced in the 16th century. "
                             "The initiative was brought into action in 1999, and by 2006 goats "
                             "were eradicated."}
    fetch = _wiki_fetch({"Proyecto Isabela": ("Proyecto Isabela", "El Proyecto Isabela fue un "
                                              "proyecto.", "Project Isabela")}, en)
    provider = ev.WikipediaEvidence(lang="es", fetch=fetch,
                                    fallback=ev.WikipediaEvidence(lang="en", fetch=fetch, max_chars=800))
    profile = ev.operation_profile("Para cada uno de los siguientes acontecimientos de Galápagos, "
                                   "indica solo el año en que ocurrió:")
    hit = provider._fallback_year("Inicio del Proyecto Isabela", profile)
    assert hit and "1997" in hit["text"] and "1999" not in hit["text"]


def test_unrelated_local_search_hit_is_not_followed():
    fetch = _wiki_fetch({"cucuve": ("Fundación Charles Darwin", "Una fundación científica.",
                                    "Charles Darwin Foundation")}, {})
    provider = ev.WikipediaEvidence(lang="es", fetch=fetch)
    assert provider.english_title("cucuve de Floreana") is None


def test_partial_match_is_not_followed():
    fetch = _wiki_fetch({"Proyecto Isabela": ("Provincia de Isabela", "Isabela es una provincia "
                                              "de Filipinas.", "Isabela (province)")}, {})
    assert ev.WikipediaEvidence(lang="es", fetch=fetch).english_title("Proyecto Isabela") is None


def test_public_evidence_is_on_by_default():
    from swarmbly_app.config import DEFAULTS
    assert DEFAULTS["evidence"]["enabled"] is True
