"""The typed carry: what a successor receives from the step before it.

V4 measured the problem. At the widest fragment tested the ordered chain cost
+47.2 % coherence tax where prose cost +5.1 % and tables +3.3 % on fragments of
*identical size*, its accuracy fell monotonically 0.259 -> 0.091 as the partition
got finer, and its tax then saturated near +76 % -- what a broken chain looks
like once the carried value is gone. No fragment size in the tested range made it
affordable, so the answer is a mechanism rather than a parameter.

The cause turned out to be worse than "the carry is lossy". At rho = 2.0 -- the
value V4 ran -- **not one packet carried a predecessor block at all**. The block
was optional context, third in priority behind the contract header and the length
note, funded from whatever slack remained after the task text, and the slack ran
out first. Every successor was asked to divide a number nobody had told it. No
fragment size fixes a packet that is missing the one thing it needs.

So there are two changes here, and they are separable. The carry is now
*mandatory* for a task whose text consumes a predecessor's value, on the same
footing as the task text itself. And the carry is *typed*: every labelled value
the fragment produced, rather than summarize_fragment's lead sentence and entity
list, which silently drops everything after the first. Completeness is bought
rather than found -- 10 tokens against 4 on a terse fragment -- and that price is
reported rather than described away.

These tests use a scripted backend rather than the mock, because MockBackend
composes prose and never emits ``[NN] value`` -- so it cannot produce a carry to
extract, and a run against it shows the arm doing nothing. That is a fact about
the mock, not about the mechanism, and it is why this file exists.
"""

from __future__ import annotations

import pytest

from swarmbly_v0.planner import carry_values, summarize_fragment
from swarmbly_v0.textutil import count_tokens


# --------------------------------------------------------------------------- #
# extraction
# --------------------------------------------------------------------------- #

def test_labelled_values_are_extracted_with_their_step() -> None:
    text = "[01] 2496\n[02] 2247\n[03] 561"
    assert carry_values(text) == {"01": "2496", "02": "2247", "03": "561"}


def test_the_last_number_on_a_line_is_the_answer() -> None:
    """Same rule the grader uses, for the same reason: a model that shows its
    work ends on the result."""
    assert carry_values("[02] 2496 minus 10 percent is 2247")["02"] == "2247"


def test_thousands_separators_survive() -> None:
    assert carry_values("[04] 1,205")["04"] == "1205"


def test_a_non_numeric_answer_is_carried_verbatim() -> None:
    """Not every chain step produces a number, and a carry that dropped the
    answer because it was a word would be worse than the prose it replaced."""
    assert carry_values("[01] Osaka")["01"] == "Osaka"


def test_prose_yields_no_carry_at_all() -> None:
    """The fallback that makes the flag safe to set unconditionally."""
    prose = ("The harbour publishes a tide window each morning. "
             "Berths are allocated against it.")
    assert carry_values(prose) == {}


def test_the_typed_summary_carries_every_value_where_prose_carries_the_first() -> None:
    """What the carry actually buys, measured rather than assumed.

    An earlier version of this test asserted the typed form was several times
    *cheaper*. It is not, and the reason is the finding: summarize_fragment is
    extractive -- it keeps the lead sentence and drops everything after it. The
    prose summary is cheap precisely because it is incomplete. A fragment that
    produced three steps hands its successor one of them and a list of entities.
    """
    fragment = ("[01] The gross value is 2496.\n"
                "[02] Reducing it by ten percent gives 2247.\n"
                "[03] Divided across four weeks that is 561.")
    typed = summarize_fragment(fragment, typed=True)
    prose = summarize_fragment(fragment, typed=False)

    assert typed == "[01]=2496 [02]=2247 [03]=561"
    assert all(v in typed for v in ("2496", "2247", "561"))
    assert "2247" not in prose and "561" not in prose, (
        "the prose summary is expected to drop everything after the lead sentence")
    # Comparable cost for three values against one, on a verbose fragment.
    assert count_tokens(typed) <= count_tokens(prose)


def test_a_typed_request_over_prose_falls_back_silently() -> None:
    prose = "The harbour publishes a tide window. Berths follow from it."
    assert summarize_fragment(prose, typed=True) == summarize_fragment(prose, typed=False)


# --------------------------------------------------------------------------- #
# through the pipeline: does the value actually reach the successor?
# --------------------------------------------------------------------------- #

class _ChainWorker:
    """A worker that answers a chain step, and records the packet it was given.

    It answers correctly *only* when the packet contains the predecessor's value,
    which is the whole point: a worker cannot divide a number it was never told.
    Given a paraphrase instead, it does what the real 2-4B models did on 24
    August -- it invents something plausible.
    """

    name = "chain-worker"

    def __init__(self) -> None:
        self.packets: list[str] = []

    def generate(self, prompt: str, **kw: object) -> str:
        self.packets.append(prompt)
        if "[01]=" in prompt or "[02]=" in prompt:
            return "[03] 561"
        return "[01] 2496\n[02] 2247"

    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


