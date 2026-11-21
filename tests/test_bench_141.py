"""Harness 1.4.1: output files, material, works by iD, N7 numbers, corrections
and the model each recipe used."""
from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("run_bank_141", ROOT / "bench" / "run_bank.py")
rb = importlib.util.module_from_spec(_spec)
sys.modules["run_bank_141"] = rb
_spec.loader.exec_module(rb)


def _bank_v4(tmp_path: Path, cards: str) -> Path:
    root = tmp_path / "banco_v4"
    for folder in (root / "01_MATERIALES" / "corpus_reservado",
                   root / "02_CASOS_RESERVADOS", root / "03_REFERENCIA",
                   root / "05_SELLO"):
        folder.mkdir(parents=True, exist_ok=True)
    (root / "01_MATERIALES" / "corpus_reservado" / "informe.md").write_text(
        "# Informe\n\nLos sensores operativos fueron 7, no 9.\n", encoding="utf-8")
    (root / "02_CASOS_RESERVADOS" / "S2_S3_S4_reservados.md").write_text(
        cards, encoding="utf-8")
    case_file = root / "02_CASOS_RESERVADOS" / "S2_S3_S4_reservados.md"
    (root / "05_SELLO" / "SELLO.sha256").write_text(
        f"{rb.sha256_file(case_file)}  02_CASOS_RESERVADOS/S2_S3_S4_reservados.md\n",
        encoding="utf-8")
    return root


def _card(extra: str = "", checks: str = "") -> str:
    return f"""```text
ID:            T14-01
Nivel:         N7
Capacidades:   código, código-exacto
Pregunta:      ¿Cuál es el caudal?
Documentos:    informe.md
Envíos permitidos: ninguno
{extra}{checks}```
"""


def test_parse_output_spec_and_evaluate_the_produced_file(tmp_path):
    spec = rb.parse_output_spec(
        "resultado.csv (columnas: estacion, caudal; filas: 2)")
    assert spec.name == "resultado.csv" and spec.extension == ".csv"
    assert spec.columns == ["estacion", "caudal"] and spec.rows == 2
    folder = tmp_path / "salidas"
    folder.mkdir()
    produced = folder / "resultado.csv"
    produced.write_text("estacion,caudal\nQA,4.1\nQB,9.1\n", encoding="utf-8")
    entries = [{"name": "resultado.csv", "size": produced.stat().st_size,
                "local": "resultado.csv"}]
    report = rb.evaluate_output(spec, entries, folder)
    assert report["ok"] and report["filas"] == 2
    assert report["columnas"] == ["estacion", "caudal"]
    # Missing file.
    assert not rb.evaluate_output(spec, [], folder)["ok"]
    # Wrong extension.
    other = [{"name": "resultado.json", "size": 10, "local": "resultado.json"}]
    assert not rb.evaluate_output(spec, other, folder)["ok"]
    # Empty file.
    empty = folder / "vacio.csv"
    empty.write_text("", encoding="utf-8")
    assert not rb.evaluate_output(
        rb.OutputSpec("vacio.csv", "vacio.csv", ".csv"), 
        [{"name": "vacio.csv", "size": 0, "local": "vacio.csv"}], folder)["ok"]
    # Wrong column and wrong row count.
    assert not rb.evaluate_output(
        rb.OutputSpec("", "resultado.csv", ".csv", ["otra"], None),
        entries, folder)["ok"]
    assert not rb.evaluate_output(
        rb.OutputSpec("", "resultado.csv", ".csv", [], 3),
        entries, folder)["ok"]


def test_output_file_field_is_parsed_and_validated(tmp_path):
    root = _bank_v4(tmp_path, _card(
        "Archivo de salida: resultado.csv (columnas: estacion, caudal; filas: 2)\n"))
    bank = rb.detect_bank(root)
    case = rb.parse_cases(bank.cases_file)[0]
    assert case.output_file.startswith("resultado.csv")
    problems, info = rb.validate_case(bank, case)
    assert problems == [] and info["salida"] == "resultado.csv"
    # A name without extension is a check-time problem.
    bad = _bank_v4(tmp_path / "malo", _card("Archivo de salida: resultado\n"))
    bad_case = rb.parse_cases(rb.detect_bank(bad).cases_file)[0]
    assert any("extensión" in problem
               for problem in rb.validate_case(rb.detect_bank(bad), bad_case)[0])


