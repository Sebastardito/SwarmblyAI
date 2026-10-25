"""Public evidence for the items of a batch (on by default since P2e round 12).

Several small models can agree on the same wrong answer ("Piquero de patas
azules → pez", "Pingüino de Galápagos → mamífero" in P3b–P3l): a vote cannot
fix an error the voters share. This module looks up a short public
description of each item and the orchestrator adds it to that item's
fragment, so every worker reads the same evidence.

Rules (preregistered in the P2 note of the P3b document):

- **On by default since P2e round 12** (``evidence.enabled``; it was off
  through P2d). Only *item texts* or entity names — never the request — go
  to the providers; the user can turn it off in Settings → Privacy.
- **Public requests only**: the orchestrator calls this module only when the
  request's lane is PUBLIC and the batch is enumerated.
- **Items that name something**: an item qualifies if it has a word of three
  or more letters and is either several words long or capitalised
  ("Piquero de patas azules", "Ecuador"); single lower-case words ("perro")
  and quantities ("1500 m") are not looked up.
- **Relevance gate**: a result is used only if its title or lead shares a
  word of four or more letters with the item (titles are often scientific
  names: "Sula nebouxii" for "Piquero de patas azules"); disambiguation
  pages ("puede referirse a:") are not evidence.
- **Provider**: Wikipedia (MediaWiki Action API, in the request's
  language), first two sentences of the lead, attributed. No API key.

Failures (network, timeout, no result) leave the fragment unchanged; the
metadata says what was looked up and what was used.

**Operation-aware lookups** (P2d, after P2c showed homonyms and neighbouring
facts misleading answers the network already got right):

- the batch operation ("Para cada uno de los siguientes animales, indica…
  si es mamífero, ave…") gives a **topic** ("animal") and **focus** terms
  ("mamífero", "capital", "símbolo", "autor", "año");
- a result must mention the topic or a focus term (or a year, when the
  focus is a year; a writer, when it is an author). If the item alone does
  not give such an article ("Cecilia" → the first name), the search is
  repeated with the topic ("Cecilia animal" → Gymnophiona) and that result
  must pass the same check;
- the snippet is the article's first sentence plus the first sentence that
  carries a focus term ("…su capital es Abuya"), instead of always the first
  two;
- translation batches are not looked up (the items name nothing).
"""

from __future__ import annotations

import json
import re
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable

WIKI_API = "https://{lang}.wikipedia.org/w/api.php"
WIKI_PAGE = "https://{lang}.wikipedia.org/wiki/{title}"
SUPPORTED_LANGS = ("es", "en", "pt", "fr")

_WORD = re.compile(r"[^\W\d_]+", re.U)
_DISAMBIGUATION = re.compile(r"(puede referirse a|puede hacer referencia a|may refer to|"
                             r"peut faire référence|pode referir-se|se refiere a varios)", re.I)

HEADER = {
    "es": "Contexto público (Wikipedia) sobre algunos elementos; úsalo solo si es pertinente:",
    "en": "Public context (Wikipedia) about some items; use it only if relevant:",
    "pt": "Contexto público (Wikipédia) sobre alguns itens; use-o apenas se for pertinente:",
    "fr": "Contexte public (Wikipédia) sur certains éléments ; utilise-le seulement s'il est pertinent :",
}


def _fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.casefold())
                   if unicodedata.category(c) != "Mn")


def qualifies(item: str) -> bool:
    words = _WORD.findall(item or "")
    if not any(len(w) >= 3 for w in words):
        return False
    return len(words) >= 2 or (words[0][:1].isupper() if words else False)


def _stem(word: str) -> str:
    """Singular-ish form, so "tortuga" meets "tortugas" and "tiburón" meets
    "tiburones"."""
    if word.endswith("ces") and len(word) > 4:      # peces → pez, luces → luz
        return word[:-3] + "z"
    if word.endswith("es") and len(word) > 5:
        return word[:-2]
    if word.endswith("s") and len(word) > 3:       # aves → ave
        return word[:-1]
    return word


