"""Tests for the ground-truth grader and the V3c calibration statistics.

The grader is the instrument the whole V3c re-run depends on, so the tests here
are mostly about the ways an instrument can flatter its subject: counting an
unintelligible answer as merely wrong, grading a model's working instead of its
answer, dropping non-compliant output silently, or reporting an accuracy over
whichever subset happened to parse.
"""

from __future__ import annotations

import collections
import json
from pathlib import Path

import pytest

from swarmbly_v0.experiment import agreement_truth_calibration
from swarmbly_v0.grading import (
    GradeReport,
    extract_items,
    grade_answer,
    grade_unit,
    grade_units,
    normalise_text,
)

CORPUS = Path(__file__).resolve().parent.parent / "prompts" / "ground_truth.json"


# --------------------------------------------------------------------------- #
# normalisation and matching
# --------------------------------------------------------------------------- #

def test_normalisation_removes_typography_not_content() -> None:
    assert normalise_text("  Valparaíso!  ") == "valparaiso"
    assert normalise_text("CLEARED,") == "cleared"
    # Content must survive: these are different answers, not formatting variants.
    assert normalise_text("42 units") != normalise_text("42")


@pytest.mark.parametrize(
    "given,expected,mode,want",
    [
        ("  42 ", "42", "numeric", True),
        ("42.0000001", "42", "numeric", True),
        ("43", "42", "numeric", False),
        ("1,250", "1250", "numeric", True),
        ("9.800", "9.8", "numeric", True),
        ("2026-09-02", "2026-09-02", "date_iso", True),
        ("2026/9/2", "2026-09-02", "date_iso", True),
        ("2026-09-03", "2026-09-02", "date_iso", False),
        ("True", "true", "boolean", True),
        ("no", "false", "boolean", True),
        ("yes", "false", "boolean", False),
        ("Valparaíso", "Valparaiso", "exact_norm", True),
        ("Lisbon", "Osaka", "exact_norm", False),
    ],
)
def test_grade_answer_matching(given: str, expected: str, mode: str, want: bool) -> None:
    assert grade_answer(given, expected, mode) is want


def test_the_last_number_is_the_answer_not_the_working() -> None:
    """A model that shows its work ends on the answer.

    Taking the first number would grade the arithmetic it narrated rather than
    the result it committed to, which would score a correct answer as wrong.
    """
    assert grade_answer("3 crates times 14 is 42", "42", "numeric") is True
    assert grade_answer("39 x 24 minus 48 = 888", "888", "numeric") is True


def test_unintelligible_is_none_not_false() -> None:
    """"Wrong" and "unintelligible" are different failures.

    Folding the second into the first would let a model that produced prose
    instead of an answer count as merely incorrect, which quietly flatters the
    accuracy of everything that did answer.
    """
    assert grade_answer("I cannot determine this", "42", "numeric") is None
    assert grade_answer("sometime next month", "2026-09-02", "date_iso") is None
    assert grade_answer("it depends", "true", "boolean") is None
    assert grade_answer("", "Lisbon", "exact_norm") is None


def test_unknown_mode_raises_rather_than_falling_back() -> None:
    """A silent fallback to string comparison would grade numbers by formatting."""
    with pytest.raises(ValueError, match="unknown match mode"):
        grade_answer("42", "42", "approximately")


# --------------------------------------------------------------------------- #
# item extraction
# --------------------------------------------------------------------------- #

def test_extract_items_handles_the_label_styles_models_actually_emit() -> None:
    text = "[01] 42\n(2) 17\n03. Lisbon\n- [04] true"
    assert extract_items(text) == [("01", "42"), ("02", "17"), ("03", "Lisbon"), ("04", "true")]


def test_preamble_before_the_first_label_is_discarded() -> None:
    items = extract_items("Here are my answers:\n[01] 42")
    assert items == [("01", "42")]


