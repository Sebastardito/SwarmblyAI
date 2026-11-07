#!/usr/bin/env python3
"""Run a sealed S2/S3 benchmark bank against Swarmbly AI, blind.

The bank stays private: this script reads the cases, the documents and the
sealed manifest by itself and never prints a question, a document or an
answer. It prints only case IDs, timings and counts. Everything it records
goes into a run folder inside the bank.

What it does, in order:

1. Verifies the bank's SHA-256 seal; refuses to run if any sealed file changed.
2. Parses the case cards (fields ID, Pregunta and Documentos only).
3. For each case, starts a fresh Swarmbly App instance (its own data folder,
   no history) with the case documents as the user's sources (LCE C1).
4. Blocks the network for the app: every HTTP(S) request outside this
   computer goes to a local proxy that refuses it and records where it was
   going. Ollama (local) and a simulated public registry (local) are allowed.
5. The simulated public registry plays the role of a public source: it
   answers with the bank's frozen public snapshot and records exactly what
   was asked.
6. Sends the question once, waits for the answer, and writes the answer, the
   execution metadata and a privacy receipt observed by the harness.
7. Verifies the seal again after the run.

Banks supported (detected from the folder): Banco_SwarmblyAI 1.0.0 ("v2",
05_SELLO/SELLO.sha256) and the v1 package (SEALED_MANIFEST.sha256).

Standard library only. Example:

    python3 bench/run_bank.py --bank ~/BancoPreguntasS2S3/v2 \\
        --model qwen2.5:7b --persona "Vera Cárdenas Moll" --executor "Seb"
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HARNESS_VERSION = "1.0.0"
RECEIPT_SCHEMA = "swarmbly.privacy_receipt/1.0"
REGISTRY_NAME = "registro_publico_simulado"
_HEX64 = re.compile(r"^([0-9a-f]{64})\s+\*?(.+)$")
_FIELD = re.compile(r"^([A-ZÁÉÍÓÚÑa-záéíóúñ][\wÁÉÍÓÚÑáéíóúñ ]{0,40}):(.*)$")
_WORD = re.compile(r"[\wÁÉÍÓÚÑáéíóúñü]+", re.UNICODE)


# --------------------------------------------------------------------------------------
# Bank layout, seal and cases
# --------------------------------------------------------------------------------------
@dataclass
class Bank:
    root: Path
    kind: str                    # "v2" | "v1"
    manifest: Path
    cases_file: Path
    corpus_dir: Path | None      # v2: shared corpus
    docs_dir: Path | None        # v1: per-case fixtures
    runs_dir: Path


def detect_bank(root: Path) -> Bank:
    root = root.expanduser().resolve()
    if (root / "05_SELLO" / "SELLO.sha256").is_file():
        return Bank(root, "v2", root / "05_SELLO" / "SELLO.sha256",
                    root / "02_CASOS_RESERVADOS" / "S2_S3_reservados.md",
                    root / "01_MATERIALES" / "corpus_reservado", None,
                    root / "04_SALIDAS_AUDITORIA" / "ejecuciones")
    if (root / "SEALED_MANIFEST.sha256").is_file():
        return Bank(root, "v1", root / "SEALED_MANIFEST.sha256",
                    root / "reserved" / "runner_pack.md", None, root / "fixtures",
                    root / "ejecuciones")
    raise SystemExit(f"not a sealed bank (no 05_SELLO/SELLO.sha256 or SEALED_MANIFEST.sha256): {root}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_seal(bank: Bank) -> dict[str, Any]:
    """Every '<sha256>  <path>' line of the manifest, checked from the bank root."""
    ok, failed = 0, []
    for line in bank.manifest.read_text(encoding="utf-8").splitlines():
        m = _HEX64.match(line.strip())
        if not m:
            continue
        expected, rel = m.group(1), m.group(2).strip()
        target = bank.root / rel
        if not target.is_file():
            failed.append({"archivo": rel, "motivo": "no existe"})
        elif sha256_file(target) != expected:
            failed.append({"archivo": rel, "motivo": "huella distinta"})
        else:
            ok += 1
    return {"ok": ok > 0 and not failed, "archivos_ok": ok, "fallos": failed,
            "hash_manifiesto": sha256_file(bank.manifest),
            "fecha_utc": utc_now()}


@dataclass
class Case:
    case_id: str
    question: str
    documents: list[str] = field(default_factory=list)


def _field_value(block: str, name: str) -> str:
    """A card field, with its indented continuation lines, joined by spaces."""
    lines = block.splitlines()
    out: list[str] = []
    taking = False
    for line in lines:
        m = _FIELD.match(line)
        if m and not line.startswith((" ", "\t")):
            if taking:
                break
            if m.group(1).strip() == name:
                taking = True
                out.append(m.group(2).strip())
            continue
        if taking:
            if line.startswith((" ", "\t")):
                out.append(line.strip())
            elif line.strip():
                break
    return " ".join(x for x in out if x).strip()


def parse_cases(path: Path) -> list[Case]:
    text = path.read_text(encoding="utf-8")
    cases: list[Case] = []
    for block in re.findall(r"```text\n(.*?)```", text, re.S):
        case_id = _field_value(block, "ID")
        question = _field_value(block, "Pregunta")
        if not case_id or not question:
            continue
        docs_text = _field_value(block, "Documentos")
        docs = re.findall(r"[\w./-]+\.(?:md|csv|txt|json|docx|pdf|html)|\bF\d\d\b", docs_text)
        cases.append(Case(case_id, question, docs))
    return cases


def is_public_fixture(name: str) -> bool:
    """A frozen public source served by the simulated registry, never a user source."""
    low = name.lower()
    return "fixtures_publicos" in low or "publico" in low or low.startswith("iucn_")


def case_documents(bank: Bank, case: Case) -> tuple[list[Path], list[Path]]:
    """(user documents, public fixtures) for one case."""
    user, public = [], []
    if bank.kind == "v2":
        assert bank.corpus_dir is not None
        user = sorted(p for p in bank.corpus_dir.iterdir() if p.is_file() and not p.name.startswith("."))
        for ref in case.documents:
            if is_public_fixture(ref):
                cand = bank.root / ref if "/" in ref else bank.root / "01_MATERIALES" / "fixtures_publicos" / ref
                if cand.is_file():
                    public.append(cand)
        return user, public
    assert bank.docs_dir is not None
    for ref in case.documents:
        m = re.fullmatch(r"F(\d\d)", ref)
        matches = sorted(bank.docs_dir.glob(f"{m.group(1)}_*")) if m else [bank.docs_dir / ref]
        for p in matches:
            if p.is_file():
                (public if is_public_fixture(p.name) else user).append(p)
    return user, public


# --------------------------------------------------------------------------------------
# Network: a proxy that refuses and records, and a simulated public registry
# --------------------------------------------------------------------------------------
class EventLog:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.events: list[dict[str, Any]] = []

    def add(self, **event: Any) -> None:
        event.setdefault("t", utc_now())
        with self._lock:
            self.events.append(event)

    def drain(self) -> list[dict[str, Any]]:
        with self._lock:
            out, self.events = self.events, []
        return out


class _ProxyHandler(socketserver.StreamRequestHandler):
    log: EventLog

    def handle(self) -> None:
        try:
            first = self.rfile.readline(8192).decode("latin-1").strip()
        except Exception:
            return
        parts = first.split()
        method = parts[0] if parts else ""
        target = parts[1] if len(parts) > 1 else ""
        size = len(first)
        while True:                                 # headers (counted, not stored)
            line = self.rfile.readline(8192)
            if not line or line in (b"\r\n", b"\n"):
                break
            size += len(line)
        if method == "CONNECT":
            host, _, port = target.rpartition(":")
            entry = {"metodo": "CONNECT", "destino": host or target, "puerto": int(port or 443),
                     "ruta": "", "consulta": ""}
        else:
            u = urllib.parse.urlsplit(target)
            entry = {"metodo": method, "destino": u.hostname or "", "puerto": u.port or 80,
                     "ruta": u.path, "consulta": u.query}
        self.log.add(tipo_evento="salida_bloqueada", bytes_cabecera=size, **entry)
        try:
            self.wfile.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        except Exception:
            pass


class EgressProxy:
    """Refuses every outbound request and records its destination."""

    def __init__(self) -> None:
        self.log = EventLog()
        handler = type("Handler", (_ProxyHandler,), {"log": self.log})
        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def close(self) -> None:
        self.server.shutdown()


class PublicRegistry:
    """A local stand-in for a public search source (SearXNG JSON API).

    It answers with the frozen public snapshot(s) of the current case and
    records every query exactly as received.
    """

    def __init__(self) -> None:
        self.log = EventLog()
        self.fixtures: list[Path] = []
        registry = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:  # silent
                return

            def do_GET(self) -> None:  # noqa: N802
                u = urllib.parse.urlsplit(self.path)
                params = dict(urllib.parse.parse_qsl(u.query))
                q = params.get("q", "")
                results = registry.answer(q) if u.path.rstrip("/") == "/search" else []
                registry.log.add(tipo_evento="consulta_registro", ruta=u.path, q=q,
                                 bytes=len(q.encode("utf-8")), resultados=len(results))
                body = json.dumps({"query": q, "results": results}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def answer(self, q: str) -> list[dict[str, Any]]:
        words = {w.lower() for w in _WORD.findall(q) if len(w) >= 4}
        out = []
        for path in self.fixtures:
            text = path.read_text(encoding="utf-8")
            head = text[:600].lower()
            if words and any(w in head for w in words):
                title = next((ln.lstrip("# ").strip() for ln in text.splitlines() if ln.strip()), path.stem)
                url = next(iter(re.findall(r"https?://[^\s)>\]]+", text)), f"https://registry.invalid/{path.name}")
                body = re.sub(r"\s+", " ", re.sub(r"[#>*`|]", " ", text)).strip()
                out.append({"title": title[:200], "content": body, "url": url,
                            "engines": [REGISTRY_NAME]})
        return out

    def close(self) -> None:
        self.server.shutdown()


# --------------------------------------------------------------------------------------
# Swarmbly App instance
# --------------------------------------------------------------------------------------
CONFIG_SNIPPET = r"""
import json, sys
from swarmbly_app.paths import DataDirs
from swarmbly_app.config import Config
dirs = DataDirs(sys.argv[1]); dirs.ensure()
cfg = Config(dirs)
cfg.update(json.loads(sys.argv[2]))
print("ok")
"""


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def http_json(method: str, url: str, token: str = "", body: Any = None,
              timeout: float = 30.0) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("X-Swarmbly-Token", token)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # local only
    with opener.open(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else None


class AppInstance:
    def __init__(self, python: str, data_dir: Path, sources: Path, settings: dict[str, Any],
                 proxy_url: str, log_path: Path) -> None:
        self.python, self.data_dir, self.sources = python, data_dir, sources
        self.settings, self.proxy_url, self.log_path = settings, proxy_url, log_path
        self.port = free_port()
        self.proc: subprocess.Popen | None = None
        self.token = ""

    def env(self) -> dict[str, str]:
        env = dict(os.environ)
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            env[key] = self.proxy_url
        env["NO_PROXY"] = env["no_proxy"] = "127.0.0.1,localhost,::1"
        env["SWARMBLY_DATA_DIR"] = str(self.data_dir)
        env.pop("SSLKEYLOGFILE", None)
        return env

    def start(self, timeout: float = 90.0) -> None:
        subprocess.run([self.python, "-c", CONFIG_SNIPPET, str(self.data_dir),
                        json.dumps(self.settings)], check=True, env=self.env(),
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self._log = open(self.log_path, "w", encoding="utf-8")
        self.proc = subprocess.Popen(
            [self.python, "-m", "swarmbly_app", "headless", "--data-dir", str(self.data_dir),
             "--host", "127.0.0.1", "--port", str(self.port)],
            env=self.env(), stdout=self._log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"the app exited with code {self.proc.returncode} (see {self.log_path})")
            try:
                http_json("GET", f"{self.base}/api/health", timeout=3)
                token_file = self.data_dir / "api_token"
                if token_file.is_file():
                    self.token = token_file.read_text(encoding="utf-8").strip()
                    return
            except Exception:
                pass
            time.sleep(0.5)
        raise RuntimeError("the app did not answer /api/health in time")

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def ask(self, question: str, timeout: float) -> dict[str, Any]:
        conv = http_json("POST", f"{self.base}/api/conversations", self.token, {})
        started = time.monotonic()
        sent = http_json("POST", f"{self.base}/api/conversations/{conv['id']}/messages",
                         self.token, {"text": question}, timeout=60)
        msg_id = sent["assistant_message"]["id"]
        while time.monotonic() - started < timeout:
            time.sleep(1.5)
            for m in http_json("GET", f"{self.base}/api/conversations/{conv['id']}/messages",
                               self.token):
                if m["id"] == msg_id and (m.get("meta") or {}).get("status") not in (None, "running"):
                    return {"message": m, "latency_s": round(time.monotonic() - started, 2),
                            "timeout": False}
        return {"message": None, "latency_s": round(time.monotonic() - started, 2), "timeout": True}

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if getattr(self, "_log", None):
            self._log.close()


# --------------------------------------------------------------------------------------
# Privacy receipt observed by the harness
# --------------------------------------------------------------------------------------
def shingles(text: str, n: int = 8) -> set[str]:
    words = [w.lower() for w in _WORD.findall(text)]
    return {" ".join(words[i:i + n]) for i in range(max(0, len(words) - n + 1))}


def classify_payload(value: str, passages: set[str], persona: list[str]) -> str:
    folded = " ".join(w.lower() for w in _WORD.findall(value))
    if any(sh in folded for sh in passages):
        return "pasaje"
    names = [w.lower() for w in persona if len(w) >= 3]
    if names and sum(1 for w in names if re.search(rf"\b{re.escape(w)}\b", folded)) >= min(2, len(names)):
        return "nombre_personal"
    return "entidad_publica"


def build_receipt(case_id: str, answer: str, meta: dict[str, Any], registry_events: list[dict],
                  proxy_events: list[dict], passages: set[str], persona: list[str]) -> dict[str, Any]:
    envios = []
    for ev in registry_events:
        if not ev.get("q"):
            continue
        envios.append({"destino": REGISTRY_NAME,
                       "tipo": classify_payload(ev["q"], passages, persona),
                       "valor": ev["q"], "bytes": ev.get("bytes", 0),
                       "motivo": "consulta a la fuente pública (registro simulado, local)"})
    blocked = []
    for ev in proxy_events:
        visible = " ".join(x for x in (ev.get("ruta", ""), ev.get("consulta", "")) if x)
        blocked.append({"destino": f"{ev.get('destino')}:{ev.get('puerto')}", "metodo": ev.get("metodo"),
                        "tipo": classify_payload(urllib.parse.unquote_plus(visible), passages, persona)
                        if visible else "no_visible (HTTPS cifrado)",
                        "salio": False})
    executed = meta.get("executed", "")
    routing = ((meta.get("swarm") or {}).get("routing") or {}) if isinstance(meta.get("swarm"), dict) else {}
    lane = str(routing.get("lane") or "").upper()
    carril = {"PUBLIC": "público", "SENSITIVE": "sensible", "PERSONAL": "personal"}.get(lane, "no_informado")
    ruta = "fragmentada" if executed == "distributed" else ("local+consulta_publica" if envios else "local")
    swarm = meta.get("swarm") if isinstance(meta.get("swarm"), dict) else {}
    fragments = int(swarm.get("n_tasks") or swarm.get("tasks") or 0) if executed == "distributed" else 0
    return {
        "schema": RECEIPT_SCHEMA,
        "recibo_id": f"R-{case_id}-{hashlib.sha256((case_id + answer).encode()).hexdigest()[:8]}",
        "caso": case_id,
        "fecha_utc": utc_now(),
        "carril": carril,
        "ruta": ruta,
        "destinos_declarados": ["local"] + ([REGISTRY_NAME] if envios else []),
        "consentimiento": {"requerido": None, "otorgado": None, "alcance": "",
                           "nota": "Swarmbly App 3.0.x no registra consentimiento; campo no informado por la app"},
        "envios": envios,
        "pasajes_enviados": sum(1 for e in envios if e["tipo"] == "pasaje"),
        "nombres_personales_enviados": sum(1 for e in envios if e["tipo"] == "nombre_personal"),
        "bytes_salientes": sum(int(e["bytes"]) for e in envios),
        "fragmentos_creados": fragments,
        "respuesta_sintetica": answer,
        "hash_respuesta_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
        "origen": "observado por el arnés bench/run_bank.py (la app 3.0.x no emite recibo propio)",
        "intentos_bloqueados": blocked,
    }


# --------------------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------------------
def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def find_python(explicit: str | None) -> str:
    if explicit:
        return explicit
    here = Path(__file__).resolve().parents[1]
    for cand in (here / ".venv" / "bin" / "python", here / ".venv" / "Scripts" / "python.exe",
                 here.parent / "SwarmblyApp" / ".venv" / "bin" / "python"):
        if cand.is_file():
            return str(cand)
    return sys.executable


def installed_versions(python: str) -> dict[str, str]:
    code = ("import json, importlib.metadata as m\n"
            "out = {}\n"
            "for p in ('swarmbly-app', 'swarmbly-lce', 'swarmbly-v0'):\n"
            "    try: out[p] = m.version(p)\n"
            "    except Exception: out[p] = 'no instalado'\n"
            "print(json.dumps(out))")
    try:
        return json.loads(subprocess.run([python, "-c", code], capture_output=True, text=True,
                                         timeout=60).stdout.strip())
    except Exception:
        return {}


def git_commit(path: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True,
                              text=True, timeout=10).stdout.strip() or "desconocido"
    except Exception:
        return "desconocido"


def ollama_check(url: str, models: list[str]) -> tuple[str, list[str]]:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url.rstrip("/") + "/api/version", timeout=5) as resp:
        version = json.loads(resp.read().decode()).get("version", "?")
    with opener.open(url.rstrip("/") + "/api/tags", timeout=5) as resp:
        names = {m.get("name", "") for m in json.loads(resp.read().decode()).get("models", [])}
    have = names | {n.removesuffix(":latest") for n in names}
    return version, [m for m in models if m and m not in have]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Blind run of a sealed S2/S3 bank against Swarmbly AI")
    ap.add_argument("--bank", required=True, help="bank root (v2: the folder with 05_SELLO; v1: the folder with SEALED_MANIFEST.sha256)")
    ap.add_argument("--model", required=True, help="chat model served by Ollama, e.g. qwen2.5:7b")
    ap.add_argument("--embed-model", default="nomic-embed-text")
    ap.add_argument("--ollama", default="http://127.0.0.1:11434")
    ap.add_argument("--persona", default="", help="name of the bank's fictitious user, to detect if it is ever sent")
    ap.add_argument("--executor", default="", help="who runs the battery (for the run record)")
    ap.add_argument("--witness", default="", help="optional witness")
    ap.add_argument("--python", default=None, help="Python with Swarmbly installed (default: the installer's .venv)")
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--case-timeout", type=float, default=1200.0, help="seconds per case")
    ap.add_argument("--check", action="store_true",
                    help="only verify the seal, the cases and the documents of each case; run nothing")
    ap.add_argument("--only", default="", help="comma-separated case IDs (diagnostics only; a scored run uses all)")
    args = ap.parse_args(argv)

    bank = detect_bank(Path(args.bank))
    python = find_python(args.python)
    print(f"Swarmbly bench {HARNESS_VERSION} · banco {bank.kind} · {bank.root}")

    seal = verify_seal(bank)
    print(f"[1/5] sello: {'OK' if seal['ok'] else 'FALLA'} · {seal['archivos_ok']} archivos · manifiesto {seal['hash_manifiesto'][:12]}")
    if not seal["ok"]:
        print("      archivos con problema:", ", ".join(f["archivo"] for f in seal["fallos"]))
        print("      La corrida no es válida con un sello roto. No se ejecuta nada.")
        return 2

    cases = parse_cases(bank.cases_file)
    if args.only:
        wanted = {c.strip() for c in args.only.split(",")}
        cases = [c for c in cases if c.case_id in wanted]
    print(f"[2/5] casos: {len(cases)} ({', '.join(c.case_id for c in cases)})")
    if not cases:
        return 2
    if args.check:
        for c in cases:
            user, public = case_documents(bank, c)
            missing = [d for d in c.documents if not any(d.endswith(p.name) or p.name.startswith(d[1:] + "_")
                                                         for p in user + public)]
            print(f"      {c.case_id:6} pregunta {len(c.question):4} caracteres · fuentes {len(user)} · "
                  f"públicas {len(public)}" + (f" · NO ENCONTRADOS: {len(missing)}" if missing else ""))
        print("      Comprobación terminada; no se ejecutó nada.")
        return 0

    versions = installed_versions(python)
    if versions.get("swarmbly-app", "no instalado") == "no instalado":
        print(f"      Swarmbly App no está instalada en {python}. Usa --python o el instalador (docs/INSTALL.md).")
        return 2
    try:
        ollama_version, missing = ollama_check(args.ollama, [args.model, args.embed_model])
    except Exception as exc:
        print(f"      Ollama no responde en {args.ollama}: {exc}")
        return 2
    if missing:
        print("      Faltan modelos en Ollama: " + ", ".join(missing) + ". Descárgalos con 'ollama pull <modelo>'.")
        return 2
    print(f"[3/5] sistema: Swarmbly App {versions.get('swarmbly-app')} · LCE {versions.get('swarmbly-lce')} · "
          f"Core {versions.get('swarmbly-v0')} · Ollama {ollama_version} · {args.model}")

    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + re.sub(r"[^\w.-]", "-", args.model)
    run_dir = bank.runs_dir / run_id
    (run_dir / "casos").mkdir(parents=True, exist_ok=False)
    (run_dir / "logs").mkdir()
    proxy, registry = EgressProxy(), PublicRegistry()
    persona = _WORD.findall(args.persona)
    print(f"[4/5] ejecución {run_id} · red bloqueada (proxy {proxy.port}) · registro público simulado ({registry.port})")

    summary, failures = [], 0
    started_at = utc_now()
    try:
        for case in cases:
            user_docs, public_docs = case_documents(bank, case)
            registry.fixtures = public_docs
            work = Path(tempfile.mkdtemp(prefix=f"swarmbly-bench-{case.case_id}-"))
            sources = work / "fuentes"
            sources.mkdir()
            for p in user_docs:
                shutil.copy2(p, sources / p.name)
            passages: set[str] = set()
            for p in user_docs:
                try:
                    passages |= shingles(p.read_text(encoding="utf-8", errors="replace"))
                except Exception:
                    pass
            settings = {
                "setup_completed": True, "language": "es",
                "model.backend": "ollama", "model.backend_url": args.ollama,
                "model.model_name": args.model, "model.embed_model": args.embed_model,
                "model.temperature": args.temperature,
                "lce.enabled": True, "lce.level": "C1", "lce.sources_dirs": [str(sources)],
                "evidence.providers": ["web"], "evidence.searxng_url": registry.url,
                "evidence.searxng_managed": "",
                "swarm.p2p_port": free_port(),      # never collide with a running Swarmbly
            }
            app = AppInstance(python, work / "datos", sources, settings, proxy.url,
                              run_dir / "logs" / f"{case.case_id}_app.log")
            proxy.log.drain(); registry.log.drain()
            record: dict[str, Any] = {"caso": case.case_id, "pregunta": case.question,
                                      "documentos_usuario": [p.name for p in user_docs],
                                      "fixtures_publicos": [p.name for p in public_docs],
                                      "modelo": args.model, "inicio_utc": utc_now()}
            status = "error"
            try:
                app.start()
                result = app.ask(case.question, args.case_timeout)
                msg = result["message"] or {}
                meta = msg.get("meta") or {}
                answer = msg.get("content") or ""
                status = "timeout" if result["timeout"] else str(meta.get("status", "?"))
                record.update({"respuesta": answer, "estado": status, "latencia_s": result["latency_s"],
                               "meta": meta, "etapas": msg.get("stages") or []})
            except Exception as exc:
                record.update({"respuesta": "", "estado": "error", "error": str(exc)[:500], "meta": {}})
                answer, meta = "", {}
            finally:
                app.stop()
            reg_ev, prx_ev = registry.log.drain(), proxy.log.drain()
            receipt = build_receipt(case.case_id, record.get("respuesta", ""), record.get("meta") or {},
                                    reg_ev, prx_ev, passages, persona)
            record["recibo"] = receipt
            record["fin_utc"] = utc_now()
            (run_dir / "casos" / f"{case.case_id}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            (run_dir / "casos" / f"{case.case_id}_recibo.json").write_text(
                json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
            with open(run_dir / "logs" / "red.jsonl", "a", encoding="utf-8") as fh:
                for ev in reg_ev + prx_ev:
                    fh.write(json.dumps({"caso": case.case_id, **ev}, ensure_ascii=False) + "\n")
            technical = status in ("error", "timeout", "failed")
            failures += technical
            row = {"caso": case.case_id, "estado": status, "latencia_s": record.get("latencia_s"),
                   "envios": len(receipt["envios"]), "intentos_bloqueados": len(receipt["intentos_bloqueados"]),
                   "pasajes": receipt["pasajes_enviados"], "nombres": receipt["nombres_personales_enviados"],
                   "ejecutado": (record.get("meta") or {}).get("executed", "")}
            summary.append(row)
            print(f"      {case.case_id:6} {status:8} {str(row['latencia_s']):>7} s · envíos {row['envios']} · "
                  f"bloqueados {row['intentos_bloqueados']} · pasajes {row['pasajes']} · nombres {row['nombres']}")
            shutil.rmtree(work, ignore_errors=True)
    finally:
        proxy.close()
        registry.close()

    post = verify_seal(bank)
    (run_dir / "verificacion_sello_post.json").write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "resumen.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    umbrella = Path(__file__).resolve().parents[1]
    registro = f"""# Registro de ejecución

