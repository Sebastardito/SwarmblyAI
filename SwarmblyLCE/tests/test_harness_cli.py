from __future__ import annotations

import json
from pathlib import Path

import pytest

from lce_validation import experiments as E
from lce_validation import instruments as I
from lce_validation.run_all import main as run_all
from swarmbly_lce.backends import MockBackend
from swarmbly_lce.cli import main as cli

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", sorted(I.ALL))
def test_instrument_passes(name):
    r = I.ALL[name](seed=0)
    assert r["passed"], r


def test_instruments_seed_robust():
    for seed in (1, 2):
        for name in ("conformity", "persistence", "collapse", "anchor_gate", "error_agreement"):
            assert I.ALL[name](seed=seed)["passed"], (name, seed)


def test_run_all_writes_reports(tmp_path):
    assert run_all(["--out", str(tmp_path)]) == 0
    res = json.loads((tmp_path / "results.json").read_text())
    assert res["header"]["backend_kind"] == "simulation" and res["header"]["evidence"] is False
    assert "NOT EVIDENCE" in (tmp_path / "REPORT.md").read_text()


def test_run_all_default_output_outside_guarded_dirs():
    """run_all must not dirty the directories run_real requires clean (it would silently demote a confirmatory run)."""
    from lce_validation.run_all import DEFAULT_OUT
    from lce_validation.run_real import GUARDED
    rel = DEFAULT_OUT.resolve().relative_to(ROOT)
    assert rel.parts[0] not in GUARDED, rel


def test_c2_prediction_holds_on_mock():
    fams = [MockBackend(family=f) for f in ("a", "b", "c")]
    r = E.c2_projection(fams, MockBackend(), bootstrap_B=500)
    assert r["homogeneity"]["mean"]["projection"] < r["homogeneity"]["mean"]["baseline"] < 1.0
    assert r["error_agreement"]["delta"] == 0.0
    assert r["lexicon"]["adherence_with"] > r["lexicon"]["adherence_without"]


def test_cli_end_to_end(tmp_path, monkeypatch):
    import shutil
    shutil.copytree(E.FIXTURES / "corpus", tmp_path / "corpus")
    home = tmp_path / ".lce"
    assert cli(["init", str(tmp_path)]) == 0
    shutil.copy(E.FIXTURES / "policy.json", tmp_path / ".lce" / "policy.json")
    assert cli(["--home", str(home), "ingest", "--sources", str(tmp_path / "corpus")]) == 0
    for _ in range(4):
        assert cli(["--home", str(home), "cycle"]) == 0
    assert cli(["--home", str(home), "status"]) == 0
    assert cli(["--home", str(home), "project", "escribe un correo"]) == 0
    assert cli(["--home", str(home), "forget", "teach/style/correo.md"]) == 0
    assert cli(["--home", str(home), "export-md", str(tmp_path / "md")]) == 0
    assert cli(["replicas", "--eps", "1e-3"]) == 0


def test_cli_capsules(tmp_path):
    pytest.importorskip("cryptography")
    key = tmp_path / "key.json"
    cap = tmp_path / "cap.json"
    assert cli(["capsule", "keygen", str(key)]) == 0
    assert cli(["capsule", "make", str(cap), "--key", str(key), "--topics", "es-EC", "--statement", "chuta es una interjección",
                "--anchor-text", "¡chuta!", "--cache", "--redistribute"]) == 0
    assert cli(["capsule", "verify", str(cap)]) == 0


def test_docs_have_status_and_no_section_sign():
    for p in (ROOT / "docs").glob("*.md"):
        text = p.read_text(encoding="utf-8")
        if p.name == "STATUS.md":
            continue
        assert text.startswith("---\nstatus:"), p.name
        assert "§" not in text, p.name
