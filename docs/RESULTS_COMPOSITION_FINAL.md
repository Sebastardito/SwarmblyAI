# The composition criterion: NOT MET by 23.5 points, and the tax could not see it

**Run:** `results/comp-final-20260904-123403`. `prompts/composition.json`, split
`final` — 24 prompts, ρ = 4.0, N ∈ {3, 8}, k = 1, five model families. 72 rows.

> **Provenance.** `harness_validation_only: false`, `embeddings_degraded:
> false`, τ_sem 0.585 fitted on the dev half, seed 0,
> **`rows_excluded_below_floor: 0`**, ρ achieved 3.97–4.03 against 4.00,
> `rho_fidelity.within_tolerance: true`. Corpus digest `e9e382b9…`, code
> fingerprint `e3d0a0dc…` — **the same code that fitted τ**, checked by
> `assert_same_code_as_dev` before the run started.

This is the first result in this project produced by the full apparatus: a cell
named in a document written before the run, a threshold set at a value the pilot
data failed, a control required to fail, a frozen corpus split, a cluster floor,
and a verdict on the upper bound. Nothing below was chosen after seeing data.

---

## 1. The verdict

> **Composition at ρ = 4.0, N = 3, k = 1 costs less than 5 points of constraint
> satisfaction against its monolithic baseline.**

| | |
|---|---|
| monolithic | **0.873** (8 of 24 at 1.000) |
| fragmented N=3 | **0.649** |
| **paired difference** | **+22.40 points** (median +22.50) |
| 95 % CI, clustered by prompt | **[+16.15, +28.51]** |
| n_prompts | **24** (floor 20) |
| **VERDICT** | **NOT MET — over by 23.51 points on the upper bound** |

**The control fails as required.** N = 8 in the same grid: **+70.56 points**, CI
[+64.58, +75.62]. The instrument separates the arms by a factor of 3.2, and a
control that had passed would have made both numbers worthless.

**Nineteen of 24 prompts lost ground. Five lost exactly nothing. None gained.**
`n_at_or_below_zero` is 5 and every one of those is exactly 0.000 — so on this
corpus fragmenting a composition never improved it.

The dev half, run first and on different prompts, put the same cell at **+18.40
points** with CI [+9.79, +29.72]. The final estimate sits inside that interval.
The held-out half produced no surprise.

## 2. The finding that matters more than the verdict

The same 24 texts, scored by the instrument this project has been built around:

| | declared cell (N=3) | control (N=8) |
|---|---|---|
| **coherence tax** | **+0.14 %** | +20.45 % |
| **constraint score** | **+22.40 points** | +70.56 points |

**The BooookScore-like coherence tax reads +0.14 % on the cell where a
mechanical count of the same strings finds 22.4 points lost.** Sixteen of the 24
prompts read **exactly +0.000**. One reads −0.448.

Section 4 of `RESULTS_V3C_FF_COMPOSITION.md` said this on three prompts, as a
description. It is now a pre-registered measurement on 24, with a control, and
it replicates.

**Why the tax cannot see it here.** Seventeen of the 24 monolithic BooookScore
baselines are exactly **1.000**. A tax defined as *(monolithic − fragmented) /
monolithic* against a denominator pinned at the ceiling can only read ≥ 0 and
has almost no resolution. The corpus was built with three difficulty tiers to
give the **constraint score** room to move, and it worked — that baseline is
0.873, not 1.000. Nothing was designed to give the **coherence metric** room,
and it saturated anyway.

The console line to be careful with is the one reading `+10.29 %`. That is the
tax **pooled over N = 3 and N = 8** — the arm under test averaged with the
control that is required to fail. Per arm it is +0.14 % and +20.45 %, and the
mean of those belongs to neither.

## 3. What actually broke

Counted from the text. No judge, no model in the verdict.

| failed check | monolithic | N = 3 | N = 8 |
|---|---|---|---|
| `term_once` | 16 | **34** | 42 |
| `must_mention` | 4 | 9 | **64** |
| `no_repeated_ngram` | 1 | 1 | 1 |
| `no_repeated_sentence` | 0 | 1 | 1 |
| **total failures** | 21 | 47 | 110 |

Two families, and they are opposites:

* **Duplication** dominates at N = 3. `term_once` fails because a term that must
  appear once appears once *per fragment*.
