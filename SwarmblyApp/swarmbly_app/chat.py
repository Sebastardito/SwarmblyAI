"""Chat engine: conversations, local inference with streaming, history, export.

Execution metadata (mode, model, timing, tokens, stages) is stored per message
so the monitor and the reports can always be reconstructed. Modes other than
``local`` arrive with the Phase 2 engine; the engine already records mode and
model per conversation as required.
"""

from __future__ import annotations

import re

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import egress
from .db import Database
from .events import EventBus
from .inference.base import BackendError, GenerationResult, Interrupted
from .inference.registry import BackendRegistry, IncompleteSettings

MAX_CONTEXT_MESSAGES = 12


@dataclass
class ActiveRequest:
    request_id: str
    conversation_id: str
    message_id: str
    mode: str = "local"
    model: str = ""
    stop_event: threading.Event = field(default_factory=threading.Event)
    started_at: float = field(default_factory=time.time)
    # 3.0.1: what left this computer for this request, and what the receipt needs
    ledger: Any = None
    receipt_ctx: dict[str, Any] = field(default_factory=dict)
    # 3.1: the conversation's project ("" = personal) and the user's yes to a
    # public lookup for this one question
    project_id: str = ""
    allow_public: bool = False
    memory_saved: dict[str, Any] | None = None     # "Recuerda: …" saved before answering


# Possessives and "about me" in es/en/pt (not French "mes", the Spanish month);
# a bare "me" ("¿me traduces…?") is not enough, so batches still go to the swarm.
_PERSONAL_TOPIC = re.compile(
    r"\b(?:mi|mis|my|meu|minha|meus|minhas)\s+(?:propi[oa]s?\s+|own\s+)?"
    r"(carrera|trayectoria|curr[ií]cul\w*|cv|tesis|publicaciones|art[ií]culos|perfil|"
    r"experiencia|historia\s+(?:profesional|laboral|cl[ií]nica|m[eé]dica)|salud|familia|"
    r"finanzas|sueldo|salario|empleos?|trabajos?|career|resume|thesis|publications|papers|"
    r"profile|experience|work\s+history|health|family|finances|salary|jobs?|carreira|"
    r"trajet[oó]ria|tese|publica[cç][oõ]es)\b", re.I)
_FIRST_PERSON = re.compile(
    r"\b(mi|mis|m[ií]o|m[ií]a|m[ií]os|m[ií]as|sobre m[ií]|de m[ií]|conmigo|"
    r"my|mine|myself|about me|meu|minha|meus|minhas)\b", re.I)


