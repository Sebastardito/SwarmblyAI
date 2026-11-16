"""Claim verifier (3.3, recipe 3).

A label under a sentence says where the model claims the sentence comes from;
it does not say the paragraph supports it. In the open battery (run x33,
qwen2.5:7b) 16 of 43 labelled sentences read by hand were not supported by
the paragraph they cite: the figure was in another paragraph ("[D1 p16] … 2,37
t/ha", which is in p17), the paragraph was about something else (the budget,
for an agreement of the same meeting), the sentence added an opinion of the
model's ("esto nos ayudará a optimizar la nutrición… [D1 p4]") or changed what
the paragraph says ("presentó una propuesta" for "presentará en junio una
propuesta").

Each labelled sentence is checked in two steps, the cheap one first:

1. By code. Every figure of the sentence has to be in the paragraphs it cites
   (or be the difference or the sum of two that are). When the figure is in
   another paragraph that was given and bears on the sentence, the citation
   is completed with that paragraph's label ("[D1 p16]" → "[D1 p16][D1 p17]"):
   the fact was right and its citation was not. A cited paragraph that shares
   no word with the sentence is reported.
2. By a model, in one short job per sentence (the ``verifier`` role): the
   cited paragraphs, the sentence, and one word back: SÍ, PARTE or NO.

No sentence is rewritten: labels are completed by code and the report goes
under the answer (``meta.verification``). Rewriting by the model that made
the mistake was measured in 3.2 and left off.

Measured on the open set of 73 claims (``bench/dev/verificador.json``, one
run): the code alone flags 5 of 31 unsupported sentences and none of the 42
supported; with qwen2.5:7b 23 of 31 and none; with qwen2.5:14b 29 and 2; with
qwen3.8:27b 31 and 2.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from .compose import _CITE, _OUTSIDE, _derived, _figures, _stems, unflatten_tables

# a sentence about what the sources do not say ("no se menciona clorosis en
# la Parcela Norte [D1 p11]") is about the sources, not a claim from them: a
# 7B verifier answered NO to it (open battery, vf33)
_ABSENCE = re.compile(r"\bno\s+(?:se\s+)?(?:menciona\w*|indica\w*|dice\w*|registra\w*|especifica\w*|"
                      r"aparece\w*|recoge\w*|informa\w*)\b|\bno\s+(?:hay|figura\w*|consta\w*)\s+"
                      r"(?:datos|informaci[oó]n|registros?|menci[oó]n)\b|\bsin\s+(?:datos|menci[oó]n)\b|"
                      r"\b(?:does|do)\s+not\s+(?:mention|say|state|report)\b|\bno\s+(?:data|mention)\b|"
                      # "Las fuentes no coinciden en este punto. [D1 p6]": about the sources
                      r"\bno\s+coincid\w*|\bsources?\b[^.]{0,30}\b(?:disagree|differ)\b", re.I)
_LABEL = re.compile(r"\[\s*((?:[A-Z]\d+\s*p\d+)|(?:W\d+))[^\]]{0,40}\]")
YES, PARTLY, NO = "yes", "partly", "no"


_ONE = re.compile(r"\b([A-Z]\d+\s*p\d+|W\d+)\b")


def _labels(sentence: str) -> list[str]:
    """Every label of the sentence, also several in one bracket ("[D1 p3, D1 p4]")."""
    out: list[str] = []
    for m in _LABEL.finditer(sentence):
        out += [_norm(x) for x in _ONE.findall(m.group(0))]
    return list(dict.fromkeys(out))


def _norm(label: str) -> str:
    return " ".join(re.sub(r"([A-Z]\d+)\s*(p\d+)", r"\1 \2", label).split())


def split(answer: str) -> list[dict[str, Any]]:
    """The sentences of an answer that carry a label, with their labels, as
    the answer writes them. Table rows, headings and what goes under "Fuera
    de tus fuentes:" are not claims about the sources."""
    out: list[dict[str, Any]] = []
    for para in re.split(r"\n\s*\n", answer or ""):
        outside = False
        for line in para.split("\n"):
            if _OUTSIDE.search(line):
                outside = True
            if outside or line.lstrip().startswith(("|", "#", ">")):
                continue
            parts = re.split(r"(?<=[.!?])\s+", line.strip())
            if not re.match(r"(?:[-*]\s+)?\[", line.strip()):
                # "…dólares. [D1 p17] La referencia…": a label after the full
                # stop belongs to the sentence it closes (unless the line
                # opens with its label: "[D2 p2] Ana: …")
                for i in range(1, len(parts)):
                    m = re.match(r"((?:\[[^\]]{2,50}\]\s*)+)", parts[i])
                    if m:
                        parts[i - 1] += " " + m.group(1).strip()
                        parts[i] = parts[i][m.end():]
            for sentence in parts:
                sentence = sentence.strip()
                labels = _labels(sentence)
                if labels and len(_CITE.sub(" ", sentence).split()) >= 5:
                    item = {"text": sentence, "labels": labels}
                    if _ABSENCE.search(sentence):
                        item["absence"] = True
                    out.append(item)
    return out


