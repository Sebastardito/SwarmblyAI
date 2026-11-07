"""Application state: wires every module together (composition root).

Phase 2 adds the P2P node manager, the worker service and the distributed
orchestrator. The P2P listener starts with the app (independent access
limits); discovery and the worker role follow the configuration.
"""

from __future__ import annotations

import time

from .chat import ChatService
from .config import Config
from .db import Database
from .events import EventBus
from .identity import IdentityManager, NodeIdentity
from .inference.registry import BackendRegistry
from .lce_adapter import LCEAdapter
from .models import ModelManager
from .paths import DataDirs
from .p2p.node import NodeManager
from .p2p.worker import WorkerService


def _app_build() -> str | None:
    """Short commit of the running checkout, if it is a git checkout."""
    import subprocess
    from pathlib import Path
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=Path(__file__).resolve().parent.parent,
                             capture_output=True, text=True, timeout=2)
        return out.stdout.strip() or None if out.returncode == 0 else None
    except Exception:
        return None


_BUILD = _app_build()


def _node_info() -> dict:
    """What a node says about itself besides its models (app extension of
    the SPEC §12 ``resources`` block). Heterogeneous rounds (P3b–P3i) could
    not tell which version or system each node ran from the network."""
    import platform

    from . import __version__
    return {"os": f"{platform.system()} {platform.release()}".strip(),
            "machine": platform.machine(),
            "app_version": __version__, "app_build": _BUILD}


