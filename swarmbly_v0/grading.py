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
from typing import Any, Iterable, Mapping

__all__ = [
    "ITEM_LABEL_RE",
    "MATCH_MODES",
    "GradedItem",
    "GradeReport",
    "normalise_text",
    "content_tokens",
    "extract_items",
    "grade_answer",
    "grade_unit",
    "grade_units",
    "is_echo",
    "returns_input_value",
]


# ``[07]`` at a line start, or inline after whitespace. Tolerant of ``(07)`` and
# ``07.`` because small models substitute bracket styles freely, and the label
# style is not what is under test.
#
# The bracketed forms may be followed by anything. The BARE form -- ``07.`` or
# ``07:`` with no bracket -- must be followed by whitespace or the end of the
# line, and that is not cosmetic. Written with ``\s*`` the pattern read the
# decimal point of a number as a label terminator, so ``[05] 42500 m is 42.5 km``
# parsed as item 05 with the answer "42500 m is", plus a phantom item 42 with the
# answer "5 km". The real answer, 42.5, was correct and was recorded as never
# attempted -- it left the accuracy denominator and landed in ``items_echoed``,
# the statistic used to argue that fragmented workers restate their inputs
# instead of answering.
#
# 20 of the 150 items in prompts/ground_truth.json have decimal answers, and the
# failure is verbosity-dependent: a bare ``[05] 42.5`` was safe, anything with a
# word before the decimal was not. Since verbosity is the documented difference
# between the arms, that made it a candidate arm asymmetry rather than noise.
ITEM_LABEL_RE = re.compile(
    r"(?:^|[\s>*\-])(?:[\[(](\d{1,3})[\])]|(\d{1,3})[.:](?=\s|$))[\s]*",
    re.MULTILINE)

MATCH_MODES = ("exact_norm", "numeric", "date_iso", "boolean", "any_of")

ANY_OF_SEPARATOR = "|"
"""Separates the accepted phrasings in an ``any_of`` key entry."""

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


_TOKEN_EDGE = ".,;:!?"


def content_tokens(value: str) -> list[str]:
    """:func:`normalise_text`, split into tokens, with sentence punctuation off.

    Every token-sequence comparison in this project must go through here, and the
    reason is a defect that appeared independently in four places.

    ``normalise_text`` deliberately keeps ``.`` -- it has to, or ``42.5`` folds to
    ``425`` and numeric grading breaks. But the checks built on top of it compare
    whitespace-split tokens, and a word that ends a sentence carries the stop
    with it. ``window.`` never equals ``window``. So:

    * ``term_once`` counted one occurrence of two where the first ended a
      sentence, and failed a single correct mention that ended one;
    * ``no_repeated_ngram`` could not see a repeated phrase whose first
      occurrence ended a sentence -- under-detection of exactly the cross-fragment
      duplication the composition corpus exists to measure;
    * ``any_of`` scored "251 kg is under." wrong and "251 kg is under the limit"
      right, on the same claim;
    * ``boolean`` returned ``None`` for "the consignment was cleared: no.",
      dropping a correct answer out of the accuracy denominator entirely and into
      ``items_unintelligible``.

    None of these is symmetric noise. Sentence-final position correlates with
    terse answers, and terseness is the documented difference between the arms --
    the monolithic baseline is the arm that writes prose, and on a non-enumerated
    prompt it is the only one not handed ``BASELINE_FORMAT_DIRECTIVE``. So the
    error is an arm asymmetry, not a wash.

    ``_as_number`` already did this (it strips a trailing dot before ``float``),
    which is the tell: the class was known and fixed in one place out of five.
    """
    return [t.strip(_TOKEN_EDGE) for t in normalise_text(value).split() if t.strip(_TOKEN_EDGE)]


