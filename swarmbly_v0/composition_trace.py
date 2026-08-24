"""The construction trace: what the assembled text is made of, and where it joins.

A score on a composition says whether the text satisfied its constraints. It
does not say *how the text came to be*, and for an architecture whose entire
claim is that fragments can be reassembled into a coherent whole, the how is the
evidence. A reader who is told "score 0.78" learns nothing about whether the
protocol works; a reader shown which worker wrote which sentence, where the
seams fell, how similar the text was across each one, and which constraint broke
at which seam, can judge it.

So this module emits, for one composition, a record with three layers:

**Provenance.** Every sentence attributed to the micro-task that produced it,
from the assembler's own offsets. This is the layer that makes a duplicated
introduction legible as *two workers doing the same thing* rather than as a
model quirk.

**Seams.** Each junction between fragments, with its semantic similarity, the
threshold it was judged against, and whether a bridge was inserted. A seam is
where assembly can fail and the only place where the coherence tax and the
constraint checks can disagree informatively.

**Constraints, located.** A failed constraint is reported with the sentence and
the fragment it occurred in, so ``no_repeated_sentence`` stops being a boolean
and becomes "task t1 and task t3 both wrote this".

Nothing here is a judgement. Every number is counted from the text, the plan and
the assembler's offsets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .constraints import CompositionReport, grade_text, paragraphs_of
from .grading import normalise_text
from .textutil import count_tokens, split_sentences

__all__ = ["CompositionTrace", "build_trace", "render_trace"]


@dataclass
class CompositionTrace:
    """One assembled composition, with everything counted about its construction."""

    prompt_id: str
    condition: str
    text: str
    report: CompositionReport
    sentences: list[dict[str, Any]] = field(default_factory=list)
    seams: list[dict[str, Any]] = field(default_factory=list)
    per_task: list[dict[str, Any]] = field(default_factory=list)
    duplicated: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "condition": self.condition,
            "composition": self.report.as_dict(),
            "sentences": self.sentences,
            "seams": self.seams,
            "per_task": self.per_task,
            "duplicated": self.duplicated,
        }


def _attribute(
    text: str,
    order: Sequence[str] | None,
    offsets: Sequence[int] | None,
) -> list[dict[str, Any]]:
    """Attribute each sentence of ``text`` to the micro-task that produced it.

    The assembler records ``order`` -- the task ids in the order they were
    spliced -- and ``fragment_sentence_offsets``, the sentence index each one
    starts at. Fragment *i* therefore owns sentences from ``offsets[i]`` up to
    ``offsets[i+1]``, and the last owns the remainder.

    With no order -- the monolithic condition has no fragments -- every sentence
    is attributed to the single generation. Leaving that condition blank would
    make the baseline unreadable next to the thing it is the baseline for.
    """
    sentences = [s.strip() for s in split_sentences(text) if s.strip()]
    spans: list[tuple[str, int, int]] = []
    if order and offsets and len(order) == len(offsets):
        for i, task_id in enumerate(order):
            start = int(offsets[i])
            end = int(offsets[i + 1]) if i + 1 < len(offsets) else len(sentences)
            spans.append((str(task_id), start, max(start, end)))

    out: list[dict[str, Any]] = []
    for i, sentence in enumerate(sentences):
        task = "monolithic"
        for task_id, start, end in spans:
            if start <= i < end:
                task = task_id
                break
        out.append({"index": i, "task_id": task, "tokens": count_tokens(sentence),
                    "text": sentence})
    return out


def _duplicates(sentences: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Sentences that appear more than once, with the tasks that wrote them.

    The signature failure of assembly, and the reason this is reported next to
    the provenance rather than as a bare count: "said twice" is a defect,
    "written twice by two different workers" is a diagnosis.
    """
    by_text: dict[str, list[Mapping[str, Any]]] = {}
    for s in sentences:
        key = normalise_text(str(s.get("text", "")))
        if key:
            by_text.setdefault(key, []).append(s)
    return [
        {"text": group[0]["text"], "count": len(group),
         "task_ids": sorted({str(g["task_id"]) for g in group}),
         "cross_task": len({str(g["task_id"]) for g in group}) > 1}
        for group in by_text.values() if len(group) > 1
    ]


