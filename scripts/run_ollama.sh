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
#   ./scripts/run_ollama.sh v4        ~16 h     the whole grid: size, editor, carry
#   ./scripts/run_ollama.sh tables-dev   ~1 h   ONE hypothesis, on 8 prompts
#   ./scripts/run_ollama.sh tables-final ~2 h   the same, evaluated once on 16
#   ./scripts/run_ollama.sh all       ~5-7 h    v0 + v3c, sequentially
#
# tables-dev and tables-final are the shape the later work takes: one causal
# claim per run, a declared cell, a control that can fail, and a corpus split so
# that no threshold is fitted on the data it then judges. The wide grids above
# answer the maximum-statistic question -- "does some cell pass?" -- which is
# the question that made V0's go/no-go unfalsifiable.
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

# The highest k this tier will ask for. The header of this script has claimed
# since it was written that the script "refuses to proceed ... if the highest k
# in a tier exceeds the family count". It did not: only the >=5 check above
# existed, and nothing read the tier's own --k list. That is not a hypothetical
# gap -- it is exactly the contamination that ruined the 24 August k=5 arm, where
# three families were loaded, k swept to 5, and `select_diverse_nodes` quietly
# repeated two of them. Mean agreement moved 0.705 -> 0.700 from k=3 to k=5,
# which is the signature of adding echoes rather than estimators, and the arm had
# to be discarded after the fact. `n_families_mean` recorded the truth in a
# column no gate read.
#
# Derived from the tier's own --k list, not hand-copied. The first version of
# this check hard-coded a table and got `smoke` wrong on its first run: smoke
# sweeps `--k 1,3` and the table said 1, so the gate printed "max k here: 1"
# while k=3 was dispatched. With five families loaded nothing was contaminated,
# but the check would not have caught a family shortage on the one tier an
# operator runs first to find out whether anything is wrong. A gate that reads a
# table beside the thing it guards drifts from it; this one greps the invocation.
TIER_MAX_K=$(awk -v tier="$TIER" '
  $0 ~ "^run_" tier_fn "\\(\\)" { infn = 1 }
  infn && /--k /  { for (i = 1; i <= NF; i++) if ($i == "--k") { print $(i+1); exit } }
' tier_fn="$(echo "$TIER" | tr '-' '_')" "$0" 2>/dev/null \
  | tr ',' '\n' | sort -rn | head -1)
# The case tiers (smoke) and any tier whose --k could not be read fall back to
# the largest k any tier in this script sweeps. Failing SAFE here means demanding
# MORE families than needed, which costs a disk pull; failing open would mean
# running a contaminated k arm, which costs a retracted result.
if ! [ "${TIER_MAX_K:-}" -ge 1 ] 2>/dev/null; then
  TIER_MAX_K=$(grep -o -- '--k [0-9,]*' "$0" | awk '{print $2}' | tr ',' '\n' \
               | sort -rn | head -1)
  TIER_MAX_K="${TIER_MAX_K:-5}"
fi
[ "$NFAM" -ge "$TIER_MAX_K" ] || die "tier '$TIER' sweeps k up to $TIER_MAX_K but \
only $NFAM distinct families are available. select_diverse_nodes would repeat a \
family to fill k, and replicas drawn from one lineage share their errors: they \
agree confidently on the same mistake. The k=$TIER_MAX_K arm would be \
contaminated upward and unusable, which has already happened once."
echo "  max k here:   $TIER_MAX_K (families available: $NFAM)"

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
TIERS_FAILED=""

# --------------------------------------------------------------------------- #
# Every tier used to end its run line with `| tee "$out/run.log" || true`.
#
# `set -o pipefail` is on, and the Python layer raises PacketInvariantError when
# a packet loses its contract header, when a dependent task loses its carry, or
# when the achieved rho misses its target -- the three gates that exist to stop
# an invalid run reaching a table. `|| true` discarded every one of them. The
# tier then printed "-> report.html" and "== Done ==", and `all` proceeded to
# the next tier, so an aborted run was reported to the operator as a completed
# one and the only trace was a stack trace in the middle of a log nobody reads
# after a six-hour sweep.
#
# `write_csv` runs once after the whole sweep, so an aborted tier leaves no
# results.csv at all -- the data was never at risk. The operator was.
#
# So: a failed tier is recorded, its directory is stamped FAILED so that a
# reader who finds the directory later cannot mistake it for a completed run,
# and the script exits non-zero at the end. Subsequent tiers still run, because
# they are independent measurements and an overnight sweep should not lose four
# of them to the first one that broke.
# --------------------------------------------------------------------------- #
run_tier() {
  local name="$1" out="$2"; shift 2
  local status=0
  "$@" 2>&1 | tee "$out/run.log" || status=$?
  if [ "$status" -ne 0 ]; then
    {
      echo "tier=$name"
      echo "exit_status=$status"
      echo "stamp=$STAMP"
      echo "This run ABORTED. Any file in this directory is partial output from"
      echo "a run the harness refused to complete. Do not quote a number from it."
    } > "$out/FAILED"
    warn "TIER '$name' FAILED (exit $status). Marked $out/FAILED."
    warn "Nothing in $out is publishable. See the end of $out/run.log."
    TIERS_FAILED="$TIERS_FAILED $name"
    return 1
  fi
  echo "  -> $out/report.html"
  return 0
}

run_v0() {
  local out="results/v0-$STAMP"
  bold ""
  bold "== V0 — the coherence tax as a function of rho (hypothesis H1) =="
  echo "  This is the make-or-break measurement: how much quality is lost to"
  echo "  fragmentation and reassembly, and whether any rho gets it under 5%."
  echo "  Output: $out"
  mkdir -p "$out"
  run_tier v0 "$out" \
    python3 -m swarmbly_v0 run \
    --backend openai --embedder api \
    --rho 1.0,1.25,1.5,2.0 --n 2,4,8 --k 1 \
    --candidates 2 --seed 0 \
    --out "$out" || return 1
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
  run_tier v3c-ff "$out" \
    python3 -m swarmbly_v0 run \
    --backend openai --embedder api \
    --prompts prompts/free_form.json \
    # rho 2.5, not 1.5. Recomputed from the code: the packing floors on this
    # tier's corpus run 1.51-2.37, so EVERY cell at rho=1.5 sat below its own
    # floor -- 0 of 15 reachable on ground_truth, 0 of 11 on free_form, 0 of 8 on
    # prompts.json. Below the floor a packet holds its bare task and nothing
    # else, so these tiers were measuring agreement between replicas answering
    # context-free micro-tasks, which is not the configuration the protocol
    # proposes. `publishable()` now drops those rows, so at 1.5 the tier would
    # burn four to six hours and emit nothing at all.
    #
    # This makes the run NOT comparable to the v3c runs of August, which were all
    # at 1.5 and therefore all below floor. That is the point: those runs
    # measured a degenerate configuration. It does not resurrect the confidence
    # map -- no signal is no signal -- but it does mean the odds ratios of 3.47,
    # 0.26 and 1.24 describe a condition nobody chose.
    --rho 2.5 --n 3 --k 1,3,5 \
    --candidates 2 --seed 0 \
    --out "$out" || return 1
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
  run_tier v3c-gt "$out" \
    python3 -m swarmbly_v0 run \
    --backend openai --embedder api \
    --prompts prompts/ground_truth.json \
    # rho 2.5, not 1.5. Recomputed from the code: the packing floors on this
    # tier's corpus run 1.51-2.37, so EVERY cell at rho=1.5 sat below its own
    # floor -- 0 of 15 reachable on ground_truth, 0 of 11 on free_form, 0 of 8 on
    # prompts.json. Below the floor a packet holds its bare task and nothing
    # else, so these tiers were measuring agreement between replicas answering
    # context-free micro-tasks, which is not the configuration the protocol
    # proposes. `publishable()` now drops those rows, so at 1.5 the tier would
    # burn four to six hours and emit nothing at all.
    #
    # This makes the run NOT comparable to the v3c runs of August, which were all
    # at 1.5 and therefore all below floor. That is the point: those runs
    # measured a degenerate configuration. It does not resurrect the confidence
    # map -- no signal is no signal -- but it does mean the odds ratios of 3.47,
    # 0.26 and 1.24 describe a condition nobody chose.
    --rho 2.5 --n 4 --k 1,3,5 \
    --candidates 2 --seed 0 \
    --out "$out" || return 1
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
  run_tier v3c "$out" \
    python3 -m swarmbly_v0 run \
    --backend openai --embedder api \
    # rho 2.5, not 1.5. Recomputed from the code: the packing floors on this
    # tier's corpus run 1.51-2.37, so EVERY cell at rho=1.5 sat below its own
    # floor -- 0 of 15 reachable on ground_truth, 0 of 11 on free_form, 0 of 8 on
    # prompts.json. Below the floor a packet holds its bare task and nothing
    # else, so these tiers were measuring agreement between replicas answering
    # context-free micro-tasks, which is not the configuration the protocol
    # proposes. `publishable()` now drops those rows, so at 1.5 the tier would
    # burn four to six hours and emit nothing at all.
    #
    # This makes the run NOT comparable to the v3c runs of August, which were all
    # at 1.5 and therefore all below floor. That is the point: those runs
    # measured a degenerate configuration. It does not resurrect the confidence
    # map -- no signal is no signal -- but it does mean the odds ratios of 3.47,
    # 0.26 and 1.24 describe a condition nobody chose.
    --rho 2.5 --n 4 --k 1,3,5 \
    --candidates 2 --seed 0 \
    --out "$out" || return 1
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
  echo "  rho is swept at 3.5 and 4.5. The floor grows with N because the"
  echo "  preamble is paid N times (rho_floor = (sum|task_i| + N*|header_i|)/|P|),"
  echo "  and on this corpus long_prose at N=8 needs 3.41. At 2.0/3.0 a quarter"
  echo "  of the grid sat below its own floor and overshot the target, which"
  echo "  would have made the fragment-size trend partly an artifact of rho"
  echo "  drifting upward exactly where the tax is highest. Compare tax across N"
  echo "  WITHIN one rho, never across."
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
  run_tier v4 "$out" \
    python3 -m swarmbly_v0 run \
    --backend openai --embedder api \
    --prompts prompts/complex.json \
    --rho 3.5,4.5 --n 2,4,6,8 --k 1,3 --editor --typed-carry \
    --candidates 2 --seed 0 \
    --out "$out" || return 1
  echo "  -> $out/summary.json"
  echo "  -> $out/composition_traces.md"
}

run_tables_dev() {
  local out="results/tables-dev-$STAMP"
  bold ""
  bold "== tables-dev — ONE question, on the half of the corpus you may look at =="
  echo ""
  echo "  THE HYPOTHESIS, stated before the run so it can fail:"
  echo "    table_summary at rho=3.5, N=2 costs less than 5 % against its"
  echo "    monolithic baseline -- the upper bound of the interval below 0.05,"
  echo "    not the point estimate."
  echo ""
  echo "  This is the only cell this project has produced that ever came close."
  echo "  The run of 26 August put it at +5.8 % with a 95 % interval of"
  echo "  [-2.2 %, +14.5 %]: not a pass, not a refutation. The interval is that"
  echo "  wide because it rests on EIGHT prompts. Sixteen more roughly halve it."
  echo ""
  echo "  THE FAILING CONTROL: N=8 runs in the same grid. V6 put it at +12.1 %."
  echo "  A test whose control cannot fail proves nothing, so if N=8 also passes"
  echo "  the instrument is not discriminating and neither number is evidence."
  echo ""
  echo "  WHAT IS DELIBERATELY ABSENT: no editor, no typed carry, one rho. Each"
  echo "  is a separate causal claim and this run makes one. The carry has"
  echo "  nothing to type in a table -- V6 measured it at -0.003 there -- and"
  echo "  the editor's effect on constraints is a different question from the"
  echo "  cost of fragmentation."
  echo ""
  echo "  WHAT MAY BE DECIDED HERE, and nowhere after: tau_sem, the agreement"
  echo "  bin edges, the flagging rate, and which arm gets reported. These eight"
  echo "  prompts are the whole budget for looking at data. The sixteen in"
  echo "  --split final are evaluated once, afterwards, with nothing left to"
  echo "  choose, and the runner refuses to start them without --tau."
  echo ""
  echo "  SECONDARY, and dev-only: the aggregate AUC. V5 read 0.605, V6 read"
  echo "  0.481 once the single-replica sentinel was removed -- at chance, with"
  echo "  a curve that stops being monotonic in the bin holding 59 % of the"
  echo "  items. k=1,3 is swept so that question has data, but it is not what"
  echo "  this run is powered for and no threshold rides on it."
  echo ""
  echo "  Read, in order:"
  echo "    go_no_go                        -- declared_cell must read"
  echo "                                      {category: table_summary, rho: 3.5,"
  echo "                                      n_tasks: 2}. n_prompts, not"
  echo "                                      n_observations, is the sample size."
  echo "    fragment_size_curve.points      -- N=2 against N=8, the control."
  echo "    truth_calibration.by_claim      -- excluded_single_replica must be"
  echo "                                      non-zero and the remaining n must"
  echo "                                      be k=3 rows only."
  echo "  Output: $out"
  [ -f prompts/tables24.json ] || python3 scripts/make_tables.py
  python3 scripts/make_tables.py --verify \
    || die "prompts/tables24.json does not match what make_tables.py builds; a
    threshold frozen against the old digest no longer applies."
  mkdir -p "$out"
  run_tier tables-dev "$out" \
    python3 -m swarmbly_v0 run \
    --backend openai --embedder api \
    --prompts prompts/tables24.json --split dev \
    --rho 3.5 --n 2,8 --k 1,3 \
    --declare 'table_summary@rho=3.5@N=2@k=1' \
    --declare 'table_summary@rho=3.5@N=8@k=1' \
    --candidates 2 --seed 0 \
    --out "$out" || return 1
  echo ""
  # This used to print "--tau <number>", which the final tier REFUSES to accept
  # and for a stated reason: a bare number cannot carry which corpus it was
  # fitted on, and the table corpus changed once already. `run_tables_final`
  # takes the dev run's DIRECTORY and reads the threshold, the corpus digest and
  # the split out of its run_metadata.json. So the tier's own closing advice
  # contradicted the tier that consumes it -- an operator following this script's
  # instructions could not proceed.
  bold "  tau_sem fitted on dev. Carry it to the final half by naming THIS RUN:"
  echo ""
  echo "    bash scripts/run_ollama.sh tables-final $out"
  echo ""
  echo "  Not the number. The directory. It carries the threshold, the corpus"
  echo "  digest it was fitted against, and the split -- and the final tier checks"
  echo "  all three before it starts."
  python3 -c "import json;print('  (for the record, tau_sem =', json.load(open('$out/run_metadata.json'))['tau_sem'], ')')" 2>/dev/null || true
  echo "  -> $out/summary.json"
}

run_tables_final() {
  local out="results/tables-final-$STAMP"
  local dev="${2:-}"
  [ -n "$dev" ] || die "name the dev run this final run inherits its threshold from:
    bash scripts/run_ollama.sh tables-final results/tables-dev-<stamp>

  tau_sem is fitted inside a run. Passing it by hand as a number is one typo
  away from a threshold that was never fitted on anything, and it cannot carry
  WHICH CORPUS it was fitted on -- which matters, because the table corpus
  changed on 27 August when a tense directive was added. Naming the dev run
  lets this script read both the threshold and the corpus digest and check them."
  # Name the mistake instead of reporting its consequence. Passing "--tau 0.68"
  # produced `ERROR: --tau/run_metadata.json does not exist`, which tells the
  # operator nothing about what they did wrong -- and this script's own dev tier
  # used to instruct exactly that, so it was a mistake the script invited.
  case "$dev" in
    --tau|--tau=*|-t)
      die "this tier takes the dev run's DIRECTORY, not a tau value:
    bash scripts/run_ollama.sh tables-final results/tables-dev-<stamp>

  A bare number cannot carry which corpus it was fitted on, and this corpus has
  changed once already. Naming the run lets this script read the threshold, the
  frozen corpus digest and the split, and refuse if any of the three disagrees
  with the corpus about to be judged. Latest dev run on disk:
$(ls -1dt results/tables-dev-* 2>/dev/null | head -3 | sed 's/^/    /' || echo '    (none found)')" ;;
    -*)
      die "unexpected option '$dev'. This tier takes the dev run's directory:
    bash scripts/run_ollama.sh tables-final results/tables-dev-<stamp>" ;;
  esac
  [ -d "$dev" ] || die "'$dev' is not a directory. This tier takes the dev run's
  directory, not a threshold and not a file:
    bash scripts/run_ollama.sh tables-final results/tables-dev-<stamp>"
  [ -f "$dev/run_metadata.json" ] || die "$dev/run_metadata.json does not exist.
  That run did not complete, or it is not a swarmbly results directory."

  local tau dev_sha now_sha dev_split
  tau="$(python3 -c "import json;print(json.load(open('$dev/run_metadata.json'))['tau_sem'])")"
  dev_sha="$(python3 -c "import json;print(json.load(open('$dev/run_metadata.json')).get('corpus_frozen_sha256',''))")"
  dev_split="$(python3 -c "import json;print(json.load(open('$dev/run_metadata.json')).get('corpus_split',''))")"
  # The FROZEN digest -- over id, split and prompt text -- which is what
  # make_tables.py --verify prints and what a frozen threshold is pinned to.
  # Not the raw file digest: those differ, and comparing the wrong pair would
  # either never match or match when it should not.
  now_sha="$(python3 -c "import json;print(json.load(open('prompts/tables24.json'))['_frozen']['sha256'])")"

  [ "$dev_split" = "dev" ] || die "$dev ran on '$dev_split', not on the dev split.
  A threshold fitted on the final half, or on the whole corpus, is fitted on the
  data it is about to judge. That is the leakage the split exists to close."

  if [ -z "$dev_sha" ]; then
    die "$dev has no corpus_frozen_sha256: it predates the digest being recorded, so
  there is no way to confirm its threshold was fitted on THIS corpus. Re-run
  tables-dev before the final half. Roughly one hour, and it also picks up the
  coherence-metric correction of 27 August."
  fi
  if [ "$dev_sha" != "$now_sha" ]; then
    die "the corpus changed since $dev ran.
    dev:  $dev_sha
    now:  $now_sha
  tau_sem = $tau was fitted on different prompts, so applying it here would
  carry a threshold across a corpus change. Re-run tables-dev on this corpus
  first: bash scripts/run_ollama.sh tables-dev"
  fi
  bold ""
  bold "== tables-final — evaluated once, with nothing left to choose =="
  echo ""
  echo "  THE HYPOTHESIS -- the original pre-registration, unchanged:"
  echo ""
  echo "    table_summary at rho=3.5, N=2, k=1 costs less than 5 % against its"
  echo "    monolithic baseline."
  echo ""
  echo "    Estimator:  mean relative degradation on the ARM-COMPARABLE score."
  echo "    Interval:   cluster bootstrap over prompts."
  echo "    Passes if:  the UPPER bound of the 95 % interval is below 0.05."
  echo ""
  echo "  Nothing here was chosen after seeing data. The cell, the threshold and"
  echo "  the estimator are the ones this project started with. What changed is"
  echo "  the instrument: the coherence metric was not arm-neutral, and scoring"
  echo "  one identical answer through the two arms conventions returned 0.9375"
  echo "  and 0.5000 -- an apparent tax of +46.7 % on text that never changed."
  echo ""
  echo "  On the dev half of 27 August, with that corrected and a tense directive"
  echo "  in the contract, the cell reads +1.57 % with an interval of"
  echo "  [-4.69 %, +7.26 %]. THREE OF EIGHT PROMPTS ARE NEGATIVE. It fails only"
  echo "  on the upper bound, on eight prompts; sixteen more roughly halve it."
  echo "  This is the first time the final half has had a question worth spending"
  echo "  on."
  echo ""
  echo "  THE FAILING CONTROL: N=8 in the same grid. Dev puts k=1 there at"
  echo "  +14.0 %, interval [+7.9 %, +19.2 %], no overlap with N=2. If N=8 also"
  echo "  clears 5 % the instrument is not discriminating and neither figure is"
  echo "  evidence."
  echo ""
  echo "  CAVEAT ON THE CONTROL: N=8 ran at rho 3.90 against a target of 3.5 on"
  echo "  both dev runs -- 11.5 % over, with rho_floor at 1.13, so the packer is"
  echo "  overshooting rather than being forced. The N=8 arm therefore receives"
  echo "  MORE context than N=2 and still does worse, which is conservative for"
  echo "  the conclusion. Read rho_fidelity and say so rather than averaging it in."
  echo ""
  echo "  WHAT IS NO LONGER DECLARED: the aggregate-claim confidence map, which"
  echo "  was the declared hypothesis for this tier on 26 August. It failed its"
  echo "  first independent test -- OR 3.47 became 0.26, and the monotone"
  echo "  accuracy curve that justified it inverted. Three non-replications now"
  echo "  (V5 to V6, dev-1 to dev-2). It is still COMPUTED and reported below,"
  echo "  because the data is free once the run happens, but nothing rides on it"
  echo "  and no threshold is set against it."
  echo ""
  echo "  THE GRID: N=2 and N=8, k=1 and k=3. k=1 carries the headline -- k is a"
  echo "  separate mechanism from fragmentation and a mean of the two belongs to"
  echo "  neither arm. k=3 is swept so the confidence map has data to be"
  echo "  reported from."
  echo ""
  echo "  Read, in order:"
  echo "    falsifiable_go_no_go[table_summary@rho=3.5@N=2@k=1]"
  echo "      ci95 upper bound against 0.05, and n_prompts -- NOT n_observations."
  echo "    the same cell at N=8, k=1  -- the control, which must fail."
  echo "    rho_fidelity               -- name any cell out of tolerance."
  echo "    truth_calibration.flag_effect_by_claim  -- reported, not declared."
  echo "  Output: $out"
  python3 scripts/make_tables.py --verify \
    || die "the corpus has moved since dev; the frozen threshold no longer applies."
  mkdir -p "$out"
  run_tier tables-final "$out" \
    python3 -m swarmbly_v0 run \
    --backend openai --embedder api \
    --prompts prompts/tables24.json --split final \
    --rho 3.5 --n 2,8 --k 1,3 --tau "$tau" \
    --declare 'table_summary@rho=3.5@N=2@k=1' \
    --declare 'table_summary@rho=3.5@N=8@k=1' \
    --candidates 2 --seed 0 \
    --out "$out" || return 1
  echo ""
  bold "  The declared test:"
  python3 -c "
