# V7 — the frozen benchmark, and what is already answered

Your redesign, assessed against what the harness now does and what the last three
runs settled. I agree with nearly all of it. The main correction is that **two of
your five tests have already run**, and one of them came back negative in a way
that removes an arm from V7.

---

## 1. Where your plan already landed

| your item | state |
|---|---|
| Test 0 — fault injection, CI speed, no LLM | **done.** `tests/test_instrument.py`, twelve injected faults, each paired with a clean control |
| statistical unit = prompt, not sentence | **done.** `swarmbly_v0/stats.py`, cluster bootstrap; `n_clusters` printed beside `n_records` |
| always paired: same prompt, same contract, one condition changed | **done** |
| dev corpus separate, thresholds frozen before the final | **done.** `prompts/tables24.json` carries its own split and SHA-256; `--split final` refuses without a dev run and compares digests |
| one hypothesis, one declared estimator, one failing control | **done.** `tables-dev` / `tables-final` |
| runner rejects a run if real ρ deviates | **done.** `assert_packet_invariants` raises `PacketInvariantError` outside `RHO_TOLERANCE` (5 %); `rho_fidelity` still reports per cell |
| runner rejects if a packet lacks its contract | **done.** The contract header is mandatory in `build_packet` and checked in `assert_packet_invariants` |
| runner rejects if a dependent task lacks its carry | **done.** The carry is mandatory — counted into `packing_floor`, not funded from slack — and checked per packet |
| below-floor cells excluded from every figure | **done.** `publishable()` is the single gate; rows are dropped, not annotated |
| a failed tier aborts loudly instead of warning | **done.** `run_tier` stamps `FAILED`, the script exits non-zero with `ABORTED TIERS:` |
| k never exceeds the distinct family count | **done.** `run_ollama.sh` refuses per tier against `NFAM` |

## 2. Two of your five tests are answered

### Test 1 — `table_summary` at N=2. **Answered: criterion not met.**

`docs/RESULTS_TABLES_FINAL.md`. Sixteen prompts, declared cell, frozen τ_sem,
control behaving.

**+3.26 %, CI [−0.02 %, +6.93 %].** The criterion requires the upper bound below
5 %; it is 6.93 %. Median prompt +1.16 %, eight of sixteen at or below zero, and
on the full score including seam classes the fragmented answer is *better* than
the baseline. The cost is small and the criterion demanded certainty the sample
could not give.

**Consequence for V7:** do not re-ask this question with the same estimator. A
ratio against a baseline that can score 1.000 is maximally sensitive — one prompt
(`bonded`, baseline 1.000) contributed 1.3 of the 3.3 points. V7 should declare
an estimator robust to that **before** it runs: a paired difference in raw score,
or a ratio with a floor on the denominator, or the median with a bootstrap
interval. Choose one now, not after seeing the numbers.

### Test 3 — V3c as triage. **Answered: no.**

You framed the right question — *does reviewing the lowest-agreement 20 % catch
more errors than reviewing 20 % at random* — and it now has an answer across
three runs on the declared estimator (Mantel-Haenszel odds ratio, prompt as
stratum):

| | dev-1 | dev-2 | final (n=16) |
|---|---|---|---|
| aggregate claims | OR 3.47 | OR 0.26 | **OR 1.24**, CI [0.25, 3.75] |

An order of magnitude of variation and an interval straddling 1.0 on the largest
sample. Accuracy by agreement value is no longer monotone: higher agreement does
not mean higher accuracy.

**Consequence for V7:** your own rule applies — *"if the lift does not clearly
exceed 1, consensus does not justify itself as a confidence mechanism and should
remain a diversity/selection mechanism, not a risk signal."* So **drop the
consensus arm from V7.** It is not a null result waiting for more data; it is
three attempts with inconsistent signs. Keep k>1 available in the harness as a
selection mechanism, measure its cost, and stop asking it to predict error.

That also simplifies V7: five arms instead of six, and no agreement threshold to
calibrate.

## 3. What V7 should be

Agreed on the split: **the harness stays as the diagnostic laboratory, V7 is a
separate frozen package.** New directory, own generator, own evaluator, minimal
runner reusing only the protocol interfaces. `swarmbly_v0/` is not rewritten.

```
benchmark_v7/
    graph.py       fact graph -> instance, with canonical answers
    instances/     generated, frozen, digested, split dev/final
    evaluate.py    independent of swarmbly_v0.metrics — deliberately
    run.py         minimal runner over the protocol interfaces
```

**`evaluate.py` must not import the harness's metrics.** The defect that cost
this project four documents was a scorer whose behaviour depended on metadata
about the partition. A benchmark that shares that scorer inherits the risk. Its
first test is the arm-neutrality invariant: *the same answer scores the same
however the prompt was cut.*

### The four task classes

