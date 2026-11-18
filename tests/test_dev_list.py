"""Tests of the open recipe 4 battery and its deterministic scorer."""

from __future__ import annotations

import importlib.util
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bench"))
_spec = importlib.util.spec_from_file_location("run_dev", ROOT / "bench" / "run_dev.py")
rd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rd)

BATTERY = ROOT / "bench" / "dev_list"
CASES = {c["id"]: c for c in rd.load_cases(BATTERY / "casos.json")}


def _output(case_id: str, values: list[str], statuses: list[str] | None = None):
    """A canned App answer that follows the case's expected cells."""
    case = CASES[case_id]
    statuses = statuses or ["answered"] * len(values)
    duplicate = {int(d["n"]): int(d["of"]) for d in case.get("expected_duplicates") or []}
    rows = []
    for n, (item, value, status) in enumerate(
            zip(case["expected_items"], values, statuses), 1):
        item_cell = item
        if n in duplicate:
            item_cell += f" (duplicado de #{duplicate[n]})"
        if status == "missing":
            value = "—"
        rows.append({"n": n, "item": item, "item_cell": item_cell,
                     "answer": value, "status": status, "duplicate_of": duplicate.get(n)})
    table = {
        "by_code": True,
        "rows": len(rows),
        "header": ["#", "Elemento", "Respuesta", "Estado"],
        "cells": [[str(r["n"]), r["item_cell"], r["answer"], r["status"]] for r in rows],
        "rows_data": rows,
        "empty": sum(1 for r in rows if r["status"] == "missing"),
        "duplicates": len(duplicate),
    }
    missing = table["empty"]
    list_meta = {
        "count": len(rows), "answered": len(rows) - missing, "missing": missing,
        "disagreement": 0, "where": "local", "executed": "local",
        "waves": case.get("expected_waves", 1), "duplicates": len(duplicate),
    }
    preview = {
        "items": list(case["expected_items"]),
        "count": len(rows),
        "duplicates": len(duplicate),
        "what_leaves": {"items": list(case["expected_items"]), "count": len(rows)},
        "default_where": "local",
        "local_only_reason": "",
        "privacy": {"sensitive": False, "items_flagged": []},
    }
    if case.get("preview_local_only"):
        preview["local_only_reason"] = "privacy tier TRUSTED: stays local"
        preview["privacy"] = {"sensitive": True, "items_flagged": [{"n": 1}]}
    meta = {"table": table, "list": list_meta,
            "receipt": {"recipe": "list", "recipe_where": "local", "envios": []}}
    return preview, meta


def _score(case_id: str, values: list[str], statuses: list[str] | None = None,
           sends: int = 0):
    preview, meta = _output(case_id, values, statuses)
    return preview, meta, rd.score_list(CASES[case_id], preview, meta, sends,
                                        {"registro": [], "proxy": []})


# --------------------------------------------------------------------------- cases


def test_the_battery_is_well_formed():
    cases = list(CASES.values())
    ids = [c["id"] for c in cases]
    assert len(cases) == 11 and len(ids) == len(set(ids))
    for case in cases:
        assert case["operation"].strip()
        assert len(case["expected"]) == len(case["expected_items"])
        assert case.get("expected_waves") == math.ceil(len(case["expected_items"]) / 12)
        for pattern in case["expected"]:
            if pattern is not None:
                re.compile(pattern)
        for dup in case.get("expected_duplicates") or []:
            assert 1 <= dup["of"] < dup["n"] <= len(case["expected_items"])
    missing = [c for c in cases if None in c["expected"]]
    assert [c["id"] for c in missing] == ["EX-03"]
    personal = [c for c in cases if c.get("preview_local_only")]
    assert [c["id"] for c in personal] == ["PN-01"]
    assert personal[0]["preview_where"] == "swarm"
    assert personal[0]["ajustes"]["privacy.tier"] == "GLOBAL"


def test_the_csv_case_points_at_the_committed_column():
    source = CASES["CS-01"]["source"]
    assert source == {"kind": "csv", "file": "lotes.csv", "column": "lote"}
    text = (BATTERY / "corpus" / source["file"]).read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    assert lines[0] == "lote,region,cantidad"
    assert ",Norte,4" in lines                           # empty lote, dropped
    assert lines.count("Aliso,Norte,3") == 2             # duplicate, kept
    assert CASES["CS-01"]["expected_items"] == ["Aliso", "Canelo", "Lingue", "Aliso"]


