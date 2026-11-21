"""The «doctor» export: one file a beta volunteer can attach (R-014).

The export is built from an allow-list, never by redacting a larger dump. It
contains versions, OS/architecture, CPU/RAM/GPU class, installed extras, the
Ollama reachability and model tags, the sandbox cache/compile measurement, P2P
counts and relay/push codes, and the last error codes with timestamps.

It never contains node ids or keys, names, circle names or ids, member names,
IP addresses or host names, paths under the user's home, project names,
document titles, prompts, answers, glossary, memory, API keys or relay hosts.
The module exposes a schema and a validator so the privacy test and the API
check the same contract the file promises.

The preview returns the exact JSON and text strings that :meth:`save` writes;
the UI shows those strings, so «what you see» is byte-for-byte «what is saved».
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

SCHEMA_VERSION = "swarmbly-doctor/1"
#: The export probes only the standard local Ollama, never the configured
#: remote model server: building a diagnostic file must not send anything out.
LOCAL_OLLAMA_URL = "http://127.0.0.1:11434"
_LIMIT = 10
_SAFE_TOKEN = re.compile(r"^(?:E_[A-Z0-9_]{2,40}|[a-z][a-z0-9_.-]{2,40})$")
_CODE_IN_TEXT = re.compile(r"^(E_[A-Z0-9_]{2,40}|[a-z][a-z0-9]*(?:_[a-z0-9]+)+)")

SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["schema", "generated_at", "app", "lce", "core", "system",
                 "extras", "ollama", "sandbox", "p2p", "errors"],
    "properties": {
        "schema": {"const": SCHEMA_VERSION},
        "generated_at": {"type": "string"},
        "app": {"type": "object", "additionalProperties": False,
                "required": ["version"],
                "properties": {"version": {"type": "string"}}},
        "lce": {"type": "object", "additionalProperties": False,
                "required": ["spec", "version"],
                "properties": {"spec": {"type": "string"},
                               "version": {"type": ["string", "null"]}}},
        "core": {"type": "object", "additionalProperties": False,
                 "required": ["spec", "version"],
                 "properties": {"spec": {"type": "string"},
                                "version": {"type": ["string", "null"]}}},
        "system": {
            "type": "object", "additionalProperties": False,
            "required": ["os", "os_release", "architecture", "python", "cpu",
                         "ram", "gpu"],
            "properties": {
                "os": {"type": "string"},
                "os_release": {"type": "string"},
                "architecture": {"type": "string"},
                "python": {"type": "string"},
                "cpu": {"type": "object", "additionalProperties": False,
                        "required": ["class", "physical_cores", "logical_cores"],
                        "properties": {
                            "class": {"type": "string"},
                            "physical_cores": {"type": ["integer", "null"]},
                            "logical_cores": {"type": ["integer", "null"]}}},
                "ram": {"type": "object", "additionalProperties": False,
                        "required": ["total_gb", "available_gb"],
                        "properties": {"total_gb": {"type": ["number", "null"]},
                                       "available_gb": {"type": ["number", "null"]}}},
                "gpu": {"type": "object", "additionalProperties": False,
                        "required": ["class", "count"],
                        "properties": {"class": {"type": "string"},
                                       "count": {"type": "integer"}}},
            },
        },
        "extras": {"type": "object", "additionalProperties": False,
                   "required": ["sandbox", "agent", "tools"],
                   "properties": {"sandbox": {"type": "boolean"},
                                  "agent": {"type": "boolean"},
                                  "tools": {"type": "boolean"}}},
        "ollama": {"type": "object", "additionalProperties": False,
                   "required": ["reachable", "model_tags"],
                   "properties": {"reachable": {"type": "boolean"},
                                  "model_tags": {"type": "array",
                                                 "items": {"type": "string"}}}},
        "sandbox": {
            "type": "object", "additionalProperties": False,
            "required": ["status", "installed", "cache_bytes", "expected_seconds",
                         "expected_memory_gb", "minimum_free_memory_gb",
                         "free_memory_gb", "can_prepare", "forced",
                         "prepared_at", "compile_seconds", "peak_memory_mib",
                         "wasi_python", "last_error_code"],
            "properties": {
                "status": {"enum": ["not_installed", "missing", "stale",
                                    "preparing", "ready", "failed", "refused"]},
                "installed": {"type": "boolean"},
                "cache_bytes": {"type": "integer"},
                "expected_seconds": {"type": "number"},
                "expected_memory_gb": {"type": "number"},
                "minimum_free_memory_gb": {"type": "number"},
                "free_memory_gb": {"type": ["number", "null"]},
                "can_prepare": {"type": "boolean"},
                "forced": {"type": "boolean"},
                "prepared_at": {"type": ["string", "null"]},
                "compile_seconds": {"type": ["number", "null"]},
                "peak_memory_mib": {"type": ["number", "null"]},
                "wasi_python": {"type": ["string", "null"]},
                "last_error_code": {"type": ["string", "null"]},
            },
        },
        "p2p": {"type": "object", "additionalProperties": False,
                "required": ["listening", "peers", "circles", "relay_configured",
                             "relay_status_codes", "push_state_codes"],
                "properties": {
                    "listening": {"type": "boolean"},
                    "peers": {"type": "integer"},
                    "circles": {"type": "integer"},
                    "relay_configured": {"type": "boolean"},
                    "relay_status_codes": {"type": "array",
                                           "items": {"type": "string"}},
                    "push_state_codes": {"type": "array",
                                         "items": {"type": "string"}}}},
        "errors": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["at", "code"],
            "properties": {"at": {"type": "string"},
                           "code": {"type": "string"}}}},
    },
}


def validate_export(data: Any) -> list[str]:
    """Validate against :data:`SCHEMA`; an empty list means the export is valid."""
    errors: list[str] = []
    _validate(data, SCHEMA, "$", errors)
    return errors


def _validate(value: Any, schema: dict[str, Any], path: str,
              errors: list[str]) -> None:
    expected = schema.get("type")
    if expected is not None:
        options = expected if isinstance(expected, list) else [expected]
        if not any(_is_type(value, option) for option in options):
            errors.append(f"{path}: expected {'/'.join(options)}, got "
                          f"{type(value).__name__}")
            return
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: not in {schema['enum']!r}")
    if isinstance(value, dict):
        properties = schema.get("properties") or {}
        for key in schema.get("required") or []:
            if key not in value:
                errors.append(f"{path}: missing {key!r}")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}: unexpected key {key!r}")
        for key, item in value.items():
            if key in properties:
                _validate(item, properties[key], f"{path}.{key}", errors)
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            _validate(item, schema["items"], f"{path}[{index}]", errors)


def _is_type(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return True


# --------------------------------------------------------------------------- gathering


def _dist_version(name: str) -> str | None:
    try:
        import importlib.metadata as md
        return str(md.version(name))
    except Exception:
        return None


def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _cpu_class(hardware: Any) -> dict[str, Any]:
    try:
        probe = hardware.detect_cpu().value
    except Exception:
        probe = {}
    physical = probe.get("cores_physical")
    logical = probe.get("cores_logical")
    import platform
    cores = physical or logical
    label = f"{platform.machine() or 'unknown'}-{cores or 'unknown'}c"
    return {"class": label, "physical_cores": physical, "logical_cores": logical}


def _ram(hardware: Any) -> dict[str, Any]:
    try:
        probe = hardware.detect_memory().value
    except Exception:
        probe = {}
    total = probe.get("total_bytes")
    available = probe.get("available_bytes")
    return {
        "total_gb": round(total / (1024 ** 3), 1) if total else None,
        "available_gb": round(available / (1024 ** 3), 1) if available else None,
    }


def _gpu(hardware: Any) -> dict[str, Any]:
    probe = None
    try:
        probe = hardware.detect_gpu()
        value = probe.value or {}
    except Exception:
        value = {}
    cards = value.get("gpus") or []
    if value.get("unified_memory"):
        kind = "unified"
    elif cards:
        kind = "discrete"
    elif probe is not None:
        kind = "none"
    else:
        kind = "unknown"
    return {"class": kind, "count": len(cards)}


def _ollama(url: str, timeout: float = 2.0) -> dict[str, Any]:
    """Reachable yes/no and model tags only: no sizes, paths or binary path."""
    reachable = False
    tags: list[str] = []
    try:
        with httpx.Client(timeout=timeout) as client:
            version = client.get(f"{url.rstrip('/')}/api/version")
            reachable = version.status_code == 200
            if reachable:
                listing = client.get(f"{url.rstrip('/')}/api/tags")
                if listing.status_code == 200:
                    for item in (listing.json() or {}).get("models") or []:
                        name = str((item or {}).get("name") or "").strip()
                        if name and len(name) <= 100:
                            tags.append(name)
    except Exception:
        pass
    return {"reachable": reachable, "model_tags": sorted(set(tags))}


def _token(value: Any) -> str:
    text = str(value or "").strip()
    return text if _SAFE_TOKEN.match(text) else "unknown"


def _code_from_text(value: Any) -> str:
    match = _CODE_IN_TEXT.match(str(value or "").strip())
    return match.group(1) if match else "unknown"


def _p2p(state: Any) -> dict[str, Any]:
    nodes = getattr(state, "nodes", None)
    try:
        status = nodes.status() if nodes is not None else {}
    except Exception:
        status = {}
    circles = getattr(state, "circles", None)
    try:
        circle_count = int((circles.summary() if circles is not None else {}).get(
            "circles") or 0)
    except Exception:
        circle_count = 0
    relay_configured = False
    try:
        payload = circles.list_payload() if circles is not None else {}
        relay_configured = any(
            bool(c.get("relay")) for c in payload.get("circles") or [])
    except Exception:
        relay_configured = False
    relay_codes: set[str] = set()
    push_codes: set[str] = set()
    try:
        relay_states = nodes.relay_status() if nodes is not None else []
    except Exception:
        relay_states = []
    for item in relay_states if isinstance(relay_states, list) else []:
        if not isinstance(item, dict):
            continue
        relay_configured = relay_configured or bool(item.get("status") not in (None, "off"))
        relay_codes.add(_token(item.get("status") or "unknown"))
        push = item.get("push") or {}
        current = push.get("current") or {}
        if current:
            push_codes.add(_token(current.get("status") or "unknown"))
            for key in ("last_refusal", "last_error"):
                if current.get(key):
                    push_codes.add(_code_from_text(current.get(key)))
        if push.get("pending_versions"):
            push_codes.add("pending")
    return {
        "listening": bool(status.get("listening")),
        "peers": int(status.get("connected_count") or 0),
        "circles": circle_count,
        "relay_configured": bool(relay_configured),
        "relay_status_codes": sorted(relay_codes),
        "push_state_codes": sorted(push_codes),
    }


def _sandbox(state: Any) -> dict[str, Any]:
    service = getattr(state, "sandbox", None)
    if service is None:
        return {
            "status": "not_installed", "installed": False, "cache_bytes": 0,
            "expected_seconds": 60.0, "expected_memory_gb": 3.3,
            "minimum_free_memory_gb": 4.0, "free_memory_gb": None,
            "can_prepare": False, "forced": False, "prepared_at": None,
            "compile_seconds": None, "peak_memory_mib": None, "wasi_python": None,
            "last_error_code": None,
        }
    try:
        status = service.status()
    except Exception:
        return {
            "status": "failed", "installed": False, "cache_bytes": 0,
            "expected_seconds": 60.0, "expected_memory_gb": 3.3,
            "minimum_free_memory_gb": 4.0, "free_memory_gb": None,
            "can_prepare": False, "forced": False, "prepared_at": None,
            "compile_seconds": None, "peak_memory_mib": None, "wasi_python": None,
            "last_error_code": "sandbox_status_failed",
        }
    measurement = status.get("measurement") or {}
    last_code = str(status.get("last_error_code") or "")
    return {
        "status": str(status.get("status") or "missing"),
        "installed": bool(status.get("installed")),
        "cache_bytes": int(status.get("cache_bytes") or 0),
        "expected_seconds": float(status.get("expected_seconds") or 60.0),
        "expected_memory_gb": float(status.get("expected_memory_gb") or 3.3),
        "minimum_free_memory_gb": float(
            status.get("minimum_free_memory_gb") or 4.0),
        "free_memory_gb": status.get("free_memory_gb"),
        "can_prepare": bool(status.get("can_prepare")),
        "forced": bool(status.get("forced")),
        "prepared_at": measurement.get("prepared_at"),
        "compile_seconds": measurement.get("elapsed_s"),
        "peak_memory_mib": measurement.get("peak_rss_mib"),
        "wasi_python": status.get("wasi_python") or measurement.get("wasi_python"),
        "last_error_code": (last_code if _SAFE_TOKEN.match(last_code) else None),
    }


def build_export(state: Any) -> dict[str, Any]:
    """Assemble the allow-listed export. No caller data is copied in."""
    import platform

    import swarmbly_app
    from . import hardware

    errors = getattr(state, "errors", None)
    try:
        recent = errors.snapshot(_LIMIT) if errors is not None else []
    except Exception:
        recent = []
    sandbox = _sandbox(state)
    data = {
        "schema": SCHEMA_VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "app": {"version": str(swarmbly_app.__version__)},
        "lce": {"spec": str(swarmbly_app.LCE_SPEC_VERSION),
                "version": _dist_version("swarmbly-lce")},
        "core": {"spec": str(swarmbly_app.PROTOCOL_SPEC_VERSION),
                 "version": _dist_version("swarmbly-v0")},
        "system": {
            "os": platform.system() or "unknown",
            "os_release": platform.release() or "unknown",
            "architecture": platform.machine() or "unknown",
            "python": platform.python_version(),
            "cpu": _cpu_class(hardware),
            "ram": _ram(hardware),
            "gpu": _gpu(hardware),
        },
        "extras": {
            "sandbox": _has_module("wasi_python") and _has_module("wasmtime"),
            "agent": _has_module("swarmbly_agent"),
            "tools": _has_module("mcp"),
        },
        "ollama": _ollama(LOCAL_OLLAMA_URL),
        "sandbox": sandbox,
        "p2p": _p2p(state),
        "errors": [{"at": str(item.get("at") or ""),
                    "code": _token(item.get("code") or "unknown")}
                   for item in recent][:_LIMIT],
    }
    return data


def render_text(data: dict[str, Any]) -> str:
    """The readable version, from the same allow-listed values as the JSON."""
    sandbox = data.get("sandbox") or {}
    system = data.get("system") or {}
    ollama = data.get("ollama") or {}
    p2p = data.get("p2p") or {}
    extras = data.get("extras") or {}
    lines = [
        "Swarmbly doctor export",
        f"Generated: {data.get('generated_at')}",
        "",
        f"App: {data.get('app', {}).get('version')}",
        f"LCE: spec {data.get('lce', {}).get('spec')} "
        f"(package {data.get('lce', {}).get('version') or 'not installed'})",
        f"Core (SwarmblyAI): spec {data.get('core', {}).get('spec')} "
        f"(package {data.get('core', {}).get('version') or 'not installed'})",
        "",
        f"OS: {system.get('os')} {system.get('os_release')} "
        f"({system.get('architecture')})",
        f"Python: {system.get('python')}",
        f"CPU: {system.get('cpu', {}).get('class')} "
        f"({system.get('cpu', {}).get('physical_cores')} physical / "
        f"{system.get('cpu', {}).get('logical_cores')} logical)",
        f"RAM: {system.get('ram', {}).get('total_gb')} GB total, "
        f"{system.get('ram', {}).get('available_gb')} GB available",
        f"GPU: {system.get('gpu', {}).get('class')} "
        f"({system.get('gpu', {}).get('count')} detected)",
        f"Extras: sandbox={extras.get('sandbox')} agent={extras.get('agent')} "
        f"tools={extras.get('tools')}",
        "",
        f"Ollama reachable: {'yes' if ollama.get('reachable') else 'no'}",
        "Model tags: " + (", ".join(ollama.get("model_tags") or []) or "none"),
        "",
        f"Sandbox: {sandbox.get('status')} "
        f"(installed={'yes' if sandbox.get('installed') else 'no'}, "
        f"cache {sandbox.get('cache_bytes')} bytes)",
        f"  expected: {sandbox.get('expected_seconds')} s, "
        f"{sandbox.get('expected_memory_gb')} GB; "
        f"free now {sandbox.get('free_memory_gb')} GB "
        f"(minimum {sandbox.get('minimum_free_memory_gb')} GB)",
        f"  prepared: {sandbox.get('prepared_at') or 'never'}; "
        f"compile {sandbox.get('compile_seconds')} s; "
        f"peak {sandbox.get('peak_memory_mib')} MiB; "
        f"forced={'yes' if sandbox.get('forced') else 'no'}",
        f"  wasi-python: {sandbox.get('wasi_python') or 'unknown'}; "
        f"last error: {sandbox.get('last_error_code') or 'none'}",
        "",
        f"P2P: listening={'yes' if p2p.get('listening') else 'no'}, "
        f"peers={p2p.get('peers')}, circles={p2p.get('circles')}, "
        f"relay configured={'yes' if p2p.get('relay_configured') else 'no'}",
        "Relay states: " + (", ".join(p2p.get("relay_status_codes") or []) or "none"),
        "Push states: " + (", ".join(p2p.get("push_state_codes") or []) or "none"),
        "",
        "Last errors (codes only):",
    ]
    for item in data.get("errors") or []:
        lines.append(f"  {item.get('at')}  {item.get('code')}")
    if not data.get("errors"):
        lines.append("  none")
    lines.extend([
        "",
        "Privacy: no node id, key, name, circle id, member, IP, host, path, "
        "project, document, prompt, answer, glossary, memory, API key or relay "
        "host is included.",
        "",
    ])
    return "\n".join(lines)


def _json_text(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


class DoctorExportService:
    """Builds a preview snapshot and writes exactly that snapshot on save."""

    def __init__(self, state: Any) -> None:
        self.state = state
        self._snapshot: dict[str, Any] | None = None

    def preview(self) -> dict[str, Any]:
        data = build_export(self.state)
        text = render_text(data)
        snapshot = {
            "snapshot_id": uuid.uuid4().hex,
            "created_at": time.time(),
            "json": data,
            "json_text": _json_text(data),
            "text": text,
        }
        self._snapshot = snapshot
        return {
            "snapshot_id": snapshot["snapshot_id"],
            "json": data,
            "json_text": snapshot["json_text"],
            "text": text,
            "json_sha256": hashlib.sha256(
                snapshot["json_text"].encode("utf-8")).hexdigest(),
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }

    def save(self, snapshot_id: str | None = None,
             directory: str | Path | None = None) -> dict[str, Any]:
        snapshot = self._snapshot
        if snapshot is None or (snapshot_id and snapshot_id != snapshot["snapshot_id"]):
            raise ValueError("the preview expired; review the export again")
        if time.time() - float(snapshot["created_at"]) > 900:
            raise ValueError("the preview expired; review the export again")
        target = (Path(directory) if directory is not None
                  else self.state.output_dir("doctor"))
        target.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        json_path = target / f"swarmbly-doctor-{stamp}.json"
        text_path = target / f"swarmbly-doctor-{stamp}.txt"
        json_path.write_text(snapshot["json_text"], encoding="utf-8")
        text_path.write_text(snapshot["text"], encoding="utf-8")
        return {
            "json_file": str(json_path),
            "text_file": str(text_path),
            "json_sha256": hashlib.sha256(
                snapshot["json_text"].encode("utf-8")).hexdigest(),
            "text_sha256": hashlib.sha256(
                snapshot["text"].encode("utf-8")).hexdigest(),
        }

    def save_current(self, directory: str | Path | None = None) -> dict[str, Any]:
        self.preview()
        return self.save(None, directory)
