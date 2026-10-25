"""Entity-grid monotonicity, the error taxonomy, redundancy and tau calibration."""

from __future__ import annotations

import random

import pytest

from swarmbly_v0 import HashEmbedder, calibrate_tau, entity_grid_coherence, seam_error_taxonomy
from swarmbly_v0.metrics import ERROR_CLASSES, entity_grid, redundancy, redundancy_between
from swarmbly_v0.schema import Plan, Task
from swarmbly_v0.textutil import split_sentences

# Strong local topic chains: three entities, three consecutive sentences each.
# This is exactly the structure the entity grid is designed to reward, and
# exactly what sentence shuffling destroys.
ORDERED_TEXT = (
    "The Aurora Registry stores every ledger entry it receives. "
    "The Aurora Registry validates each entry before writing it. "
    "The Aurora Registry then emits a signed receipt. "
    "The Vesper Cache holds the most recent receipts in memory. "
    "The Vesper Cache expires each receipt after one hour. "
    "The Vesper Cache reports its hit rate to the operator. "
    "The Orion Auditor reads the expired receipts each night. "
    "The Orion Auditor compares them against the stored ledger. "
    "The Orion Auditor raises a discrepancy whenever the two differ."
)


def _shuffled(text: str, seed: int) -> str:
    sentences = split_sentences(text)
    rng = random.Random(seed)
    rng.shuffle(sentences)
    return " ".join(sentences)


def test_entity_grid_prefers_ordered_text_over_shuffled() -> None:
    """Coherence must drop when the sentence order is destroyed."""
    ordered = entity_grid_coherence(ORDERED_TEXT)
    shuffled_scores = [entity_grid_coherence(_shuffled(ORDERED_TEXT, s)) for s in range(12)]
    mean_shuffled = sum(shuffled_scores) / len(shuffled_scores)

    assert 0.0 <= ordered <= 1.0
    assert ordered > mean_shuffled, (
        f"ordered {ordered:.3f} should beat mean shuffled {mean_shuffled:.3f}"
    )
    assert ordered > max(shuffled_scores) - 1e-9 or ordered > mean_shuffled * 1.2


def test_entity_grid_is_bounded_and_deterministic() -> None:
    first = entity_grid(ORDERED_TEXT)
    second = entity_grid(ORDERED_TEXT)

    assert 0.0 <= first.score <= 1.0
    assert first.score == second.score
    assert first.sentences == len(split_sentences(ORDERED_TEXT))
    assert all(len(roles) == first.sentences for roles in first.grid.values())
    assert all(role in ("S", "O", "X", "-") for roles in first.grid.values() for role in roles)


def test_entity_grid_handles_degenerate_input() -> None:
    assert entity_grid_coherence("") == 0.0
    assert entity_grid_coherence("Hello.") >= 0.0


# --------------------------------------------------------------------------
# Taxonomy
# --------------------------------------------------------------------------


def _plan(n: int = 2) -> Plan:
    return Plan(
        prompt="test",
        tasks=[
            Task(task_id=f"t{i}", instruction=f"part {i}",
                 expected_entities=("Aurora Registry",))
            for i in range(n)
        ],
    )


def test_clean_text_scores_near_one() -> None:
    report = seam_error_taxonomy(ORDERED_TEXT, _plan(3))
    assert report.n_sentences == 9
    assert report.booook_like_score > 0.7
    assert set(report.counts) == set(ERROR_CLASSES)


def test_taxonomy_detects_duplicated_content() -> None:
    duplicated = ORDERED_TEXT + " The Aurora Registry validates each entry before writing it."
    report = seam_error_taxonomy(duplicated, _plan(3))
    assert report.counts["duplicated_content"] >= 1


def test_taxonomy_detects_contradiction() -> None:
    text = (
        "The Aurora Registry always validates the ledger entry before writing. "
        "The Vesper Cache holds receipts for one hour. "
        "The Aurora Registry never validates the ledger entry before writing."
    )
    report = seam_error_taxonomy(text, _plan(2))
    assert report.counts["contradiction"] >= 1


def test_taxonomy_detects_register_and_tense_shift() -> None:
    text = ORDERED_TEXT + " Honestly, the whole thing was kind of a mess and you'll hate it!"
    report = seam_error_taxonomy(text, _plan(3))
    assert report.counts["register_tense_shift"] >= 1


def test_taxonomy_detects_missing_transition_and_dangling_reference() -> None:
    first = "The Aurora Registry stores every ledger entry it receives."
    second = "It follows directly from that result."
    text = f"{first} {second}"
    report = seam_error_taxonomy(text, _plan(2), fragment_sentence_offsets=[0, 1])

    assert report.counts["dangling_reference"] >= 1
    assert report.counts["missing_transition"] >= 1
    assert report.sentence_flags[1] is True


def test_taxonomy_detects_entity_omission() -> None:
    text = "The Vesper Cache holds receipts. The Vesper Cache expires them hourly."
    report = seam_error_taxonomy(text, _plan(2))
    assert report.counts["entity_omission"] >= 1
    assert "Aurora Registry" in report.details["missing_entities"]


