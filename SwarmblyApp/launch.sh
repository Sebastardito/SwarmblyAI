#!/usr/bin/env bash
# Swarmbly App — one-command launcher (macOS / Linux).
#   ./launch.sh                 check, prepare (asks first) and start
#   ./launch.sh --check         report only
#   ./launch.sh --headless      node without the browser interface
#   ./launch.sh --help          all options
# Finds Python 3.10+ and hands over to scripts/launch.py (standard library only).
set -euo pipefail
cd "$(dirname "$0")"

pick_python() {
  local candidates=("${PYTHON:-}" python3.13 python3.12 python3.11 python3.10 python3)
  for py in "${candidates[@]}"; do
    [[ -z "$py" ]] && continue
    command -v "$py" >/dev/null 2>&1 || continue
    if "$py" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      echo "$py"; return 0
    fi
  done
  return 1
}

if ! PY="$(pick_python)"; then
  echo "Swarmbly App needs Python 3.10 or newer, and none was found."
  case "$(uname -s)" in
    Darwin) echo "Install it from https://www.python.org/downloads/ or: brew install python@3.12" ;;
    *)      echo "Install it with your package manager, e.g.: sudo apt install python3.12 python3.12-venv" ;;
  esac
  echo "Or point to one explicitly: PYTHON=/path/to/python3.12 ./launch.sh"
  exit 1
fi

exec "$PY" scripts/launch.py "$@"
