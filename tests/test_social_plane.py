from __future__ import annotations

import json

import pytest

from swarmbly_lce.affinity import AffinityCache, Candidate, select_with_affinity
from swarmbly_lce.capsules import Capsule, CapsuleRequest, CapsuleStore, DeltaEvidence, make_capsule, make_descendant, paraphrase_distance
from swarmbly_lce.diversity import (CanarySet, conformist_step, error_agreement_given_both_wrong, fst, generations_to_loss,
                                    homogeneity, wright_fst, wright_nm)
from swarmbly_lce.errors import CapsuleCode, CapsuleError, InvariantViolation
from swarmbly_lce.persistence import Holder, annual_loss, place_copies, replicas_for, target_replicas, window_loss_q
from swarmbly_lce.plural import ReplicaAnswer, build_plural
from swarmbly_lce.profile import CognitiveBlock
from swarmbly_lce.social import SocialCache, check_at_most_linear, identity_violation

import numpy as np


def _cap(kp, **kw):
    base = dict(kind="term", topics=["linguistics", "es-EC"], statement="En el español de Ecuador, 'chuta' es una interjección informal.",
                anchor_kind="user_source", anchor_digest="ab" * 16, permissions={"cache": True, "redistribute": True, "train": True})
    base.update(kw)
    return make_capsule(kp, **base)


# -- capsules -------------------------------------------------------------------

def test_capsule_sign_verify_roundtrip(keypair):
    c = _cap(keypair)
    c2 = Capsule.from_dict(json.loads(c.to_json()))
    c2.validate(); c2.verify_signature()
    assert c2.capsule_id == c.capsule_id and len(c.capsule_id) == 32


def test_capsule_tamper_detected(keypair):
    c = _cap(keypair)
    d = json.loads(c.to_json()); d["statement"] = "otra cosa"
    t = Capsule.from_dict(d)
    with pytest.raises(CapsuleError) as e:
        t.validate()
    assert e.value.code == CapsuleCode.BAD_SIGNATURE


def test_capsule_wrong_signer(keypair, keypair2):
    c = Capsule(origin_node=keypair.public, kind="term", topics=["x"], statement="s", anchor={"kind": "user_source", "digest": "a"})
    with pytest.raises(CapsuleError):
        c.sign_with(keypair2)


def test_capsule_bounds(keypair):
    with pytest.raises(CapsuleError) as e:
        _cap(keypair, statement="x" * 9000)
    assert e.value.code == CapsuleCode.TOO_LARGE
    with pytest.raises(CapsuleError):
        _cap(keypair, topics=[f"t{i}" for i in range(17)])


def test_v01_capsule_is_local_cache_only(keypair):
    c = Capsule(origin_node=keypair.public, kind="term", topics=["x"], statement="s", v="0.1",
                permissions={"cache": True, "redistribute": True, "train": True}).sign_with(keypair)
    c2 = Capsule.from_dict(json.loads(c.to_json()))
    assert c2.epistemic_distance == 2
    with pytest.raises(CapsuleError) as e:
        c2.check_redistributable()
    assert e.value.code == CapsuleCode.DISTANCE


def test_descendant_requires_delta(keypair, keypair2):
    parent = _cap(keypair)
    child = make_descendant(parent, keypair2, statement="'Chuta' también expresa asombro leve.",
                            delta=DeltaEvidence("native_speaker_note", "cd" * 16))
    child.verify_signature()
    assert child.parent_id == parent.capsule_id and child.epistemic_distance == 1 and child.revision == 1
    child.check_redistributable(); child.check_trainable()
    para = Capsule(origin_node=keypair2.public, kind="term", topics=["x"], statement="reformulada", parent_id=parent.capsule_id,
                   anchor={"kind": "user_source", "digest": "a"}, permissions={"cache": True, "redistribute": True, "train": True})
    with pytest.raises(CapsuleError) as e:
        para.check_redistributable()
    assert e.value.code == CapsuleCode.NO_DELTA
    assert paraphrase_distance(parent) == 2