def test_the_preview_payload_keeps_pasted_blanks_and_sends_a_csv_source_only():
    pasted = rd.list_preview_payload(CASES["CL-01"])
    assert "\n\n" in pasted["items"] and pasted["source"] == {"kind": "pasted"}
    csv = rd.list_preview_payload(CASES["CS-01"])
    assert csv["items"] == ""
    assert csv["source"] == {"kind": "csv", "file": "lotes.csv", "column": "lote"}
    personal = rd.list_preview_payload(CASES["PN-01"])
    assert personal["where"] == "swarm"


# --------------------------------------------------------------------------- scoring


def test_a_perfect_answer_passes_every_check():
    preview, meta, score = _score(
        "CL-01", ["vocal", "consonante", "vocal", "consonante", "vocal", "vocal", "consonante"])
    assert score["aprobado"] is True
    assert score["celdas_ok"] == score["celdas_total"] == 7
    assert all(score["comprobaciones"].values())


def test_a_missing_row_is_caught():
    preview, meta = _output(
        "CL-01", ["vocal", "consonante", "vocal", "consonante", "vocal", "vocal", "consonante"])
    meta["table"]["rows_data"].pop()
    meta["table"]["cells"].pop()
    score = rd.score_list(CASES["CL-01"], preview, meta, 0)
    assert score["aprobado"] is False
    assert score["comprobaciones"]["filas"] is False
    assert score["celdas_ok"] < score["celdas_total"]


def test_a_reordered_table_is_caught():
    preview, meta = _output(
        "CL-01", ["vocal", "consonante", "vocal", "consonante", "vocal", "vocal", "consonante"])
    meta["table"]["rows_data"][0], meta["table"]["rows_data"][1] = (
        meta["table"]["rows_data"][1], meta["table"]["rows_data"][0])
    score = rd.score_list(CASES["CL-01"], preview, meta, 0)
    assert score["aprobado"] is False
    assert score["comprobaciones"]["filas"] is False


def test_an_invented_value_for_the_no_basis_item_is_caught():
    preview, meta, good = _score(
        "EX-03", ["LN-410", "LN-411", "—", "LN-413"],
        ["answered", "answered", "missing", "answered"])
    assert good["aprobado"] is True and good["faltantes"] == 1

    meta["table"]["rows_data"][2].update(answer="LN-999", status="answered")
    meta["table"]["cells"][2][2] = "LN-999"
    meta["table"]["cells"][2][3] = "answered"
    meta["table"]["empty"] = 0
    meta["list"].update(answered=4, missing=0)
    score = rd.score_list(CASES["EX-03"], preview, meta, 0)
    assert score["aprobado"] is False
    assert score["comprobaciones"]["celdas"] is False
    assert score["comprobaciones"]["metadatos"] is False
    assert any(f["n"] == 3 for f in score["celdas_fallidas"])


def test_a_non_zero_send_is_caught():
    preview, meta, score = _score(
        "CL-01", ["vocal", "consonante", "vocal", "consonante", "vocal", "vocal", "consonante"])
    meta["receipt"]["envios"] = [{"destino": "127.0.0.1"}]
    bad = rd.score_list(CASES["CL-01"], preview, meta, 1, {"registro": [{"q": "x"}], "proxy": []})
    assert score["aprobado"] is True
    assert bad["aprobado"] is False and bad["comprobaciones"]["envios"] is False


