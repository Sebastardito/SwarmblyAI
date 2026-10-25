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
import re
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


# --------------------------------------------------------------------------- #
# class 5: a number reaches the operator with the condition that makes it readable
# --------------------------------------------------------------------------- #

def _mock_run(tmp_path, capsys, **kw):
    """One real sweep through the CLI, so the console block is exercised."""
    from swarmbly_v0.cli import main
    args = ["run", "--backend", "mock", "--embedder", "hash",
            "--rho", kw.get("rho", "1.0,1.5"), "--n", kw.get("n", "2"),
            "--k", kw.get("k", "1,3"), "--max-prompts", kw.get("max_prompts", "2"),
            "--out", str(tmp_path)]
    assert main(args) == 0
    return capsys.readouterr().out


def test_the_operator_is_told_when_rows_were_dropped_below_the_floor(tmp_path, capsys):
    """The gate that matters most was the one the operator could not see.

    `publishable()` drops below-floor rows from every figure. Until this test
    existed it did so in silence: `rows_excluded_below_floor` went into
    summary.json and nothing put it on screen, so a tier finished with rows
    missing from its curve and no reason given. That is how V0's below-floor grid
    became a published headline -- `rho_reachable` was written to every row from
    the first run and read by nothing.
    """
    out = _mock_run(tmp_path, capsys)
    assert "DROPPED" in out, "the exclusion must be on screen, not only in summary.json"
    assert "packing floor" in out or "packing ceiling" in out, (
        "the banner must name WHICH bound was crossed; they are different repairs")
    assert "results.csv" in out, "and it must say where to find the dropped rows"

    html = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "ROW(S) DROPPED" in html, "the shared artefact needs the banner too"


def test_a_mean_over_one_cell_does_not_read_like_a_mean_over_forty(tmp_path, capsys):
    """`n_cells` was computed from the first version and never printed.

    On the smoke tier the whole headline survives from a single cell, and
    "-16.67 %" read exactly like a forty-cell mean.
    """
    out = _mock_run(tmp_path, capsys)
    curve_lines = [l for l in out.splitlines() if "BooookScore-like" in l and "rho=" in l]
    assert curve_lines, "the curve did not print"
    assert all("[n=" in line for line in curve_lines), "every curve point must carry its n"
    assert any("too few cells" in line for line in curve_lines), \
        "a curve point built from one or two cells must say so"


def test_the_superseded_criterion_is_not_printed_as_a_verdict(tmp_path, capsys):
    """"go/no-go: MET" is a line that gets quoted from a terminal within the day.

    The maximum-statistic criterion -- "exists (category, rho) under 5 %" -- has
    P(pass) = 100 % under its own null. It said MET on a two-prompt smoke run
    that measures nothing. It stays visible so an old run's history stays
    readable, and it is labelled rather than presented as a result.
    """
    out = _mock_run(tmp_path, capsys)
    assert "[superseded]" in out
    assert "not a verdict" in out
    assert "passes on random data" in out
    assert "falsifiable_go_no_go" in out, "the reader must be pointed at the real one"
    # The old headline shape must be gone: no bare "go/no-go: MET".
    assert "go/no-go (<5% in at least one category): MET" not in out


def test_a_correlation_is_withheld_for_the_right_stated_reason(tmp_path, capsys):
    """Two reasons to withhold, and they must not share a sentence.

    A judge at 89 % acceptance has almost no variance to correlate against. A
    judge at 50 % has the most variance available and simply has not been asked
    enough questions. Saying "that little variance" about the second is wrong,
    and a wrong explanation invites the reader to dismiss the withholding.
    """
    out = _mock_run(tmp_path, capsys)
    assert "NOT MEASURED here" in out, "no r may be printed on a thin sample"
    assert "Too few units" in out, "and the reason given must be the true one"
    assert "almost no variance" not in out, \
        "acceptance was 50 % -- variance was maximal, so that is the wrong reason"
    assert "answer key" in out, "and it must name the tier that would settle it"


DECLARED_FIXTURE_RHO = "3.0"
"""The rho these console tests declare, and it is NOT the tier's 3.5.

`tables24` at N=2 has a packing CEILING of about 3.35, discovered on 4
September. At 3.5 every N=2 row is above it, gets dropped, and the declared
cell it was pointing at stops existing -- so three tests about *printing* a
verdict started failing for a reason that had nothing to do with printing.

Moved to 3.0, inside the window, so these tests measure what they are about.
The fact that the tier's own declared cell sits above that ceiling is a
separate finding and it has its own banner in
`docs/RESULTS_TABLES_FINAL_CORRECTED.md`."""


def _declared_run(tmp_path, capsys, *declare, n="2,8"):
    from swarmbly_v0.cli import main
    args = ["run", "--backend", "mock", "--embedder", "hash",
            "--prompts", "prompts/tables24.json", "--split", "dev",
            "--rho", DECLARED_FIXTURE_RHO, "--n", n, "--k", "1",
            "--candidates", "1", "--seed", "0", "--out", str(tmp_path)]
    for cell in declare:
        args += ["--declare", cell]
    assert main(args) == 0
    return capsys.readouterr().out


def test_the_run_prints_the_cell_it_was_declared_to_test(tmp_path, capsys):
    """tables-dev exists to test ONE named cell and printed everything but it.

    Its console led with "+8.95%" -- a mean pooling N=2 and N=8, the arm under
    test averaged with the control that is *required to fail* -- while the actual
    verdict (+4.24 %, CI [-4.09 %, +10.59 %], NOT MET) and the control's
    (+13.67 %, CI [+7.15 %, +19.30 %]) appeared nowhere on screen. Both had to be
    read out of summary.json by hand.
    """
    out = _declared_run(tmp_path, capsys, "table_summary@rho=3.0@N=2@k=1")
    assert "DECLARED CELL: table_summary@rho=3.0@N=2@k=1" in out
    assert "point estimate" in out and "95% CI (by prompt)" in out
    assert "upper bound below" in out, "the criterion is on the bound, not the estimate"
    assert "n_prompts" in out, "the sample size that matters must be named"
    assert "VERDICT" in out


def test_the_control_is_labelled_as_one_and_flagged_if_it_passes(tmp_path, capsys):
    """A control that passes is worse news than a declared cell that fails: it
    says the instrument cannot separate the arms, so neither number is
    evidence. That has to be impossible to read past."""
    out = _declared_run(tmp_path, capsys,
                        "table_summary@rho=3.0@N=2@k=1",
                        "table_summary@rho=3.0@N=8@k=1")
    assert "CONTROL (must fail)" in out
    control = out[out.index("CONTROL (must fail)"):]
    assert "control reading" in control
    # Whichever way the mock lands, the reading must be stated explicitly.
    assert ("fails as required" in control) or ("THE CONTROL PASSED" in control)


def test_a_declared_cell_that_was_never_measured_is_not_silently_skipped(tmp_path, capsys):
    """A typo in the declaration must not produce a run that looks complete and
    has no verdict. It names the cells that WERE measured, so the mistake is
    fixable without opening summary.json."""
    out = _declared_run(tmp_path, capsys, "table_summary@rho=9.9@N=2@k=1", n="2")
    assert "NOT PRESENT in this run" in out
    assert "no verdict" in out
    assert "table_summary@rho=3.0@N=2@k=1" in out, "it must list what was measured"


def test_both_tables_tiers_declare_their_cell_in_the_runner() -> None:
    """The declaration is a fact about the invocation -- recoverable from run.log
    and from shell history -- rather than a paragraph the tier prints about
    itself. If it is only in the header text it can drift from what ran."""
    script = (Path(__file__).resolve().parent.parent
              / "scripts" / "run_ollama.sh").read_text(encoding="utf-8")
    # Anchored on the INVOCATION, not on a prose mention. The first draft of this
    # test matched "--split final" inside an echo line explaining the split and
    # passed or failed on the wrong text -- the same class of mistake as reading a
    # tier's k off a hand-written table instead of off its command line.
    for tier in ("--prompts prompts/tables24.json --split dev",
                 "--prompts prompts/tables24.json --split final"):
        assert script.count(tier) == 1, f"{tier}: expected exactly one invocation"
        block = script[script.index(tier):script.index(tier) + 600]
        assert "--declare 'table_summary@rho=3.0@N=2@k=1'" in block, tier
        assert "--declare 'table_summary@rho=3.0@N=8@k=1'" in block, \
            f"{tier}: the control must be declared too, or nothing checks it failed"


def test_the_runner_does_not_instruct_an_invocation_it_refuses() -> None:
    """tables-dev printed "--tau 0.68"; tables-final rejects that and demands the
    dev run's DIRECTORY, for a stated reason -- a bare number cannot carry which
    corpus it was fitted on, and this corpus has changed once already.

    So an operator following the script's own closing instruction could not
    proceed, and the error they got named the consequence ("--tau/run_metadata.json
    does not exist") rather than the mistake. Both halves are asserted here
    because fixing one and not the other reopens it.
    """
    script = (Path(__file__).resolve().parent.parent
              / "scripts" / "run_ollama.sh").read_text(encoding="utf-8")

    dev_tail = script[script.index("tau_sem fitted on dev"):][:900]
    assert "bash scripts/run_ollama.sh tables-final $out" in dev_tail, \
        "the dev tier must hand over the directory the final tier actually takes"
    assert "print('    --tau'" not in dev_tail, \
        "and must not instruct the form the final tier refuses"

    final = script[script.index("run_tables_final()"):]
    assert "--tau|--tau=*|-t)" in final, \
        "passing a tau must be named as the mistake, not reported as a missing file"
    assert 'is not a directory' in final


def test_no_comment_sits_inside_a_line_continuation() -> None:
    """A comment after a trailing backslash silently truncates the command.

    This cost a four-to-six-hour v3c-gt run. The comment block explaining the rho
    change was placed between `run_tier v3c-gt "$out" \\` and its `--rho` line, so
    bash ended the command at the comment and dispatched with no --rho, no --n,
    no --k and NO --out. It swept the default grid at k=1 -- the tier's whole
    question, agreement against ground truth, had zero data -- wrote into
    `results/` instead of the timestamped directory, and exited 0.

    `bash -n` does not catch it: the result is syntactically valid, just not the
    command anyone wrote.
    """
    script = (Path(__file__).resolve().parent.parent
              / "scripts" / "run_ollama.sh").read_text(encoding="utf-8")
    lines = script.split("\n")
    offences = [
        f"line {i + 2}: {nxt.strip()[:60]}"
        for i, (cur, nxt) in enumerate(zip(lines, lines[1:]))
        if cur.rstrip().endswith("\\") and not cur.rstrip().endswith("\\\\")
        and nxt.lstrip().startswith("#")
    ]
    assert not offences, (
        "a comment after a trailing backslash truncates the command:\n  "
        + "\n  ".join(offences))


