#!/usr/bin/env python3
"""Swarmbly App launcher: check, prepare, start.

Run it through the wrapper for your system (they find a suitable Python):

    ./launch.sh                 macOS / Linux
    Swarmbly.command            macOS, double-click in Finder
    launch.bat                  Windows

or directly with Python >= 3.10:  python3 scripts/launch.py [options]

What it does, in order, and what it asks before doing:

1. Python    — 3.10 or newer (tells you how to get one otherwise).
2. git       — needed to install the pinned SwarmblyAI / SwarmblyLCE commits.
3. .venv     — the app's own virtual environment; created on first run.
4. Packages  — installed or updated inside .venv only. Asks first.
5. Ollama    — optional model runner. Started for you if installed and you
               agree; never installed for you (official instructions shown).
6. Port      — if Swarmbly is already running it opens it; if the port is
               taken by something else it picks the next free one.

Then it starts the app (``swarmbly-app``) and your browser opens. Nothing is
shared on the network until you allow it inside the app.

Only the standard library is used here, so this file runs before anything is
installed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"
STAMP = VENV / ".swarmbly-install"
MIN_PY = (3, 10)
DEFAULT_PORT = 8765
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
if not OLLAMA_URL.startswith("http"):
    OLLAMA_URL = "http://" + OLLAMA_URL
IMPORTS = ["swarmbly_app", "swarmbly_v0", "swarmbly_lce", "fastapi", "uvicorn",
           "httpx", "psutil", "cryptography", "zeroconf"]
IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"

# ---- output -----------------------------------------------------------------
_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR") and not IS_WIN


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def step(n: int, total: int, label: str, value: str, state: str = "ok") -> None:
    mark = {"ok": _c("32", "ok"), "warn": _c("33", "!!"), "fail": _c("31", "xx"),
            "info": _c("36", "··")}[state]
    print(f"  [{n}/{total}] {label:<13} {mark}  {value}", flush=True)


def note(text: str) -> None:
    for line in text.strip("\n").splitlines():
        print(f"                       {line}")


def fail(text: str, code: int = 1) -> int:
    print()
    print(_c("31", "Stopped: ") + text)
    return code


class Asker:
    def __init__(self, assume_yes: bool, assume_no: bool):
        self.yes = assume_yes
        self.no = assume_no
        self.tty = sys.stdin.isatty()

    def __call__(self, question: str, default: bool = True) -> bool:
        if self.yes:
            print(f"                       {question} yes (--yes)")
            return True
        if self.no or not self.tty:
            print(f"                       {question} no"
                  + ("" if self.no else " (not interactive; use --yes to accept)"))
            return False
        hint = "[Y/n]" if default else "[y/N]"
        try:
            answer = input(f"                       {question} {hint} ").strip().lower()
        except EOFError:
            return False
        return default if not answer else answer in ("y", "yes", "s", "si", "sí")


# ---- helpers ----------------------------------------------------------------
def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if IS_WIN else "bin/python")


def venv_entry() -> Path:
    return VENV / ("Scripts/swarmbly-app.exe" if IS_WIN else "bin/swarmbly-app")


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, **kw)


def install_fingerprint(py_version: str) -> str:
    data = (ROOT / "pyproject.toml").read_bytes() + py_version.encode()
    return hashlib.sha256(data).hexdigest()


def venv_version() -> str | None:
    py = venv_python()
    if not py.exists():
        return None
    try:
        out = run([str(py), "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"],
                  capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def missing_imports() -> list[str]:
    probe = (
        "import importlib, json, sys\n"
        f"names = {IMPORTS!r}\n"
        "bad = []\n"
        "for n in names:\n"
        "    try: importlib.import_module(n)\n"
        "    except Exception: bad.append(n)\n"
        "try:\n"
        "    import swarmbly_app, pathlib\n"
        f"    if not pathlib.Path(swarmbly_app.__file__).resolve().is_relative_to(pathlib.Path({str(ROOT)!r}).resolve()):\n"
        "        bad.append('swarmbly_app (installed from another folder)')\n"
        "except Exception: pass\n"
        "print(json.dumps(bad))\n"
    )
    # Run outside the repo so the working directory cannot mask a broken install.
    out = subprocess.run([str(venv_python()), "-c", probe], capture_output=True,
                         text=True, cwd=str(VENV), timeout=120)
    try:
        return json.loads(out.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return list(IMPORTS)


def clear_macos_hidden_flag() -> None:
    # Python skips hidden .pth files; Finder and sync tools can set UF_HIDDEN on
    # .venv, which silently breaks the editable install (see docs/INSTALL.md).
    if IS_MAC and VENV.exists():
        subprocess.run(["chflags", "-R", "nohidden", str(VENV)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def http_json(url: str, timeout: float = 1.5):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def swarmbly_on(port: int) -> dict | None:
    try:
        data = http_json(f"http://127.0.0.1:{port}/api/health")
    except Exception:
        return None
    return data if isinstance(data, dict) and "protocol_spec" in data else None


def python_hint() -> str:
    if IS_MAC:
        return ("Install Python 3.12 from https://www.python.org/downloads/ "
                "or with Homebrew: brew install python@3.12")
    if IS_WIN:
        return "Install Python 3.12 from https://www.python.org/downloads/ (tick 'Add to PATH')"
    return "Install Python 3.12 with your package manager, e.g. sudo apt install python3.12 python3.12-venv"


def git_hint() -> str:
    if IS_MAC:
        return "Install the command-line tools: xcode-select --install"
    if IS_WIN:
        return "Install Git from https://git-scm.com/download/win"
    return "Install git with your package manager, e.g. sudo apt install git"


def ollama_hint() -> str:
    if IS_MAC:
        return "Download Ollama from https://ollama.com/download (or: brew install ollama)"
    if IS_WIN:
        return "Download Ollama from https://ollama.com/download"
    return "Install Ollama: see https://ollama.com/download (official install script)"


# ---- steps --------------------------------------------------------------------
TOTAL = 6


def check_python() -> bool:
    ver = "%d.%d.%d" % sys.version_info[:3]
    if sys.version_info[:2] < MIN_PY:
        step(1, TOTAL, "Python", f"{ver} is too old (3.10 or newer needed)", "fail")
        note(python_hint())
        return False
    step(1, TOTAL, "Python", f"{ver}  {sys.executable}")
    return True


def check_git(needed: bool) -> bool:
    git = shutil.which("git")
    if git:
        step(2, TOTAL, "git", git)
        return True
    if not needed:
        step(2, TOTAL, "git", "not found (not needed: packages already installed)", "info")
        return True
    step(2, TOTAL, "git", "not found — needed to install SwarmblyAI and SwarmblyLCE", "fail")
    note(git_hint())
    return False


def ensure_venv(ask: Asker, check_only: bool) -> bool:
    current = "%d.%d" % sys.version_info[:2]
    ver = venv_version()
    if ver and tuple(int(x) for x in ver.split(".")[:2]) >= MIN_PY:
        step(3, TOTAL, "Environment", f".venv (Python {ver})")
        return True
    if VENV.exists():
        step(3, TOTAL, "Environment", ".venv exists but its Python does not run "
             "(moved folder or removed interpreter)", "warn")
        if check_only or not ask("Rebuild .venv from scratch?"):
            return False
        shutil.rmtree(VENV)
    else:
        step(3, TOTAL, "Environment", "no .venv yet", "info")
        if check_only:
            return False
        if not ask(f"Create the app's virtual environment in .venv (Python {current})?"):
            return False
    try:
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    except subprocess.CalledProcessError:
        note("Could not create the environment. On Debian/Ubuntu: "
             f"sudo apt install python{current}-venv")
        return False
    note(f"created .venv with Python {current}")
    return True


def ensure_packages(ask: Asker, check_only: bool, dev: bool, force: bool) -> bool:
    ver = venv_version() or ""
    fingerprint = install_fingerprint(ver)
    stamp_ok = STAMP.exists() and STAMP.read_text().strip() == fingerprint
    clear_macos_hidden_flag()
    missing = missing_imports()
    if stamp_ok and not missing and not force and not (dev and not _has_pytest()):
        step(4, TOTAL, "Packages", "up to date")
        return True
    reason = ("missing: " + ", ".join(missing)) if missing else \
        "requirements changed since last install" if not stamp_ok else "reinstall requested"
    step(4, TOTAL, "Packages", reason, "warn" if missing else "info")
    if check_only:
        return not missing
    if not shutil.which("git"):
        note("git is needed to install SwarmblyAI and SwarmblyLCE. " + git_hint())
        return False
    if not ask("Install or update Swarmbly App's packages into .venv "
               "(PyPI + pinned SwarmblyAI/SwarmblyLCE from GitHub)?"):
        return not missing
    py = str(venv_python())
    target = ".[dev]" if dev else "."
    cmds = [[py, "-m", "pip", "install", "--disable-pip-version-check", "--upgrade", "pip"],
            [py, "-m", "pip", "install", "--disable-pip-version-check", "-e", target]]
    for cmd in cmds:
        if run(cmd).returncode != 0:
            note("pip failed; the messages above say why (network, git, compiler).")
            return False
    clear_macos_hidden_flag()
    missing = missing_imports()
    if missing:
        note("still missing after install: " + ", ".join(missing))
        return False
    STAMP.write_text(fingerprint)
    note("packages installed")
    return True


def _has_pytest() -> bool:
    out = subprocess.run([str(venv_python()), "-c", "import pytest"],
                         capture_output=True, cwd=str(VENV))
    return out.returncode == 0


def ollama_binary() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    if IS_MAC and Path("/Applications/Ollama.app").exists():
        return "/Applications/Ollama.app"
    return None


def ollama_models() -> list[str] | None:
    try:
        data = http_json(f"{OLLAMA_URL}/api/tags")
    except Exception:
        return None
    return [m.get("name", "?") for m in data.get("models", [])]


def ensure_ollama(ask: Asker, check_only: bool, skip: bool) -> None:
    if skip:
        step(5, TOTAL, "Ollama", "skipped (--no-ollama)", "info")
        return
    models = ollama_models()
    if models is None:
        binary = ollama_binary()
        if not binary:
            step(5, TOTAL, "Ollama", "not installed (optional)", "info")
            note(ollama_hint())
            note("Without a model runner the app opens, but chat needs a model.\n"
                 "OpenAI-compatible servers (llama.cpp, vLLM) also work: Settings → Models.")
            return
        step(5, TOTAL, "Ollama", "installed, not running", "warn")
        if check_only or not ask("Start Ollama now?"):
            return
        _start_ollama(binary)
        for _ in range(40):
            time.sleep(0.5)
            models = ollama_models()
            if models is not None:
                break
        if models is None:
            note("Ollama did not answer within 20 s; the app will keep checking.")
            return
    names = ", ".join(models[:4]) + (" …" if len(models) > 4 else "")
    if models:
        step(5, TOTAL, "Ollama", f"running, {len(models)} model(s): {names}")
    else:
        step(5, TOTAL, "Ollama", "running, no models yet", "info")
        note("The app suggests models that fit your computer and downloads them\n"
             "through Ollama after you allow it (first-run assistant or Settings → Models).")


def _start_ollama(binary: str) -> None:
    if binary.endswith(".app"):
        subprocess.Popen(["open", "-a", binary])
        return
    log_dir = ROOT / ".venv"
    log = open(log_dir / "ollama-serve.log", "ab")
    kwargs = {"stdout": log, "stderr": log, "stdin": subprocess.DEVNULL}
    if IS_WIN:
        kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED | NEW_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen([binary, "serve"], **kwargs)
    note(f"started `ollama serve` (log: {log_dir / 'ollama-serve.log'})")


def choose_port(requested: int) -> tuple[int | None, dict | None]:
    running = swarmbly_on(requested)
    if running:
        step(6, TOTAL, "Port", f"{requested}: Swarmbly {running.get('version', '?')} "
             f"already running (node {running.get('node_id', '?')})", "info")
        return requested, running
    if port_free(requested):
        step(6, TOTAL, "Port", f"{requested} free")
        return requested, None
    for port in range(requested + 1, requested + 20):
        if swarmbly_on(port):
            step(6, TOTAL, "Port", f"Swarmbly already running on {port}", "info")
            return port, swarmbly_on(port)
        if port_free(port):
            step(6, TOTAL, "Port", f"{requested} is used by another program; using {port}", "warn")
            return port, None
    step(6, TOTAL, "Port", f"{requested}–{requested + 19} all busy", "fail")
    return None, None


# ---- main ---------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check requirements, prepare the environment and start Swarmbly App.",
        epilog="Anything after -- is passed to swarmbly-app, e.g. -- --data-dir ~/swarmbly-test")
    parser.add_argument("--headless", action="store_true",
                        help="run the node without the browser interface (worker computers)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"local interface port (default {DEFAULT_PORT})")
    parser.add_argument("--check", action="store_true",
                        help="only report what is ready; change nothing, start nothing")
    parser.add_argument("--setup-only", action="store_true",
                        help="prepare everything but do not start the app")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="answer yes to every question (unattended setup)")
    parser.add_argument("--no", action="store_true", help="answer no to every question")
    parser.add_argument("--dev", action="store_true", help="also install test tools (pytest)")
    parser.add_argument("--reinstall", action="store_true",
                        help="reinstall packages even if they look up to date")
    parser.add_argument("--no-ollama", action="store_true", help="do not check or start Ollama")
    parser.add_argument("passthrough", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    extra = [a for a in args.passthrough if a != "--"]
    ask = Asker(args.yes, args.no)

    print()
    print(_c("1;32", "  Swarmbly App") + "  — fragments the problem, not the model")
    print(f"  {ROOT}")
    print(f"  {platform.system()} {platform.release()} · {platform.machine()}")
    print()

    if not check_python():
        return fail("a newer Python is needed.")
    have_packages = venv_version() is not None and not missing_imports()
    if not check_git(needed=not have_packages):
        return fail("git is needed for the first install.")
    if not ensure_venv(ask, args.check):
        if args.check:
            return fail("no environment yet; run without --check to create it.", 2)
        return fail("the app's environment is not ready.")
    if not ensure_packages(ask, args.check, args.dev, args.reinstall):
        return fail("packages are missing; run again and accept the install, "
                    "or see docs/INSTALL.md.")
    ensure_ollama(ask, args.check, args.no_ollama)

    if args.headless:
        step(6, TOTAL, "Port", "headless: no interface", "info")
        port, running = args.port, None
    else:
        port, running = choose_port(args.port)
        if port is None:
            return fail("no free port; pass --port <number>.")

    print()
    if args.check:
        print("  Ready. Start with ./launch.sh (or launch.bat on Windows).")
        return 0
    if args.setup_only:
        print("  Setup complete. Start with ./launch.sh, or activate .venv and run swarmbly-app.")
        return 0
    if running:
        url = f"http://127.0.0.1:{port}/"
        print(f"  Opening the running app: {url}")
        import webbrowser
        webbrowser.open(url)
        return 0

    cmd = [str(venv_entry()), "headless" if args.headless else "serve", "--port", str(port), *extra]
    print("  Starting: " + " ".join(cmd[1:]) + "   (Ctrl+C to stop)")
    print()
    clear_macos_hidden_flag()
    if IS_WIN:
        try:
            return subprocess.call(cmd)
        except KeyboardInterrupt:
            return 0
    os.execv(cmd[0], cmd)
    return 0  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())