def test_permissions_respected(keypair):
    c = _cap(keypair, permissions={"cache": True, "redistribute": False, "train": False})
    with pytest.raises(CapsuleError) as e:
        c.check_trainable()
    assert e.value.code == CapsuleCode.FORBIDDEN


def test_store_serve_pull_only(keypair):
    a = CapsuleStore("A"); a.add_origin(_cap(keypair))
    resp = a.serve(CapsuleRequest(topics=["es-EC"], request_id="r1"))
    assert resp.error is None and len(resp.capsules) == 1
    b = CapsuleStore("B")
    assert b.receive(resp.capsules[0])
    assert b.serve(CapsuleRequest(topics=["es-EC"])).capsules  # redistribute=True
    bad = b.serve(CapsuleRequest(topics=[]))
    assert bad.error == CapsuleCode.TOO_LARGE
    assert b.serve(CapsuleRequest(topics=["nada"])).error == CapsuleCode.NOT_FOUND


def test_no_cache_permission_not_stored(keypair):
    c = _cap(keypair, permissions={"cache": False, "redistribute": False, "train": False})
    b = CapsuleStore("B")
    assert not b.receive(c) and not b.capsules


def test_profile_block():
    CognitiveBlock("pull", ["term"], ["genomics"], ["es", "en-CA"]).validate()
    with pytest.raises(CapsuleError):
        CognitiveBlock("pull", domains=["religion catolica"]).validate()
    with pytest.raises(CapsuleError):
        CognitiveBlock("pull", languages=["Spanish!!"]).validate()
    with pytest.raises(CapsuleError):
        CognitiveBlock("pull", domains=[f"d{i}" for i in range(17)]).validate()


# -- social and affinity ----------------------------------------------------------

def test_prevalence_is_label_not_adoption():
    sc = SocialCache()
    for i in range(10):
        p = sc.observe("'chuta' se usa en Ecuador como interjección", node=f"n{i}", family=f"f{i % 3}")
    assert p.independent_nodes == 10 and "10 nodes" in p.prevalence_label
    assert not sc.decide(p.pattern_id, 0.0)  # no utility observed: popularity alone does not adopt
    sc.observe(p.statement, "n0", "f0", utility=0.9)
    assert sc.decide(p.pattern_id, 0.99)


def test_superlinear_rule_rejected():
    check_at_most_linear(lambda n: min(1.0, 0.03 * n))
    check_at_most_linear(lambda n: 1 - 0.9 ** n)  # concave
    with pytest.raises(InvariantViolation):
        check_at_most_linear(lambda n: min(1.0, (n / 10) ** 2))
    with pytest.raises(InvariantViolation):
        check_at_most_linear(lambda n: 1.0 if n >= 5 else 0.0)


def test_identity_guard():
    assert identity_violation("Soy ecuatoriano y digo chuta")
    assert not identity_violation("En Ecuador se usa 'chuta'")
    with pytest.raises(InvariantViolation):
        SocialCache().observe("I am Ecuadorian", "n", "f")


def test_affinity_decays_normalises_and_caps():
    a = AffinityCache()
    a.update("p1", "gen", 1.0, now=0.0); a.update("p2", "gen", 0.5, now=0.0)
    n = a.normalised("gen", now=0.0)
    assert abs(sum(n.values()) - 1.0) < 1e-9
    assert a._decayed(("p1", "gen"), now=60.0) < a._decayed(("p1", "gen"), now=0.0)
    assert a.adjust(1.0, "p1", "gen", 0.0) <= 1.2 + 1e-9
    with pytest.raises(ValueError):
        a.adjust(1.0, "p1", "gen", 0.0, beta=0.5)


