"""Deterministic grading of answers against a key -- the instrument V3c needs.

Why this module exists
---------------------

The first agreement calibration (Section 11.3) reported ``r = -0.030`` between
per-unit agreement and judged acceptability, and could not interpret it. The
judge accepted **93.3 %** of everything it saw, so the dependent variable had
almost no variance; a real signal could have been present and undetectable. The
honest statement was that the confidence map is *unsupported, not refuted*, and
the whitepaper's Section 11.4 already specified the fix: run the calibration
against **ground truth** rather than against a peer-class judge.

Ground truth means a verdict that does not come from a model. That is what this
module is: a parser and a comparator, no embeddings, no generation, no judge. It
is deliberately dull. The value of a measuring instrument is that it does not
have opinions.

The contract with the corpus
----------------------------

A ground-truth prompt asks for one answer per item, each on its own line, keyed
by a two-digit label the prompt supplies:

    [07] 42

The key then maps ``"07" -> "42"`` plus a match mode. Everything downstream is
mechanical. Three consequences worth stating plainly:

* **A unit may carry several items.** Consensus segments text into semantic
  units without knowing about items, so one unit can hold two answers. Grading
  therefore emits one record per *item occurrence*, each carrying the agreement
  of the unit it appeared in. Items are the observations; agreement is the
  predictor. Collapsing several items into one unit-level verdict would throw
  away exactly the resolution this experiment needs.

* **Non-compliant output is counted, not discarded.** A unit with no parsable
  item label is recorded as ungraded and reported. A model that ignores the
  output format is a real result about small models, and hiding it would inflate
  the accuracy of whatever remains.

* **Duplicate answers to one item are kept.** If a replica answers item 07
  twice, both occurrences are graded. Silently keeping the first would let a
  model launder a wrong answer by repeating itself.

What this module refuses to do
------------------------------

It does not judge partial credit, and it does not paraphrase-match. Both would
reintroduce a model, or a threshold set by taste, into the position the judge
just vacated. The corpus is built so that a correct answer is a short canonical
string; if an item cannot be graded by normalised comparison, it does not
belong in a ground-truth corpus.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "ITEM_LABEL_RE",
    "MATCH_MODES",
    "GradedItem",
    "GradeReport",
    "normalise_text",
    "extract_items",
    "grade_answer",
    "grade_unit",
    "grade_units",
    "is_echo",
]


# ``[07]`` at a line start, or inline after whitespace. Tolerant of ``(07)`` and
# ``07.`` because small models substitute bracket styles freely, and the label
# style is not what is under test.
ITEM_LABEL_RE = re.compile(r"(?:^|[\s>*\-])[\[\(]?(\d{1,3})[\]\).:]\s*", re.MULTILINE)

MATCH_MODES = ("exact_norm", "numeric", "date_iso", "boolean")

_TRUE_WORDS = {"true", "yes", "y", "t", "si", "s", "verdadero", "cierto", "1"}
_FALSE_WORDS = {"false", "no", "n", "f", "falso", "incorrecto", "0"}

_PUNCT_RE = re.compile(r"[^\w\s.\-/]", re.UNICODE)
_WS_RE = re.compile(r"\s+")
_NUM_RE = re.compile(r"-?\d[\d,._ ]*\d|-?\d")
_ISO_RE = re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})")


def normalise_text(value: str) -> str:
    """Fold a string to the form comparisons are made in.

    Unicode-normalise, strip accents, lowercase, drop punctuation that carries
    no meaning here, collapse whitespace. Kept narrow on purpose: this removes
    typography, not content. ``"42 units"`` and ``"42"`` stay different, because
    an item whose answer is ambiguous between those two is a badly written item.
    """
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    text = _PUNCT_RE.sub(" ", text.lower())
    return _WS_RE.sub(" ", text).strip()


def _as_number(value: str) -> float | None:
    """Last number in ``value``, or ``None``.

    The *last* number, not the first: a model that shows its work ends on the
    answer ("3 boxes times 14 is 42"). Taking the first would grade the working.
    """
    matches = _NUM_RE.findall(str(value))
    if not matches:
        return None
    raw = matches[-1].replace(",", "").replace(" ", "").replace("_", "")
    # A trailing dot is sentence punctuation, not a decimal point.
    raw = raw.rstrip(".")
    try:
        return float(raw)
    except ValueError:
        return None


def _as_iso_date(value: str) -> str | None:
    m = _ISO_RE.search(str(value))
    if not m:
        return None
    year, month, day = (int(g) for g in m.groups())
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def _as_boolean(value: str) -> bool | None:
    words = normalise_text(value).split()
    for word in words:
        if word in _TRUE_WORDS:
            return True
        if word in _FALSE_WORDS:
            return False
    return None


ECHO_COVERAGE = 0.70
"""Share of the item's content words an answer must repeat to count as an echo."""