_NEGATORS = frozenset({
    "not", "no", "never", "isnt", "arent", "wasnt", "werent",
    "doesnt", "dont", "didnt", "cannot", "cant", "without", "neither", "nor",
})
"""Words that invert the alternative immediately after them.

Needed because ``any_of`` keys in this corpus come in antonym pairs -- the
``under`` set and the ``over`` set -- and one member is a substring of a phrasing
of the other. Without this guard, "not over the limit" would satisfy a key
expecting ``over``, which is the single most damaging kind of grading error:
a wrong answer scored right.
"""


def _contains_accepted_phrase(got_n: str, accepted: set[str]) -> bool:
    """Does the answer *state* one of the accepted alternatives?

    Why this exists at all
    ----------------------

    ``any_of`` originally required the whole normalised answer to equal one of
    the alternatives. That is correct only when every condition in the run is
    told to answer tersely, and in the run of 24 August only the fragmented
    condition was: its packets carry a format directive, the monolithic baseline
    does not. So the baseline answered "pallet R752, 251 kg under" -- the right
    verdict, stated in a sentence -- and was graded wrong, fifty times out of
    fifty. The baseline scored 0 % against a fragmented condition scoring 66 %,
    and the comparison the whole experiment exists to make came out *inverted*.

    A right answer graded wrong is the error that has cost this project most, and
    an error that lands on one condition only is worse than noise: it is a
    result. So the comparison is loosened, but not to substring matching, which
    would trade this failure for the opposite one --

    Rules, in order:

    * whole *token* sequences only, so ``over`` does not match inside ``overdue``
      and ``no`` does not match inside ``nothing``;
    * longest alternative first, so ``not over`` is tried before ``over`` and
      wins the position it occupies;
    * an alternative immediately preceded by a negator does not count, unless
      the alternative itself begins with that negator.

    What this deliberately does not do is judge. It asks whether the answer
    contains the accepted phrase as a phrase; it has no opinion about the rest of
    the sentence, and an answer that states both members of an antonym pair
    ("not under -- over") is scored on the one that is not negated.
    """
    # Through ``content_tokens``, not ``.split()``: a phrase that ends the
    # sentence carries the stop into its last token, and "is under." would not
    # match the accepted ``under``. See ``content_tokens``.
    tokens = content_tokens(got_n)
    if not tokens:
        return False
    for alternative in sorted(accepted, key=len, reverse=True):
        want = content_tokens(alternative)
        if not want:
            continue
        span = len(want)
        for i in range(len(tokens) - span + 1):
            if tokens[i:i + span] != want:
                continue
            negated = i > 0 and tokens[i - 1] in _NEGATORS and want[0] not in _NEGATORS
            if not negated:
                return True
    return False


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
    # ``content_tokens``, so that a boolean stated at the end of a sentence --
    # "the consignment was cleared: no." -- is read. Under ``.split()`` the token
    # was ``no.``, no word matched, the function returned ``None``, and a correct
    # answer left the accuracy denominator for ``items_unintelligible``.
    for word in content_tokens(value):
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