def _passage(source: dict[str, Any]) -> tuple[str, str, str]:
    """(label, title or file name, text) of a passage or a public result."""
    label = _norm(str(source.get("label", "")))
    title = str(source.get("doc_title") or source.get("title") or "")
    if not title:
        title = re.sub(r"\.\w{1,5}$", "", str(source.get("rel") or source.get("source") or "").rsplit("/", 1)[-1])
        title = re.sub(r"[_-]+", " ", title)
    text = str(source.get("text") or source.get("snippet") or "")
    return label, title.strip(), unflatten_tables(text)


_COMPUTED = re.compile(r"(diferencia|m[aá]s|menos|superior|inferior|por\s+encima|por\s+debajo|total|suma|"
                       r"difference|more|less|higher|lower|above|below|sum)[^\w,;]+(?:\w+[^\w,;]+){0,3}$", re.I)


def _presented_as_computed(sentence: str, figure: str) -> bool:
    """Whether the sentence writes this figure as a difference or a sum
    ("una diferencia de 0,3", "0,3 t/ha más")."""
    from .compose import _NUMBER, _canon
    for m in _NUMBER.finditer(_CITE.sub(" ", sentence)):
        if _canon(m.group(1)) == figure:
            before = _CITE.sub(" ", sentence)[max(0, m.start() - 60):m.start()]
            after = _CITE.sub(" ", sentence)[m.end():m.end() + 30]
            if _COMPUTED.search(before) or re.match(r"\s*(?:%|t/ha|kg\S*|\w+/\w+)?\s*(m[aá]s|menos|more|less)\b",
                                                    after, re.I):
                return True
    return False


