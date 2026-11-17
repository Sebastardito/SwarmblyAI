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
    num = num.replace(",", ".")
    if re.fullmatch(r"\d+\.\d+", num):          # "2,80" is the "2,8" of the sources
        num = num.rstrip("0").rstrip(".")
    return num


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


# --- F3a: what the text leaves out -------------------------------------------------
#
# Diagnosis of the open battery runs (15 November 2026, all runs so far): of 59
# key data missing from answers, 41 were in the passages the model was given
# and 18 never reached it (the farmers' text got the minutes only, never the
# report with the chlorosis). Omission did not grow with the size of the
# context; facts of the same kind in parallel documents were merged or
# dropped (chlorosis in 15 % of AB1's plants and 22 % of AB2's: one of them
# kept). The code lists the facts of the passages that bear on the request
# and, after the answer, those it does not mention; the app shows them under
# the answer with their labels (``meta.coverage``). Nothing is rewritten.

_INSTRUCTION = {"escri", "redac", "prepa", "elabo", "inclu", "palab", "fuent", "citas", "cita", "dato",
                "datos", "tabla", "texto", "parra", "resum", "ejecu", "unas", "entre", "sobre", "para",
                "segun", "como", "cada", "cifra", "cuatr", "cinco", "siete", "nueve", "three", "four", "afirm", "relac", "compa", "expli", "haz", "write",
                "words", "table", "cite", "sourc", "summa", "inclu", "infor", "nota", "notas"}


_GROUP_STEMS = {"sitio", "lote", "lotes", "parce", "isla", "islas", "espec", "docum", "pobla", "varie", "sites",
                "plots", "speci", "tres", "ambos", "todos", "todas", "enero", "febre", "marzo", "abril", "mayo",
                "junio", "julio", "agost", "septi", "octub", "novie", "dicie",
                # units of measure are not a topic ("por hectárea" in costs and in every density)
                "hecta", "dolar", "tonel", "kilog", "gramo", "metro", "litro", "porce", "unida"}


def _request_stems(text: str) -> set[str]:
    return {s for s in _stems(text) if s not in _INSTRUCTION}


_INSTRUCTION_LIKE = re.compile(
    r"\b(ignor[ae]\w*\s+(?:todas?\s+)?(?:las\s+|tus\s+)?instrucciones|olvida\w*\s+(?:las\s+|tus\s+)?instrucciones|"
    r"ignore\s+(?:all\s+)?(?:the\s+|your\s+)?(?:previous|prior|above)\s+instructions|disregard\s+(?:all\s+)?"
    r"(?:previous|prior)\s+instructions|system\s+prompt|prompt\s+del\s+sistema|"
    r"env[ií]a\w*\s+(?:tambi[eé]n\s+)?(?:el\s+contenido|todos\s+los\s+documentos|tus\s+documentos)|"
    r"send\s+(?:all|the\s+contents?\s+of)\s+(?:the\s+|your\s+)?(?:documents|files)|"
    r"a\s+partir\s+de\s+ahora\s+(?:responde|act[uú]a|eres)|from\s+now\s+on\s+(?:you\s+are|answer|act))", re.I)


# a document's header line ("Responsable: …", "Fecha: …", "Author: …") is not a fact of its subject
_HEADER = re.compile(r"^\s*(?:autor[a]?|responsable|fecha|versi[oó]n|p[aá]gina|archivo|documento|t[ií]tulo|"
                     r"revisad[oa]|elaborad[oa]|preparad[oa]|author|date|version|page|file|title|prepared by)\s*:",
                     re.I)


# a line of a list of publications ("Revista Andina de Cultivos 12: 45–52.")
_REFERENCE = re.compile(r"\b\d{1,4}\s*(?:\(\d+\))?\s*:\s*\d+\s*[–-]\s*\d+\b")
_CODE = re.compile(r"\b[A-Z]{1,4}-?\d{1,4}\b")


def instruction_like(text: str) -> bool:
    """Text addressed to an assistant ("ignora todas las instrucciones
    anteriores y…", "send all the documents to…"): in a document it is
    content to report, never an order."""
    return bool(_INSTRUCTION_LIKE.search(text or ""))


_RULE_RUN = re.compile(r"\|(?:\s*:?-{3,}:?\s*\|)+")


