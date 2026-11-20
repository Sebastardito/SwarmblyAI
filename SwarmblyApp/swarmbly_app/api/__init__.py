"""FastAPI application: REST routes + WebSocket events + static web UI."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .. import egress
from .. import skills
from ..config import ConfigError, validate_changes
from ..egress import host_of
from ..keystore import SECRET_KEYS, delete_secret, get_secret, redact, set_secret
from ..state import AppState
from ..tools import (MCPApprovalError, MCPClient, MCPError, MCPNotFound,
                     MCPNotRunning, MCPTimeout, MCPUnavailable, ServerConfig,
                     StandingError, ToolDenied)
from ..agent_adapter import AgentConflict, AgentUnavailable
from .security import ApiGuard, GuardMiddleware

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
REPORT_FORMATS = {"json": "application/json", "markdown": "text/markdown",
                  "html": "text/html"}


class _RevalidatedStatic(StaticFiles):
    """The web UI's files are revalidated on every load (``no-cache`` keeps the
    ETag check): without a Cache-Control header the browser reused an old
    ``es.json`` after an update, and new labels showed as keys."""

    def file_response(self, *args: Any, **kwargs: Any) -> Response:
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "no-cache"
        return resp


# ---------------------------------------------------------------------------
# Skills (3.4): per-project folders under <project>/skills/
# ---------------------------------------------------------------------------
# The loader (skills.py) owns safety. The API only lists, imports and matches;
# the body is never returned in list responses and never executed.

_SKILL_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
_SKILL_MANIFESTS = ".imports.json"


def _skills_root(project: Any) -> Path:
    return Path(project.path) / "skills"


def _read_skill_manifests(root: Path) -> dict[str, dict[str, Any]]:
    path = root / _SKILL_MANIFESTS
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_skill_manifests(root: Path, data: dict[str, dict[str, Any]]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    path = root / _SKILL_MANIFESTS
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _skill_size(root: Path) -> int:
    total = 0
    try:
        for path in root.rglob("*"):
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
    except OSError:
        return total
    return total


def _skill_info(skill: Any, manifests: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Listing metadata; the body is deliberately not sent to the browser."""
    saved = manifests.get(skill.name) or {}
    return {
        "name": skill.name,
        "description": skill.description,
        "source": str(saved.get("source") or skill.root),
        "destination": str(skill.root),
        "size": _skill_size(skill.root),
        "sha256": skill.sha256,
        "license": skill.license,
        "compatibility": skill.compatibility,
        "allowed_tools": list(skill.allowed_tools),
        "requested_tools": list(skill.requested_tools),
        "tools_note": skill.tools_note,
        "warnings": list(skill.warnings),
        "copied": list(saved.get("copied") or []),
        "ignored": list(saved.get("ignored") or []),
        "imported_at": str(saved.get("imported_at") or ""),
    }


_TOKEN_RE = re.compile(r"[0-9a-záéíóúñü]+", re.I)
_STOP = frozenset("""
a an and are as at be by can did do does for from has have how i if in into is it
its me my no not of on or our should than that the their them then there these
they this to up us was we were what when where which who why will with would you
your al algo como con cual cuando de del desde donde dos el ella ellas ellos en
entre era es esa ese eso esta este esto fue ha han hasta hay la las le les lo los
más me mi mis muy no nos o para pero por porque que qué se sea ser si sin sobre su
sus te tiene todo tu tus un una uno unos y ya
""".split())


def _match_tokens(text: str) -> set[str]:
    return {word for word in _TOKEN_RE.findall((text or "").lower())
            if len(word) >= 3 and word not in _STOP}


def _skill_suggestions(items: list[dict[str, Any]], text: str,
                       limit: int = 3) -> list[dict[str, Any]]:
    """Simple lexical offer: name + description words against the message.

    Two shared meaningful words, or any of the skill's name words, offer the
    skill. The score is the share of the first six description words found,
    plus 0.2 when the name matches. This only proposes; activation is the
    user's click (or the explicit selector).
    """
    words = _match_tokens(text)
    if len(words) < 2:
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        description = _match_tokens(f"{item.get('name', '')} {item.get('description', '')}")
        if not description:
            continue
        overlap = description & words
        name_overlap = _match_tokens(str(item.get("name") or "")) & words
        if len(overlap) < 2 and not name_overlap:
            continue
        score = len(overlap) / max(1, min(len(description), 6))
        if name_overlap:
            score += 0.2
        if score < 0.25:
            continue
        out.append({"name": item.get("name", ""),
                    "description": item.get("description", ""),
                    "score": round(min(score, 1.0), 3),
                    "matched": sorted(overlap)})
    out.sort(key=lambda item: (-item["score"], item["name"]))
    return out[:limit]



