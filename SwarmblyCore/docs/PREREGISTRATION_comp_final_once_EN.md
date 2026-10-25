---
status: current
lang: en
---
# Preregistration — `comp-final-once`

> **CLOSED 5 September 2026. NOT MET by 8.61 points** on the upper bound:
> +7.64, CI [+1.42, +13.61], 24 clusters, control failing. None of the four
> invalidating conditions was met (56 sentences removed, control fails, 24
> prompts, zero rows excluded). Against the +22.40 of 4 September on the SAME
> split, that is nearly fifteen points recovered. See
> `docs/RESULTS_2026-09-05_final_dedup.md`.

**Written on 5 September 2026, after `comp-dev-once` and BEFORE
`comp-final-once` runs.** Nothing that follows may change once the run has
started.

## The hypothesis

> With `term_once` enforced **mechanically at the assembler**, composition at
> ρ = 4.0, N = 3, k = 1 costs **less than 5 points** of constraint satisfaction
> against its monolithic baseline — judged on the **upper bound** of a bootstrap
> clustered by prompt, with **N = 8 as a control that must fail**.

* **Estimator:** mean paired difference, monolithic minus fragmented, on
  `constraint_score_comparable`.
* **Interval:** cluster bootstrap over prompts, 24 clusters.
* **Passes if:** the upper bound of the 95% CI stays below 0.05.
* **Split:** final, 24 prompts, inheriting τ_sem from
  `comp-dev-once-20260905-120541`.

It is a **different hypothesis about a different system**. `comp-final` of 4
September judged the pipeline *without* this enforcement and answered NOT MET by
23.51 points. That answer stands and is not revisited here.

## The cost, said beforehand

**This is the SECOND use of the final split.**

The value of a final split comes from being evaluated once. Using it twice
weakens it, even if the hypothesis and the system are different: each use is
another chance for a favourable result to appear by luck. It is written down
here and the tier itself prints it, because a cost that is not named beforehand
turns into a footnote afterwards.

**A third use demands a new corpus.** The v2 generator is being built in
parallel for exactly that.

## What to expect, said beforehand and not after

In dev the point estimate moved from **+18.40 to +8.61**, but the upper bound
stayed at **+22.08**. A trade of +12 / −2 in a single class of constraint does
not have to be enough to bring an upper bound below 5 points.

**NOT MET is still the most likely outcome.** And it would still be the best
number this project has produced: `term_once` went from 6/24 to 18/24, above the
monolithic ceiling of 13/24, on real fragments.

## What would invalidate the run (not "refute": it would make it unreadable)

| # | condition | consequence |
|---|---|---|
| 1 | `term_once_sentences_removed` = 0 in every cell | The pass did not fire. The comparison is **void**, whatever the score is. The tier prints it in words. |
| 2 | The control at N=8 **passes** | The instrument does not separate the arms and **neither** of the two numbers is evidence. Worse news than a failure of the declared cell. |
| 3 | `n_prompts` < 20 | There is no verdict, whatever the point estimate is. |
| 4 | Any row excluded for floor, ceiling or rejected plan | The curves are read without them; if there are many, the cell was not measured. |

## What is NOT claimed

* **Nothing about quality.** Deleting a sentence to satisfy a counting rule
  makes the text shorter and may make it worse in ways that no constraint in
  this corpus checks. The score counts satisfied constraints, and that is all it
  is.
* **Nothing about the other ~19 points.** `comp-oracle` put **1.4 %** of the
  loss within reach of allocation. The residual is `no_repeated_ngram` (−7 of
  12, irreducible for parallel workers) and `must_mention` (−5 of 36, an effect
  of fragment size). This change touches neither of the two.
* **Nothing about N = 8.** The control exists in order to fail, and in dev the
  dedup barely fired there — 8 removals against 30 at N=3 — because at N=8 the
  problem is omission and you cannot deduplicate what was never written.
* **Nothing outside 3B models.** A model that followed "mention this term"
  reliably would move `must_mention` and leave `no_repeated_ngram` where it is.

## The gate that was added for this run

`read_dev_run` now demands that **the assembly pipeline match**: a `-final` with
`--enforce-term-once` only accepts a `-dev` that also had it, and the other way
round. Four things used to be checked — threshold, corpus, split, code — and
this is the fifth.

Without it, a threshold fitted by a pipeline that enforces `term_once`
mechanically could be silently paired with another that asks the model for it,
and the pairing is the whole value of having a split. Tested in both directions.

## The run — and why dev is run again first

**`comp-dev-once-20260905-120541` no longer serves as dev for this final one**,
and the two gates say so separately:

* `code_sha256` moved — `feff3e83…` in that run against `136fc431…` today.
  Adding `enforce_term_once` to the metadata **is** a code change. A threshold
  fitted before a code change is a threshold carried across a code change, which
  is the same leak as carrying it across a corpus change.
* That run predates the `enforce_term_once` field, so it does not say which
  pipeline its threshold was fitted with. The gate rejects it **for that reason
  of its own**, not by confusing it with a mismatch — reading "absent" as
  "false" would send the operator to fix what is not broken.

There is no override, and the remedy is the one the gate has always stated: run
dev again.

The dev numbers cited above (+8.61, upper bound +22.08, `term_once` 6/24 →
18/24) are still the evidence that motivates this hypothesis. What the re-run
produces is a threshold and a fingerprint valid for judging the final split; if
its point estimates come out very different from those of 12:05, **that is
information about the variance between runs** and it has to be said before
looking at the final one.

```bash
bash scripts/run_ollama.sh comp-dev-once                                  # ~1 h
bash scripts/run_ollama.sh comp-final-once results/comp-dev-once-<stamp>  # ~2 h
```
