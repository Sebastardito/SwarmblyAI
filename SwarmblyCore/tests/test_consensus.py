"""Micro-level assembly: alignment, gaps, agreement, routing, coverage, diversity."""

from __future__ import annotations

import math

import pytest

from swarmbly_v0 import HashEmbedder, MockBackend, get_backend, get_embedder, load_prompts
from swarmbly_v0.backends import MOCK_FAMILY_POOL, replica_backends, select_diverse_nodes
from swarmbly_v0.consensus import (
    DEFAULT_ALPHA_HIGH,
    DEFAULT_ALPHA_LOW,
    Column,
    Replica,
    Unit,
    agreement_score,
    align_multiple,
    consensus,
    segment_units,
)
from swarmbly_v0.experiment import (
    CSV_COLUMNS,
    SweepConfig,
    agreement_quality_correlation,
    run_sweep,
    summarize,
)
from swarmbly_v0.metrics import (
    calibrate_alpha,
    effective_coverage,
    expected_islands,
    expected_uncovered,
    required_coverage,
)
from swarmbly_v0.schema import Contract

# Four mutually distinct claims. Distinct lexis matters: the hash embedder is a
# lexical-overlap proxy, so units that share no vocabulary are the honest way to
# construct "these are different things" without relying on a semantic model.
S0 = "The Aurora Registry validates every ledger entry before writing it to disk."
S1 = "The Vesper Cache expires each stored receipt after exactly one hour."
S2 = "The Orion Auditor reconciles the nightly ledger against the receipt archive."
S3 = "The Northwind Gateway throttles inbound submissions during peak windows."

CONTRACT = Contract(
    objective="Describe the ledger receipt lifecycle.",
    audience="an auditor",
    register="formal",
    output_format="report",
    target_length_tokens=200,
    forbidden_terms=("obviously",),
    canonical_entities=("Aurora Registry",),
    session_id="test0001",
    prompt_tokens=60,
)


@pytest.fixture()
def embedder() -> HashEmbedder:
    return HashEmbedder()


def _units(texts: list[str], replica_id: str) -> list[Unit]:
    return [Unit(text=t, replica_id=replica_id, index=i) for i, t in enumerate(texts)]


def _ladder() -> list[list[Unit]]:
    """Four replicas covering 4, 3, 2 and 1 of the same units, in the same order.

    Every column therefore has a known, hand-computable agreement: 4/4, 3/4,
    2/4, 1/4.
    """
    return [
        _units([S0, S1, S2, S3], "r0"),
        _units([S0, S1, S2], "r1"),
        _units([S0, S1], "r2"),
        _units([S0], "r3"),
    ]


# --------------------------------------------------------------------------
# Segmentation
# --------------------------------------------------------------------------


def test_segment_units_by_sentence_and_clause() -> None:
    text = "The registry validates entries; the cache expires them, but the auditor reconciles."
    sentences = segment_units(text, "sentence")
    clauses = segment_units(text, "clause")

    assert len(sentences) == 1
    assert len(clauses) > len(sentences)
    assert all(unit.text.strip() for unit in clauses)
    assert [u.index for u in clauses] == list(range(len(clauses)))


def test_segment_units_rejects_unknown_granularity() -> None:
    with pytest.raises(ValueError, match="granularity"):
        segment_units("anything", "paragraph")


# --------------------------------------------------------------------------
# Alignment
# --------------------------------------------------------------------------


def test_alignment_handles_different_lengths(embedder: HashEmbedder) -> None:
    """Replicas of different lengths align by content, not by position."""
    columns = align_multiple(_ladder(), embedder)

    assert len(columns) == 4
    assert [len(c.units) for c in columns] == [4, 3, 2, 1]
    # Every column holds one distinct claim, never two different ones.
    for column in columns:
        assert len({unit.text for unit in column.present}) == 1