def test_one_unit_can_carry_several_items() -> None:
    """Consensus segments text without knowing about items.

    Collapsing several items into one verdict would throw away exactly the
    resolution the calibration needs.
    """
    key = {"01": {"expected": "42", "mode": "numeric"}, "02": {"expected": "17", "mode": "numeric"}}
    graded = grade_unit("[01] 42 [02] 18", key)
    assert [(g.item_id, g.correct) for g in graded] == [("01", True), ("02", False)]


def test_a_repeated_item_is_graded_twice() -> None:
    """Keeping only the first would let a model launder a wrong answer."""
    key = {"01": {"expected": "42", "mode": "numeric"}}
    graded = grade_unit("[01] 42 [01] 99", key)
    assert [g.correct for g in graded] == [True, False]


def test_a_label_outside_the_key_is_flagged_not_scored() -> None:
    graded = grade_unit("[77] 42", {"01": {"expected": "42", "mode": "numeric"}})
    assert graded[0].unknown_item is True
    assert graded[0].graded is False


# --------------------------------------------------------------------------- #
# reporting: the denominators must travel with the numerator
# --------------------------------------------------------------------------- #

class _Unit:
    def __init__(self, text: str, agreement: float = 0.5, accepted: bool = True) -> None:
        self.text, self.agreement, self.accepted = text, agreement, accepted
        self.label, self.judge_score = "MEDIUM", 0.5


def test_units_with_no_label_are_counted_not_dropped() -> None:
    key = {"01": {"expected": "42", "mode": "numeric"}}
    records, report = grade_units([_Unit("[01] 42"), _Unit("I am unable to help with that.")], key)
    assert len(records) == 1
    assert report.units_total == 2
    assert report.units_with_no_label == 1


def test_accuracy_is_none_when_nothing_was_gradable() -> None:
    """An absent measurement must not read as a zero."""
    report = GradeReport()
    assert report.accuracy is None
    assert report.as_dict()["accuracy"] is None


def test_report_separates_wrong_from_unintelligible() -> None:
    key = {f"{i:02d}": {"expected": "42", "mode": "numeric"} for i in range(1, 4)}
    _, report = grade_units([_Unit("[01] 42 [02] 43 [03] no idea")], key)
    assert (report.n_graded, report.n_correct, report.n_unintelligible) == (2, 1, 1)
    assert report.accuracy == pytest.approx(0.5)


# --------------------------------------------------------------------------- #
# the calibration statistics
# --------------------------------------------------------------------------- #

def test_perfect_signal_scores_auc_one() -> None:
    recs = [{"agreement": 0.9, "correct": True}] * 20 + [{"agreement": 0.2, "correct": False}] * 20
    out = agreement_truth_calibration(recs)
    assert out["auc"] == 1.0
    assert out["pearson_r"] == 1.0
    assert out["n_items"] == 40


def test_no_signal_scores_auc_near_half() -> None:
    """The null result must look like a null result, not like a small effect."""
    recs = [{"agreement": (i % 7) / 7.0, "correct": i % 2 == 0} for i in range(280)]
    out = agreement_truth_calibration(recs)
    assert out["auc"] == pytest.approx(0.5, abs=0.05)


def test_auc_is_undefined_with_only_one_class() -> None:
    out = agreement_truth_calibration([{"agreement": 0.4, "correct": True}] * 10)
    assert out["auc"] is None
    assert out["accuracy"] == 1.0


def test_exclusions_are_counted_separately() -> None:
    out = agreement_truth_calibration([
        {"agreement": 0.5, "correct": None},   # unintelligible
        {"agreement": None, "correct": True},  # no agreement (single replica)
        {"agreement": 0.5, "correct": True},
    ])
    assert (out["n_items"], out["excluded_unintelligible"], out["excluded_no_agreement"]) == (1, 1, 1)


