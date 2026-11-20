"""Recipe-5 sandbox checks against *this* runner (T7.1).

These are the T7.0 spike's ten adversarial/functional checks, adapted to the
worker-pool runner: no network, read-only ``/data``, no writes outside
``/out`` (including symlink collection), no processes/threads/ctypes, deadline,
memory, output, disk (hard on POSIX, watchdog everywhere) and pandas/openpyxl.
The last one exercises ``warm_up`` and the warm latency (R-005).

Run with the optional extra::

    python -m pytest -m sandbox tests/test_sandbox_runner.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import socket
import stat
import sys
import textwrap
import threading
import time
import zipfile
from collections import defaultdict
from pathlib import Path

import pytest

from swarmbly_app.sandbox import Limits, SandboxRunner, available

pytestmark = [
    pytest.mark.sandbox,
    pytest.mark.skipif(not available()[0], reason="the [sandbox] extra is not installed"),
]

MIB = 1024 * 1024


# --------------------------------------------------------------------------- fixtures


@pytest.fixture(scope="session")
def sandbox_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One app-owned root for the whole session.

    The wasmtime ``.cwasm`` file is the expensive part; paying it once per
    session keeps CI time bounded.  Sharing it does not share user data: every
    run still gets a fresh ``runs/<uuid>/data`` and ``runs/<uuid>/out``, and
    the cache is a separate directory that is never granted to the guest.
    """
    return tmp_path_factory.mktemp("sandbox-root")


@pytest.fixture(scope="session", autouse=True)
def _warm_cache(sandbox_root: Path) -> None:
    runner = SandboxRunner(sandbox_root)
    try:
        warmed = runner.warm_up()
        assert warmed["ok"], warmed
    finally:
        runner.close()


@pytest.fixture()
def runner(sandbox_root: Path):
    instance = SandboxRunner(sandbox_root, pool_size=1)
    try:
        yield instance
    finally:
        instance.close()


# --------------------------------------------------------------------------- helpers


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(MIB), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_results(stdout: str) -> list[dict]:
    marker = "RESULTS="
    assert marker in stdout, f"guest did not report results:\n{stdout}"
    raw = stdout.split(marker, 1)[1].strip().splitlines()[0]
    return [{"name": row[0], "status": row[1],
             "exc_type": row[2] if len(row) > 2 else None,
             "detail": row[3] if len(row) > 3 else None}
            for row in json.loads(raw)]


def assert_all_refused(rows: list[dict], label: str) -> None:
    ok = [row for row in rows if row["status"] == "OK"]
    assert not ok, f"{label}: these attempts succeeded but must not: {ok}"


def rows_debug(rows: list[dict]) -> str:
    """The guest's own report, attached to every test_03 failure message."""
    return "guest RESULTS rows:\n" + json.dumps(rows, indent=2, ensure_ascii=False)


def walk_output_links(out_dir: Path) -> list[tuple[str, str, Path]]:
    """Every symlink under ``out_dir`` as (name, target, resolved target).

    The walk uses ``os.lstat`` and never follows a link, so it is a host-side
    view of what the guest actually left in ``/out``, independent of the
    guest's RESULTS rows.  ``resolve(strict=False)`` follows the link text
    without requiring the target to exist.
    """
    root = Path(out_dir)
    found: list[tuple[str, str, Path]] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in (*dirnames, *filenames):
            path = Path(dirpath) / name
            info = os.lstat(path)
            if not stat.S_ISLNK(info.st_mode):
                continue
            target = os.readlink(path)
            resolved = (path.parent / target).resolve(strict=False)
            found.append((path.relative_to(root).as_posix(), target, resolved))
    return found


