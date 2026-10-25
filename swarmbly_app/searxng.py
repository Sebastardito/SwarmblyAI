"""Optional local SearXNG: public web evidence through free search engines.

SearXNG is a free metasearch engine (AGPL-3.0). Installed on request, with the
user's consent, it runs on this computer only (``127.0.0.1``) and lets the
evidence layer reach DuckDuckGo, Google, Google Scholar, Bing, Brave, Mojeek
and scholarly indexes (PubMed, Semantic Scholar, OpenAlex, Crossref, arXiv)
without API keys. As for every public source, only entity names are searched.

Two ways to run it, chosen automatically:

* ``docker``: the official ``searxng/searxng`` image, when Docker is running.
* ``native``: SearXNG's source in the app's data directory with its own
  virtual environment (Python 3.11 or newer, or ``uv`` to provide one). The
  process starts and stops with the app.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

SOURCE_URL = "https://codeload.github.com/searxng/searxng/tar.gz/refs/heads/master"
IMAGE = "docker.io/searxng/searxng:latest"
CONTAINER = "swarmbly-searxng"
DEFAULT_PORT = 8888
GENERAL = ["duckduckgo", "google", "bing", "brave", "mojeek", "wikipedia"]
SCIENCE = ["google scholar", "pubmed", "semantic scholar", "openalex", "crossref", "arxiv"]
METHODS = ("auto", "docker", "native")
MIN_PYTHON = (3, 11)       # SearXNG imports tomllib


def settings_yaml(port: int, secret: str, docker: bool = False) -> str:
    """SearXNG settings: JSON output on, rate limiter off (local use only)."""
    bind = "0.0.0.0" if docker else "127.0.0.1"   # docker publishes on 127.0.0.1 only
    keep = ", ".join(GENERAL + SCIENCE)
    enable = "".join(f"  - name: {name}\n    disabled: false\n" for name in SCIENCE)
    return (
        "# Written by Swarmbly App. Local use only: never expose this port.\n"
        "use_default_settings:\n"
        "  engines:\n"
        f"    keep_only: [{keep}]\n"
        "general:\n"
        "  instance_name: swarmbly-local\n"
        "search:\n"
        "  safe_search: 0\n"
        "  formats: [html, json]\n"
        "server:\n"
        f"  bind_address: \"{bind}\"\n"
        f"  port: {8080 if docker else port}\n"
        f"  secret_key: \"{secret}\"\n"
        "  limiter: false\n"
        "  public_instance: false\n"
        "  image_proxy: false\n"
        "outgoing:\n"
        "  request_timeout: 4.0\n"
        "engines:\n" + enable)


def healthy(url: str, timeout: float = 8.0) -> bool:
    """True when ``url`` answers a JSON search (results may be empty offline)."""
    try:
        req = urllib.request.Request(
            url.rstrip("/") + "/search?" + urllib.parse.urlencode(
                {"q": "Galapagos", "format": "json"}),
            headers={"User-Agent": "SwarmblyApp"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (local)
            data = json.loads(resp.read().decode("utf-8", "replace"))
        return isinstance(data, dict) and "results" in data
    except Exception:
        return False


def free_port(start: int = DEFAULT_PORT, span: int = 12) -> int:
    for port in range(start, start + span):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError(f"no free port in {start}-{start + span - 1}")


def _run(cmd: list[str], timeout: float = 60, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return _run(["docker", "info", "--format", "{{.ServerVersion}}"], 15).returncode == 0
    except Exception:
        return False


def _py_version(exe: str) -> tuple[int, int] | None:
    try:
        out = _run([exe, "-c", "import sys; print(*sys.version_info[:2])"], 15).stdout.split()
        return int(out[0]), int(out[1])
    except Exception:
        return None


def find_python() -> tuple[str, str] | None:
    """``("python", path)`` for a Python ≥ 3.11, else ``("uv", path)``, else None."""
    if sys.version_info[:2] >= MIN_PYTHON:
        return "python", sys.executable
    names = ["python3.13", "python3.12", "python3.11"]
    dirs = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]
    seen = [shutil.which(n) for n in names] + [f"{d}/{n}" for d in dirs for n in names]
    for exe in filter(None, seen):
        if os.path.exists(exe) and (_py_version(exe) or (0, 0)) >= MIN_PYTHON:
            return "python", exe
    uv = shutil.which("uv") or next((p for p in (str(Path.home() / ".local/bin/uv"),
                                                 "/opt/homebrew/bin/uv") if os.path.exists(p)), None)
    return ("uv", uv) if uv else None


def safe_extract(archive: Path, dest: Path) -> Path:
    """Extract a source tarball refusing absolute paths, ``..`` and links out."""
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        for m in members:
            target = (root / m.name).resolve()
            if not str(target).startswith(str(root) + os.sep) and target != root:
                raise RuntimeError(f"unsafe path in archive: {m.name}")
            if m.issym() or m.islnk():
                link = (target.parent / m.linkname).resolve()
                if not str(link).startswith(str(root) + os.sep):
                    raise RuntimeError(f"unsafe link in archive: {m.name}")
            if m.isdev():
                raise RuntimeError(f"device file in archive: {m.name}")
        try:
            tar.extractall(root, members=members, filter="data")
        except TypeError:          # Python without extraction filters
            tar.extractall(root, members=members)  # noqa: S202 (checked above)
    tops = {m.name.split("/", 1)[0] for m in members if m.name}
    if len(tops) != 1:
        raise RuntimeError("unexpected archive layout")
    return root / tops.pop()


@dataclass
class SearxJob:
    method: str
    status: str = "pending"       # pending|running|done|failed|refused
    step: str = ""
    log: list[str] = field(default_factory=list)


class SearxngManager:
    """Install, start, stop and remove the local SearXNG (consent required)."""

    def __init__(self, root: Path, bus, get_config: Callable[[], dict[str, Any]],
                 update_config: Callable[[dict[str, Any]], Any]):
        self.dir = Path(root) / "searxng"
        self.bus = bus
        self.get_config = get_config
        self.update_config = update_config
        self.job: SearxJob | None = None
        self.proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    # -- paths --------------------------------------------------------------------------
    @property
    def settings_path(self) -> Path:
        return self.dir / "settings.yml"

    @property
    def venv_python(self) -> Path:
        sub = "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
        return self.dir / "venv" / sub

    @property
    def pid_path(self) -> Path:
        return self.dir / "searxng.pid"

    def _ev(self) -> dict[str, Any]:
        return self.get_config().get("evidence") or {}

    # -- status ---------------------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        ev = self._ev()
        url, method = str(ev.get("searxng_url") or ""), str(ev.get("searxng_managed") or "")
        job = self.job
        return {
            "managed": method, "url": url,
            "running": bool(url) and healthy(url, 3.0),
            "web_enabled": "web" in (ev.get("providers") or []),
            "docker": bool(shutil.which("docker")),
            "python": (find_python() or ("", ""))[0],
            "job": None if job is None else {"method": job.method, "status": job.status,
                                              "step": job.step, "log": job.log[-20:]},
        }

    # -- install ----------------------------------------------------------------------------
    def install(self, method: str = "auto", consent: bool = False) -> SearxJob:
        job = SearxJob(method=method)
        perms = self.get_config().get("permissions") or {}
        if not consent:
            job.status, job.log = "refused", ["explicit consent is required"]
        elif method not in METHODS:
            job.status, job.log = "refused", [f"method must be one of {list(METHODS)}"]
        elif perms.get("internet") is False:
            job.status, job.log = "refused", ["internet access was refused in Permissions"]
        if job.status == "refused":
            return job
        with self._lock:
            if self.job and self.job.status == "running":
                job.status, job.log = "refused", ["another SearXNG installation is running"]
                return job
            self.job = job
        threading.Thread(target=self._install, args=(job,), daemon=True,
                         name="swarmbly-searxng").start()
        return job

    def _say(self, job: SearxJob, step: str, line: str = "") -> None:
        job.step = step
        if line:
            job.log.append(line)
        self.bus.publish("searxng.install", status=job.status, step=step, method=job.method)

    def _install(self, job: SearxJob) -> None:
        job.status = "running"
        try:
            method = job.method
            if method == "auto":
                method = "docker" if docker_available() else "native"
            elif method == "docker" and not docker_available():
                raise RuntimeError("Docker is not installed or not running")
            job.method = method
            self.stop()
            self.dir.mkdir(parents=True, exist_ok=True)
            port = free_port()
            self.settings_path.write_text(
                settings_yaml(port, secrets.token_hex(32), docker=method == "docker"),
                encoding="utf-8")
            url = f"http://127.0.0.1:{port}"
            if method == "docker":
                self._install_docker(job, port)
            else:
                self._install_native(job)
                self._start_native(port)
            self._say(job, "health", f"waiting for {url}")
            deadline = time.monotonic() + 90
            while not healthy(url, 4.0):
                if self.proc is not None and self.proc.poll() is not None:
                    raise RuntimeError("SearXNG exited; see searxng.log in the data folder")
                if time.monotonic() > deadline:
                    raise RuntimeError(f"SearXNG did not answer on {url}")
                time.sleep(2)
            providers = list(self._ev().get("providers") or ["wikidata", "wikipedia", "pubmed"])
            if "web" not in providers:
                providers.append("web")
            self.update_config({"evidence.searxng_url": url, "evidence.searxng_managed": method,
                                "evidence.providers": providers})
            job.status = "done"
            self._say(job, "done", f"SearXNG ({method}) running on {url}")
        except Exception as exc:
            job.status = "failed"
            self._say(job, "failed", str(exc))

    def _install_docker(self, job: SearxJob, port: int) -> None:
        self._say(job, "pull", f"docker pull {IMAGE}")
        pull = _run(["docker", "pull", IMAGE], 900)
        if pull.returncode != 0:
            raise RuntimeError((pull.stderr or pull.stdout).strip()[-400:])
        _run(["docker", "rm", "-f", CONTAINER], 60)
        self._say(job, "start", "docker run")
        run = _run(["docker", "run", "-d", "--name", CONTAINER,
                    "-p", f"127.0.0.1:{port}:8080",
                    "-v", f"{self.dir}:/etc/searxng:rw",
                    "-e", "SEARXNG_BIND_ADDRESS=0.0.0.0", "-e", "SEARXNG_PORT=8080",
                    IMAGE], 120)
        if run.returncode != 0:
            raise RuntimeError((run.stderr or run.stdout).strip()[-400:])

    def _install_native(self, job: SearxJob) -> None:
        found = find_python()
        if not found:
            raise RuntimeError("SearXNG needs Python 3.11 or newer (or uv, or Docker); "
                               "none was found")
        kind, exe = found
        self._say(job, "download", f"downloading {SOURCE_URL}")
        archive = self.dir / "searxng-src.tar.gz"
        req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "SwarmblyApp"})
        with urllib.request.urlopen(req, timeout=120) as resp, open(archive, "wb") as out:  # noqa: S310
            shutil.copyfileobj(resp, out)
        if (self.dir / "src").exists():
            shutil.rmtree(self.dir / "src")
        top = safe_extract(archive, self.dir / "src-tmp")
        top.rename(self.dir / "src")
        shutil.rmtree(self.dir / "src-tmp", ignore_errors=True)
        archive.unlink(missing_ok=True)
        venv = self.dir / "venv"
        if venv.exists():
            shutil.rmtree(venv)
        self._say(job, "venv", f"virtual environment with {kind} ({exe})")
        reqs = str(self.dir / "src" / "requirements.txt")
        if kind == "uv":
            steps = [[exe, "venv", "-q", "-p", "3.12", str(venv)],
                     [exe, "pip", "install", "-q", "-p", str(self.venv_python), "-r", reqs]]
        else:
            steps = [[exe, "-m", "venv", str(venv)],
                     [str(self.venv_python), "-m", "pip", "install", "-q", "--upgrade", "pip"],
                     [str(self.venv_python), "-m", "pip", "install", "-q", "-r", reqs]]
        for cmd in steps:
            self._say(job, "packages" if "install" in cmd else "venv", " ".join(cmd[:4]))
            proc = _run(cmd, 900)
            if proc.returncode != 0:
                raise RuntimeError((proc.stderr or proc.stdout).strip()[-600:])

    # -- lifecycle ----------------------------------------------------------------------------
    def _start_native(self, port: int | None = None) -> None:
        if not self.venv_python.exists():
            raise RuntimeError("SearXNG is not installed")
        env = dict(os.environ, SEARXNG_SETTINGS_PATH=str(self.settings_path))
        log = open(self.dir / "searxng.log", "ab")
        self.proc = subprocess.Popen(
            [str(self.venv_python), "-m", "searx.webapp"], cwd=str(self.dir / "src"),
            env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            start_new_session=True)
        self.pid_path.write_text(str(self.proc.pid), encoding="utf-8")

    def autostart(self) -> None:
        """Start the managed SearXNG with the app (no-op when not installed)."""
        ev = self._ev()
        method, url = ev.get("searxng_managed"), str(ev.get("searxng_url") or "")
        if not method or not url or healthy(url, 2.0):
            return
        try:
            if method == "docker":
                _run(["docker", "start", CONTAINER], 60)
            else:
                self._start_native()
        except Exception as exc:
            self.bus.publish("searxng.install", status="failed", step="autostart",
                             method=method, detail=str(exc))

    def stop(self) -> None:
        method = self._ev().get("searxng_managed")
        if self.proc is not None:
            self._terminate(self.proc.pid)
            try:
                self.proc.wait(timeout=8)
            except Exception:
                pass
            self.proc = None
        elif self.pid_path.exists():
            try:
                pid = int(self.pid_path.read_text().strip())
                if _is_searx(pid):
                    self._terminate(pid)
            except (ValueError, OSError):
                pass
        self.pid_path.unlink(missing_ok=True)
        if method == "docker" and shutil.which("docker"):
            try:
                _run(["docker", "stop", CONTAINER], 60)
            except Exception:
                pass

    @staticmethod
    def _terminate(pid: int) -> None:
        try:
            if sys.platform == "win32":
                os.kill(pid, signal.SIGTERM)
            else:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass

    def uninstall(self) -> dict[str, Any]:
        method = self._ev().get("searxng_managed")
        self.stop()
        if method == "docker" and shutil.which("docker"):
            _run(["docker", "rm", "-f", CONTAINER], 60)
        for sub in ("src", "venv", "src-tmp"):
            shutil.rmtree(self.dir / sub, ignore_errors=True)
        ev = self._ev()
        changes: dict[str, Any] = {"evidence.searxng_url": "", "evidence.searxng_managed": ""}
        if not (ev.get("google_cse_key") and ev.get("google_cse_cx")):
            changes["evidence.providers"] = [p for p in (ev.get("providers") or []) if p != "web"]
        self.update_config(changes)
        self.job = None
        return self.status()


def _is_searx(pid: int) -> bool:
    """Only signal a leftover PID if it still is our SearXNG process."""
    try:
        out = _run(["ps", "-p", str(pid), "-o", "command="], 5).stdout
        return "searx.webapp" in out
    except Exception:
        return False
