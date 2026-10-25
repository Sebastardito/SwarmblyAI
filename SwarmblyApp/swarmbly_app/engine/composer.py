"""Composition planner (P1): the local model plans a long text; workers write sections.

A single composition — an essay, a speech, a report of N words — has no
enumerated structure to split, and P0 stopped splitting it by accident. It
does have a structure the request implies: an opening, a few lines of
argument, a closing, sometimes a table. This module makes that structure
explicit *on this device*:

1. **Outline** — the local model reads the whole request and returns a JSON
   outline: title, topic, style line, and 3–6 sections, each with a purpose,
   a word budget, key points, the explicit requirements that belong to it
   ("open with the presenter", "a summary table") and a kind (prose/table).
   The code validates it; if the model's output is not usable, a
   deterministic outline is used instead, and the monitor says so.
2. **Sections** — every section becomes one micro-task. Its packet carries
   Γ (minimised), the title, the topic, its own brief and its position — not
   the request. That is the decontextualisation the SPEC asks for: a worker
   sees one section's brief, never the instruction list, the rubric or the
   other sections' requirements.
3. **Assembly** — sections are joined in order under the title. Workers
   write their own opening transition (the brief asks for one); no bridges
   are generated, because the upstream bridge prompt is English.
4. **Requirement check** — every ``must_include`` of the outline is checked
   against the final text and reported (found / not found). It is a lexical
   check, not a judgement of quality.

The local model never writes the answer here; it only plans. Whether this
beats one local model writing the whole text is an open question that P3.2
measures (preregistered); nothing in this module assumes it does.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

MIN_SECTIONS = 3
MIN_SECTION_WORDS = 60
TABLE_SECTION_WORDS = 120
OUTLINE_MAX_TOKENS = 1400

LANGUAGE_NAMES = {"en": "English", "es": "Spanish", "pt": "Portuguese", "fr": "French"}
_TABLE_CUE = re.compile(r"\b(tablas?|tables?|tabelas?|tableaux?|tabla de resumen)\b", re.I)
_BULLET = re.compile(r"^\s*[-*•]\s+(.+?)\s*$", re.M)
_NUMBER_WORDS = {"dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
                 "ocho": 8, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                 "seven": 7, "eight": 8, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5,
                 "duas": 2, "três": 3, "quatro": 4}
_SECTION_COUNT = re.compile(
    r"\b(\d|" + "|".join(_NUMBER_WORDS) + r")\s+(?:secciones|apartados|partes|"
    r"sections|parts|seções|secções|parties)\b(\s*:)?", re.I)
_OPENING_CUE = re.compile(r"\b(introducci[óo]n|introduction|introdu[çc][ãa]o)\b", re.I)
_CLOSING_CUE = re.compile(r"\b(conclusi[óo]n|conclusion|conclus[ãa]o)\b", re.I)
MAX_REQUESTED_SECTIONS = 8
_LIST_CUE = re.compile(r"\b(listas?|vi[ñn]etas?|enumera\w*|lists?|bullets?|bullet points?|"
                       r"puntos|listes?|puces)\b", re.I)
_FORMAT_WORDS = re.compile(r"\b(tablas?|tables?|tabelas?|tableaux?|listas?|lists?|"
                           r"vi[ñn]etas?|bullets?|bullet points?|numbered|numeradas?|"
                           r"headings?|subheadings?|encabezados?|subt[íi]tulos?)\b", re.I)
_HEADING_LINE = re.compile(r"^\s*(#{1,6}\s+.*|\*\*[^*]{1,120}\*\*\s*:?)\s*$")


@dataclass
class Section:
    heading: str
    purpose: str
    words: int
    key_points: list[str] = field(default_factory=list)
    must_include: list[str] = field(default_factory=list)
    kind: str = "prose"                 # prose | table

    def to_dict(self) -> dict[str, Any]:
        return {"heading": self.heading, "purpose": self.purpose, "words": self.words,
                "key_points": list(self.key_points),
                "must_include": list(self.must_include), "kind": self.kind}


@dataclass
class Outline:
    title: str
    topic: str
    style: str
    sections: list[Section]
    source: str                         # local_model | fallback
    errors: list[str] = field(default_factory=list)
    adjustments: list[str] = field(default_factory=list)
    lists_ok: bool = False              # the request asks for lists or bullets

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "topic": self.topic, "style": self.style,
                "lists_ok": self.lists_ok,
                "source": self.source, "errors": list(self.errors),
                "adjustments": list(self.adjustments),
                "sections": [s.to_dict() for s in self.sections]}


# -- outline -----------------------------------------------------------------------
def requested_sections(prompt: str) -> int | None:
    """The number of prose sections the request asks for, or ``None``.

    "una introducción, tres secciones y una conclusión" → 5: the opening and
    the closing are named apart from the three. "en tres secciones:
    introducción, desarrollo y conclusión" → 3: the colon introduces the
    sections themselves. P3d.2 (22 Oct 2026): the report asked for an
    introduction, three sections and a conclusion and the outline had four.
    """
    match = _SECTION_COUNT.search(prompt or "")
    if not match:
        return None
    word = match.group(1).lower()
    n = int(word) if word.isdigit() else _NUMBER_WORDS.get(word, 0)
    if n < 1:
        return None
    if not match.group(2):
        n += int(bool(_OPENING_CUE.search(prompt))) + int(bool(_CLOSING_CUE.search(prompt)))
    return n if MIN_SECTIONS <= n <= MAX_REQUESTED_SECTIONS else None


def outline_prompt(prompt: str, lang: str, target_words: int, max_sections: int,
                   sections: int | None = None) -> str:
    language = LANGUAGE_NAMES.get(lang, "the language of the request")
    count = (f"- Exactly {sections} sections (a table section, if any, is extra), as "
             f"the request asks; their words add up to about {target_words}.\n"
             if sections else
             f"- {MIN_SECTIONS} to {max_sections} sections; their words add up to about "
             f"{target_words}.\n")
    return (
        "You are planning a long text before it is written. Read the request and "
        "return ONLY a JSON object, with no commentary and no code fence.\n\n"
        f"Request:\n<<<\n{prompt.strip()}\n>>>\n\n"
        f"Return this JSON, with every value written in {language}:\n"
        '{"title": "...", "topic": "short topic phrase", '
        '"style": "one line: register, tone, voice and formatting rules from the request", '
        '"sections": [{"heading": "...", "purpose": "what this section does", '
        '"words": 150, "key_points": ["short phrase", "short phrase"], '
        '"must_include": ["explicit requirement of the request that belongs here"], '
        '"kind": "prose"}]}\n\n'
        "Rules:\n"
        + count +
        "- The first section opens the text; the last section closes it.\n"
        "- Put each explicit requirement of the request (people, how to open, tables, "
        "examples, how to close) in the must_include of the one section where it "
        "belongs.\n"
        '- If the request asks for tables, add a section with "kind": "table".\n'
        "- key_points are short phrases. Do not invent figures or statistics.\n"
    )


def _json_block(raw: str) -> Any:
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.M)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the outline")
    body = text[start:end + 1]
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(re.sub(r",\s*([}\]])", r"\1", body))   # trailing commas
    except json.JSONDecodeError:
        pass
    # Cut at the last complete section object and close the structure: a
    # 3B model's outline was cut mid-section in a live test (2026-10-16).
    cut = body.rfind("},")
    if cut > 0:
        return json.loads(re.sub(r",\s*([}\]])", r"\1", body[:cut + 1] + "]}"))
    raise ValueError("unreadable outline JSON")


def _strings(value: Any, limit: int, max_chars: int = 160) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    out = [" ".join(str(v).split())[:max_chars] for v in value
           if isinstance(v, (str, int, float)) and str(v).strip()]
    return out[:limit]


def _rescale(sections: list[Section], target_words: int) -> None:
    """Prose sections share ``target_words``; table sections keep a fixed size."""
    prose = [s for s in sections if s.kind != "table"]
    if not prose:
        return
    budget = max(MIN_SECTION_WORDS * len(prose),
                 target_words - TABLE_SECTION_WORDS * (len(sections) - len(prose)))
    total = sum(max(1, s.words) for s in prose)
    for s in prose:
        s.words = max(MIN_SECTION_WORDS, round(budget * max(1, s.words) / total))
    for s in sections:
        if s.kind == "table":
            s.words = TABLE_SECTION_WORDS


def parse_outline(raw: str, *, target_words: int, max_sections: int) -> Outline:
    """Validate the local model's outline; raises ``ValueError`` when unusable."""
    data = _json_block(raw)
    if not isinstance(data, dict):
        raise ValueError("the outline is not a JSON object")
    items = data.get("sections")
    if not isinstance(items, list):
        raise ValueError("the outline has no section list")
    sections: list[Section] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        heading = " ".join(str(item.get("heading") or "").split())[:120]
        purpose = " ".join(str(item.get("purpose") or "").split())[:240]
        if not heading:
            continue
        try:
            words = int(float(item.get("words") or 0))
        except (TypeError, ValueError):
            words = 0
        kind = "table" if (str(item.get("kind") or "").lower() == "table"
                           or _TABLE_CUE.search(heading)) else "prose"
        sections.append(Section(heading=heading, purpose=purpose or heading,
                                words=words, key_points=_strings(item.get("key_points"), 5),
                                must_include=_strings(item.get("must_include"), 4),
                                kind=kind))
    seen: set[str] = set()
    unique = []
    for sec in sections:                  # a repeated heading is a repeated section
        key = sec.heading.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(sec)
    sections = unique
    if len(sections) < MIN_SECTIONS:
        raise ValueError(f"the outline has {len(sections)} usable sections "
                         f"(minimum {MIN_SECTIONS})")
    sections = sections[:max_sections]
    if sections[0].kind == "table" or sections[-1].kind == "table":
        prose = [s for s in sections if s.kind != "table"]
        tables = [s for s in sections if s.kind == "table"]
        if len(prose) < 2:
            raise ValueError("the outline has no prose opening and closing")
        sections = prose[:-1] + tables + prose[-1:]   # tables before the closing
    _rescale(sections, target_words)
    return Outline(title=" ".join(str(data.get("title") or "").split())[:160],
                   topic=" ".join(str(data.get("topic") or "").split())[:160],
                   style=" ".join(str(data.get("style") or "").split())[:240],
                   sections=sections, source="local_model")


