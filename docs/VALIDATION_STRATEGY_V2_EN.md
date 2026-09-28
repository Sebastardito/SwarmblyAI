---
status: current
lang: en
---

# Swarmbly AI — Validation strategy, version 2

## What has to be tested to show the architecture has a future, is feasible and is scalable

**Accompanies `WHITEPAPER_V2_EN.md`
and replaces the strategy implicit in whitepaper v1.4. It is written in plain
language on purpose: its job is to decide where to spend the time, not to argue.

---

## 0. The short answer

The strategy **does change**, but not in its objective. It changes in three
things: **the order**, **the price** and **what counts as passing**.

| | before (v1.4) | now (v2) |
|---|---|---|
| First test | Measure the coherence tax | **Fix the corpus.** Without it, no measurement of the tax discriminates |
| What is measured | One question: is fragmenting expensive? | A surface: *where* is it expensive? `D(ρ, δ)` |
| Tests available | The tax, H2, H3, verification, churn, SCI | The same, **plus five cheap tests** that did not exist before |
| Comparison baseline | Single-pass monolithic | Monolithic **and** a single agent with self-consistency |
| What scalable means | More nodes → more coverage | Two axes: coverage **and** solvability, which are independent |
| Abandonment criterion | 5%, upper bound of the CI, pre-registered | **Unchanged.** It is not rewritten |
| Status of the agenda | to be executed | **executed**: 13 tests against 341 real runs over five families (§11) |

**The net effect in one line:** the cheap work moves to the front, the expensive
work sits behind a single blocker, and one test is cancelled. It is a better
agenda than the previous one — but it is worth being clear about why: it is not
that the architecture is now more likely to work, it is that it can now be ruled
out before spending.

---

## 1. Why it changes: the underlying reason

Version 1.4 treated fragmentation as an action with a cost. You measured the
cost and decided.

The new fundamentals say that cost **is not a number, it is a function of three
things the design chooses**: where you cut (δ, the density of dependencies
crossing the cut), what size (L) and how much flank you pay (F).

That has one uncomfortable consequence and one comfortable one.

**The uncomfortable one:** all previous measurements of the coherence tax mixed
the three together. They are not wrong, but they are not interpretable as "the
cost of fragmenting" — they are the cost of fragmenting *in one particular way
that nobody chose on purpose*.

**The comfortable one:** if the cost depends on where you cut, then **there are
good cuts and bad cuts**, and finding the good ones is an engineering decision
rather than a fixed property of the architecture. That turns a negative result —
"fragmenting costs 2.30%" — into an answerable question: which of the two regimes
were you measuring?

And the data itself already hints at it, which is what makes it worth chasing.

---

## 2. The observation that reorganises everything

In the abandonment-criterion measurement, over 16 held-out prompts:

- The mean tax was **+2.30%**, 95% CI **[−2.05%, +7.49%]** — criterion **not
  met** by 2.49 points on the upper bound.
- But the **median prompt loses exactly 0.00%**, and **11 of 16 are at or below
  zero**.
- And **two prompts** — `tbl24_outturn` (+28.50%) and `tbl24_bonded` (+23.08%) —
  are between them **140% of the mean**. Without them, the other fourteen average
  **−1.06%**: splitting in two was slightly *better* than not splitting.

The honest description is not "fragmenting costs 2.3%". It is: **on 11 of 16
prompts it was free, and on 2 it was expensive.**

And there is one more clue, which is what turns this into a hypothesis rather
than a curiosity: **those two prompts are the only two where `N` = 2 is worse
than `N` = 8** (outturn +28.50% against +13.57%; bonded +23.08% against
+14.00%). More fragments *helping* is not what a coherence-tax story predicts. It
is what a **partition-quality** failure predicts: a two-way split that put a seam
somewhere costly, which cutting eight ways happened to avoid.

> **The hypothesis that organises the agenda:** the cost is not of fragmenting,
> it is of *where*. The two expensive prompts are high-δ prompts badly cut.

