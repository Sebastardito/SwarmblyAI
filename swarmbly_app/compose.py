"""Grounded composition, step by step (3.2).

F0 is 3.1: the sources, a citation reminder and the requested length.
Each later step is behind its own setting (``compose.*``, off by default) and
is kept only if the open development battery (``bench/dev``) shows it helps.

**F1, the requirement inventory** (``compose.inventory``). A composition
request is read by code into a short list of what the answer must contain:
its length, a table, a number of items ("las tres recomendaciones"), the
entities it must cover ("AB1 y AB2 en los tres sitios" → the two lots and
the three sites named in the user's documents), and a citation for every
fact. The list goes to the model next to the question, and the answer is
checked against it by code (``meta.requirements``), which later steps use.

In the F0 run of the open battery (15 November 2026) a note asked for "the
three main recommendations" and got two from the sources and one invented
("aunque no se menciona directamente en las fuentes"), while the third one
in the minutes was left out; paragraphs came out at half or double the
requested length, and two compositions had no citation at all.
"""

from __future__ import annotations

import re
from typing import Any

_COMPOSE_VERB = re.compile(
    r"\b(escrib\w*|redact\w*|prepar\w*|resum\w*|compar\w*|elabor\w*|haz\b|hace\b|arm\w*|"
    r"desarroll\w*|explic\w*\s+en\s+(un|una|unos|unas)|write|draft|prepare|summari[sz]e|compare)\b", re.I)
_NUMBERS = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
            "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "two": 2, "three": 3, "four": 4,
            "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_NUM = r"(\d{1,2}|un|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|two|three|four|five|six|seven|eight|nine|ten)"
_ITEMS = re.compile(_NUM + r"\s+(?:\w+\s+)?(recomendaciones|puntos|razones|ideas|pasos|acciones|conclusiones|"
                    r"preguntas|riesgos|ventajas|desventajas|lecciones|decisiones|propuestas|hallazgos|"
                    r"recommendations|points|reasons|steps|actions|conclusions|risks|lessons|decisions|findings)\b",
                    re.I)
_GROUP = re.compile(r"\b(?:los|las|the)?\s*" + _NUM + r"\s+(sitios|lotes|parcelas|islas|especies|"
                    r"documentos|informes|poblaciones|variedades|sites|lots|plots|islands|species|populations)\b",
                    re.I)
_EACH = re.compile(r"\b(?:cada|todos los|todas las|each|every|all the)\s+(sitio|lote|parcela|isla|especie|"
                   r"poblaci[oó]n|variedad|site|lot|plot|island|species|population)(?:s|es)?\b", re.I)
_CODE = re.compile(r"\b[A-Z]{1,4}-?\d{1,4}\b")
_PROPER = re.compile(r"\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+(?:de\s+|del\s+)?[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+)\b")
_NOT_ENTITY = {"Escribe", "Redacta", "Prepara", "Haz", "Incluye", "Cita", "Resume", "Compara"}
_TABLE = re.compile(r"\b(tabla|cuadro|table)\b", re.I)
_AUDIENCE = re.compile(r"\bpara\s+(el|la|los|las)\s+([\wáéíóúñ ]{3,40}?)(?=[:,.;]|\s+con\b|\s+que\b|$)", re.I)
_ITEM_LINE = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+\S", re.M)
_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}", re.M)
_CITE = re.compile(r"\[(?:D\d+\s*p\d+|W\d+)(?:[^\]]{0,40})\]")


def is_composition(text: str) -> bool:
    """A request for a written piece (a report, a summary, a note, a table),
    not a question: a composing verb and a stated length, a table or a count
    of items."""
    from .engine.contract import requested_words
    t = text or ""
    if not _COMPOSE_VERB.search(t):
        return False
    return bool(requested_words(t) or _TABLE.search(t) or _ITEMS.search(t)
                or re.search(r"\b(informe|resumen|nota|texto|p[aá]rrafo|ensayo|carta|report|summary|note)\b", t, re.I))


def _number(word: str) -> int:
    return int(word) if word.isdigit() else _NUMBERS.get(word.lower(), 0)


def _enumeration(passages: list[str], noun: str, n: int) -> list[str]:
    """Names the user's documents list for a group the request mentions:
    "los tres sitios" → "Parcela Norte, Parcela Sur y Ladera Este"."""
    name = r"[A-ZÁÉÍÓÚÑ][\wáéíóúñ]*(?:\s+[A-ZÁÉÍÓÚÑ0-9][\wáéíóúñ]*)*"
    pattern = re.compile(rf"({name}(?:,\s*{name})*\s+(?:y|and|e)\s+{name})")
    stem = noun.lower()[:5]
    for text in passages:
        for sentence in re.split(r"(?<=[.;])\s+", text or ""):
            if stem not in sentence.lower():
                continue
            for m in pattern.finditer(sentence):
                names = [x.strip() for x in re.split(r",\s*|\s+(?:y|and|e)\s+", m.group(1)) if x.strip()]
                if (n and len(names) == n) or (not n and len(names) >= 2):
                    return names
    return []


