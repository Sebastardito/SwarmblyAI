"""Application state: wires every module together (composition root).

Phase 2 adds the P2P node manager, the worker service and the distributed
orchestrator. The P2P listener starts with the app (independent access
limits); discovery and the worker role follow the configuration.
"""

from __future__ import annotations

import time

from . import test_hosts
from .chat import ChatService
from .config import Config
from .db import Database
from .events import EventBus
from .identity import IdentityManager, NodeIdentity
from .inference.registry import BackendRegistry
from .lce_adapter import LCEAdapter
from .models import ModelManager, family_for
from .node_roles import (configured_corpus_share, corpus_size_bucket,
                         derive_roles, valid_corpus_name)
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
            models.append({"family": family_for(name, info.get("family", "")),
                           "version": name,
                           "quantization": info.get("quantization", ""),
                           "ctx": None, "tok_per_s_est": None})
    vm = psutil.virtual_memory()
    circles = getattr(state, "circles", None)
    # 3.5, D-018: node roles are only announced while this node is a worker
    # and only for models it really shares. large_model/reasoner come from the
    # models; search/corpus only from the owner's explicit WP4b opt-in. A role
    # adds placement information, never a permission.
    roles = state._node_roles([str(m.get("version") or "") for m in models],
                              announce=bool(worker_policy.get("kinds")),
                              remote=True)
    return {
        "node_id": state.identity.node_id,
        "models": models,
        "roles": roles,
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
        # 3.5, D-021: manifest versions this node holds. A claim admits
        # nothing; the receiver checks its own signed manifest.
        "circle_versions": circles.advertised_versions() if circles else [],
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
        # 3.5, R-014: only stable error codes are kept for the doctor export.
        from .recent_errors import RecentErrors
        self.errors = RecentErrors(self.bus, self.db)
        # 3.5, R-005: the compiled sandbox cache is prepared from first launch,
        # never inside a request. The state object is cheap and never compiles.
        from .sandbox import SandboxPreparation
        self.sandbox = SandboxPreparation(self.dirs.root / "sandbox", self.bus)
        self.identity_manager = IdentityManager(self.dirs.identity_key_path())
        self.identity: NodeIdentity = self.identity_manager.load_or_create()
        self.model_manager = ModelManager()
        self.backends = BackendRegistry()
        self.lce = LCEAdapter(self.dirs)
        self._last_embedding_meta: dict = {}
        self.nodes = NodeManager(self.identity_manager, self.config, self.db,
                                 self.bus, lambda: _build_advertisement(self),
                                 dirs=self.dirs)
        # 3.5, D-015: signed circle manifests and invitations. The node
        # manager consults this service at the handshake; the worker consults
        # it again for every task.
        from .p2p.circles import CircleService
        self.circles = CircleService(self.identity_manager, self.config,
                                     self.dirs, self.bus)
        self.circles.attach(self.nodes)
        self.nodes.circles = self.circles
        # 3.5, D-020: signed reciprocity receipts, the local wallet and the
        # issuer's double-spend log. Circle control delegates credit messages.
        from .p2p.credits import CreditService
        self.credits = CreditService(self.identity_manager, self.config,
                                     self.dirs, self.bus, circles=self.circles)
        self.circles.credits = self.credits
        self.worker: WorkerService | None = None
        from .console import ConsoleReporter
        self.console = ConsoleReporter(self.bus, lambda: self.nodes.peers)
        self.orchestrator = None  # built lazily with a live local backend
        self.latency = None       # p95 history shared across orchestrator rebuilds
        from .engine.scheduler import RoleStats, SpeedStats
        self.speed = SpeedStats()  # tokens/s per (node, model), shared the same way
        # 3.5, D-018: per-role outcomes per node, shared across requests.
        self.role_stats = RoleStats()
        self.chat = ChatService(self.db, self.bus, self.backends,
                                self.config.all, self.get_orchestrator)
        self.chat.sandbox = self.sandbox
        self.chat.report_sink = self._auto_report
        self.chat.self_node = self.identity.node_id[:12]
        self.chat.circles = self.circles
        self.chat.retriever = self._lce_retrieve
        self.chat.retrieval_active = self._lce_active
        self.chat.retrieval_candidates = lambda: list(getattr(self.lce, "last_candidates", []))
        self.chat.retrieval_meta = self.retrieval_meta
        self.chat.glossary = lambda text, project_id="": (
            self.lce.glossary_terms(text, roots=self.c1_roots(project_id))
            if self._lce_active(project_id) else "")
        self.chat.glossary_entries = lambda project_id="": (
            self.lce.glossary_entries(roots=self.c1_roots(project_id))
            if self._lce_active(project_id) else [])
        self.chat.glossary_meta = lambda project_id="": (
            self.lce.glossary_meta(roots=self.c1_roots(project_id))
            if self._lce_active(project_id) else {})
        self.chat.glossary_avoid = lambda project_id="": (
            self.lce.glossary_avoid(roots=self.c1_roots(project_id))
            if self._lce_active(project_id) else {})
        # 3.1: projects — folders of their own, with their chats kept in them
        from .projects import ProjectRegistry
        self.projects = ProjectRegistry(self.config.all, self.config.update)
        # 3.5, D-019: teams are stored plan templates, per user and optionally
        # per project; the project registry decides where its file lives.
        from .teams import TeamStore
        self.teams = TeamStore(
            self.dirs.root,
            project_path=lambda pid: (project.path if (project := self.projects.get(pid))
                                      else None))
        # 3.4: one broker for every tool call. Approvals are per project, or
        # personal when no project is active. The chat drives the optional
        # agent adapter; the broker is still the only path that invokes a tool.
        from .tools import ToolBroker
        from .tools.standing import StandingStore
        self.tools = ToolBroker(
            self.dirs.root,
            project_path=lambda pid: (project.path if (project := self.projects.get(pid))
                                      else None))
        self.standing = StandingStore(
            self.dirs.root,
            project_path=lambda pid: (project.path if (project := self.projects.get(pid))
                                      else None))
        # 3.4, D-011: the conversation can drive MCP tools through the Core
        # runtime. The package is optional and imported only when used.
        from .agent_adapter import AgentAdapter
        self.agent = AgentAdapter(self.tools, self.config.all, self.backends,
                                  standing=self.standing, bus=self.bus)
        self.chat.tools = self.tools
        self.chat.agent = self.agent
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
        # 3.5, R-014: preview and save share one snapshot (same bytes).
        from .doctor_export import DoctorExportService
        self.doctor_export = DoctorExportService(self)

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

    def _embedding_choice(self, allow_fallback: bool = True):
        """Who computes embeddings for this request (the ``embeddings`` role)."""
        from . import roles
        return roles.choose("embeddings", self.config.all(), None, "",
                            self.backends, allow_fallback=allow_fallback)

    def _record_embedding_refusal(self, choice) -> None:
        """A refused destination is part of the receipt even when nothing left."""
        if not choice.blocked:
            return
        from . import egress
        egress.record(destino=choice.blocked, clase=egress.THIRD_PARTY,
                      tipo=egress.PASSAGES, bytes=0,
                      motivo=f"embeddings {choice.asked or 'role'}: {choice.note}",
                      bloqueado=True)

    def retrieval_meta(self) -> dict:
        """What the last C1 retrieval did with embeddings (meta.lce.embeddings)."""
        return dict(self._last_embedding_meta)

    def _lce_retrieve(self, query: str, expansion: str = "", project_id: str = "") -> list:
        """LCE C1 retrieval for local answers, over the conversation's folders.

        Embeddings go through the ``embeddings`` role.  A third-party
        destination without both authorisations is refused before a byte;
        then the app's own embedder is used when it is local, and otherwise
        C1 keeps the keyword search.  Either way the answer's meta says so.
        """
        if not self._lce_active(project_id):
            return []
        cfg = self.config.all().get("lce") or {}
        meta: dict = {"role": "embeddings", "enabled": True}
        if not cfg.get("dense_retrieval", True):
            meta.update(enabled=False,
                        note="dense retrieval is off: keyword search only")
            self._last_embedding_meta = meta
            self.lce.note_embeddings(meta)
            return self.lce.retrieve(query, k=int(cfg.get("retrieval_k", 6)),
                                     expansion=expansion, roots=self.c1_roots(project_id),
                                     embed=None)
        choice = self._embedding_choice()
        meta.update(model=choice.model or "",
                    backend=getattr(choice.backend, "backend", "") or "",
                    where=choice.where or "", own=bool(choice.own))
        if choice.note:
            meta.update(note=choice.note, asked=choice.asked)
            if choice.blocked:
                meta["blocked"] = choice.blocked
        client = choice.backend
        if client is None:
            meta["fallback"] = "lexical"
            self._record_embedding_refusal(choice)
            self._last_embedding_meta = meta
            self.lce.note_embeddings(meta)
            return self.lce.retrieve(query, k=int(cfg.get("retrieval_k", 6)),
                                     expansion=expansion, roots=self.c1_roots(project_id),
                                     embed=None)
        if choice.note:
            # The chosen destination was refused; the local embedder does it.
            meta["fallback"] = "local"
            self._record_embedding_refusal(choice)
        meta.update(self.lce.prepare_embeddings(client.identity, client.model, client.dim))
        self._last_embedding_meta = meta
        self.lce.note_embeddings(meta)

        def embed(texts: list[str], kind: str) -> list[list[float]]:
            try:
                vectors = client.embed(texts, kind)
            except Exception as exc:
                meta["fallback"] = "lexical"
                meta["error"] = str(exc)[:300]
                self._last_embedding_meta = meta
                raise
            if vectors:
                meta["dimension"] = len(vectors[0])
                self._last_embedding_meta = meta
            return vectors

        try:
            return self.lce.retrieve(query, k=int(cfg.get("retrieval_k", 6)),
                                     expansion=expansion, roots=self.c1_roots(project_id),
                                     embed=embed)
        finally:
            self._last_embedding_meta = meta
            self.lce.note_embeddings(meta)

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
            self.memory_log(project_id, {"decision": "saved", "via": "Recuerda:", "notes": [text]})
            return {"scope": "project", "path": str(path.relative_to(project.path)),
                    "full_path": str(path)}
        path = save_note(self.dirs.sources, text, title="Memoria personal")
        return {"scope": "personal", "path": str(path), "full_path": str(path),
                "read_back": self._personal_c1()}

    def memory_log(self, project_id: str, event: dict) -> None:
        """Provenance of every memory decision (saved or discarded): date,
        scope, conversation, message, model that proposed it. Kept as
        ``memory/registro.jsonl`` (a project's travels with it); C1 does not
        read it."""
        import json as _json
        import time as _time
        try:
            folder = (self.projects.require(project_id).memory if project_id
                      else self.dirs.sources)
            folder.mkdir(parents=True, exist_ok=True)
            with open(folder / "registro.jsonl", "a", encoding="utf-8") as fh:
                fh.write(_json.dumps({"t": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
                                      "scope": project_id or "personal", **event},
                                     ensure_ascii=False) + "\n")
        except Exception:
            pass

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
            elif g.get("term") and not g.get("definition"):
                written.setdefault("skipped", []).append(g["term"])   # nothing to save
            if g.get("definition") and not any(g["definition"] in n for n in notes or []):
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
        """Vectors from the ``embeddings`` role, refusing before any byte.

        Kept as the direct entry point for callers that want the refusal to
        surface (the retrieval path uses it through ``_lce_retrieve``, which
        falls back to the local embedder or to keyword search)."""
        from . import egress
        choice = self._embedding_choice(allow_fallback=False)
        if choice.backend is None:
            raise egress.EgressDenied(
                choice.note or "no embedding backend",
                choice.blocked,
                egress.QUESTION if kind == "query" else egress.PASSAGES)
        return choice.backend.embed(texts, kind)

    # -- node roles and executors (3.5, D-018) ------------------------------------
    def _corpus_role(self, *, remote: bool = True) -> dict[str, Any] | None:
        """The corpus metadata this node may advertise, if any.

        The owner picks one project and the circles allowed to retrieve from
        it. A remote advertisement requires at least one such circle that this
        node still belongs to; the local pool may use the collection without a
        circle because nothing leaves the computer. Only the display name and a
        size bucket leave the node; no title, path or content does.
        """
        cfg = self.config.all()
        share = configured_corpus_share(cfg)
        if share is None:
            return None
        project = self.projects.get(share["project_id"])
        if project is None:
            return None
        circle_ids: list[str] = []
        if share["circle_ids"]:
            payload = self.circles.list_payload() if getattr(self, "circles", None) else {}
            local_ids = {str(c.get("circle_id")) for c in payload.get("circles") or []}
            circle_ids = [cid for cid in share["circle_ids"] if cid in local_ids]
        if remote and not circle_ids:
            return None
        try:
            sources = self.lce.list_sources(roots=project.roots())
            documents = sum(1 for entry in sources if not entry.get("glossary"))
        except Exception:
            return None
        if documents <= 0:
            return None
        name = share["display_name"] or project.name.strip()
        if not share["display_name"] and len(name) > 40:
            name = name[:40].strip()
        if not valid_corpus_name(name):
            return None
        return {"name": name, "size": corpus_size_bucket(documents),
                "circle_ids": circle_ids}

    def _node_roles(self, models: list[str], *, announce: bool = True,
                    remote: bool = True) -> list[dict[str, Any]]:
        """Node roles for ``models`` (large_model/reasoner/search/corpus)."""
        corpus = self._corpus_role(remote=remote) if announce else None
        corpus_meta = ({"name": corpus["name"], "size": corpus["size"]}
                       if corpus else None)
        return derive_roles(models, self.config.all(), announce=announce,
                            corpus_share=corpus_meta)

    def _worker_roles(self, models: list[str] | None = None, *,
                      announce: bool = True, remote: bool = True
                      ) -> list[dict[str, Any]]:
        """Role provider for the worker: shared models and the same settings."""
        if models is None:
            models = self.worker.shared_models() if self.worker is not None else []
        return self._node_roles(models, announce=announce, remote=remote)

    def _circle_for(self, node_id: str,
                    allowed: Any = None) -> dict[str, Any] | None:
        """A valid shared trusted circle that admits ``node_id``, if any.

        Executors that send data to a third party (search) or read a shared
        collection (corpus) require a circle; the explicit *my own devices*
        mode is not enough. This is deliberately stricter than the 3.4 LAN
        admission. Only valid, unexpired manifests that list both nodes count
        (the same rule as admission). With ``allowed`` (circle ids), only one
        of those circles is returned, so a requester who shares several
        circles with this node is matched against the one the corpus is
        shared with.
        """
        circles = getattr(self, "circles", None)
        if circles is None or circles.mode() != "circle":
            return None
        try:
            candidates = circles._local_candidates(node_id)
        except Exception:
            return None
        wanted = {str(c) for c in allowed} if allowed is not None else None
        for manifest in sorted(candidates, key=lambda m: (
                str(m.get("name") or "").casefold(), str(m.get("circle_id") or ""))):
            circle_id = str(manifest.get("circle_id") or "")
            if wanted is not None and circle_id not in wanted:
                continue
            return {"circle_id": circle_id,
                    "circle_name": str(manifest.get("name") or "")}
        return None

    def _public_query(self, text: str, project_id: str = "") -> str:
        """A public search query from a request, without the user's private
        terms, or ``""`` when none can be produced.

        Uses the same guard as the chat's public-search proposal and the same
        160-character bound. Glossary entries and private glossary terms come
        from the conversation's project (or the personal sources). If a private
        term survives the guard, nothing is returned, so nothing is sent.
        """
        from . import web_search
        try:
            roots = self.c1_roots(project_id)
            glossary = self.lce.glossary_entries(roots=roots)
            private = web_search.private_terms(text or "")
            for term in self.lce.glossary_private_terms(roots=roots):
                if term not in private:
                    private.append(term)
            try:
                passages = self.lce.passages_for_roots(roots=roots)
            except Exception:
                passages = []
            detail = web_search.propose_query_details(
                text or "", glossary=glossary, private=private,
                passages=passages)
            query = str(detail.get("query") or "").strip()[:160]
            if not query or web_search.contains_private_terms(query, private):
                return ""
            return query
        except Exception:
            return ""

    # -- P2P lifecycle -----------------------------------------------------------
    def _circle_guard(self, node_id: str) -> tuple[bool, str, str]:
        """The worker gate of D-015: membership is checked again per task."""
        circles = getattr(self, "circles", None)
        if circles is None:
            return True, "", ""
        return circles.admits_local(node_id)

    def start_p2p(self) -> None:
        if self.worker is None:
            self.worker = WorkerService(
                self.config, self.db, self.bus, self.identity_manager,
                self.lce, lambda: self.backends.resolve(self.config.all()),
                model_info=self.model_info, circle_guard=self._circle_guard,
                role_provider=self._worker_roles, circle_for=self._circle_for,
                project_provider=lambda project_id: self.projects.get(project_id),
                credits=self.credits)
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
        circles = getattr(self, "circles", None)
        if circles is not None:
            # Switching to circle-only must not leave 3.4 LAN peers connected.
            circles.enforce_admission()

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
        health = {
            "status": "ok",
            "version": __import__("swarmbly_app").__version__,
            "protocol_spec": __import__("swarmbly_app").PROTOCOL_SPEC_VERSION,
            "lce_spec": __import__("swarmbly_app").LCE_SPEC_VERSION,
            "node_id": self.identity.short_id(12),
            "uptime_s": int(time.time() - self.started_at),
            "data_dir": str(self.dirs.root),
        }
        if test_hosts.active():
            # D-013: only in test mode; without the map this response is
            # exactly what it always was. Never read from the configuration.
            health["test_mode"] = test_hosts.describe()
        return health

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
                latency=self.latency, speed=self.speed,
                role_stats=self.role_stats, stats_sink=self._client_stats,
                public_query=self._public_query,
                local_pool_factory=self._local_pool,
                credits=self.credits)
        return self.orchestrator

    def _local_pool(self):
        """The device's own multi-model pool, when enabled with ≥2 models."""
        from .engine.directory import LocalPool
        model_cfg = self.config.all()["model"]
        models = [m for m in (model_cfg.get("local_models") or []) if m]
        if not model_cfg.get("multi_model") or len(models) < 2 or self.worker is None:
            return None
        families = {m: family_for(m, (self.model_info(m) or {}).get("family", ""))
                    for m in models}
        # The local pool advertises the roles its own models have, derived
        # exactly like a remote worker's but without the "shared" condition:
        # a role-aware plan can then run entirely on this one node.
        roles = self._node_roles(models, announce=True, remote=False)
        return LocalPool(self.identity.node_id, self.worker, models, families,
                         parallel=int(model_cfg.get("local_parallel", 1) or 1),
                         roles=roles)

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
