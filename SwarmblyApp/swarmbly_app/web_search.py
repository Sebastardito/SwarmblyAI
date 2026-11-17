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


def relevant(hit: dict[str, Any], terms: list[str],
             groups: dict[str, str] | None = None) -> bool:
    """A result is kept only if it is about the query's concepts.

    ``groups`` maps a word to its concept (from the user's glossary: "Mimus"
    and "mockingbird" are both "cucuve"), so two names of one concept count
    once. A paper needs one concept in its title; an encyclopaedia entry or a
    web page needs two concepts (when the query has two) in its title and
    snippet, a web page at least one in its title. "Mimus inbreeding
    mockingbird" brought "Cooper's hawk", "Everglades National Park" and
    "MockingBird: code translation" (sixth test)."""
    if not terms:
        return True
    groups = groups or {}
    title = _fold(hit.get("title", ""))
    snippet = _fold(hit.get("snippet", ""))

    def stem(t: str) -> str:
        return _fold(t)[:max(4, len(t) - 2)]

    def concept(t: str) -> str:
        f = _fold(t)
        return groups.get(f) or next((g for w, g in groups.items()
                                      if len(w) >= 4 and (f.startswith(w[:max(4, len(w) - 2)])
                                                          or w.startswith(stem(t)))), f)
    in_title = {concept(t) for t in terms if stem(t) in title}
    in_text = {concept(t) for t in terms if stem(t) in f"{title} {snippet}"}
    provider = hit.get("provider", "")
    if provider == "pubmed" or not provider:
        return bool(in_title)
    n = len({concept(t) for t in terms})
    need = 2 if n >= 2 else 1
    if provider.startswith("wikipedia"):
        return len(in_title) >= need or len(in_text) >= need
    # a web page: one concept in its title and enough in its text, or every
    # concept of the query in its title and snippet. A page with a generic
    # title ("Ficha técnica 2025") whose text names the variety and the measure
    # asked about was dropped in 7 of 7 results (sealed bank v3.2)
    return (bool(in_title) and len(in_text) >= need) or len(in_text) >= n


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
    spans = private_spans(question)
    # private words, codes, figures and format words go before the cap, so
    # they do not take the place of the topic
    words = [w for w in rest.split() if len(w) > 2 and _public_word(w, spans)][:6]
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
    return strip_private(" ".join(out), question)[:160].strip()


# ---- what a proposed query must not carry (3.3, sealed bank v3.2) -------------
# A query proposed from the user's words carried a plot name and the words of
# the format request ("… para la Parcela Norte y redacta un informe de unas 200
# palabras"); approved as proposed, the plot name left the computer. The
# proposal keeps the public topic: no private places, people, codes, figures or
# instructions. The user still sees it and may edit it before anything is sent.
_PLACE = re.compile(
    r"^(parcelas?|lotes?|fincas?|predios?|campos?|sectores?|sector|bloques?|canteros?|bancal(?:es)?|"
    r"huertos?|huertas?|invernaderos?|potreros?|cuarteles?|chacras?|terrenos?|camas?|surcos?|"
    r"tratamientos?|r[eé]plicas?|repeticiones|plots?|fields?|lots?|farms?|blocks?|beds?|"
    r"greenhouses?|paddocks?|orchards?|treatments?|replicates?)$", re.I)
_PLACE_TAIL = re.compile(
    r"^(norte|sur|este|oeste|alta|alto|baja|bajo|media|medio|central|nueva|nuevo|vieja|viejo|"
    r"grande|chica|chico|peque[nñ]a|peque[nñ]o|uno|dos|tres|cuatro|cinco|north|south|east|west|"
    r"upper|lower|middle|new|old|big|small|one|two|three|four|five|[ivxl]+)$", re.I)
_PERSON_CUE = re.compile(r"^(dr|dra|ing|lic|sr|sra|srta|prof|mr|mrs|ms|don|do[nñ]a)\.?$", re.I)
_ARTICLE = re.compile(r"^(el|la|los|las|del|de|the|of)$", re.I)
_STOP_SCOPE = re.compile(
    r"^(de|del|con|en|y|o|para|por|sobre|frente|seg[uú]n|que|a|al|with|and|or|for|about|"
    r"against|than|in|on|to|from|of)$", re.I)