If that is true, the architecture does not need to be cheaper — it needs a router
that can recognise the expensive case. And that is exactly what it already does
(P2), only today it decides on the wrong features.

---

## 3. The single blocker: the corpus

Before anything else, there is an instrument problem and it has to be solved
first because **two expensive tests depend on it**.

**What happened.** The L-curve experiment was built and run. The monolithic arm
answers **1 of 72** global questions, even on the smallest material. With the
baseline on the floor there is no difference to measure.

**What saved the run was verifying the instrument before concluding anything:**

- A hand-built perfect answer scores **100% on all 72 documents**. The grader is
  not the problem.
- Five model families were probed: **4 of 5 do the local lookups at ~0.84**. The
  models are not the problem.
- Global questions come out at **4 of 60** across all families.
- The hypothesis that the contract wrapper was strangling the global answer was
  tested with an A/B and **was refuted by its own measurement**: 4/60 both ways,
  delta **0.000**.

**The diagnosis is corpus design, not architecture and not instrument.** The
corpus needs a *global* question this model pool can answer on small material.

**The operating rule, and it matters:** the held-out half of the corpus **must
not be run**. Spending the reserved split against an instrument that does not
discriminate destroys the only reserve left, and it cannot be recovered.

**What is needed.** An answerable global question is one that requires combining
information from two or three places in the document, not twelve. The test that
it works is simple: the monolithic arm must clear the floor plainly — say 0.5 or
better — because if the monolithic arm cannot, there is nothing to compare
against.

---

## 4. The cheap tests, in order of attack

These five need no new corpus. Three of them need no new measurement at all.

### 4.1 Split `k` into three — cost: zero measurement

Today `k` pays for three distinct things at the price of the most expensive:

| purpose | what it buys | correct mechanism |
|---|---|---|
| `k_avail` — availability | that the task completes even if a node drops | threshold over-dispatch |
| `k_verif` — verification | that a dishonest node cannot impose a false result | credibility-based spot-checking |
| `k_epist` — epistemic redundancy | that the divergence map has something to align | replicas from different families |

**It is a conceptual separation of a parameter that already exists.** Implement
and observe. There is no experiment to run.

*Predicts:* the total cost can be lowered while keeping all three guarantees.
*Killed if:* they turn out to be so coupled in practice that separating them
saves nothing.

### 4.2 The triage gate — cost: cheap, binary prediction

A mechanical predicate per level: *does the carry that arrived answer the task
that requested it?* No judge, no model.

*Predicts:* the blast radius of a defective fragment stays contained in that
fragment. The recorded incident of **42 of 60 packets carrying another packet's
answers** becomes impossible.
*Killed if:* it rejects so much legitimate work that the retry cost exceeds the
damage it prevents.

The prediction is binary — the incident happens or it does not — which is why it
is the second cheapest to settle.

### 4.3 Uniqueness assigned in the plan — cost: a corpus that already exists

Today `term_once` is asked for in the contract and enforced mechanically at the
assembler. It works, and it is measured: it raised compliance from **6/24 to
18/24**, above the monolithic arm's 13/24.

The proposal is to compute the uniqueness set **before** dispatch and assign each
element to exactly one fragment, as a property of the plan.

*Predicts:* the violation rate falls **to zero**, not improves. A node cannot
satisfy "exactly once" because it does not know what the others wrote; the
planner can.
*Killed if:* it does not go below 18/24, which is what mechanical enforcement
already achieves.

The prediction is deliberately strong so that it is easy to refute. And there is
an already-measured baseline to compare against, which is what makes it cheap.

### 4.4 Explain the bimodality with δ — cost: the 16 prompts already run

This is the one that gives the most information for what it costs, and it did not
exist in the previous strategy.

**Procedure.** For each of the 16 prompts already measured, compute δ — a measure
of how many necessary relations cross the cut that was made, normalised by the
number of fragments. Then look at whether the two expensive prompts have high δ
and the eleven free ones low δ.

