#!/usr/bin/env bash
# F-forget y A/A (Enmienda 6 c de PREREGISTRATION_BENCH_R1X), en el Mac con Ollama.
#
#   bash scripts/run_forget_aa_mac.sh
#
# Pasos, cada uno comprobado antes del siguiente:
#   1. entorno bloqueado (Python 3.11 del .venv), árbol limpio, pruebas en verde;
#   2. Ollama responde y los modelos están (los digests se comprueban dentro);
#   3. F-forget (unos 30-40 min: digiere 30 wikis);
#   4. A/A (unos 20-30 min).
# Nada se confirma ni se sube: revisa results/bench_forget y results/aa_test.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
[ -x "$PY" ] || { echo "falta .venv (python3.11 -m venv .venv && .venv/bin/pip install -r requirements.lock)"; exit 1; }
"$PY" -c 'import sys; assert sys.version_info[:2] == (3, 11), sys.version' || { echo "el .venv no es Python 3.11"; exit 1; }

echo "== 1. estado del repositorio"
if [ -n "$(git status --porcelain -- swarmbly_lce lce_validation docs)" ]; then
  echo "cambios sin confirmar en swarmbly_lce/, lce_validation/ o docs/: confírmalos primero"; exit 1
fi
"$PY" -m pytest -q >/dev/null && echo "pruebas en verde"

echo "== 2. Ollama y modelos"
curl -fsS http://localhost:11434/api/version >/dev/null || { echo "Ollama no responde en localhost:11434"; exit 1; }
for m in qwen2.5:3b llama3.2:3b gemma2:2b nomic-embed-text; do
  names=$(ollama list | awk '{print $1}')
  echo "$names" | grep -qx "$m" || echo "$names" | grep -qx "$m:latest" \
    || { echo "falta el modelo $m (no se descarga solo: cambiaría el digest)"; exit 1; }
done

mkdir -p results/bench_forget results/aa_test
echo "== 3. F-forget"
"$PY" -m lce_validation.bench_forget 2>&1 | tee results/bench_forget/run.log
echo "== 4. A/A"
"$PY" -m lce_validation.aa_test 2>&1 | tee results/aa_test/run.log
echo
echo "Listo. Salidas en results/bench_forget/ y results/aa_test/ (sin confirmar)."