def _build_advertisement(state: "AppState") -> dict:
    """SPEC §12 node profile from live state.

    ``models`` lists only what this node actually serves to third parties
    (worker role on); ``policy.kinds`` is empty while the role is off, so no
    peer offers us a task we would refuse. ``endpoint`` (app extension, SPEC
    §3-tolerant) tells inbound peers which port to dial back.
    """
    import psutil
    cfg = state.config.all()
    worker_policy = state.worker.policy() if state.worker else {"kinds": []}
    models = []
    if worker_policy.get("kinds") and state.worker is not None:
        for name in state.worker.shared_models():
            info = state.model_info(name)
            models.append({"family": info.get("family") or name.split(":")[0],
                           "version": name,
                           "quantization": info.get("quantization", ""),
                           "ctx": None, "tok_per_s_est": None})
    vm = psutil.virtual_memory()
    return {
        "node_id": state.identity.node_id,
        "models": models,
        "capabilities": {"tee": False, "attestation": None},
        "swarm": None,
        "resources": {"vram_mb": None, "ram_mb": int(vm.total // (1024 ** 2)),
                      # free memory when this advertisement was built
                      "ram_available_mb": int(vm.available // (1024 ** 2)),
                      **_node_info()},
        "policy": {"max_tokens_per_task":
                   int(cfg["swarm"].get("worker_max_tokens_per_task", 800)),
                   "kinds": list(worker_policy.get("kinds", [])),
                   # app extension: concurrent tasks this node accepts
                   "max_concurrent": int(worker_policy.get("max_concurrent", 1))},
        "reputation": None,  # self-reported reputation is never trusted (SPEC §12)
        "endpoint": {"port": state.nodes.listen_port},
    }


class AppState:
    """One instance per process; built once at startup."""

    def __init__(self, data_dir: str | None = None):
        self.started_at = time.time()
        self._stopped = False
        # 1. Boot dirs (CLI/env) → 2. config may override data_dir → 3. effective dirs
        boot_dirs = DataDirs(data_dir)
        self.config = Config(boot_dirs)
        configured = self.config.get("data_dir")
        self.dirs = DataDirs(configured) if configured else boot_dirs
        self.dirs.ensure()
        if str(self.dirs.root) != str(boot_dirs.root):
            self.config = Config(self.dirs)  # re-read from the effective location
        # 3.0.1: API keys live in the keystore, and every outbound call is
        # checked against the user's destinations policy.
        from . import egress, keystore
        keystore.configure(self.dirs.root)
        try:
            keystore.migrate(self.config)
        except Exception:
            pass                          # a keychain problem never blocks start-up
        egress.configure(self.config.all)
        self.db = Database(self.dirs.db_path())
        self.bus = EventBus()
        self.identity_manager = IdentityManager(self.dirs.identity_key_path())
        self.identity: NodeIdentity = self.identity_manager.load_or_create()
        self.model_manager = ModelManager()
        self.backends = BackendRegistry()
        self.lce = LCEAdapter(self.dirs)
        self.nodes = NodeManager(self.identity_manager, self.config, self.db,
                                 self.bus, lambda: _build_advertisement(self),
                                 dirs=self.dirs)
        self.worker: WorkerService | None = None
        from .console import ConsoleReporter
        self.console = ConsoleReporter(self.bus, lambda: self.nodes.peers)
        self.orchestrator = None  # built lazily with a live local backend
        self.latency = None       # p95 history shared across orchestrator rebuilds
        from .engine.scheduler import SpeedStats
        self.speed = SpeedStats()  # tokens/s per (node, model), shared the same way
        self.chat = ChatService(self.db, self.bus, self.backends,
                                self.config.all, self.get_orchestrator)
        self.chat.report_sink = self._auto_report
        self.chat.self_node = self.identity.node_id[:12]
        self.chat.retriever = self._lce_retrieve
        self.chat.retrieval_active = self._lce_active
        self.chat.retrieval_candidates = lambda: list(getattr(self.lce, "last_candidates", []))
        self.chat.glossary = lambda text, project_id="": (
            self.lce.glossary_terms(text, roots=self.c1_roots(project_id))
            if self._lce_active(project_id) else "")
        self.chat.glossary_entries = lambda project_id="": (
            self.lce.glossary_entries(roots=self.c1_roots(project_id))
            if self._lce_active(project_id) else [])
        # 3.1: projects — folders of their own, with their chats kept in them
        from .projects import ProjectRegistry
        self.projects = ProjectRegistry(self.config.all, self.config.update)
        self.chat.on_conversation_changed = self._copy_chat_to_project
        self.chat.on_conversation_deleted = self._remove_chat_from_project
        self.chat.project_name = lambda pid: (getattr(self.projects.get(pid), "name", "")
                                              if pid else "")
        self.chat.remember = self.remember
        self.chat.document_list = lambda pid: self.lce.list_sources(roots=self.c1_roots(pid))
        self.chat.document_spans = lambda pid, doc: self.lce.document_spans(
            doc, roots=self.c1_roots(pid))
        self.sync_projects()
        from .doctor import Installer
        from .model_manager import OllamaModels
        self.installer = Installer(self.bus)
        from .searxng import SearxngManager
        self.searxng = SearxngManager(self.dirs.root, self.bus, self.config.all,
                                      self._update_config)
        self.ollama = OllamaModels(self.bus, self._ollama_url, lambda: self.dirs.root)
        # A finished download changes what is installed: refresh detection.
        self.bus.subscribe(lambda e: self.model_manager.invalidate()
                           if e["type"] == "models.pull"
                           and e["payload"].get("status") == "done" else None)

    def _personal_c1(self) -> bool:
        cfg = self.config.all().get("lce") or {}
        return bool(cfg.get("enabled")) and cfg.get("level") in ("C1", "C2", "C3", "C4")

    def _lce_active(self, project_id: str = "") -> bool:
        """C1 for this conversation: a project always reads its own folder;
        a personal conversation reads the personal sources when C1 is on."""
        if project_id:
            return self.projects.get(project_id) is not None
        return self._personal_c1()

    def c1_roots(self, project_id: str = "") -> list:
        """The folders a conversation may read (3.1 isolation): a project's
        sources and memory, plus the personal sources only if the project says
        so; a personal conversation never reads a project."""
        cfg = self.config.all().get("lce") or {}
        personal = self.lce.personal_roots(cfg.get("sources_dirs") or [])
        if not project_id:
            return personal
        project = self.projects.get(project_id)
        if project is None:
            return []
        roots = project.roots()
        if project.include_personal and self._personal_c1():
            roots += personal
        return roots

    def _lce_retrieve(self, query: str, expansion: str = "", project_id: str = "") -> list:
        """LCE C1 retrieval for local answers, over the conversation's folders."""
        if not self._lce_active(project_id):
            return []
        cfg = self.config.all().get("lce") or {}
        return self.lce.retrieve(query, k=int(cfg.get("retrieval_k", 6)),
                                 expansion=expansion, roots=self.c1_roots(project_id),
                                 embed=self._embed if cfg.get("dense_retrieval", True) else None)

    # -- projects (3.1) -------------------------------------------------------------
    def _copy_chat_to_project(self, conversation_id: str) -> None:
        conv = self.db.get_conversation(conversation_id)
        if not conv or not conv.get("project_id"):
            return
        project = self.projects.get(conv["project_id"])
        if project is not None:
            project.write_chat(conv, self.db.get_messages(conversation_id))

    def _remove_chat_from_project(self, conv: dict) -> None:
        project = self.projects.get(conv.get("project_id") or "")
        if project is not None:
            project.chat_file(conv["id"]).unlink(missing_ok=True)

    def remember(self, project_id: str, text: str) -> dict:
        """An explicit "remember …" from the chat, written to local memory:
        the project's ``memory/notas.md``, or ``notas.md`` in the personal
        sources folder. Nothing is sent anywhere; C1 reads it back."""
        from .projects import save_note
        if project_id:
            project = self.projects.require(project_id)
            path = save_note(project.memory, text, title=f"Memoria del proyecto {project.name}")
            return {"scope": "project", "path": str(path.relative_to(project.path)),
                    "full_path": str(path)}
        path = save_note(self.dirs.sources, text, title="Memoria personal")
        return {"scope": "personal", "path": str(path), "full_path": str(path),
                "read_back": self._personal_c1()}

    def save_memory(self, project_id: str, notes: list[str], glossary: list[dict]) -> dict:
        """What the user confirmed from a proposal: notes to notas.md, glossary
        entries to glosario.md (and their definitions as notes)."""
        from .memory_capture import glossary_line
        from .projects import save_glossary, save_note
        if project_id:
            project = self.projects.require(project_id)
            folder, base, title = project.memory, project.path, f"del proyecto {project.name}"
        else:
            folder, base, title = self.dirs.sources, self.dirs.sources, "personal"
        written: dict = {"notes": [], "glossary": []}
        for note in notes or []:
            if note.strip():
                path = save_note(folder, note, title=f"Memoria {title}")
                written["notes"].append(note.strip())
        lines = []
        for g in glossary or []:
            line = glossary_line(g)
            if line:
                lines.append(line)
            if g.get("definition"):
                save_note(folder, f"{g['term']}: {g['definition']}", title=f"Memoria {title}")
        if lines:
            gpath = save_glossary(folder, lines, title=f"Glosario {title}")
            written["glossary"] = lines
            written["glossary_path"] = str(gpath.relative_to(base)) if project_id else str(gpath)
        written["notes_path"] = (str((folder / "notas.md").relative_to(base)) if project_id
                                 else str(folder / "notas.md"))
        return written

    def sync_projects(self, project_id: str | None = None) -> dict[str, int]:
        """Bring into the app the chats a project folder has and the app does
        not (a restored or copied project). The folder's copy is never
        overwritten here."""
        added: dict[str, int] = {}
        from .projects import Project
        for project in self.projects.list():
            if not isinstance(project, Project) or (project_id and project.id != project_id):
                continue
            n = 0
            for data in project.read_chats():
                try:
                    if self.db.import_conversation(data["conversation"],
                                                   data.get("messages") or [], project.id):
                        n += 1
                except Exception:
                    continue
            added[project.id] = n
        return added

    def _embed(self, texts: list[str], kind: str) -> list[list[float]]:
        """Vectors from the local embedding model (Ollama /api/embed); local only."""
        import json as _json
        import urllib.request
        model_cfg = self.config.all().get("model") or {}
        name = model_cfg.get("embed_model") or "nomic-embed-text"
        prefix = ""
        if "nomic" in name:          # nomic-embed-text expects task prefixes
            prefix = "search_query: " if kind == "query" else "search_document: "
        url = (model_cfg.get("backend_url") or self._ollama_url()).rstrip("/")
        url = url[:-3] if url.endswith("/v1") else url
        body = _json.dumps({"model": name, "input": [prefix + t for t in texts]}).encode()
        # Documents' text is passages; a query is the question. A server that is
        # not on this computer only gets them under the destinations policy.
        from . import egress
        egress.check_call(url, len(body), reason=f"embeddings {name}",
                          kind=egress.QUESTION if kind == "query" else egress.PASSAGES)
        req = urllib.request.Request(
            url + "/api/embed", data=body,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:   # noqa: S310 (local server)
            return _json.loads(resp.read().decode())["embeddings"]

    # -- P2P lifecycle -----------------------------------------------------------
    def start_p2p(self) -> None:
        if self.worker is None:
            self.worker = WorkerService(
                self.config, self.db, self.bus, self.identity_manager,
                self.lce, lambda: self.backends.resolve(self.config.all()),
                model_info=self.model_info)
            self.nodes.start(task_handler=self.worker.handle,
                             cancel_handler=self.worker.cancel)

    def _ollama_url(self) -> str:
        model_cfg = self.config.all()["model"]
        if model_cfg.get("backend") in ("auto", "ollama") and model_cfg.get("backend_url"):
            return model_cfg["backend_url"]
        return "http://127.0.0.1:11434"

    def model_info(self, name: str) -> dict:
        """Family/quantization of an installed model as its backend reports it."""
        try:
            model_cfg = self.config.all()["model"]
            infos = self.model_manager.detect_cached(
                model_cfg.get("backend", "auto"), model_cfg.get("backend_url", ""))
        except Exception:
            return {}
        for info in infos:
            for model in info.models or []:
                if model.name == name:
                    return {"family": model.family, "quantization": model.quantization,
                            "size_bytes": model.size_bytes}
        return {}

    def output_dir(self, kind: str = "") -> "Path":
        """Configured output directory (default ``<data>/output``), created on use.
        Never inside the installed package (which may be read-only)."""
        from pathlib import Path
        configured = (self.config.get("results.export_dir")
                      or self.config.get("output_dir"))
        base = Path(configured).expanduser() if configured else self.dirs.root / "output"
        path = base / kind if kind else base
        path.mkdir(parents=True, exist_ok=True)
        return path

    def backup_config(self, name: str) -> None:
        import json
        path = self.dirs.root / f"config.{name}.json"
        path.write_text(json.dumps(self.config.all(), indent=2, ensure_ascii=False),
                        encoding="utf-8")

    def restore_config(self, name: str) -> bool:
        import json
        path = self.dirs.root / f"config.{name}.json"
        if not path.exists():
            return False
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("api", None)  # never restored from a file written by the UI flow
        self.config.update(data)
        return True

    def on_config_changed(self) -> None:
        """Apply configuration at runtime (no restart): discovery on/off,
        re-advertise, rebuild the orchestrator with the current model."""
        self.orchestrator = None
        self.nodes.apply_config()

    def _update_config(self, changes: dict) -> dict:
        merged = self.config.update(changes)
        self.on_config_changed()
        return merged

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        try:
            self.searxng.stop()
        except Exception:
            pass
        self.console.stop()
        self.nodes.stop()
        self.db.close()

    close = stop  # the CLI and tests may use either name

    # -- one-shot helpers ------------------------------------------------------
    def system_report(self) -> dict:
        from . import hardware
        return hardware.detect_all(str(self.dirs.root))

    def health(self) -> dict:
        return {
            "status": "ok",
            "version": __import__("swarmbly_app").__version__,
            "protocol_spec": __import__("swarmbly_app").PROTOCOL_SPEC_VERSION,
            "lce_spec": __import__("swarmbly_app").LCE_SPEC_VERSION,
            "node_id": self.identity.short_id(12),
            "uptime_s": int(time.time() - self.started_at),
            "data_dir": str(self.dirs.root),
        }

    def get_orchestrator(self):
        """Built lazily and rebuilt after any configuration change, so it
        always uses the current local model and backend."""
        from .engine.orchestrator import Orchestrator
        from .engine.scheduler import LatencyStats
        if self.orchestrator is None:
            if self.latency is None:
                self.latency = LatencyStats()
            cfg = self.config.all()
            try:
                local_stream = self.backends.resolve(cfg)
            except Exception:
                local_stream = None  # bridges degrade to plain splices, recorded
            self.orchestrator = Orchestrator(
                self.nodes, self.bus, local_stream, self.config.all,
                local_model=cfg["model"].get("model_name", ""),
                latency=self.latency, speed=self.speed, stats_sink=self._client_stats,
                local_pool_factory=self._local_pool)
        return self.orchestrator

    def _local_pool(self):
        """The device's own multi-model pool, when enabled with ≥2 models."""
        from .engine.directory import LocalPool
        model_cfg = self.config.all()["model"]
        models = [m for m in (model_cfg.get("local_models") or []) if m]
        if not model_cfg.get("multi_model") or len(models) < 2 or self.worker is None:
            return None
        families = {m: (self.model_info(m) or {}).get("family") or m.split(":")[0]
                    for m in models}
        return LocalPool(self.identity.node_id, self.worker, models, families,
                         parallel=int(model_cfg.get("local_parallel", 1) or 1))

    def _auto_report(self, request_id: str) -> None:
        from .reports import render_report
        detail = self.config.get("results.report_detail") or "standard"
        fmt = self.config.get("results.export_format") or "markdown"
        ext = {"markdown": "md", "json": "json", "html": "html"}.get(fmt, "md")
        content = render_report(self.db, request_id, fmt=fmt, detail=detail)
        (self.output_dir("reports") / f"report-{request_id}.{ext}").write_text(
            content, encoding="utf-8")

    def _client_stats(self, **fields: int) -> None:
        import datetime
        self.db.add_stats(datetime.date.today().isoformat(), **fields)
