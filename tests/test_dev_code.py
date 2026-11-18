"""Tests of the open recipe 5 battery and its deterministic scorer."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bench"))
_spec = importlib.util.spec_from_file_location("run_dev", ROOT / "bench" / "run_dev.py")
rd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rd)

BATTERY = ROOT / "bench" / "dev_code"
CASES = {c["id"]: c for c in rd.load_cases(BATTERY / "casos.json")}


def _proposal(script: str = "import pandas as pd\nprint(1)\n") -> dict:
    digest = hashlib.sha256(script.encode("utf-8")).hexdigest()
    return {"script": script, "script_sha256": digest, "proposal_id": "p1",
            "files": [{"name": "colmenas.csv", "rel": "colmenas.csv"}]}


def _meta(proposal: dict, *, trapped: str | None = None,
          destination: str = "local", corrections: int = 0,
          files: list[dict] | None = None) -> dict:
    digest = proposal["script_sha256"]
    return {
        "status": "done",
        "model_destination": {"clase": destination, "host": "127.0.0.1"},
        "code": {"script_sha256": digest, "trapped": trapped, "approved_by": "user",
                 "corrections": corrections, "files_in": ["colmenas.csv"]},
        "code_run": {"run_id": "a" * 32, "files": files or [],
                     "platform_guard": "rlimit+watchdog", "stdout_chars": 10},
        "receipt": {"recipe": "code", "envios": [], "tools": [{"spec_id": "sandbox/python",
                                                               "clase": "local"}],
                    "code": {"script_sha256": digest, "trapped": trapped}},
    }


def _score(case_id: str, stdout: str, *, meta: dict | None = None,
           proposal: dict | None = None, out_files: list[dict] | None = None,
           sends: int = 0) -> dict:
    proposal = proposal or _proposal()
    meta = meta if meta is not None else _meta(proposal)
    return rd.score_code(CASES[case_id], proposal, meta, stdout, "",
                         out_files or [], sends, {"registro": [], "proxy": []})


# --------------------------------------------------------------------------- cases


def test_the_battery_is_well_formed():
    cases = list(CASES.values())
    ids = [c["id"] for c in cases]
    assert len(cases) == 12 and len(ids) == len(set(ids))
    assert sum(1 for c in cases if c.get("cancel")) == 1
    assert {c["id"] for c in cases if c.get("expect_trap")} == {"NW-01", "WR-01"}
    assert {c["id"] for c in cases if c.get("refusal")} == {"NA-01", "NW-01", "WR-01"}
    corpus = BATTERY / "corpus"
    for case in cases:
        assert case["question"].strip() and case["files"]
        for name in case["files"]:
            if case.get("aliases"):
                assert (corpus / case["aliases"][name]).is_file()
            else:
                assert (corpus / name).is_file()
        for spec in case.get("expected_numbers") or []:
            assert isinstance(spec["value"], (int, float))
            assert float(spec["tolerance"]) >= 0
    xl = CASES["XL-01"]
    assert xl["aliases"] == {"produccion.csv": "produccion.xlsx"}
    assert xl["files"] == ["produccion.csv"]
    assert (corpus / "produccion.xlsx").is_file()
    with zipfile.ZipFile(corpus / "produccion.xlsx") as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        assert "Cosecha" in workbook
        assert "xl/worksheets/sheet1.xml" in archive.namelist()


def test_expected_values_recomputed_from_the_csv():
    weights: dict[str, list[float]] = {}
    dates: list[str] = []
    with (BATTERY / "corpus" / "colmenas.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            weights.setdefault(row["apiario"], []).append(float(row["peso_kg"]))
            dates.append(row["fecha_revision"])
    means = {a: sum(v) / len(v) for a, v in weights.items()}
    sums = {a: sum(v) for a, v in weights.items()}
    assert [s["value"] for s in CASES["AG-01"]["expected_numbers"]] == [
        round(means[a], 4) for a in ("Los Aromos", "El Lingue", "Las Nieves")]
    assert [s["value"] for s in CASES["AG-02"]["expected_numbers"]] == [
        round(sums[a], 4) for a in ("Los Aromos", "El Lingue", "Las Nieves")] + [8, 8, 8]
    assert CASES["FL-01"]["expected_numbers"][0]["value"] == sum(
        1 for w in weights["Los Aromos"] if w >= 30)
    assert CASES["FL-01"]["expected_numbers"][1]["value"] == 62.5
    assert CASES["MX-01"]["expected_numbers"][0]["value"] == max(
        w for values in weights.values() for w in values)
    assert CASES["DT-01"]["expected_numbers"][0]["value"] == sum(
        1 for d in dates if d.startswith("2026-03"))
    with (BATTERY / "corpus" / "correcciones.csv").open(encoding="utf-8", newline="") as fh:
        corrections = {row["colmena"]: float(row["peso_kg"]) for row in csv.DictReader(fh)}
    total = 0.0
    with (BATTERY / "corpus" / "colmenas.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            total += corrections.get(row["colmena"], float(row["peso_kg"]))
    assert CASES["CR-01"]["expected_numbers"][0]["value"] == 633.2
    assert abs(total - 633.2) < 1e-9


# --------------------------------------------------------------------------- scoring


def test_a_perfect_run_passes_every_check():
    score = _score("AG-02", "Los Aromos: 247.9 (8)\nEl Lingue: 205.3 (8)\nLas Nieves: 171.0 (8)\n")
    assert score["aprobado"] is True
    assert score["numeros_ok"] == score["numeros_total"] == 6
    assert all(score["comprobaciones"].values())


def test_a_wrong_value_is_caught():
    score = _score("AG-02", "Los Aromos: 247.9 (8)\nEl Lingue: 205.3 (8)\nLas Nieves: 200.0 (8)\n")
    assert score["aprobado"] is False
    assert score["numeros_ok"] == 5
    assert score["comprobaciones"]["numeros"] is False


def test_a_missing_value_is_caught():
    score = _score("AG-02", "Los Aromos: 247.9 (8)\nEl Lingue: 205.3 (8)\n")
    assert score["aprobado"] is False
    assert score["numeros_ok"] == 5


def test_expected_no_basis_answer_needs_a_refusal_and_no_invented_temperature():
    refusal = "No se puede calcular la temperatura media porque no hay datos de temperatura.\n"
    score = _score("NA-01", refusal)
    assert score["aprobado"] is True
    invented = _score("NA-01", "La temperatura media fue de 32.5 grados C.\n")
    assert invented["aprobado"] is False
    assert invented["prohibido_encontrado"]


def test_an_expected_trap_or_a_refusal_is_accepted_but_an_unexpected_trap_is_not():
    proposal = _proposal()
    network = _meta(proposal, trapped="error")
    score = _score("NW-01", "No se pudo descargar: no hay red.\n", meta=network, proposal=proposal)
    assert score["aprobado"] is True and score["comprobaciones"]["trampa"] is True
    refusal = _score("NW-01", "Sin red: no se descargaron precios.\n",
                     meta=_meta(proposal), proposal=proposal)
    assert refusal["aprobado"] is True
    normal = _score("AG-02", "Los Aromos: 247.9 (8)\nEl Lingue: 205.3 (8)\nLas Nieves: 171.0 (8)\n",
                    meta=_meta(proposal, trapped="error"), proposal=proposal)
    assert normal["aprobado"] is False and normal["comprobaciones"]["trampa"] is False


def test_a_send_greater_than_zero_is_caught():
    proposal = _proposal()
    meta = _meta(proposal)
    meta["receipt"]["envios"] = [{"destino": "https://example.test"}]
    score = _score("AG-02", "Los Aromos: 247.9 (8)\nEl Lingue: 205.3 (8)\nLas Nieves: 171.0 (8)\n",
                   meta=meta, proposal=proposal, sends=1)
    assert score["aprobado"] is False
    assert score["comprobaciones"]["sin_envios"] is False


def test_a_third_party_destination_and_a_hash_mismatch_are_caught():
    proposal = _proposal()
    meta = _meta(proposal, destination="terceros")
    score = _score("AG-02", "Los Aromos: 247.9 (8)\nEl Lingue: 205.3 (8)\nLas Nieves: 171.0 (8)\n",
                   meta=meta, proposal=proposal)
    assert score["comprobaciones"]["sin_terceros"] is False

    proposal = _proposal("print('one')")
    meta = _meta(proposal)
    meta["code"]["script_sha256"] = "0" * 64
    meta["receipt"]["code"]["script_sha256"] = "0" * 64
    score = _score("AG-02", "Los Aromos: 247.9 (8)\nEl Lingue: 205.3 (8)\nLas Nieves: 171.0 (8)\n",
                   meta=meta, proposal=proposal)
    assert score["comprobaciones"]["script"] is False
    assert score["comprobaciones"]["recibo"] is False


def test_the_correction_case_accepts_the_value_or_an_explicit_note():
    value = _score("CR-01", "633.2\n")
    assert value["aprobado"] is True and value["numeros_ok"] == 1
    note = _score("CR-01", "No usé las correcciones; el total es 624.2.\n")
    assert note["aprobado"] is True and note["alternativa"] is True
    silent = _score("CR-01", "624.2\n")
    assert silent["aprobado"] is False


def test_an_unsafe_output_name_is_caught():
    proposal = _proposal()
    score = _score("AG-02", "Los Aromos: 247.9 (8)\nEl Lingue: 205.3 (8)\nLas Nieves: 171.0 (8)\n",
                   meta=_meta(proposal, files=[{"name": "../escape.txt"}]),
                   proposal=proposal)
    assert score["comprobaciones"]["archivos"] is False


# --------------------------------------------------------------------------- cancel


def test_cancel_must_not_run_and_must_refuse_approval():
    proposal = _proposal()
    cancelled = {"cancelled": True, "proposal_id": "p1"}
    good = rd.score_code_cancel(CASES["CN-01"], proposal, cancelled, 400, [], 0,
                                {"registro": [], "proxy": []})
    assert good["aprobado"] is True
    ran = rd.score_code_cancel(CASES["CN-01"], proposal, cancelled, 400,
                               [{"meta": {"code_run": {"run_id": "a" * 32}}}], 0)
    assert ran["aprobado"] is False and ran["comprobaciones"]["sin_ejecucion"] is False
    accepted = rd.score_code_cancel(CASES["CN-01"], proposal, cancelled, 200, [], 0)
    assert accepted["comprobaciones"]["aprobacion_rechazada"] is False
    not_cancelled = rd.score_code_cancel(CASES["CN-01"], proposal, {}, 400, [], 0)
    assert not_cancelled["comprobaciones"]["cancelado"] is False


# --------------------------------------------------------------------------- summary/rescore


def test_the_code_summary_counts_checks_numbers_and_cases():
    proposal = _proposal()
    perfect = _score("AG-02", "Los Aromos: 247.9 (8)\nEl Lingue: 205.3 (8)\nLas Nieves: 171.0 (8)\n")
    wrong = _score("AG-02", "Los Aromos: 247.9 (8)\nEl Lingue: 205.3 (8)\nLas Nieves: 200.0 (8)\n")
    rows = [
        {"id": "AG-02", "cat": "AG", "rep": 1, "estado": "done", "turnos": [{"latencia_s": 1.0}],
         "puntuacion": perfect},
        {"id": "AG-02", "cat": "AG", "rep": 2, "estado": "done", "turnos": [{"latencia_s": 1.0}],
         "puntuacion": wrong},
    ]
    summ = rd.summarise_code(rows)
    assert summ["total"]["n"] == 2 and summ["total"]["aprobados"] == 1
    assert summ["total"]["numeros"] == [11, 12]
    assert summ["por_caso"]["AG-02"]["aprobados"] == 1
    assert summ["total"]["por_comprobacion"]["script"] == [2, 2]
    md = rd.code_summary_markdown("run", {"modelo": "qwen2.5:7b", "repeticiones": 2,
                                          "versiones": {"swarmbly-app": "0.7.0"}},
                                  summ, rows, None)
    assert "Batería abierta de código" in md and "| AG-02 |" in md
    assert "batería abierta, no una medición sellada" in md


def test_rescore_reuses_the_stored_code_answer(tmp_path):
    battery = tmp_path / "battery"
    (battery / "ejecuciones" / "run1" / "casos").mkdir(parents=True)
    (battery / "casos.json").write_text(
        (BATTERY / "casos.json").read_text(encoding="utf-8"), encoding="utf-8")
    proposal = _proposal()
    sheet = {"name": "result.txt", "text": "", "sha256": "", "error": ""}
    row = {"id": "AG-02", "cat": "AG", "rep": 1, "estado": "done",
           "proposal": proposal, "meta": _meta(proposal), "stdout":
           "Los Aromos: 247.9 (8)\nEl Lingue: 205.3 (8)\nLas Nieves: 171.0 (8)\n",
           "stderr": "", "out_files": [sheet], "messages": [],
           "red": {"registro": [], "proxy": []},
           "turnos": [{"latencia_s": 1.0}],
           "puntuacion": _score("AG-02", "Los Aromos: 247.9 (8)\nEl Lingue: 205.3 (8)\n"
                                 "Las Nieves: 171.0 (8)\n")}
    (battery / "ejecuciones" / "run1" / "casos" / "AG-02_r1.json").write_text(
        json.dumps(row, ensure_ascii=False), encoding="utf-8")
    (battery / "ejecuciones" / "run1" / "resumen.json").write_text(json.dumps({
        "info": {"run_id": "run1", "modelo": "qwen2.5:7b", "repeticiones": 1,
                 "versiones": {"swarmbly-app": "0.7.0"}},
        "resumen": {}}), encoding="utf-8")

    code = rd.main(["--rescore", str(battery / "ejecuciones" / "run1")])
    assert code == 0
    summary = json.loads((battery / "ejecuciones" / "run1" / "resumen.json")
                         .read_text(encoding="utf-8"))["resumen"]
    assert summary["total"]["aprobados"] == 1
    assert summary["total"]["numeros"] == [6, 6]
    assert (battery / "ejecuciones" / "run1" / "resumen.md").is_file()
