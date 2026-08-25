"""Mechanical checks on a generated text -- ground truth for prose.

Why this exists
---------------

Everything V3c has measured so far is item-level: a number, a date, a city name.
That was the right place to start, because a key can be written down and a
comparator has no opinions. But it is not the workload the protocol is for. The
architecture is pitched on assembling *prose* from fragments, and prose has no
answer key.

It does, however, have checkable properties. A prompt can demand two paragraphs
of ninety to a hundred and twenty words each, mentioning three named things,
avoiding one, and repeating nothing. Those are facts about a string, decidable
by counting, and they do not need a judge any more than ``42`` did.

What the constraints are chosen to catch
----------------------------------------

Not style. Constraints that measure taste would reintroduce the judge this whole
apparatus exists to remove. Each check here corresponds to a way that *assembly
from fragments* specifically fails, which is what makes them evidence about the
architecture rather than about the models:

* ``must_mention`` / ``must_not_mention`` -- a fragment that never saw the
  contract drops the thing the contract required, or smuggles in the thing it
  forbade. This is coverage.

* ``paragraph_count`` and ``words_per_paragraph`` -- a splice of two fragments
  that each wrote a full answer produces four paragraphs, not two, and a
  fragment that got a thin packet produces forty words instead of a hundred.
  This is the shape of the seam.

* ``term_once`` and ``no_repeated_sentence`` and ``no_repeated_ngram`` -- the
  classic failure. Two workers each introduce the topic, each define the same
  term, each conclude. Monolithic generation almost never repeats itself;
  assembled generation does it constantly, and a coherence score computed on
  sentence transitions can miss it entirely because each repetition is locally
  fluent. **This is the check the coherence tax cannot make**, and on the
  evidence of 24 August -- tax +39.8 % while item accuracy said nothing at all
  about correctness -- it is the one worth having.

Every check returns a verdict *and* the number behind it, so a failure can be
read rather than merely counted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .grading import normalise_text
from .textutil import count_tokens, split_sentences

__all__ = [
    "CONSTRAINT_KINDS",
    "check_numeric_fidelity",
    "derived_aggregates",
    "asserts_an_aggregate",
    "is_source_table_row",
    "ConstraintResult",
    "CompositionReport",
    "paragraphs_of",
    "check_constraint",
    "grade_text",
]

CONSTRAINT_KINDS = (
    "must_mention",
    "must_not_mention",
    "paragraph_count",
    "words_per_paragraph",
    "term_once",
    "no_repeated_sentence",
    "no_repeated_ngram",
)

_PARA_SPLIT = re.compile(r"\n\s*\n+")


@dataclass(frozen=True)
class ConstraintResult:
    """One constraint, checked."""

    constraint_id: str
    kind: str
    satisfied: bool
    observed: Any
    expected: Any
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "kind": self.kind,
            "satisfied": self.satisfied,
            "observed": self.observed,
            "expected": self.expected,
            "detail": self.detail,
        }


@dataclass
class CompositionReport:
    """Every constraint on one text, plus the counts a reader needs."""

    results: list[ConstraintResult]
    n_paragraphs: int = 0
    n_sentences: int = 0
    n_tokens: int = 0

    @property
    def n_satisfied(self) -> int:
        return sum(1 for r in self.results if r.satisfied)

    @property
    def score(self) -> float | None:
        """Share of constraints satisfied, or ``None`` when there are none.

        ``None`` rather than 1.0: a text checked against nothing has not passed,
        it has not been checked.
        """
        return (self.n_satisfied / len(self.results)) if self.results else None

    @property
    def failed(self) -> list[ConstraintResult]:
        return [r for r in self.results if not r.satisfied]

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_constraints": len(self.results),
            "n_satisfied": self.n_satisfied,
            "score": round(self.score, 6) if self.score is not None else None,
            "n_paragraphs": self.n_paragraphs,
            "n_sentences": self.n_sentences,
            "n_tokens": self.n_tokens,
            "failed": [r.constraint_id for r in self.failed],
            "results": [r.as_dict() for r in self.results],
        }


def paragraphs_of(text: str) -> list[str]:
    """Non-empty paragraphs, split on blank lines.

    A model that separates paragraphs with a single newline is treated as having
    written one paragraph, which is what a reader would say too.
    """
    return [p.strip() for p in _PARA_SPLIT.split(text or "") if p.strip()]


def _ngrams(tokens: Sequence[str], size: int) -> list[tuple[str, ...]]:
    return [tuple(tokens[i:i + size]) for i in range(max(0, len(tokens) - size + 1))]


def check_constraint(text: str, spec: Mapping[str, Any]) -> ConstraintResult:
    """Check one constraint against ``text``.

    Args:
        text: The candidate composition.
        spec: ``{"id": ..., "kind": ..., ...}`` with kind-specific fields.

    Raises:
        ValueError: On an unknown kind. Skipping an unrecognised constraint
            would quietly raise every score that contained one.
    """
    kind = str(spec.get("kind", ""))
    cid = str(spec.get("id", kind))
    if kind not in CONSTRAINT_KINDS:
        raise ValueError(f"unknown constraint kind {kind!r}; expected one of {CONSTRAINT_KINDS}")

    normalised = normalise_text(text)
    paras = paragraphs_of(text)

    if kind == "must_mention":
        term = str(spec["term"])
        ok = normalise_text(term) in normalised
        return ConstraintResult(cid, kind, ok, ok, True, f"term={term!r}")

    if kind == "must_not_mention":
        term = str(spec["term"])
        ok = normalise_text(term) not in normalised
        return ConstraintResult(cid, kind, ok, not ok, False, f"term={term!r}")

    if kind == "paragraph_count":
        want = int(spec["count"])
        return ConstraintResult(cid, kind, len(paras) == want, len(paras), want)

    if kind == "words_per_paragraph":
        lo, hi = int(spec["min"]), int(spec["max"])
        counts = [count_tokens(p) for p in paras]
        ok = bool(counts) and all(lo <= c <= hi for c in counts)
        return ConstraintResult(cid, kind, ok, counts, [lo, hi])

    if kind == "term_once":
        # Duplication across fragments is the signature failure of assembly:
        # two workers each define the same term, and each definition is locally
        # fluent, so a transition-based coherence score sees nothing wrong.
        term = normalise_text(str(spec["term"]))
        seen = len(_ngrams(normalised.split(), len(term.split()))) and sum(
            1 for g in _ngrams(normalised.split(), len(term.split())) if " ".join(g) == term
        )
        return ConstraintResult(cid, kind, seen == 1, seen, 1, f"term={spec['term']!r}")

    if kind == "no_repeated_sentence":
        sentences = [normalise_text(s) for s in split_sentences(text) if s.strip()]
        counts: dict[str, int] = {}
        for s in sentences:
            if s:
                counts[s] = counts.get(s, 0) + 1
        repeats = sorted(s for s, n in counts.items() if n > 1)
        return ConstraintResult(cid, kind, not repeats, len(repeats), 0,
                                f"repeated={repeats[:2]}" if repeats else "")

    size = int(spec.get("size", 8))
    tokens = normalised.split()
    counts = {}
    for gram in _ngrams(tokens, size):
        counts[gram] = counts.get(gram, 0) + 1
    repeats = [g for g, n in counts.items() if n > 1]
    return ConstraintResult(cid, kind, not repeats, len(repeats), 0,
                            f"first={' '.join(repeats[0])!r}" if repeats else "")


def grade_text(text: str, constraints: Iterable[Mapping[str, Any]]) -> CompositionReport:
    """Check every constraint and report the counts behind the score."""
    results = [check_constraint(text, spec) for spec in constraints]
    paras = paragraphs_of(text)
    return CompositionReport(
        results=results,
        n_paragraphs=len(paras),
        n_sentences=len([s for s in split_sentences(text) if s.strip()]),
        n_tokens=count_tokens(text),
    )


# --------------------------------------------------------------------------- #
# numeric fidelity: per-sentence ground truth for grounded prose
# --------------------------------------------------------------------------- #

_NUM = re.compile(r"(?<![A-Za-z0-9])-?\d[\d,]*(?:\.\d+)?(?![A-Za-z0-9])")
"""A figure, and not the digits inside an identifier.

