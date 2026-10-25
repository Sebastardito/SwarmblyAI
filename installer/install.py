#!/usr/bin/env python3
"""Swarmbly AI installer — standard library only, macOS / Linux / Windows.

Two ways to install, chosen at the start:

* Quick: everything recommended for this computer, explained once, then no
  more questions. Steps that need an administrator password are skipped and
  listed at the end with the exact command to run.
* Custom: step by step, each item explained, each one optional.

What it can set up: an isolated Python environment with SwarmblyCore,
SwarmblyLCE and SwarmblyApp from this folder; Ollama and models that fit
this computer; pdftotext (reading PDFs) and SearXNG (web search) as
optional extras; a launcher, a desktop shortcut and a diagnostic command.
Nothing outside this folder, the Swarmbly data folder and the shortcuts is
changed, and the system Python is never modified.

    python installer/install.py            # asks quick or custom
    python installer/install.py --quick    # quick, no questions
    python installer/install.py --custom
    python installer/install.py --doctor   # check an existing installation
    python installer/install.py --uninstall
    python installer/install.py --dry-run  # show the plan, change nothing
"""

from __future__ import annotations

import argparse
import json
import locale
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPONENTS = ("SwarmblyCore", "SwarmblyLCE", "SwarmblyApp")
STATE = ROOT / ".swarmbly"
LOG = ROOT / "install.log"
IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
OLLAMA = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
OLLAMA = OLLAMA if OLLAMA.startswith("http") else "http://" + OLLAMA
EMBED_MODEL = ("nomic-embed-text", 0.27)
# (minimum RAM in GB, model, download GB) — the same models as the app's catalog
CHAT_MODELS = [(24, "qwen2.5:7b", 4.7), (10, "qwen2.5:3b", 1.9), (0, "qwen2.5:1.5b", 1.0)]
EXTRA_FAMILIES = [("llama3.2:3b", 2.0), ("gemma2:2b", 1.6), ("phi3.5:3.8b", 2.2)]

