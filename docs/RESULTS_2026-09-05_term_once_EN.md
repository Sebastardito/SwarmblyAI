---
status: current
lang: en
---
# comp-dev-once — the prediction held, and with twice the margin

`results/comp-dev-once-20260905-120541`. Corpus digest `e9e382b9…`,
`harness_validation_only: false`, `embeddings_degraded: false`, **zero rows
excluded** for any reason.

**Preregistered:** at least 5 points of improvement over the +18.40 of the dev
k=1, that is **+13.40 or better**.

**Result: +8.61 points.** Almost twice the predicted margin.

---

## 1. The mechanism, told in constraints

The clean comparison is not against the September 4 dev, whose monolithic arm
was a different sample. It is against the `real` arm of `comp-oracle`: **the
same cell** (ρ 4.0, N 3, k 1), **the same monolithic value** (0.844), the same
corpus, the same day.

| class | total | monolithic | real, no dedup | **real + DEDUP** |
|---|---|---|---|---|
| `must_mention` | 36 | 32 | 29 | **27** |
| `must_not_mention` | 12 | 12 | 12 | 12 |
| `no_repeated_ngram` | 12 | 11 | 4 | 4 |
| `no_repeated_sentence` | 12 | 12 | 11 | 11 |
| **`term_once`** | 24 | **13** | **6** | **18** |
| `paragraph_count` | 12 | 12 | 0 | 0 *(excluded)* |
| `words_per_paragraph` | 12 | 12 | 0 | 0 *(excluded)* |

**`term_once`: 6 → 18 out of 24.** Twelve constraints won, and **well above the
monolithic arm**, which only reaches 13. It cost **two** `must_mention`.

Net across the 96 comparable checks: **62 → 72**. Which is exactly the
0.649 → 0.758 of the per-prompt averages.

The oracle had predicted +8 / −2. Over the real fragments it gave **+12 / −2**,
because the real arm already started from 21/24 on `must_mention` — its
accidental redundancy — while the redundant oracle started from 17/24. The
reason it had to work better here than in the oracle held, and for the stated
reason.

---

## 2. The shape of the result changed, not just the mean

| | comp-final (24 prompts, no dedup) | **comp-dev-once (12 prompts, with dedup)** |
|---|---|---|
| prompts where fragmenting lost | 19 out of 24 | **5 out of 12** |
| tied | 0 | **4** |
| prompts where fragmenting **won** | 0 | **3** |
| median | — | **+0.00** |

Three prompts where the fragmented arm **beat** the monolithic one
(`granary_dry` −0.167, `harbour_storm` −0.167, `relay_winter` −0.100). In
`comp-final` there was not a single one in twenty-four.

The median is zero: in at least half of the prompts, fragmenting no longer costs
anything measurable on this instrument.

---

## 3. What this result is NOT

**It is not a verdict.** Twelve clusters against a floor of twenty. The tier
printed `VERDICT NONE` and it is right.

**The interval does not drop below the threshold.** [−2.78, **+22.08**]. The
declared criterion requires the upper bound to sit below 5 points. The point
estimate moved a great deal; **the upper bound did not**. With 24 clusters the
interval would narrow, but nothing guarantees it drops below 5.

**The control still fails, and hard:** N=8 at +63.40, CI [+56.11, +71.18]. The
instrument still separates the arms, which is the check that matters most — if
the control had also collapsed, the dedup would be papering over everything.

**The dedup barely fires at N=8:** 8 sentences removed across twelve prompts,
against 30 at N=3. At N=8 the problem is not duplication but **omission** —
almost every `mentions_*` fails — and you cannot deduplicate what was never
written.

---

## 4. One of my three refutation conditions fired

I wrote them before the run. They are:

| # | condition | did it fire? |
|---|---|---|
| 1 | `mean_delta` ≥ +18.40 | **No.** +8.61 |
| 2 | `must_mention` rate equal to or below the shipped pipeline | **YES.** 27/36 against 29/36 |
| 3 | `term_once_sentences_removed` = 0 everywhere | **No.** 30 removals at N=3 |

**Condition 2 fired**, and that has to be said before anything else.

Now, the mechanism that condition was written to detect **did not occur**. I
wrote it like this: *"the removals cost more on real fragments than on the
oracle's, and the interaction is the finding"*. Measured: on the oracle's text
the dedup cost **−2** `must_mention`; on the real text it cost **−2**.
Identical.

So **the condition was badly specified**: any method based on deleting sentences
has to cost *something* on `must_mention`. A condition that fires whenever the
method does anything at all is not a refutation condition, it is a tautology. It
should have said *"it loses more on `must_mention` than it gains on
`term_once`"*, or *"it loses more than the 2 the oracle lost"*.

**Pointing this out after seeing the data is exactly the maneuver to watch under
a microscope**, so the record keeps both readings: the primary endpoint was met
with twice the margin, and a secondary condition fired because it was badly
written. The correction for the future is to name the **trade**, not the
direction.

---

## 5. Where the residue sits

Against monolithic, in checks:

| class | lost | reachable? |
|---|---|---|
| `no_repeated_ngram` | **−7** out of 12 | **No.** It is a property of a *pair* of fragments; no parallel worker can verify a pair |
| `must_mention` | **−5** out of 36 | Partly. It is an effect of **fragment size**: less room to fit the terms in |
| `no_repeated_sentence` | −1 out of 12 | Same as the first |
| **`term_once`** | **+5** out of 24 | Already solved — and above the ceiling |

After this change, **`no_repeated_ngram` is half of the residue**. And it is the
irreducible class. What is left to win is in `must_mention`, and `v0` already
said where: larger fragments, smaller N.

---

## 6. What comes next, and its cost

The only way to turn this into a claim is **24 clusters**, that is `comp-final`
with the flag.

That has a cost that has to be named: **it would be the second use of the final
split.** Its value comes from being evaluated exactly once. Using it twice
weakens it, even if the hypothesis is different and so is the system.

Three options, and the decision is yours:

| option | what it costs | what it gains |
|---|---|---|
| **a.** `comp-final --enforce-term-once` against this dev | second use of the final split, recorded as such | a real verdict, in ~2 h |
| **b.** A new corpus of 36 prompts, fresh dev+final | revalidating the difficulty tiers; half a day | the final split is worth one use again |
| **c.** Do not run it yet | nothing | the result stays as a dev description |

My recommendation is **(a), declared as a second use, with a preregistration
written beforehand**, and stating that a third use requires a new corpus. The
reason: the point estimate moved 10 points, but the upper bound is still at +22,
and the only datum that decides whether that is signal or the noise of twelve
clusters is running it with twenty-four.

And a warning about what to expect: **it is perfectly possible that the verdict
is still NOT MET.** A trade of +12 / −2 in one class does not have to be enough
to bring the upper bound of an interval below 5 points. That would still be the
best result this project has produced, and it is worth saying before the run and
not after.
