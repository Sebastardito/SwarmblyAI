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
   (or be the difference or the sum of two that are). A figure that is in
   another paragraph given to the model is reported with that paragraph. A
   cited paragraph that shares no word with the sentence is reported too.
2. By a model, in one short job per sentence (the ``verifier`` role): the
   cited paragraphs, the sentence, and one word back: SÍ, PARTE or NO.

Nothing is rewritten: the answer keeps its text and the report goes under it
(``meta.verification``). Rewriting by the model that made the mistake was
measured in 3.2 and left off.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from .compose import _CITE, _OUTSIDE, _derived, _figures, _stems, unflatten_tables

_LABEL = re.compile(r"\[\s*((?:[A-Z]\d+\s*p\d+)|(?:W\d+))[^\]]{0,40}\]")
YES, PARTLY, NO = "yes", "partly", "no"


def _norm(label: str) -> str:
    return " ".join(re.sub(r"([A-Z]\d+)\s*(p\d+)", r"\1 \2", label).split())


def split(answer: str) -> list[dict[str, Any]]:
    """The sentences of an answer that carry a label, with their labels.
    Table rows, headings and what goes under "Fuera de tus fuentes:" are not
    claims about the sources."""
    out: list[dict[str, Any]] = []
    for para in re.split(r"\n\s*\n", answer or ""):
        outside = False
        for line in para.split("\n"):
            if _OUTSIDE.search(line):
                outside = True
            if outside or line.lstrip().startswith(("|", "#", ">")):
                continue
            if not re.match(r"\s*(?:[-*]\s+)?\[", line):
                # "…dólares. [D1 p17] La referencia…": a label after the full
                # stop belongs to the sentence it closes (unless the line
                # opens with its label: "[D2 p2] Ana: …")
                line = re.sub(r"([.!?])\s+((?:\[[^\]]{2,50}\]\s*)+)", lambda m: f" {m.group(2).strip()}{m.group(1)} ", line)
            for sentence in re.split(r"(?<=[.!?])\s+", line):
                sentence = sentence.strip()
                labels = list(dict.fromkeys(_norm(m) for m in _LABEL.findall(sentence)))
                if labels and len(_CITE.sub(" ", sentence).split()) >= 5:
                    out.append({"text": sentence, "labels": labels})
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


def by_code(sentence: str, labels: list[str], sources: list[dict[str, Any]]) -> dict[str, Any]:
    """What the code can say about a labelled sentence: figures that are not
    in the paragraphs it cites (and the paragraph that has them, if one of
    those given does), labels of paragraphs that were not given, and cited
    paragraphs that share no word with the sentence."""
    known = {lab: (title, text) for lab, title, text in map(_passage, sources) if lab}
    cited = [(lab, *known[lab]) for lab in labels if lab in known]
    unknown = [lab for lab in labels if lab not in known]
    figs = _figures(sentence)
    have = set().union(*(_figures(f"{title}\n{text}") for _, title, text in cited)) if cited else set()
    missing = figs - have
    missing -= _derived(figs, have)
    elsewhere: list[str] = []
    if missing:
        words = _stems(sentence)
        for lab, (title, text) in known.items():
            if lab not in labels and missing <= _figures(f"{title}\n{text}") and words & _stems(text):
                elsewhere.append(lab)
    words = _stems(sentence)
    unrelated = [lab for lab, title, text in cited
                 if words and not (words & _stems(f"{title} {text}")) and not (figs & _figures(text))]
    return {"missing_figures": sorted(missing), "elsewhere": elsewhere[:3], "unknown": unknown,
            "unrelated": unrelated, "cited": [lab for lab, _, _ in cited]}


def prompt(sentence: str, labels: list[str], sources: list[dict[str, Any]], lang: str = "es") -> str:
    """One short job: the cited paragraphs, the sentence, one word back."""
    known = {lab: (title, text) for lab, title, text in map(_passage, sources) if lab}
    blocks = []
    for lab in labels:
        if lab in known:
            title, text = known[lab]
            head = f"[{lab}]" + (f" ({title})" if title else "")
            blocks.append(f"{head}\n{text.strip()}")
    # the sentence keeps its labels: the paragraphs are shown under the same ones
    claim = " ".join(sentence.replace("**", "").split())
    if lang == "es":
        return ("Párrafos:\n\n" + "\n\n".join(blocks) + f"\n\nFrase: {claim}\n\n"
                "¿Los párrafos dicen lo que afirma la frase? Responde con una sola palabra:\n"
                "SÍ: los párrafos lo dicen.\n"
                "PARTE: dicen una parte, pero la frase añade algo que no está o lo cambia.\n"
                "NO: no lo dicen, o dicen otra cosa.")
    return ("Paragraphs:\n\n" + "\n\n".join(blocks) + f"\n\nSentence: {claim}\n\n"
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
          generate: Callable[[str, int], str] | None = None, lang: str = "es") -> dict[str, Any]:
    """The verdict on one labelled sentence: ``ok`` is False when the code or
    the model found it unsupported, None when nobody could tell (no model, or
    a reply that is not a verdict)."""
    code = by_code(sentence, labels, sources)
    out: dict[str, Any] = {"text": sentence[:300], "labels": labels, "by": "code", "ok": None}
    if code["unknown"] and not code["cited"]:
        return {**out, "ok": False, "why": "unknown_label", "unknown": code["unknown"]}
    if code["missing_figures"]:
        return {**out, "ok": False, "why": "figure_not_in_cited", "figures": code["missing_figures"],
                "elsewhere": code["elsewhere"]}
    if code["unrelated"] and len(code["unrelated"]) == len(code["cited"]):
        return {**out, "ok": False, "why": "unrelated_paragraph", "unrelated": code["unrelated"]}
    if code["unrelated"]:
        out["unrelated"] = code["unrelated"]
    if generate is None:
        return out
    verdict = parse(generate(prompt(sentence, code["cited"], sources, lang), 6))
    out["by"] = "model"
    if verdict is None:
        return out
    out["verdict"] = verdict
    out["ok"] = verdict == YES
    if verdict != YES:
        out["why"] = "partly" if verdict == PARTLY else "not_in_cited"
    return out


def verify(answer: str, sources: list[dict[str, Any]], generate: Callable[[str, int], str] | None = None,
           lang: str = "es", limit: int = 24) -> dict[str, Any]:
    """Every labelled sentence of the answer, checked. ``limit`` bounds the
    model's jobs (a long composition has about fifteen labelled sentences)."""
    claims = split(answer)
    checked, asked = [], 0
    for c in claims:
        use = generate if asked < limit else None
        r = check(c["text"], c["labels"], sources, use, lang)
        asked += r["by"] == "model"
        checked.append(r)
    flagged = [r for r in checked if r["ok"] is False]
    return {"claims": len(checked), "supported": sum(1 for r in checked if r["ok"]),
            "flagged": flagged, "unchecked": sum(1 for r in checked if r["ok"] is None), "asked": asked}