def _chain_spec():
    from swarmbly_v0.experiment import PromptSpec
    return PromptSpec(
        prompt_id="chain", category="dependency_chain", expected_decomposable=True,
        text=("Work through the costing chain below, one step at a time.\n\n"
              "  [01] Multiply 52 units by the unit price of 48 to get the gross value.\n"
              "  [02] Reduce the gross value from step 1 by 10 percent.\n"
              "  [03] Divide the net value from step 2 by 4 weeks, rounding down.\n\n"
              "Each step uses the numeric result of the step before it."),
        key={"01": {"expected": "2496", "mode": "numeric"},
             "02": {"expected": "2247", "mode": "numeric"},
             "03": {"expected": "561", "mode": "numeric"}},
    )


def _run(typed: bool):
    from swarmbly_v0.experiment import SweepConfig, run_fragmented
    backend = _ChainWorker()
    row = run_fragmented(_chain_spec(), backend, backend,
                         SweepConfig(rhos=(2.0,), ns=(2,), ks=(1,)),
                         rho_target=2.0, n_tasks=2, tau_sem=0.5, typed_carry=typed)
    return row, backend


def test_the_carried_value_reaches_the_successors_packet_verbatim() -> None:
    """The claim, checked at the only place it can be checked: the packet."""
    _, typed_backend = _run(typed=True)
    successor_packets = [p for p in typed_backend.packets if "PREDECESSOR" in p]
    assert successor_packets, "no packet carried a predecessor block at all"
    assert any("[01]=2496" in p for p in successor_packets), successor_packets[-1][:400]


def test_without_the_carry_the_successor_gets_a_paraphrase_instead() -> None:
    _, plain_backend = _run(typed=False)
    successor_packets = [p for p in plain_backend.packets if "PREDECESSOR" in p]
    assert successor_packets
    assert not any("[01]=2496" in p for p in successor_packets), (
        "the untyped arm must not already be carrying typed values")


def test_the_typed_arm_is_recorded_on_the_row_so_the_pair_can_be_found() -> None:
    typed_row, _ = _run(typed=True)
    plain_row, _ = _run(typed=False)
    assert typed_row["typed_carry"] is True
    assert plain_row["typed_carry"] is False
    # Same cell in every other respect: that is what makes the pairing valid.
    for field in ("prompt_id", "rho_target", "n_tasks", "k", "condition"):
        assert typed_row[field] == plain_row[field]


def test_the_context_the_carry_costs_is_small_and_reported() -> None:
    """Completeness is bought, not found, and the price has to stay small.

    A terse worker reply gives 10 tokens of typed carry against 4 of prose. That
    is more, and it is the cost of the successor receiving both values instead of
    the first one. What would sink the mechanism is a *large* cost, so the bound
    is what this test asserts -- not the sign.
    """
    typed_row, _ = _run(typed=True)
    plain_row, _ = _run(typed=False)
    overhead = typed_row["rho_achieved"] - plain_row["rho_achieved"]
    assert overhead >= 0, "a complete carry cannot be cheaper than a truncated one"
    assert overhead < 0.20, f"the carry cost {overhead:.3f} of rho, which is not small"


def test_carry_effect_pairs_the_arms_and_reports_both_sides() -> None:
    from swarmbly_v0.experiment import carry_effect

    rows = [
        {"prompt_id": "c", "condition": "fragmented", "typed_carry": False,
         "rho_target": 2.0, "n_tasks": 2, "k": 1, "rho_achieved": 2.10,
         "coherence_tax_booook": 0.47,
         "_truth_records": [{"category": "dependency_chain", "correct": False}] * 7},
        {"prompt_id": "c", "condition": "fragmented", "typed_carry": True,
         "rho_target": 2.0, "n_tasks": 2, "k": 1, "rho_achieved": 1.80,
         "coherence_tax_booook": 0.09,
         "_truth_records": [{"category": "dependency_chain", "correct": True}] * 6
                           + [{"category": "dependency_chain", "correct": False}]},
    ]
    out = carry_effect(rows)
    assert out["n_pairs"] == 1
    assert out["accuracy_delta"] == pytest.approx(6 / 7)
    assert out["rho_delta"] == pytest.approx(-0.30)
    assert out["tax_delta"] == pytest.approx(-0.38)
    assert out["accuracy_delta_by_category"]["dependency_chain"]["delta"] > 0


def test_a_category_with_nothing_to_type_must_show_no_change() -> None:
    """If prose moves, the two arms differ for some reason other than the carry."""
    from swarmbly_v0.experiment import carry_effect

    def _row(typed: bool):
        return {"prompt_id": "p", "condition": "fragmented", "typed_carry": typed,
                "rho_target": 2.0, "n_tasks": 2, "k": 1, "rho_achieved": 2.0,
                "coherence_tax_booook": 0.05,
                "_truth_records": [{"category": "long_prose", "correct": True},
                                   {"category": "long_prose", "correct": False}]}

    out = carry_effect([_row(False), _row(True)])
    assert out["accuracy_delta_by_category"]["long_prose"]["delta"] == 0.0