_POSSESSIVE = re.compile(r"^(mi|mis|nuestr[oa]s?|tu|tus|su|sus|my|our|your)$", re.I)
_INSTRUCTION = re.compile(
    r"^(escrib\w*|redact\w*|resum\w*|haz|hazlo|hazme|haga|explic\w*|compar\w*|indic\w*|"
    r"señal\w*|senal\w*|menciona\w*|di|dime|da|dame|incluy\w*|añad\w*|anad\w*|agrega\w*|"
    r"responde\w*|cont[eé]sta\w*|calcul\w*|arma|armar|ordena\w*|lista\w*|enumera\w*|"
    r"informe|informes|p[aá]rrafos?|palabras|frases?|oraciones|l[ií]neas|tablas?|columnas?|filas?|"
    r"vi[nñ]etas|apartados?|secci[oó]n|secciones|t[ií]tulos?|formato|extensi[oó]n|resumen|"
    r"correo|carta|mensaje|breve|corto|corta|largo|larga|m[aá]ximo|m[ií]nimo|aproximadamente|"
    r"unas|unos|coincid\w*|cuadra\w*|difier\w*|diferenci\w*|concuerd\w*|fuentes?|p[uú]blicas?|"
    r"documentos?|notas|apuntes|archivos?|seg[uú]n|dicen|dice|publica|publicado|cifras?|datos|"
    r"write|draft|summari[sz]e\w*|summary|explain|compare\w*|list|table|tables|words|sentences?|"
    r"paragraphs?|lines|bullets?|section|sections|format|length|email|letter|short|long|"
    r"maximum|minimum|about|roughly|approximately|match\w*|agree\w*|differ\w*|sources?|public|"
    r"documents?|notes|files?|says?|said|figures?|data|report|reports|"
    # the form of the answer and whom it is for (sealed bank v3.2: "nota" and
    # an audience stayed in a proposed query)
    r"nota|s[ií]ntesis|conclusi[oó]n|conclusiones|introducci[oó]n|borrador|versi[oó]n|texto|respuesta|"
    r"jef[ea]s?|director[ae]?s?|directorio|equipo|comit[eé]|junta|gerente|gerencia|consejo|socios?|"
    r"clientes?|estudiantes|alumn[oa]s|colegas|profesor[ae]?s?|tutor[ae]?s?|evaluador[ae]?s?|"
    r"financiador[ae]?s?|auditor[ae]?s?|note|memo|draft|text|answer|boss|manager|board|committee|"
    r"team|students|colleagues|reviewers?|funders?|frente|comparad[oa]s?|respecto|versus|vs|"
    r"compared|against)$", re.I)


# a name that follows one of these is a public entity ("la variedad Lumbre",
# "la isla Floreana"); any other capitalised name of the question is taken as
# the user's (sealed bank v3.2: the name of the user's site, with no word like
# "parcela" before it, was proposed and sent)
_PUBLIC_NOUN = re.compile(
    r"^(variedad(?:es)?|especies?|subespecies?|g[eé]neros?|familias?|cultivares?|cultivar|razas?|cepas?|"
    r"h[ií]bridos?|enfermedad(?:es)?|plagas?|virus|hongos?|bacterias?|compuestos?|mol[eé]culas?|"
    r"f[aá]rmacos?|genes?|prote[ií]nas?|regi[oó]n|regiones|provincias?|pa[ií]s(?:es)?|ciudad(?:es)?|"
    r"islas?|r[ií]os?|lagos?|volc[aá]n|volcanes|cordilleras?|desiertos?|archipi[eé]lagos?|parques?|"
    r"reservas?|varieties|variety|species|genus|genera|family|cultivars?|breeds?|strains?|hybrids?|"
    r"diseases?|pests?|compounds?|genes?|proteins?|regions?|provinces?|country|countries|city|cities|"
    r"islands?|rivers?|lakes?|volcano(?:es)?|park|reserve)$", re.I)


