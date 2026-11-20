"""Disposable worker process that executes exactly one sandbox run.

The parent starts this module with ``python -m swarmbly_app.sandbox.worker``.
It pins ``TMPDIR`` and the wasi-python cache inside the app-owned root, makes
two unguarded guest calls to pay the one-time stdlib copy/compile, writes a
ready file, waits for one job directory on stdin, runs the guest, writes
``result.json`` and exits.  The parent kills the whole process group if the
hard wall clock expires, so a broken worker can never outlive a run.

This module is the *only* place that imports ``wasi_python``; the app package
and :mod:`swarmbly_app.sandbox` import without the optional extra.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

MIB = 1024 * 1024


# --------------------------------------------------------------------------- helpers


def _write_json(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _regular_stats(path: Path) -> tuple[int, int]:
    """(logical bytes, allocated bytes) of one path, never following a symlink."""
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        return 0, 0
    return st.st_size, getattr(st, "st_blocks", 0) * 512


def _out_stats(out_dir: Path) -> tuple[int, int, int]:
    """(logical bytes, allocated bytes, entry count), never through a symlink."""
    logical = allocated = entries = 0
    stack = [Path(out_dir)]
    while stack:
        current = stack.pop()
        try:
            listing = list(os.scandir(current))
        except OSError:
            continue
        for entry in listing:
            try:
                if entry.is_symlink():
                    entries += 1
                elif entry.is_dir(follow_symlinks=False):
                    entries += 1
                    stack.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    size, blocks = _regular_stats(Path(entry.path))
                    logical += size
                    allocated += blocks
                    entries += 1
            except OSError:
                continue
    return logical, allocated, entries


def _discard_bytes(out_dir: Path, max_bytes: int | None) -> list[dict[str, Any]]:
    """Delete the largest regular files until the total fits; never follow links."""
    if max_bytes is None:
        return []
    found: list[tuple[int, Path]] = []
    stack = [Path(out_dir)]
    while stack:
        current = stack.pop()
        try:
            listing = list(os.scandir(current))
        except OSError:
            continue
        for entry in listing:
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    stack.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    found.append((_regular_stats(Path(entry.path))[0], Path(entry.path)))
            except OSError:
                continue
    total = sum(size for size, _ in found)
    removed: list[dict[str, Any]] = []
    for size, path in sorted(found, reverse=True):
        if total <= max_bytes:
            break
        try:
            path.unlink()
        except OSError:
            continue
        total -= size
        removed.append({"name": path.relative_to(out_dir).as_posix(), "size": size})
    return removed


def _discard_files(out_dir: Path, max_files: int | None) -> list[str]:
    """Delete regular files until the entry count fits; never follow links."""
    if max_files is None:
        return []
    found: list[Path] = []
    stack = [Path(out_dir)]
    while stack:
        current = stack.pop()
        try:
            listing = list(os.scandir(current))
        except OSError:
            continue
        for entry in listing:
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    stack.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    found.append(Path(entry.path))
            except OSError:
                continue
    removed: list[str] = []
    for path in reversed(sorted(found)):
        try:
            path.unlink()
        except OSError:
            continue
        removed.append(path.relative_to(out_dir).as_posix())
        if _out_stats(out_dir)[2] <= max_files:
            break
    return removed


def _hashed(path: Path) -> str | None:
    """SHA-256 of a regular file opened with O_NOFOLLOW; None if it is not one."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return None
        import hashlib

        digest = hashlib.sha256()
        with os.fdopen(fd, "rb", closefd=False) as handle:
            for block in iter(lambda: handle.read(MIB), b""):
                digest.update(block)
        return digest.hexdigest()
    finally:
        os.close(fd)


