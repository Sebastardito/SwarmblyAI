---
status: current
lang: en
---

# Pre-registration — the interaction between node strength and the fragmentation tax

**25 September 2026 · written BEFORE running the analysis**

Published together with `RESULTS_2026-09-25_interaction_EN.md`, which reports
that the hypothesis **did not survive**. The pre-registration is published
anyway, and above all for that reason: it is the document that stopped a false
finding from being confirmed.

This document fixes the hypothesis, the tests, the refusal conditions and the
death conditions **before** the data are touched with this design. It exists
because the finding that motivates the analysis was found by looking at the
data, and a finding found that way is not confirmed with the same degrees of
freedom that produced it.

Data: `swarmbly_ref/data/benchmark.jsonl`, 341 runs, sha256
`d94bb9cc7694d0f7…`, frozen before this was written.

---

## 1. Where the hypothesis comes from (declaration of origin)

> **Later note, added on publication.** That aggregate was subsequently **refused**: it is confounded with the output budget and has not been measured. The analysis below never depended on its being correct — it starts from the fact that it mixes cells of opposite sign — but the reader should not carry the figure away on its own.

Reviewing `REPORT_REAL.md` it was observed that the aggregate tax (−18.32 %)
mixes cells of opposite sign, and that in the mono/frag/SC table the models with
a low monolithic baseline gained a great deal from fragmenting while those with
a high baseline lost. An exploratory analysis with a threshold chosen by eye
(`mono < 0.5`) gave −73 % and +15 % in the two strata.

**That analysis is exploratory and does not count as confirmation.** Its
threshold was chosen after seeing the data and its statistic has a defect that
Section 3 describes. What follows is the design that does count.

---

## 2. Hypothesis

> **H-INT.** The fragmentation tax depends on node strength: the better a node
> solves the task without fragmenting, the more fragmenting costs it.
> Equivalently, fragmentation rescues weak nodes and harms strong ones.

Directional prediction: **positive association** between node strength and the
tax, where `tax = (mono − frag)/mono · 100` (positive = fragmenting is worse).

---

## 3. The defect that forces a change of statistic

`tax = 1 − frag/mono` carries `mono` in the denominator. If the tax is
correlated with the `mono` of **the same cell**, the association appears partly
by construction: the measurement noise in `mono` enters twice, with signs that
reinforce each other. A cell whose `mono` is low by chance produces a very
negative tax without anything real having happened.

It is exactly the kind of check that claims more than it measured, so the design
avoids it:

> **Node strength is estimated *leave-one-out*: that model's mean monolithic
> score over ALL THE OTHER tasks.** Predictor and outcome then come from
> disjoint data, and the mathematical coincidence disappears.

It is the same precaution `T0RR` already applied to reputation ("no leakage from
the held-out task").

---

## 4. Tests

### 4.1 Primary — H-INT with the LOO predictor

For each cell `(task, model)` with comparable monolithic and fragmented cells:

- `LOO_strength(model, task)` = mean of that model's monolithic scores on all
  tasks **other** than this one.
- `tax(task, model)` = `(mono − frag)/mono · 100` on that task.

**Statistic:** Spearman between `LOO_strength` and `tax`, with a permutation p
(50 000, seed 11) **clustered by task**, so that cells of the same task are not
treated as independent.

**H-INT holds if** ρ > 0 with p < 0.05.

### 4.2 Length control

The same test restricted to cells where **the fragmented text is NOT longer than
the monolithic one** (`ratio ≤ 1.0`). If the association holds there, it is not
verbosity.

### 4.3 Ceiling control

The same test excluding cells with `mono ≥ 0.90`. A node with a near-maximal
score can only lose, so part of the association could be lack of headroom rather
than a real effect.

### 4.4 Secondary — stratified table

Descriptive, not confirmatory. The threshold is fixed **mechanically** as the
**median of the corpus's monolithic scores**, computed before looking at the
result, not chosen. It is accompanied by a **threshold sweep** over the whole
interquartile range, to show that the result does not depend on the cut point.

---

## 5. Refusal conditions (the analysis refuses, it does not guess)

1. **< 20 groups (tasks)** in any test → refuse (`MIN_CLUSTERS`).
2. **< 8 cells** in the length-controlled stratum → refuse in that test and say
   so, rather than reporting an underpowered null.
3. **Zero variance** in `LOO_strength` → refuse.
4. **Minimum attainable p > 0.05** with the observed values → refuse for lack of
   power.
5. If the corpus does not reproduce its sha256 → stop everything.

## 6. Death conditions

**H-INT dies if** any of these occurs:

- ρ ≤ 0 in the primary test, or p ≥ 0.05.
- The association **disappears under the length control** (§4.2): then what was
  measured was verbosity and the finding is withdrawn.
- The association **disappears when the ceiling is excluded** (§4.3): then it
  was lack of headroom and not an effect of fragmentation.
- The threshold sweep (§4.4) shows that the sign of a stratum changes within the
  interquartile range: then there are not two regimes, there is a gradient with
  no useful cut point, and the stratified table must not be published.

## 7. What this analysis does NOT decide

- **It does not re-test the abandonment criterion.** The criterion requires
  60–72 prompts from a single category; these are cells from several categories.
  What it does is show that the aggregate is not interpretable, not replace it.
- **It does not establish causality about the mechanism.** That fragmenting
  rescues weak nodes does not say *why*.
- **It does not enlarge the sample.** The weak, length-controlled stratum will
  remain small; enlarging it requires running more cells, and that is outside
  this analysis.

## 8. Amendments

Any change to this document after the first run is recorded here with a date and
a reason. A declared amendment counts; a silent one does not.

*(no amendments at the time of the first run)*

---

*Swarmbly AI — Sebastián A. Espinoza-Ulloa · Spanish companion:
`PREREGISTRATION_2026-09-25_interaction_ES.md`. Results:
`RESULTS_2026-09-25_interaction_EN.md`.*
