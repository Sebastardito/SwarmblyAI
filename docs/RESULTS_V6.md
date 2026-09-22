---
status: partially_withdrawn
stands: the accuracy, agreement and constraint figures
reason: >
  Every coherence tax and every monotone-in-N claim was produced by a metric
  that was not arm-neutral and whose penalty grew with N by construction.
lang: en
---
# V6 — the first run whose instrument was checked before it ran

> ## ⚠ The coherence-tax figures in this document are SUPERSEDED (27 August 2026)
>
> The metric that produced them was not arm-neutral. The monolithic baseline was
> held to a smaller expected-entity set than the fragmented arm, its omissions
> dirtied one sentence where the fragmented arm's dirtied N, and it could not
> incur a seam error at all — so the penalty grew with N by construction.
> Scoring one identical answer through both conventions gives 0.9375 against
> 0.5000. Every coherence tax and every "monotone in N" claim below is affected;
> the accuracy, agreement and constraint figures are not.
>
> `scripts/rescore.py <run>` recomputes a finished run's tax with the corrected
> metric from the run's own assembled answers — but only for runs whose traces
> store the assembler's sentence offsets, which none written before 27 August do.
> For those, the corrected figure can only come from running them again.


**Run:** `results/v4-20260825-184625`. Twenty prompts across three task shapes,
five model families over Ollama, transport `openai-sdk`, **0 transport retries**,
embeddings not degraded, τ_sem calibrated to 0.580 from 240 labelled pairs.
ρ ∈ {3.5, 4.5}, N ∈ {2, 4, 6, 8}, k ∈ {1, 3}, editor and typed-carry arms both
paired. 1 280 fragmented rows, ~16 hours.

This is the first run preceded by an adversarial review of the harness. Nine
defects were found and fixed beforehand, five of which would have made the
numbers meaningless. Two consequences dominate everything below.

---

## 1. Fixing the instrument roughly halved the measured cost

Fragments of `long_prose` had been receiving an answer-sheet directive instead of
their own format block, so the eight-paragraph, 70-to-130-word, mention-once
contract reached **no fragment** while the monolithic baseline kept all of it.
With that fixed:

| N | tokens/fragment | dependency_chain | long_prose | table_summary |
|---|---|---|---|---|
| 2 | 228 | +21.2 % | **+9.7 %** | **+5.8 %** |
| 4 | 114 | +55.1 % | +12.6 % | +11.8 % |
| 6 | 76 | +77.0 % | +15.4 % | +10.8 % |
| 8 | 57 | +100.0 % | **+20.0 %** | **+12.1 %** |

Monotone, `comparable_across_n: true`, one clean cell per point (ρ=3.5, k=1, no
editor, no carry).

Against V5's figures at N=8 — `long_prose` +41.4 %, `table_summary` +49.0 % —
both roughly halve. **V4 and V5 were measuring a missing contract, not a cost of
fragmentation.** The shape ordering survives: at identical fragment size the
ordered chain still costs several times what prose or tables cost.

## 2. The chain corpus fix worked, and ε-compounding is visible for the first time

Replacing the two percentage steps — which the 2–4B class failed at 3.6 % and
0.0 % regardless of context — took chain accuracy from **0.303 to 0.719**. The
instrument now discriminates, and what it shows is the shape the dependency
argument predicts:

| step | accuracy | n |
|---|---|---|
| 1 | 100.0 % | 84 |
| 2 | 94.4 % | 71 |
| 3 | 80.4 % | 46 |
| 4 | 81.8 % | 33 |
| 6 | 16.0 % | 25 |
| 7 | 8.3 % | 24 |
| 8 | 0.0 % | 22 |

That is 1 − (1 − ε)^D made visible: near-perfect at depth 1, decaying through the
middle, collapsing by depth 6. Every earlier attempt to see this was blocked by a
step the models could not compute at all.

Two things in the table are themselves findings. The denominators **fall with
depth** — 84 down to 22 — so a chain does not merely answer later steps wrongly,
it increasingly stops producing a parsable answer at all. And step 5 is absent
because it fell below the reporting threshold, which is the same phenomenon.

## 3. The typed carry: still not resolvable, and now honestly so

| N | plain | typed | delta |
|---|---|---|---|
| 2 | 78.9 % (45/57) | 86.5 % (45/52) | **+7.6** |
| 4 | 50.0 % (7/14) | 58.3 % (7/12) | **+8.3** |
| 6 | 79.1 % (34/43) | 64.5 % (40/62) | **−14.6** |
| 8 | 59.4 % (19/32) | 56.0 % (28/50) | −3.4 |

Pooled: −0.037. But the pooled figure is a **mixture of opposite signs**, not an
effect: the carry helps at coarse partitions and hurts at fine ones, on 12 to 62
records per cell. Nothing here is resolvable at this sample size, and reporting
−0.037 as "the carry does not work" would be reading noise.

The controls behave. `table_summary` moves by −0.003 — there is nothing to type
where answers carry no labels. ρ moves by −0.002, so the mechanism is neither
buying nor spending context.

One observation worth carrying forward: the typed arm produces **more** graded
records at N=6 and N=8 (62 vs 43, 50 vs 32). The scope filter added before this
run stops a fragment being credited for items outside its packet, so these are
in-scope answers — the carry is making successors *answer more*, and at fine
partitions those extra answers are disproportionately wrong.

**The chain arm needs its own run.** Four prompts is too few for an eight-step ×
four-N design, and it is the cheapest part of the corpus to run alone.

## 4. A defect in the go/no-go, of my own making

The criterion filtered on category and ρ but **not on N** — and N is the axis
with by far the largest effect. Pooled over N, `table_summary` at ρ=3.5 reads
+20.9 % and fails comfortably. Restricted to N=2, the fragment size the threshold
question is actually about:

| cell | point | 95 % CI | passes |
|---|---|---|---|
| table_summary @ ρ3.5, N=2 | **+5.8 %** | [−2.2 %, +14.5 %] | no |
| long_prose @ ρ3.5, N=2 | +9.7 % | [+3.8 %, +16.2 %] | no |
| dependency_chain @ ρ3.5, N=2 | +21.2 % | [+15.6 %, +25.0 %] | no |

A criterion written to stop a maximum statistic from passing on noise was itself
**hiding the one live candidate inside a mean**. `n_tasks` is now part of the
declared cell and a test encodes the case.

`table_summary` at the widest fragment remains the only candidate that has ever
come close, and it is still undecided — now on n = 8, because slicing correctly
costs sample. That is the honest state: not a pass, not a refutation, and the
narrowest question the project has left.

## 5. The editor replicates and strengthens

| measure | V5 (320 pairs) | V6 (640 pairs) |
|---|---|---|
| apply rate | 61.6 % | 67.7 % |
| mean constraint gain | +14.9 % | **+21.0 %** |
| accuracy delta | −0.003 | **+0.0006** |

The refusal holds at twice the sample and the gain is larger now that fragments
receive the constraints the editor repairs against. It recovers a fifth of the
mechanical checks and moves item correctness by nothing, which is exactly what a
mechanism with the answer and the contract but not the source should do.

## 6. The "agreement collapse" was my arithmetic — and what it was hiding

*Written after the fact, from the run's own artefacts. The figures first
published in this section were:*

| claim class | n | accuracy | mean agreement | AUC |
|---|---|---|---|---|
| aggregate | 2 359 | 57.0 % | 0.392 | 0.583 |
| local | 6 041 | 93.9 % | 0.391 | **0.477** |

**Both agreement figures were constants, not measurements.** Two populations
whose accuracy differs by 37 points cannot agree to three decimals; that is a
default announcing itself, and I published it as a phenomenon.

The cause is a fix I made before this run. k=1 had produced no gradable records
at all, so the fragmented arm was graded only at k=3 while the baseline is a
single generation — fragmentation and consensus were inseparable. Grading k=1
was right. What went with it was a single-replica `agreement` of **0.0**, under a
comment asserting that this "keeps it out of every calibration by construction".
Nothing kept it out. 0.0 is a legal agreement score, so **8 984 rows — 45 % of
the graded mass — entered the calibration as its least confident items.**

Restricted to k = 3, where agreement is defined:

| claim class | n | prompts | accuracy | mean agreement | AUC | 95 % CI (by prompt) |
|---|---|---|---|---|---|---|
| aggregate | 1 137 | 8 | 65.5 % | **0.813** | 0.481 | [0.414, 0.541] |
| local | 3 210 | 8 | 92.2 % | **0.736** | 0.616 | [0.508, 0.712] |

V5's 0.836 and 0.699 — **replicated**. There was no collapse.

The below-chance AUC has the same origin and is worth stating separately,
because it is the pooling artefact again, the fifth time. The tied-at-zero block
was **95.8 % correct** against 92.2 % for the k=3 rows. A mass of *correct*
items nailed to the bottom of the agreement scale drags the statistic under 0.5.
The instrument was not mis-calibrated; it was being asked about a variable that
did not exist for half its inputs.

**What survives the correction is smaller than either version claimed.** With
intervals resampled over prompts rather than sentences — 8 prompts, not 8 400
sentences:

* **local claims replicate, weakly.** AUC 0.616 [0.508, 0.712] against V5's
  0.660 [0.540, 0.771]. The curve is monotonic (72.7 % → 88.9 % → 92.5 % →
  94.7 %), but the whole spread is 22 points and 48 % of the mass sits in the
  top bin. Range restriction, exactly as in V3c.
* **aggregate claims do not.** AUC 0.481 [0.414, 0.541] — **at chance**, against
  V5's 0.605 [0.537, 0.654]. The curve is no longer monotonic: 16.7 % → 58.2 % →
  78.8 % → **62.2 %**, and the fall is in the top bin, which holds 59 % of the
  items. High agreement stopped predicting correctness for the claims that
  matter most.

That non-replication is a real result and it is the one to carry forward. It
rests on eight prompts, which is why §*What follows* now begins with the corpus.

**Fixed.** `agreement` is `None` where it is undefined; `agreement_truth_calibration`
excludes single-replica records on `k` rather than on the value — a sentinel of
0.5 would have passed a value filter — and reports `excluded_single_replica`
beside the other denominators. `tests/test_instrument.py` injects the fault with
three different sentinels and fails if any reaches the statistic.

## What follows

1. **Twenty-four table prompts, split before anything is fitted.**
   `prompts/tables24.json`, built by `scripts/make_tables.py`: 8 dev / 16 final,
   interleaved, with a SHA-256 in the file and `--verify` to check it.
   Thresholds, bin edges, flagging rates and τ_sem are fitted on dev; final is
   evaluated once. Every interval above rests on 8 prompts, and so does the one
   live threshold candidate.
2. **`table_summary` at ρ=3.5, N=2** is that candidate: +5.8 %, interval
   [−2.2 %, +14.5 %]. Sixteen more prompts roughly halve it.
3. **Run the chain alone.** Four prompts and eight steps cannot answer the carry
   question; the chains are also the cheapest slice to run, roughly two hours.
4. **The aggregate AUC did not replicate.** 0.605 → 0.481, at chance, with a
   non-monotonic curve. This is now the calibration question, and it replaced
   the one I thought I had.
5. **V4 and V5's prose and table figures are superseded**, not refined. They
   measured fragments that never received their contract. V5's agreement
   figures, by contrast, stand — it was V6's that were wrong.