def test_an_omitted_unit_becomes_a_gap_not_a_misalignment(embedder: HashEmbedder) -> None:
    """The whole reason for aligning rather than zipping.

    Replica ``r1`` skips the middle claim. A positional zip would pair its third
    claim against the second column and report disagreement everywhere after the
    omission; the aligner must instead leave a gap and keep the tail aligned.
    """
    replicas = [_units([S0, S1, S2], "r0"), _units([S0, S2], "r1")]
    columns = align_multiple(replicas, embedder)

    assert len(columns) == 3
    assert columns[0].contributing == ("r0", "r1")
    assert columns[1].contributing == ("r0",)  # the gap
    assert columns[1].n_gaps == 1
    assert columns[2].contributing == ("r0", "r1")
    assert columns[2].units["r1"].text == S2
    assert columns[2].units["r0"].text == S2


def test_alignment_survives_a_transposition(embedder: HashEmbedder) -> None:
    """Two replicas swap an adjacent pair; shared claims must stay in one column."""
    replicas = [
        _units([S0, S1, S2], "r0"),
        _units([S1, S0, S2], "r1"),
        _units([S0, S1, S2], "r2"),
    ]
    columns = align_multiple(replicas, embedder)

    for column in columns:
        assert len({unit.text for unit in column.present}) == 1, (
            "a column must never mix two different claims"
        )
    aurora = [c for c in columns if c.present[0].text == S0]
    assert len(aurora) == 1 and aurora[0].n_present == 3
    orion = [c for c in columns if c.present[0].text == S2]
    assert len(orion) == 1 and orion[0].n_present == 3


def test_alignment_is_deterministic(embedder: HashEmbedder) -> None:
    first = align_multiple(_ladder(), embedder)
    second = align_multiple(_ladder(), embedder)
    assert [c.contributing for c in first] == [c.contributing for c in second]


def test_alignment_of_a_single_replica_is_the_identity(embedder: HashEmbedder) -> None:
    columns = align_multiple([_units([S0, S1], "r0")], embedder)
    assert [c.present[0].text for c in columns] == [S0, S1]


# --------------------------------------------------------------------------
# Agreement
# --------------------------------------------------------------------------


def test_agreement_is_high_for_near_identical_replicas(embedder: HashEmbedder) -> None:
    replicas = [_units([S0, S1], f"r{i}") for i in range(4)]
    columns = align_multiple(replicas, embedder)
    assert all(agreement_score(c, embedder) == pytest.approx(1.0) for c in columns)


def test_agreement_is_low_for_divergent_replicas(embedder: HashEmbedder) -> None:
    """Four replicas that share no content: every column is one lonely claim."""
    replicas = [_units([text], f"r{i}") for i, text in enumerate([S0, S1, S2, S3])]
    columns = align_multiple(replicas, embedder)

    scores = [agreement_score(c, embedder) for c in columns]
    assert max(scores) <= 0.25 + 1e-9
    assert all(score < DEFAULT_ALPHA_LOW for score in scores)


def test_agreement_normalises_by_k_not_by_units_present(embedder: HashEmbedder) -> None:
    """One replica of five saying something must not score like five agreeing."""
    columns = align_multiple(_ladder(), embedder)
    scores = [agreement_score(c, embedder) for c in columns]
    assert scores == pytest.approx([1.0, 0.75, 0.5, 0.25])


def test_agreement_of_an_empty_column_is_zero(embedder: HashEmbedder) -> None:
    empty = Column(index=0, replica_ids=("r0", "r1"))
    assert agreement_score(empty, embedder) == 0.0


# --------------------------------------------------------------------------
# Three-way routing
# --------------------------------------------------------------------------


def _labels(alpha_high: float, alpha_low: float, embedder: HashEmbedder) -> list[str]:
    """Route the agreement ladder (1.0, 0.75, 0.5, 0.25) at the given alphas."""
    replicas = [
        Replica(replica_id="r0", text=" ".join([S0, S1, S2, S3]), family="llama"),
        Replica(replica_id="r1", text=" ".join([S0, S1, S2]), family="mistral"),
        Replica(replica_id="r2", text=" ".join([S0, S1]), family="qwen"),
        Replica(replica_id="r3", text=S0, family="gemma"),
    ]
    result = consensus(replicas, CONTRACT, embedder,
                       alpha_high=alpha_high, alpha_low=alpha_low)
    assert [round(u.agreement, 2) for u in result.units] == [1.0, 0.75, 0.5, 0.25]
    return [u.label for u in result.units]


def test_routing_splits_high_medium_low(embedder: HashEmbedder) -> None:
    assert _labels(0.80, 0.50, embedder) == ["HIGH", "MEDIUM", "MEDIUM", "LOW"]


