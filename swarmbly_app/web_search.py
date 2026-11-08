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
    r"that|this|esto|eso|este|esta|con|para|por|se|lo|le|les|es|son|no|est[eé]n|"
    r"papers?|latest|new|nuevos?|review|reviews|publicaciones|trabajos|investigaci[oó]n(?:es)?|"
    r"literature|literatura|bibliograf[ií]a|informaci[oó]n|information|some|any|algunos?|"
    r"sobre|acerca|related|relacionad[oa]s?|tema|topic|me|show|give|list|lista)\b", re.I)
# Words that say nothing about the topic: a result must share something more
# specific with the query (4th test: "cucujos recent papers" returned papers on
# biosensors, and "Charles Darwin" for mockingbirds)
_GENERIC = frozenset("""
study studies analysis analyses genomic genomics genetic genetics population populations species
data effect effects impact evolution evolutionary ecology ecological review recent new approach
method methods model models role case report reports research science biology insights based
estudio estudios análisis genómica genética población poblaciones especie especies efecto
""".split())
_RECENT = re.compile(r"\b(reciente|recientes|[uú]ltimos\s+a[nñ]os|recent|latest|new)\b", re.I)


def _fold(w: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", w.lower()) if not unicodedata.combining(c))


_LATIN = re.compile(r"\b([A-Z][a-z]{3,}(?:idae|inae|aceae|ales)|[A-Z][a-z]{3,}\s[a-z]{4,}|"
                    r"[A-Z][a-z]{4,}(?:us|um|is|es|a))\b")


def topic_terms(query: str) -> list[str]:
    """The query's specific words: not filler, not generic science words."""
    out = []
    for w in re.findall(r"[\wÁÉÍÓÚÑáéíóúñ'-]+", query or ""):
        f = _fold(w).strip("'")
        if len(f) >= 4 and f not in _GENERIC and not _FILLER.fullmatch(w) \
                and not _FIRST_PERSON.fullmatch(w) and f not in (_fold(x) for x in out):
            out.append(w)
    return out


def relevant(hit: dict[str, Any], terms: list[str]) -> bool:
    """A result is kept only if its title (or, for an encyclopaedia, its
    snippet) carries one of the query's specific words."""
    if not terms:
        return True
    title = _fold(hit.get("title", ""))
    snippet = _fold(hit.get("snippet", ""))

    def has(t: str, text: str) -> bool:
        stem = _fold(t)[:max(4, len(t) - 2)]
        return stem in text
    if any(has(t, title) for t in terms):
        return True
    return hit.get("provider", "").startswith("wikipedia") and \
        sum(has(t, snippet) for t in terms) >= min(2, len(terms))


def propose_query(question: str, keywords: str = "",
                  glossary: list[tuple[str, str]] | None = None,
                  passages: list[str] | None = None) -> str:
    """A short query without first-person words; the user edits it before
    anything is sent.

    The user's glossary translates first ("cucuve = mockingbird, Mimus" turns
    "cucuves" into "mockingbird"); the local model's keywords are used only
    when they share a word with the question or the glossary (in the third
    test it offered "galapagos quails" and "Darwin's finches" for cucuves, and
    PubMed found nothing for the whole string)."""
    from .lang import detect_language  # noqa: F401  (kept for callers' symmetry)
    q = question or ""
    fold = q.lower()
    translated: list[str] = []
    for term, equivalents in glossary or []:
        stem = term.lower().rstrip("s")
        if len(stem) >= 3 and stem in fold:
            translated += [e.strip() for e in equivalents.split(",") if e.strip()][:2]
            q = re.sub(re.escape(term.rstrip("s")) + r"\w*", " ", q, flags=re.I)
    rest = _FIRST_PERSON.sub(" ", q)
    rest = _FILLER.sub(" ", rest)
    rest = re.sub(r"[¿?¡!.,;:()\"]", " ", rest)
    words = [w for w in rest.split() if len(w) > 2][:6]
    # The topic, defined from the user's own material: scientific names that
    # appear next to a word of the question in the retrieved passages or notes
    # ("cucujos (cucuyos) son el género Pyrophorus de la familia Elateridae").
    defined: list[str] = []
    anchors = [_fold(w)[:5] for w in words + translated if len(w) >= 4]
    for text in passages or []:
        for sentence in re.split(r"(?<=[.;!?])\s+", text or ""):
            if any(a in _fold(sentence) for a in anchors):
                defined += [m for m in _LATIN.findall(sentence) if " " not in m or True]
    defined = defined[:3]
    known = _fold(" ".join([*words, *translated, *defined]))
    kw = [k.strip() for k in re.split(r"[,;]", keywords or "") if k.strip()]
    kw = [k for k in kw if not _FIRST_PERSON.search(k) and not _FILLER.fullmatch(k)
          and any(_fold(w)[:5] in known for w in k.split() if len(w) >= 4)][:3]
    out: list[str] = []
    for piece in [*translated, *defined, *kw, *words]:
        for w in _FILLER.sub(" ", piece).split():
            if len(w) > 2 and not any(_same_word(w, x) for x in out):
                out.append(w)
    return " ".join(out)[:160].strip()


def _same_word(a: str, b: str) -> bool:
    """The same word, or the same word in two languages ("endogamy" /
    "endogamia", "mockingbird" / "mockingbirds"): the first one stays."""
    fa, fb = _fold(a), _fold(b)
    return fa == fb or (min(len(fa), len(fb)) >= 6 and fa[:6] == fb[:6])


def _variants(query: str) -> list[str]:
    """The approved text without filler words, then shorter subsets of it:
    PubMed ANDs every word, so one untranslated or rare word returned nothing
    (third test). Subsets keep the specific words; only words of the approved
    text are ever sent."""
    cleaned = " ".join(w for w in query.split() if not _FILLER.fullmatch(w)) or query
    words = []
    for w in cleaned.split():
        if not any(_same_word(w, x) for x in words):
            words.append(w)
    out = [" ".join(words)]
    ascii_words = [w for w in words if w.isascii()]
    if ascii_words and len(ascii_words) < len(words):
        out.append(" ".join(ascii_words))
    specific = [w for w in (ascii_words or words) if w in topic_terms(" ".join(words))]
    ranked = sorted(dict.fromkeys(specific or ascii_words or words), key=len, reverse=True)
    for n in (3, 2):
        if len(ranked) >= n and len(ranked) > 1:
            out.append(" ".join(w for w in words if w in ranked[:n]))
    return list(dict.fromkeys(v for v in out if v))


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
    terms = topic_terms(" ".join(w for w in query.split() if not _FILLER.fullmatch(w)))
    tried: list[str] = []
    dropped = 0
    if "pubmed" in providers:
        for variant in _variants(query):
            tried.append(variant)
            try:
                found = _pubmed(variant, recent, fetch, timeout)
            except Exception as exc:
                errors.append(f"pubmed: {type(exc).__name__}")
                break
            kept = [h for h in found if relevant(h, terms)]
            dropped += len(found) - len(kept)
            if kept:
                hits += kept
                break
    if "wikipedia" in providers:
        for wl in dict.fromkeys([lang, "en"]):
            for variant in _variants(query):
                try:
                    found = _wikipedia(variant, wl, fetch, timeout)
                except Exception as exc:
                    errors.append(f"wikipedia-{wl}: {type(exc).__name__}")
                    break
                kept = [h for h in found if relevant(h, terms)]
                dropped += len(found) - len(kept)
                if kept:
                    hits += kept
                    break
    url = str(ev_cfg.get("searxng_url") or "")
    if "web" in providers and url and _reachable(url):
        try:
            found = _searxng(query, url, lang, fetch, timeout)
            kept = [h for h in found if relevant(h, terms)]
            dropped += len(found) - len(kept)
            hits += kept
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
    return {"query": query, "results": out[:limit], "errors": errors, "variants": tried,
            "topic": terms, "dropped_unrelated": dropped,
            "providers": sorted(p for p in providers if p in ("pubmed", "wikipedia", "web"))}


def _reachable(url: str) -> bool:
    """A configured SearXNG that is not running is skipped (the third test
    logged "searxng: URLError" on every search)."""
    import socket
    parts = urllib.parse.urlsplit(url)
    try:
        with socket.create_connection((parts.hostname or "127.0.0.1",
                                       parts.port or (443 if parts.scheme == "https" else 80)),
                                      timeout=1.0):
            return True
    except OSError:
        return False


def _pubmed(query: str, recent: bool, fetch: Fetch, timeout: float) -> list[dict[str, Any]]:
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": "6",
              "sort": "relevance", "tool": "SwarmblyApp"}
    if recent:
        # "recent" = the last five years, still by relevance: sorting by date
        # brought the newest papers on anything (4th test)
        import datetime
        year = datetime.date.today().year
        params.update(datetype="pdat", mindate=str(year - 5), maxdate=str(year + 1))
    ids = ((fetch(base + "esearch.fcgi?" + urllib.parse.urlencode(params),
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
