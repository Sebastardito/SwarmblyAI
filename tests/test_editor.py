"""The post-processing editor, and the three refusals that make it safe.

The editor exists because every defect the composition runs produced is a
property of the whole answer, which no worker can see. It is *dangerous* for the
same reason the bridge turned out to be: a mechanism with the whole answer in
hand and one objective in mind will trade an unmeasured dimension for a measured
one. Most of these tests are about the trades it must refuse.
"""

from __future__ import annotations

import pytest

from swarmbly_v0.constraints import derived_aggregates, grade_text
from swarmbly_v0.editor import REPAIR_INSTRUCTIONS, edit_assembled

TWO_PARAGRAPHS = [
    {"id": "paragraphs", "kind": "paragraph_count", "count": 2},
    {"id": "tide_once", "kind": "term_once", "term": "tide window"},
]


class _Backend:
    """A backend that returns whatever it was told to, and records the prompt."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    def generate(self, prompt: str, **kwargs: object) -> str:
        self.prompts.append(prompt)
        return self.reply


class _Exploding:
    def generate(self, prompt: str, **kwargs: object) -> str:
        raise RuntimeError("node unreachable")


THREE_PARAS = ("The tide window is narrow.\n\nA bridge sentence.\n\n"
               "Berths are allocated in order.")
TWO_PARAS = ("The tide window is narrow. A bridge sentence.\n\n"
             "Berths are allocated in order.")


def test_the_extra_paragraph_the_bridge_creates_is_repairable() -> None:
    """The exact defect of 25 August: comp_harbour k=3, three paragraphs for two.

    The assembler inserted a bridge because the seam similarity fell below
    tau_sem. The bridge repaired the seam and became a paragraph, breaking a
    constraint the assembler cannot see.
    """
    before = grade_text(THREE_PARAS, TWO_PARAGRAPHS)
    assert before.n_satisfied == 1

    out = edit_assembled(THREE_PARAS, TWO_PARAGRAPHS, _Backend(TWO_PARAS),
                         objective="Describe the harbour.")
    assert out.applied
    assert out.reason == "applied"
    assert out.score_after == 1.0
    assert out.gain == pytest.approx(0.5)
    assert "paragraphs" in out.violations_before
    assert out.violations_after == ()


def test_a_revision_that_scores_worse_is_rejected_and_the_answer_survives() -> None:
    """The gate the bridge never had.

    Without it the editor is one more mechanism that improves what it is looking
    at while quietly breaking what it is not.
    """
    worse = "The tide window is narrow.\n\nTwo.\n\nThree. The tide window again."
    out = edit_assembled(THREE_PARAS, TWO_PARAGRAPHS, _Backend(worse))
    assert not out.applied
    assert out.reason == "the revision scored worse and was rejected"
    assert out.text == THREE_PARAS, "a rejected repair must not lose the answer"


def test_an_equal_scoring_revision_is_accepted_but_named_as_such() -> None:
    """An edit that removes a duplicate without reaching the paragraph count.

    It has not earned a better score and it has still improved the answer, so it
    is applied and labelled honestly rather than counted as a gain.
    """
    still_three = ("The tide window is narrow.\n\nA bridge sentence.\n\n"
                   "Berths are allocated in strict order.")
    out = edit_assembled(THREE_PARAS, [{"id": "p", "kind": "paragraph_count", "count": 2}],
                         _Backend(still_three))
    assert out.applied and out.reason == "applied without gain"
    assert out.gain == pytest.approx(0.0)


def test_the_editor_may_not_invent_a_figure_to_satisfy_a_constraint() -> None:
    """On grounded prose, "mention the total" is satisfiable by writing one.

    That is the failure that would make the editor worse than useless: a
    fabrication introduced by the repair itself, in the one corpus built so that
    correctness could be checked.
    """
    constraints = [{"id": "total", "kind": "must_mention", "term": "total"},
                   {"id": "paragraphs", "kind": "paragraph_count", "count": 1}]
    original = "The heaviest consignment is 830 kg."
    invented = "The heaviest consignment is 830 kg and the total is 9999 kg."

    out = edit_assembled(original, constraints, _Backend(invented),
                         numeric_allowed=[830.0, 375.0, 1205.0])
    assert not out.applied
    assert out.reason == "the revision introduced an unsupported figure"
    assert "9999" not in out.text


def test_a_legitimate_aggregate_is_not_treated_as_a_fabrication() -> None:
    """The guard must not punish the editor for doing arithmetic correctly."""
    constraints = [{"id": "total", "kind": "must_mention", "term": "total"},
                   {"id": "paragraphs", "kind": "paragraph_count", "count": 1}]
    original = "The consignments weigh 830 kg and 375 kg."
    correct = "The consignments weigh 830 kg and 375 kg, a total of 1205 kg."

    out = edit_assembled(original, constraints, _Backend(correct),
                         numeric_allowed=sorted({830.0, 375.0} | derived_aggregates([830.0, 375.0])))
    assert out.applied, out.reason
    assert "1205" in out.text


def test_the_fabrication_guard_is_off_when_no_figures_were_declared() -> None:
    """Silence is not permission to check: a prose prompt has no allowed set."""
    constraints = [{"id": "p", "kind": "paragraph_count", "count": 1}]
    out = edit_assembled("One.\n\nTwo.", constraints, _Backend("One. Two. In 1999."))
    assert out.applied


def test_a_failed_repair_call_never_loses_the_answer() -> None:
    out = edit_assembled(THREE_PARAS, TWO_PARAGRAPHS, _Exploding())
    assert out.text == THREE_PARAS
    assert not out.applied and out.reason == "the repair call failed"


def test_an_empty_revision_is_refused() -> None:
    out = edit_assembled(THREE_PARAS, TWO_PARAGRAPHS, _Backend("   "))
    assert out.text == THREE_PARAS and out.reason == "the revision was empty"


def test_a_clean_answer_costs_nothing() -> None:
    """No defect, no call: the editor must not be a tax on answers that are fine."""
    backend = _Backend("should never be used")
    out = edit_assembled(TWO_PARAS, [{"id": "p", "kind": "paragraph_count", "count": 2}],
                         backend)
    assert not out.applied and out.reason == "nothing failed"
    assert backend.prompts == [], "the editor called the backend with nothing to fix"
    assert out.input_tokens == 0


def test_the_repair_prompt_names_the_defect_rather_than_asking_for_a_rewrite() -> None:
    """"Improve this text" produces a new answer, and a new answer cannot be
    attributed to assembly repair. The instruction has to carry the numbers."""
    backend = _Backend(TWO_PARAS)
    edit_assembled(THREE_PARAS, TWO_PARAGRAPHS, backend, objective="Describe the harbour.")
    prompt = backend.prompts[0]
    assert "exactly 2 paragraphs" in prompt
    assert "currently has 3" in prompt
    assert "Describe the harbour." in prompt
    assert "do not add any fact" in prompt
    for word in ("improve", "rewrite", "better"):
        assert word not in prompt.lower(), f"the prompt invites a rewrite via {word!r}"


def test_the_cost_is_reported_as_its_own_budget_line() -> None:
    """rho is defined over the problem and the editor never sees the problem, so
    rho is unchanged -- but that is an argument, and the tokens are a fact."""
    out = edit_assembled(THREE_PARAS, TWO_PARAGRAPHS, _Backend(TWO_PARAS))
    assert out.input_tokens > 0 and out.output_tokens > 0
    assert out.calls == 1
    d = out.as_dict()
    assert d["editor_input_tokens"] == out.input_tokens
    assert d["editor_gain"] == out.gain


def test_every_constraint_kind_has_a_repair_instruction() -> None:
    """A kind with no instruction degrades to a vague sentence, which is exactly
    the prompt that produces a rewrite."""
    from swarmbly_v0.constraints import CONSTRAINT_KINDS
    missing = [k for k in CONSTRAINT_KINDS if k not in REPAIR_INSTRUCTIONS]
    assert not missing, f"no repair instruction for {missing}"


# --------------------------------------------------------------------------- #
# through the real pipeline
# --------------------------------------------------------------------------- #

def test_the_editor_arm_runs_end_to_end_and_reports_its_own_budget() -> None:
    """The preflight: a real sweep with both arms, driven by a scripted backend.

    Mirrors the pattern the rest of the suite uses. The backend answers the
    micro-tasks with a two-sentence block and answers the repair prompt with a
    compliant text, so the run exercises planning, packing, assembly, the editor
    gate and the summary in one pass.
    """
    from swarmbly_v0.experiment import PromptSpec, SweepConfig, run_sweep, summarize

    class _Scripted:
        name = "scripted"

        def generate(self, prompt: str, **kwargs: object) -> str:
            if "[CORRECTIONS REQUIRED]" in prompt:
                return ("The tide window governs every berth allocation here.\n\n"
                        "Cargo is scheduled against that window and nothing else.")
            return "The tide window governs berth allocation."

        def embed(self, texts):
            return [[1.0, 0.0] for _ in texts]

    spec = PromptSpec(
        prompt_id="comp", category="composition", expected_decomposable=True,
        text=("Explain how a harbour schedules cargo. Write exactly two paragraphs, "
              "separated by a blank line."),
        constraints=[{"id": "paragraphs", "kind": "paragraph_count", "count": 2},
                     {"id": "tide_once", "kind": "term_once", "term": "tide window"}],
    )
    backend = _Scripted()
    cfg = SweepConfig(rhos=(1.5,), ns=(2,), ks=(1,), editors=(False, True), tau_sem=0.5)
    rows, _ = run_sweep([spec], cfg, backend=backend, embedder=backend)

    conditions = {str(r["condition"]) for r in rows}
    assert conditions == {"monolithic", "fragmented", "fragmented+editor"}

    plain = next(r for r in rows if r["condition"] == "fragmented")
    edited = next(r for r in rows if r["condition"] == "fragmented+editor")

    # The unedited arm must carry no editor cost at all -- blank, not zero.
    assert plain["editor_applied"] == ""
    assert plain["editor_input_tokens"] == ""
    assert isinstance(edited["editor_calls"], int)

    summary = summarize(rows, prompts=[spec])
    effect = summary["editor_effect"]
    assert effect["n_pairs"] == 1
    assert effect["accuracy_delta"] is None, "no answer key here, so no accuracy claim"
    assert "rho is" in effect["note"]


def test_the_fragment_size_curve_reports_both_axes_and_flags_monotonicity() -> None:
    from swarmbly_v0.experiment import fragment_size_curve

    rows = [
        {"prompt_id": "p", "condition": "monolithic", "input_tokens": 264},
        {"prompt_id": "p", "condition": "fragmented", "category": "a", "n_tasks": 2,
         "coherence_tax_booook": 0.067},
        {"prompt_id": "p", "condition": "fragmented", "category": "a", "n_tasks": 4,
         "coherence_tax_booook": 0.140},
        {"prompt_id": "p", "condition": "fragmented", "category": "a", "n_tasks": 8,
         "coherence_tax_booook": 0.351},
    ]
    curve = fragment_size_curve(rows)
    sizes = [pt["tokens_per_fragment"] for pt in curve["points"]]
    assert sizes == [132.0, 66.0, 33.0]
    assert curve["tax_monotone_in_n"] is True
    assert curve["points"][0]["tax_balanced"] == pytest.approx(0.067)
    assert curve["planner_constant_tokens_per_task"] == 60


def test_the_curve_separates_a_balanced_mean_from_a_pooled_one() -> None:
    """The pooling artifact has produced a wrong headline three times already."""
    from swarmbly_v0.experiment import fragment_size_curve

    rows = [{"prompt_id": "p", "condition": "monolithic", "input_tokens": 100}]
    rows += [{"prompt_id": "p", "condition": "fragmented", "category": "many",
              "n_tasks": 2, "coherence_tax_booook": 0.5} for _ in range(9)]
    rows += [{"prompt_id": "p", "condition": "fragmented", "category": "few",
              "n_tasks": 2, "coherence_tax_booook": 0.1}]

    point = fragment_size_curve(rows)["points"][0]
    assert point["tax_pooled"] == pytest.approx(0.46)
    assert point["tax_balanced"] == pytest.approx(0.30)


def test_the_old_go_no_go_cannot_fail_and_the_new_one_can() -> None:
    """The audit finding, encoded so it cannot quietly come back.

    A cell whose tax is plainly above the threshold must fail, and it must fail
    on the interval rather than on the point estimate.
    """
    from swarmbly_v0.experiment import falsifiable_go_no_go

    expensive = [{"condition": "fragmented", "category": "a", "rho_target": 1.5,
                  "coherence_tax_booook": v} for v in (0.20, 0.24, 0.19, 0.22)]
    out = falsifiable_go_no_go(expensive, category="a", rho=1.5)
    assert out["passed"] is False
    assert out["declared_cell"] == {"category": "a", "rho": 1.5}

    cheap = [{"condition": "fragmented", "category": "a", "rho_target": 1.5,
              "coherence_tax_booook": v} for v in (0.01, 0.02, 0.015, 0.012)]
    assert falsifiable_go_no_go(cheap, category="a", rho=1.5)["passed"] is True

    # Cheap on average but wildly variable: the point estimate clears the bar and
    # the interval does not. This is the case the old criterion counted as a pass.
    noisy = [{"condition": "fragmented", "category": "a", "rho_target": 1.5,
              "coherence_tax_booook": v} for v in (-0.30, 0.35, -0.25, 0.32)]
    noisy_out = falsifiable_go_no_go(noisy, category="a", rho=1.5)
    assert noisy_out["point_estimate"] < 0.05
    assert noisy_out["passed"] is False


def test_the_declared_cell_cannot_be_chosen_after_the_fact() -> None:
    """n_cells_examined states how many chances the criterion really had."""
    from swarmbly_v0.experiment import falsifiable_go_no_go

    rows = [{"condition": "fragmented", "category": c, "rho_target": r,
             "coherence_tax_booook": 0.01}
            for c in ("a", "b", "c") for r in (1.0, 1.5)] * 2
    out = falsifiable_go_no_go(rows, category="a", rho=1.5)
    assert out["n_cells_examined"] == 6


# --------------------------------------------------------------------------- #
# the V4 corpus
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def complex_corpus() -> dict:
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "prompts" / "complex.json"
    if not path.exists():
        pytest.skip("prompts/complex.json not generated")
    return json.loads(path.read_text())


def test_the_corpus_spans_fragment_sizes_the_older_corpora_could_not_reach(complex_corpus) -> None:
    """A corpus that cannot express the independent variable cannot measure it.

    V0's widest fragment was 133 tokens and its curve was still falling there.
    Sweeping N over a 124-160 token prompt cannot produce anything larger, which
    is why the top of the curve has never been observed.
    """
    from swarmbly_v0.textutil import count_tokens
    sizes = [count_tokens(p["prompt"]) for p in complex_corpus["prompts"]]
    assert min(sizes) >= 200, f"shortest prompt is {min(sizes)} tokens"
    assert max(sizes) / 2 > 133, "N=2 must reach past V0's widest fragment"
    assert max(sizes) / 16 < 40, "N=16 must still reach the starved end"


def test_all_three_task_shapes_are_present(complex_corpus) -> None:
    """S* is claimed to be a semantic unit, not a token count, so it must be
    measurable on shapes whose units differ: a topic, a row group, a step."""
    from collections import Counter
    shapes = Counter(p["category"] for p in complex_corpus["prompts"])
    assert set(shapes) == {"long_prose", "table_summary", "dependency_chain"}
    assert all(n >= 3 for n in shapes.values()), shapes


def test_every_dependency_chain_key_is_arithmetically_consistent(complex_corpus) -> None:
    """The keys are computed by the generator from the prompt's own numbers, so
    a key cannot drift from its prompt -- but only if the chain is really a
    chain. Each step must be reachable from the one before it."""
    import re
    chains = [p for p in complex_corpus["prompts"] if p["category"] == "dependency_chain"]
    assert chains
    for chain in chains:
        key = chain["key"]
        assert len(key) >= 8, "the depth axis needs a chain deep enough to break"
        values = [int(key[f"{i:02d}"]["expected"]) for i in range(1, len(key) + 1)]
        assert len(set(values)) == len(values), (
            f"{chain['id']}: a repeated intermediate lets a wrong step score right")
        for i in range(1, len(key) + 1):
            source = key[f"{i:02d}"]["source"]
            if i > 1:
                assert re.search(rf"step {i - 1}\b", source), (
                    f"{chain['id']} step {i} does not consume step {i - 1}")


def test_every_table_figure_is_supported_by_its_own_table(complex_corpus) -> None:
    """The defect that made grounded prose unusable: a correct citation graded a
    fabrication. Here the allowed set is built from the enclosed rows."""
    from swarmbly_v0.constraints import check_numeric_fidelity
    tables = [p for p in complex_corpus["prompts"] if p["category"] == "table_summary"]
    assert tables
    for table in tables:
        allowed = table["numeric_facts"]["allowed"]
        assert check_numeric_fidelity(f"The total is {table['numeric_facts']['total']:.0f}.",
                                      allowed) is True
        assert check_numeric_fidelity("The total is 999999.", allowed) is False
        rows = [line for line in table["prompt"].splitlines() if line.count("|") == 3]
        assert len(rows) >= 20, f"{table['id']} has only {len(rows)} table lines"


def test_the_long_prose_prompts_forbid_figures_so_prose_is_graded_as_prose(
        complex_corpus) -> None:
    """Separating the axes: long_prose tests structure, table_summary tests
    numeric fidelity. A prose prompt that invited figures would confound them."""
    prose = [p for p in complex_corpus["prompts"] if p["category"] == "long_prose"]
    for prompt in prose:
        assert "Do not state any numeric figure" in prompt["prompt"]
        assert "numeric_facts" not in prompt


def test_every_constraint_in_the_corpus_is_a_kind_the_editor_can_repair(
        complex_corpus) -> None:
    from swarmbly_v0.constraints import CONSTRAINT_KINDS
    for prompt in complex_corpus["prompts"]:
        for spec in prompt.get("constraints", []):
            assert spec["kind"] in CONSTRAINT_KINDS
            assert spec["kind"] in REPAIR_INSTRUCTIONS, (
                f"{prompt['id']} uses {spec['kind']}, which the editor cannot act on")


def test_the_curve_flags_when_its_points_are_made_of_different_shapes() -> None:
    """N is capped by how many divisible units a prompt has, so the high-N points
    lose the prompts that ran out of units. The curve must say so rather than
    letting a change of composition read as a change of cost."""
    from swarmbly_v0.experiment import fragment_size_curve

    rows = [{"prompt_id": "p", "condition": "monolithic", "input_tokens": 320}]
    # 'table' survives to every N; 'prose' caps out at 4.
    for n, tax in ((2, 0.05), (4, 0.10), (8, 0.20)):
        rows.append({"prompt_id": "p", "condition": "fragmented", "category": "table",
                     "n_tasks": n, "coherence_tax_booook": tax})
    for n, tax in ((2, 0.45), (4, 0.50)):
        rows.append({"prompt_id": "p", "condition": "fragmented", "category": "prose",
                     "n_tasks": n, "coherence_tax_booook": tax})

    curve = fragment_size_curve(rows)
    assert curve["comparable_across_n"] is False
    assert curve["common_categories"] == ["table"]

    at_eight = next(p for p in curve["points"] if p["n_tasks"] == 8)
    at_two = next(p for p in curve["points"] if p["n_tasks"] == 2)
    # Balanced falls from 0.25 to 0.20 purely because the expensive shape dropped
    # out; restricted to the common shape the cost rises, which is the truth.
    assert at_two["tax_balanced"] > at_eight["tax_balanced"]
    assert at_two["tax_common"] < at_eight["tax_common"]
    assert curve["tax_monotone_in_n"] is False
    assert curve["tax_common_monotone_in_n"] is True


def test_the_paragraph_count_no_longer_freezes_the_partition() -> None:
    """The sweep asked for N in (2,4,8,16) and every cell came back at N=6.

    A prompt saying "exactly six paragraphs" was planned as six fragments, so
    fragment size -- the whole independent variable of V4 -- could not move.
    """
    from swarmbly_v0.assembler import _join

    pieces = [f"Fragment {i}." for i in range(8)]
    assert _join(pieces, 2).count("\n\n") == 1, "8 workers, 2 paragraphs"
    assert len(_join(pieces, 4).split("\n\n")) == 4
    assert _join(pieces, True).count("\n\n") == 7, "the old behaviour still available"
    assert "\n\n" not in _join(pieces, False)
    # Fewer fragments than paragraphs: the shortfall fails honestly.
    assert len(_join(["only one"], 6).split("\n\n")) == 1


def test_grouping_is_contiguous_and_balanced() -> None:
    """A paragraph made of several workers' output must keep them in order."""
    from swarmbly_v0.assembler import _join

    groups = _join([f"f{i}" for i in range(7)], 3).split("\n\n")
    assert groups == ["f0 f1 f2", "f3 f4", "f5 f6"]