class Canary:
    """A localhost TCP server that records every accepted connection."""

    def __init__(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.sock.settimeout(0.2)
        self.port = self.sock.getsockname()[1]
        self.connections = 0
        self._halt = threading.Event()
        self.thread = threading.Thread(target=self._serve, name="tcp-canary", daemon=True)

    def _serve(self) -> None:
        while not self._halt.is_set():
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            self.connections += 1
            try:
                conn.recv(1024)
                conn.sendall(b"HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\nok")
            except OSError:
                pass
            finally:
                conn.close()

    def start(self) -> "Canary":
        self.thread.start()
        return self

    def stop(self) -> None:
        self._halt.set()
        try:
            self.sock.close()
        except OSError:
            pass
        self.thread.join(timeout=3)


def write_xlsx(path: Path, rows: list[list[object]]) -> None:
    """Minimal valid .xlsx with only the stdlib (inline strings, numeric cells)."""

    def col(index: int) -> str:
        return chr(ord("A") + index)

    cells = []
    for r, row in enumerate(rows, start=1):
        parts = []
        for c, value in enumerate(row):
            ref = f"{col(c)}{r}"
            if isinstance(value, str):
                parts.append(f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>')
            else:
                parts.append(f'<c r="{ref}"><v>{value}</v></c>')
        cells.append(f'<row r="{r}">' + "".join(parts) + "</row>")
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>" + "".join(cells) + "</sheetData></worksheet>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)


# --------------------------------------------------------------------------- 1. network


def test_01_no_network(runner: SandboxRunner, tmp_path: Path) -> None:
    canary = Canary().start()
    data = tmp_path / "input.csv"
    data.write_text("a,b\n1,2\n")
    script = textwrap.dedent(
        """
        import json, socket, urllib.request

        out = []
        def attempt(name, fn):
            try:
                out.append([name, "OK", repr(fn())[:80]])
            except BaseException as exc:
                out.append([name, "ERR", type(exc).__name__, str(exc)[:180]])

        attempt("socket.create_connection", lambda: socket.create_connection(("127.0.0.1", PORT), timeout=2))
        attempt("urllib canary", lambda: urllib.request.urlopen("http://127.0.0.1:PORT/", timeout=2))
        attempt("urllib example.com", lambda: urllib.request.urlopen("http://example.com", timeout=3))
        attempt("getaddrinfo", lambda: socket.getaddrinfo("example.com", 80))
        attempt("ssl import", lambda: __import__("ssl"))
        attempt("raw socket()", lambda: socket.socket())
        print("RESULTS=" + json.dumps(out))
        """
    ).replace("PORT", str(canary.port))
    try:
        result = runner.run(script, [data], Limits(deadline_s=40), "pytest")
    finally:
        canary.stop()

    rows = parse_results(result.stdout)
    assert_all_refused(rows, "network")
    assert canary.connections == 0, f"canary saw {canary.connections} connection(s)"


# --------------------------------------------------------------------------- 2. data read-only


def test_02_data_is_read_only_and_not_linked(runner: SandboxRunner, tmp_path: Path) -> None:
    target = tmp_path / "input.csv"
    target.write_text("region,amount\nnorth,10\nsouth,20\n")
    before = sha256(target)
    mode_before = stat.S_IMODE(target.stat().st_mode)
    host_inode = target.stat().st_ino

    script = textwrap.dedent(
        """
        import json, os

        D = "/data/input.csv"
        out = []
        def attempt(name, fn):
            try:
                fn()
                out.append([name, "OK"])
            except BaseException as exc:
                out.append([name, "ERR", type(exc).__name__, getattr(exc, "errno", None)])

        attempt("append", lambda: open(D, "a").write("x"))
        attempt("write", lambda: open(D, "w").write("x"))
        attempt("r+", lambda: open(D, "r+").write("x"))
        attempt("truncate", lambda: os.truncate(D, 0))
        attempt("remove", lambda: os.remove(D))
        attempt("rename to /out", lambda: os.rename(D, "/out/stolen.csv"))
        attempt("rename within data", lambda: os.rename(D, "/data/other.csv"))
        attempt("chmod", lambda: os.chmod(D, 0o777))
        attempt("mkdir in data", lambda: os.mkdir("/data/newdir"))
        attempt("unlink", lambda: os.unlink(D))
        print("INODE=" + str(os.stat(D).st_ino))
        print("RESULTS=" + json.dumps(out))
        """
    )
    result = runner.run(script, [target], Limits(deadline_s=30), "pytest")
    after = sha256(target)
    mode_after = stat.S_IMODE(target.stat().st_mode)
    rows = parse_results(result.stdout)
    guest_inode = int(result.stdout.split("INODE=", 1)[1].splitlines()[0])

    # chmod is the one call the guest can "win": WASI has no chmod and the host
    # mode is untouched.  Everything that would change the file must fail.
    assert_all_refused([row for row in rows if row["name"] != "chmod"], "data read-only")
    assert mode_after == mode_before
    assert after == before, "the host input changed"
    assert guest_inode != host_inode, "the guest saw a link to the host input, not a copy"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["input.csv"]


# --------------------------------------------------------------------------- 3. no writes outside /out


def test_03_no_writes_outside_out_and_symlinks_rejected(
        runner: SandboxRunner, tmp_path: Path) -> None:
    data = tmp_path / "input.csv"
    data.write_text("a\n1\n")
    canary_dir = tmp_path / "host_canary"
    canary_dir.mkdir()
    secret = canary_dir / "secret.txt"
    secret.write_text("HOST-SECRET")
    secret_before = sha256(secret)
    host_target = canary_dir / "pwned.txt"

    script = textwrap.dedent(
        """
        import json, os

        HOST_TARGET = __HOST_TARGET__
        HOST_TARGET2 = __HOST_TARGET2__
        HOST_SECRET = __HOST_SECRET__
        HOST_DIR = __HOST_DIR__
        out = []
        def attempt(name, fn):
            try:
                fn()
                out.append([name, "OK"])
            except BaseException as exc:
                out.append([name, "ERR", type(exc).__name__, getattr(exc, "errno", None)])

        targets = [
            "/tmp/pwned.txt", "/var/tmp/pwned.txt", "/etc/pwned.txt",
            "/root/pwned.txt", "/home/user/pwned.txt",
            "../pwned.txt", "../../pwned.txt", "/out/../pwned.txt",
            HOST_TARGET, HOST_TARGET2,
        ]
        for t in targets:
            attempt("write " + t, lambda t=t: open(t, "w").write("pwned"))
        attempt("mkdir /home/user", lambda: os.makedirs("/home/user", exist_ok=True))
        attempt("read /etc/passwd", lambda: open("/etc/passwd").read())
        attempt("read host secret", lambda: open(HOST_SECRET).read())
        attempt("listdir host canary", lambda: os.listdir(HOST_DIR))

        # A relative symlink can be created in /out, but neither the guest nor
        # the host collector may follow it.
        attempt("symlink abs host", lambda: os.symlink(HOST_TARGET, "/out/escape_abs"))
        attempt("symlink to /data", lambda: os.symlink("/data/input.csv", "/out/data_link"))
        attempt("symlink rel ../../etc", lambda: os.symlink("../../../../etc/passwd", "/out/escape_rel"))
        attempt("read through rel symlink", lambda: open("/out/escape_rel").read())
        attempt("write through rel symlink", lambda: open("/out/escape_rel", "w").write("x"))
        attempt("mkdir /out/sub", lambda: os.mkdir("/out/sub"))
        attempt("symlink nested ../../etc", lambda: os.symlink("../../../../../etc", "/out/sub/etc"))
        attempt("read nested symlink", lambda: open("/out/sub/etc/passwd").read())
        attempt("hardlink from /data", lambda: os.link("/data/input.csv", "/out/hardlink"))
        attempt("write /out/ok.txt", lambda: open("/out/ok.txt", "w").write("fine"))
        print("RESULTS=" + json.dumps(out))
        """
    ).replace("__HOST_SECRET__", json.dumps(str(secret))) \
        .replace("__HOST_DIR__", json.dumps(str(canary_dir))) \
        .replace("__HOST_TARGET2__", json.dumps(str(host_target.with_name("pwned2.txt")))) \
        .replace("__HOST_TARGET__", json.dumps(str(host_target)))

    result = runner.run(script, [data], Limits(deadline_s=30), "pytest",
                        keep_output=True)
    rows = parse_results(result.stdout)
    debug = rows_debug(rows)
    by_name = {row["name"]: row for row in rows}
    required = ("symlink abs host", "symlink to /data", "symlink rel ../../etc",
                "read through rel symlink", "write through rel symlink",
                "symlink nested ../../etc", "read nested symlink")
    for name in required:
        assert name in by_name, f"missing guest attempt {name!r}\n{debug}"
    # WASI's POSIX contract does not require the target of a symlink to exist;
    # wasmtime's Windows implementation does (crates/wasi/src/filesystem/
    # windows.rs::symlink stats the target before it creates the link).  On
    # Windows the link therefore fails and the next "write through" call
    # creates a plain regular file inside /out, which is contained, not an
    # escape.
    rel_created = by_name["symlink rel ../../etc"]["status"] == "OK"

    allowed = {
        "mkdir /out/sub",
        "write /out/ok.txt",
        "symlink rel ../../etc",
        "symlink nested ../../etc",
    }
    if not rel_created:
        allowed.add("write through rel symlink")
    unexpected = [row for row in rows
                  if row["status"] == "OK" and row["name"] not in allowed]
    assert not unexpected, (
        f"these attempts succeeded but must not: {unexpected}\n{debug}")

    assert by_name["read through rel symlink"]["status"] == "ERR", debug
    assert by_name["read nested symlink"]["status"] == "ERR", debug
    write_rel = by_name["write through rel symlink"]
    if rel_created:
        assert write_rel["status"] == "ERR", (
            "the relative symlink exists, so writing through it must be "
            f"refused\n{debug}")
    else:
        assert write_rel["status"] == "OK", (
            "the guest could not create the relative symlink, so the plain "
            f"write inside /out should have succeeded\n{debug}")

    assert sha256(secret) == secret_before, debug
    assert not host_target.exists(), debug
    assert not host_target.with_name("pwned2.txt").exists(), debug

    # Only regular files are collected; every symlink is rejected and never
    # hashed or followed.
    names = {item["name"] for item in result.files}
    files = {item["name"]: item for item in result.files}
    assert "ok.txt" in names, debug
    assert "escape_abs" not in names and "data_link" not in names, debug
    assert "sub/etc" not in names, debug
    if rel_created:
        assert "escape_rel" not in names, (
            f"the escaping symlink was collected as output\n{debug}")
        assert result.rejected_entries >= 2, debug
    else:
        # Windows: no link was created, so escape_rel is a regular file in /out
        # and the collector accepts it like any other output.
        assert "escape_rel" in names, (
            f"the contained regular file was not collected\n{debug}")
        assert files["escape_rel"]["size"] == 1, debug

    # Host-side view, independent of the guest's RESULTS rows.  lstat sees what
    # is really in /out; the collector must never accept a link, and a link
    # that points outside the run's output must never have been followed into
    # a protected host path.
    assert result.output_dir, f"the run did not keep its output\n{debug}"
    out_dir = Path(result.output_dir)
    out_root = out_dir.resolve()
    assert (out_dir / "ok.txt").read_text(encoding="utf-8") == "fine", debug
    links = walk_output_links(out_dir)
    links_by_name = {name: (target, resolved)
                     for name, target, resolved in links}
    link_rows = {
        "escape_abs": "symlink abs host",
        "data_link": "symlink to /data",
        "escape_rel": "symlink rel ../../etc",
        "sub/etc": "symlink nested ../../etc",
    }
    collected = {item["name"] for item in result.files}
    protected = {host_target.resolve(), host_target.with_name("pwned2.txt").resolve(),
                 secret.resolve()}
    for name, target, resolved in links:
        assert name in link_rows, (
            f"the host tree has an unexpected symlink {name!r} -> {target!r}\n"
            f"{debug}")
        assert by_name[link_rows[name]]["status"] == "OK", (
            f"the host tree has symlink {name!r}, but the guest reported "
            f"{link_rows[name]!r} as {by_name[link_rows[name]]['status']}\n{debug}")
        assert name not in collected, (
            f"the collector accepted symlink {name!r} -> {target!r}\n{debug}")
        if not resolved.is_relative_to(out_root):
            assert resolved not in protected, (
                f"an output symlink reached protected host path {resolved}\n{debug}")
    # A row that says it created a link must have a link in the host tree; a
    # reported ERR must not hide one.
    for link_name, row_name in link_rows.items():
        if by_name[row_name]["status"] == "OK":
            assert link_name in links_by_name, (
                f"the guest reported {row_name!r} OK, but {link_name!r} is "
                f"not a link in /out\n{debug}")
    if rel_created:
        assert "escape_rel" in links_by_name, (
            f"the guest reported a link but the host tree has none\n{debug}")
        _, rel_resolved = links_by_name["escape_rel"]
        assert not rel_resolved.is_relative_to(out_root), (
            f"the relative link unexpectedly stayed inside /out: "
            f"{links_by_name['escape_rel']}\n{debug}")
        assert stat.S_ISLNK(os.lstat(out_dir / "escape_rel").st_mode), debug
    else:
        # No guest link was created, so the host tree must not contain one
        # pointing outside either.
        escaping = [link for link in links if not link[2].is_relative_to(out_root)]
        assert not escaping, (
            "the guest reported no relative symlink, yet the output tree has "
            f"a link pointing outside it: {escaping}\n{debug}")
        rel = out_dir / "escape_rel"
        assert rel.is_file() and not rel.is_symlink(), (
            f"escape_rel is not a regular file inside /out: {rel}\n{debug}")
        assert rel.read_bytes() == b"x", debug
    assert all("sha256" in item and "size" in item for item in result.files)


# --------------------------------------------------------------------------- 4. process/thread/native


def test_04_no_process_thread_or_native_escape(runner: SandboxRunner,
                                               tmp_path: Path) -> None:
    import psutil

    data = tmp_path / "input.csv"
    data.write_text("a\n1\n")
    script = textwrap.dedent(
        """
        import ctypes, json, multiprocessing, os, subprocess, threading

        out = []
        def attempt(name, fn):
            try:
                fn()
                out.append([name, "OK"])
            except BaseException as exc:
                out.append([name, "ERR", type(exc).__name__, str(exc)[:160]])

        attempt("subprocess.run", lambda: subprocess.run(["/bin/echo", "x"], capture_output=True))
        attempt("os.system", lambda: os.system("echo x"))
        attempt("os.fork", lambda: os.fork())
        attempt("multiprocessing.Process", lambda: multiprocessing.Process(target=lambda: None).start())
        attempt("threading.Thread.start", lambda: threading.Thread(target=lambda: None).start())
        attempt("ctypes.CDLL libc.so.6", lambda: ctypes.CDLL("libc.so.6"))
        attempt("ctypes.CDLL None", lambda: ctypes.CDLL(None))
        attempt("os.execv", lambda: os.execv("/bin/echo", ["echo", "x"]))
        attempt("os.posix_spawn", lambda: os.posix_spawn("/bin/echo", ["echo", "x"], os.environ))
        print("RESULTS=" + json.dumps(out))
        """
    )
    result = runner.run(script, [data], Limits(deadline_s=30), "pytest")
    rows = parse_results(result.stdout)
    assert_all_refused(rows, "process/thread/native")
    runner.close()
    children = psutil.Process(os.getpid()).children(recursive=True)
    assert children == [], f"the sandbox left child processes behind: {children}"


# --------------------------------------------------------------------------- 5. time


def test_05a_deadline(runner: SandboxRunner) -> None:
    # Start the clock with a ready worker: the first call would otherwise
    # include worker spawn + warm-up (minutes on a cold, small Linux runner).
    # The upper bound still catches a missing hard wall clock.
    runner._ensure_pool()
    limits = Limits(deadline_s=2.0)
    started = time.perf_counter()
    result = runner.run("while True: pass", [], limits, "pytest")
    elapsed = time.perf_counter() - started
    assert result.trapped == "deadline", result
    assert result.elapsed_s < limits.deadline_s + 2.5, \
        f"deadline overshoot: {result.elapsed_s}s"
    assert elapsed < limits.deadline_s + limits.hard_grace_s + 2.0, \
        f"deadline wall {elapsed:.2f}s exceeds deadline + grace + margin"


def test_05b_optional_fuel(runner: SandboxRunner) -> None:
    # The runner pre-warms wasi-python's separate metered engine before it
    # starts the hard wall clock (worker ``metered-warm.json`` handshake).  A
    # cold metered compile therefore costs wall time but is never charged to
    # the guest, and ``deadline_s`` keeps bounding guest work only.  No test-
    # only ``hard_wall_s`` is passed: 30 s + the runner's 5 s grace must be
    # enough for 100 M fuel, and a regression that charges the compile again
    # should fail here rather than be papered over.
    fueled = runner.run("while True: pass", [],
                        Limits(deadline_s=30, fuel=100_000_000), "pytest")
    # ``out of fuel`` is not one of the public RunResult traps; it maps to
    # "error" and the spent fuel is reported separately.
    assert fueled.trapped == "error", fueled
    assert fueled.fuel_used == 100_000_000, fueled
    assert "hard wall" not in fueled.stderr, fueled


# --------------------------------------------------------------------------- 6. memory


def test_06_memory_cap(runner: SandboxRunner) -> None:
    result = runner.run("b = bytearray(512 * 1024 * 1024)\nprint('ALLOC OK', len(b))",
                        [], Limits(deadline_s=30, memory_bytes=128 * MIB), "pytest")
    assert result.trapped == "memory", result
    assert "ALLOC OK" not in result.stdout
    assert "MemoryError" in result.stderr


# --------------------------------------------------------------------------- 7. output


def test_07_output_cap(runner: SandboxRunner) -> None:
    result = runner.run(
        "import sys\n"
        "sys.stdout.write('x' * (10 * 1024 * 1024))\n"
        "sys.stdout.flush()\n"
        "print('AFTER')",
        [], Limits(deadline_s=60, memory_bytes=512 * MIB, output_bytes=1 * MIB), "pytest")
    assert result.trapped == "output", result
    assert len(result.stdout.encode("utf-8")) == 1 * MIB
    assert "stdout" in result.truncated
    assert set(result.stdout) == {"x"}


# --------------------------------------------------------------------------- 8. disk


def test_08a_disk_hard_cap_on_posix(runner: SandboxRunner) -> None:
    if sys.platform == "win32":
        pytest.xfail("R-006: Windows has no RLIMIT_FSIZE; the watchdog test covers it")
    cap = 64 * MIB
    script = (
        "f = open('/out/big.bin', 'wb')\n"
        "chunk = b'A' * (16 * 1024 * 1024)\n"
        "while True:\n"
        "    f.write(chunk)"
    )
    result = runner.run(script, [], Limits(
        deadline_s=60, memory_bytes=512 * MIB, max_file_bytes=cap,
        max_out_bytes=None, max_out_files=None), "pytest")
    assert result.trapped == "disk", result
    assert "rlimit" in result.platform_guard
    assert result.hard_file_cap_bytes == cap
    assert "File too large" in result.stderr
    big = next(item for item in result.files if item["name"] == "big.bin")
    assert big["size"] == cap, f"the kernel cap did not stop the file at {cap}: {big}"


def test_08b_disk_soft_watchdog_all_platforms(runner: SandboxRunner) -> None:
    cap = 8 * MIB
    script = (
        "f = open('/out/big.bin', 'wb')\n"
        "chunk = b'A' * (16 * 1024 * 1024)\n"
        "while True:\n"
        "    f.write(chunk)"
    )
    result = runner.run(script, [], Limits(
        deadline_s=60, memory_bytes=512 * MIB, max_out_bytes=cap,
        max_out_files=100_000, max_file_bytes=None), "pytest")
    assert result.trapped == "disk", result
    assert result.disk_guard == "out_bytes"
    assert result.max_out_bytes_seen >= cap
    assert not any(item["name"] == "big.bin" for item in result.files), \
        "the over-budget file was not discarded"


def test_08c_file_count_watchdog(runner: SandboxRunner) -> None:
    script = (
        "for i in range(50):\n"
        "    open('/out/f%02d.txt' % i, 'w').write('x')\n"
        "print('DONE')"
    )
    result = runner.run(script, [], Limits(
        deadline_s=30, max_out_files=10, max_out_bytes=None,
        max_file_bytes=None), "pytest")
    assert result.trapped == "files", result
    assert result.disk_guard == "out_files"
    assert len(result.files) <= 10


def test_08d_platform_guard_records_r006(runner: SandboxRunner) -> None:
    """R-006: Windows has no RLIMIT_FSIZE, so the watchdog is the only disk guard.

    POSIX sets the kernel file-size cap before the guest starts; Windows must
    report the watchdog-only platform guard and no hard cap.  This is a record
    of the platform reality, not a relaxed assertion: test_08b still checks the
    watchdog on every platform.
    """
    cap = 8 * MIB
    result = runner.run("open('/out/one.bin', 'wb').write(b'x')", [],
                        Limits(deadline_s=30, max_file_bytes=cap), "pytest")
    assert result.ok, result
    if sys.platform == "win32":
        assert result.platform_guard == "watchdog", result
        assert result.hard_file_cap_bytes is None, result
    else:
        assert result.platform_guard == "rlimit+watchdog", result
        assert result.hard_file_cap_bytes == cap, result


# --------------------------------------------------------------------------- 9. functional


def test_09_functional_pandas_and_openpyxl(runner: SandboxRunner,
                                           tmp_path: Path) -> None:
    regions = ["north", "south", "east", "west", "central"]
    rows = [(i, regions[i % 5], (i * 37) % 1000) for i in range(10_000)]
    input_csv = tmp_path / "input.csv"
    with open(input_csv, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "region", "amount"])
        writer.writerows(rows)
    expected: dict[str, int] = defaultdict(int)
    for _, region, amount in rows:
        expected[region] += amount

    xlsx_rows: list[list[object]] = [["region", "amount"], ["north", 10],
                                     ["south", 20], ["east", 30]]
    input_xlsx = tmp_path / "input.xlsx"
    write_xlsx(input_xlsx, xlsx_rows)

    script = textwrap.dedent(
        """
        import json
        import openpyxl
        import pandas as pd

        df = pd.read_csv("/data/input.csv")
        grouped = df.groupby("region", as_index=False)["amount"].sum().sort_values("region")
        grouped.to_csv("/out/result.csv", index=False)

        wb = openpyxl.load_workbook("/data/input.xlsx", data_only=True)
        ws = wb.active
        values = [[cell.value for cell in row] for row in ws.iter_rows()]
        open("/out/xlsx.json", "w").write(json.dumps(values))

        print("ROWS=" + str(len(df)))
        print("RESULT=" + json.dumps({r.region: int(r.amount) for r in grouped.itertuples()}))
        """
    )
    result = runner.run(script, [input_csv, input_xlsx],
                        Limits(deadline_s=60, memory_bytes=512 * MIB), "pytest")
    assert result.ok, result.stderr
    assert "ROWS=10000" in result.stdout
    got = json.loads(result.stdout.split("RESULT=", 1)[1].splitlines()[0])
    assert got == dict(expected), f"wrong group sums: {got} != {dict(expected)}"
    files = {item["name"]: item for item in result.files}
    assert {"result.csv", "xlsx.json"} <= set(files)
    assert files["result.csv"]["size"] > 0 and files["xlsx.json"]["size"] > 0
    assert len(files["result.csv"]["sha256"]) == 64


