"""The properties the suite did not have, and eight defects that used the gap.

Every one of the 526 tests that preceded this file is single-shot: run an input,
compare against a literal, or break a mechanism and check the metric moves. Not
one of them relates *two* evaluations of the instrument to each other. Eight
real defects walked through that gap in one sitting, and they fall into three
classes:

**Representation invariance.** The verdict must not change under a
transformation that does not change what is being measured. A sentence-final
full stop is such a transformation, and it broke four checks. So was the arm
label, and it broke two.

**Conservation.** Two quantities derived from the same population and published
side by side must agree. ``_truth_records`` returned records filtered by scope
and a report that was not, and printed both.

**Round-trip over the real corpus.** The parser must recover exactly the items
that were written, for every answer the corpus actually contains -- not for the
four hand-picked answers a parametrised test happened to list.

Fault injection cannot reach any of this. It tests *sensitivity* -- the metric
moves when the mechanism breaks -- and these are movements with no mechanism
change at all. ``tests/test_instrument.py`` already had one test of the right
shape, for one metric. It caught its defect. It was never generalised, and the
seven others are what that cost.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from swarmbly_v0.constraints import check_constraint, grade_text
from swarmbly_v0.grading import content_tokens, extract_items, grade_answer
from swarmbly_v0.planner import carry_values

GROUND_TRUTH = Path(__file__).resolve().parent.parent / "prompts" / "ground_truth.json"


# --------------------------------------------------------------------------- #
# class 1: a verdict about content does not depend on where a sentence ends
# --------------------------------------------------------------------------- #

SENTENCE_ENDINGS = ("", ".", "!", "?")


@pytest.mark.parametrize("stop", SENTENCE_ENDINGS)
def test_any_of_reads_a_phrase_that_ends_the_sentence(stop: str) -> None:
    """"251 kg is under." and "251 kg is under the limit" are the same claim.

    Under ``.split()`` the first scored wrong and the second right. This is the
    single most consequential form of the bug, because a terse answer is more
    likely to end on the operative word -- and terseness is the documented
    difference between the arms.
    """
    assert grade_answer(f"pallet R752, 251 kg is under{stop}",
                        "under|below|within", "any_of") is True


def test_the_negation_guard_survives_the_punctuation_fix() -> None:
    """The fix must not buy sensitivity by giving up the guard that stops a
    wrong answer being scored right."""
    assert grade_answer("not over the limit", "over", "any_of") is False
    assert grade_answer("the pallet is not over.", "over", "any_of") is False
    assert grade_answer("not under -- over.", "over", "any_of") is True


@pytest.mark.parametrize("stop", SENTENCE_ENDINGS)
def test_a_boolean_that_ends_the_sentence_is_still_a_boolean(stop: str) -> None:
    """Returning ``None`` here does not score the answer wrong -- it removes it
    from the accuracy denominator and files it under ``items_unintelligible``,
    the statistic used to argue that fragmented workers fail to answer."""
    assert grade_answer(f"the consignment was cleared: no{stop}", "false", "boolean") is True
    assert grade_answer(f"yes{stop}", "true", "boolean") is True


@pytest.mark.parametrize("stop", SENTENCE_ENDINGS)
def test_term_once_sees_a_term_wherever_the_sentence_breaks(stop: str) -> None:
    """Both directions. The error was bidirectional, so it did not cancel: it
    false-PASSED the duplication the check exists to detect, and false-FAILED a
    single correct mention."""
    spec = {"id": "t", "kind": "term_once", "term": "tide window"}

    single = check_constraint(f"Work stops at the tide window{stop}", spec)
    assert single.satisfied is True and single.observed == 1

    twice = check_constraint(
        f"The tide window closes at noon{stop} Work stops at the tide window.", spec)
    assert twice.satisfied is False and twice.observed == 2


@pytest.mark.parametrize("stop", SENTENCE_ENDINGS)
def test_a_repeated_phrase_is_seen_wherever_the_sentence_breaks(stop: str) -> None:
    """One-sided under-detection of repetition, in the check whose whole purpose
    is repetition across fragments. The miss inflated the fragmented arm's
    constraint score against its own baseline."""
    spec = {"id": "n", "kind": "no_repeated_ngram", "size": 6}
    text = (f"Crews are told the tide gate opens at dawn{stop} "
            "Nothing else follows except that the tide gate opens at dawn each spring.")
    result = check_constraint(text, spec)
    assert result.satisfied is False, "the repeated six-gram was invisible"
    assert result.observed >= 1


def test_content_tokens_is_the_one_place_this_is_decided() -> None:
    """The defect appeared in four checks because four call sites each did their
    own splitting. They now share one function, so a fifth check cannot
    reintroduce it by writing ``.split()`` again -- as long as it calls this."""
    assert content_tokens("Work stops at the tide window.") == \
        ["work", "stops", "at", "the", "tide", "window"]
    # A decimal is not sentence punctuation and must survive.
    assert content_tokens("the distance is 42.5 km.") == ["the", "distance", "is", "42.5", "km"]


# --------------------------------------------------------------------------- #
# class 2: a label grammar does not depend on the answer's lexical content
# --------------------------------------------------------------------------- #

def test_a_decimal_point_is_not_an_item_label() -> None:
    """``[05] 42500 m is 42.5 km`` was parsed as item 05 with the answer
    "42500 m is", plus a phantom item 42 answering "5 km". The real answer was
    correct and was recorded as never attempted."""
    assert extract_items("[05] 42500 m is 42.5 km") == [("05", "42500 m is 42.5 km")]


def test_a_decimal_point_is_not_a_carry_label() -> None:
    """The sibling regex in the planner, where the same defect is worse.

    ``carry_values`` feeds the successor's packet. A phantom ``[42]=5`` is not
    merely mis-scored -- it is handed to the next model as though a predecessor
    had produced it, inviting the restatement that ``task_item_scope`` exists to
    remove, in the typed-carry arm only.
    """
    assert carry_values("42.5 km is the distance travelled") == {}
    assert carry_values("[01] 480\n42.5 km is the remainder") == {"01": "480"}
    # The bare form still works where it is genuinely a label.
    assert carry_values("01. 480\n02: 909") == {"01": "480", "02": "909"}


@pytest.mark.parametrize("style", ["[{}] {}", "({}) {}", "{}. {}", "{}: {}"])
def test_every_answer_in_the_corpus_round_trips_through_every_label_style(style) -> None:
    """Over the real key, not four hand-picked answers.

    The parametrised test in test_grading.py crossed label styles with the
    answers ``42``, ``17``, ``Lisbon`` and ``true`` -- none of which contains a
    decimal point. 20 of the corpus's items do.
    """
    corpus = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    checked = 0
    for spec in corpus["prompts"]:
        for item_id, entry in spec["key"].items():
            expected = str(entry["expected"])
            if "\n" in expected:
                continue
            parsed = extract_items(style.format(item_id, expected))
            assert parsed == [(item_id.zfill(2), expected)], \
                f"{spec['id']} item {item_id}: {expected!r} parsed as {parsed!r}"
            checked += 1
    assert checked >= 100, f"only {checked} items exercised; the corpus should hold ~150"


def test_the_corpus_contains_the_answers_this_test_exists_for() -> None:
    """A round-trip test over a corpus with no decimals proves nothing. If the
    corpus loses them, this fails rather than passing vacuously."""
    corpus = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    decimals = [str(e["expected"]) for s in corpus["prompts"] for e in s["key"].values()
                if "." in str(e["expected"]) and any(c.isdigit() for c in str(e["expected"]))]
    assert len(decimals) >= 10, f"only {len(decimals)} decimal answers; the defect is untestable"


# --------------------------------------------------------------------------- #
# class 3: a published counter is the aggregation of the rows published beside it
# --------------------------------------------------------------------------- #

class _Unit:
    def __init__(self, text: str, agreement: float = 0.5) -> None:
        self.text, self.agreement, self.accepted = text, agreement, True
        self.label, self.judge_score = "MEDIUM", 0.5


class _FakeResult:
    def __init__(self, units, k: int = 3) -> None:
        self.units, self.k = units, k


def _spec_with_four_items():
    from swarmbly_v0.experiment import PromptSpec
    return PromptSpec(
        prompt_id="gt_demo", category="demo", expected_decomposable=True,
        text="[01] ... [02] ... [03] ... [04] ...",
        key={"01": {"expected": "42", "mode": "numeric"},
             "02": {"expected": "17", "mode": "numeric"},
             "03": {"expected": "8", "mode": "numeric"},
             "04": {"expected": "5", "mode": "numeric"}},
    )


def test_the_report_counts_the_records_it_is_printed_beside() -> None:
    """The scope filter removed items from the records and left the report alone.

    A fragment asked for items 01 and 02 restates 03 and 04 -- which the typed
    carry handed it, formatted as answer lines -- and scored them for free. One
    enumerated corpus reported 379 graded items against a key holding 150.

    The bias is one-sided (a restated answer is correct by construction), it
    grows with N, and it is larger in the typed-carry arm than in its control.
    The monolithic baseline has no scope and is unaffected, so the *comparison*
    was skewed, not just the level.
    """
    from swarmbly_v0.experiment import _truth_records

    spec = _spec_with_four_items()
    # The fragment was asked for 01 and 02. It restates 03 and 04 as well.
    fragment = _FakeResult([_Unit("[01] 42"), _Unit("[02] 17"),
                            _Unit("[03] 8"), _Unit("[04] 5")])
    scope = {"t0": {"01", "02"}}

    records, report = _truth_records(
        spec, {"condition": "fragmented", "rho_target": 1.5}, [("t0", fragment)], scope)

    assert len(records) == 2, "the filter kept the out-of-scope items"
    assert report["items_seen"] == len(records)
    assert report["items_graded"] == sum(1 for r in records if r["graded"])
    assert report["items_correct"] == sum(1 for r in records if r["correct"])
    assert report["accuracy"] == pytest.approx(
        report["items_correct"] / report["items_graded"])


def test_the_unit_counters_are_not_filtered_by_scope() -> None:
    """The other half of the invariant, and the reason the fix is not simply
    "sum everything from the records".

    ``units_total`` and ``units_with_no_label`` are about UNITS. A unit that
    produced nothing parsable contributes no records at all, so deriving these
    from the records would silently drop the format-failure denominator -- which
    is the number that tells a reader whether a low accuracy means "wrong" or
    "never answered".
    """
    from swarmbly_v0.experiment import _truth_records

    spec = _spec_with_four_items()
    fragment = _FakeResult([_Unit("[01] 42"), _Unit("I am unable to help with that.")])
    _, report = _truth_records(
        spec, {"condition": "fragmented"}, [("t0", fragment)], {"t0": {"01"}})

    assert report["units_total"] == 2
    assert report["units_with_no_label"] == 1


# --------------------------------------------------------------------------- #
# class 4: a figure compared across arms is a property of the answer
# --------------------------------------------------------------------------- #

_CONSTRAINTS = [
    {"id": "c_para", "kind": "paragraph_count", "count": 2},
    {"id": "c_words", "kind": "words_per_paragraph", "min": 5, "max": 60},
    {"id": "c_must", "kind": "must_mention", "term": "tide gate"},
    {"id": "c_once", "kind": "term_once", "term": "tide gate"},
]


def test_the_comparable_constraint_score_ignores_what_the_assembler_supplied() -> None:
    """``paragraph_count`` and ``words_per_paragraph`` are satisfied by the
    ASSEMBLER in the fragmented arm and by the model alone in the baseline.

    ``select_then_splice`` is handed ``paragraph_join=requested_paragraphs(...)``
    and deterministically emits exactly that many paragraphs; ``run_monolithic``
    is a bare generate with no post-processing at all. On the table corpus that
    is a guaranteed pass for one arm against a near-certain fail for the other,
    on two of seven checks -- and the sign *flips* by corpus: where a prompt
    describes its structure without naming a count, the pieces are spliced into
    one paragraph and the fragmented arm fails by construction. Same instrument,
    opposite bias, decided by prompt wording.
    """
    one_paragraph = "The tide gate is the subject here, and it opens at dawn each day."
    two_paragraphs = "The tide gate is the subject here.\n\nIt opens at dawn each day."

    wrong_shape = grade_text(one_paragraph, _CONSTRAINTS)
    right_shape = grade_text(two_paragraphs, _CONSTRAINTS)

    # The raw score sees the formatting difference, which is correct: it is a
    # real property of the text, and the record keeps it.
    assert wrong_shape.score != right_shape.score

    # The comparable score does not, because that difference belongs to the
    # assembler in one arm and to the model in the other.
    excluded = ("paragraph_count", "words_per_paragraph")
    assert wrong_shape.score_excluding(excluded) == right_shape.score_excluding(excluded)


def test_the_excluded_set_is_the_one_the_summary_actually_uses() -> None:
    """A test that hard-codes the exclusion list drifts from the code it guards.

    This asserts the constant, so adding an assembler-enforced check without
    declaring it here fails rather than quietly entering the cross-arm figure.
    """
    from swarmbly_v0.experiment import ASSEMBLER_ENFORCED
    assert ASSEMBLER_ENFORCED == frozenset({"paragraph_count", "words_per_paragraph"})


def test_score_excluding_returns_none_rather_than_one_when_nothing_is_left() -> None:
    """A text checked against nothing has not passed; it has not been checked.
    Returning 1.0 here would let a prompt whose only constraints are the two
    excluded kinds contribute a perfect score to the cross-arm mean."""
    only_excluded = [{"id": "c_para", "kind": "paragraph_count", "count": 1}]
    report = grade_text("One paragraph.", only_excluded)
    assert report.score == 1.0
    assert report.score_excluding(("paragraph_count", "words_per_paragraph")) is None
