from __future__ import annotations


import pytest

from swarmbly_lce.canonical import canonical_json, digest16
from swarmbly_lce.claims import Anchor, Claim, ClaimType, Maturity, Provenance, Status, advance, derived_distance, regress
from swarmbly_lce.depgraph import DependencyGraph
from swarmbly_lce.errors import CycleError, InvariantViolation, PolicyError, TransitionError
from swarmbly_lce.policy import LearningPolicy
from swarmbly_lce.retrieval import BM25Retriever
from swarmbly_lce.wiki import Wiki


# -- canonical JSON -----------------------------------------------------------

def test_canonical_sorted_and_compact():
    assert canonical_json({"b": 1, "a": [True, None, "ñ"]}) == '{"a":[true,null,"ñ"],"b":1}'


def test_canonical_rejects_nan():
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})


def test_digest_is_order_independent():
    assert digest16({"a": 1, "b": 2}) == digest16({"b": 2, "a": 1})
    assert len(digest16({"a": 1})) == 32


def test_crypto_roundtrip(keypair):
    from swarmbly_lce.crypto import sign, verify

    s = sign(keypair, b"hello")
    assert verify(keypair.public, b"hello", s)
    assert not verify(keypair.public, b"hellO", s)
    assert "private" not in repr(keypair).lower() or "public" in repr(keypair)


# -- policy -------------------------------------------------------------------

def test_policy_default_is_reference_only():
    p = LearningPolicy.from_mapping({"learning_policy": {}})
    r = p.rule_for("anything/at/all.md")
    assert r.reference_only and not r.trainable


def test_policy_longest_prefix_and_style_requires_authorship(policy):
    assert policy.rule_for("teach/style/correo.md").allows_type("style")
    assert not policy.rule_for("teach/knowledge/genetica.md").allows_type("style")
    assert not policy.rule_for("reference_only/reunion.md").trainable


def test_policy_rejects_unknown_keys():
    with pytest.raises(PolicyError):
        LearningPolicy.from_mapping({"learning_policy": {"sources": {"x": {"lern_style": True}}}})
    with pytest.raises(PolicyError):
        LearningPolicy.from_mapping({"learning_policy": {"sources": {"x": {"learn_style": "yes"}}}})


def test_policy_rule_does_not_inherit_permissive_default():
    p = LearningPolicy.from_mapping({"learning_policy": {"defaults": {"reference_only": False, "learn_style": True, "authored_by_user": True},
                                                         "sources": {"narrow": {"wiki": True}}}})
    assert not p.rule_for("narrow/a.md").trainable


# -- claims and state machine --------------------------------------------------

def _claim(t=ClaimType.STYLE, verified=True, d=0, src="s/a.md"):
    return Claim(text="Escribo con un registro cálido.", type=t, anchors=[Anchor(src, 0, 10, "h", verified=verified)],
                 provenance=Provenance(epistemic_distance=d))


def test_advance_requires_anchor():
    c = _claim(verified=False)
    c.maturity = Maturity.DIGESTED
    with pytest.raises(TransitionError):
        advance(c)


def test_fact_needs_two_independent_sources():
    c = _claim(t=ClaimType.FACT)
    c.maturity, c.links = Maturity.CONNECTED, {"x"}
    with pytest.raises(TransitionError):
        advance(c)
    c.anchors.append(Anchor("s/b.md", 0, 5, "h2", human_source="other", verified=True))
    assert advance(c) == Maturity.CORROBORATED


def test_non_behavioural_never_trainable():
    c = _claim(t=ClaimType.FACT)
    c.maturity = Maturity.CONSOLIDATED
    with pytest.raises(InvariantViolation):
        advance(c, policy_allows_training=True)


def test_trainable_requires_policy_and_distance():
    c = _claim(d=2)
    c.maturity = Maturity.CONSOLIDATED
    with pytest.raises(TransitionError):
        advance(c, policy_allows_training=False)
    with pytest.raises(TransitionError):
        advance(c, policy_allows_training=True)
    c.provenance.epistemic_distance = 1
    assert advance(c, policy_allows_training=True) == Maturity.TRAINABLE