def relevant(item: str, text: str) -> bool:
    a = {_stem(w) for w in (_fold(x) for x in _WORD.findall(item)) if len(w) >= 4}
    b = {_stem(w) for w in (_fold(x) for x in _WORD.findall(text)) if len(w) >= 4}
    return bool(a & b)


_STOP = frozenset(_fold(w) for w in (
    "para cada uno una unos unas los las del de la el en su sus si es o y u a al "
    "que por con sin solo sola indica indicar da dar escribe di dime nombre nombres "
    "palabra palabras siguientes siguiente following each for the of a an in its "
    "only one word give write name answer what which is are it this that its "
    "ocurrio ocurrió occurred happened se").split())
_TRANSLATION = re.compile(r"\b(tradu\w*|translat\w*|tradui\w*)", re.I)
_TOPIC = re.compile(r"(?:siguientes|following|seguintes|suivant(?:e)?s)\s+([^,:;]+?)"
                    r"(?:\s+en\s+\w+)?\s*[,:;]", re.I)
_YEAR = re.compile(r"\b(1\d{3}|20\d{2})\b")
_AUTHOR = frozenset({"autor", "autora", "escritor", "escritora", "novelista", "poeta",
                     "poetisa", "dramaturgo", "escrita", "escrito", "author", "writer",
                     "novelist", "poet", "ecrivain", "auteur", "escritor"})


@dataclass
class OperationProfile:
    topic: list[str]                    # stems of the topic noun phrase
    focus: list[str]                    # stems of what is asked
    translation: bool = False
    query_topic: str = ""               # singular topic phrase for a retry

    @property
    def wants_year(self) -> bool:
        return "ano" in self.focus or "year" in self.focus or "date" in self.focus

    @property
    def wants_author(self) -> bool:
        return any(f in ("autor", "author", "auteur") for f in self.focus)

    def to_dict(self) -> dict[str, Any]:
        return {"topic": self.query_topic, "focus": self.focus,
                "translation": self.translation}


def _singular(phrase: str) -> str:
    out = []
    for w in phrase.split():
        f = w.lower()
        if f.endswith(("íses", "eses")) or (f.endswith("es") and len(f) > 5
                                             and f[-3] in "lrndz"):
            w = w[:-2]
        elif f.endswith("s") and len(f) > 3:
            w = w[:-1]
        out.append(w)
    return " ".join(out)


def operation_profile(preamble: str) -> OperationProfile:
    """Topic and focus of a batch operation ("…siguientes países, indica…
    su capital" → topic "país", focus "capital")."""
    text = " ".join((preamble or "").split())
    match = _TOPIC.search(text)
    topic_phrase = match.group(1).strip() if match else ""
    rest = text[match.end():] if match else text
    words = lambda t: [_stem(_fold(w)) for w in _WORD.findall(t)
                       if _fold(w) not in _STOP and len(w) >= 3]
    topic = words(topic_phrase)
    # "su símbolo químico" for "elementos químicos": "químico" is the topic,
    # only "símbolo" is what is asked (P2d dry run: a first sentence with
    # "elemento químico de número atómico 47" passed as the focus sentence).
    focus = [w for w in words(rest) if w not in topic]
    return OperationProfile(topic=topic, focus=focus,
                            translation=bool(_TRANSLATION.search(text)),
                            query_topic=_singular(topic_phrase))


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡(«\"])", text)
    return [p.strip() for p in parts if p.strip()]


def _mentions(profile: OperationProfile, text: str) -> bool:
    stems = {_stem(_fold(w)) for w in _WORD.findall(text)}
    if stems & set(profile.topic) or stems & set(profile.focus):
        return True
    if profile.wants_year and _YEAR.search(text):
        return True
    return profile.wants_author and bool(stems & {_stem(a) for a in _AUTHOR})


