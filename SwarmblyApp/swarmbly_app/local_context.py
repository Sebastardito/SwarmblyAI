"""Context for answers produced on this device (P2e).

Two optional steps around LCE C1 retrieval, both decided here and run here:

1. **Query expansion** — the local model rewrites the question as search
   keywords in English plus the public entities it names (species, places,
   programmes). Spanish questions then reach English sources (a thesis, papers)
   that plain BM25 never matched. One short generation on the local model;
   nothing leaves the device.
2. **Public evidence for local answers** — when the user enabled public
   evidence, Wikipedia is asked about at most ``evidence.local_max_entities``
   entity names. Only those names are sent: never the question, never a
   passage. Names come from the question (scientific binomials, the entities
   the local model listed) and, as a bridge, from scientific binomials in the
   retrieved passages (species names are public nomenclature, not personal
   data); every name sent is listed in the answer's metadata.

The answer then gets two system blocks: the user's local sources ([1], [2]…)
and the public evidence ([W1], [W2]…), with an instruction to state both when
they differ (a thesis written before a reclassification, for instance).
"""

from __future__ import annotations

import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

BINOMIAL = re.compile(r"\b([A-Z][a-z]{3,})\s([a-z]{4,})\b")
# The fusion template (P2e round 4): local passages and public evidence in the
# user's turn, under explicit labels, with a three-part answer.
FUSION = {
    "es": {"local": "MIS DOCUMENTOS (privados, en este equipo):",
           "none": "(ningún pasaje)",
           "public": "FUENTES PÚBLICAS (Wikidata, Wikipedia, PubMed…, consultadas hoy; solo se enviaron estos nombres: {names}):",
           "question": "PREGUNTA:",
           "ask": ("Responde en tres partes:\n"
                   "1. Mis documentos: qué dicen [1], [2]… sobre la pregunta (si no dicen nada, dilo). "
                   "No cites aquí nada de las fuentes públicas.\n"
                   "2. Fuentes públicas: qué dicen [W1], [W2]… (di de cuál viene cada dato).\n"
                   "3. Comparación: si difieren, da las dos versiones; la de las fuentes públicas es la actual.")},
    "en": {"local": "MY DOCUMENTS (private, on this device):",
           "none": "(no passage)",
           "public": "PUBLIC SOURCES (Wikidata, Wikipedia, PubMed…, fetched today; only these names were sent: {names}):",
           "question": "QUESTION:",
           "ask": ("Answer in three parts:\n"
                   "1. My documents: what [1], [2]… say about the question (say so if nothing). "
                   "Do not cite the public sources here.\n"
                   "2. Public sources: what [W1], [W2]… say (name the source of each fact).\n"
                   "3. Comparison: if they differ, give both versions; the public one is the current one.")},
}


def fusion_prompt(sources: list[dict[str, Any]], hits: list[dict[str, Any]],
                  question: str, lang: str) -> str:
    t = FUSION.get(lang, FUSION["en"])
    lines = [t["local"]]
    lines += [f"[{i}] ({s['source']}) {s['text']}" for i, s in enumerate(sources, 1)] or [t["none"]]
    lines += ["", t["public"].format(names=", ".join(h["sent"] for h in hits))]
    lines += [f"[W{i}] ({h['title']}) {h['text']}" for i, h in enumerate(hits, 1)]
    lines += ["", f"{t['question']} {question.strip()}", "", t["ask"]]
    return "\n".join(lines)
# Latin epithets end like these; "Goat eradication" or "Según tu" do not.
_LATIN_END = re.compile(r"(?:us|um|a|ae|is|i|ii|ei|er|ix|ax|ex|ensis|oides|otis|atus|ata|ens|ans)$")
# Capitalised words that start a binomial-looking pair but are not genera.
_NOT_GENUS = frozenset("""Para Como Cual Cuando Donde Desde Hasta Entre Sobre Segun Según Mientras
Esta Este Estos Estas Esto Aquel Dime Dame Escribe Explica Relaciona Indica Compara Cuantos Cuántos
Que Qué Quien Quién Porque Pero Also After Before During From Into Over Under With Within Without
This That These Those There Their They What When Where Which While Write Explain Compare Tell Give
Since Until Then Than Thus Hence Here Each Every Both Many Most Some Such Only Even""".split())
_NOT_EPITHET = frozenset("""species genus individuals population populations genome genomes support
lineage lineages samples sample clade data results analysis analyses mockingbirds islands island""".split())

EXPAND_SYSTEM = ("You turn a question into English search keywords. Reply with one line "
                 "only, in the format of the example.")
# One worked example: small local models (3B) follow the format far more
# reliably with it than with instructions alone (P2e trial, 24 Oct 2026).
EXPAND_USER = ("Translate the question into English search keywords. Keep scientific names, "
               "place names and numbers. Then, after \" || \", copy the names of species, "
               "places or programmes that the question itself mentions, translated to "
               "English. One line only.\n\n"
               "Question: ¿Qué edad tienen las tortugas gigantes de la isla Santa Cruz según "
               "mi informe de campo?\n"
               "Answer: giant tortoises, age, Santa Cruz Island, field report, Chelonoidis, "
               "Galapagos tortoise || Galapagos giant tortoise; Santa Cruz Island\n\n"
               "Question: {q}\nAnswer:")


