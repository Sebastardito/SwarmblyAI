"""Lightweight SQLite persistence (stdlib ``sqlite3``).

Stores conversations, messages, request metadata (for the monitor and
reports), node discovery metadata and daily statistics. A single writer lock
keeps concurrent access safe; all operations are synchronous and cheap.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    mode        TEXT NOT NULL DEFAULT 'local',
    model       TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,               -- user | assistant | system
    content         TEXT NOT NULL DEFAULT '',
    created_at      REAL NOT NULL,
    meta            TEXT NOT NULL DEFAULT '{}',  -- JSON: execution metadata
    stages          TEXT NOT NULL DEFAULT '[]'   -- JSON: pipeline stage log
);
CREATE TABLE IF NOT EXISTS requests (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT,
    message_id      TEXT,
    mode            TEXT NOT NULL,
    model           TEXT NOT NULL DEFAULT '',
    started_at      REAL NOT NULL,
    finished_at     REAL,
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending|running|done|failed|stopped
    meta            TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS node_cache (
    node_id      TEXT PRIMARY KEY,
    discovered_at REAL NOT NULL,
    last_seen    REAL,
    verified     INTEGER NOT NULL DEFAULT 0,
    address      TEXT,
    port         INTEGER,
    profile      TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS stats_daily (
    day          TEXT PRIMARY KEY,      -- YYYY-MM-DD (local)
    tasks_served INTEGER NOT NULL DEFAULT 0,
    gen_ms       INTEGER NOT NULL DEFAULT 0,
    tokens_out   INTEGER NOT NULL DEFAULT 0,
    bytes_in     INTEGER NOT NULL DEFAULT 0,
    bytes_out    INTEGER NOT NULL DEFAULT 0,
    tasks_requested INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, created_at);
"""


# Additive migrations (columns added after v0.1.0). Each is idempotent.
_MIGRATIONS = [
    # Served-to-others vs. consumed-locally are separate counters (Swarm
    # Contribution must never mix the two).
    ("stats_daily", "served_ms", "INTEGER NOT NULL DEFAULT 0"),
    ("stats_daily", "served_tokens", "INTEGER NOT NULL DEFAULT 0"),
    ("stats_daily", "dispatched", "INTEGER NOT NULL DEFAULT 0"),
    ("stats_daily", "dispatch_failed", "INTEGER NOT NULL DEFAULT 0"),
    ("stats_daily", "distributed_requests", "INTEGER NOT NULL DEFAULT 0"),
]


