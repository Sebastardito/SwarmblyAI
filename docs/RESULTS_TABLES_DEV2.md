---
status: current
lang: en
---
# tables-dev, second run — the cost hypothesis is alive, the successor is dead

**Run:** `results/tables-dev-20260827-095758`. The dev half of
`prompts/tables24.json`, frozen digest `0c5cb7e2…`, verified before the run.
ρ = 3.5, N ∈ {2, 8}, k ∈ {1, 3}. No editor, no typed carry. Five model families
over Ollama, transport `openai-sdk`, **0 retries**, embeddings not degraded,
`harness_validation_only: false`. τ_sem fitted here at **0.680**. 40 rows.

The first run of this cell after two corrections: an arm-neutral coherence
metric, and a tense-and-register directive in the contract. Both landed at once
and they cannot be separated from these two runs — that is stated here rather
than glossed.

---

## 1. The declared cell now reads +1.6 %, and it is undecided

**Declared, unchanged since the original pre-registration:** `table_summary` at
ρ=3.5, N=2 costs less than 5 %, with the *upper bound* of a prompt-clustered
interval below 0.05.

| cell | point | 95 % CI (over prompts) | verdict |
|---|---|---|---|
| **N=2, k=1** | **+1.57 %** | **[−4.69 %, +7.26 %]** | undecided |
| N=2, k=3 | +20.48 % | [+11.64 %, +30.57 %] | fail |
| N=8, k=1 *(control)* | +14.00 % | [+7.95 %, +19.23 %] | fail |
| N=8, k=3 *(control)* | +35.02 % | [+26.22 %, +44.59 %] | fail |

The same cell, on the same corpus family, read **+22.9 %** before the metric was
corrected. It now reads **+1.6 %**, and **three of eight prompts are negative** —
the fragmented answer scored *better* than its monolithic baseline:

| prompt | tax | on the full score |
|---|---|---|
| manifest | 0.0 % | −18.8 % |
| intake | +8.7 % | +4.4 % |
| consolidation | +12.5 % | +18.8 % |
| reconciliation | +4.3 % | +8.8 % |
| **drayage** | **−15.7 %** | −12.1 % |
| **groupage** | **−9.1 %** | +1.8 % |
| recall | +8.6 % | −1.6 % |
| staging | +3.2 % | −4.8 % |

On the *full* score — seam classes included — the cell reads **−0.44 %**.
Fragmenting a table summary into two parts, at this context budget, costs
approximately nothing.

**It still fails the criterion**, because the criterion is written on the upper
bound and the upper bound is +7.26 %. On **eight prompts**. That is the correct
verdict and the interesting one: for the first time the cell is undecided in the
*favourable* direction, and sixteen more prompts would roughly halve the
interval.

**Two changes landed together and this run cannot separate them.** The metric
correction is demonstrated independently — one identical answer scored 0.9375
and 0.5000 through the two arms' conventions — so it is not in doubt that it
mattered. How much of the remaining movement is the tense directive is not
recoverable from two runs. What is recoverable: the *current* instrument, on the
*current* corpus, reads +1.6 %.

## 2. Consensus is now unambiguously expensive

| | k=1 | k=3 |
|---|---|---|
| N=2 | **+1.6 %** | +20.5 % |
| N=8 | +14.0 % | +35.0 % |

In the previous run k=3 *helped* at N=2 (+16.0 % against +20.6 %). It now hurts
by nineteen points. The direction flipped, which on eight prompts means the
earlier reading was noise, not that consensus changed character.

What survives across both runs is the interaction: **k=3 costs more the finer
the partition**. Three replicas of a 56-token fragment have too little to
converge on, the medoid picks one reading, and eight such choices assembled in
sequence produce something far worse than a single generation of the same
fragments.

## 3. The seam cost, now in its own column

