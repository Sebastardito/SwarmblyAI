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
    assert "packing floor" in out
    assert "rho_reachable=false" in out, "and it must say where to find the dropped rows"

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


def _declared_run(tmp_path, capsys, *declare, n="2,8"):
    from swarmbly_v0.cli import main
    args = ["run", "--backend", "mock", "--embedder", "hash",
            "--prompts", "prompts/tables24.json", "--split", "dev",
            "--rho", "3.5", "--n", n, "--k", "1",
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
    out = _declared_run(tmp_path, capsys, "table_summary@rho=3.5@N=2@k=1")
    assert "DECLARED CELL: table_summary@rho=3.5@N=2@k=1" in out
    assert "point estimate" in out and "95% CI (by prompt)" in out
    assert "upper bound below" in out, "the criterion is on the bound, not the estimate"
    assert "n_prompts" in out, "the sample size that matters must be named"
    assert "VERDICT" in out


def test_the_control_is_labelled_as_one_and_flagged_if_it_passes(tmp_path, capsys):
    """A control that passes is worse news than a declared cell that fails: it
    says the instrument cannot separate the arms, so neither number is
    evidence. That has to be impossible to read past."""
    out = _declared_run(tmp_path, capsys,
                        "table_summary@rho=3.5@N=2@k=1",
                        "table_summary@rho=3.5@N=8@k=1")
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
    assert "table_summary@rho=3.5@N=2@k=1" in out, "it must list what was measured"


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
        assert "--declare 'table_summary@rho=3.5@N=2@k=1'" in block, tier
        assert "--declare 'table_summary@rho=3.5@N=8@k=1'" in block, \
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


def _floors(corpus: Path | None, n_values: list[int]) -> dict[int, float]:
    """Worst-case packing floor per N, over the corpus, from the real code."""
    from swarmbly_v0.backends import MockBackend
    from swarmbly_v0.experiment import DEFAULT_PROMPTS_PATH, load_prompts, _answer_budget
    from swarmbly_v0.packing import packing_floor
    from swarmbly_v0.planner import global_contract, plan as build_plan

    backend = MockBackend()
    specs = load_prompts(str(corpus or DEFAULT_PROMPTS_PATH))
    worst: dict[int, float] = {}
    for spec in specs:
        contract = global_contract(spec.text, backend,
                                   target_length_tokens=_answer_budget(spec, 420))
        for n_tasks in n_values:
            plan = build_plan(spec.text, backend, n_tasks=n_tasks, contract=contract)
            floor = packing_floor(contract, plan)
            worst[n_tasks] = max(worst.get(n_tasks, 0.0), floor)
    return worst


def test_every_N_in_the_v0_grid_keeps_at_least_three_reachable_rho_points() -> None:
    """A curve needs points, and a point below the floor is not one.

    The floor is roughly linear in N -- one contract header per packet -- so no
    single rho is both above the floor at N=8 and a low-context condition at
    N=2. The grid is therefore uneven on purpose, and what has to hold is that
    each N keeps enough points to be a curve rather than a dot.
    """
    rhos, ns = _grid(_tier_body("v0"))
    floors = _floors(None, ns)
    for n_tasks in ns:
        reachable = [r for r in rhos if r > floors[n_tasks]]
        assert len(reachable) >= 3, (
            f"N={n_tasks} has floor {floors[n_tasks]:.3f} and only "
            f"{len(reachable)} of {len(rhos)} rho points above it "
            f"({reachable}); a rho curve cannot be read from fewer than three")


def test_the_v0_grid_has_an_overlap_where_N_can_be_compared() -> None:
    """Comparing N at fixed rho is only honest where every N is above its floor.

    Outside the overlap a cell keeps only the prompts whose own floor is below
    the target, so the point rests on a different prompt subset -- which is the
    quiet version of the same defect: the figure is not wrong, it is about
    different prompts than the one beside it.
    """
    rhos, ns = _grid(_tier_body("v0"))
    floors = _floors(None, ns)
    overlap = [r for r in rhos if all(r > floors[n] for n in ns)]
    assert len(overlap) >= 2, (
        f"no rho in {rhos} clears every floor {floors}; N cannot be compared at "
        f"fixed rho anywhere in this grid")


def test_the_spec_target_is_recorded_as_unattainable_and_not_merely_unmet() -> None:
    """SPEC 11.5 asks for rho < 2.0. The floor at N=8 makes that impossible.

    Worth a test rather than a note: an unmet target invites another sweep, and
    an unattainable one is a claim to revise. Every sweep aimed below the floor
    is a night spent measuring a configuration nobody chose, and three have been.
    """
    _, ns = _grid(_tier_body("v0"))
    floors = _floors(None, ns)
    assert max(floors.values()) > 2.0, (
        f"floors {floors} are all under 2.0, so SPEC 11.5's target is reachable "
        f"after all and this test -- and the runner's claim -- must be removed")


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
    for tier in ("run_tables_final", "run_comp_final"):
        body = _tier_body(tier[len("run_"):])
        assert "assert_same_code_as_dev" in body, (
            f"{tier} does not compare its dev run's code fingerprint")
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
