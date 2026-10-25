"""Consented model downloads through Ollama (decision D12).

The app never fetches model weights itself: it asks the local Ollama server
to pull a model (``POST /api/pull``) after the user has seen the download
size, the publisher's licence, the model page and the free disk space. Progress
is streamed to the UI as ``models.pull`` events and can be cancelled. When the
pull finishes, the licence *Ollama reports* (``/api/show``) is shown, because
it is the authoritative text for the copy actually installed.
"""

from __future__ import annotations

import re
import shutil
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from .catalog import by_name

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._\-/]{0,80}(:[a-z0-9._\-]{1,40})?$", re.I)
GB = 1024 ** 3


@dataclass
class PullJob:
    name: str
    status: str = "pending"            # pending|running|done|failed|cancelled
    completed: int = 0
    total: int = 0
    detail: str = ""
    license: str = ""
    started_at: float = field(default_factory=time.time)
    cancel: threading.Event = field(default_factory=threading.Event)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status, "completed": self.completed,
                "total": self.total, "detail": self.detail,
                "license": self.license[:2000],
                "percent": round(100 * self.completed / self.total, 1) if self.total else None}


class OllamaModels:
    def __init__(self, bus, url_getter, data_dir_getter, transport=None):
        self.bus = bus
        self.url = url_getter            # () -> base URL of Ollama
        self.data_dir = data_dir_getter  # () -> Path (for free-space checks)
        self.transport = transport       # injectable for tests
        self.jobs: dict[str, PullJob] = {}
        self._lock = threading.Lock()

    def _client(self, timeout: float | None = 10.0) -> httpx.Client:
        kwargs: dict[str, Any] = {"timeout": timeout}
        if self.transport is not None:
            kwargs["transport"] = self.transport
        return httpx.Client(**kwargs)

    # -- before downloading: what the user must see ------------------------------
    def preview(self, name: str) -> dict[str, Any]:
        if not _NAME_RE.match(name or ""):
            raise ValueError("invalid model name")
        entry = by_name(name)
        free = shutil.disk_usage(str(self.data_dir())).free / GB
        size = entry["download_gb"] if entry else None
        return {
            "name": name,
            "known": entry is not None,
            "download_gb": size,
            "license": entry["license"] if entry else "unknown until downloaded "
                                                      "(Ollama reports it afterwards)",
            "page": entry["page"] if entry else f"https://ollama.com/library/{name.split(':')[0]}",
            "origin": "ollama.com registry, pulled by your local Ollama",
            "free_disk_gb": round(free, 1),
            "enough_space": size is None or free > size + 1.0,
            "checked_on": entry.get("checked_on") if entry else None,
            "note": entry.get("note") if entry else "",
        }

    # -- pull ------------------------------------------------------------------------
    def start_pull(self, name: str, consent: bool) -> PullJob:
        preview = self.preview(name)
        job = PullJob(name=name)
        if not consent:
            job.status, job.detail = "failed", "explicit consent is required"
            return job
        if not preview["enough_space"]:
            job.status, job.detail = "failed", "not enough free disk space"
            return job
        with self._lock:
            running = self.jobs.get(name)
            if running and running.status == "running":
                return running
            self.jobs[name] = job
        threading.Thread(target=self._run, args=(job,), daemon=True,
                         name=f"pull-{name}").start()
        return job

    def cancel(self, name: str) -> bool:
        job = self.jobs.get(name)
        if job is None or job.status != "running":
            return False
        job.cancel.set()
        return True

    def _emit(self, job: PullJob) -> None:
        self.bus.publish("models.pull", **job.to_dict())

    def _run(self, job: PullJob) -> None:
        import json
        job.status = "running"
        self._emit(job)
        last_emit = 0.0
        base = self.url().rstrip("/")
        try:
            with self._client(timeout=None) as client:
                with client.stream("POST", f"{base}/api/pull",
                                   json={"model": job.name, "name": job.name,
                                         "stream": True}) as resp:
                    if resp.status_code != 200:
                        raise RuntimeError(f"Ollama answered HTTP {resp.status_code}")
                    for line in resp.iter_lines():
                        if job.cancel.is_set():
                            job.status, job.detail = "cancelled", "cancelled by the user"
                            break
                        if not line:
                            continue
                        data = json.loads(line)
                        if data.get("error"):
                            raise RuntimeError(str(data["error"]))
                        job.detail = str(data.get("status", ""))
                        if data.get("total"):
                            job.total = int(data["total"])
                            job.completed = int(data.get("completed") or 0)
                        now = time.monotonic()
                        if now - last_emit > 0.5:
                            self._emit(job)
                            last_emit = now
            if job.status == "running":
                job.status = "done"
                job.license = self.license(job.name)
        except Exception as exc:
            if job.status == "running":
                job.status, job.detail = "failed", str(exc)[:300]
        self._emit(job)

    # -- after downloading ------------------------------------------------------------
    def show(self, name: str) -> dict[str, Any]:
        with self._client() as client:
            resp = client.post(f"{self.url().rstrip('/')}/api/show",
                               json={"model": name, "name": name})
            resp.raise_for_status()
            return resp.json()

    def license(self, name: str) -> str:
        try:
            text = self.show(name).get("license") or ""
        except Exception:
            return ""
        return text if isinstance(text, str) else "\n".join(map(str, text))