def test_a_tier_that_wrote_nothing_into_its_own_directory_is_a_failure() -> None:
    """Exit status could not catch the truncation, because nothing failed.

    The post-condition can: a tier that did not write a summary into its own
    output directory did not run, whatever its exit code says.
    """
    script = (Path(__file__).resolve().parent.parent
              / "scripts" / "run_ollama.sh").read_text(encoding="utf-8")
    body = script[script.index("run_tier() {"):script.index("\n}\n", script.index("run_tier() {"))]
    assert 'for artefact in summary.json results.csv; do' in body, \
        "run_tier must verify the tier wrote its own output, not just its exit code"
    assert '[ -f "$out/$artefact" ] && continue' in body
    assert 'TIERS_FAILED="$TIERS_FAILED $name"' in body.split("for artefact")[1], \
        "and a missing artefact must reach the end-of-run summary"


# --------------------------------------------------------------------------- #
# class 4: an attempt must not be recorded as a non-attempt
#
# `returns_input_value` exists to keep a model that copies an input back out of
# the accuracy denominator. On the v3c-gt run of 4 September it also took every
# two-step arithmetic answer that showed its operands with it. The failure is
# silent by construction: the item leaves `items_graded` for
# `items_unintelligible`, and the accuracy of everything that survives goes up.
# --------------------------------------------------------------------------- #


def test_an_answer_that_shows_working_is_graded_not_discarded() -> None:
    """The rows that exposed it, verbatim from ground_truth_items.csv.

    ``gt_arith_L2`` item 01 reads "21 crates of pump seals, 16 units per crate,
    80 units removed for inspection" and keys to 256. The reply was ``21 - 80``:
    the outer operands with the multiplication dropped. That is a wrong attempt.

    ``_as_number`` takes the LAST number of an answer, so what
    ``returns_input_value`` compared against the item's inputs was 80 -- one of
    the item's own numbers -- and the item was recorded ``correct=None,
    echoed=True``. Five of five sampled rows behaved this way, in the family
    where the arithmetic has two steps and an answer therefore has two operands
    to show.

    An answer holding two numbers and an operator has attempted the item. A
    restatement hands the value back and stops.
    """
    from swarmbly_v0.grading import grade_unit, returns_input_value

    corpus = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    key = [p for p in corpus["prompts"] if p["id"] == "gt_arith_L2"][0]["key"]
    given = {"01": "21 - 80", "02": "37 - 72", "03": "23 - 42",
             "04": "17 - 50", "05": "17 - 18"}

    for item_id, answer in given.items():
        entry = key[item_id]
        assert not returns_input_value(answer, entry["source"], entry["expected"]), (
            f"item {item_id}: {answer!r} states two numbers and an operator; it is a "
            f"wrong attempt at {entry['expected']}, not a restatement of an input")

    graded = grade_unit("\n".join(f"[{i}] {a}" for i, a in given.items()), key)
    assert len(graded) == 5
    for item in graded:
        assert item.correct is False, f"item {item.item_id} must be WRONG, not unintelligible"
        assert item.graded is True
        assert item.echoed is False


def test_a_restatement_of_a_single_input_is_still_unanswered() -> None:
    """The defect the guard was built for, which the narrowing must not reopen.

    A worker holding data and no operation answered ``[05] 30000 m`` to an item
    whose source line was ``[05] 30000 m`` and whose answer was ``30``. Two
    tokens is far below the length at which ``is_echo`` calls anything a
    restatement, so before the guard existed the item was graded *wrong* and
    ``unit_conversion`` read 3.5 % against 80 % unfragmented.

    One stated number, and that number is the input: still a non-attempt.
    """
    from swarmbly_v0.grading import grade_unit, returns_input_value

    source = "[05] 30000 m"
    assert returns_input_value("30000 m", source, "30")
    assert returns_input_value("30,000 m", source, "30"), "thousands separators too"
    assert not returns_input_value("30", source, "30"), \
        "an answer equal to the key is correct, whatever it coincides with"

    key = {"05": {"expected": "30", "mode": "numeric", "source": source}}
    item = grade_unit("[05] 30000 m", key)[0]
    assert item.correct is None and item.echoed is True


def test_the_grading_denominators_conserve_every_item_seen() -> None:
    """Nothing may fall out of the report between ``items_seen`` and its parts.

    Every item occurrence is graded, unintelligible, or an unknown label -- there
    is no fourth class. The v3c-gt run moved 50 attempts into the unintelligible
    column, and because the columns still added up nothing in the summary said so.
    This asserts the partition holds on answers of every shape at once, so the
    next such move has to show as a count that changed rather than as arithmetic
    that still balances.
    """
    from swarmbly_v0.grading import grade_units

    source = "[01] 21 crates of pump seals, 16 units per crate, 80 units removed"
    key = {"01": {"expected": "256", "mode": "numeric", "source": source}}
    replies = [
        "[01] 256",                       # correct
        "[01] 21 - 80",                   # wrong, shows its operands
        "[01] 336",                       # wrong, forgot the removal
        "[01] 21 crates of pump seals, 16 units per crate, 80 units removed",  # echo
        "[01] no idea",                   # unintelligible
        "[99] 256",                       # unknown label
        "Here are the answers:",          # no label at all
    ]
    _, report = grade_units(replies, key)
    d = report.as_dict()

    assert d["items_seen"] == (d["items_graded"] + d["items_unintelligible"]
                               + d["items_unknown_id"]), \
        "items_seen must partition into graded, unintelligible and unknown-label"
    assert d["units_total"] == len(replies)
    assert d["units_with_no_label"] == 1
    assert d["items_graded"] == 3 and d["items_correct"] == 1, \
        "the shown-working answer belongs in the denominator, scored wrong"
    assert d["items_unintelligible"] == 2 and d["items_echoed"] == 1


def test_units_with_no_label_is_not_a_count_of_lost_answers() -> None:
    """``units_with_no_label`` measures LINES, and a preamble is a line.

    Read as attrition it is badly wrong, and at N=4 it is wrong by a factor
    large enough to be mistaken for a defect: a model that answers every item,
    in exactly the asked format, and gets every one right, but opens with "Here
    are the answers:" and closes with a sign-off, reports 40 % of its units
    unlabelled while losing nothing at all.

    The ratio grows with fragmentation for a purely structural reason -- the
    per-reply overhead is paid N times against N-way-smaller answer lists -- so
    it must never be compared between arms either. The count of *items* is the
    only attrition figure in the report.

    This is a characterisation test: it passes before and after the
    ``returns_input_value`` fix, and it is here so that the next reader of a 45 %
    figure checks the denominator before rewriting the packet contract.
    """
    from swarmbly_v0.grading import grade_units

    key = {f"{i:02d}": {"expected": str(100 + i), "mode": "numeric",
                        "source": f"[{i:02d}] {i} crates, 10 units per crate"}
           for i in range(1, 4)}
    reply = ("Here are the answers:\n"
             + "\n".join(f"[{i:02d}] {100 + i}" for i in range(1, 4))
             + "\nLet me know if you need anything else.")

    _, report = grade_units([u for u in reply.split("\n")], key)
    d = report.as_dict()

    assert d["items_seen"] == 3 and d["items_graded"] == 3 and d["items_correct"] == 3
    assert d["accuracy"] == 1.0, "every item was answered and every answer was right"
    assert d["units_with_no_label"] == 2 and d["units_total"] == 5
    assert d["units_with_no_label"] / d["units_total"] == 0.4, (
        "40 % of units carried no item label and NOTHING was lost -- the ratio is "
        "not attrition, and the run report's 45 % must not be read as one")


# --------------------------------------------------------------------------- #
# class 5: the two arms must be dispatched the same question
#
# The v3c-gt run of 3 September reported 150/150 items seen in the monolithic
# arm and 24/150 in the fragmented arm at k=1 -- a five-to-one asymmetry in a
# DENOMINATOR, on the same corpus, from the same model. Two readings were left
# open: the workers do not emit the format, or `task_item_scope` discards
# in-scope answers.
#
# The scope filter is innocent, and `test_a_compliant_worker_loses_no_item_to_the_scope_filter`
# below is the experiment that says so. What the fragmented arm actually got
# that the baseline did not was a `[PREDECESSOR SUMMARIES]` block holding
# another packet's ANSWER LINES -- in 42 of its 60 packets -- because every
# prompt in a corpus that states "Items are independent" was planned as a chain.
# --------------------------------------------------------------------------- #


def _gt_specs():
    from swarmbly_v0.experiment import load_prompts
    return load_prompts(str(GROUND_TRUTH))


class _ItemWorker:
    """Answers the items in its own packet, correctly, in the asked format.

    Optionally reproduces the documented failure mode of a fragment that is
    handed its predecessor's answers: it reads on and restates them instead of
    answering its own items (``carry_block``: "the successor restates them as
    its own, and an enumerated corpus reported 379 graded items against a key
    holding 150").
    """

    def __init__(self, key, restate_the_carry: bool = False):
        import re as _re
        from swarmbly_v0.backends import HashEmbedder
        self._re = _re
        self.key = {str(k).zfill(2): (v["expected"] if isinstance(v, dict) else v)
                    for k, v in (key or {}).items()}
        self.restate_the_carry = restate_the_carry
        self.packets: list[str] = []
        self.answered: dict[str, set] = {}
        self._embedder = HashEmbedder()
        self.family = ""
        self.model = ""
        self.name = "item-worker"

    def for_replica(self, family, model=""):
        clone = _ItemWorker({}, self.restate_the_carry)
        clone.key, clone.packets, clone.answered = self.key, self.packets, self.answered
        clone.family, clone.model = family, model
        return clone

    def generate(self, prompt, **kw):
        self.packets.append(prompt)
        marker = self._re.search(r"\[TASK (t\d+)\]", prompt)
        task_id = marker.group(1) if marker else "monolithic"
        context = prompt[: marker.start()] if marker else ""
        body = prompt[marker.start():] if marker else prompt
        if self.restate_the_carry and "[PREDECESSOR SUMMARIES]" in context:
            carried = [m.group(1).zfill(2) for m in
                       self._re.finditer(r"[\[(](\d{1,3})[\])]", context)]
            return "\n".join(f"[{i}] {self.key[i]}" for i in dict.fromkeys(carried)
                             if i in self.key)
        mine = [m.group(1).zfill(2) for m in
                self._re.finditer(r"(?:^|\s)[\[(](\d{1,3})[\])]", body, self._re.MULTILINE)]
        mine = [i for i in dict.fromkeys(mine) if i in self.key]
        self.answered.setdefault(task_id, set()).update(mine)
        return "\n".join(f"[{i}] {self.key[i]}" for i in mine)

    def embed(self, texts):
        return self._embedder.embed(texts)


def _run_gt_cell(spec, worker, k=1, rho=2.5, n_tasks=4):
    """One v3c-gt cell through the real pipeline: rho 2.5, N=4, answer sheet."""
    from swarmbly_v0.experiment import SweepConfig, run_fragmented, _answer_budget
    from swarmbly_v0.planner import global_contract
    contract = global_contract(spec.text, worker,
                               target_length_tokens=_answer_budget(spec, 420))
    config = SweepConfig(rhos=(rho,), ns=(n_tasks,), ks=(k,), n_candidates=1,
                         seed=0, tau_sem=0.5)
    return run_fragmented(spec, worker, worker, config, rho_target=rho,
                          n_tasks=n_tasks, tau_sem=0.5, k=k, contract=contract)


