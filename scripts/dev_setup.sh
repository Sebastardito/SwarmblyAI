#!/usr/bin/env bash
# Development setup (macOS / Linux): environment + packages + test tools, no launch.
# Same checks as ./launch.sh; answers yes to the install questions.
#   bash scripts/dev_setup.sh            PYTHON=python3.12 bash scripts/dev_setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."
exec ./launch.sh --setup-only --dev --yes --no-ollama "$@"