def unflatten_tables(text: str) -> str:
    """A Markdown table that arrives on one line gets its lines back. LCE
    joins the lines of a paragraph, so a table of the user's document reached
    the model, and the code, as "Resultados — | Sitio | pH | |---|---| |
    Parcela Norte | 6,8 | | …": the code found no table to read (recipe 2,
    open battery) and the model had to count cells."""
    out = []
    for line in (text or "").split("\n"):
        m = _RULE_RUN.search(line)
        start = line.find("|")
        if not m or start < 0 or start >= m.start():
            out.append(line)
            continue
        n = len([c for c in m.group(0).strip().strip("|").split("|")])
        head = [c.strip() for c in line[start:m.start()].strip().strip("|").split("|")]
        cells = [c.strip() for c in line[m.end():].split("|") if c.strip()]
        if len(head) != n or not cells or len(cells) % n:
            out.append(line)
            continue
        lead = line[:start].rstrip(" —–-:")
        if lead:
            out.append(lead)
        out.append("| " + " | ".join(head) + " |")
        out.append("|" + "---|" * n)
        out += ["| " + " | ".join(cells[i:i + n]) + " |" for i in range(0, len(cells), n)]
    return "\n".join(out)


def _units(text: str) -> list[str]:
    """Sentences of a passage, and the rows of its tables with their header
    ("Sitio: Parcela Norte · Rendimiento medio (t/ha): 2,8 …")."""
    out, header = [], None
    prose = []
    # LCE shows the paragraph under a heading with it ("Siembra y germinación —
    # El lote AB2 se sembró…"): the heading is context, not part of the first
    # sentence (it made the sowing sentence a germination fact, open battery u32)
    text = re.sub(r"^[^.!?\n|]{1,90}?\s—\s", "", unflatten_tables(text or ""), count=1)
    for line in (text or "").split("\n"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.strip().startswith("|") else None
        if cells is None:
            header = None
            prose.append(line)
            continue
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
            continue
        if header is None:
            header = cells
            continue
        out.append(" · ".join(f"{h}: {c}" for h, c in zip(header, cells) if c))
    for sentence in re.split(r"(?<=[.;])\s+", " ".join(prose)):
        if sentence.strip():
            out.append(sentence.strip())
    return out


def facts(request: str, sources: list[dict[str, Any]], inv: dict[str, Any] | None = None,
          answer: str = "", limit: int = 10, ratio: float = 0.6) -> list[dict[str, Any]]:
    """Facts of the passages that bear on the request: sentences or table rows
    with a figure or one of the request's entities that share a word of its
    topic, best first. A topic word counts more the fewer paragraphs use it
    ("clorosis" is in two, "hectárea" in many), and a fact of the same kind as
    a chosen one (same specific word, with figures) is kept with it: the
    chlorosis of the other lot is the fact the model drops."""
    import math
    entities = [e.lower() for e in (inv or {}).get("entities") or []]
    # the topic: the request's words without its entities and group nouns
    # ("compare la germinación de AB1 y AB2 en cada sitio" → germinación)
    topic = _request_stems(request) - _stems(" ".join(entities)) - _GROUP_STEMS
    # the request's codes ("AB1"): a fact about another one ("el rendimiento
    # medio del lote AB2…", or a row of informe_lote_AB2.md) is not about this
    # request (open battery x33: the notice listed it for a paragraph on AB1)
    asked = {c.replace("-", "") for c in _CODE.findall(request or "")}
    wants_rows = bool((inv or {}).get("table"))
    said = _stems(request or "")
    units: list[tuple[int, str, str, set[str]]] = []
    for order, s in enumerate(sources):
        label = " ".join(str(s.get("label", "")).split())
        # the file's name says what its rows are about ("analisis_suelo_2026.md"
        # for a row "Parcela Sur · Nitrógeno total (%): 0,09")
        file_name = re.sub(r"[_\-.]+", " ", str(s.get("rel") or s.get("source") or ""))
        name = _stems(file_name)
        for unit in _units(str(s.get("text", ""))):
            if not (len(unit.split()) >= 5 and not unit.startswith("#") and not instruction_like(unit)
                    and not _HEADER.match(unit) and not _REFERENCE.search(unit)):
                continue
            about = ({c.replace("-", "") for c in _CODE.findall(unit)}
                     or {c.replace("-", "") for c in _CODE.findall(file_name)})
            if asked and about and not (about & asked):
                continue
            # the rows of a table are its detail: facts of their own when the
            # request asks for a table, names what the rows are ("por sitio")
            # or names the row ("Parcela Sur")
            if " · " in unit and ": " in unit and not wants_rows:
                key_name, _, rest = unit.partition(": ")
                key_value = rest.split(" · ")[0]
                if not (_stems(key_name) & said or _fold(key_value) in _fold(request or "")):
                    continue
            units.append((order, label, unit, name))
    df: dict[str, int] = {}
    for _, _, unit, _ in units:
        for st in _stems(unit) & topic:
            df[st] = df.get(st, 0) + 1
    idf = {st: math.log(1 + len(units) / n) for st, n in df.items()}
    scored: list[tuple[float, int, dict[str, Any]]] = []
    seen: set[str] = set()
    for order, label, unit, name in units:
        key = _fold(unit)[:120]
        if key in seen:
            continue
        figs = {f for f in _figures(unit) if not _YEAR.fullmatch(f)}
        has_entity = any(e in unit.lower() for e in entities)
        own = _stems(unit) & topic
        named = bool(name & topic)
        if not ((figs or has_entity) and (own or (named and figs))):
            continue
        # a table row is a record about its entity: naming the request's
        # entity counts more there ("Parcela Sur, sector oeste · N 0,09 · pH 7,9"
        # in a file called analisis_suelo)
        row = " · " in unit
        score = (sum(idf[st] for st in own)
                 + 0.5 * sum(idf.get(st, 1.0) for st in name & topic)
                 + ((1.0 if row else 0.3) if has_entity else 0))
        seen.add(key)
        scored.append((score, -order, {"text": unit[:240], "label": label, "figures": sorted(figs),
                                       "topic": sorted(own | (name & topic)), "own": sorted(own)}))
    if not scored:
        return []
    top = max(x[0] for x in scored)
    # a word is specific when few paragraphs use it ("clorosis", not "análisis"
    # in a soil report)
    least = min(df.values()) if df else 0
    specific = {st for st, n in df.items() if n <= max(4, 1.5 * least)}
    chosen = [x for x in scored if x[0] >= ratio * top]
    kinds = set().union(*(set(x[2]["own"]) for x in chosen)) & specific
    chosen += [x for x in scored if x not in chosen and x[2]["figures"] and set(x[2]["own"]) & kinds]
    for x in chosen:
        x[2]["keys"] = sorted(set(x[2]["own"]) & specific)
    chosen.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [f for _, _, f in chosen[:limit]]


def uncovered(answer: str, fact_list: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    """The facts the answer does not mention: one with figures is covered when
    at least half of them are in the answer; one without, when most of its
    words are."""
    figs = _figures(answer)
    words = _stems(answer)
    out = []
    for f in fact_list:
        if f["figures"]:
            if len(set(f["figures"]) & figs) * 2 >= len(f["figures"]):
                continue
        else:
            st = _stems(f["text"])
            if st and len(st & words) / len(st) >= 0.6:
                continue
        out.append({"text": f["text"], "label": f["label"]})
    return out[:limit]


# --- F3b: composition by scaffolding --------------------------------------------
#
# The 7B model answers short questions from a few passages without fault (S1
# and S2 at 100 % in every run) and drops facts when it writes a whole piece
# from many (41 of 59 missing key data were in its passages). This is the
# IA-Scaffolding idea of Swarmbly applied on one machine: the code groups the
# facts that bear on the request by topic (the chlorosis of both lots goes
# together), the model writes one short section per group from those facts
# only, and the code assembles them; a table, when asked for, is one more
# short task with the figures. The sections are independent, so a network of
# nodes could write them at the same time.

def plan(request: str, sources: list[dict[str, Any]], inv: dict[str, Any],
         max_sections: int = 4) -> dict[str, Any] | None:
    """Sections of the answer, each with its facts, or None when the code
    finds too few facts to build on (the request is then answered in one go)."""
    listed = facts(request, sources, inv, limit=12, ratio=0.5)
    if len(listed) < 2:
        return None
    # facts that share a specific topic word go in one section (union-find):
    # the chlorosis of both lots, the soil analysis and what was decided on it
    parent = list(range(len(listed)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(len(listed)):
        for j in range(i):
            if set(listed[i].get("keys") or []) & set(listed[j].get("keys") or []):
                parent[root(i)] = root(j)
    groups: dict[int, list[dict[str, Any]]] = {}
    for i, f in enumerate(listed):
        groups.setdefault(root(i), []).append(f)
    ordered = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    sections = [list(v) for _, v in ordered[:max_sections]]
    for _, rest in ordered[max_sections:]:
        for f in rest:              # a small group joins the section it shares most words with
            best = max(range(len(sections)),
                       key=lambda i: len(_stems(f["text"]) & set().union(*(_stems(x["text"]) for x in sections[i]))))
            sections[best].append(f)
    # in the order the request names their topics ("la clorosis … con el
    # análisis de suelo y con las decisiones")
    folded = _fold(request)

    def first_mention(sec: list[dict[str, Any]]) -> int:
        spots = [folded.find(st) for f in sec for st in f.get("topic") or [] if folded.find(st) >= 0]
        return min(spots) if spots else len(folded)
    sections.sort(key=first_mention)
    words = inv.get("words") or [0, 0]
    total = (words[0] + words[1]) // 2 if words[1] else 60 * len(sections)
    if inv.get("table"):
        total = max(40, total - 30)
    return {"sections": [{"facts": sec, "words": max(30, total // len(sections))} for sec in sections],
            "table": bool(inv.get("table"))}


def section_prompt(request: str, section: dict[str, Any], index: int, count: int, lang: str = "es") -> str:
    lines = "\n".join(f"[{f['label']}] {f['text']}" for f in section["facts"])
    if lang == "es":
        place = ("el primer párrafo" if index == 0 else
                 "el último párrafo" if index == count - 1 else f"el párrafo {index + 1}") + f" de {count}"
        return (f"Solicitud del usuario: {request}\n\n"
                f"Escribe solo {place} de ese texto, de unas {section['words']} palabras, con estos datos de sus "
                f"fuentes:\n{lines}\n\n"
                "Usa todas las cifras de esos datos y pon la etiqueta entre corchetes, por ejemplo [D1 p3], en la "
                "misma frase de cada dato. No añadas datos que no estén en la lista, ni títulos, ni saludos. "
                "Devuelve solo el párrafo.")
    place = ("the first paragraph" if index == 0 else
             "the last paragraph" if index == count - 1 else f"paragraph {index + 1}") + f" of {count}"
    return (f"User's request: {request}\n\nWrite only {place} of that text, about {section['words']} words, "
            f"with these facts from their sources:\n{lines}\n\nUse every figure in those facts and put the "
            "label in brackets, for example [D1 p3], in the same sentence as each fact. Add no facts that are "
            "not in the list, no headings, no greetings. Return only the paragraph.")


def table_prompt(request: str, fact_list: list[dict[str, Any]], lang: str = "es") -> str:
    lines = "\n".join(f"[{f['label']}] {f['text']}" for f in fact_list if f["figures"])
    if lang == "es":
        return (f"Solicitud del usuario: {request}\n\nHaz solo la tabla que pide la solicitud, en Markdown, con "
                f"estos datos de sus fuentes:\n{lines}\n\nSi pide una diferencia, calcúlala con esas cifras. "
                "Debajo de la tabla, una línea: «Fuente: » y las etiquetas usadas. Devuelve solo la tabla y esa línea.")
    return (f"User's request: {request}\n\nMake only the table the request asks for, in Markdown, with these "
            f"facts from their sources:\n{lines}\n\nIf it asks for a difference, compute it from those figures. "
            "Under the table, one line: \"Source: \" and the labels used. Return only the table and that line.")


# --- F3c: closing the gaps ---------------------------------------------------------
#
# F3b, measured (S3 × 3, qwen2.5:7b): key data 90/99 → 73/99. Each section saw
# only the facts the code picked, and the picking missed what the whole
# passages held (the second lot's yields, the soil figures); a table task
# without the second lot's rows invented them. The single pass keeps what it
# had; what it drops is a few facts that F3a can name. F3c writes those as one
# short closing paragraph: a task the size of a simple question, the kind the
# model does without fault. In genome terms, closing the gaps between contigs
# rather than re-assembling from fewer reads.

def gap_candidates(answer: str, fact_list: list[dict[str, Any]], limit: int = 3,
                   request: str = "") -> list[dict[str, Any]]:
    """The left-out facts worth a closing paragraph: those of the same kind as
    a fact the answer already gives (a specific topic word in common: the
    other lot's chlorosis), or whose specific word the request itself says
    ("relacione la clorosis observada…": both chlorosis records were left out
    and neither was given, so none was "of the same kind"; open battery,
    r3full), never a loose fact of a cited document. On the sealed banks (3.2
    measurement) the paragraph brought content foreign to the question, once
    in another language and once a document's header."""
    missing = uncovered(answer, fact_list, limit=len(fact_list))
    missing_texts = {m["text"] for m in missing}
    given = [f for f in fact_list if f["text"] not in missing_texts]
    kinds = set().union(*(set(f.get("keys") or []) for f in given)) if given else set()
    kinds |= _request_stems(request) - _GROUP_STEMS if request else set()
    out = [m for m, f in ((m, next(x for x in fact_list if x["text"] == m["text"])) for m in missing)
           if kinds & set(f.get("keys") or [])]
    return out[:limit]


def gap_prompt(request: str, draft: str, gaps: list[dict[str, Any]], lang: str = "es") -> str:
    # the label after the fact: the model copies the line, and "[D4 p11] A
    # mediados…" came back with the label in front (open battery, F3c run)
    lines = "\n".join(f"- {g['text'].rstrip('.;')} [{g['label']}]." for g in gaps)
    words = min(90, 30 * len(gaps))
    if lang == "es":
        return (f"Solicitud del usuario: {request}\n\nTexto ya escrito:\n{draft}\n\n"
                f"Estos datos de sus fuentes tocan la solicitud y el texto no los menciona:\n{lines}\n\n"
                f"Escribe en español un párrafo final de no más de {words} palabras que los incorpore, cada uno "
                "con su etiqueta entre corchetes en la misma frase. No repitas lo que el texto ya dice ni añadas "
                "otros datos. Devuelve solo ese párrafo.")
    return (f"User's request: {request}\n\nText already written:\n{draft}\n\n"
            f"These facts from their sources bear on the request and the text does not mention them:\n{lines}"
            f"\n\nWrite, in English, one closing paragraph of no more than {words} words that brings them in, each with its "
            "label in brackets in the same sentence. Do not repeat what the text says or add other facts. "
            "Return only that paragraph.")


def accept_gap(draft: str, addition: str, gaps: list[dict[str, Any]]) -> tuple[bool, str]:
    """Keep the closing paragraph only if it brings at least one of the facts
    and no figure that is neither in those facts nor in the draft."""
    if not (addition or "").strip():
        return False, "empty"
    if addition.lstrip().startswith("|"):
        return False, "not a paragraph"
    label = re.compile(r"\[([A-Z]\d+\s*p\d+)\]")
    known_labels = {" ".join(g["label"].split()) for g in gaps}
    known_labels |= {" ".join(x.split()) for x in label.findall(draft or "")}
    strange = sorted({" ".join(x.split()) for x in label.findall(addition)} - known_labels)
    if strange:          # "[C2 p11]": a label no passage has
        return False, "unknown labels: " + ", ".join(strange[:3])
    known = _figures(draft)
    gap_figs: set[str] = set()
    for g in gaps:
        gap_figs |= _figures(g["text"])
    known |= gap_figs
    new = sorted(_figures(addition) - known - _derived(_figures(addition), known))
    if new:
        return False, "new figures: " + ", ".join(new[:5])
    brought = _figures(addition) & gap_figs
    if gap_figs and not brought:
        return False, "brings none of the facts"
    return True, ""


# --- Sources that disagree ---------------------------------------------------------
#
# CX-01 of the open battery: the April minutes set the harvest of both lots for
# the second week of June; a later e-mail moves AB2 to the third. Every 7B
# answer gave the e-mail's date and said nothing of the change. The code finds
# sentences of different documents about the same thing (a word of the
# question's topic, the question's entity or "ambos/todos"), each with a date
# or an amount of the same kind, and values that differ; it tells the model,
# and the app shows both under the answer (``meta.conflicts``). Two documents
# about different lots (AB1's report, AB2's report) do not disagree.

_MONTHS = r"(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)"
_WHEN = re.compile(r"\b(?:(?:primera|segunda|tercera|cuarta|[uú]ltima)\s+semana\s+de\s+" + _MONTHS +
                   r"|\d{1,2}\s+de\s+" + _MONTHS + r"|(?:principios|mediados|finales)\s+de\s+" + _MONTHS + r")\b", re.I)
_AMOUNT = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)?)\s?(%|kg(?:\s?N)?(?:/ha)?|t/ha|d[ií]as|d[oó]lares|usd|ha)\b", re.I)
_COLLECTIVE = re.compile(r"\b(ambos|ambas|todos\s+los|todas\s+las|los\s+dos|las\s+dos|both|all\s+the)\b", re.I)
_QUESTION_WORDS = {"cuand", "donde", "quien", "cuale", "cual", "como", "cuant", "hubo", "habra", "sera", "when",
                   "where", "which", "what", "many", "much",
                   # reporting verbs say nothing of what is reported ("se registró")
                   "regis", "obser", "indic", "mostr", "repor", "tuvo", "dice", "segun"}


def _codes(text: str) -> set[str]:
    return {c.upper().replace("-", "") for c in re.findall(r"\b[A-Za-z]{1,4}-?\d{1,4}\b", text or "")
            if not _YEAR.fullmatch(c)}


def _values(sentence: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for m in _WHEN.finditer(sentence):
        out.setdefault("when", set()).add(_fold(" ".join(m.group(0).split())))
    for m in _AMOUNT.finditer(sentence):
        unit = _fold(m.group(2)).replace(" ", "")
        out.setdefault(unit, set()).add(_canon(m.group(1)))
    return out


def conflicts(question: str, sources: list[dict[str, Any]], limit: int = 2) -> list[dict[str, Any]]:
    """Pairs of sentences from different documents that give different dates
    or amounts of the same kind for what the question asks."""
    q_codes = _codes(question)
    q_names = [n.lower() for n in _PROPER.findall(question or "") if n.split()[0] not in _NOT_ENTITY]
    # the topic is what is asked about, not where ("la Parcela Norte") or which lot
    topic = _request_stems(question) - _GROUP_STEMS - _QUESTION_WORDS - _stems(" ".join(q_names))
    if not topic:
        return []
    found: list[tuple[str, str, str, set[str], dict[str, set[str]], bool]] = []
    found_public = {str(s.get("rel") or s.get("source") or ""): bool(s.get("public")) for s in sources}
    for s in sources:
        label = " ".join(str(s.get("label", "")).split())
        rel = str(s.get("rel") or s.get("source") or "")
        public = bool(s.get("public"))
        name_codes = _codes(re.sub(r"[_.]+", " ", rel))
        whole = str(s.get("text", "")).lower()
        for unit in _units(str(s.get("text", ""))):
            if instruction_like(unit) or not (_stems(unit) & topic):
                continue
            low = unit.lower()
            codes = _codes(unit) | name_codes
            about = (bool(q_codes & codes) or any(n in low for n in q_names) or bool(_COLLECTIVE.search(unit))
                     or (not q_codes and not q_names)
                     # a public source speaks in general ("para suelos con
                     # nitrógeno bajo se recomiendan 60 kg N/ha"), not of the
                     # user's plot or lot by name
                     or public)
            # against a public result, a sentence of the paragraph that names
            # the place counts ("El sector oeste de la Parcela Sur tiene
            # nitrógeno bajo… Se recomienda una fertilización nitrogenada de
            # 40 kg N/ha")
            in_paragraph = about or any(n in whole for n in q_names) or bool(q_codes & codes)
            if q_codes and codes and not (q_codes & codes):
                about = in_paragraph = False     # another lot's document
            values = _values(unit)
            if in_paragraph and values:
                found.append((rel, label, unit, codes, values, about))
    out: list[dict[str, Any]] = []
    for i, (ra, la, ua, ca, va, sa) in enumerate(found):
        for rb, lb, ub, cb, vb, sb in found[i + 1:]:
            if ra == rb or (ca and cb and not (ca & cb)):
                continue
            pa, pb = found_public.get(ra), found_public.get(rb)
            if pa and pb:
                continue                     # two public results: not the user's sources against each other
            if not (pa or pb) and not (sa and sb):
                continue                     # two documents: each sentence names what is asked
            shared = _stems(ua) & _stems(ub) & topic
            if not shared:
                continue                     # not about the same thing
            if pa != pb and len(shared) < 2:
                # a public result against a document: the same measure, not only
                # the same word ("rendimiento medio del lote" is not the
                # register's "rendimiento de referencia"; "se recomienda…
                # nitrogenada" is the guide's "se recomiendan… nitrógeno")
                continue
            kinds = [k for k in va if k in vb and va[k] != vb[k]]
            if kinds:
                out.append({"a": {"label": la, "text": ua[:240]}, "b": {"label": lb, "text": ub[:240]},
                            "kind": kinds[0]})
                if len(out) >= limit:
                    return out
    return out


_COMPARE_Q = re.compile(r"\b(compar\w*|diferencia\w*|frente\s+a|versus|vs\.?|contrast\w*|difference)\b", re.I)


def _as_float(text: str) -> float | None:
    try:
        return float(_canon(text))
    except ValueError:
        return None


def _shown(value: float, like: str, lang: str) -> str:
    decimals = len(re.split(r"[.,]", like)[1]) if re.search(r"[.,]\d+$", like) and not re.fullmatch(
        r"\d{1,3}(?:[.,]\d{3})+", like) else 0
    out = f"{value:.{max(decimals, 2 if value < 1 and value else decimals)}f}"
    if "." in out:
        out = out.rstrip("0").rstrip(".")
    return out.replace(".", ",") if lang == "es" else out


# counts of individuals, for comparisons only ("fewer than 60 adults", "unos 45
# adultos"): the notes' figure was given as the public one's (open battery RC-04)
_COUNT = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)?)\s+(adult(?:o|a)?s|individu(?:o|al)s|ejemplares|parejas|pairs|"
                    r"nidos|nests|aves|birds|plantas|plants)\b", re.I)
_COUNT_ES = {"adults": "adultos", "adultas": "adultos", "individuals": "individuos", "pairs": "parejas",
             "nests": "nidos", "birds": "aves", "plants": "plantas"}
_COUNT_EN = {"adultos": "adults", "adultas": "adults", "individuos": "individuals", "parejas": "pairs",
             "nidos": "nests", "aves": "birds", "plantas": "plants"}
_QUALIFIER = re.compile(r"(fewer\s+than|less\s+than|more\s+than|over|under|about|around|approximately|unos|unas|"
                        r"cerca\s+de|menos\s+de|m[aá]s\s+de|alrededor\s+de|aproximadamente)\s*$", re.I)
_BOUND = {"fewer than": ("menos de", "fewer than"), "less than": ("menos de", "fewer than"),
          "under": ("menos de", "fewer than"), "menos de": ("menos de", "fewer than"),
          "more than": ("más de", "more than"), "over": ("más de", "more than"), "más de": ("más de", "more than"),
          "mas de": ("más de", "more than")}
_ABOUT = {"about", "around", "approximately", "unos", "unas", "cerca de", "alrededor de", "aproximadamente"}


def comparisons(question: str, sources: list[dict[str, Any]], lang: str = "es",
                limit: int = 2) -> list[dict[str, Any]]:
    """For a request that asks to compare a figure of the user's documents
    with one of a public result (recipe 3): the two figures, the difference
    and its direction, computed by code. Only when each side gives one value
    of that unit for what is asked. Asked to compare 2,53 t/ha with a
    reference of 2,9 t/ha, a 7B model wrote "superando ligeramente" in 3 of 4
    answers; told the difference and that it is lower, in 0 of 4."""
    if not _COMPARE_Q.search(question or ""):
        return []
    q_codes = _codes(question)
    q_names = [n.lower() for n in _PROPER.findall(question or "") if n.split()[0] not in _NOT_ENTITY]
    topic = _request_stems(question) - _GROUP_STEMS - _QUESTION_WORDS - _stems(" ".join(q_names))
    sides: dict[str, dict[bool, dict[float, tuple[str, str, str, str, str]]]] = {}
    for s in sources:
        public = bool(s.get("public"))
        label = " ".join(str(s.get("label", "")).split())
        rel = str(s.get("rel") or s.get("source") or "")
        name_codes = _codes(re.sub(r"[_.]+", " ", rel))
        whole = str(s.get("text", "")).lower()
        for unit in _units(str(s.get("text", ""))):
            if instruction_like(unit) or not (_stems(unit) & topic):
                continue
            codes = _codes(unit) | name_codes
            if not public:
                if q_codes and not (q_codes & codes):
                    continue                     # another lot's document, or none named
                if q_names and not any(n in whole for n in q_names) and not (q_codes & codes):
                    continue
            years = sorted({y for y in re.findall(r"\b(?:19|20)\d\d\b", unit)})
            year = years[0] if len(years) == 1 else ""
            for rx in (_AMOUNT, _COUNT):
                for m in rx.finditer(unit):
                    value = _as_float(m.group(1))
                    if value is None or (rx is _AMOUNT and _YEAR.fullmatch(m.group(1))):
                        continue
                    shown_unit = m.group(2)
                    if rx is _COUNT:
                        word = _fold(shown_unit)
                        kind = _COUNT_ES.get(word, word)
                        shown_unit = kind if lang == "es" else _COUNT_EN.get(kind, kind)
                    else:
                        kind = _fold(shown_unit).replace(" ", "")
                    q = _QUALIFIER.search(unit[max(0, m.start() - 30):m.start()])
                    qualifier = " ".join(q.group(1).lower().split()) if q else ""
                    sides.setdefault(kind, {}).setdefault(public, {}).setdefault(
                        value, (label, m.group(1), shown_unit, qualifier, year))
    out: list[dict[str, Any]] = []
    for kind, by in sides.items():
        mine, theirs = by.get(False) or {}, by.get(True) or {}
        if len(mine) != 1 or len(theirs) != 1:
            continue                             # nothing to compare, or not one figure on each side
        (a, (la, ta, unit, qa, ya)), = mine.items()
        (b, (lb, tb, _, qb, yb)), = theirs.items()

        def side(label: str, value: str, qualifier: str, year: str) -> dict[str, Any]:
            out_side: dict[str, Any] = {"label": label, "value": value, "unit": unit}
            if qualifier in _BOUND:
                out_side["qualifier"] = _BOUND[qualifier][0 if lang == "es" else 1]
            elif qualifier in _ABOUT:
                out_side["qualifier"] = "unos" if lang == "es" else "about"
            if year:
                out_side["year"] = year
            return out_side
        diff = abs(a - b)
        item = {"a": side(la, ta, qa, ya), "b": side(lb, tb, qb, yb),
                "difference": _shown(diff, ta if len(ta) >= len(tb) else tb, lang),
                "percent": round(100 * diff / b) if b else None,
                "direction": "equal" if diff < 1e-9 else ("lower" if a < b else "higher")}
        if qa in _BOUND or qb in _BOUND:
            # "fewer than 60" against 45: two figures, not a difference
            item.update(difference="", percent=None, direction="bound")
        out.append(item)
        if len(out) >= limit:
            break
    return out


def comparison_block(found: list[dict[str, Any]], lang: str = "es") -> str:
    es = lang == "es"
    lines = ["Cálculo hecho por el programa para la comparación que se pide (las cifras son de las fuentes):"
             if es else "Calculation made by the program for the comparison asked (the figures are the sources'):"]
    def fig(x: dict[str, Any]) -> str:
        text = " ".join(p for p in (x.get("qualifier", ""), x["value"], x["unit"]) if p)
        return text + (f" ({'en ' if es else 'in '}{x['year']})" if x.get("year") else "")
    for c in found:
        a, b = c["a"], c["b"]
        if c["direction"] == "bound":
            lines.append(f"- {fig(a)} [{a['label']}] · {fig(b)} [{b['label']}]")
            continue
        if c["direction"] == "equal":
            lines.append(f"- {a['value']} {a['unit']} [{a['label']}] es igual a {b['value']} {b['unit']} [{b['label']}]."
                         if es else f"- {a['value']} {a['unit']} [{a['label']}] equals {b['value']} {b['unit']} "
                                    f"[{b['label']}].")
            continue
        low = c["direction"] == "lower"
        pct = f" (un {c['percent']} % {'menos' if low else 'más'})" if es and c["percent"] is not None else (
            f" ({c['percent']} % {'less' if low else 'more'})" if c["percent"] is not None else "")
        if es:
            lines.append(f"- {a['value']} {a['unit']} [{a['label']}] es {c['difference']} {a['unit']} "
                         f"{'MENOR' if low else 'MAYOR'} que {b['value']} {b['unit']} [{b['label']}]{pct}.")
        else:
            lines.append(f"- {a['value']} {a['unit']} [{a['label']}] is {c['difference']} {a['unit']} "
                         f"{'LOWER' if low else 'HIGHER'} than {b['value']} {b['unit']} [{b['label']}]{pct}.")
    first = found[0]
    if first["direction"] == "bound":
        lines.append("Da las dos cifras, cada una con su etiqueta y, si la tiene, su año; son dos datos distintos, no "
                     "atribuyas uno a la fuente del otro." if es else
                     "Give both figures, each with its label and, if it has one, its year; they are two different "
                     "data, do not attribute one to the other's source.")
        return "\n".join(lines)
    words = {"lower": ("menor, no superior", "lower, not higher"), "higher": ("mayor, no inferior", "higher, not lower"),
             "equal": ("igual", "equal")}[first["direction"]]
    diff = f"{first['difference']} {first['a']['unit']}"
    # the difference itself, not only the percentage: three answers in five
    # gave "un 13 % menos" and no 0,37 t/ha (open battery rc2)
    lines.append(f"Da la diferencia ({diff}) y usa esta dirección ({words[0]})." if es else
                 f"Give the difference ({diff}) and use this direction ({words[1]}).")
    return "\n".join(lines)


def related(question: str, sources: list[dict[str, Any]]) -> bool:
    """Whether any retrieved passage shares a word of the question (or of its
    search terms): "¿Cuál es la capital de Perú?" got two crop reports whole,
    and the 7B answered that the sources did not say (open battery, OUT-01)."""
    asked = (_request_stems(question) - _QUESTION_WORDS) | {c.lower() for c in _codes(question)}
    if not asked:
        return True
    for s in sources:
        text = str(s.get("text", ""))
        if _stems(text) & asked or {c.lower() for c in _codes(text)} & asked:
            return True
    return False


def conflict_block(found: list[dict[str, Any]], lang: str = "es") -> str:
    es = lang == "es"
    lines = ["Tus fuentes no coinciden en esto:" if es else "Your sources disagree on this:"]
    for c in found:
        lines.append(f"- [{c['a']['label']}] {c['a']['text']}")
        lines.append(f"- [{c['b']['label']}] {c['b']['text']}")
    if any(c[k]["label"].startswith("W") for c in found for k in ("a", "b")):
        # a public source against the user's documents: no "which is later"
        # (the 7B wrote "[D1 p6] es posterior a [W1]", open battery rc2)
        lines.append("Da los dos datos, cada uno con su etiqueta, y di que no coinciden: la fuente pública habla en "
                     "general y los documentos del usuario de su caso. No elijas uno en silencio." if es else
                     "Give both, each with its label, and say they disagree: the public source speaks in general and "
                     "the user's documents of their case. Do not pick one silently.")
    else:
        lines.append("Da los dos datos, cada uno con su etiqueta, y di cuál es posterior si las fuentes lo indican; no "
                     "elijas uno en silencio." if es else
                     "Give both, each with its label, and say which is later if the sources show it; do not pick one "
                     "silently.")
    return "\n".join(lines)
