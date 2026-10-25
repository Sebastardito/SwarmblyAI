"""Tier routing and privacy classification (specification section 15c)."""

from __future__ import annotations

import pytest

from swarmbly_v0.privacy import (
    GLOBAL,
    LOCAL,
    TRUSTED,
    KDecision,
    PrivacyDecision,
    SwarmRegistry,
    TierViolation,
    UnknownSwarm,
    classify,
    detect_regulated,
    resolve_k,
    routing_metadata,
    select_tier_nodes,
)


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------


def test_plain_prompt_stays_global():
    d = classify("Write a short blog post about the history of shotgun sequencing.")
    assert d.tier == GLOBAL
    assert d.source == "default"
    assert d.entity_classes == ()
    assert d.routable


@pytest.mark.parametrize(
    "prompt,expected",
    [
        ("Summarise the patient's diagnosis from the medical record.", "health"),
        ("My email is seb@example.org, draft a reply.", "personal_identifier"),
        ("Rotate the api_key before Friday.", "credential"),
        ("Draft a response for case no. 44-2019 under attorney-client privilege.", "legal"),
        ("Reconcile the payroll against the IBAN on file.", "financial"),
    ],
)
def test_triage_detects_regulated_classes(prompt, expected):
    assert expected in detect_regulated(prompt)


def test_triage_raises_tier_and_requires_a_swarm():
    prompt = "Summarise the patient's diagnosis from the medical record."
    d = classify(prompt, swarm_id="hospital-a")
    assert d.tier == TRUSTED
    assert d.source == "auto"
    assert "health" in d.entity_classes
    assert d.swarm_id == "hospital-a"

    with pytest.raises(ValueError, match="requires a swarm_id"):
        classify(prompt)


def test_manual_flag_takes_precedence_and_is_never_downgraded():
    # A prompt with no regulated cue at all, manually declared local.
    d = classify("What is the capital of Ecuador?", manual="local")
    assert d.tier == LOCAL
    assert d.source == "manual"
    assert not d.routable

    # Triage would say GLOBAL; the flag says TRUSTED and wins.
    d = classify("Nothing sensitive here.", manual="trusted", swarm_id="lab-1")
    assert d.tier == TRUSTED and d.source == "manual"


def test_manual_flag_is_validated():
    with pytest.raises(ValueError, match="unknown privacy flag"):
        classify("hello", manual="paranoid")


def test_disabling_triage_does_not_disable_the_manual_flag():
    prompt = "Patient diagnosis follows."
    assert classify(prompt, auto_triage=False).tier == GLOBAL
    assert classify(prompt, manual="local", auto_triage=False).tier == LOCAL


# --------------------------------------------------------------------------
# Swarm membership
# --------------------------------------------------------------------------


@pytest.fixture
def registry() -> SwarmRegistry:
    return SwarmRegistry(
        swarm_id="hospital-a",
        operator="Hospital A IT",
        members=frozenset({"nodeA", "nodeB", "nodeC"}),
        loss_rate=0.0,
    )


def test_a_swarm_must_name_its_operator():
    with pytest.raises(ValueError, match="must name its operator"):
        SwarmRegistry(swarm_id="s", operator="", members=frozenset())


def test_whitelist_filters_and_self_declaration_confers_nothing(registry):
    d = classify("x", manual="trusted", swarm_id="hospital-a")
    pool = [
        {"node_id": "nodeA", "mtls": True},
        {"node_id": "stranger", "mtls": True, "swarm_id": "hospital-a"},
        {"node_id": "nodeC", "mtls": True},
    ]
    kept = select_tier_nodes(pool, d, {"hospital-a": registry})
    assert [n["node_id"] for n in kept] == ["nodeA", "nodeC"]


def test_mutual_tls_is_required(registry):
    d = classify("x", manual="trusted", swarm_id="hospital-a")
    pool = [{"node_id": "nodeA", "mtls": False}]
    assert select_tier_nodes(pool, d, {"hospital-a": registry}) == []