* **Omission** takes over at N = 8. `must_mention` failures go from 9 to 64: with
  eight fragments each writing a slice, required terms stop being covered at all.

`repeated_sentences_cross_task` — two different workers writing the same
sentence — is **0 monolithic, 12 at N=3, 50 at N=8**. This **contradicts** the
free-form run, which reported 0 everywhere and concluded the duplication was
finer than sentence level. On this corpus it is not: whole sentences are being
written twice by different workers. The earlier refinement was true of that
corpus, not of prose composition in general, and it is corrected here.

### The cost falls where there was something to lose

| monolithic baseline | n | mean loss |
|---|---|---|
| **1.000** | 8 | **+0.360** |
| 0.80 – 0.99 | 11 | +0.206 |
| **< 0.80** | 5 | **+0.045** |

Correlation between baseline and loss: **r = +0.705**. Part of that is
mechanical — a baseline of 0.70 caps the loss at 0.70 — but at 1.000 the mean
loss is 0.360, nowhere near its cap, so the pattern is not an artefact of the
ceiling. Where the monolithic arm was already failing checks, fragmenting cost
almost nothing extra. The five prompts that lost exactly zero all have baselines
between 0.700 and 0.833.

## 4. The choice that made the result smaller, and why it was right

`constraint_score_comparable` excludes `paragraph_count` and
`words_per_paragraph`, which the assembler satisfies for one arm and the model
must earn alone in the other. The raw scores:

| arm | raw | comparable |
|---|---|---|
| monolithic | 0.898 | 0.873 |
| fragmented N=3 | **0.514** | **0.649** |

On the raw score the gap is **38.4 points**. On the arm-comparable score it is
**22.4**. Excluding the two assembler-enforced checks **cut the measured effect
nearly in half, in the direction that favours the hypothesis under test** — and
it still fails by 23.5 points on the upper bound.

This is worth stating plainly because every instrument defect this project
found before August leaned the other way.

## 5. The limit of this result, and it is a real one

**`mean_paragraphs`: monolithic 2.0, fragmented N=3 = 7.96, N=8 = 14.13.**

Every prompt says *"Write exactly two paragraphs."* The monolithic arm writes
exactly two. The fragmented arm writes **eight**, and at N = 8 it writes
**fourteen**. Each fragment is producing a complete, full-length answer rather
than a slice of one, and the assembler is concatenating them.

That is not a detail. It is most of the mechanism behind the 22.4 points: a term
that must appear once appears three times **because three workers each wrote a
whole composition**. So the honest statement of what was measured is narrower
than "fragmenting prose costs 22.4 points":

> **This implementation, fragmenting a two-paragraph composition three ways at
> ρ = 4.0, loses 22.4 points of constraint satisfaction against its own
> monolithic baseline.**

It is an end-to-end measurement of the shipped pipeline, which is exactly what
the criterion declared. It is **not** evidence that splitting prose is
inherently expensive, because the fragments were not given a scope they could
respect.

**What separates those two readings is an oracle arm, and composition does not
have one.** `benchmark_v7` has one for fact-graph tasks and it localised a fault
in a single reading on the day it was built. An oracle arm here — each fragment
told explicitly which paragraph, which word budget, and which required terms are
*its* responsibility — would say whether 22.4 points is the cost of division or
the cost of a contract that does not divide the task's constraints. That is the
next measurement, and it is cheap.

Two things that are **not** wrong with this run, checked rather than assumed:
ρ was within tolerance on every cell (3.97–4.03 against 4.00), and no row was
dropped below the packing floor.

## 6. What this settles

**Settled.** The declared criterion has been tested and failed, on a corpus
split before the run, with a control that failed as required and an interval
that does not come within 11 points of the threshold at its lower bound. The
project's central quantitative claim about prose composition, as this
implementation performs it, is refuted rather than unsupported.

**Settled, and larger.** The coherence tax is not a usable instrument for this
workload. It reads +0.14 % where a mechanical count finds 22.4 points, on the
same strings, at the fragmentation level the architecture actually proposes.
Every figure this project has produced about composition — withdrawn or standing
— was measured with it.

**Open.** Whether the 22.4 points is division or contract. §5 says how to find
out.

**Unaffected.** `tables-final`'s verdict on `table_summary` (+2.30 %, CI
[−2.05 %, +7.49 %], NOT MET) stands; it is a different corpus, a different
metric and a different cell.
