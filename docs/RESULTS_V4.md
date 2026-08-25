# V4 — the effective size of a semantic fragment

**Run:** `results/v4-20260824-175122`. Five model families over Ollama, transport
`openai-sdk`, 0 transport retries, embeddings not degraded, `tau_sem` calibrated
to 0.575 from 108 labelled pairs. ρ ∈ {2.0, 3.0}, N ∈ {2, 4, 6, 8}, k ∈ {1, 3},
nine prompts across three task shapes, 72 fragmented cells per N.

Three predictions were written into `scripts/run_ollama.sh` before the run. Two
are confirmed, one is confirmed including its refusal, and one axis of the
measurement is not interpretable and is reported as such.

---

## 1. Cost falls with fragment size, monotonically

Re-examining the V0 run of 14 August finds one durable result in it: the
coherence tax rises as fragments get smaller. It had never been tested above 133
canonical tokens per fragment, because no corpus was long enough to produce a
wider one, and every run after it fixed N and swept `k` instead.

| N | tokens per fragment | coherence tax | cells |
|---|---|---|---|
| 2 | 224 | **+18.5 %** | 72 |
| 4 | 112 | +41.3 % | 72 |
| 6 | 75 | +47.1 % | 72 |
| 8 | 56 | +59.0 % | 72 |

Monotone, `comparable_across_n: true` — all three task shapes contribute to every
point, so no part of the trend is a change in what the point is made of. This is
the first measurement of the effect on a corpus built to express it.

**Immediate consequence for the planner.** `suggest_n_tasks` hardcodes one
micro-task per **60 canonical tokens**, a constant that has never been validated
against anything. On this corpus 60 tokens per fragment sits between the N=6 and
N=8 rows — a coherence tax around **+50 %**. The measured curve says fragments
should be roughly four times larger.

## 2. S\* is not one number — it is a property of the task shape

This was the sharper claim, and it is the one the run answers most clearly. Read
the widest fragment, where all three shapes have the most context they will ever
get in this sweep:

| N | tokens/fragment | dependency_chain | long_prose | table_summary |
|---|---|---|---|---|
| 2 | 224 | **+47.2 %** | **+5.1 %** | **+3.3 %** |
| 4 | 112 | +76.2 % | +19.4 % | +28.3 % |
| 6 | 75 | +74.2 % | +28.7 % | +38.2 % |
| 8 | 56 | +76.2 % | +48.8 % | +51.9 % |

At 224 tokens per fragment, prose and table summarisation are **nearly free to
fragment** — 5.1 % and 3.3 %, at or below the threshold the project has been
chasing since August. At the same fragment size the dependency chain is already
costing 47.2 %: ten to fourteen times more, on fragments of identical size.

A single token count cannot describe both. The effective fragment is the
**semantic unit** — a topic, a group of rows, a step — and the chain's units are
ordered, so a packet boundary does not merely divide the work, it cuts a value
the next step needs.

The chain's accuracy says the same thing on the other axis, and it is the one
clean monotone accuracy series in the run: **0.259 → 0.219 → 0.143 → 0.091** as
fragments shrink. Its tax then saturates near +76 % from N=4 onward, which is
what a broken chain looks like: once the carried value is lost, losing it again
costs nothing more.

**No S\* exists for the dependency chain in the range tested** — and the reason
turned out not to be fragment size at all.

Tracing a chain packet through the packer afterwards showed that at ρ = 2.0, the
value this run used, **not one packet carried a predecessor block**. The block
was optional context, third in priority behind the contract header and the length
note, funded from whatever slack remained after the task text — and the slack ran
out first. Every successor was handed "divide the net value from step 2" with
nothing about what step 2 produced. The packet was unanswerable by construction.

So the figures above are real but were misread when first written down. They are
not the price of fragmenting an ordered task; they are the price of fragmenting
it *while dropping the carry*. The saturation near +76 % from N=4 onward is the
signature: once the carried value is gone, losing it again costs nothing more.

Two changes follow, and they are separable. The carry is now **mandatory** for a
task whose text consumes a prior value — on the same footing as the task text,
rather than competing with the glossary for slack. And it is **typed**: every
labelled value the fragment produced, where `summarize_fragment` kept the lead
sentence and silently dropped the rest, so a fragment covering steps 3 to 5
handed its successor step 3 and a list of entities.

Completeness is bought rather than found: 10 tokens against 4 on a terse
fragment. A first draft of the mechanism predicted ρ would *fall*, on the
reasoning that a number is cheaper than prose. Measurement said otherwise — the
prose summary is cheap precisely because it is incomplete — and the prediction
was corrected rather than the measurement.

The re-run with both changes is what settles whether an ordered chain is
expensive at all.

## 3. The editor repairs form and does not touch fact — exactly as predicted

144 paired cells, each edited cell with an unedited twin at the same prompt, N
and k.