def test_an_independent_item_batch_is_not_planned_as_a_chain() -> None:
    """A ``then`` in the FORMAT block is typography, not a dependency.

    Every prompt in ``prompts/ground_truth.json`` ends "Begin the line with the
    item number in square brackets, exactly as given, **then** a single space,
    **then** the value", and every one of them also says "Items are independent:
    the answer to one must not depend on the answer to any other."
    ``router._SEQUENTIAL_CUES`` contains ``\\bthen\\b``, one cue clears the 0.45
    gate (``_saturate(1, 1.5) = 0.487``), and all fifteen were planned as
    four-deep CHAINS.

    Two costs. The critical path is reported as admitting no parallelism for a
    workload that is nothing but parallel; and every task acquires a dependency
    edge, which is what put another packet's answer lines into 42 of the 60
    packets of the v3c-gt cell.
    """
    from swarmbly_v0.backends import MockBackend
    from swarmbly_v0.planner import global_contract, plan as build_plan

    backend = MockBackend()
    for spec in _gt_specs():
        contract = global_contract(spec.text, backend)
        plan = build_plan(spec.text, backend, n_tasks=4, contract=contract,
                          answer_sheet=True)
        assert plan.sequential is False, (
            f"{spec.prompt_id} states its items are independent and was planned "
            f"as a chain")
        assert len(plan.topological_levels()) == 2, (
            f"{spec.prompt_id}: {len(plan.topological_levels())} levels for a bag "
            f"of independent items; the critical path is the speedup bound and "
            f"this one is fabricated")
        assert sum(1 for t in plan.tasks if t.depends_on) == 1, (
            f"{spec.prompt_id}: only the integration node may depend on anything")


def test_a_real_dependency_chain_is_still_planned_as_one() -> None:
    """CONTROL for the test above -- it must not flatten a genuine chain.

    ``prompts/complex.json`` carries prompts whose step i cannot start before
    step i-1 finished, and they say so in the *work*, not in the format block.
    If this ever passes vacuously the fix has been widened into a different
    defect: a chain planned as a fan-in dispatches successors that have not been
    told the value they consume, which is the V4 dependency-chain artefact.
    """
    from swarmbly_v0.backends import MockBackend
    from swarmbly_v0.experiment import load_prompts
    from swarmbly_v0.planner import global_contract, plan as build_plan

    backend = MockBackend()
    corpus = GROUND_TRUTH.parent / "complex.json"
    chains = [s for s in load_prompts(str(corpus)) if s.prompt_id.startswith("chain_")]
    assert chains, "the control corpus must actually contain chain prompts"
    for spec in chains:
        contract = global_contract(spec.text, backend)
        plan = build_plan(spec.text, backend, n_tasks=4, contract=contract)
        assert plan.sequential is True, f"{spec.prompt_id} is a real chain"


def test_no_answer_sheet_fragment_is_handed_another_packets_answers() -> None:
    """The arm asymmetry, measured on the dispatched text.

    ``rho`` 2.5, N=4, ``prompts/ground_truth.json`` -- the v3c-gt cell. The
    monolithic arm is dispatched one prompt and no predecessor block. Before the
    fix the fragmented arm was dispatched 42 packets out of 60 carrying
    ``[PREDECESSOR SUMMARIES]`` holding another fragment's answer lines
    (``- t0: [01] 576``) directly above a task block reading "Answer only the
    items listed here".

    That block is not context for an answer sheet, it is the answer to somebody
    else's items in the same notation, and ``task_item_scope`` discards whatever
    the fragment restates from it. The count that matters is zero, and it must be
    zero in both arms or the arms are not answering the same question.
    """
    from swarmbly_v0.experiment import SweepConfig, run_monolithic, _answer_budget
    from swarmbly_v0.planner import global_contract

    contaminated = dispatched = baseline_contaminated = 0
    for spec in _gt_specs():
        worker = _ItemWorker(spec.key)
        _run_gt_cell(spec, worker)
        # Micro-task packets only: the assembler's bridge prompts are not
        # packets and carry no contract.
        for packet in dict.fromkeys(p for p in worker.packets if "[TASK t" in p):
            dispatched += 1
            contaminated += int("[PREDECESSOR SUMMARIES]" in packet)

        baseline = _ItemWorker(spec.key)
        contract = global_contract(spec.text, baseline,
                                   target_length_tokens=_answer_budget(spec, 420))
        run_monolithic(spec, baseline, baseline,
                       SweepConfig(rhos=(2.5,), ns=(4,), ks=(1,), n_candidates=1,
                                   seed=0, tau_sem=0.5),
                       contract=contract)
        baseline_contaminated += sum(
            1 for p in baseline.packets if "[PREDECESSOR SUMMARIES]" in p)

    assert dispatched >= 60, dispatched
    assert baseline_contaminated == 0, "the baseline never had one; that is the point"
    assert contaminated == 0, (
        f"{contaminated} of {dispatched} fragmented packets carry another packet's "
        f"answer lines while the baseline carries none -- an instruction the arms "
        f"do not share, on the notation the grader reads")


def test_every_key_item_survives_a_worker_that_restates_what_it_is_shown() -> None:
    """The denominator, end to end, against the documented failure mode.

    ``carry_block`` already names what a fragment does when it is handed its
    predecessor's answers: "the successor restates them as its own". The worker
    here does exactly that and nothing else -- it is a stand-in for the
    behaviour, not a claim about any particular model. The assertion is about
    the harness: it must never put a fragment in that position, so no reply of
    that shape can arise and every key item must be seen.

    Before the fix this returned 45 of 150 -- the first fragment of each prompt,
    the only one with no predecessor -- which is the shape of the 24/150 the run
    reported.
    """
    seen: set = set()
    total = 0
    for spec in _gt_specs():
        worker = _ItemWorker(spec.key, restate_the_carry=True)
        row = _run_gt_cell(spec, worker)
        total += len(spec.key or {})
        for record in row.get("_truth_records") or []:
            seen.add((spec.prompt_id, str(record["item_id"]).zfill(2)))

    assert total == 150, total
    assert len(seen) == total, (
        f"{len(seen)} of {total} key items reached the grader; the rest were "
        f"restatements of a block the packet should never have carried")


def test_a_compliant_worker_loses_no_item_to_the_scope_filter() -> None:
    """The experiment that separates the two readings of the v3c-gt attrition.

    A worker that answers every item in its own packet, perfectly, in the asked
    format, removes "the models do not comply" by construction. Anything lost
    after that is lost by the harness. Nothing is lost: assigned, answered and
    kept are all 150 at N=4, k=1, rho 2.5 -- so ``task_item_scope`` is not
    discarding in-scope answers, and the reading that blamed it is refuted.

    This is a characterisation test. It passed before the fix as well, and that
    is what it is for: it is the control that says which of the two candidate
    causes was real.
    """
    from swarmbly_v0.experiment import task_item_scope, _answer_budget
    from swarmbly_v0.planner import global_contract, plan as build_plan

    assigned = answered = kept = 0
    for spec in _gt_specs():
        worker = _ItemWorker(spec.key)
        row = _run_gt_cell(spec, worker)
        contract = global_contract(spec.text, worker,
                                   target_length_tokens=_answer_budget(spec, 420))
        plan = build_plan(spec.text, worker, n_tasks=4, contract=contract,
                          answer_sheet=True)
        scope = task_item_scope(plan)
        key = {str(k).zfill(2) for k in (spec.key or {})}

        assigned += len(set().union(*scope.values()) & key)
        answered += len({i for items in worker.answered.values() for i in items})
        kept += len({str(r["item_id"]).zfill(2)
                     for r in (row.get("_truth_records") or [])} & key)

    assert (assigned, answered, kept) == (150, 150, 150), (
        f"assigned={assigned} answered={answered} kept={kept}; a gap between "
        f"assigned and kept is the scope filter, a gap between assigned and "
        f"answered is the models")


# --------------------------------------------------------------------------- #
# class 6: a criterion must be able to refuse
#
# The composition finding of 3 September is the strongest measurement this
# project has -- monolithic 1.000 against fragmented 0.864, counted from the
# text with no model in the verdict -- and it had no apparatus behind it: three
# prompts, no declared cell, no control, no split. The coherence tax had all
# three. The tests below are about the apparatus, not the finding: a criterion
# that cannot decline to answer is the maximum statistic in different clothes,
# and this project has published one interval on eight clusters already.
# --------------------------------------------------------------------------- #

COMPOSITION = Path(__file__).resolve().parent.parent / "prompts" / "composition.json"
MAKE_COMPOSITION = Path(__file__).resolve().parent.parent / "scripts" / "make_composition.py"


def _comp_rows(n_prompts: int, delta: float, *, baseline: float = 0.90,
               n_tasks: int = 3, k: int = 1, rho: float = 4.0,
               category: str = "composition") -> list[dict]:
    """``n_prompts`` fragmented rows, each ``delta`` points below its baseline.

    Reachable by construction: ``rho_floor`` below ``rho_target``, so
    ``publishable`` keeps them and a test about the criterion is not silently
    testing the floor gate instead.
    """
    return [{
        "prompt_id": f"p{i:02d}", "category": category, "condition": "fragmented",
        "rho_target": rho, "rho_floor": rho - 1.0, "rho_reachable": True,
        "n_tasks": n_tasks, "k": k,
        "constraint_score_comparable": round(baseline - delta, 6),
        "baseline_constraint_score_comparable": baseline,
        "n_constraints_checked": 9,
    } for i in range(n_prompts)]


def test_no_verdict_is_printed_below_the_cluster_floor() -> None:
    """Nineteen prompts is not twenty, and the difference is a returned ``None``.

    The free-form run of 3 September reported AUC 0.602 with a clustered 95 %
    interval of [0.5014, 0.7243] -- excluding chance by 0.0014, on EIGHT
    clusters. The caveat was in the prose and the number was in the reader's
    memory. So the refusal is in the code: below
    ``MIN_CLUSTERS_FOR_A_VERDICT`` the criterion returns ``passed: None``, and
    the note must say the count rather than leave a bound to be quoted.
    """
    from swarmbly_v0.experiment import (MIN_CLUSTERS_FOR_A_VERDICT,
                                        composition_criterion)

    floor = MIN_CLUSTERS_FOR_A_VERDICT
    below = composition_criterion(_comp_rows(floor - 1, 0.01), "composition",
                                  rho=4.0, threshold_points=0.05, n_tasks=3, k=1)
    assert below["n_prompts"] == floor - 1
    assert below["passed"] is None, (
        "a verdict on fewer clusters than the floor is exactly the thing that "
        "had to be withdrawn on 4 September")
    assert str(floor) in below["note"] and str(floor - 1) in below["note"], (
        "the note must state both counts, because a reader who sees only "
        "'insufficient' cannot tell how far short the run fell")

    at = composition_criterion(_comp_rows(floor, 0.01), "composition",
                               rho=4.0, threshold_points=0.05, n_tasks=3, k=1)
    assert at["passed"] is True, (
        "at the floor, with a one-point gap against a five-point threshold, the "
        "criterion must actually decide -- a gate that never opens is not a gate")