def test_flagging_reports_lift_against_the_base_error_rate() -> None:
    """Lift is the number a reader can argue with: 1.0 means random flagging."""
    recs = [{"agreement": 0.1, "correct": False}] * 10 + [{"agreement": 0.9, "correct": True}] * 90
    out = agreement_truth_calibration(recs, flag_rates=(0.10,))
    flag = out["flagging"][0]
    assert flag["n_flagged"] == 10
    assert flag["recall"] == 1.0        # all ten errors are in the lowest decile
    assert flag["precision"] == 1.0
    assert flag["lift"] == 10.0         # base error rate is 0.10


def test_flag_metrics_are_none_when_there_is_nothing_to_catch() -> None:
    out = agreement_truth_calibration([{"agreement": 0.5, "correct": True}] * 10, flag_rates=(0.2,))
    assert out["flagging"][0]["recall"] is None


def test_empty_input_yields_no_fabricated_numbers() -> None:
    out = agreement_truth_calibration([])
    assert out["n_items"] == 0
    assert out["accuracy"] is None and out["auc"] is None and out["pearson_r"] is None


# --------------------------------------------------------------------------- #
# the corpus itself
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def corpus() -> dict:
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def test_corpus_exists_and_every_item_has_a_gradable_key(corpus: dict) -> None:
    assert corpus["prompts"], "the ground-truth corpus is empty"
    for spec in corpus["prompts"]:
        assert spec["key"], f"{spec['id']} has no answer key"
        for item_id, entry in spec["key"].items():
            assert item_id.isdigit() and len(item_id) == 2, f"{spec['id']}: bad item id {item_id!r}"
            assert entry["expected"] != "", f"{spec['id']}/{item_id}: empty expected value"
            # The key must grade itself. A key that cannot is not a key.
            assert grade_answer(entry["expected"], entry["expected"], entry["mode"]) is True


def test_every_key_item_appears_in_its_prompt(corpus: dict) -> None:
    """A key entry with no question is an item no model can answer."""
    for spec in corpus["prompts"]:
        labels = {item_id for item_id, _ in extract_items(spec["prompt"])}
        missing = sorted(set(spec["key"]) - labels)
        assert not missing, f"{spec['id']}: key items absent from the prompt: {missing}"


def test_the_corpus_spans_difficulties(corpus: dict) -> None:
    """A dependent variable with no variance is what made the last attempt unreadable."""
    assert len(corpus["prompts"]) >= 3
    modes = {e["mode"] for s in corpus["prompts"] for e in s["key"].values()}
    assert len(modes) >= 3, f"only {modes} represented; difficulty will not spread"


def test_a_perfect_answer_sheet_grades_as_perfect(corpus: dict) -> None:
    """End to end: the grader must accept a correct submission in the asked format."""
    for spec in corpus["prompts"]:
        sheet = "\n".join(f"[{i}] {e['expected']}" for i, e in sorted(spec["key"].items()))
        _, report = grade_units([_Unit(sheet)], spec["key"])
        assert report.n_graded == len(spec["key"]), f"{spec['id']}: only {report.n_graded} graded"
        assert report.accuracy == 1.0, f"{spec['id']}: accuracy {report.accuracy}"


# --------------------------------------------------------------------------- #
# the sweep wiring: records, summary block, sidecar CSV
# --------------------------------------------------------------------------- #

class _FakeResult:
    """Stand-in for a ConsensusResult carrying labelled units."""

    def __init__(self, units: list[_Unit], k: int = 3) -> None:
        self.units, self.k = units, k


def _spec_with_key():
    from swarmbly_v0.experiment import PromptSpec
    return PromptSpec(
        prompt_id="gt_demo",
        category="demo",
        expected_decomposable=True,
        text="[01] ... [02] ...",
        key={"01": {"expected": "42", "mode": "numeric"},
             "02": {"expected": "17", "mode": "numeric"}},
    )


def test_prompt_spec_reports_whether_it_has_a_key() -> None:
    from swarmbly_v0.experiment import load_prompts
    assert all(p.has_ground_truth for p in load_prompts(str(CORPUS)))
    # The coherence-tax corpus deliberately has none, and must not gain any.
    assert not any(p.has_ground_truth for p in load_prompts())