_STYLE_CUE = re.compile(r"\b(tono|registro|estilo|voz|persona|lenguaje|español|neutro|tone|"
                        r"register|style|voice|plain|formal|informal|tom|estilo|ton|registre)\b",
                        re.I)
_ANGLES = {
    "es": ("contexto e historia", "situación actual, con ejemplos concretos",
           "retos y perspectivas futuras"),
    "en": ("context and history", "the present situation, with concrete examples",
           "challenges and future prospects"),
}
_FALLBACK = {
    "es": ("Introducción", "Presenta el tema y la idea central",
           "Perspectiva {n}", "Desarrolla un argumento con ejemplos concretos, centrado en {a}",
           "Tabla de resumen", "Resume los datos clave en una tabla",
           "Conclusión", "Sintetiza los puntos principales y cierra con una reflexión"),
    "en": ("Introduction", "Present the topic and the central idea",
           "Perspective {n}", "Develop one argument with concrete examples, focused on {a}",
           "Summary table", "Summarise the key facts in a table",
           "Conclusion", "Synthesise the main points and close with a reflection"),
}


_ABOUT = re.compile(r"\b(?:sobre|acerca de|about|on|sur|à propos de)\b\s*:?\s*(.+)$", re.I | re.S)
_LENGTH_PHRASE = re.compile(r"\b(?:de\s+|of\s+)?(?:aproximadamente\s+|about\s+|unas\s+)?\d[\d.,]*\s*"
                            r"(?:words|palabras|palavras|mots)\b", re.I)