def private_spans(question: str) -> set[str]:
    """Words of the question that are about the user's own material: a place of
    theirs and its name ("la Parcela Norte", "lote AB7", "Huerto Los Aromos"),
    what follows a possessive up to the next connector ("mis conteos" → conteos),
    a person introduced by a title ("la Dra. Ana Pérez"), codes and figures."""
    tokens = re.findall(r"[\wÁÉÍÓÚÑáéíóúñü'.-]+", question or "")
    tokens = [t.strip(".'") for t in tokens]
    tokens = [t for t in tokens if t]
    out: set[str] = set()
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if _PLACE.match(t):
            out.add(_fold(t))
            j = i + 1
            while j < len(tokens) and j <= i + 4 and (
                    tokens[j][:1].isupper() or any(c.isdigit() for c in tokens[j])
                    or _PLACE_TAIL.match(tokens[j])
                    or (_ARTICLE.match(tokens[j]) and j + 1 < len(tokens) and tokens[j + 1][:1].isupper())):
                if not _ARTICLE.match(tokens[j]):
                    out.add(_fold(tokens[j]))
                j += 1
            i = j
            continue
        if _PERSON_CUE.match(t):
            j = i + 1
            while j < len(tokens) and j <= i + 3 and tokens[j][:1].isupper():
                out.add(_fold(tokens[j]))
                j += 1
            i = j
            continue
        if _POSSESSIVE.match(t):
            j = i + 1
            while j < len(tokens) and j <= i + 3 and not _STOP_SCOPE.match(tokens[j]):
                out.add(_fold(tokens[j]))
                j += 1
            i = j
            continue
        if any(c.isdigit() for c in t):
            out.add(_fold(t))
        i += 1
    # capitalised names: public only after a public noun (and the names that
    # follow it) or as a scientific name; the first word of a sentence is not
    # a name
    from .local_context import binomials
    latin = {_fold(w) for b in binomials(question or "") for w in b.split()}
    latin |= {_fold(m) for m in re.findall(r"\b[A-Z][a-z]{3,}(?:idae|inae|aceae|ales)\b", question or "")}
    raw = re.findall(r"[\wÁÉÍÓÚÑáéíóúñü'.-]+|[.?!¿¡]", question or "")
    public = False
    for j, t in enumerate(raw):
        word = t.strip(".'")
        if not word or not word[0].isalpha():
            public = False
            continue
        if _PUBLIC_NOUN.match(word):
            public = True
            continue
        if word[:1].isupper():
            first = j == 0 or raw[j - 1] in (".", "?", "!", "¿", "¡") or raw[j - 1].endswith(".")
            if not first and not public and _fold(word) not in latin and not _ARTICLE.match(word):
                out.add(_fold(word))
            continue
        if not _ARTICLE.match(word):
            public = False
    return out


def strip_private(query: str, question: str = "", private: list[str] | None = None) -> str:
    """The query without the question's private words, codes, figures and the
    words of a format request; ``private`` adds terms known to be the user's
    (their name, people in their documents)."""
    spans = private_spans(question)
    for term in private or []:
        spans |= {_fold(w) for w in re.findall(r"[\wÁÉÍÓÚÑáéíóúñü-]+", term) if len(w) >= 3}
    return " ".join(w for w in (query or "").split() if _public_word(w, spans))


_VERB = re.compile(
    r"^(es|son|era|eran|fue|fueron|ser|est[aá]|est[aá]n|estaba|estaban|estuvo|hay|hubo|habia|"
    r"ha|han|he|hemos|tiene|tienen|tenia|tuvo|tuvieron|tenemos|tengo|sabe|saben|sabemos|"
    r"puede|pueden|podemos|hace|hacen|hizo|hicimos|dio|dieron|dan|vimos|vi|vio|vieron|"
    r"anot[oó]|anot[eé]|anotamos|cont[oó]|contamos|registr[oó]|registramos|midi[oó]|medimos|"
    r"sali[oó]|salieron|dijo|dicen|qued[oó]|quedaron|obtuvo|obtuvimos|logr[oó]|lleg[oó]|"
    r"is|are|was|were|be|been|has|have|had|did|does|do|can|could|saw|seen|got|get|counted|"
    r"recorded|measured|found)$", re.I)