ECHO_MIN_TOKENS = 6
"""Below this an answer is too short to be a restatement, whatever it covers."""


def is_echo(given: str, source: str) -> bool:
    """Is ``given`` a restatement of the item rather than an answer to it?

    In the run of 24 August a model answered item 01 with *"37 crates of pump
    seals, 17 units per crate, 68 units removed for inspection"* -- the question,
    copied back. Numeric grading then took the last number it found, 68, compared
    it to the expected 561, and scored the item **wrong**. It is not wrong. It is
    unanswered, and the difference matters twice over: it deflates accuracy, and
    it fills the error class that the flagging metric is trying to catch with
    items that were never attempted.

    The test is coverage, not containment. A correct answer is often a *piece* of
    the item -- ``Osaka`` appears verbatim in the record it was extracted from --
    so a substring test would flag the right answers as echoes. A restatement is
    different in kind: it repeats most of the item's content words and adds
    nothing. Short answers are exempt outright, since a handful of tokens cannot
    be a restatement of anything.

    Args:
        given: The model's text for this item.
        source: The item's line as it appeared in the prompt.

    Returns:
        ``True`` when the answer covers at least :data:`ECHO_COVERAGE` of the
        item's content words and is at least :data:`ECHO_MIN_TOKENS` long.
        ``False`` whenever ``source`` is absent -- an unverifiable suspicion is
        not grounds for discarding an observation.
    """
    if not source or not given:
        return False
    given_tokens = normalise_text(given).split()
    if len(given_tokens) < ECHO_MIN_TOKENS:
        return False
    source_tokens = set(normalise_text(source).split())
    if not source_tokens:
        return False
    covered = len(source_tokens & set(given_tokens)) / len(source_tokens)
    return covered >= ECHO_COVERAGE


def grade_answer(given: str, expected: str, mode: str = "exact_norm") -> bool | None:
    """Is ``given`` the answer ``expected``, under ``mode``?

    Returns ``None`` -- not ``False`` -- when the answer cannot be interpreted
    at all in the mode's terms: no number where a number was required, no
    parsable date, no yes/no token. That distinction matters. "Wrong" and
    "unintelligible" are different failures, and folding the second into the
    first would let a model that produced prose instead of an answer count as
    merely incorrect, quietly flattering the accuracy of everything else.

    Args:
        given: The model's text for this item.
        expected: The canonical answer from the key.
        mode: One of :data:`MATCH_MODES`.

    Raises:
        ValueError: On an unknown mode. A silent fallback to string comparison
            would grade numeric items by their formatting.
    """
    if mode not in MATCH_MODES:
        raise ValueError(f"unknown match mode {mode!r}; expected one of {MATCH_MODES}")

    if mode == "numeric":
        got, want = _as_number(given), _as_number(expected)
        if got is None or want is None:
            return None
        tolerance = max(abs(want) * 1e-6, 1e-9)
        return abs(got - want) <= tolerance

    if mode == "date_iso":
        got, want = _as_iso_date(given), _as_iso_date(expected)
        if got is None or want is None:
            return None
        return got == want

    if mode == "boolean":
        got, want = _as_boolean(given), _as_boolean(expected)
        if got is None or want is None:
            return None
        return got == want

    got_n, want_n = normalise_text(given), normalise_text(expected)
    if not got_n:
        return None
    return got_n == want_n


def extract_items(text: str) -> list[tuple[str, str]]:
    """Split ``text`` into ``(item_id, answer_text)`` pairs, in order.

    An item's answer runs from its label to the next label or the end of the
    text. Text before the first label is discarded: it is a preamble, not an
    answer. Item ids keep their zero padding normalised to two digits so that
    ``[7]`` and ``[07]`` are the same item.
    """
    matches = list(ITEM_LABEL_RE.finditer(text or ""))
    out: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        # Trailing bullet or quote markers belong to the *next* item's label,
        # which the pattern consumes as a prefix; leaving them in would make
        # "Lisbon" and "Lisbon -" different answers.
        answer = text[m.end():end].strip().rstrip("-*>\u2022\u00b7 \t\n\r")
        item_id = m.group(1).lstrip("0") or "0"
        out.append((item_id.zfill(2), answer))
    return out


@dataclass(frozen=True)
class GradedItem:
    """One item occurrence, graded."""

    item_id: str
    given: str
    expected: str
    mode: str
    correct: bool | None      # None => the answer was unintelligible in this mode
    unknown_item: bool = False   # a label the key does not contain
    echoed: bool = False         # the item restated instead of answered

    @property
    def graded(self) -> bool:
        return self.correct is not None and not self.unknown_item


