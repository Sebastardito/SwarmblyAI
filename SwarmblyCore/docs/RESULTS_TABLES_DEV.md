---
status: partially_withdrawn
stands: Sections 5 and 6
reason: >
  Sections 1 to 4 and 7 rest on a coherence metric that was not arm-neutral:
  one identical answer scores 0.9375 through one arm's convention and 0.5000
  through the other.
lang: en
---
# tables-dev — the hypothesis was refuted, and something else was found

> ## ⚠ WITHDRAWN, 27 August 2026 — §1 to §4 and §7 do not stand
>
> **The coherence metric was not arm-neutral.** Scoring one identical
> 16-sentence answer through the two arms' calling conventions returns **0.9375
> and 0.5000** — an apparent tax of **+46.7 % on text that never changed**. That
> demonstration needs no data from this run and is not in doubt.
>
> **The size of the effect on this run is not established, and an earlier draft
> of this notice claimed it was.** It quoted +17.2 % at N=2 and +14.6 % at N=8,
> from a re-scoring of the run's own answers. Those figures came from
> reconstructing the assembler's sentence offsets as an even split, and the
> offsets are not evenly spaced — fragments produce different numbers of
> sentences. `scripts/rescore.py` now checks that reconstruction against
> `results.csv` and **rejects it**, by up to 0.15. The traces of this run do not
> store the offsets, so it cannot be re-scored exactly. **The corrected number
> for this run can only come from running it again.**
>
> What is established: the bias exists, it inflates the fragmented arm, and it
> grows with N by construction.
>
> Three mechanisms, all functions of the partition rather than of the answer:
> the omission detector's expected set grew with N (0 for a baseline passing
> `plan=None`, 6 at N=2, **17 at N=8**); the same omissions were attributed
> round-robin across N fragment heads, so one document's omissions dirtied one
> sentence at monolithic and up to N at N tasks; and `missing_transition` and
> seam-anchored `dangling_reference` can only fire at seams, of which a
> monolithic answer has none. See `swarmbly_v0/metrics.py` and the invariant now
> asserted in `tests/test_instrument.py`.
>
> **What this means for §1:** the refutation of the coherence-tax hypothesis
> **is withdrawn**. `table_summary` at ρ=3.5, N=2 is undecided again, not
> refuted. A fourth mechanism — `register_tense_shift`, a homogeneity penalty
> that fired on 0.00 of the baseline's sentences and 0.44 of the fragmented
> arm's — would take it to +4.3 %, but that one was **not** treated as a bug:
> the tense directive was added to the corpus instead, so the question is
> settled by measurement rather than by argument.
>
> **What still stands:** §5 (the judge accepting 100 %), §6 (the confidence map
> working for aggregate claims only) and §8 (the successor hypothesis). None of
> them rests on the coherence metric — they rest on numeric fidelity and
> agreement.
>
> **The corpus also changed**, so `tables24.json` moves from digest `47ceb5f0…`
> to `0c5cb7e2…` and τ_sem = 0.805 no longer applies to anything.
>
> `tables-dev` must be re-run before any of §1–§4 is quoted. Roughly one hour.


**Run:** `results/tables-dev-20260826-115300`. Eight table prompts, the dev half
of `prompts/tables24.json` (sha256 `47ceb5f0…1ecaea`, verified before the run).
ρ = 3.5, N ∈ {2, 8}, k ∈ {1, 3}. No editor, no typed carry. Five model families
over Ollama, transport `openai-sdk`, **0 retries**, embeddings not degraded,
`harness_validation_only: false`. τ_sem fitted here at **0.805** and frozen for
the final half. 40 rows.

This is the first run in the project with one declared hypothesis, one named
cell, and a control chosen in advance to fail. All figures below come from
`scripts/reanalyse.py`, which recomputes them from the run's own CSVs through
the library functions — six defects were found in the analysis after the run
finished, and none of them required regenerating anything.

---

