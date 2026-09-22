---
status: current
lang: en
---
# Pre-registration — the cost of fragmentation on prose composition

**Written:** 4 September 2026, **before** the corpus was run against any real
model. Nothing below may be changed once `comp-final` has been executed; a
figure that moves after the final half is seen is not an estimate of anything.

**Status:** declared, not yet run. `comp-dev` fits τ_sem and checks the corpus
behaves; `comp-final` produces the verdict, once.

---

## 1. Why this exists

The run of 3 September produced the strongest measurement this project has. On
three two-paragraph compositions, graded by counting facts about the string with
no model anywhere in the verdict:

| arm | constraint score (arm-comparable) |
|---|---|
| **monolithic** | **1.000** |
| fragmented N=3, k=1 | 0.864 |
| fragmented N=3, k=3 | 0.786 |
| fragmented N=3, k=5 | 0.857 |

Fourteen to twenty-one points. And on the *same texts*, the BooookScore-like
coherence tax — the quantity this project's go/no-go criterion is written
against, the quantity four withdrawn documents reported — read **+0.000** at
every k.

That finding rested on **three prompts**, with no pre-registered cell, no
control, and no corpus split. `tables24.json` was built to give the coherence
tax exactly that apparatus. **The stronger instrument had the weaker method
behind it**, and a description of three prompts is not evidence about a
workload. This document is the missing apparatus, and building it is worth more
than any further run of the tax.

## 2. The declared hypothesis

> **Prose composition at ρ = 4.0, N = 3, k = 1 costs less than 5 points of
> constraint satisfaction against its monolithic baseline.**

| | |
|---|---|
| **Corpus** | `prompts/composition.json`, split `final` — 24 prompts, digest `e9e382b9…` |
| **Metric** | `constraint_score_comparable` — the share of checks satisfied, excluding `paragraph_count` and `words_per_paragraph` |
| **Estimator** | mean **paired** difference, monolithic − fragmented, one pair per prompt |
| **Interval** | cluster bootstrap over prompts, 10 000 draws, seed 0 |
| **Passes if** | the **upper** bound of the 95 % interval is below 0.05 |
| **Control** | the same cell at **N = 8**, required to **fail** |
| **Refuses if** | fewer than 20 prompts contribute (`MIN_CLUSTERS_FOR_A_VERDICT`) |

Implemented in `experiment.composition_criterion`; the threshold is
`experiment.COMPOSITION_THRESHOLD_POINTS`; the cell is named on the command line
by `--declare-composition`, so the declaration is a fact about the invocation
and is recoverable from `run.log`.

## 3. Every choice above, and what forced it

### Points, not per cent

Ten of the eleven monolithic baselines on 3 September scored exactly **1.000**.
A relative tax `(baseline − fragmented) / baseline` against a denominator pinned
at the ceiling is maximally sensitive exactly where the baseline is best: one
lost check is the entire numerator. It also cannot read below zero, so it can
never show fragmentation costing nothing. The paired difference in points has no
denominator to be sensitive to.

This is a change of estimator, and changing an estimator after it returns an
unwelcome answer is how a project talks itself out of a result — so it is worth
being precise about what is and is not being changed. The **coherence tax
criterion is untouched**: `tables-final` still declares a relative degradation
under 5 %, and its verdict of 4 September (+2.30 %, CI [−2.05 %, +7.49 %], NOT
MET by 2.49 points) stands. What is new is a *second* criterion, on a *different
metric*, for a *different corpus*. The tax was never a good instrument for prose
and §4 of `RESULTS_V3C_FF_COMPOSITION.md` is the measurement that says so.

### Paired within prompt

Both arms answer the same prompt, so the prompt's difficulty cancels. Until
`constraint_score_comparable` became a per-row column on 4 September the score
lived only inside `_trace` and could only be reported as a **mean over a
condition** — two unpaired means, with prompt difficulty left in the estimate.
That is how the coherence tax spent four runs being sensitive to which prompts
happened to land in which cell.

### The upper bound

A criterion cleared by the point estimate is the one this project already
withdrew. `falsifiable_go_no_go`'s docstring carries the arithmetic: "exists
(category, ρ) with degradation < 5 %" has P(pass) = **100 %** under its own
null. The bound is what makes a pass mean something.

### A control required to fail

N = 8 in the same grid. If eight-way fragmentation also costs under 5 points,
the instrument is not separating the arms and **neither number is evidence**. A
control that passes is worse news than a declared cell that fails, and the CLI
prints it in those words.

### The threshold was declared against data that fails it

`COMPOSITION_THRESHOLD_POINTS = 0.05` is the existing 5 % go/no-go translated
onto a metric that is counted rather than judged. The pilot put the gap at 14 to
21 points — **three to four times the ceiling**. The threshold is written down
at the value the old criterion implies, knowing that, precisely so nobody can
later say it was set where the answer landed. A threshold chosen after seeing 14
points would have been 0.25.

### A cluster floor, in the code rather than in a caveat

