#!/usr/bin/env bash
# Swarmbly AI — installer for macOS and Linux.
#   ./install.sh              asks: quick or custom install
#   ./install.sh --quick      everything recommended, no questions
#   ./install.sh --custom     step by step
#   ./install.sh --doctor     check an existing installation
#   ./install.sh --uninstall
#   ./install.sh --help       all options
# Finds Python 3.10+ and hands over to installer/install.py (standard library only).
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
  case "${LANG:-}" in es*) es=1 ;; *) es=0 ;; esac
  if [[ $es == 1 ]]; then
    echo "Swarmbly AI necesita Python 3.10 o superior y no se encontró."
  else
    echo "Swarmbly AI needs Python 3.10 or newer, and none was found."
  fi
  case "$(uname -s)" in
    Darwin) echo "  https://www.python.org/downloads/   or:  brew install python@3.12" ;;
    *)      echo "  sudo apt install python3.12 python3.12-venv   (or your distribution's equivalent)" ;;
  esac
  echo "  PYTHON=/path/to/python3.12 ./install.sh"
  exit 1
fi

exec "$PY" installer/install.py "$@"