| measure | value |
|---|---|
| apply rate | 52.1 % (75 of 144) |
| mean constraint gain | **+15.4 %** of mechanical checks recovered |
| mean coherence-tax delta | **−2.6 %** |
| item accuracy, unedited | 0.3804 |
| item accuracy, edited | **0.3804** |
| **accuracy delta** | **0.000** |
| tokens per edit | 671 |

The prediction was that constraint scores would rise and item accuracy would
**not**, because the editor holds the assembled answer and the contract and has
no access to the source material. Accuracy moved by exactly zero across 144
pairs. Had it risen, the arm would have been contaminated — the editor answering
from its own knowledge rather than editing — and the constraint gain would have
been worthless.

Both refusals fired on real data: **19 revisions rejected for scoring worse**,
and **1 rejected for introducing an unsupported figure**. The first is the gate
the bridge never had; without it the editor would have traded unmeasured
dimensions for measured ones, which is precisely how bridge synthesis broke a
`paragraph_count` constraint on 25 August.

ρ is unchanged by construction — the editor never sees the problem prompt — so
the 671 tokens are reported as their own budget line rather than folded into it.

## 4. Aggregation is a distinct failure class

The wrong answers on table summarisation are not grading artifacts. They are
inventions:

> "The heaviest consignment is the one from Mombasa, weighing 935 kg, and the
> total weight of all consignments is 1650 kg."

A total of 1650 kg over twenty rows one of which weighs 935 kg is not a
misreading, it is a fabrication. Others are worse — "a 500-ton container, while
the lightest item is a 10-ton package" — in units the table does not use.

Splitting claims by whether they assert an aggregate (a total, an average, the
heaviest or lightest — anything requiring sight of rows the fragment does not
hold):

| claim type | wrong | rate |
|---|---|---|
| asserts an aggregate | 74 / 155 | **47.7 %** |
| asserts nothing aggregate | 32 / 101 | 31.7 % |

Fisher exact **p = 0.014**. A worker asked for the total while holding a third of
the table does not decline; it invents. This is a failure the architecture
predicts and the confidence map ought to be able to catch, and it is a better
target for the next calibration attempt than anything tried so far — the
prediction is available, mechanical, and the two classes differ.

## 5. The go/no-go now fails, which is the point

The success criterion has been restated. The earlier form -- "there exists a
(category, ρ) cell under 5 %" -- is a maximum statistic over many noisy cells
with no multiple-comparison control, and shuffling observations between cells
under the null that none differ satisfies it essentially always. A criterion met
with near-certainty by construction reports nothing about the world.

The replacement names its cell **in advance** and requires the **upper bound** of
a bootstrap interval to clear the threshold.

At the widest fragment, N=2:

| cell | ρ | point estimate | 95 % CI | passes |
|---|---|---|---|---|
| table_summary | 2.0 | +3.1 % | [−3.5 %, +10.3 %] | **no** |
| table_summary | 3.0 | +3.4 % | [−3.1 %, +10.6 %] | **no** |
| long_prose | 3.0 | +4.2 % | [+0.6 %, +7.8 %] | **no** |
| long_prose | 2.0 | +6.0 % | [+1.1 %, +12.2 %] | no |
| dependency_chain | 2.0 | +62.5 % | [+43.8 %, +81.3 %] | no |

`table_summary` has a point estimate **under 5 %** at both ρ values. A criterion
reading point estimates alone would declare a pass on that — and this is exactly
the situation the restatement exists to catch, because with n = 12 the interval
runs from −3.5 % to +10.3 % and settles nothing.

The honest statement is: **two of three task shapes are plausibly under the
threshold at 224 tokens per fragment, and the run does not have the power to
establish it.** More observations in those two cells would settle it; nothing
else needs to change.

## What is *not* interpretable in this run

**Accuracy against fragment size, pooled.** The balanced series is 0.480, 0.484,
0.249, 0.388 — not monotone. The denominators behind it swing from 38 to 90
graded items out of 336 to 466 units, because how many sentences happen to
contain a figure varies with fragment size. A ratio whose denominator moves for
reasons unrelated to the hypothesis is not a measurement of the hypothesis. The
per-shape accuracy for `dependency_chain` is monotone and is reported above; the
pooled series is not, and is not used.

**The per-N breakdown of the fabrication rate.** The gap between aggregate and
non-aggregate claims is solid over the whole run (p = 0.014). Split by N it rests
on as few as 6 aggregate claims in a cell, and is not reported.

## What this changes

1. **The planner's 60-token constant is wrong by roughly 4×** on this evidence,
   and should be replaced by a measured value — per task shape, not globally.
2. **Prose and table workloads may already be under the threshold** at large
   fragments. That cell deserves the observations needed to settle it.
3. **The dependency chain needs a mechanism, not a parameter.** No fragment size
   in the tested range makes it affordable.
4. **The editor earns its place**: 15 % of mechanical checks recovered, a small
   reduction in coherence tax, zero effect on correctness, for 671 tokens
   outside the ρ budget.
5. **Aggregation is the next calibration target**, and unlike the six saturated
   attempts before it, the two classes it separates actually differ.
