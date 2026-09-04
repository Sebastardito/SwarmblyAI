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