def test_selection_keeps_family_diversity_and_explores():
    a = AffinityCache()
    for _ in range(20):
        a.update("hot", "d", 1.0, now=0.0)
    cands = [Candidate("hot", "qwen", 1.0), Candidate("hot2", "qwen", 0.99), Candidate("l1", "llama", 0.8),
             Candidate("g1", "gemma", 0.7), Candidate("cold", "phi", 0.1)]
    chosen = select_with_affinity(cands, 3, "d", a, now=0.0)
    fams = [c.family for c in chosen]
    assert len(set(fams[:2])) == 2  # family diversity before affinity
    assert len(chosen) == 3 and chosen[-1].peer not in {"hot"}


# -- persistence -------------------------------------------------------------------

def test_replica_math_matches_whitepaper():
    q = window_loss_q(91, 7)
    assert abs(q - 0.074) < 1e-3
    assert replicas_for(1e-3, q) == 3 and replicas_for(1e-4, q) == 4
    assert abs(annual_loss(2, q) - 0.25) < 0.01 and abs(annual_loss(3, q) - 0.021) < 0.002


def test_target_replicas_eligibility(keypair):
    c = _cap(keypair, preserve=True)
    assert target_replicas(c, estimated_holders=100) == 3
    assert target_replicas(c, estimated_holders=1) == 4
    c.preserve = False
    assert target_replicas(c, 1) == 0


def test_place_copies_distinct_operators():
    hs = [Holder("a", "op1"), Holder("b", "op1"), Holder("c", "op2"), Holder("d", "op3", load=10**6)]
    chosen = place_copies(3, hs)
    assert len({h.operator for h in chosen}) == len(chosen) == 2


# -- plural and diversity -------------------------------------------------------------

def test_plural_minimum_support():
    ans = [ReplicaAnswer(1, "A", "qwen"), ReplicaAnswer(1, "A", "llama"), ReplicaAnswer(1, "B", "gemma"),
           ReplicaAnswer(2, "X", "qwen"), ReplicaAnswer(2, "Y", "llama"), ReplicaAnswer(2, "Y", "gemma"), ReplicaAnswer(2, "X", "phi")]
    out = build_plural(ans)
    assert out["note"] == "agreement_is_not_truth"
    units = {u["unit"]: u for u in out["units"]}
    assert 1 not in units  # single-family minority is hidden
    assert len(units[2]["positions"]) == 2 and abs(sum(p["share"] for p in units[2]["positions"]) - 1.0) < 1e-9


def test_fst_and_wright():
    assert fst([{"a": 1.0}, {"b": 1.0}]) == pytest.approx(1.0)
    assert fst([{"a": 0.5, "b": 0.5}, {"a": 0.5, "b": 0.5}]) == pytest.approx(0.0)
    assert wright_fst(1.0) == pytest.approx(0.2)
    assert wright_nm(0.2) == pytest.approx(1.0)


def test_conformist_dynamics_numbers():
    assert generations_to_loss(0.2, 0.2) == 18
    assert generations_to_loss(0.2, 0.1) == 37
    assert conformist_step(0.5, 0.3) == pytest.approx(0.5)


def test_homogeneity_and_error_agreement():
    v = np.eye(3)
    assert homogeneity(v) == pytest.approx(0.0)
    assert error_agreement_given_both_wrong(["x", "y", "g"], ["x", "z", "g"], ["g", "g", "g"]) == pytest.approx(0.5)
    assert error_agreement_given_both_wrong(["g"], ["g"], ["g"]) is None


def test_canary_guard(tmp_path):
    from swarmbly_lce.diversity import CanaryItem
    cs = CanarySet([CanaryItem("es-EC", "chuta", ("sorpresa",))])
    with pytest.raises(ValueError):
        cs.guard_training(["¡chuta, se cayó el servidor!".replace("¡", "")])
    cs.guard_training(["nada que ver"])
    assert cs.tail_mass({"chuta": "expresa sorpresa"}) == 1.0