```text
run_id:              {run_id}
fecha_utc:           {started_at} → {utc_now()}
proyecto:            Swarmbly AI
version_o_commit:    {git_commit(umbrella)} (repositorio del arnés); paquetes: {json.dumps(versions, ensure_ascii=False)}
modelo(s):           {args.model} (chat) · {args.embed_model} (embeddings)
proveedor(es):       Ollama {ollama_version} en {args.ollama}
sistema_operativo:   {platform.platform()}
modo:                sin_red (internet bloqueado por proxy; fuente pública = registro simulado local con la instantánea congelada)
semilla:             no controlada (Swarmbly App 3.0.x no pasa semilla a Ollama)
temperatura:         {args.temperature}
casos_ejecutados:    {len(summary)}
fallos_tecnicos:     {failures}
incidencias:         {'ninguna' if not failures else 'ver casos con estado error/timeout; el protocolo pide repetir la batería completa'}
autor_de_la_ejecucion: {args.executor}
testigo:             {args.witness}
sello_verificado:    sí, antes ({seal['fecha_utc']}) y después ({post['fecha_utc']}: {'OK' if post['ok'] else 'FALLA'})
hash_del_manifiesto: {seal['hash_manifiesto']}
arnes:               bench/run_bank.py {HARNESS_VERSION}
```

## Configuración aplicada a cada instancia de la app

- Instancia nueva por caso (carpeta de datos propia, sin historial).
- Fuentes del usuario (LCE C1): {'corpus completo' if bank.kind == 'v2' else 'documentos listados en la ficha'}; las instantáneas públicas no se cargan como fuentes: las sirve el registro simulado.
- Evidencia pública: proveedor web apuntando al registro simulado local; Wikidata, Wikipedia y PubMed desactivados (sin red).
- Modo de conversación: el predeterminado de la app (local). Temperatura {args.temperature}.
- Red: todo HTTP(S) fuera de este equipo pasa por un proxy que lo rechaza y lo registra (`logs/red.jsonl`).

## Recibos

Los recibos los construye el arnés a partir de lo observado (registro simulado y proxy). La app 3.0.x no
emite recibo propio, ni carril en modo local, ni consentimiento: esos campos quedan como «no informado».
"""
    (run_dir / "registro_ejecucion.md").write_text(registro, encoding="utf-8")
    print(f"[5/5] sello después: {'OK' if post['ok'] else 'FALLA'} · fallos técnicos: {failures} · resultados en {run_dir}")
    return 0 if post["ok"] and not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
