# V3c against ground truth — the confidence map fails, and this run says why

> # ⚠ WITHDRAWN — 4 September 2026
>
> **Every figure in this document was produced under an arm asymmetry in the
> STIMULUS, not in the metric. Do not quote a number from it, in either
> direction.**
>
> All 15 prompts in `ground_truth.json` end with: *"Begin the line with the item
> number in square brackets, exactly as given, **then** a single space, **then**
> the value."* The router's `_SEQUENTIAL_CUES` matches `\bthen\b`. One cue
> clears the gate, so **every prompt was planned as a four-deep chain** — on a
> corpus whose every prompt says, in the same sentence, *"Items are independent:
> the answer to one must not depend on the answer to any other."*
>
> The consequence: **42 of 60 fragment packets carried another packet's ANSWER
> LINES** — `- t0: [01] 576` — directly above a task block reading *"Answer only
> the items listed here."* The monolithic prompt carried none.
>
> **What this invalidates, and it is more than the arm comparisons.**
>
> - Every fragmented-vs-monolithic figure here. The two arms were dispatched
>   different questions.
> - **The calibration too, and in a direction that cuts against this document's
>   own conclusion.** At k > 1 every replica of one task receives the *same*
>   packet, so a shared predecessor block gives them something to converge on.
>   Mean agreement 0.966 may be inflated by the defect. If it is, the verdict
>   "the predictor has no variance, AUC 0.525, the map is retired" rests on
>   variance that was artificially suppressed — so **this document's central
>   finding is not safe in either direction.**
> - §2's mechanism claim — five families agreeing almost always, and wrong 29 %
>   of the time where they agree — is the part most exposed to this, because it is
>   a claim *about the agreement distribution*.
>
> **What survives.** Nothing about agreement. The item-attrition arithmetic in §4
> is explained by this defect rather than invalidated by it: the "missing" items
> were restatements of the predecessor block, correctly discarded by
> `task_item_scope`, which is why they recovered with k.
>
> Fixed in `planner.ordering_text()` and `packing.answers_by_item_label()`; after
> the fix 0 of 15 prompts plan as chains and the genuine `chain_*` prompts in
> `complex.json` still do. **This tier must be re-run before any figure from it is
> used.** See `docs/INCIDENT_2026-09-04_chain_misplan.md`.


**Run:** `results/v3c-gt-20260903-201624`. 15 prompts × 150 items,
`prompts/ground_truth.json`, ρ = 2.5, N = 4, k ∈ {1, 3, 5}, five distinct model
families. Graded mechanically against an answer key by `swarmbly_v0.grading` —
**no model in the verdict**. 60 rows.

> **Provenance.** `harness_validation_only: false`, `embeddings_degraded: false`,
> τ_sem 0.765 fitted on 180 pairs, seed 0, code fingerprint `4abed34a…`.
> **`rows_excluded_below_floor: 0`** and ρ achieved 2.49–2.51 against a target of
> 2.50. `n_families_mean` 3.0 at k=3 and 5.0 at k=5 — the k=5 arm really did run
> five distinct lineages, which the contaminated run of 24 August did not.

**This is the first time this experiment has been run above its own packing
floor.** Every previous v3c tier swept ρ = 1.5 against floors of 1.51–2.37, so
every fragmented cell collapsed to a bare task: those runs measured agreement
between replicas answering *context-free* micro-tasks. Their odds ratios of 3.47,
0.26 and 1.24 describe a configuration nobody chose.

---

## 1. The verdict

| statistic | value | reading |
|---|---|---|
| **AUC, pooled** | **0.525** | 0.500 is chance. Was 0.507 before the `returns_input_value` fix of 4 September; see §4. |
| **Flagging lift** at 10 / 20 / 30 % flag rate | **1.12 / 1.21 / 0.99** | 1.0 is random |
| Pearson *r* | +0.117 | see §3 — it rests on three items |
| items in the calibration | 183 (127 right, 56 wrong) | |

The tier's own instructions, written before the run: *"lift near 1.0 means the
flag is no better than random, and that result retires the confidence map."*

Flagging the lowest-agreement 30 % of items catches 29.6 % of the errors. That is
what flagging 30 % of items at random does.

**Per category, the AUCs scatter on both sides of chance and cancel:**

| category | n | accuracy | AUC |
|---|---|---|---|
| unit_conversion | 51 | 0.941 | 0.812 |
| arithmetic | 22 | 0.455 | 0.583 |
| date_arithmetic | 51 | 0.353 | 0.530 |
| **threshold_decision** | 40 | 0.850 | **0.382** |
| field_extraction | 17 | 1.000 | — (no errors) |

`threshold_decision` is **below** chance: there, higher agreement predicts a
*wrong* answer. Categories landing on both sides of 0.5 and pooling to chance is
the signature of no signal, not of a weak one. (This table is computed before
the grading fix of §4, which moves `arithmetic` accuracy to 0.478 and the pooled
AUC to 0.525; the pattern is unchanged.)

**And adding families does not help.** k=3 gives AUC 0.483, k=5 gives 0.527. Two
more independent lineages bought nothing.

## 2. Why — and this is the part the earlier runs could not reach

The earlier verdict was "agreement does not predict correctness". This run shows
the mechanism, and it is worse than a weak relationship.

**Mean agreement is 0.966. One hundred and seventy-three of 183 items sit in the
top bin, and the grading fix of §4 leaves that bin untouched.**

| agreement bin | items | accuracy |
|---|---|---|
| 0.0 – 0.2 | 0 | — |
| 0.2 – 0.4 | 2 | 0.000 |
| 0.4 – 0.6 | 1 | 0.000 |
| 0.6 – 0.8 | 5 | 0.800 |
| **0.8 – 1.0** | **173** | **0.711** |