def _collect(out_dir: Path, max_total: int | None) -> tuple[list[dict[str, Any]], int, bool]:
    """Collect regular files from ``/out`` without following a single link.

    Symlinks, directories, pipes, devices and anything that resolves outside
    ``out_dir`` are rejected (counted in the second return value).  Collected
    bytes are capped by ``max_total``; the third value says whether the cap
    stopped collection.
    """
    files: list[dict[str, Any]] = []
    rejected = 0
    truncated = False
    total = 0
    root = Path(out_dir).resolve()

    def walk(directory: Path) -> None:
        nonlocal rejected, truncated, total
        try:
            listing = sorted(os.scandir(directory), key=lambda e: e.name)
        except OSError:
            return
        for entry in listing:
            path = directory / entry.name
            try:
                if entry.is_symlink():
                    rejected += 1
                    continue
                if entry.is_dir(follow_symlinks=False):
                    walk(path)
                    continue
                if not entry.is_file(follow_symlinks=False):
                    rejected += 1
                    continue
                try:
                    resolved = path.resolve(strict=True)
                except OSError:
                    rejected += 1
                    continue
                if not resolved.is_relative_to(root):
                    rejected += 1
                    continue
                size, _ = _regular_stats(path)
                if max_total is not None and total + size > max_total:
                    truncated = True
                    rejected += 1
                    continue
                digest = _hashed(path)
                if digest is None:
                    rejected += 1
                    continue
                files.append({"name": path.relative_to(root).as_posix(),
                              "size": size, "sha256": digest})
                total += size
            except OSError:
                rejected += 1

    walk(root)
    return files, rejected, truncated


class _Watchdog(threading.Thread):
    """Soft guard on ``/out`` size, file count and the hard wall clock."""

    daemon = True

    def __init__(self, out_dir: Path, limits: Any, cancel: threading.Event) -> None:
        super().__init__(name="swarmbly-sandbox-watchdog")
        self.out_dir = Path(out_dir)
        self.limits = limits
        self.cancel = cancel
        self._halt = threading.Event()
        self._t0 = time.perf_counter()
        self.reason: str | None = None
        self.max_logical = 0
        self.max_allocated = 0
        self.max_entries = 0

    def run(self) -> None:
        poll = max(0.005, float(self.limits.poll_s))
        while not self._halt.wait(poll):
            self._sample()
            if self.reason is not None:
                self.cancel.set()
                break
        # Keep measuring while wasi-python stops (about 50 ms).
        while not self._halt.wait(0.002):
            self._sample()

    def _sample(self) -> None:
        logical, allocated, entries = _out_stats(self.out_dir)
        self.max_logical = max(self.max_logical, logical)
        self.max_allocated = max(self.max_allocated, allocated)
        self.max_entries = max(self.max_entries, entries)
        if self.reason is not None:
            return
        if (self.limits.max_out_bytes is not None
                and logical > self.limits.max_out_bytes):
            self.reason = "out_bytes"
        elif (self.limits.max_out_files is not None
              and entries > self.limits.max_out_files):
            self.reason = "out_files"
        elif (self.limits.deadline_s is not None
              and time.perf_counter() - self._t0
              > float(self.limits.deadline_s) + float(self.limits.hard_grace_s)):
            self.reason = "wall"

    def stop(self) -> None:
        self._halt.set()
        self.join(timeout=5)


class _RssSampler(threading.Thread):
    daemon = True

    def __init__(self) -> None:
        super().__init__(name="swarmbly-sandbox-rss")
        self._halt = threading.Event()
        self.peak = 0

    def run(self) -> None:
        try:
            import psutil

            process = psutil.Process()
            while not self._halt.wait(0.02):
                self.peak = max(self.peak, process.memory_info().rss)
        except Exception:
            return

    def stop(self) -> int:
        self._halt.set()
        self.join(timeout=2)
        return self.peak


# --------------------------------------------------------------------------- guest run


def _trap_reason(done: Any, watchdog: _Watchdog, stderr: str,
                 guest_error: str | None) -> str | None:
    if watchdog.reason == "out_bytes":
        return "disk"
    if watchdog.reason == "out_files":
        return "files"
    if watchdog.reason == "wall":
        return "deadline"
    if guest_error is not None:
        return "error"
    if done is None:
        return "error"
    trapped = done.trapped
    if trapped == "deadline":
        return "deadline"
    lowered = (stderr or "").lower()
    if trapped and "memory" in str(trapped).lower():
        return "memory"
    if "memoryerror" in lowered or "out of memory" in lowered or "cannot allocate" in lowered:
        return "memory"
    if "file too large" in lowered or "efbig" in lowered or "errno 27" in lowered:
        return "disk"
    if done.truncated:
        return "output"
    if trapped:
        return "error"
    if done.exit_code not in (0, None):
        return "error"
    return None