# ---------------------------------------------------------------------------- text
T = {
 "es": {
  "title": "Instalador de Swarmbly AI",
  "intro": (
   "Swarmbly AI es una IA descentralizada que fragmenta el problema, no el modelo.\n"
   "Este paquete reúne sus tres partes:\n"
   "  • SwarmblyCore — protocolo, orquestador y red entre computadoras (P2P).\n"
   "  • SwarmblyLCE  — memoria local: lee tus documentos sin sacarlos del equipo.\n"
   "  • SwarmblyApp  — la aplicación: chat, monitor de la red y ajustes.\n"
   "Los modelos de lenguaje corren en tu computadora con Ollama."),
  "menu": "¿Cómo quieres instalar?",
  "quick": "Instalación rápida — todo lo recomendado, explicado ahora y sin más preguntas",
  "custom": "Instalación personalizada — paso a paso, decides cada cosa",
  "doctor": "Comprobar una instalación existente",
  "uninstall": "Desinstalar",
  "exit": "Salir",
  "choice": "Elige una opción",
  "quick_plan": "La instalación rápida hará esto:",
  "online": "Se descargará de internet: paquetes de Python (PyPI), Ollama y modelos (ollama.com) y, para la búsqueda web, el código de SearXNG (GitHub). No se envía ningún dato tuyo.",
  "admin_note": "Lo que necesite contraseña de administrador se omitirá y quedará anotado al final, con el comando exacto.",
  "proceed": "¿Empezar?",
  "yes": "s", "no": "n",
  "skipped": "omitido", "done": "listo", "failed": "falló", "pending": "pendiente",
  "step_python": "Python",
  "why_python": "Swarmbly necesita Python 3.10 o superior. Se usa solo para crear un entorno aislado; el Python del sistema no se modifica.",
  "py_ok": "Python {v} — correcto",
  "py_searx": "Nota: la búsqueda web local (SearXNG) necesita Python 3.11+, Docker o uv; si no hay ninguno, se omitirá.",
  "step_env": "Entorno aislado",
  "why_env": "Una carpeta propia (.venv) con las bibliotecas de Swarmbly, separada del resto del sistema. Desinstalar = borrar esa carpeta.",
  "env_where": "Ubicación del entorno",
  "step_modules": "Componentes de Swarmbly",
  "why_modules": "Instala SwarmblyCore, SwarmblyLCE y SwarmblyApp desde esta carpeta, con las versiones probadas juntas (components.lock).",
  "dev_mode": "¿Modo desarrollador? (instalación editable y herramientas de prueba)",
  "step_ollama": "Ollama (motor de modelos)",
  "why_ollama": "Ollama ejecuta los modelos de lenguaje en tu equipo. Sin él la app abre, pero el chat no tiene modelo.",
  "ollama_ok": "Ollama funcionando",
  "ollama_start": "Ollama está instalado pero apagado; se inicia.",
  "ollama_install": "¿Instalar Ollama ahora?",
  "ollama_manual": "Instálalo desde https://ollama.com/download y vuelve a ejecutar el instalador (o usa --doctor).",
  "step_models": "Modelos",
  "why_models": "Un modelo de chat que quepa en tu memoria ({ram} GB de RAM) y el modelo de vectores que usa la memoria local para buscar por significado.",
  "models_plan": "Se descargarán: {list} (≈ {gb:.1f} GB)",
  "models_pick": "Modelos sugeridos para este equipo:",
  "models_extra": "¿Añadir otra familia de modelos? Sirve para que la red compare respuestas de modelos distintos",
  "step_pdf": "pdftotext (lectura de PDF)",
  "why_pdf": "Permite que la memoria local lea tus PDF. Sin él, los PDF aparecen como «no se puede leer».",
  "step_searx": "SearXNG (búsqueda web, opcional)",
  "why_searx": "Un buscador libre que corre solo en tu equipo y consulta DuckDuckGo, Google Scholar, PubMed, OpenAlex y otros sin claves. A los buscadores solo se envían nombres, nunca tus documentos. Ocupa ~60 MB.",
  "step_sources": "Tus documentos (memoria local)",
  "why_sources": "Si tienes una carpeta con tus documentos (CV, artículos, tesis, notas), Swarmbly puede consultarla al responder. Se lee en su sitio, nunca se copia ni sale del equipo.",
  "sources_ask": "Ruta de la carpeta (Enter para omitir)",
  "sources_bad": "Esa carpeta no existe; se omite.",
  "step_shortcuts": "Accesos directos",
  "why_shortcuts": "Un comando «swarmbly» para abrir la app, «swarmbly doctor» para comprobarla, y un acceso directo en el escritorio.",
  "step_doctor": "Comprobación final",
  "summary": "Resumen",
  "start_hint": "Para empezar: {cmd}  (o el acceso directo «Swarmbly» del escritorio)",
  "pending_title": "Pendiente (necesita tu intervención):",
  "launch_now": "¿Abrir Swarmbly ahora?",
  "uninstall_what": "Se borrarán el entorno (.venv), los lanzadores y los accesos directos. Tus datos (conversaciones, configuración) se conservan.",
  "purge_ask": "¿Borrar también tus datos de Swarmbly ({path})? Esto no se puede deshacer",
  "uninstalled": "Desinstalado.",
  "dry": "[simulación] ",
  "log": "Registro completo: {path}",
  "need_app": "Necesita los componentes instalados; se omite.",
  "support": "Swarmbly se desarrolla de forma independiente. Si quieres apoyarlo: https://buymeacoffee.com/swarmbly",
  "ask_pdf": "¿Instalar pdftotext?",
  "ask_searx": "¿Instalar SearXNG?",
  "ask_shortcuts": "¿Crear el comando y los accesos directos?",
 },
 "en": {
  "title": "Swarmbly AI installer",
  "intro": (
   "Swarmbly AI is a decentralized AI that splits the problem, not the model.\n"
   "This package brings its three parts together:\n"
   "  • SwarmblyCore — protocol, orchestrator and peer-to-peer network.\n"
   "  • SwarmblyLCE  — local memory: reads your documents without them leaving this computer.\n"
   "  • SwarmblyApp  — the application: chat, network monitor and settings.\n"
   "Language models run on your computer through Ollama."),
  "menu": "How do you want to install?",
  "quick": "Quick install — everything recommended, explained now, no further questions",
  "custom": "Custom install — step by step, you decide each item",
  "doctor": "Check an existing installation",
  "uninstall": "Uninstall",
  "exit": "Exit",
  "choice": "Choose an option",
  "quick_plan": "The quick install will:",
  "online": "It downloads Python packages (PyPI), Ollama and models (ollama.com) and, for web search, SearXNG's source code (GitHub). None of your data is sent.",
  "admin_note": "Anything that needs an administrator password is skipped and listed at the end with the exact command.",
  "proceed": "Start?",
  "yes": "y", "no": "n",
  "skipped": "skipped", "done": "done", "failed": "failed", "pending": "pending",
  "step_python": "Python",
  "why_python": "Swarmbly needs Python 3.10 or newer, only to create an isolated environment; the system Python is not changed.",
  "py_ok": "Python {v} — OK",
  "py_searx": "Note: local web search (SearXNG) needs Python 3.11+, Docker or uv; without any of them it is skipped.",
  "step_env": "Isolated environment",
  "why_env": "A folder of its own (.venv) with Swarmbly's libraries, apart from the rest of the system. Uninstalling = deleting that folder.",
  "env_where": "Environment location",
  "step_modules": "Swarmbly components",
  "why_modules": "Installs SwarmblyCore, SwarmblyLCE and SwarmblyApp from this folder, at the versions tested together (components.lock).",
  "dev_mode": "Developer mode? (editable install and test tools)",
  "step_ollama": "Ollama (model runner)",
  "why_ollama": "Ollama runs the language models on your computer. Without it the app opens but chat has no model.",
  "ollama_ok": "Ollama running",
  "ollama_start": "Ollama is installed but stopped; starting it.",
  "ollama_install": "Install Ollama now?",
  "ollama_manual": "Install it from https://ollama.com/download and run the installer again (or use --doctor).",
  "step_models": "Models",
  "why_models": "A chat model that fits your memory ({ram} GB RAM) and the embedding model the local memory uses to search by meaning.",
  "models_plan": "Will download: {list} (≈ {gb:.1f} GB)",
  "models_pick": "Suggested models for this computer:",
  "models_extra": "Add another model family? It lets the network compare answers from different models",
  "step_pdf": "pdftotext (reading PDFs)",
  "why_pdf": "Lets the local memory read your PDFs. Without it, PDFs show as \"cannot be read\".",
  "step_searx": "SearXNG (web search, optional)",
  "why_searx": "A free search engine that runs only on this computer and queries DuckDuckGo, Google Scholar, PubMed, OpenAlex and others without keys. Only names are sent to search engines, never your documents. About 60 MB.",
  "step_sources": "Your documents (local memory)",
  "why_sources": "If you have a folder with your documents (CV, papers, thesis, notes), Swarmbly can consult it when answering. It is read in place, never copied, and never leaves this computer.",
  "sources_ask": "Folder path (Enter to skip)",
  "sources_bad": "That folder does not exist; skipped.",
  "step_shortcuts": "Shortcuts",
  "why_shortcuts": "A \"swarmbly\" command to open the app, \"swarmbly doctor\" to check it, and a desktop shortcut.",
  "step_doctor": "Final check",
  "summary": "Summary",
  "start_hint": "To start: {cmd}  (or the \"Swarmbly\" desktop shortcut)",
  "pending_title": "Pending (needs you):",
  "launch_now": "Open Swarmbly now?",
  "uninstall_what": "The environment (.venv), launchers and shortcuts will be deleted. Your data (conversations, settings) is kept.",
  "purge_ask": "Also delete your Swarmbly data ({path})? This cannot be undone",
  "uninstalled": "Uninstalled.",
  "dry": "[dry run] ",
  "log": "Full log: {path}",
  "need_app": "Needs the components installed; skipped.",
  "support": "Swarmbly is developed independently. To support it: https://buymeacoffee.com/swarmbly",
  "ask_pdf": "Install pdftotext?",
  "ask_searx": "Install SearXNG?",
  "ask_shortcuts": "Create the command and shortcuts?",
 },
}