def by_code(sentence: str, labels: list[str], sources: list[dict[str, Any]],
            computed: set[str] | None = None) -> dict[str, Any]:
    """What the code can say about a labelled sentence: figures that are not
    in the paragraphs it cites, the paragraphs that have them (``complete``:
    labels that complete the citation), figures computed from sourced ones,
    labels of paragraphs that were not given, and cited paragraphs that share
    no word with the sentence."""
    known = {lab: (title, text) for lab, title, text in map(_passage, sources) if lab}
    cited = [(lab, *known[lab]) for lab in labels if lab in known]
    unknown = [lab for lab in labels if lab not in known]
    figs = _figures(sentence)
    words = _stems(sentence)
    have = set().union(*(_figures(f"{title}\n{text}") for _, title, text in cited)) if cited else set()
    # paragraphs that were given, are not cited and bear on the sentence
    near = {lab: _figures(f"{title}\n{text}") for lab, (title, text) in known.items()
            if lab not in labels and len(words & _stems(text)) >= 2}
    absent = figs - have
    # a figure another paragraph gives is a figure with a citation missing, not
    # a calculation ("AB2 3,1 t/ha, 0,3 más que AB1 con 2,8 [D1 p16]": 3,1 is
    # in AB2's table, though it is also 2,8 plus the 0,3 of a deviation)
    elsewhere = {f for f in absent if any(f in fg for fg in near.values())}
    derived = _derived(figs, have) - elsewhere
    # figures the program itself computed for this answer (a comparison's
    # difference and percentage, recipe 3): the verifier flagged "un 13 % menos"
    derived |= figs & (computed or set())
    derived |= _derived(figs, have | elsewhere) - elsewhere
    # "3,1 frente a 2,8, una diferencia de 0,3": the 0,3 is also a deviation
    # in the cited table, but in the sentence it is the difference of two of
    # its figures; the model is told so (a 7B and a 14B verifier answered
    # PARTE to right sentences like this one, vf33 and vf14)
    # (only the figure the sentence presents as one: each of three figures is
    # the difference of the other two)
    for f in figs & have:
        rest = (figs & (have | elsewhere)) - {f}
        if f in _derived({f} | rest, rest) and _presented_as_computed(sentence, f):
            derived.add(f)
    missing = absent - derived
    complete: list[str] = []
    left = set(missing)
    while left and len(complete) < 2:
        best = max(near, key=lambda lab: (len(left & near[lab]), len(words & _stems(known[lab][1]))), default="")
        if not best or not (left & near[best]):
            break
        complete.append(best)
        left -= near.pop(best)
    if left:
        complete = []
    unrelated = [lab for lab, title, text in cited
                 if words and not (words & _stems(f"{title} {text}")) and not (figs & _figures(text))]
    return {"missing_figures": sorted(missing), "complete": complete, "derived": sorted(derived),
            "unknown": unknown, "unrelated": unrelated, "cited": [lab for lab, _, _ in cited]}


def prompt(sentence: str, labels: list[str], sources: list[dict[str, Any]], lang: str = "es",
           derived: list[str] | None = None) -> str:
    """One short job: the cited paragraphs, the sentence, one word back.
    ``derived``: figures of the sentence that the code computed from figures
    of the paragraphs (a difference, a sum)."""
    known = {lab: (title, text) for lab, title, text in map(_passage, sources) if lab}
    blocks = []
    for lab in labels:
        if lab in known:
            title, text = known[lab]
            head = f"[{lab}]" + (f" ({title})" if title else "")
            blocks.append(f"{head}\n{text.strip()}")
    # the sentence keeps its labels: the paragraphs are shown under the same ones
    claim = " ".join(sentence.replace("**", "").split())
    shown = ", ".join(f.replace(".", ",") if lang == "es" else f for f in derived or [])
    if lang == "es":
        note = (f"Nota: {shown} se calcula con cifras de los párrafos (una diferencia o una suma) y el cálculo "
                "es correcto; no cuenta como algo añadido.\n\n") if shown else ""
        return ("Párrafos:\n\n" + "\n\n".join(blocks) + f"\n\nFrase: {claim}\n\n{note}"
                "¿Los párrafos dicen lo que afirma la frase? Responde con una sola palabra:\n"
                "SÍ: los párrafos lo dicen.\n"
                "PARTE: dicen una parte, pero la frase añade algo que no está o lo cambia.\n"
                "NO: no lo dicen, o dicen otra cosa.")
    note = (f"Note: {shown} is computed from figures of the paragraphs (a difference or a sum) and the "
            "calculation is right; it does not count as something added.\n\n") if shown else ""
    return ("Paragraphs:\n\n" + "\n\n".join(blocks) + f"\n\nSentence: {claim}\n\n{note}"
            "Do the paragraphs say what the sentence states? Answer with one word:\n"
            "YES: the paragraphs say it.\n"
            "PARTLY: they say a part, but the sentence adds something that is not there or changes it.\n"
            "NO: they do not say it, or they say something else.")


