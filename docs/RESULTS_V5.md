# V5 — power, the typed carry, and where the confidence map finally has a signal

**Run:** `results/v4-20260824-214220`. Twenty prompts across three task shapes,
five model families over Ollama, transport `openai-sdk`, 0 transport retries,
embeddings not degraded, τ_sem calibrated to 0.575. ρ ∈ {2.0, 3.0}, N ∈ {2, 4, 6,
8}, k ∈ {1, 3}, editor and typed-carry arms both paired. 320 fragmented cells per
N — four times V4's count.

Three questions were open. One is answered and the answer is negative, one is
**inconclusive because the instrument was wrong**, and one produced the best
result the confidence map has ever had.

---

## 1. The threshold question is answered, and less kindly than V4 suggested

V4 left two shapes looking plausibly under the 5 % coherence-degradation
threshold. Quadrupling the observations was supposed to settle it, and it did.

| cell | ρ | V4 (n=12) | V5 (n=64) | 95 % CI | passes |
|---|---|---|---|---|---|
| table_summary | 3.0 | +3.4 % | **+2.7 %** | [−0.7 %, +6.3 %] | no |
| table_summary | 2.0 | +3.1 % | +6.5 % | [+2.1 %, +10.9 %] | no |
| long_prose | 3.0 | +4.2 % | **+7.6 %** | [+4.9 %, +10.4 %] | no |
| long_prose | 2.0 | +6.0 % | +8.2 % | [+5.2 %, +11.4 %] | no |

The interval halved, as intended. What it revealed is that **`long_prose` is
confidently *above* the threshold** — its lower bound now excludes 5 % at both ρ
values. V4's +5.1 % was an optimistic small-sample estimate, and more data moved
it the unwelcome way.

`table_summary` at ρ = 3.0 remains the only candidate: +2.7 %, interval
[−0.7 %, +6.3 %]. With n = 64 the remaining width is real variance between
prompts rather than sampling noise, so more prompts of the same kind will narrow
it slowly. This is now a question about how tightly the claim needs to be made,
not about whether the experiment was big enough.

The curve itself replicates cleanly at four times the cell count:

| N | tokens/fragment | tax (balanced) | dependency_chain | long_prose | table_summary |
|---|---|---|---|---|---|
| 2 | 229 | +23.4 % | +57.7 % | +7.9 % | +4.6 % |
| 4 | 115 | +39.7 % | +74.6 % | +18.4 % | +26.0 % |
| 6 | 76 | +49.8 % | +85.7 % | +28.3 % | +35.5 % |
| 8 | 57 | +62.6 % | +97.3 % | +41.4 % | +49.0 % |

Monotone, `comparable_across_n: true`, 320 cells per point. The shape ordering
from V4 holds: at identical fragment size the ordered chain costs an order of
magnitude more than prose or tables.

## 2. The typed carry: the prediction failed, and the instrument is why

The prediction was that carrying every labelled value verbatim would raise chain
accuracy sharply. It did the opposite:

| | plain summary | typed carry | delta |
|---|---|---|---|
| dependency_chain | 0.303 | 0.255 | **−0.049** |
| table_summary | 0.617 | 0.618 | +0.001 |
| ρ achieved | 2.690 | 2.698 | +0.008 |

`table_summary` moving by +0.001 is the control behaving correctly — there is
nothing to type where answers carry no labels. ρ rose by the small amount
predicted. Only the effect the mechanism exists for went the wrong way.

**Before concluding the mechanism fails, look at what the corpus was asking.**
Accuracy by step, pooled over both arms:

| step | operation | accuracy |
|---|---|---|
| 1 | multiply | 67.4 % |
| 2 | **reduce by N percent** | **3.6 %** |
| 3 | divide, round down | 58.1 % |
| 4 | add | 51.5 % |
| 5 | **increase by N percent** | **0.0 %** |
| 6 | divide, round down | 4.0 % |
| 7 | subtract | 7.4 % |
| 8 | multiply | 3.1 % |

The two percentage steps are the two catastrophic ones. Two of eight steps were
**unanswerable by these models regardless of what the packet contained** — and
sitting at positions 2 and 5 they poison everything downstream, which is most of
the chain. Steps 6, 7 and 8 sit below 8 % not because subtraction is hard but
because step 5 was wrong for everyone.

