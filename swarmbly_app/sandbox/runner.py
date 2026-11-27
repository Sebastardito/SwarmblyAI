"""Recipe-5 sandbox runner: a disposable, pre-warmed worker per run.

Public contract (T7.1)::

    SandboxRunner.run(script, inputs, limits, approval) -> RunResult

``inputs`` are *copied* into a fresh per-run data directory granted read-only
at ``/data``; a fresh output directory is granted writable at ``/out``.  No
root, no mounts, no host/tools/import_path/stdin/env overlays.  The module
cache and ``TMPDIR`` live in an app-owned 0700 directory outside every grant.

A worker is a child process (``python -m swarmbly_app.sandbox.worker``).  It
pays the one-time wasi-python warm-up before reporting ready, runs exactly one
job, then exits.  A fuel run also pays wasi-python's separate metered compile
before the parent starts its wall clock.  The parent then enforces the hard wall
clock (``deadline_s`` plus grace) by killing the worker's process group, so a
timed-out run leaves no orphan.  On POSIX the worker also applies
``RLIMIT_FSIZE`` before the guest starts; on Windows the soft watchdog is the
only disk guard and the result says ``platform_guard: "watchdog"`` (R-006).

Importing this module never imports ``wasi_python`` and never compiles the
module; :func:`available` reports whether the optional extra is installed and
:meth:`SandboxRunner.warm_up` triggers the one-time cost explicitly (R-005).
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable

from .limits import MIB, Limits

__all__ = ["Limits", "RunResult", "SandboxError", "SandboxRunner", "available"]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKER_MODULE = "swarmbly_app.sandbox.worker"


class SandboxError(RuntimeError):
    """The sandbox could not be started (an infrastructure failure, not a guest trap)."""


def available() -> tuple[bool, str]:
    """``(True, "")`` when the optional sandbox extra can run, else ``(False, why)``.

    The check imports the two packages (cheap; it does not compile a module),
    so a broken or half-installed package reports unavailable instead of
    failing later inside a worker.
    """
    for name in ("wasi_python", "wasmtime"):
        try:
            importlib.import_module(name)
        except Exception as exc:
            return False, (f"{name} is not installed or not importable: "
                           f"{type(exc).__name__}: {exc}")
    return True, ""


@dataclass(frozen=True)
class RunResult:
    """What one guest run produced.  Extra diagnostic fields are harmless."""

    ok: bool
    stdout: str
    stderr: str
    files: list[dict[str, Any]]
    files_partial: bool
    trapped: str | None
    elapsed_s: float
    script_sha256: str
    platform_guard: str = "watchdog"
    exit_code: int | None = None
    truncated: list[str] = field(default_factory=list)
    worker_pid: int | None = None
    fuel_used: int | None = None
    disk_guard: str | None = None
    max_out_bytes_seen: int = 0
    max_out_files_seen: int = 0
    rejected_entries: int = 0
    collection_truncated: bool = False
    hard_file_cap_bytes: int | None = None
    run_id: str | None = None
    output_dir: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "files": [dict(item) for item in self.files],
            "files_partial": self.files_partial,
            "trapped": self.trapped,
            "elapsed_s": self.elapsed_s,
            "script_sha256": self.script_sha256,
            "platform_guard": self.platform_guard,
            "exit_code": self.exit_code,
            "truncated": list(self.truncated),
            "worker_pid": self.worker_pid,
            "fuel_used": self.fuel_used,
            "disk_guard": self.disk_guard,
            "max_out_bytes_seen": self.max_out_bytes_seen,
            "max_out_files_seen": self.max_out_files_seen,
            "rejected_entries": self.rejected_entries,
            "collection_truncated": self.collection_truncated,
            "hard_file_cap_bytes": self.hard_file_cap_bytes,
            "run_id": self.run_id,
            "output_dir": self.output_dir,
        }


@dataclass
class _Worker:
    process: subprocess.Popen[bytes]
    pid: int
    directory: Path
    stderr_path: Path
    ready: dict[str, Any]

    def stderr_tail(self, limit: int = 4000) -> str:
        try:
            data = self.stderr_path.read_bytes()
        except OSError:
            return ""
        return data[-limit:].decode("utf-8", "replace")


class SandboxRunner:
    """A small pool of disposable, pre-warmed worker processes.

    ``pool_size`` defaults to 1.  A worker handles one run and is replaced;
    call :meth:`close` (or use the runner as a context manager) to kill idle
    workers immediately.
    """

    def __init__(self, root: str | Path | None = None, *, pool_size: int = 1,
                 warm_timeout_s: float = 180.0) -> None:
        if isinstance(pool_size, bool) or not isinstance(pool_size, int) or pool_size < 1:
            raise ValueError("pool_size must be a positive integer")
        if pool_size > 4:
            raise ValueError("pool_size is bounded at 4 (memory: each worker is large)")
        self.root = Path(root) if root is not None else self._default_root()
        self.pool_size = pool_size
        self.warm_timeout_s = float(warm_timeout_s)
        self.cache_dir = self.root / "cache" / "wasi-python"
        self.tmp_root = self.root / "tmp"
        self.runs_dir = self.root / "runs"
        self.workers_dir = self.root / "workers"
        self._workers: list[_Worker] = []
        self._pool_lock = threading.RLock()
        self._replenish_thread: threading.Thread | None = None
        self._closed = False
        self._prepared = False

    # -- paths ---------------------------------------------------------------
    @staticmethod
    def _default_root() -> Path:
        # Imported lazily so importing the package stays cheap.
        from ..paths import default_data_dir

        return default_data_dir() / "sandbox"

    def _prepare(self) -> None:
        if self._prepared:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.root, 0o700)
        except OSError:
            pass
        for path in (self.cache_dir, self.tmp_root, self.runs_dir, self.workers_dir):
            path.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(path, 0o700)
            except OSError:
                pass
        self._prepared = True

    # -- worker lifecycle ----------------------------------------------------
    def _worker_command(self, worker_dir: Path) -> list[str]:
        return [sys.executable, "-m", _WORKER_MODULE,
                "--root", str(self.root),
                "--worker-dir", str(worker_dir),
                "--ready-file", str(worker_dir / "ready.json")]

    def _spawn_worker(self) -> _Worker:
        self._prepare()
        worker_id = uuid.uuid4().hex
        directory = self.workers_dir / worker_id
        directory.mkdir(mode=0o700, parents=True, exist_ok=False)
        ready_path = directory / "ready.json"
        stderr_path = directory / "stderr.log"
        env = os.environ.copy()
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (str(_REPO_ROOT) + (os.pathsep + existing if existing else ""))
        stderr_handle = open(stderr_path, "wb")
        try:
            process = subprocess.Popen(
                self._worker_command(directory),
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=stderr_handle,
                cwd=str(_REPO_ROOT),
                env=env,
                start_new_session=(os.name == "posix"),
            )
        finally:
            stderr_handle.close()

        deadline = time.monotonic() + self.warm_timeout_s
        ready: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            if ready_path.is_file():
                try:
                    ready = json.loads(ready_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    ready = None
                if ready is not None:
                    break
            if process.poll() is not None:
                break
            time.sleep(0.02)

        if ready is None or not ready.get("ok"):
            tail = ""
            try:
                tail = stderr_path.read_bytes()[-2000:].decode("utf-8", "replace")
            except OSError:
                pass
            self._kill_process(process)
            self._discard_worker_dir(directory)
            reason = (ready or {}).get("error") or tail or "worker did not become ready"
            raise SandboxError(f"sandbox worker failed to start: {reason}")

        return _Worker(process, process.pid, directory, stderr_path, ready)

    def _ensure_pool(self) -> None:
        with self._pool_lock:
            if self._closed:
                raise SandboxError("sandbox runner is closed")
            while len(self._workers) < self.pool_size:
                self._workers.append(self._spawn_worker())

    def _take_worker(self) -> _Worker:
        with self._pool_lock:
            if self._closed:
                raise SandboxError("sandbox runner is closed")
            while len(self._workers) < self.pool_size:
                self._workers.append(self._spawn_worker())
            return self._workers.pop(0)

    def _replenish_async(self) -> None:
        with self._pool_lock:
            if self._closed:
                return
            if self._replenish_thread is not None and self._replenish_thread.is_alive():
                return
            thread = threading.Thread(target=self._replenish, name="sandbox-replenish",
                                      daemon=True)
            self._replenish_thread = thread
            thread.start()

    def _replenish(self) -> None:
        while True:
            with self._pool_lock:
                if self._closed or len(self._workers) >= self.pool_size:
                    return
                try:
                    worker = self._spawn_worker()
                except Exception:
                    return
                if self._closed:
                    self._retire(worker)
                    return
                self._workers.append(worker)

    def _kill_process(self, process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        if os.name == "posix":
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                try:
                    process.kill()
                except OSError:
                    pass
        else:
            try:
                process.kill()
            except OSError:
                pass
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass

    @staticmethod
    def _discard_worker_dir(directory: Path) -> None:
        shutil.rmtree(directory, ignore_errors=True)

    def _retire(self, worker: _Worker) -> None:
        """Kill (if still alive), reap and remove a worker's private directory."""
        try:
            if worker.process.stdin is not None:
                try:
                    worker.process.stdin.close()
                except OSError:
                    pass
            if worker.process.poll() is None:
                self._kill_process(worker.process)
            else:
                try:
                    worker.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._kill_process(worker.process)
        finally:
            self._discard_worker_dir(worker.directory)

    # -- public warm-up ------------------------------------------------------
    def warm_up(self) -> dict[str, Any]:
        """Trigger the one-time wasi-python module compile in a worker.

        Returns wall time, the worker's peak RSS and the package version.  It
        is never called at import time (R-005); a deploy can call it once.
        """
        ok, reason = available()
        if not ok:
            return {"ok": False, "reason": reason}
        started = time.perf_counter()
        try:
            worker = self._spawn_worker()
        except Exception as exc:
            return {"ok": False, "reason": f"{type(exc).__name__}: {exc}",
                    "elapsed_s": round(time.perf_counter() - started, 3)}
        elapsed = time.perf_counter() - started
        try:
            self._retire(worker)
        finally:
            worker.process.wait(timeout=5)
        return {
            "ok": True,
            "elapsed_s": round(elapsed, 3),
            "warm_s": worker.ready.get("warm_s"),
            "peak_rss_mib": worker.ready.get("peak_rss_mib"),
            "wasi_python": worker.ready.get("wasi_python", ""),
            "platform_guard": worker.ready.get("platform_guard", ""),
            "worker_pid": worker.pid,
        }

    # -- public run ----------------------------------------------------------
    def run(self, script: str, inputs: Iterable[str | os.PathLike[str]] | None,
            limits: Limits | None = None, approval: str = "",
            *, keep_output: bool = False) -> RunResult:
        """Run ``script`` once in a fresh guest and collect ``/out``.

        ``approval`` is the broker's approval reference (``"token"`` after a
        one-time token was consumed).  The runner refuses an empty approval so
        a direct caller cannot silently bypass the broker's token check; the
        broker remains the component that actually validates the token.
        """
        if not isinstance(script, str):
            raise TypeError("script must be a string")
        if not isinstance(approval, str) or not approval.strip():
            raise ValueError("sandbox run requires a non-empty approval reference")
        limits = Limits() if limits is None else limits
        if not isinstance(limits, Limits):
            raise TypeError("limits must be swarmbly_app.sandbox.Limits")

        script_sha256 = hashlib.sha256(script.encode("utf-8")).hexdigest()
        ok, reason = available()
        if not ok:
            return self._error_result(script_sha256, reason)

        self._prepare()
        run_id = uuid.uuid4().hex
        run_dir = self.runs_dir / run_id
        data_dir = run_dir / "data"
        out_dir = run_dir / "out"
        tmp_dir = run_dir / "tmp"
        try:
            data_dir.mkdir(parents=True, mode=0o700)
            out_dir.mkdir(mode=0o700)
            # A per-run writable scratch preopened at /tmp: openpyxl/xlsxwriter
            # and tempfile need one, while /data stays read-only and /out is
            # still the only collected output.  It is deleted with the run.
            tmp_dir.mkdir(mode=0o700)
            self._copy_inputs(inputs or [], data_dir)
            (run_dir / "script.py").write_text(script, encoding="utf-8")
            (run_dir / "limits.json").write_text(
                json.dumps(self._limits_dict(limits), sort_keys=True), encoding="utf-8")
            os.chmod(run_dir, 0o700)
        except Exception:
            shutil.rmtree(run_dir, ignore_errors=True)
            raise

        worker: _Worker | None = None
        started = 0.0
        killed = False
        payload: dict[str, Any] | None = None
        keep_this = False
        try:
            try:
                worker = self._take_worker()
                self._submit(worker, run_dir)
                if limits.fuel is not None:
                    # wasi-python compiles a second, fuel-metered module (a cold
                    # compile is several seconds on a laptop and longer on a
                    # 2-4 vCPU runner).  The worker pays that cost before it
                    # reports ``metered-warm.json``; only then does the parent
                    # start the guest's hard wall clock, so a cold metered
                    # compile can never be mistaken for an over-deadline run.
                    self._await_metered_prewarm(worker, run_dir)
            except Exception as exc:
                return self._result_from_payload(
                    None, script_sha256, 0.0, None, limits,
                    stderr=f"sandbox infrastructure error: {type(exc).__name__}: {exc}",
                    trapped="error")
            started = time.perf_counter()
            wall = limits.wall_s()
            try:
                worker.process.wait(timeout=wall)
            except subprocess.TimeoutExpired:
                killed = True
                self._kill_process(worker.process)
                try:
                    worker.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
            elapsed = time.perf_counter() - started
            result_path = run_dir / "result.json"
            if result_path.is_file():
                try:
                    payload = json.loads(result_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    payload = None
            tail = worker.stderr_tail()
            if killed:
                result = self._result_from_payload(
                    None, script_sha256, elapsed, worker.pid, limits,
                    stderr=("sandbox run exceeded its hard wall clock and was killed\n"
                            + tail).strip(),
                    trapped="deadline")
            elif payload is None:
                result = self._result_from_payload(
                    None, script_sha256, elapsed, worker.pid, limits,
                    stderr=("sandbox worker exited without a result\n" + tail).strip(),
                    trapped="error")
            else:
                result = self._result_from_payload(payload, script_sha256, elapsed,
                                                   worker.pid, limits)
                if keep_output:
                    keep_this = True
                    result = replace(result, run_id=run_id,
                                     output_dir=str(out_dir))
            return result
        finally:
            if worker is not None:
                self._retire(worker)
            if keep_this:
                # Keep only /out: the copied inputs, the scratch directory
                # and the script are not needed once the result is recorded.
                shutil.rmtree(data_dir, ignore_errors=True)
                shutil.rmtree(tmp_dir, ignore_errors=True)
                for name in ("script.py", "limits.json", "result.json",
                             "metered-warm.json"):
                    try:
                        (run_dir / name).unlink()
                    except OSError:
                        pass
            else:
                shutil.rmtree(run_dir, ignore_errors=True)
            self._replenish_async()

    # -- helpers -------------------------------------------------------------
    def _await_metered_prewarm(self, worker: _Worker, run_dir: Path) -> None:
        """Wait until the worker has paid the separate metered compile.

        The marker is written atomically after the worker's own fixed
        ``print('warm')`` call and before it starts the guest.  The pre-warm is
        bounded by ``warm_timeout_s``, not by the run's limits: it is fixed work
        on the runner's own account, not guest work.  A worker that exits first
        is left to the normal payload/exit handling.
        """
        marker = run_dir / "metered-warm.json"
        deadline = time.monotonic() + self.warm_timeout_s
        while time.monotonic() < deadline:
            if marker.is_file():
                return
            if worker.process.poll() is not None:
                return
            time.sleep(0.02)
        raise SandboxError(
            "sandbox worker did not finish the metered pre-warm within "
            f"{self.warm_timeout_s:g}s")

    @staticmethod
    def _limits_dict(limits: Limits) -> dict[str, Any]:
        return {
            "deadline_s": limits.deadline_s,
            "memory_bytes": limits.memory_bytes,
            "output_bytes": limits.output_bytes,
            "fuel": limits.fuel,
            "max_out_bytes": limits.max_out_bytes,
            "max_out_files": limits.max_out_files,
            "max_file_bytes": limits.max_file_bytes,
            "hard_grace_s": limits.hard_grace_s,
            "hard_wall_s": limits.hard_wall_s,
            "poll_s": limits.poll_s,
            "max_collect_bytes": limits.max_collect_bytes,
            "discard_over_budget": limits.discard_over_budget,
        }

    @staticmethod
    def _submit(worker: _Worker, run_dir: Path) -> None:
        if worker.process.stdin is None:
            raise SandboxError("sandbox worker has no control pipe")
        try:
            worker.process.stdin.write((str(run_dir) + "\n").encode("utf-8"))
            worker.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise SandboxError(f"sandbox worker is not accepting jobs: {exc}") from exc

    @staticmethod
    def _copy_inputs(inputs: Iterable[str | os.PathLike[str]], data_dir: Path) -> None:
        seen: set[str] = set()
        for item in inputs:
            source = Path(item).expanduser()
            try:
                resolved = source.resolve(strict=True)
                info = resolved.lstat()
            except OSError as exc:
                raise ValueError(f"input {source} cannot be read: {exc}") from exc
            if not stat.S_ISREG(info.st_mode):
                raise ValueError(f"input {source} is not a regular file")
            name = resolved.name
            if not name or name in seen:
                raise ValueError(f"duplicate or empty input name: {name!r}")
            seen.add(name)
            destination = data_dir / name
            fd_in = os.open(resolved, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            try:
                fd_out = os.open(destination,
                                 os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                try:
                    with os.fdopen(fd_in, "rb", closefd=False) as src, \
                            os.fdopen(fd_out, "wb", closefd=False) as dst:
                        shutil.copyfileobj(src, dst, MIB)
                finally:
                    os.close(fd_out)
            finally:
                os.close(fd_in)

    @staticmethod
    def _result_from_payload(payload: dict[str, Any] | None, script_sha256: str,
                             elapsed: float, worker_pid: int | None, limits: Limits,
                             *, stderr: str = "", trapped: str | None = None) -> RunResult:
        if payload is None:
            return RunResult(
                ok=False, stdout="", stderr=stderr, files=[],
                files_partial=False,
                trapped=trapped or "error", elapsed_s=round(elapsed, 3),
                script_sha256=script_sha256,
                platform_guard="watchdog" if os.name == "nt" else "rlimit+watchdog",
                worker_pid=worker_pid)
        return RunResult(
            ok=bool(payload.get("ok")),
            stdout=str(payload.get("stdout") or ""),
            stderr=str(payload.get("stderr") or ""),
            files=list(payload.get("files") or []),
            files_partial=bool(payload.get("files_partial")),
            trapped=payload.get("trapped"),
            elapsed_s=round(elapsed, 3),
            script_sha256=script_sha256,
            platform_guard=str(payload.get("platform_guard") or "watchdog"),
            exit_code=payload.get("exit_code"),
            truncated=list(payload.get("truncated") or []),
            worker_pid=worker_pid if worker_pid is not None else payload.get("worker_pid"),
            fuel_used=payload.get("fuel_used"),
            disk_guard=payload.get("disk_guard"),
            max_out_bytes_seen=int(payload.get("max_out_bytes_seen") or 0),
            max_out_files_seen=int(payload.get("max_out_files_seen") or 0),
            rejected_entries=int(payload.get("rejected_entries") or 0),
            collection_truncated=bool(payload.get("collection_truncated")),
            hard_file_cap_bytes=payload.get("hard_file_cap_bytes"),
        )

    @staticmethod
    def _error_result(script_sha256: str, reason: str) -> RunResult:
        return RunResult(ok=False, stdout="", stderr=reason, files=[],
                         files_partial=False, trapped="error", elapsed_s=0.0,
                         script_sha256=script_sha256,
                         platform_guard="watchdog" if os.name == "nt" else "rlimit+watchdog")

    def output_dir_for(self, run_id: str) -> Path | None:
        """The retained ``/out`` of one run, or ``None`` for an invalid id."""
        if not isinstance(run_id, str) or not re.fullmatch(r"[0-9a-f]{32}", run_id):
            return None
        return self.runs_dir / run_id / "out"

    # -- lifecycle -----------------------------------------------------------
    def close(self) -> None:
        with self._pool_lock:
            if self._closed:
                return
            self._closed = True
            workers, self._workers = self._workers, []
            thread = self._replenish_thread
        for worker in workers:
            self._retire(worker)
        if thread is not None:
            thread.join(timeout=10)

    def __enter__(self) -> "SandboxRunner":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()
