"""MCP client core: approved local and remote servers through the tool broker.

Nothing here starts at import or at application launch. A local server process
is spawned only when the caller explicitly asks :class:`MCPClient` to
``start`` it, with the exact command, arguments, working directory and an
explicit environment allowlist that the user approved. A remote server is
always a third party: connecting calls ``egress.check_call`` with
``TOOL_REMOTE`` and needs its host in ``privacy.tool_hosts``.

Permissions are enforced at the tool level (D-008). The client lists every
tool with pagination, hashes the canonical manifest of names, descriptions and
input schemas, and lets the user approve a subset. Only that subset becomes a
``ToolSpec`` in the broker (id ``mcp:<server>/<tool>``), with arguments checked
against the broker's strict schema on every call. If the live manifest changes
on reconnect, or a ``tools/list_changed`` notification arrives and the hash no
longer matches, the server is suspended, its specs are unregistered and the
next call fails until the user approves the new manifest.

Calls go through ``broker.invoke`` only. Text content is concatenated,
structured content is kept as data, ``isError`` becomes ``ToolResult.ok=False``
and images, audio and resources are reported as ``omitted: <type>`` because
3.4 does not pass them to the model. Tool descriptions and results are
untrusted data.

A local MCP server runs with the user's own rights. This module does not
sandbox it; the app must state that plainly.

The MCP SDK is optional (``pip install 'swarmbly-app[tools]'``); it is imported
lazily so the app works without it.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import contextvars
import copy
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

from .. import egress, test_hosts
from .broker import ToolBroker, ToolCall, ToolDenied, ToolResult, ToolSpec
from .mcp_registry import (MCPApprovalError, MCPError, MCPNotRunning,
                           MCPProtocolError, MCPTimeout, MCPUnavailable,
                           ServerConfig, ServerRegistry)
from .schema import SchemaError, canonical_json, sha256_canonical, validate_schema

DEFAULT_INIT_TIMEOUT = 15.0
DEFAULT_LIST_TIMEOUT = 15.0
DEFAULT_CALL_TIMEOUT = 30.0
MAX_MANIFEST_PAGES = 1000
# Conservative passages guard: a remote MCP argument payload this long, or one
# containing an 8-word shingle of the retrieved passages, is treated as
# carrying user documents and needs privacy.third_party_passages.
PASSAGE_ARG_CHARS = 1200
PASSAGE_SHINGLE_WORDS = 8

# Presentation-only JSON Schema annotations produced by real SDK servers
# (including Pydantic's title fields). They do not constrain a value, so the
# broker's strict schema can ignore them. Validation keywords such as pattern,
# oneOf or $ref are still refused.
_ANNOTATION_KEYWORDS = frozenset({
    "title", "description", "$schema", "$id", "$comment", "examples",
    "default", "deprecated", "readOnly", "writeOnly",
})
_TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

_passages: contextvars.ContextVar[tuple[str, ...]] = contextvars.ContextVar(
    "swarmbly_mcp_passages", default=())
_sdk_cache: dict[str, Any] | None = None


@contextlib.contextmanager
def passages(texts: Iterable[str]) -> Iterator[None]:
    """Mark retrieved/user text for the remote-tool shingle guard.

    The agent adapter enters this context with the tool observations the model
    has already seen, so a passage returned by one tool cannot be forwarded to
    a remote MCP tool unless ``privacy.third_party_passages`` is on.
    """
    token = _passages.set(tuple(str(text) for text in texts if text is not None))
    try:
        yield
    finally:
        _passages.reset(token)


def _sdk() -> dict[str, Any]:
    """Import the optional SDK once, with a clear error when it is absent."""
    global _sdk_cache
    if _sdk_cache is not None:
        return _sdk_cache
    try:
        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client
        from mcp.client.streamable_http import streamable_http_client
        from mcp_types import PaginatedRequestParams, ToolListChangedNotification
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise MCPUnavailable(
            "the MCP client needs the optional MCP SDK; install it with "
            "pip install 'swarmbly-app[tools]'"
        ) from exc
    _sdk_cache = {
        "ClientSession": ClientSession,
        "StdioServerParameters": StdioServerParameters,
        "stdio_client": stdio_client,
        "streamable_http_client": streamable_http_client,
        "PaginatedRequestParams": PaginatedRequestParams,
        "ToolListChangedNotification": ToolListChangedNotification,
    }
    return _sdk_cache


@dataclass(frozen=True)
class ManifestTool:
    """One tool exactly as the server declared it (untrusted data)."""

    name: str
    description: str
    input_schema: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description,
                "input_schema": copy.deepcopy(self.input_schema)}


@dataclass(frozen=True)
class ToolManifest:
    """The canonical manifest whose hash the user approves."""

    server_id: str
    tools: tuple[ManifestTool, ...]
    hash: str

    @property
    def manifest_hash(self) -> str:
        return self.hash

    def tool(self, name: str) -> ManifestTool | None:
        for item in self.tools:
            if item.name == name:
                return item
        return None

    def to_dict(self) -> dict[str, Any]:
        return {"server_id": self.server_id, "manifest_hash": self.hash,
                "tools": [item.to_dict() for item in self.tools]}

    def __getitem__(self, key: str) -> Any:
        if key in {"server_id", "manifest_hash", "hash", "tools"}:
            return self.to_dict()[key if key != "hash" else "manifest_hash"]
        raise KeyError(key)


@dataclass
class _Runtime:
    key: tuple[str, str]
    config: ServerConfig
    stack: contextlib.AsyncExitStack
    session: Any
    manifest: ToolManifest | None = None
    refresh_task: Any = None
    stale: bool = False


def _approval_schema(schema: Any) -> dict[str, Any]:
    """Remove presentation-only annotations before the broker's strict check."""
    if not isinstance(schema, dict):
        raise MCPApprovalError("input schema must be a JSON object")
    out = {key: value for key, value in schema.items() if key not in _ANNOTATION_KEYWORDS}
    properties = out.get("properties")
    if isinstance(properties, dict):
        out["properties"] = {
            name: _approval_schema(item) for name, item in properties.items()
        }
    items = out.get("items")
    if isinstance(items, dict):
        out["items"] = _approval_schema(items)
    return out