A carry can only be measured by whether a *carriable* value survives a packet
boundary. A step the model could not compute while holding the whole prompt says
nothing about carrying. **The −0.049 is measured through an instrument dominated
by a different failure, and it does not answer the question.**

### What the run did establish about the carry

Echoing is real and quantified. Of the chain's wrong answers, **13.4 % are
exactly the predecessor's value repeated**, concentrated at the percentage steps:
35.3 % at step 5, 18.9 % at step 2. Handed `[04]=370` and asked for step 5, a
model that cannot compute the percentage returns 370.

That is a genuine hazard the typed form creates and the prose summary does not:
presenting values as `[NN]=value` makes echoing the path of least resistance. It
explains a third of the step-5 failures — not the majority, but enough that the
next design of the carry should be **selective**, offering only the value the
successor's own text names, rather than everything the predecessor produced.

### The corpus is rebuilt, and two invariants are now enforced

Every operation is one the 2–4B class demonstrably performs: add, subtract,
multiply by a small integer, divide with no remainder. The rebate is nudged so
step 3's division is exact rather than introducing a rounding rule.

Two properties are now enforced by tests rather than by hope. The chain is
**strictly linear** — a first rebuild accidentally had step 3 consume step 1,
which the test caught. And **no two intermediates coincide**: `chain_northwind`
came out with 550 at both step 2 and step 5, which would let a model that merely
echoes score a later step right by accident. That is exactly the reading that
would make a broken carry look like a working one.

## 3. Aggregation: the first calibration signal that survives its own guard

Six attempts to calibrate the confidence map failed because the predictor
saturated — agreement between 0.85 and 0.96 with almost no spread. Splitting
graded units by whether they assert something requiring sight of rows the
fragment may not hold gives, for the first time, two classes that differ in
**correctness**:

| claim class | n | accuracy | mean agreement | AUC |
|---|---|---|---|---|
| aggregate | 800 | 57.1 % | 0.836 | **0.605** |
| local | 568 | 68.3 % | 0.699 | **0.660** |

Three things matter here. The accuracy gap replicates V4's finding at five times
the sample. The agreement distributions differ, so the predictor is no longer
saturated. And the AUCs are **within class**, not pooled — so they are not the
between-population artifact that produced a wrong headline three times in this
project.

0.605 and 0.660 are modest. They are also the first numbers in this project where
agreement predicts correctness above chance inside a homogeneous population.
Retiring the confidence map on the earlier evidence would have been wrong, and
the reason it looked retirable was that nothing had yet been measured on a
population where correctness varied.

## 4. The editor replicates

| measure | V4 (144 pairs) | V5 (320 pairs) |
|---|---|---|
| apply rate | 52.1 % | 61.6 % |
| mean constraint gain | +15.4 % | **+14.9 %** |
| accuracy delta | 0.000 | **−0.003** |

The refusal holds at more than twice the sample: the editor recovers about
fifteen per cent of mechanical checks and moves item correctness by nothing. It
has the assembled answer and the contract and no access to the source, so it can
repair form and cannot repair fact — and the measurement continues to say so.

## What is not interpretable, and one thing that could not be checked at all

The per-item sidecar does not record which carry arm produced each record, so
accuracy by step **could not be split between the arms**. The step table above is
pooled, which is enough to show the percentage steps are broken for everyone and
not enough to say how the carry behaves at each depth. The column is added for
the next run; this analysis simply could not be done.

## What follows

1. **Re-run the chain on the rebuilt corpus.** The carry question is open, not
   answered. Nothing else needs to change to ask it properly.
2. **Make the carry selective.** Offer the successor the value its own text
   names, not every value the predecessor produced. Echo accounts for a third of
   the failures at the step where the model is weakest.
3. **`table_summary` at ρ = 3.0 is the one live threshold candidate.** +2.7 %,
   interval [−0.7 %, +6.3 %], n = 64.
4. **Calibrate within claim class.** It is the only split so far where both
   agreement and correctness vary, which is what the previous six attempts were
   missing.
