"""Pruebas de las reparaciones de la revisión (E1–E4, N3, abstención).

Cada defecto que la revisión encontró en los datos tiene aquí una prueba que
falla si el defecto vuelve. Verificar con ``grep`` no es una prueba: una
edición perdida (como la del 10 de octubre) la rompe esta suite.
"""

from __future__ import annotations

import ast
import json
import shutil
from pathlib import Path

import pytest

from swarmbly_lce.backends import MockBackend
from swarmbly_lce.claims import Anchor, Claim, ClaimType, Maturity
from swarmbly_lce.policy import LearningPolicy
from swarmbly_lce.wiki import Wiki

from lce_validation import instruments as I
from lce_validation import run_r13 as R
from lce_validation.experiments import build_wiki
from lce_validation.provenance import check_digests, expected_digests

ROOT = Path(__file__).resolve().parents[1]
USERS = ROOT / "lce_validation" / "fixtures" / "bench_users"


def _wiki(claims: list[tuple[str, str, Maturity]]) -> Wiki:
    w = Wiki(policy=LearningPolicy())
    for text, src, mat in claims:
        c = Claim(text=text, type=ClaimType.FACT, anchors=[Anchor(src, 0, 5, "h")])
        c = w.add(c)
        c.maturity = mat
    return w


# --- E2: vigencia al derecho y una claim por hecho, en A3 y A4 -------------

def test_wiki_context_puts_the_newest_dated_claim_first():
    w = _wiki([
        ("El F_ST entre Barú y Fábrega fue 0.036 en el análisis.", "old.md", Maturity.CONNECTED),
        ("El F_ST entre Barú y Fábrega corregido es 0.041 en el análisis.", "new.md", Maturity.CONNECTED),
    ])
    ctx = R.wiki_context(w, "¿Cuál es el F_ST entre Barú y Fábrega?",
                         {"old.md": 202601, "new.md": 202610})
    assert "0.041" in ctx
    # una claim por hecho: la antigua queda sombreada por la vigente
    assert "0.036" not in ctx


def test_wiki_context_ranks_by_score_when_dates_tie():
    w = _wiki([
        ("Umbral de cobertura del ochenta por ciento.", "a.md", Maturity.CONNECTED),
        ("La cobertura de pruebas exige un umbral de cobertura del 80 por ciento antes de fusionar cambios de cobertura.", "a.md", Maturity.CONNECTED),
    ])
    ranked_first = R.wiki_context(w, "umbral de cobertura de pruebas", {"a.md": 0}).splitlines()[0]
    assert "80 por ciento" in ranked_first


def test_a3_and_a4_share_the_same_context_function():
    src = (ROOT / "lce_validation" / "run_r13.py").read_text(encoding="utf-8")
    assert src.count("wiki_context(wiki, q[\"q\"], src_dates)") == 2
    assert "sorted(\n        hits," in src and src.count("reverse=True") == 1


# --- E1: el resumen no sobrescribe digestores -----------------------------

def _cell(arm, q, r, ok, d=None):
    c = {"user": "u", "arm": arm, "responder": r, "q": {"q": q}, "ok": ok, "tokens": 10}
    if d:
        c["digester"] = d
    return c


def test_summarize_keeps_every_digester_and_pairs_by_question():
    cells = [_cell("A2", "q1", "r1", True)]
    cells += [_cell("A3", "q1", "r1", ok, d) for d, ok in (("d1", True), ("d2", False), ("d3", False))]
    s = R.summarize(cells, ["d1", "d2", "d3"], B=200)
    assert s["a3_by_digester"] == {"d1": 1.0, "d2": 0.0, "d3": 0.0}
    assert s["mean_by_arm"]["A3"] == pytest.approx(1 / 3, abs=1e-3)
    # emparejado: (1-1)+(0-1)+(0-1) / 3
    assert s["a3_minus_a2_by_question"] == pytest.approx(-2 / 3, abs=1e-3)


def test_stored_r13_summary_is_reproduced_by_summarize():
    d = json.loads((ROOT / "results" / "bench_r13" / "results.json").read_text(encoding="utf-8"))
    s = R.summarize(d["cells"], d["digesters"])
    for k, v in s.items():
        assert d["summary"][k] == v, k


# --- E3: la fuente olvidada no se digiere; forget_source la elimina ------

def _corpus(tmp_path: Path) -> Path:
    dst = tmp_path / "andres"
    shutil.copytree(USERS / "andres", dst)
    return dst


def test_build_wiki_excludes_named_sources(tmp_path):
    base = _corpus(tmp_path)
    wiki, _ = build_wiki(base, base / "policy.json", MockBackend(), anchor_mode="quote",
                         suffixes=frozenset({".md"}), exclude_names=frozenset({"borrada.md"}))
    assert wiki.claims, "la digestión simulada debe producir claims"
    assert not any("borrada" in a.source for c in wiki.claims.values() for a in c.anchors)


def test_forget_source_equals_never_ingested(tmp_path):
    base = _corpus(tmp_path)
    kw = dict(anchor_mode="quote", suffixes=frozenset({".md"}))
    full, _ = build_wiki(base, base / "policy.json", MockBackend(), **kw)
    never, _ = build_wiki(base, base / "policy.json", MockBackend(), exclude_names=frozenset({"borrada.md"}), **kw)
    src = "teach/knowledge/borrada.md"
    assert any(a.source == src for c in full.claims.values() for a in c.anchors)
    full.forget_source(src)
    assert not any(a.source == src for c in full.claims.values() for a in c.anchors)
    assert set(full.claims) == set(never.claims)


# --- E4: ninguna digestión de benchmark ingiere archivos que no son fuentes

def test_every_benchmark_build_wiki_call_restricts_sources_to_md():
    files = sorted((ROOT / "lce_validation").glob("bench_*.py")) + [ROOT / "lce_validation" / "run_r13.py"]
    calls = 0
    for f in files:
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", "")) == "build_wiki":
                calls += 1
                assert any(k.arg == "suffixes" for k in node.keywords), f"{f.name}:{node.lineno}"
    assert calls >= 4


# --- N3: --confirm verifica digests de verdad ----------------------------

def test_check_digests_refuses_an_empty_manifest():
    assert check_digests({"models": {"m": "abc"}}, {}) == ["manifiesto de digests vacío o ausente"]


def test_check_digests_flags_mismatch_and_unknown_models():
    man = expected_digests()
    assert "qwen2.5:3b" in man
    ok = {"models": {"qwen2.5:3b": man["qwen2.5:3b"]}}
    assert check_digests(ok) == []
    bad = {"models": {"qwen2.5:3b": "0" * 64, "otro:1b": "f" * 64}}
    probs = check_digests(bad)
    assert any("qwen2.5:3b" in p for p in probs) and any("otro:1b" in p for p in probs)


# --- abstención: números repetidos de la pregunta no son contenido -------

@pytest.mark.parametrize("answer,question,want", [
    ("No tengo información sobre el piloto de 2024.", "¿Qué anotó el piloto de 2024?", "abstain"),
    ("El piloto de 2024 anotó 63 por ciento.", "¿Qué anotó el piloto de 2024?", "content"),
    ("No está en mis fuentes, pero el borrador hablaba de un tamizaje amplio.", "", "content"),
])
def test_abstention_classifier(answer, question, want):
    assert I._classify_abstention(answer, question) == want