def test_truth_records_grade_units_and_carry_the_agreement() -> None:
    from swarmbly_v0.experiment import _truth_records
    spec = _spec_with_key()
    results = [("t0", _FakeResult([_Unit("[01] 42", agreement=0.91),
                                   _Unit("[02] 19", agreement=0.22)]))]
    records, report = _truth_records(spec, {"condition": "fragmented", "rho_target": 1.5}, results)
    assert [(r["item_id"], r["correct"], r["agreement"]) for r in records] == [
        ("01", True, 0.91), ("02", False, 0.22)]
    assert report["items_graded"] == 2 and report["items_correct"] == 1
    assert report["accuracy"] == pytest.approx(0.5)


def test_truth_records_are_empty_without_a_key() -> None:
    from swarmbly_v0.experiment import PromptSpec, _truth_records
    spec = PromptSpec("p", "c", True, "text")
    records, report = _truth_records(spec, {}, [("t0", _FakeResult([_Unit("[01] 42")]))])
    assert records == [] and report == {}


def test_summary_block_is_absent_for_a_corpus_without_keys() -> None:
    """A coherence-tax run must not gain a calibration section full of nulls."""
    from swarmbly_v0.experiment import _truth_summary
    assert _truth_summary([{"prompt_id": "x"}]) == {}


def test_summary_block_reports_a_total_format_failure_rather_than_vanishing() -> None:
    from swarmbly_v0.experiment import _truth_summary
    out = _truth_summary([{"_truth_records": [],
                           "_truth_report": {"units_total": 8, "units_with_no_label": 8,
                                             "items_seen": 0, "items_graded": 0,
                                             "items_correct": 0, "items_unintelligible": 0,
                                             "items_unknown_id": 0}}])
    tc = out["truth_calibration"]
    assert tc["grading"]["units_with_no_label"] == 8
    assert tc["pooled"]["auc"] is None
    assert "not a missing measurement" in tc["note"]


def test_summary_splits_calibration_by_category_and_by_k() -> None:
    """Section 11.4 asks for curves per task category, and pooling can fake a signal."""
    from swarmbly_v0.experiment import _truth_summary
    recs = (
        [{"category": "easy", "k": 3, "agreement": 0.9, "correct": True}] * 10
        + [{"category": "hard", "k": 3, "agreement": 0.3, "correct": False}] * 10
    )
    tc = _truth_summary([{"_truth_records": recs, "_truth_report": {}}])["truth_calibration"]
    assert set(tc["by_category"]) == {"easy", "hard"}
    assert tc["by_category"]["easy"]["accuracy"] == 1.0
    assert tc["by_category"]["hard"]["accuracy"] == 0.0
    # Pooled looks like a perfect predictor; per category there is no variance at all.
    assert tc["pooled"]["auc"] == 1.0
    assert tc["by_category"]["easy"]["auc"] is None
    assert set(tc["by_k"]) == {"3"}


def test_sidecar_csv_is_written_only_when_there_is_something_in_it(tmp_path) -> None:
    from swarmbly_v0.experiment import TRUTH_CSV_COLUMNS, write_truth_csv
    assert write_truth_csv([{"prompt_id": "x"}], tmp_path / "none.csv") is None

    rows = [{"_truth_records": [
        {"prompt_id": "gt_demo", "category": "demo", "k": 3, "task_id": "t0",
         "unit_index": 0, "item_id": "01", "label": "HIGH", "agreement": 0.91,
         "judge_score": 0.7, "accepted": True, "mode": "numeric", "expected": "42",
         "given": "42", "correct": True, "graded": True, "unknown_item": False},
        {"prompt_id": "gt_demo", "category": "demo", "k": 3, "task_id": "t0",
         "unit_index": 1, "item_id": "02", "label": "LOW", "agreement": None,
         "judge_score": None, "accepted": None, "mode": "numeric", "expected": "17",
         "given": "no idea", "correct": None, "graded": False, "unknown_item": False},
    ]}]
    out = write_truth_csv(rows, tmp_path / "items.csv")
    assert out is not None
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].split(",")[:3] == list(TRUTH_CSV_COLUMNS[:3])
    assert len(lines) == 3
    # None must render as empty, never as the string "None" -- a reader loading this
    # into a dataframe would get a literal that silently is not null.
    assert "None" not in lines[2]