def topic_from(objective: str) -> str:
    """The subject of the request, without the whole text's length ("800 words")."""
    text = " ".join((objective or "").split())
    match = _ABOUT.search(text)
    topic = match.group(1) if match else _LENGTH_PHRASE.sub("", text)
    return " ".join(topic.split()).strip(" .:;\"'“”«»")[:160]


def fallback_outline(prompt: str, contract, lang: str, target_words: int,
                     error: str = "") -> Outline:
    """Deterministic outline: opening, three perspectives, optional table, closing.

    The request's closing paragraph (after the last blank line) usually holds
    its delivery requirements ("as a speech opened by …"); it is attached to
    the opening section. Bullet instructions become the style line.
    """
    s = _FALLBACK.get(lang, _FALLBACK["en"])
    angles = _ANGLES.get(lang, _ANGLES["en"])
    # Style = the instruction bullets that speak of tone/register/voice only;
    # structural bullets ("open with…", "include a title") are not sent to
    # every section.
    bullets = [b for b in _BULLET.findall(prompt) if _STYLE_CUE.search(b)][:2]
    tail = (prompt or "").strip().split("\n\n")[-1].strip()
    opening_req, table_req = [], []
    if tail and not tail.lstrip().startswith(("-", "1")):
        for sentence in re.split(r"(?<=[.!?])\s+", " ".join(tail.split())):
            (table_req if _TABLE_CUE.search(sentence) else opening_req).append(sentence[:200])
    sections = [Section(s[0], s[1], 15, must_include=opening_req[:2])]
    sections += [Section(s[2].format(n=i), s[3].format(a=angles[i - 1]), 20)
                 for i in (1, 2, 3)]
    if _TABLE_CUE.search(prompt or ""):
        sections.append(Section(s[4], s[5], TABLE_SECTION_WORDS, kind="table",
                                must_include=table_req[:1]))
    sections.append(Section(s[6], s[7], 15))
    _rescale(sections, target_words)
    topic = topic_from(getattr(contract, "objective", "") or "")
    return Outline(title="", topic=topic, style="; ".join(bullets)[:240],
                   sections=sections, source="fallback",
                   errors=[error] if error else [])