def test_09b_shared_cache_has_no_user_data(sandbox_root: Path,
                                           runner: SandboxRunner,
                                           tmp_path: Path) -> None:
    """The session cache is compiled code only, never a run's input/output."""
    sentinel = "CACHE-LEAK-SENTINEL-7f3c"
    source = tmp_path / "input.csv"
    source.write_text(f"hive,apiary,weight\n{sentinel},A,1\n", encoding="utf-8")
    result = runner.run("print(open('/data/input.csv').read())", [source],
                        Limits(deadline_s=30), "pytest")
    assert result.ok and sentinel in result.stdout
    runner.close()

    cache = sandbox_root / "cache" / "wasi-python"
    files = [path for path in cache.rglob("*") if path.is_file()]
    assert files, "the worker did not write a compiled module cache"
    assert all(path.suffix == ".cwasm" for path in files), \
        f"unexpected files in the compile cache: {[p.name for p in files]}"
    runs = sandbox_root / "runs"
    assert all(not path.is_relative_to(runs) for path in files)
    needle = sentinel.encode("utf-8")
    tail = b""
    for path in files:
        with open(path, "rb") as handle:
            while chunk := handle.read(MIB):
                haystack = tail + chunk
                assert needle not in haystack, f"user data found in {path}"
                tail = haystack[-len(needle):]