def returns_input_value(given: str, source: str, expected: str) -> bool:
    """Did the model hand back one of the item's own numbers instead of a result?

    The short cousin of :func:`is_echo`, and the one that cost the most. On 24
    August a worker answered ``[05] 30000 m`` to an item whose source line was
    ``[05] 30000 m`` and whose answer was ``30``: it restated the input rather
    than converting it. Two tokens is far below the length at which
    :func:`is_echo` will call something a restatement, so the item was graded
    **wrong**, and ``unit_conversion`` came back at 3.5 % against 80 %
    unfragmented.

    Numeric only, and deliberately narrow: the value must appear in the item and
    must differ from the expected answer. When the two coincide -- an item whose
    result happens to equal one of its inputs -- the answer is simply correct and
    is left alone.

    **The answer must state exactly one number.** That guard is the difference
    between "handed back an input" and "did the arithmetic and got it wrong", and
    without it the second was being counted as the first. On the v3c-gt run the
    two-step arithmetic items came back as ``21 - 80`` against a key of ``256``:
    the item's outer operands with the multiplication dropped, which is a wrong
    attempt at the task and nothing else. ``_as_number`` takes the LAST number of
    an answer, so the value this function tested was ``80`` -- one of the item's
    own inputs -- and every such attempt was recorded ``correct=None``,
    ``echoed=True``: removed from the accuracy denominator as a non-attempt.

    That is the error class this project has already withdrawn results for twice,
    arriving through the guard built to prevent it. An answer holding two numbers
    and an operator has *attempted* the item; a restatement hands back the value
    and stops. So a multi-number answer is graded -- wrong, if it is wrong --
    while ``[05] 30000 m`` against an item reading ``[05] 30000 m`` still fires,
    because it states one number and that number is the input.

    The direction matters and is worth stating: this makes reported accuracy
    *lower*, because every item it restores to the denominator is one the model
    got wrong.
    """
    if not source:
        return False
    stated = [n for n in (_as_number(token) for token in _NUM_RE.findall(str(given)))
              if n is not None]
    if len(stated) != 1:
        return False
    got = stated[0]
    want = _as_number(expected)
    if got is None or want is None or abs(got - want) <= max(abs(want) * 1e-6, 1e-9):
        return False
    source_numbers = {
        n for n in (_as_number(tok) for tok in _NUM_RE.findall(source)) if n is not None
    }
    return any(abs(got - n) <= max(abs(n) * 1e-6, 1e-9) for n in source_numbers)


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

    if mode == "any_of":
        # Several phrasings, all correct. This is the mode the confidence map
        # actually needs: where a correct answer can be *said differently*,
        # independent models stop emitting identical strings and the agreement
        # score has something to measure. On the canonical-answer corpus of
        # 24 August, 260 of 280 items came back at agreement exactly 1.0 -- not
        # because the models were confident but because "30" has one spelling.
        got_n = normalise_text(given)
        if not got_n:
            return None
        accepted = {
            normalise_text(part)
            for part in str(expected).split(ANY_OF_SEPARATOR)
            if part.strip()
        }
        if got_n in accepted:
            return True
        return _contains_accepted_phrase(got_n, accepted)

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
        # Two capture groups: the bracketed form and the bare form.
        item_id = (m.group(1) or m.group(2)).lstrip("0") or "0"
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
        if is_echo(answer, source) or (
            mode == "numeric" and returns_input_value(answer, source, expected)
        ):
            # Unanswered, not wrong. See is_echo and returns_input_value.
            graded.append(GradedItem(item_id, answer, expected, mode, None, echoed=True))
            continue
        graded.append(GradedItem(item_id, answer, expected, mode, grade_answer(answer, expected, mode)))
    return graded


def _optional_score(unit: Any, field: str) -> float | None:
    """Read a per-unit score, preserving *absent* as ``None``.

    ``getattr(unit, field, 0.0)`` was the old form and it manufactured a
    measurement out of a missing one. A single-replica unit has no agreement --
    there is no second reply for it to agree with -- and coercing that to 0.0
    put it in the calibration as the *least confident* item in the dataset
    rather than as an item with no confidence score at all.

    The run of 26 August is what this cost. 8 984 single-replica rows, 45 % of
    the graded mass, entered the agreement calibration pinned at 0.0. Mean
    agreement read 0.392 and 0.391 for two claim classes whose accuracy differed
    by 37 points -- two classes reading the same value to three decimals is the
    signature of a constant, not of a measurement. Restricted to k=3 the same
    data give 0.813 and 0.736, in line with the run before it. The "collapse"
    was arithmetic.

    ``None`` is returned instead, and every consumer already excludes it and
    counts the exclusion.
    """
    if isinstance(unit, str):
        return None
    value = getattr(unit, field, None)
    if value is None or isinstance(value, bool):
        return None
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


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
                "agreement": _optional_score(unit, "agreement"),
                "judge_score": _optional_score(unit, "judge_score"),
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