def test_routing_boundaries_are_inclusive_at_the_thresholds(embedder: HashEmbedder) -> None:
    """The comparisons are ``>= alpha_high`` and ``>= alpha_low``, exactly."""
    # 0.75 sits exactly on alpha_high -> HIGH, not MEDIUM.
    assert _labels(0.75, 0.50, embedder)[1] == "HIGH"
    # A hair above it -> MEDIUM.
    assert _labels(0.7501, 0.50, embedder)[1] == "MEDIUM"
    # 0.75 sits exactly on alpha_low -> MEDIUM, not LOW.
    assert _labels(0.90, 0.75, embedder)[1] == "MEDIUM"
    # A hair above it -> LOW.
    assert _labels(0.90, 0.7501, embedder)[1] == "LOW"


def test_low_units_are_recorded_as_low_confidence_regions(embedder: HashEmbedder) -> None:
    replicas = [
        Replica(replica_id="r0", text=" ".join([S0, S2, S3]), family="llama"),
        Replica(replica_id="r1", text=S0, family="mistral"),
    ]
    result = consensus(replicas, CONTRACT, embedder, alpha_high=0.9, alpha_low=0.6)

    assert [u.label for u in result.units] == ["HIGH", "LOW", "LOW"]
    assert len(result.low_confidence_regions) == 1, "adjacent LOW units form one region"
    region = result.low_confidence_regions[0]
    assert (region.start, region.end, region.n_units) == (1, 2, 2)
    assert S2 in region.text and S3 in region.text


def test_high_agreement_takes_the_medoid_and_reports_contributors(
    embedder: HashEmbedder
) -> None:
    replicas = [Replica(replica_id=f"r{i}", text=S0, family=f"f{i}") for i in range(3)]
    result = consensus(replicas, CONTRACT, embedder)

    assert len(result.units) == 1
    unit = result.units[0]
    assert unit.label == "HIGH"
    assert unit.text == S0
    assert unit.contributing == ("r0", "r1", "r2")
    assert result.k == 3 and result.n_families == 3
    assert result.mean_agreement == pytest.approx(1.0)
    assert result.label_fractions()["HIGH"] == pytest.approx(1.0)


def test_consensus_rejects_inverted_thresholds(embedder: HashEmbedder) -> None:
    with pytest.raises(ValueError, match="alpha_low"):
        consensus([Replica("r0", S0)], CONTRACT, embedder, alpha_high=0.4, alpha_low=0.8)


def test_consensus_accepts_bare_strings_and_is_deterministic(embedder: HashEmbedder) -> None:
    first = consensus([S0, S1, S0], CONTRACT, embedder)
    second = consensus([S0, S1, S0], CONTRACT, embedder)

    assert first.text == second.text
    assert [u.label for u in first.units] == [u.label for u in second.units]
    assert first.k == 3
    assert first.n_families == 1, "bare strings carry no family: the score means little"


def test_empty_replica_set_does_not_crash(embedder: HashEmbedder) -> None:
    result = consensus([], CONTRACT, embedder)
    assert result.text == "" and result.units == [] and result.k == 0


def test_default_thresholds_are_documented_placeholders() -> None:
    """They must remain overridable parameters, never module state read at use."""
    assert DEFAULT_ALPHA_HIGH == 0.80
    assert DEFAULT_ALPHA_LOW == 0.55
    assert "calibrat" in (consensus.__doc__ or "").lower()


# --------------------------------------------------------------------------
# alpha calibration
# --------------------------------------------------------------------------


def _observations() -> list[tuple[float, bool]]:
    """Agreement genuinely predicts acceptability in this synthetic set."""
    high = [(0.9, True), (0.85, True), (0.95, True), (0.8, True), (0.88, True)]
    low = [(0.2, False), (0.3, False), (0.1, False), (0.35, False), (0.25, False)]
    return high + low + [(0.6, True), (0.55, False)]


def test_calibrate_alpha_separates_the_two_classes() -> None:
    calibration = calibrate_alpha(_observations(), beta=0.5)

    assert 0.0 < calibration.alpha_low <= calibration.alpha_high < 1.0
    assert 0.35 < calibration.alpha_high < 0.95
    assert calibration.precision_high > 0.8
    assert calibration.n_units == len(_observations())
    assert all(0.0 < point["alpha"] < 1.0 for point in calibration.curve)