# --------------------------------------------------------------------------- 10. warm-up/latency


def test_10_warm_up_reports_time_and_peak_rss(runner: SandboxRunner) -> None:
    warmed = runner.warm_up()
    assert warmed["ok"], warmed
    assert warmed["elapsed_s"] >= 0
    assert warmed["warm_s"] is not None and warmed["warm_s"] >= 0
    assert warmed["peak_rss_mib"] and warmed["peak_rss_mib"] > 0
    assert warmed["wasi_python"] == "0.1.5"

    started = time.perf_counter()
    result = runner.run("print('hi')", [], Limits(deadline_s=30), "pytest")
    elapsed = time.perf_counter() - started
    assert result.ok and result.stdout.strip() == "hi"
    assert elapsed < 10.0, f"a warm hello took {elapsed:.2f}s"


def test_11_each_run_uses_a_new_worker(runner: SandboxRunner) -> None:
    import psutil

    first = runner.run("print('first')", [], Limits(deadline_s=30), "pytest")
    second = runner.run("print('second')", [], Limits(deadline_s=30), "pytest")
    assert first.ok and second.ok
    assert first.worker_pid and second.worker_pid
    assert first.worker_pid != second.worker_pid, "a worker was reused for two runs"
    runner.close()
    assert not psutil.pid_exists(first.worker_pid)
    assert not psutil.pid_exists(second.worker_pid)


def test_12_timeout_kill_leaves_no_orphan(runner: SandboxRunner) -> None:
    import psutil

    result = runner.run("while True: pass", [],
                        Limits(deadline_s=60, hard_wall_s=0.4), "pytest")
    assert result.trapped == "deadline", result
    assert result.worker_pid
    assert not psutil.pid_exists(result.worker_pid), \
        f"the killed worker {result.worker_pid} is still alive"
    runner.close()
    assert psutil.Process(os.getpid()).children(recursive=True) == []