The lookarounds are the whole point. Without them ``G4667`` -- a reference code
copied correctly out of the very table the summary was given -- yields the
"figure" 4667, which appears in no row and in no aggregate, so the sentence is
scored a fabrication. In the run of 24 August this hit 31 of the 62 graded
grounded-prose units and drove that corpus to an accuracy of 1.6 %, which then
inverted its AUC to 0.21. Reference codes are the one thing a summary of a
manifest is most likely to quote.
"""

_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")

_AGGREGATE_RE = re.compile(
    r"\b(total|totals|totalling|sum|summed|altogether|combined|aggregate|"
    r"heaviest|lightest|largest|smallest|highest|lowest|maximum|minimum|"
    r"average|averages|mean|median|overall|in all|across all|every consignment)\b",
    re.IGNORECASE,
)


def asserts_an_aggregate(text: str) -> bool:
    """Does this claim require sight of rows the fragment may not hold?

    The distinction V4 found and could not act on. Splitting graded table-summary
    units by whether they assert a total, an average or an extreme gave 47.7 %
    wrong against 31.7 % for claims about the rows in front of the worker --
    Fisher exact p = 0.014 over 256 units. A worker asked for the total while
    holding a third of the table does not decline; it invents one, and the
    inventions are not subtle: "a total weight of 1650 kg" over twenty rows one
    of which weighs 935.

    Why this belongs in the codebase rather than in an analysis script: six
    attempts to calibrate the confidence map failed because the predictor
    saturated -- 0.85 to 0.96 agreement with almost no spread, so nothing could
    discriminate. This is the first split where the two classes demonstrably
    differ in *correctness*, which is the other half a calibration needs. Marking
    it per record lets the calibration be computed within each class instead of
    across a mixture, which is the pooling error that has produced a wrong
    headline three times in this project.

    Deliberately lexical. A classifier here would need its own validation and
    would put a model back inside the measurement, which is what the mechanical
    graders exist to avoid.
    """
    return bool(_AGGREGATE_RE.search(text or ""))


def is_source_table_row(text: str) -> bool:
    """Is this unit a row of the input table rather than a sentence about it?

    A model handed a table and asked for prose sometimes reproduces the table.
    That is a real failure and worth counting -- but it is a failure of
    *instruction-following*, not of numeric fidelity: the figures in a copied row
    are, by construction, exactly the given ones. Grading such a row on fidelity
    puts the wrong name on the defect and, worse, pollutes the only corpus in
    this run where agreement and correctness were both supposed to vary.

    In the run of 24 August, 47 of 62 graded grounded-prose units were table
    rows. They are excluded from the fidelity records and counted separately, so
    the number that disappears from the accuracy reappears as a named behaviour.
    """
    return bool(_TABLE_ROW.match(text or ""))


def derived_aggregates(values: Sequence[float]) -> set[float]:
    """Figures a summary may legitimately state that are not rows in the table.

    A summary of a table is allowed to total it, count it, and name its
    extremes; that is what summarising *is*. Without this set every correct
    aggregate would be scored as a fabrication, which is the same class of error
    -- a right answer graded wrong -- that has cost this project most.
    """
    if not values:
        return set()
    total = float(sum(values))
    out = {total, float(len(values)), float(max(values)), float(min(values))}
    mean = total / len(values)
    out.update({mean, round(mean, 1), round(mean), float(int(mean))})
    return out


def check_numeric_fidelity(text: str, allowed: Sequence[float]) -> bool | None:
    """Does every figure in ``text`` come from the data it was given?

    The per-sentence ground truth that grounded prose makes possible, and the
    reason this corpus exists. Item corpora gave correctness with no spread in
    agreement; compositions gave spread in agreement with no correctness at the
    unit level. A sentence summarising an enclosed table has both: its agreement
    is scored by consensus, and its figures either appear in the table -- or are
    an aggregate of it -- or were invented.

    Returns ``None`` for a sentence containing no figure at all. Such a sentence
    is not correct or incorrect on this measure; counting it either way would
    silently move the accuracy toward whichever verdict was chosen.
    """
    found = [
        float(m.group(0).replace(",", ""))
        for m in _NUM.finditer(text or "")
    ]
    if not found:
        return None
    permitted = {round(float(v), 4) for v in allowed}
    return all(round(v, 4) in permitted for v in found)
