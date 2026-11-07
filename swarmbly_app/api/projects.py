"""Projects API (3.1): create, open, switch, export and restore projects."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from .. import __version__
from ..keystore import SECRET_KEYS, get_secret
from ..projects import (PACKAGE_SUFFIX, Project, ProjectError, cloud_warning, default_parent,
                        export_package, import_package, inspect_package)

MAX_UPLOAD = 2 * 1024 ** 3


def register(app: FastAPI, state: Any) -> None:
    def _bad(exc: Exception) -> HTTPException:
        return HTTPException(status_code=400, detail=str(exc))

    def _project(project_id: str) -> Project:
        try:
            return state.projects.require(project_id)
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects")
    def list_projects() -> dict:
        parent = default_parent()
        return {"items": state.projects.describe(), "active": state.projects.active_id,
                "default_parent": str(parent), "default_parent_warning": cloud_warning(parent)}

    @app.post("/api/projects")
    def create_project(body: dict[str, Any]) -> dict:
        try:
            project = state.projects.create(str(body.get("name", "")), body.get("parent") or None,
                                            include_personal=bool(body.get("include_personal")))
            if body.get("activate", True):
                state.projects.set_active(project.id)
        except (ProjectError, OSError) as exc:
            raise _bad(exc) from exc
        return project.describe()

    @app.post("/api/projects/open")
    def open_project(body: dict[str, Any]) -> dict:
        try:
            project = state.projects.open(str(body.get("path", "")))
        except (ProjectError, OSError) as exc:
            raise _bad(exc) from exc
        added = state.sync_projects(project.id).get(project.id, 0)
        if body.get("activate", True):
            state.projects.set_active(project.id)
        return {**project.describe(), "chats_added": added}

    @app.put("/api/projects/active")
    def set_active(body: dict[str, Any]) -> dict:
        try:
            state.projects.set_active(str(body.get("id") or ""))
        except ProjectError as exc:
            raise _bad(exc) from exc
        return {"active": state.projects.active_id}

    @app.patch("/api/projects/{project_id}")
    def update_project(project_id: str, body: dict[str, Any]) -> dict:
        _project(project_id)
        allowed = {k: v for k, v in body.items() if k in ("name", "include_personal", "description")}
        try:
            return state.projects.update(project_id, **allowed).describe()
        except (ProjectError, OSError) as exc:
            raise _bad(exc) from exc

    @app.delete("/api/projects/{project_id}")
    def forget_project(project_id: str) -> dict:
        """Close the project in this app. Its folder and files are kept."""
        project = state.projects.get(project_id)
        state.projects.forget(project_id)
        for conv in state.chat.list_conversations(project_id):
            state.db.delete_conversation(conv["id"])      # the folder keeps the chats
        return {"forgotten": project_id, "folder_kept": str(project.path) if project else ""}

    @app.get("/api/projects/{project_id}/sources")
    def project_sources(project_id: str) -> list[dict]:
        project = _project(project_id)
        return state.lce.list_sources(roots=project.roots())

    @app.post("/api/projects/{project_id}/export")
    def export_project(project_id: str) -> dict:
        project = _project(project_id)
        for conv in state.chat.list_conversations(project_id):   # the folder is up to date
            project.write_chat(conv, state.db.get_messages(conv["id"]))
        secrets = [get_secret(k) for k in SECRET_KEYS]
        try:
            return export_package(project, secrets=secrets, app_version=__version__)
        except (ProjectError, OSError) as exc:
            raise _bad(exc) from exc

    @app.get("/api/projects/{project_id}/export/{filename}")
    def download_export(project_id: str, filename: str) -> FileResponse:
        project = _project(project_id)
        path = project.exports / filename
        if (not filename.endswith(PACKAGE_SUFFIX) or "/" in filename or "\\" in filename
                or not path.is_file()):
            raise HTTPException(status_code=404, detail="no such export")
        return FileResponse(path, media_type="application/zip", filename=filename)

    async def _upload(request: Request) -> Path:
        body = await request.body()
        if not body or len(body) > MAX_UPLOAD:
            raise HTTPException(status_code=400, detail="empty or too large package")
        tmp = tempfile.NamedTemporaryFile(suffix=PACKAGE_SUFFIX, delete=False)
        tmp.write(body)
        tmp.close()
        return Path(tmp.name)

    @app.post("/api/projects/inspect")
    async def inspect(request: Request) -> dict:
        """Verify an uploaded package (hashes, no extra files) without restoring it."""
        path = await _upload(request)
        try:
            info = inspect_package(path)
        except ProjectError as exc:
            raise _bad(exc) from exc
        finally:
            path.unlink(missing_ok=True)
        return {"project": info["manifest"]["project"], "files": info["files"],
                "chats": info["chats"], "sources": info["sources"],
                "created_at": info["manifest"].get("created_at"),
                "app_version": info["manifest"].get("app_version")}

    @app.post("/api/projects/import")
    async def restore(request: Request, parent: str = "", as_copy: bool = False) -> dict:
        """Restore an uploaded ``.swarmbly`` package into a new folder."""
        path = await _upload(request)
        try:
            project, renamed = import_package(path, state.projects, parent or None,
                                              as_copy=as_copy)
        except (ProjectError, OSError) as exc:
            raise _bad(exc) from exc
        finally:
            path.unlink(missing_ok=True)
        added = state.sync_projects(project.id).get(project.id, 0)
        state.projects.set_active(project.id)
        return {**project.describe(), "chats_added": added, "restored_as_copy": bool(renamed)}