The same 3 September run reported AUC 0.602 with a clustered 95 % interval of
[0.5014, 0.7243] — excluding chance by 0.0014, on **eight clusters**. The
caveat was in the prose; the number is what a reader remembers. Below 20
prompts `composition_criterion` returns `passed: None` and states both counts.
`comp-dev` has 12 prompts and will therefore print **no verdict at all**, by
design.

### ρ = 4.0, which is far above what SPEC asks for

The packing floor on this corpus at N = 8 runs **3.324 – 3.843**. There is no
lower ρ at which the control arm exists: below the floor every packet collapses
to its bare task, and `publishable()` drops those rows from every figure. Three
v3c tiers were run at ρ = 1.5 against floors of 1.51 – 2.37 and produced 0 of
15, 0 of 11 and 0 of 8 reachable cells.

Two consequences, both stated rather than smoothed over:

1. **This is itself a finding.** The floor rises with N — 2.13 at N = 3, 3.84 at
   N = 8 — so fragmenting harder *forces* more context. That is the opposite of
   the architecture's pitch, and it is the same wall as SPEC §11.5's ρ < 2.0
   target, which is unattainable on any corpus measured so far.
2. **It is conservative for this criterion.** More context can only help the
   fragmented arm, so a **FAIL at ρ = 4.0 is strong** and a **PASS is weak**.
   Given that twelve instrument defects found in this project all leaned toward
   its own hypothesis, being conservative in this direction is the point.

## 4. The corpus, and the two ways to break a frozen split silently

`scripts/make_composition.py`, seed 20260904, 36 prompts, **12 dev / 24 final**,
digest over id, split, tier and prompt text.

Three difficulty tiers, twelve prompts each, because a saturated baseline is a
problem even for a paired difference: it can never show fragmentation costing
nothing and it cannot be checked for arm-neutrality. The knobs are the checks
the pilot showed actually bind — three of its five failures were `*_once`:

| tier | required terms | of which exactly once | repeated-phrase window |
|---|---|---|---|
| easy | 2 | 1 | 8 |
| mid | 3 | 2 | 7 |
| hard | 4 | 3 | 5 |

`term_once` is hard for the **monolithic** arm too: a writer covering a term
across two paragraphs names it twice without noticing. That is deliberate.

**Two failure modes a digest does not catch**, both asserted instead:

* **An unbalanced split.** Assigning every hard prompt to dev leaves the digest
  intact and the two halves incomparable. The generator refuses to write, and
  `test_the_split_is_balanced_across_difficulty_tiers` checks the file that
  shipped: dev is 4/4/4, final is 8/8/8.
* **A final half too small to answer.** 24 against a floor of 20, asserted by
  `test_the_composition_corpus_can_support_a_verdict`, so the tier cannot burn a
  night to return `passed: None`.

The topics are deliberately dull and knowledge-free — how a bakery handles a
late flour delivery. A corpus that needed facts would confuse "the model does
not know this" with "assembly from fragments broke this", which is the confound
the answer-key corpora exist to avoid.

**Checked against the defect of 4 September:** 0 of 36 prompts match a
sequential cue, and 0 of 36 plan as a dependency chain. A new corpus is exactly
where that class of mistake returns, and on a composition prompt a misplanned
chain would be *silent* rather than visible in the grading —
`test_no_composition_prompt_is_planned_as_a_dependency_chain` is there for that
reason.

## 5. What is deliberately absent

One ρ, one k, two N. No editor, no typed carry, no judge, no agreement
calibration declared.

Each of those is a separate causal claim, and a corpus swept over many cells
answers the **maximum-statistic** question — does *some* cell clear the
threshold — which passes on random data. The agreement machinery still runs and
is still reported, because the data is free once the run happens, but **nothing
rides on it**: the confidence map has been measured six times, five null and the
sixth withdrawn on 4 September, and it is not re-declared here.

## 6. How to run it

```bash
bash scripts/run_ollama.sh comp-dev            # ~1 h, 12 prompts, NO verdict
bash scripts/run_ollama.sh comp-final <dir>    # ~2 h, 24 prompts, once
```

`comp-final` takes the dev run's **directory**, not a τ value: a bare number
cannot carry which corpus it was fitted on, and the tier checks the threshold,
the frozen digest and the split before it starts.

**Before proceeding from dev to final, read `baseline_at_ceiling`.** If it is 12
of 12 the corpus saturated like the last one, and the tiers need rebuilding
*before* the final half is touched. That is the one decision `comp-dev` exists
to support, and it is the last point at which anything may be changed.

## 7. What a result here would and would not establish

**Would:** a bound on what fragmenting a prose composition three ways costs, on
24 prompts, at a context budget generous enough that the fragmented arm is not
starved — measured mechanically, with a control that had to fail and a threshold
fixed in advance.

**Would not:** anything about the coherence tax, which reads +0.000 on these
texts and is measured on a different quantity; anything about agreement or the
confidence map; anything at a ρ the architecture would actually want to run at,
since N = 8 cannot be reached below 3.85 on this corpus at all.
