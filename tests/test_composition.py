"""Constraint checking, the construction trace, and the preflight for both.

Same discipline as ``test_item_partition.py``, for the same reason: four V3c
runs were spent measuring through machinery nobody had verified. Every check
here is cheap and runs against the mock, so a defect surfaces in seconds rather
than five hours into a sweep.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from swarmbly_v0.composition_trace import build_trace, render_trace
from swarmbly_v0.constraints import CONSTRAINT_KINDS, check_constraint, grade_text, paragraphs_of

CORPUS = Path(__file__).resolve().parent.parent / "prompts" / "free_form.json"

CLEAN = (
    "The harbour publishes a tide window each morning and assigns every arrival to a berth "
    "before the pilots leave the quay. Cargo is drawn from the manifest in the order the "
    "shipper filed it, which keeps the crane crews from idling between lifts and keeps the "
    "reefer boxes moving. When the outer channel closes, the queue does not stop; it is "
    "rebuilt against the shorter window that remains, and the boxes that cannot be moved on "
    "this tide are held rather than shuffled between yards. The harbourmaster records the "
    "reason for every deferral so the backlog can be explained afterwards to the shippers "
    "who paid for a slot they did not get on the day they expected it.\n\n"
    "Rebuilding the queue is mostly a question of what cannot wait. Perishables and hazardous "
    "consignments hold their position, bulk aggregate yields, and anything already lifted "
    "stays lifted rather than being returned to the stack for the sake of a tidier sequence. "
    "The crane crews are told once, at the start of the shift, and are not asked to "
    "re-sequence mid-lift, because a change communicated halfway through costs more time than "
    "it saves. What emerges is a schedule that is worse than the one the storm interrupted "
    "and better than the one that would result from letting each gang decide for itself which "
    "box matters most on a wet afternoon."
)

CONSTRAINTS = [
    {"id": "paragraphs", "kind": "paragraph_count", "count": 2},
    {"id": "length", "kind": "words_per_paragraph", "min": 60, "max": 140},
    {"id": "mentions_tide", "kind": "must_mention", "term": "tide window"},
    {"id": "mentions_berth", "kind": "must_mention", "term": "berth"},
    {"id": "mentions_manifest", "kind": "must_mention", "term": "manifest"},
    {"id": "avoids_forbidden", "kind": "must_not_mention", "term": "obviously"},
    {"id": "no_repeated_sentence", "kind": "no_repeated_sentence"},
    {"id": "no_repeated_phrase", "kind": "no_repeated_ngram", "size": 8},
    {"id": "tide_once", "kind": "term_once", "term": "tide window"},
]


# --------------------------------------------------------------------------- #
# the checks themselves
# --------------------------------------------------------------------------- #

def test_a_compliant_composition_satisfies_every_constraint() -> None:
    """The instrument must not fail a text that actually complies.

    A grader that cannot award full marks makes every comparison against it
    meaningless, and this project has already lost runs to exactly that.
    """
    report = grade_text(CLEAN, CONSTRAINTS)
    assert report.failed == [], [f.as_dict() for f in report.failed]
    assert report.score == 1.0
    assert report.n_paragraphs == 2


def test_the_seam_signature_is_caught() -> None:
    """Two workers each introducing the subject is the failure assembly produces.

    Each copy is locally fluent, which is why a coherence score computed on
    sentence transitions can miss it entirely.
    """
    stitched = ("The harbour publishes a tide window each morning. Cargo waits for it.\n\n"
                "The harbour publishes a tide window each morning. The queue is rebuilt.")
    report = grade_text(stitched, CONSTRAINTS)
    failed = {f.constraint_id for f in report.failed}
    assert "no_repeated_sentence" in failed
    assert "no_repeated_phrase" in failed
    assert "tide_once" in failed


def test_paragraph_counting_matches_what_a_reader_would_say() -> None:
    assert len(paragraphs_of("one\n\ntwo")) == 2
    # A single newline is not a paragraph break to a reader, and must not be one here.
    assert len(paragraphs_of("one\ntwo")) == 1
    assert paragraphs_of("") == []


def test_a_short_fragment_fails_the_length_check() -> None:
    """A worker handed a thin packet writes forty words where a hundred were asked for."""
    report = grade_text("Too short.\n\nAlso too short.", CONSTRAINTS)
    assert "length" in {f.constraint_id for f in report.failed}


def test_unknown_constraint_kind_raises() -> None:
    """Skipping an unrecognised constraint would quietly raise every score containing one."""
    with pytest.raises(ValueError, match="unknown constraint kind"):
        check_constraint("text", {"id": "x", "kind": "reads_nicely"})


def test_score_is_none_rather_than_perfect_when_nothing_was_checked() -> None:
    """A text checked against nothing has not passed; it has not been checked."""
    assert grade_text(CLEAN, []).score is None


def test_every_kind_is_reachable() -> None:
    for kind in CONSTRAINT_KINDS:
        assert any(c["kind"] == kind for c in CONSTRAINTS), f"{kind} is untested"


# --------------------------------------------------------------------------- #
# the trace
# --------------------------------------------------------------------------- #

def test_the_trace_attributes_each_sentence_to_its_micro_task() -> None:
    text = "One. Two.\n\nThree. Four."
    trace = build_trace("t", "fragmented k=3", text, CONSTRAINTS[:1],
                        order=["t0", "t1"], offsets=[0, 2])
    assert [s["task_id"] for s in trace.sentences] == ["t0", "t0", "t1", "t1"]
    assert {t["task_id"]: t["n_sentences"] for t in trace.per_task} == {"t0": 2, "t1": 2}


def test_a_sentence_written_by_two_workers_is_marked_cross_task() -> None:
    """"Said twice" is a defect; "written twice by two workers" is a diagnosis."""
    text = "The harbour logs the tide. Berths follow.\n\nThe harbour logs the tide. Cargo waits."
    trace = build_trace("t", "fragmented k=3", text, CONSTRAINTS[:1],
                        order=["t0", "t1"], offsets=[0, 2])
    assert len(trace.duplicated) == 1
    assert trace.duplicated[0]["cross_task"] is True
    assert trace.duplicated[0]["task_ids"] == ["t0", "t1"]


def test_the_monolithic_baseline_is_traced_too() -> None:
    """Leaving the baseline blank makes it unreadable next to what it is a baseline for."""
    trace = build_trace("t", "monolithic", CLEAN, CONSTRAINTS)
    assert {s["task_id"] for s in trace.sentences} == {"monolithic"}
    assert trace.report.score == 1.0


def test_the_rendered_trace_carries_the_text_and_the_numbers() -> None:
    text = "One. Two.\n\nOne. Three."
    trace = build_trace("comp_x", "fragmented k=3", text, CONSTRAINTS,
                        order=["t0", "t1"], offsets=[0, 2])
    out = render_trace([trace])
    assert "comp_x" in out and "fragmented k=3" in out
    assert "Contribution by micro-task" in out
    assert "Repeated sentences" in out
    assert "across different micro-tasks" in out
    assert text.strip() in out, "a reader must be able to check the numbers against the text"


# --------------------------------------------------------------------------- #
# the corpus
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def corpus() -> dict:
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def test_the_corpus_holds_both_shapes(corpus: dict) -> None:
    prompts = corpus["prompts"]
    assert any(p.get("key") for p in prompts), "no free-form answer prompts"
    assert any(p.get("constraints") for p in prompts), "no composition prompts"
    assert not any(p.get("key") and p.get("constraints") for p in prompts), \
        "a prompt is both, which leaves the grading path ambiguous"


def test_every_accepted_phrasing_is_accepted_by_its_own_key(corpus: dict) -> None:
    """A right answer graded wrong is the error that has cost this project most."""
    from swarmbly_v0.grading import grade_answer
    for spec in corpus["prompts"]:
        for item_id, entry in (spec.get("key") or {}).items():
            for variant in entry["expected"].split("|"):
                assert grade_answer(variant, entry["expected"], entry["mode"]) is True, \
                    f"{spec['id']}/{item_id}: {variant!r} rejected by its own key"


def test_the_two_answer_classes_never_overlap(corpus: dict) -> None:
    """If "over" were accepted for both classes the item would be unfailable."""
    from swarmbly_v0.grading import normalise_text
    for spec in corpus["prompts"]:
        key = spec.get("key") or {}
        classes = {frozenset(normalise_text(v) for v in e["expected"].split("|"))
                   for e in key.values()}
        for a in classes:
            for b in classes:
                if a is not b:
                    assert not (a & b), f"{spec['id']}: answer classes share {sorted(a & b)}"


def test_composition_constraints_are_self_consistent(corpus: dict) -> None:
    for spec in corpus["prompts"]:
        constraints = spec.get("constraints") or []
        if not constraints:
            continue
        required = {c["term"] for c in constraints if c["kind"] == "must_mention"}
        forbidden = {c["term"] for c in constraints if c["kind"] == "must_not_mention"}
        assert not (required & forbidden), f"{spec['id']}: a term is both required and forbidden"
        assert any(c["kind"] == "no_repeated_sentence" for c in constraints), \
            f"{spec['id']}: no repetition check, which is the point of the exercise"


# --------------------------------------------------------------------------- #
# preflight
# --------------------------------------------------------------------------- #

def test_a_compliant_model_scores_full_marks_through_the_real_pipeline() -> None:
    """Drive the sweep with a model that writes a compliant composition.

    The counterpart of the item-partition preflight. If a text that satisfies
    every constraint does not score 1.0 after going through planning, packing,
    dispatch, consensus and assembly, the loss is the pipeline's and the sweep
    would be measuring it rather than the models.
    """
    from swarmbly_v0.backends import HashEmbedder, MockBackend
    from swarmbly_v0.experiment import SweepConfig, load_prompts, run_monolithic

    class Compliant(MockBackend):
        def generate(self, prompt, max_tokens=None, **kwargs):  # type: ignore[override]
            return CLEAN

    specs = [s for s in load_prompts(str(CORPUS)) if s.is_composition]
    assert specs, "the corpus has no composition prompts"

    config = SweepConfig(rhos=(1.5,), ns=(3,), ks=(3,), seed=0)
    row = run_monolithic(specs[0], Compliant(seed=0), HashEmbedder(), config)
    trace = row.get("_trace")

    assert trace is not None, "no composition trace was produced for a composition prompt"
    assert trace.report.n_paragraphs == 2
    assert trace.duplicated == [], "a compliant text was reported as repeating itself"