class Database:
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            for table, column, decl in _MIGRATIONS:
                cols = {r[1] for r in self._conn.execute(f"PRAGMA table_info({table})")}
                if column not in cols:
                    self._conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- conversations -------------------------------------------------------
    def create_conversation(self, title: str = "", mode: str = "local",
                            model: str = "") -> dict[str, Any]:
        conv_id = uuid.uuid4().hex[:16]
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO conversations(id,title,created_at,updated_at,mode,model)"
                " VALUES(?,?,?,?,?,?)", (conv_id, title, now, now, mode, model))
            self._conn.commit()
        return self.get_conversation(conv_id)  # type: ignore[return-value]

    def get_conversation(self, conv_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM conversations WHERE id=?", (conv_id,)).fetchone()
        return dict(row) if row else None

    def list_conversations(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM conversations ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]

    def update_conversation(self, conv_id: str, **fields: Any) -> None:
        fields = {k: v for k, v in fields.items()
                  if k in ("title", "mode", "model", "updated_at")}
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        with self._lock:
            self._conn.execute(
                f"UPDATE conversations SET {sets} WHERE id=?",
                (*fields.values(), conv_id))
            self._conn.commit()

    def delete_conversation(self, conv_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM conversations WHERE id=?", (conv_id,))
            self._conn.commit()

    def touch_conversation(self, conv_id: str) -> None:
        self.update_conversation(conv_id, updated_at=time.time())

    # -- messages ------------------------------------------------------------
    def add_message(self, conversation_id: str, role: str, content: str = "",
                    meta: dict[str, Any] | None = None,
                    stages: list[dict[str, Any]] | None = None,
                    message_id: str | None = None) -> dict[str, Any]:
        mid = message_id or uuid.uuid4().hex[:16]
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO messages(id,conversation_id,role,content,created_at,meta,stages)"
                " VALUES(?,?,?,?,?,?,?)",
                (mid, conversation_id, role, content, now,
                 json.dumps(meta or {}), json.dumps(stages or [])))
            self._conn.commit()
        return {"id": mid, "conversation_id": conversation_id, "role": role,
                "content": content, "created_at": now, "meta": meta or {},
                "stages": stages or []}

    def update_message(self, message_id: str, content: str | None = None,
                       meta: dict[str, Any] | None = None,
                       stages: list[dict[str, Any]] | None = None) -> None:
        sets: list[str] = []
        values: list[Any] = []
        if content is not None:
            sets.append("content=?")
            values.append(content)
        if meta is not None:
            sets.append("meta=?")
            values.append(json.dumps(meta))
        if stages is not None:
            sets.append("stages=?")
            values.append(json.dumps(stages))
        if not sets:
            return
        values.append(message_id)
        with self._lock:
            self._conn.execute(
                f"UPDATE messages SET {', '.join(sets)} WHERE id=?",
                tuple(values))
            self._conn.commit()

    def get_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at",
                (conversation_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["meta"] = json.loads(d["meta"] or "{}")
            d["stages"] = json.loads(d["stages"] or "[]")
            out.append(d)
        return out

    # -- requests (execution log) ---------------------------------------------
    def add_request(self, request_id: str, conversation_id: str | None,
                    message_id: str | None, mode: str, model: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO requests(id,conversation_id,message_id,mode,model,started_at)"
                " VALUES(?,?,?,?,?,?)",
                (request_id, conversation_id, message_id, mode, model, time.time()))
            self._conn.commit()

    def finish_request(self, request_id: str, status: str,
                       meta: dict[str, Any] | None = None) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE requests SET finished_at=?, status=?, meta=? WHERE id=?",
                (time.time(), status, json.dumps(meta or {}), request_id))
            self._conn.commit()

    def get_request(self, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["meta"] = json.loads(d["meta"] or "{}")
        return d

    # -- node cache (discovery metadata) --------------------------------------
    def upsert_node(self, node_id: str, address: str | None, port: int | None,
                    verified: bool, profile: dict[str, Any] | None = None,
                    last_seen: float | None = None) -> None:
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT discovered_at FROM node_cache WHERE node_id=?", (node_id,)).fetchone()
            if row:
                self._conn.execute(
                    "UPDATE node_cache SET last_seen=?, verified=?, address=?, port=?, profile=?"
                    " WHERE node_id=?",
                    (last_seen or now, int(verified), address, port,
                     json.dumps(profile or {}), node_id))
            else:
                self._conn.execute(
                    "INSERT INTO node_cache(node_id,discovered_at,last_seen,verified,address,port,profile)"
                    " VALUES(?,?,?,?,?,?,?)",
                    (node_id, now, last_seen or now, int(verified), address, port,
                     json.dumps(profile or {})))
            self._conn.commit()

    def list_nodes(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM node_cache").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["profile"] = json.loads(d["profile"] or "{}")
            out.append(d)
        return out

    def prune_nodes(self, max_age_s: float) -> int:
        cutoff = time.time() - max_age_s
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM node_cache WHERE last_seen < ?", (cutoff,))
            self._conn.commit()
            return cur.rowcount

    # -- stats ----------------------------------------------------------------
    def add_stats(self, day: str, **fields: int) -> None:
        cols = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        updates = ", ".join(f"{k}={k}+excluded.{k}" for k in fields)
        with self._lock:
            self._conn.execute(
                f"INSERT INTO stats_daily(day,{cols}) VALUES(?,{placeholders})"
                f" ON CONFLICT(day) DO UPDATE SET {updates}",
                (day, *fields.values()))
            self._conn.commit()

    def get_stats(self, days: int = 30) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM stats_daily ORDER BY day DESC LIMIT ?", (days,)).fetchall()
        return [dict(r) for r in rows]