# --------------------------------------------------------------------------- #
# the segmentation failure that cost the 24 August run its control category
# --------------------------------------------------------------------------- #

def test_line_granularity_keeps_a_label_with_its_answer() -> None:
    """Regression for the defect that made the first ground-truth run unreadable.

    A reply of "1. Osaka" splits at the full stop under sentence granularity into
    "1." and "Osaka" -- a label holding no answer, then an answer belonging to
    nobody. In the run of 24 August that produced 73 % empty answers in
    ``field_extraction``, the control category no model should fail, and 43 % of
    all units came back unlabelled. When one line is one answer, splitting
    inside it destroys the observation rather than localising it.
    """
    from swarmbly_v0.consensus import segment_units

    reply = "1. Osaka\n2. Valparaiso\n3. Lisbon"
    assert [u.text for u in segment_units(reply, "sentence")] == [
        "1.", "Osaka", "2.", "Valparaiso", "3.", "Lisbon"]
    assert [u.text for u in segment_units(reply, "line")] == [
        "1. Osaka", "2. Valparaiso", "3. Lisbon"]


def test_line_granularity_grades_where_sentence_granularity_loses_the_answer() -> None:
    """The same reply, graded both ways. This is the whole bug in four lines."""
    from swarmbly_v0.consensus import segment_units

    key = {"01": {"expected": "Osaka", "mode": "exact_norm"},
           "02": {"expected": "Valparaiso", "mode": "exact_norm"}}
    reply = "1. Osaka\n2. Valparaiso"

    _, by_sentence = grade_units(segment_units(reply, "sentence"), key)
    _, by_line = grade_units(segment_units(reply, "line"), key)

    assert by_sentence.n_correct == 0          # every answer lost to the splitter
    assert by_sentence.units_with_no_label == 2
    assert by_line.n_correct == 2
    assert by_line.accuracy == 1.0


def test_unknown_granularity_still_raises() -> None:
    from swarmbly_v0.consensus import segment_units
    with pytest.raises(ValueError, match="granularity must be"):
        segment_units("x", "paragraph")


# --------------------------------------------------------------------------- #
# echo detection, difficulty levels, and the fragmentation-cost comparison
# --------------------------------------------------------------------------- #

def test_a_restated_item_is_unanswered_not_wrong() -> None:
    """The 24 August run scored copied-back questions as incorrect answers.

    Numeric grading took the last number in the restatement -- an input value --
    and compared it to the key. That both deflates accuracy and fills the error
    class the flagging metric exists to catch with items nobody attempted.
    """
    from swarmbly_v0.grading import is_echo

    source = "[01] 37 crates of pump seals, 17 units per crate, 68 units removed for inspection"
    assert is_echo("37 crates of pump seals, 17 units per crate, 68 units removed", source)
    # Working shown on the way to an answer is not a restatement.
    assert not is_echo("37 crates * 17 units/crate = 629 units", source)
    # A bare answer never is, however short.
    assert not is_echo("561", source)


def test_a_correct_answer_that_appears_in_the_source_is_not_an_echo() -> None:
    """Extraction answers are always substrings of the record they came from.

    A containment test would flag every right answer in the control category, so
    the rule is coverage of the item's content words, not containment.
    """
    from swarmbly_v0.grading import is_echo
    record = "[01] ref A1234 | origin Lisbon | destination Osaka | customs held | weight 200 kg"
    assert not is_echo("Osaka", record)


