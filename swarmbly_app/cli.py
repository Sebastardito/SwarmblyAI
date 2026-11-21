"""Command-line entry point: ``swarmbly-app``.

Default: start the backend and open the local web UI. ``headless`` runs the
service without a browser — the engine and the UI are separate processes
(user requirement E: a node must work without a window).
"""

from __future__ import annotations

import argparse
import sys
import webbrowser


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="swarmbly-app",
        description="Swarmbly App — decentralized AI client and network dashboard")
    parser.add_argument("command", nargs="?", default="serve",
                        choices=["serve", "headless", "status", "init", "config",
                                 "doctor-export"],
                        help="serve (default, opens the UI) | headless (no UI) | "
                             "status | init | config get/set | doctor-export")
    parser.add_argument("config_args", nargs="*",
                        help="config set <key> <value> | config get [<key>]")
    parser.add_argument("--data-dir", default=None,
                        help="override the per-OS data directory")
    parser.add_argument("--port", type=int, default=None,
                        help="override the API port (default 8765)")
    parser.add_argument("--host", default=None,
                        help="API bind address (default 127.0.0.1)")
    parser.add_argument("--test-host-map", default=None, metavar="FILE",
                        help="TEST ONLY (D-013): JSON map of declared host -> loopback "
                             "target; never settable from the UI, the API or the config "
                             "file. Also read once from SWARMBLY_TEST_HOST_MAP at startup.")
    parser.add_argument("--prepare-sandbox", action="store_true",
                        help="compile the optional sandbox cache and exit "
                             "(for the umbrella installer; no server is started)")
    parser.add_argument("--force", action="store_true",
                        help="with --prepare-sandbox, override the free-memory floor "
                             "after an explicit warning; the umbrella installer "
                             "never passes it by itself")
    args = parser.parse_args(argv)

    if args.prepare_sandbox:
        return _prepare_sandbox(args)

    # D-013: the seam is decided here, at launch, before any client exists.
    # Nothing in the UI, the API or the config file can enable it later.
    from . import test_hosts
    try:
        mapping = test_hosts.load(args.test_host_map)
    except test_hosts.TestHostMapError as exc:
        print(f"swarmbly-app: refusing to start: {exc}", file=sys.stderr)
        return 2
    if mapping:
        print(test_hosts.startup_line())

    from .state import AppState

    if args.command == "config":
        state = AppState(args.data_dir)
        return _config_command(state, args.config_args)

    if args.command == "init":
        state = AppState(args.data_dir)
        print(f"Swarmbly App initialized.")
        print(f"  data directory: {state.dirs.root}")
        print(f"  node id:        {state.identity.node_id}")
        print(f"  config:         {state.dirs.config_path()}")
        return 0

    state = AppState(args.data_dir)
    if args.command == "status":
        for key, value in state.health().items():
            print(f"{key:14} {value}")
        return 0

    if args.command == "doctor-export":
        try:
            saved = state.doctor_export.save_current()
        except Exception as exc:
            print(f"swarmbly-app: doctor export failed: {exc}", file=sys.stderr)
            return 1
        finally:
            state.stop()
        print("Doctor export written:\n"
              f"  {saved['json_file']}\n  {saved['text_file']}")
        return 0

    state.start_p2p()  # independent P2P listener; discovery/worker per config
    import threading
    threading.Thread(target=state.searxng.autostart, daemon=True,
                     name="swarmbly-searxng-start").start()  # only if the user installed it

    api_cfg = state.config.get("api")
    host = args.host or api_cfg.get("host", "127.0.0.1")
    port = args.port or api_cfg.get("port", 8765)
    if host not in ("127.0.0.1", "localhost", "::1"):
        print("Warning: binding the admin interface to a non-loopback address "
              "exposes it to the local network. The P2P service has its own "
              "independent access limits.", file=sys.stderr)

    from .api import create_app
    app = create_app(state)

    if args.command == "serve":
        url = f"http://{host}:{port}/"
        webbrowser.open(url)

    import uvicorn
    print(f"Swarmbly App {__import__('swarmbly_app').__version__} "
          f"— http://{host}:{port}/ (node {state.identity.short_id(12)})")
    try:
        from .console import uvicorn_log_config
        # A long swarm request keeps the event loop busy at times: a longer
        # ping timeout avoids dropping the browser's WebSocket mid-answer.
        uvicorn.run(app, host=host, port=port, log_level="info",
                    access_log=False, log_config=uvicorn_log_config(),
                    ws_ping_interval=20.0, ws_ping_timeout=90.0)
    except KeyboardInterrupt:
        pass
    finally:
        state.close()
    return 0