def _focus_sentence(profile: OperationProfile, sentence: str) -> bool:
    stems = {_stem(_fold(w)) for w in _WORD.findall(sentence)}
    if stems & set(profile.focus):
        return True
    if profile.wants_year and _YEAR.search(sentence):
        return True
    return profile.wants_author and bool(stems & {_stem(a) for a in _AUTHOR})


# Operation focus terms (folded, singular) → English words to look for in an
# English article when the local-language article lacks the fact.
EN_FOCUS = {
    "uicn": "iucn threatened endangered vulnerable concern assessed",
    "iucn": "iucn threatened endangered vulnerable concern assessed",
    "categoria": "status", "conservacion": "conservation",
    "estado": "status", "amenaza": "threatened", "capital": "capital", "simbolo": "symbol",
    "autor": "author", "autora": "author", "ano": "year", "fecha": "year",
    "poblacion": "population", "habitante": "population", "altitud": "elevation",
    "altura": "height", "pai": "country", "continente": "continent", "idioma": "language",
    "moneda": "currency", "fundacion": "founded", "descubrimiento": "discovered",
}

# Spanish event words (folded prefixes) → English stems a dated sentence uses.
EN_EVENT = {
    "muerte": "died death", "fallec": "died death", "murio": "died death",
    "inicio": "began begin start initiat launch", "comienzo": "began begin start",
    "fundacion": "found establish", "creacion": "creat establish found",
    "extirpacion": "extirpat extinct", "extincion": "extinct extirpat",
    "desaparicion": "extinct extirpat disappear",
    "proteccion": "protect", "declaracion": "declar", "descubrimiento": "discover",
    "llegada": "arriv", "erupcion": "erupt", "registro": "record report detect",
    "nacimiento": "born", "publicacion": "publish", "erradicacion": "eradicat",
}

_IUCN_ANCHOR = re.compile(r"\b(IUCN|UICN|Red List|Lista Roja|BirdLife)\b", re.I)

_NUMERIC_FOCUS = frozenset(_stem(_fold(w)) for w in (
    "año años fecha fechas número números cantidad población habitantes altura altitud "
    "longitud distancia superficie área edad temperatura precio peso masa duración "
    "kilómetros metros porcentaje cifra year date number population height length "
    "area age temperature price weight").split())
_CLAUSE = re.compile(r"\s*(?:[,;]|\s+y\s+|\s+e\s+|\s+and\s+)\s*")


def drop_unasked_numbers(profile: OperationProfile, text: str) -> str:
    """Remove clauses that carry figures the operation does not ask for.

    P2d (24 Oct 2026): "cuyo símbolo es Pb … y su número atómico es 82" made a
    fragment answer 82, 80 and 50 instead of Pb, Hg and Sn. When the focus is
    not numeric, a clause with digits and no focus term is dropped; clauses
    that carry the asked fact are kept whole.
    """
    if profile.wants_year or set(profile.focus) & _NUMERIC_FOCUS or not re.search(r"\d", text):
        return text
    out = []
    for sentence in _sentences(text):
        clauses = [re.sub(r"^(?:y|e|and)\s+", "", c) for c in _CLAUSE.split(sentence) if c]
        kept = [c for c in clauses
                if not re.search(r"\d", c) or _focus_sentence(profile, c)]
        if not kept:
            continue
        joined = ", ".join(kept).rstrip(" ,")
        if not joined.endswith((".", "!", "?", "…")):
            joined += "."
        out.append(joined)
    return " ".join(out) if out else text


_SUBJECT_SPLIT = re.compile(r"\s+(?:del|de\s+la|de\s+los|de\s+las|of\s+the|of)\s+", re.I)
_LOCATIVE = re.compile(r"\s+(?:en|in|on)\s+.*$", re.I)


