#!/usr/bin/env python3
"""Two-node privacy mode: a loopback circle member and a non-member.

The harness starts the App under test as the circle owner, a second App on
loopback as a member (invitation accepted and approved) and a third App that
is **not** a member.  It records the requester's receipt (``CIRCLE`` sends,
circle/member names and passage counts) and the member's own worker ledger
(through the App's WebSocket event bus), and checks that the non-member was
never admitted.

Nothing here contains a path or a host: the caller passes the Python, the App
objects and the work folders.  Standard library only.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


class TwoNodeError(RuntimeError):
    """The loopback circle could not be built."""


# 1.4.4: a slow machine may take longer than 30 s to deliver the join request;
# one retry is allowed before the observation is a technical failure.
JOIN_TIMEOUT = 90.0
CIRCLE_TIMEOUT = 90.0
ORDINARY_TASK_ERROR = "la App no registra tareas ordinarias del miembro"


# --------------------------------------------------------------------------- http
def http_json(method: str, url: str, token: str = "", body: Any = None,
              timeout: float = 30.0) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("X-Swarmbly-Token", token)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else None


def wait_until(predicate: Callable[[], Any], timeout: float = 30.0,
               interval: float = 0.25) -> Any:
    deadline = time.monotonic() + max(0.1, timeout)
    last: Any = None
    while time.monotonic() < deadline:
        try:
            last = predicate()
            if last:
                return last
        except Exception:
            last = None
        time.sleep(interval)
    return last


# --------------------------------------------------------------------------- websocket
class _WebSocket:
    """The small RFC 6455 client needed for the App's ``/ws`` event stream."""

    def __init__(self, host: str, port: int, token: str, timeout: float = 10.0) -> None:
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(1.0)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        path = f"/ws?token={urllib.parse.quote(token)}"
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise TwoNodeError("WebSocket handshake closed")
            response += chunk
        head, _, rest = response.partition(b"\r\n\r\n")
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise TwoNodeError("WebSocket upgrade refused: "
                               + head.split(b"\r\n", 1)[0].decode("latin-1"))
        self._buffer = rest
        self._closed = False

    def _recv_exact(self, count: int) -> bytes:
        while len(self._buffer) < count:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise TwoNodeError("WebSocket closed")
            self._buffer += chunk
        data, self._buffer = self._buffer[:count], self._buffer[count:]
        return data

    def _send(self, opcode: int, payload: bytes = b"") -> None:
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
        header = bytes([0x80 | opcode])
        length = len(payload)
        if length < 126:
            header += bytes([0x80 | length])
        elif length < 65536:
            header += bytes([0x80 | 126]) + length.to_bytes(2, "big")
        else:
            header += bytes([0x80 | 127]) + length.to_bytes(8, "big")
        self.sock.sendall(header + mask + masked)

    def events(self) -> list[dict[str, Any]]:
        """Read the frames available now; a timeout is not an error."""
        out: list[dict[str, Any]] = []
        try:
            while True:
                first, second = self._recv_exact(2)
                opcode = first & 0x0F
                length = second & 0x7F
                if length == 126:
                    length = int.from_bytes(self._recv_exact(2), "big")
                elif length == 127:
                    length = int.from_bytes(self._recv_exact(8), "big")
                masked = bool(second & 0x80)
                mask = self._recv_exact(4) if masked else b""
                payload = self._recv_exact(length)
                if masked:
                    payload = bytes(byte ^ mask[i % 4]
                                    for i, byte in enumerate(payload))
                if opcode == 0x8:          # close
                    self._closed = True
                    return out
                if opcode == 0x9:          # ping
                    self._send(0xA, payload)
                    continue
                if opcode in (0x1, 0x2):
                    try:
                        out.append(json.loads(payload.decode("utf-8")))
                    except (UnicodeDecodeError, ValueError):
                        continue
        except (socket.timeout, TimeoutError):
            return out

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        if not self._closed:
            try:
                self._send(0x8)
            except OSError:
                pass
        self._closed = True
        try:
            self.sock.close()
        except OSError:
            pass