def parse(text: str) -> str | None:
    """The verdict in the model's reply (its first word that is one)."""
    for word in re.findall(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]+", (text or "")[:120]):
        w = word.lower().replace("í", "i")
        if w in ("si", "yes"):
            return YES
        if w in ("parte", "partly", "parcial", "parcialmente", "partially"):
            return PARTLY
        if w in ("no", "not"):
            return NO
    return None


def check(sentence: str, labels: list[str], sources: list[dict[str, Any]],
          generate: Callable[[str, int], str] | None = None, lang: str = "es",
          computed: set[str] | None = None) -> dict[str, Any]:
    """The verdict on one labelled sentence: ``ok`` is False when the code or
    the model found it unsupported, None when nobody could tell (no model, or
    a reply that is not a verdict). ``added``: labels that complete its
    citation (its figures are in those paragraphs)."""
    code = by_code(sentence, labels, sources, computed)
    out: dict[str, Any] = {"text": sentence[:300], "labels": labels, "by": "code", "ok": None}
    if code["unknown"] and not code["cited"]:
        return {**out, "ok": False, "why": "unknown_label", "unknown": code["unknown"]}
    cited = list(code["cited"])
    if code["missing_figures"]:
        if not code["complete"]:
            return {**out, "ok": False, "why": "figure_not_in_cited", "figures": code["missing_figures"]}
        out["added"] = code["complete"]
        cited += code["complete"]
    if code["unrelated"] and len(code["unrelated"]) == len(code["cited"]) and not out.get("added"):
        return {**out, "ok": False, "why": "unrelated_paragraph", "unrelated": code["unrelated"]}
    if code["unrelated"]:
        out["unrelated"] = code["unrelated"]
        cited = [lab for lab in cited if lab not in code["unrelated"]]     # they cannot support anything
    if generate is None:
        return out
    verdict = parse(generate(prompt(sentence, cited, sources, lang, code["derived"]), 6))
    out["by"] = "model"
    if verdict is None:
        return out
    out["verdict"] = verdict
    out["ok"] = verdict == YES
    if verdict != YES:
        out["why"] = "partly" if verdict == PARTLY else "not_in_cited"
    return out


def _with_labels(sentence: str, added: list[str]) -> str:
    """The sentence with these labels after its last one."""
    last = None
    for last in _LABEL.finditer(sentence):
        pass
    if last is None:
        return sentence
    return sentence[:last.end()] + "".join(f"[{lab}]" for lab in added) + sentence[last.end():]


def verify(answer: str, sources: list[dict[str, Any]], generate: Callable[[str, int], str] | None = None,
           lang: str = "es", limit: int = 24, computed: list[str] | None = None) -> dict[str, Any]:
    """Every labelled sentence of the answer, checked. ``limit`` bounds the
    model's jobs (a long composition has about fifteen labelled sentences).
    ``text`` is the answer with the citations the code completed."""
    claims = split(answer)
    done = set().union(*(_figures(str(x)) for x in computed)) if computed else set()
    checked, asked, text, completed, about = [], 0, answer or "", [], 0
    for c in claims:
        if c.get("absence"):
            about += 1          # what the sources do not say: not a claim from them
            continue
        use = generate if asked < limit else None
        r = check(c["text"], c["labels"], sources, use, lang, done)
        asked += r["by"] == "model"
        if r.get("added") and c["text"] in text:
            text = text.replace(c["text"], _with_labels(c["text"], r["added"]), 1)
            completed.append({"text": c["text"][:200], "added": r["added"]})
        checked.append(r)
    flagged = [r for r in checked if r["ok"] is False]
    return {"claims": len(checked), "supported": sum(1 for r in checked if r["ok"]),
            "flagged": flagged, "unchecked": sum(1 for r in checked if r["ok"] is None), "asked": asked,
            "completed": completed, "about_sources": about, "text": text}
