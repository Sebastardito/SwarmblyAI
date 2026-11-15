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
requested length, and two compositions had no citation at all. F1 measured
on the six compositions × 3 gave no gain (passed 5/18 → 3/18, length in range
10/18 → 7/18): the inventory and its check stay because F4 uses them, and the
list for the model has its own setting (``compose.checklist``).

**F2, labels attached by code** (``compose.attach_citations``) and **F4, one
bounded repair** (``compose.repair``) are below. Measured together on the
same cases: F2 brought a citation to 18 of 18 answers and cut the unsupported
sentences from 83 to 52; F4 did not work with the 7B model (it returned the
same text when asked to lengthen and dropped content when asked to shorten)
and stays off.
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


# --- F2: labels attached by code ------------------------------------------------
#
# F1 alone did not move the 7B model (open battery, 15 November 2026, S3 × 3):
# a paragraph comparing germination by site carried every figure and no label
# in all six runs, with or without the requirement list. The figures of a
# sentence can be found in the passages by code: when every figure in an
# unlabelled sentence appears in one passage (or two passages, each giving
# part of them), the passage's label is added and the addition is recorded
# (``meta.citations_attached``). It certifies where the figures are, not the
# reasoning around them: "AB2 cost less because it yielded more" keeps a
# figure from each report and an invented "because".

_NUMBER = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)*)(\s?%)?")
_OUTSIDE = re.compile(r"^\W*(fuera\s+de\s+tus\s+fuentes|outside\s+your\s+sources)\b", re.I)
_SENT_END = re.compile(r"([.!?]+[*_)\"»]*)\s*$")


def _canon(num: str) -> str:
    """"1.150" and "1,150" (thousands) → "1150"; "2,8" and "2.8" → "2.8"."""
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", num):
        return re.sub(r"[.,]", "", num)
    return num.replace(",", ".")


def _figures(text: str) -> set[str]:
    """The figures of a sentence worth tracing: decimals, percentages and
    numbers of two digits or more (a lone "3" is usually a count or a list
    number)."""
    out = set()
    for m in _NUMBER.finditer(_CITE.sub(" ", text or "")):
        num, pct = m.group(1), bool(m.group(2))
        if len(num) < 2 and not pct:
            continue
        out.add(_canon(num))
    return out


def _fold(text: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", (text or "").lower())
                   if unicodedata.category(c) != "Mn")


def _stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[a-z]{4,}", _fold(_CITE.sub(" ", text or "")))}


def _sentence_spans(line: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for m in re.finditer(r"(?<=[.!?])\s+", line):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(line)))
    return [(a, b) for a, b in spans if b > a]


def _derived(figs: set[str], known: set[str]) -> set[str]:
    """Figures of the sentence that are the difference or the sum of two other
    figures in it that the passages give ("1.150 … 1.080 … una diferencia de
    70"): computed from sourced figures, so they need no passage of their own."""
    def num(x: str) -> float | None:
        try:
            return float(x)
        except ValueError:
            return None
    given = [v for v in (num(x) for x in figs & known) if v is not None]
    out = set()
    for f in figs - known:
        v = num(f)
        if v is None:
            continue
        if any(abs(abs(a - b) - v) < 0.006 or abs(a + b - v) < 0.006
               for i, a in enumerate(given) for b in given[i + 1:]):
            out.add(f)
    return out


_YEAR = re.compile(r"(?:19|20)\d\d")


def _first(sentence: str, figs: set[str]) -> int:
    """Where the first of these figures appears in the sentence (to give two
    labels in the order of the figures: "AB1 87 %, AB2 90 %" → AB1's first)."""
    for m in _NUMBER.finditer(sentence):
        if _canon(m.group(1)) in figs:
            return m.start()
    return len(sentence)


def _labels_for(sentence: str, passages: list[tuple[str, str, set[str], set[str]]]) -> list[str]:
    figs = _figures(sentence)
    known: set[str] = set()
    for _, _, fg, _ in passages:
        known |= fg
    figs -= _derived(figs, known)
    words = _stems(sentence)
    if not words:
        return []

    def overlap(st: set[str]) -> float:
        return len(words & st) / len(words)

    if figs and all(_YEAR.fullmatch(f) for f in figs):
        # only years ("la temporada 2025-2026"): they are in many paragraphs, so
        # they count only with half of the sentence's words in the same one
        full = [(overlap(st), lab) for lab, _, fg, st in passages if figs <= fg]
        full = sorted(x for x in full if x[0] >= 0.5)
        return [full[-1][1]] if full else []
    if figs:
        full = [(overlap(st), lab) for lab, _, fg, st in passages if figs <= fg]
        full = [x for x in full if x[0] >= 0.3]
        if full:
            return [max(full)[1]]
        best: tuple[float, list[str]] | None = None
        for i, (la, _, fa, sa) in enumerate(passages):
            for lb, _, fb, sb in passages[i + 1:]:
                if la == lb or not (figs <= (fa | fb)) or not (figs & fa) or not (figs & fb):
                    continue
                score = len(words & (sa | sb)) / len(words)
                if score >= 0.3 and (best is None or score > best[0]):
                    best = (score, [la, lb] if _first(sentence, fa - fb) <= _first(sentence, fb - fa)
                            else [lb, la])
        return best[1] if best else []
    scored = sorted(((overlap(st), lab) for lab, _, _, st in passages), reverse=True)
    if scored and scored[0][0] >= 0.6 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        return [scored[0][1]]
    return []