class WorkerLedger:
    """Collect the member's ``worker.egress`` events in a background thread.

    1.4.4: the subscription is ready before the first task, reconnects after a
    dropped WebSocket and records ``ledger_error`` instead of ending silently.
    """

    def __init__(self, app: Any, connect_timeout: float = 10.0) -> None:
        parsed = urllib.parse.urlsplit(app.base)
        self._host = parsed.hostname or "127.0.0.1"
        self._port = int(parsed.port or 80)
        self._token = app.token
        self._ws: _WebSocket | None = None
        self._events: list[dict[str, Any]] = []
        self._tasks: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._error = ""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if not self._ready.wait(max(0.1, float(connect_timeout))):
            self._set_error("no se pudo suscribir al bus del miembro a tiempo")

    def _set_error(self, message: str) -> None:
        text = " ".join(str(message or "").split())[:400]
        if text:
            with self._lock:
                self._error = text

    @property
    def error(self) -> str:
        with self._lock:
            return self._error

    @property
    def ready(self) -> bool:
        return self._ready.is_set()

    def _connect(self) -> None:
        self._ws = _WebSocket(self._host, self._port, self._token)
        self._ready.set()

    def _run(self) -> None:
        delay = 0.2
        while not self._stop.is_set():
            if self._ws is None:
                try:
                    self._connect()
                    delay = 0.2
                except Exception as exc:       # noqa: BLE001 - recorded, retried
                    self._set_error(f"no se pudo suscribir: {type(exc).__name__}: {exc}")
                    if self._stop.wait(delay):
                        break
                    delay = min(delay * 2, 2.0)
                    continue
            try:
                events = self._ws.events()
            except Exception as exc:           # noqa: BLE001 - reconnect, never silent
                self._set_error(f"la suscripción se cortó: {type(exc).__name__}: {exc}")
                try:
                    self._ws.close()
                except Exception:
                    pass
                self._ws = None
                if self._stop.wait(0.2):
                    break
                continue
            if self._ws is not None and self._ws.closed:
                try:
                    self._ws.close()
                except Exception:
                    pass
                self._ws = None
                continue
            for event in events:
                if not isinstance(event, dict):
                    continue
                kind = str(event.get("type") or "")
                payload = event.get("payload") or {}
                if kind == "worker.egress":
                    entries = payload.get("events") if isinstance(payload, dict) else None
                    if not isinstance(entries, list):
                        self._set_error("worker.egress sin lista de eventos")
                        continue
                    with self._lock:
                        self._events.extend(dict(item) for item in entries
                                            if isinstance(item, dict))
                elif kind in ("worker.task_served", "worker.executor_served"):
                    # The ordinary-task evidence the App actually publishes:
                    # model, time and tokens (no attempt id, role, circle or
                    # requester).  Keep it as an event, never as a fake peer
                    # ledger row.
                    row = {"tipo": kind, "evento_id": str(event.get("id") or ""),
                           "ts": event.get("ts")}
                    if isinstance(payload, dict):
                        row.update(payload)
                    with self._lock:
                        self._tasks.append(row)
            time.sleep(0.05)

    def drain(self) -> list[dict[str, Any]]:
        with self._lock:
            out, self._events = self._events, []
        return out

    def drain_tasks(self) -> list[dict[str, Any]]:
        with self._lock:
            out, self._tasks = self._tasks, []
        return out

    def close(self) -> None:
        self._stop.set()
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None
        self._thread.join(timeout=3)


# --------------------------------------------------------------------------- env
def _normalise_endpoint(port: int) -> list[str]:
    return [f"127.0.0.1:{int(port)}"]


def member_settings(*, model: str, embed_model: str, ollama_url: str,
                    p2p_port: int, temperature: float,
                    language: str = "es") -> dict[str, Any]:
    return {
        "setup_completed": True, "language": language,
        "model.backend": "ollama", "model.backend_url": ollama_url,
        "model.model_name": model, "model.embed_model": embed_model,
        "model.embedder": "hash",
        "model.temperature": temperature,
        "privacy.tier": "GLOBAL",
        "lce.enabled": True, "lce.level": "C1", "lce.sources_dirs": [],
        "evidence.providers": [], "evidence.searxng_url": "",
        "swarm.mode": "lan", "swarm.lan_enabled": True,
        "swarm.worker_enabled": True, "swarm.worker_allow_lan": True,
        "swarm.worker_models": [model], "swarm.p2p_port": p2p_port,
        "circle.admission_mode": "circle",
        "node_roles.large_model_min_b": 1.0,
        "node_roles.reasoner_models": [model],
    }


