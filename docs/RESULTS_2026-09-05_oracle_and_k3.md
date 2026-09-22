---
status: current
lang: en
---
# comp-oracle and comp-dev-k3 — 5 September 2026

Two runs, both short, both testing something named before it started. One
confirmed its prediction. The other refused to answer the question it was built
for, because the instrument was wrong — and the way it was wrong turned out to
be the more interesting result.

| run | directory |
|---|---|
| comp-oracle | `results/comp-oracle-20260905-103954` |
| comp-dev-k3 | `results/comp-dev-k3-20260905-104132` |

Corpus digest verified on both: `e9e382b9…`.

---

## 1. comp-dev-k3 — the prediction holds

> **Stated before the run:** `comp-final`'s headline does **not** improve at k=3.

| | paired difference | 95% CI | n |
|---|---|---|---|
| k=1 dev (4 Sept) | **+18.40 points** | [+9.79, +29.72] | 12 |
| **k=3 dev (5 Sept)** | **+19.38 points** | [+11.18, +27.36] | 12 |

Median +18.33. The control at N=8 reads +44.65 and fails as required. Neither
prints a verdict — 12 prompts against a floor of 20, by design.

**Consensus is not the answer to the composition cost.** k=3 leaves the headline
where k=1 left it, and if anything a point worse. The reasoning that predicted
it holds up: k repairs `paragraph_count` and `words_per_paragraph`, and
`constraint_score_comparable` is defined by excluding exactly those.

Two things worth recording from the same run:

* **The coherence tax read +4.07%** on texts where the mechanical count finds
  19.4 points lost. Third independent confirmation that the tax is the wrong
  instrument for prose.
* **The `_full`/`comparable` split printed correctly in the field.** The new
  line read `on the FULL score +0.1304 (seams and assembler-enforced classes
  included — not comparable across arms)` beside `+0.0407`. Before yesterday's
  fix those two would have appeared as "relative" and "absolute" of the same
  thing, three times apart.
* Mean agreement fell to **0.735** on compositions against 0.978 on
  ground-truth answers — prose replicas genuinely differ, so the saturation
  problem is a property of short factual answers, not of the agreement
  machinery. The judge still accepted **100.0%** of 720 units.

---

## 2. comp-oracle — the oracle scored below the thing it was measuring

| arm | constraint score (comparable) | paragraphs |
|---|---|---|
| monolithic | **0.844** | 2.00 |
| oracle (exclusive allocation) | **0.571** | 2.00 |
| real (shipped pipeline) | **0.649** | 8.92 |

The decomposition guard refused to attribute the loss and named the oracle's
briefs as the thing to check. It was right, and that guard was written the day
before precisely for this shape of result.

**The first check passed, and it matters:** the oracle wrote **2.00 paragraphs**
against monolithic's 2.00. The brief was obeyed. So half of `comp-final`'s
stated limit is now answered — telling a fragment "write paragraph 1 of 2 and
nothing else" works, and the 7.96 paragraphs the shipped pipeline produces are a
brief defect, not a fact about fragmentation. The real arm still writes **8.92**.

### The whole collapse is in one bucket

Splitting `must_mention` by whether the term is **also** subject to `term_once`:

| bucket | monolithic | oracle | real |
|---|---|---|---|
| term is **also** `term_once` | 21/24 (0.875) | **11/24 (0.458)** | 21/24 (0.875) |
| term is **not** `term_once` | 11/12 (0.917) | 8/12 (0.667) | 8/12 (0.667) |

On the terms exclusivity does not touch, **the oracle and the shipped pipeline
are identical.** On the terms it forbids to every non-owner, the oracle halves.

Pooled, this reads `must_mention` 19/36 oracle against 29/36 real, which looks
like a worse oracle. Split, it is a diagnosis: the exclusivity clause converts a
term with N chances into a term with **one**, and a 3B owner complies about half
the time.

And it did buy what it was for — `term_once` **9/24** against real's **6/24**.
Three satisfied constraints, for ten lost. A bad trade, hardcoded as a rule.

---

## 3. The finding this produced instead

**A term that must APPEAR and must appear EXACTLY ONCE is a conjunction that
parallel workers cannot satisfy blind.**

