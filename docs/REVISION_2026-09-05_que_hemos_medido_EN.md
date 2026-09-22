---
status: current
lang: en
---
# Are we going in circles? — a review of the framing

**September 5, 2026.** Written because Seb asked two things that had to be
answered without getting defensive: whether there is something wrong in how the
tests are framed, and whether there is a bias toward exposing weaknesses instead
of seeing the strength of the foundation.

Both answers are **yes, in part** — and the second points to a framing defect
that is larger than any of the execution errors.

---

## 1. The fact that reframes everything

The largest prompt in **the entire** project measures **375 tokens**.

| corpus | n | median | maximum |
|---|---|---|---|
| `complex.json` | 20 | 332 | **375** |
| `ground_truth.json` | 15 | 243 | 373 |
| `tables24.json` | 24 | 332 | 332 |
| `free_form.json` | 11 | 179 | 296 |
| `prompts.json` | 8 | 145 | 160 |
| `composition.json` | 36 | 106 | 119 |

The smallest model in the pool (`gemma2:2b`) has a window of **8,192 tokens**.
The largest prompt uses **4.6%** of the memory of the smallest node.

**No task, in any corpus, in any run, has ever needed to be fragmented.** The
monolithic arm always worked because it always fit.

So what we have been measuring for three weeks is: *how much it costs to split a
task that did not need splitting*. And the correct answer to that question —
measured rigorously, six times, with instruments we kept correcting — is **it
costs**. It could not have been anything else. There is no possible gain to
measure, because there was never anything infeasible.

That does not invalidate any measurement. It invalidates them as an
**evaluation of the architecture**.

---

## 2. On bias: where there is some and where there is not

### Where the instrument DID favor the architecture

* `constraint_score_comparable` was created to **remove** a bias against the
  fragmented arm: the classes anchored to seams charged more the more
  fragmented the run was (5.7 points at N=2, 10.1 at N=8).
* `packing_ceiling`, `predict_rho` and `check_grid` exist to eliminate **false
  failures** — cells that aborted because of the grid, not because of the
  architecture.
* The oracle arm was built to give the architecture its **best case**, and when
  the first policy was unfairly hard on myself I corrected it and measured both
  halves.

### Where the framing IS tilted

1. **Every gate runs in one direction only.** None has ever aborted a run for
   being *too favorable*. They stop false positives and not false negatives.
2. **Every verdict is judged on the UPPER bound** of the interval. For a *cost*
   measure that means always taking the most pessimistic estimate. It is the
   right choice for a claim of the form "it costs less than 5 points", but it
   means a marginally good result reads as a failure.
3. **I replaced a favorable instrument with an unfavorable one.** The coherence
   tax read +0.14%; I argued it was saturated and blind to duplication and
   omission — which is true and demonstrable — and I replaced it with a count
   that reads 22 points. The justification is solid; **the direction of the
   change deserves to be written down**.
4. **The composition corpus is built with the hardest possible conjunction for
   parallel workers**: `must_mention` + `term_once` on the same term. I built it
   that way so the baseline would not saturate. The side effect is that I
   selected exactly the constraints that are sensitive to coordination.
5. **3B models confuse capability with architecture.** A good part of the loss
   on `must_mention` is the model not following the instruction, not the
   architecture losing information. There is no arm that separates the two.
6. **No axis where fragmenting should win has ever been measured.** Not cost per
   node, not peak memory, not feasibility. Every measurement is quality against
   monolithic, which is the only axis where splitting can only lose.

Point 6 and the fact of the 375 tokens are the same problem seen twice.

---

## 3. And even so: we have not gone in circles

Seven things were established, and none has had to be withdrawn:

| # | result | status |
|---|---|---|
| 1 | Agreement between models does **not** predict correctness. AUC 0.532 and 0.547, six measurements, against an answer key. | Closed. Withdraws the confidence map. |
| 2 | ρ is not the lever; **N** is. Within one arm, sweeping the whole window moves 0.06–0.21; changing N moves 20.5 points. | Closed. |
| 3 | ρ < 2.0 with N=8 is **unreachable** in this corpus, not merely unmet. | Closed. |
| 4 | The coherence tax is the wrong instrument for prose. | Closed, three confirmations. |
| 5 | Consensus (k) does **not** recover the composition cost: +19.38 against +18.40. | Closed, predicted in advance. |
| 6 | With perfect assignment, **98.6%** of the composition cost is still there. It is not a defect of the planner. | Closed at dev level. |
| 7 | `term_once` belongs to the **assembler**: 14/24 against 6/24, above monolithic. | Promising, under test now. |

Seven conclusions in three weeks is not going in circles. The feeling comes from
the fact that **the errors are loud and the conclusions are quiet**, and that six
of the seven are negative. A negative result is still a result: point 1 kills an
entire feature of the design, and point 2 redirects all the optimization effort
that would have been spent on ρ.

---

## 4. What has to change

### a. Test the case the architecture exists for

A corpus where the monolithic arm **cannot run**: material that exceeds the
node's window. There the question stops being "how much does splitting cost?"
and becomes "is this feasible in any other way?". If the answer is no, the
quality cost is the price of existing, not a loss.

It is also the only way for ρ to mean anything: today ρ = 4 says we pay four
times the tokens for a worse result. With material that does not fit, ρ is the
reason the result exists at all.

### b. Measure the axes where fragmenting should win

Tokens per node, peak memory per node, and **feasibility**: did it run or did it
not? None of them is instrumented today.

### c. Separate model capability from architecture

An arm with a large model. If `must_mention` goes up and `no_repeated_ngram`
stays where it is, the part attributable to the architecture is smaller than what
we have been reporting — and the irreducible part is larger.

### d. Run the best known configuration, all together

It has never been done: **N=2**, `term_once` in the assembler, no exclusive
assignment, with the one-paragraph brief per fragment. Each piece was measured
separately and no run has them all.

### e. A symmetric gate

Something that flags a suspiciously **favorable** result as harshly as an invalid
one is flagged today.

---

## 5. The short answer to the question

**There is no bias in the instruments** — several of them correct in favor of the
architecture and are documented.

**There is a bias in the framing**, and it is this: for three weeks we evaluated
Swarmbly solely on the axis where fragmenting can only lose, on tasks that never
needed fragmenting. That was not a decision anyone made; it was one nobody made,
and I should have seen it before you did.

The foundation has not been refuted. **It has been left untested.**
