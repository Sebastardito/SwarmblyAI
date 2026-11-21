#!/usr/bin/env python3
"""Team versus local battery (ARCH §4.1).

Runs one stored team (the same steps and roles) in two modes:

* ``local``: one App instance with the local model pool;
* ``distributed``: the same App plus 2–3 loopback circle members, or real
  machines given with ``--peer host:port`` and an invitation code.

It reports wall time, step completion, per-step role placement, answer
agreement between the two modes and the receipt counters.  The script writes a
CSV and a short Markdown summary; the run is the maintainer's job on his
machines.  ``--fake-ollama`` is for deterministic CI smoke runs only.

    python3 bench/run_team.py --model qwen2.5:7b --local --distributed
    python3 bench/run_team.py --model qwen2.5:7b --fake-ollama --members 2

Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_bank as rb  # noqa: E402
import two_node as tn  # noqa: E402

TEAM_VERSION = "0.1.0"
DEFAULT_STEPS = [
    {"id": "s1", "name": "Draft", "role": "large_model",
     "instruction": "Write a short, factual answer to: {request}"},
    {"id": "s2", "name": "Review", "role": "reasoner", "depends_on": ["s1"],
     "instruction": "Review the draft for unsupported claims and give the final "
                    "answer. Request: {request}"},
]


def _json(url: str, token: str, body: Any | None = None,
          method: str = "GET", timeout: float = 120.0) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Swarmbly-Token", token)
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
            request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else None


def settings_for(*, model: str, embed_model: str, ollama_url: str,
                 local_roles: bool, p2p_port: int, language: str = "es",
                 multi_model: bool = False, local_models: list[str] | None = None) -> dict[str, Any]:
    settings = {
        "setup_completed": True, "language": language,
        "model.backend": "ollama", "model.backend_url": ollama_url,
        "model.model_name": model, "model.embed_model": embed_model,
        "model.embedder": "hash", "model.temperature": 0.0,
        "model.multi_model": bool(multi_model),
        "model.local_models": list(local_models or ([model] if multi_model else [])),
        "lce.enabled": True, "lce.level": "C1", "lce.sources_dirs": [],
        "evidence.providers": [], "evidence.searxng_url": "",
        "privacy.tier": "GLOBAL",
        "swarm.mode": "lan", "swarm.lan_enabled": True,
        "swarm.worker_enabled": True, "swarm.worker_allow_lan": True,
        "swarm.worker_models": [model], "swarm.p2p_port": p2p_port,
        "circle.admission_mode": "circle",
        "swarm.k_min": 1, "swarm.k_max": 1, "swarm.max_retries": 0,
        "node_roles.large_model_min_b": 1.0 if local_roles else 100.0,
        "node_roles.reasoner_models": [model] if local_roles else [],
    }
    return settings


def ask_team(app: Any, text: str, team_id: str, timeout: float) -> dict[str, Any]:
    conv = _json(f"{app.base}/api/conversations", app.token, {}, "POST")
    started = time.monotonic()
    sent = _json(f"{app.base}/api/conversations/{conv['id']}/messages", app.token,
                 {"text": text, "team_id": team_id}, "POST")
    message_id = sent["assistant_message"]["id"]
    message = None
    while time.monotonic() - started < timeout:
        time.sleep(0.5)
        for item in _json(f"{app.base}/api/conversations/{conv['id']}/messages",
                          app.token):
            if item.get("id") == message_id and \
                    (item.get("meta") or {}).get("status") not in (None, "running"):
                message = item
        if message is not None:
            break
    return {"message": message, "latency_s": round(time.monotonic() - started, 2),
            "timeout": message is None}


def swarm_meta(message: dict[str, Any] | None) -> dict[str, Any]:
    meta = (message or {}).get("meta") or {}
    return meta.get("swarm") or {}


def step_rows(swarm: dict[str, Any], owner_node: str,
              team_steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names = {f"t{index}": str(step.get("name") or f"s{index + 1}")
             for index, step in enumerate(team_steps)}
    roles = {f"t{index}": str(step.get("role") or "")
             for index, step in enumerate(team_steps)}
    attempts: dict[str, list[dict[str, Any]]] = {}
    for attempt in swarm.get("attempts") or []:
        attempts.setdefault(str(attempt.get("task") or ""), []).append(attempt)
    rows = []
    for step in swarm.get("steps") or []:
        task = str(step.get("step") or "")
        placed = attempts.get(task) or []
        node = ""
        if placed:
            node = str(placed[-1].get("node") or "")
        rows.append({
            "step": task,
            "name": names.get(task, step.get("name") or task),
            "role_expected": roles.get(task, step.get("role") or ""),
            "role_placed": str((placed[-1].get("role") if placed else "") or ""),
            "node": node,
            "local": bool(node and node == owner_node),
            "status": str(step.get("status") or ""),
            "reason": str(step.get("reason") or ""),
            "blocked_by": list(step.get("blocked_by") or []),
        })
    return rows


def word_agreement(first: str, second: str) -> float:
    """Jaccard over content words: a coarse, reproducible answer agreement."""
    def words(text: str) -> set[str]:
        return {word.lower() for word in re.findall(r"[\wÁÉÍÓÚÑÜáéíóúñü]{3,}", text or "")}
    left, right = words(first), words(second)
    if not left and not right:
        return 1.0
    return round(len(left & right) / max(1, len(left | right)), 4)


def run_one(mode: str, case: dict[str, Any], args: argparse.Namespace,
            python: str, ollama_url: str, fake: Any | None) -> dict[str, Any]:
    work = Path(tempfile.mkdtemp(prefix=f"swarmbly-team-{mode}-"))
    logs = work / "logs"
    logs.mkdir()
    local_roles = mode == "local"
    owner_settings = settings_for(
        model=args.model, embed_model=args.embed_model, ollama_url=ollama_url,
        local_roles=local_roles, p2p_port=rb.free_port(),
        multi_model=local_roles, local_models=args.local_models if local_roles else [])
    app = rb.AppInstance(python, work / "datos", work / "sources", owner_settings,
                         "http://127.0.0.1:9", logs / "owner.log")
    env = None
    started = time.monotonic()
    row: dict[str, Any] = {"modo": mode, "caso": case["id"], "rep": 1,
                           "estado": "error", "wall_s": None, "steps_total": 0,
                           "steps_completed": 0, "steps_failed": 0, "steps_blocked": 0,
                           "remote_steps": 0, "roles_placed": "",
                           "agreement": "", "envios": 0, "envios_circulo": 0,
                           "pasajes_a_pares": 0}
    try:
        app.start()
        owner_node = str((app.health or {}).get("node_id") or "")
        if mode == "distributed":
            if args.invitation or args.peer:
                if args.invitation:
                    _json(f"{app.base}/api/circles/accept", app.token,
                          {"code": args.invitation}, "POST")
                for peer in args.peer:
                    host, _, port = peer.rpartition(":")
                    _json(f"{app.base}/api/swarm/connect", app.token,
                          {"host": host, "port": int(port)}, "POST")
                time.sleep(2.0)
            else:
                env = tn.TwoNodeEnv(
                    owner=app, python=python, work_root=work / "nodes",
                    proxy_url="http://127.0.0.1:9", model=args.model,
                    embed_model=args.embed_model, ollama_url=ollama_url,
                    temperature=0.0, log_dir=logs)
                env.start(members=max(1, args.members), nonmember=False)
        team = _json(f"{app.base}/api/teams", app.token, {
            "name": f"team {case['id']} {mode}",
            "steps": case.get("steps") or DEFAULT_STEPS}, "POST")
        played = ask_team(app, str(case["question"]), str(team.get("id")), args.case_timeout)
        message = played.get("message")
        answer = str((message or {}).get("content") or "")
        meta = (message or {}).get("meta") or {}
        swarm = meta.get("swarm") or {}
        steps = step_rows(swarm, owner_node, case.get("steps") or DEFAULT_STEPS)
        receipt = meta.get("receipt") or {}
        circle = tn.two_node_report(
            receipt, env.member_ledger() if env is not None else [],
            nonmember_refused=True,
            circle_passages=True)
        row.update({
            "estado": str(meta.get("status") or ("timeout" if played.get("timeout") else "?")),
            "wall_s": played.get("latency_s"),
            "steps_total": len(steps),
            "steps_completed": sum(1 for s in steps if s["status"] == "completed"),
            "steps_failed": sum(1 for s in steps if s["status"] == "failed"),
            "steps_blocked": sum(1 for s in steps if s["status"] == "blocked"),
            "remote_steps": sum(1 for s in steps if s["node"] and not s["local"]),
            "roles_placed": "|".join(
                f"{s['step']}:{s['role_placed'] or s['role_expected'] or '-'}@"
                f"{'local' if s['local'] else (s['node'][:8] or 'none')}"
                for s in steps),
            "steps": steps,
            "answer": answer,
            "envios": len(receipt.get("envios") or []),
            "envios_circulo": circle.get("envios_circulo", 0),
            "pasajes_a_pares": circle.get("pasajes_a_pares", 0),
            "receipt": receipt,
            "swarm": swarm,
        })
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"[:400]
    finally:
        if env is not None:
            env.close()
        app.stop()
        shutil.rmtree(work, ignore_errors=True)
    row["_seconds"] = round(time.monotonic() - started, 2)
    return row


def _csv_rows(rows: list[dict[str, Any]], local_answers: dict[str, str]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        answer = str(row.pop("answer", "") or "")
        row["agreement"] = ("" if row["modo"] == "local"
                            else word_agreement(local_answers.get(row["caso"], ""), answer))
        out.append({key: row.get(key, "") for key in (
            "modo", "caso", "rep", "estado", "wall_s", "steps_total",
            "steps_completed", "steps_failed", "steps_blocked", "remote_steps",
            "roles_placed", "agreement", "envios", "envios_circulo",
            "pasajes_a_pares", "error")})
    return out


def summary(rows: list[dict[str, Any]], metadata: dict[str, Any]) -> str:
    modes = sorted({row["modo"] for row in rows})
    lines = ["# Team versus local · team vs local", "",
             f"Harness {TEAM_VERSION} · cases {len({r['caso'] for r in rows})} · "
             f"members {metadata.get('members')} · model `{metadata.get('model')}`", ""]
    lines += ["| Mode | Rows | Completed steps | Remote steps | Wall seconds | Agreement |",
              "|---|---|---|---|---|---|"]
    for mode in modes:
        subset = [row for row in rows if row["modo"] == mode]
        done = sum(int(row.get("steps_completed") or 0) for row in subset)
        total = sum(int(row.get("steps_total") or 0) for row in subset)
        remote = sum(int(row.get("remote_steps") or 0) for row in subset)
        wall = round(sum(float(row.get("wall_s") or 0) for row in subset) /
                     max(1, len(subset)), 2)
        agree = [float(row["agreement"]) for row in subset
                 if str(row.get("agreement") or "") != ""]
        lines.append(f"| {mode} | {len(subset)} | {done}/{total} | {remote} | {wall} | "
                     f"{round(sum(agree) / len(agree), 3) if agree else '—'} |")
    lines += ["", "## Per-step placement", "",
              "| Mode | Case | Step | Role expected | Role placed | Node | Status |",
              "|---|---|---|---|---|---|---|"]
    for row in rows:
        for step in row.get("steps") or []:
            lines.append(f"| {row['modo']} | {row['caso']} | {step['name']} | "
                         f"{step['role_expected'] or '—'} | {step['role_placed'] or '—'} | "
                         f"{'local' if step['local'] else (step['node'][:8] or '—')} | "
                         f"{step['status']} |")
    lines += ["", "The pre-registration and success criteria are in "
              "`bench/dev_team/README.md`. Agreement is a word-overlap measure, "
              "not correctness."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Team versus local battery")
    ap.add_argument("--model", required=True)
    ap.add_argument("--embed-model", default="nomic-embed-text")
    ap.add_argument("--ollama", default="http://127.0.0.1:11434")
    ap.add_argument("--app-python", "--python", dest="python", default=None)
    ap.add_argument("--case-timeout", type=float, default=600.0)
    ap.add_argument("--members", type=int, default=2)
    ap.add_argument("--local-model", action="append", default=[],
                    help="local-pool model (repeat twice; default: the chat model twice)")
    ap.add_argument("--local", action="store_true", help="run the one-node mode")
    ap.add_argument("--distributed", action="store_true", help="run the 2–3 node mode")
    ap.add_argument("--peer", action="append", default=[], help="real machine host:port")
    ap.add_argument("--invitation", default="", help="invitation code for a real circle")
    ap.add_argument("--fake-ollama", action="store_true",
                    help="start a deterministic fake Ollama (CI smoke only)")
    ap.add_argument("--battery", default=str(HERE / "dev_team"))
    ap.add_argument("--label", default="")
    args = ap.parse_args(argv)
    battery = Path(args.battery)
    cases = json.loads((battery / "casos.json").read_text(encoding="utf-8"))["casos"]
    modes = [m for m, want in (("local", args.local), ("distributed", args.distributed))
             if want] or ["local", "distributed"]
    python = rb.find_python(args.python)
    args.local_models = list(args.local_model) or ([args.model, "fake:3b"]
                                                   if args.fake_ollama else
                                                   [args.model, args.model])
    fake = None
    ollama_url = args.ollama
    if args.fake_ollama:
        from fake_ollama import FakeOllama
        fake = FakeOllama(models=tuple(dict.fromkeys(
            [args.model, args.embed_model, *args.local_models])))
        ollama_url = fake.url
    rows: list[dict[str, Any]] = []
    try:
        for mode in modes:
            for case in cases:
                row = run_one(mode, case, args, python, ollama_url, fake)
                print(f"  {mode:11} {case['id']:10} {row['estado']:8} "
                      f"{row['steps_completed']}/{row['steps_total']} steps · "
                      f"{row['remote_steps']} remote · {row['wall_s']} s")
                rows.append(row)
        local_answers = {row["caso"]: row.get("answer", "")
                         for row in rows if row["modo"] == "local"}
        csv_rows = _csv_rows(rows, local_answers)
        run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + (
            f"_{args.label}" if args.label else "")
        out = battery / "ejecuciones" / run_id
        out.mkdir(parents=True)
        with (out / "resultados.csv").open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(csv_rows[0]) if csv_rows else [])
            writer.writeheader()
            writer.writerows(csv_rows)
        meta = {"run_id": run_id, "model": args.model, "members": args.members,
                "modes": modes, "fake_ollama": bool(fake),
                "python": python, "version": TEAM_VERSION,
                "ollama": args.ollama if not fake else "fake"}
        (out / "resumen.md").write_text(summary(rows, meta), encoding="utf-8")
        (out / "resumen.json").write_text(json.dumps(
            {"info": meta, "filas": csv_rows,
             "detalle": [{key: value for key, value in row.items()
                          if key not in ("answer", "receipt")}
                         for row in rows]}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"Team battery: {len(csv_rows)} rows · results in {out}")
    finally:
        if fake is not None:
            fake.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