@dataclass
class Expansion:
    keywords: str = ""
    entities: list[str] = field(default_factory=list)
    raw: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"keywords": self.keywords, "entities": self.entities,
                **({"error": self.error} if self.error else {})}


def parse_expansion(text: str) -> Expansion:
    text = re.sub(r"(?s)<think>.*?(</think>|$)", " ", text or "")   # reasoning models
    line = " ".join(text.strip().split())
    line = re.sub(r"^(keywords?|format|answer)\s*:\s*", "", line, flags=re.I)
    if "||" in line:
        kw, ents = line.split("||", 1)
    else:
        kw, ents = line, ""
    words = []
    for w in re.split(r"\s*[,;]\s*", kw.strip(" .|")):
        if w and w.lower() not in (x.lower() for x in words):   # small models loop
            words.append(w)
    kw = ", ".join(words)[:400]
    names = []
    for n in re.split(r"[;,\n]" if ";" not in ents else r"[;\n]", ents):
        n = n.strip(" .,'\"*-")
        n = re.sub(r"^(name|names)\s*:\s*", "", n, flags=re.I)
        if 3 <= len(n) <= 60 and n.lower() not in {"none", "n/a", "name"}:
            names.append(n)
    return Expansion(keywords=kw, entities=names[:3], raw=line[:600])


def expand_query(backend: Any, model: str, question: str,
                 timeout_tokens: int = 90) -> Expansion:
    """One short local generation; failures leave the question unexpanded."""
    try:
        result = backend.stream_chat(
            [{"role": "system", "content": EXPAND_SYSTEM},
             {"role": "user", "content": EXPAND_USER.format(q=question.strip()[:800])}],
            model=model, max_tokens=timeout_tokens, temperature=0.0)
        return parse_expansion(getattr(result, "text", "") or "")
    except Exception as exc:          # the answer must not depend on this step
        return Expansion(error=type(exc).__name__)


def binomials(text: str) -> list[str]:
    out = []
    for m in BINOMIAL.finditer(text or ""):
        genus, epithet = m.group(1), m.group(2)
        if genus in _NOT_GENUS or epithet in _NOT_EPITHET or not _LATIN_END.search(epithet):
            continue
        name = f"{genus} {epithet}"
        if name not in out:
            out.append(name)
    return out


def _fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold())
                   if not unicodedata.combining(c))


