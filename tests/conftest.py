from __future__ import annotations

from pathlib import Path

import pytest

from swarmbly_lce.anchors import AnchorVerifier
from swarmbly_lce.backends import MockBackend
from swarmbly_lce.digest import Digester
from swarmbly_lce.policy import LearningPolicy
from swarmbly_lce.sources import SourceSpace
from swarmbly_lce.wiki import Wiki

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "lce_validation" / "fixtures"


@pytest.fixture
def policy() -> LearningPolicy:
    return LearningPolicy.load(FIX / "policy.json")


@pytest.fixture
def space(tmp_path: Path) -> SourceSpace:
    import shutil

    dst = tmp_path / "corpus"
    shutil.copytree(FIX / "corpus", dst)
    return SourceSpace(dst)


@pytest.fixture
def wiki(space: SourceSpace, policy: LearningPolicy) -> Wiki:
    w = Wiki(policy=policy)
    Digester(MockBackend(), space, AnchorVerifier(space)).digest_all(w)
    by_source: dict[str, list[str]] = {}
    for c in w.claims.values():
        by_source.setdefault(c.anchors[0].source, []).append(c.claim_id)
    for ids in by_source.values():
        for a, b in zip(ids, ids[1:]):
            w.link(a, b)
    for _ in range(4):
        w.consolidation_cycle()
    return w


@pytest.fixture
def keypair():
    pytest.importorskip("cryptography")
    from swarmbly_lce.crypto import keypair_from_seed

    return keypair_from_seed(bytes(range(32)))


@pytest.fixture
def keypair2():
    pytest.importorskip("cryptography")
    from swarmbly_lce.crypto import keypair_from_seed

    return keypair_from_seed(bytes(range(1, 33)))
