#!/usr/bin/env python3
"""Interface preview with a fake swarm (development aid).

Starts the UI on http://127.0.0.1:8799 plus two worker nodes, all with a
canned backend and two pretend installed models, so every view can be seen
with real P2P events without Ollama. The canned answers measure nothing.

Nothing is announced on your network: every node listens on 127.0.0.1 only,
mDNS stays off, and the interface node connects to the two workers by
address. A real Swarmbly node on the same network can never see (or send
work to) these fake workers.

    python scripts/ui_preview.py            # then open the printed URL
    python scripts/ui_preview.py --fresh    # show the first-run assistant
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from multi_node_demo import FakeBackend  # noqa: E402
from swarmbly_app.models import BackendInfo, DetectedModel  # noqa: E402
from swarmbly_app.state import AppState  # noqa: E402

GB = 1024 ** 3
FAKE_MODELS = [
    DetectedModel("llama3.2:3b", "llama", int(2.0 * GB), "Q4_K_M", parameter_size="3.2B"),
    DetectedModel("qwen2.5:3b", "qwen2", int(1.9 * GB), "Q4_K_M", parameter_size="3.1B"),
    DetectedModel("phi3.5:3.8b", "phi3", int(2.2 * GB), "Q4_0", parameter_size="3.8B"),
]


def fake_node(base: Path, name: str, port: int, models: list[DetectedModel], **swarm) -> AppState:
    state = AppState(str(base / name))
    # Loopback only and no mDNS: fake workers must never reach a real network.
    state.config.update({"swarm": {"p2p_port": port, "p2p_host": "127.0.0.1",
                                   "lan_enabled": False, **swarm},
                         "privacy": {"tier": "GLOBAL"},
                         "permissions": {"lan_discovery": False},
                         "model": {"model_name": models[0].name}})
    backend = FakeBackend(models[0].name)
    state.backends.resolve = lambda cfg=None: backend  # type: ignore[method-assign]
    info = [BackendInfo("ollama", "http://127.0.0.1:11434", True, models=list(models))]
    state.model_manager.detect_cached = lambda *a, **k: info  # type: ignore[method-assign]
    state.start_p2p()
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8799)
    parser.add_argument("--fresh", action="store_true", help="show the first-run assistant")
    args = parser.parse_args()
    base = Path(tempfile.mkdtemp(prefix="swarmbly-ui-"))
    workers = [fake_node(base, "w1", 19971, [FAKE_MODELS[0]], worker_enabled=True,
                         worker_max_concurrent=2),
               fake_node(base, "w2", 19972, [FAKE_MODELS[2]], worker_enabled=True,
                         worker_max_concurrent=2)]
    ui = fake_node(base, "ui", 19970, FAKE_MODELS[:2], k_min=2, k_max=3)
    for worker in workers:
        ui.nodes.connect_manual("127.0.0.1", worker.nodes.listen_port, wait=True)
    ui.config.update({"setup_completed": not args.fresh,
                      "model": {"multi_model": True,
                                "local_models": ["llama3.2:3b", "qwen2.5:3b"]}})
    import uvicorn
    from swarmbly_app.api import create_app
    app = create_app(ui)
    print(f"Preview (FAKE swarm): http://127.0.0.1:{args.port}/", flush=True)
    try:
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    finally:
        for state in [ui, *workers]:
            state.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