def pick_lang(arg: str | None) -> str:
    if arg in T:
        return arg
    loc = (os.environ.get("LANG") or os.environ.get("LC_ALL") or "")
    if not loc:
        try:
            loc = locale.getlocale()[0] or ""
        except Exception:
            loc = ""
    return "es" if loc.lower().startswith("es") or "spanish" in loc.lower() else "en"


# ---------------------------------------------------------------------------- console
_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR") and not IS_WIN


def c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


class UI:
    def __init__(self, lang: str, interactive: bool, dry: bool):
        self.t = T[lang]
        self.interactive = interactive
        self.dry = dry
        self.pending: list[str] = []
        self.results: list[tuple[str, str, str]] = []
        LOG.write_text(f"Swarmbly AI installer — {time.ctime()}\n", encoding="utf-8")

    def __getitem__(self, key: str) -> str:
        return self.t[key]

    def log(self, text: str) -> None:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(text.rstrip() + "\n")

    def say(self, text: str = "") -> None:
        print(text)
        self.log(text)

    def header(self, n: int, total: int, title: str, why: str) -> None:
        self.say()
        self.say(c("1", f"[{n}/{total}] {title}"))
        for line in (_wrap(why) if why else []):
            self.say(c("2", "    " + line))

    def ask(self, question: str, default: bool = True) -> bool:
        if not self.interactive:
            return default
        hint = f"[{self['yes'].upper()}/{self['no']}]" if default else f"[{self['yes']}/{self['no'].upper()}]"
        try:
            ans = input(f"    {question} {hint} ").strip().lower()
        except EOFError:
            return default
        if not ans:
            return default
        return ans[0] in ("s", "y")

    def text(self, question: str, default: str = "") -> str:
        if not self.interactive:
            return default
        try:
            ans = input(f"    {question}{f' [{default}]' if default else ''}: ").strip()
        except EOFError:
            return default
        return ans or default

    def result(self, title: str, status: str, detail: str = "") -> None:
        self.results.append((title, status, detail))
        mark = {"done": c("32", "✓"), "skipped": c("2", "–"), "failed": c("31", "✗"),
                "pending": c("33", "!")}.get(status, "·")
        self.say(f"    {mark} {self[status]}{(': ' + detail) if detail else ''}")


def _wrap(text: str, width: int = 76) -> list[str]:
    out = []
    for para in text.split("\n"):
        line = ""
        for word in para.split():
            if len(line) + len(word) + 1 > width:
                out.append(line)
                line = word
            else:
                line = f"{line} {word}".strip()
        out.append(line)
    return out


def run(ui: UI, cmd: list[str], timeout: int = 1800, check: bool = True,
        capture: bool = False, env: dict | None = None) -> subprocess.CompletedProcess | None:
    ui.log("$ " + " ".join(cmd))
    if ui.dry:
        shown = [a if "\n" not in a else "<script>" for a in cmd]
        ui.say(c("2", "    " + ui["dry"] + " ".join(shown)))
        return subprocess.CompletedProcess(cmd, 0, "", "")
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), timeout=timeout, text=True,
                              capture_output=True, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        ui.log(f"error: {exc}")
        if check:
            raise RuntimeError(str(exc)) from exc
        return None
    ui.log(proc.stdout[-4000:] + proc.stderr[-4000:])
    if check and proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip()[-600:])
    return proc


# ---------------------------------------------------------------------------- facts
def ram_gb() -> float:
    try:
        if IS_MAC:
            return int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True,
                                      text=True).stdout) / 1e9
        if IS_WIN:
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MS()
            m.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullTotalPhys / 1e9
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9
    except Exception:
        return 8.0


