"""The post-processing editor: one pass over the assembled answer.

Why there is a gap here at all
------------------------------

Everything downstream of generation, until now, was the assembler: order the
fragments, measure each junction, and synthesise a bridge where the cosine falls
below ``tau_sem``. That is the *only* post-processing the protocol has ever had,
and the run of 25 August showed it doing harm. In ``comp_harbour`` at k=3 the
bridge repaired a bad seam and, being a sentence standing between two blocks,
became a third paragraph -- breaking a ``paragraph_count`` constraint the
assembler has no way to know exists. A repair mechanism that optimises one
measure while blind to the others is not a repair mechanism.

What an editor can do that a micro-task cannot
----------------------------------------------

Every defect the composition runs actually produced is a property of the *whole*
answer, and no worker can see the whole answer by construction:

* a term defined twice, because two workers each introduced it;
* a paragraph count that is the sum of what each worker chose;
* a required term dropped, because the fragment that would have carried it got
  a packet that never mentioned it;
* a phrase repeated across a seam.

These are exactly the checks in :mod:`swarmbly_v0.constraints`, and they are all
decidable by counting. So the editor does not need judgement and does not get
any: it is told which mechanical checks failed and asked to fix those.

The budget argument, stated precisely
-------------------------------------

The obvious objection is that a pass over everything reintroduces the context
cost the protocol exists to avoid. It does not, and the distinction is worth
being exact about.

``rho`` is defined over the *problem*: the sum of packet contents against the
size of the prompt P. The editor never sees P. Its context is the assembled
answer plus the contract, which is O(answer) -- and the answer is the thing a
single node was always going to have to hold anyway, because it is what gets
returned. So the editor adds a **serial stage**, not context pressure, and
``rho`` is unchanged by construction.

That is an argument, not a licence. ``editor_input_tokens`` is reported on every
row so the cost is visible as its own budget line rather than folded into a
number that would hide it.

Three refusals, and why each is load-bearing
--------------------------------------------

**It never accepts a regression.** The revision is scored by the same mechanical
checks as the original and kept only if it satisfies at least as many. The
bridge is the cautionary tale: without this gate an editor is one more mechanism
that can trade an unmeasured dimension for a measured one.

**It never invents a figure.** On grounded prose the editor could satisfy
"mention the total" by writing a plausible total. Any revision introducing a
number outside the allowed set is rejected whole.

**It cannot fix a fact.** The editor has the answer and the contract; it does
*not* have the source material. So it can restore a dropped term, merge a
duplicated definition, and repair the shape -- and it cannot know that 830 kg
should have been 840. This is the sharpest prediction the module makes: the
editor should recover *format* and not *accuracy*. If a run shows item accuracy
rising under the editor, the editor is answering from its own knowledge rather
than editing, and the result is contaminated rather than good.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .constraints import (
    CompositionReport,
    check_numeric_fidelity,
    grade_text,
    paragraphs_of,
)
from .textutil import count_tokens

__all__ = ["EditorReport", "REPAIR_INSTRUCTIONS", "edit_assembled"]


REPAIR_INSTRUCTIONS: dict[str, str] = {
    "paragraph_count":
        "The answer must be exactly {expected} paragraphs separated by blank lines; "
        "it currently has {observed}. Merge or split paragraphs to reach the count. "
        "Do not add new material and do not delete any fact.",
    "words_per_paragraph":
        "Every paragraph must be between {lo} and {hi} words; the current counts are "
        "{observed}. Expand the short ones using only material already present "
        "elsewhere in the answer, and condense the long ones.",
    "must_mention":
        "The answer must mention {term!r} and does not. Add it where it belongs, "
        "without inventing any claim about it.",
    "must_not_mention":
        "The answer must not mention {term!r}. Remove it and any clause that "
        "depends on it.",
    "term_once":
        "The term {term!r} must appear exactly once and appears {observed} times. "
        "Keep the clearest occurrence and remove the rest, preserving anything "
        "the removed sentences said that is not said elsewhere.",
    "no_repeated_sentence":
        "{observed} sentence(s) appear more than once. Keep one copy of each.",
    "no_repeated_ngram":
        "A phrase is repeated verbatim ({detail}). Rewrite one occurrence.",
}
"""One instruction per constraint kind, filled from the failure's own numbers.

