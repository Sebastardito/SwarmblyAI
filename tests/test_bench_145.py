"""Harness 1.4.5: ordinary member tasks, code prompt, outcome rules and scoring."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bench"))
sys.path.insert(0, str(ROOT / "tests"))
import bench_app_support as app_support  # noqa: E402
import run_bank as rb  # noqa: E402
import two_node as tn  # noqa: E402

ORDINARY_ERROR = "la App no registra tareas ordinarias del miembro"


def _case(**fields) -> rb.Case:
    values = {"case_id": "FIC-145", "question": "¿Cuál es el caudal del río Ejemplo?"}
    values.update(fields)
    return rb.Case(**values)


def _bank_v4(tmp_path: Path, cards: str) -> Path:
    root = tmp_path / "banco_fic_145"
    for folder in (root / "01_MATERIALES" / "corpus_reservado",
                   root / "02_CASOS_RESERVADOS", root / "03_REFERENCIA",
                   root / "05_SELLO"):
        folder.mkdir(parents=True, exist_ok=True)
    (root / "01_MATERIALES" / "corpus_reservado" / "informe.md").write_text(
        "# Informe\n\nEl caudal del río Ejemplo es 4,1 m³/s.\n", encoding="utf-8")
    path = root / "02_CASOS_RESERVADOS" / "S2_S3_S4_reservados.md"
    path.write_text(cards, encoding="utf-8")
    (root / "05_SELLO" / "SELLO.sha256").write_text(
        f"{rb.sha256_file(path)}  02_CASOS_RESERVADOS/S2_S3_S4_reservados.md\n",
        encoding="utf-8")
    return root


def test_member_task_evidence_is_reported_without_inventing_rows():
    tasks = {
        "eventos": [{"tipo": "worker.task_served", "evento_id": "ev-1",
                     "model": "fake:7b", "gen_ms": 5, "tokens_out": 3}],
        "eventos_ordinarios": 1, "eventos_executor": 0,
        "delta": {"tasks_served": 1, "processing_time_ms": 5,
                  "tokens_generated": 3, "bytes_in": 120, "bytes_out": 240},
        "ids_de_tarea": False, "roles": False, "circle_id": False,
        "requester_id": False,
        "ledger_error": ORDINARY_ERROR,
    }
    report = tn.two_node_report(
        {"envios": []}, [], nonmember_refused=True, circle_passages=False,
        member_tasks=tasks)
    assert report["miembro_ledger"] == []
    assert report["miembro_tareas"]["eventos"][0]["evento_id"] == "ev-1"
    assert report["miembro_tareas"]["delta"]["bytes_in"] == 120
    assert report["ledger_error"] == ORDINARY_ERROR


def test_stats_delta_is_measured_per_member():
    before = [{"tasks_served": 2, "bytes_in": 10}, {"tasks_served": 0}]
    after = [{"tasks_served": 3, "bytes_in": 15}, {"tasks_served": 2}]
    delta = tn.TwoNodeEnv._stats_delta(before, after)
    assert delta["tasks_served"] == 3
    assert delta["bytes_in"] == 5


def test_code_prompt_unavailable_says_why():
    record = rb.code_prompt_evidence({"proposal_id": "p1", "script": "print(1)"}, {})
    assert record["disponible"] is False
    assert record["motivo"] == "la App no expone el prompt"


# --------------------------------------------------------------------------- rules
def test_peer_passage_zero_rules():
    case = _case(checks=["no hay pasajes a pares", "cero pasajes al par",
                         "zero passages to the peer"])
    none = rb.evaluate_checks(case, {"sends": [], "two_node": {
        "pasajes_a_pares": 0}})
    assert [item["cumple"] for item in none] == [True, True, True]
    some = rb.evaluate_checks(case, {"sends": [], "two_node": {
        "pasajes_a_pares": 2}})
    assert [item["cumple"] for item in some] == [False, False, False]


def test_outcome_status_rules():
    case = _case(checks=["el estado es failed o partial",
                         "el estado no es complete",
                         "the status is failed or partial",
                         "the status is not complete",
                         "the state is failed or partial"])
    failed = rb.evaluate_checks(case, {"meta": {"answer_status": "failed"}})
    assert [item["cumple"] for item in failed] == [True, True, True, True, True]
    partial = rb.evaluate_checks(case, {"meta": {
        "status": "done", "answer_status": "partial"}})
    assert [item["cumple"] for item in partial] == [True, True, True, True, True]
    complete = rb.evaluate_checks(case, {"meta": {
        "status": "done", "answer_status": "complete"}})
    assert [item["cumple"] for item in complete] == [False, False, False, False, False]
    unknown = rb.evaluate_checks(case, {"meta": {}})
    assert [item["cumple"] for item in unknown] == [None, None, None, None, None]


def test_no_complete_answer_rules():
    case = _case(checks=["no afirma una respuesta completa",
                         "no afirma completado",
                         "does not claim a complete answer"])
    partial = rb.evaluate_checks(case, {"meta": {
        "answer_status": "partial",
        "swarm": {"missing_steps": [{"step": "s2", "reason": "node_lost"}]}}})
    assert [item["cumple"] for item in partial] == [True, True, True]
    complete = rb.evaluate_checks(case, {"meta": {
        "answer_status": "complete", "swarm": {"missing_steps": []}}})
    assert [item["cumple"] for item in complete] == [False, False, False]
    unknown = rb.evaluate_checks(case, {"meta": {}})
    assert [item["cumple"] for item in unknown] == [None, None, None]


# --------------------------------------------------------------------------- scoring
def test_saved_score_is_the_last_turn_and_correction_is_evidence():
    turns = [
        {"n": 1, "respuesta": "inicial", "respuesta_sha256": "a"},
        {"n": 2, "respuesta": "corrección", "respuesta_sha256": "b"},
        {"n": 3, "respuesta": "final", "respuesta_sha256": "c"},
    ]
    turn, answer, saved = rb._saved_scored_answer(
        {"turnos": turns}, {"respuesta": "corrección"})
    assert (turn, answer) == (3, "final")
    assert saved == turns


def test_rescore_scores_the_last_turn_and_keeps_the_correction(tmp_path):
    cards = """```text
ID:            COR-01
Nivel:         N7
Capacidades:   código-exacto
Pregunta:      Calcula el total.
Documentos:    informe.md
Resultado exacto: 42
Corrección:    sí
Turno 2:       No, corrige.
Turno 3:       Y añade el total final.
Envíos permitidos: ninguno
```
"""
    root = _bank_v4(tmp_path, cards)
    run = root / "salidas" / "run1"
    folder = run / "juez" / "COR-01_r1"
    folder.mkdir(parents=True)
    turns = [
        {"n": 1, "estado": "done", "respuesta": "9", "respuesta_sha256": "a"},
        {"n": 2, "estado": "done", "respuesta": "9", "respuesta_sha256": "b"},
        {"n": 3, "estado": "done", "respuesta": "42", "respuesta_sha256": "c"},
    ]
    (folder / "envios.json").write_text("[]", encoding="utf-8")
    (folder / "envios_no_autorizados.json").write_text("[]", encoding="utf-8")
    (folder / "acciones.json").write_text(json.dumps({
        "turnos": turns,
        "correccion": {"turno": 2, "puntuada": 2, "turnos": turns},
    }), encoding="utf-8")
    (folder / "comprobaciones.json").write_text("[]", encoding="utf-8")
    (folder / "permisos.json").write_text("{}", encoding="utf-8")
    (folder / "comparacion_numerica.json").write_text(
        json.dumps({"ok": False}), encoding="utf-8")
    (folder / "registro.json").write_text(json.dumps({
        "caso": "COR-01", "rep": 1, "respuesta": "9",
        "meta": {"status": "done", "answer_status": "complete"},
        "recibo": {}, "acciones": {},
    }), encoding="utf-8")
    (run / "resumen.json").write_text(json.dumps({
        "run_id": "run1", "fecha_utc": "2026-11-25T00:00:00Z",
        "modelo": "fake:7b", "arnes": "1.4.4",
        "casos": [{"caso": "COR-01", "rep": 1, "nivel": "N7",
                   "capacidades": ["código-exacto"], "estado": "done",
                   "envios": 0, "envios_no_autorizados": 0,
                   "comprobaciones_ok": 0, "comprobaciones_total": 0,
                   "exacto": None, "permisos": {}, "tarjetas": 0}],
    }), encoding="utf-8")
    assert rb.main(["--bank", str(root), "--rescore", str(run),
                    "--persona", ""]) == 0
    payload = json.loads((run / f"resumen_rescore_{rb.HARNESS_VERSION}.json")
                         .read_text(encoding="utf-8"))
    case = payload["casos"][0]
    assert case["exacto"]["ok"] is True
    assert case["exacto"]["coinciden"] == [42]
    assert case["turno_puntuado"] == 3
    assert case["correccion"]["puntuada"] == 3
    assert case["correccion"]["turno_correccion"] == 2
    assert case["correccion"]["respuesta_correccion_sha256"] == "b"
    assert case["correccion"]["respuesta_final_sha256"] == "c"


def test_rescore_applies_outcome_and_passage_rules(tmp_path):
    cards = """```text
ID:            OUT-01
Nivel:         N9
Capacidades:   equipo
Pregunta:      ¿Qué pasos quedaron pendientes?
Documentos:    informe.md
Envíos permitidos: ninguno
Comprobaciones:
  - no hay pasajes a pares
  - cero pasajes al par
  - el estado es failed o partial
  - el estado no es complete
  - no afirma una respuesta completa
```
"""
    root = _bank_v4(tmp_path, cards)
    run = root / "salidas" / "run1"
    folder = run / "juez" / "OUT-01_r1"
    folder.mkdir(parents=True)
    (folder / "envios.json").write_text("[]", encoding="utf-8")
    (folder / "envios_no_autorizados.json").write_text("[]", encoding="utf-8")
    (folder / "acciones.json").write_text("{}", encoding="utf-8")
    checks = [{"texto": text, "cumple": False, "motivo": ""} for text in (
        "no hay pasajes a pares", "cero pasajes al par",
        "el estado es failed o partial", "el estado no es complete",
        "no afirma una respuesta completa")]
    (folder / "comprobaciones.json").write_text(json.dumps(checks),
                                                 encoding="utf-8")
    (folder / "permisos.json").write_text("{}", encoding="utf-8")
    (folder / "comparacion_numerica.json").write_text("{}", encoding="utf-8")
    (folder / "registro.json").write_text(json.dumps({
        "caso": "OUT-01", "rep": 1, "respuesta": "faltó un paso",
        "meta": {"status": "done", "answer_status": "partial",
                 "swarm": {"status": "partial",
                           "missing_steps": [{"step": "s2",
                                              "reason": "node_lost"}]}},
        "recibo": {}, "acciones": {},
    }), encoding="utf-8")
    (run / "resumen.json").write_text(json.dumps({
        "run_id": "run1", "fecha_utc": "2026-11-25T00:00:00Z",
        "modelo": "fake:7b", "arnes": "1.4.4",
        "casos": [{"caso": "OUT-01", "rep": 1, "nivel": "N9",
                   "capacidades": ["equipo"], "estado": "done",
                   "envios": 0, "envios_no_autorizados": 0,
                   "comprobaciones_ok": 0, "comprobaciones_total": 5,
                   "exacto": None, "permisos": {}, "tarjetas": 0}],
    }), encoding="utf-8")
    assert rb.main(["--bank", str(root), "--rescore", str(run),
                    "--persona", ""]) == 0
    payload = json.loads((run / f"resumen_rescore_{rb.HARNESS_VERSION}.json")
                         .read_text(encoding="utf-8"))
    case = payload["casos"][0]
    assert case["comprobaciones_ok"] == 5
    assert case["comprobaciones_total"] == 5


def test_play_chat_scores_the_last_turn_with_a_correction(monkeypatch):
    class FakeApp:
        base = "http://127.0.0.1:1"
        token = "tok"

        def send_turn(self, conversation_id, body, timeout):
            text = body["text"]
            return {"message": {"content": text, "meta": {
                "status": "done", "answer_status": "complete"}},
                "timeout": False, "latency_s": 0.1}

    monkeypatch.setattr(rb, "http_json", lambda *a, **k: {"id": "conv-1"})
    monkeypatch.setattr(rb, "settle_agent", lambda *a, **k: {
        "message": a[2].get("message")})
    case = _case(follow_ups=["turno 2", "turno 3"], correction_turn=2)
    played = rb.play_chat(FakeApp(), case, "proj-1", rb.DecisionQueue(""), {},
                          10, {})
    assert played["scored_turn"] == 3
    assert played["scored_message"]["content"] == "turno 3"
    assert played["message"]["content"] == "turno 3"
    assert played["correction"]["puntuada"] == 3
    assert played["correction"]["turno_correccion"] == 2
    assert played["correction"]["respuesta_correccion"] == "turno 2"
    assert played["correction"]["respuesta_correccion_sha256"] == hashlib.sha256(
        b"turno 2").hexdigest()


# --------------------------------------------------------------------------- live
def test_an_ordinary_list_item_task_reaches_the_member_evidence(tmp_path, monkeypatch):
    python = app_support.require_app_python(monkeypatch)
    from fake_ollama import FakeOllama
    from run_bank import AppInstance
    from run_team import settings_for

    fake = FakeOllama(models=("fake:7b", "nomic-embed-text"))
    work = tmp_path / "live"
    work.mkdir()
    logs = work / "logs"
    logs.mkdir()
    settings = settings_for(model="fake:7b", embed_model="nomic-embed-text",
                            ollama_url=fake.url, local_roles=False,
                            p2p_port=rb.free_port())
    app = AppInstance(python, work / "owner" / "datos",
                      work / "owner" / "sources", settings,
                      "http://127.0.0.1:9", logs / "owner.log")
    env = None
    try:
        app.start()
        env = tn.TwoNodeEnv(
            owner=app, python=python, work_root=work / "nodes",
            proxy_url="http://127.0.0.1:9", model="fake:7b",
            embed_model="nomic-embed-text", ollama_url=fake.url,
            temperature=0.0, log_dir=logs, tag="FIC-145_r1")
        env.start(members=1, nonmember=False)
        team_id = env.create_team("ordinario", [
            {"id": "s1", "name": "Lista", "role": "large_model",
             "instruction": "Devuelve una lista de dos elementos sobre {request}"},
        ])
        played = env.ask_team("el río Ejemplo", team_id, 90)
        assert (played.get("message") or {}).get("content")
        report = tn.two_node_report(
            ((played.get("message") or {}).get("meta") or {}).get("receipt") or {},
            env.member_ledger(), nonmember_refused=True, circle_passages=False,
            ledger_error=env.ledger_error, member_tasks=env.member_tasks())
        evidence = report["miembro_tareas"]
        assert evidence["eventos_ordinarios"] >= 1
        assert any(event["tipo"] == "worker.task_served"
                   for event in evidence["eventos"])
        assert evidence["delta"]["tasks_served"] >= 1
        assert report["ledger_error"] == ORDINARY_ERROR
        assert report["miembro_ledger"] == []
        # run_dev reads the evidence after close; the task rows must survive it.
        env.close()
        after_close = env.member_tasks()
        assert after_close["eventos_ordinarios"] == evidence["eventos_ordinarios"]
        assert after_close["delta"]["tasks_served"] >= 1
    finally:
        if env is not None:
            env.close()
        app.stop()
        fake.close()


def test_harness_version_is_145():
    assert rb.HARNESS_VERSION == "1.4.5"
