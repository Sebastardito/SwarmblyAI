#!/usr/bin/env bash
# Confirmatory run of C1/C2 (docs/PREREGISTRATION_C1_C2_EN.md) on a Mac with Ollama.
#
#   bash scripts/run_c1_c2_mac.sh
#
# Steps, each checked before the next:
#   1. the repository is clean and the pre-registration is committed;
#   2. Ollama answers and the four models are pulled;
#   3. the MCQ item set is drawn ONCE and committed (skipped if already committed);
#   4. run_real, confirmatory; outputs in lce_validation/results_real.json and REPORT_REAL.md.
# Nothing is pushed. Review the outputs, then commit and push them yourself.
set -euo pipefail
cd "$(dirname "$0")/.."

PREREG=docs/PREREGISTRATION_C1_C2_EN.md
MCQ=lce_validation/data/mmlu_test_1500.json
MODELS="qwen2.5:3b,llama3.2:3b,gemma2:2b"
EMBED="nomic-embed-text"
PY="${PYTHON:-python3}"

echo "== 1. repository state"
git ls-files --error-unmatch "$PREREG" >/dev/null || { echo "pre-registration not committed: $PREREG"; exit 1; }
if [ -n "$(git status --porcelain -- swarmbly_lce lce_validation docs)" ]; then
  echo "uncommitted changes in swarmbly_lce/, lce_validation/ or docs/: commit or stash them first"; exit 1
fi
"$PY" -m pytest -q >/dev/null && echo "tests pass"

echo "== 2. Ollama and models"
curl -fsS http://localhost:11434/api/version >/dev/null || { echo "Ollama is not answering on localhost:11434 (open the Ollama app or run 'ollama serve')"; exit 1; }
for m in ${MODELS//,/ } "$EMBED"; do
  ollama list | awk '{print $1}' | grep -qx "$m" || ollama pull "$m"
done

echo "== 3. MCQ item set"
if git ls-files --error-unmatch "$MCQ" >/dev/null 2>&1; then
  echo "already committed: $MCQ"
else
  [ -e "$MCQ" ] && { echo "$MCQ exists but is not committed; inspect it, then commit it or delete it (a declared deviation)"; exit 1; }
  "$PY" -m lce_validation.fetch_mcq
  git add "$MCQ"
  git commit -s -q -m "Conjunto de 1.500 preguntas MMLU para C2 (preregistrado, semilla 20261005)"
  echo "committed $(git rev-parse --short HEAD)"
fi

echo "== 4. confirmatory run (about one to two hours; stops in about a minute if the projection fails the preflight)"
# Run settings fixed by amendment 3 of the pre-registration (run 2 onwards).
"$PY" -m lce_validation.run_real --models "$MODELS" --embed-model "$EMBED" --prereg "$PREREG" \
  --anchor-mode quote --span-projection --reconcile-types --preflight 2>&1 | tee lce_validation/run_real.log
echo
echo "Done. Review lce_validation/REPORT_REAL.md, then commit results_real.json, REPORT_REAL.md and run_real.log."
