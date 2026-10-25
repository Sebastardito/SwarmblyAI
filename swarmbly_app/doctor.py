"""Dependency and environment checks (product spec §4.2).

For each dependency: what it is for, whether it is required or optional, the
version found versus required, and — when missing — how it can be installed.

Installation rules:

- Only Python packages declared by Swarmbly App are installed, and only into
  the app's own virtual environment (never the system Python). Outside a
  virtual environment the app shows the command instead of running it.
- Nothing is installed without an explicit consent flag in the request, and
  the result is verified by importing the package again.
- External programs (Ollama) need an installer and possibly administrator
  rights: the app explains and links, it does not install them.
- Models are not dependencies of the code: they are downloaded through Ollama
  after their own consent (see ``model_manager``).
"""

from __future__ import annotations

import importlib
import importlib.metadata as md
import json
import platform
import shutil
import socket
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from typing import Any

import httpx

# (import name, distribution, minimum version, purpose, required)
PYTHON_DEPS: list[tuple[str, str, str, str, bool]] = [
    ("fastapi", "fastapi", "0.110", "local API and WebSocket for the interface", True),
    ("uvicorn", "uvicorn", "0.29", "web server that runs the local API", True),
    ("httpx", "httpx", "0.27", "talks to Ollama / OpenAI-compatible servers", True),
    ("psutil", "psutil", "5.9", "hardware, memory, power and idle detection", True),
    ("cryptography", "cryptography", "41", "Ed25519 identity and TLS certificates", True),
    ("zeroconf", "zeroconf", "0.132", "mDNS discovery of other Swarmbly nodes", True),
    ("numpy", "numpy", "1.24", "embeddings and alignment (via swarmbly-v0)", True),
    ("swarmbly_v0", "swarmbly-v0", "0.1.0", "SwarmblyAI protocol engine (pinned)", True),
    ("swarmbly_lce", "swarmbly-lce", "0.1.0", "Local Cognitive Extension (pinned)", True),
]
PINS = {
    "swarmbly-v0": "51eb44e8e471757f8abe2f90e60023633719fd0b",
    "swarmbly-lce": "b659ac4d77b42d186609799f925520837db94bb3",
}
OLLAMA_URL = "http://127.0.0.1:11434"


def _vtuple(text: str) -> tuple[int, ...]:
    out = []
    for part in str(text).split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        if not digits:
            break
        out.append(int(digits))
    return tuple(out)


def in_virtualenv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def _pinned_commit(dist: str) -> str | None:
    try:
        raw = md.distribution(dist).read_text("direct_url.json")
        data = json.loads(raw or "{}")
        return (data.get("vcs_info") or {}).get("commit_id")
    except Exception:
        return None


def check_python_packages() -> list[dict[str, Any]]:
    results = []
    for module, dist, minimum, purpose, required in PYTHON_DEPS:
        entry: dict[str, Any] = {"name": dist, "module": module, "purpose": purpose,
                                 "required": required, "minimum": minimum}
        try:
            version = md.version(dist)
            importlib.import_module(module)
            ok = _vtuple(version) >= _vtuple(minimum)
            entry.update(version=version, status="ok" if ok else "outdated")
        except Exception:
            entry.update(version=None, status="missing")
        if dist in PINS:
            commit = _pinned_commit(dist)
            entry["pinned_commit"] = PINS[dist][:7]
            entry["installed_commit"] = commit[:7] if commit else None
            if entry["status"] == "ok" and commit and commit != PINS[dist]:
                entry["status"] = "pin_mismatch"
        results.append(entry)
    return results


def check_ollama(url: str = OLLAMA_URL) -> dict[str, Any]:
    binary = shutil.which("ollama")
    out: dict[str, Any] = {"name": "Ollama", "purpose": "runs the local models",
                           "required": True, "installed": bool(binary),
                           "binary": binary, "running": False, "version": None,
                           "url": url}
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{url.rstrip('/')}/api/version")
            if resp.status_code == 200:
                out["running"] = True
                out["version"] = resp.json().get("version")
    except Exception:
        pass
    if out["running"]:
        out["status"] = "ok"
        out["installed"] = True
    elif binary:
        out["status"] = "not_running"
        out["fix"] = ("Start it: open the Ollama app (macOS/Windows) or run "
                      "`ollama serve` (Linux).")
    else:
        out["status"] = "missing"
        out["fix"] = _ollama_install_hint()
    return out


def _ollama_install_hint() -> str:
    system = platform.system()
    if system == "Darwin":
        return ("Download Ollama for macOS from https://ollama.com/download and open "
                "it once (no terminal needed).")
    if system == "Windows":
        return "Download the Windows installer from https://ollama.com/download."
    return ("Install Ollama with the official script from https://ollama.com/download "
            "(it asks for administrator rights), then run `ollama serve`.")