import json
s=json.load(open('$out/summary.json'))
cells=s.get('falsifiable_go_no_go',{})
for key,role in (('table_summary@rho=3.5@N=2@k=1','(UNDER TEST)'),
                 ('table_summary@rho=3.5@N=8@k=1','(control, must fail)')):
    c=cells.get(key)
    if not c: print(f'    {key}: absent'); continue
    ci=c.get('ci95')
    ok = ci is not None and ci[1] < 0.05
    print(f'    {key}')
    print(f'      {role:<22} point={c.get(\"point_estimate\")}  CI95={ci}  '
          f'prompts={c.get(\"n_prompts\")}  -> {\"PASS\" if ok else \"fail\"}')
rf=s.get('rho_fidelity',{})
print(f'    rho within tolerance: {rf.get(\"within_tolerance\")}'
      + ('' if rf.get('within_tolerance') else f\"  (worst: {rf.get('worst')})\"))
" 2>/dev/null || true
  echo "  -> $out/summary.json"
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
    bold "Smoke run finished. It proved the wiring; it measured nothing."
    echo ""
    echo "  Two prompts at N=2 on a corpus whose packing floor is 1.42-1.68, swept"
    echo "  at rho 1.0 and 1.5. Most of that grid is BELOW its own floor, so expect"
    echo "  dropped rows and a curve built from one or two cells. That is the gate"
    echo "  working, not a fault."
    echo ""
    bold "  Next, in this order:"
    echo "    bash scripts/run_ollama.sh tables-dev              ~1 h   fits tau on 8 prompts"
    echo "    bash scripts/run_ollama.sh tables-final --tau <T>  ~2 h   the declared verdict, 16 held out"
    echo ""
    echo "  Those two are what a claim rests on: one hypothesis, a cell named before"
    echo "  the run, and a control required to fail."
    echo ""
    echo "  NOT 'all' yet. It runs v0, whose rho sweep (1.0-2.0) sits almost entirely"
    echo "  below the packing floor -- 13 of 96 cells were reachable -- so it will now"
    echo "  produce empty curves by design. That is why V0's published result was"
    echo "  withdrawn. Redefine its grid above the floor (>=2.7 at N=8) before"
    echo "  spending hours on it. See docs/REVISION_2026-08-12.md section 7."
    ;;
  v0)  run_v0 || true ;;
  v3c) run_v3c || true ;;
  v3c-gt) run_v3c_gt || true ;;
  v3c-ff) run_v3c_ff || true ;;
  v4) run_v4 || true ;;
  tables-dev) run_tables_dev || true ;;
  tables-final) run_tables_final "$@" || true ;;
  # `|| true` on a tier dispatch, and on no run line anywhere. `run_tier` has
  # already recorded the failure
  # in TIERS_FAILED and stamped the directory; this only stops `set -e` killing
  # the script before the summary below can name what broke, and lets an
  # overnight `all` finish its independent tiers. The exit status is restored at
  # the bottom.
  all) run_v0 || true; run_v3c || true ;;
  *)   die "unknown tier '$TIER'. Use: smoke | v0 | v3c | v3c-gt | v3c-ff | v4 | tables-dev | tables-final | all" ;;
esac

if [ -n "$TIERS_FAILED" ]; then
  bold ""
  die "ABORTED TIERS:$TIERS_FAILED
Each of those directories carries a FAILED marker and holds no results.csv.
The harness refused to complete them, which is the gate working. Read the end
of the tier's run.log for the invariant that was violated, fix it, and re-run.
Do not quote a number from a run that appears in this list."
fi

bold ""
bold "== Done =="
echo "Before quoting any number from these runs, check run_metadata.json for:"
echo "  harness_validation_only : must be false (it is true only for the mock backend)"
echo "  embeddings_degraded     : must be false, or tau_sem carries no meaning"
echo "  n_families_mean         : must be 3 in the k>1 rows, or agreement is not evidence"
