"""Optional local SearXNG: settings, consent, safe extraction, lifecycle, web check."""

from __future__ import annotations

import io
import tarfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from swarmbly_app import searxng as sx
from swarmbly_app.engine.providers import WebSearchProvider, web_check
from fastapi.testclient import TestClient

from swarmbly_app.api import create_app


def make_client(app_state):
    app = create_app(app_state)
    client = TestClient(app, base_url="http://127.0.0.1:8765")
    client.headers["X-Swarmbly-Token"] = app.state.guard.token
    return client


class Bus:
    def __init__(self):
        self.events = []

    def publish(self, kind, **payload):
        self.events.append((kind, payload))


def manager(tmp_path, cfg=None):
    cfg = cfg if cfg is not None else {"evidence": {"providers": ["wikidata", "wikipedia", "pubmed"],
                                                    "searxng_url": "", "searxng_managed": "",
                                                    "google_cse_key": "", "google_cse_cx": ""},
                                       "permissions": {}}

    def update(changes):
        for key, value in changes.items():
            node = cfg
            *parts, last = key.split(".")
            for p in parts:
                node = node[p]
            node[last] = value
        return cfg
    return sx.SearxngManager(tmp_path, Bus(), lambda: cfg, update), cfg


class TestSettings:
    def test_native_listens_on_loopback_with_json(self):
        text = sx.settings_yaml(8890, "s3cret")
        assert 'bind_address: "127.0.0.1"' in text and "port: 8890" in text
        assert "formats: [html, json]" in text and "limiter: false" in text
        assert "google scholar" in text and "duckduckgo" in text
        assert "- name: pubmed\n    disabled: false" in text

    def test_docker_binds_inside_the_container(self):
        text = sx.settings_yaml(8890, "s3cret", docker=True)
        assert 'bind_address: "0.0.0.0"' in text and "port: 8080" in text


class TestConsent:
    def test_refused_without_consent(self, tmp_path):
        m, _ = manager(tmp_path)
        assert m.install("auto", consent=False).status == "refused"

    def test_refused_when_internet_is_denied(self, tmp_path):
        m, cfg = manager(tmp_path)
        cfg["permissions"]["internet"] = False
        assert m.install("auto", consent=True).status == "refused"

    def test_refused_unknown_method(self, tmp_path):
        m, _ = manager(tmp_path)
        assert m.install("brew", consent=True).status == "refused"


def _tar(entries):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in entries:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class TestExtract:
    def test_extracts_single_top_folder(self, tmp_path):
        arc = tmp_path / "a.tgz"
        arc.write_bytes(_tar([("searxng-master/requirements.txt", b"flask\n"),
                              ("searxng-master/searx/__init__.py", b"")]))
        top = sx.safe_extract(arc, tmp_path / "out")
        assert top.name == "searxng-master" and (top / "requirements.txt").read_text() == "flask\n"

    def test_rejects_path_traversal(self, tmp_path):
        arc = tmp_path / "a.tgz"
        arc.write_bytes(_tar([("searxng-master/ok.txt", b""), ("../evil.txt", b"x")]))
        with pytest.raises(RuntimeError):
            sx.safe_extract(arc, tmp_path / "out")
        assert not (tmp_path / "evil.txt").exists()


class _Handler(BaseHTTPRequestHandler):
    body = b'{"results": []}'

    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *a):
        pass


@pytest.fixture()
def server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()


class TestHealth:
    def test_json_search_is_healthy(self, server):
        _Handler.body = b'{"results": []}'
        assert sx.healthy(f"http://127.0.0.1:{server.server_port}")

    def test_html_is_not(self, server):
        _Handler.body = b"<html>no json</html>"
        assert not sx.healthy(f"http://127.0.0.1:{server.server_port}")

    def test_nothing_listening(self):
        assert not sx.healthy("http://127.0.0.1:9", 0.5)


