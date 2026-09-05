# v0, v3c-ff, v3c-gt — 4–5 September 2026

Three tiers, roughly eleven hours, all completed. Provenance is clean on all
three: `harness_validation_only: false`, `embeddings_degraded: false`, code
fingerprint `81e0215b…` on every one, and **zero rows excluded for any reason**
— no cell below floor, above ceiling, forced above target, or refused. The grid
work of 4 September holds.

Read in the order the runbook prescribes; the order is why four documents were
withdrawn.

| run | directory |
|---|---|
| v0 | `results/v0-20260904-231812/{N2,N4,N8}` |
| v3c-ff | `results/v3c-ff-20260904-233926` |
| v3c-gt | `results/v3c-gt-20260904-234814` |

---

## 1. v0 produced no verdict, and it never could have

All **forty** entries of `falsifiable_go_no_go` came back `passed: null`,
`n_observations: 1`. The declared cell is (category, ρ, N, k); v0's corpus holds
exactly **one prompt per category**; the criterion needs two clusters to form an
interval. So on this corpus the criterion cannot fire — not for this grid, not
for any grid, not on a re-run.

Meanwhile the tier printed, three times:

```
[superseded] maximum-statistic criterion: passes (20 passing cells) -- not a verdict.
             ... Read falsifiable_go_no_go in summary.json instead
```

It sent the reader to a structurally empty block while a statistic that *passes
on random data* sat on screen reading "passes". Both halves are individually
honest and the pair is misleading.

**Fixed:** `summarize` now emits `falsifiable_go_no_go_census`
(`cells` / `with_a_verdict` / `refused` / `max_observations_in_any_cell`) and the
CLI prints, immediately under the superseded line:

```
             AND IT IS EMPTY: 0 of 40 declared cells returned a verdict.
             This corpus holds ONE prompt per category ... THIS TIER PRODUCES
             CURVES, NOT A VERDICT
```

**v0 is a curve tier.** Nothing in it is a declared result, and this document
quotes it as description only.

---

## 2. The finding: the tax is a function of N, not of ρ

This is the first time all three arms have run on grids that are entirely
inside their packing windows, so it is the first time the curves mean anything.

| arm | ρ swept | tax at each ρ | range | mean |
|---|---|---|---|---|
| N=2 | 2.0 → 4.8 | +10.5%, +7.3%, −10.3%, −4.3%, −1.5% | 0.208 | **+0.4%** |
| N=4 | 3.0 → 6.6 | +2.0%, +5.1%, +3.8%, −0.6%, +0.4% | 0.057 | **+2.2%** |
| N=8 | 4.5 → 6.5 | +21.4%, +25.3%, +22.9%, +16.2%, +18.8% | 0.091 | **+20.9%** |

Sweeping ρ across an arm's **entire usable window** moves the tax by 0.06–0.21
and does so non-monotonically — the signature of noise, not of a curve. Changing
N moves it by **20.5 points**.

ρ is not the lever. That is the answer to H1, and it is a negative one for the
way SPEC 11.5 poses the question.

Two things sharpen it:

* **The cost is not linear in N.** N=2 → N=4 is +1.8 points; N=4 → N=8 is
  **+18.7**. At ρ = 4.8, the one grid point two arms share, N=2 reads −1.5% and
  N=4 reads +3.8% — a 5.3-point gap, comfortably inside each arm's own spread.
  N=2 and N=4 are not distinguishable here. N=8 is different in kind.
* **SPEC 11.5's target is unreachable, not merely unmet.** It asks for ρ < 2.0.
  The N=8 arm cannot be packed below 4.45 on this corpus. No sweep reaches it.

### A defect this run exposed, now fixed

The three arms **shared no ρ point at all**. N=8 swept 5.0 where N=2 and N=4
swept 4.8, while the tier's own text said "comparing N at fixed ρ is honest only
at 4.5 and 4.8" — 4.5 was in no other arm and 4.8 was not in N=8. The single
comparison the tier told the operator to make could not be made from the data.

