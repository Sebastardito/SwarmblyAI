#!/usr/bin/env python3
"""Multi-node demo: N workers + 1 orchestrator, discovered WITHOUT IPs.

Every node is a full Swarmbly App state with its own identity, data directory
and P2P port. By default the orchestrator finds the workers through mDNS
(nothing is typed); ``--manual`` connects by address instead, for networks
that block multicast. The request is fragmented by the admission policy,
dispatched in parallel, verified, (optionally) resolved by cross-family
consensus, assembled and reported with SPEC §19 metadata.

Real models (Ollama running, models already installed — nothing is downloaded):
    python scripts/multi_node_demo.py --workers llama3.2:3b qwen2.5:3b \
        --orchestrator-model gemma2:2b --k 2

Without models (``--fake``): validates the protocol path only — discovery,
handshake, packets, scheduling, signatures, assembly — never model quality.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from swarmbly_app.inference.base import GenerationResult  # noqa: E402
from swarmbly_app.state import AppState  # noqa: E402

DEFAULT_PROMPT = (
    "Extract one key fact per item from the following list of five items: "
    "apples, bridges, comets, drums, electrons. List 5 bullet points, one per "
    "item, separately."
)
BASE_PORT = 19900


class FakeBackend:
    """Protocol-path stand-in. Its answers are canned; they measure nothing."""

    name = "fake"

    def __init__(self, label: str):
        self.label = label

    def list_models(self):
        return [self.label]

    def stream_chat(self, messages, *, model, max_tokens=256, temperature=0.2,
                    on_delta=None, interrupt=None, **kw):
        prompt = messages[-1]["content"]
        items = [line.split(". ", 1)[1] for line in prompt.splitlines()
                 if ". " in line and line.split(". ", 1)[0].strip().isdigit()]
        text = "\n".join(f"[{i:02d}] ({model}) a fact about {item}"
                         for i, item in enumerate(items, 1)) or f"({model}) ok."
        time.sleep(0.3)
        return GenerationResult(text=text, model=model,
                                completion_tokens=len(text.split()), total_ms=300)


def build_node(base: Path, name: str, port: int, model: str, *, worker: bool,
               fake: bool, k: int) -> AppState:
    state = AppState(str(base / name))
    swarm = {"p2p_port": port, "lan_enabled": True, "worker_enabled": worker,
             "worker_max_concurrent": 2, "k_min": k, "k_max": max(k, 2)}
    state.config.update({"swarm": swarm, "privacy": {"tier": "GLOBAL"},
                         "model": {"model_name": model,
                                   "embedder": "hash" if fake else "server"}})
    if fake:
        backend = FakeBackend(model)
        state.backends.resolve = lambda cfg=None: backend  # type: ignore[method-assign]
    state.start_p2p()
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workers", nargs="+", default=["llama3.2:3b", "qwen2.5:3b"],
                        help="one model per worker node")
    parser.add_argument("--orchestrator-model", default="gemma2:2b")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--k", type=int, default=1, help="replicas per micro-task (k_min)")
    parser.add_argument("--manual", action="store_true",
                        help="connect by address instead of mDNS discovery")
    parser.add_argument("--fake", action="store_true",
                        help="canned backend: protocol path only, no models")
    args = parser.parse_args()

    base = Path(tempfile.mkdtemp(prefix="swarmbly-demo-"))
    n = len(args.workers)
    print(f"[swarm] {n} worker(s) + 1 orchestrator · k_min={args.k} · "
          f"{'manual' if args.manual else 'mDNS discovery (no IPs)'}"
          f"{' · FAKE backend' if args.fake else ''}")
    workers = [build_node(base, f"w{i}", BASE_PORT + i, model, worker=True,
                          fake=args.fake, k=1)
               for i, model in enumerate(args.workers)]
    orch = build_node(base, "orchestrator", BASE_PORT + 50, args.orchestrator_model,
                      worker=False, fake=args.fake, k=args.k)
    states = workers + [orch]
    try:
        if args.manual:
            for w in workers:
                orch.nodes.connect_manual("127.0.0.1", w.nodes.listen_port)
        deadline = time.time() + 30
        while time.time() < deadline and len(orch.nodes.available_workers()) < n:
            time.sleep(0.25)
        found = orch.nodes.available_workers()
        print(f"[nodes] authenticated workers: {len(found)}/{n}")
        for peer in found:
            fams = [m.get("family") for m in peer.advertisement.get("models", [])]
            print(f"  {peer.node_id[:12]} via {peer.source:7} models={fams}")
        if len(found) < n:
            print("[nodes] not all workers found — multicast blocked? retry with --manual")
            return 1

        conv = orch.chat.create_conversation(title="demo", mode="lan",
                                             model=args.orchestrator_model)
        started = time.time()
        orch.chat.send(conv["id"], args.prompt, mode="lan", run_async=False)
        elapsed = time.time() - started
        final = orch.chat.get_messages(conv["id"])[-1]

        print(f"\n=== PIPELINE ({elapsed:.2f} s) — executed: "
              f"{final['meta'].get('executed')} {final['meta'].get('local_reason', '')}")
        for stage in final.get("stages", []):
            extra = "  ".join(f"{k}={v}" for k, v in stage.items()
                              if k not in ("stage", "status"))[:150]
            print(f"  {stage['stage']:26} {stage['status']:10} {extra}")
        swarm = final["meta"].get("swarm") or {}
        if swarm:
            print("\n=== ATTEMPTS ===")
            for a in swarm.get("attempts", []):
                print(f"  {a['task']} #{a['attempt']} {a['reason']:7} {a['node']} "
                      f"{a['family']:10} {a['status']:14} {a['elapsed_ms']} ms {a['code']}")
            keys = ("n_tasks", "n_levels", "rho_achieved", "rho_floor", "rho_policy",
                    "consensus_waived_reason", "tau_source", "coverage", "embedder")
            print("\n=== SPEC §19 (subset) ===")
            print(json.dumps({k: swarm.get(k) for k in keys}, indent=2, ensure_ascii=False))
            if swarm.get("consensus"):
                c = swarm["consensus"]
                print(f"\nconsensus families={c['families']} mean_agreement="
                      f"{c['mean_agreement']} — {c['interpretation']}")
        print("\n=== WORKER CONTRIBUTION ===")
        for w, model in zip(workers, args.workers):
            print(f"  {model}: served {w.worker.status()['tasks_served_today']} task(s)")
        print("\n=== FINAL RESPONSE ===")
        print(final["content"][:1500])
        return 0
    finally:
        for state in states:
            state.stop()


if __name__ == "__main__":
    raise SystemExit(main())