| strategy | `must_mention` | `term_once` |
|---|---|---|
| redundancy (what the shipped pipeline does by accident) | 21/24 | 6/24 |
| exclusivity (what the oracle did on purpose) | 11/24 | 9/24 |
| **one writer who can see the whole text** | **21/24** | **13/24** |

Redundancy makes the term appear and guarantees it appears twice. Exclusivity
makes it appear once and often not at all. Monolithic satisfies both, because
the information each parallel worker is missing is *the other worker's output* —
and no allocation scheme over parallel fragments can supply it.

This is a stronger and more specific statement than "fragmentation costs 22
points". It names a class of constraint — global, exactly-once — and says why
parallel fragmentation cannot satisfy it, in a way that is independent of this
implementation's quality.

Note the shipped pipeline lands on the redundancy side **by accident**: every
fragment sees the whole prompt, so several mention the term. That accident is
load-bearing. Anyone "fixing" the planner to allocate terms properly would have
made things worse, and now there is a measurement saying so.

### And the parallelism cost, measured cleanly

`no_repeated_ngram`: monolithic **11/12**, oracle **5/12**, real **4/12**.

This is the one number in the run that means exactly what it was designed to
mean. Allocation was never going to help — a repeated phrase is a property of a
*pair* of fragments and no parallel worker can check a pair — and it didn't. Six
of twelve lost to parallelism alone, with a perfect allocation.

---

## 4. What was built in response

The allocation policy is now a **parameter with both halves measured**, not a
rule. Five arms:

| arm | what it does |
|---|---|
| `monolithic` | the ceiling |
| `oracle-exclusive` | one owner per term, others forbidden it |
| `oracle-redundant` | every fragment required to mention every term |
| `oracle-redundant-dedup` | the redundant arm's **text**, with `term_once` enforced mechanically at assembly |
| `real` | the shipped pipeline |

`oracle-redundant-dedup` is the proposal the trade produced, and it is an
**assembly** change rather than a planning one. `paragraph_count` and
`words_per_paragraph` are already satisfied mechanically by the assembler rather
than by asking a model nicely; `term_once` is the same shape of constraint — a
property of the finished text, checkable by counting — and only history puts it
on the generation side.

The dedup keeps the first sentence carrying each once-term and drops the rest.
Whole sentences, because removing a noun phrase leaves a sentence that no longer
parses and this step has no model in it. The cost is that a deleted sentence may
carry another required term, which is why `sentences_removed` travels with the
score rather than being assumed away.

The dedup arm reuses the redundant arm's **text** rather than generating again,
so the comparison between them is the assembly step alone and not two samples of
a model.

**Three oracles means three chances to pick a winner after the fact.** So each
gets its own decomposition, reported side by side and named, and the headline
stays on the policy declared first — exclusive, the one this run used. Choosing
the best-scoring policy after seeing the scores is the defect
`falsifiable_go_no_go` exists to prevent.

The `must_mention` split is now **computed**, not noted. It was invisible in the
mean, and a mean that hides its own diagnosis is the thing this project keeps
correcting.

---

## What this changes

* **Consensus is not a lever on composition.** Measured, predicted in advance,
  confirmed.
* **`comp-final`'s stated limit is half removed.** The paragraph inflation is a
  brief defect and the oracle does not reproduce it. The remaining half — how
  much of the 22.4 points survives a correct allocation — is still open, because
  the first allocation tried was the wrong one.
* **The planner should not be "fixed" to allocate terms exclusively.** It would
  cost more than it buys, and there is now a number for it.
* **Global exactly-once constraints belong to the assembler**, alongside the two
  that already live there. `oracle-redundant-dedup` tests that in about an hour.

## Next

```bash
bash scripts/run_ollama.sh comp-oracle    # ~2-3 h, five arms now
```

Read in this order: `by_arm.mean_paragraphs` (the run is void if the oracles
are not at 2.0), then `must_mention_split`, then `by_constraint_kind`, then
`decomposition_by_policy`.

The result that would matter most: **`oracle-redundant-dedup` at or above
monolithic on `term_once` while holding 21/24 on `must_mention`.** That would
make the exactly-once class an assembler problem with a solved answer, and would
take a real bite out of the 22.4 points.