Deliberately specific. "Improve the coherence of this text" is the prompt that
produces a rewrite -- new claims, dropped facts, a different answer -- and a
rewrite cannot be attributed to assembly repair. Naming the count, the term and
the observed value keeps the edit local and keeps the comparison honest.
"""


@dataclass(frozen=True)
class EditorReport:
    """What the editor did, and what it cost."""

    text: str
    applied: bool
    reason: str
    score_before: float | None = None
    score_after: float | None = None
    violations_before: tuple[str, ...] = ()
    violations_after: tuple[str, ...] = ()
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    @property
    def gain(self) -> float | None:
        if self.score_before is None or self.score_after is None:
            return None
        return round(self.score_after - self.score_before, 6)

    def as_dict(self) -> dict[str, Any]:
        return {
            "editor_applied": self.applied,
            "editor_reason": self.reason,
            "editor_score_before": self.score_before,
            "editor_score_after": self.score_after,
            "editor_gain": self.gain,
            "editor_violations_before": list(self.violations_before),
            "editor_violations_after": list(self.violations_after),
            "editor_input_tokens": self.input_tokens,
            "editor_output_tokens": self.output_tokens,
            "editor_calls": self.calls,
        }


def _describe(result: Any) -> str:
    """Turn one failed check into the sentence the editor is given."""
    template = REPAIR_INSTRUCTIONS.get(result.kind)
    if not template:
        return f"A {result.kind} check failed (observed {result.observed})."
    term = ""
    detail = result.detail or ""
    if "term=" in detail:
        term = detail.split("term=", 1)[1].strip().strip("'\"")
    lo = hi = ""
    if isinstance(result.expected, (list, tuple)) and len(result.expected) == 2:
        lo, hi = result.expected
    try:
        return template.format(expected=result.expected, observed=result.observed,
                               term=term, detail=detail, lo=lo, hi=hi)
    except (KeyError, IndexError):  # a template outgrew its fields
        return f"A {result.kind} check failed (observed {result.observed})."


def _build_prompt(text: str, failures: Sequence[Any], objective: str) -> str:
    """The repair prompt: the answer, the specific defects, and nothing else.

    The objective is included because a constraint like "mention the total" is
    unintelligible without knowing what the answer is *for*; it is one line, not
    the source material, and it is already in the contract every node received.
    """
    numbered = "\n".join(f"{i}. {_describe(f)}" for i, f in enumerate(failures, 1))
    return (
        "You are editing a finished answer. Apply only the corrections listed and "
        "change nothing else.\n\n"
        f"[OBJECTIVE]\n{objective.strip()}\n\n"
        f"[ANSWER]\n{text.strip()}\n\n"
        f"[CORRECTIONS REQUIRED]\n{numbered}\n\n"
        "Rules: do not add any fact, figure or claim that is not already in the "
        "answer above; do not remove any fact that is not named in a correction; "
        "keep the wording wherever a correction does not require changing it. "
        "Return the corrected answer alone, with no preamble and no commentary."
    )


def _introduces_a_figure(revision: str, original: str, allowed: Sequence[float]) -> bool:
    """Did the revision state a number the data does not support?

    Checked against the allowed set rather than against the original, because an
    editor asked to "mention the total" can compute a legitimate aggregate -- and
    :func:`check_numeric_fidelity` already knows which aggregates are legitimate.
    A revision that fails it while the original passed is a fabrication
    introduced by the repair, which is the one failure mode that would make the
    editor worse than useless.
    """
    if not allowed:
        return False
    before = check_numeric_fidelity(original, allowed)
    after = check_numeric_fidelity(revision, allowed)
    return after is False and before is not False


def edit_assembled(
    text: str,
    constraints: Sequence[Mapping[str, Any]],
    backend: Any,
    objective: str = "",
    numeric_allowed: Sequence[float] = (),
    max_tokens: int = 512,
    max_rounds: int = 1,
) -> EditorReport:
    """Repair the mechanically-checkable defects of an assembled answer.

    Args:
        text: The assembled answer.
        constraints: The prompt's constraint specs, as read by
            :mod:`swarmbly_v0.constraints`.
        backend: Used for the single repair generation.
        objective: One line naming what the answer is for.
        numeric_allowed: Figures the answer may legitimately state. Supplying
            this arms the fabrication guard; omitting it disarms it, so grounded
            prompts must pass it.
        max_tokens: Budget for the revision.
        max_rounds: Repair attempts. One by default: a second round on the same
            defect list is usually the model failing to follow the instruction,
            not needing another go, and every round is a real cost.

    Returns:
        An :class:`EditorReport`. When nothing was applied, ``text`` is the
        input unchanged -- the caller can always use the returned text and never
        has to branch on ``applied``.
    """
    if not constraints:
        return EditorReport(text=text, applied=False, reason="no constraints to check")

    report: CompositionReport = grade_text(text, constraints)
    if not report.failed:
        return EditorReport(text=text, applied=False, reason="nothing failed",
                            score_before=report.score, score_after=report.score)

    current, current_report = text, report
    total_in = total_out = calls = 0
    reason = "no revision improved the score"

    for _ in range(max(1, int(max_rounds))):
        prompt = _build_prompt(current, current_report.failed, objective)
        total_in += count_tokens(prompt)
        calls += 1
        try:
            revision = (backend.generate(prompt, max_tokens=max_tokens) or "").strip()
        except Exception:  # a failed repair must never lose the answer
            reason = "the repair call failed"
            break
        total_out += count_tokens(revision)

        if not revision or not paragraphs_of(revision):
            reason = "the revision was empty"
            break
        if _introduces_a_figure(revision, current, numeric_allowed):
            reason = "the revision introduced an unsupported figure"
            break

        revised_report = grade_text(revision, constraints)
        # The gate the bridge never had. Equal is accepted: an edit that fixes
        # one defect and creates another has not earned the swap, but one that
        # holds the score while removing a duplicate has.
        if revised_report.n_satisfied < current_report.n_satisfied:
            reason = "the revision scored worse and was rejected"
            break

        improved = revised_report.n_satisfied > current_report.n_satisfied
        current, current_report = revision, revised_report
        reason = "applied" if improved else "applied without gain"
        if not revised_report.failed:
            break

    applied = current is not text
    return EditorReport(
        text=current,
        applied=applied,
        reason=reason,
        score_before=report.score,
        score_after=current_report.score,
        violations_before=tuple(r.constraint_id for r in report.failed),
        violations_after=tuple(r.constraint_id for r in current_report.failed),
        input_tokens=total_in,
        output_tokens=total_out,
        calls=calls,
    )