def check_ports(api_port: int, p2p_port: int) -> list[dict[str, Any]]:
    out = []
    for name, port, purpose in (("api", api_port, "local interface"),
                                ("p2p", p2p_port, "swarm connections (TCP)")):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0" if name == "p2p" else "127.0.0.1", port))
            status = "free"
        except OSError:
            status = "in_use"
        finally:
            sock.close()
        out.append({"name": name, "port": port, "purpose": purpose, "status": status,
                    "note": "in use is expected while Swarmbly App is running"})
    return out


def run_checks(state) -> dict[str, Any]:
    cfg = state.config.all()
    packages = check_python_packages()
    ollama = check_ollama((cfg["model"].get("backend_url") or OLLAMA_URL)
                          if cfg["model"].get("backend") in ("auto", "ollama")
                          else OLLAMA_URL)
    py_ok = sys.version_info >= (3, 10)
    try:
        writable = state.dirs.root.exists() and _writable(state.dirs.root)
    except Exception:
        writable = False
    missing = [p for p in packages if p["required"] and p["status"] != "ok"]
    return {
        "python": {"version": platform.python_version(), "required": ">=3.10",
                   "status": "ok" if py_ok else "too_old",
                   "virtualenv": in_virtualenv(), "executable": sys.executable},
        "packages": packages,
        "ollama": ollama,
        "data_dir": {"path": str(state.dirs.root), "writable": writable},
        "ports": check_ports(int((cfg.get("api") or {}).get("port", 8765)),
                             int(cfg["swarm"].get("p2p_port") or 9765)),
        "ready": py_ok and not missing and writable,
        "inference_ready": ollama["status"] == "ok",
        "installable": [p["name"] for p in missing] if in_virtualenv() else [],
        "manual_command": (None if in_virtualenv() or not missing else
                           f"{sys.executable} -m pip install "
                           + " ".join(_spec(p["name"]) for p in missing)),
    }


def _writable(path) -> bool:
    probe = path / ".write-probe"
    try:
        probe.write_text("ok")
        probe.unlink()
        return True
    except OSError:
        return False


def _spec(dist: str) -> str:
    if dist in PINS:
        repo = "SwarmblyAI" if dist == "swarmbly-v0" else "SwarmblyLCE"
        return f"{dist}@git+https://github.com/Sebastardito/{repo}.git@{PINS[dist]}"
    minimum = next((m for _, d, m, _, _ in PYTHON_DEPS if d == dist), "")
    return f"{dist}>={minimum}" if minimum else dist


@dataclass
class InstallJob:
    packages: list[str]
    status: str = "pending"        # pending|running|done|failed|refused
    log: list[str] = field(default_factory=list)
    verified: dict[str, bool] = field(default_factory=dict)


class Installer:
    """Consent-gated ``pip install`` into the app's own virtual environment."""

    def __init__(self, bus):
        self.bus = bus
        self.job: InstallJob | None = None
        self._lock = threading.Lock()

    def start(self, packages: list[str], consent: bool) -> InstallJob:
        allowed = {d for _, d, _, _, _ in PYTHON_DEPS}
        unknown = [p for p in packages if p not in allowed]
        job = InstallJob(packages=list(packages))
        if not consent:
            job.status, job.log = "refused", ["explicit consent is required"]
            return job
        if unknown:
            job.status, job.log = "refused", [f"not a Swarmbly dependency: {unknown}"]
            return job
        if not in_virtualenv():
            job.status, job.log = "refused", [
                "not running inside a virtual environment: the system Python is "
                "never modified. Run the command shown by the checks instead."]
            return job
        with self._lock:
            if self.job and self.job.status == "running":
                job.status, job.log = "refused", ["another installation is running"]
                return job
            self.job = job
        threading.Thread(target=self._run, args=(job,), daemon=True,
                         name="swarmbly-install").start()
        return job

    def _run(self, job: InstallJob) -> None:
        job.status = "running"
        self.bus.publish("doctor.install", status="running", packages=job.packages)
        cmd = [sys.executable, "-m", "pip", "install", *(_spec(p) for p in job.packages)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            job.log = (proc.stdout + proc.stderr).splitlines()[-40:]
            importlib.invalidate_caches()
            for _, dist, _, _, _ in PYTHON_DEPS:
                if dist in job.packages:
                    try:
                        md.version(dist)
                        job.verified[dist] = True
                    except md.PackageNotFoundError:
                        job.verified[dist] = False
            job.status = "done" if proc.returncode == 0 and all(job.verified.values()) \
                else "failed"
        except Exception as exc:
            job.status, job.log = "failed", [str(exc)]
        self.bus.publish("doctor.install", status=job.status, packages=job.packages,
                         verified=job.verified)