def test_echo_is_graded_as_unintelligible_and_counted_separately() -> None:
    source = "[01] 37 crates of pump seals, 17 units per crate, 68 units removed for inspection"
    key = {"01": {"expected": "561", "mode": "numeric", "source": source}}
    _, report = grade_units(
        [_Unit("[01] 37 crates of pump seals, 17 units per crate, 68 units removed")], key)
    assert report.n_graded == 0
    assert report.n_echoed == 1
    assert report.as_dict()["items_echoed"] == 1


def test_echo_detection_is_off_without_a_source() -> None:
    """An unverifiable suspicion is not grounds for discarding an observation."""
    from swarmbly_v0.grading import is_echo
    assert is_echo("anything at all, at length, with many words", "") is False


def test_summary_reports_the_fragmentation_cost_against_the_baseline() -> None:
    """Separates 'the model cannot do this' from 'fragmenting destroyed it'.

    After 24 August returned one correct answer in sixty-four on two-step
    arithmetic, this is the more interesting of the two questions, and the run
    could not answer it because only the fragmented condition was graded.
    """
    from swarmbly_v0.experiment import _truth_summary
    frag = [{"category": "arithmetic", "level": 1, "condition": "fragmented",
             "k": 3, "agreement": 0.5, "correct": i < 4} for i in range(10)]
    mono = [{"category": "arithmetic", "level": 1, "condition": "monolithic",
             "k": 1, "agreement": None, "correct": i < 9} for i in range(10)]
    tc = _truth_summary([{"_truth_records": frag + mono, "_truth_report": {}}])["truth_calibration"]
    assert tc["fragmentation_cost"]["monolithic"]["accuracy"] == pytest.approx(0.9)
    assert tc["fragmentation_cost"]["fragmented"]["accuracy"] == pytest.approx(0.4)
    # The baseline carries no agreement, so it must not enter the calibration.
    assert tc["pooled"]["n_items"] == 10


def test_summary_splits_calibration_by_difficulty_level() -> None:
    """If agreement predicts correctness anywhere, it should be mid-range."""
    from swarmbly_v0.experiment import _truth_summary
    recs = ([{"category": "c", "level": 1, "condition": "fragmented", "k": 3,
              "agreement": 0.9, "correct": True}] * 6
            + [{"category": "c", "level": 3, "condition": "fragmented", "k": 3,
                "agreement": 0.4, "correct": False}] * 6)
    tc = _truth_summary([{"_truth_records": recs, "_truth_report": {}}])["truth_calibration"]
    assert set(tc["by_level"]) == {"1", "3"}
    assert tc["by_level"]["1"]["accuracy"] == 1.0
    assert tc["by_level"]["3"]["accuracy"] == 0.0


def test_the_corpus_ships_three_levels_per_family(corpus: dict) -> None:
    levels = collections.Counter(p["level"] for p in corpus["prompts"])
    assert set(levels) == {1, 2, 3}, f"levels present: {sorted(levels)}"
    assert len(set(levels.values())) == 1, "families must ship the same number of levels each"


def test_every_key_entry_carries_its_source_line(corpus: dict) -> None:
    """Without the source the grader cannot tell a restatement from an answer."""
    for spec in corpus["prompts"]:
        for item_id, entry in spec["key"].items():
            assert entry.get("source"), f"{spec['id']}/{item_id}: no source line"
            assert entry.get("level") in (1, 2, 3), f"{spec['id']}/{item_id}: no level"


def test_no_correct_answer_in_the_corpus_reads_as_an_echo(corpus: dict) -> None:
    """A rule that discards right answers is worse than no rule."""
    from swarmbly_v0.grading import is_echo
    for spec in corpus["prompts"]:
        for item_id, entry in spec["key"].items():
            assert not is_echo(entry["expected"], entry["source"]), f"{spec['id']}/{item_id}"