*Predicts:* yes, with clear separation.
*Killed if:* δ does not separate the two groups. Then the bimodality has another
cause, the second axis of whitepaper §6.8 is decoration, and M4 loses its
empirical motivation before a corpus has been spent on it.

**Why it is valuable:** it is the cheapest test that can kill the most expensive
model. If δ does not explain the bimodality, the calibrated corpus M4 needs is
not worth building.

### 4.5 The ρ scaling law — cost: logs that already exist

The new derivation says:

```
ρ ≈ (L + 2F) / L  +  H / (L · s)
```

with `H ≈ 39` header tokens per packet and `s ≈ 15` tokens per sentence.

That is a **scalability prediction checkable against historical data**: cost per
unit of material must *fall* as `L` grows, tending asymptotically to
`1 + 2F/L`.

And there is a limiting case already lived through: the composition measurements
were taken with **35-token** fragments and a **39-token** header. In that regime
the header weighs more than the material. If the derivation is correct, it
**explains without fitting why ρ appeared to have a high floor** — it was not a
property of the protocol, it was fragmenting too finely.

*Procedure:* recover from the logs the observed ρ at different fragment sizes and
overlay it on the predicted curve.
*Killed if:* the observed ρ does not follow that shape. Then the derivation is
wrong and the 29% saving is fictitious.

This test requires running nothing. It is reading data that is already written.

---

## 5. The expensive tests, and what they depend on

### 5.1 The `D(ρ, δ)` surface — depends on the corpus (§3)

Three measurements, all over a difficulty-calibrated corpus:

- **Fix δ, vary ρ** (same cut, different flank) → should give a curve
  monotonically decreasing in distortion.
- **Fix ρ, vary δ** (same budget, cuts of different coupling) → should give
  variation in distortion **at constant rate**. This is the one that decides: if
  there is no variation, ρ suffices as an axis and the new framing adds nothing.
- **Look for the unreachable region** → a distortion floor that no ρ improves.

### 5.2 The `L` curve — depends on the corpus (§3)

This is the test that cannot be run today. What it looks for:

- **`L_min`**: a hard floor exists below which a fragment is not independently
  solvable. It is predicted to be sharper than the optimum.
- **The optimal band**: predicted to be wide, a factor of 3 to 6, and dependent
  on how you define "unit". The source analogy supports it: over the same
  material, Pfam averages 96 residues and SCOP 174 — almost double, because they
  cut by different definitions.

**This is worth saying in full:** `L_min` and the band are **predicted, not
measured**. Any `L` the project uses today is an informed guess.

### 5.3 The aligner with learned substitution — the most expensive

Build M1: segment into sentences, align with affine gaps, a substitution matrix
counted empirically BLOSUM-style, consistency extension, position-specific
profile.

*Predicts:* it separates correct from incorrect better than match counting and
better than a scalar per answer — **in a non-saturated regime**.
*Killed if:* with the correct instrument and in a regime where the models
genuinely disagree, per-unit agreement does not beat chance.

**The regime clause must be declared now, and here is why.** The first
measurement failed partly because the judge accepted 93.3% of units — there was
no variance left for a correlation to appear against. Declaring the condition in
advance is the only thing that prevents using it as an excuse afterwards. Stated
once the result is in, it is worth nothing.

**And what does not change:** the confidence map's reliability claim **remains
withdrawn**. M1 is a different instrument, not a reinterpretation of that result.
Labels are reported as *agreement*, never as *accuracy*.

### 5.4 Re-test of the abandonment criterion — depends on the corpus and sample size

Two conditions, and neither is optional:

**Sample size.** The declared cell of the composition experiment gave a mean of
−0.35 with a between-cluster standard deviation of 20.36 and a standard error of
4.16, for a CI of [−8.49, +7.80] against a threshold of 5.0 — it contains both
the threshold and zero, and decides nothing. The calculation, cross-checked
against the measured standard error, calls for **60 prompts minimum, 72 with
margin**.