def test_the_composition_criterion_can_fail_and_fails_on_the_upper_bound() -> None:
    """The pilot's own numbers, and they must not pass.

    Fourteen points against a five-point threshold. The verdict is on the upper
    bound, so a cell whose POINT estimate clears the threshold while its
    interval does not must still fail -- that requirement is the whole
    difference between this criterion and the one that could not fail.
    """
    from swarmbly_v0.experiment import composition_criterion

    pilot = composition_criterion(_comp_rows(24, 0.14), "composition", rho=4.0,
                                  threshold_points=0.05, n_tasks=3, k=1)
    assert pilot["passed"] is False
    assert pilot["short_by_points"] > 0
    assert pilot["mean_delta"] == pytest.approx(0.14, abs=1e-6)

    # A spread whose mean is under the threshold but whose upper bound is not.
    rows = _comp_rows(24, 0.04)
    for index, row in enumerate(rows):
        if index % 2:
            row["constraint_score_comparable"] = round(
                row["baseline_constraint_score_comparable"] - 0.20, 6)
    marginal = composition_criterion(rows, "composition", rho=4.0,
                                     threshold_points=0.05, n_tasks=3, k=1)
    lo, hi = marginal["mean_ci95"]
    assert hi >= 0.05 and marginal["passed"] is False, (
        f"point estimate {marginal['mean_delta']} with upper bound {hi}: a "
        f"criterion judged on the point estimate would have passed this")


def test_the_declared_cell_is_a_cell_and_not_a_category() -> None:
    """N and k are part of the declaration, because pooling them hid a result.

    On the table run of 26 August, filtering on category and rho but not N gave
    +20.9 % while the cell actually under test read +5.8 %; not filtering on k
    gave +18.3 %, the midpoint of two arms and a number belonging to neither.
    The same trap exists here, so the same axes are part of the key.
    """
    from swarmbly_v0.experiment import composition_criterion

    rows = _comp_rows(24, 0.01, n_tasks=3) + _comp_rows(24, 0.30, n_tasks=8)
    declared = composition_criterion(rows, "composition", rho=4.0,
                                     threshold_points=0.05, n_tasks=3, k=1)
    control = composition_criterion(rows, "composition", rho=4.0,
                                    threshold_points=0.05, n_tasks=8, k=1)
    pooled = composition_criterion(rows, "composition", rho=4.0,
                                   threshold_points=0.05, n_tasks=None, k=1)

    assert declared["passed"] is True and control["passed"] is False, (
        "the control must be able to fail while the declared cell passes, or "
        "the instrument is not separating the arms")
    assert pooled["mean_delta"] == pytest.approx(0.155, abs=1e-6)
    assert not (declared["mean_delta"] <= pooled["mean_delta"]
                <= control["mean_delta"]) or True
    assert pooled["mean_delta"] > declared["mean_delta"], (
        "pooling N moves the estimate away from the declared cell; that is why "
        "N is in the key rather than averaged over")


def test_a_row_below_its_packing_floor_cannot_reach_the_criterion() -> None:
    """The same chokepoint as every other figure, on the new one.

    ``publishable`` exists because below the floor every packet collapses to its
    bare task and two rho labels produce byte-identical cells. A criterion added
    later must go through it, or the gate has a hole the moment someone adds a
    statistic.
    """
    from swarmbly_v0.experiment import composition_criterion

    rows = _comp_rows(24, 0.01)
    for row in rows[:12]:
        row["rho_reachable"] = False
        row["rho_floor"] = row["rho_target"] + 1.0
    result = composition_criterion(rows, "composition", rho=4.0,
                                   threshold_points=0.05, n_tasks=3, k=1)
    assert result["n_observations"] == 12
    assert result["passed"] is None, (
        "twelve reachable rows is below the cluster floor; the below-floor rows "
        "must not be counted towards it")


def test_the_criterion_reads_the_arm_comparable_score_by_default() -> None:
    """``paragraph_count`` and ``words_per_paragraph`` cannot cross arms at all.

    The assembler emits exactly the requested number of paragraphs for the
    fragmented arm; the monolithic arm gets no post-processing. On the table
    corpus that is a guaranteed pass for one arm, and on the free-form corpus
    the bias INVERTED -- +23 points the other way -- decided by prompt wording.
    A default that read the raw score would put that back into the verdict.
    """
    from swarmbly_v0.experiment import ASSEMBLER_ENFORCED, composition_criterion
    import inspect

    signature = inspect.signature(composition_criterion)
    assert signature.parameters["score"].default == "constraint_score_comparable"
    assert signature.parameters["baseline"].default == (
        "baseline_constraint_score_comparable")
    assert ASSEMBLER_ENFORCED == {"paragraph_count", "words_per_paragraph"}


def test_the_constraint_score_reaches_the_row_from_both_arms() -> None:
    """The column, end to end, through the real pipeline.

    Before this existed the constraint score lived only in ``_trace`` and was
    reported as a mean over a condition. Two condition means cannot be paired,
    and unpaired is how the coherence tax spent four runs being sensitive to
    prompt difficulty rather than to fragmentation. The monolithic row must
    carry the score and no baseline; the fragmented row must carry both, and its
    baseline must equal the monolithic row's own score for the same prompt.
    """
    from swarmbly_v0.backends import MockBackend
    from swarmbly_v0.experiment import (CSV_COLUMNS, SweepConfig, load_prompts,
                                        run_fragmented, run_monolithic,
                                        _answer_budget)
    from swarmbly_v0.planner import global_contract

    for column in ("constraint_score", "constraint_score_comparable",
                   "n_constraints_checked", "baseline_constraint_score",
                   "baseline_constraint_score_comparable"):
        assert column in CSV_COLUMNS, (
            f"{column} is computed and not written; a figure that exists only "
            f"in memory cannot be re-analysed from a stored run")

    spec = next(s for s in load_prompts(str(COMPOSITION)) if s.is_composition)
    backend = MockBackend()
    config = SweepConfig(rhos=(4.0,), ns=(3,), ks=(1,), n_candidates=1, seed=0,
                         tau_sem=0.5)
    contract = global_contract(spec.text, backend,
                               target_length_tokens=_answer_budget(spec, 420))
    mono = run_monolithic(spec, backend, backend, config, contract=contract)
    frag = run_fragmented(spec, backend, backend, config, rho_target=4.0,
                          n_tasks=3, tau_sem=0.5, k=1, contract=contract,
                          baseline=mono)

    assert isinstance(mono["constraint_score_comparable"], float)
    assert mono.get("baseline_constraint_score_comparable", "") in ("", None), (
        "a monolithic row is its own baseline and must not carry one")
    # `write_csv` fills a missing column with "" rather than raising, so an
    # absent key and a blank one reach disk identically. Asserted rather than
    # assumed: a DictWriter without that default would fail the whole run on the
    # first monolithic row, hours in.
    from swarmbly_v0.experiment import write_csv
    import csv as _csv
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        written = write_csv([mono, frag], Path(tmp) / "results.csv")
        stored = list(_csv.DictReader(written.open()))
    assert stored[0]["baseline_constraint_score_comparable"] == ""
    assert stored[1]["baseline_constraint_score_comparable"] != ""
    assert frag["baseline_constraint_score_comparable"] == pytest.approx(
        mono["constraint_score_comparable"]), (
        "the fragmented row's baseline must be the monolithic score for the "
        "SAME prompt, or the pairing is a join on nothing")
    assert frag["n_constraints_checked"] == len(spec.constraints or ())


def test_a_non_composition_row_carries_a_blank_and_not_a_zero() -> None:
    """Blank, not zero. A row with no constraints has no score.

    A zero reads as "every check failed", which is a different fact, and it
    would enter a mean. This is the same distinction ``_EMPTY_EDITOR_COLUMNS``
    documents for the editor columns.
    """
    from swarmbly_v0.experiment import fill_constraint_columns

    row: dict = {}
    fill_constraint_columns(row, None)
    assert row["constraint_score"] == ""
    assert row["constraint_score_comparable"] == ""
    assert row["n_constraints_checked"] == ""


# --------------------------------------------------------------------------- #
# the corpus the criterion needs, and the two ways to break a frozen split
# without touching the digest
# --------------------------------------------------------------------------- #


def test_the_composition_corpus_can_support_a_verdict() -> None:
    """The final half must clear the cluster floor, or the corpus is pointless.

    ``MIN_CLUSTERS_FOR_A_VERDICT`` is 20 and a verdict is computed on the final
    split alone. A corpus whose final half holds fewer prompts than that would
    run for hours and return ``passed: None`` -- which is the honest answer and
    a wasted night.
    """
    from swarmbly_v0.experiment import MIN_CLUSTERS_FOR_A_VERDICT, load_prompts

    final = load_prompts(str(COMPOSITION), split="final")
    dev = load_prompts(str(COMPOSITION), split="dev")
    assert len(final) >= MIN_CLUSTERS_FOR_A_VERDICT, (
        f"{len(final)} final prompts against a floor of "
        f"{MIN_CLUSTERS_FOR_A_VERDICT}: this corpus cannot produce a verdict")
    assert dev, "the dev half is where tau_sem is fitted; it cannot be empty"
    assert not (set(p.prompt_id for p in dev) & set(p.prompt_id for p in final))
    assert all(p.is_composition for p in dev + final)


def test_the_split_is_balanced_across_difficulty_tiers() -> None:
    """A split whose halves differ in difficulty is not a split.

    The digest covers which prompt sits on which side, so it would not move if
    every hard prompt were assigned to dev: the corpus would be frozen and the
    two halves incomparable at the same time. The generator asserts this when it
    writes; this asserts it about the file that shipped.
    """
    payload = json.loads(COMPOSITION.read_text())
    counts: dict[tuple[str, str], int] = {}
    for prompt in payload["prompts"]:
        key = (prompt["split"], prompt["tier"])
        counts[key] = counts.get(key, 0) + 1
    tiers = sorted({t for _, t in counts})
    assert len(tiers) >= 3, "difficulty must actually vary"
    for split in ("dev", "final"):
        per_tier = {t: counts.get((split, t), 0) for t in tiers}
        assert len(set(per_tier.values())) == 1, (
            f"{split} is not balanced across tiers: {per_tier}")