def make_outline(prompt: str, contract, lang: str, target_words: int, backend,
                 max_sections: int) -> Outline:
    """Outline from the local model, or the deterministic fallback."""
    errors: list[str] = []
    outline = None
    wanted = requested_sections(prompt)
    if wanted:
        max_sections = max(max_sections, wanted + 1)       # + a table section
    # Two attempts: the second at temperature 0 (a malformed outline is
    # usually a sampling accident, not a misunderstanding of the request).
    for temperature in ((0.2, 0.0) if backend is not None else ()):
        raw = backend.generate(outline_prompt(prompt, lang, target_words, max_sections,
                                              wanted),
                               max_tokens=OUTLINE_MAX_TOKENS,
                               temperature=temperature) or ""
        if not raw.strip():
            errors.append("no local model output for the outline")
            continue
        try:
            outline = parse_outline(raw, target_words=target_words,
                                    max_sections=max_sections)
            break
        except (ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc)[:160])
    if outline is None:
        outline = fallback_outline(prompt, contract, lang, target_words,
                                   "; ".join(errors) or "no local model for the outline")
        _ensure_section_count(outline, wanted, lang, target_words)
        return outline
    outline.errors = errors                       # recovered on the retry
    if not outline.topic:
        outline.topic = topic_from(getattr(contract, "objective", "") or "")
    _ensure_table(outline, prompt, lang, target_words, max_sections)
    _drop_unrequested_tables(outline, prompt, target_words)
    _ensure_section_count(outline, wanted, lang, target_words)
    _ensure_request_requirements(outline, prompt)
    _clean_style(outline, prompt)
    return outline


