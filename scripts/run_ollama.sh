#!/usr/bin/env bash
#
# Swarmbly V0 + V3c against a local Ollama, with five model families.
#
#   ./scripts/run_ollama.sh smoke     ~5 min    does the wiring hold?
#   ./scripts/run_ollama.sh v0        ~2-4 h    the coherence-tax curve (H1)
#   ./scripts/run_ollama.sh v3c       ~2-3 h    agreement vs judged quality (V3c)
#   ./scripts/run_ollama.sh v3c-gt    ~4-6 h    agreement vs GROUND TRUTH (V3c proper)
#                                               15 prompts x 150 items x 5 families
#   ./scripts/run_ollama.sh v3c-ff    ~2-3 h    free-form answers + composition
#   ./scripts/run_ollama.sh all       ~5-7 h    v0 + v3c, sequentially
#
# Run v3c-gt before v3c if you only have time for one. The v3c tier grades with
# a peer-class judge, which is the instrument that made the 14 August result
# uninterpretable: it accepted 93.3 % of everything, so the correlation could
# not appear whether or not the signal was there. v3c-gt grades against an
# answer key instead, which is what Section 11.4 actually specifies.
#
# Everything is written under results/<tier>-<timestamp>/. Nothing is deleted.
#
# Why *families* and not sizes: agreement between replicas is only evidence to
# the extent the replicas could have disagreed. Models sharing training data
# share errors and agree confidently on the same mistake, so a k=3 run drawn
# from one family produces a high agreement score that means nothing at all.
#
# Why five and not three: the run of 24 August had three families loaded and
# swept k up to 5, so the k=5 arm ran with two duplicated families. The
# fingerprint is in the data -- mean agreement 0.705 at k=3 and 0.700 at k=5,
# barely moved, which is what happens when the replicas you add are echoes of
# the ones already there. That arm is contaminated upward and cannot be used.
# k can never exceed the number of distinct families, so five families is the
# floor for a k=5 sweep, not a luxury.
#
# The script refuses to proceed if fewer than five distinct families are
# present, or if the highest k in a tier exceeds the family count.

set -euo pipefail

