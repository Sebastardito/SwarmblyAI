"""First-launch preparation of the recipe-5 compiled cache (R-005).

The App never compiles the WebAssembly module at import time and never starts
that compile silently. :class:`SandboxPreparation` answers the three questions
the notice, the API and the doctor export ask:

* is the extra installed, and is the cache missing, stale or ready?
* how long and how much memory should this machine expect?
* is a compile running now, and what did the last one measure?

When a compile is requested it runs in one daemon thread and publishes
``sandbox.prepare`` events (``starting`` → ``compiling`` → ``ready``/``failed``),
so the chat loop is never blocked. A machine with less than
:data:`~swarmbly_app.sandbox.cache.MIN_FREE_MEMORY_BYTES` free is refused by
the automatic/first-launch start and by a plain «Prepare now»: the peak is
~3.3 GB and a 4 GB floor keeps the OS out of swap. An explicit, informed
``force=True`` may override that floor (never automatically); it records
``forced: true`` and the free memory at start, and the measured peak afterwards.
The raw failure reason stays local; the doctor export only sees its stable code.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Callable

from . import cache
from .runner import SandboxRunner, available

RunnerFactory = Callable[[Path], Any]
AvailableProbe = Callable[[], tuple[bool, str]]
MemoryProbe = Callable[[], int | None]

_ERROR_REASONS = {
    "not_installed": "sandbox_not_installed",
    "low_memory": "low_memory",
    "compile_failed": "sandbox_compile_failed",
    "interrupted": "sandbox_prepare_interrupted",
}


def _default_root() -> Path:
    from ..paths import default_data_dir
    return default_data_dir() / "sandbox"


class SandboxPreparation:
    """Owns the compiled-cache state and the one background compile."""

    def __init__(self, root: str | Path | None = None, bus: Any = None, *,
                 runner_factory: RunnerFactory | None = None,
                 available_probe: AvailableProbe | None = None,
                 memory_probe: MemoryProbe | None = None) -> None:
        self.root = Path(root) if root is not None else _default_root()
        self.bus = bus
        self._runner_factory: RunnerFactory = runner_factory or SandboxRunner
        self._available: AvailableProbe = available_probe or available
        self._memory: MemoryProbe = memory_probe or cache._free_memory_bytes
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        state = cache.read_state(self.root)
        if state.get("status") == "preparing":
            # A previous process died mid-compile: do not show a forever spinner.
            state = cache.write_state(
                self.root, status="failed", stage="failed",
                reason_code=_ERROR_REASONS["interrupted"],
                reason="the previous preparation did not finish", finished_at=cache.utc_now())
        self._state: dict[str, Any] = state

    # -- read ---------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        with self._lock:
            running = self._thread is not None and self._thread.is_alive()
            state = dict(self._state)
            if state.get("status") == "preparing" and not running:
                state = cache.write_state(
                    self.root, status="failed", stage="failed",
                    reason_code=_ERROR_REASONS["interrupted"],
                    reason="the preparation stopped before it finished",
                    finished_at=cache.utc_now())
                self._state = state
        installed, _reason = self._available()
        version = cache.sandbox_version()[1] if installed else ""
        compiled = cache.cache_status(self.root)
        estimate = cache.estimate_prepare(self.root, memory_probe=self._memory)
        status = self._classify(installed, running, state, compiled)
        measurement = compiled.get("manifest") or {}
        snoozed_until = float(state.get("snoozed_until") or 0)
        notice = bool(
            installed
            and status in ("missing", "stale", "failed", "refused")
            and time.time() >= snoozed_until)
        return {
            "status": status,
            "stage": str(state.get("stage") or ""),
            "installed": bool(installed),
            "wasi_python": version,
            "cache_bytes": compiled.get("cache_bytes", 0),
            "expected_seconds": estimate["expected_seconds"],
            "expected_memory_gb": estimate["expected_memory_gb"],
            "minimum_free_memory_gb": estimate["minimum_free_memory_gb"],
            "free_memory_gb": estimate["free_memory_gb"],
            "enough_memory": estimate["enough_memory"],
            "estimate_basis": estimate["estimate_basis"],
            "can_prepare": bool(installed and status != "ready" and not running
                                and estimate["enough_memory"]),
            "can_force": bool(installed and status not in ("ready", "preparing")
                              and not running
                              and not estimate["enough_memory"]),
            "forced": bool(state.get("forced")),
            "started_free_memory_gb": state.get("started_free_memory_gb"),
            "notice": notice,
            "snoozed_until": _iso(snoozed_until) if snoozed_until else None,
            "measurement": _public_measurement(measurement),
            "last_error_code": (str(state.get("reason_code") or "")
                                if status in ("failed", "refused") else ""),
            "last_error": (str(state.get("reason") or "")[:300]
                           if status in ("failed", "refused") else ""),
            "started_at": state.get("started_at"),
            "finished_at": state.get("finished_at"),
            "elapsed_s": state.get("elapsed_s"),
        }

    @staticmethod
    def _classify(installed: bool, running: bool, state: dict[str, Any],
                  compiled: dict[str, Any]) -> str:
        if not installed:
            return "not_installed"
        # A ready manifest wins even if the thread has not fully exited yet:
        # otherwise a status poll can leave the UI on «preparing» for ever.
        if compiled.get("status") == "ready":
            return "ready"
        if running or state.get("status") == "preparing":
            return "preparing"
        if state.get("status") == "failed":
            return "failed"
        if state.get("status") == "refused":
            return "refused"
        return str(compiled.get("status") or "missing")

    # -- actions ------------------------------------------------------------
    def start(self, *, trigger: str = "user", force: bool = False) -> dict[str, Any]:
        """Start the background compile; never block the caller.

        ``force=True`` is the explicit, informed override for a machine below
        the free-memory floor. The automatic trigger ignores it, so an
        ``auto`` start is never forced; a plain start (``force=False``) keeps
        the floor.
        """
        if trigger == "auto":
            force = False
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return {"started": False, "reason_code": "already_preparing",
                        "status": self.status()}
            installed, _ = self._available()
            if not installed:
                self._state = cache.write_state(
                    self.root, status="failed", stage="failed",
                    reason_code=_ERROR_REASONS["not_installed"],
                    reason="the optional sandbox extra is not installed",
                    forced=False, started_free_memory_gb=None,
                    finished_at=cache.utc_now())
                return {"started": False, "reason_code": "not_installed",
                        "status": self.status()}
            if cache.cache_status(self.root).get("status") == "ready":
                self._state = cache.write_state(
                    self.root, status="ready", stage="ready",
                    reason_code="", reason="", snoozed_until=0)
                return {"started": False, "reason_code": "already_ready",
                        "status": self.status()}
            estimate = cache.estimate_prepare(self.root, memory_probe=self._memory)
            low_memory = not estimate["enough_memory"]
            if low_memory and not force:
                free = estimate["free_memory_gb"]
                reason = (f"free memory could not be measured; at least "
                          f"{estimate['minimum_free_memory_gb']} GB are required"
                          if free is None else
                          f"{free} GB free; at least "
                          f"{estimate['minimum_free_memory_gb']} GB are required")
                self._state = cache.write_state(
                    self.root, status="refused", stage="refused",
                    reason_code=_ERROR_REASONS["low_memory"],
                    reason=reason, trigger=trigger, forced=False,
                    started_free_memory_gb=None,
                    finished_at=cache.utc_now(), snoozed_until=0)
                self._publish("refused", reason_code="low_memory",
                              free_memory_gb=estimate["free_memory_gb"],
                              minimum_free_memory_gb=estimate["minimum_free_memory_gb"])
                return {"started": False, "reason_code": "low_memory",
                        "status": self.status()}
            # Recorded only when the override changed the outcome.
            forced = bool(force and low_memory)
            self._state = cache.write_state(
                self.root, status="preparing", stage="starting", trigger=trigger,
                forced=forced,
                started_free_memory_gb=estimate["free_memory_gb"],
                reason_code="", reason="", started_at=cache.utc_now(),
                finished_at=None, elapsed_s=None, snoozed_until=0)
            self._publish("preparing", stage="starting")
            thread = threading.Thread(target=self._run, daemon=True,
                                      name="swarmbly-sandbox-prepare")
            self._thread = thread
            thread.start()
        return {"started": True, "reason_code": "", "status": self.status()}

    def defer(self) -> dict[str, Any]:
        """Hide the notice for a week; the compile is not started."""
        with self._lock:
            self._state = cache.write_state(
                self.root, snoozed_until=time.time() + cache.DEFER_SECONDS)
        return self.status()

    def wait(self, timeout: float) -> dict[str, Any]:
        """Test/installer helper; the UI never calls this."""
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout)
        return self.status()

    # -- background ---------------------------------------------------------
    def _run(self) -> None:
        try:
            with self._lock:
                self._state = cache.write_state(
                    self.root, status="preparing", stage="compiling",
                    reason_code="", reason="")
            self._publish("preparing", stage="compiling")
            started = time.perf_counter()
            runner = self._runner_factory(self.root)
            result = runner.warm_up()
            elapsed = time.perf_counter() - started
            if not result or not result.get("ok"):
                self._fail(str((result or {}).get("reason") or "compile failed"),
                           elapsed)
                return
            measurement = cache.record_measurement(self.root, {
                **result, "elapsed_s": result.get("elapsed_s") or round(elapsed, 3)})
            with self._lock:
                self._state = cache.write_state(
                    self.root, status="ready", stage="ready", reason_code="",
                    reason="", finished_at=cache.utc_now(),
                    elapsed_s=measurement.get("elapsed_s"),
                    peak_rss_mib=measurement.get("peak_rss_mib"))
            self._publish("ready", elapsed_s=measurement.get("elapsed_s"),
                          peak_rss_mib=measurement.get("peak_rss_mib"))
        except Exception as exc:
            self._fail(f"{type(exc).__name__}: {exc}", None)

    def _fail(self, reason: str, elapsed: float | None) -> None:
        with self._lock:
            self._state = cache.write_state(
                self.root, status="failed", stage="failed",
                reason_code=_ERROR_REASONS["compile_failed"],
                reason=str(reason)[:300], finished_at=cache.utc_now(),
                elapsed_s=round(elapsed, 3) if elapsed is not None else None)
        self._publish("failed", reason_code="sandbox_compile_failed")

    def _publish(self, status: str, **fields: Any) -> None:
        if self.bus is None:
            return
        fields.setdefault("forced", bool(self._state.get("forced")))
        try:
            self.bus.publish("sandbox.prepare", status=status, **fields)
        except Exception:
            pass


def _public_measurement(manifest: dict[str, Any]) -> dict[str, Any]:
    """Only the fields the doctor export may carry (no paths, no hosts)."""
    if not manifest:
        return {}
    return {
        "prepared_at": manifest.get("prepared_at"),
        "elapsed_s": manifest.get("elapsed_s"),
        "warm_s": manifest.get("warm_s"),
        "peak_rss_mib": manifest.get("peak_rss_mib"),
        "wasi_python": manifest.get("wasi_python"),
    }


def _iso(timestamp: float) -> str:
    import datetime
    return datetime.datetime.fromtimestamp(
        timestamp, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