def create_app(state: AppState, guard: ApiGuard | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # The WebSocket bridge lives on this loop; chat/P2P publish from other
        # threads, so capture the loop for run_coroutine_threadsafe dispatch.
        state.bus.set_loop(asyncio.get_running_loop())
        try:
            yield
        finally:
            # A local MCP server was started by an explicit request; app
            # shutdown stops it and reaps it, never leaving a process behind.
            client = getattr(state, "_mcp_client", None)
            if client is not None:
                try:
                    client.close()
                finally:
                    try:
                        delattr(state, "_mcp_client")
                    except AttributeError:
                        pass

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
        return HTMLResponse(guard.inject(html), headers={"Cache-Control": "no-store"})

    app.add_api_route("/", _index, methods=["GET"], include_in_schema=False)
    app.add_api_route("/index.html", _index, methods=["GET"], include_in_schema=False)

    # ---- MCP servers (3.4) -----------------------------------------------------
    def _mcp() -> MCPClient:
        """One client per app, created lazily; it starts nothing by itself."""
        client = getattr(state, "_mcp_client", None)
        if client is None:
            client = MCPClient(state.tools, data_root=state.dirs.root)
            state._mcp_client = client
        return client

    def _project_id(project: str | None, body: dict[str, Any] | None = None) -> str:
        if isinstance(body, dict) and "project_id" in body:
            value = body.get("project_id")
        elif project is not None:
            value = project
        else:
            value = state.projects.active_id
        pid = str(value or "")
        if pid and state.projects.get(pid) is None:
            raise HTTPException(status_code=404, detail="unknown or unavailable project")
        return pid

    def _env_names(body: dict[str, Any]) -> list[str]:
        """The API accepts environment variable NAMES, never values."""
        for key in ("env_values", "environment", "env_vars", "environment_values", "envValues"):
            if key in body:
                raise HTTPException(
                    status_code=400,
                    detail="environment variable values are not accepted; send names only")
        for key in ("env", "env_allowlist"):
            if key in body and isinstance(body[key], dict):
                raise HTTPException(
                    status_code=400,
                    detail="environment variable values are not accepted; send names only")
        raw = body.get("env_allowlist", body.get("env", []))
        if raw is None:
            raw = []
        if isinstance(raw, dict):
            raise HTTPException(
                status_code=400,
                detail="environment variable values are not accepted; send names only")
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, list):
            raise HTTPException(status_code=400, detail="env_allowlist must be a list of names")
        names: list[str] = []
        for item in raw:
            if not isinstance(item, str):
                raise HTTPException(
                    status_code=400,
                    detail="environment entries must be names, not values")
            names.append(item)
        return names

    def _server_config(body: dict[str, Any]) -> ServerConfig:
        body = body or {}
        kind = str(body.get("kind") or ("remote_http" if body.get("url") else "local_stdio"))
        env_names = _env_names(body)
        if kind == "local_stdio":
            args = body.get("args") or []
            if isinstance(args, str):
                args = [args]
            if not isinstance(args, list) or any(not isinstance(arg, str) for arg in args):
                raise HTTPException(status_code=400,
                                    detail="args must be a list of strings")
            return ServerConfig(
                id=str(body.get("id") or ""), kind=kind,
                command=str(body.get("command") or ""),
                args=tuple(args),
                cwd=str(body.get("cwd") or state.dirs.root),
                env_allowlist=tuple(env_names),
            )
        return ServerConfig(
            id=str(body.get("id") or ""), kind="remote_http",
            url=str(body.get("url") or ""),
        )

    def _env_is_set(server_id: str, name: str) -> bool:
        if os.environ.get(name) is not None:
            return True
        try:
            return bool(get_secret(f"mcp.{server_id}.{name}"))
        except Exception:
            return False

    def _server_view(config: ServerConfig, project_id: str) -> dict[str, Any]:
        out = config.describe()
        out["project_id"] = project_id
        out["running"] = _mcp().is_running(config.id, project_id)
        # Names and whether they are set; a value is never read out to the API.
        out["env"] = {name: _env_is_set(config.id, name)
                      for name in config.env_allowlist}
        if config.kind == "local_stdio":
            out["command_line"] = shlex.join([config.command, *config.args])
            out["third_party"] = False
        else:
            host = host_of(config.url)
            cls, _ = egress.classify_url(config.url)
            policy = egress.policy()
            out["command_line"] = ""
            out["host"] = host
            out["host_class"] = cls
            out["third_party"] = True
            out["host_authorised"] = policy.tool_authorised(host)
            out["passages_authorised"] = policy.third_party_passages
        return out

    def _http_status(exc: Exception) -> int:
        if isinstance(exc, MCPNotFound):
            return 404
        if isinstance(exc, (ToolDenied, egress.EgressDenied)):
            return 403
        if isinstance(exc, MCPUnavailable):
            return 503
        if isinstance(exc, MCPTimeout):
            return 504
        if isinstance(exc, MCPNotRunning):
            return 409
        if isinstance(exc, (MCPError, ValueError, OSError)):
            return 400
        return 500

    def _mcp_fail(exc: Exception) -> HTTPException:
        return HTTPException(status_code=_http_status(exc), detail=str(exc))

    @app.get("/api/mcp/servers")
    def mcp_servers(project: str | None = None) -> dict[str, Any]:
        pid = _project_id(project)
        client = _mcp()
        return {
            "project_id": pid,
            "active_project": state.projects.active_id,
            "author_enabled": bool(state.config.get("tools.author.enabled")),
            "servers": [_server_view(config, pid) for config in client.servers(pid)],
        }

    @app.post("/api/mcp/servers")
    def mcp_add(body: dict[str, Any], project: str | None = None) -> dict[str, Any]:
        pid = _project_id(project, body)
        try:
            config = _server_config(body)
            config = _mcp().add_server(config, pid)
        except HTTPException:
            raise
        except Exception as exc:
            raise _mcp_fail(exc) from exc
        return _server_view(config, pid)

    @app.delete("/api/mcp/servers/{server_id}")
    def mcp_remove(server_id: str, project: str | None = None,
                   body: dict[str, Any] | None = None) -> dict[str, Any]:
        pid = _project_id(project, body)
        try:
            removed = _mcp().remove_server(server_id, pid)
        except Exception as exc:
            raise _mcp_fail(exc) from exc
        if not removed:
            raise HTTPException(status_code=404, detail=f"unknown MCP server {server_id!r}")
        return {"removed": True, "id": server_id, "project_id": pid}

    @app.get("/api/mcp/servers/{server_id}/status")
    def mcp_status(server_id: str, project: str | None = None,
                   body: dict[str, Any] | None = None) -> dict[str, Any]:
        pid = _project_id(project, body)
        try:
            config = _mcp().server(server_id, pid)
        except Exception as exc:
            raise _mcp_fail(exc) from exc
        return _server_view(config, pid)

    @app.post("/api/mcp/servers/{server_id}/start")
    def mcp_start(server_id: str, project: str | None = None,
                  body: dict[str, Any] | None = None) -> dict[str, Any]:
        pid = _project_id(project, body)
        try:
            config = _mcp().start(server_id, pid)
        except Exception as exc:
            raise _mcp_fail(exc) from exc
        return _server_view(config, pid)

    @app.post("/api/mcp/servers/{server_id}/stop")
    def mcp_stop(server_id: str, project: str | None = None,
                 body: dict[str, Any] | None = None) -> dict[str, Any]:
        pid = _project_id(project, body)
        try:
            stopped = _mcp().stop(server_id, pid)
            config = _mcp().server(server_id, pid)
        except Exception as exc:
            raise _mcp_fail(exc) from exc
        view = _server_view(config, pid)
        view["stopped"] = stopped
        return view

    @app.post("/api/mcp/servers/{server_id}/propose")
    def mcp_propose(server_id: str, project: str | None = None,
                    body: dict[str, Any] | None = None) -> dict[str, Any]:
        pid = _project_id(project, body)
        try:
            manifest = _mcp().propose(server_id, pid)
            view = _server_view(_mcp().server(server_id, pid), pid)
        except Exception as exc:
            raise _mcp_fail(exc) from exc
        out = manifest.to_dict()
        out.update(status=view["status"], running=view["running"],
                   suspension_reason=view["suspension_reason"], server=view)
        return out

    @app.post("/api/mcp/servers/{server_id}/approve")
    def mcp_approve(server_id: str, body: dict[str, Any] | None = None,
                    project: str | None = None) -> dict[str, Any]:
        body = body or {}
        pid = _project_id(project, body)
        tools = body.get("tools")
        if tools is not None:
            if not isinstance(tools, list) or any(not isinstance(name, str) for name in tools):
                raise HTTPException(status_code=400,
                                    detail="tools must be a list of tool names")
        try:
            config = _mcp().approve(server_id, tools, pid)
        except Exception as exc:
            raise _mcp_fail(exc) from exc
        return _server_view(config, pid)

    # ---- agent runtime and standing approvals (3.4, D-011) -------------------
    @app.get("/api/agent/tools")
    def agent_tools(project: str | None = None) -> dict[str, Any]:
        pid = _project_id(project)
        try:
            return state.chat.agent_tools(pid)
        except Exception as exc:
            raise _mcp_fail(exc) from exc

    @app.get("/api/tools/standing")
    def list_standing(project: str | None = None) -> dict[str, Any]:
        pid = _project_id(project)
        try:
            records = state.agent.standing_records(pid)
        except Exception as exc:
            raise _mcp_fail(exc) from exc
        return {"project_id": pid, "standing": records}

    @app.post("/api/tools/standing")
    def set_standing(body: dict[str, Any] | None = None,
                     project: str | None = None) -> dict[str, Any]:
        body = body or {}
        pid = _project_id(project, body)
        spec_id = str(body.get("spec_id") or "")
        if not spec_id:
            raise HTTPException(status_code=400, detail="spec_id is required")
        enabled = body.get("standing", True)
        if not isinstance(enabled, bool):
            raise HTTPException(status_code=400, detail="standing must be true or false")
        try:
            if enabled:
                state.agent.grant_standing(spec_id, pid)
            else:
                state.agent.revoke_standing(spec_id, pid)
            records = state.agent.standing_records(pid)
        except StandingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise _mcp_fail(exc) from exc
        return {"project_id": pid, "spec_id": spec_id,
                "standing": enabled, "standing_tools": records}

    @app.post("/api/conversations/{conv_id}/messages/{message_id}/approve")
    def approve_agent_tool(conv_id: str, message_id: str,
                           body: dict[str, Any] | None = None) -> dict[str, Any]:
        body = body or {}
        decision = str(body.get("decision") or "")
        if decision not in ("run", "skip", "stop", "approve", "deny"):
            raise HTTPException(
                status_code=400,
                detail="decision must be run, skip or stop")
        args_sha256 = str(body.get("args_sha256") or "")
        remember = body.get("remember", False)
        if not isinstance(remember, bool):
            raise HTTPException(status_code=400, detail="remember must be true or false")
        try:
            return state.chat.agent_decide(
                conv_id, message_id, decision,
                remember=remember, args_sha256=args_sha256)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except AgentConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except AgentUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except StandingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise _mcp_fail(exc) from exc

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
        return redact(state.config.all())

    @app.put("/api/config")
    def put_config(body: dict[str, Any]) -> dict:
        try:
            changes = validate_changes(body)
        except ConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        # API keys go to the keystore, never to config.json (3.0.1)
        for key in SECRET_KEYS:
            if key in changes:
                value = changes.pop(key)
                if isinstance(value, str) and value.strip():
                    set_secret(key, value.strip())
                else:
                    delete_secret(key)
                changes[key] = ""
        if "privacy.third_party_models" in changes:
            changes["privacy.third_party_models"] = sorted(
                {host_of(str(h)) or str(h).strip().lower()
                 for h in changes["privacy.third_party_models"] if str(h).strip()})
        merged = state.config.update(changes)
        swarm = merged["swarm"]
        if int(swarm.get("k_max", 1)) < int(swarm.get("k_min", 1)):
            merged = state.config.update({"swarm.k_max": int(swarm["k_min"])})
        state.on_config_changed()
        return redact(merged)

    @app.post("/api/config/reset")
    def reset_config(body: dict[str, Any] | None = None) -> dict:
        section = (body or {}).get("section")
        if section == "api":
            raise HTTPException(status_code=400,
                                detail="api settings are changed from the command line")
        state.config.reset(section)
        state.on_config_changed()
        return redact(state.config.all())

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
        return {"applied": changes, "config": redact(merged)}

    @app.post("/api/setup/revert")
    def setup_revert() -> dict:
        if not state.restore_config("before-profile"):
            raise HTTPException(status_code=404, detail="no previous configuration saved")
        state.on_config_changed()
        return redact(state.config.all())

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

    # ---- author search (3.4) -----------------------------------------------------
    # The only path to an author lookup: the user presses Run in the consent
    # box, the API issues one token per chosen service and invokes it. No
    # model turn reaches this code, and no request is made before it.
    def _author_enabled() -> bool:
        from ..tools import author_enabled
        return author_enabled(state.config.all())

    def _author_status() -> dict[str, Any]:
        from ..tools import AUTHOR_HOSTS, AUTHOR_SERVICES
        enabled = _author_enabled()
        return {
            "enabled": enabled,
            "author_enabled": enabled,
            "services": [{"id": service, "host": AUTHOR_HOSTS[service]}
                         for service in AUTHOR_SERVICES],
            "hosts": {service: AUTHOR_HOSTS[service]
                      for service in AUTHOR_SERVICES},
        }

    @app.get("/api/author/status")
    @app.get("/api/author")
    def author_status() -> dict[str, Any]:
        return _author_status()

    @app.post("/api/author/cancel")
    def author_cancel(body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Cancel closes the consent box; it never sends anything."""
        return {"cancelled": True, "sent": 0}

    @app.post("/api/author/lookup")
    @app.post("/api/author/approve")
    def author_lookup(body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Approve one exact name and the chosen services, then look them up."""
        from ..author_search import (AuthorSearchDisabled, AuthorSearchError,
                                     lookup)
        from ..tools import AUTHOR_HOSTS
        body = body or {}
        conversation_id = str(body.get("conversation_id") or "")
        conv = None
        if conversation_id:
            conv = state.db.get_conversation(conversation_id)
            if conv is None:
                raise HTTPException(status_code=404,
                                    detail="conversation not found")
            project_id = str(conv.get("project_id") or "")
        else:
            # A scripts/CLI caller can ask without a chat message; the UI
            # always sends the conversation so the table lands in the answer.
            project_id = str(body.get("project_id") or "")
            if project_id and state.projects.get(project_id) is None:
                raise HTTPException(status_code=404,
                                    detail="unknown or unavailable project")
        lang = str(state.config.get("language") or "en")
        try:
            result = lookup(
                state.tools, state.config.all(),
                name=body.get("name"), services=body.get("services"),
                project_id=project_id, orcid=str(body.get("orcid") or ""),
                affiliation=str(body.get("affiliation") or ""),
                max_results=body.get("max_results"), lang=lang,
                candidates_shown=body.get("candidates_shown"))
        except AuthorSearchDisabled as exc:
            detail = ("La búsqueda de autores está desactivada. Actívala en "
                      "Ajustes → Herramientas." if lang.lower().startswith("es")
                      else str(exc))
            raise HTTPException(status_code=403, detail=detail) from exc
        except AuthorSearchError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (ToolDenied, egress.EgressDenied) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

        if result["ambiguous"]:
            # A name search came back with several people: show them and stop.
            # No works are fetched and no message is added before the pick.
            return {
                "ambiguous": True,
                "conversation_id": conversation_id,
                "project_id": project_id,
                "candidates": result["candidates"],
                "works": [],
                "author": result["author"],
                "receipt": result["receipt"],
                "message": ("ORCID encontró más de una persona. Elige una; "
                            "todavía no se buscaron obras."
                            if lang.lower().startswith("es") else
                            "ORCID found more than one person. Pick one; no works "
                            "have been fetched yet."),
            }

        es = lang.lower().startswith("es")
        services = list(result["author"]["services"])
        exact_name = str(body.get("name") or "")
        answer = {
            "ambiguous": False,
            "conversation_id": conversation_id,
            "project_id": project_id,
            "works": result["works"],
            "candidates": [],
            "author": result["author"],
            "receipt": result["receipt"],
            "hosts": {service: AUTHOR_HOSTS[service] for service in services},
        }
        if conv is None:
            return answer
        user_text = ((f"Buscar las obras de {exact_name} en "
                      f"{', '.join(services)}") if es else
                     f"Look up the works of {exact_name} in "
                     f"{', '.join(services)}")
        meta = {
            "status": "done", "mode": "local", "model": "author",
            "executed": "local",
            "author": result["author"],
            "receipt": result["receipt"],
            "recipe": "author",
        }
        request_id = result["request_id"]
        meta["request_id"] = request_id
        user_msg = state.db.add_message(conversation_id, "user", user_text,
                                        meta={"kind": "author_lookup"})
        if str(conv.get("title") or "") in ("", "New conversation"):
            title = user_text[:56]
            state.db.update_conversation(
                conversation_id,
                title=(title + "…") if len(user_text) > 56 else title)
        assistant_msg = state.db.add_message(
            conversation_id, "assistant", result["content"], meta=meta)
        state.db.add_request(request_id, conversation_id,
                             assistant_msg["id"], "local", "author")
        state.db.finish_request(request_id, "done", meta)
        state.db.touch_conversation(conversation_id)
        try:
            state.chat._changed(conversation_id)
        except Exception:
            pass
        state.bus.publish("chat.done", request_id=request_id,
                          conversation_id=conversation_id,
                          message_id=assistant_msg["id"], status="done",
                          content=result["content"], meta=meta)
        answer.update({"user_message": user_msg,
                       "assistant_message": assistant_msg})
        return answer

    # ---- conversations -----------------------------------------------------------
    @app.get("/api/conversations")
    def list_conversations(project: str | None = None) -> list[dict]:
        """All conversations, or one project's (``?project=<id>``; empty = personal)."""
        return state.chat.list_conversations(project)

    @app.post("/api/conversations")
    def create_conversation(body: dict[str, Any] | None = None) -> dict:
        body = body or {}
        project_id = str(body.get("project_id") or "")
        if project_id and state.projects.get(project_id) is None:
            raise HTTPException(status_code=404, detail="unknown or unavailable project")
        return state.chat.create_conversation(
            title=body.get("title", ""),
            mode=body.get("mode", ""),
            model=body.get("model", ""), project_id=project_id)

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
        from ..recipes import ListJobError
        recipe = str(body.get("recipe") or "")
        list_job = body.get("list_job")
        text = str(body.get("text", "")).strip()
        if not text and recipe == "list" and isinstance(list_job, dict):
            text = str(list_job.get("operation") or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="empty message")
        skill_name = str(body.get("skill") or "").strip()
        skill_obj = None
        if skill_name:
            conv = state.db.get_conversation(conv_id)
            if conv is None:
                raise HTTPException(status_code=404,
                                    detail=f"unknown conversation {conv_id}")
            project_id = str(conv.get("project_id") or "")
            if not project_id:
                raise HTTPException(
                    status_code=400,
                    detail="skills belong to a project; open a project first")
            skill_obj = _load_skill(project_id, skill_name)
        try:
            user_msg, assistant_msg = state.chat.send(
                conv_id, text,
                mode=body.get("mode") or None,
                model=body.get("model") or None,
                allow_public=bool(body.get("allow_public")),
                web_query=str(body.get("web_query") or ""),
                recipe=recipe, list_job=list_job, skill=skill_obj,
                use_tools=bool(body.get("use_tools")))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ListJobError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"user_message": user_msg, "assistant_message": assistant_msg}

    # ---- skills (3.4): import, list and offer, never a tool ---------------------
    def _project_or_404(project_id: str):
        project = state.projects.get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        return project

    def _discover(project_id: str):
        project = _project_or_404(project_id)
        root = _skills_root(project)
        errors: list[tuple[Path, str]] = []
        found = skills.discover(root, errors=errors) if root.is_dir() else []
        manifests = _read_skill_manifests(root)
        return project, root, found, [(str(path), reason) for path, reason in errors], manifests

    @app.get("/api/skills")
    def list_skills(project_id: str = "") -> dict:
        if not project_id:
            return {"project_id": "", "skills": [], "errors": []}
        _project, _root, found, errors, manifests = _discover(project_id)
        return {"project_id": project_id,
                "skills": [_skill_info(skill, manifests) for skill in found],
                "errors": [{"path": path, "reason": reason}
                           for path, reason in errors]}

    @app.post("/api/skills/import")
    def import_skill(body: dict[str, Any]) -> dict:
        project_id = str(body.get("project_id") or "")
        _project_or_404(project_id)
        raw = str(body.get("path") or "").strip()
        if not raw:
            raise HTTPException(status_code=400,
                                detail="choose the skill folder to import")
        source = Path(raw).expanduser()
        if source.is_symlink() or not source.is_dir():
            raise HTTPException(status_code=400,
                                detail=f"{source}: not a folder")
        _project, root, _found, _errors, _manifests = _discover(project_id)
        root.mkdir(parents=True, exist_ok=True)
        try:
            imported = skills.import_skill(source, root,
                                           overwrite=bool(body.get("overwrite")))
        except skills.SkillError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=400,
                                detail=f"cannot import {source}: {exc}") from exc
        manifests = _read_skill_manifests(root)
        manifest = imported.manifest
        manifests[imported.name] = {
            "source": manifest.source if manifest else str(source),
            "copied": list(manifest.copied) if manifest else [],
            "ignored": ([{"path": path, "reason": reason}
                         for path, reason in manifest.ignored] if manifest else []),
            "imported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        _write_skill_manifests(root, manifests)
        return {"imported": True, "skill": _skill_info(imported, manifests)}

    @app.post("/api/skills/match")
    def match_skills(body: dict[str, Any]) -> dict:
        """Offer skills whose name/description share words with the message.

        Two shared meaningful words, or a name word, are enough. The route
        only offers; a skill starts only when the user picks it.
        """
        project_id = str(body.get("project_id") or "")
        text = str(body.get("text") or "")
        if not project_id or not text.strip():
            return {"suggestions": [], "errors": []}
        _project, _root, found, errors, manifests = _discover(project_id)
        items = [_skill_info(skill, manifests) for skill in found]
        return {"suggestions": _skill_suggestions(items, text),
                "errors": [{"path": path, "reason": reason}
                           for path, reason in errors]}

    def _load_skill(project_id: str, name: str) -> Any:
        if not name or not _SKILL_NAME_RE.fullmatch(name) or "--" in name:
            raise HTTPException(status_code=400, detail=f"invalid skill name {name!r}")
        _project, _root, found, errors, _manifests = _discover(project_id)
        skill = next((item for item in found if item.name == name), None)
        if skill is None:
            detail = f"no skill named {name!r}"
            if errors:
                detail += ": " + "; ".join(f"{path}: {reason}"
                                           for path, reason in errors[:3])
            raise HTTPException(status_code=404, detail=detail)
        return skill

    # ---- recipes (3.3): "¿Qué quieres hacer?" ------------------------------------
    @app.get("/api/recipes")
    def list_recipes() -> list[dict[str, Any]]:
        from ..recipes import listing
        return listing()

    @app.post("/api/recipes/list/preview")
    def recipe_list_preview(body: dict[str, Any]) -> dict:
        """Validate a list and show what would leave. Nothing is sent."""
        from ..recipes import ListJobError, normalise_list_job, preview_list
        body = body or {}
        project_id = str(body.get("project_id") or "")
        if project_id:
            project = state.projects.get(project_id)
            if project is None:
                raise HTTPException(status_code=404, detail="unknown or unavailable project")
            roots = [project.sources]
        else:
            roots = state.c1_roots("")
        cfg = state.config.all()
        max_items = int((cfg.get("recipes") or {}).get("list_max_items", 200) or 200)
        try:
            job = normalise_list_job(body, max_items=max_items, roots=roots)
        except ListJobError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        workers = state.nodes.available_workers() if state.nodes is not None else []
        nodes = [{"node": str(w.node_id)[:12],
                  "families": sorted({str(m.get("family") or "")
                                      for m in (w.advertisement.get("models") or [])
                                      if str(m.get("family") or "")})}
                 for w in workers]
        return preview_list(job, cfg=cfg, nodes_available=len(workers), nodes=nodes)

    @app.post("/api/recipes/query")
    def recipe_query(body: dict[str, Any]) -> dict:
        """The query offered before a research answer. Nothing leaves the
        computer here: the user sees it, edits it and approves it."""
        from ..recipes import propose_query_details
        body = body or {}
        text = str(body.get("text") or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="empty text")
        glossary: list[tuple[str, str]] = []
        getter = state.chat.glossary_entries
        if getter is not None:
            try:
                glossary = list(getter(str(body.get("project_id") or "")))
            except Exception:
                glossary = []
        # Terms the caller already knows are the user's (a name from their
        # documents) are removed whole, not word by word.  They never leave
        # this response: the endpoint is a local proposal.
        extra = body.get("private") if isinstance(body.get("private"), list) else []
        private = [str(term)[:200] for term in extra if str(term).strip()][:50]
        detail = propose_query_details(text, glossary, private=private)
        detail["message"] = ("no public query remains after removing private terms"
                             if detail.get("empty") else "")
        return detail

    # ---- recipe 5: data with code (3.4) ---------------------------------------
    @app.get("/api/recipes/code/sources")
    def recipe_code_sources(project_id: str = "") -> list[dict[str, Any]]:
        """Recipe 5's picker: C1 documents plus CSV/TSV/XLSX/XLSM sources."""
        from ..recipes import CodeRecipeError
        if project_id and state.projects.get(project_id) is None:
            raise HTTPException(status_code=404, detail="unknown or unavailable project")
        try:
            return state.chat.code_sources(project_id)
        except CodeRecipeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/recipes/code/status")
    def recipe_code_status() -> dict:
        return state.chat.code_status()

    @app.post("/api/recipes/code/propose")
    def recipe_code_propose(body: dict[str, Any] | None = None) -> dict:
        """Ask the writer for one script. Nothing runs and no token is issued."""
        from ..recipes import CodeRecipeError, CodeUnavailableError
        body = body or {}
        try:
            return state.chat.propose_code(
                conversation_id=str(body.get("conversation_id") or ""),
                project_id=str(body.get("project_id") or ""),
                question=str(body.get("question") or ""),
                files=body.get("files"),
                model=str(body.get("model") or ""),
                mode=str(body.get("mode") or ""),
                correction_of=str(body.get("correction_of") or ""))
        except CodeUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
        except CodeRecipeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/recipes/code/approve")
    def recipe_code_approve(body: dict[str, Any] | None = None) -> dict:
        """The only path that issues the one-time sandbox token and runs."""
        from ..recipes import CodeRecipeError, CodeUnavailableError
        body = body or {}
        proposal_id = str(body.get("proposal_id") or "")
        if not proposal_id:
            raise HTTPException(status_code=400, detail="a proposal id is required")
        try:
            return state.chat.approve_code(proposal_id)
        except CodeUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except CodeRecipeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/recipes/code/cancel")
    def recipe_code_cancel(body: dict[str, Any] | None = None) -> dict:
        from ..recipes import CodeRecipeError
        body = body or {}
        proposal_id = str(body.get("proposal_id") or "")
        if not proposal_id:
            raise HTTPException(status_code=400, detail="a proposal id is required")
        try:
            return state.chat.cancel_code(proposal_id)
        except CodeRecipeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/recipes/code/runs/{run_id}/files/{name:path}")
    def recipe_code_file(run_id: str, name: str) -> FileResponse:
        """Serve one regular file from exactly that run's retained /out."""
        from ..recipes import CodeRecipeError
        try:
            path = state.chat.code_output_path(run_id, name)
        except CodeRecipeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return FileResponse(path, filename=path.name)

    @app.post("/api/conversations/{conv_id}/messages/{message_id}/retry")
    def retry_message(conv_id: str, message_id: str,
                      body: dict[str, Any] | None = None) -> dict:
        result = state.chat.retry(conv_id, message_id,
                                  allow_public=bool((body or {}).get("allow_public")),
                                  web_query=str((body or {}).get("web_query") or ""))
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

    @app.post("/api/conversations/{conv_id}/messages/{message_id}/memory")
    def save_memory(conv_id: str, message_id: str, body: dict[str, Any]) -> dict:
        """Save (or discard) what the user confirmed of a memory proposal (3.1)."""
        conv = state.chat.get_conversation(conv_id)
        msg = next((m for m in (state.chat.get_messages(conv_id) if conv else [])
                    if m["id"] == message_id), None)
        if msg is None or not (msg.get("meta") or {}).get("memory_proposals"):
            raise HTTPException(status_code=404, detail="no memory proposal in that message")
        meta = msg["meta"]
        prop = meta["memory_proposals"]
        provenance = {"conversation": conv_id, "message": message_id,
                      "proposal": prop.get("id", ""), "model": prop.get("model", "")}
        if body.get("discard"):
            meta["memory_proposals"]["status"] = "discarded"
            state.memory_log(str(conv.get("project_id") or ""),
                             {**provenance, "decision": "discarded"})
        else:
            notes = [str(n) for n in body.get("notes") or []][:10]
            glossary = [g for g in body.get("glossary") or [] if isinstance(g, dict)][:10]
            try:
                written = state.save_memory(str(conv.get("project_id") or ""), notes, glossary)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            meta["memory_proposals"].update(status="saved", saved=written)
            state.memory_log(str(conv.get("project_id") or ""),
                             {**provenance, "decision": "saved", "notes": written["notes"],
                              "glossary": written["glossary"]})
        state.db.update_message(message_id, meta=meta)
        state.chat._changed(conv_id)
        return meta["memory_proposals"]

    def _message(conv_id: str, message_id: str) -> tuple[dict, dict]:
        conv = state.chat.get_conversation(conv_id)
        msg = next((m for m in (state.chat.get_messages(conv_id) if conv else [])
                    if m["id"] == message_id), None)
        if msg is None:
            raise HTTPException(status_code=404, detail="message not found")
        return conv, msg

    @app.post("/api/conversations/{conv_id}/messages/{message_id}/terms")
    def resolve_terms(conv_id: str, message_id: str, body: dict[str, Any]) -> dict:
        """Concept candidates for the words of a search (3.1): the glossary, and
        Wikidata and GBIF when the user asks (``online``). The single words sent
        are recorded with the message."""
        from .. import egress
        from ..terms import resolve
        conv, msg = _message(conv_id, message_id)
        pid = str(conv.get("project_id") or "")
        words = [str(w) for w in body.get("words") or []][:6]
        lang = str(body.get("lang") or "es")[:2]
        roots = state.c1_roots(pid)
        with egress.request_ledger(f"terms-{message_id}") as ledger:
            with egress.purpose(egress.PUBLIC_QUERY):
                result = resolve(words, lang, state.lce.glossary_entries(roots=roots),
                                 state.lce.glossary_meta(roots=roots),
                                 online=bool(body.get("online", True)))
        sends = [{"destino": e.get("destino", ""), "valor": e.get("valor", ""),
                  "bytes": e.get("bytes", 0)} for e in ledger.events if not e.get("bloqueado")]
        if sends:
            meta = msg.get("meta") or {}
            meta.setdefault("term_lookups", []).append({"words": words, "sends": sends})
            # the message's receipt shows these sends too (they came after it)
            receipt = meta.get("receipt")
            if isinstance(receipt, dict):
                receipt.setdefault("envios", []).extend(
                    {"destino": x["destino"], "clase": "terceros",
                     "tipo": ("id_resultado" if re.fullmatch(r"[\dQ|,]+", str(x["valor"]))
                              else "palabra_suelta"),
                     "valor": x["valor"], "bytes": x["bytes"],
                     "motivo": "revisar términos (lo pediste con el botón)"} for x in sends)
                receipt["bytes_salientes"] = int(receipt.get("bytes_salientes") or 0) + \
                    sum(int(x["bytes"] or 0) for x in sends)
                declared = receipt.setdefault("destinos_declarados", [])
                for host in dict.fromkeys(x["destino"] for x in sends):
                    if host and host not in declared:
                        declared.append(host)
            state.db.update_message(message_id, meta=meta)
            state.chat._changed(conv_id)
        return {"terms": result, "sends": sends}

    @app.post("/api/conversations/{conv_id}/messages/{message_id}/terms/save")
    def save_terms(conv_id: str, message_id: str, body: dict[str, Any]) -> dict:
        """Keep chosen concepts in the glossary (``word = label, name | wd: Q…``)."""
        from ..terms import glossary_entry
        conv, _msg = _message(conv_id, message_id)
        pid = str(conv.get("project_id") or "")
        entries = [glossary_entry(str(x.get("word", "")), x.get("concept") or {})
                   for x in body.get("choices") or [] if x.get("word") and x.get("concept")]
        entries = [e for e in entries if e["term"] and (e["equivalents"] or e["wd"])][:6]
        if not entries:
            return {"saved": []}
        for e in entries:
            e["definition"] = ""            # the description stays in the dialog, not in notes
        written = state.save_memory(pid, [], entries)
        state.memory_log(pid, {"conversation": conv_id, "message": message_id,
                               "decision": "saved", "via": "search terms",
                               "glossary": written.get("glossary", [])})
        return {"saved": written.get("glossary", [])}

    # ---- projects (3.1) ---------------------------------------------------------------
    from .projects import register as _register_projects
    _register_projects(app, state)

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
        app.mount("/", _RevalidatedStatic(directory=str(WEB_DIR), html=True), name="web")

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