def test_taxonomy_detects_inconsistent_naming() -> None:
    text = (
        "The Aurora Registry stores every ledger entry it receives. "
        "The Aurora Registry validates each entry before writing it. "
        "The AURORA REGISTRY then emits a signed receipt for the entry."
    )
    report = seam_error_taxonomy(text, _plan(2))
    assert report.counts["inconsistent_naming"] >= 1


def test_taxonomy_detects_repeated_introduction() -> None:
    text = (
        "In this report we introduce the Aurora Registry and explain its role. "
        "The Aurora Registry validates each entry before writing it. "
        "In this report we introduce the Vesper Cache and explain its role. "
        "The Vesper Cache expires receipts hourly."
    )
    report = seam_error_taxonomy(text, _plan(2), fragment_sentence_offsets=[0, 2])
    assert report.counts["repeated_introduction"] >= 1


def test_booook_like_score_is_a_clean_sentence_fraction() -> None:
    report = seam_error_taxonomy(ORDERED_TEXT, _plan(3))
    clean = sum(1 for flagged in report.sentence_flags if not flagged)
    assert report.booook_like_score == pytest.approx(clean / report.n_sentences)
    assert 0.0 <= report.booook_like_score <= 1.0


def test_empty_text_does_not_crash() -> None:
    report = seam_error_taxonomy("", _plan(2))
    assert report.n_sentences == 0
    assert report.booook_like_score == 0.0


# --------------------------------------------------------------------------
# Redundancy
# --------------------------------------------------------------------------


def test_self_redundancy_rises_with_repetition() -> None:
    unique = redundancy(ORDERED_TEXT)
    repeated = redundancy(ORDERED_TEXT + " " + ORDERED_TEXT)
    assert 0.0 <= unique < repeated <= 1.0


def test_between_fragment_redundancy() -> None:
    a = "The Aurora Registry validates every ledger entry before writing it to disk."
    b = "Coastal fog forms when warm marine air passes over a cold upwelling current."
    assert redundancy_between([a, a]) > redundancy_between([a, b])
    assert redundancy([a, b]) == pytest.approx(redundancy_between([a, b]))


# --------------------------------------------------------------------------
# tau calibration
# --------------------------------------------------------------------------


def _calibration_pairs() -> list[tuple[str, str, bool]]:
    """Continuations within a topic (not seams) vs cross-topic joins (seams)."""
    registry = [
        "The Aurora Registry stores every ledger entry it receives.",
        "The Aurora Registry validates each ledger entry before writing it.",
        "The Aurora Registry emits a signed receipt for each ledger entry.",
        "The Aurora Registry retains each ledger receipt for seven years.",
    ]
    fog = [
        "Coastal fog forms when warm marine air meets a cold upwelling current.",
        "Coastal fog density was logged by lighthouse keepers every four hours.",
        "Coastal fog reduces visibility below one nautical mile near the shore.",
        "Coastal fog dissipates when the marine air warms above the dew point.",
    ]
    pairs: list[tuple[str, str, bool]] = []
    for group in (registry, fog):
        for i in range(len(group) - 1):
            pairs.append((group[i], group[i + 1], False))
    for a in registry:
        for b in fog:
            pairs.append((a, b, True))
    return pairs


def test_calibrate_tau_returns_a_threshold_strictly_inside_zero_one() -> None:
    calibration = calibrate_tau(_calibration_pairs(), HashEmbedder(), beta=0.5)

    assert 0.0 < calibration.tau < 1.0
    assert calibration.beta == 0.5
    assert 0.0 <= calibration.f_beta <= 1.0
    assert calibration.n_pairs == len(_calibration_pairs())
    assert len(calibration.curve) > 10
    assert all(0.0 < point["tau"] < 1.0 for point in calibration.curve)


def test_calibrated_tau_separates_seams_from_continuations() -> None:
    """The fitted threshold must actually do its job on the data it was fitted to."""
    pairs = _calibration_pairs()
    embedder = HashEmbedder()
    calibration = calibrate_tau(pairs, embedder, beta=0.5)

    correct = 0
    for left, right, is_seam in pairs:
        vectors = embedder.embed([left, right])
        similarity = float(vectors[0] @ vectors[1])
        if (similarity < calibration.tau) == is_seam:
            correct += 1
    assert correct / len(pairs) > 0.8


def test_calibration_is_deterministic() -> None:
    pairs = _calibration_pairs()
    assert calibrate_tau(pairs, HashEmbedder()).tau == calibrate_tau(pairs, HashEmbedder()).tau


def test_beta_must_be_asymmetric() -> None:
    """beta >= 1 would drop the precision weighting the design requires."""
    with pytest.raises(ValueError, match="asymmetric"):
        calibrate_tau(_calibration_pairs(), HashEmbedder(), beta=1.0)


def test_empty_pairs_rejected() -> None:
    with pytest.raises(ValueError):
        calibrate_tau([], HashEmbedder())
