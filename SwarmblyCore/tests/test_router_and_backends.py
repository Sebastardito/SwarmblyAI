"""Router asymmetry and the MockBackend's drift contract."""

from __future__ import annotations

import pytest

from swarmbly_v0 import HashEmbedder, MockBackend, evaluate_router, is_decomposable, load_prompts
from swarmbly_v0.backends import OpenAICompatBackend, get_backend, get_embedder
from swarmbly_v0.router import DEFAULT_THRESHOLD, extract_features

PARALLEL = (
    "Extract structured fields from each of the 40 invoice records in the export. "
    "For each record, extract the customer name, the invoice total, and the payment status. "
    "Return one bullet per record. The records are mutually independent and may be "
    "processed separately, so do not reconcile totals across records."
)
SEQUENTIAL = (
    "Solve the problem step by step. First compute the weekly demand from the series. "
    "Then use that result to derive the reorder point given a three week lead time. "
    "Then substitute the reorder point into the safety-stock equation and calculate the "
    "holding cost. Each step depends on the numeric output of the previous step."
)


def test_threshold_is_asymmetric_by_default() -> None:
    """False-positive fragmentation is worse, so the bar sits above 0.5."""
    assert DEFAULT_THRESHOLD > 0.5


def test_router_separates_parallel_from_sequential_prompts() -> None:
    parallel = is_decomposable(PARALLEL)
    sequential = is_decomposable(SEQUENTIAL)

    assert parallel.decomposable is True
    assert sequential.decomposable is False
    assert parallel.score > sequential.score


def test_raising_the_threshold_can_only_reduce_fragmentation() -> None:
    """Monotonicity: a stricter router never fragments something a looser one refused."""
    prompts = [spec.text for spec in load_prompts()]
    loose = {p for p in prompts if is_decomposable(p, 0.30).decomposable}
    strict = {p for p in prompts if is_decomposable(p, 0.85).decomposable}
    assert strict <= loose


def test_router_beats_chance_on_the_labelled_corpus() -> None:
    prompts = load_prompts()
    evaluation = evaluate_router([(p.text, p.expected_decomposable) for p in prompts])

    assert evaluation.total == len(prompts)
    assert evaluation.accuracy >= 0.75
    assert evaluation.false_positive_rate <= 0.25


def test_invalid_threshold_rejected() -> None:
    for bad in (0.0, 1.0, -0.5, 2.0):
        with pytest.raises(ValueError):
            is_decomposable(PARALLEL, bad)


def test_features_are_bounded_and_explainable() -> None:
    features = extract_features(SEQUENTIAL)
    assert features["bias"] == 1.0
    assert all(0.0 <= v <= 1.0 for v in features.values())
    assert features["sequential_cues"] > 0.0
    assert is_decomposable(SEQUENTIAL).rationale


# --------------------------------------------------------------------------
# MockBackend
# --------------------------------------------------------------------------


def test_mock_backend_is_deterministic() -> None:
    a, b = MockBackend(seed=3), MockBackend(seed=3)
    prompt = "[TASK t0]\nDescribe the ledger receipt lifecycle."
    assert a.generate(prompt) == b.generate(prompt)
    assert a.generate(prompt) == a.generate(prompt)


def test_mock_backend_seed_changes_output() -> None:
    prompt = "[TASK t0]\nDescribe the ledger receipt lifecycle."
    assert MockBackend(seed=1).generate(prompt) != MockBackend(seed=2).generate(prompt)


def test_drift_probability_decreases_with_context() -> None:
    """This monotonicity is the entire premise of the harness."""
    backend = MockBackend(seed=0)
    for channel in backend.drift_base:
        probabilities = [backend.drift_probability(channel, c)
                         for c in (0.0, 0.25, 0.5, 0.75, 1.0)]
        assert probabilities == sorted(probabilities, reverse=True)
        assert probabilities[-1] == pytest.approx(backend.floor)
        assert probabilities[0] > probabilities[-1]


def test_context_starved_packets_drift_more_than_context_rich_ones() -> None:
    """Averaged over prompts, more context must yield cleaner fragments."""
    from swarmbly_v0.metrics import seam_error_taxonomy

    backend = MockBackend(seed=0)
    task = "[TASK t0]\nDescribe how the ledger validates and stores each receipt."
    context = (
        "[GLOBAL CONTRACT]\nsession: abc\nobjective: describe the ledger lifecycle\n"
        "register: formal\noutput_format: report\ntarget_length_tokens: 120\n"
        "glossary:\n- Aurora Registry: canonical name; use this exact surface form.\n"
        "- Vesper Cache: canonical name; use this exact surface form.\n"
    ) * 3

    bare_scores, rich_scores = [], []
    for variant in range(12):
        bare = backend.generate(task, variant=variant)
        rich = backend.generate(context + task, variant=variant)
        bare_scores.append(seam_error_taxonomy(bare).booook_like_score)
        rich_scores.append(seam_error_taxonomy(rich).booook_like_score)

    assert sum(rich_scores) / len(rich_scores) > sum(bare_scores) / len(bare_scores)


def test_monolithic_prompts_get_full_context_strength() -> None:
    """No [TASK] marker means the baseline is scored at maximum context."""
    spec = MockBackend._parse_packet("Just answer this question about ledgers.")
    assert spec["monolithic"] is True
    assert spec["context_strength"] == 1.0


def test_bridge_prompts_produce_one_transition_sentence() -> None:
    from swarmbly_v0.textutil import split_sentences

    backend = MockBackend(seed=0)
    bridge = backend.generate("ledger receipts stored here\n[BRIDGE]\ncoastal fog density logs")
    assert len(split_sentences(bridge)) == 1


def test_hash_embedder_produces_unit_vectors() -> None:
    import numpy as np

    vectors = HashEmbedder(dim=64).embed(["ledger receipt entry", "coastal fog density"])
    assert vectors.shape == (2, 64)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)


def test_hash_embedder_is_process_stable() -> None:
    """Hashing must not depend on PYTHONHASHSEED."""
    import numpy as np

    assert np.allclose(HashEmbedder().embed(["ledger"]), HashEmbedder().embed(["ledger"]))


def test_embedder_similarity_tracks_topic() -> None:
    embedder = HashEmbedder()
    vectors = embedder.embed([
        "the ledger receipt records the validated entry",
        "the ledger entry receipt was validated and recorded",
        "coastal fog reduces visibility near the shoreline",
    ])
    assert float(vectors[0] @ vectors[1]) > float(vectors[0] @ vectors[2])


def test_factories() -> None:
    assert isinstance(get_backend("mock"), MockBackend)
    assert isinstance(get_embedder("hash"), HashEmbedder)
    with pytest.raises(ValueError):
        get_backend("nope")
    with pytest.raises(ValueError):
        get_embedder("nope")


def test_openai_backend_constructs_without_network() -> None:
    """Constructing must never require a reachable server or optional packages."""
    backend = OpenAICompatBackend(base_url="http://127.0.0.1:9/v1", model="test")
    assert backend.transport
    # Embeddings degrade to hashing rather than raising when the server is absent.
    vectors = backend.embed(["ledger receipt"])
    assert vectors.shape[0] == 1