def build_trace(
    prompt_id: str,
    condition: str,
    text: str,
    constraints: Sequence[Mapping[str, Any]],
    order: Sequence[str] | None = None,
    offsets: Sequence[int] | None = None,
    seams: Sequence[Any] | None = None,
) -> CompositionTrace:
    """Assemble the full construction record for one composition."""
    report = grade_text(text, constraints)
    sentences = _attribute(text, order, offsets)

    per_task: dict[str, dict[str, Any]] = {}
    for s in sentences:
        entry = per_task.setdefault(str(s["task_id"]),
                                    {"task_id": s["task_id"], "n_sentences": 0, "tokens": 0})
        entry["n_sentences"] += 1
        entry["tokens"] += int(s["tokens"])

    seam_rows: list[dict[str, Any]] = []
    for seam in seams or []:
        seam_rows.append({
            "index": getattr(seam, "index", None),
            "left_task": getattr(seam, "left_task", None),
            "right_task": getattr(seam, "right_task", None),
            "similarity": round(float(getattr(seam, "similarity", 0.0)), 6),
            "tau_sem": round(float(getattr(seam, "tau_sem", 0.0)), 6),
            "bridged": bool(getattr(seam, "bridged", False)),
        })

    return CompositionTrace(
        prompt_id=prompt_id,
        condition=condition,
        text=text,
        report=report,
        sentences=sentences,
        seams=seam_rows,
        per_task=sorted(per_task.values(), key=lambda d: str(d["task_id"])),
        duplicated=_duplicates(sentences),
    )


def render_trace(traces: Sequence[CompositionTrace]) -> str:
    """Render traces as Markdown -- the artefact a reader actually opens.

    Deliberately plain. The point is that someone can read the generated text,
    see which worker wrote each sentence, and check the numbers by hand against
    the paragraph in front of them.
    """
    lines: list[str] = [
        "# Composition traces",
        "",
        "One section per composition per condition. Every number below is counted from the",
        "text, the plan and the assembler's sentence offsets -- there is no judge anywhere in",
        "this file. `monolithic` is the unfragmented baseline and exists so that a defect can",
        "be attributed to assembly rather than to the model.",
        "",
    ]
    for trace in traces:
        r = trace.report
        lines += [
            f"## {trace.prompt_id} — {trace.condition}",
            "",
            f"**Constraints satisfied: {r.n_satisfied}/{len(r.results)}"
            + (f" ({r.score:.0%})" if r.score is not None else "")
            + f"** · {r.n_paragraphs} paragraphs · {r.n_sentences} sentences · {r.n_tokens} tokens",
            "",
        ]
        if r.failed:
            lines += ["| Constraint | Kind | Observed | Expected | Detail |",
                      "|---|---|---|---|---|"]
            for f in r.failed:
                lines.append(f"| `{f.constraint_id}` | {f.kind} | {f.observed} | "
                             f"{f.expected} | {f.detail} |")
            lines.append("")
        else:
            lines += ["Every constraint satisfied.", ""]

        if trace.per_task:
            lines += ["**Contribution by micro-task**", "",
                      "| Task | Sentences | Tokens |", "|---|---|---|"]
            for t in trace.per_task:
                lines.append(f"| `{t['task_id']}` | {t['n_sentences']} | {t['tokens']} |")
            lines.append("")

        if trace.seams:
            lines += ["**Seams**", "",
                      "| # | Left | Right | Similarity | tau_sem | Bridged |", "|---|---|---|---|---|---|"]
            for s in trace.seams:
                lines.append(f"| {s['index']} | `{s['left_task']}` | `{s['right_task']}` | "
                             f"{s['similarity']:.3f} | {s['tau_sem']:.3f} | "
                             f"{'yes' if s['bridged'] else 'no'} |")
            lines.append("")

        if trace.duplicated:
            lines += ["**Repeated sentences** — the failure mode assembly produces and "
                      "monolithic generation almost never does:", ""]
            for d in trace.duplicated:
                where = ", ".join(f"`{t}`" for t in d["task_ids"])
                across = " **across different micro-tasks**" if d["cross_task"] else ""
                lines.append(f"- {d['count']}× from {where}{across}: {d['text'][:120]}")
            lines.append("")

        lines += ["<details><summary>Generated text</summary>", "", "```", trace.text.strip(),
                  "```", "", "</details>", ""]
    return "\n".join(lines) + "\n"