def _run_guest(script: str, data_dir: Path, out_dir: Path, limits: Any,
               wasi: Any, cache_dir: Path, platform_guard: str,
               script_sha256: str) -> dict[str, Any]:
    from wasi_python import Grant

    cancel = threading.Event()
    watchdog = _Watchdog(out_dir, limits, cancel)
    watchdog.start()
    started = time.perf_counter()
    done = None
    guest_error: str | None = None
    try:
        done = wasi.run(
            ["-c", script],
            root=False,
            grants=[Grant(data_dir, "/data"),
                    Grant(out_dir, "/out", writable=True)],
            env={"HOME": "/nonexistent-home"},
            cache_dir=cache_dir,
            deadline_s=limits.deadline_s,
            memory_bytes=limits.memory_bytes,
            output_bytes=limits.output_bytes,
            fuel=limits.fuel,
            cancel=cancel,
        )
    except BaseException as exc:  # wasi-python may raise for a host-side fault
        guest_error = f"{type(exc).__name__}: {exc}"
    finally:
        elapsed = time.perf_counter() - started
        watchdog.stop()
        # One final sample after the guest ended, so a burst that finished
        # between two polls still trips the size/count guard.
        watchdog._sample()

    stdout = done.stdout.decode("utf-8", "replace") if done is not None else ""
    stderr = done.stderr.decode("utf-8", "replace") if done is not None else ""
    if guest_error:
        stderr = (stderr + "\n" + guest_error).strip()

    discarded_bytes: list[dict[str, Any]] = []
    discarded_files: list[str] = []
    if watchdog.reason == "out_bytes" and limits.discard_over_budget:
        discarded_bytes = _discard_bytes(out_dir, limits.max_out_bytes)
    elif watchdog.reason == "out_files" and limits.discard_over_budget:
        discarded_files = _discard_files(out_dir, limits.max_out_files)

    max_total = limits.max_out_bytes
    if max_total is None:
        max_total = limits.max_collect_bytes
    files, rejected, collection_truncated = _collect(out_dir, max_total)
    trapped = _trap_reason(done, watchdog, stderr, guest_error)
    ok = trapped is None and done is not None and done.exit_code == 0

    return {
        "ok": ok,
        "stdout": stdout,
        "stderr": stderr,
        "files": files,
        "trapped": trapped,
        "elapsed_s": round(elapsed, 3),
        "script_sha256": script_sha256,
        "platform_guard": platform_guard,
        "exit_code": done.exit_code if done is not None else None,
        "truncated": list(done.truncated) if done is not None else [],
        "fuel_used": done.fuel_used if done is not None else None,
        "disk_guard": watchdog.reason,
        "max_out_bytes_seen": watchdog.max_logical,
        "max_out_allocated_seen": watchdog.max_allocated,
        "max_out_files_seen": watchdog.max_entries,
        "discarded": discarded_bytes,
        "discarded_files": discarded_files,
        "rejected_entries": rejected,
        "collection_truncated": collection_truncated,
        "hard_file_cap_bytes": limits.max_file_bytes if "rlimit" in platform_guard else None,
        "worker_pid": os.getpid(),
    }


