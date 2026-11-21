"""First-launch sandbox preparation (R-005): notice, low memory, background
state and the installer flag. No test compiles WebAssembly: the runner is a
fake and the cache manifest is written through the same code path."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from swarmbly_app import cli
from swarmbly_app import sandbox as sandbox_pkg
from swarmbly_app.events import EventBus
from swarmbly_app.recipes import CodeUnavailableError
from swarmbly_app.sandbox import cache
from swarmbly_app.sandbox.prepare import SandboxPreparation
from test_api_lce import make_client

GIB = 1024 ** 3


@pytest.fixture(autouse=True)
def _fake_installed(monkeypatch):
    """The cache rules are tested without requiring the optional extra."""
    monkeypatch.setattr(cache, "sandbox_version", lambda: (True, "0.1.5"))


class FakeRunner:
    """Writes a cache file so the manifest is classified as ready."""

    def __init__(self, root: Path, *, fail: bool = False) -> None:
        self.root = root
        self.fail = fail
        self.started = threading.Event()
        self.release = threading.Event()
        self.release.set()
        self.calls = 0

    def warm_up(self) -> dict:
        self.calls += 1
        self.started.set()
        if not self.release.wait(5):
            raise RuntimeError("test did not release the compile")
        if self.fail:
            return {"ok": False, "reason": "CANARY /home/somebody/private/path"}
        cache_dir = cache.cache_dir_for(self.root)
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "module.cwasm").write_bytes(b"x" * 4096)
        return {"ok": True, "elapsed_s": 4.5, "warm_s": 4.0,
                "peak_rss_mib": 3300.0, "wasi_python": "0.1.5"}


def make(tmp_path: Path, *, runner: FakeRunner | None = None,
         available: bool = True, free: int = 8 * GIB, bus=None) -> SandboxPreparation:
    fake = runner
    return SandboxPreparation(
        tmp_path, bus,
        available_probe=lambda: (available, "" if available else "not installed"),
        memory_probe=lambda: free,
        runner_factory=lambda root: fake if fake is not None else FakeRunner(root))


def _cache_file(tmp_path: Path) -> None:
    directory = cache.cache_dir_for(tmp_path)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "module.cwasm").write_bytes(b"x" * 2048)


def _valid_measurement(**overrides) -> dict:
    data = {"ok": True, "elapsed_s": 4.5, "warm_s": 4.0,
            "peak_rss_mib": 3300.0, "wasi_python": "0.1.5"}
    data.update(overrides)
    return data


def test_notice_only_when_extra_installed_and_cache_unready(tmp_path, monkeypatch):
    missing_extra = make(tmp_path, available=False)
    status = missing_extra.status()
    assert status["status"] == "not_installed"
    assert status["notice"] is False and status["can_prepare"] is False

    preparation = make(tmp_path)
    status = preparation.status()
    assert status["status"] == "missing" and status["notice"] is True
    assert status["expected_seconds"] > 0 and status["expected_memory_gb"] == 3.3
    assert status["minimum_free_memory_gb"] == 4.0 and status["can_prepare"] is True

    _cache_file(tmp_path)
    status = preparation.status()
    assert status["status"] == "stale" and status["notice"] is True

    cache.record_measurement(tmp_path, _valid_measurement())
    status = preparation.status()
    assert status["status"] == "ready" and status["notice"] is False
    assert status["measurement"]["elapsed_s"] == 4.5

    # A cache recorded by another wasi-python/Python version is stale again.
    monkeypatch.setattr(cache, "sandbox_version", lambda: (True, "9.9.9"))
    status = preparation.status()
    assert status["status"] == "stale" and status["notice"] is True


def test_low_memory_is_refused_without_force(tmp_path):
    fake = FakeRunner(tmp_path)
    preparation = make(tmp_path, runner=fake, free=2 * GIB)
    result = preparation.start(trigger="user")
    assert result["started"] is False and result["reason_code"] == "low_memory"
    assert fake.calls == 0 and not fake.started.is_set()
    status = preparation.status()
    assert status["status"] == "refused" and status["notice"] is True
    assert status["can_prepare"] is False and status["can_force"] is True
    assert status["forced"] is False
    assert status["last_error_code"] == "low_memory"


def test_forced_start_below_the_floor_is_recorded(tmp_path):
    bus = EventBus()
    events: list[dict] = []
    bus.subscribe(lambda event: events.append(event)
                  if event["type"] == "sandbox.prepare" else None)
    fake = FakeRunner(tmp_path)
    fake.release.clear()
    preparation = make(tmp_path, runner=fake, free=2 * GIB, bus=bus)

    result = preparation.start(trigger="user", force=True)
    assert result["started"] is True and result["reason_code"] == ""
    assert fake.started.wait(2)
    running = preparation.status()
    assert running["status"] == "preparing"
    assert running["forced"] is True
    assert running["started_free_memory_gb"] == 2.0

    fake.release.set()
    final = preparation.wait(5)
    assert final["status"] == "ready"
    assert final["forced"] is True
    assert final["started_free_memory_gb"] == 2.0
    assert final["measurement"]["peak_rss_mib"] == 3300.0
    state = cache.read_state(tmp_path)
    assert state["forced"] is True
    assert state["started_free_memory_gb"] == 2.0
    assert state["peak_rss_mib"] == 3300.0
    assert events and all(event["payload"].get("forced") is True
                          for event in events)
    assert {"preparing", "ready"} <= {
        event["payload"].get("status") for event in events}


def test_automatic_start_can_never_be_forced(tmp_path):
    fake = FakeRunner(tmp_path)
    preparation = make(tmp_path, runner=fake, free=2 * GIB)
    # Even if a caller passes force, the automatic trigger ignores it and
    # keeps the floor.
    refused = preparation.start(trigger="auto", force=True)
    assert refused["started"] is False and refused["reason_code"] == "low_memory"
    assert refused["status"]["forced"] is False
    assert fake.calls == 0


def test_api_force_starts_below_the_floor(app_state, tmp_path):
    fake = FakeRunner(tmp_path)
    preparation = make(tmp_path, runner=fake, free=2 * GIB)
    app_state.sandbox = preparation
    client = make_client(app_state)

    refused = client.post("/api/sandbox/prepare",
                          json={"consent": True})
    assert refused.status_code == 409
    assert preparation.status()["status"] == "refused"

    forced = client.post("/api/sandbox/prepare",
                         json={"consent": True, "force": True})
    assert forced.status_code == 200, forced.text
    assert forced.json()["started"] is True
    assert preparation.wait(5)["status"] == "ready"
    status = client.get("/api/sandbox").json()
    assert status["forced"] is True
    assert status["started_free_memory_gb"] == 2.0
    assert fake.calls == 1


def test_request_during_preparation_runs_without_the_code_recipe(app_state, tmp_path,
                                                                 monkeypatch):
    fake = FakeRunner(tmp_path)
    fake.release.clear()
    preparation = make(tmp_path, runner=fake)
    monkeypatch.setattr(sandbox_pkg, "available", lambda: (True, ""))
    app_state.chat.sandbox = preparation
    assert preparation.start()["started"] is True
    assert fake.started.wait(2)

    status = app_state.chat.code_status()
    assert status["available"] is False
    assert status["preparation"]["status"] == "preparing"
    assert "prepared" in status["reason"] or "code recipe" in status["reason"]
    with pytest.raises(CodeUnavailableError):
        app_state.chat.propose_code(question="total the table")

    fake.release.set()
    assert preparation.wait(5)["status"] == "ready"
    assert app_state.chat.code_status()["available"] is True


def test_background_state_transitions_and_measurement(tmp_path):
    bus = EventBus()
    events: list[dict] = []
    bus.subscribe(lambda event: events.append(event)
                  if event["type"] == "sandbox.prepare" else None)
    fake = FakeRunner(tmp_path)
    fake.release.clear()
    preparation = make(tmp_path, runner=fake, bus=bus)

    assert preparation.start(trigger="user")["started"] is True
    assert fake.started.wait(2)
    running = preparation.status()
    assert running["status"] == "preparing" and running["stage"] == "compiling"

    fake.release.set()
    final = preparation.wait(5)
    assert final["status"] == "ready"
    assert final["measurement"]["elapsed_s"] == 4.5
    assert final["measurement"]["peak_rss_mib"] == 3300.0
    assert final["notice"] is False
    assert cache.read_manifest(tmp_path)["wasi_python"] == "0.1.5"
    statuses = [event["payload"]["status"] for event in events]
    assert "preparing" in statuses and "ready" in statuses


def test_measurement_reaches_the_doctor_export(app_state, tmp_path, monkeypatch):
    from swarmbly_app import doctor_export
    fake = FakeRunner(tmp_path)
    preparation = make(tmp_path, runner=fake)
    preparation.start()
    assert preparation.wait(5)["status"] == "ready"
    app_state.sandbox = preparation
    monkeypatch.setattr(doctor_export, "_gpu",
                        lambda hardware: {"class": "unified", "count": 1})
    monkeypatch.setattr(doctor_export, "_ollama",
                        lambda url, timeout=2.0: {"reachable": False,
                                                  "model_tags": []})
    data = doctor_export.build_export(app_state)
    assert data["sandbox"]["status"] == "ready"
    assert data["sandbox"]["compile_seconds"] == 4.5
    assert data["sandbox"]["peak_memory_mib"] == 3300.0
    assert data["sandbox"]["wasi_python"] == "0.1.5"
    assert data["sandbox"]["forced"] is False


def test_failed_compile_is_visible_and_not_retried_silently(tmp_path):
    fake = FakeRunner(tmp_path, fail=True)
    preparation = make(tmp_path, runner=fake)
    assert preparation.start()["started"] is True
    final = preparation.wait(5)
    assert final["status"] == "failed"
    assert final["last_error_code"] == "sandbox_compile_failed"
    assert "CANARY" in final["last_error"]       # local detail for the UI
    assert final["notice"] is True
    assert fake.calls == 1


def test_defer_hides_the_notice_and_start_clears_it(tmp_path):
    preparation = make(tmp_path)
    assert preparation.status()["notice"] is True
    deferred = preparation.defer()
    assert deferred["notice"] is False and deferred["snoozed_until"]
    # An explicit start is still possible after «Later» and clears the snooze.
    assert preparation.start()["started"] is True
    assert preparation.status()["snoozed_until"] is None


class FakeCliPrep:
    def __init__(self, status: dict, *, start: dict | None = None,
                 final: dict | None = None) -> None:
        self._status = status
        self._start = start or {"started": True, "reason_code": "", "status": status}
        self._final = final or status
        self.started = 0
        self.force_seen: bool | None = None

    def status(self) -> dict:
        return self._status

    def start(self, *, trigger: str = "user", force: bool = False) -> dict:
        self.started += 1
        self.force_seen = force
        return self._start

    def wait(self, timeout: float) -> dict:
        return self._final


def _base_status(**overrides) -> dict:
    status = {"installed": True, "status": "missing", "expected_seconds": 5.0,
              "expected_memory_gb": 3.3, "free_memory_gb": 8.0,
              "minimum_free_memory_gb": 4.0, "last_error": "", "measurement": {}}
    status.update(overrides)
    return status


def _install_fake_cli(monkeypatch, fake: FakeCliPrep) -> None:
    monkeypatch.setattr(sandbox_pkg, "SandboxPreparation", lambda root: fake)


def test_prepare_sandbox_flag_exit_codes(tmp_path, monkeypatch):
    args = ["--prepare-sandbox", "--data-dir", str(tmp_path)]

    fake = FakeCliPrep(_base_status(installed=False, status="not_installed"))
    _install_fake_cli(monkeypatch, fake)
    assert cli.main(args) == 2

    low = _base_status(status="refused", last_error="only 2.0 GB free")
    fake = FakeCliPrep(_base_status(), start={"started": False,
                                              "reason_code": "low_memory",
                                              "status": low})
    _install_fake_cli(monkeypatch, fake)
    assert cli.main(args) == 3
    assert fake.force_seen is False

    failed = _base_status(status="failed", last_error="compile failed")
    fake = FakeCliPrep(_base_status(), start={"started": True, "reason_code": "",
                                              "status": _base_status(status="preparing")},
                       final=failed)
    _install_fake_cli(monkeypatch, fake)
    assert cli.main(args) == 1

    ready = _base_status(status="ready", measurement={"elapsed_s": 4.5,
                                                      "peak_rss_mib": 3300.0})
    fake = FakeCliPrep(_base_status(), start={"started": True, "reason_code": "",
                                              "status": _base_status(status="preparing")},
                       final=ready)
    _install_fake_cli(monkeypatch, fake)
    assert cli.main(args) == 0

    already = FakeCliPrep(ready)
    _install_fake_cli(monkeypatch, already)
    assert cli.main(args) == 0
    assert already.started == 0


def test_prepare_sandbox_force_flag(tmp_path, monkeypatch):
    ready = _base_status(status="ready", measurement={"elapsed_s": 4.5,
                                                      "peak_rss_mib": 3300.0})
    fake = FakeCliPrep(
        _base_status(), start={"started": True, "reason_code": "",
                               "status": _base_status(status="preparing")},
        final=ready)
    _install_fake_cli(monkeypatch, fake)
    assert cli.main(["--prepare-sandbox", "--force",
                     "--data-dir", str(tmp_path)]) == 0
    assert fake.force_seen is True


def test_ui_force_strings_exist_in_english_and_spanish():
    base = Path(__file__).resolve().parents[1] / "swarmbly_app" / "web" / "i18n"
    for language in ("en", "es"):
        data = json.loads((base / f"{language}.json").read_text(encoding="utf-8"))
        sandbox = data["sandbox"]
        for key in ("prepareAnyway", "forceWarning", "forcingToast", "forcedNote"):
            assert sandbox.get(key), (language, key)
    english = json.loads((base / "en.json").read_text(encoding="utf-8"))["sandbox"]
    spanish = json.loads((base / "es.json").read_text(encoding="utf-8"))["sandbox"]
    assert "Prepare anyway" in english["prepareAnyway"]
    assert "Preparar de todos modos" in spanish["prepareAnyway"]
    assert "swap" in english["forceWarning"] and "swap" in spanish["forceWarning"]
    ui = (base.parent / "js" / "app.js").read_text(encoding="utf-8")
    assert "sandbox.prepareAnyway" in ui
    assert "sandbox.forceWarning" in ui
    assert "s.can_force" in ui


def test_force_with_enough_memory_is_not_recorded_as_forced(tmp_path):
    """--force on a machine above the floor changes nothing and is not
    reported as an override."""
    prep = make(tmp_path, free=8 * GIB)
    started = prep.start(trigger="installer", force=True)
    assert started["started"] is True
    status = prep.wait(30)
    assert status.get("forced") is False
