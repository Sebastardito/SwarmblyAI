"""The invariant the fragmented condition has to satisfy before it can measure anything.

Three V3c runs were spent measuring *through* a fragmented condition nobody had
checked. The run of 24 August finally made the damage visible -- item accuracy
fell from 65.8 % unfragmented to 11.7 % fragmented, and the control category,
copying a city name out of a record, fell from 100 % to 12 % -- and the cause was
not the models and not the grader. It was the partition.

``_ENUM_SPLIT_RE`` did not recognise ``[NN]`` labels, so a ten-item prompt split
into one unit, fell through to sentence packing, and produced this:

    t0: "Convert each length from metres to kilometres..."   <- operation, no data
    t1: "[05] 30000 m [06] 3000 m ... Answer every item"      <- data, no operation
    t2: "Emit the answer only: no working, no restatement"    <- boilerplate only
    t3: "Items are independent: the answer to one must not"   <- boilerplate only

Items 01 through 04 appeared in no fragment at all, and the one fragment holding
data held no instruction, so its worker restated ``30000 m`` instead of
converting it. That is not a coherence failure, a model failure or a grading
failure. It is a fragment that could not have succeeded.

These tests state the two properties that make the fragmented condition mean
what the experiment assumes it means. They run in milliseconds. Had they existed
in August they would have saved three runs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from swarmbly_v0.planner import _segment, split_enumerated

CORPUS = Path(__file__).resolve().parent.parent / "prompts" / "ground_truth.json"
LABEL = re.compile(r"[\[(](\d{1,3})[\])]")


def _corpus_prompts() -> list[dict]:
    return json.loads(CORPUS.read_text(encoding="utf-8"))["prompts"]


def _ids(specs: list[dict]) -> list[str]:
    return [s["id"] for s in specs]


# --------------------------------------------------------------------------- #
# the two invariants
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("spec", _corpus_prompts(), ids=_ids(_corpus_prompts()))
@pytest.mark.parametrize("n_tasks", [2, 3, 4, 8])
def test_every_item_reaches_exactly_one_fragment(spec: dict, n_tasks: int) -> None:
    """No item may be dropped, and none may be answered twice.

    A dropped item is an unanswerable question in the key. A duplicated item is
    the same question asked of two workers, which inflates the apparent replica
    count and lets one worker's error be counted as an independent observation.
    """
    segments = _segment(spec["prompt"], n_tasks)
    seen: list[str] = []
    for segment in segments:
        body = segment.split("\n\n")[1] if "\n\n" in segment else segment
        seen.extend(LABEL.findall(body))

    expected = sorted(spec["key"])
    assert sorted(seen) == expected, (
        f"{spec['id']} at N={n_tasks}: expected each of {len(expected)} items once, "
        f"got {len(seen)} placements"
    )


@pytest.mark.parametrize("spec", _corpus_prompts(), ids=_ids(_corpus_prompts()))
@pytest.mark.parametrize("n_tasks", [2, 3, 4, 8])
def test_every_fragment_carries_the_operation(spec: dict, n_tasks: int) -> None:
    """A worker holding data and no instruction cannot succeed at any rho.

    This is the defect that cost ``unit_conversion`` 77 points: the fragment
    with the numbers had no sentence telling it to convert them, so it restated
    them. The preamble is duplicated into every fragment for this reason, and the
    duplication is paid in the rho floor rather than hidden.
    """
    preamble = (split_enumerated(spec["prompt"]) or ("", [], ""))[0]
    assert preamble, f"{spec['id']}: no preamble found; the corpus shape changed"

    first_sentence = preamble.split(".")[0].strip()
    for i, segment in enumerate(_segment(spec["prompt"], n_tasks)):
        assert first_sentence in segment, (
            f"{spec['id']} fragment {i} at N={n_tasks} carries no operation: {segment[:90]!r}"
        )


@pytest.mark.parametrize("spec", _corpus_prompts(), ids=_ids(_corpus_prompts()))
def test_no_fragment_is_only_boilerplate(spec: dict) -> None:
    """Every fragment must contain at least one item.

    Two of the four fragments in the 24 August partition held nothing but output
    formatting. They consumed a worker, a network traversal and a slot in the
    replica count, and could not contribute an answer to anything.
    """
    for i, segment in enumerate(_segment(spec["prompt"], 4)):
        assert LABEL.search(segment), f"{spec['id']} fragment {i} holds no item"


# --------------------------------------------------------------------------- #
# the splitter itself
# --------------------------------------------------------------------------- #

def test_bracketed_labels_are_recognised_as_enumeration() -> None:
    """The absence of this pattern is the whole root cause."""
    from swarmbly_v0.planner import _ENUM_SPLIT_RE
    assert _ENUM_SPLIT_RE.search("[01] 11000 m")
    assert _ENUM_SPLIT_RE.search("(7) Lisbon")
    assert _ENUM_SPLIT_RE.search("3. Osaka")
    assert _ENUM_SPLIT_RE.search("- bullet")


def test_split_separates_operation_data_and_format() -> None:
    prompt = ("Convert each length from metres to kilometres.\n\n"
              "[01] 1000 m\n[02] 2000 m\n[03] 3000 m\n\n"
              "Answer every item on its own line.")
    preamble, items, postamble = split_enumerated(prompt)
    assert preamble == "Convert each length from metres to kilometres."
    assert items == ["[01] 1000 m", "[02] 2000 m", "[03] 3000 m"]
    assert postamble.startswith("Answer every item")


def test_prose_is_left_to_the_general_segmenter() -> None:
    """A prompt that is not a batch must not be forced into this shape."""
    assert split_enumerated("Write an essay about lighthouses. Keep one voice.") is None
    assert split_enumerated("[01] only one item") is None


def test_the_short_format_directive_does_not_name_a_literal_answer() -> None:
    """Models copied the template word into their replies.

    On 24 August 8.8 % of fragmented items came back as "answer Osaka" -- the
    right content, wrapped in the placeholder from the instruction, and graded
    wrong for it. Monolithic replies, which never carried the fragment header,
    did this zero times.
    """
    from swarmbly_v0.planner import _SHORT_FORMAT_DIRECTIVE
    assert '"[NN] answer"' not in _SHORT_FORMAT_DIRECTIVE
    assert "[NN]" in _SHORT_FORMAT_DIRECTIVE


@pytest.mark.parametrize("n_tasks", [1, 2, 3, 5, 10, 20])
def test_partition_is_stable_across_task_counts(n_tasks: int) -> None:
    """N is the sweep's independent variable; the partition must honour it.

    Above the item count it cannot: empty fragments would be dispatched to
    workers with nothing to do. The item count caps N and the caller sees the
    smaller number rather than a fragment that is only a header.
    """
    spec = _corpus_prompts()[0]
    segments = _segment(spec["prompt"], n_tasks)
    assert len(segments) == min(n_tasks, len(spec["key"]))
    assert all(LABEL.search(s) for s in segments)


# --------------------------------------------------------------------------- #
# end to end: the preflight that should have run before any of the three sweeps
# --------------------------------------------------------------------------- #

def test_an_obedient_model_scores_full_marks_through_the_real_pipeline() -> None:
    """Drive the actual sweep with a model that answers correctly, and check the plumbing.

    Every previous V3c run measured agreement against correctness *through* the
    fragmented condition without ever asking whether that condition delivers the
    work intact. It did not: on 24 August, 46 % of units carried no item label,
    150 items produced 671 sightings, and item accuracy read 11.7 % against
    65.8 % unfragmented.

    This test removes the models as a variable. The backend returns the right
    answer, correctly formatted, for exactly the items it was handed. Anything
    less than a clean sweep is the pipeline's fault and nobody else's -- and
    because it runs in seconds against the mock, it can gate every change rather
    than being discovered five hours into a sweep.
    """
    from swarmbly_v0.backends import HashEmbedder, MockBackend
    from swarmbly_v0.experiment import (
        SweepConfig, _truth_summary, load_prompts, run_fragmented, run_monolithic,
    )

    key: dict[str, str] = {}
    label = re.compile(r"\[(\d{1,3})\]")

    class Obedient(MockBackend):
        def generate(self, prompt, max_tokens=None, **kwargs):  # type: ignore[override]
            ids = [i for i in label.findall(prompt) if i in key]
            return "\n".join(f"[{i}] {key[i]}" for i in dict.fromkeys(ids)) or "no items"

    specs = load_prompts(str(CORPUS))
    config = SweepConfig(rhos=(1.5,), ns=(4,), ks=(3,), seed=0)
    backend, embedder = Obedient(seed=0), HashEmbedder()

    rows = []
    for spec in specs:
        key.clear()
        key.update({i: e["expected"] for i, e in (spec.key or {}).items()})
        baseline = run_monolithic(spec, backend, embedder, config)
        rows.append(baseline)
        rows.append(run_fragmented(spec, backend, embedder, config, rho_target=1.5,
                                   n_tasks=4, tau_sem=0.5, baseline=baseline, k=3))

    calibration = _truth_summary(rows)["truth_calibration"]
    grading = calibration["grading"]
    total_items = sum(len(s.key or {}) for s in specs)

    assert grading["units_with_no_label"] == 0, (
        f"{grading['units_with_no_label']} of {grading['units_total']} units carried no item "
        "label; the label is not surviving the pipeline"
    )
    assert grading["items_graded"] == grading["items_seen"], "some items were seen but not graded"

    cost = calibration["fragmentation_cost"]
    assert cost["monolithic"]["n_items"] == total_items
    assert cost["fragmented"]["n_items"] == total_items, (
        f"fragmented saw {cost['fragmented']['n_items']} items, expected {total_items}: "
        "items are being dropped or duplicated by the partition"
    )
    assert cost["monolithic"]["accuracy"] == 1.0
    assert cost["fragmented"]["accuracy"] == 1.0, (
        "a model that answers every item correctly did not score full marks after "
        "fragmentation, so the loss is in the pipeline rather than in the model"
    )
