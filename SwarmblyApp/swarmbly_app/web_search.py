"""Online search the user approves, query in view (3.1).

Public evidence (P2e) sends only entity names, and only when the question
names a species: "search for recent articles on this" sent nothing, and the
model then invented references with authors and journals. Here the app
proposes a search query, the user sees it, can edit it, and approves it;
only that text is sent, to:

* **PubMed** (NCBI E-utilities): real articles with authors, journal, year
  and link (``esearch`` + ``esummary``), newest first when the question asks
  for recent work;
* **Wikipedia** (search API, in the user's language and in English);
* **SearXNG** (the user's own instance), when configured.

Every request goes through ``egress`` (recorded in the receipt). Results are
given to the model as numbered online references [W1]…, with the rule that
no other reference may be cited. When no search was made, the model is told
so and must not invent references.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any, Callable

from .engine.providers import USER_AGENT, _get

Fetch = Callable[[str, float, str], Any]

_FIRST_PERSON = re.compile(
    r"\b(yo|mi|mis|me|conmigo|nuestr[oa]s?|i|my|me|mine|our|we|eu|meu|minha)\b", re.I)
_FILLER = re.compile(
    r"\b(puedes|podr[ií]as|busca(?:r)?|buscar|encuentra|dime|hay|que|qu[eé]|cu[aá]les?|sobre|"
    r"en\s+l[ií]nea|online|internet|referencias?|art[ií]culos?|estudios?|recientes?|"
    r"de\s+los\s+[uú]ltimos\s+a[nñ]os|[uú]ltimos|a[nñ]os|please|search|find|for|about|recent|"
    r"articles?|studies|references?|el|la|los|las|un|una|de|del|y|o|en|a|the|of|and|or|in|"
    r"that|this|esto|eso|este|esta|con|para|por|se|lo|le|les|es|son|no|est[eé]n)\b", re.I)
_RECENT = re.compile(r"\b(reciente|recientes|[uú]ltimos\s+a[nñ]os|recent|latest|new)\b", re.I)


def propose_query(question: str, keywords: str = "") -> str:
    """A short query without first-person words; the user edits it before
    anything is sent. The local model's English keywords come first (PubMed
    and Wikipedia answer better in English)."""
    kw = [k.strip() for k in re.split(r"[,;]", keywords or "") if k.strip()]
    kw = [k for k in kw if not _FIRST_PERSON.search(k)][:4]
    rest = _FIRST_PERSON.sub(" ", question or "")
    rest = _FILLER.sub(" ", rest)
    rest = re.sub(r"[¿?¡!.,;:()\"]", " ", rest)
    words = [w for w in rest.split() if len(w) > 2][:8]
    query = " ".join(dict.fromkeys([*kw, *words]))
    return query[:160].strip()


def wants_recent(question: str) -> bool:
    return bool(_RECENT.search(question or ""))


def search(query: str, ev_cfg: dict[str, Any], lang: str = "es", recent: bool = False,
           limit: int = 6, fetch: Fetch | None = None) -> dict[str, Any]:
    """Search approved by the user. Fails closed per provider."""
    fetch = fetch or _get
    query = " ".join((query or "").split())[:200]
    timeout = max(float(ev_cfg.get("timeout_s", 4.0)), 6.0)
    providers = set(ev_cfg.get("providers") or ["wikidata", "wikipedia", "pubmed"])
    hits: list[dict[str, Any]] = []
    errors: list[str] = []
    if not query:
        return {"query": query, "results": [], "errors": ["empty query"]}
    if "pubmed" in providers:
        try:
            hits += _pubmed(query, recent, fetch, timeout)
        except Exception as exc:
            errors.append(f"pubmed: {type(exc).__name__}")
    if "wikipedia" in providers:
        for wl in dict.fromkeys([lang, "en"]):
            try:
                hits += _wikipedia(query, wl, fetch, timeout)
            except Exception as exc:
                errors.append(f"wikipedia-{wl}: {type(exc).__name__}")
    url = str(ev_cfg.get("searxng_url") or "")
    if "web" in providers and url:
        try:
            hits += _searxng(query, url, lang, fetch, timeout)
        except Exception as exc:
            errors.append(f"searxng: {type(exc).__name__}")
    seen, out = set(), []
    for h in hits:
        if h["url"] in seen:
            continue
        seen.add(h["url"])
        out.append(h)
    for i, h in enumerate(out[:limit], 1):
        h["label"] = f"W{i}"
    return {"query": query, "results": out[:limit], "errors": errors,
            "providers": sorted(p for p in providers if p in ("pubmed", "wikipedia", "web"))}


def _pubmed(query: str, recent: bool, fetch: Fetch, timeout: float) -> list[dict[str, Any]]:
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    ids = ((fetch(base + "esearch.fcgi?" + urllib.parse.urlencode(
        {"db": "pubmed", "term": query, "retmode": "json", "retmax": "4",
         "sort": "pub_date" if recent else "relevance", "tool": "SwarmblyApp"}),
        timeout, USER_AGENT) or {}).get("esearchresult") or {}).get("idlist") or []
    if not ids:
        return []
    data = fetch(base + "esummary.fcgi?" + urllib.parse.urlencode(
        {"db": "pubmed", "id": ",".join(ids), "retmode": "json", "tool": "SwarmblyApp"}),
        timeout, USER_AGENT) or {}
    res = data.get("result") or {}
    out = []
    for pmid in ids:
        r = res.get(pmid) or {}
        if not r.get("title"):
            continue
        authors = [a.get("name", "") for a in r.get("authors") or []][:3]
        year = str(r.get("pubdate", ""))[:4]
        out.append({"provider": "pubmed", "title": r["title"].rstrip("."),
                    "authors": ", ".join(authors) + (" et al." if len(r.get("authors") or []) > 3
                                                     else ""),
                    "year": year, "source": r.get("fulljournalname") or r.get("source", ""),
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", "snippet": ""})
    return out


def _wikipedia(query: str, lang: str, fetch: Fetch, timeout: float) -> list[dict[str, Any]]:
    data = fetch(f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "query", "list": "search", "srsearch": query, "srlimit": "2",
         "format": "json", "utf8": "1"}), timeout, USER_AGENT) or {}
    out = []
    for r in (data.get("query") or {}).get("search") or []:
        title = r.get("title", "")
        snippet = re.sub(r"<[^>]+>", "", r.get("snippet", ""))
        out.append({"provider": f"wikipedia-{lang}", "title": title, "authors": "", "year": "",
                    "source": f"Wikipedia ({lang})", "snippet": snippet[:300],
                    "url": f"https://{lang}.wikipedia.org/wiki/"
                           + urllib.parse.quote(title.replace(" ", "_"))})
    return out


def _searxng(query: str, url: str, lang: str, fetch: Fetch, timeout: float) -> list[dict[str, Any]]:
    data = fetch(url.rstrip("/") + "/search?" + urllib.parse.urlencode(
        {"q": query, "format": "json", "language": lang, "categories": "general,science"}),
        timeout, USER_AGENT) or {}
    return [{"provider": "searxng", "title": r.get("title", ""), "authors": "", "year": "",
             "source": urllib.parse.urlparse(r.get("url", "")).netloc,
             "snippet": (r.get("content") or "")[:300], "url": r.get("url", "")}
            for r in (data.get("results") or [])[:4] if r.get("url")]


def results_block(found: dict[str, Any], lang: str) -> str:
    head = {"es": ("Resultados de la búsqueda en línea que el usuario aprobó (consulta: «{q}»). "
                   "Son las ÚNICAS referencias en línea que puedes citar, como [W1], [W2]…; no "
                   "inventes autores, títulos, revistas, años ni enlaces. Si no responden a la "
                   "pregunta, dilo."),
            "en": ("Results of the online search the user approved (query: \"{q}\"). They are "
                   "the ONLY online references you may cite, as [W1], [W2]…; do not invent "
                   "authors, titles, journals, years or links. If they do not answer the "
                   "question, say so.")}
    lines = [head.get(lang, head["en"]).format(q=found.get("query", ""))]
    for h in found.get("results") or []:
        meta = " · ".join(x for x in (h.get("authors"), h.get("year"), h.get("source")) if x)
        lines.append(f"[{h['label']}] {h['title']}" + (f" — {meta}" if meta else "")
                     + f" <{h['url']}>" + (f": {h['snippet']}" if h.get("snippet") else ""))
    if not found.get("results"):
        lines.append("(sin resultados)" if lang == "es" else "(no results)")
    return "\n".join(lines)


NO_SEARCH = {
    "es": ("En esta respuesta NO se hizo ninguna búsqueda en internet. No cites artículos, "
           "autores, revistas ni enlaces que no estén en las fuentes dadas; si te piden "
           "referencias en línea, di que el usuario puede autorizar la búsqueda con el botón "
           "«Buscar en línea» debajo de la respuesta."),
    "en": ("NO internet search was made for this answer. Do not cite articles, authors, "
           "journals or links that are not in the given sources; if asked for online "
           "references, say the user can approve a search with the \"Search online\" button "
           "under the answer."),
}
