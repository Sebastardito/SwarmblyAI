---
status: current
note: >
  The current composition verdict. comp-final-v2 reads -0.35 on a corpus
  nobody had seen.
lang: en
---
# The two final verdicts — September 5, 2026

Four runs: `comp-dev-once` (re-run), `comp-final-once`, `comp-dev-v2`,
`comp-final-v2`. Identical code fingerprint across all four (`136fc431…`),
corpora verified, control failing in all of them, zero rows excluded.

**Both verdicts are NOT MET.** And even so this is, by a wide margin, the
strongest result the project has produced.

---

## 1. The three final splits, side by side

All at ρ = 4.0, N = 3, k = 1, 24 clusters, same estimator, same criterion.

| run | monolithic | fragmented | difference | 95% CI | verdict |
|---|---|---|---|---|---|
| `comp-final` (Sep 4, **no** dedup) | 0.873 | 0.649 | **+22.40** | [+16.15, +28.51] | NOT MET by 23.51 |
| `comp-final-once` (v1, **with** dedup) | 0.873 | 0.797 | **+7.64** | [+1.42, +13.61] | NOT MET by **8.61** |
| `comp-final-v2` (v2, **with** dedup) | 0.813 | 0.816 | **−0.35** | [−8.33, +7.64] | NOT MET by **2.64** |

On the same v1 corpus, with the same split, with the only difference being
enforcing `term_once` in the assembler: **+22.40 → +7.64**. Almost **fifteen
points** recovered on the final split, and the failure went from 23.51 points to
8.61.

On a corpus nobody had seen: **−0.35 points**. The fragmented arm scored *above*
the monolithic one. It fails the criterion by 2.64 points, and it fails **by the
width of the interval, not by the size of the effect**.

---

## 2. The shape of the result

| run | loses | ties | **wins** |
|---|---|---|---|
| Sep 4, no dedup | 19 | 5 | **0** |
| v1, with dedup | 13 | 5 | **6** |
| v2, with dedup | 8 | 6 | **10** |

In v2, fragmenting into three **won on 10 out of 24 prompts** and lost on 8. It
is a coin flip. In the September 4 run it did not win a single one in
twenty-four.

---

## 3. The baseline ceiling: where the cost that remains lives

`baseline_at_ceiling` exists because **where the monolithic arm scores 1.000 the
paired difference cannot be negative**. Separating the prompts by that:

| run | at the ceiling | Δ there | off the ceiling | **Δ there** |
|---|---|---|---|---|
| Sep 4, no dedup | 8 | +36.04 | 16 | +15.57 |
| v1, with dedup | 8 | +22.40 | 16 | **+0.26** |
| v2, with dedup | 4 | +14.17 | 20 | **−3.25** |

**On the prompts where the difference is free to move in both directions, the
cost with dedup is +0.26 in v1 and −3.25 in v2.** Zero, twice, on two
independent corpora.

All of the measured cost that remains is concentrated on the prompts where the
monolithic arm was perfect. And here one has to be honest, because it admits two
readings:

* **It is real:** fragmenting costs ~2 constraints when the monolithic arm
  satisfies them all, and ~0 when the monolithic arm already fails some.
  Fragmenting does not reach perfection but it does match imperfection.
* **It is censoring:** if the true per-prompt effect were noise centered on
  zero, on the ceiling prompts only the unfavorable half is observed (the
  monolithic arm cannot be beaten), and the mean of a half-normal is positive. A
  positive Δ there is **exactly** what would be seen under a null effect with
  censoring.

The data do not separate the two with 24 clusters. What can be said: **the
difference between v1 (+7.64) and v2 (−0.35) is explained almost entirely by how
many prompts sit at the ceiling** — 8 out of 24 against 4 out of 24. There is no
need to invoke "another corpus, another number".

---

## 4. What this does NOT say

**It is not a pass.** The declared criterion is the upper bound below 5 points,
and it is +7.64 in v2. It failed, twice, on preregistered hypotheses.

**The two corpora do not agree on magnitude.** +7.64 against −0.35. Their
intervals overlap on [+1.42, +7.64], so they are compatible, but **neither of
the two should be cited alone as "the" cost**. Replication did its job: it
detected that the number depends on the corpus, and the ceiling table says why.

**It says nothing about quality.** The dedup deletes sentences.
`enforce_term_once` removed 55 sentences in v1 and 75 in v2 at N=3. The score
counts satisfied constraints; whether the text ends up better or worse to read
is measured by nothing here.

**It says nothing about N = 8.** The control failed hard in both (+69.62 and
+49.79) — the instrument separates the arms, which is the check that matters
most. And the dedup barely fires there: **1 sentence** across 24 cells, against
55 and 75 at N=3. At N=8 the problem is omission, and you cannot deduplicate
what was never written.

**It is still with 3B models, and on tasks that fit twenty times over in the
window of the smallest node.** The limit in `REVISION_2026-09-05` has not moved.

---

## 5. Two minor things that are now settled

**The pipeline is deterministic.** The re-run of `comp-dev-once` at 13:21 gave
**identical** numbers to the one at 12:05 — same τ (0.585), same +8.61, the same
rate cell by cell. The question I left open ("if the estimates come out
different, that is between-run variance") has an answer: at seed 0 there is no
between-run variance. What changes between corpora is the corpus.

**The v2 tiers replicate the v1 ones.** `baseline_at_ceiling` 3 out of 12 in
both devs, `mean_baseline` 0.842 against 0.844. The new generator produces
equivalent difficulty, which was the condition for v2 to be worth anything.

---

## 6. Where the project stands

| result | status |
|---|---|
| `term_once` in the assembler recovers ~15 points on the final split | **Measured, preregistered, replicated on two corpora** |
| Off the baseline ceiling, the cost of fragmenting into 3 is zero | Measured twice, +0.26 and −3.25 |
| The declared criterion (upper bound < 5) is still unmet | NOT MET by 8.61 (v1) and 2.64 (v2) |
| The control at N=8 always fails | The instrument separates the arms |
| 98.6% of the *previous* cost was parallelism, not the planner | `comp-oracle`, unchanged |
| Agreement between models does not predict correctness | Closed, six measurements |
| ρ is not the lever; N is | Closed |

**What blocks a pass now is the width of the interval, not the effect.** With 24
clusters and a per-prompt deviation of this size, the upper bound does not drop
below 5 points even if the mean is zero. To pass, more clusters are needed — a
corpus of 60 or 72 prompts — or a measure with less per-prompt variance.

That is an experimental design decision, not a fix to the architecture, and it
is worth deciding with a cool head: **raising the number of clusters until a null
effect passes the criterion is a way of getting the result one wants.** If it is
done, how many clusters and why is declared beforehand, and the corpus is
generated before looking at anything.

## What is still pending and did not change

The case the architecture exists for is still untested: **a task that does not
fit in one node**. The largest prompt in the project measures 375 tokens against
a window of 8,192. Everything above measures how much it costs to split
something that did not need splitting — and that cost is now approximately zero,
which is good news and is still not the question.