class ChatService:
    def __init__(self, db: Database, bus: EventBus,
                 registry: BackendRegistry, config_getter: Callable[[], dict[str, Any]],
                 orchestrator_getter: Callable[[], Any] | None = None):
        self.db = db
        self.bus = bus
        self.registry = registry
        self.config = config_getter
        self.orchestrator = orchestrator_getter  # distributed engine (Phase 2)
        self._active: dict[str, ActiveRequest] = {}
        self.report_sink: Callable[[str], None] | None = None  # set by AppState
        # LCE C1: local retrieval over the user's sources (set by AppState);
        # used only for answers produced on this device.
        self.retriever: Callable[..., list[dict[str, Any]]] | None = None
        self.retrieval_active: Callable[..., bool] = lambda project_id="": self.retriever is not None
        # P2e: the public provider for local answers (injectable for tests).
        self.public_provider: Any = None
        self.glossary: Callable[[str], str] | None = None
        self.glossary_entries: Callable[[], list] | None = None
        self.retrieval_candidates: Callable[[], list] | None = None
        self.self_node: str = ""          # this node's id prefix (set by AppState)
        # 3.1: called after a conversation changes (its project folder keeps a copy)
        self.on_conversation_changed: Callable[[str], None] | None = None
        self.on_conversation_deleted: Callable[[dict[str, Any]], None] | None = None
        self.project_name: Callable[[str], str] = lambda project_id: ""
        # 3.1: an explicit "remember …" is written to memory (project or personal)
        self.remember: Callable[[str, str], dict[str, Any] | None] | None = None
        # 3.1: the documents a project conversation can read (names and status)
        self.document_list: Callable[[str], list[dict[str, Any]]] | None = None
        # 3.1: every paragraph of one document (project_id, doc_id), in order
        self.document_spans: Callable[[str, str], list[dict[str, Any]]] | None = None
        self._lock = threading.Lock()

    def _changed(self, conversation_id: str) -> None:
        if self.on_conversation_changed is not None:
            try:
                self.on_conversation_changed(conversation_id)
            except Exception:
                pass          # the project copy never blocks an answer

    # -- conversations -------------------------------------------------------
    def list_conversations(self, project_id: str | None = None) -> list[dict[str, Any]]:
        return self.db.list_conversations(project_id)

    def create_conversation(self, title: str = "", mode: str = "",
                            model: str = "", project_id: str = "") -> dict[str, Any]:
        cfg = self.config()
        conv = self.db.create_conversation(
            title=title or "New conversation",
            mode=mode or cfg["swarm"]["mode"] or "local",
            model=model or cfg["model"]["model_name"] or "", project_id=project_id)
        self._changed(conv["id"])
        return conv

    def get_conversation(self, conv_id: str) -> dict[str, Any] | None:
        return self.db.get_conversation(conv_id)

    def get_messages(self, conv_id: str) -> list[dict[str, Any]]:
        return self.db.get_messages(conv_id)

    def delete_conversation(self, conv_id: str) -> None:
        conv = self.db.get_conversation(conv_id)
        self.db.delete_conversation(conv_id)
        if conv and self.on_conversation_deleted is not None:
            try:
                self.on_conversation_deleted(conv)
            except Exception:
                pass

    # -- sending -------------------------------------------------------------
    def send(self, conversation_id: str, text: str, *,
             mode: str | None = None, model: str | None = None,
             run_async: bool = True,
             allow_public: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
        """Store the user message and start generation.

        Returns ``(user_message, assistant_message)``; when ``run_async`` the
        assistant message is a placeholder being filled as deltas arrive.
        """
        conv = self.db.get_conversation(conversation_id)
        if conv is None:
            raise KeyError(f"unknown conversation {conversation_id}")
        cfg = self.config()
        mode = mode or conv["mode"] or cfg["swarm"]["mode"]
        model = model or conv["model"] or cfg["model"]["model_name"] or ""

        memory_saved = None
        if self.remember is not None and wants_memory(text):
            try:
                memory_saved = self.remember(str(conv.get("project_id") or ""), text)
            except Exception as exc:
                memory_saved = {"error": str(exc)[:200]}
        user_msg = self.db.add_message(conversation_id, "user", text)
        if conv.get("title") in ("", "New conversation"):
            first_line = " ".join(text.strip().split())
            self.db.update_conversation(conversation_id,
                                        title=(first_line[:56] + "…") if len(first_line) > 56
                                        else first_line)
        assistant_msg = self.db.add_message(conversation_id, "assistant", "",
                                            meta={"mode": mode, "model": model,
                                                  "status": "running"})
        self.db.touch_conversation(conversation_id)

        request = ActiveRequest(
            request_id=uuid.uuid4().hex[:16],
            conversation_id=conversation_id,
            message_id=assistant_msg["id"],
            mode=mode, model=model, project_id=str(conv.get("project_id") or ""),
            allow_public=bool(allow_public), memory_saved=memory_saved)
        with self._lock:
            self._active[request.request_id] = request
        self.db.add_request(request.request_id, conversation_id,
                            user_msg["id"], mode, model)
        self.bus.publish("request.started", request_id=request.request_id,
                         conversation_id=conversation_id,
                         message_id=assistant_msg["id"], mode=mode, model=model)
        self._changed(conversation_id)

        if run_async:
            thread = threading.Thread(
                target=self._run_generation, args=(request, mode, model),
                name=f"chat-{request.request_id[:8]}", daemon=True)
            thread.start()
        else:
            self._run_generation(request, mode, model)
        return user_msg, assistant_msg

    def _whole_small_documents(self, sources: list[dict[str, Any]],
                               project_id: str) -> list[dict[str, Any]]:
        """A short document that answered is given whole, in order (3.1).

        "Describe the manual step by step" over a three-page manual got four
        scattered paragraphs and the model filled the gaps. A document of up
        to WHOLE_DOC_CHARS characters replaces its retrieved paragraphs with
        all of them; long documents keep the retrieved ones.
        """
        if not sources or self.document_spans is None:
            return sources
        out: list[dict[str, Any]] = []
        done: set[str] = set()
        budget = WHOLE_DOC_CHARS * 2
        for s in sources:
            doc = s.get("doc_id", "")
            if doc in done:
                continue
            spans = []
            if doc and budget > 0:
                try:
                    spans = self.document_spans(project_id, doc)
                except Exception:
                    spans = []
            size = sum(len(x.get("text", "")) for x in spans)
            if spans and size <= min(WHOLE_DOC_CHARS, budget):
                budget -= size
                done.add(doc)
                out.extend({**x, "score": s.get("score"), "cite": f"doc:{doc}#{x['anchor']}",
                            "whole_document": True} for x in spans)
            else:
                out.append(s)
        return out

    def _personal_request(self, text: str, project_id: str = "") -> bool:
        """A first-person request about the user's own material ("mi carrera",
        "mis artículos", "my thesis") while C1 has sources for it. Such a request
        goes to the swarm without the user's passages, which never leave this
        device, so the workers would write without facts (the October 2026
        test: "investigador de materiales"), and it would carry personal
        details to other machines."""
        lce = (self.config().get("lce") or {})
        if not lce.get("keep_personal_local", True) or not _FIRST_PERSON.search(text or ""):
            return False
        # "mi carrera", "mis publicaciones", "my thesis": personal whatever the
        # sources say (the 25 Oct retest had C1 on but no source folder, and the
        # request went to the swarm again with the user's name in it)
        if _PERSONAL_TOPIC.search(text):
            return True
        if self.retriever is None or not self.retrieval_active(project_id):
            return False
        try:
            return bool(self.retriever(text, "", project_id))
        except Exception:
            return False

    def _run_generation(self, request: ActiveRequest, mode: str, model: str) -> None:
        """Every outbound call of this request is checked and recorded (3.0.1)."""
        with egress.request_ledger(request.request_id) as ledger:
            request.ledger = ledger
            self._run_generation_inner(request, mode, model)

    def _run_generation_inner(self, request: ActiveRequest, mode: str, model: str) -> None:
        conv_id = request.conversation_id
        try:
            history = self.db.get_messages(conv_id)
            prior = [m for m in history if m["id"] != request.message_id]
            context = [{"role": m["role"], "content": m["content"]}
                       for m in prior if m["role"] in ("user", "assistant")]
            context = context[-MAX_CONTEXT_MESSAGES:]
            if not context:
                return self._fail(request, "no user message in context")
            user_text = context[-1]["content"]
            request.receipt_ctx.update(_lane_for_receipt(user_text))

            # Distributed modes route through the swarm engine.
            local_reason = ""
            routing_stages: list[dict[str, Any]] | None = None
            routing_meta: dict[str, Any] = {}
            multi_local = mode == "local" and bool(self.config()["model"].get("multi_model"))
            personal = mode in ("lan", "internet", "auto") and (
                request.memory_saved is not None
                or self._personal_request(user_text, request.project_id))
            if personal:
                local_reason = ("about you and your documents: answered on this device "
                                "with your sources (nothing sent to the swarm)")
                self.bus.publish("chat.notice", request_id=request.request_id,
                                 conversation_id=conv_id, message_id=request.message_id,
                                 note=local_reason)
            if (mode in ("lan", "internet", "auto") or multi_local) and not personal \
                    and self.orchestrator is not None:
                if mode == "internet":
                    return self._fail(
                        request, "Internet swarms are Phase 3 (rendezvous not implemented)")
                try:
                    # The conversation stays on this device: the orchestrator
                    # rewrites a follow-up locally into a standalone request.
                    with egress.purpose(egress.QUESTION):
                        outcome = self.orchestrator().run(
                            user_text, mode=mode, request_id=request.request_id,
                            cancel=request.stop_event, history=context[:-1])
                except Exception as exc:
                    return self._fail(request, f"swarm execution failed: {exc}")
                routed = outcome.get("routed")
                if routed == "distributed":
                    self._finish_distributed(request, outcome["text"],
                                             outcome["metadata"], outcome["stages"])
                    return
                if routed == "error":
                    if outcome.get("status") == "stopped":
                        return self._finish(request, None, status="stopped",
                                            note="interrupted by user",
                                            stages=outcome.get("stages"))
                    return self._fail(request, outcome.get("reason", "swarm error"),
                                      stages=outcome.get("stages"),
                                      swarm=outcome.get("metadata"))
                # routed == "local": privacy, router, admission or no workers.
                local_reason = outcome.get("reason", "")
                routing_stages = outcome.get("stages")
                routing_meta = outcome.get("metadata") or {}
                self.bus.publish("chat.notice", request_id=request.request_id,
                                 conversation_id=conv_id,
                                 message_id=request.message_id,
                                 note=local_reason)

            backend = self.registry.resolve(self.config())
            # 3.0.1: where the model runs decides what it may receive.
            from .inference.registry import endpoint
            dest_cls, dest_host = egress.classify_url(endpoint(backend) or "http://127.0.0.1")
            request.receipt_ctx["model_destination"] = {"clase": dest_cls, "host": dest_host}
            passages_allowed = True
            if dest_cls == egress.THIRD_PARTY:
                pol = egress.policy()
                if not pol.authorised(dest_host):
                    egress.record(destino=dest_host, clase=dest_cls, tipo=egress.QUESTION,
                                  bytes=0, motivo="modelo", bloqueado=True)
                    return self._fail(request, (
                        f"The configured model runs at {dest_host}, a third-party service you "
                        "have not authorised. Nothing was sent. Authorise it in Settings → "
                        "Models (third-party model services), or choose a model on this "
                        "computer."))
                passages_allowed = pol.third_party_passages
            model = model or (backend.list_models() or [""])[0]
            if not model:
                raise IncompleteSettings("no model selected")

            def on_delta(delta: str) -> None:
                self.bus.publish("chat.delta", request_id=request.request_id,
                                 conversation_id=conv_id,
                                 message_id=request.message_id, delta=delta)

            from .engine.contract import answer_budget
            cfg = self.config()
            sources: list[dict[str, Any]] = []
            expansion = None
            ev_cfg = cfg.get("evidence") or {}
            from .local_context import wants_public
            want_public = (bool(ev_cfg.get("enabled")) and bool(ev_cfg.get("local_answers", True))
                           and wants_public(user_text))
            lce_on = self.retriever is not None and self.retrieval_active(request.project_id)
            if lce_on and not passages_allowed:
                # authorised for questions only: the documents stay out of the call
                lce_on = False
                request.receipt_ctx["passages_withheld"] = dest_host
            if (lce_on and (cfg.get("lce") or {}).get("query_expansion", True)) or want_public:
                from .local_context import expand_query
                # Keywords come from the small default model even when the
                # conversation uses a large one: fast, and a reasoning model
                # returned nothing in 90 tokens (P2e round 6).
                exp_model = ((cfg.get("lce") or {}).get("expansion_model")
                             or (cfg.get("model") or {}).get("model_name") or model)
                with egress.purpose(egress.QUESTION):
                    expansion = expand_query(backend, exp_model, user_text)
            if lce_on:
                # 3.1: a short follow-up ("¿qué aplicaciones necesita este
                # proceso?") is searched with the previous question as well
                extra_terms = expansion.keywords if expansion else ""
                prev_user = _previous_user_turn(context)
                if prev_user and _is_follow_up(user_text):
                    extra_terms = f"{extra_terms} {prev_user}"
                try:
                    sources = self.retriever(user_text, extra_terms, request.project_id) or []
                except Exception:
                    sources = []
                sources = self._whole_small_documents(sources, request.project_id)
                _label_sources(sources, history)
            public_hits: list[dict[str, Any]] = []
            public_report: dict[str, Any] | None = None
            if want_public and expansion is not None:
                from .local_context import public_entities, public_evidence
                known, pairs = "", []
                if self.glossary is not None:
                    try:
                        known = self.glossary(f"{user_text} {expansion.keywords}",
                                              request.project_id)
                        pairs = (self.glossary_entries(request.project_id)
                                 if self.glossary_entries else [])
                    except Exception:
                        known, pairs = "", []
                entities = public_entities(user_text, expansion, sources,
                                           int(ev_cfg.get("local_max_entities", 3)), pairs)
                # 3.1: about you (your documents, a personal or sensitive
                # question) → a public lookup needs your yes for this question.
                lane_now = request.receipt_ctx.get("lane")
                needs_yes = bool(sources) or lane_now in ("personal", "sensible")
                consent_mode = str((cfg.get("privacy") or {}).get("public_lookup_consent", "ask"))
                request.receipt_ctx["consent_required"] = bool(entities) and needs_yes
                if entities and needs_yes and consent_mode == "ask" and not request.allow_public:
                    request.receipt_ctx["public_offer"] = [e.get("name", "") for e in entities]
                    entities = []
                if entities:
                    provider = self.public_provider
                    if provider is None:
                        from .engine.evidence import WikipediaEvidence
                        from .engine.providers import build
                        from .lang import detect_language
                        wiki = WikipediaEvidence(
                            lang=str(ev_cfg.get("local_lang", "en")),
                            timeout_s=float(ev_cfg.get("timeout_s", 4.0)))
                        provider = build(detect_language(user_text), ev_cfg, wiki)
                    public_hits, public_report = public_evidence(entities, expansion, provider,
                                                                 known, user_text)
            # P2e: an enumerated PUBLIC batch answered here (too small to
            # fragment, or no workers) gets the same item evidence as fragments.
            batch_report = None
            routing_info = (routing_meta.get("routing") or {}) if routing_meta else {}
            # Only when the request itself could have left (PUBLIC lane, tier
            # allowing egress): a LOCAL tier or a sensitive lane sends nothing.
            if (routing_info.get("lane") == "PUBLIC" and routing_info.get("remote_allowed")
                    and not public_hits):
                from .engine.evidence import local_batch
                from .lang import detect_language
                try:
                    block, batch_report = local_batch(user_text, cfg, detect_language(user_text))
                except Exception:
                    block, batch_report = "", None
                if block:
                    context = [{"role": "system", "content": block}, *context]
            answer_model = model
            if public_hits and ev_cfg.get("fusion_model"):
                # P2e: a larger local model writes only the answers that fuse the
                # user's sources with public evidence (few, and quality matters).
                answer_model = str(ev_cfg["fusion_model"])
            if public_hits:
                # P2e fusion template: both kinds of source in the user's turn,
                # labelled, with the answer's structure; a 3B model mixed them up
                # when they came as system blocks (round 3).
                from .lang import detect_language
                from .local_context import fusion_prompt
                context = [*context[:-1],
                           {"role": "user", "content": fusion_prompt(
                               sources, public_hits, user_text, detect_language(user_text))}]
            elif sources:
                context = [{"role": "system", "content": _sources_block(sources, user_text)},
                           *context]
            if lce_on and request.project_id and self.document_list is not None:
                # 3.1: the model knows which documents this project has (names
                # only), so "which sources do you have?" is not invented
                try:
                    docs = self.document_list(request.project_id)
                except Exception:
                    docs = []
                block = _documents_block(docs, user_text, _doc_labels(history, sources))
                if not sources:
                    block += "\n" + _NOTHING_FOUND.get(_lang(user_text), _NOTHING_FOUND["en"])
                context = [{"role": "system", "content": block}, *context]
            if request.memory_saved and not request.memory_saved.get("error"):
                context = [{"role": "system", "content": _MEMORY_DONE.get(
                    _lang(user_text),
                    _MEMORY_DONE["en"]).format(path=request.memory_saved.get("path", ""))},
                           *context]
            request.receipt_ctx["passages"] = [str(s.get("text", "")) for s in sources]
            if sources:
                request.receipt_ctx["lane"] = "personal" if request.receipt_ctx.get("lane") != "sensible" \
                    else "sensible"
            if public_report is not None:
                request.receipt_ctx["public_lookup"] = True
            budget = answer_budget(user_text, int(self.config()["model"].get("max_tokens", 1024)))
            answer_kind = egress.PASSAGES if sources else egress.QUESTION
            if answer_model != model:
                budget *= 2          # a reasoning model spends tokens before it answers
            with egress.purpose(answer_kind):
                result = backend.stream_chat(
                    context, model=answer_model, max_tokens=budget,
                    temperature=float(self.config()["model"].get("temperature", 0.2)),
                    on_delta=on_delta,
                    interrupt=request.stop_event.is_set)
            fusion_fallback = ""
            if answer_model != model and not (getattr(result, "text", "") or "").strip():
                # The fusion model returned nothing (P2e round 9c: one empty answer
                # out of 18): the conversation's model answers the same prompt.
                fusion_fallback = f"{answer_model} returned an empty answer"
                answer_model = model
                with egress.purpose(answer_kind):
                    result = backend.stream_chat(
                        context, model=model, max_tokens=budget // 2,
                        temperature=float(self.config()["model"].get("temperature", 0.2)),
                        on_delta=on_delta, interrupt=request.stop_event.is_set)
            extra = {}
            if request.receipt_ctx.get("passages_withheld"):
                extra["passages_withheld"] = (
                    f"your documents were not sent to {request.receipt_ctx['passages_withheld']} "
                    "(authorised for questions only)")
            if local_reason:
                extra = {"executed": "local", "local_reason": local_reason,
                         "swarm": routing_meta}
            if sources:
                extra["lce"] = {"level": "C1", "sources": [
                    {"n": i, "source": s["source"], "start": s["start"], "end": s["end"],
                     "score": s.get("score"), "rel": s.get("rel", ""),
                     "label": s.get("label", ""), "doc_id": s.get("doc_id", ""),
                     "whole_document": bool(s.get("whole_document")),
                     # 3.1: stable citation (content hash + paragraph), resolves
                     # after the folder is moved or restored elsewhere
                     "cite": s.get("cite", "")} for i, s in enumerate(sources, 1)]}
                if self.retrieval_candidates is not None:
                    try:
                        extra["lce"]["candidates"] = self.retrieval_candidates()
                    except Exception:
                        pass
            if expansion is not None:
                extra.setdefault("lce", {})["expansion"] = expansion.to_dict()
            if request.receipt_ctx.get("public_offer"):
                # nothing was looked up: the answer offers to repeat it with a lookup
                extra["public_offer"] = {"entities": request.receipt_ctx["public_offer"]}
            if public_report is not None:
                extra["evidence"] = public_report
            elif batch_report is not None:
                extra["evidence"] = batch_report
            if answer_model != model:
                extra["answer_model"] = answer_model
            if fusion_fallback:
                extra["fusion_fallback"] = fusion_fallback
            self._finish(request, result, note=local_reason, stages=routing_stages,
                         extra=extra)
        except Interrupted:
            self._finish(request, None, status="stopped",
                         note="interrupted by user")
        except egress.EgressDenied as exc:
            self._fail(request, str(exc))
        except (BackendError, IncompleteSettings, KeyError) as exc:
            self._fail(request, str(exc))
        except Exception as exc:  # never leave a request hanging in "running"
            self._fail(request, f"unexpected error: {exc}")

    def _finish_distributed(self, request: ActiveRequest, text: str,
                            metadata: dict[str, Any],
                            stages: list[dict[str, Any]]) -> None:
        """Complete a distributed request: assembled text + SPEC §19 metadata."""
        truncated = metadata.get("truncated_tasks") or []
        note = (f"output reached its token budget in {len(truncated)} task(s); the "
                "answer may be incomplete" if truncated else "")
        meta: dict[str, Any] = {"status": "done", "note": note,
                                "mode": request.mode, "model": request.model,
                                "request_id": request.request_id,
                                "executed": "distributed", "swarm": metadata}
        self._attach_receipt(request, meta, text, distributed=metadata)
        try:
            self.db.update_message(request.message_id, content=text,
                                   meta=meta, stages=stages)
            self.db.finish_request(request.request_id, "done", meta)
            self.db.touch_conversation(request.conversation_id)
        except Exception:  # database may be closing during shutdown
            pass
        with self._lock:
            self._active.pop(request.request_id, None)
        if self.config().get("results", {}).get("auto_report") and self.report_sink:
            try:
                self.report_sink(request.request_id)
            except Exception:
                pass  # a report failure never affects the answer
        self._changed(request.conversation_id)
        self.bus.publish("chat.done", request_id=request.request_id,
                         conversation_id=request.conversation_id,
                         message_id=request.message_id, status="done",
                         content=text, meta=meta)

    def _finish(self, request: ActiveRequest, result: GenerationResult | None,
                status: str = "done", note: str = "",
                stages: list[dict[str, Any]] | None = None,
                extra: dict[str, Any] | None = None) -> None:
        meta: dict[str, Any] = {"status": status, "note": note,
                                "mode": request.mode, "model": request.model,
                                "request_id": request.request_id,
                                "executed": "local"}
        meta.update(extra or {})
        if request.memory_saved:
            meta["memory_saved"] = request.memory_saved
        content = ""
        if result is not None:
            content = result.text
            meta.update(result.to_dict())
        self._attach_receipt(request, meta, content)
        try:
            if result is not None:
                self._record_stats(result)
            self.db.update_message(request.message_id, content=content, meta=meta,
                                   **({"stages": stages} if stages else {}))
            self.db.finish_request(request.request_id, status, meta)
            self.db.touch_conversation(request.conversation_id)
        except Exception:  # database may be closing during shutdown
            pass
        with self._lock:
            self._active.pop(request.request_id, None)
        self._changed(request.conversation_id)
        self.bus.publish("chat.done", request_id=request.request_id,
                         conversation_id=request.conversation_id,
                         message_id=request.message_id, status=status,
                         content=content, meta=meta)

    def _fail(self, request: ActiveRequest, error: str,
              stages: list[dict[str, Any]] | None = None,
              swarm: dict[str, Any] | None = None) -> None:
        meta: dict[str, Any] = {"status": "failed", "error": error,
                                "mode": request.mode, "model": request.model,
                                "request_id": request.request_id}
        if swarm:
            meta["swarm"] = swarm
        self._attach_receipt(request, meta, "")
        try:
            self.db.update_message(request.message_id,
                                   content=f"[Error] {error}", meta=meta,
                                   **({"stages": stages} if stages else {}))
            self.db.finish_request(request.request_id, "failed", meta)
            self.db.touch_conversation(request.conversation_id)
        except Exception:  # database may be closing during shutdown
            pass
        with self._lock:
            self._active.pop(request.request_id, None)
        self._changed(request.conversation_id)
        self.bus.publish("chat.done", request_id=request.request_id,
                         conversation_id=request.conversation_id,
                         message_id=request.message_id, status="failed",
                         error=error, meta=meta)

    def _attach_receipt(self, request: ActiveRequest, meta: dict[str, Any], answer: str,
                        distributed: dict[str, Any] | None = None) -> None:
        """The privacy receipt: what actually left, built from the ledger (3.0.1)."""
        try:
            ctx = request.receipt_ctx
            dest = ctx.get("model_destination") or egress.model_destination(self.config())
            extra_sends, fragments = [], 0
            if distributed:
                fragments = int(distributed.get("n_tasks") or 0)
                for att in distributed.get("attempts") or []:
                    node = str(att.get("node", ""))
                    if self.self_node and node == self.self_node[:len(node)]:
                        continue          # this device's own models (local pool)
                    extra_sends.append({"destino": f"nodo {node}", "clase": egress.OWN_NETWORK,
                                        "tipo": egress.FRAGMENT, "bytes": att.get("bytes_out") or 0,
                                        "motivo": f"fragmento {att.get('task', '')}"})
            ledger = request.ledger
            public = any(e.get("tipo") == egress.PUBLIC_QUERY and not e.get("bloqueado")
                         for e in (ledger.events if ledger else []))
            route = "fragmentada" if distributed else ("local+consulta_publica" if public else "local")
            # 3.1: consent is always a yes/no, and says on what it rests
            required = bool(ctx.get("consent_required"))
            consent: dict[str, Any] = {"requerido": required, "otorgado": False, "alcance": "",
                                       "base": "no hubo consulta pública"}
            if ctx.get("public_offer"):
                consent.update(base="no se pidió en esta pregunta: no se consultó nada público",
                               alcance="")
            if public or ctx.get("public_lookup"):
                if request.allow_public:
                    base = "lo pediste en esta pregunta"
                elif required:
                    base = "ajuste «consultas públicas sin preguntar» (public_lookup_consent=always)"
                else:
                    base = "pregunta sin datos tuyos; evidencia pública activada"
                consent = {"requerido": required, "otorgado": True,
                           "alcance": "nombres de entidades públicas de la pregunta o de tus fuentes",
                           "base": base}
            if dest.get("clase") == egress.THIRD_PARTY:
                consent["modelo_terceros"] = {
                    "host": dest.get("host", ""), "autorizado": True,
                    "pasajes": not bool(ctx.get("passages_withheld"))}
            meta["model_destination"] = dest
            meta["receipt"] = egress.build_receipt(
                ledger, lane=ctx.get("lane", "no_informado"), route=route, answer=answer,
                consent=consent, passages=ctx.get("passages") or [],
                fragments=fragments, extra_sends=extra_sends, model_destination=dest)
            # 3.1: whose documents this answer could read
            meta["receipt"]["ambito"] = (
                {"tipo": "proyecto", "id": request.project_id,
                 "nombre": self.project_name(request.project_id)}
                if request.project_id else {"tipo": "personal"})
            if dest.get("clase") != egress.LOCAL and meta.get("executed") == "local":
                meta["computed_at"] = dest.get("host", "")
        except Exception as exc:          # a receipt problem never loses the answer
            meta["receipt_error"] = str(exc)[:200]

    def _record_stats(self, result: GenerationResult) -> None:
        import datetime
        day = datetime.date.today().isoformat()
        # Local (consumed) work only; served-to-others lives in served_* columns.
        self.db.add_stats(day,
                          tasks_requested=1,
                          tokens_out=result.completion_tokens or 0,
                          gen_ms=result.total_ms or 0)

    def interrupt(self, request_id: str) -> bool:
        with self._lock:
            request = self._active.get(request_id)
        if request is None:
            return False
        request.stop_event.set()
        return True

    def active_requests(self) -> list[dict[str, Any]]:
        with self._lock:
            return [{"request_id": r.request_id, "conversation_id": r.conversation_id,
                     "message_id": r.message_id, "started_at": r.started_at}
                    for r in self._active.values()]

    def retry(self, conversation_id: str, message_id: str,
              allow_public: bool = False) -> tuple[dict, dict] | None:
        """Re-send the last user message before ``message_id`` (spec: retry)."""
        messages = self.db.get_messages(conversation_id)
        index = next((i for i, m in enumerate(messages) if m["id"] == message_id), None)
        if index is None or index == 0:
            return None
        user_msg = messages[index - 1]
        if user_msg["role"] != "user":
            return None
        return self.send(conversation_id, user_msg["content"], allow_public=allow_public)

    # -- export ---------------------------------------------------------------
    def export(self, conversation_id: str, fmt: str = "markdown",
               out_dir: Path | None = None) -> str:
        conv = self.db.get_conversation(conversation_id)
        if conv is None:
            raise KeyError(f"unknown conversation {conversation_id}")
        messages = self.db.get_messages(conversation_id)
        if fmt == "json":
            content = json.dumps({"conversation": conv, "messages": messages},
                                 indent=2, ensure_ascii=False)
            suffix = ".json"
        elif fmt == "html":
            content = self._as_html(conv, messages)
            suffix = ".html"
        else:
            content = self._as_markdown(conv, messages)
            suffix = ".md"
        if out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"conversation-{conversation_id}{suffix}"
            path.write_text(content, encoding="utf-8")
            return str(path)
        return content

    @staticmethod
    def _as_markdown(conv: dict[str, Any], messages: list[dict[str, Any]]) -> str:
        lines = [f"# {conv['title']}", "",
                 f"- conversation: `{conv['id']}`",
                 f"- mode: {conv['mode']} · model: {conv['model'] or '-'}",
                 f"- exported: {time.strftime('%Y-%m-%d %H:%M:%S')}", ""]
        for m in messages:
            if m["role"] == "system":
                continue
            who = "**User**" if m["role"] == "user" else "**Swarmbly**"
            lines += [f"## {who}", "", m["content"], ""]
        return "\n".join(lines)

    @staticmethod
    def _as_html(conv: dict[str, Any], messages: list[dict[str, Any]]) -> str:
        import html
        parts = [f"<h1>{html.escape(conv['title'])}</h1>",
                 f"<p><code>{conv['id']}</code> · mode: {conv['mode']} · "
                 f"model: {conv['model'] or '-'}</p>"]
        for m in messages:
            if m["role"] == "system":
                continue
            who = "User" if m["role"] == "user" else "Swarmbly"
            parts.append(
                f"<h3>{who}</h3><div>{html.escape(m['content']).replace(chr(10), '<br>')}</div>")
        return ("<!doctype html><html><head><meta charset='utf-8'>"
                "<title>Swarmbly export</title></head><body>"
                + "".join(parts) + "</body></html>")


_SOURCES_HEAD = {
    # 3.1: grounded. The first project test showed acronyms expanded from
    # nowhere ("TRU (Terminal Remote User)"), invented species and table rows.
    "es": ("Fuentes locales del usuario (no salen de este equipo). Responde solo con lo que "
           "dicen estos párrafos: si algo no está en ellos, di que las fuentes no lo dicen en "
           "vez de suponerlo. No expandas siglas ni añadas nombres, cifras, lugares o filas de "
           "tabla que no aparezcan aquí. Cita cada dato con la etiqueta de su párrafo, por "
           "ejemplo [D1 p3]; la etiqueta de una respuesta anterior sigue nombrando el mismo "
           "párrafo:"),
    "en": ("The user's local sources (they never leave this device). Answer only with what "
           "these paragraphs say: if something is not in them, say the sources do not say it "
           "instead of guessing. Do not expand acronyms or add names, figures, places or table "
           "rows that do not appear here. Cite each fact with its paragraph's label, e.g. "
           "[D1 p3]; a label from an earlier answer still names the same paragraph:"),
}


WHOLE_DOC_CHARS = 6000          # a document this short is given whole (3.1)
_FOLLOW_UP = re.compile(r"\b(este|esta|esto|ese|esa|eso|estos|estas|anterior|lo mismo|"
                        r"this|that|these|those|it|previous|above|isso|isto)\b", re.I)


def _previous_user_turn(context: list[dict[str, Any]]) -> str:
    users = [m["content"] for m in context if m.get("role") == "user"]
    return users[-2][:400] if len(users) >= 2 else ""


def _is_follow_up(text: str) -> bool:
    return len((text or "").split()) <= 12 or bool(_FOLLOW_UP.search(text or ""))


def _doc_labels(history: list[dict[str, Any]], sources: list[dict[str, Any]] = ()
                ) -> dict[str, tuple[str, str]]:
    """doc_id -> (label "D1", file) for this conversation: earlier answers'
    labels are kept, so a citation in an old answer still means the same
    document (3.1; before, [1] meant a different passage on every turn)."""
    labels: dict[str, tuple[str, str]] = {}
    for m in history:
        for s in ((m.get("meta") or {}).get("lce") or {}).get("sources") or []:
            doc, label = s.get("doc_id"), str(s.get("label") or "")
            if doc and label and doc not in labels:
                labels[doc] = (label.split()[0], s.get("rel") or s.get("source", ""))
    for s in sources:
        doc, label = s.get("doc_id"), str(s.get("label") or "")
        if doc and label and doc not in labels:
            labels[doc] = (label.split()[0], s.get("rel") or s.get("source", ""))
    return labels


def _label_sources(sources: list[dict[str, Any]], history: list[dict[str, Any]]) -> None:
    """Give each passage a label "D<n> p<k>": D<n> is the document's number in
    this conversation, p<k> the paragraph in that document."""
    labels = _doc_labels(history)
    used = {lab for lab, _ in labels.values()}
    n = max([int(lab[1:]) for lab in used if lab[1:].isdigit()] or [0])
    for s in sources:
        doc = s.get("doc_id") or s.get("source", "")
        if doc not in labels:
            n += 1
            labels[doc] = (f"D{n}", s.get("rel") or s.get("source", ""))
        s["label"] = f"{labels[doc][0]} {s.get('anchor', '')}".strip()


_NOTHING_FOUND = {
    "es": ("En esta pregunta no se encontró nada en los documentos del proyecto. Si la pregunta "
           "trata de ellos, dilo así en vez de responder de memoria."),
    "en": ("Nothing was found in the project's documents for this question. If the question is "
           "about them, say so instead of answering from memory."),
}

_MEMORY_VERB = re.compile(
    r"^\s*(?:por\s+favor[,\s]+)?(?:memoriza|memorice|recuerda|recuerde|anota|apunta|"
    r"guarda(?:\s+esto)?\s+en\s+(?:la\s+|tu\s+)?memoria|remember|memori[sz]e|note\s+down|"
    r"keep\s+in\s+mind|lembre|memorize|anote)\b", re.I)


def wants_memory(text: str) -> bool:
    """An explicit request to remember ("Recuerda: …", "Memoriza …",
    "Remember that …"). A question ("¿recuerdas…?") is not one."""
    t = (text or "").strip()
    return bool(_MEMORY_VERB.match(t)) and not t.endswith("?")


def _lang(text: str) -> str:
    from .lang import detect_language
    return detect_language(text)


_MEMORY_DONE = {
    "es": ("La app ya guardó el mensaje del usuario en su memoria local ({path}); "
           "confírmalo en una frase y no digas que no puedes recordar."),
    "en": ("The app has saved the user's message in local memory ({path}); confirm it in one "
           "sentence and do not say you cannot remember."),
}

_DOCS_HEAD = {
    "es": ("Documentos de este proyecto (solo nombres; si te preguntan qué fuentes hay, "
           "responde con esta lista y no inventes otras):"),
    "en": ("Documents of this project (names only; if asked which sources there are, answer "
           "with this list and invent none):"),
}


def _documents_block(docs: list[dict[str, Any]], user_text: str,
                     labels: dict[str, tuple[str, str]] | None = None) -> str:
    lang = _lang(user_text)
    lines = [_DOCS_HEAD.get(lang, _DOCS_HEAD["en"])]
    labels = labels or {}
    for d in docs[:60]:
        name = d.get("rel") or d.get("name", "")
        if d.get("doc_id") in labels:
            name = f"{labels[d['doc_id']][0]}: {name}"
        if d.get("unreadable"):
            lines.append(f"- {name} ({'sin texto legible' if lang == 'es' else 'no readable text'})")
        else:
            lines.append(f"- {name}")
    if len(lines) == 1:
        lines.append("- (ninguno)" if lang == "es" else "- (none)")
    return "\n".join(lines)


def _sources_block(sources: list[dict[str, Any]], user_text: str) -> str:
    """LCE C1: retrieved paragraphs for a local answer, with their origin."""
    from .lang import detect_language
    head = _SOURCES_HEAD.get(detect_language(user_text), _SOURCES_HEAD["en"])
    lines = [head]
    for i, s in enumerate(sources, 1):
        label = s.get("label") or str(i)
        lines.append(f"[{label}] ({s.get('rel') or s['source']}) {s['text']}")
    return "\n".join(lines)


def _lane_for_receipt(text: str) -> dict[str, Any]:
    """The receipt's lane: sensible (strong or first-person sensitive terms),
    personal (about the user), or público. Classification only, local."""
    try:
        from .engine.lane import classify
        lane = classify(text or "")
    except Exception:
        lane = "SENSITIVE"
    if lane == "SENSITIVE":
        return {"lane": "sensible"}
    if _PERSONAL_TOPIC.search(text or "") or _FIRST_PERSON.search(text or ""):
        return {"lane": "personal"}
    return {"lane": "público"}