def _clean_style(outline: Outline, prompt: str) -> None:
    """Formatting the request did not ask for leaves the style line.

    P3g.2 (23 Oct 2026): the local model wrote "formatting rules: headings,
    subheadings, bullet points, numbered lists, tables" for a request that
    asked for one table; every section added its own table (31 rows) and the
    report got bullets. A requested table has its own section; lists stay
    only if the request asks for them.
    """
    outline.lists_ok = bool(_LIST_CUE.search(prompt or ""))
    if outline.style.lower().startswith("one line: register"):
        # The local model copied the schema's placeholder (P3i.2).
        outline.style = ""
        outline.adjustments.append("style placeholder copied from the schema removed")
    if not outline.style:
        return
    parts = re.split(r"\s*[;]\s*", outline.style)
    kept = []
    for part in parts:
        if _FORMAT_WORDS.search(part) and not (outline.lists_ok and _LIST_CUE.search(part)):
            cleaned = _FORMAT_WORDS.sub("", part)
            cleaned = re.sub(r"\b(formatting rules|formato|reglas de formato)\s*:?", "",
                             cleaned, flags=re.I)
            cleaned = re.sub(r"[,\s]+(,|$)", r"\1", cleaned).strip(" ,:")
            if len(cleaned.split()) >= 2:
                kept.append(cleaned)
            continue
        kept.append(part)
    style = "; ".join(k for k in kept if k)
    if style != outline.style:
        outline.adjustments.append("format words removed from the style line")
        outline.style = style

def _drop_unrequested_tables(outline: Outline, prompt: str, target_words: int) -> None:
    """A table section the request did not ask for is removed; its key
    points go to the section before it (P3e.2, 22 Oct 2026: the solar-energy
    report, which asks for no table, got "Tabla de comparación de costos")."""
    if _TABLE_CUE.search(prompt or ""):
        return
    dropped = []
    for i in range(len(outline.sections) - 1, 0, -1):
        sec = outline.sections[i]
        if sec.kind == "table" and len(outline.sections) > MIN_SECTIONS:
            prev = outline.sections[i - 1]
            prev.key_points = (prev.key_points + sec.key_points)[:6]
            prev.must_include = (prev.must_include + sec.must_include)[:5]
            outline.sections.pop(i)
            dropped.append(sec.heading)
    if dropped:
        _rescale(outline.sections, target_words)
        outline.adjustments.append("table section removed: not requested ("
                                   + "; ".join(dropped) + ")")


def _ensure_section_count(outline: Outline, wanted: int | None, lang: str,
                          target_words: int) -> None:
    """Give the outline the number of prose sections the request asked for.

    The opening and the closing are kept. Extra middle sections are folded
    into the section before them (their key points and requirements travel
    with them); missing ones are added before the closing, each on an angle
    the outline does not already have. Table sections are not counted.
    """
    if not wanted:
        return
    prose = [i for i, sec in enumerate(outline.sections) if sec.kind != "table"]
    before = len(prose)
    if before == wanted or before < 2:
        return
    while len(prose) > wanted and len(prose) > 2:
        middle = prose[1:-1]
        drop = min(middle, key=lambda i: outline.sections[i].words)
        into = prose[prose.index(drop) - 1]
        gone, keep = outline.sections[drop], outline.sections[into]
        keep.key_points = (keep.key_points + [gone.heading] + gone.key_points)[:6]
        keep.must_include = (keep.must_include + gone.must_include)[:5]
        outline.sections.pop(drop)
        prose = [i for i, sec in enumerate(outline.sections) if sec.kind != "table"]
    s = _FALLBACK.get(lang, _FALLBACK["en"])
    angles = list(_ANGLES.get(lang, _ANGLES["en"]))
    taken = " ".join(sec.heading + " " + sec.purpose for sec in outline.sections).casefold()
    fresh = [a for a in angles if a.split(",")[0].casefold() not in taken]
    added = 0
    while len(prose) < wanted:
        added += 1
        angle = fresh.pop(0) if fresh else None
        heading = (angle.split(",")[0][:1].upper() + angle.split(",")[0][1:]
                   if angle else s[2].format(n=added))
        section = Section(heading, s[3].format(a=angle or outline.topic or heading), 1)
        first_table = next((i for i, sec in enumerate(outline.sections)
                            if sec.kind == "table" and i > 0), None)
        at = first_table if first_table is not None else prose[-1]
        outline.sections.insert(min(at, prose[-1]), section)
        prose = [i for i, sec in enumerate(outline.sections) if sec.kind != "table"]
    middle_words = [outline.sections[i].words for i in prose[1:-1] if outline.sections[i].words > 1]
    for i in prose:
        if outline.sections[i].words <= 1:
            outline.sections[i].words = (round(sum(middle_words) / len(middle_words))
                                         if middle_words else 100)
    _rescale(outline.sections, target_words)
    outline.adjustments.append(
        f"section count set to the {wanted} the request asks for (outline had {before})")