**Repeats buy nothing.** The pipeline is deterministic at temperature 0. More
runs of the same prompt do not reduce the *between-prompt* variance, which is
what dominates. It is a useful negative result: it saves spending compute in the
wrong direction.

### 5.5 What was already there and is unchanged

H2 (capability substitution), H3 (conversion), dishonest-node detection, latency
under churn, and the SCI environmental measurement. None of the new fundamentals
touches them. The whole privacy and verification agenda is **intact**.

---

## 6. What "feasible" and "scalable" now mean

This is the part of the question that changes most, and it is worth separating.

### 6.1 Feasible

**Before:** can a 3–8B model solve an atomic sub-task as well as a frontier
model? (H2)

**Now there is a prior question:** *can this material be cut into domains at
all?*

If the dependencies cannot be avoided — if δ does not come down whatever you do —
then no amount of worker quality saves the situation. The fragment stops being a
domain, and the independence guarantee does not apply.

That moves the router from the margin to the centre. Feasibility becomes, in
large part, **routability**: not "is fragmenting cheap?" but "can the system
recognise in advance the cases where it is not?". And because the cost of being
wrong is asymmetric — fragmenting something that should not be is worse than
refusing too often — the router is calibrated with F_β and β < 1, which was
already the case, but now with δ among its features.

### 6.2 Scalable

**Before:** more nodes → more coverage → better.

**Now there are two independent axes, and the second is new:**

| axis | question | what governs it |
|---|---|---|
| **Coverage** | will an answer arrive? | `c ≥ ln(1/ε)/(1−p)`, with *p* measured |
| **Solvability** | does the answer contain the necessary information? | the information floor: `L > max{ℓ_interleaved, ℓ_triple} + 1` |

And they are **independent**. You can add all the nodes you want and remain in a
region where no correct assembly is possible, because the fragments simply do not
contain the information — however clever the assembler is.

**This was already measured without knowing it.** The `no_repeated_ngram`
constraint stayed at **4/12 against 11/12** for the monolithic arm under *every*
context-allocation policy tested. It was the defect that would not yield. The
reason, now nameable: a repeat is a property of *a pair* of fragments, not of a
fragment, and a fragment cannot avoid repeating what it cannot see. No allocation
*can* reach it. That is why the solution is M2 — resolve it in the plan — and not
more context.

**Consequence for scale testing:** a scalability test has to measure both things.
That quality holds as material grows, *and* that the fragments remain solvable.
Measuring only the first gives a system that scales confidently toward wrong
answers.

### 6.3 Has a future

The criterion does not change: **there must exist a ρ at which degradation is
below 5% against monolithic generation, in at least one task category**, judged
against the **upper bound** of the 95% CI clustered by prompt.

What changes is how a failure reads. Under the new framing, "not met" no longer
means "the architecture does not work". It means "at the point on the surface
where it was measured, it was not met" — and the next question is whether another
point exists. That **is not an escape hatch** so long as the point is declared
before measuring, which is precisely what pre-registration requires.

---

## 7. The correct baselines

A small change of statement with a large consequence.

| comparison | status |
|---|---|
| vs. single-pass monolithic | stands |
| vs. **a single agent with self-consistency** | **new, mandatory** |
| vs. speculative decoding | stands, as the honest speed comparator |

The reason: Zhang et al. find that multi-agent methods "fail to consistently
outperform single-agent baselines such as Chain-of-Thought and Self-Consistency,
even when consuming additional inference-time compute", across 9 benchmarks, 4
models and 5 methods.

Their criticism targets **debate** — agents arguing to converge — and Swarmbly
does not debate, it decomposes. But the lesson transfers all the same:
**additional compute must be justified against the right rival**, and single-pass
monolithic generation is not it. An architecture that only beats that one is
comparing itself against the easy rival.

This raises the bar. Every past comparison looks somewhat less favourable than it
did.

---

## 8. What does not change

Worth having in writing so it is not re-argued:

- **The 5% criterion**, against the upper bound of the interval, pre-registered.
  It is not rewritten now that it has produced a failure.