Five model families — five organisations, five pretraining lineages, chosen for
diversity precisely so they could disagree — **agree with each other almost
always. And where they agree nearly perfectly, they are wrong 29 % of the time.**

The confidence map does not fail because the correlation is weak. It fails
because **the predictor has almost no variance to offer**, and what variance it
has does not track error. A signal cannot be extracted from a constant.

This is the failure mode the project's own design notes named and then assumed
away: *models sharing training data share errors, so they agree confidently on
the same mistake*. It has now been measured directly. Independent families are
not independent estimators on this workload.

**That is a finding about model ecology, not about Swarmbly**, and it is the more
useful half of this run. It bounds any architecture — not only this one — that
proposes to derive reliability from cross-model agreement at this scale.

## 3. Why the Pearson *r* is not evidence

`pearson_r = +0.117` is positive and points the "right" way. It should not be
quoted. It rests on the 0.2–0.6 range, which holds **three items** in total, all
of them wrong. Remove those three and the predictor is a constant.

Read AUC before *r* — which is what the tier's instructions say, and why they say
it. AUC 0.525 is the honest summary.

## 4. Correction — and the compliance finding that survives it

> **The first version of this section, published 3 September, was wrong.** It
> read `units_with_no_label: 323 of 719` as a 45 % attrition rate and concluded
> that "three quarters of the dispatched work does not reach the calibration".
> That is a misreading of the statistic, and it is exactly the class of error
> this project keeps correcting: a count read as though it measured something it
> does not.

A **unit is a line**, not an answer opportunity. `units_with_no_label` counts
every line that is not an answer — a preamble, a sign-off, a blank. It discards
nothing. Running the real pipeline over the real corpus with a model that answers
**every item, in the asked format, correctly**:

| arm | units | unlabelled | items seen | correct |
|---|---|---|---|---|
| monolithic | 180 | 30 (16.7 %) | 150 | 150 |
| fragmented N=2 | 210 | 60 (28.6 %) | 150 | 150 |
| **fragmented N=4** | 270 | **120 (44.4 %)** | 150 | 150 |
| fragmented N=8 | 390 | 240 (61.5 %) | 150 | 150 |

44.4 % at N = 4 against the run's 45 %, with **zero items lost and accuracy
1.000**. The ratio is a pure function of N — a fixed per-reply overhead paid N
times against N-way-smaller answer lists — so it is not an error rate and it must
never be compared between arms.

### The real attrition, which is smaller and more interesting

`items_seen` is 387 against a ceiling of 600 (150 key items × 4 conditions).
Broken out, it is not a uniform 35 % loss — it is almost entirely one arm at low
k, and it *improves* as replicas are added:

| condition | items seen / 150 |
|---|---|
| monolithic | **150 (100 %)** |
| fragmented, k = 1 | **24 (16 %)** |
| fragmented, k = 3 | 82 (55 %) |
| fragmented, k = 5 | 131 (87 %) |

The monolithic arm is perfectly compliant. A single fragmented worker produces a
parsable answer for **one item in six**. Adding replicas recovers most of it,
because an item counts as seen if *any* replica labelled it.

This is a large arm asymmetry in a denominator, which is the shape of defect this
project has withdrawn results for twice. **It is stated here and not
interpreted.** Two readings are live and this run cannot separate them: either
fragmented workers genuinely fail to emit the format, or `task_item_scope` is
removing in-scope items it should keep. It needs its own diagnosis before any
figure that compares arms on this corpus is quoted.

### The grading defect this investigation found

`returns_input_value` reduced an answer to `_as_number` — the **last** number —
and called it a restatement whenever that number appeared in the item's source
line. `21 - 80`, against a source reading *"21 crates, 16 units per crate, 80
removed"* and a key of 256, was filed as a restatement. It is an attempt: it
states two numbers and a dropped operator. A restatement hands one value back and
stops, so the guard now requires the answer to state exactly one number.

Recomputed from this run's stored answers, the fix returns **12 items** to the
denominator, all in `arithmetic`, all wrong by construction:

| | before | after |
|---|---|---|
| items graded | 308 | 320 |
| pooled accuracy | 0.7175 | **0.6906** |
| `arithmetic` accuracy | 0.647 | **0.478** |
| calibration items | 181 | 183 |
| calibration accuracy | 0.7017 | 0.6940 |
| **pooled AUC** | 0.5073 | **0.5249** |

The direction is the one that matters: **the reported accuracy was too high.**
The top-agreement bin is unchanged at 173 items and 0.711 accuracy, so §2 stands
exactly as written.

## 5. What this settles

The confidence map has now been measured **five times**: once against a saturated
judge (r = −0.030, uninterpretable), three times against an answer key on
below-floor runs (common odds ratios 3.47, 0.26, 1.24 — above, below and astride
1), and once here, above the floor, with five genuine families and a mechanical
verdict.

**AUC 0.525. Flagging lift 1.0. It is retired.**

The mechanism stays in the protocol: replicas are still dispatched, agreement is
still computed and reported, and a low-agreement region is still a place a reader
might look. What is withdrawn is the *claim* — that the agreement score carries
information about whether the answer is right. It does not, and now there is an
explanation rather than only a null.

**What must not be said:** that this is a weak or preliminary result. It is the
cleanest run this question has had, and it is unambiguous. The honest cost of the
consensus mechanism should be stated alongside it: k = 5 costs a large share of
output quality against a signal that does not exist.
