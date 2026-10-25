#!/usr/bin/env python3
"""Two-node demo (one worker + one orchestrator), discovered without IPs.

Thin wrapper over ``multi_node_demo.py``:

    python scripts/two_nodes_demo.py --worker-model llama3.2:3b --client-model gemma2:2b
    python scripts/two_nodes_demo.py --fake          # protocol path only, no models
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import multi_node_demo  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-model", default="llama3.2:3b")
    parser.add_argument("--client-model", default="gemma2:2b")
    parser.add_argument("--k", type=int, default=1)
    parser.add_argument("--manual", action="store_true")
    parser.add_argument("--fake", action="store_true")
    parser.add_argument("--prompt", default=multi_node_demo.DEFAULT_PROMPT)
    args = parser.parse_args()
    argv = ["--workers", args.worker_model, "--orchestrator-model", args.client_model,
            "--k", str(args.k), "--prompt", args.prompt]
    argv += ["--manual"] if args.manual else []
    argv += ["--fake"] if args.fake else []
    sys.argv = [sys.argv[0], *argv]
    return multi_node_demo.main()


if __name__ == "__main__":
    raise SystemExit(main())