- **The coverage/conversion decomposition.** The swarm supplies coverage, the
  client supplies conversion, and the ceiling is set by the client's selector.
- **The sample-size arithmetic:** 60 prompts minimum, 72 with margin, and repeats
  buy nothing.
- **H2 and H3** as stated.
- **The whole privacy, verification and adversarial agenda.** Intact.
- **The two withdrawals from v1.4.** The ρ-tax curve and the confidence map's
  reliability claim remain withdrawn. Nothing new lifts them.

And one test **is cancelled**: V3c, the agreement calibration, is closed. It was
run three times against an answer key and returned common odds ratios of **3.47,
0.26 and 1.24** — above, below and astride 1 on the same question. Three mutually
contradictory estimates are not a weak signal: they are no signal, measured three
times. Reopening it would require a new instrument, not a re-run of that one.

---

## 9. Instrument discipline

A note that is not about the architecture but about how it is measured, and that
is worth more than any of the individual measurements.

This project's recurring defect has a name:

> **A check that claims more than it measured.**

An aggregate is reported without asking where it comes from. It appeared **four
times in a single day**, and each time inside code written to catch the previous
occurrence: a verdict reading a key the bootstrap function did not return — and
which would therefore have said "not met" on any data at all; a probe that
silently degraded to one model family and concluded about five; a difficulty
diagnosis derived from a single model and presented as a property of the corpus;
and a threshold that fired on the effect of a single cell.

**The defence that worked was not more care. It was making the check refuse.**
Derive the family list from the runner itself and refuse below two. Withdraw a
pooled conclusion if removing the largest contributor undoes it. Cross-check the
sample-size plan against the measured standard error and refuse if they differ by
more than 25%.

An instrument that can refuse is worth more than one that is right more often.

Four thresholds exist for that reason and are declared: **a minimum of 20
clusters before a verdict is issued**; a **baseline floor of 0.20**, added
*after* seeing the data and labelled as such in the pre-registration — because a
declared amendment counts and a silent one does not; and the two control
tolerances above.

**Rule for everything that follows:** each test in this document is implemented
with its own refusal condition before it is run. If you do not know what would
make it refuse, it is not ready to run.

---

## 10. Summary table

| # | test | predicts | killed if | cost | depends on | **status** |
|---|---|---|---|---|---|---|
| 1 | Split `k` into three | total cost falls while keeping all three guarantees | the three are so coupled that separating saves nothing | **none** | nothing | unmeasured |
| 2 | Triage gate | damage contained to one fragment; the 42/60 incident impossible | it rejects so much legitimate work that retries cost more | very low | nothing | **survives** (T02R) |
| 3 | Uniqueness in the plan | violations to zero, not "better" | it does not go below 18/24 | low | existing composition corpus | **survives corrected** (T03R) |
| 4 | δ explains the bimodality | the 2 expensive have high δ, the 11 free low δ | δ does not separate the groups | **none** | the 16 prompts already run | **falsified** (T04, T04R) |
| 5 | ρ scaling law | cost/material falls with `L` toward `1+2F/L` | observed ρ does not follow the curve | **none** | existing logs | **verified** (T05R) |
| 6 | Corpus with a global question | the monolithic arm clears the floor plainly | — (construction, not a test) | medium | — | **built and verified** (T06, T06R) |
| 7 | `D(ρ, δ)` surface | δ moves distortion at constant ρ | distortion depends on ρ alone | high | 6 | **falsified, and it is the decisive one** (T07R) |
| 8 | `L` curve | a hard `L_min` exists; optimum is a wide band | no discernible floor or band | high | 6 | **measured; the band does not appear** (T08R, T0LR) |
| 9 | Criterion re-test | — | — | high | 6 + 72 prompts | **refused**: confounded with length (T09R, T11) |
| 10 | M1 aligner | localising beats clustering, in a non-saturated regime | agreement does not beat chance where real disagreement exists | **highest** | 6, and building the aligner | built; **no regime** in this corpus (T10, T10R) |
| 11 | Routability | the router anticipates the expensive cells | AUC does not beat chance | low | existing logs | **falsified per cell; separates by class** (T0RR, T0RR2) |

