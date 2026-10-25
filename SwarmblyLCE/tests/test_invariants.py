"""One test per invariant I1–I8 (SPEC 4.2). If any of these fails, the
implementation is non-conformant regardless of what else passes."""

from __future__ import annotations

import pytest

from swarmbly_lce.capsules import Capsule, make_capsule
from swarmbly_lce.claims import Anchor, Claim, ClaimType, Maturity, Provenance, advance
from swarmbly_lce.errors import CapsuleCode, CapsuleError, InvariantViolation
from swarmbly_lce.policy import LearningPolicy
from swarmbly_lce.social import check_at_most_linear
from swarmbly_lce.training import BatchComposer, Example, ExampleBuilder, Recipe, TestSetRegistry
from swarmbly_lce.wiki import Wiki
from swarmbly_lce.worker import WorkerGuard
from swarmbly_lce.diversity import fst


def test_I1_facts_never_trainable():
    for t in (ClaimType.FACT, ClaimType.USER_CLAIM, ClaimType.OPINION, ClaimType.BELIEF, ClaimType.HYPOTHESIS, ClaimType.EXPERIENCE):
        c = Claim(text="x y z", type=t, anchors=[Anchor("s/a", 0, 1, "h", verified=True)])
        c.maturity = Maturity.CONSOLIDATED
        with pytest.raises(InvariantViolation):
            advance(c, policy_allows_training=True)


def test_I2_worker_base_model():
    class B:
        model, adapter = "base", "lora-of-the-owner"

        def generate(self, p, **k):
            return ""
    with pytest.raises(InvariantViolation):
        WorkerGuard("base").execute(B(), "task")


def test_I3_social_minority_and_distance(wiki):
    new = ExampleBuilder(wiki).from_claims()
    replay = [Example("replay", "o", "r")]
    with pytest.raises(InvariantViolation):
        BatchComposer().compose(new, replay, [], [], Recipe(social_fraction=0.6), wiki)
    far = Example("qa", "p", "r", origin="social", epistemic_distance=2, human_source="n1")
    b = BatchComposer().compose(new, replay, [], [far] * 5, Recipe(social_fraction=0.3), wiki)
    assert all(e.epistemic_distance <= 1 for e in b.examples)


def test_I4_variation_from_people(keypair):
    parent = make_capsule(keypair, kind="term", topics=["t"], statement="s", anchor_kind="user_source", anchor_digest="a",
                          permissions={"cache": True, "redistribute": True, "train": True})
    child = Capsule(origin_node=keypair.public, kind="term", topics=["t"], statement="s2", parent_id=parent.capsule_id,
                    anchor={"kind": "user_source", "digest": "a"}, permissions=dict(parent.permissions))
    with pytest.raises(CapsuleError) as e:
        child.check_trainable()
    assert e.value.code == CapsuleCode.NO_DELTA


def test_I5_prevalence_not_superlinear():
    with pytest.raises(InvariantViolation):
        check_at_most_linear(lambda n: min(1.0, n * n / 100))


def test_I6_fresh_tests_and_replay(wiki):
    reg = TestSetRegistry()
    t = reg.fresh(wiki, 1, [])
    with pytest.raises(InvariantViolation):
        reg.assert_unused(t, 2)
    with pytest.raises(InvariantViolation):
        BatchComposer().compose(ExampleBuilder(wiki).from_claims(), [Example("replay", "o", "r")], [], [], Recipe(replay_fraction=0), wiki)


def test_I7_diversity_is_measurable():
    assert fst([{"a": 3, "b": 1}, {"a": 1, "b": 3}]) > 0


def test_I8_undeclared_never_trains():
    w = Wiki(policy=LearningPolicy.from_mapping({"learning_policy": {}}))
    c = w.add(Claim(text="Escribo así siempre.", type=ClaimType.STYLE, anchors=[Anchor("cualquier/x.md", 0, 5, "h", verified=True)],
                    provenance=Provenance(epistemic_distance=0)))
    c.links.add("other")
    for _ in range(6):
        w.consolidation_cycle()
    assert c.maturity != Maturity.TRAINABLE and not w.trainable()