## 1. The declared hypothesis fails, and not narrowly

**Declared before the run:** `table_summary` at ρ=3.5, N=2 costs less than 5 %,
with the *upper bound* of the interval below 0.05.

| cell | point | 95 % CI (over prompts) | verdict |
|---|---|---|---|
| **N=2, k=1** | **+20.6 %** | [+10.6 %, +29.7 %] | fail |
| **N=2, k=3** | **+16.0 %** | [+2.2 %, +27.6 %] | fail |
| N=8, k=1 *(control)* | +25.3 % | [+19.1 %, +31.2 %] | fail |
| N=8, k=3 *(control)* | +63.7 % | [+56.5 %, +72.3 %] | fail |

n = 8 prompts in every cell. The interval at N=2, k=1 clears 5 % by more than
five points at its *lower* bound. This is a refutation, not an undecided result.

`table_summary` at the widest fragment was the only cell this project had ever
produced that came close to the threshold. It does not survive its own corpus.

**The control behaves.** N=8 is worse than N=2 at both k, and at k=3 the
intervals do not come close to touching. The instrument discriminates, so the
failure at N=2 is a measurement rather than an instrument that fails everything.

## 2. Against V6's +5.8 %, and why sixteen more prompts are the answer

V6 put this same cell — `table_summary`, ρ=3.5, N=2, k=1 — at **+5.8 %** with an
interval of [−2.2 %, +14.5 %]. This run puts it at **+20.6 %**, [+10.6 %,
+29.7 %].

The two intervals overlap only in [+10.6 %, +14.5 %]. They are not formally
incompatible, but they are strained, and the reason is visible in both: each
rests on **eight prompts**. Two samples of eight, from two different draws of the
same generator, disagree by fourteen points. That is the honest size of the
uncertainty, and no amount of care in the analysis substitutes for the sixteen
prompts in the final half.

What this does *not* license is picking the friendlier of the two. The dev half
is where thresholds and choices are made; the estimate belongs to the final half,
run once.

## 3. Consensus and fragmentation interact, sharply

| | k=1 | k=3 | difference |
|---|---|---|---|
| N=2 | +20.6 % | **+16.0 %** | consensus **helps** by 4.6 |
| N=8 | +25.3 % | **+63.7 %** | consensus **hurts** by 38.4 |

At a coarse partition three replicas improve the assembled text. At a fine one
they wreck it. A 56-token fragment gives three models too little to converge on;
the medoid picks one reading, and eight such choices assembled in sequence
produce something far worse than a single generation of the same fragments.

This is the second mechanism to show the same N-dependence. V6's typed carry ran
+7.6 and +8.3 at N=2 and 4, then −14.6 and −3.4 at N=6 and 8. Two independent
repairs that help at coarse partitions and hurt at fine ones is a pattern worth a
name and a test of its own.

It is also why the criterion now names k. Filtered on category, ρ and N alone,
the declared cell read **+18.3 %** — the midpoint of +20.6 % and +16.0 %, a
number describing neither arm. At N=8 the same omission would have averaged
+25.3 % with +63.7 %.

## 4. The tax is not tracking factual accuracy

At k=1, across the same cells where the coherence tax rises from +20.6 % to
+25.3 %:

| N | tokens/fragment | coherence tax | numeric fidelity | n graded |
|---|---|---|---|---|
| 2 | 222 | +20.6 % | **80.0 %** | 65 |
| 8 | 56 | +25.3 % | **81.0 %** | 189 |

Accuracy does not move. At k=3 it falls modestly — 85.3 % to 78.0 % — while the
tax rises by 48 points over the same interval.

**Fragmentation is costing coherence, not correctness.** The figures a fragment
states stay faithful to the table it can see; what degrades is the shape of the
assembled answer — paragraph structure, the mention-once constraints, repetition
across seams. That is a narrower and more useful claim than "fragmentation
degrades quality", and it points the editor at exactly the thing it can repair.