def test_calibrate_alpha_requires_an_asymmetric_beta() -> None:
    with pytest.raises(ValueError, match="asymmetric"):
        calibrate_alpha(_observations(), beta=1.0)


def test_calibrate_alpha_rejects_an_empty_set() -> None:
    with pytest.raises(ValueError):
        calibrate_alpha([])


def test_calibrate_alpha_is_deterministic() -> None:
    assert calibrate_alpha(_observations()).as_dict() == calibrate_alpha(_observations()).as_dict()


# --------------------------------------------------------------------------
# Coverage model
# --------------------------------------------------------------------------


def test_effective_coverage_discounts_lost_packets() -> None:
    assert effective_coverage(5.0, 0.0) == pytest.approx(5.0)
    assert effective_coverage(5.0, 0.20) == pytest.approx(4.0)
    assert effective_coverage(0.0, 0.5) == pytest.approx(0.0)


def test_expected_uncovered_matches_hand_computation() -> None:
    # M = 100 units, c = 3, p = 0 -> 100 * e^-3 = 4.9787...
    assert expected_uncovered(100, 3.0, 0.0) == pytest.approx(100 * math.exp(-3.0))
    # With 10% loss the effective coverage is 2.7 -> 100 * e^-2.7 = 6.7206...
    assert expected_uncovered(100, 3.0, 0.10) == pytest.approx(6.720551, abs=1e-5)
    # M = 1 returns the fraction itself.
    assert expected_uncovered(1, 8.0, 0.0) == pytest.approx(0.00033546, abs=1e-8)


def test_expected_islands_reduces_to_the_textbook_form_as_theta_falls() -> None:
    assert expected_islands(20, 4.0, 0.0, 1.0) == pytest.approx(20 * math.exp(-4.0))
    assert expected_islands(20, 4.0, 0.0, 0.0) == pytest.approx(20.0)
    # Loss makes the assembly more fragmented, never less.
    assert expected_islands(20, 4.0, 0.25, 0.5) > expected_islands(20, 4.0, 0.0, 0.5)


def test_required_coverage_matches_hand_computed_values() -> None:
    # ln(1/0.01) / (1 - 0.10) = 4.605170 / 0.9 = 5.116856
    assert required_coverage(0.01, 0.10) == pytest.approx(4.6051702 / 0.9, abs=1e-6)
    assert required_coverage(0.01, 0.10) == pytest.approx(5.108, abs=0.01)
    # With no loss it is the plain ln(1/epsilon).
    assert required_coverage(0.01, 0.0) == pytest.approx(math.log(100.0))
    assert required_coverage(0.001, 0.0) == pytest.approx(math.log(1000.0))


def test_required_coverage_inverts_expected_uncovered() -> None:
    for epsilon, p in ((0.01, 0.0), (0.05, 0.1), (0.001, 0.25)):
        c = required_coverage(epsilon, p)
        assert expected_uncovered(1.0, c, p) == pytest.approx(epsilon, rel=1e-9)


def test_coverage_model_rejects_impossible_parameters() -> None:
    for bad_p in (1.0, -0.1, 1.5):
        with pytest.raises(ValueError):
            effective_coverage(3.0, bad_p)
    for bad_epsilon in (0.0, 1.0, -1.0):
        with pytest.raises(ValueError):
            required_coverage(bad_epsilon, 0.1)
    with pytest.raises(ValueError):
        expected_islands(10, 3.0, 0.0, 1.5)


# --------------------------------------------------------------------------
# Family diversity
# --------------------------------------------------------------------------


def test_family_selection_returns_distinct_families_when_available() -> None:
    for k in (2, 3, 5):
        chosen = select_diverse_nodes(MOCK_FAMILY_POOL, k)
        assert len(chosen) == k
        assert len({family for family, _ in chosen}) == k, "families must all differ"