def http_json(url: str, timeout: float = 2.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 (local Ollama)
        return json.loads(r.read().decode())


def ollama_models() -> list[str] | None:
    try:
        return [m.get("name", "") for m in http_json(f"{OLLAMA}/api/tags").get("models", [])]
    except Exception:
        return None


def ollama_binary() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    for p in ("/usr/local/bin/ollama", "/opt/homebrew/bin/ollama",
              "/Applications/Ollama.app/Contents/Resources/ollama",
              os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")):
        if os.path.exists(p):
            return p
    return None


def can_sudo() -> bool:
    if IS_WIN or not shutil.which("sudo"):
        return False
    if os.geteuid() == 0:
        return True
    return subprocess.run(["sudo", "-n", "true"], capture_output=True).returncode == 0


def linux_pkg() -> tuple[str, list[str]] | None:
    for tool, cmd in (("apt-get", ["apt-get", "install", "-y"]), ("dnf", ["dnf", "install", "-y"]),
                      ("pacman", ["pacman", "-S", "--noconfirm"]), ("zypper", ["zypper", "-n", "install"])):
        if shutil.which(tool):
            return tool, cmd
    return None


class Ctx:
    def __init__(self, args, ui: UI):
        self.args = args
        self.ui = ui
        self.venv = Path(args.venv).expanduser().resolve() if args.venv else ROOT / ".venv"
        self.dev = args.dev
        self.models: list[tuple[str, float]] = []
        self.sources: str = args.sources or ""

    @property
    def py(self) -> Path:
        return self.venv / ("Scripts/python.exe" if IS_WIN else "bin/python")

    @property
    def app_entry(self) -> Path:
        return self.venv / ("Scripts/swarmbly-app.exe" if IS_WIN else "bin/swarmbly-app")


def plan_models(ram: float, extra: bool = False) -> list[tuple[str, float]]:
    chat = next((m, gb) for need, m, gb in CHAT_MODELS if ram >= need)
    out = [chat, EMBED_MODEL]
    if extra:
        out.append(EXTRA_FAMILIES[0] if ram >= 10 else EXTRA_FAMILIES[1])
    return out


# ---------------------------------------------------------------------------- steps
def step_python(ctx: Ctx) -> None:
    v = "%d.%d.%d" % sys.version_info[:3]
    ctx.ui.result(ctx.ui["step_python"], "done", ctx.ui["py_ok"].format(v=v))
    if sys.version_info < (3, 11) and not shutil.which("uv") and not shutil.which("docker"):
        ctx.ui.say(c("2", "    " + ctx.ui["py_searx"]))


def step_env(ctx: Ctx) -> None:
    ui = ctx.ui
    if ui.interactive and ctx.args.mode == "custom":
        where = ui.text(ui["env_where"], str(ctx.venv))
        ctx.venv = Path(where).expanduser().resolve()
    if ctx.py.exists():
        ui.result(ui["step_env"], "done", f"{ctx.venv} (existing)")
        return
    uv = shutil.which("uv")
    if uv:
        run(ui, [uv, "venv", "-q", "--seed", "-p", sys.executable, str(ctx.venv)])
    else:
        run(ui, [sys.executable, "-m", "venv", str(ctx.venv)])
    run(ui, [str(ctx.py), "-m", "pip", "install", "-q", "--upgrade", "pip"], check=False)
    ui.result(ui["step_env"], "done", str(ctx.venv))


def _app_dependencies() -> list[str]:
    """SwarmblyApp's dependencies except the Swarmbly ones (installed from here)."""
    text = (ROOT / "SwarmblyApp" / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"^dependencies\s*=\s*\[(.*?)^\]", text, re.S | re.M)
    deps = re.findall(r'"([^"]+)"', block.group(1)) if block else []
    return [d for d in deps if not d.lower().startswith("swarmbly")]


def step_modules(ctx: Ctx) -> None:
    ui = ctx.ui
    if ui.interactive and ctx.args.mode == "custom" and not ctx.dev:
        ctx.dev = ui.ask(ui["dev_mode"], default=False)
    pip = [str(ctx.py), "-m", "pip", "install", "-q"]
    edit = ["-e"] if ctx.dev else []
    missing = [n for n in COMPONENTS if not (ROOT / n / "pyproject.toml").exists()]
    if missing:
        raise RuntimeError(f"missing component folders: {missing}")
    # Core and LCE from their folders; the app without its git pins, so pip does
    # not fetch another copy of Core or LCE; then the app's other dependencies.
    run(ui, pip + edit + [str(ROOT / "SwarmblyCore")] + edit + [str(ROOT / "SwarmblyLCE")])
    run(ui, pip + ["--no-deps"] + edit + [str(ROOT / "SwarmblyApp")])
    run(ui, pip + _app_dependencies())
    if ctx.dev:
        run(ui, pip + ["pytest>=8.0", "pytest-asyncio>=0.23"], check=False)
    probe = run(ui, [str(ctx.py), "-c", "import swarmbly_app, swarmbly_lce, swarmbly_v0; print('ok')"],
                check=False, capture=True)
    ok = ui.dry or (probe is not None and probe.returncode == 0)
    ui.result(ui["step_modules"], "done" if ok else "failed",
              "SwarmblyCore + SwarmblyLCE + SwarmblyApp" + (" (dev)" if ctx.dev else ""))


def _start_ollama(ui: UI, binary: str) -> bool:
    if ui.dry:
        return True
    if binary.endswith(".app") or "Ollama.app" in binary:
        subprocess.Popen(["open", "-a", "Ollama"])
    else:
        kw = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "stdin": subprocess.DEVNULL}
        if IS_WIN:
            kw["creationflags"] = 0x00000008 | 0x00000200
        else:
            kw["start_new_session"] = True
        subprocess.Popen([binary, "serve"], **kw)
    for _ in range(40):
        time.sleep(0.5)
        if ollama_models() is not None:
            return True
    return False


def step_ollama(ctx: Ctx) -> None:
    ui = ctx.ui
    if ollama_models() is not None:
        ui.result(ui["step_ollama"], "done", ui["ollama_ok"])
        return
    binary = ollama_binary()
    if binary:
        ui.say("    " + ui["ollama_start"])
        ok = _start_ollama(ui, binary)
        ui.result(ui["step_ollama"], "done" if ok else "pending", "" if ok else "ollama serve")
        if not ok:
            ui.pending.append("ollama serve")
        return
    if ctx.args.mode == "custom" and not ui.ask(ui["ollama_install"]):
        ui.result(ui["step_ollama"], "skipped")
        return
    cmd = None
    if IS_MAC and shutil.which("brew"):
        cmd = ["brew", "install", "ollama"]
    elif IS_WIN and shutil.which("winget"):
        cmd = ["winget", "install", "-e", "--id", "Ollama.Ollama",
               "--accept-source-agreements", "--accept-package-agreements"]
    elif IS_LINUX and shutil.which("curl"):
        script = "curl -fsSL https://ollama.com/install.sh | sh"
        if can_sudo() or ui.interactive and ctx.args.mode == "custom":
            cmd = ["sh", "-c", script]
        else:
            ui.pending.append(script)
            ui.result(ui["step_ollama"], "pending", script)
            return
    if not cmd:
        ui.pending.append(ui["ollama_manual"])
        ui.result(ui["step_ollama"], "pending", "https://ollama.com/download")
        return
    try:
        run(ui, cmd, timeout=1800)
        binary = ollama_binary() or "ollama"
        ok = _start_ollama(ui, binary)
        ui.result(ui["step_ollama"], "done" if ok else "pending", " ".join(cmd[:3]))
    except RuntimeError as exc:
        ui.pending.append(ui["ollama_manual"])
        ui.result(ui["step_ollama"], "failed", str(exc)[:160])


def step_models(ctx: Ctx) -> None:
    ui = ctx.ui
    have = ollama_models()
    if have is None and not ui.dry:
        ui.result(ui["step_models"], "skipped", "Ollama")
        return
    have = have or []
    wanted = ctx.models or plan_models(ram_gb())
    if ctx.args.mode == "custom":
        ui.say("    " + ui["models_pick"])
        chosen = []
        for name, gb in wanted:
            if ui.ask(f"{name} (≈ {gb} GB)", default=True):
                chosen.append((name, gb))
        if ui.ask(ui["models_extra"], default=False):
            name, gb = EXTRA_FAMILIES[0] if ram_gb() >= 10 else EXTRA_FAMILIES[1]
            chosen.append((name, gb))
        wanted = chosen
    todo = [(n, gb) for n, gb in wanted
            if not any(h == n or h.startswith(n + ":") or h == n + ":latest" for h in have)]
    if not todo:
        ui.result(ui["step_models"], "done", ", ".join(n for n, _ in wanted) or "—")
        return
    binary = ollama_binary()
    failed = []
    for name, gb in todo:
        ui.say(f"    ↓ {name} (≈ {gb} GB)")
        try:
            if binary:
                run(ui, [binary, "pull", name], timeout=7200)
            else:
                _pull_http(ui, name)
        except RuntimeError as exc:
            failed.append(name)
            ui.log(f"pull {name}: {exc}")
    ui.result(ui["step_models"], "failed" if failed else "done",
              ", ".join(n for n, _ in todo) + (f" — {ui['failed']}: {', '.join(failed)}" if failed else ""))


def _pull_http(ui: UI, name: str) -> None:
    if ui.dry:
        return
    req = urllib.request.Request(f"{OLLAMA}/api/pull", data=json.dumps({"name": name}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=7200) as r:  # noqa: S310 (local Ollama)
        for line in r:
            ui.log(line.decode(errors="replace").strip())


def step_pdf(ctx: Ctx) -> None:
    ui = ctx.ui
    if shutil.which("pdftotext") or any(os.access(f"{d}/pdftotext", os.X_OK)
                                        for d in ("/opt/homebrew/bin", "/usr/local/bin")):
        ui.result(ui["step_pdf"], "done", "pdftotext")
        return
    if ctx.args.mode == "custom" and not ui.ask(ui["ask_pdf"]):
        ui.result(ui["step_pdf"], "skipped")
        return
    cmd = None
    if IS_MAC and shutil.which("brew"):
        cmd = ["brew", "install", "poppler"]
    elif IS_WIN:
        if shutil.which("scoop"):
            cmd = ["scoop", "install", "poppler"]
        elif shutil.which("choco"):
            cmd = ["choco", "install", "-y", "poppler"]
    elif IS_LINUX:
        pkg = linux_pkg()
        if pkg:
            name = "poppler-utils" if pkg[0] in ("apt-get", "zypper") else "poppler"
            full = ["sudo"] + pkg[1] + [name] if os.geteuid() != 0 else pkg[1] + [name]
            if can_sudo() or (ui.interactive and ctx.args.mode == "custom"):
                cmd = full
            else:
                ui.pending.append(" ".join(full))
                ui.result(ui["step_pdf"], "pending", " ".join(full))
                return
    if not cmd:
        hint = ("brew install poppler" if IS_MAC else
                "scoop install poppler  /  choco install poppler" if IS_WIN else
                "sudo apt install poppler-utils")
        ui.pending.append(hint)
        ui.result(ui["step_pdf"], "pending", hint)
        return
    try:
        run(ui, cmd, timeout=1800)
        ui.result(ui["step_pdf"], "done", " ".join(cmd))
    except RuntimeError as exc:
        ui.result(ui["step_pdf"], "failed", str(exc)[:160])


SEARX_SNIPPET = r"""
import json, time
from swarmbly_app.paths import DataDirs
from swarmbly_app.config import Config
from swarmbly_app.searxng import SearxngManager
dirs = DataDirs(); dirs.ensure(); cfg = Config(dirs)
class Bus:
    def publish(self, kind, **p):
        if p.get("step"): print("step", p["step"], flush=True)
m = SearxngManager(dirs.root, Bus(), cfg.all, lambda ch: cfg.update(ch))
if m.status()["managed"] and m.status()["running"]:
    print(json.dumps({"status": "done", "detail": m.status()["url"]})); raise SystemExit
job = m.install("auto", consent=True)
while job.status in ("pending", "running"):
    time.sleep(2)
detail = job.log[-1] if job.log else ""
m.stop()          # the app starts it with itself from now on
print(json.dumps({"status": job.status, "detail": detail}))
"""


def step_searx(ctx: Ctx) -> None:
    ui = ctx.ui
    if ctx.args.mode == "custom" and not ui.ask(ui["ask_searx"], default=True):
        ui.result(ui["step_searx"], "skipped")
        return
    if not ctx.py.exists() and not ui.dry:
        ui.result(ui["step_searx"], "skipped", ui["need_app"])
        return
    proc = run(ui, [str(ctx.py), "-c", SEARX_SNIPPET], timeout=1500, check=False, capture=True)
    if ui.dry:
        ui.result(ui["step_searx"], "done")
        return
    try:
        out = json.loads((proc.stdout or "").strip().splitlines()[-1])
    except Exception:
        out = {"status": "failed", "detail": (proc.stderr or "")[-200:] if proc else ""}
    status = "done" if out.get("status") == "done" else "failed"
    ui.result(ui["step_searx"], status, str(out.get("detail", ""))[:160])


SOURCES_SNIPPET = r"""
import sys
from swarmbly_app.paths import DataDirs
from swarmbly_app.config import Config
dirs = DataDirs(); dirs.ensure(); cfg = Config(dirs)
folder = sys.argv[1]
current = list((cfg.all().get("lce") or {}).get("sources_dirs") or [])
if folder not in current:
    current.append(folder)
cfg.update({"lce.enabled": True, "lce.level": "C1", "lce.sources_dirs": current})
print("ok")
"""


def step_sources(ctx: Ctx) -> None:
    ui = ctx.ui
    folder = ctx.sources
    if not folder and ctx.args.mode == "custom":
        folder = ui.text(ui["sources_ask"], "")
    if not folder:
        ui.result(ui["step_sources"], "skipped")
        return
    path = Path(folder).expanduser()
    if not path.is_dir():
        ui.result(ui["step_sources"], "skipped", ui["sources_bad"])
        return
    run(ui, [str(ctx.py), "-c", SOURCES_SNIPPET, str(path.resolve())], check=False)
    ui.result(ui["step_sources"], "done", str(path.resolve()))


def _launcher_text(ctx: Ctx) -> tuple[str, str]:
    doctor = f'"{sys.executable}" "{ROOT / "installer" / "install.py"}" --doctor'
    if IS_WIN:
        return "swarmbly.cmd", (
            "@echo off\r\n"
            f'if /I "%~1"=="doctor" ( {doctor} & exit /b )\r\n'
            f'"{ctx.app_entry}" %*\r\n')
    return "swarmbly", (
        "#!/usr/bin/env bash\n"
        "# Swarmbly AI launcher (written by the installer)\n"
        f'if [ "${{1:-}}" = "doctor" ]; then exec {doctor}; fi\n'
        f'exec "{ctx.app_entry}" "$@"\n')


def step_shortcuts(ctx: Ctx) -> None:
    ui = ctx.ui
    if ctx.args.mode == "custom" and not ui.ask(ui["ask_shortcuts"], default=True):
        ui.result(ui["step_shortcuts"], "skipped")
        return
    if ui.dry:
        ui.result(ui["step_shortcuts"], "done")
        return
    bindir = STATE / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    name, text = _launcher_text(ctx)
    launcher = bindir / name
    launcher.write_text(text, encoding="utf-8")
    made = [str(launcher)]
    if not IS_WIN:
        launcher.chmod(0o755)
        local_bin = Path.home() / ".local" / "bin"
        try:
            local_bin.mkdir(parents=True, exist_ok=True)
            link = local_bin / "swarmbly"
            if link.is_symlink() or not link.exists():
                if link.is_symlink():
                    link.unlink()
                link.symlink_to(launcher)
                made.append(str(link))
        except OSError:
            pass
    desktop = Path.home() / "Desktop"
    try:
        if IS_MAC and desktop.is_dir():
            sc = desktop / "Swarmbly.command"
            sc.write_text(f'#!/bin/bash\nexec "{launcher}"\n', encoding="utf-8")
            sc.chmod(0o755)
            made.append(str(sc))
        elif IS_LINUX:
            apps = Path.home() / ".local" / "share" / "applications"
            apps.mkdir(parents=True, exist_ok=True)
            entry = ("[Desktop Entry]\nType=Application\nName=Swarmbly\n"
                     f"Exec={launcher}\nTerminal=true\nCategories=Utility;Network;\n")
            (apps / "swarmbly.desktop").write_text(entry, encoding="utf-8")
            made.append(str(apps / "swarmbly.desktop"))
            if desktop.is_dir():
                d = desktop / "swarmbly.desktop"
                d.write_text(entry, encoding="utf-8")
                d.chmod(0o755)
                made.append(str(d))
        elif IS_WIN:
            ps = ("$s=(New-Object -ComObject WScript.Shell);"
                  "foreach($d in @([Environment]::GetFolderPath('Desktop'),"
                  "[Environment]::GetFolderPath('Programs'))){"
                  "$l=$s.CreateShortcut((Join-Path $d 'Swarmbly.lnk'));"
                  f"$l.TargetPath='{launcher}';$l.WorkingDirectory='{ROOT}';$l.Save()}}")
            run(ui, ["powershell", "-NoProfile", "-Command", ps], check=False)
            made.append("Desktop\\Swarmbly.lnk, Start menu\\Swarmbly.lnk")
    except OSError as exc:
        ui.log(f"shortcut: {exc}")
    (STATE / "install.json").write_text(json.dumps(
        {"venv": str(ctx.venv), "launcher": str(launcher), "made": made,
         "installed_at": time.strftime("%Y-%m-%d %H:%M")}, indent=2), encoding="utf-8")
    ui.result(ui["step_shortcuts"], "done", name)


def doctor(ctx: Ctx) -> int:
    ui = ctx.ui
    checks = []
    info = {}
    try:
        info = json.loads((STATE / "install.json").read_text(encoding="utf-8"))
        ctx.venv = Path(info.get("venv") or ctx.venv)
    except Exception:
        pass
    checks.append(("Python ≥ 3.10", sys.version_info >= (3, 10), "%d.%d" % sys.version_info[:2]))
    checks.append((".venv", ctx.py.exists(), str(ctx.venv)))
    ok_import = False
    if ctx.py.exists():
        p = subprocess.run([str(ctx.py), "-c", "import swarmbly_app, swarmbly_lce, swarmbly_v0"],
                           capture_output=True)
        ok_import = p.returncode == 0
    checks.append(("SwarmblyCore / LCE / App", ok_import, ""))
    models = ollama_models()
    checks.append(("Ollama", models is not None, OLLAMA))
    chat = [m for m in (models or []) if "embed" not in m]
    checks.append(("chat model", bool(chat), ", ".join(chat[:3])))
    checks.append(("nomic-embed-text", any("nomic-embed" in m for m in (models or [])), ""))
    pdf = bool(shutil.which("pdftotext") or any(os.access(f"{d}/pdftotext", os.X_OK)
                                                for d in ("/opt/homebrew/bin", "/usr/local/bin")))
    checks.append(("pdftotext (optional)", pdf, ""))
    lock = {}
    try:
        lock = json.loads((ROOT / "components.lock").read_text(encoding="utf-8"))
    except Exception:
        pass
    ui.say(c("1", ui["step_doctor"]))
    for name, ok, detail in checks:
        mark = c("32", "✓") if ok else (c("33", "!") if "optional" in name else c("31", "✗"))
        ui.say(f"  {mark} {name:28} {detail}")
    if lock:
        comps = lock.get("components", {})
        ui.say("  " + ", ".join(f"{k} {v.get('version', '?')}" for k, v in comps.items()))
    return 0 if all(ok for name, ok, _ in checks if "optional" not in name) else 1


def uninstall(ctx: Ctx) -> int:
    ui = ctx.ui
    ui.say(ui["uninstall_what"])
    if not ui.ask(ui["proceed"], default=False):
        return 1
    try:
        info = json.loads((STATE / "install.json").read_text(encoding="utf-8"))
    except Exception:
        info = {"venv": str(ctx.venv), "made": []}
    for p in info.get("made", []):
        try:
            path = Path(p)
            if path.is_symlink() or path.is_file():
                path.unlink()
        except OSError:
            pass
    if IS_WIN:
        run(ui, ["powershell", "-NoProfile", "-Command",
                 "foreach($d in @([Environment]::GetFolderPath('Desktop'),"
                 "[Environment]::GetFolderPath('Programs'))){Remove-Item -ErrorAction "
                 "SilentlyContinue (Join-Path $d 'Swarmbly.lnk')}"], check=False)
    venv = Path(info.get("venv") or ctx.venv)
    if venv.exists() and (venv / "pyvenv.cfg").exists():
        shutil.rmtree(venv, ignore_errors=True)
    shutil.rmtree(STATE, ignore_errors=True)
    data = _data_dir()
    if data and data.exists() and ui.ask(ui["purge_ask"].format(path=data), default=False):
        shutil.rmtree(data, ignore_errors=True)
    ui.say(ui["uninstalled"])
    return 0


def _data_dir() -> Path | None:
    if os.environ.get("SWARMBLY_DATA_DIR"):
        return Path(os.environ["SWARMBLY_DATA_DIR"]).expanduser()
    if IS_MAC:
        return Path.home() / "Library" / "Application Support" / "Swarmbly"
    if IS_WIN:
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Swarmbly"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "swarmbly"


# ---------------------------------------------------------------------------- flow
STEPS = [
    ("step_python", "why_python", step_python),
    ("step_env", "why_env", step_env),
    ("step_modules", "why_modules", step_modules),
    ("step_ollama", "why_ollama", step_ollama),
    ("step_models", "why_models", step_models),
    ("step_pdf", "why_pdf", step_pdf),
    ("step_searx", "why_searx", step_searx),
    ("step_sources", "why_sources", step_sources),
    ("step_shortcuts", "why_shortcuts", step_shortcuts),
]


def menu(ui: UI) -> str:
    options = [("quick", ui["quick"]), ("custom", ui["custom"]), ("doctor", ui["doctor"]),
               ("uninstall", ui["uninstall"]), ("exit", ui["exit"])]
    ui.say(ui["menu"])
    for i, (_, label) in enumerate(options, 1):
        ui.say(f"  {i}. {label}")
    while True:
        try:
            ans = input(f"{ui['choice']} [1]: ").strip() or "1"
        except EOFError:
            return "exit"
        if ans.isdigit() and 1 <= int(ans) <= len(options):
            return options[int(ans) - 1][0]


def quick_plan(ui: UI, ctx: Ctx) -> None:
    ram = ram_gb()
    ctx.models = plan_models(ram)
    models = ", ".join(n for n, _ in ctx.models)
    gb = sum(g for _, g in ctx.models)
    ui.say(c("1", ui["quick_plan"]))
    for key, why_key, _ in STEPS:
        if key == "step_sources" and not ctx.sources:
            continue
        why = ui[why_key].format(ram=f"{ram:.0f}")
        ui.say(f"  • {ui[key]} — " + _wrap(why, 200)[0])
    ui.say("    " + ui["models_plan"].format(list=models, gb=gb))
    for line in _wrap(ui["online"]) + _wrap(ui["admin_note"]):
        ui.say(c("2", "  " + line))


def _utf8_console() -> None:
    """Windows consoles and CI runners default to cp1252, which cannot print
    "✓", "═" or "≈": write UTF-8, and replace what a console cannot show."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
    ap = argparse.ArgumentParser(description="Swarmbly AI installer")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--quick", action="store_true", help="install everything recommended, no questions")
    g.add_argument("--custom", action="store_true", help="step by step")
    g.add_argument("--doctor", action="store_true", help="check an existing installation")
    g.add_argument("--uninstall", action="store_true")
    ap.add_argument("--yes", "-y", action="store_true", help="with --quick: do not ask to start")
    ap.add_argument("--dry-run", action="store_true", help="show the plan, change nothing")
    ap.add_argument("--lang", choices=["es", "en"])
    ap.add_argument("--venv", help="environment folder (default: .venv here)")
    ap.add_argument("--dev", action="store_true", help="editable install and test tools")
    ap.add_argument("--sources", help="a documents folder for the local memory")
    ap.add_argument("--skip", default="", help="comma-separated steps to skip: "
                    "ollama,models,pdf,searxng,shortcuts,sources")
    args = ap.parse_args(argv)
    lang = pick_lang(args.lang)
    if sys.version_info < (3, 10):
        print("Swarmbly AI needs Python 3.10+." if lang == "en" else "Swarmbly AI necesita Python 3.10+.")
        return 1
    mode = ("quick" if args.quick else "custom" if args.custom else
            "doctor" if args.doctor else "uninstall" if args.uninstall else None)
    ui = UI(lang, interactive=True, dry=args.dry_run)
    ui.say(c("1", "═" * 60))
    ui.say(c("1", "  " + ui["title"]))
    ui.say(c("1", "═" * 60))
    if mode is None:
        for line in ui["intro"].split("\n"):
            ui.say(line)
        ui.say()
        mode = menu(ui)
    args.mode = mode
    ctx = Ctx(args, ui)
    if mode == "exit":
        return 0
    if mode == "doctor":
        return doctor(ctx)
    if mode == "uninstall":
        return uninstall(ctx)
    if mode == "quick":
        ui.say()
        quick_plan(ui, ctx)
        if not args.yes and not ui.ask(ui["proceed"], default=True):
            return 1
        ui.interactive = False            # no more questions after this point
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    names = {"step_ollama": "ollama", "step_models": "models", "step_pdf": "pdf",
             "step_searx": "searxng", "step_shortcuts": "shortcuts", "step_sources": "sources"}
    total = len(STEPS)
    for n, (key, why_key, fn) in enumerate(STEPS, 1):
        if mode == "quick" and key == "step_sources" and not ctx.sources:
            continue
        ui.header(n, total, ui[key], ui[why_key].format(ram=f"{ram_gb():.0f}")
                  if mode == "custom" else "")
        if names.get(key) in skip:
            ui.result(ui[key], "skipped", "--skip")
            continue
        try:
            fn(ctx)
        except RuntimeError as exc:
            ui.result(ui[key], "failed", str(exc)[:200])
            if key in ("step_env", "step_modules"):
                ui.say(ui["log"].format(path=LOG))
                return 1
    ui.say()
    if not ui.dry:
        doctor(ctx)
    ui.say()
    ui.say(c("1", ui["summary"]))
    for title, status, detail in ui.results:
        ui.say(f"  {ui[status]:10} {title}{(' — ' + detail) if detail else ''}")
    if ui.pending:
        ui.say(c("33", ui["pending_title"]))
        for p in dict.fromkeys(ui.pending):
            ui.say("  • " + p)
    launcher = STATE / "bin" / ("swarmbly.cmd" if IS_WIN else "swarmbly")
    cmd = "swarmbly" if (Path.home() / ".local" / "bin" / "swarmbly").exists() else str(launcher)
    ui.say()
    ui.say(ui["start_hint"].format(cmd=cmd))
    ui.say(ui["log"].format(path=LOG))
    ui.say(c("2", ui["support"]))
    if mode == "custom" and not ui.dry and launcher.exists() and ui.ask(ui["launch_now"], default=True):
        subprocess.Popen([str(launcher)], start_new_session=not IS_WIN)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        sys.exit(130)