## 5. The judge is dead on this corpus

```
agreement vs judged quality: r = undefined over 723 units (acceptance rate 100.0%)
```

The peer-class judge accepted **everything**. This is the failure that made the
run of 14 August uninterpretable at 93.3 %; at 100 % the correlation cannot exist
whether or not the signal does. Every judge-based number on grounded prose should
be treated as absent, not as null. Ground-truth grading is unaffected and is what
Section 11.4 specifies anyway.

## 6. The confidence map works — for one class of claim

This is the finding, and both of the summary statistics I would have quoted hid
it.

Agreement is `consistent / k`, so at k=3 it takes **four values**. Accuracy at
each:

| agreement | aggregate claims | local claims | pooled |
|---|---|---|---|
| 0.00 | **0.000** (n=2) | 0.833 (n=6) | 0.625 |
| 0.33 | **0.250** (n=8) | 0.946 (n=74) | 0.878 |
| 0.67 | **0.625** (n=40) | 0.936 (n=47) | 0.793 |
| 1.00 | **0.750** (n=44) | 0.845 (n=97) | 0.816 |
| | **monotone, span 0.75** | not monotone, span 0.11 | not monotone |

For **aggregate claims** — statements requiring sight of rows a fragment may not
hold — agreement separates right from wrong across seventy-five accuracy points,
monotonically, with no exceptions. For **local claims** it separates nothing: the
span is eleven points and the top bin is *worse* than the two below it.

Pooled, the two produce a curve that is neither, and the pooled AUC reads
**0.481** — at chance — while the aggregate AUC reads **0.656**.

The flagging tells the same story:

| flag rate | pooled lift | aggregate | local |
|---|---|---|---|
| 10 % | **0.52** | **2.21** | 1.62 |
| 20 % | 0.96 | **2.21** | 0.61 |
| 30 % | 0.76 | **2.21** | 0.61 |

Reviewing the lowest-agreement aggregate claims catches errors at **2.2× the
base rate**. The pooled figure says the confidence map is worse than random.

**Why pooling inverts it.** The two classes sit at opposite corners: aggregate
claims carry *high* agreement (0.78) and *low* accuracy (0.64); local claims
carry *low* agreement (0.68) and *high* accuracy (0.90). Pooled, the
high-agreement items are disproportionately the wrong ones. Replicas agree
readily on a total or an average because those are formulaic to phrase, not
because the arithmetic is right.

This is the sixth pooling artefact in this project and the first that ran the
other way. The previous five made a null look like a result; this one made a
result look like a null.

**The lift is 2.21 at all three rates because the predictor supports one cut.**
Tie groups are now taken whole — flagging 20 % of a four-valued predictor asked
for 64 items out of a group of 82 the predictor cannot tell apart, and two
correct implementations disagreed by 0.6 in lift on tie order alone. What the map
actually offers here is a single decision: review the aggregate claims that fewer
than two of three replicas agreed on. That is 10 of 94 items, and 8 of those 10
are wrong.

## 7. A cell that did not run at the budget its label names

| ρ target | N | ρ achieved | deviation |
|---|---|---|---|
| 3.5 | 2 | 3.481 | −0.5 % |
| 3.5 | 8 | **3.907** | **+11.6 %** |

`rho_floor` at N=8 is 1.13, so the floor was not forcing this — the packer
overshot. The N=8 control therefore received *more* context than N=2 and still
did far worse, which is conservative for the conclusion drawn from it. The
direction was luck, not design. Nothing had ever checked this; `rho_fidelity`
now does, and a run with `within_tolerance: false` should name the drifting cell
rather than average it in.

## 8. The successor hypothesis, declared before the final half was run

Recorded here on **26 August 2026**, after the dev half and before any of the
sixteen final prompts was generated. Implemented as
`swarmbly_v0.experiment.flag_effect`; run by `bash scripts/run_ollama.sh
tables-final`.