Worse, a test asserted the sentence **verbatim**, so the false claim was pinned
in place by the suite. A string is not a fact about the grid.

N=8 now sweeps `4.5, 4.8, 5.5, 6.0, 6.5` — `check_grid` packs 4.8 at −0.5%
worst case across the eight prompts — and the test now intersects the three
grids instead of matching a sentence.

---

## 3. Agreement does not predict correctness. Two corpora, one answer.

The question Section 11.4 specifies, asked twice on the same night, with the
verdict coming from an answer key rather than a peer-class judge.

| | v3c-gt | v3c-ff |
|---|---|---|
| items graded | 465 of 526 seen | 160 |
| accuracy | **0.695** | 0.688 |
| mean agreement | 0.978 | 0.935 |
| **AUC** | **0.532** | **0.547** |
| Pearson r | 0.179 | 0.129 |

0.5 is no signal. Flagging the lowest-agreement items at a 10% flag rate catches
8 of 79 errors — **lift 1.009**, indistinguishable from flagging at random. The
20% rate reads 1.70 and the 30% rate 1.22, non-monotonic on 26/52/78 flagged
items, which is what noise looks like.

Within category, where pooling cannot manufacture a signal by mixing easy items
that both agree more and are more often right:

| category | accuracy | mean agreement | AUC |
|---|---|---|---|
| arithmetic | 0.409 | 0.941 | 0.596 |
| date_arithmetic | 0.358 | 0.985 | 0.515 |
| field_extraction | 1.000 | 0.987 | — (no variance) |
| threshold_decision | 0.814 | 0.982 | 0.570 |
| unit_conversion | 0.857 | 0.990 | 0.479 |

Accuracy ranges from 0.36 to 1.00 while agreement sits at 0.94–0.99 throughout.
The predictor is flat across a fourfold range in the thing it is supposed to
predict.

**This retires the confidence map.** It is the fifth and sixth measurement, and
the first two where the instrument was capable of showing a signal had there
been one — the 14 August result was uninterpretable because the judge accepted
93.3% of everything. Note that the *judge* did it again here: acceptance 100.0%
on 340 units in v3c-gt and 367 in v3c-ff. The answer key is the only reason
these runs say anything.

Caveats that belong with the number: 112 of 643 units carried no label, 61 items
were unintelligible and 27 echoed the prompt. The denominators are sound but the
models' format compliance is not.

---

## 4. k fixes the paragraph explosion — and only that

`comp-final`'s +22.4-point verdict carried a stated limit: the fragmented arm
wrote 7.96 paragraphs against monolithic's 2.0, so each fragment was writing a
complete answer and the result measured the implementation, not fragmentation.

v3c-ff, at N=3 on the same composition workload, shows what k does to that:

| condition | paragraphs | constraint score (raw) | constraint score (**comparable**) |
|---|---|---|---|
| monolithic | 2.00 | 1.000 | 1.000 |
| fragmented k=1 | **7.40** | 0.633 | 0.864 |
| fragmented k=3 | **2.00** | 0.711 | 0.786 |
| fragmented k=5 | **2.00** | 0.756 | 0.857 |

Consensus **completely removes** the paragraph inflation — 7.40 → exactly 2.00,
matching monolithic. The raw score rises with k accordingly (0.633 → 0.756).

And the comparable score, which excludes `paragraph_count` and
`words_per_paragraph` precisely because the assembler enforces them, **does not
move**: 0.864, 0.786, 0.857 on five compositions is flat.

So k repairs the assembler-enforced constraints and does nothing for the rest.
Which predicts that **`comp-final`'s headline would not improve at k=3**, since
the part k fixes is the part `constraint_score_comparable` already excludes.
That is cheap to test — `comp-dev` at k=3 — and worth testing before anyone
proposes consensus as the answer to the 22.4 points.

