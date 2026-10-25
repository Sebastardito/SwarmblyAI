from __future__ import annotations

import pytest

from swarmbly_lce.claims import Anchor, Claim, ClaimType, Provenance
from swarmbly_lce.errors import InvariantViolation
from swarmbly_lce.policy import LearningPolicy
from swarmbly_lce.projection import HeuristicClassifier, Lane, Projector
from swarmbly_lce.training import (AdapterManager, BatchComposer, Example, ExampleBuilder, Gate, GateScores, MockEvaluator,
                                   MockTrainer, Recipe, TestSetRegistry, eligible)
from swarmbly_lce.wiki import Wiki
from swarmbly_lce.worker import WorkerGuard


# -- projection ------------------------------------------------------------------

def test_projection_uses_only_behavioural_claims(wiki):
    res = Projector().project("escribe un correo sobre fragmentación", list(wiki.claims.values()))
    g = res.projection.gamma_fields()
    assert set(g) <= {"audience", "register", "lexicon", "entities", "style_seed"}
    text = res.projection.as_text().lower()
    assert "café" not in text and "laboratorio" not in text  # beliefs and experiences never projected
    assert g.get("lexicon", {}).get("fragmentación semántica") == "preferred"


def test_projection_byte_cap(wiki):
    from swarmbly_lce.params import Params
    res = Projector(params=Params(projection_max_bytes=40)).project("correo", list(wiki.claims.values()))
    assert res.projection.size_bytes() <= 40


def test_double_classification_only_raises():
    clf = HeuristicClassifier()
    assert clf.classify("explica F_ST") == Lane.PUBLIC
    assert clf.classify("mi diagnóstico médico") == Lane.SENSITIVE
    p = Projector(entities={"contacto": "seb@example.com"})
    res = p.project("explica F_ST", [])
    assert res.lane_initial == Lane.PUBLIC and res.lane_final >= Lane.SANITISABLE


# -- worker ------------------------------------------------------------------------

class _B:
    def __init__(self, model, adapter=None):
        self.model, self.adapter = model, adapter

    def generate(self, prompt, **kw):
        return "ok"


def test_worker_serves_base_model_only():
    g = WorkerGuard(declared_model="qwen2.5:3b")
    assert g.execute(_B("qwen2.5:3b"), "task") == "ok"
    with pytest.raises(InvariantViolation):
        g.execute(_B("qwen2.5:3b", adapter="personal-lora"), "task")
    with pytest.raises(InvariantViolation):
        g.execute(_B("llama3.2:1b"), "task")
    assert g.counters["tasks"] == 1


# -- training ------------------------------------------------------------------------

def _wiki_with_style(n=20):
    pol = LearningPolicy.from_mapping({"learning_policy": {"sources": {"s": {"authored_by_user": True, "learn_style": True}}}})
    w = Wiki(policy=pol)
    for i in range(n):
        w.add(Claim(text=f"Uso la construcción {i} en informes.", type=ClaimType.STYLE,
                    anchors=[Anchor("s/f.md", 0, 5, "h", verified=True)], provenance=Provenance(epistemic_distance=0)))
    ids = list(w.claims)
    for a, b in zip(ids, ids[1:]):
        w.link(a, b)
    for _ in range(4):
        w.consolidation_cycle()
    return w


def _pools():
    return ([Example("replay", f"o{i}", f"r{i}") for i in range(10)], [Example("general", f"g{i}", f"x{i}") for i in range(10)])


def test_eligibility_rules():
    w = _wiki_with_style()
    ex = ExampleBuilder(w).from_claims()
    assert ex and all(eligible(e, w) for e in ex)
    bad = Example("style", "p", "r", claim_ids=ex[0].claim_ids, generator="adapter:old")
    assert not eligible(bad, w)
    far = Example("qa", "p", "r", claim_ids=ex[0].claim_ids, epistemic_distance=2)
    assert not eligible(far, w)


def test_batch_requires_replay_and_caps_social():
    w = _wiki_with_style()
    new = ExampleBuilder(w).from_claims()
    replay, general = _pools()
    with pytest.raises(InvariantViolation):
        BatchComposer().compose(new, replay, general, [], Recipe(replay_fraction=0.0), w)
    with pytest.raises(InvariantViolation):
        BatchComposer().compose(new, replay, general, [], Recipe(social_fraction=0.5), w)
    with pytest.raises(InvariantViolation):
        BatchComposer().compose(new, [], general, [], Recipe(), w)
    b = BatchComposer().compose(new, replay, general, [], Recipe(), w)
    assert b.replay_share > 0 and b.social_share == 0


def test_gate_conditions():
    from swarmbly_lce.training import Adapter
    a = Adapter("a", "base", Recipe(), (), "base", 1)
    assert Gate().choose([(a, GateScores(12, 1, 0.9))]) is a
    assert Gate().choose([(a, GateScores(12, 3, 0.9))]) is None
    assert Gate().choose([(a, GateScores(12, 1, 0.5))]) is None


def test_fresh_test_sets_never_reused():
    w = _wiki_with_style()
    reg = TestSetRegistry()
    t1 = reg.fresh(w, 1, [])
    t2 = reg.fresh(w, 2, [])
    assert t1.test_id != t2.test_id
    with pytest.raises(InvariantViolation):
        reg.assert_unused(t1, 2)


def test_adapter_manager_generations_and_forgetting():
    w = _wiki_with_style()
    new = ExampleBuilder(w).from_claims()
    replay, general = _pools()
    mgr = AdapterManager(w, "base", MockTrainer(seed=1), MockEvaluator(reliability=0.9, seed=1))
    winner = None
    for g in range(5):
        winner = mgr.run_generation(new, replay, general, [Recipe(rank=8, lr=1e-4, seed=g * 10 + i) for i in range(3)]) or winner
    assert mgr.current is not None and mgr.current.init_from == "base"
    assert len({h["test_id"] for h in mgr.history}) == len(mgr.history)
    # forget a source → adapter affected → retired (SPEC 7.8)
    w.forget_source("s/f.md")
    assert mgr.current_affected()
    assert mgr.enforce_forgetting() and mgr.current is None


def test_correction_pair():
    e = ExampleBuilder.correction("texto antes", "texto después")
    assert e.kind == "preference_pair" and e.rejected == "texto antes"
