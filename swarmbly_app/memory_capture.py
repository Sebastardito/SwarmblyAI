"""What the user asks to remember, and terms worth a glossary entry (3.1).

The model cannot write memory, and must not say it did: in the first
project tests it answered "memorizo…" while nothing was saved. Here the app
itself notices two things in the user's message:

* an explicit request to remember or to add to the glossary, anywhere in
  the message ("…, memorízalo", "agrégalo a tu glosario");
* a definition or a correction the user gives ("X significa Y", "X, también
  conocidos como Y", "X no es Y, sino Z"), which is a glossary candidate even
  if nothing was asked.

The local model turns the message into short notes and glossary entries;
the user sees them under the answer and confirms, edits or discards them.
Nothing is written without that yes (except a message that *starts* with
"Recuerda:", which is saved at once). Everything stays on this computer.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

_REMEMBER = re.compile(
    r"\b(memor[ií]za(?:lo|la|los|las)?|memorice|memoriza\w*|recu[eé]rda(?:lo|la|los|las)?\s+"
    r"(?:esto|eso|que)|recuerde\s+que|gu[aá]rda(?:lo|la)?\s+en\s+(?:la\s+|tu\s+)?memoria|"
    r"actualiza\s+(?:tu|la)\s+memoria|apr[eé]nde(?:te)?(?:lo|la)?|"
    r"(?:agr[eé]ga|a[nñ]ade|incluye|pon)(?:lo|la|los|las)?\s+(?:esto\s+)?(?:a|en|al)\s+"
    r"(?:tu|la|el)\s+(?:memoria|glosario)|"
    r"remember\s+(?:this|that|it)|memori[sz]e|add\s+(?:it|this|that)\s+to\s+(?:your|the)\s+"
    r"(?:memory|glossary)|update\s+(?:your|the)\s+memory|lembre-se|memorize)\b", re.I)
_GLOSSARY_WORD = re.compile(r"\b(glosario|glossary|gloss[aá]rio)\b", re.I)
_DEFINITION = re.compile(
    r"(\b[\wÁÉÍÓÚÑáéíóúñ-]{2,40}\b[^.?!\n]{0,40}?\s+(?:significa|quiere decir|se refiere a|"
    r"(?:tambi[eé]n\s+)?(?:conocid[oa]s?|llamad[oa]s?)\s+como|stands for|means|"
    r"also known as|no (?:es|son) [^.?!\n]{2,60}?,?\s*sino)\b)", re.I)
_ACRONYM_DEF = re.compile(r"\b([A-Z]{2,6})\s*(?:=|:|\(|significa|means|stands for)\s*"
                          r"([A-Z][\w ]{3,60})")


def remember_intent(text: str) -> bool:
    """An explicit request to remember or to add to memory or the glossary."""
    return bool(_REMEMBER.search(text or ""))


def glossary_intent(text: str) -> bool:
    return bool(_GLOSSARY_WORD.search(text or ""))


def definition_hint(text: str) -> bool:
    """The user defines or corrects a term (a glossary candidate)."""
    return bool(_DEFINITION.search(text or "") or _ACRONYM_DEF.search(text or ""))


def needs_capture(text: str) -> bool:
    return remember_intent(text) or glossary_intent(text) or definition_hint(text)


EXTRACT_SYSTEM = (
    "You turn one message of a user into memory for a local assistant. Reply with JSON only: "
    '{"notes": ["..."], "glossary": [{"term": "...", "equivalents": ["..."], '
    '"definition": "..."}]}. '
    "notes: short facts the user states or asks to remember, in the user's language, each one "
    "self-contained (who/what), without questions or requests. glossary: terms the user "
    "defines, corrects or asks to add: the term, its synonyms or translations or scientific "
    "names (equivalents), and a one-line definition taken only from the user's words. "
    "Never add facts the user did not state. Empty lists if there is nothing.")


def _clean_list(value: Any, limit: int = 6, size: int = 400) -> list[str]:
    out = []
    for v in value or []:
        s = " ".join(str(v).split())[:size]
        if s and s not in out:
            out.append(s)
    return out[:limit]


def parse_extraction(raw: str) -> dict[str, Any]:
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        return {"notes": [], "glossary": []}
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return {"notes": [], "glossary": []}
    entries = []
    for g in (data.get("glossary") or [])[:6]:
        if not isinstance(g, dict):
            continue
        term = " ".join(str(g.get("term", "")).split())[:80]
        if not term or "=" in term:
            continue
        eq = [e.replace("=", " ").strip() for e in _clean_list(g.get("equivalents"), 8, 80)]
        entries.append({"term": term, "equivalents": [e for e in eq if e and e != term],
                        "definition": " ".join(str(g.get("definition", "")).split())[:300]})
    return {"notes": _clean_list(data.get("notes")), "glossary": entries}


def propose(text: str, backend: Any = None, model: str = "") -> dict[str, Any]:
    """Proposals for this message: notes and glossary entries, for the user
    to confirm. Without a model (or if it fails), the message itself is the
    note when the user asked to remember."""
    extracted: dict[str, Any] = {"notes": [], "glossary": []}
    if backend is not None and model:
        try:
            result = backend.stream_chat(
                [{"role": "system", "content": EXTRACT_SYSTEM},
                 {"role": "user", "content": text.strip()[:2000]}],
                model=model, max_tokens=400, temperature=0.0)
            extracted = parse_extraction(getattr(result, "text", "") or "")
        except Exception:
            pass
    if not extracted["notes"] and not extracted["glossary"] and remember_intent(text):
        extracted["notes"] = [" ".join(text.split())[:600]]
    for m in _ACRONYM_DEF.finditer(text or ""):
        term, meaning = m.group(1), m.group(2).strip()
        if not any(g["term"] == term for g in extracted["glossary"]):
            extracted["glossary"].append({"term": term, "equivalents": [meaning],
                                          "definition": ""})
    return {"id": uuid.uuid4().hex[:12], "status": "proposed",
            "asked": remember_intent(text) or glossary_intent(text), **extracted}


def glossary_line(entry: dict[str, Any]) -> str:
    """``term = eq1, eq2`` (the format C1 reads; equivalents widen the search)."""
    eq = [e for e in entry.get("equivalents") or [] if e]
    return f"{entry['term']} = {', '.join(eq)}" if eq else ""


MODEL_NOTE = {
    "es": ("El usuario pidió guardar algo en la memoria o el glosario. Tú no puedes guardar "
           "nada: la app le muestra debajo de tu respuesta una propuesta para que la confirme. "
           "No digas que lo memorizaste ni que lo agregaste; di que puede confirmarlo con "
           "«Guardar en memoria»."),
    "en": ("The user asked to save something to memory or the glossary. You cannot save "
           "anything: the app shows the user a proposal under your answer to confirm. Do not "
           "say you memorised or added it; say they can confirm it with \"Save to memory\"."),
}