v3c-gt points the same way from the other side: the comparable tax **rises**
with k, +21.2% → +37.4% → +44.6%. More replicas, worse composite.

`repeated_sentences_cross_task` was **0 in every condition**. The signature
assembly failure — two workers writing the same sentence, invisible to a
transition-based coherence score because each copy reads well — did not occur on
this corpus. A clean negative on the thing the tier was built to detect.

---

## 5. A mislabelled pair of numbers, in every tier, for two weeks

Every tier printed:

```
rho=2.5  BooookScore-like  +21.15%
         absolute difference  BooookScore-like  +0.4335   (denominator-free)
```

On v3c-gt **every monolithic baseline was exactly 1.000** — the case where a
relative and an absolute difference are arithmetically the same number. They
differed by 0.22.

The gap was not the denominator. The relative headline is computed on
`booook_comparable`; the absolute was computed on `booook_like_score`. Those are
different scores, and the summary called them "the denominator-free version of
the same comparison".

The difference between them is the seam-anchored and assembler-enforced classes
that `booook_comparable` exists to remove, because a monolithic text has no
seams and cannot incur them, and there are N−1 seams — so including them charges
the fragmented arm **more the more it is fragmented**: 5.7 points at N=2 and
10.1 at N=8 on the table run of 26 August.

The absolute figure was therefore reintroducing, under a label promising
neutrality, exactly the bias the comparable score was created to retire.

**Fixed.** `abs_delta_booook` is now the comparable score with no denominator;
`abs_delta_booook_full` keeps the old figure under its own name and prints only
where it disagrees, labelled *not comparable across arms*. Three tests pin it,
including the baseline-of-1.0 case where the two must coincide.

---

## What this changes

* **H1 is answered, negatively.** ρ is not the lever; N is, and the cost appears
  between N=4 and N=8. The architecture cannot hold N and ρ independent — the
  usable windows are 0.45 wide at their intersection.
* **The confidence map is retired.** Agreement does not predict correctness, on
  two corpora, with a mechanical verdict.
* **Consensus is not the answer to the composition cost.** It fixes the part the
  headline already excludes.
* **v0 is a curve tier and now says so.**

## What is still open — and what was built for it

Both of the follow-ups this document called for now exist as tiers, rehearse
clean, and are in the runbook at Step 4b. Neither has been run against real
models yet.

```bash
bash scripts/run_ollama.sh comp-oracle    # ~1-2 h
bash scripts/run_ollama.sh comp-dev-k3    # ~1 h
```

**`comp-oracle`** is the arm that can change the reading of the 22.4 points.
Three arms on one mechanical scorer: monolithic, an oracle whose constraint
allocation is correct by construction, and the shipped pipeline. Every required
term is owned by exactly one fragment, and where the term is also `term_once`
the others are told to avoid it — so the two mechanisms `comp-final` localised
(duplication at N=3, omission at N=8) are gone by construction.

Its `decomposition.reading` gives one of two opposite answers, and both are
worth having: **ALLOCATION dominates** makes the 22.4 points a planner defect
with a planner fix; **PARALLELISM dominates** makes this workload
non-fragmentable rather than badly fragmented.

The oracle is deliberately **parallel** — no fragment sees another's text —
because a sequential oracle would recover the repetition constraints by
abolishing the thing under test. `no_repeated_ngram` and `no_repeated_sentence`
are therefore the classes allocation cannot reach, and what the oracle loses on
them is the price of parallelism itself.

The one check that can invalidate the whole run: `by_arm.mean_paragraphs`. If
the oracle still writes seven paragraphs, its brief is not being obeyed and
nothing below it means anything.

**`comp-dev-k3`** tests §4's prediction directly, against the k=1 dev estimate
of +18.40, dev to dev.

**Duplication versus ρ** is unchanged and is still an architecture decision, not
a run: the oracle partition is a covering, not a partition, and ρ charges for
every duplicated token.