Map, Reduce, Chain, Compose, as you specify. One note on Reduce: it is the class
where the current protocol is weakest and the one your fact graph makes properly
measurable for the first time — aggregate claims were wrong 36 % of the time
against 8 % for local ones, consistently across runs. That contrast is the most
durable finding the project has, and Reduce is built to test it.

### The arms

| arm | what it isolates |
|---|---|
| monolithic | the model's ceiling |
| **fragmented + oracle context** | whether the partition is viable *in principle* |
| fragmented, real | the cost of router + packer + assembler |
| real + selective carry | the causal effect of state transport |
| real + editor | the causal effect of formal repair |

**The oracle arm is the best idea in your proposal and it is cheap.** Every
failure this project spent weeks on — a missing contract, a rationed predecessor
block, a metric that was not arm-neutral — would have shown as *oracle fine, real
broken*, which localises the fault to the packaging in one reading. It should be
the first arm implemented, not the last.

### What the runner must refuse

Your three, made blocking rather than advisory:

1. a packet without its contract;
2. achieved ρ outside tolerance of target;
3. a dependent task without its mandatory carry.

Plus one from this session: **a corpus or code digest that does not match what
the declared thresholds were fitted on.** All four abort the run rather than
annotate it. An advisory that has to be read is an advisory that gets skipped —
`rho_fidelity` has now reported the same N=8 drift in four consecutive runs and
nothing stopped.

**Status: the first three are now blocking in the existing harness.**
`assert_packet_invariants` raises rather than warns on all three, and the
mandatory-carry and mandatory-header changes in `swarmbly_v0/packing.py` mean
the conditions it checks are conditions the packer now satisfies by
construction. A fourth gate has been added alongside them: `publishable()`
drops below-floor rows from every figure rather than annotating them, which is
the same principle applied to reporting rather than to dispatch — a note beside
a printed number does not travel with the number. V7 inherits all four; it
should not re-implement them, and its runner must not weaken any of them to
advisory.

### Metrics

Yours, unchanged: claim accuracy and coverage, fabrication rate, aggregate
accuracy, accuracy by chain depth, repetition and contract compliance, and cost
in context/calls/latency/retries. Blind human evaluation as external validation
of coherence, never as the arbiter of correctness.

One addition: **report the seam-error rate separately from any quality ratio.**
A monolithic answer has no seams and cannot incur those errors however incoherent
it is; folding them into a ratio against it charges the fragmented arm for a
category the baseline is exempt from, and the charge grows with N. That is
exactly how the coherence tax came to read +22.9 % where the corrected figure
reads +3.3 %.

## 4. What I would add to your plan

**A stated limit.** A fact-graph corpus is synthetic and its answers are
canonical by construction. That is what makes it measurable, and it is also why a
pass on V7 does not transfer to real documents. V7 can establish *the protocol
does not lose information it was given*; it cannot establish *the protocol works
on your documents*. Say so in the benchmark's own README, before the first
result, so it is a design property and not a caveat added under pressure.

**Retire the judge explicitly.** It accepted 100 % of 1 502 units on the last
run — fourth consecutive run at or above 93 %. It is not an instrument on
grounded prose and should be removed from V7 rather than carried and ignored.

**Fix the packer before V7 measures anything at N>2. — Done.** Achieved ρ had
sat at ~3.91 against a target of 3.5 at N=8 in four runs. Three distinct defects
were responsible: the per-level budget allocation re-computed each task's
`desired` on every topological pass, so a late integration node claimed slack an
earlier level had already reserved; the contract header was rationable context
rather than mandatory content; and `packing_floor` omitted both the header and
the mandatory carry, so `rho_reachable` came back true for cells that then
overshot. ρ now lands within 5 % of target at N ∈ {2, 4, 8} wherever the target
is above the floor, and collapses to the floor with `reachable=False` where it
is not. V7 can measure at N>2.

## 5. Order

Your priority was *instrument → table_summary at N=2 → chain carry → V3c triage →
integration*. Two of those are done and one is answered negatively, so:

1. ~~**The four blocking checks**, in the existing harness.~~ **Done this
   session** — three blocking invariants plus the `publishable()` reporting gate.
2. ~~**Fix ρ at N=8.**~~ **Done this session** — three packer defects, ρ within
   tolerance at N ∈ {2, 4, 8} above the floor.
3. **The carry test** — your Test 2, the one genuinely open question, and now the
   first outstanding item. Four arms,
   N=2 first, N=6 only if there is an effect. New chains, operations the model
   solves monolithically, so the control separates state transport from
   arithmetic.
4. **`benchmark_v7/`**: fact graph, oracle arm, evaluator, runner. Map and Chain
   first — Map establishes the floor, Chain is where the carry result lands.
5. **Reduce and Compose**, then the integration run with only the mechanisms that
   passed.

The editor stays as you describe — no source access, allowed-facts ledger, applied
only when it improves constraints, its tokens reported outside ρ. It is the
best-evidenced module and does not need another campaign.