def _tool_spec_id(server_id: str, tool_name: str) -> str:
    if not isinstance(tool_name, str) or not _TOOL_NAME_RE.fullmatch(tool_name):
        raise MCPApprovalError(
            f"tool name {tool_name!r} cannot be represented as mcp:{server_id}/<tool>"
        )
    return f"mcp:{server_id}/{tool_name}"


def _texts(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _texts(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _texts(item)


def _has_passage_shingle(arguments: dict[str, Any], passages: Iterable[str]) -> bool:
    shingles: set[str] = set()
    for text in passages:
        words = str(text).lower().split()
        shingles |= {" ".join(words[i:i + PASSAGE_SHINGLE_WORDS])
                     for i in range(max(0, len(words) - PASSAGE_SHINGLE_WORDS + 1))}
    if not shingles:
        return False
    for text in _texts(arguments):
        folded = " ".join(text.lower().split())
        if any(shingle in folded for shingle in shingles):
            return True
    return False


class MCPClient:
    """Optional MCP SDK sessions, manifests and broker registration."""

    def __init__(self, broker: ToolBroker, registry: ServerRegistry | None = None,
                 *, data_root: str | Path | None = None,
                 project_path: Any = None,
                 init_timeout: float = DEFAULT_INIT_TIMEOUT,
                 list_timeout: float = DEFAULT_LIST_TIMEOUT,
                 call_timeout: float = DEFAULT_CALL_TIMEOUT):
        if not isinstance(broker, ToolBroker):
            raise TypeError("broker must be a ToolBroker")
        if registry is None:
            root = data_root if data_root is not None else broker.approvals.data_root
            resolver = project_path
            if resolver is None:
                resolver = getattr(broker.approvals, "_project_path", None)
            registry = ServerRegistry(root, project_path=resolver)
        self.broker = broker
        self.registry = registry
        self.init_timeout = float(init_timeout)
        self.list_timeout = float(list_timeout)
        self.call_timeout = float(call_timeout)
        self._runtimes: dict[tuple[str, str], _Runtime] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._tasks: set[Any] = set()

    # -- configured servers -------------------------------------------------
    def servers(self, project_id: str = "") -> list[ServerConfig]:
        return self.registry.servers(project_id)

    def server(self, server_id: str, project_id: str = "") -> ServerConfig:
        return self.registry.require(server_id, project_id)

    def add_server(self, config: ServerConfig, project_id: str = "") -> ServerConfig:
        """Create or replace a configuration. A running server of that id stops."""
        if self.is_running(config.id, project_id):
            self.stop(config.id, project_id)
        return self.registry.put(config, project_id)

    def remove_server(self, server_id: str, project_id: str = "") -> bool:
        if self.is_running(server_id, project_id):
            self.stop(server_id, project_id)
        return self.registry.remove(server_id, project_id)

    def status(self, server_id: str, project_id: str = "") -> str:
        return self.server(server_id, project_id).status

    def describe(self, server_id: str, project_id: str = "") -> dict[str, Any]:
        return self.server(server_id, project_id).describe()

    def is_running(self, server_id: str, project_id: str = "") -> bool:
        with self._lock:
            return (str(project_id), str(server_id)) in self._runtimes

    def running(self) -> list[str]:
        with self._lock:
            return sorted(server_id for _, server_id in self._runtimes)

    def passages(self, texts: Iterable[str]) -> Iterator[None]:
        """Mark the retrieved passages of the current request for the guard."""
        return passages(texts)

    # -- lifecycle ----------------------------------------------------------
    def start(self, server_id: str, project_id: str = "") -> ServerConfig:
        """Explicitly spawn/connect one server and check its live manifest.

        This is the only entry point that starts a local process. It never
        starts anything by itself and never approves a tool.
        """
        config = self.registry.require(server_id, project_id)
        key = (str(project_id), str(server_id))
        with self._lock:
            if key in self._runtimes:
                return self._runtimes[key].config
            for other_project, other_server in self._runtimes:
                if other_server == server_id and other_project != key[0]:
                    raise MCPError(
                        f"MCP server {server_id!r} is already running for another "
                        "project; tool ids are global, so stop it first")
        config = self._run(self._start_async(config, project_id),
                           timeout=self.init_timeout + self.list_timeout + 5.0)
        with self._lock:
            runtime = self._runtimes.get(key)
            if runtime is not None:
                runtime.config = config
        return config

    async def _start_async(self, config: ServerConfig, project_id: str) -> ServerConfig:
        if config.kind == "local_stdio" and config.cwd and not Path(config.cwd).is_dir():
            raise MCPError(f"working directory does not exist: {config.cwd}")
        if config.kind == "remote_http":
            # Before a single byte is sent to the endpoint.
            egress.check_call(
                config.url, 0, reason=f"MCP server {config.id}",
                kind=egress.TOOL_REMOTE, spec_id=f"mcp:{config.id}", aprobado_por="",
            )
        runtime = await self._connect_async(config, project_id)
        key = (str(project_id), str(config.id))
        try:
            manifest = await self._list_manifest_async(runtime.session, config.id)
            runtime.manifest = manifest
            with self._lock:
                self._runtimes[key] = runtime
            if config.approved_manifest_hash and config.status in ("approved", "suspended"):
                if manifest.hash != config.approved_manifest_hash:
                    self._suspend(
                        config,
                        "the live tools/list manifest changed (hash "
                        f"{manifest.hash[:12]}… != approved {config.approved_manifest_hash[:12]}…); "
                        "approve the server again",
                        project_id, runtime,
                    )
                    return config
                if config.status == "approved":
                    self._register_approved(config, runtime, project_id)
                return config
            if config.status != "unapproved" or config.approved_manifest_hash:
                config.status = "unapproved"
                config.approved_manifest_hash = ""
                config.approved_tools = ()
                config.suspension_reason = "no approved manifest; call propose and approve"
                config = self.registry.put(config, project_id)
            return config
        except Exception:
            with self._lock:
                self._runtimes.pop(key, None)
            await runtime.stack.aclose()
            raise

    async def _connect_async(self, config: ServerConfig, project_id: str) -> _Runtime:
        sdk = _sdk()
        stack = contextlib.AsyncExitStack()
        try:
            await stack.__aenter__()
            handler = self._message_handler(config.id, project_id)
            if config.kind == "local_stdio":
                parameters = sdk["StdioServerParameters"](
                    command=config.command,
                    args=list(config.args),
                    env=self._environment(config),
                    cwd=config.cwd or None,
                )
                read_stream, write_stream = await stack.enter_async_context(
                    sdk["stdio_client"](parameters))
            else:
                # D-013: an active test host map redirects only the TCP
                # connection; config.url (and every receipt/policy decision)
                # stays the declared host.
                http_client = None
                if test_hosts.active():
                    http_client = test_hosts.httpx2_async_client()
                    await stack.enter_async_context(http_client)
                read_stream, write_stream = await stack.enter_async_context(
                    sdk["streamable_http_client"](config.url, http_client=http_client))
            session = await stack.enter_async_context(
                sdk["ClientSession"](
                    read_stream, write_stream,
                    read_timeout_seconds=self.call_timeout,
                    message_handler=handler,
                ))
            try:
                await asyncio.wait_for(session.initialize(), timeout=self.init_timeout)
            except TimeoutError:
                raise MCPTimeout(
                    f"MCP server {config.id!r} did not initialize within "
                    f"{self.init_timeout:g}s") from None
            return _Runtime(
                key=(str(project_id), config.id), config=config,
                stack=stack, session=session,
            )
        except BaseException:
            await stack.aclose()
            raise

    def _environment(self, config: ServerConfig) -> dict[str, str]:
        """Only the approved names. Values come from the environment/keychain."""
        env: dict[str, str] = {}
        for name in config.env_allowlist:
            value = os.environ.get(name)
            if value is None:
                try:
                    from ..keystore import get_secret
                    value = get_secret(f"mcp.{config.id}.{name}") or None
                except Exception:
                    value = None
            if value is not None:
                env[name] = value
        return env

    def stop(self, server_id: str, project_id: str = "") -> bool:
        key = (str(project_id), str(server_id))
        with self._lock:
            runtime = self._runtimes.pop(key, None)
        config = self.registry.get(server_id, project_id)
        if config is not None:
            self._unregister_tools(config)
        if runtime is None:
            return False
        self._run(self._close_runtime(runtime), timeout=self.init_timeout + 5.0)
        return True

    async def _close_runtime(self, runtime: _Runtime) -> None:
        if runtime.refresh_task is not None:
            runtime.refresh_task.cancel()
        try:
            await runtime.stack.aclose()
        except Exception:
            # Cleanup must not hide the fact that the process is gone; the
            # SDK's stdio transport terminates and reaps it in its own finally.
            pass

    def stop_all(self) -> None:
        with self._lock:
            keys = list(self._runtimes)
        for project_id, server_id in keys:
            try:
                self.stop(server_id, project_id)
            except Exception:
                pass

    def close(self) -> None:
        self.stop_all()
        with self._lock:
            loop, thread = self._loop, self._thread
            self._loop = None
            self._thread = None
        if loop is not None:
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=5.0)

    def __enter__(self) -> "MCPClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- loop bridge --------------------------------------------------------
    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is not None and self._thread is not None and self._thread.is_alive():
                return self._loop
            loop = asyncio.new_event_loop()
            ready = threading.Event()

            def run() -> None:
                asyncio.set_event_loop(loop)
                ready.set()
                loop.run_forever()
                pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.close()

            thread = threading.Thread(target=run, name="swarmbly-mcp", daemon=True)
            thread.start()
            ready.wait(5.0)
            self._loop = loop
            self._thread = thread
            return loop

    def _run(self, coro: Any, *, timeout: float) -> Any:
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        try:
            return future.result(timeout)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise MCPTimeout(f"MCP operation exceeded {timeout:g}s") from None

    # -- manifest and approval ---------------------------------------------
    async def _list_manifest_async(self, session: Any, server_id: str) -> ToolManifest:
        sdk = _sdk()
        seen: dict[str, ManifestTool] = {}
        cursor: str | None = None
        for _ in range(MAX_MANIFEST_PAGES):
            params = sdk["PaginatedRequestParams"](cursor=cursor) if cursor else None
            try:
                page = await asyncio.wait_for(
                    session.list_tools(params=params), timeout=self.list_timeout)
            except TimeoutError:
                raise MCPTimeout(
                    f"MCP server {server_id!r} did not answer tools/list within "
                    f"{self.list_timeout:g}s") from None
            for tool in list(page.tools or []):
                name = str(getattr(tool, "name", "") or "")
                if not name:
                    raise MCPProtocolError(f"MCP server {server_id!r} returned a tool without a name")
                if name in seen:
                    raise MCPProtocolError(
                        f"MCP server {server_id!r} returned duplicate tool {name!r}")
                schema = getattr(tool, "input_schema", None)
                if not isinstance(schema, dict):
                    raise MCPProtocolError(
                        f"MCP tool {name!r} has a non-object input schema")
                description = getattr(tool, "description", "") or ""
                seen[name] = ManifestTool(
                    name=name, description=str(description),
                    input_schema=copy.deepcopy(schema),
                )
            cursor = getattr(page, "next_cursor", None) or None
            if not cursor:
                break
        else:
            raise MCPProtocolError(
                f"MCP server {server_id!r} paginated tools/list more than "
                f"{MAX_MANIFEST_PAGES} times")
        tools = tuple(seen[name] for name in sorted(seen))
        payload = [item.to_dict() for item in tools]
        try:
            digest = sha256_canonical(payload)
        except SchemaError as exc:
            raise MCPProtocolError(f"{server_id!r}: manifest is not canonical JSON: {exc}") from None
        return ToolManifest(server_id=server_id, tools=tools, hash=digest)

    def propose(self, server_id: str, project_id: str = "") -> ToolManifest:
        """List every live tool for the user; no approval is granted."""
        runtime = self._runtime(server_id, project_id)
        manifest = self._run(
            self._list_manifest_async(runtime.session, server_id),
            timeout=self.list_timeout + 2.0)
        runtime.manifest = manifest
        config = self.registry.require(server_id, project_id)
        if (config.status == "approved" and config.approved_manifest_hash
                and manifest.hash != config.approved_manifest_hash):
            self._suspend(
                config,
                "the live tools/list manifest changed; approve the server again",
                project_id, runtime,
            )
        return manifest

    def approve(self, server_id: str, tools: Iterable[str] | None = None,
                project_id: str = "") -> ServerConfig:
        """Store the live manifest hash and register only the selected tools.

        Every selected schema must fit the broker's strict subset. If any one
        does not, nothing is approved or registered and the reason names it.
        """
        runtime = self._runtime(server_id, project_id)
        config = self.registry.require(server_id, project_id)
        if config.command_hash != runtime.config.command_hash:
            raise MCPError("the server configuration changed; stop it and start it again")
        manifest = self._run(
            self._list_manifest_async(runtime.session, server_id),
            timeout=self.list_timeout + 2.0)
        runtime.manifest = manifest
        if tools is None:
            selected = tuple(item.name for item in manifest.tools)
        elif isinstance(tools, str):
            selected = (tools,)
        else:
            selected = tuple(sorted(set(str(name) for name in tools)))
        prepared: list[tuple[str, ToolSpec]] = []
        for name in selected:
            item = manifest.tool(name)
            if item is None:
                raise MCPApprovalError(
                    f"tool {name!r} is not in the live manifest; list the server again")
            try:
                schema = _approval_schema(item.input_schema)
                validate_schema(schema, root=True)
                spec = ToolSpec(
                    _tool_spec_id(server_id, name),
                    "mcp_local" if config.kind == "local_stdio" else "mcp_remote",
                    "local" if config.kind == "local_stdio" else config.url,
                    schema,
                    item.description,
                )
            except (SchemaError, MCPError, ValueError) as exc:
                raise MCPApprovalError(
                    f"tool {name!r} cannot be approved: {exc}") from None
            prepared.append((name, spec))

        old_ids = set()
        for name in config.approved_tools:
            try:
                old_ids.add(_tool_spec_id(server_id, name))
            except MCPApprovalError:
                continue
        new_ids = {spec.id for _, spec in prepared}
        for old_id in sorted(old_ids - new_ids):
            self.broker.unregister(old_id)
            self.broker.revoke(old_id, project_id)
        self._unregister_tools(config, keep=new_ids)

        registered: list[str] = []
        try:
            for _name, spec in prepared:
                self.broker.register(
                    spec, self._handler(server_id, _name, project_id))
                registered.append(spec.id)
                self.broker.approve(spec.id, project_id)
        except Exception:
            for spec_id in registered:
                self.broker.unregister(spec_id)
            raise

        config.approved_manifest_hash = manifest.hash
        config.approved_tools = tuple(name for name, _ in prepared)
        config.status = "approved"
        config.suspension_reason = ""
        config = self.registry.put(config, project_id)
        runtime.config = config
        runtime.stale = False
        return config

    def _register_approved(self, config: ServerConfig, runtime: _Runtime,
                           project_id: str) -> None:
        """Re-register the already approved subset after a matching reconnect."""
        for name in config.approved_tools:
            item = runtime.manifest.tool(name) if runtime.manifest else None
            if item is None:
                self._suspend(config, f"approved tool {name!r} disappeared", project_id, runtime)
                return
            try:
                schema = _approval_schema(item.input_schema)
                validate_schema(schema, root=True)
                spec = ToolSpec(
                    _tool_spec_id(config.id, name),
                    "mcp_local" if config.kind == "local_stdio" else "mcp_remote",
                    "local" if config.kind == "local_stdio" else config.url,
                    schema, item.description,
                )
            except (SchemaError, MCPError, ValueError) as exc:
                self._suspend(
                    config, f"approved tool {name!r} is no longer usable: {exc}",
                    project_id, runtime)
                return
            self.broker.register(spec, self._handler(config.id, name, project_id))

    def _suspend(self, config: ServerConfig, reason: str, project_id: str,
                 runtime: _Runtime | None = None) -> None:
        config.status = "suspended"
        config.suspension_reason = reason
        self._unregister_tools(config)
        try:
            self.registry.put(config, project_id)
        except MCPError:
            pass
        if runtime is not None:
            runtime.config = config
            runtime.stale = True

    def _unregister_tools(self, config: ServerConfig, *,
                          keep: set[str] | None = None) -> None:
        prefix = f"mcp:{config.id}/"
        with self._lock:
            spec_ids = set(self.broker.specs())
        for spec_id in spec_ids:
            if spec_id.startswith(prefix) and (keep is None or spec_id not in keep):
                self.broker.unregister(spec_id)

    # -- notifications ------------------------------------------------------
    def _message_handler(self, server_id: str, project_id: str) -> Any:
        notification = _sdk()["ToolListChangedNotification"]

        async def handler(message: Any) -> None:
            if isinstance(message, notification):
                self._schedule_refresh(server_id, project_id)

        return handler

    def _schedule_refresh(self, server_id: str, project_id: str) -> None:
        try:
            task = asyncio.create_task(self._refresh(server_id, project_id))
        except RuntimeError:
            return
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _refresh(self, server_id: str, project_id: str) -> None:
        runtime = self._runtimes.get((str(project_id), str(server_id)))
        if runtime is None or runtime.stale:
            return
        try:
            manifest = await self._list_manifest_async(runtime.session, server_id)
        except Exception:
            return
        runtime.manifest = manifest
        config = self.registry.get(server_id, project_id)
        if (config is not None and config.status == "approved"
                and config.approved_manifest_hash
                and manifest.hash != config.approved_manifest_hash):
            self._suspend(
                config,
                "tools/list_changed: the manifest no longer matches the approved hash "
                f"({manifest.hash[:12]}… != {config.approved_manifest_hash[:12]}…)",
                project_id, runtime,
            )

    # -- calls --------------------------------------------------------------
    def _runtime(self, server_id: str, project_id: str = "") -> _Runtime:
        runtime = self._runtimes.get((str(project_id), str(server_id)))
        if runtime is None:
            raise MCPNotRunning(
                f"MCP server {server_id!r} is not running; call start() first")
        return runtime

    def _handler(self, server_id: str, tool_name: str, project_id: str) -> Any:
        def handler(call: ToolCall, ctx: Any) -> ToolResult:
            return self._call(server_id, tool_name, project_id, call, ctx)
        return handler

    def _call(self, server_id: str, tool_name: str, project_id: str,
              call: ToolCall, ctx: Any) -> ToolResult:
        runtime = self._runtime(server_id, project_id)
        if runtime.stale:
            raise ToolDenied(
                f"MCP server {server_id!r} is suspended; approve its manifest again",
                ctx.spec.id,
            )
        self._passages_guard(ctx.spec, call.arguments, ctx)
        if ctx.spec.destination != "local":
            try:
                payload = canonical_json(call.arguments).encode("utf-8")
            except SchemaError as exc:
                raise ToolDenied(f"invalid arguments for {ctx.spec.id}: {exc}",
                                 ctx.spec.id) from None
            ctx._send(ctx.spec.destination, len(payload),
                      f"MCP tool {ctx.spec.id}")
        return self._run(
            self._call_async(runtime.session, tool_name, call.arguments, ctx.spec.id),
            timeout=self.call_timeout + 2.0)

    async def _call_async(self, session: Any, tool_name: str,
                          arguments: dict[str, Any], spec_id: str) -> ToolResult:
        try:
            result = await asyncio.wait_for(
                session.call_tool(tool_name, arguments), timeout=self.call_timeout)
        except TimeoutError:
            raise MCPTimeout(
                f"MCP tool {spec_id} did not answer within {self.call_timeout:g}s") from None
        if not hasattr(result, "content"):
            raise MCPProtocolError(f"MCP tool {spec_id} returned an unsupported result")
        texts: list[str] = []
        omitted: list[str] = []
        for item in list(result.content or []):
            kind = str(getattr(item, "type", "") or "unknown")
            if kind == "text":
                texts.append(str(getattr(item, "text", "") or ""))
            elif kind in ("image", "audio", "resource"):
                omitted.append(kind)
            elif kind == "resource_link":
                omitted.append("resource")
            else:
                omitted.append(kind)
        text = "\n".join(texts)
        markers = "\n".join(f"omitted: {kind}" for kind in omitted)
        limit = max(0, int(self.broker.max_result_chars))
        if len(text) > limit:
            text = text[:limit]
            truncated = True
        else:
            truncated = False
        content = text
        if markers:
            content = f"{text}\n{markers}" if text else markers
        is_error = bool(getattr(result, "is_error", False))
        return ToolResult(
            spec_id=spec_id, ok=not is_error, content=content,
            data=getattr(result, "structured_content", None),
            error="" if not is_error else (text or "MCP tool returned isError"),
            truncated=truncated,
        )

    def _passages_guard(self, spec: ToolSpec, arguments: dict[str, Any],
                        ctx: Any) -> None:
        if spec.provider != "mcp_remote":
            return
        try:
            size = len(canonical_json(arguments))
        except SchemaError:
            size = 0
        documents = _passages.get()
        if size <= PASSAGE_ARG_CHARS and not _has_passage_shingle(arguments, documents):
            return
        if egress.policy().third_party_passages:
            return
        reason = (
            f"MCP tool {spec.id} would receive text that may come from your "
            "documents; privacy.third_party_passages is required. Nothing was sent."
        )
        class_, host = egress.classify_url(spec.destination)
        egress.record(destino=host, clase=class_, tipo=egress.TOOL_REMOTE, bytes=0,
                      motivo=reason, bloqueado=True, spec_id=spec.id,
                      aprobado_por=getattr(ctx, "approved_by", ""))
        ctx.attempted = True
        raise ToolDenied(reason, spec.id)
