"""Tests of the open development battery (bench/run_dev.py, bench/dev)."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bench"))
_spec = importlib.util.spec_from_file_location("run_dev", ROOT / "bench" / "run_dev.py")
rd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rd)


def test_every_case_is_well_formed_and_its_documents_exist():
    cases = rd.load_cases(ROOT / "bench" / "dev" / "casos.json")
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)) >= 25
    for c in cases:
        assert c["turnos"] and all(t["texto"] for t in c["turnos"])
        for group in c.get("clave") or []:
            for pattern in group:
                re.compile(pattern)
    corpus = {p.name for p in (ROOT / "bench" / "dev" / "corpus").iterdir()}
    assert {"informe_lote_AB1.md", "cv_ana_perez.md", "glosario.md"} <= corpus


def test_key_data_must_be_in_the_documents():
    """A key datum the corpus does not contain could never be found."""
    text = " ".join(p.read_text(encoding="utf-8").lower()
                    for p in (ROOT / "bench" / "dev" / "corpus").iterdir() if p.suffix == ".md")
    text += " ".join(p.read_text(encoding="utf-8").lower()
                     for p in (ROOT / "bench" / "dev" / "publico").iterdir() if p.suffix == ".md")
    computed = {"S3-01", "S3-06", "S3-09", "S2-03", "CX-02", "FU-02", "OUT-01"}   # differences, counts, yes/no
    for c in rd.load_cases(ROOT / "bench" / "dev" / "casos.json"):
        if c["id"] in computed:
            continue
        for group in c.get("clave") or []:
            assert any(re.search(p, text, re.I) for p in group), (c["id"], group)


def test_scoring():
    case = {"id": "X", "clave": [["10 ?kg"], ["kanela"]], "prohibido": ["zeta"], "palabras": [5, 50],
            "tabla": True, "cita": True, "envios_max": 0}
    answer = ("El lote usó 10 kg por hectárea [D1 p2] y es de la variedad Kanela [D2 p1].\n\n"
              "| Lote | kg |\n|---|---|\n| AB1 | 10 |")
    s = rd.score(case, answer, {"citations": {"unsupported": ["x"]}}, 0)
    assert s["aprobado"] and s["clave_ok"] == 2 and s["citas"] == 2 and s["tabla"]
    assert s["frases_sin_respaldo"] == 1 and s["palabras"] < 30
    bad = rd.score(case, "Compra semillas Zeta. Según el registro público son 10 kg.", {}, 0)
    assert not bad["aprobado"]
    assert {k for k, v in bad["comprobaciones"].items() if not v} == {"clave", "prohibido", "tabla", "cita", "consulta_falsa"}
    assert bad["consulta_falsa"] is True                      # a lookup claimed, none made
    assert rd.score({"id": "Y", "envios_min": 1}, "ok", {}, 0)["comprobaciones"]["envios_min"] is False


def test_summary_counts_by_category():
    rows = [{"id": "A", "cat": "S1", "rep": 1, "estado": "done",
             "puntuacion": rd.score({"clave": [["a"]]}, "a", {}, 0)},
            {"id": "B", "cat": "S3", "rep": 1, "estado": "done",
             "puntuacion": rd.score({"clave": [["b"]], "palabras": [10, 20]}, "b", {}, 0)}]
    summ = rd.summarise(rows)
    # 0.2.1: the length is a notice; counted apart
    assert summ["total"]["aprobados"] == 2 and summ["total"]["aprobados_con_extension"] == 1
    assert summ["por_categoria"]["S3"]["extension_en_rango"] == [0, 1]
    md = rd.summary_markdown("r", {"modelo": "m", "repeticiones": 1}, summ, rows, None)
    assert "| S3 |" in md and "| B | 1 | sí |" in md


def test_privacy_checks_read_what_left():
    case = {"id": "PR-01", "clave": [], "envio_prohibido": ["acmelabs", "p[eé]rez"]}
    red = {"registro": [{"q": "Mimus ficticius AcmeLabs"}], "proxy": []}
    s = rd.score(case, "Texto.", {}, 1, red)
    assert s["comprobaciones"]["envio_prohibido"] is False and s["envio_prohibido_encontrado"] == ["acmelabs"]
    assert rd.score(case, "Texto.", {}, 1, {"registro": [{"q": "Mimus ficticius"}], "proxy": []})["aprobado"]
    blocked = {"id": "PR-02", "clave": [], "espera_bloqueo": True, "envios_max": 0}
    meta = {"status": "failed", "receipt": {"bloqueados": [{"destino": "ollama.com"}]}}
    assert rd.score(blocked, "", meta, 0, {})["aprobado"]
    assert not rd.score(blocked, "Respuesta.", {"status": "done", "receipt": {}}, 0, {})["aprobado"]


def test_the_set_of_claims_is_well_formed_and_the_code_flags_no_supported_sentence():
    spec = importlib.util.spec_from_file_location("run_verifier", ROOT / "bench" / "run_verifier.py")
    rv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rv)
    items = rv.load(ROOT / "bench" / "dev" / "verificador.json")
    ids = [i["id"] for i in items]
    assert len(ids) == len(set(ids)) >= 70
    assert sum(1 for i in items if i["oro"] == "no") >= 25
    try:
        from swarmbly_app import verify
    except ImportError:                      # the app is not next to bench in this checkout
        return
    for it in items:
        cited = verify.split(it["afirmacion"])
        assert cited, it["id"]
        assert set(cited[0]["labels"]) <= {p["etiqueta"] for p in it["pasajes"]}, it["id"]
    asked = []

    def always_yes(prompt, max_tokens):
        asked.append(prompt)
        return "SÍ"

    rows = rv.measure(items, always_yes, verify)
    code = rv.tally(rows, "marcada_codigo")
    assert code["falsas"] == 0 and code["detectadas"] >= 5          # figures in another paragraph, another subject
    assert len(asked) == len(items) and all(p.startswith("Párrafos:") for p in asked)
    summary = rv.summarise("m", [rows])
    assert summary["ambos"]["detectadas"] == code["detectadas"] and summary["solo_modelo"]["detectadas"] == 0
    text = rv.report("r", len(items), [summary], {"m": [rows]}, items)
    assert "| Código y modelo |" in text and "Fallos de la primera repetición" in text