def _closing_sentences(prompt: str) -> list[str]:
    """Sentences of the request's last paragraph, when it is prose (that is
    where requests put delivery requirements: "as a speech opened by …")."""
    tail = (prompt or "").strip().split("\n\n")[-1].strip()
    if not tail or tail.lstrip().startswith(("-", "*", "•")) or re.match(r"\s*\d+[.)]", tail):
        return []
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+", " ".join(tail.split())) if x.strip()]


def _ensure_request_requirements(outline: Outline, prompt: str) -> None:
    """An explicit requirement of the request whose names the outline lost is
    attached to the opening section (live test 2026-10-21: the outline of the
    Galápagos request dropped the presenter, so no section asked for him)."""
    planned = " ".join(" ".join(s.must_include + s.key_points + [s.purpose, s.heading])
                       for s in outline.sections).casefold()
    for sentence in _closing_sentences(prompt):
        if _TABLE_CUE.search(sentence):
            continue                       # tables: _ensure_table
        keys = requirement_keys(sentence)
        proper = [k for k in keys if k not in _STOP]
        if proper and not all(k in planned for k in proper):
            outline.sections[0].must_include.insert(0, sentence[:200])
            outline.adjustments.append(
                "request requirement attached to the opening: " + ", ".join(proper))
            planned += " " + sentence.casefold()


def _ensure_table(outline: Outline, prompt: str, lang: str, target_words: int,
                  max_sections: int) -> None:
    """A requested table is a requirement, not a suggestion: add the section
    the local model left out (live test 2026-10-16: the outline of a request
    for "tablas de resumen" had none)."""
    if not _TABLE_CUE.search(prompt or "") or any(s.kind == "table" for s in outline.sections):
        return
    s = _FALLBACK.get(lang, _FALLBACK["en"])
    sentences = re.split(r"(?<=[.!?])\s+", " ".join((prompt or "").split()))
    req = [x[:200] for x in sentences if _TABLE_CUE.search(x)][:1]
    table = Section(s[4], s[5], TABLE_SECTION_WORDS, must_include=req, kind="table")
    if len(outline.sections) >= max_sections:
        middle = [i for i, sec in enumerate(outline.sections[1:-1], 1) if sec.kind != "table"]
        if middle:
            outline.sections.pop(middle[-1])
    outline.sections.insert(len(outline.sections) - 1, table)
    _rescale(outline.sections, target_words)
    outline.adjustments.append("table section added: requested but missing from the outline")