> Among **aggregate claims**, flagging those on which fewer than two of three
> replicas agreed identifies errors at better than chance, **within a prompt**.

| | |
|---|---|
| **Estimator** | Mantel-Haenszel common odds ratio, **prompt as stratum** |
| **Interval** | cluster bootstrap over prompts |
| **Passes if** | the **lower bound** of the 95 % interval exceeds **2.0** |
| **Cut** | `agreement < 2/3`, frozen as `FLAG_CUT` |
| **Grid** | ρ=3.5, N=2, k=3 — one cell |
| **Failing control** | the same flag on **local** claims must not pass |

**Why an odds ratio and not the lift.** Dev's unstratified lift reads 2.21, and
it is not trustworthy. Three of eight prompts held no flagged item at all, and
the three with the most flags were the three with the most errors:

| prompt | flagged, wrong | unflagged, wrong |
|---|---|---|
| drayage | 4 / 4 | 4 / 7 |
| consolidation | 2 / 3 | 7 / 11 |
| groupage | 1 / 1 | 4 / 13 |
| intake | 0 / 1 | 3 / 7 |
| recall | 1 / 1 | 2 / 10 |
| manifest, reconciliation, staging | 0 / 0 | 6 / 36 |

A lift computed across prompts cannot separate *this claim is wrong* from *this
prompt is hard* — and only the first is worth anything, because the second is
already available from the error rate. Stratified, the effect survives:

| class | OR | 95 % CI | strata contributing | flagged |
|---|---|---|---|---|
| **aggregate** | **3.47** | **[0.80, 11.19]** | 5 / 8 | 10 / 94 |
| local *(control)* | 0.56 | [0.14, 1.09] | 8 / 8 | 80 / 224 |

Two things to read here. The aggregate interval **does not exclude 1.0**, so dev
does not establish the effect — it sizes it. And the control does more than fail:
at OR 0.56 the same flag is *worse than useless* on local claims. The two classes
are opposite in sign, not merely different in degree, which is what a
claim-specific mechanism predicts and a prompt-difficulty artefact does not.

**Why the bar is 2.0.** An odds ratio of 2 is roughly where flagging doubles a
reviewer's hit rate, which is the smallest effect that pays for the reviewer. It
is not a bar built to be cleared: dev's own lower bound is **0.80**.

**Why N=2 and k=3 only.** The hypothesis is about claims, not fragment size; k=1
has no agreement to measure; and N=8 ran at ρ 3.91 against a target of 3.5, so
that cell did not measure what its label says.

**The risk in doing this, stated plainly.** Replacing a refuted hypothesis with
one discovered in the same data is how a project talks itself out of a negative
result. Three things are load-bearing against that, and if any of them slips the
successor is worth nothing: the coherence-tax refutation **stands** and is not
withdrawn; this declaration is recorded before the final half exists; and the
final half is spent once, on this, with the estimator, the cut, the threshold and
the control all fixed above.

## What follows

1. **Do not run the final half yet.** The declared hypothesis is refuted on dev,
   and running sixteen more prompts to refute it again spends two hours on a
   question already answered. The final half is worth spending on a hypothesis
   that survived dev. This one did not.
2. **The aggregate-claim confidence map is that hypothesis**, declared in §8
   above with its estimator, cut, threshold and control fixed. It is the first
   positive calibration result in the project that is monotone, has a mechanism,
   and states a decision a user could act on.
3. **Fix ρ drift at N=8** before any run uses N=8 as a comparison point.
4. **The consensus × N interaction needs its own test.** +16 % at N=2 against
   +64 % at N=8 is the largest interaction in any run so far, and the typed carry
   showed the same shape.
5. **Retire the judge on grounded prose.** 100 % acceptance is not a measurement.
6. **`table_summary` at N=2 is no longer a live candidate.** It was the last one.
   No cell in this project currently has a credible path to the 5 % threshold,
   and that should be said plainly rather than left for the next corpus to
   rediscover.