# --------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    import argparse
    import hashlib

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--root", required=True)
    parser.add_argument("--worker-dir", required=True)
    parser.add_argument("--ready-file", required=True)
    args = parser.parse_args(argv)

    root = Path(args.root)
    worker_dir = Path(args.worker_dir)
    ready_file = Path(args.ready_file)
    cache_dir = root / "cache" / "wasi-python"
    tmp_dir = worker_dir / "tmp"
    for path in (root, cache_dir, worker_dir, tmp_dir):
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass
    # Pin wasi-python's private copies (about 70 MB of stdlib zip, an empty HOME,
    # matplotlib data) inside the app-owned tree, before importing the package.
    os.environ["TMPDIR"] = str(tmp_dir)
    tempfile.tempdir = str(tmp_dir)

    status: dict[str, Any] = {"ok": False, "pid": os.getpid(),
                              "platform_guard": "watchdog"}
    try:
        import wasi_python as wasi
    except Exception as exc:
        status["error"] = f"wasi-python is not importable: {type(exc).__name__}: {exc}"
        _write_json(ready_file, status)
        return 2

    data_dir = tmp_dir / "warm-data"
    data_dir.mkdir(parents=True, exist_ok=True)
    sampler = _RssSampler()
    sampler.start()
    warm_started = time.perf_counter()
    try:
        # Two plain calls: the first copies the stdlib zip and compiles the
        # module, the second stabilises the private-directory stamp (spike §5/§6).
        for index in range(2):
            out_dir = tmp_dir / f"warm-out-{index}"
            out_dir.mkdir(parents=True, exist_ok=True)
            warm = wasi.run(
                ["-c", "print('warm')"],
                root=False,
                grants=[wasi.Grant(data_dir, "/data"),
                        wasi.Grant(out_dir, "/out", writable=True)],
                env={"HOME": "/nonexistent-home"},
                cache_dir=cache_dir,
                deadline_s=120,
                memory_bytes=512 * MIB,
                output_bytes=1 * MIB,
            )
            if warm.trapped is not None or warm.exit_code != 0:
                raise RuntimeError(
                    f"warm-up call {index + 1} failed: trapped={warm.trapped!r} "
                    f"stderr={warm.stderr[-300:]!r}")
    except Exception as exc:
        status["error"] = f"warm-up failed: {type(exc).__name__}: {exc}"
        status["peak_rss_mib"] = round(sampler.stop() / MIB, 1)
        _write_json(ready_file, status)
        return 3

    status.update({
        "ok": True,
        "warm_s": round(time.perf_counter() - warm_started, 3),
        "peak_rss_mib": round(sampler.stop() / MIB, 1),
        "wasi_python": getattr(wasi, "__version__", ""),
    })
    _write_json(ready_file, status)

    try:
        line = sys.stdin.readline()
    except Exception:
        return 0
    if not line.strip():
        return 0
    job_dir = Path(line.strip())
    result_file = job_dir / "result.json"
    try:
        limits_data = json.loads((job_dir / "limits.json").read_text(encoding="utf-8"))
        from .limits import Limits

        limits = Limits(**limits_data)
        script = (job_dir / "script.py").read_text(encoding="utf-8")
        script_sha256 = hashlib.sha256(script.encode("utf-8")).hexdigest()
        data_dir = job_dir / "data"
        out_dir = job_dir / "out"
    except Exception as exc:
        _write_json(result_file, {
            "ok": False, "stdout": "", "stderr": f"bad job: {type(exc).__name__}: {exc}",
            "files": [], "trapped": "error", "elapsed_s": 0.0,
            "script_sha256": "", "platform_guard": status["platform_guard"],
            "exit_code": None, "truncated": [], "fuel_used": None,
            "disk_guard": None, "max_out_bytes_seen": 0,
            "max_out_allocated_seen": 0, "max_out_files_seen": 0,
            "discarded": [], "discarded_files": [], "rejected_entries": 0,
            "collection_truncated": False, "hard_file_cap_bytes": None,
            "worker_pid": os.getpid(),
        })
        return 4

    platform_guard = status["platform_guard"]
    if limits.fuel is not None:
        # A metered engine is a separate compile in wasi-python (spike §7.2):
        # pay it here, before RLIMIT_FSIZE, and never inside the measured run.
        # The parent waits for ``metered-warm.json`` before it starts the hard
        # wall clock, so a cold compile is not charged to the guest either.
        metered_started = time.perf_counter()
        metered_error: str | None = None
        try:
            metered_out = tmp_dir / "metered-warm-out"
            metered_out.mkdir(parents=True, exist_ok=True)
            wasi.run(["-c", "print('warm')"], root=False,
                     grants=[wasi.Grant(tmp_dir / "warm-data", "/data"),
                             wasi.Grant(metered_out, "/out", writable=True)],
                     env={"HOME": "/nonexistent-home"}, cache_dir=cache_dir,
                     deadline_s=120, memory_bytes=512 * MIB,
                     output_bytes=1 * MIB, fuel=10_000_000)
        except Exception as exc:
            # A pre-warm failure is not fatal: the guest run reports whatever
            # the metered engine actually does.  The marker still releases the
            # parent so the hard wall covers the guest, not the compile.
            metered_error = f"{type(exc).__name__}: {exc}"
        _write_json(job_dir / "metered-warm.json", {
            "ok": metered_error is None,
            "elapsed_s": round(time.perf_counter() - metered_started, 3),
            "error": metered_error,
        })

    if (os.name == "posix" and limits.max_file_bytes is not None):
        try:
            import resource
            import signal

            # The kernel returns EFBIG instead of killing the worker.
            signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
            resource.setrlimit(resource.RLIMIT_FSIZE,
                               (limits.max_file_bytes, limits.max_file_bytes))
            platform_guard = "rlimit+watchdog"
        except Exception:
            # No RLIMIT_FSIZE here: the watchdog is the only disk guard.
            platform_guard = "watchdog"

    result = _run_guest(script, data_dir, out_dir, limits, wasi, cache_dir,
                        platform_guard, script_sha256)
    _write_json(result_file, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