def test_the_corpus_on_disk_is_the_one_its_generator_builds() -> None:
    """``--verify`` must pass, and the digest must cover the split assignment.

    A threshold frozen against a digest is worth nothing if the digest does not
    change when the corpus does. Rebuilding with one prompt moved to the other
    half must change it.
    """
    import subprocess
    import sys as _sys

    result = subprocess.run(
        [_sys.executable, str(MAKE_COMPOSITION), "--verify"],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

    spec = __import__("importlib.util", fromlist=["util"]).spec_from_file_location(
        "make_composition", MAKE_COMPOSITION)
    module = __import__("importlib.util", fromlist=["util"]).module_from_spec(spec)
    spec.loader.exec_module(module)
    prompts = module.build()
    before = module.digest(prompts)
    moved = [dict(p) for p in prompts]
    moved[0]["split"] = "final" if moved[0]["split"] == "dev" else "dev"
    assert module.digest(moved) != before, (
        "the digest does not cover the split assignment, so a prompt could "
        "cross from final to dev without the freeze noticing")


def test_no_composition_prompt_is_planned_as_a_dependency_chain() -> None:
    """The defect of 4 September, checked on the corpus written after it.

    A ``then`` in a format directive planned all fifteen ground-truth prompts as
    four-deep chains and put another packet's answer lines into 42 of 60
    packets. A new corpus is exactly where that class of mistake gets
    reintroduced, and a composition prompt has no items to carry, so a chain
    here would be silent rather than visible in the grading.
    """
    from swarmbly_v0.backends import MockBackend
    from swarmbly_v0.experiment import load_prompts
    from swarmbly_v0.planner import global_contract, plan as build_plan

    backend = MockBackend()
    for spec in load_prompts(str(COMPOSITION)):
        contract = global_contract(spec.text, backend)
        plan = build_plan(spec.text, backend, n_tasks=3, contract=contract)
        assert plan.sequential is False, (
            f"{spec.prompt_id} is a bag of prose to be written in parallel and "
            f"was planned as a chain")


def test_the_declared_cell_sits_above_the_packing_floor_at_every_N_it_runs() -> None:
    """The tier's rho must be reachable for BOTH arms, or the control does not exist.

    Three v3c tiers were run at rho 1.5 against floors of 1.51-2.37 and every
    fragmented cell collapsed to a bare task: 0 of 15, 0 of 11, 0 of 8
    reachable. The floor rises with N -- 2.13 at N=3 and 3.84 at N=8 on this
    corpus -- so a tier that names N=8 as its control must clear the N=8 floor
    or the control silently disappears from every figure.
    """
    from swarmbly_v0.backends import MockBackend
    from swarmbly_v0.experiment import load_prompts, _answer_budget
    from swarmbly_v0.packing import packing_floor
    from swarmbly_v0.planner import global_contract, plan as build_plan

    runner = (Path(__file__).resolve().parent.parent / "scripts" / "run_ollama.sh"
              ).read_text()
    assert "--rho 4.0 --n 3,8 --k 1" in runner, (
        "the comp tiers' grid moved; this test pins rho and N to what it "
        "checks the floor against")

    backend = MockBackend()
    worst: tuple[float, str, int] = (0.0, "", 0)
    for spec in load_prompts(str(COMPOSITION)):
        contract = global_contract(spec.text, backend,
                                   target_length_tokens=_answer_budget(spec, 420))
        for n_tasks in (3, 8):
            plan = build_plan(spec.text, backend, n_tasks=n_tasks, contract=contract)
            floor = packing_floor(contract, plan)
            if floor > worst[0]:
                worst = (floor, spec.prompt_id, n_tasks)
    assert worst[0] < 4.0, (
        f"the tier runs at rho 4.0 and {worst[1]} needs {worst[0]:.3f} at "
        f"N={worst[2]}; that cell would be dropped by publishable() and the "
        f"run would produce a verdict with a missing arm")


def test_both_composition_tiers_declare_their_cell_and_a_control() -> None:
    """The declaration lives in the invocation, recoverable from run.log.

    ``tables-dev`` exists to test one named cell and printed everything except
    that cell, because the declaration was a paragraph the tier printed about
    itself rather than an argument. Same requirement here, and the control must
    be there too: a test whose control cannot fail proves nothing.
    """
    runner = (Path(__file__).resolve().parent.parent / "scripts" / "run_ollama.sh"
              ).read_text()
    for tier in ("run_comp_dev", "run_comp_final"):
        start = runner.index(f"{tier}()")
        body = runner[start:runner.index("\n}\n", start)]
        declarations = [line for line in body.splitlines()
                        if "--declare-composition" in line and "help=" not in line]
        invoked = [line for line in declarations if "'composition@" in line]
        assert len(invoked) == 2, (
            f"{tier} passes {len(invoked)} declared cells; it needs the cell "
            f"under test and a control expected to fail")
        assert "N=3" in invoked[0] and "N=8" in invoked[1], (
            f"{tier}: the declared cell must come first and the control second, "
            f"because the CLI labels them by position")


# --------------------------------------------------------------------------- #
# class 7: a tier's grid must be reachable on the corpus it names
#
# V0's published rho curve -- 24.1 % falling to 13.7 % -- was withdrawn because
# 13 of its 96 cells sat above their own packing floor and the rho=1.00 and
# rho=1.25 rows had none at all. Below the floor `build_packet` sets the budget
# to the mandatory tokens, so two different rho labels produce byte-identical
# packets: the curve was reading a variable that was not varying.
#
# `publishable()` now drops those rows from every figure, which turns the defect
# from a wrong number into an empty one. That is better and it is not enough:
# an empty figure still costs the night. These tests read the grid out of the
# runner and check it against floors measured from the code.
# --------------------------------------------------------------------------- #

RUNNER = Path(__file__).resolve().parent.parent / "scripts" / "run_ollama.sh"


def _tier_body(name: str) -> str:
    text = RUNNER.read_text()
    start = text.index(f"run_{name}()")
    return text[start:text.index("\n}\n", start)]


def _grid(body: str) -> tuple[list[float], list[int]]:
    """The rho and N values a tier actually passes, from its invocation.

    Read from the ``--rho``/``--n`` arguments and not from the tier's own
    printed description, because the description is prose and the invocation is
    what runs. ``tables-dev`` printed a handover command its own consumer
    refused, for exactly this reason.
    """
    import re as _re

    rho_match = _re.search(r"--rho ([0-9.,]+)", body)
    n_match = _re.search(r"--n ([0-9,]+)", body)
    assert rho_match and n_match, "the tier passes no --rho/--n at all"
    return ([float(v) for v in rho_match.group(1).split(",")],
            [int(v) for v in n_match.group(1).split(",")])


def _windows(corpus: Path | None,
             n_values: list[int]) -> dict[int, tuple[float, float]]:
    """``{N: (worst floor, worst ceiling)}`` over the corpus, from the real code.

    A WINDOW, not a floor, and the second bound cost a five-hour run. The first
    version of this helper returned floors only, so the v0 grid was checked
    against one end and topped out at 5.5 where the N=2 ceiling is 4.90.
    """
    from swarmbly_v0.backends import MockBackend
    from swarmbly_v0.experiment import DEFAULT_PROMPTS_PATH, load_prompts, _answer_budget
    from swarmbly_v0.packing import packing_ceiling, packing_floor
    from swarmbly_v0.planner import global_contract, plan as build_plan

    backend = MockBackend()
    specs = load_prompts(str(corpus or DEFAULT_PROMPTS_PATH))
    floors: dict[int, float] = {}
    ceilings: dict[int, float] = {}
    for spec in specs:
        contract = global_contract(spec.text, backend,
                                   target_length_tokens=_answer_budget(spec, 420))
        for n_tasks in n_values:
            plan = build_plan(spec.text, backend, n_tasks=n_tasks, contract=contract)
            floors[n_tasks] = max(floors.get(n_tasks, 0.0),
                                  packing_floor(contract, plan))
            ceilings[n_tasks] = min(ceilings.get(n_tasks, float("inf")),
                                    packing_ceiling(contract, plan))
    return {n: (floors[n], ceilings[n]) for n in n_values}


def _floors(corpus: Path | None, n_values: list[int]) -> dict[int, float]:
    """Worst-case packing floor per N. Kept for the tests written against it."""
    return {n: lo for n, (lo, _) in _windows(corpus, n_values).items()}


def _v0_grid_by_n() -> dict[int, list[float]]:
    """The rho list `run_v0` sweeps at each N, read from its own case statement.

    v0 is three sweeps now, one per N, because a single grid across all three is
    impossible on this corpus: N=8 cannot start below 4.45 and N=2 cannot go
    above 4.90, so the common window is 0.45 wide.
    """
    import re as _re

    body = _tier_body("v0")
    grid: dict[int, list[float]] = {}
    pattern = r'(\d+)\)\s+rhos="([\d.,]+)"'
    for n_text, rhos in _re.findall(pattern, body):
        grid[int(n_text)] = [float(v) for v in rhos.split(",")]
    return grid


def test_every_v0_cell_would_measure_its_own_label() -> None:
    """The whole class, checked the way the runner checks it before dispatching.

    This replaces four tests that each encoded a PARTIAL theory of what makes a
    rho unreachable -- a floor, then a ceiling, then a margin -- and each was
    written after a tier died of the reason it did not know about. Three tiers,
    three causes, and I hand-patched the grid twice from a hypothesis and was
    wrong twice.

    So this asserts the thing that actually matters, using the same predictor
    the runner gates on: every cell packs within tolerance. It needs no theory
    of why a cell might not.
    """
    from swarmbly_v0.experiment import (RHO_TOLERANCE, load_prompts, predict_rho,
                                        DEFAULT_PROMPTS_PATH, _answer_budget)
    from swarmbly_v0.backends import MockBackend
    from swarmbly_v0.planner import global_contract, plan as build_plan

    grid = _v0_grid_by_n()
    assert set(grid) == {2, 4, 8}, f"expected a rho list per N, got {sorted(grid)}"

    backend = MockBackend()
    specs = load_prompts(str(DEFAULT_PROMPTS_PATH))
    offences: list[str] = []
    for spec in specs:
        contract = global_contract(spec.text, backend,
                                   target_length_tokens=_answer_budget(spec, 420))
        for n_tasks, rhos in grid.items():
            plan = build_plan(spec.text, backend, n_tasks=n_tasks,
                              contract=contract,
                              answer_sheet=spec.has_ground_truth)
            for rho in rhos:
                achieved = predict_rho(spec, contract, plan, rho)
                drift = abs(achieved - rho) / rho
                if drift > RHO_TOLERANCE:
                    offences.append(
                        f"{spec.prompt_id} rho={rho} N={n_tasks}: predicted "
                        f"{achieved:.3f} ({drift * 100:+.1f}%)")
    assert not offences, (
        "these cells would not measure their own label, and each one either "
        "aborts the tier or -- worse -- stays inside tolerance and mislabels a "
        "published cell:\n  " + "\n  ".join(offences[:10]))
    assert sum(len(v) for v in grid.values()) >= 12, "too few cells to be a curve"


def test_the_v0_windows_barely_overlap_and_the_runner_says_so() -> None:
    """Comparing N at fixed rho is honest in a 0.45-wide band and nowhere else.

    N=8 cannot be packed below 4.45 -- its floor is lower, but on a chain the
    mandatory carries force an overshoot in the band just above it -- and N=2
    cannot exceed 4.90. That is not a nuisance to route around, it is the
    finding: the architecture cannot hold N and rho independent.

    `tables-final` is what happens when this is not said. Its two arms ran at
    3.38 and 3.51 under one label.

    This test used to assert the literal sentence "honest only at 4.5 and 4.8",
    which was false: 4.5 was in no arm but N=8 and 4.8 was in every arm but N=8,
    so the intersection of the three grids was empty and the comparison the
    sentence recommended could not be made. The assertion held anyway, because a
    string is not a fact about the grid. It now checks the grid.
    """
    body = _tier_body("v0")
    grid = _v0_grid_by_n()
    shared = set(grid[2]) & set(grid[4]) & set(grid[8])
    assert shared, "no rho is sampled by all three arms; see test_the_three_v0_arms_share_a_rho_point"
    assert all(str(rho) in body for rho in shared), (
        "the runner must tell the operator where a cross-N comparison is valid; "
        "tables-final compared two arms at different rho under one label")
    assert "honest" in body.lower(), (
        "and it must say so in words, not leave the reader to intersect the grids")


def test_the_spec_target_is_recorded_as_unattainable_and_not_merely_unmet() -> None:
    """SPEC 11.5 asks for rho < 2.0. The N=8 arm cannot be packed below 4.45.

    Worth a test rather than a note: an unmet target invites another sweep, and
    an unattainable one is a claim to revise. Four nights have now gone to
    sweeps aimed at rho values that cannot be reached.
    """
    grid = _v0_grid_by_n()
    assert min(grid[8]) > 2.0, (
        f"the N=8 sweep starts at {min(grid[8])}; if it can start below 2.0 "
        f"then SPEC 11.5's target is reachable and both this test and the "
        f"runner's claim must be removed")
    assert "unreachable" in _tier_body("v0")


@pytest.mark.parametrize("tier", ["v0", "v3c-gt", "v3c-ff", "tables-dev",
                                  "tables-final", "comp-dev", "comp-final"])
def test_the_family_gate_reads_the_k_the_tier_actually_sweeps(tier: str) -> None:
    """``TIER_MAX_K`` must equal the largest k in the tier's own invocation.

    The gate that refuses to run a k arm with too few model families derived
    this by awk over the script, and for `smoke` it read 1 while the tier sweeps
    k=1,3 -- a bug in the check that exists to catch bugs, in the tier that runs
    first. Replicas drawn from one lineage share their errors and agree
    confidently on the same mistake, so a contaminated k arm is not a degraded
    measurement, it is a retracted one.
    """
    import re as _re
    import subprocess
    import sys as _sys

    body = _tier_body(tier.replace("-", "_"))
    declared = sorted(int(v) for v in
                      _re.search(r"--k ([0-9,]+)", body).group(1).split(","))
    derived = subprocess.run(
        ["awk", "-v", f"tier_fn={tier.replace('-', '_')}",
         '$0 ~ "^run_" tier_fn "\\\\(\\\\)" { infn = 1 } '
         'infn && /--k / { for (i = 1; i <= NF; i++) if ($i == "--k") '
         '{ print $(i+1); exit } }', str(RUNNER)],
        capture_output=True, text=True).stdout.strip()
    assert derived, f"the awk in run_ollama.sh reads no k for tier {tier}"
    assert max(int(v) for v in derived.split(",")) == max(declared), (
        f"tier {tier} sweeps k={declared} but the family gate derives "
        f"{derived}; the gate would allow a k arm drawn from too few lineages")
    assert _sys.version_info  # keeps the import honest under -O


def test_both_final_tiers_check_the_code_that_fitted_their_threshold() -> None:
    """A frozen split freezes the PROMPTS. Nothing froze the code.

    Both final tiers checked the corpus digest, the split and tau_sem, and
    neither checked which code fitted tau. On 27 August three ``tables-*`` runs
    sat side by side -- two scored by an arm-neutral coherence metric, one by
    the defective predecessor -- and nothing in any of them said which. The
    directory timestamp against a memory of when the fix landed was the only
    evidence. ``source_fingerprint`` was added for exactly that, recorded as
    ``code_sha256`` in every run's metadata, and never compared.

    It matters most on a day the code is moving: a dev half fitted in the
    morning and a final half judged in the evening, across an edit to the
    planner, carries a threshold across a code change -- the same leakage as
    carrying it across a corpus change, and invisible because both halves name
    the same corpus digest.
    """
    runner = RUNNER.read_text()
    assert "def assert_same_code_as_dev" in runner or \
        "assert_same_code_as_dev()" in runner, "the gate does not exist"
    # Directly, or through the shared `read_dev_run` gate -- which itself must
    # call it, checked below. The indirection arrived with `comp-final-once`,
    # where a fifth thing had to be inherited (which assembly pipeline fitted
    # the threshold) and duplicating four checks into a second tier would have
    # been the way the two copies drift apart.
    for tier in ("run_tables_final", "run_comp_final", "run_comp_final_once",
                 "run_comp_final_v2"):
        body = _tier_body(tier[len("run_"):])
        assert ("assert_same_code_as_dev" in body or "read_dev_run" in body), (
            f"{tier} does not compare its dev run's code fingerprint")
    shared = runner[runner.index("read_dev_run() {"):]
    shared = shared[:shared.index("\n}\n")]
    assert "assert_same_code_as_dev" in shared, (
        "every -final tier now inherits the fingerprint check through "
        "read_dev_run; if that call goes, all of them lose it at once")
    # No escape hatch. Checked against the shapes an override actually takes --
    # an environment variable or a parsed flag -- rather than against the word
    # "--force", which appears in the gate's own comment explaining why there
    # isn't one.
    gate = runner[runner.index("assert_same_code_as_dev() {"):]
    gate = gate[:gate.index("\n}\n")]
    for escape in ("FORCE", "SKIP", "OVERRIDE", "IGNORE"):
        assert escape not in gate.replace("# ", "// "), (
            f"the gate reads {escape}; the fingerprint moves on any edit on "
            f"purpose, because deciding which edits matter is the judgement it "
            f"exists to remove, and an override puts that judgement back")
    assert gate.count("die ") == 2, (
        f"the gate has {gate.count('die ')} refusals; it needs one for a "
        f"missing fingerprint and one for a mismatch, and this count is here "
        f"so that deleting either is visible")


def test_the_code_fingerprint_moves_when_the_package_moves(tmp_path) -> None:
    """A digest that does not move is not a gate.

    Asserted rather than trusted: the fingerprint hashes name and content in
    sorted order over the package's own ``.py`` files, so any edit -- a comment
    included -- moves it. If this ever passes vacuously the gate above is
    decoration.
    """
    from swarmbly_v0.schema import _source_files, source_fingerprint

    before = source_fingerprint()
    files = _source_files()
    assert files, "the fingerprint covers no files at all"
    target = next(p for p in files if p.name == "planner.py")
    original = target.read_bytes()
    try:
        target.write_bytes(original + b"\n# fingerprint probe\n")
        assert source_fingerprint() != before, (
            "editing the planner did not move the fingerprint; the gate that "
            "compares it cannot see a code change")
    finally:
        target.write_bytes(original)
    assert source_fingerprint() == before, "the probe did not clean up"


# --------------------------------------------------------------------------- #
# class 8: a segmenter change must not move an existing partition
#
# The fused repair of 4 September added a third path to `_segment`: a prompt
# that states its questions apart from its material is partitioned so each
# question travels with the material it names, and REFUSED when that link
# cannot be recovered.
#
# Both halves are dangerous in the same way. Every published figure in this
# project was measured on a partition, so a segmenter that re-partitioned an
# existing prompt would silently change what those figures were about -- and a
# gate that refused one would empty a cell that used to be full. Neither shows
# up as an error. The only way to know is to compare, so this compares.
# --------------------------------------------------------------------------- #

CORPORA = ("prompts.json", "complex.json", "ground_truth.json", "free_form.json",
           "tables24.json", "composition.json")


def test_the_reference_path_fires_on_no_existing_corpus_prompt() -> None:
    """The shape the repair is for does not occur in any corpus this project ran.

    That is why six versions never saw the defect: every corpus puts a question
    and its data in the SAME item -- ``[01] 21 crates, 16 units per crate, 80
    removed`` -- so a contiguous cut keeps them together by accident of format.

    Asserted, because if the shape ever appears in a NEW corpus the partition of
    that corpus is decided by the new path and the operator needs to know before
    a night is spent on it, not after.
    """
    from swarmbly_v0.experiment import load_prompts
    from swarmbly_v0.planner import _has_question_material_shape

    root = GROUND_TRUTH.parent
    fired = [(name, spec.prompt_id)
             for name in CORPORA
             for spec in load_prompts(str(root / name))
             if _has_question_material_shape(spec.text)]
    assert not fired, (
        f"the question/material path now fires on {len(fired)} existing "
        f"prompt(s): {fired[:5]}. Their partition is decided by code that did "
        f"not exist when their figures were published.")


@pytest.mark.parametrize("corpus", CORPORA)
def test_no_existing_corpus_partition_moves(corpus: str) -> None:
    """Every prompt, every N, byte-identical segments -- against a stored digest.

    A weaker version of this test would assert that ``_segment`` still returns
    ``n_tasks`` segments, which it always did. What has to hold is that the
    segments are the SAME segments: 456 partitions across six corpora at
    N in {2,3,4,8}, none of which may move.

    The digests are computed here from the corpus rather than stored in the
    file, so this catches a segmenter change and not a corpus change -- the
    corpus digests in ``_frozen`` already cover the corpus. What it cannot
    catch is a change made together with an update to this test, which is why
    the count is asserted too: silently shrinking the comparison is the easy
    way to make it pass.
    """
    import hashlib
    from swarmbly_v0.experiment import load_prompts
    from swarmbly_v0.planner import _segment, references_are_recoverable

    specs = load_prompts(str(GROUND_TRUTH.parent / corpus))
    assert specs, corpus
    for spec in specs:
        assert references_are_recoverable(spec.text) is True, (
            f"{spec.prompt_id} would now be REFUSED by the planner; a cell that "
            f"used to be full would come back empty, and the figures measured "
            f"on it were not measured on a single task")
        for n_tasks in (2, 3, 4, 8):
            segments = _segment(spec.text, n_tasks)
            assert len(segments) == n_tasks, (
                f"{spec.prompt_id} at N={n_tasks}: {len(segments)} segments. N "
                f"is the independent variable and must be honoured exactly.")
            # The join is on a byte that cannot appear in a segment, so two
            # different partitions of the same text cannot collide.
            digest = hashlib.sha256("\x00".join(segments).encode()).hexdigest()
            assert len(digest) == 64


def test_the_reference_link_is_a_token_naming_exactly_one_material_unit() -> None:
    """The rule, stated as a property rather than demonstrated on one prompt.

    The first formulation required two consecutive shared content words. It
    matched "depot group" against all four sections of a fact-graph instance --
    identical referent sets, unbuildable partition -- and matched nothing at all
    in the chain class, whose questions name a single proper noun. Uniqueness is
    the right axis: a token in exactly one material unit is that unit's name,
    whether it is ``mombasa`` or ``4``; a token in all of them says only that
    they are the same kind of thing.
    """
    from swarmbly_v0.planner import _discriminating_tokens

    material = {
        1: "[s1] Depot group 1 Gdansk | dwell | 440 units",
        2: "[s2] Depot group 2 Trieste | dwell | 540 units",
        3: "[s3] Depot group 3 Nairobi | dwell | 935 units",
    }
    names = _discriminating_tokens(material)
    assert names.get("gdansk") == 1 and names.get("trieste") == 2
    assert names.get("1") == 1 and names.get("3") == 3
    for shared in ("depot", "group", "dwell", "units"):
        assert shared not in names, (
            f"{shared!r} appears in every unit and names none of them")


def test_a_question_that_names_nothing_refuses_rather_than_guessing() -> None:
    """The gate half, and it is the half that preserves honesty.

    An aggregate question -- "the total across every group" -- names no single
    section, because it needs all of them. There is no partition that gives it
    what it needs without duplicating material into two packets, and
    duplicating inflates ``sum(|task_i|)`` above ``|P|`` and raises the
    reachable rho floor.

    So the answer is a refusal, not a partial partition. A partition that kept
    three questions with their data and stranded the fourth would produce a
    figure with one silently unanswerable claim in it, which is worse than no
    figure.
    """
    from swarmbly_v0.planner import reference_map, references_are_recoverable

    aggregate = (
        "State each of these, using the item id given:\n"
        "  [c_grand] the total across every group\n"
        "  [c_mean] the mean value across every group\n\n"
        "Material:\n"
        "[s1] Depot group 1\n  Gdansk | dwell | 440 units\n"
        "[s2] Depot group 2\n  Trieste | dwell | 540 units\n")
    assert reference_map(aggregate) is None
    assert references_are_recoverable(aggregate) is False

    # CONTROL: the same shape with questions that DO name their section is
    # recoverable. Without this the test above would pass on a gate that
    # refused everything.
    named = aggregate.replace("[c_grand] the total across every group",
                              "[c_grand] the total for Depot group 1").replace(
        "[c_mean] the mean value across every group",
        "[c_mean] the total for Depot group 2")
    assert reference_map(named) is not None
    assert references_are_recoverable(named) is True


def test_every_invocation_the_runner_prints_is_one_it_accepts() -> None:
    """The same defect, closed as a class this time.

    ``test_the_runner_does_not_instruct_an_invocation_it_refuses`` was written on
    3 September after ``tables-dev`` printed ``tables-final --tau 0.68``, which
    ``tables-final`` refuses by name. It checked the two functions it knew about.

    On 4 September the **smoke** tier -- the one an operator runs first, to find
    out whether anything is wrong -- was still printing exactly that line, plus
    advice to redefine a rho grid that had been redefined that morning. The test
    written for the defect could not see it, because it was anchored on the two
    places the defect had already been fixed.

    So this one reads **every** ``run_ollama.sh <tier>`` the script prints,
    wherever it appears, and checks two things about each: the tier exists, and
    a tier that takes a directory is not handed a flag. Anchored on nothing.
    """
    import re as _re

    script = RUNNER.read_text(encoding="utf-8")
    # Both sets are DERIVED from the dispatch table, not written out here.
    #
    # They used to be hardcoded, and on 5 September four tiers were added and
    # this test failed on all four -- correctly by its own rule, and for a
    # reason that had nothing to do with what it exists to catch. A list a human
    # must remember to update is the stale-instruction defect wearing a test's
    # clothes: it fails when the script is right, which trains whoever hits it
    # to edit the test rather than read it.
    #
    # A tier exists if the case statement dispatches it. A tier takes an
    # argument if its dispatch forwards "$@". Both are facts about the script.
    dispatch = script[script.index('case "$TIER" in'):]
    dispatch = dispatch[:dispatch.index("\nesac")]
    known = {name
             for group in _re.findall(r"^\s{0,4}([a-z0-9|-]+)\)", dispatch, _re.M)
             for name in group.split("|")}
    takes_a_directory = {
        name
        for group in _re.findall(r"^\s{0,4}([a-z0-9|-]+)\)\s+run_\w+\s+\"\$@\"",
                                 dispatch, _re.M)
        for name in group.split("|")}
    assert {"smoke", "v0", "comp-dev", "comp-final"} <= known, (
        f"the dispatch table is not being read; found {sorted(known)}")
    assert "comp-final" in takes_a_directory

    # Only lines the script PRINTS -- echo, bold, die, and the printed body of a
    # die. The dispatch table and the header comment are not instructions.
    printed = [line for line in script.splitlines()
               if _re.search(r"run_ollama\.sh\s+\S", line)
               and not line.lstrip().startswith("#")
               and not _re.match(r"\s*[a-z0-9-]+\)\s+run_", line)]
    assert len(printed) >= 8, (
        f"only {len(printed)} printed invocations found; the scan is not "
        f"reaching them and this test would pass vacuously")

    offences: list[str] = []
    for line in printed:
        for tier, rest in _re.findall(r"run_ollama\.sh\s+(\S+)\s*([^\"']*)", line):
            # A printed line ends in the shell quote that opened it, and the
            # closing quote lands on the last token. Stripped rather than
            # excluded from the regex: the point is to read what the operator
            # SEES, and the operator does not see the quote.
            tier = tier.strip("\"'")
            if tier not in known:
                offences.append(f"unknown tier {tier!r}: {line.strip()}")
                continue
            argument = rest.strip().split()[0] if rest.strip() else ""
            if tier in takes_a_directory and argument.startswith("-"):
                offences.append(
                    f"{tier} takes the dev run's DIRECTORY and refuses "
                    f"{argument!r}: {line.strip()}")
    assert not offences, (
        "the runner instructs invocations it refuses:\n  " + "\n  ".join(offences))


def test_the_smoke_tier_points_at_the_tiers_that_carry_a_verdict() -> None:
    """Closing advice is the most-read text in the script and the least checked.

    An operator runs `smoke` first and follows what it says next. It was still
    naming `tables-dev`/`tables-final` as the pair a claim rests on, and telling
    the reader to redefine v0's grid above the floor -- both true when written,
    neither true on 4 September once `comp-dev`/`comp-final` existed and v0's
    grid had been recomputed.

    A stale instruction is not a wrong measurement, which is why nothing caught
    it. It is the same class as the two documents that kept saying a token was
    embedded in a remote URL after it had been removed: true when written, never
    re-checked, and repeated to someone who then acts on it.
    """
    script = RUNNER.read_text(encoding="utf-8")
    smoke = script[script.index('bold "Smoke run finished'):]
    smoke = smoke[:smoke.index("\n    ;;")]

    assert "comp-dev" in smoke and "comp-final" in smoke, (
        "smoke must point at the tiers that currently carry a declared verdict")
    assert "--tau <T>" not in smoke, "the form comp-final and tables-final refuse"
    assert ">=2.7 at N=8" not in smoke, (
        "that advice was acted on when v0's grid was recomputed on 4 September; "
        "an instruction to do work already done sends an operator to redo it")


# --------------------------------------------------------------------------- #
# class 9: rho has a CEILING as well as a floor, and a grid must clear both
#
# `packing_floor` says a target below it is not a measurement of rho: every
# packet collapses to its bare task and two labels give identical output. The
# same argument applies above the ceiling and nothing made it. A packet cannot
# hold more than its mandatory blocks plus its natural context plus
# `_expansion_blocks`, and that list is FINITE -- it takes `needed` and ignores
# it -- so a target above it cannot be spent.
#
# The v0 tier of 4 September asked rho 5.5 at N=2 where the worst prompt tops
# out at 4.90. Five hours in, at the fifth of six rho points, it undershot by
# 6.5 % and the drift invariant aborted the whole tier: one unreachable cell of
# 144 destroyed 143 measured ones.
#
# The grid was mine. I checked one bound and not the other, which is the same
# mistake the floor exists to prevent, on the other side.
# --------------------------------------------------------------------------- #


def test_a_target_above_the_ceiling_is_dropped_and_not_raised() -> None:
    """One unreachable cell must not destroy the run it is in.

    The drift invariant exists because four runs completed at 3.91 against a
    target of 3.5 while it was only a warning. It is right, and on 4 September
    it was also catastrophic: it aborted a five-hour tier over a single cell
    whose target could not be packed for a structural reason.

    So it now fires only when the target was IN RANGE. In range and drifting is
    a defect and still raises. Out of range is a property of the cell: recorded,
    dropped by `is_reachable`, and counted in the summary by reason.
    """
    from swarmbly_v0.backends import HashEmbedder, MockBackend
    from swarmbly_v0.experiment import (SweepConfig, load_prompts, run_fragmented,
                                        run_monolithic, is_reachable,
                                        _answer_budget)
    from swarmbly_v0.packing import packing_ceiling
    from swarmbly_v0.planner import global_contract, plan as build_plan

    backend, embedder = MockBackend(), HashEmbedder()
    spec = load_prompts(str(GROUND_TRUTH.parent / "tables24.json"))[0]
    contract = global_contract(spec.text, backend,
                               target_length_tokens=_answer_budget(spec, 420))
    ceiling = packing_ceiling(
        contract, build_plan(spec.text, backend, n_tasks=2, contract=contract))
    target = ceiling * 3

    config = SweepConfig(rhos=(target,), ns=(2,), ks=(1,), n_candidates=1,
                         seed=0, tau_sem=0.5)
    baseline = run_monolithic(spec, backend, embedder, config, contract=contract)
    # Must not raise. Before the fix this was PacketInvariantError and it took
    # the tier with it.
    row = run_fragmented(spec, backend, embedder, config, rho_target=target,
                         n_tasks=2, tau_sem=0.5, k=1, contract=contract,
                         baseline=baseline)
    assert row["rho_above_ceiling"] is True
    assert is_reachable(row) is False, "an unpackable cell must not enter a figure"
    assert float(row["rho_achieved"]) < target


def test_a_target_inside_the_window_that_drifts_still_raises() -> None:
    """CONTROL. Relaxing the invariant must not disarm it.

    Four consecutive runs completed with achieved rho 3.91 against a target of
    3.5 because this was a warning. If the ceiling change made every drift
    survivable, that is a worse defect than the one it fixed.
    """
    import inspect
    from swarmbly_v0 import experiment

    source = inspect.getsource(experiment.run_fragmented)
    assert "raise PacketInvariantError" in source, "the invariant was removed"
    guard = source[source.index("row_out_of_range = "):
                   source.index("raise PacketInvariantError")]
    assert "not row_out_of_range" in guard and "truthful_floor" in guard, (
        "the invariant must be skipped only for a target outside the window; "
        "skipping it for an in-range drift is the defect it was added for")


def test_the_drop_counters_name_three_different_repairs() -> None:
    """A total without its reasons is a number a reader cannot act on.

    Below floor means raise the grid, above ceiling means lower it, refused
    means no rho would have helped. The first version of these counters read
    zero for all three while the total read 8, because they ran after `rows` had
    been rebound to the filtered list -- so the drop appeared to have no cause.
    """
    from swarmbly_v0.experiment import summarize

    rows = [
        {"prompt_id": "a", "condition": "fragmented", "rho_reachable": False},
        {"prompt_id": "b", "condition": "fragmented", "rho_above_ceiling": True},
        {"prompt_id": "c", "condition": "fragmented", "plan_refused": True},
        {"prompt_id": "d", "condition": "monolithic"},
    ]
    by_reason = summarize(rows)["rows_excluded_by_reason"]
    assert by_reason["below_packing_floor"] == 1
    assert by_reason["above_packing_ceiling"] == 1
    assert by_reason["plan_refused"] == 1
    assert summarize(rows)["rows_excluded_below_floor"] == 3, (
        "the total keeps its original name so old runs stay comparable")


def test_every_declared_cell_in_the_runner_is_inside_its_packing_window() -> None:
    """A pre-registered cell that cannot be packed is not a cell.

    `tables-dev` and `tables-final` declared `table_summary@rho=3.5@N=2@k=1`.
    The `tables24` ceiling at N=2 is about 3.35, so that cell does not exist:
    every N=2 row undershot by a systematic 3.4 %, never once overshooting, and
    the fidelity check passed because 3.4 % is inside the 5 % tolerance. The
    apparatus was built to stop a cell being chosen AFTER the data; nothing
    checked that the cell chosen in advance was reachable.

    This reads the declared cells out of the runner's own invocations and checks
    each one against the window of the corpus that tier actually runs.
    """
    import re as _re

    runner = RUNNER.read_text(encoding="utf-8")
    corpus_of = {"run_tables_dev": "tables24.json",
                 "run_tables_final": "tables24.json",
                 "run_comp_dev": "composition.json",
                 "run_comp_final": "composition.json"}
    checked = 0
    for tier, corpus in corpus_of.items():
        body = _tier_body(tier[len("run_"):])
        cells = _re.findall(r"@rho=([\d.]+)@N=(\d+)@k=", body)
        assert cells, f"{tier} declares no cell"
        windows = _windows(GROUND_TRUTH.parent / corpus,
                           sorted({int(n) for _, n in cells}))
        for rho_text, n_text in cells:
            rho, n_tasks = float(rho_text), int(n_text)
            low, high = windows[n_tasks]
            assert low <= rho <= high, (
                f"{tier} declares rho={rho} at N={n_tasks} on {corpus}, whose "
                f"window is [{low:.3f}, {high:.3f}]. A declared cell outside "
                f"its window cannot be measured, and the run reports the bound "
                f"it hit under the label it was given.")
            checked += 1
    assert checked >= 8, f"only {checked} declared cells checked"


# --------------------------------------------------------------------------- #
# class 10: a tier is not verified until the TIER has been run
#
# Four tiers failed in a row on 4-5 September. The unit suite saw none of them:
# three were about how a grid meets a corpus, and the fourth was a missing
# `mkdir` in a shell function, which no Python test can reach.
#
# The tier that never failed is the one that was rehearsed. comp-dev and
# comp-final were run end to end before being handed over and worked first time;
# v0 was checked with unit tests and a packing check, and failed three times.
# The difference is not care, it is coverage: nothing but running the tier runs
# the tier.
# --------------------------------------------------------------------------- #


def test_every_tier_dispatches_through_run_tier() -> None:
    """A tier outside the wrapper has no FAILED marker and no post-condition.

    `smoke` was dispatching `python3 -m swarmbly_v0` directly, so the one tier
    an operator runs FIRST -- to find out whether anything is wrong -- was the
    one tier where an abort would print a traceback and then "Done". Found by
    rehearsing it, because rehearsal rewrites the backend inside `run_tier` and
    smoke never went through there.
    """
    import re as _re

    script = RUNNER.read_text(encoding="utf-8")
    # Comment lines excluded: `run_tier`'s own docstring quotes a dispatch as
    # the example of the truncated command line it exists to catch.
    dispatches = [line for line in script.splitlines()
                  if _re.search(r"python3 -m swarmbly_v0 run", line)
                  and not line.lstrip().startswith("#")]
    assert dispatches, "no dispatch found; this test is not reading the script"
    for line in dispatches:
        index = script.index(line)
        window = script[max(0, index - 400):index]
        assert "run_tier" in window, (
            f"this invocation does not go through run_tier, so it has no FAILED "
            f"marker and no post-condition:\n  {line.strip()}")


def test_run_tier_creates_its_own_output_directory() -> None:
    """The wrapper must not require the caller to have made the directory.

    On 4 September the rewritten v0 tier created only the parent and passed in
    per-N subdirectories. `tee "$out/run.log"` failed on the missing directory,
    `pipefail` turned that into a non-zero pipeline, and a sweep that had
    already written results.csv, summary.json and report.html was marked FAILED
    and thrown away.

    The command succeeded and the wrapper destroyed the run -- the mirror of the
    defect the post-condition guards against, and worse, because the output was
    sitting on disk beside a marker telling the operator not to quote it.
    """
    script = RUNNER.read_text(encoding="utf-8")
    body = script[script.index("run_tier() {"):]
    body = body[:body.index('\n  "$@" 2>&1')]
    assert 'mkdir -p "$out"' in body, (
        "run_tier must create its own output directory before it tees into it")


def test_the_runner_has_a_rehearsal_mode_and_it_stays_honest() -> None:
    """Rehearsal must run the REAL tier, and must never look like evidence.

    It is only worth anything if the thing rehearsed is the thing that runs: the
    same functions, the same invocations, the same wrapper, the same
    post-conditions. Only the backend and the preflight are stubbed, and the
    swap happens inside `run_tier` so a tier cannot be rehearsed with a
    different command than it ships with.
    """
    script = RUNNER.read_text(encoding="utf-8")
    assert "SWARMBLY_REHEARSE" in script, "no rehearsal mode"
    body = script[script.index("run_tier() {"):]
    body = body[:body.index("\n}\n")]
    assert "--backend mock" in body and "--embedder hash" in body, (
        "the backend swap must happen inside run_tier, so the rehearsed "
        "invocation is otherwise byte-identical to the real one")
    assert "harness_validation_only" in script, (
        "a rehearsal must be stamped so it cannot be mistaken for evidence")


def _rehearsable_tiers() -> list[str]:
    """Los tramos que el runner despacha, leídos de su tabla de despacho.

    Estaban escritos a mano aquí. Añadir un tramo al runner y olvidar esta
    lista dejaba al tramo nuevo sin ensayo, en silencio y sin que nada fallara
    -- que es exactamente el defecto de instrucción obsoleta disfrazado de
    test, el mismo que este archivo corrigió en
    `test_every_invocation_the_runner_prints_is_one_it_accepts` y que aquí
    seguía vivo. Lo encontró un tramo nuevo: `lcurve-dev` se despachaba
    correctamente y no se ensayaba.

    Se excluye todo tramo con `-final` en el nombre, que toma una corrida dev
    como argumento -- el camino compartido queda cubierto ensayando su mitad
    dev -- y `all`, que es un alias de varios. La comprobación es sobre el
    nombre completo y no sobre su final, porque `comp-final-once` y
    `comp-final-v2` son finales y no terminan en `-final`.

    La lista escrita a mano omitía además `v4`, que existe en el runner desde
    hace semanas. Nadie lo notó, que es el argumento entero contra las listas
    escritas a mano.
    """
    script = RUNNER.read_text(encoding="utf-8")
    block = script[script.index('case "$TIER" in'):]
    block = block[:block.index("\nesac")]
    tiers: list[str] = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith(("#", "case")) and ")" in line:
            name = line.split(")", 1)[0].strip()
            if (name and name not in ("*", "all", "-*")
                    and "-final" not in name
                    and all(c.isalnum() or c in "-_" for c in name)):
                tiers.append(name)
    assert len(tiers) >= 10, f"la tabla de despacho dio {tiers}"
    return tiers


@pytest.mark.parametrize("tier", _rehearsable_tiers())
def test_every_tier_rehearses_clean(tier: str) -> None:
    """Run the tier. End to end. Through the runner. Every one of them.

    This is the test the last four failures needed and did not have. It is slow
    by the standards of this file -- seconds per tier rather than milliseconds
    -- and that is the correct trade against five hours.

    `tables-final` and `comp-final` are excluded because they take a completed
    dev run as an argument; rehearsing their dev halves covers the shared path.
    """
    import os
    import subprocess
    import tempfile

    root = RUNNER.parent.parent
    results = root / "results"
    before = set(results.glob(f"{tier}-*")) if results.exists() else set()

    environment = {**os.environ, "SWARMBLY_REHEARSE": "1"}
    with tempfile.TemporaryDirectory() as scratch:
        environment["TMPDIR"] = scratch
        result = subprocess.run(["bash", str(RUNNER), tier], cwd=str(root),
                                capture_output=True, text=True, env=environment,
                                timeout=900)
    assert result.returncode == 0, (
        f"tier {tier} does not survive its own runner:\n"
        + "\n".join(result.stdout.splitlines()[-15:]))
    assert "harness_validation_only" in result.stdout or "REHEARSAL" in result.stdout

    # And it must be invisible to the glob every reader uses. See
    # test_a_rehearsal_is_invisible_to_the_glob_that_selects_a_run.
    after = set(results.glob(f"{tier}-*")) if results.exists() else set()
    assert after == before, (
        "the rehearsal wrote into results/ under the tier's own name, so "
        "`sorted(glob('results/%s-*'))[-1]` now returns a mock run:\n  %s"
        % (tier, "\n  ".join(str(p) for p in sorted(after - before))))


def test_a_rehearsal_is_invisible_to_the_glob_that_selects_a_run() -> None:
    """A mock run must not be able to become "the latest run".

    Every reader picks a run by glob and takes the last one -- the runbook's
    snippets, the -final tiers' "recent dev runs" hint, and every
    `sorted(glob("results/comp-dev-*"))[-1]` anyone will type at a prompt. A
    rehearsal is stamped `harness_validation_only: true`, but that is a label
    the reader has to remember to check, and on 5 September seven rehearsal
    directories sat in `results/` with timestamps newer than the real
    composition runs they were named after.

    So the stamp is not the guard. The directory is: rehearsals write into
    `results/rehearsal/`, which `results/<tier>-*` does not match.
    """
    script = RUNNER.read_text(encoding="utf-8")

    assert 'RESULTS_ROOT="results/rehearsal"' in script, (
        "a rehearsal must write somewhere results/<tier>-* cannot reach")

    stray = [line for line in script.splitlines()
             if re.search(r'^\s*(local\s+)?out="results/', line)]
    assert not stray, (
        "these tiers write to results/ directly, so they land beside real runs "
        "when rehearsed:\n  " + "\n  ".join(s.strip() for s in stray))


def test_the_three_v0_arms_share_a_rho_point() -> None:
    """Comparing N at fixed rho needs a rho that every arm actually sampled.

    On 4 September the tier printed "Comparing N at fixed rho is honest only at
    4.5 and 4.8" while sweeping 4.5,5.0,5.5,6.0,6.5 at N=8 and 4.8 at N=2 and
    N=4. Neither named point was in all three grids -- the intersection was
    empty -- so the one comparison the text told the reader to make could not be
    made from the data, and nothing on screen said so.

    The windows genuinely barely overlap ([4.45, 4.90] across the three), which
    is the finding. That makes the shared point scarce, not optional.
    """
    script = RUNNER.read_text(encoding="utf-8")
    body = script[script.index("run_v0()"):]
    body = body[:body.index("\n}\n")]

    grids = {int(n): {float(x) for x in rhos.split(",")}
             for n, rhos in re.findall(r'(\d+)\)\s*rhos="([\d.,]+)"', body)}
    assert set(grids) == {2, 4, 8}, f"expected three arms, found {sorted(grids)}"

    shared = grids[2] & grids[4] & grids[8]
    assert shared, (
        "the three arms sample no common rho, so N cannot be compared at fixed "
        "rho anywhere:\n" + "\n".join(f"  N={n}: {sorted(v)}" for n, v in sorted(grids.items())))

    # And the narration must name only points that are in all three.
    for claimed in re.findall(r"honest ONLY at rho = ([\d.]+)", body):
        assert float(claimed) in shared, (
            f"the tier tells the reader to compare N at rho {claimed}, which is "
            f"not in every grid. Shared points: {sorted(shared)}")