def inventory(text: str, passages: list[str] | None = None) -> dict[str, Any]:
    """What the request asks for, read by code."""
    from .engine.contract import _RANGE, requested_words
    t = text or ""
    inv: dict[str, Any] = {"words": None, "at_most": False, "table": bool(_TABLE.search(t)),
                           "items": None, "entities": [], "audience": "", "cite": True}
    words = requested_words(t)
    if words:
        m = _RANGE.search(t)
        if m and m.group(3).lower() != "tokens":
            low, high = int(re.sub(r"\D", "", m.group(1))), int(re.sub(r"\D", "", m.group(2)))
        else:
            low, high = int(words * 0.85), int(words * 1.15)
        inv["at_most"] = bool(re.search(r"\b(m[aá]ximo|no m[aá]s de|hasta|at most|no more than)\b", t, re.I))
        inv["words"] = [0, words] if inv["at_most"] else [low, high]
    m = _ITEMS.search(t)
    if m and _number(m.group(1)) > 1:
        inv["items"] = {"n": _number(m.group(1)), "noun": m.group(2).lower()}
    entities: list[str] = []
    for code in _CODE.findall(t):
        if code not in entities:
            entities.append(code)
    for name in _PROPER.findall(t):
        first = name.split()[0]
        if first not in _NOT_ENTITY and name not in entities:
            entities.append(name)
    groups = [(_number(m.group(1)), m.group(2)) for m in _GROUP.finditer(t)]
    groups += [(0, m.group(1)) for m in _EACH.finditer(t)]
    for n, noun in groups:
        for name in _enumeration(passages or [], noun, n):
            if name not in entities:
                entities.append(name)
    inv["entities"] = entities[:12]
    a = _AUDIENCE.search(t)
    if a:
        inv["audience"] = f"{a.group(1)} {a.group(2)}".strip()
    return inv


def checklist(inv: dict[str, Any], lang: str = "es") -> str:
    """The inventory as a short list for the model, placed next to the question."""
    es = lang == "es"
    lines = ["Requisitos de esta solicitud (cúmplelos todos):" if es
             else "Requirements of this request (meet all of them):"]
    if inv.get("words"):
        low, high = inv["words"]
        if inv.get("at_most"):
            lines.append(f"- Extensión: no más de {high} palabras." if es else f"- Length: no more than {high} words.")
        else:
            lines.append(f"- Extensión: entre {low} y {high} palabras; ni más corta ni más larga." if es
                         else f"- Length: between {low} and {high} words; neither shorter nor longer.")
    if inv.get("table"):
        lines.append("- Incluye una tabla con los valores de las fuentes; si calculas una diferencia, muestra también "
                     "los valores de los que sale." if es else
                     "- Include a table with the values from the sources; if you compute a difference, show the "
                     "values it comes from.")
    if inv.get("items"):
        n, noun = inv["items"]["n"], inv["items"]["noun"]
        lines.append(f"- {n} {noun}, numeradas, cada una tomada de las fuentes y con su etiqueta. Si las fuentes "
                     f"no dan {n}, di cuántas dan; no inventes ninguna." if es else
                     f"- {n} {noun}, numbered, each taken from the sources with its label. If the sources do not "
                     f"give {n}, say how many they give; do not invent any.")
    if inv.get("entities"):
        names = ", ".join(inv["entities"])
        lines.append(f"- Cubre cada uno de estos: {names}." if es else f"- Cover each of these: {names}.")
    if inv.get("audience"):
        lines.append(f"- Escribe para {inv['audience']}." if es else f"- Write for {inv['audience']}.")
    lines.append("- Cada dato lleva su etiqueta, por ejemplo [D1 p3], en la misma frase; lo que no esté en las "
                 "fuentes no se escribe como si lo estuviera." if es else
                 "- Every fact carries its label, for example [D1 p3], in the same sentence; what is not in the "
                 "sources is not written as if it were.")
    return "\n".join(lines)


def check(answer: str, inv: dict[str, Any]) -> dict[str, Any]:
    """Which requirements the answer meets, by code."""
    text = answer or ""
    plain = _CITE.sub(" ", text)
    plain = re.sub(r"^\s*\|?[\s:|-]+\|?\s*$", " ", plain, flags=re.M).replace("|", " ")
    n_words = len(re.findall(r"[0-9A-Za-zÁÉÍÓÚÑÜáéíóúñü][\wÁÉÍÓÚÑÜáéíóúñü.,%'-]*", plain))
    out: dict[str, Any] = {}
    if inv.get("words"):
        low, high = inv["words"]
        out["length"] = {"want": [low, high], "got": n_words, "ok": low <= n_words <= high}
    if inv.get("table"):
        out["table"] = {"ok": bool(_TABLE_RULE.search(text))}
    if inv.get("items"):
        got = len(_ITEM_LINE.findall(text))
        out["items"] = {"want": inv["items"]["n"], "got": got, "ok": got == inv["items"]["n"]}
    if inv.get("entities"):
        low_text = text.lower()
        missing = [e for e in inv["entities"] if e.lower() not in low_text]
        out["entities"] = {"missing": missing, "ok": not missing}
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if len(p.split()) >= 12 and not p.lstrip().startswith("|")]
    cited = sum(bool(_CITE.search(p)) for p in paragraphs)
    out["citations"] = {"paragraphs": len(paragraphs), "cited": cited, "ok": cited == len(paragraphs)}
    out["ok"] = all(v.get("ok", True) for v in out.values() if isinstance(v, dict))
    return out