# -- section briefs ----------------------------------------------------------------
_BRIEF = {
    "es": {
        "head": "Escribe la sección {i} de {n} de un texto{title} sobre {topic}.",
        "title": " titulado «{t}»",
        "section": "Sección: {h}.", "purpose": "Propósito: {p}.",
        "points": "Puntos clave: {x}.", "must": "REQUISITO OBLIGATORIO de esta sección: {x}.",
        "style": "Estilo: {x}.", "words": "Extensión: unas {w} palabras.",
        "first": "Es la apertura: empieza el texto.",
        "last": ("Es el cierre: conecta con lo anterior (que trató sobre «{prev}») con una "
                 "frase de transición natural, sin repetir ese título, y termina el texto "
                 "con una conclusión."),
        "middle": ("Conecta con la sección anterior (que trató sobre «{prev}») con una frase "
                   "de transición natural, sin repetir ese título. No escribas introducción "
                   "ni conclusión del texto completo."),
        "table": ("Presenta esta sección como una tabla en Markdown con encabezados de "
                  "columna, precedida por una frase breve."),
        "only": "Escribe solo el contenido de esta sección, sin el encabezado ni el título.",
        "prose": "Escribe en párrafos, sin tablas.",
        "prose_nolists": "Escribe en párrafos, sin tablas ni listas.",
    },
    "en": {
        "head": "Write section {i} of {n} of a text{title} about {topic}.",
        "title": " titled “{t}”",
        "section": "Section: {h}.", "purpose": "Purpose: {p}.",
        "points": "Key points: {x}.", "must": "MANDATORY for this section: {x}.",
        "style": "Style: {x}.", "words": "Length: about {w} words.",
        "first": "This is the opening: it starts the text.",
        "last": ("This is the closing: connect to what came before (it covered “{prev}”) "
                 "with a natural transition, without repeating that heading, and end the "
                 "text with a conclusion."),
        "middle": ("Connect to the previous section (it covered “{prev}”) with a natural "
                   "transition sentence, without repeating that heading. Do not write an "
                   "introduction or a conclusion of the whole text."),
        "table": ("Present this section as a Markdown table with column headers, "
                  "preceded by one short sentence."),
        "only": "Write only the content of this section, without its heading or the title.",
        "prose": "Write in paragraphs, without tables.",
        "prose_nolists": "Write in paragraphs, without tables or lists.",
    },
}


def _bare(text: str) -> str:
    return (text or "").strip().rstrip(" .;")


def section_instruction(outline: Outline, index: int, lang: str,
                        length_factor: float = 1.0) -> str:
    """The task text of one section: its brief and position, never the request.

    ``length_factor`` scales the words asked of the worker (not the section's
    target): small models overshoot short word targets, by +16 to +44 % in
    the six P3.2 runs of 2026-10-16. Provisional; recalibrate with more runs.
    """
    b = _BRIEF.get(lang, _BRIEF["en"])
    sec = outline.sections[index]
    n = len(outline.sections)
    prev = outline.sections[index - 1].heading if index > 0 else ""
    lines = [b["head"].format(i=index + 1, n=n,
                              title=b["title"].format(t=outline.title) if outline.title else "",
                              topic=outline.topic or "—"),
             b["section"].format(h=_bare(sec.heading)), b["purpose"].format(p=_bare(sec.purpose))]
    if sec.must_include:     # first after the heading: small models drop late constraints
        lines.append(b["must"].format(x="; ".join(_bare(m) for m in sec.must_include)))
    if sec.key_points:
        lines.append(b["points"].format(x="; ".join(_bare(k) for k in sec.key_points)))
    if outline.style and sec.kind != "table":
        lines.append(b["style"].format(x="; ".join(_bare(x) for x in outline.style.split("; "))))
    lines.append(b["words"].format(w=asked_words(sec, length_factor)))
    if sec.kind != "table":
        lines.append(b["prose" if outline.lists_ok else "prose_nolists"])
    if sec.kind == "table":
        lines.append(b["table"])
    elif index == 0:
        lines.append(b["first"])
    elif index == n - 1:
        lines.append(b["last"].format(prev=prev))
    else:
        lines.append(b["middle"].format(prev=prev))
    lines.append(b["only"])
    return "\n".join(lines)


SMALL_SECTION_WORDS = 200


def asked_words(sec: Section, length_factor: float = 1.0) -> int:
    """Words asked of the worker for a section. Short sections are scaled
    down further: asked for 74–89 words, small models wrote 1.0–2.1 times
    that (median ~1.7) in P3g.2, while for 150+ words they stayed within
    1.0–1.4. Provisional, like ``length_factor``."""
    scale = min(1.0, max(0.75, sec.words / SMALL_SECTION_WORDS))
    return max(30, round(sec.words * length_factor * scale))