def test_unknown_swarm_aborts_instead_of_degrading(registry):
    d = classify("x", manual="trusted", swarm_id="nowhere")
    with pytest.raises(UnknownSwarm):
        select_tier_nodes([{"node_id": "nodeA", "mtls": True}], d, {"hospital-a": registry})


def test_local_tier_selects_nothing_at_all():
    d = classify("x", manual="local")
    with pytest.raises(TierViolation):
        select_tier_nodes([{"node_id": "nodeA", "mtls": True}], d)


def test_global_tier_passes_the_pool_through():
    d = classify("ordinary prompt")
    pool = [{"node_id": "n1"}, {"node_id": "n2"}]
    assert select_tier_nodes(pool, d) == pool


# --------------------------------------------------------------------------
# The k=1 trade-off -- the point of the whole section
# --------------------------------------------------------------------------


def test_trusted_k1_is_permitted_but_forfeits_the_confidence_map(registry):
    d = classify("x", manual="trusted", swarm_id="hospital-a")
    kd = resolve_k(1, d, registry)
    assert kd.k == 1
    assert kd.consensus_available is False
    assert kd.waived_reason == "trusted_swarm_k1"


def test_trusted_k1_is_overridden_when_measured_loss_exceeds_epsilon():
    lossy = SwarmRegistry(
        swarm_id="hospital-a",
        operator="Hospital A IT",
        members=frozenset({"nodeA"}),
        loss_rate=0.05,
    )
    d = classify("x", manual="trusted", swarm_id="hospital-a")
    kd = resolve_k(1, d, lossy, epsilon=0.01)
    assert kd.k == 2
    assert kd.consensus_available is True
    assert kd.waived_reason is None


def test_trusted_swarm_keeps_consensus_when_k_stays_above_one(registry):
    d = classify("x", manual="trusted", swarm_id="hospital-a")
    kd = resolve_k(3, d, registry)
    assert (kd.k, kd.consensus_available, kd.waived_reason) == (3, True, None)


def test_global_k1_also_reports_that_no_map_exists():
    d = classify("ordinary prompt")
    kd = resolve_k(1, d)
    assert kd.k == 1 and kd.consensus_available is False
    assert kd.waived_reason == "k=1_requested"


def test_trusted_decision_without_registry_is_an_error():
    d = classify("x", manual="trusted", swarm_id="hospital-a")
    with pytest.raises(ValueError, match="needs its registry"):
        resolve_k(1, d, None)


def test_requested_k_must_be_at_least_one():
    with pytest.raises(ValueError):
        resolve_k(0, classify("ordinary prompt"))


# --------------------------------------------------------------------------
# Response metadata
# --------------------------------------------------------------------------


def test_routing_metadata_carries_the_waiver(registry):
    d = classify("x", manual="trusted", swarm_id="hospital-a")
    kd = resolve_k(1, d, registry)
    meta = routing_metadata(d, kd, registry)
    assert meta["tier"] == TRUSTED
    assert meta["swarm_operator"] == "Hospital A IT"
    assert meta["mtls"] is True
    assert meta["consensus_available"] is False
    assert meta["consensus_waived_reason"] == "trusted_swarm_k1"
    assert all(isinstance(line, str) and line for line in meta["rationale"])


def test_routing_metadata_on_the_open_mesh():
    d = classify("ordinary prompt")
    meta = routing_metadata(d, resolve_k(3, d))
    assert meta["tier"] == GLOBAL
    assert meta["swarm_id"] is None
    assert meta["mtls"] is False
    assert meta["consensus_waived_reason"] is None


def test_decision_serialises():
    d = classify("Rotate the api_key.", swarm_id="lab-1")
    payload = d.as_dict()
    assert payload["tier"] == TRUSTED
    assert payload["classifier"] == "auto"
    assert "credential" in payload["entity_classes"]
