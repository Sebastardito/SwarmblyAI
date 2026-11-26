"""Bank-v5 cards, two-node report fields, node loss and team outputs."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bench"))
sys.path.insert(0, str(ROOT / "tests"))
import bench_app_support as app_support  # noqa: E402
import run_bank as rb  # noqa: E402
import run_node_loss as loss  # noqa: E402
import run_team as team  # noqa: E402
import two_node as tn  # noqa: E402


def _bank_v5(tmp_path: Path, card: str) -> Path:
    root = tmp_path / "banco_v5"
    for folder in (root / "01_MATERIALES" / "corpus_reservado",
                   root / "02_CASOS_RESERVADOS", root / "03_REFERENCIA",
                   root / "05_SELLO"):
        folder.mkdir(parents=True, exist_ok=True)
    (root / "01_MATERIALES" / "corpus_reservado" / "notas.md").write_text(
        "# Notas\n\nEl río ficticio tiene caudal 4,1 m³/s.\n", encoding="utf-8")
    (root / "02_CASOS_RESERVADOS" / "S2_S3_S4_reservados.md").write_text(
        card, encoding="utf-8")
    lines = []
    for path in sorted(root.rglob("*.md")):
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  "
                     f"{path.relative_to(root).as_posix()}")
    (root / "05_SELLO" / "SELLO.sha256").write_text("\n".join(lines) + "\n",
                                                    encoding="utf-8")
    return root


CARD = '''```text
ID:            V5-01
Nivel:         N9
Capacidades:   lista, círculo
Pregunta:      Para cada código, dime el caudal del río ficticio.
Receta:        lista
Lista:
<<<
A
B
>>>
Dónde:         enjambre
Documentos:    notas.md
Dos nodos:     sí
Pasajes a pares: sí
Pasajes esperados: no
Envíos permitidos: cualquier envío al círculo
Comprobaciones:
  - passages to peers only with circle_passages on
  - non-member refused
  - receipt names the circle and the member
```
'''


def test_v5_card_fields_are_parsed_and_validated(tmp_path):
    root = _bank_v5(tmp_path, CARD)
    bank = rb.detect_bank(root)
    cases = rb.parse_cases(bank.cases_file)
    assert rb.HARNESS_VERSION == "1.4.5"
    assert len(cases) == 1
    case = cases[0]
    assert case.two_node is True
    assert case.circle_passages is True
    assert case.expected_passages is False
    assert rb.validate_case(bank, case)[0] == []
    assert rb.check_bank(bank, cases) == 0


def test_check_mode_accepts_two_node_cards_without_running_them(tmp_path, capsys):
    root = _bank_v5(tmp_path, CARD)
    assert rb.main(["--bank", str(root), "--model", "fake:7b", "--check"]) == 0
    out = capsys.readouterr().out
    assert "dos nodos" in out
    assert "Para cada código" not in out


def test_circle_fields_without_two_nodes_are_rejected(tmp_path):
    card = CARD.replace("Dos nodos:     sí\n", "")
    root = _bank_v5(tmp_path, card)
    case = rb.parse_cases(rb.detect_bank(root).cases_file)[0]
    problems = rb.validate_case(rb.detect_bank(root), case)[0]
    assert any("Dos nodos" in problem for problem in problems)


def test_two_node_report_fields_and_v5_rules():
    receipt = {"envios": [
        {"clase": "circulo", "destino": "nodo a", "circle_id": "c1",
         "circle_name": "Circle", "member_name": "Member", "passages": 2,
         "tipo": "pasajes"},
        {"clase": "terceros", "destino": "example.test", "tipo": "pregunta"},
    ]}
    ledger = [{"clase": "circulo", "destino": "nodo b", "circle_id": "c1",
               "circle_name": "Circle", "member_name": "Member",
               "passages": 2, "tipo": "pasajes"}]
    report = tn.two_node_report(
        receipt, ledger, nonmember_refused=True, circle_passages=True,
        expected_passages=True)
    assert report["envios_circulo"] == 1
    assert report["pasajes_a_pares"] == 2
    assert report["no_miembro_rechazado"] is True
    assert report["two_node_rules"] == {
        "pasajes_solo_con_permiso": True,
        "no_miembro_rechazado": True,
        "recibo_nombra_circulo_y_miembro": True,
    }
    # With the switch off, a passage to a peer is a failure.
    off = tn.two_node_report(
        receipt, ledger, nonmember_refused=True, circle_passages=False)
    assert off["two_node_rules"]["pasajes_solo_con_permiso"] is False
    # A receipt row without circle/member names is a failure.
    unnamed = {"envios": [{"clase": "circulo", "destino": "nodo a",
                           "passages": 0}]}
    no_names = tn.two_node_report(
        unnamed, [], nonmember_refused=True, circle_passages=False)
    assert no_names["two_node_rules"]["recibo_nombra_circulo_y_miembro"] is False
    # The non-member rule is not faked.
    denied = tn.two_node_report(
        receipt, ledger, nonmember_refused=False, circle_passages=True)
    assert denied["no_miembro_rechazado"] is False


def test_node_loss_assertions_on_a_canned_partial_result():
    swarm = {"status": "partial", "steps": [
        {"step": "t0", "name": "First", "status": "completed"},
        {"step": "t1", "name": "Second", "status": "failed",
         "reason": "node_lost", "detail": "worker lost"},
        {"step": "t2", "name": "Third", "status": "blocked",
         "blocked_by": ["t1"]},
    ]}
    receipt = {"envios": [{"motivo": "fragmento t0", "clase": "circulo"}]}
    report = loss.assert_partial(swarm, receipt)
    assert report["ok"] is True
    assert report["completed"] == ["t0"]
    assert report["lost"][0]["reason"] == "node_lost"
    assert report["blocked"][0]["blocked_by"] == ["t1"]
    # A complete answer must not pass the same assertions.
    complete = dict(swarm)
    complete["status"] = "complete"
    assert loss.assert_partial(complete, receipt)["ok"] is False


def test_team_csv_and_summary_format():
    rows = [
        {"modo": "local", "caso": "TEAM-01", "rep": 1, "estado": "done",
         "wall_s": 1.2, "steps_total": 2, "steps_completed": 2,
         "steps_failed": 0, "steps_blocked": 0, "remote_steps": 0,
         "roles_placed": "t0:large_model@local|t1:reasoner@local",
         "agreement": "", "envios": 0, "envios_circulo": 0,
         "pasajes_a_pares": 0, "answer": "alpha beta gamma",
         "steps": [{"step": "t0", "name": "Draft", "role_expected": "large_model",
                    "role_placed": "large_model", "node": "", "local": True,
                    "status": "completed"}]},
        {"modo": "distributed", "caso": "TEAM-01", "rep": 1, "estado": "done",
         "wall_s": 0.8, "steps_total": 2, "steps_completed": 2,
         "steps_failed": 0, "steps_blocked": 0, "remote_steps": 2,
         "roles_placed": "t0:large_model@node|t1:reasoner@node",
         "agreement": "", "envios": 2, "envios_circulo": 2,
         "pasajes_a_pares": 0, "answer": "alpha beta delta",
         "steps": [{"step": "t0", "name": "Draft", "role_expected": "large_model",
                    "role_placed": "large_model", "node": "abcdef123456",
                    "local": False, "status": "completed"}]},
    ]
    csv_rows = team._csv_rows(rows, {"TEAM-01": "alpha beta gamma"})
    assert list(csv_rows[0]) == [
        "modo", "caso", "rep", "estado", "wall_s", "steps_total",
        "steps_completed", "steps_failed", "steps_blocked", "remote_steps",
        "roles_placed", "agreement", "envios", "envios_circulo",
        "pasajes_a_pares", "error"]
    assert csv_rows[0]["agreement"] == ""
    assert csv_rows[1]["agreement"] > 0
    markdown = team.summary(rows, {"members": 2, "model": "fake:7b"})
    assert "| Mode | Rows | Completed steps | Remote steps |" in markdown
    assert "| local | TEAM-01 | Draft |" in markdown
    assert "Agreement is a word-overlap measure" in markdown


def test_a_circle_allowed_send_is_not_unauthorized():
    allowed = rb.parse_allowed_sends("cualquier envío al círculo")
    send = {"destino": "nodo a", "tipo": "fragmento", "clase": "circulo",
            "circle_id": "c1", "circle_name": "Circle", "member_name": "Member"}
    assert rb.send_authorized(send, allowed)[0] is True
    outsider = {"destino": "example.test", "tipo": "pregunta"}
    assert rb.send_authorized(outsider, allowed)[0] is False


def test_the_equipo_field_is_read():
    card = CARD.replace("Envíos permitidos: cualquier envío al círculo",
                        "Equipo:        example-write-review\n"
                        "Envíos permitidos: cualquier envío al círculo")
    # parse_cases needs a bank path; build one on the fly in a temp dir.
    import tempfile
    from pathlib import Path as _Path
    with tempfile.TemporaryDirectory() as folder:
        root = _bank_v5(_Path(folder), card)
        case = rb.parse_cases(rb.detect_bank(root).cases_file)[0]
        assert case.team == "example-write-review"


def test_two_node_check_phrases_evaluate_the_report():
    checks = ["passages to peers only with circle_passages on",
              "non-member refused",
              "receipt names the circle and the member"]
    report = {"two_node_rules": {
        "pasajes_solo_con_permiso": True,
        "no_miembro_rechazado": True,
        "recibo_nombra_circulo_y_miembro": True}}
    out = tn.two_node_check(checks, report)
    assert [item["cumple"] for item in out] == [True, True, True]
    report["two_node_rules"]["no_miembro_rechazado"] = False
    assert tn.two_node_check(checks, report)[1]["cumple"] is False


def test_two_node_report_fields_with_the_real_app_on_loopback(tmp_path, monkeypatch):
    """Live smoke: owner + approved member + non-member, all on loopback."""
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
            temperature=0.0, log_dir=logs)
        env.start(members=1, nonmember=True)
        team_id = env.create_team("live", [
            {"id": "s1", "name": "Draft", "role": "large_model",
             "instruction": "Write a short note: {request}"},
            {"id": "s2", "name": "Review", "role": "reasoner",
             "depends_on": ["s1"], "instruction": "Review the note: {request}"},
        ])
        played = env.ask_team("Explain a fictitious spring river.", team_id, 90)
        meta = (played.get("message") or {}).get("meta") or {}
        report = tn.two_node_report(
            meta.get("receipt") or {}, env.member_ledger(),
            nonmember_refused=env.nonmember_refused, circle_passages=False)
        assert report["envios_circulo"] >= 1
        assert report["no_miembro_rechazado"] is True
        assert report["two_node_rules"]["recibo_nombra_circulo_y_miembro"] is True
    finally:
        if env is not None:
            env.close()
        app.stop()
        fake.close()