def section_budget(section: Section, tokens_per_word: float, headroom: float = 1.5) -> int:
    return int(section.words * tokens_per_word * headroom) + 32


# -- assembly ----------------------------------------------------------------------
def clean_section(text: str, section: Section, title: str) -> str:
    """Drop what a worker adds around its section: fences, headings, the title,
    horizontal rules, and a trailing unfinished sentence (a section cut at its
    token budget ended in "Estos puntos" in a live test)."""
    body = (text or "").strip()
    body = re.sub(r"^```[a-zA-Z]*\s*\n?|\n?```\s*$", "", body).strip()
    # a fence's language tag left alone on the first line ("markdown")
    body = re.sub(r"^(?:markdown|md|text)\s*\n", "", body, flags=re.I).strip()
    lines = [ln for ln in body.splitlines() if not re.match(r"^\s*([-*_]\s*){3,}$", ln)]
    names = {section.heading.casefold().strip(" .:*#"), (title or "").casefold().strip(" .:*#")}
    while lines and (not lines[0].strip()
                     or (section.kind != "table" and _HEADING_LINE.match(lines[0]))
                     or lines[0].strip().casefold().strip(" .:*#") in names):
        lines.pop(0)
    body = "\n".join(lines).strip()
    last = body.splitlines()[-1].strip() if body else ""
    if last and not last.startswith("|") and not re.search(r"[.!?:»”\")]\s*$", last):
        cut = max(body.rfind(". "), body.rfind(".\n"), body.rfind("! "), body.rfind("? "))
        if cut > len(body) // 2:
            body = body[:cut + 1].rstrip()
    return body


def assemble(outline: Outline, texts: list[str]) -> str:
    parts = [t for t in texts if t.strip()]
    head = f"# {outline.title}\n\n" if outline.title else ""
    return head + "\n\n".join(parts)


_STOP = frozenset("debe deben texto escrito como para con sobre incluye incluir include "
                  "should must with that this esta este the and las los del una unos unas "
                  "este esta estos estas".split())


def proper_keys(term: str) -> list[str]:
    """The proper nouns of a requirement (not a sentence's capitalised first
    word), case-folded: names such as the presenter's."""
    return [m.group(0).casefold()
            for m in re.finditer(r"\b[A-ZÁÉÍÓÚÑ][\wáéíóúñ]{2,}", term)
            if not re.search(r"(^|[.!?:]\s*)$", term[:m.start()].rstrip(" ¡¿\"'“«"))
            and m.group(0).casefold() not in _STOP]


def requirement_keys(term: str) -> list[str]:
    """Words a text must contain to satisfy a requirement: its proper nouns
    (not the capitalised first word of a sentence), else its content words."""
    proper = proper_keys(term)
    if proper:
        return proper
    words = [w for w in re.findall(r"\w{5,}", term.casefold()) if w not in _STOP]
    return words[:3]


_significant = requirement_keys


def requirement_report(outline: Outline, final_text: str) -> dict[str, Any]:
    """Lexical check of each ``must_include`` and of requested tables."""
    lowered = (final_text or "").casefold()
    checks = []
    table_lines = len(re.findall(r"^\s*\|.*\|\s*$", final_text or "", re.M))
    for sec in outline.sections:
        for req in sec.must_include:
            keys = requirement_keys(req)
            if sec.kind == "table":                # a table requirement is met by a table
                found, keys = table_lines >= 3, ["markdown table (≥ 3 rows)"]
            else:
                found = bool(keys) and all(k in lowered for k in keys)
            checks.append({"section": sec.heading, "requirement": req, "found": found,
                           "matched_on": keys})
    tables_requested = any(s.kind == "table" for s in outline.sections)
    return {"checks": checks,
            "found": sum(1 for c in checks if c["found"]), "total": len(checks),
            "tables_requested": tables_requested, "table_rows": table_lines,
            "words": len((final_text or "").split()),
            "note": "lexical presence check, not a quality judgement"}