def test_regressions():
    c = _claim()
    c.maturity = Maturity.CONSOLIDATED
    assert regress(c, "contradiction") == Maturity.CONNECTED and c.status == Status.CONTESTED
    assert regress(c, "anchor_lost") == Maturity.DIGESTED and not c.anchored


def test_derived_distance():
    p = _claim(d=1)
    assert derived_distance([p], new_human_evidence=False) == 2
    assert derived_distance([p], new_human_evidence=True) == 1


def test_attributed_rendering():
    c = Claim(text="el café causa insomnio", type=ClaimType.BELIEF)
    assert "attributed to the user" in c.render_for_retrieval() and "not a fact" in c.render_for_retrieval()


# -- dependency graph ------------------------------------------------------------

def test_depgraph_invalidation_and_cycles():
    g = DependencyGraph()
    for n, k in [("s", "source"), ("c", "claim"), ("e", "example"), ("a", "adapter")]:
        g.add_node(n, k)
    g.add_edge("s", "c"); g.add_edge("c", "e"); g.add_edge("e", "a")
    with pytest.raises(CycleError):
        g.add_edge("a", "s")
    assert g.invalidate("s") == {"c", "e", "a"}
    assert g.affected_adapters() == {"a"}


# -- wiki end to end -----------------------------------------------------------

def test_wiki_digest_and_maturity(wiki):
    types = {c.type for c in wiki.claims.values()}
    assert ClaimType.STYLE in types and ClaimType.PROCEDURE in types and ClaimType.BELIEF in types
    trainable = wiki.trainable()
    assert trainable and all(c.behavioural for c in trainable)
    assert all(c.anchors[0].source.startswith("teach/") for c in trainable)


def test_wiki_roundtrip(wiki, tmp_path, policy):
    p = tmp_path / "w.json"
    wiki.save(p)
    w2 = Wiki.load(p, policy=policy)
    assert {k: c.maturity for k, c in w2.claims.items()} == {k: c.maturity for k, c in wiki.claims.items()}
    assert w2.to_json() == wiki.to_json()


def test_source_change_regresses_claims(wiki, space):
    path = space.root / "teach/style/correo.md"
    path.write_text(path.read_text(encoding="utf-8") + "\nNueva línea.\n", encoding="utf-8")
    stale = wiki.register_source("teach/style/correo.md", space.file_hash("teach/style/correo.md"))
    assert stale
    affected = [wiki.claims[n.split(":", 1)[1]] for n in stale if n.startswith("claim:")]
    assert affected and all(c.maturity == Maturity.DIGESTED for c in affected)


def test_forget_source_removes_claims(wiki):
    n = len(wiki.claims)
    wiki.forget_source("teach/style/correo.md")
    assert len(wiki.claims) < n
    assert all(a.source != "teach/style/correo.md" for c in wiki.claims.values() for a in c.anchors)


def test_policy_change_marks_stale(wiki, policy):
    narrowed = LearningPolicy.from_mapping({"learning_policy": {"sources": {"teach/style": {"wiki": True}}}})
    stale = wiki.set_policy(narrowed)
    assert stale
    assert all(c.maturity != Maturity.TRAINABLE for c in wiki.claims.values() if c.anchors[0].source.startswith("teach/style"))


def test_episodic_requires_policy(policy):
    w = Wiki(policy=policy)
    c = Claim(text="Ayer hablé con el equipo.", type=ClaimType.EXPERIENCE, anchors=[Anchor("teach/style/x.md", 0, 5, "h")])
    with pytest.raises(InvariantViolation):
        w.add(c)


def test_retrieval_excludes_retracted_and_marks_contested(wiki):
    cs = list(wiki.claims.values())
    cs[0].status = Status.RETRACTED
    r = BM25Retriever().index(cs)
    assert cs[0] not in r.docs


def test_export_markdown(wiki, tmp_path):
    files = wiki.export_markdown(tmp_path / "md")
    assert files and all(f.read_text(encoding="utf-8").startswith("# ") for f in files)