TIER="${1:-smoke}"
HOST="${OLLAMA_HOST:-http://localhost:11434}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# --- the five families ------------------------------------------------------
# Override with SWARMBLY_MODELS="fam:model,fam:model,fam:model" if you prefer
# different ones. Keep them small: three models resident at once on a laptop.
# Five distinct pretraining lineages, five organisations. Diversity of corpus is
# what buys independent error modes; diversity of parameter count buys nothing
# for this measurement.
MODELS_DEFAULT="llama:llama3.2:3b,qwen:qwen2.5:3b,gemma:gemma2:2b,phi:phi3.5:3.8b,granite:granite3.1-dense:2b"
MODELS="${SWARMBLY_MODELS:-$MODELS_DEFAULT}"
EMBED_MODEL="${SWARMBLY_EMBED_MODEL:-nomic-embed-text}"
PRIMARY="$(echo "$MODELS" | cut -d, -f1 | cut -d: -f2-)"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m%s\033[0m\n' "$*"; }
die()  { printf '\033[31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

# --------------------------------------------------------------------------
# Preflight. Every check here is one that would otherwise fail three hours in.
# --------------------------------------------------------------------------
bold "== Preflight =="

command -v ollama >/dev/null 2>&1 || die "ollama is not on PATH. https://ollama.com/download"

if ! curl -sS -m 5 "$HOST/api/tags" >/dev/null 2>&1; then
  warn "Ollama is not answering on $HOST — starting it in the background."
  (ollama serve >/tmp/ollama-serve.log 2>&1 &)
  for _ in $(seq 1 30); do
    sleep 1
    curl -sS -m 2 "$HOST/api/tags" >/dev/null 2>&1 && break
  done
  curl -sS -m 5 "$HOST/api/tags" >/dev/null 2>&1 \
    || die "could not reach $HOST after 30s. See /tmp/ollama-serve.log"
fi
echo "  ollama:       reachable at $HOST"

# distinct families
NFAM=$(echo "$MODELS" | tr ',' '\n' | cut -d: -f1 | sort -u | wc -l | tr -d ' ')
[ "$NFAM" -ge 5 ] || die "only $NFAM distinct families in SWARMBLY_MODELS. \
k>1 across one family measures that family's sampling variance, not the \
disagreement between independent estimators — which is the whole point of V3c. \
k can never exceed the family count: the v3c tiers sweep k up to 5, so five \
distinct families is the floor."
echo "  families:     $NFAM distinct"

# pull what is missing
HAVE="$(ollama list 2>/dev/null | tail -n +2 | awk '{print $1}')"
for entry in $(echo "$MODELS" | tr ',' ' '); do
  model="${entry#*:}"
  if ! echo "$HAVE" | grep -qx "$model"; then
    bold "  pulling $model (first run only)"
    ollama pull "$model" || die "failed to pull $model"
  else
    echo "  present:      $model"
  fi
done
if ! echo "$HAVE" | grep -q "^${EMBED_MODEL}"; then
  bold "  pulling $EMBED_MODEL (embeddings)"
  ollama pull "$EMBED_MODEL" || warn "could not pull $EMBED_MODEL — tau will be calibrated on hashed vectors and will mean nothing"
else
  echo "  present:      $EMBED_MODEL"
fi

# python side
python3 -c "import swarmbly_v0" 2>/dev/null || {
  bold "  installing swarmbly_v0 in editable mode"
  python3 -m pip install -e . --quiet || die "pip install -e . failed"
}
python3 -c "import swarmbly_v0; print('  swarmbly_v0:  ', swarmbly_v0.__version__)"

export OPENAI_BASE_URL="$HOST/v1"
export OPENAI_API_KEY="ollama"
export SWARMBLY_MODEL="$PRIMARY"
export SWARMBLY_EMBED_MODEL="$EMBED_MODEL"
export SWARMBLY_REPLICA_MODELS="$MODELS"

# end-to-end smoke of the actual transport, before committing hours to it
bold "  round-trip test"
python3 - <<'PY' || die "the endpoint is reachable but the round trip failed"
from swarmbly_v0 import get_backend, get_embedder
b = get_backend("openai")
out = b.generate("Reply with exactly the word: ready", max_tokens=8)
print(f"  generate:     {out[:60]!r}  (transport: {b.transport})")
e = get_embedder("api")
v = e.embed(["alpha", "beta"])
print(f"  embeddings:   shape {v.shape}  available={e.available}")
if not e.available:
    print("  WARNING: embeddings degraded to hashing; tau_sem will be meaningless.")
PY

STAMP="$(date +%Y%m%d-%H%M%S)"

run_v0() {
  local out="results/v0-$STAMP"
  bold ""
  bold "== V0 — the coherence tax as a function of rho (hypothesis H1) =="
  echo "  This is the make-or-break measurement: how much quality is lost to"
  echo "  fragmentation and reassembly, and whether any rho gets it under 5%."
  echo "  Output: $out"
  mkdir -p "$out"
  python3 -m swarmbly_v0 run \
    --backend openai --embedder api \
    --rho 1.0,1.25,1.5,2.0 --n 2,4,8 --k 1 \
    --candidates 2 --seed 0 \
    --out "$out" 2>&1 | tee "$out/run.log" || true
  echo "  -> $out/report.html"
}

run_v3c_ff() {
  local out="results/v3c-ff-$STAMP"
  bold ""
  bold "== V3c on free-form answers, and the first composition measurement =="
  echo "  The ground-truth run of 24 August fixed the pipeline -- fragmented"
  echo "  accuracy 68.6 % against 76.8 % unfragmented, control at 100 % in both --"
  echo "  and then saturated the predictor instead: 260 of 280 items came back at"
  echo "  agreement exactly 1.0, four distinct values in all, and at k=3 the"
  echo "  agreement was 1.0 everywhere and carried no information whatsoever."
  echo "  Independent models that get '30' right emit the same string."
  echo ""
  echo "  This corpus supplies answers that can be phrased differently and still"
  echo "  be right, which is what the agreement machinery was built for, plus"
  echo "  three two-paragraph compositions -- the workload the architecture is"
  echo "  actually pitched on, and which has never been measured."
  echo ""
  echo "  Read in this order:"
  echo "    composition.by_condition        -- constraint scores, fragmented vs"
  echo "                                       monolithic. Counted from the text,"
  echo "                                       never judged."
  echo "    repeated_sentences_cross_task   -- two workers writing the same"
  echo "                                       sentence. The signature failure of"
  echo "                                       assembly, and invisible to a"
  echo "                                       transition-based coherence score"
  echo "                                       because each copy reads well."
  echo "    truth_calibration.pooled.auc    -- and check mean_agreement first: if"
  echo "                                       it is near 1.0 again the predictor"
  echo "                                       saturated and the AUC means little."
  echo "    composition_traces.md           -- the generated text with its"
  echo "                                       construction: which micro-task wrote"
  echo "                                       which sentence, the seams, and every"
  echo "                                       repetition located."
  echo "  Output: $out"
  mkdir -p "$out"
  python3 -m swarmbly_v0 run \
    --backend openai --embedder api \
    --prompts prompts/free_form.json \
    --rho 1.5 --n 3 --k 1,3,5 \
    --candidates 2 --seed 0 \
    --out "$out" 2>&1 | tee "$out/run.log" || true
  echo "  -> $out/composition_traces.md"
  echo "  -> $out/summary.json"
}

run_v3c_gt() {
  local out="results/v3c-gt-$STAMP"
  bold ""
  bold "== V3c against ground truth — does agreement predict CORRECTNESS? =="
  echo "  The experiment Section 11.4 specifies, and the one the 14 August run"
  echo "  was not. There the verdict came from a peer-class judge that accepted"
  echo "  93.3 % of everything, so r = -0.030 could not distinguish 'agreement"
  echo "  does not predict correctness' from 'the judge cannot tell'. Here the"
  echo "  verdict comes from prompts/ground_truth.json — an answer key, graded"
  echo "  mechanically by swarmbly_v0.grading. No model in the verdict."
  echo ""
  echo "  Read the summary in this order:"
  echo "    truth_calibration.pooled.flagging  — flag the lowest-agreement items."
  echo "                                         lift near 1.0 means the flag is"
  echo "                                         no better than random, and that"
  echo "                                         result retires the confidence map."
  echo "    truth_calibration.pooled.auc       — 0.5 means no signal. Read this"
  echo "                                         before pearson_r, because accuracy"
  echo "                                         will not be near 50 %."
  echo "    truth_calibration.by_category      — pooling can manufacture a signal"
  echo "                                         when easy items both agree more"
  echo "                                         and are more often right."
  echo "    truth_calibration.grading          — the denominators. If"
  echo "                                         units_with_no_label is close to"
  echo "                                         units_total the models ignored the"
  echo "                                         output format and nothing else in"
  echo "                                         the block means anything."
  echo "  Output: $out  (see ground_truth_items.csv for every graded item)"
  mkdir -p "$out"
  python3 -m swarmbly_v0 run \
    --backend openai --embedder api \
    --prompts prompts/ground_truth.json \
    --rho 1.5 --n 4 --k 1,3,5 \
    --candidates 2 --seed 0 \
    --out "$out" 2>&1 | tee "$out/run.log" || true
  echo "  -> $out/report.html"
  echo "  -> $out/summary.json  (truth_calibration)"
}

run_v3c() {
  local out="results/v3c-$STAMP"
  bold ""
  bold "== V3c — does agreement predict quality? =="
  echo "  k complete replicas per micro-task, one per family, aligned and scored."
  echo "  The number that matters is the correlation between the per-unit"
  echo "  agreement score and judged acceptability. If it is flat, the confidence"
  echo "  map is decoration and the paper must say so."
  echo "  Output: $out"
  mkdir -p "$out"
  python3 -m swarmbly_v0 run \
    --backend openai --embedder api \
    --rho 1.5 --n 4 --k 1,3,5 \
    --candidates 2 --seed 0 \
    --out "$out" 2>&1 | tee "$out/run.log" || true
  echo "  -> $out/report.html"
}

run_v4() {
  local out="results/v4-$STAMP"
  bold ""
  bold "== V4 — how big is a semantic fragment, and can an editor repair the seam? =="
  echo "  Three questions in one grid, because they are the same question seen"
  echo "  from three sides."
  echo ""
  echo "  1. FRAGMENT SIZE. Every run since 14 August fixed N at 3 or 4 and swept"
  echo "     k instead, so the whole truth-calibration arc sat on one point of a"
  echo "     curve without saying so. Re-examining the V0 run finds that curve"
  echo "     to be its one durable result: +6.7 % at ~133 tokens per"
  echo "     fragment, +14.0 % at ~66, +35.1 % at ~33, monotone in 7 of 8"
  echo "     categories. It has never been measured against ACCURACY, and the"
  echo "     corpora were too short to reach past 133 tokens. Both are fixed here."
  echo ""
  echo "  2. THE EDITOR. The only post-processing the protocol has ever had is"
  echo "     bridge synthesis, and on 25 August it did harm: it repaired a seam"
  echo "     and became a third paragraph, breaking a constraint it cannot see."
  echo "     The editor arm is paired -- every edited cell has an unedited twin."
  echo ""
  echo "  3. SHAPE. S* is claimed to be a semantic unit, not a token count, so it"
  echo "     should differ between a topic, a row group and a dependency step."
  echo ""
  echo "  rho is swept at 2.0 and 3.0, not 1.5: the reachable floor grows with N"
  echo "  (rho_floor = (sum|task_i| + N*|header_i|) / |P|), and at N=6 on this"
  echo "  corpus the floor is already 1.99. Cells below their floor are flagged"
  echo "  rho_reachable=false; compare tax across N WITHIN one rho, never across."
  echo ""
  echo "  4. THE CARRY. The first V4 run found dependency_chain costing +47.2 %"
  echo "     at the widest fragment where prose cost +5.1 % on fragments of the"
  echo "     same size. The cause was not fragment size. At rho = 2.0 NOT ONE"
  echo "     packet carried a predecessor block: it was optional context, third"
  echo "     in priority, funded from slack that ran out first, so every"
  echo "     successor was asked to divide a number nobody had told it. The"
  echo "     carry is now mandatory where a task text consumes a prior value,"
  echo "     and typed -- every labelled value rather than the lead sentence."
  echo ""
  echo "  Predictions, stated before the run so they can fail:"
  echo "    - tax and accuracy both improve monotonically with fragment size;"
  echo "    - the typed carry raises dependency_chain accuracy sharply and moves"
  echo "      long_prose not at all -- there is nothing to type in prose, so a"
  echo "      change there means the arms differ for some other reason;"
  echo "    - rho rises slightly under the carry. Completeness is bought, not"
  echo "      found: three values cost more to send than one;"
  echo "    - the editor raises constraint scores and does NOT raise item"
  echo "      accuracy. It never sees the source, so a rise there means it is"
  echo "      answering from its own knowledge and the arm is contaminated;"
  echo "    - aggregate claims are wrong more often than local ones, and"
  echo "      truth_calibration.by_claim is where a confidence map could finally"
  echo "      have two classes that differ in correctness rather than only in"
  echo "      agreement."
  echo ""
  echo "  Read, in order:"
  echo "    fragment_size_curve.points      -- tax_balanced and accuracy_balanced"
  echo "                                      against tokens_per_fragment."
  echo "    carry_effect                    -- accuracy_delta_by_category first,"
  echo "                                      then rho_delta as its price."
  echo "    editor_effect                   -- apply_rate, mean_constraint_gain,"
  echo "                                      and accuracy_delta as the guard."
  echo "    truth_calibration.by_category   -- dependency_chain by level is which"
  echo "                                      STEP the chain broke at."
  echo "  Output: $out"
  [ -f prompts/complex.json ] || python3 scripts/make_complex.py
  mkdir -p "$out"
  python3 -m swarmbly_v0 run \
    --backend openai --embedder api \
    --prompts prompts/complex.json \
    --rho 2.0,3.0 --n 2,4,6,8 --k 1,3 --editor --typed-carry \
    --candidates 2 --seed 0 \
    --out "$out" 2>&1 | tee "$out/run.log" || true
  echo "  -> $out/summary.json"
  echo "  -> $out/composition_traces.md"
}

case "$TIER" in
  smoke)
    out="results/smoke-$STAMP"
    bold ""
    bold "== Smoke — two prompts, minimal grid. Proves the wiring, measures nothing. =="
    mkdir -p "$out"
    python3 -m swarmbly_v0 run \
      --backend openai --embedder api \
      --rho 1.0,1.5 --n 2 --k 1,3 --max-prompts 2 \
      --out "$out" 2>&1 | tee "$out/run.log"
    bold ""
    bold "Smoke run finished. If the numbers above look sane, run:"
    echo "  ./scripts/run_ollama.sh all"
    ;;
  v0)  run_v0 ;;
  v3c) run_v3c ;;
  v3c-gt) run_v3c_gt ;;
  v3c-ff) run_v3c_ff ;;
  v4) run_v4 ;;
  all) run_v0; run_v3c ;;
  *)   die "unknown tier '$TIER'. Use: smoke | v0 | v3c | v3c-gt | v3c-ff | v4 | all" ;;
esac

bold ""
bold "== Done =="
echo "Before quoting any number from these runs, check run_metadata.json for:"
echo "  harness_validation_only : must be false (it is true only for the mock backend)"
echo "  embeddings_degraded     : must be false, or tau_sem carries no meaning"
echo "  n_families_mean         : must be 3 in the k>1 rows, or agreement is not evidence"
