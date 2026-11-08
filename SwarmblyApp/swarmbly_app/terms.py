"""Search terms as concepts, chosen by the user (3.1).

Choosing search words by translating them failed in every hands-on test: the
local model rendered "endogamia" as "endogamy" (in English, marriage within a
group; the biological term is "inbreeding") and "cucuves" as "quails" or
"cicadas", and regular expressions cannot know either. A word is not a
concept; a concept has labels in every language.

So the search dialog can resolve the words of the query into **concepts**:

* the user's glossary first (local, nothing sent);
* **Wikidata** (``wbsearchentities`` + ``wbgetentities``): language-neutral
  items with labels in the user's language and in English, a description to
  tell homonyms apart ("endogamia": *inbreeding* — mating of related
  individuals — or *endogamy* — marriage within a group), the scientific name
  of a taxon (P225) and the MeSH heading (P486) when there is one;
* **GBIF** vernacular names, for organisms ("cucuve" → *Mimus*).

The user picks one concept per word (or keeps the word); the query is built
from the chosen concepts (English label, scientific name), and the choice can
be saved to the glossary with the Wikidata id, so the next search, in any
language, starts from the concept. Only the single words being resolved are
sent, when the user asks for it, and every request is recorded in the receipt.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.parse
from typing import Any, Callable

from .engine.providers import USER_AGENT, _get

Fetch = Callable[[str, float, str], Any]
WIKIDATA = "https://www.wikidata.org/w/api.php?"
GBIF = "https://api.gbif.org/v1/species/search?"


def _patient(fetch: Fetch, url: str, timeout: float) -> Any:
    """One retry when the service says "too many requests" (HTTP 429), waiting
    what it asks for, at most two seconds. Wikimedia limits shared addresses."""
    try:
        return fetch(url, timeout, USER_AGENT)
    except urllib.error.HTTPError as exc:
        if exc.code != 429:
            raise
        try:
            wait = float(exc.headers.get("Retry-After", "1")) if exc.headers else 1.0
        except ValueError:
            wait = 1.0
        time.sleep(min(max(wait, 0.5), 2.0))
        return fetch(url, timeout, USER_AGENT)


def _reason(exc: Exception) -> str:
    """A short, readable cause for the dialog."""
    if isinstance(exc, urllib.error.HTTPError):
        return "429" if exc.code == 429 else f"HTTP {exc.code}"
    if isinstance(exc, (urllib.error.URLError, TimeoutError, OSError)):
        return "offline"
    return type(exc).__name__


# Creative works and documents are never the concept of a search word
# ("mockingbird": an album, a single, a TV episode; "inbreeding": a book).
_WORKS = frozenset({
    "Q482994", "Q134556", "Q7366", "Q105543609", "Q2188189", "Q21191270", "Q1259759", "Q11424",
    "Q24856", "Q5398426", "Q7725634", "Q571", "Q47461344", "Q13442814", "Q732577", "Q3305213",
    "Q7889", "Q215380", "Q169930", "Q17537576", "Q3331189", "Q1004", "Q87167", "Q49084",
})


def _instances(entity: dict[str, Any]) -> set[str]:
    out = set()
    for c in (entity.get("claims") or {}).get("P31") or []:
        v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if isinstance(v, dict) and v.get("id"):
            out.add(v["id"])
    return out


def _claim(entity: dict[str, Any], prop: str) -> str:
    for c in (entity.get("claims") or {}).get(prop) or []:
        v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if isinstance(v, str):
            return v
    return ""


def wikidata(word: str, lang: str, fetch: Fetch, timeout: float, limit: int = 4) -> list[dict[str, Any]]:
    found = _patient(fetch, WIKIDATA + urllib.parse.urlencode(
        {"action": "wbsearchentities", "search": word, "language": lang, "uselang": lang,
         "type": "item", "limit": str(limit), "format": "json"}), timeout) or {}
    ids = [r["id"] for r in found.get("search") or [] if r.get("id")]
    if not ids:
        return []
    data = _patient(fetch, WIKIDATA + urllib.parse.urlencode(
        {"action": "wbgetentities", "ids": "|".join(ids), "props": "labels|descriptions|claims",
         "languages": "|".join(dict.fromkeys([lang, "en"])), "format": "json"}), timeout) or {}
    out = []
    for qid in ids:
        e = (data.get("entities") or {}).get(qid) or {}
        labels, descs = e.get("labels") or {}, e.get("descriptions") or {}
        en = (labels.get("en") or {}).get("value", "")
        local = (labels.get(lang) or {}).get("value", "")
        if not (en or local) or _instances(e) & _WORKS:
            continue
        out.append({"source": "wikidata", "id": qid, "label_en": en, "label": local or en,
                    "description": (descs.get(lang) or descs.get("en") or {}).get("value", ""),
                    "scientific": _claim(e, "P225"), "mesh": _claim(e, "P486"),
                    "url": f"https://www.wikidata.org/wiki/{qid}"})
    return out


def gbif(word: str, fetch: Fetch, timeout: float, limit: int = 3) -> list[dict[str, Any]]:
    data = _patient(fetch, GBIF + urllib.parse.urlencode(
        {"q": word, "qField": "VERNACULAR", "limit": str(limit * 3)}), timeout) or {}
    out, seen = [], set()
    for r in data.get("results") or []:
        name = r.get("canonicalName") or r.get("scientificName") or ""
        if not name or name in seen:
            continue
        seen.add(name)
        names = [v.get("vernacularName", "") for v in r.get("vernacularNames") or []
                 if word.lower()[:5] in v.get("vernacularName", "").lower()]
        out.append({"source": "gbif", "id": str(r.get("key", "")), "label_en": name,
                    "label": names[0] if names else name, "common_en": _english(r),
                    "description": " · ".join(x for x in (r.get("rank", "").lower(),
                                                          r.get("family", ""), r.get("kingdom", ""))
                                              if x),
                    "scientific": name, "mesh": "",
                    "url": f"https://www.gbif.org/species/{r.get('key', '')}"})
        if len(out) >= limit:
            break
    # several species of one genus for a common name ("cucuve": Mimus parvulus,
    # M. macdonaldi, M. trifasciatus): the genus is offered first
    genera: dict[str, dict[str, Any]] = {}
    for r in data.get("results") or []:
        if r.get("genus") and (r.get("rank") or "").upper() in ("SPECIES", "SUBSPECIES"):
            genera.setdefault(r["genus"], r).setdefault("_n", 0)
            genera[r["genus"]]["_n"] = genera[r["genus"]].get("_n", 0) + 1
    for genus, r in genera.items():
        if r.get("_n", 0) >= 2 and genus not in seen:
            heads = {_english(x).split()[-1].lower() for x in data.get("results") or []
                     if x.get("genus") == genus and _english(x)}
            out.insert(0, {"source": "gbif", "id": str(r.get("genusKey", "")), "label_en": genus,
                           "label": genus, "common_en": heads.pop() if len(heads) == 1 else "",
                           "description": " · ".join(x for x in ("genus", r.get("family", ""),
                                                                 r.get("kingdom", "")) if x),
                           "scientific": genus, "mesh": "",
                           "url": f"https://www.gbif.org/species/{r.get('genusKey', '')}"})
    return out[:limit + 1]


def _english(r: dict[str, Any]) -> str:
    """The English common name GBIF gives for a taxon ("Galapagos Mockingbird")."""
    for v in r.get("vernacularNames") or []:
        if (v.get("language") or "").lower() in ("eng", "en") and v.get("vernacularName"):
            return " ".join(v["vernacularName"].split())
    return ""


def _singulars(word: str) -> list[str]:
    """Singular forms to try when a plural finds nothing ("cucuves" → "cucuve")."""
    w = word.strip()
    if len(w) < 5 or " " in w or not w.lower().endswith("s"):
        return []
    out = [w[:-1]]
    if w.lower().endswith("es") and len(w) > 5:
        out.append(w[:-2])
    return out


def resolve(words: list[str], lang: str = "es", glossary: list[tuple[str, str]] | None = None,
            meta: dict[str, dict[str, list[str]]] | None = None, fetch: Fetch | None = None,
            timeout: float = 6.0, online: bool = True) -> list[dict[str, Any]]:
    """Concept candidates for each word: the glossary's entry, if the word is a
    glossary term or one of its equivalents (then nothing is sent for it), or
    else Wikidata and GBIF when ``online``. Fails closed per source."""
    fetch = fetch or _get
    out = []
    for word in words[:6]:
        word = " ".join(word.split())[:60]
        if not word:
            continue
        cands: list[dict[str, Any]] = []
        errors: list[str] = []
        for term, eq in glossary or []:
            stem = term.lower().rstrip("s")
            names = [stem, *[e.strip().lower().rstrip("s") for e in eq.split(",") if e.strip()]]
            w = word.lower().rstrip("s")
            # the word is the glossary term or one of its equivalents ("Mimus",
            # "mockingbird" after "cucuves = Mimus, mockingbird"): already chosen
            if any(len(n) >= 3 and (w.startswith(n) or n.startswith(w)) for n in names):
                m = (meta or {}).get(term, {})
                cands.append({"source": "glossary", "id": (m.get("wd") or [""])[0], "label": term,
                              "label_en": eq.split(",")[0].strip(), "description": eq,
                              "scientific": "", "mesh": "", "url": ""})
        if online and not any(c["source"] == "glossary" for c in cands):
            found: list[dict[str, Any]] = []
            for form in [word, *_singulars(word)]:
                errors = []
                for name, call in (("wikidata", lambda f=form: wikidata(f, lang, fetch, timeout)),
                                   ("gbif", lambda f=form: gbif(f, fetch, timeout))):
                    try:
                        found += call()
                    except Exception as exc:
                        errors.append(f"{name}: {_reason(exc)}")
                if found:
                    break
            cands += found
        out.append({"word": word, "candidates": cands[:8], "errors": errors})
    return out


def concept_terms(c: dict[str, Any]) -> list[str]:
    """Words a chosen concept contributes to a query: its English label and,
    for a taxon, its scientific name."""
    terms = []
    for t in (c.get("label_en"), c.get("scientific")):
        t = " ".join(str(t or "").split())
        if t and t.lower() not in (x.lower() for x in terms):
            terms.append(t)
    return terms


def glossary_entry(word: str, c: dict[str, Any]) -> dict[str, Any]:
    """The glossary entry that keeps this choice: ``word = English label,
    scientific name, English common name | wd: Q…``. The common name lets the
    model match the user's word to the sources ("cucuve" to "Galápagos
    mockingbirds", which the 7B model rendered as "galgapos de Groenlandia")."""
    eq = [t for t in concept_terms(c) if t.lower() != word.lower()]
    common = " ".join(str(c.get("common_en") or "").split())
    if common and common.lower() not in (x.lower() for x in eq):
        eq.append(common)
    return {"term": word, "equivalents": eq, "definition": c.get("description", "")[:200],
            "wd": c.get("id", "") if c.get("source") == "wikidata" else ""}
