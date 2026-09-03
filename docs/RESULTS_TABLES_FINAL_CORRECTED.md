# tables-final on a corrected instrument — the criterion is NOT MET, and the mean is the wrong statistic

**Run:** `results/tables-final-20260903-153237`. The final half of
`prompts/tables24.json`, frozen digest `0c5cb7e2…`, verified before the run.
Sixteen held-out prompts, ρ = 3.5, N ∈ {2, 8}, k ∈ {1, 3}. τ_sem **inherited**
at 0.680 from `tables-dev-20260903-150427` — the runner reads it from that run's
metadata and refuses to start if its corpus digest or split disagrees. 80 rows.

**This half is spent. There is no second one.**

> **Provenance, checked before anything below was read.**
> `harness_validation_only: false`, `embeddings_degraded: false` — real models,
> real embeddings. `rows_excluded_below_floor: 0` — every cell sat above its own
> packing floor, so ρ is an axis here rather than a label.
> `rho_fidelity.within_tolerance: true`. Code fingerprint
> `4abed34a…`, seed 0. Five distinct model families, `n_families_mean` 3.0 in the
> k > 1 rows.

---

## 1. The verdict

Declared before the run and unchanged since the original pre-registration:
`table_summary` at ρ = 3.5, N = 2, k = 1 costs less than 5 %, judged on the
**upper bound** of a 95 % bootstrap interval clustered by prompt.

| cell | point | 95 % CI (16 prompts) | verdict |
|---|---|---|---|
| **N = 2, k = 1 — under test** | **+2.30 %** | **[−2.05 %, +7.49 %]** | **NOT MET** — short by 2.49 points on the upper bound |
| N = 8, k = 1 — control, must fail | +16.23 % | [+11.33 %, +20.28 %] | fails as required |

The control behaves: its interval excludes zero, sits entirely above the
threshold, and **does not overlap** the arm under test. The instrument separates
N = 2 from N = 8. Without that, neither figure would be evidence.

The criterion is not met and is not being rewritten. The point estimate clears
5 % comfortably; the interval does not, and the criterion was written against the
interval precisely so that a favourable point estimate could not carry it alone.

## 2. The mean is the wrong statistic for this result

The headline hides the finding. Per prompt, at N = 2, k = 1:

| | count |
|---|---|
| coherence tax **negative** (fragmenting was better) | 6 |
| coherence tax **exactly zero** | 5 |
| coherence tax positive | 5 |
| **at or below zero** | **11 of 16** |

**The median prompt loses exactly nothing.** And the mean is not merely pulled by
the positive prompts — it is *manufactured* by two of them:

| prompt | tax at N = 2 |
|---|---|
| `tbl24_outturn` | **+28.50 %** |
| `tbl24_bonded` | **+23.08 %** |
| `tbl24_demurrage` | +7.14 % |
| `tbl24_clearance` | +6.67 % |
| `tbl24_holdover` | +4.55 % |

Those two sum to **+0.516 against a total of +0.368 — 140 % of it.** Remove them
and the mean over the remaining fourteen prompts is **−1.06 %**: fragmenting into
two is, on those, very slightly *better* than not fragmenting at all.

So "fragmentation costs 2.3 %" is a poor description of what happened. What
happened is: **on eleven of sixteen table-summarisation prompts, splitting the
work in two was free, and on two of them it was expensive.** The corpus does not
yet say what distinguishes them — but §4 has a strong clue.

## 3. The control, and what N = 8 costs

| | N = 2 | N = 8 |
|---|---|---|
| mean | +2.30 % | +16.23 % |
| median | **0.00 %** | +18.59 % |
| prompts at or below zero | 11 / 16 | **1 / 16** |

At eight fragments the cost is real, consistent and large: fifteen of sixteen
prompts are worse than their monolithic baseline, the median is +18.6 %, and the
interval is nowhere near the threshold. Whatever is free at N = 2 is emphatically
not free at N = 8.

This is the shape the architecture needs: a partition width at which the cost
vanishes for most work, and a width at which it does not. It is also the first
time the two have been measured side by side on a corrected instrument with a
control that could have failed and did not.

## 4. The inversion, which is a mechanism clue and not noise

Sorting by N = 2 cost puts the two expensive prompts at the bottom — and they are
**the only two prompts where N = 2 is WORSE than N = 8**:

| prompt | N = 2 | N = 8 | |
|---|---|---|---|
| `tbl24_outturn` | **+28.50 %** | +13.57 % | N=2 worse by 15 points |
| `tbl24_bonded` | **+23.08 %** | +14.00 % | N=2 worse by 9 points |
| every other prompt | ≤ +7.14 % | ≥ +7.68 % | N=8 worse, always |

More fragments *helping* is not what a coherence-tax story predicts. Whatever
went wrong on `outturn` and `bonded` at N = 2 is therefore unlikely to be
"fragmentation degrades coherence" — that would get worse with N, not better.
It looks like a **partition-quality** failure: the planner's two-way split of
those particular prompts puts a seam somewhere costly, and cutting eight ways
happens to avoid it.

That is a testable claim and it is the single most valuable thing this run
produced. It is **not** tested here.

One further row worth naming: `tbl24_closeout` is negative in *both* arms
(−11.1 % at N = 2, −11.5 % at N = 8) and has the weakest monolithic baseline in
the corpus (0.583). A prompt the monolithic arm handles badly is a prompt where
fragmenting can only help, and it should be read as a baseline failure rather
than a fragmentation success.

## 5. Against the withdrawn measurement

| | 27 Aug (defective instrument) | 3 Sep (corrected) |
|---|---|---|
| point | +3.26 % | **+2.30 %** |
| 95 % CI | [−0.02 %, +6.93 %] | **[−2.05 %, +7.49 %]** |
| median | +1.16 % | **0.00 %** |
| prompts ≤ 0 | 8 / 16 | **11 / 16** |
| verdict | NOT MET | **NOT MET** |

The verdict is unchanged and the point estimate moved down by about a point, as
the direction of the defects predicted — every one of the twelve was one-sided
toward a larger apparent tax. The interval is slightly *wider*, not narrower,
which is the honest consequence of removing an instrument that was manufacturing
agreement between prompts.

The distribution moved much more than the mean did: the median went from +1.16 %
to exactly zero, and three more prompts crossed to the free side. **The corrected
instrument did not change the answer to the declared question. It changed what
the data is about.**

## 6. What is reported and not declared

**k = 3 is expensive and buys nothing measurable.** Consensus by multiple
alignment costs roughly 14 points at N = 2 and 25 at N = 8 against the same cells
at k = 1. Against four measurements of whether agreement predicts quality — one
flat correlation and three ground-truth odds ratios of 3.47, 0.26 and 1.24 — that
is a quarter of the output quality spent on a signal there is no evidence for.

**The judge accepted 100 % of 1517 units.** Total saturation. The harness
withheld the correlation rather than printing an uninterpretable number, which is
the behaviour that should have existed on 14 August. Any judge-based figure from
this run is absent, not zero.

**The entity grid remains unusable on this corpus:** 24 cells excluded for a
near-zero monolithic denominator. Read the absolute differences, never the ratio.

## 7. What this does and does not license

**It does not license the claim the criterion tests.** At ρ = 3.5, N = 2, on 16
held-out prompts, the upper bound of the interval is 7.49 % against a threshold
of 5 %. The architecture has not cleared the bar it set for itself.

**It does license a narrower and more useful claim**, which the criterion was not
designed to ask: on this corpus, at two fragments, **the median cost of
fragmentation is zero**, and the mean is carried by two prompts out of sixteen.

That difference matters for the design rather than for the paper. A threshold
criterion asks "is the average cost acceptable?", which is the wrong question for
a routing protocol — the router does not have to accept the average, it decides
per request. A bimodal cost with an identifiable boundary is worth more than a
low uniform one, because it is **routable**. V1's decomposability classifier
stops being an optimisation and becomes the mechanism the rest of the design
depends on.

**Next, in order of value:**

1. **Diagnose `outturn` and `bonded`.** Two prompts carry 140 % of the mean and
   are the only two where N = 2 beats N = 8. Read their seams and their two-way
   plan. If it is a partition-quality failure the planner can be fixed, and the
   declared cell would then likely clear its threshold — which is a reason to be
   careful, not encouraged: fixing the planner *after* seeing which prompts hurt
   is fitting on the final half. Any planner change must be evaluated on a new
   corpus, not on these sixteen.
2. **Widen the corpus** before re-testing the criterion. With a between-prompt
   variance this size, sixteen prompts cannot bring a 9.5-point interval under a
   5-point threshold, whatever the true effect is. That is an arithmetic fact
   about the design, not a result.
3. **Drop k > 1 from the coherence grid.** It costs a quarter of the quality and
   answers a question that has been withdrawn.
