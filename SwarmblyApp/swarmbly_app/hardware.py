"""Hardware and environment detection (spec §4.1).

Every probe reports a *source* and a *confidence*. Values that cannot be
detected reliably are reported as ``unknown`` — never invented.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil


def _run(args: list[str], timeout: float = 5.0) -> str | None:
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


@dataclass
class Probe:
    value: Any
    source: str
    confidence: str = "measured"  # measured | estimated | unknown


def detect_os() -> Probe:
    return Probe(
        {"system": platform.system(), "release": platform.release(),
         "machine": platform.machine(), "python": sys.version.split()[0]},
        "platform", "measured")


def detect_cpu() -> Probe:
    try:
        return Probe({
            "cores_physical": psutil.cpu_count(logical=False),
            "cores_logical": psutil.cpu_count(logical=True),
            "brand": platform.processor() or "unknown",
        }, "psutil+platform", "measured")
    except Exception:
        return Probe({"cores_physical": None, "cores_logical": None,
                      "brand": "unknown"}, "none", "unknown")


def detect_memory() -> Probe:
    try:
        vm = psutil.virtual_memory()
        return Probe({
            "total_bytes": vm.total,
            "available_bytes": vm.available,
            "percent_used": round(vm.percent, 1),
        }, "psutil", "measured")
    except Exception:
        return Probe({}, "none", "unknown")


def detect_storage(path: str | None = None) -> Probe:
    try:
        usage = shutil.disk_usage(path or "/")
        return Probe({
            "total_bytes": usage.total,
            "free_bytes": usage.free,
            "used_bytes": usage.used,
        }, "shutil", "measured")
    except Exception:
        return Probe({}, "none", "unknown")


def detect_gpu() -> Probe:
    """Best-effort GPU probe per OS. Unreliable sources are marked unknown."""
    system = platform.system()
    gpus: list[dict[str, Any]] = []
    source = "unknown"
    confidence = "unknown"
    if system == "Darwin":
        out = _run(["system_profiler", "SPDisplaysDataType", "-json"], timeout=20)
        if out:
            import json
            try:
                data = json.loads(out)
                for card in data.get("SPDisplaysDataType", []):
                    gpus.append({
                        "name": card.get("sppci_model", "unknown"),
                        "vendor": card.get("sppci_vendor", "unknown"),
                        "vram": card.get("spdisplays_vram", "unknown"),
                        "metal": card.get("spdisplays_metal", "unknown"),
                    })
                source, confidence = "system_profiler", "measured"
            except Exception:
                pass
    elif system == "Linux":
        out = _run(["nvidia-smi", "--query-gpu=name,memory.total",
                    "--format=csv,noheader"])
        if out:
            for line in out.splitlines():
                parts = [p.strip() for p in line.split(",")]
                gpus.append({"name": parts[0], "vram": parts[1] if len(parts) > 1 else "unknown"})
            source, confidence = "nvidia-smi", "measured"
        else:
            for line in Path("/sys/class/drm").glob("card*/device/vendor"):
                gpus.append({"name": "drm-card", "vram": "unknown"})
            source, confidence = "sysfs (vendor only)", "unknown"
    elif system == "Windows":
        # wmic was removed from Windows 11 24H2; PowerShell CIM works on 10/11.
        out = _run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_VideoController | "
                    "Select-Object -ExpandProperty Name"], timeout=10)
        if out is None:
            out = _run(["wmic", "path", "win32_VideoController", "get", "Name"])
            out = "\n".join(out.splitlines()[1:]) if out else None
        if out:
            for line in out.splitlines():
                if line.strip():
                    # AdapterRAM is a 32-bit field (wrong above 4 GB): not reported.
                    gpus.append({"name": line.strip(), "vram": "unknown"})
            source, confidence = "powershell/wmic (names only)", "measured"
        nvidia = _run(["nvidia-smi", "--query-gpu=name,memory.total",
                       "--format=csv,noheader"])
        if nvidia:
            gpus = [{"name": p[0], "vram": p[1] if len(p) > 1 else "unknown"}
                    for p in (l.split(",") for l in nvidia.splitlines()) if p]
            source, confidence = "nvidia-smi", "measured"
    return Probe({"gpus": gpus, "unified_memory": _apple_silicon()}, source, confidence)


def _apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() in ("arm64", "aarch64")


def detect_power() -> Probe:
    """Battery / AC state (for the worker's 'only when plugged in' option)."""
    try:
        battery = psutil.sensors_battery()
    except Exception:
        battery = None
    if battery is None:
        return Probe({"has_battery": False, "plugged": None, "percent": None},
                     "psutil (no battery reported)", "unknown")
    return Probe({"has_battery": True, "plugged": bool(battery.power_plugged),
                  "percent": round(float(battery.percent), 1)}, "psutil", "measured")


def detect_python_and_deps() -> Probe:
    deps: dict[str, str] = {}
    for name in ("numpy", "httpx", "fastapi", "uvicorn", "cryptography", "zeroconf",
                 "psutil", "swarmbly_v0", "swarmbly_lce"):
        try:
            module = __import__(name)
            deps[name] = getattr(module, "__version__", "installed")
        except Exception:
            deps[name] = "missing"
    return Probe(deps, "importlib", "measured")


def detect_network() -> Probe:
    try:
        addrs = psutil.net_if_addrs()
        interfaces = {}
        for iface, entries in addrs.items():
            for entry in entries:
                if entry.family.name == "AF_INET":
                    interfaces[iface] = entry.address
        return Probe({"interfaces": interfaces}, "psutil", "measured")
    except Exception:
        return Probe({}, "none", "unknown")


def detect_all(data_dir_hint: str | None = None) -> dict[str, Any]:
    """Run every check; the first-run assistant renders this."""
    result: dict[str, Any] = {}
    probes = {
        "os": detect_os(),
        "cpu": detect_cpu(),
        "memory": detect_memory(),
        "storage": detect_storage(data_dir_hint),
        "gpu": detect_gpu(),
        "python_deps": detect_python_and_deps(),
        "network": detect_network(),
        "power": detect_power(),
    }
    for name, probe in probes.items():
        result[name] = {"value": probe.value, "source": probe.source,
                        "confidence": probe.confidence}
    return result