def event_subjects(item: str) -> list[str]:
    """Subjects of an event item, outermost first: "Inicio de la protección
    legal del lobo peletero de Galápagos en Ecuador" → ["lobo peletero de
    Galápagos"] (the tail after each "del/de la…", skipping tails that start
    with another event word, without a trailing place such as "en la isla
    Floreana"); "Fundación de la Universidad de los Andes" → ["Universidad de
    los Andes", "Andes"]."""
    out = []
    for m in _SUBJECT_SPLIT.finditer(item):
        tail = _LOCATIVE.sub("", item[m.end():]).strip(" ,.;")
        words = tail.split()
        if len(tail) < 4 or not words or any(_fold(words[0]).startswith(k) for k in EN_EVENT):
            continue
        if tail not in out:
            out.append(tail)
    return out


def _http_get_json(url: str, timeout_s: float, user_agent: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:   # noqa: S310 (fixed host)
        return json.loads(resp.read().decode("utf-8"))


@dataclass
class WikipediaEvidence:
    lang: str = "es"
    timeout_s: float = 4.0
    max_chars: int = 220
    user_agent: str = "SwarmblyApp (https://github.com/Sebastardito/SwarmblyApp)"
    fetch: Callable[[str, float, str], Any] | None = None   # injectable for tests
    # P2e: when the article in ``lang`` lacks the asked fact (Spanish articles on
    # Galápagos species carry no IUCN status), an English provider is asked for
    # the sentences with the focus terms, translated by ``EN_FOCUS``.
    fallback: "WikipediaEvidence | None" = None

    def url_for(self, query: str, sentences: int | None = 2, intro: bool = True) -> str:
        params = {"action": "query", "format": "json", "utf8": "1",
                  "generator": "search", "gsrsearch": query, "gsrlimit": "1",
                  "prop": "extracts", "explaintext": "1",
                  "redirects": "1"}
        if intro:
            params["exintro"] = "1"
        if sentences:
            params["exsentences"] = str(sentences)
        return WIKI_API.format(lang=self.lang) + "?" + urllib.parse.urlencode(params)

    def _page(self, query: str, sentences: int | None, intro: bool = True):
        data = (self.fetch or _http_get_json)(self.url_for(query, sentences, intro),
                                              self.timeout_s, self.user_agent)
        pages = ((data or {}).get("query") or {}).get("pages") or {}
        for page in pages.values():
            title = str(page.get("title") or "")
            text = " ".join(str(page.get("extract") or "").split())
            if title and text and not _DISAMBIGUATION.search(text):
                return title, text
        return None

    def _cut(self, text: str) -> str:
        if len(text) <= self.max_chars:
            return text
        cut = text[: self.max_chars]
        return cut[: cut.rfind(" ")] + " …" if " " in cut else cut

    def lookup(self, item: str, profile: OperationProfile | None = None) -> dict[str, Any] | None:
        if profile is None:                       # P2a behaviour
            page = self._page(item, 2)
            if not page or not relevant(item, f"{page[0]} {page[1][:300]}"):
                return None
            title, text = page
            return self._hit(item, item, title, self._cut(text))
        queries = [item]
        if profile.query_topic:
            queries.append(f"{item} {profile.query_topic}")
        for query in queries:
            page = self._page(query, None)        # whole lead: pick the sentence
            if not page:
                continue
            title, text = page
            head = f"{title} {text[:600]}"
            if not relevant(item, head) or not _mentions(profile, head):
                continue
            sentences = _sentences(text)
            first = sentences[0] if sentences else text
            focus = next((x for x in sentences[1:] if _focus_sentence(profile, x)), "")
            if _focus_sentence(profile, first) or not focus:
                snippet = self._around_focus(profile, first)
            else:
                snippet = f"{first} {focus}"
                if len(snippet) > self.max_chars:
                    snippet = self._around_focus(profile, focus)   # the asked-for fact
            if not focus and not _focus_sentence(profile, first) and self.fallback is not None:
                hit = self._fallback(item, profile)
                if hit:
                    return hit
            snippet = drop_unasked_numbers(profile, snippet)
            return self._hit(item, query, title, self._cut(snippet))
        if self.fallback is not None:
            return self._fallback(item, profile)
        return None

    def _fallback(self, item: str, profile: OperationProfile) -> dict[str, Any] | None:
        if profile.wants_year:
            return self._fallback_year(item, profile)
        focus = sorted({w for f in profile.focus if f in EN_FOCUS for w in EN_FOCUS[f].split()})
        if not focus:
            return None
        try:
            hit = self.fallback.passages(item, focus, max_sentences=2)
        except Exception:
            return None
        if not hit:
            return None
        sentences = _sentences(hit["text"])
        stems = {_stem(f) for f in focus}
        chosen = [x for x in sentences[2:] if {_stem(_fold(w)) for w in _WORD.findall(x)} & stems]
        if "iucn" in focus:
            # "vulnerable to disease" is not a status: an assessment needs its author
            chosen = [x for x in chosen if _IUCN_ANCHOR.search(x)]
        if not chosen:
            return None
        text = drop_unasked_numbers(profile, " ".join(chosen[:2]))
        hit["text"] = text if len(text) <= max(self.max_chars, 320) else \
            text[:320][: text[:320].rfind(" ")] + " …"
        hit["fallback"] = self.fallback.lang
        return hit

    def english_title(self, query: str) -> str | None:
        """Title of the best article for ``query`` in this language, as the
        English article it links to ("cucuve de Floreana" → Mimus trifasciatus
        → Floreana mockingbird). The match must share a word with the query in
        its title or first sentences, so an unrelated hit is not followed.
        Every content word of the query must appear there: "Proyecto Isabela"
        must not follow "Provincia de Isabela" (Philippines)."""
        params = {"action": "query", "format": "json", "utf8": "1",
                  "generator": "search", "gsrsearch": query, "gsrlimit": "1",
                  "prop": "extracts|langlinks", "exintro": "1", "explaintext": "1",
                  "exsentences": "3", "lllang": "en", "redirects": "1"}
        try:
            data = (self.fetch or _http_get_json)(
                WIKI_API.format(lang=self.lang) + "?" + urllib.parse.urlencode(params),
                self.timeout_s, self.user_agent)
        except Exception:
            return None
        for page in (((data or {}).get("query") or {}).get("pages") or {}).values():
            title = str(page.get("title") or "")
            want = {_stem(w) for w in (_fold(x) for x in _WORD.findall(query)) if len(w) >= 4}
            have = {_stem(w) for w in (_fold(x) for x in
                                       _WORD.findall(f"{title} {page.get('extract') or ''}"))}
            if not title or not want or not want <= have:
                continue
            if self.lang == "en":
                return title
            links = page.get("langlinks") or []
            return str(links[0].get("*") or links[0].get("title") or "") or None if links else None
        return None

    def _fallback_year(self, item: str, profile: OperationProfile) -> dict[str, Any] | None:
        """Events ("Inicio del Proyecto Isabela") have no article of their own
        (P2e rounds 9b, 10b, 11a). The year comes from the English article of
        the event's subject, and only from a sentence with a year and the
        event's verb in English ("muerte" → died, "inicio" → began/initiated):
        an article full of years must not answer with the wrong one.

        The subject is the phrase after "del/de la…" ("cucuve de Floreana",
        "lobo peletero de Galápagos"), found through this language's search and
        its English interlanguage link; failing that, the item's proper names.
        The first qualifying sentence in article order wins, preferring the
        event word nearest the subject ("protección" over "inicio" in "Inicio
        de la protección legal del lobo…"): the lead states the canonical date,
        later sentences add side events ("brought into action in 1999")."""
        words = _WORD.findall(item)
        groups = [v.split() for w in words for k, v in EN_EVENT.items() if _fold(w).startswith(k)]
        if not groups:
            return None
        events = {e for g in groups for e in g}
        main = set(groups[-1])
        names = [w for i, w in enumerate(words) if i > 0 and len(w) >= 4 and w[:1].isupper()]
        titles = []
        if self.fallback is not None:
            for subject in event_subjects(item):
                title = self.english_title(subject)
                if title and title not in titles:
                    titles.append(title)
        candidates = [(t, True) for t in titles]
        if names:
            candidates.append((" ".join(names), False))
        for query, exact in candidates:
            try:
                page = self.fallback._page(query, None, intro=False)
            except Exception:
                page = None
            if not page:
                continue
            title, text = page
            if not exact and not relevant(" ".join(names), f"{title} {text[:400]}"):
                continue
            text = re.sub(r"\s*={2,}[^=]{1,80}={2,}\s*", " ", text)
            dated = [x for x in _sentences(text) if _YEAR.search(x)]

            def has(sentence: str, stems: set[str]) -> bool:
                return any(_fold(w).startswith(e) for w in _WORD.findall(sentence) for e in stems)
            chosen = next((x for x in dated if has(x, main)), None) or \
                next((x for x in dated if has(x, events)), None)
            if not chosen:
                continue
            hit = self.fallback._hit(item, query, title, chosen if len(chosen) <= 320
                                     else chosen[:320][: chosen[:320].rfind(" ")] + " …")
            hit["fallback"] = self.fallback.lang
            return hit
        return None

    def _around_focus(self, profile: OperationProfile, sentence: str) -> str:
        """A long sentence is cut around its first focus term, so the cut
        does not drop the asked-for fact ("…el mayor animal" without
        "mamífero", P2d dry run)."""
        if len(sentence) <= self.max_chars:
            return sentence
        pos = None
        for m in _WORD.finditer(sentence):
            if _stem(_fold(m.group(0))) in profile.focus:
                pos = m.start()
                break
        if pos is None and profile.wants_year:
            year = _YEAR.search(sentence)
            pos = year.start() if year else None
        if pos is None or pos < self.max_chars - 40:
            return sentence
        start = sentence.rfind(" ", 0, max(0, pos - self.max_chars // 3)) + 1
        return "… " + sentence[start:]

    def passages(self, entity: str, focus: list[str], max_sentences: int = 3,
                 max_chars: int = 800) -> dict[str, Any] | None:
        """P2e (local answers): the whole article of the best match for ``entity``,
        reduced to its first sentence plus the sentences that carry the focus
        terms (e.g. "IUCN", "status"), which often sit outside the intro."""
        page = self._page(entity, None, intro=False)
        if not page or not relevant(entity, f"{page[0]} {page[1][:400]}"):
            return None
        title, text = page
        text = re.sub(r"\s*={2,}[^=]{1,80}={2,}\s*", " ", text)   # "== Status ==" headings
        sentences = _sentences(text)
        if not sentences:
            return None
        want_year = "__year__" in focus
        stems = {_stem(_fold(f)) for f in focus if len(f) >= 3 and f != "__year__"}
        chosen = sentences[:2]           # the lead usually states what the thing is
        if stems or want_year:
            scored = []
            for i, sent in enumerate(sentences[2:], 2):
                words = {_stem(w) for w in (_fold(x) for x in _WORD.findall(sent))}
                score = len(words & stems) + (2 if want_year and _YEAR.search(sent) else 0)
                if score:
                    scored.append((-score, i, sent))
            for _, i, sent in sorted(scored)[: max_sentences - 1]:
                chosen.append(sent)
                # the next sentence often finishes the fact ("In 1994 … Endangered.
                # In 2008 … then in 2017 returned to Endangered status.")
                if i + 1 < len(sentences):
                    chosen.append(sentences[i + 1])
        out = " ".join(dict.fromkeys(chosen))
        if len(out) > max_chars:
            cut = out[:max_chars]
            out = cut[: cut.rfind(" ")] + " …"
        return self._hit(entity, entity, title, out)

    def _hit(self, item: str, query: str, title: str, text: str) -> dict[str, Any]:
        return {"item": item, "query": query, "title": title, "text": text,
                "url": WIKI_PAGE.format(lang=self.lang,
                                        title=urllib.parse.quote(title.replace(" ", "_")))}


def gather(items: dict[int, str], provider: WikipediaEvidence,
           max_items: int = 24, profile: OperationProfile | None = None
           ) -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    """Evidence per item number, and a report of what was asked and used."""
    if profile is not None and profile.translation:
        return {}, {"provider": "wikipedia", "lang": provider.lang, "queried": [],
                    "used": 0, "sources": [], "errors": [],
                    "skipped": "translation batch: its items name nothing",
                    "operation": profile.to_dict()}
    wanted = [(n, t) for n, t in sorted(items.items()) if qualifies(t)][:max_items]
    found: dict[int, dict[str, Any]] = {}
    errors: list[str] = []

    def one(pair):
        n, text = pair
        try:
            return n, provider.lookup(text, profile), None
        except Exception as exc:          # network, timeout, bad JSON
            return n, None, f"{type(exc).__name__}"

    if wanted:
        with ThreadPoolExecutor(max_workers=min(6, len(wanted))) as pool:
            for n, hit, err in pool.map(one, wanted):
                if hit:
                    found[n] = hit
                if err:
                    errors.append(err)
    report = {"provider": "+".join(getattr(provider, "names", ["wikipedia"])),
              "lang": provider.lang,
              "queried": [t for _, t in wanted], "used": len(found),
              "sources": [{"item": h["item"], "title": h["title"], "url": h["url"],
                           "query": h.get("query", h["item"]),
                           "provider": h.get("provider", "wikipedia")}
                          for _, h in sorted(found.items())],
              "errors": sorted(set(errors))}
    if profile is not None:
        report["operation"] = profile.to_dict()
        report["retried"] = sum(1 for h in found.values()
                                if h.get("query", h["item"]) != h["item"])
    return found, report


def render(evidence: dict[int, dict[str, Any]], lang: str) -> str:
    """The block added to a fragment, after its items."""
    if not evidence:
        return ""
    lines = [HEADER.get(lang, HEADER["en"])]
    for n, hit in sorted(evidence.items()):
        lines.append(f"- {hit['item']}: {hit['text']}")
    return "\n".join(lines)


def batch_provider(lang: str, ev_cfg: dict[str, Any]):
    """The batch provider: Wikipedia (with an English fallback for other
    languages) behind Wikidata and the other enabled providers."""
    timeout = float(ev_cfg.get("timeout_s", 4.0))
    max_chars = int(ev_cfg.get("max_chars", 220))
    fallback = None if lang == "en" else WikipediaEvidence(lang="en", timeout_s=timeout,
                                                           max_chars=800)
    wiki = WikipediaEvidence(lang=lang, timeout_s=timeout, max_chars=max_chars,
                             fallback=fallback)
    from .providers import build
    return build(lang, ev_cfg, wiki)


_NUMBERED = re.compile(r"^\s*[\[(]?(\d{1,3})[\]).:]\s+(.+?)\s*$", re.M)


def local_batch(text: str, cfg: dict[str, Any], lang: str
                ) -> tuple[str, dict[str, Any] | None]:
    """P2e: evidence for an enumerated batch answered on this device (too small
    to fragment, or no workers). Same rules as for fragments: only item texts are
    sent. Returns (system block, report)."""
    ev_cfg = cfg.get("evidence") or {}
    items = {int(m.group(1)): m.group(2) for m in _NUMBERED.finditer(text or "")}
    if not ev_cfg.get("enabled") or len(items) < 3:
        return "", None
    lang_ = lang if lang in SUPPORTED_LANGS else "en"
    preamble = _NUMBERED.split(text, maxsplit=1)[0]
    profile = operation_profile(preamble) if ev_cfg.get("operation_aware", True) else None
    found, report = gather(items, batch_provider(lang_, ev_cfg),
                           int(ev_cfg.get("max_items", 24)), profile)
    report["local_batch"] = True
    return render(found, lang_), report

