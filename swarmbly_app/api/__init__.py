"""FastAPI application: REST routes + WebSocket events + static web UI."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from ..config import ConfigError, validate_changes
from ..state import AppState
from .security import ApiGuard, GuardMiddleware

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
REPORT_FORMATS = {"json": "application/json", "markdown": "text/markdown",
                  "html": "text/html"}


def create_app(state: AppState, guard: ApiGuard | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # The WebSocket bridge lives on this loop; chat/P2P publish from other
        # threads, so capture the loop for run_coroutine_threadsafe dispatch.
        state.bus.set_loop(asyncio.get_running_loop())
        yield

    app = FastAPI(title="Swarmbly App", version="0.1.0",
                  docs_url="/api/docs", openapi_url="/api/openapi.json",
                  lifespan=lifespan)
    app.state.swarmbly = state
    api_host = str((state.config.get("api") or {}).get("host") or "")
    guard = guard or ApiGuard(extra_hosts={api_host.lower()})
    app.state.guard = guard
    try:
        guard.write_token(state.dirs.root / "api_token")
    except OSError:
        pass
    app.add_middleware(GuardMiddleware, guard=guard)
    state.bus.subscribe_async(_on_event_factory(app))

    def _index() -> HTMLResponse:
        html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(guard.inject(html))

    app.add_api_route("/", _index, methods=["GET"], include_in_schema=False)
    app.add_api_route("/index.html", _index, methods=["GET"], include_in_schema=False)

    # ---- health / system ------------------------------------------------------
    @app.get("/api/health")
    def health() -> dict:
        return state.health()

    @app.get("/api/system")
    def system() -> dict:
        return state.system_report()

    @app.get("/api/identity")
    def identity() -> dict:
        return {"node_id": state.identity.node_id,
                "short_id": state.identity.short_id(12)}

    # ---- models ----------------------------------------------------------------
    @app.get("/api/models")
    def models() -> dict:
        cfg = state.config.all()
        model_cfg = cfg["model"]
        infos = state.model_manager.detect_cached(
            model_cfg.get("backend", "auto"), model_cfg.get("backend_url", ""))
        hardware = state.system_report()
        return {
            "backends": [i.to_dict() for i in infos],
            "recommendations": state.model_manager.recommend(hardware),
            "configured": {
                "backend": model_cfg.get("backend", "auto"),
                "url": model_cfg.get("backend_url", ""),
                "model": model_cfg.get("model_name", ""),
            },
        }

    # ---- dependencies (doctor) ------------------------------------------------------
    @app.get("/api/doctor")
    def doctor() -> dict:
        from ..doctor import run_checks
        return run_checks(state)

    @app.post("/api/doctor/install")
    def doctor_install(body: dict[str, Any]) -> dict:
        job = state.installer.start(list(body.get("packages") or []),
                                    consent=bool(body.get("consent")))
        if job.status == "refused":
            raise HTTPException(status_code=400, detail="; ".join(job.log))
        return {"status": job.status, "packages": job.packages}

    @app.get("/api/doctor/install")
    def doctor_install_status() -> dict:
        job = state.installer.job
        return {"status": "idle"} if job is None else {
            "status": job.status, "packages": job.packages, "log": job.log[-20:],
            "verified": job.verified}

    # ---- optional local SearXNG and web-search check (consent required) ----------
    @app.get("/api/evidence/searxng")
    def searxng_status() -> dict:
        return state.searxng.status()

    @app.post("/api/evidence/searxng/install")
    def searxng_install(body: dict[str, Any]) -> dict:
        job = state.searxng.install(str(body.get("method") or "auto"),
                                    consent=bool(body.get("consent")))
        if job.status == "refused":
            raise HTTPException(status_code=400, detail="; ".join(job.log))
        return {"status": job.status, "method": job.method}

    @app.post("/api/evidence/searxng/uninstall")
    def searxng_uninstall() -> dict:
        return state.searxng.uninstall()

    @app.post("/api/evidence/web/test")
    def web_test() -> dict:
        """One fixed public query through the configured web search (no user data)."""
        from ..engine.providers import web_check
        return web_check(state.config.all().get("evidence") or {})

    # ---- model downloads through Ollama (consent required) -----------------------
    @app.get("/api/models/preview")
    def model_preview(name: str) -> dict:
        try:
            return state.ollama.preview(name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/models/pull")
    def model_pull(body: dict[str, Any]) -> dict:
        if state.config.get("permissions.model_downloads") is False:
            raise HTTPException(status_code=403,
                                detail="model downloads are disabled in Permissions")
        try:
            job = state.ollama.start_pull(str(body.get("name", "")),
                                          consent=bool(body.get("consent")))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if job.status == "failed":
            raise HTTPException(status_code=400, detail=job.detail)
        return job.to_dict()

    @app.post("/api/models/pull/cancel")
    def model_pull_cancel(body: dict[str, Any]) -> dict:
        return {"cancelled": state.ollama.cancel(str(body.get("name", "")))}

    @app.get("/api/models/pulls")
    def model_pulls() -> list[dict]:
        return [j.to_dict() for j in state.ollama.jobs.values()]

    @app.get("/api/models/info")
    def model_info(name: str) -> dict:
        try:
            data = state.ollama.show(name)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Ollama: {exc}") from exc
        return {"name": name, "details": data.get("details"),
                "license": (data.get("license") or "")[:4000],
                "parameters": data.get("parameters"),
                "modified_at": data.get("modified_at")}

    # ---- config -----------------------------------------------------------------
    @app.get("/api/config")
    def get_config() -> dict:
        return state.config.all()

    @app.put("/api/config")
    def put_config(body: dict[str, Any]) -> dict:
        try:
            changes = validate_changes(body)
        except ConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        merged = state.config.update(changes)
        swarm = merged["swarm"]
        if int(swarm.get("k_max", 1)) < int(swarm.get("k_min", 1)):
            merged = state.config.update({"swarm.k_max": int(swarm["k_min"])})
        state.on_config_changed()
        return merged

    @app.post("/api/config/reset")
    def reset_config(body: dict[str, Any] | None = None) -> dict:
        section = (body or {}).get("section")
        if section == "api":
            raise HTTPException(status_code=400,
                                detail="api settings are changed from the command line")
        state.config.reset(section)
        state.on_config_changed()
        return state.config.all()

    # ---- setup: recommended profile (explained, reversible) ----------------------
    def _recommendation() -> dict:
        from ..advisor import recommend
        cfg = state.config.all()["model"]
        state.model_manager.invalidate()
        infos = state.model_manager.detect_cached(cfg.get("backend", "auto"),
                                                  cfg.get("backend_url", ""))
        return recommend(state.system_report(), [i.to_dict() for i in infos],
                         state.config.all())

    @app.get("/api/setup/recommendation")
    def setup_recommendation() -> dict:
        return _recommendation()

    @app.post("/api/setup/apply")
    def setup_apply(body: dict[str, Any] | None = None) -> dict:
        """Apply the recommendation (or a subset of its keys). The previous
        configuration is saved first and can be restored with /revert."""
        rec = _recommendation()
        keys = (body or {}).get("keys")
        changes = {k: v for k, v in rec["changes"].items() if not keys or k in keys}
        try:
            changes = validate_changes(changes)
        except ConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        state.backup_config("before-profile")
        merged = state.config.update({**changes, "profile": "automatic"})
        state.on_config_changed()
        return {"applied": changes, "config": merged}

    @app.post("/api/setup/revert")
    def setup_revert() -> dict:
        if not state.restore_config("before-profile"):
            raise HTTPException(status_code=404, detail="no previous configuration saved")
        state.on_config_changed()
        return state.config.all()

    @app.post("/api/permissions")
    def set_permissions(body: dict[str, Any]) -> dict:
        """Explicit consent for network access (asked in the setup assistant)."""
        import time as _time
        changes: dict[str, Any] = {}
        for key in ("lan_discovery", "internet", "model_downloads"):
            if key in body:
                changes[f"permissions.{key}"] = bool(body[key])
        if not changes:
            raise HTTPException(status_code=400, detail="nothing to set")
        changes["permissions.asked_at"] = _time.time()
        if changes.get("permissions.lan_discovery") is False:
            changes["swarm.lan_enabled"] = False
            changes["swarm.worker_enabled"] = False
        if changes.get("permissions.internet") is False:
            changes["swarm.internet_enabled"] = False
        state.config.update(changes)
        state.on_config_changed()
        return state.config.all()["permissions"]

    @app.get("/api/lce/levels")
    def lce_levels() -> dict:
        from ..advisor import lce_levels as levels, memory_budget
        hw = state.system_report()
        has_model = bool(state.config.get("model.model_name"))
        return levels(hw, memory_budget(hw), has_model)

    # ---- conversations -----------------------------------------------------------
    @app.get("/api/conversations")
    def list_conversations() -> list[dict]:
        return state.chat.list_conversations()

    @app.post("/api/conversations")
    def create_conversation(body: dict[str, Any] | None = None) -> dict:
        body = body or {}
        return state.chat.create_conversation(
            title=body.get("title", ""),
            mode=body.get("mode", ""),
            model=body.get("model", ""))

    @app.get("/api/conversations/{conv_id}")
    def get_conversation(conv_id: str) -> dict:
        conv = state.chat.get_conversation(conv_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        return conv

    @app.get("/api/conversations/{conv_id}/messages")
    def get_messages(conv_id: str) -> list[dict]:
        if state.chat.get_conversation(conv_id) is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        return state.chat.get_messages(conv_id)

    @app.delete("/api/conversations/{conv_id}")
    def delete_conversation(conv_id: str) -> dict:
        state.chat.delete_conversation(conv_id)
        return {"deleted": conv_id}

    @app.post("/api/conversations/{conv_id}/messages", status_code=202)
    def send_message(conv_id: str, body: dict[str, Any]) -> dict:
        text = str(body.get("text", "")).strip()
        if not text:
            raise HTTPException(status_code=400, detail="empty message")
        try:
            user_msg, assistant_msg = state.chat.send(
                conv_id, text,
                mode=body.get("mode") or None,
                model=body.get("model") or None)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"user_message": user_msg, "assistant_message": assistant_msg}

    @app.post("/api/conversations/{conv_id}/messages/{message_id}/retry")
    def retry_message(conv_id: str, message_id: str) -> dict:
        result = state.chat.retry(conv_id, message_id)
        if result is None:
            raise HTTPException(status_code=400, detail="nothing to retry")
        user_msg, assistant_msg = result
        return {"user_message": user_msg, "assistant_message": assistant_msg}

    @app.post("/api/requests/{request_id}/stop")
    def stop_request(request_id: str) -> dict:
        stopped = state.chat.interrupt(request_id)
        return {"stopped": stopped}

    @app.post("/api/requests/_stop_last")
    def stop_last_request() -> dict:
        active = state.chat.active_requests()
        if not active:
            return {"stopped": False}
        last = active[-1]["request_id"]
        return {"stopped": state.chat.interrupt(last), "request_id": last}

    @app.get("/api/conversations/{conv_id}/export")
    def export_conversation(conv_id: str, format: str = "markdown") -> Any:
        if format not in ("json", "markdown", "html"):
            raise HTTPException(status_code=400, detail="format must be json|markdown|html")
        try:
            content = state.chat.export(conv_id, fmt=format)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        media = {"json": "application/json", "markdown": "text/markdown",
                 "html": "text/html"}[format]
        if format == "json":
            return JSONResponse(content=json.loads(content))
        return Response(
            content=content, media_type=media,
            headers={"Content-Disposition":
                     f'attachment; filename="conversation-{conv_id}.{format if format != "markdown" else "md"}"'})

    # ---- LCE ----------------------------------------------------------------------
    @app.get("/api/lce/status")
    def lce_status() -> dict:
        cfg = state.config.all()["lce"]
        return state.lce.status(bool(cfg["enabled"]), cfg["level"])

    @app.post("/api/lce/activate")
    def lce_activate(body: dict[str, Any]) -> dict:
        level = str(body.get("level", "C0")).upper()
        if level not in ("C0", "C1"):
            raise HTTPException(status_code=400,
                                detail=f"level {level} not available in v0.1 (C0 active, C1 prepared)")
        try:
            status = state.lce.activate(level)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        state.config.update({"lce": {"enabled": True, "level": level}})
        return status

    @app.post("/api/lce/deactivate")
    def lce_deactivate() -> dict:
        state.config.update({"lce": {"enabled": False}})
        cfg = state.config.all()["lce"]
        return state.lce.status(False, cfg["level"])

    @app.get("/api/lce/sources")
    def lce_sources() -> list[dict]:
        cfg = state.config.all().get("lce") or {}
        return state.lce.list_sources(cfg.get("sources_dirs") or [])

    # ---- swarm (Phase 2) --------------------------------------------------------------
    @app.get("/api/swarm")
    def swarm_status() -> dict:
        cfg = state.config.all()["swarm"]
        return {
            **state.nodes.status(),
            "config": {k: cfg.get(k) for k in
                       ("mode", "lan_enabled", "internet_enabled",
                        "worker_enabled", "worker_allow_lan",
                        "worker_allow_internet", "worker_max_concurrent",
                        "worker_only_idle", "k_min", "k_max",
                        "n_fragments_max", "discovery_enabled")},
            "worker": state.worker.status() if state.worker else None,
        }

    @app.get("/api/swarm/nodes")
    def swarm_nodes() -> dict:
        return {"peers": state.nodes.status()["peers"],
                "discovered": state.nodes.status()["discovered"]}

    @app.post("/api/swarm/connect")
    def swarm_connect(body: dict) -> dict:
        host = str(body.get("host", "")).strip()
        try:
            port = int(body.get("port", 9765))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="port must be an integer")
        if not host:
            raise HTTPException(status_code=400, detail="host is required")
        state.nodes.connect_manual(host, port)
        return {"connecting": f"{host}:{port}"}

    @app.post("/api/swarm/rescan")
    def swarm_rescan() -> dict:
        """Active mDNS search: a real query; entries refresh only on answers."""
        try:
            result = state.nodes.rescan()
            state.console.scan_finished(result)
            return {"rescanned": True, **result}
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/swarm/worker")
    def swarm_worker(body: dict) -> dict:
        enabled = bool(body.get("enabled", False))
        changes: dict[str, Any] = {"swarm.worker_enabled": enabled}
        if enabled:  # a worker is only reachable with LAN on (v0.1)
            changes["swarm.lan_enabled"] = True
        state.config.update(changes)
        state.on_config_changed()
        return state.worker.status() if state.worker else {"policy": {}}

    @app.get("/api/requests/{request_id}")
    def request_detail(request_id: str) -> dict:
        req = state.db.get_request(request_id)
        if req is None:
            raise HTTPException(status_code=404, detail="request not found")
        return req

    @app.get("/api/requests/{request_id}/report")
    def request_report(request_id: str, format: str = "markdown",
                       detail: str | None = None, save: bool = False) -> Any:
        """Generated on demand; written to the output directory only if
        ``save=true`` (spec §11: viewable without being stored)."""
        if format not in REPORT_FORMATS:
            raise HTTPException(status_code=400, detail="format must be json|markdown|html")
        if state.db.get_request(request_id) is None:
            raise HTTPException(status_code=404, detail="request not found")
        from ..reports import render_report
        detail = detail or state.config.get("results.report_detail") or "standard"
        content = render_report(state.db, request_id, fmt=format, detail=detail)
        headers = {}
        if save:
            ext = {"markdown": "md", "json": "json", "html": "html"}[format]
            path = state.output_dir("reports") / f"report-{request_id}.{ext}"
            path.write_text(content, encoding="utf-8")
            headers["X-Saved-To"] = str(path)
        return Response(content=content, media_type=REPORT_FORMATS[format],
                        headers=headers)

    @app.get("/api/monitor")
    def monitor_summary() -> dict:
        from ..monitor import swarm_health, contribution
        swarm = state.nodes.status()
        stats = state.db.get_stats(days=30)
        return {
            "health": swarm_health(swarm),
            "contribution": contribution(stats),
            "swarm": {
                "nodes_discovered": len(swarm["discovered"]),
                "nodes_connected": swarm["connected_count"],
                "workers_available": len(state.nodes.available_workers()),
                "uptime_s": int(__import__("time").time() - state.started_at),
            },
            "tasks": {"local_requests": sum(s.get("tasks_requested", 0) for s in stats),
                      "distributed_requests": sum(s.get("distributed_requests", 0)
                                                  for s in stats),
                      "dispatched": sum(s.get("dispatched", 0) for s in stats),
                      "dispatch_failed": sum(s.get("dispatch_failed", 0) for s in stats),
                      "served": sum(s.get("tasks_served", 0) for s in stats),
                      "window_days": 30},
        }

    # ---- websocket -----------------------------------------------------------------
    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket) -> None:
        reason = guard.check_websocket(ws.headers, ws.query_params.get("token"))
        if reason:
            await ws.close(code=1008, reason=reason)
            return
        state.bus.set_loop(asyncio.get_running_loop())
        await ws.accept()
        hub = getattr(app.state, "ws_hub", None)
        if hub is not None:
            await hub.handle(ws)

    # ---- static web UI ---------------------------------------------------------------
    if WEB_DIR.exists():
        app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

    return app


class WsHub:
    """Broadcasts bus events to every connected WebSocket client."""

    def __init__(self):
        self._clients: list[WebSocket] = []

    async def handle(self, ws: WebSocket) -> None:
        self._clients.append(ws)
        try:
            while True:
                await ws.receive_text()  # keep-alive; client messages ignored for now
        except WebSocketDisconnect:
            pass
        finally:
            if ws in self._clients:
                self._clients.remove(ws)

    async def broadcast(self, event: dict) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._clients):
            try:
                await ws.send_text(json.dumps(event))
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in self._clients:
                self._clients.remove(ws)


def _on_event_factory(app: FastAPI):
    """Attach a bus→WS bridge; hub is created lazily on first connection."""
    hub = WsHub()
    app.state.ws_hub = hub

    async def _on_event(event: dict) -> None:
        await hub.broadcast(event)

    return _on_event