def test_material_phrases_match_used_material_and_the_answer():
    case = rb.Case("M-01", "¿Sensores?", skill="demo", servers=["planillas"],
                   team="example-write-review",
                   material="«informe.md» y «Los sensores operativos fueron 7, no 9»")
    meta = {"lce": {"sources": [{"source": "informe.md", "rel": "informe.md"}]},
            "roles": {"writer": {"model": "qwen2.5:7b"}}}
    actions = {"skill": {"name": "demo"},
               "mcp": [{"servidor": "planillas", "tools": ["buscar_estacion"]}],
               "proyecto": {"documentos": ["informe.md"]}}
    report = rb.evaluate_material(
        case, meta, actions, [], "El informe dice que los sensores operativos fueron 7, no 9.")
    assert report["frases"] == 2 and report["usadas"] == 2 and not report["faltan"]
    assert [item["usada"] for item in report["detalle"]] == [True, True]
    # A material name is not rescued by mentioning it in the answer.
    missing = rb.evaluate_material(
        rb.Case("M-02", "¿?", material="«otro_informe.md»"),
        {"lce": {"sources": [{"source": "informe.md"}]}}, {}, [],
        "otro_informe.md aparece aquí")
    assert missing["faltan"] == ["otro_informe.md"]
    # A plain phrase may be matched in the answer.
    answer_only = rb.evaluate_material(
        rb.Case("M-03", "¿?", material="«un dato suelto»"), {}, {}, [],
        "La respuesta contiene un dato suelto.")
    assert answer_only["usadas"] == 1
    assert rb.check_text_for_material("informe.md") == "Material necesario: informe.md"


def test_works_by_id_is_its_own_group_only_when_the_card_asks():
    asked = rb.Case("A-01", "¿Obras?", checks=[
        "lista las obras por iD aparte de las consultas públicas"])
    plain = rb.Case("A-02", "¿Obras?", checks=["lista las obras"])
    assert rb.asks_works_by_id(asked)
    assert not rb.asks_works_by_id(plain)
    sends = [
        {"destino": "pub.orcid.org", "tipo": "consulta_autor", "payload": "Tomás",
         "campo": "q", "bytes": 6},
        {"destino": "pub.orcid.org", "tipo": "consulta_autor", "payload": "0000-0000-0000-0101",
         "campo": "orcid", "orcid": "0000-0000-0000-0101", "bytes": 19},
        {"destino": "registro_publico_simulado", "tipo": "buscador_publico",
         "payload": "caudal", "bytes": 6},
    ]
    groups = rb.group_sends(sends)
    assert groups["obras_por_id"]["total"] == 1
    assert groups["autores_por_nombre"]["total"] == 1
    assert groups["publicas"]["total"] == 1
    assert "payload" not in groups["obras_por_id"]["items"][0]


def test_n7_exact_numbers_use_zero_tolerance_unless_the_card_states_one():
    assert rb.compares_exact_numbers(
        rb.Case("N7-00", "¿?", level="N7", exact_result="4,1"))
    assert not rb.compares_exact_numbers(rb.Case("N7-00", "¿?", level="N7"))
    no_tolerance = rb.Case("N7-01", "¿?", level="N7", exact_result="4,1")
    stated = rb.Case("N7-02", "¿?", level="N7", tolerance="±0,01")
    other = rb.Case("N5-01", "¿?", level="N5", tolerance="±0,01")
    assert rb.effective_tolerance(no_tolerance) == 0.0
    assert rb.effective_tolerance(stated) == 0.01
    assert rb.effective_tolerance(other) == 0.01
    strict = rb.compare_numbers([4.173], "4,18", rb.effective_tolerance(no_tolerance))
    loose = rb.compare_numbers([4.173], "4,18", rb.effective_tolerance(stated))
    assert not strict["ok"] and loose["ok"]
    assert strict["coinciden"] == [] and loose["coinciden"] == [4.173]
    assert loose["no_coinciden"] == []