def test_family_selection_repeats_only_after_exhausting_families() -> None:
    families = {family for family, _ in MOCK_FAMILY_POOL}
    chosen = select_diverse_nodes(MOCK_FAMILY_POOL, len(families) + 1)

    assert len(chosen) == len(families) + 1
    assert {family for family, _ in chosen} == families
    assert len(set(chosen)) == len(chosen), "prefer another model of a family over a repeat"


def test_family_selection_is_deterministic_and_degenerate_safe() -> None:
    assert select_diverse_nodes(MOCK_FAMILY_POOL, 4) == select_diverse_nodes(MOCK_FAMILY_POOL, 4)
    assert select_diverse_nodes([], 3) == []
    assert select_diverse_nodes(MOCK_FAMILY_POOL, 0) == []


def test_replica_backends_produce_related_but_different_outputs() -> None:
    """Identical replicas would make every agreement score 1.0 by construction."""
    prompt = (
        "[GLOBAL CONTRACT]\nsession: t\nobjective: describe the ledger lifecycle\n"
        "register: formal\noutput_format: report\ntarget_length_tokens: 90\n"
        "glossary:\n- Aurora Registry: canonical name; use this exact surface form.\n"
        "[TASK t0]\nDescribe how the ledger validates and stores each receipt."
    )
    nodes = replica_backends(MockBackend(seed=0), 4)
    outputs = [node.generate(prompt, max_tokens=90) for node in nodes]

    assert len({node.family for node in nodes}) == 4
    assert len(set(outputs)) == 4, "replicas must not be identical strings"
    # ... but they must still be about the same thing.
    embedder = HashEmbedder()
    vectors = embedder.embed(outputs)
    assert all(float(vectors[0] @ vectors[i]) > 0.3 for i in range(1, 4))


def test_family_replicas_are_deterministic() -> None:
    prompt = "[TASK t0]\nDescribe the ledger receipt lifecycle."
    first = replica_backends(MockBackend(seed=5), 3)
    second = replica_backends(MockBackend(seed=5), 3)
    assert [n.generate(prompt) for n in first] == [n.generate(prompt) for n in second]


def test_family_free_mock_is_unchanged_by_the_replica_machinery() -> None:
    """k = 1 must be the old pipeline exactly, or k is not a controlled variable."""
    prompt = "[TASK t0]\nDescribe the ledger receipt lifecycle."
    assert MockBackend(seed=3).generate(prompt) == MockBackend(seed=3, family="").generate(prompt)
    assert MockBackend(seed=3).generate(prompt) != MockBackend(seed=3,
                                                              family="qwen").generate(prompt)


# --------------------------------------------------------------------------
# Sweep integration
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def k_sweep():
    prompts = load_prompts()[:2]
    config = SweepConfig(rhos=(1.5,), ns=(2,), ks=(1, 3), seed=0)
    rows, metadata = run_sweep(
        prompts, config, get_backend("mock", seed=0), get_embedder("hash")
    )
    return prompts, rows, metadata


def test_sweep_populates_every_consensus_column(k_sweep) -> None:
    _, rows, _ = k_sweep
    fragmented = [r for r in rows if r["condition"] == "fragmented"]
    consensus_rows = [r for r in fragmented if r["k"] == 3]

    assert len(consensus_rows) == 2
    for column in ("k", "n_families", "mean_agreement", "frac_high", "frac_medium",
                   "frac_low", "n_low_conf_regions", "consensus_used"):
        assert column in CSV_COLUMNS
    for row in consensus_rows:
        assert row["consensus_used"] is True
        assert row["n_families"] == 3
        assert 0.0 <= row["mean_agreement"] <= 1.0
        assert row["frac_high"] + row["frac_medium"] + row["frac_low"] == pytest.approx(1.0)
        assert row["n_low_conf_regions"] >= 0


def test_k_one_rows_skip_consensus_entirely(k_sweep) -> None:
    _, rows, _ = k_sweep
    for row in rows:
        if row.get("k") == 1:
            assert row["consensus_used"] is False
            assert row["mean_agreement"] == ""


def test_replicas_cost_input_tokens_but_do_not_inflate_rho(k_sweep) -> None:
    """rho is contextual redundancy; replica redundancy is a separate axis."""
    _, rows, _ = k_sweep
    cells = {r["k"]: r for r in rows if r["condition"] == "fragmented"
             and r["prompt_id"] == rows[0]["prompt_id"]}

    assert cells[1]["rho_achieved"] == pytest.approx(cells[3]["rho_achieved"])
    assert cells[3]["input_tokens"] == 3 * cells[1]["input_tokens"]