def test_duplicate_marker_by_code_and_status_column_are_each_caught():
    preview, meta = _output(
        "CL-01", ["vocal", "consonante", "vocal", "consonante", "vocal", "vocal", "consonante"])
    meta["table"]["rows_data"][4]["item_cell"] = "aroma"
    meta["table"]["cells"][4][1] = "aroma"
    assert rd.score_list(CASES["CL-01"], preview, meta, 0)["comprobaciones"]["duplicados"] is False

    preview, meta = _output(
        "CL-01", ["vocal", "consonante", "vocal", "consonante", "vocal", "vocal", "consonante"])
    meta["table"]["by_code"] = False
    assert rd.score_list(CASES["CL-01"], preview, meta, 0)["comprobaciones"]["tabla_por_codigo"] is False

    preview, meta = _output(
        "CL-01", ["vocal", "consonante", "vocal", "consonante", "vocal", "vocal", "consonante"])
    meta["table"]["header"][-1] = "Valor"
    assert rd.score_list(CASES["CL-01"], preview, meta, 0)["comprobaciones"]["columnas"] is False


def test_the_personal_preview_must_be_local_and_explain_why():
    preview, meta, good = _score("PN-01", ["Los Coigües", "Los Aromos", "El Lingue"])
    assert good["aprobado"] is True and good["comprobaciones"]["vista_previa"] is True

    preview["default_where"] = "swarm"
    preview["local_only_reason"] = ""
    bad = rd.score_list(CASES["PN-01"], preview, meta, 0)
    assert bad["aprobado"] is False
    assert bad["comprobaciones"]["vista_previa"] is False


def test_a_nonlocal_run_fails_the_metadata_check():
    preview, meta = _output(
        "CL-01", ["vocal", "consonante", "vocal", "consonante", "vocal", "vocal", "consonante"])
    meta["list"]["where"] = "swarm"
    meta["list"]["executed"] = "distributed"
    score = rd.score_list(CASES["CL-01"], preview, meta, 0)
    assert score["aprobado"] is False and score["comprobaciones"]["metadatos"] is False


# --------------------------------------------------------------------------- summary/rescore


def test_the_list_summary_counts_checks_cells_and_cases():
    rows = []
    for rep in (1, 2):
        preview, meta, score = _score(
            "CL-01", ["vocal", "consonante", "vocal", "consonante", "vocal", "vocal", "consonante"])
        rows.append({"id": "CL-01", "cat": "CL", "rep": rep, "estado": "done",
                     "turnos": [{"latencia_s": 1.0}], "puntuacion": score})
    preview, meta, score = _score(
        "EX-03", ["LN-410", "LN-411", "—", "LN-413"],
        ["answered", "answered", "missing", "answered"])
    score["aprobado"] = False                         # a defective repetition
    rows.append({"id": "EX-03", "cat": "EX", "rep": 1, "estado": "done",
                 "turnos": [{"latencia_s": 1.0}], "puntuacion": score})
    summ = rd.summarise_list(rows)
    assert summ["total"]["n"] == 3 and summ["total"]["aprobados"] == 2
    assert summ["total"]["celdas"] == [18, 18]
    assert summ["por_caso"]["CL-01"]["aprobados"] == 2
    assert summ["total"]["por_comprobacion"]["vista_previa"] == [3, 3]
    md = rd.list_summary_markdown("run", {"modelo": "qwen2.5:7b", "repeticiones": 1,
                                          "versiones": {"swarmbly-app": "0.7.0"}},
                                  summ, rows, None)
    assert "Batería abierta de listas" in md and "| CL-01 |" in md
    assert "batería abierta, no una medición sellada" in md


def test_rescore_reuses_the_stored_answer_for_a_list_run(tmp_path):
    battery = tmp_path / "battery"
    (battery / "ejecuciones" / "run1" / "casos").mkdir(parents=True)
    (battery / "casos.json").write_text(
        (BATTERY / "casos.json").read_text(encoding="utf-8"), encoding="utf-8")
    preview, meta, score = _score(
        "CL-01", ["vocal", "consonante", "vocal", "consonante", "vocal", "vocal", "consonante"])
    row = {"id": "CL-01", "cat": "CL", "rep": 1, "estado": "done",
           "preview": preview, "meta": meta, "respuesta": "table",
           "red": {"registro": [], "proxy": []},
           "turnos": [{"latencia_s": 1.0}], "puntuacion": score}
    (battery / "ejecuciones" / "run1" / "casos" / "CL-01_r1.json").write_text(
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
    assert summary["total"]["celdas"] == [7, 7]
    assert (battery / "ejecuciones" / "run1" / "resumen.md").is_file()
