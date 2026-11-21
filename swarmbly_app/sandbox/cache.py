"""Compiled-cache state and measurements for the recipe-5 sandbox (R-005).

The first ``wasi-python`` run compiles CPython to WebAssembly: about 5 s and
3.3 GB of memory on an Apple-silicon laptop, about 60 s on a 2-vCPU machine.
This module answers one question without compiling anything — *is the cache
missing, stale or ready?* — and keeps the last measured compile (wall time and
peak RSS) next to the cache for the doctor export.

The manifest and the preparation state contain no user data and no absolute
paths: versions, wall time, peak memory and the cache size are enough.
"""

from __future__ import annotations

import datetime
import importlib
import importlib.metadata as md
import importlib.util
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any, Callable

MIB = 1024 * 1024
GIB = 1024 * 1024 * 1024

CACHE_SCHEMA = "swarmbly-sandbox-cache/1"
STATE_SCHEMA = "swarmbly-sandbox-prepare/1"
MANIFEST_NAME = "prepared.json"
STATE_NAME = "prepare-state.json"

#: Measured on the reference machines in ARCH_3.5 §3.8 / RISKS R-005.
EXPECTED_MEMORY_GB = 3.3
#: The compile peaks at ~3.3 GB; leave ~0.7 GB for the OS and the App so a
#: machine with 4 GB total is not pushed into swap or the OOM killer.
MIN_FREE_MEMORY_BYTES = 4 * GIB
#: "Later" hides the notice for a week; the next launch or Settings reopens it.
DEFER_SECONDS = 7 * 24 * 3600


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cache_dir_for(root: str | Path) -> Path:
    return Path(root) / "cache" / "wasi-python"


def manifest_path(root: str | Path) -> Path:
    return Path(root) / "cache" / MANIFEST_NAME


def state_path(root: str | Path) -> Path:
    return Path(root) / "cache" / STATE_NAME


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2),
                   encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def directory_bytes(path: Path) -> int:
    """Bytes of regular files below ``path``, never following a symlink."""
    total = 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    total += directory_bytes(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
            except OSError:
                continue
    except OSError:
        return total
    return total


def sandbox_version() -> tuple[bool, str]:
    """``(installed, version)`` of the optional sandbox extra.

    Uses ``find_spec`` and the distribution metadata: no import, so checking
    the cache never pays any part of the compile or of the package start-up.
    A broken package that is present still reports installed here; the
    runner's ``available()`` is the probe that imports it for a real run.
    """
    try:
        if (importlib.util.find_spec("wasi_python") is None
                or importlib.util.find_spec("wasmtime") is None):
            return False, ""
        return True, md.version("wasi-python")
    except Exception:
        return False, ""


def read_manifest(root: str | Path) -> dict[str, Any] | None:
    return _read_json(manifest_path(root))


def cache_status(root: str | Path) -> dict[str, Any]:
    """Classify the compiled cache. This function never starts a compile.

    * ``not_installed`` — the optional ``[sandbox]`` extra is absent;
    * ``missing`` — no manifest and no cache files;
    * ``stale`` — files without a manifest (a pre-3.5 cache), or the recorded
      ``wasi-python``/Python version no longer matches the installed one;
    * ``ready`` — manifest and cache files agree.
    """
    installed, version = sandbox_version()
    cache_dir = cache_dir_for(root)
    size = directory_bytes(cache_dir)
    manifest = read_manifest(root)
    result: dict[str, Any] = {
        "status": "not_installed" if not installed else "missing",
        "wasi_python": version,
        "cache_bytes": size,
        "manifest": manifest,
        "python": platform.python_version(),
    }
    if not installed:
        return result
    if manifest is None:
        result["status"] = "missing" if size == 0 else "stale"
        return result
    recorded_version = str(manifest.get("wasi_python") or "")
    recorded_python = str(manifest.get("python") or "")
    recorded_bytes = int(manifest.get("cache_bytes") or 0)
    if (not recorded_version or not recorded_python
            or recorded_version != version
            or recorded_python != platform.python_version()
            or (recorded_bytes and size < recorded_bytes)):
        result["status"] = "stale"
        return result
    if size == 0:
        result["status"] = "missing"
        return result
    result["status"] = "ready"
    return result


def record_measurement(root: str | Path, result: dict[str, Any]) -> dict[str, Any]:
    """Write the successful compile measurement next to the cache."""
    cache_dir = cache_dir_for(root)
    measurement = {
        "schema": CACHE_SCHEMA,
        "prepared_at": utc_now(),
        "elapsed_s": result.get("elapsed_s"),
        "warm_s": result.get("warm_s"),
        "peak_rss_mib": result.get("peak_rss_mib"),
        "wasi_python": result.get("wasi_python") or sandbox_version()[1],
        "python": sys.version.split()[0],
        "platform": platform.system(),
        "machine": platform.machine(),
        "cache_bytes": directory_bytes(cache_dir),
    }
    _write_json(manifest_path(root), measurement)
    return measurement


def _free_memory_bytes() -> int | None:
    """Available memory from the same probe the setup assistant shows."""
    try:
        from .. import hardware
        value = hardware.detect_memory().value
        available = value.get("available_bytes")
        return int(available) if available is not None else None
    except Exception:
        return None


def _logical_cores() -> int | None:
    try:
        from .. import hardware
        return hardware.detect_cpu().value.get("cores_logical")
    except Exception:
        return None


def _expected_seconds(logical: int | None) -> tuple[float, str]:
    """The documented expectation for this class of machine."""
    if platform.system() == "Darwin" and platform.machine() in ("arm64", "aarch64"):
        return 5.0, "apple_silicon"
    if logical is None:
        return 60.0, "unknown_cores"
    if logical <= 2:
        return 60.0, "two_cores_or_less"
    if logical <= 4:
        return 30.0, "four_cores_or_less"
    return 60.0, "many_cores"


def estimate_prepare(root: str | Path | None = None, *,
                     memory_probe: Callable[[], int | None] | None = None
                     ) -> dict[str, Any]:
    """Expected time and memory, and whether this machine may start the compile.

    ``memory_probe`` is injectable so the low-memory rule is testable without
    allocating memory. ``None`` means the probe could not measure free memory;
    the compile is then refused rather than started blindly.
    """
    free = (memory_probe or _free_memory_bytes)()
    logical = _logical_cores()
    seconds, basis = _expected_seconds(logical)
    enough = free is not None and free >= MIN_FREE_MEMORY_BYTES
    return {
        "expected_seconds": seconds,
        "expected_memory_gb": EXPECTED_MEMORY_GB,
        "minimum_free_memory_gb": round(MIN_FREE_MEMORY_BYTES / GIB, 1),
        "free_memory_gb": round(free / GIB, 1) if free is not None else None,
        "enough_memory": bool(enough),
        "estimate_basis": basis,
    }


def read_state(root: str | Path) -> dict[str, Any]:
    data = _read_json(state_path(root)) or {}
    if data.get("schema") != STATE_SCHEMA:
        return {}
    return data


def write_state(root: str | Path, **fields: Any) -> dict[str, Any]:
    data = read_state(root)
    data.update(fields)
    data["schema"] = STATE_SCHEMA
    data["updated_at"] = utc_now()
    _write_json(state_path(root), data)
    return data
