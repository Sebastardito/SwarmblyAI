"""Tests of the blind benchmark harness (bench/run_bank.py) on a tiny fictitious bank."""

from __future__ import annotations

import importlib.util
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MINI = ROOT / "tests" / "fixtures" / "bench_mini"
_spec = importlib.util.spec_from_file_location("run_bank", ROOT / "bench" / "run_bank.py")
rb = importlib.util.module_from_spec(_spec)
sys.modules["run_bank"] = rb
_spec.loader.exec_module(rb)


def test_detects_bank_and_verifies_seal():
    bank = rb.detect_bank(MINI)
    assert bank.kind == "v2"
    seal = rb.verify_seal(bank)
    assert seal["ok"] and seal["archivos_ok"] == 4 and not seal["fallos"]


def test_broken_seal_is_detected(tmp_path):
    copy = tmp_path / "bank"
    shutil.copytree(MINI, copy)
    target = copy / "01_MATERIALES" / "corpus_reservado" / "nota_2025.md"
    target.write_text(target.read_text(encoding="utf-8") + "\nedit\n", encoding="utf-8")
    seal = rb.verify_seal(rb.detect_bank(copy))
    assert not seal["ok"]
    assert seal["fallos"][0]["archivo"].endswith("nota_2025.md")


def test_parses_only_id_question_and_documents():
    cases = rb.parse_cases(MINI / "02_CASOS_RESERVADOS" / "S2_S3_reservados.md")
    assert [c.case_id for c in cases] == ["S2-01", "S3-01"]
    assert cases[0].question == "¿Desde cuándo soy coordinadora de calidad de datos?"
    assert cases[0].documents == ["cv_ana_perez.md"]
    assert "agosto" not in cases[0].question          # the key is never part of the question


def test_public_snapshot_is_served_not_loaded_as_a_source():
    bank = rb.detect_bank(MINI)
    case = rb.parse_cases(bank.cases_file)[1]
    user, public = rb.case_documents(bank, case)
    assert {p.name for p in user} == {"cv_ana_perez.md", "nota_2025.md"}
    assert [p.name for p in public] == ["Registro_Orestias_ficticia_2024.md"]


def test_payload_classification():
    corpus = (MINI / "01_MATERIALES" / "corpus_reservado" / "cv_ana_perez.md").read_text(encoding="utf-8")
    passages = rb.shingles(corpus)
    persona = ["Ana", "Pérez", "Rojas"]
    assert rb.classify_payload("Orestias ficticia estado", passages, persona) == "entidad_publica"
    assert rb.classify_payload("Ana Pérez Rojas AcmeLabs", passages, persona) == "nombre_personal"
    leak = "Coordinadora de Calidad de Datos en AcmeLabs, desde agosto de 2022"
    assert rb.classify_payload(leak, passages, persona) == "pasaje"


def test_proxy_refuses_and_records():
    proxy = rb.EgressProxy()
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy.url}))
        with pytest.raises(urllib.error.HTTPError):
            opener.open("http://example.org/search?q=Ana+P%C3%A9rez", timeout=5)
        events = proxy.log.drain()
        assert events and events[0]["destino"] == "example.org"
        assert "q=Ana" in events[0]["consulta"]
    finally:
        proxy.close()


def test_registry_answers_with_snapshot_and_records_query():
    registry = rb.PublicRegistry()
    try:
        registry.fixtures = [MINI / "01_MATERIALES" / "fixtures_publicos" / "Registro_Orestias_ficticia_2024.md"]
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(registry.url + "/search?q=Orestias+ficticia&format=json", timeout=5) as resp:
            body = resp.read().decode("utf-8")
        assert "En Peligro" in body
        events = registry.log.drain()
        assert events[0]["q"] == "Orestias ficticia" and events[0]["resultados"] == 1
    finally:
        registry.close()