def _coerce(value: str):
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if value.lower() in ("null", "none"):
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def _config_command(state, args: list[str]) -> int:
    if not args or args[0] not in ("get", "set"):
        print("usage: swarmbly-app config get [key]")
        print("       swarmbly-app config set <key> <value>")
        return 2
    op = args[0]
    if op == "get":
        if len(args) > 1:
            print(state.config.get(args[1]))
        else:
            import json
            print(json.dumps(state.config.all(), indent=2, ensure_ascii=False))
        return 0
    if len(args) < 3:
        print("usage: swarmbly-app config set <key> <value>", file=sys.stderr)
        return 2
    key, value = args[1], _coerce(args[2])
    state.config.update({key: value})
    print(f"{key} = {value!r}")
    return 0


def _prepare_sandbox(args) -> int:
    """Umbrella-installer entry point: compile the cache and exit with a code.

    Exit codes are stable for the installer:
      0  ready (compiled now, or the cache was already ready)
      1  the compile failed
      2  the optional ``[sandbox]`` extra is not installed
      3  not enough free memory / the environment refuses to start it
      4  invalid data directory or unexpected error
    """
    from .paths import DataDirs
    from .sandbox import SandboxPreparation

    try:
        boot = DataDirs(args.data_dir)
        configured = None
        try:
            import json
            raw = json.loads(boot.config_path().read_text(encoding="utf-8"))
            configured = raw.get("data_dir") if isinstance(raw, dict) else None
        except (OSError, ValueError):
            configured = None
        dirs = DataDirs(configured) if configured else boot
        preparation = SandboxPreparation(dirs.root / "sandbox")
    except Exception as exc:
        print(f"swarmbly-app: cannot prepare the sandbox: {exc}", file=sys.stderr)
        return 4
    status = preparation.status()
    if not status["installed"]:
        print("swarmbly-app: the optional [sandbox] extra is not installed; "
              "nothing was compiled.", file=sys.stderr)
        return 2
    if status["status"] == "ready":
        measurement = status.get("measurement") or {}
        print("swarmbly-app: the sandbox cache is already ready "
              f"(compile {measurement.get('elapsed_s', '?')} s, "
              f"peak {measurement.get('peak_rss_mib', '?')} MiB).")
        return 0
    estimate = (f"{status['expected_seconds']:g} s and "
                f"{status['expected_memory_gb']:g} GB expected; "
                f"{status['free_memory_gb']} GB free")
    force = bool(getattr(args, "force", False))
    if force:
        print("swarmbly-app: --force was given: the compile may take minutes and "
              "slow this computer or swap; close other applications first.",
              file=sys.stderr)
    print(f"swarmbly-app: preparing the sandbox cache ({estimate})…", flush=True)
    started = preparation.start(trigger="installer", force=force)
    if started.get("reason_code") == "low_memory":
        print(f"swarmbly-app: refused: {started['status'].get('last_error')}",
              file=sys.stderr)
        return 3
    if started.get("reason_code") == "not_installed":
        print("swarmbly-app: the optional [sandbox] extra is not installed.",
              file=sys.stderr)
        return 2
    final = preparation.wait(900.0)
    if final["status"] == "ready":
        measurement = final.get("measurement") or {}
        print("swarmbly-app: sandbox ready "
              f"(compile {measurement.get('elapsed_s', '?')} s, "
              f"peak {measurement.get('peak_rss_mib', '?')} MiB).")
        return 0
    reason = final.get("last_error") or final.get("status")
    print(f"swarmbly-app: sandbox preparation failed: {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
