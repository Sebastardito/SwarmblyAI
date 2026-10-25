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
        self.retrieval_active: Callable[[], bool] = lambda: self.retriever is not None
        # P2e: the public provider for local answers (injectable for tests).
        self.public_provider: Any = None
        self.glossary: Callable[[str], str] | None = None
        self.glossary_entries: Callable[[], list] | None = None
        self.retrieval_candidates: Callable[[], list] | None = None
        self._lock = threading.Lock()

    # -- conversations -------------------------------------------------------
    def list_conversations(self) -> list[dict[str, Any]]:
        return self.db.list_conversations()

    def create_conversation(self, title: str = "", mode: str = "",
                            model: str = "") -> dict[str, Any]:
        cfg = self.config()
        return self.db.create_conversation(
            title=title or "New conversation",
            mode=mode or cfg["swarm"]["mode"] or "local",
            model=model or cfg["model"]["model_name"] or "")

    def get_conversation(self, conv_id: str) -> dict[str, Any] | None:
        return self.db.get_conversation(conv_id)

    def get_messages(self, conv_id: str) -> list[dict[str, Any]]:
        return self.db.get_messages(conv_id)

    def delete_conversation(self, conv_id: str) -> None:
        self.db.delete_conversation(conv_id)

    # -- sending -------------------------------------------------------------
    def send(self, conversation_id: str, text: str, *,
             mode: str | None = None, model: str | None = None,
             run_async: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
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
            mode=mode, model=model)
        with self._lock:
            self._active[request.request_id] = request
        self.db.add_request(request.request_id, conversation_id,
                            user_msg["id"], mode, model)
        self.bus.publish("request.started", request_id=request.request_id,
                         conversation_id=conversation_id,
                         message_id=assistant_msg["id"], mode=mode, model=model)

        if run_async:
            thread = threading.Thread(
                target=self._run_generation, args=(request, mode, model),
                name=f"chat-{request.request_id[:8]}", daemon=True)
            thread.start()
        else:
            self._run_generation(request, mode, model)
        return user_msg, assistant_msg

    def _personal_request(self, text: str) -> bool:
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
        if self.retriever is None or not self.retrieval_active():
            return False
        try:
            return bool(self.retriever(text, ""))
        except Exception:
            return False

    def _run_generation(self, request: ActiveRequest, mode: str, model: str) -> None:
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

            # Distributed modes route through the swarm engine.
            local_reason = ""
            routing_stages: list[dict[str, Any]] | None = None
            routing_meta: dict[str, Any] = {}
            multi_local = mode == "local" and bool(self.config()["model"].get("multi_model"))
            personal = mode in ("lan", "internet", "auto") and self._personal_request(user_text)
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
            lce_on = self.retriever is not None and self.retrieval_active()
            if (lce_on and (cfg.get("lce") or {}).get("query_expansion", True)) or want_public:
                from .local_context import expand_query
                # Keywords come from the small default model even when the
                # conversation uses a large one: fast, and a reasoning model
                # returned nothing in 90 tokens (P2e round 6).
                exp_model = ((cfg.get("lce") or {}).get("expansion_model")
                             or (cfg.get("model") or {}).get("model_name") or model)
                expansion = expand_query(backend, exp_model, user_text)
            if lce_on:
                try:
                    sources = self.retriever(
                        user_text, expansion.keywords if expansion else "") or []
                except Exception:
                    sources = []
            public_hits: list[dict[str, Any]] = []
            public_report: dict[str, Any] | None = None
            if want_public and expansion is not None:
                from .local_context import public_entities, public_evidence
                known, pairs = "", []
                if self.glossary is not None:
                    try:
                        known = self.glossary(f"{user_text} {expansion.keywords}")
                        pairs = self.glossary_entries() if self.glossary_entries else []
                    except Exception:
                        known, pairs = "", []
                entities = public_entities(user_text, expansion, sources,
                                           int(ev_cfg.get("local_max_entities", 3)), pairs)
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
            budget = answer_budget(user_text, int(self.config()["model"].get("max_tokens", 1024)))
            if answer_model != model:
                budget *= 2          # a reasoning model spends tokens before it answers
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
                result = backend.stream_chat(
                    context, model=model, max_tokens=budget // 2,
                    temperature=float(self.config()["model"].get("temperature", 0.2)),
                    on_delta=on_delta, interrupt=request.stop_event.is_set)
            extra = {}
            if local_reason:
                extra = {"executed": "local", "local_reason": local_reason,
                         "swarm": routing_meta}
            if sources:
                extra["lce"] = {"level": "C1", "sources": [
                    {"n": i, "source": s["source"], "start": s["start"], "end": s["end"],
                     "score": s.get("score")} for i, s in enumerate(sources, 1)]}
                if self.retrieval_candidates is not None:
                    try:
                        extra["lce"]["candidates"] = self.retrieval_candidates()
                    except Exception:
                        pass
            if expansion is not None:
                extra.setdefault("lce", {})["expansion"] = expansion.to_dict()
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
        content = ""
        if result is not None:
            content = result.text
            meta.update(result.to_dict())
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
        self.bus.publish("chat.done", request_id=request.request_id,
                         conversation_id=request.conversation_id,
                         message_id=request.message_id, status="failed",
                         error=error, meta=meta)

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

    def retry(self, conversation_id: str, message_id: str) -> tuple[dict, dict] | None:
        """Re-send the last user message before ``message_id`` (spec: retry)."""
        messages = self.db.get_messages(conversation_id)
        index = next((i for i, m in enumerate(messages) if m["id"] == message_id), None)
        if index is None or index == 0:
            return None
        user_msg = messages[index - 1]
        if user_msg["role"] != "user":
            return None
        return self.send(conversation_id, user_msg["content"])

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
    "es": ("Fuentes locales del usuario (no salen de este equipo). Úsalas solo si son "
           "pertinentes y cita la que uses como [1], [2]…:"),
    "en": ("The user's local sources (they never leave this device). Use them only if "
           "relevant and cite the one you use as [1], [2]…:"),
}


def _sources_block(sources: list[dict[str, Any]], user_text: str) -> str:
    """LCE C1: retrieved paragraphs for a local answer, with their origin."""
    from .lang import detect_language
    head = _SOURCES_HEAD.get(detect_language(user_text), _SOURCES_HEAD["en"])
    lines = [head]
    for i, s in enumerate(sources, 1):
        lines.append(f"[{i}] ({s['source']}) {s['text']}")
    return "\n".join(lines)