@dataclass
class GradeReport:
    """Grading outcome for a batch of units, with everything that was skipped."""

    items: list[GradedItem] = field(default_factory=list)
    units_total: int = 0
    units_with_no_label: int = 0

    @property
    def graded_items(self) -> list[GradedItem]:
        return [i for i in self.items if i.graded]

    @property
    def n_graded(self) -> int:
        return len(self.graded_items)

    @property
    def n_correct(self) -> int:
        return sum(1 for i in self.graded_items if i.correct)

    @property
    def n_unintelligible(self) -> int:
        return sum(1 for i in self.items if i.correct is None and not i.unknown_item)

    @property
    def n_echoed(self) -> int:
        """Items restated rather than answered -- a subset of the unintelligible."""
        return sum(1 for i in self.items if i.echoed)

    @property
    def n_unknown_item(self) -> int:
        return sum(1 for i in self.items if i.unknown_item)

    @property
    def accuracy(self) -> float | None:
        """Share of graded items that are correct, or ``None`` if none were.

        Reported alongside :attr:`n_unintelligible` and
        :attr:`units_with_no_label`, never alone. An accuracy computed over the
        subset a model happened to format correctly is not the model's accuracy.
        """
        return (self.n_correct / self.n_graded) if self.n_graded else None

    def as_dict(self) -> dict[str, Any]:
        return {
            "units_total": self.units_total,
            "units_with_no_label": self.units_with_no_label,
            "items_seen": len(self.items),
            "items_graded": self.n_graded,
            "items_correct": self.n_correct,
            "items_unintelligible": self.n_unintelligible,
            "items_echoed": self.n_echoed,
            "items_unknown_id": self.n_unknown_item,
            "accuracy": round(self.accuracy, 6) if self.accuracy is not None else None,
        }


def grade_unit(
    text: str,
    key: Mapping[str, Mapping[str, str] | str],
    default_mode: str = "exact_norm",
) -> list[GradedItem]:
    """Grade every item occurrence inside one unit of text.

    Args:
        text: The unit's text, as produced by consensus or by a single replica.
        key: ``{item_id: expected}`` or ``{item_id: {"expected": ..., "mode": ...}}``.
        default_mode: Mode for entries given as a bare string.
    """
    graded: list[GradedItem] = []
    for item_id, answer in extract_items(text):
        entry = key.get(item_id)
        if entry is None:
            graded.append(GradedItem(item_id, answer, "", default_mode, None, unknown_item=True))
            continue
        if isinstance(entry, str):
            expected, mode, source = entry, default_mode, ""
        else:
            expected = str(entry.get("expected", ""))
            mode = str(entry.get("mode", default_mode))
            source = str(entry.get("source", ""))
        if is_echo(answer, source):
            # Unanswered, not wrong. See is_echo.
            graded.append(GradedItem(item_id, answer, expected, mode, None, echoed=True))
            continue
        graded.append(GradedItem(item_id, answer, expected, mode, grade_answer(answer, expected, mode)))
    return graded


def grade_units(
    units: Iterable[Any],
    key: Mapping[str, Mapping[str, str] | str],
    default_mode: str = "exact_norm",
) -> tuple[list[dict[str, Any]], GradeReport]:
    """Grade a sequence of units, returning long-format records and a report.

    Each record carries the unit's ``agreement`` next to the item's ``correct``,
    which is the pair the V3c calibration correlates. ``units`` may hold
    :class:`~swarmbly_v0.consensus.ConsensusUnit` objects or any object exposing
    ``text``, ``agreement``, ``label``, ``judge_score`` and ``accepted``; plain
    strings are accepted too, and get no agreement.

    Returns:
        ``(records, report)``. The report is not optional decoration: it holds
        the denominators without which the records cannot be honestly read.
    """
    records: list[dict[str, Any]] = []
    report = GradeReport()

    for index, unit in enumerate(units):
        report.units_total += 1
        text = unit if isinstance(unit, str) else getattr(unit, "text", "")
        graded = grade_unit(text, key, default_mode)
        if not graded:
            report.units_with_no_label += 1
            continue
        for item in graded:
            report.items.append(item)
            records.append({
                "unit_index": index,
                "item_id": item.item_id,
                "label": "" if isinstance(unit, str) else getattr(unit, "label", ""),
                "agreement": (
                    None if isinstance(unit, str)
                    else round(float(getattr(unit, "agreement", 0.0)), 6)
                ),
                "judge_score": (
                    None if isinstance(unit, str)
                    else round(float(getattr(unit, "judge_score", 0.0)), 6)
                ),
                # The judge's verdict, kept next to the truth so the two can be
                # compared. Quantifying how far the judge was from ground truth
                # is the other thing this experiment settles.
                "accepted": None if isinstance(unit, str) else bool(getattr(unit, "accepted", False)),
                "mode": item.mode,
                "expected": item.expected,
                "given": item.given[:200],
                "correct": item.correct,
                "graded": item.graded,
                "unknown_item": item.unknown_item,
                "echoed": item.echoed,
            })

    return records, report