def attach_citations(answer: str, sources: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Adds the label of the passage that holds an unlabelled sentence's
    figures (or most of its words). Tables, headings, questions and anything
    under "Fuera de tus fuentes:" are left alone."""
    passages = [(" ".join(str(s.get("label", "")).split()), str(s.get("text", "")),
                 _figures(str(s.get("text", ""))), _stems(str(s.get("text", ""))))
                for s in sources if s.get("label")]
    if not passages or not answer:
        return answer, []
    attached: list[dict[str, Any]] = []
    # "(D1 p4)" written by the model is the same label in the wrong brackets
    for m in re.finditer(r"\((D\d+\s*p\d+)\)", answer):
        attached.append({"sentence": m.group(0), "labels": [], "by": "format"})
    answer = re.sub(r"\((D\d+\s*p\d+)\)", r"[\1]", answer)
    out_paras = []
    for para in re.split(r"(\n\s*\n)", answer):
        if not para.strip():
            out_paras.append(para)
            continue
        outside = False
        lines = []
        for line in para.split("\n"):
            if _OUTSIDE.search(line):
                outside = True
            stripped = line.lstrip()
            if outside or stripped.startswith(("|", "#", ">")):
                lines.append(line)
                continue
            pieces, cursor = [], 0
            for a, b in _sentence_spans(line):
                sentence = line[a:b]
                pieces.append(line[cursor:a])
                cursor = b
                # a label right after the full stop belongs to this sentence
                # ("…(administración). [D1 p2]", open battery, F2 run)
                labelled_after = bool(re.match(_CITE, line[b:].lstrip()))
                if (len(sentence.split()) < 6 or _CITE.search(sentence) or labelled_after
                        or sentence.rstrip("*_ ").endswith("?")):
                    pieces.append(sentence)
                    continue
                labels = _labels_for(sentence, passages)
                if not labels:
                    pieces.append(sentence)
                    continue
                tag = " " + "".join(f"[{x}]" for x in labels)
                m = _SENT_END.search(sentence)
                new = sentence[:m.start()].rstrip() + tag + m.group(1) if m else sentence.rstrip() + tag
                pieces.append(new)
                attached.append({"sentence": sentence.strip()[:200], "labels": labels,
                                 "by": "figures" if _figures(sentence) else "words"})
            pieces.append(line[cursor:])
            lines.append("".join(pieces))
        out_paras.append("\n".join(lines))
    return "".join(out_paras), attached


# --- F4: one bounded repair -------------------------------------------------------
#
# The length the request asked for was missed in 8 of 18 compositions with F0
# and 11 of 18 with the requirement list (the 7B model wrote 73–79 words for
# "un párrafo de 150 a 200 palabras" every time). When the code's check finds
# the length out of range, the model gets its own text back once, with the
# count and the range; the new text is kept only if it lands closer to the
# range and brings no figure that is neither in the draft nor in the sources.

def needs_repair(chk: dict[str, Any]) -> str:
    length = chk.get("length") or {}
    if length and not length.get("ok"):
        return "length"
    return ""


def repair_message(chk: dict[str, Any], lang: str = "es") -> str:
    low, high = chk["length"]["want"]
    got = chk["length"]["got"]
    es = lang == "es"
    if got < low:
        return (f"Tu texto tiene {got} palabras y se pidieron entre {low} y {high}. Reescríbelo completo con "
                f"entre {low} y {high} palabras: desarrolla los datos de los párrafos de las fuentes que ya usas "
                "o que la solicitud pide (cada uno con su etiqueta), sin añadir nada que no esté en ellos. "
                "Devuelve solo el texto nuevo." if es else
                f"Your text has {got} words and {low} to {high} were asked for. Rewrite it in full with "
                f"{low} to {high} words: develop the facts from the source paragraphs that you use or that the "
                "request asks for (each with its label), adding nothing that is not in them. Return only the "
                "new text.")
    return (f"Tu texto tiene {got} palabras y se pidieron entre {low} y {high}. Reescríbelo completo con "
            f"entre {low} y {high} palabras: quita lo que no responde a la solicitud y conserva cada dato con "
            "su etiqueta. Devuelve solo el texto nuevo." if es else
            f"Your text has {got} words and {low} to {high} were asked for. Rewrite it in full with {low} to "
            f"{high} words: remove what does not answer the request and keep every fact with its label. "
            "Return only the new text.")


def _distance(chk: dict[str, Any]) -> int:
    length = chk.get("length") or {}
    if not length:
        return 0
    low, high = length["want"]
    got = length["got"]
    return max(0, low - got, got - high)


def accept_repair(draft: str, repaired: str, inv: dict[str, Any], passages: list[str]) -> tuple[bool, str]:
    """Keep the repaired text only if it is closer to the requested length,
    keeps the table and the entities it had, and brings no new figure that is
    not in the sources."""
    if not (repaired or "").strip():
        return False, "empty"
    before, after = check(draft, inv), check(repaired, inv)
    if _distance(after) >= _distance(before):
        return False, "not closer to the requested length"
    if (before.get("table") or {}).get("ok") and not (after.get("table") or {}).get("ok"):
        return False, "lost the table"
    missing_before = len((before.get("entities") or {}).get("missing") or [])
    if len((after.get("entities") or {}).get("missing") or []) > missing_before:
        return False, "lost an entity"
    known = _figures(draft)
    for p in passages:
        known |= _figures(p)
    new = sorted(_figures(repaired) - known)
    if new:
        return False, "new figures not in the sources: " + ", ".join(new[:5])
    return True, ""
