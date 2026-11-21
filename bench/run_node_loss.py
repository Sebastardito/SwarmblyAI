#!/usr/bin/env python3
"""Node-loss battery (ARCH §4.2).

Runs a three-step team on one loopback circle member, waits until the member is
generating the second step, stops that member, and checks the honest partial
result: completed steps stay, the lost step is named with ``node_lost``, its
dependent is ``blocked`` and the requester's receipt lists only what was sent.

Deterministic with ``--fake-ollama``: the member's fake backend holds the
second step until the harness kills the process.  A real-model run uses
``--kill-after`` seconds instead.  Standard library only.

    python3 bench/run_node_loss.py --model qwen2.5:7b --fake-ollama
    python3 bench/run_node_loss.py --model qwen2.5:7b --kill-after 8
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import threading
import time
import shutil
import json as _json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_bank as rb  # noqa: E402
import two_node as tn  # noqa: E402
from run_team import settings_for, ask_team  # noqa: E402

NODE_LOSS_VERSION = "0.1.0"
TEAM_STEPS = [
    {"id": "s1", "name": "First", "role": "large_model",
     "instruction": "FIRSTSTEP: answer briefly: {request}"},
    # search has no truthful local substitute, so losing the worker surfaces a
    # failed step instead of silently retrying on the requester.
    {"id": "s2", "name": "Second", "role": "search", "depends_on": ["s1"],
     "instruction": "public sources about {request}"},
    {"id": "s3", "name": "Third", "role": "large_model", "depends_on": ["s2"],
     "instruction": "THIRDSTEP: give the final answer: {request}"},
]


def assert_partial(swarm: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    """The D-019 assertions on one canned or real run metadata."""
    steps = list(swarm.get("steps") or [])
    completed = [step for step in steps if step.get("status") == "completed"]
    failed = [step for step in steps if step.get("status") == "failed"]
    blocked = [step for step in steps if step.get("status") == "blocked"]
    lost = [step for step in failed if step.get("reason") == "node_lost"]
    lost_ids = {str(step.get("step")) for step in lost}
    blocked_names = [step for step in blocked
                     if set(map(str, step.get("blocked_by") or [])) & lost_ids]
    sent_tasks = set()
    for entry in receipt.get("envios") or []:
        motivo = str(entry.get("motivo") or "")
        for token in ("t0", "t1", "t2"):
            if f"fragmento {token}" in motivo:
                sent_tasks.add(token)
    status = str(swarm.get("status") or "")
    missing_after_loss = [step for step in steps
                          if step.get("status") in ("blocked", "failed")]
    checks = {
        "estado_parcial_o_fallido": status in ("partial", "failed"),
        "paso_completado_presente": bool(completed),
        "paso_perdido_nombrado": bool(lost),
        "dependiente_bloqueado": bool(blocked_names),
        # A step after the lost one must not appear in the receipt; what was
        # sent before the loss may appear once.
        "recibo_solo_lo_enviado": not any(
            "fragmento t2" in str(entry.get("motivo") or "")
            for entry in receipt.get("envios") or []),
        "motivo_node_lost": bool(lost),
    }
    return {
        "version": NODE_LOSS_VERSION,
        "status": status,
        "completed": [step.get("step") for step in completed],
        "lost": [{"step": step.get("step"), "reason": step.get("reason"),
                  "detail": step.get("detail", "")} for step in lost],
        "blocked": [{"step": step.get("step"),
                     "blocked_by": list(step.get("blocked_by") or [])}
                    for step in blocked],
        "missing_after_loss": missing_after_loss,
        "checks": checks,
        "ok": all(checks.values()),
    }


class SlowSearch:
    """A search endpoint that keeps the request open until the member is killed."""

    def __init__(self) -> None:
        self.message = threading.Event()
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:
                return

            def do_GET(self) -> None:  # noqa: N802
                server.message.set()
                time.sleep(30.0)
                body = _json.dumps({"query": "", "results": []}).encode("utf-8")
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except OSError:
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def _wait_for_search(slow: SlowSearch, timeout: float) -> bool:
    return slow.message.wait(timeout)


def run(args: argparse.Namespace) -> dict[str, Any]:
    python = rb.find_python(args.python)
    work = Path(tempfile.mkdtemp(prefix="swarmbly-node-loss-"))
    logs = work / "logs"
    logs.mkdir()
    owner_fake = None
    slow = SlowSearch()
    env = None
    try:
        if args.fake_ollama:
            from fake_ollama import FakeOllama
            owner_fake = FakeOllama(models=(args.model, args.embed_model))
        owner_url = owner_fake.url if owner_fake else args.ollama
        member_url = owner_url
        owner_settings = settings_for(
            model=args.model, embed_model=args.embed_model, ollama_url=owner_url,
            local_roles=False, p2p_port=rb.free_port())
        owner = rb.AppInstance(python, work / "owner" / "datos",
                               work / "owner" / "sources", owner_settings,
                               "http://127.0.0.1:9", logs / "owner.log")
        owner.start()
        env = tn.TwoNodeEnv(
            owner=owner, python=python, work_root=work / "nodes",
            proxy_url="http://127.0.0.1:9", model=args.model,
            embed_model=args.embed_model, ollama_url=member_url,
            temperature=0.0, log_dir=logs)
        env.start(members=1, nonmember=False, member_extra={
            "evidence.providers": ["web"],
            "evidence.searxng_url": slow.url,
            "node_roles.search": {"enabled": True},
        })
        member = env.members[0]
        team = _json_post(
            f"{owner.base}/api/teams", owner.token,
            {"name": "node-loss", "steps": TEAM_STEPS})
        result: dict[str, Any] = {}

        def play() -> None:
            result.update(ask_team(owner, args.question, str(team.get("id")),
                                   args.case_timeout))

        thread = threading.Thread(target=play, daemon=True)
        thread.start()
        killed = _wait_for_search(slow, args.wait_seconds) if args.fake_ollama \
            else False
        if not killed:
            time.sleep(max(0.0, args.kill_after))
            killed = True
        if killed:
            member.stop()             # kill the process, not a graceful leave
        thread.join(timeout=args.case_timeout + 10)
        message = result.get("message")
        meta = (message or {}).get("meta") or {}
        swarm = meta.get("swarm") or {}
        receipt = meta.get("receipt") or {}
        report = assert_partial(swarm, receipt)
        report.update({
            "killed": killed,
            "wall_s": result.get("latency_s"),
            "timeout": result.get("timeout"),
            "status_meta": meta.get("status"),
            "answer": (message or {}).get("content", "")[:500],
            "receipt_envios": receipt.get("envios") or [],
        })
        return report
    finally:
        if env is not None:
            env.close()
        if owner_fake is not None:
            owner_fake.close()
        slow.close()
        shutil.rmtree(work, ignore_errors=True)


def _json_post(url: str, token: str, body: dict[str, Any]) -> dict[str, Any]:
    import urllib.request
    request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Swarmbly-Token", token)
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
            request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Node-loss battery")
    ap.add_argument("--model", required=True)
    ap.add_argument("--embed-model", default="nomic-embed-text")
    ap.add_argument("--ollama", default="http://127.0.0.1:11434")
    ap.add_argument("--app-python", "--python", dest="python", default=None)
    ap.add_argument("--fake-ollama", action="store_true",
                    help="use two deterministic fake Ollama servers (CI)")
    ap.add_argument("--kill-after", type=float, default=8.0,
                    help="seconds before stopping the member in a real-model run")
    ap.add_argument("--wait-seconds", type=float, default=60.0)
    ap.add_argument("--case-timeout", type=float, default=180.0)
    ap.add_argument("--question", default="Explain why a fictitious river rises in spring.")
    ap.add_argument("--label", default="")
    args = ap.parse_args(argv)
    report = run(args)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + (
        f"_{args.label}" if args.label else "")
    out = HERE / "dev_node_loss" / "ejecuciones" / stamp
    out.mkdir(parents=True)
    (out / "resultado.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    lines = [f"# Node loss · pérdida de nodo · {stamp}", "",
             f"- killed: {report.get('killed')}",
             f"- status: {report.get('status')}",
             f"- completed: {', '.join(report.get('completed') or []) or '—'}",
             f"- lost: {', '.join(item['step'] for item in report.get('lost') or []) or '—'}",
             f"- blocked: {', '.join(item['step'] for item in report.get('blocked') or []) or '—'}",
             f"- ok: {report.get('ok')}", "",
             "| Check | Result |", "|---|---|"]
    lines += [f"| {key} | {'yes' if value else 'no'} |"
              for key, value in (report.get("checks") or {}).items()]
    (out / "resumen.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Node loss: status {report.get('status')} · ok {report.get('ok')} · {out}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
