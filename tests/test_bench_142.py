"""Harness 1.4.2: the recipe-5 sandbox is prepared before a code card."""
from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bench"))
import run_bank as rb  # noqa: E402


class FakeSandboxApp:
    """A local stand-in for the App's /api/sandbox routes."""

    def __init__(self, initial: str, *, low_memory: bool = False,
                 finish: str = "ready", polls: int = 2) -> None:
        self.state = initial
        self.low_memory = low_memory
        self.finish = finish
        self.polls_left = polls
        self.posts: list[dict] = []
        self.token = "tok"
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # noqa: D401 - silence
                return

            def _send(self, code: int, body: dict) -> None:
                raw = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):  # noqa: N802
                assert self.headers.get("X-Swarmbly-Token") == "tok"
                if owner.state == "preparing":
                    owner.polls_left -= 1
                    if owner.polls_left <= 0:
                        owner.state = owner.finish
                body = {"status": owner.state, "elapsed_s": 4.2,
                        "started_free_memory_gb": 3.1 if owner.low_memory else 9.0,
                        "forced": bool(owner.low_memory and any(
                            p.get("force") for p in owner.posts)),
                        "last_error_code": "compile_failed" if owner.state == "failed" else ""}
                self._send(200, body)

            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                owner.posts.append(body)
                if owner.low_memory and body.get("force") is not True:
                    self._send(409, {"detail": "3.1 GB free; at least 4 GB are required"})
                    return
                owner.state = "preparing"
                self._send(200, {"started": True})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()


@pytest.fixture
def make_app():
    apps: list[FakeSandboxApp] = []

    def factory(*args, **kwargs) -> FakeSandboxApp:
        app = FakeSandboxApp(*args, **kwargs)
        apps.append(app)
        return app

    yield factory
    for app in apps:
        app.close()


def test_harness_version_is_143():
    assert rb.HARNESS_VERSION == "1.4.5"


def test_a_ready_sandbox_is_not_prepared_again(make_app):
    app = make_app("ready")
    record = rb.prepare_sandbox(app, poll=0.01)
    assert record["estado"] == "ready" and record["forzado"] is False
    assert app.posts == []


def test_a_missing_sandbox_is_prepared_with_consent_and_awaited(make_app):
    app = make_app("missing", polls=3)
    record = rb.prepare_sandbox(app, poll=0.01)
    assert app.posts == [{"consent": True}]
    assert record == {"forzado": False, "inicial": "missing", "estado": "ready",
                      "segundos": 4.2, "memoria_libre_gb": 9.0, "forzado_app": False}


def test_below_the_memory_floor_the_override_is_used_and_recorded(make_app):
    app = make_app("missing", low_memory=True)
    record = rb.prepare_sandbox(app, poll=0.01)
    assert app.posts == [{"consent": True}, {"consent": True, "force": True}]
    assert record["forzado"] is True and record["forzado_app"] is True


def test_a_failed_preparation_is_a_technical_failure(make_app):
    app = make_app("missing", finish="failed")
    with pytest.raises(RuntimeError, match="failed: compile_failed"):
        rb.prepare_sandbox(app, poll=0.01)


def test_an_app_without_the_sandbox_extra_is_refused(make_app):
    app = make_app("not_installed")
    with pytest.raises(RuntimeError, match=r"\[sandbox\] extra"):
        rb.prepare_sandbox(app, poll=0.01)
    assert app.posts == []


def test_preparation_has_a_deadline(make_app):
    app = make_app("missing", polls=10_000)
    with pytest.raises(RuntimeError, match="did not finish"):
        rb.prepare_sandbox(app, timeout=0.05, poll=0.01)


def test_the_code_card_paths_call_the_preparation():
    bank = (Path(rb.__file__)).read_text(encoding="utf-8")
    dev = (Path(rb.__file__).with_name("run_dev.py")).read_text(encoding="utf-8")
    assert 'if case.recipe == "code":\n                        actions["sandbox"] = prepare_sandbox(app)' in bank
    assert 'row["sandbox"] = rb.prepare_sandbox(app)' in dev


# 1.4.3: «Archivo de salida: ninguno» means the card expects no file.
@pytest.mark.parametrize("raw", ["ninguno", "Ninguno.", "ninguna", "No", "no aplica",
                                 "N/A", "—", "-", "sin archivo", "Ninguno (solo texto)"])
def test_no_output_file_is_empty(raw):
    assert rb._output_field(raw) == ""


@pytest.mark.parametrize("raw", ["resultado.csv", "notas_finales.md (filas: 3)",
                                 "nombres.csv (columnas: a, b; filas: 2)"])
def test_a_named_output_file_is_kept(raw):
    assert rb._output_field(raw) == raw


def test_a_card_with_no_output_file_passes_the_check_field(tmp_path):
    block = ("ID: S4-01\nNivel: N7\nCapacidades: código\nPregunta: x\nReceta: código\n"
             "Archivos: datos.csv\nScript: aprobar\nArchivo de salida: ninguno\n"
             "Envíos permitidos: ninguno\n")
    cases_file = tmp_path / "casos.md"
    cases_file.write_text("```text\n" + block + "```\n", encoding="utf-8")
    case = rb.parse_cases(cases_file)[0]
    assert case.output_file == ""