def test_summary_reports_the_agreement_quality_correlation(k_sweep) -> None:
    prompts, rows, _ = k_sweep
    stats = summarize(rows, prompts)
    calibration = stats["agreement_quality_correlation"]

    assert calibration["n_units"] > 0
    assert 0.0 <= calibration["mean_agreement"] <= 1.0
    assert calibration["pearson_r"] is None or -1.0 <= calibration["pearson_r"] <= 1.0
    assert [b["midpoint"] for b in calibration["bins"]] == [0.1, 0.3, 0.5, 0.7, 0.9]
    assert any(int(c["k"]) == 3 for c in stats["consensus_curve"])


def test_correlation_is_undefined_rather_than_faked_when_a_variable_is_constant() -> None:
    constant = [{"agreement": 0.8, "accepted": True} for _ in range(10)]
    assert agreement_quality_correlation(constant)["pearson_r"] is None

    perfect = [{"agreement": a, "accepted": a > 0.5}
               for a in (0.1, 0.2, 0.3, 0.7, 0.8, 0.9)]
    assert agreement_quality_correlation(perfect)["pearson_r"] == pytest.approx(1.0, abs=0.15)


def test_unit_sidecar_round_trips_and_feeds_the_report(k_sweep, tmp_path) -> None:
    """The chart must render from a bare CSV path, so the per-unit data must persist."""
    from swarmbly_v0 import render_report
    from swarmbly_v0.experiment import UNIT_CSV_NAME, read_unit_rows, write_csv

    prompts, rows, metadata = k_sweep
    csv_path = write_csv(rows, tmp_path / "results.csv")
    sidecar = csv_path.with_name(UNIT_CSV_NAME)

    assert sidecar.exists()
    units = read_unit_rows(sidecar)
    assert units and all(0.0 <= u["agreement"] <= 1.0 for u in units)
    assert {u["label"] for u in units} <= {"HIGH", "MEDIUM", "LOW"}
    assert isinstance(units[0]["accepted"], bool)

    html = render_report(csv_path, tmp_path / "report.html", metadata, prompts).read_text(
        encoding="utf-8"
    )
    assert html.count("<svg") == 2, "macro curve plus micro calibration"
    assert "consensus agreement score" in html
    assert "judged acceptable" in html
    # Chart conventions, on the new chart as much as the old one.
    assert "#2a78d6" in html and "#3987e5" in html
    assert 'stroke-width="2"' in html and 'r="5"' in html
    assert "<title>" in html, "hover tooltip"
    assert 'data-group="agreement"' in html, "the new chart owns its own table toggle"
    for forbidden in ("http://", "https://", "cdn.", "<link", "src="):
        assert forbidden not in html


def test_report_degrades_gracefully_without_consensus_units(tmp_path) -> None:
    from swarmbly_v0 import render_report
    from swarmbly_v0.experiment import write_csv

    prompts = load_prompts()[:1]
    config = SweepConfig(rhos=(1.5,), ns=(2,), ks=(1,), seed=0)
    rows, metadata = run_sweep(prompts, config, get_backend("mock", seed=0),
                               get_embedder("hash"))
    csv_path = write_csv(rows, tmp_path / "results.csv")

    assert not csv_path.with_name("agreement_units.csv").exists()
    html = render_report(csv_path, tmp_path / "report.html", metadata, prompts).read_text(
        encoding="utf-8"
    )
    assert "sweep with --k greater than 1" in html


def test_k_sweep_is_reproducible_under_a_seed() -> None:
    prompts = load_prompts()[:1]
    config = SweepConfig(rhos=(1.5,), ns=(2,), ks=(3,), seed=13)
    first, _ = run_sweep(prompts, config, get_backend("mock", seed=13), get_embedder("hash"))
    second, _ = run_sweep(prompts, config, get_backend("mock", seed=13), get_embedder("hash"))

    keys = ("mean_agreement", "frac_high", "frac_low", "booook_like_score")
    assert [[r[k] for k in keys] for r in first] == [[r[k] for k in keys] for r in second]