def test_correction_turn_parses_runs_two_turns_and_scores_the_correction(tmp_path, monkeypatch):
    cards = _card("Turno 2: No, corrige: el caudal es 4,1 m³/s.\nCorrección: sí\n")
    bank = rb.detect_bank(_bank_v4(tmp_path, cards))
    case = rb.parse_cases(bank.cases_file)[0]
    assert case.correction_turn == 2
    assert rb.validate_case(bank, case)[0] == []

    first = {"id": "m1", "role": "assistant", "content": "primera",
             "meta": {"status": "done", "model": "qwen2.5:7b",
                      "meta": {"backend": "ollama"},
                      "receipt": {"envios": [{"valor": "uno"}]}}}
    second = {"id": "m2", "role": "assistant", "content": "corregida",
              "meta": {"status": "done", "model": "qwen2.5:7b",
                       "meta": {"backend": "ollama"},
                       "receipt": {"envios": [{"valor": "dos"}]}}}
    messages = [first, second]

    class _ChatApp:
        base, token = "http://fake", "t"

        def send_turn(self, conversation_id, body, timeout):
            return {"message": messages.pop(0), "latency_s": 0.1,
                    "timeout": False, "message_id": "m"}

    monkeypatch.setattr(rb, "http_json", lambda *args, **kwargs: {"id": "c1"})
    actions: dict = {}
    played = rb.play_chat(_ChatApp(), case, "p", rb.DecisionQueue(""), actions,
                          5.0, {})
    assert played["scored_message"]["content"] == "corregida"
    assert played["scored_turn"] == 2
    assert len(played["receipts"]) == 2
    assert [turn["n"] for turn in played["correction"]["turnos"]] == [1, 2]
    assert played["correction"]["turnos"][1]["respuesta"] == "corregida"
    assert played["correction"]["turno"] == 2
    assert len(played["correction"]["recibos"]) == 2
    assert played["correction"]["recibos"][1]["envios"] == [{"valor": "dos"}]


def test_model_report_and_csv_keep_the_reported_model_and_backend(tmp_path):
    case = rb.Case("R-01", "¿?", recipe="code")
    meta = {"model": "qwen2.5:7b", "meta": {"backend": "ollama"},
            "model_destination": {"clase": "LOCAL", "host": "127.0.0.1"}}
    turns = [{"n": 1, "receta": "code", "modelo": "qwen2.5:7b",
              "backend": "ollama", "destino_modelo": {"clase": "LOCAL"}}]
    report = rb.model_report(case, meta, {}, turns)
    assert report["receta"] == "code"
    assert report["modelo"] == "qwen2.5:7b" and report["backend"] == "ollama"
    assert report["destino_modelo"]["clase"] == "LOCAL"
    assert report["por_turno"][0]["turno"] == 1
    path = tmp_path / "casos.csv"
    rb.write_cases_csv(path, [{
        "caso": "R-01", "rep": 1, "nivel": "N7", "estado": "done",
        "latencia_s": 1.0, "envios": 0, "envios_no_autorizados": 0,
        "comprobaciones_ok": 1, "comprobaciones_total": 1,
        "exacto": {"ok": True}, "modelo_por_receta": report,
        "envios_obras_por_id": 0, "correccion": {"turno": 0},
    }])
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert rows[0]["modelo"] == "qwen2.5:7b"
    assert rows[0]["backend"] == "ollama"
    assert rows[0]["destino_modelo"] == "LOCAL@127.0.0.1"
    assert rows[0]["exacto_ok"] == "True"


def test_check_accepts_the_new_fields_and_keeps_content_out_of_stdout(tmp_path, capsys):
    cards = _card(
        "Archivo de salida: resultado.csv (columnas: estacion, caudal; filas: 2)\n"
        "Material necesario: «informe.md»\n"
        "Turno 2: No, corrige: el caudal es 4,1 m³/s.\n"
        "Corrección: sí\n",
        "Comprobaciones:\n  - lista las obras por iD aparte\n")
    bank_root = _bank_v4(tmp_path, cards)
    assert rb.main(["--bank", str(bank_root), "--model", "fake:7b", "--check"]) == 0
    out = capsys.readouterr().out
    assert "archivo de salida" in out and "material" in out
    assert "corrección en el turno 2" in out and "obras por iD" in out
    assert "¿Cuál es el caudal?" not in out