**Recommended order:** 1 → 2 → 4 → 5 → 3 → 6 → 7 → 8 → 9 → 10.

The first four cost between nothing and very little, and two of them (4 and 5)
can **kill the expensive models before anything is built**. That is the entire
point of this reordering.

---


## 11. What the execution returned

The agenda was executed. The instrument is two published artifacts — a reference
implementation and a falsification harness — and a record of **341 runs** over
five local model families. The detail is in §15.9 of the whitepaper; what
follows is what happens to **this strategy**.

**Three of the four cheap tests did exactly what was asked of them.** Test 4 (δ
and the bimodality) and test 5 (the ρ scaling law) were declared capable of
killing the expensive models before anything was built. Test 4 killed M4 without
spending corpus. Test 5 verified the ρ derivation with 7.5% accounting error.
Test 2 confirmed triage containment. The reordering paid for itself.

**One of the strategy's predictions was false, and that should be said.** §4.4
claimed test 4 was free and could kill M4 *before* building the corpus. Not
quite: over the 16 held-out prompts, δ turned out to be **constant** — 3.50
across all 24 cells — and a predictor with no variance separates nothing. Test 4
could be run, but its force came from a much larger table corpus (127
intra-category cells) and from the controlled experiment of test 7, which **did**
depend on the corpus. The claim "free and sufficient" was optimistic.

**Test 7 turned out to be the decisive one, as foreseen, and it failed.** Cutting
the same prompt twice at the same `L` — once minimising δ and once maximising it
— leaves ρ equal and moves δ alone. M4 predicts that the bad cut worsens
distortion in every pair; it worsens in 19 of 32. This is the measurement the
strategy declared decisive in advance, and it is the one that decides.

**Test 9 gives no verdict, and the reason is a lesson in method.** The aggregate
came out in favour of fragmenting, but the fragmented arm received more output
budget than the monolithic one. The harness **refuses** rather than reporting a
criterion met. The correction is implemented and the pending run is a single
command.

**And there is a test this strategy did not have: number 11.** It was not on the
agenda because v2 took for granted the premise that a router can anticipate a
cell's cost. Measured, it cannot: AUC 0.38 with δ and reputation, 0.47 with
capability probes. What does separate is the node class. The lesson for this
strategy is general: **the premises that are not on the list of tests are the
ones that accumulate the most risk**, precisely because nobody wrote them as
falsifiable.

**What remains, in order:** (1) the run with matched output budget, which
unblocks test 9; (2) a corpus that produces real disagreement between families,
which unblocks test 10; (3) test 1, which still costs nothing and still has not
been done.

---

## 12. Honest close

This strategy is better than the previous one in a precise and limited sense: **it
allows ruling out before spending**. Four tests costing between nothing and little
move to the front; two of them can falsify the expensive models without building a
corpus; one test is cancelled; and the blocker concentrates at a single point —
the corpus — instead of being spread out.

What it does **not** do is improve the architecture's odds. The abandonment
criterion has neither been met nor failed: it **has not been measured**, and
until the output budget is matched nothing can be claimed about it. The `L`
curve is now measurable and was measured: `L*` varies by family, and the
predicted wide band **does not appear**. Of the five models, two are falsified,
two survive corrected, and one still lacks an instrument. And the project's dominant risk is still not technical: volunteer
computing has been contracting for two decades, and no incentive design in this
project is yet a demonstrated answer to why that reverses.

What this agenda buys is **knowing sooner and more cheaply**. Which, in a
one-person project, is probably what is worth most.

---

*Swarmbly AI — Sebastián A. Espinoza-Ulloa · Spanish companion:
`VALIDATION_STRATEGY_V2_ES.md`. Main document: `WHITEPAPER_V2_EN.md`.*
