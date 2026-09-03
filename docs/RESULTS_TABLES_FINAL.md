# tables-final — the pre-registered criterion is NOT MET

> **The run below (27 August) was made with a DEFECTIVE instrument and is kept
> as history. The measurement that stands is [`RESULTS_TABLES_FINAL_CORRECTED.md`]
> (RESULTS_TABLES_FINAL_CORRECTED.md), re-run on 3 September once twelve
> instrument defects were fixed. Its verdict is the same — NOT MET — but every
> figure moved, and the distribution behind the figure moved a great deal more.**
>
> Do not quote a number from this file. The defects, and why each was one-sided
> in the direction of the project's own hypothesis, are in
> [`REVISION_2026-08-12.md`](REVISION_2026-08-12.md).

## The withdrawn run of 27 August, unaltered below

**Run:** `results/tables-final-20260827-102014`. The final half of
`prompts/tables24.json`, digest `0c5cb7e2…`, verified before the run. Sixteen
prompts, ρ = 3.5, N ∈ {2, 8}, k ∈ {1, 3}. τ_sem **inherited** from
`tables-dev-20260827-095758` at 0.680, not refitted. Transport `openai-sdk`,
**0 retries**, embeddings not degraded, `harness_validation_only: false`.
80 rows.

**This half is spent. There is no second one.**

---

## The verdict

**Declared before the run, unchanged since the original pre-registration:**
`table_summary` at ρ=3.5, N=2, k=1 costs less than 5 %, with the **upper bound**
of a prompt-clustered 95 % interval below 0.05.

| cell | point | 95 % CI (16 prompts) | verdict |
|---|---|---|---|
| **N=2, k=1** — *under test* | **+3.26 %** | **[−0.02 %, +6.93 %]** | **FAIL** |
| N=8, k=1 — *control, must fail* | +17.64 % | [+13.33 %, +21.55 %] | fail ✓ |
| N=2, k=3 | +25.80 % | [+17.54 %, +34.43 %] | fail |
| N=8, k=3 | +32.25 % | [+27.90 %, +36.70 %] | fail |

**The criterion is not met.** The upper bound is 6.93 % against a threshold of
5 % — short by 1.93 points, on the metric, cell, threshold and estimator declared
in advance.

**The control behaved.** N=8 costs +17.6 % with an interval that does not come
near N=2's. The instrument discriminates, so the failure at N=2 is a measurement
and not an instrument that fails everything.

---

## What was actually measured

The verdict above is the answer to the question that was asked. It is not the
same as "fragmentation is expensive", and the distinction matters.

| statistic | value |
|---|---|
| point estimate | **+3.26 %** — below the threshold |
| **median prompt** | **+1.16 %** |
| lower bound of the interval | **−0.02 %** — at zero |
| prompts costing ≤ 0 | **8 of 16** |
| prompts costing < 5 % | 9 of 16 |
| tax on the **full** score, seams included | **−1.19 %** |
| seam errors per sentence | fragmented **0.062**, baseline **0.081** |

Splitting a table summary in two, at this context budget, costs **somewhere
between nothing and seven percent**, most likely around one to three. Half the
prompts show no cost at all, and on the score that includes seam defects the
fragmented answer is *better* than the unfragmented baseline — with **fewer**
seam-local errors per sentence than a text that has no seams.

The pre-registered criterion demanded certainty that the cost is below five
percent. Sixteen prompts do not deliver that certainty. Both things are true and
both belong in the record.

### The per-prompt distribution

| prompt | tax | | prompt | tax |
|---|---|---|---|---|
| returns | −7.7 % | | closeout | +5.6 % |
| layover | −5.8 % | | clearance | +6.7 % |
| backlog | −2.5 % | | demurrage | +7.1 % |
| salvage | −2.4 % | | holdover | +8.3 % |
| transit | 0.0 % | | outturn | +8.3 % |
| quarantine | 0.0 % | | transhipment | +9.1 % |
| overspill | 0.0 % | | **bonded** | **+23.1 %** |
| prealert | 0.0 % | | dispatch | +2.3 % |

`bonded` is an outlier: it alone lifts the mean by 1.3 points, and without it the
mean is **+1.94 %** with an upper bound that would clear the threshold.

**That figure is recorded and it is not used.** Removing an outlier after a
criterion has failed, to make it pass, is the textbook form of exactly what the
split, the frozen digest and the declared estimator exist to prevent. The
criterion was named in advance, applied as written, and it failed. `bonded`'s
baseline scored a perfect 1.000, which makes any deficit a maximally sensitive
ratio — an argument for revisiting the estimator *in a future study*, declared
before that study runs, and for nothing else here.

---

## The confidence map: dead, now on sixteen prompts

Reported, not declared — it was demoted after failing its first independent test.

| class | dev-1 | dev-2 | **final (n=16)** |
|---|---|---|---|
| aggregate *(was under test)* | OR 3.47 | OR 0.26 | **OR 1.24**, CI [0.25, 3.75] |
| local *(control)* | OR 0.56 | OR 0.89 | OR 0.50, CI [0.13, 1.49] |

Three values spanning an order of magnitude across three runs, and an interval
straddling 1.0 on the largest sample. Accuracy by agreement value for aggregate
claims now runs 1.000 (n=2) / 0.556 / 0.661 / 0.637 — **higher agreement does not
mean higher accuracy**.

Declaring this on 26 August and having it die on the dev half is the single
clearest thing the split has bought: it cost one hour of GPU and never touched
these sixteen prompts.

---

## Instrument notes

- **ρ at N=8 is 3.911 against a target of 3.5** — 11.7 % over, third run running.
  The packer overshoots; `rho_floor` is 1.13, so nothing is forcing it. The N=8
  control therefore received *more* context than N=2 and still cost five times as
  much, which is conservative for the conclusion drawn from it. N=2, the declared
  cell, sits at 3.392 — inside tolerance.
- **`scripts/rescore.py` round-trips this run at 0.0000.** The offsets stored
  from 27 August make a finished run exactly re-scorable; a future metric
  correction can be applied to these generations without re-running them.
- **The judge accepted 100 %** of 1 502 units. Fourth run running. It is not an
  instrument on grounded prose and should be retired there.
- **k=3 costs +25.8 % at N=2 and +32.3 % at N=8.** Consensus is expensive at
  every partition measured, and more so the finer the split.

---

## What this settles, and what it does not

**Settled.** H1 as pre-registered — *there exists a configuration whose coherence
cost is below 5 %* — is **not demonstrated**. The best cell this project ever
produced, measured with a corrected instrument on a corpus split before the
thresholds were fixed, lands at +3.3 % with an interval reaching 6.9 %. The
criterion was written to be failable and it failed.

**Not settled, and not claimable in either direction.** Whether the true cost is
below 5 %. The point estimate says probably; the interval says not
demonstrably. Half the prompts cost nothing.

**What would settle it** is a new study: a new corpus, more prompts, an
estimator declared in advance that is robust to a baseline at 1.000, and the
whole thing pre-registered before it runs. Not eight more prompts appended to
this one — that is the same study, and this study is finished.

**What changed about the project's foundations** is in
`docs/RESULTS_TABLES_DEV.md` §8 and stands: the cost is far smaller than four
earlier runs reported, because those runs measured a defective instrument; what
degrades under fragmentation is *form*, not *fact*; and the fragmented arm's
seam defects are fewer than the baseline's at N=2. A protocol that splits a
document in two and loses one to three percent of a form score, with numeric
fidelity unchanged, is not the protocol those earlier documents described.