class TestLifecycle:
    def test_install_enables_web_and_records_url(self, tmp_path, monkeypatch):
        m, cfg = manager(tmp_path)
        monkeypatch.setattr(sx, "docker_available", lambda: False)
        monkeypatch.setattr(m, "_install_native", lambda job: None)
        monkeypatch.setattr(m, "_start_native", lambda port=None: None)
        monkeypatch.setattr(sx, "healthy", lambda url, timeout=8.0: True)
        job = m.install("auto", consent=True)
        for _ in range(100):
            if job.status in ("done", "failed"):
                break
            time.sleep(0.05)
        assert job.status == "done", job.log
        ev = cfg["evidence"]
        assert ev["searxng_managed"] == "native" and ev["searxng_url"].startswith("http://127.0.0.1:")
        assert ev["providers"] == ["wikidata", "wikipedia", "pubmed", "web"]
        assert 'bind_address: "127.0.0.1"' in m.settings_path.read_text()

    def test_docker_requested_but_missing_fails(self, tmp_path, monkeypatch):
        m, _ = manager(tmp_path)
        monkeypatch.setattr(sx, "docker_available", lambda: False)
        job = m.install("docker", consent=True)
        for _ in range(100):
            if job.status in ("done", "failed"):
                break
            time.sleep(0.05)
        assert job.status == "failed" and "Docker" in job.log[-1]

    def test_uninstall_drops_web_unless_google_is_set(self, tmp_path):
        m, cfg = manager(tmp_path)
        cfg["evidence"].update(searxng_url="http://127.0.0.1:8888", searxng_managed="native",
                               providers=["wikidata", "web"])
        (tmp_path / "searxng" / "venv").mkdir(parents=True)
        m.uninstall()
        assert cfg["evidence"]["providers"] == ["wikidata"]
        assert cfg["evidence"]["searxng_url"] == "" and cfg["evidence"]["searxng_managed"] == ""
        assert not (tmp_path / "searxng" / "venv").exists()
        cfg["evidence"].update(searxng_managed="native", providers=["wikidata", "web"],
                               google_cse_key="k", google_cse_cx="c")
        m.uninstall()
        assert cfg["evidence"]["providers"] == ["wikidata", "web"]

    def test_autostart_does_nothing_when_not_installed(self, tmp_path, monkeypatch):
        m, _ = manager(tmp_path)
        monkeypatch.setattr(m, "_start_native", lambda port=None: (_ for _ in ()).throw(AssertionError))
        m.autostart()


class TestWebSearch:
    def test_searxng_asks_general_and_science(self):
        seen = []
        p = WebSearchProvider(url="http://127.0.0.1:8888", fetch=lambda u, t, a: seen.append(u) or {"results": []})
        p.passages("Philornis downsi", ["Galapagos"])
        assert "categories=general%2Cscience" in seen[0] and "format=json" in seen[0]

    def test_web_check_reports_engines(self):
        data = {"results": [{"title": "Galápagos", "engines": ["duckduckgo", "google scholar"]}],
                "unresponsive_engines": [["google", "CAPTCHA"]]}
        r = web_check({"searxng_url": "http://x", "providers": ["web"]}, fetch=lambda u, t, a: data)
        assert r["ok"] and r["engines"] == ["duckduckgo", "google scholar"]
        assert r["unresponsive"] == ["google"] and r["web_enabled"]

    def test_web_check_google_and_nothing(self):
        r = web_check({"google_cse_key": "k", "google_cse_cx": "c"},
                      fetch=lambda u, t, a: {"items": [{"title": "G"}]})
        assert r["ok"] and r["provider"] == "google" and not r["web_enabled"]
        assert not web_check({})["ok"]


class TestApi:
    def test_status_and_consent_over_http(self, app_state):
        client = make_client(app_state)
        s = client.get("/api/evidence/searxng").json()
        assert s["managed"] == "" and s["running"] is False and s["job"] is None
        assert client.post("/api/evidence/searxng/install", json={}).status_code == 400

    def test_managed_value_is_validated(self, app_state):
        client = make_client(app_state)
        assert client.put("/api/config", json={"evidence.searxng_managed": "brew"}).status_code == 400
        assert client.put("/api/config", json={"evidence.searxng_managed": "native"}).status_code == 200

    def test_web_test_without_configuration(self, app_state):
        client = make_client(app_state)
        r = client.post("/api/evidence/web/test").json()
        assert r["ok"] is False and r["error"]


class TestWebDedup:
    def test_skips_pages_of_providers_already_asked(self):
        data = {"results": [
            {"title": "Floreana mockingbird - Wikipedia", "content": "The Floreana mockingbird is endangered.",
             "url": "https://en.wikipedia.org/wiki/Floreana_mockingbird"},
            {"title": "Floreana Mockingbird Factsheet", "content": "Floreana mockingbird endangered factsheet.",
             "url": "https://datazone.birdlife.org/species/factsheet/floreana-mockingbird"}]}
        p = WebSearchProvider(url="http://x", fetch=lambda u, t, a: data, skip_hosts=("wikipedia.org",))
        got = p.passages("Floreana mockingbird", ["endangered"])
        assert got and "birdlife" in got["url"]

    def test_build_skips_enabled_providers_hosts(self):
        from swarmbly_app.engine.providers import build
        mp = build("en", {"providers": ["wikipedia", "web"], "searxng_url": "http://x"}, wikipedia=None)
        assert mp.web.skip_hosts == ("wikipedia.org",)
