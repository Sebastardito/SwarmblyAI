"""Dependency checks and consented model downloads (fake Ollama transport)."""

from __future__ import annotations

import json
import time

import httpx
import pytest

from swarmbly_app.doctor import Installer, check_python_packages, run_checks
from swarmbly_app.model_manager import OllamaModels


def fake_ollama(pulled: list[str]):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/pull":
            name = json.loads(request.content)["model"]
            pulled.append(name)
            lines = [{"status": "pulling manifest"},
                     {"status": "downloading", "total": 1000, "completed": 500},
                     {"status": "downloading", "total": 1000, "completed": 1000},
                     {"status": "success"}]
            return httpx.Response(200, content="\n".join(json.dumps(x) for x in lines))
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"license": "Apache License 2.0 ...",
                                             "details": {"family": "qwen2"}})
        return httpx.Response(404)
    return httpx.MockTransport(handler)


@pytest.fixture()
def models(app_state, tmp_path):
    pulled: list[str] = []
    mgr = OllamaModels(app_state.bus, lambda: "http://ollama.test", lambda: tmp_path,
                       transport=fake_ollama(pulled))
    return mgr, pulled


def wait(job, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline and job.status in ("pending", "running"):
        time.sleep(0.05)
    return job


class TestModelDownloads:
    def test_preview_shows_size_licence_page_and_space(self, models):
        mgr, _ = models
        p = mgr.preview("qwen2.5:3b")
        assert p["known"] and p["download_gb"] == 1.9
        assert "non-commercial" in p["license"]
        assert p["page"].startswith("https://ollama.com/library/")
        assert "free_disk_gb" in p and "enough_space" in p

    def test_no_consent_no_download(self, models):
        mgr, pulled = models
        job = mgr.start_pull("qwen2.5:1.5b", consent=False)
        assert job.status == "failed" and pulled == []

    def test_consented_pull_reports_progress_and_licence(self, models, app_state):
        mgr, pulled = models
        events = []
        app_state.bus.subscribe(lambda e: events.append(e)
                                if e["type"] == "models.pull" else None)
        job = wait(mgr.start_pull("qwen2.5:1.5b", consent=True))
        assert job.status == "done", job.detail
        assert pulled == ["qwen2.5:1.5b"]
        assert job.completed == job.total == 1000
        assert job.license.startswith("Apache")
        assert events[-1]["payload"]["status"] == "done"

    def test_invalid_name_rejected(self, models):
        mgr, _ = models
        with pytest.raises(ValueError):
            mgr.preview("../../etc/passwd")


class TestDoctor:
    def test_required_packages_present(self):
        statuses = {p["name"]: p["status"] for p in check_python_packages()}
        assert statuses["fastapi"] == "ok" and statuses["zeroconf"] == "ok"
        assert statuses["swarmbly-v0"] in ("ok", "pin_mismatch")

    def test_report_shape(self, app_state):
        report = run_checks(app_state)
        assert report["python"]["status"] == "ok"
        assert report["ollama"]["status"] in ("ok", "not_running", "missing")
        assert "fix" in report["ollama"] or report["ollama"]["status"] == "ok"

    def test_installer_requires_consent_and_known_packages(self, app_state):
        inst = Installer(app_state.bus)
        assert inst.start(["zeroconf"], consent=False).status == "refused"
        assert inst.start(["requests-evil"], consent=True).status == "refused"

    def test_api_pull_respects_permission(self, app_state):
        from fastapi.testclient import TestClient
        from swarmbly_app.api import create_app
        app = create_app(app_state)
        c = TestClient(app, base_url="http://127.0.0.1:8765")
        c.headers["X-Swarmbly-Token"] = app.state.guard.token
        app_state.config.update({"permissions.model_downloads": False})
        r = c.post("/api/models/pull", json={"name": "qwen2.5:1.5b", "consent": True})
        assert r.status_code == 403