class TwoNodeEnv:
    """Owner (already started) + one or more members + one non-member."""

    def __init__(self, *, owner: Any, python: str, work_root: Path,
                 proxy_url: str, model: str, embed_model: str,
                 ollama_url: str, temperature: float, log_dir: Path,
                 app_factory: Callable[..., Any] | None = None,
                 language: str = "es", tag: str = "") -> None:
        self.owner, self.python = owner, python
        self.root = Path(work_root)
        self.proxy_url, self.model = proxy_url, model
        self.embed_model, self.ollama_url = embed_model, ollama_url
        self.temperature, self.log_dir = temperature, Path(log_dir)
        self.language = language
        # One log per observation: <case>_r<rep>_member-<n>.log instead of a
        # single member-1.log overwritten by every repetition (1.4.4).
        self.tag = str(tag or "")
        if app_factory is None:
            import run_bank as rb          # runtime import avoids a circular import
            app_factory = rb.AppInstance
        self.app_factory = app_factory
        self.members: list[Any] = []
        self.nonmember: Any = None
        self.circle_id = ""
        self.circle_name = ""
        self.owner_p2p = int((owner.settings.get("swarm.p2p_port")))
        self.circle_passages = False
        self._ledgers: list[WorkerLedger] = []
        self._member_rows: list[dict[str, Any]] = []
        self._task_rows: list[dict[str, Any]] = []
        self._member_stats_before: list[dict[str, Any]] = []
        self._member_stats_after: list[dict[str, Any]] = []
        self.ledger_errors: list[str] = []
        self.join_attempts: list[dict[str, Any]] = []
        self.nonmember_refused = False

    def _new_app(self, name: str, settings: dict[str, Any], *,
                 sources: Path | None = None) -> Any:
        base = self.root / name
        base.mkdir(parents=True, exist_ok=True)
        source_dir = sources or (base / "sources")
        source_dir.mkdir(parents=True, exist_ok=True)
        prefix = f"{self.tag}_" if self.tag else ""
        app = self.app_factory(
            self.python, base / "datos", source_dir, settings, self.proxy_url,
            self.log_dir / f"{prefix}{name}.log")
        app.start()
        return app

    def start(self, *, members: int = 1, nonmember: bool = True,
              corpus_doc: Path | None = None,
              member_extra: dict[str, Any] | None = None) -> "TwoNodeEnv":
        for index in range(1, max(0, int(members)) + 1):
            settings = member_settings(
                model=self.model, embed_model=self.embed_model,
                ollama_url=self.ollama_url, p2p_port=self._free_port(),
                temperature=self.temperature, language=self.language)
            if member_extra:
                settings.update(member_extra)
            self.members.append(self._new_app(f"member-{index}", settings))
        if nonmember:
            settings = member_settings(
                model=self.model, embed_model=self.embed_model,
                ollama_url=self.ollama_url, p2p_port=self._free_port(),
                temperature=self.temperature, language=self.language)
            settings.update({"swarm.worker_enabled": False,
                             "swarm.worker_models": []})
            self.nonmember = self._new_app("nonmember", settings)
        if self.members:
            # The App's only aggregate for served tasks is /api/monitor; take a
            # baseline before the first task (metadata only).
            self._member_stats_before = [self._contribution(member)
                                         for member in self.members]
            # Subscribe before the circle is built, so no member event can be
            # published before the WebSocket client exists.
            for member in self.members:
                ledger = WorkerLedger(member)
                self._ledgers.append(ledger)
                if not ledger.ready:
                    self.ledger_errors.append(ledger.error or "suscripción no lista")
            self._create_circle(corpus_doc=corpus_doc)
            if self.nonmember is not None:
                self._check_nonmember()
        return self

    @staticmethod
    def _free_port() -> int:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    def _create_circle(self, *, corpus_doc: Path | None) -> None:
        owner = self.owner
        manifest = http_json("POST", f"{owner.base}/api/circles", owner.token,
                             {"name": "Loopback circle"})
        self.circle_id = str(manifest.get("circle_id") or "")
        self.circle_name = str(manifest.get("name") or "")
        for member in self.members:
            payload = self._join_member(member)
            node_id = str(payload["pending_joins"][0].get("node_id") or "")
            http_json("POST",
                      f"{owner.base}/api/circles/{self.circle_id}/requests/"
                      f"{urllib.parse.quote(node_id)}/approve",
                      owner.token, {"name": "Loopback member"})
        def both_members() -> bool:
            for app in [owner, *self.members]:
                payload = http_json("GET", f"{app.base}/api/circles", app.token)
                found = [c for c in payload.get("circles") or []
                         if c.get("circle_id") == self.circle_id]
                if not found or len(found[0].get("members") or []) != 1 + len(self.members):
                    return False
            return True
        if not wait_until(both_members, timeout=CIRCLE_TIMEOUT):
            raise TwoNodeError("the circle did not list every loopback member")
        wait_until(lambda: (http_json("GET", f"{owner.base}/api/swarm",
                                      owner.token).get("admitted_count") or 0) >= 1,
                   timeout=20)
        if corpus_doc is not None:
            self._share_corpus(self.members[0], Path(corpus_doc))
        for member in self.members:
            wait_until(lambda m=member: any(
                role.get("role") == "large_model"
                for role in (http_json("GET", f"{m.base}/api/swarm", m.token)
                             .get("roles") or [])), timeout=20)

    def _pending_join(self) -> dict[str, Any] | None:
        owner = self.owner
        return next((circle for circle in
                     (http_json("GET", f"{owner.base}/api/circles",
                                owner.token).get("circles") or [])
                     if circle.get("circle_id") == self.circle_id
                     and circle.get("pending_joins")), None)

    def _join_member(self, member: Any) -> dict[str, Any]:
        """Ask the owner to admit one member, retrying the join once (1.4.4)."""
        owner = self.owner
        payload: dict[str, Any] | None = None
        attempts: list[dict[str, Any]] = []
        for attempt in (1, 2):
            if attempt > 1:
                # The first request may have arrived just after its deadline.
                payload = wait_until(self._pending_join, timeout=JOIN_TIMEOUT)
                if payload:
                    break
            invitation = http_json(
                "POST", f"{owner.base}/api/circles/{self.circle_id}/invite",
                owner.token, {"endpoints": _normalise_endpoint(self.owner_p2p)})
            code = str(invitation.get("code") or "")
            member_p2p = int(member.settings.get("swarm.p2p_port"))
            http_json("POST", f"{member.base}/api/circles/accept", member.token,
                      {"code": code, "name": "Loopback member",
                       "endpoints": _normalise_endpoint(member_p2p)})
            payload = wait_until(self._pending_join, timeout=JOIN_TIMEOUT)
            attempts.append({"intento": attempt, "recibido": bool(payload)})
            if payload:
                break
        self.join_attempts.extend(attempts)
        if not payload:
            raise TwoNodeError(
                "the owner did not receive the join request after two attempts")
        return payload

    def _share_corpus(self, member: Any, document: Path) -> None:
        project = http_json("POST", f"{member.base}/api/projects", member.token,
                            {"name": "Member notes", "parent": str(self.root / "projects"),
                             "activate": True})
        sources = Path(str(project.get("path"))) / "sources"
        sources.mkdir(parents=True, exist_ok=True)
        (sources / document.name).write_text(
            document.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        http_json("PUT", f"{member.base}/api/config", member.token, {
            "node_roles.corpus.project_id": project.get("id"),
            "node_roles.corpus.circle_ids": [self.circle_id],
            "node_roles.corpus.display_name": "Member notes",
        })
        wait_until(lambda: any(role.get("role") == "corpus"
                               for role in (http_json("GET", f"{member.base}/api/swarm",
                                                       member.token).get("roles") or [])),
                   timeout=20)

    def _check_nonmember(self) -> None:
        owner, outsider = self.owner, self.nonmember
        node_id = str(http_json("GET", f"{outsider.base}/api/circles",
                                outsider.token).get("node_id") or "")
        try:
            http_json("POST", f"{outsider.base}/api/swarm/connect", outsider.token,
                      {"host": "127.0.0.1", "port": self.owner_p2p})
        except Exception:
            pass
        time.sleep(1.5)
        owner_peers = http_json("GET", f"{owner.base}/api/swarm", owner.token).get("peers") or []
        admitted = [peer for peer in owner_peers
                    if str(peer.get("node_id") or "").startswith(node_id[:12])
                    and peer.get("admitted")]
        outsider_view = http_json("GET", f"{outsider.base}/api/swarm", outsider.token)
        self.nonmember_refused = (not admitted
                                  and int(outsider_view.get("admitted_count") or 0) == 0)

    def set_circle_passages(self, enabled: bool) -> None:
        http_json("POST",
                  f"{self.owner.base}/api/circles/{self.circle_id}/passages",
                  self.owner.token, {"enabled": bool(enabled)})
        self.circle_passages = bool(enabled)

    def create_team(self, name: str, steps: list[dict[str, Any]]) -> str:
        team = http_json("POST", f"{self.owner.base}/api/teams", self.owner.token,
                         {"name": name, "steps": steps})
        return str(team.get("id") or "")

    def ask_team(self, text: str, team_id: str, timeout: float = 120.0) -> dict[str, Any]:
        owner = self.owner
        conversation = http_json("POST", f"{owner.base}/api/conversations",
                                 owner.token, {})
        started = time.monotonic()
        sent = http_json("POST",
                         f"{owner.base}/api/conversations/{conversation['id']}/messages",
                         owner.token, {"text": text, "team_id": team_id})
        message_id = sent["assistant_message"]["id"]
        message = None
        while time.monotonic() - started < timeout:
            time.sleep(0.5)
            for item in http_json("GET",
                                  f"{owner.base}/api/conversations/{conversation['id']}/messages",
                                  owner.token):
                if item.get("id") == message_id and \
                        (item.get("meta") or {}).get("status") not in (None, "running"):
                    message = item
            if message is not None:
                break
        return {"message": message, "latency_s": round(time.monotonic() - started, 2),
                "timeout": message is None}

    @staticmethod
    def _contribution(member: Any) -> dict[str, Any]:
        """The member's measured contribution counters (no task content)."""
        try:
            payload = http_json("GET", f"{member.base}/api/monitor",
                                member.token, timeout=10)
        except Exception as exc:           # noqa: BLE001 - reported, not hidden
            return {"error": f"{type(exc).__name__}: {exc}"[:300]}
        contribution = ((payload or {}).get("contribution")
                        if isinstance(payload, dict) else {})
        contribution = contribution if isinstance(contribution, dict) else {}
        transferred = (contribution.get("bytes_transferred")
                       if isinstance(contribution.get("bytes_transferred"), dict)
                       else {})

        def _int(value: Any) -> int:
            try:
                return int(value or 0)
            except (TypeError, ValueError):
                return 0
        return {
            "tasks_served": _int(contribution.get("tasks_served")),
            "processing_time_ms": _int(contribution.get("processing_time_ms")),
            "tokens_generated": _int(contribution.get("tokens_generated")),
            "bytes_in": _int(transferred.get("in")),
            "bytes_out": _int(transferred.get("out")),
        }

    @staticmethod
    def _stats_delta(before: list[dict[str, Any]],
                     after: list[dict[str, Any]]) -> dict[str, int]:
        keys = ("tasks_served", "processing_time_ms", "tokens_generated",
                "bytes_in", "bytes_out")
        delta: dict[str, int] = {}
        for key in keys:
            total = 0
            for left, right in zip(before, after):
                if "error" in left or "error" in right:
                    continue
                total += max(0, int(right.get(key) or 0) - int(left.get(key) or 0))
            delta[key] = total
        return delta

    def _drain_ledgers(self) -> int:
        fresh = 0
        for ledger in self._ledgers:
            rows = ledger.drain()
            fresh += len(rows)
            self._member_rows.extend(rows)
            self._task_rows.extend(ledger.drain_tasks())
            if ledger.error and ledger.error not in self.ledger_errors:
                self.ledger_errors.append(ledger.error)
        return fresh

    @property
    def ledger_error(self) -> str:
        errors = list(self.ledger_errors)
        for ledger in self._ledgers:
            if ledger.error and ledger.error not in errors:
                errors.append(ledger.error)
        return " · ".join(errors)

    def member_ledger(self, wait: float = 0.8) -> list[dict[str, Any]]:
        """Drain the member's worker ledger, allowing the event bus to deliver.

        The executor publishes ``worker.egress`` just before it replies; the
        WebSocket bridge is asynchronous, so wait for a short quiet period
        instead of assuming the event is already in the client.  Rows are kept
        after the first drain and after ``close``: the observations read this
        evidence once the task has ended.
        """
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline:
            fresh = self._drain_ledgers()
            if fresh:
                time.sleep(max(0.0, wait))
                continue
            if self._member_rows:
                break
            time.sleep(0.1)
        self._drain_ledgers()
        return list(self._member_rows)

    def member_tasks(self, wait: float = 0.0) -> dict[str, Any]:
        """What the member App records for the tasks it served (metadata only).

        The App publishes ``worker.task_served`` with the model, generation
        time and tokens, and keeps daily aggregate counters (served tasks,
        time, tokens, bytes in/out) behind ``/api/monitor``.  It records no
        attempt/task id, role, circle id, requester id or passage count for an
        ordinary large_model/reasoner/list task, and does not put those tasks
        in the executor egress ledger.  This method returns the evidence that
        does exist and a precise ``ledger_error``; it never fabricates rows.
        """
        if wait:
            time.sleep(max(0.0, float(wait)))
        self._drain_ledgers()
        after = self._member_stats_after or [
            self._contribution(member) for member in self.members]
        before = self._member_stats_before or []
        events = list(self._task_rows)
        ordinary = [event for event in events
                    if str(event.get("tipo")) == "worker.task_served"]
        executor = [event for event in events
                    if str(event.get("tipo")) == "worker.executor_served"]
        delta = self._stats_delta(before, after)
        note = ""
        if ordinary or delta.get("tasks_served", 0) > len(executor):
            note = ORDINARY_TASK_ERROR
        return {
            "eventos": events,
            "eventos_ordinarios": len(ordinary),
            "eventos_executor": len(executor),
            "antes": before,
            "despues": after,
            "delta": delta,
            "registro": ("worker.task_served (modelo, ms, tokens) y los "
                         "contadores diarios de /api/monitor (tareas, tiempo, "
                         "tokens, bytes); sin id de tarea, rol, círculo, "
                         "solicitante ni pasajes"),
            "ids_de_tarea": False,
            "roles": False,
            "circle_id": False,
            "requester_id": False,
            "ledger_error": note,
        }

    def close(self) -> None:
        for ledger in self._ledgers:
            ledger.close()
            self._member_rows.extend(ledger.drain())
            self._task_rows.extend(ledger.drain_tasks())
            if ledger.error and ledger.error not in self.ledger_errors:
                self.ledger_errors.append(ledger.error)
        if not self._member_stats_after:
            self._member_stats_after = [self._contribution(member)
                                        for member in self.members]
        self._ledgers.clear()
        for app in [*self.members, self.nonmember]:
            if app is not None:
                try:
                    app.stop()
                except Exception:
                    pass
        self.members.clear()
        self.nonmember = None


# --------------------------------------------------------------------------- report
def _send_class(value: Any) -> str:
    text = str(value or "").strip().lower()
    return "CIRCLE" if text in ("circulo", "círculo", "circle") else text.upper()


def circle_send_rows(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    """The receipt rows that went to a circle peer, with the D-017 fields."""
    rows: list[dict[str, Any]] = []
    for entry in receipt.get("envios") or []:
        if not isinstance(entry, dict) or _send_class(entry.get("clase")) != "CIRCLE":
            continue
        rows.append({
            "destino": entry.get("destino", ""),
            "clase": "CIRCLE",
            "circle_id": entry.get("circle_id", ""),
            "circle_name": entry.get("circle_name", ""),
            "member_name": entry.get("member_name", ""),
            "tipo": entry.get("tipo", ""),
            "passages": int(entry.get("passages") or entry.get("pasajes") or 0),
            "bytes": int(entry.get("bytes") or 0),
            "transport": entry.get("transport", "direct"),
        })
    return rows


def member_ledger_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalise the member's worker ledger to the same metadata fields.

    1.4.4: the real shape is an egress event such as ``{"destino": "nodo …",
    "clase": "circulo", "circle_id": …, "member_name": …, "passages": …}``.
    Events the member made on behalf of a peer (a public search included) are
    kept even when their class is not ``CIRCLE``; a local tool call without a
    circle is not a peer row.
    """
    rows: list[dict[str, Any]] = []
    for entry in events:
        if not isinstance(entry, dict):
            continue
        circle = entry.get("circle") if isinstance(entry.get("circle"), dict) else {}
        circle_id = str(entry.get("circle_id") or circle.get("circle_id")
                        or circle.get("id") or "")
        circle_name = str(entry.get("circle_name") or circle.get("name") or "")
        member_name = str(entry.get("member_name") or entry.get("member")
                          or entry.get("on_behalf") or "")
        destino = str(entry.get("destino") or entry.get("destination") or "")
        on_behalf = str(entry.get("on_behalf") or "")
        clase = _send_class(entry.get("clase") or entry.get("class") or "")
        if not (circle_id or destino or on_behalf):
            continue
        if not circle_id and not on_behalf \
                and clase not in ("CIRCLE", "LOCAL", "RED_PROPIA", ""):
            continue
        rows.append({
            "destino": destino,
            "clase": clase,
            "circle_id": circle_id,
            "circle_name": circle_name,
            "member_name": member_name,
            "tipo": str(entry.get("tipo") or ""),
            "passages": int(entry.get("passages") or entry.get("pasajes") or 0),
            "bytes": int(entry.get("bytes") or 0),
            "executor": str(entry.get("executor") or ""),
            "on_behalf": on_behalf,
        })
    return rows


def two_node_report(receipt: dict[str, Any], member_events: list[dict[str, Any]],
                    *, nonmember_refused: bool,
                    circle_passages: bool,
                    expected_passages: bool | None = None,
                    ledger_error: str = "",
                    member_tasks: dict[str, Any] | None = None) -> dict[str, Any]:
    """The new report fields and the three v5 rules for one observation."""
    sends = circle_send_rows(receipt)
    ledger = member_ledger_rows(member_events)
    task_evidence = member_tasks if isinstance(member_tasks, dict) else {}
    task_error = str(task_evidence.get("ledger_error") or "")
    if not task_error and int(task_evidence.get("eventos_ordinarios") or 0) > 0:
        task_error = ORDINARY_TASK_ERROR
    errors = [value for value in (ledger_error, task_error) if value]
    ledger_error = " · ".join(dict.fromkeys(errors))
    member_passages = sum(row["passages"] for row in ledger)
    passages = max(sum(row["passages"] for row in sends), member_passages)
    # 1.4.4: with no CIRCLE send this rule does not apply (None), it is not a
    # failure.  With one or more, every row must name circle id, name and member.
    if not sends:
        names_ok: bool | None = None
    else:
        names_ok = all(
            row["circle_id"] and row["circle_name"] and row["member_name"]
            for row in sends)
    # D-017: no passage may reach a peer unless the circle switch is on.  With
    # the switch on, passages are allowed but not required (a route may have no
    # documents); a card can still expect them through `expected_passages`.
    only_with_permission = (passages == 0) if not circle_passages else True
    if expected_passages is True:
        only_with_permission = only_with_permission and passages > 0
    elif expected_passages is False:
        only_with_permission = only_with_permission and passages == 0
    rules = {
        "pasajes_solo_con_permiso": bool(only_with_permission),
        "no_miembro_rechazado": bool(nonmember_refused),
        "recibo_nombra_circulo_y_miembro": names_ok,
    }
    return {
        "envios_circulo": len(sends),
        "envios_circulo_detalle": sends,
        "pasajes_a_pares": passages,
        "pasajes_ledger_miembro": member_passages,
        "miembro_ledger": ledger,
        "miembro_tareas": task_evidence,
        "ledger_error": str(ledger_error or ""),
        "no_miembro_rechazado": bool(nonmember_refused),
        "two_node_rules": rules,
    }


def two_node_check(case_checks: list[str], report: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate the three v5 check phrases if a card uses them."""
    rules = report.get("two_node_rules") or {}
    out: list[dict[str, Any]] = []
    for text in case_checks:
        low = str(text or "").lower()
        verdict = None
        reason = ""
        if "circle_passages" in low and ("pasaje" in low or "passage" in low):
            verdict = bool(rules.get("pasajes_solo_con_permiso"))
            reason = ("sin pasajes a pares con el interruptor apagado"
                      if verdict else "hubo pasajes a pares con el interruptor apagado")
        elif "no miembro" in low or "non-member" in low or "nonmember" in low:
            verdict = bool(rules.get("no_miembro_rechazado"))
            reason = "el no miembro no fue admitido" if verdict else "el no miembro fue admitido"
        elif ("recibo" in low and ("círculo" in low or "circulo" in low)
              and "miembro" in low) or \
                ("receipt" in low and "circle" in low and "member" in low):
            value = rules.get("recibo_nombra_circulo_y_miembro")
            if value is None:
                out.append({"texto": text, "cumple": None,
                            "motivo": "no aplica: no hubo envíos al círculo"})
                continue
            verdict = bool(value)
            reason = ("el recibo nombra círculo y miembro" if verdict
                      else "el recibo no nombra círculo y miembro")
        if verdict is not None:
            out.append({"texto": text, "cumple": verdict, "motivo": reason})
    return out