def _words(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[^\W\d_]{3,}", text or ""):
        f = _fold(w)
        out.add(f[:-1] if f.endswith("s") and len(f) > 4 else f)
    return out


_PUBLIC_ASK = re.compile(
    r"\b(actual(?:es|mente)?|hoy|hoy en d[ií]a|p[uú]blic[oa]s?|p[uú]blicamente|reciente(?:s|mente)?|"
    r"current(?:ly)?|today|now|public(?:ly)?|recent(?:ly)?|atual(?:mente)?|actuel(?:le)?s?|publique|"
    r"internet|en l[ií]nea|online|web|busca(?:r)?|search)\b",
    re.I)


def wants_public(question: str) -> bool:
    """Public evidence is fetched for a local answer only when the question asks
    for something public or current ("estado actual", "según fuentes públicas");
    a question about the user's own documents alone sends nothing."""
    return bool(_PUBLIC_ASK.search(question or ""))


_PROPER = r"((?:[A-ZÁÉÍÓÚÑ][\wáéíóúñ'-]+)(?:\s+(?:de\s+)?[A-ZÁÉÍÓÚÑ][\wáéíóúñ'-]+)*)"


def translated_names(question: str, glossary: list[tuple[str, str]]) -> list[str]:
    """Common names written "<término> de <Lugar>" rendered with the user's
    glossary: "cucuve de Floreana" + "cucuve = mockingbird, Mimus" →
    "Floreana mockingbird"; "lobo peletero de Galápagos" → "Galápagos fur seal"."""
    out: list[str] = []
    for term, equivalents in glossary:
        first = equivalents.split(",")[0].strip()
        if (term[:1].isupper() and not term.isupper() and first
                and re.search(r"\b" + re.escape(term) + r"\b", question)):
            out.append(first)          # a proper name the user listed: "Proyecto Isabela"
            continue
        english = next((e.strip() for e in equivalents.split(",")
                        if e.strip() and e.strip()[0].islower()), "")
        if not english or len(term) < 3:
            continue
        pattern = (r"(?i:\b" + re.escape(term) + r"(?:e?s)?\s+de(?:l|\s+la|\s+las|\s+los)?\s+"
                   r"(?:(?:la\s+)?isla\s+|islote\s+)?)" + _PROPER)   # the place: capitalised
        for m in re.finditer(pattern, question):
            name = f"{m.group(1)} {english}"
            if name not in out:
                out.append(name)
    return out


def public_entities(question: str, expansion: Expansion,
                    sources: list[dict[str, Any]], max_n: int = 3,
                    glossary: list[tuple[str, str]] | None = None) -> list[dict[str, str]]:
    """Names that may be sent to the public provider, with where each came from.

    Only names that cannot carry personal data are sent: scientific names in the
    question, common names of the question rendered through the user's glossary
    ("cucuve de Floreana" → "Floreana mockingbird") and, when the question names
    no species at all, a scientific name repeated in the retrieved passages
    (bridge). Names listed by the local model are not sent: a 3B model offered
    "Galapagos Cuckoo", "Canis" and "Panthera" for these questions (P2e round
    2), and an organisation named in the question (an employer) must not leave.
    """
    picked: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(name: str, origin: str) -> None:
        key = _fold(name)
        if len(picked) >= max_n or key in seen or len(name) < 3:
            return
        seen.add(key)
        picked.append({"name": name, "from": origin})

    for b in binomials(question):
        add(b, "question")
    for t in translated_names(question, glossary or []):
        add(t, "question (glossary)")
    if not picked:
        counts: dict[str, int] = {}
        joined = " ".join(s.get("text", "") for s in sources)
        for b in binomials(joined):
            genus, epithet = b.split(" ", 1)
            counts[b] = joined.count(b) + joined.count(f"{genus[0]}. {epithet}")  # "P. downsi"
        repeated = [b for b, c in sorted(counts.items(), key=lambda x: -x[1]) if c >= 2]
        if repeated:
            add(repeated[0], "local passages (repeated scientific name)")
    return picked


_ASKS_YEAR = re.compile(r"\b(año|años|cu[aá]ndo|fecha|year|when|ano|quand|ann[ée]e)\b", re.I)
YEAR_FOCUS = "__year__"


def focus_terms(expansion: Expansion, entity: str, known: str = "",
                question: str = "") -> list[str]:
    ent = {_fold(w) for w in re.findall(r"\w+", entity)}
    terms = [YEAR_FOCUS] if _ASKS_YEAR.search(question) else []
    for w in re.findall(r"[A-Za-z][A-Za-z-]{3,}", f"{known} {expansion.keywords}"):
        f = _fold(w)
        if f not in ent and f not in terms and f not in {"galapagos", "thesis", "article",
                                                        "paper", "study", "island", "islands"}:
            terms.append(f)
    return terms[:12]


def public_evidence(entities: list[dict[str, str]], expansion: Expansion, provider: Any,
                    known: str = "", question: str = ""
                    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    errors: list[str] = []

    def one(ent):
        try:
            return provider.passages(ent["name"], focus_terms(expansion, ent["name"], known, question)), None
        except Exception as exc:
            return None, type(exc).__name__

    if entities:
        with ThreadPoolExecutor(max_workers=min(3, len(entities))) as pool:
            titles: set[str] = set()
            for ent, (got, err) in zip(entities, pool.map(one, entities)):
                for hit in (got if isinstance(got, list) else [got] if got else []):
                    if hit["title"] in titles:          # two names, one article
                        continue
                    titles.add(hit["title"])
                    hit["sent"] = ent["name"]
                    hit["from"] = ent["from"]
                    hits.append(hit)
                if err:
                    errors.append(err)
    report = {"provider": "+".join(getattr(provider, "names", ["wikipedia"])),
              "lang": getattr(provider, "lang", ""),
              "local_answer": True,
              "queried": [e["name"] for e in entities],
              "queried_from": entities,
              "used": len(hits),
              "sources": [{"item": h["sent"], "title": h["title"], "url": h["url"],
                           "query": h["sent"], "provider": h.get("provider", "wikipedia")}
                          for h in hits],
              "errors": sorted(set(errors))}
    return hits, report


PUBLIC_HEAD = {
    "es": ("Evidencia pública (Wikipedia, consultada ahora; solo se enviaron estos nombres: {names}). "
           "Úsala para los datos públicos y cítala como [W1], [W2]…. Si difiere de las fuentes "
           "locales (por ejemplo, porque cambió con el tiempo), di las dos versiones y cuál es la "
           "más reciente:"),
    "en": ("Public evidence (Wikipedia, fetched now; only these names were sent: {names}). Use it "
           "for public facts and cite it as [W1], [W2]…. If it differs from the local sources (for "
           "instance because it changed over time), give both and say which is more recent:"),
}


def render_public(hits: list[dict[str, Any]], lang: str) -> str:
    if not hits:
        return ""
    names = ", ".join(h["sent"] for h in hits)
    lines = [PUBLIC_HEAD.get(lang, PUBLIC_HEAD["en"]).format(names=names)]
    for i, h in enumerate(hits, 1):
        lines.append(f"[W{i}] ({h['title']}) {h['text']}")
    return "\n".join(lines)