def test_rescore_recomputes_the_new_checks_when_their_evidence_exists(tmp_path, capsys):
    cards = """```text
ID:            T14-02
Nivel:         N7
Capacidades:   código-exacto
Pregunta:      ¿Cuál es el caudal?
Documentos:    informe.md
Resultado exacto: 4,1 m³/s
Archivo de salida: resultado.csv (columnas: estacion, caudal; filas: 1)
Material necesario: «informe.md»
Envíos permitidos: ninguno
```
"""
    root = _bank_v4(tmp_path, cards)
    bank = rb.detect_bank(root)
    run = root / "04_SALIDAS_AUDITORIA" / "ejecuciones" / "run1"
    folder = run / "juez" / "T14-02_r1"
    (folder / "salidas").mkdir(parents=True)
    (folder / "salidas" / "resultado.csv").write_text(
        "estacion,caudal\nQA,4.1\n", encoding="utf-8")
    (folder / "envios.json").write_text("[]", encoding="utf-8")
    (folder / "envios_no_autorizados.json").write_text("[]", encoding="utf-8")
    (folder / "comprobaciones.json").write_text("[]", encoding="utf-8")
    (folder / "acciones.json").write_text("{}", encoding="utf-8")
    (folder / "permisos.json").write_text("{}", encoding="utf-8")
    (folder / "comparacion_numerica.json").write_text("{}", encoding="utf-8")
    (folder / "salidas.json").write_text(json.dumps({"producidas": [{
        "name": "resultado.csv", "size": 24, "local": "resultado.csv"}]}),
        encoding="utf-8")
    (folder / "registro.json").write_text(json.dumps({
        "caso": "T14-02", "rep": 1, "respuesta": "El caudal es 4,1 m³/s.",
        "meta": {"model": "qwen2.5:7b", "meta": {"backend": "ollama"},
                 "lce": {"sources": [{"source": "informe.md"}]}},
        "recibo": {"destino_modelo": {"clase": "local", "host": "127.0.0.1"}},
        "acciones": {},
    }), encoding="utf-8")
    (run / "resumen.json").write_text(json.dumps({
        "run_id": "run1", "fecha_utc": "2026-11-21T00:00:00Z",
        "modelo": "qwen2.5:7b", "arnes": "1.4.0",
        "casos": [{"caso": "T14-02", "rep": 1, "nivel": "N7",
                   "capacidades": ["código-exacto"], "estado": "done",
                   "envios": 0, "envios_no_autorizados": 0,
                   "comprobaciones_ok": 0, "comprobaciones_total": 0,
                   "exacto": None, "permisos": {}, "tarjetas": 0}],
    }), encoding="utf-8")
    assert rb.main(["--bank", str(root), "--rescore", str(run),
                    "--persona", ""]) == 0
    capsys.readouterr()
    payload = json.loads((run / f"resumen_rescore_{rb.HARNESS_VERSION}.json").read_text(
        encoding="utf-8"))
    case = payload["casos"][0]
    assert case["exacto"]["ok"] and case["exacto"]["coinciden"] == [4.1]
    assert case["salida"]["ok"] and case["salida"]["filas"] == 1
    assert case["material"]["usadas"] == 1 and case["material"]["faltan"] == 0
    assert case["comprobaciones_total"] == 2 and case["comprobaciones_ok"] == 2
    assert case["modelo"] == "qwen2.5:7b" and case["backend"] == "ollama"
    assert (run / f"casos_rescore_{rb.HARNESS_VERSION}.csv").is_file()


def test_correction_field_with_an_unreadable_value_is_a_check_problem(tmp_path):
    cards = _card("Corrección: pronto\n")
    bank = rb.detect_bank(_bank_v4(tmp_path, cards))
    case = rb.parse_cases(bank.cases_file)[0]
    assert any("Corrección" in problem for problem in rb.validate_case(bank, case)[0])