def _public_word(w: str, spans: set[str]) -> bool:
    f = _fold(w.strip(".,;:()«»\"'"))
    return bool(f) and f not in spans and not any(c.isdigit() for c in f) \
        and not _INSTRUCTION.match(f) and not _VERB.match(f) and not _PERSON_CUE.match(f) \
        and not _NUMBER_WORD.match(f) and not _ARTICLE.match(f)


_NUMBER_WORD = re.compile(
    r"^(uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|veinte|treinta|"
    r"cuarenta|cincuenta|cien|ciento|cientos|doscientas?|doscientos|trescientas?|trescientos|"
    r"cuatrocientas?|quinientas?|mil|one|two|three|four|five|six|seven|eight|nine|ten|twenty|"
    r"fifty|hundred|thousand|primer[oa]?|segund[oa]|tercer[oa]?|first|second|third)$", re.I)


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
           limit: int = 6, fetch: Fetch | None = None,
           groups: dict[str, str] | None = None) -> dict[str, Any]:
    """Search approved by the user. Fails closed per provider. ``groups`` maps
    words to concepts (see :func:`relevant`)."""
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
            kept = [h for h in found if relevant(h, terms, groups)]
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
                kept = [h for h in found if relevant(h, terms, groups)]
                dropped += len(found) - len(kept)
                if kept:
                    hits += kept
                    break
    url = str(ev_cfg.get("searxng_url") or "")
    if "web" in providers and url and _reachable(url):
        try:
            found = _searxng(query, url, lang, fetch, timeout)
            kept = [h for h in found if relevant(h, terms, groups)]
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


_WEB_SNIPPET = 600     # characters of a web result's text kept (300 cut the topic off)


def _searxng(query: str, url: str, lang: str, fetch: Fetch, timeout: float) -> list[dict[str, Any]]:
    data = fetch(url.rstrip("/") + "/search?" + urllib.parse.urlencode(
        {"q": query, "format": "json", "language": lang, "categories": "general,science"}),
        timeout, USER_AGENT) or {}
    return [{"provider": "searxng", "title": r.get("title", ""), "authors": "", "year": "",
             "source": urllib.parse.urlparse(r.get("url", "")).netloc,
             "snippet": (r.get("content") or "")[:_WEB_SNIPPET], "url": r.get("url", "")}
            for r in (data.get("results") or [])[:4] if r.get("url")]


def asked_names(question: str, query: str) -> list[str]:
    """Names the user asked about and approved in the query ("la variedad
    Zafira" → Zafira): capitalised words inside the question that the query
    also has."""
    words = {w.lower() for w in re.findall(r"\w+", query or "")}
    out = []
    for m in re.finditer(r"(?<=[^\W\d_])[\s,;:(«\"']+([A-ZÁÉÍÓÚÑ][\wáéíóúñü-]{3,})", question or ""):
        name = m.group(1)
        if name.lower() in words and name not in out:
            out.append(name)
    return out


def mark_missing(found: dict[str, Any], question: str) -> dict[str, Any]:
    """Each result is told which of the asked names it does not mention. A
    search for "Zafira variedad quinua registro" returned the register's
    entry for another variety, and a 7B model gave that variety's figure as
    Zafira's in 6 of 6 answers (open battery, CO-07)."""
    names = asked_names(question, found.get("query", ""))
    for h in found.get("results") or []:
        text = f"{h.get('title', '')} {h.get('snippet', '')}".lower()
        missing = [n for n in names if n.lower() not in text]
        if missing:
            h["missing"] = missing
    return found


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
        if h.get("missing"):
            names = ", ".join(f"«{n}»" for n in h["missing"])
            lines.append(f"(Este resultado no menciona {names}.)" if lang == "es"
                         else f"(This result does not mention {names}.)")
    if not found.get("results"):
        dropped = int(found.get("dropped_unrelated") or 0)
        if dropped:
            lines.append(f"(sin resultados: se descartaron {dropped} que no trataban del tema de la consulta)"
                         if lang == "es" else
                         f"(no results: {dropped} were left out because they were not about the query's topic)")
        else:
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