| cell | tax (comparable) | tax (full) | seam errors/sentence | vs baseline |
|---|---|---|---|---|
| N=2 k=1 | +1.6 % | −0.4 % | 0.056 | **−0.024** |
| N=2 k=3 | +20.5 % | +21.6 % | 0.088 | +0.007 |
| N=8 k=1 | +14.0 % | +17.6 % | 0.109 | +0.029 |
| N=8 k=3 | +35.0 % | +52.7 % | 0.285 | +0.204 |

The monolithic baseline carries a seam rate of **0.081** despite having no
seams — `dangling_reference` also fires on a sentence with no antecedent overlap,
which any text can have. The class name is imprecise; the comparison is not,
because the class is excluded from both arms or included in both.

At N=2, k=1 the fragmented answer has **fewer** of these than the baseline. At
N=8, k=3 it has three and a half times as many. That is the specific damage
assembly does, and it is now visible rather than folded into a coherence ratio.

## 4. The successor hypothesis failed its first independent test

Declared on 26 August, before this run existed: *among aggregate claims, flagging
those on which fewer than two of three replicas agreed identifies errors at
better than chance, within a prompt.* Estimator: Mantel-Haenszel odds ratio,
prompt as stratum. Passes if the lower bound exceeds 2.0.

| class | previous run | this run | 95 % CI | strata | flagged |
|---|---|---|---|---|---|
| **aggregate** *(under test)* | OR 3.47 | **OR 0.26** | [0.00, 3.25] | 5 / 8 | 8 / 83 |
| local *(control)* | OR 0.56 | OR 0.89 | [0.09, 4.79] | 8 / 8 | 63 / 215 |

**It does not replicate. It reverses.** And the accuracy table that was its whole
justification no longer has the shape it was named for:

| agreement | previous run | this run |
|---|---|---|
| 0.00 | 0.000 (n=2) | *no items* |
| 0.33 | 0.250 (n=8) | **0.875** (n=8) |
| 0.67 | 0.625 (n=40) | 0.692 (n=26) |
| 1.00 | 0.750 (n=44) | 0.796 (n=49) |
| | **monotone, span 0.75** | not monotone, span 0.18 |

The lowest agreement bin now holds the *most accurate* claims. Aggregate accuracy
rose from 63.8 % to 77.1 %, and the flagged group shrank to eight items.

**This is the split doing exactly what it is for.** A hypothesis with a clean
mechanism, a monotone curve across seventy-five accuracy points, and a control
that failed in the opposite direction — declared with its estimator, cut and
threshold fixed — died on the development half at a cost of one hour, without
ever touching the sixteen prompts reserved to decide it. Two runs of eight
prompts gave opposite signs. **At n = 8 this measurement is noise, and it was
noise the first time too.**

The honest conclusion is the one V5-against-V6 already suggested and I did not
act on hard enough: the confidence map has now failed to replicate three times
(V5→V6, dev-1→dev-2), and no version of it should be declared again until
something explains why it moves.

## 5. What did not change

- **The judge accepts 100 %** of 761 units. Third run running. On grounded prose
  it is not an instrument.
- **ρ at N=8 is 3.90 against a target of 3.5** — 11.5 % over, unchanged from the
  previous run. The N=8 control did not run at the budget its label names. It is
  conservative for the conclusion drawn from it (more context, worse result), but
  the packer needs fixing before N=8 is used as a comparison point.
- N=2 sits at 3.38, −3.4 %, inside tolerance.

## What follows

1. **Run the final half on the cost hypothesis.** It is the original
   pre-registration — the cell, the threshold and the estimator have never moved;
   what moved was a defective instrument, now fixed. The point estimate is
   +1.6 %, the interval is [−4.69 %, +7.26 %] on eight prompts, and sixteen more
   plausibly decide it. This is the first time the final half has had a question
   worth spending on.
2. **Do not declare the confidence map again.** Three non-replications. It needs
   an explanation before it needs another test.
3. **Fix ρ drift at N=8** before any run uses N=8 as a control.
4. **Separate the metric fix from the tense directive** if the distinction ever
   matters for a claim. It does not for the decision above.
5. **Retire the judge on grounded prose.** 100 % acceptance, three runs running.
