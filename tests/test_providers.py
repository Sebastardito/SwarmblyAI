"""Public evidence providers: Wikidata facts, PubMed sentences, composite."""

from __future__ import annotations

import json

from swarmbly_app.engine import evidence as ev
from swarmbly_app.engine.providers import (MultiProvider, PubMedProvider, WebSearchProvider,
                                           WikidataProvider, _names_only, build, wanted_props)

ENTITIES = {
    "Q1": {"labels": {"es": {"value": "Mimus melanotis"}}, "descriptions": {"es": {"value": "especie de ave"}},
           "claims": {"P141": [{"mainsnak": {"datavalue": {"value": {"id": "Q719675"}}}}]}},
    "Q2": {"labels": {"es": {"value": "Solitario George"}}, "descriptions": {"es": {"value": "tortuga"}},
           "claims": {"P570": [{"mainsnak": {"datavalue": {"value": {"time": "+2012-06-24T00:00:00Z",
                                                                      "precision": 11}}}}]}},
}


def wikidata_fetch(url, timeout, ua):
    if "wbsearchentities" in url:
        if "melanotis" in url:
            return {"search": [{"id": "Q1", "display": {"label": {"value": "Mimus melanotis"}}}]}
        if "Solitario" in url:
            return {"search": [{"id": "Q2", "display": {"label": {"value": "Lonesome George"}},
                                "match": {"text": "Solitario George"}}]}
        return {"search": []}
    if "ids=Q719675" in url:
        return {"entities": {"Q719675": {"labels": {"es": {"value": "casi amenazado"}}}}}
    for qid, data in ENTITIES.items():
        if f"ids={qid}" in url:
            return {"entities": {qid: data}}
    return {}


def test_wikidata_gives_the_status_and_dates_as_one_sentence():
    wd = WikidataProvider(lang="es", fetch=wikidata_fetch)
    hit = wd.facts("Mimus melanotis", ("P141",))
    assert hit["text"] == "Mimus melanotis (especie de ave) — estado de conservación UICN: casi amenazado."
    hit = wd.facts("Solitario George", ("P570",))
    assert "fecha de muerte: 24/6/2012" in hit["text"] and hit["provider"] == "wikidata"
    assert wd.facts("Nada que ver", ("P141",)) is None


def test_props_follow_the_operation_and_the_event_word():
    assert wanted_props(["categoria", "actual", "lista", "roja", "uicn"]) == ("P141",)
    assert wanted_props(["ano", "__year__"], "Muerte del Solitario George") == ("P570",)
    assert "P571" in wanted_props(["__year__"], "Inicio del Proyecto Isabela")
    assert wanted_props(["capital"]) == ()
    assert wanted_props(["__year__"], "Extirpación del cucuve de Floreana") == ()
    assert "P585" in wanted_props(["__year__"], "Batalla de Pichincha")
    assert _names_only("Muerte del Solitario George") == "Solitario George"
    assert _names_only("Mimus melanotis") == "Mimus melanotis"


def test_batch_lookup_prefers_the_structured_fact():
    class Wiki:
        lang = "es"

        def lookup(self, item, profile):
            return {"item": item, "title": "W", "text": "prose", "url": "u"}
    mp = MultiProvider(wikipedia=Wiki(), wikidata=WikidataProvider(fetch=wikidata_fetch))
    status = ev.operation_profile("Para cada una de las siguientes especies, indica solo su "
                                  "categoría actual en la Lista Roja de la UICN:")
    assert "casi amenazado" in mp.lookup("Mimus melanotis", status)["text"]
    capital = ev.operation_profile("Para cada uno de los siguientes países, indica solo su capital:")
    assert mp.lookup("Mimus melanotis", capital)["text"] == "prose"
    years = ev.operation_profile("Para cada uno de los siguientes acontecimientos, indica solo el "
                                 "año en que ocurrió:")
    hit = mp.lookup("Muerte del Solitario George", years)
    assert "2012" in hit["text"] and hit["item"] == "Muerte del Solitario George"


PUBMED_XML = """<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article>
<ArticleTitle>Philornis downsi in Galapagos birds</ArticleTitle><Journal><JournalIssue><PubDate><Year>2010</Year></PubDate></JournalIssue></Journal>
<Abstract><AbstractText>Philornis downsi is an invasive fly. It was first recorded in Darwin's finch nests in 1997. Larvae feed on nestlings.</AbstractText></Abstract>
</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""


def test_pubmed_brings_the_sentence_with_the_year_and_terms():
    seen = []

    def fetch(url, timeout, ua):
        seen.append(url)
        if "esearch" in url:
            return {"esearchresult": {"idlist": ["123"]}}
        return PUBMED_XML
    hit = PubMedProvider(fetch=fetch).passages("Philornis downsi", ["recorded", "__year__"])
    assert "1997" in hit["text"] and hit["url"].endswith("/123/") and hit["provider"] == "pubmed"
    assert all("Darwin" not in u.split("term=")[-1] for u in seen if "esearch" in u)


def test_web_search_only_with_a_url_or_a_key():
    assert WebSearchProvider().passages("Mimus melanotis", []) is None

    def fetch(url, timeout, ua):
        assert url.startswith("http://localhost:8888/search?") and "format=json" in url
        return {"results": [{"title": "Mimus melanotis", "content": "Near Threatened since 2020.",
                             "url": "https://x"}]}
    hit = WebSearchProvider(url="http://localhost:8888", fetch=fetch).passages("Mimus melanotis",
                                                                               ["threatened"])
    assert hit["provider"] == "searxng" and "2020" in hit["text"]


def test_build_respects_the_enabled_providers():
    mp = build("es", {"providers": ["wikipedia"]}, wikipedia=object())
    assert mp.names == ["wikipedia"]
    mp = build("es", {"providers": ["wikidata", "pubmed", "web"]}, wikipedia=None)
    assert mp.names == ["wikidata", "pubmed"]          # web needs a URL or a key


def test_local_passages_collect_every_provider():
    class Wiki:
        lang = "en"

        def passages(self, entity, focus):
            return {"title": "San Cristóbal mockingbird", "text": "Near Threatened.", "url": "u"}
    mp = MultiProvider(wikipedia=Wiki(), wikidata=WikidataProvider(fetch=wikidata_fetch))
    hits = mp.passages("Mimus melanotis", ["iucn", "status"])
    assert [h["title"] for h in hits] == ["Wikidata: Mimus melanotis", "San Cristóbal mockingbird"]


def test_no_wikidata_date_when_the_event_is_inside_the_item():
    assert wanted_props(["__year__"], "Inicio de la protección legal del lobo peletero de "
                                      "Galápagos en Ecuador") == ()
    assert "P580" in wanted_props(["__year__"], "Inicio de la Revolución francesa")
    assert "P580" in wanted_props(["__year__"], "Inicio de la Primera Guerra Mundial")