def test_receipt_counts_sends_and_blocked_attempts():
    passages = rb.shingles((MINI / "01_MATERIALES" / "corpus_reservado" / "nota_2025.md").read_text(encoding="utf-8"))
    receipt = rb.build_receipt(
        "S3-01", "respuesta", {"executed": "local"},
        [{"q": "Orestias ficticia", "bytes": 17}],
        [{"metodo": "CONNECT", "destino": "www.wikidata.org", "puerto": 443}],
        passages, ["Ana", "Pérez"])
    assert receipt["schema"] == "swarmbly.privacy_receipt/1.0"
    assert receipt["ruta"] == "local+consulta_publica"
    assert receipt["bytes_salientes"] == 17 and receipt["pasajes_enviados"] == 0
    assert receipt["intentos_bloqueados"][0]["salio"] is False


def test_v1_bank_uses_listed_fixtures_and_serves_the_public_one(tmp_path):
    root = tmp_path / "v1"
    (root / "fixtures").mkdir(parents=True)
    (root / "reserved").mkdir()
    (root / "fixtures" / "01_cv_ana.md").write_text("# CV\n", encoding="utf-8")
    (root / "fixtures" / "02_nota.md").write_text("# Nota\n", encoding="utf-8")
    (root / "fixtures" / "07_registro_publico_simulado.md").write_text("# Registro\n", encoding="utf-8")
    (root / "reserved" / "runner_pack.md").write_text(
        "```text\nID:            S3-02\nPregunta:      Compara.\nDocumentos:    F02, F07\n```\n",
        encoding="utf-8")
    lines = [f"{rb.sha256_file(p)}  {p.relative_to(root).as_posix()}"
             for p in sorted(root.rglob("*.md"))]
    (root / "SEALED_MANIFEST.sha256").write_text("Swarmbly bank v1\n" + "\n".join(lines) + "\n",
                                                 encoding="utf-8")
    bank = rb.detect_bank(root)
    assert bank.kind == "v1" and rb.verify_seal(bank)["ok"]
    case = rb.parse_cases(bank.cases_file)[0]
    user, public = rb.case_documents(bank, case)
    assert [p.name for p in user] == ["02_nota.md"]
    assert [p.name for p in public] == ["07_registro_publico_simulado.md"]


def test_v1_receipt_rows_and_regeneration(tmp_path):
    rows = rb.build_receipt_v1(
        "S3-02", [{"q": "Orestias ficticia estado", "resultados": 1, "t": "2026-11-07T00:00:00Z"}],
        [{"metodo": "CONNECT", "destino": "www.wikidata.org", "puerto": 443}],
        ["07_registro_publico_simulado.md"])
    assert rows["events"] == 2
    first, second = rows["rows"]
    assert first["destination_class"] == "simulated-public-registry"
    assert first["payload_terms"] == ["Orestias", "ficticia", "estado"]
    assert first["response_fixture"] == "F07" and len(first["payload_sha256"]) == 64
    assert second["approved"] is False and second["destination_class"].startswith("blocked-external")
    assert rb.build_receipt_v1("S2-01", [], [], [])["rows"] == []
    run = tmp_path / "run"
    (run / "casos").mkdir(parents=True)
    (run / "logs").mkdir()
    (run / "casos" / "S2-01.json").write_text('{"caso": "S2-01", "fixtures_publicos": []}', encoding="utf-8")
    (run / "logs" / "red.jsonl").write_text("", encoding="utf-8")
    assert rb.main(["--regenerate-receipts", str(run)]) == 0
    assert (run / "casos" / "S2-01_recibo_v1.json").is_file()


def test_app_receipt_is_compared_on_queries_only():
    app = {"envios": [{"tipo": "entidad_publica", "valor": "Orestias ficticia"},
                      {"tipo": "pregunta", "valor": "(pregunta)", "destino": "127.0.0.1"}],
           "pasajes_enviados": 0}
    observed = {"envios": [{"valor": "Orestias ficticia"}], "pasajes_enviados": 0}
    out = rb.compare_app_receipt(app, observed)
    assert out["coincide"] and out["consultas_app"] == ["Orestias ficticia"]
    observed["envios"].append({"valor": "Orestias ficticia estado"})
    assert not rb.compare_app_receipt(app, observed)["coincide"]
