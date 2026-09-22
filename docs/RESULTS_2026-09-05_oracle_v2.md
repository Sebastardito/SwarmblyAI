---
status: current
lang: en
---
# comp-oracle, five arms — 5 September 2026

`results/comp-oracle-20260905-112603`, corpus digest `e9e382b9…`, twelve dev
prompts.

**The first check passed:** all three oracles wrote **2.00 paragraphs**, against
monolithic's 2.00 and the shipped pipeline's **8.92**. The briefs were obeyed,
so the run is readable.

---

## The answer: parallelism, by a factor of seventy

| arm | constraint score (comparable) | paragraphs |
|---|---|---|
| monolithic | **0.844** | 2.00 |
| oracle-exclusive | 0.571 | 2.00 |
| oracle-redundant | 0.586 | 2.00 |
| **oracle-redundant-dedup** | **0.652** | 2.00 |
| real (shipped) | 0.649 | 8.92 |

Only `oracle-redundant-dedup` is an **upper bound** on what allocation can
achieve — the other two score below the shipped pipeline, so they measured their
own briefs rather than allocation. Its decomposition:

| | |
|---|---|
| end-to-end loss | **0.194** |
| parallelism (monolithic → oracle) | **0.192** |
| allocation (oracle → real) | **0.003** |
| **share recoverable by allocation** | **1.4 %** |

**98.6 % of the composition cost is not reachable by any planning change.** A
perfect allocator, plus mechanical enforcement of the one constraint class that
can be mechanised, lands at 0.652 against monolithic's 0.844 — still 19.2 points
short, and level with the shipped pipeline it was meant to improve on.

This is the answer `comp-final` was published without, and it is the unflattering
one. The 22.4 points are **not** a planner defect.

### A rule I changed after seeing the data, and the audit of that

The headline used to be pinned to the policy **declared first** — exclusive —
which on this run produced "check the oracle's briefs" while a clean
decomposition sat two lines below it.

The rule is now stated on the **instrument**: an oracle is an upper bound, so one
scoring below the shipped pipeline has not measured allocation. The headline is
the declared-first policy **among those that pass** that check. Choosing among
valid instruments by declaration order is not choosing a result; choosing among
all of them by score would be.

A rule revised after seeing data has to be audited for which direction it moves.
This one moved the headline from *"the oracle is broken"* to *"PARALLELISM
dominates — this workload is not fragmentable"* — **away** from the project's own
hypothesis, not toward it.

---

## Where the residual lives

Monolithic minus the headline oracle, in checks rather than points:

| class | monolithic | dedup oracle | lost |
|---|---|---|---|
| `must_mention` | 32/36 | 23/36 | **−9** |
| `no_repeated_ngram` | 11/12 | 4/12 | **−7** |
| `no_repeated_sentence` | 12/12 | 10/12 | −2 |
| `words_per_paragraph` | 12/12 | 10/12 | −2 *(assembler-enforced)* |
| `must_not_mention` | 12/12 | 12/12 | 0 |
| `paragraph_count` | 12/12 | 12/12 | 0 *(assembler-enforced)* |
| **`term_once`** | 13/24 | **14/24** | **+1** |

Two classes carry it.

**`no_repeated_ngram`, −7 of 12.** Irreducible. A repeated 8-gram is a property
of a *pair* of fragments; no parallel worker can check a pair; every arm that
does not see the other's text lands at 4–5 of 12 while monolithic sits at 11.
This is the price of parallelism with a name on it.

**`must_mention`, −9 of 36.** This one is *not* about allocation, and that is the
surprise. Telling **every** fragment to mention **every** term still lands only
25/36 (23 after dedup's deletions) against monolithic's 32/36. A fragment writing
60–140 words about one paragraph's worth of a topic has less room to work three
or four required terms in than a writer with the whole 120–280 words. It is a
**fragment-size** effect.

Which lands exactly where `v0` landed from a completely different instrument:
the tax is a function of N, N=2 and N=4 are indistinguishable, and N=8 is
different in kind. Fewer, larger fragments. Two instruments, one conclusion.

---

## The one thing that worked, and it worked better than the ceiling

| arm | `term_once` |
|---|---|
| monolithic | 13/24 |
| shipped pipeline | 6/24 |
| oracle, redundant briefs | 6/24 |
| **oracle, redundant + mechanical dedup** | **14/24** |

Moving "exactly once" off the generation side and onto the assembler took it
from 6/24 to 14/24 — **above the unfragmented arm**. It cost two `must_mention`
and two `words_per_paragraph`, both from deleted sentences that carried
something else. Eight gained, four lost, two of the four excluded from the
headline anyway.

It is the same shape of constraint as `paragraph_count` and
`words_per_paragraph`, which the assembler has always enforced this way: a
property of the finished text, checkable by counting. Only history put it on the
generation side.

**This is a shipping recommendation**, and it now exists as one:
`--enforce-term-once`, default **off**, with `swarmbly_v0.constraints.
enforce_term_once` as the single implementation the oracle and the assembler
both call — asserted by a test, because two implementations of one behaviour
drift and the drift gets attributed to whichever arm notices second.

The prediction is preregistered in `docs/PREREGISTRATION_term_once.md` and the
tier is `comp-dev-once`.

---

## Two things worth keeping that are not the headline

**The shipped pipeline's redundancy is load-bearing, and it beats both oracles
on `must_mention`.** 21/24 on the also-once bucket, against the redundant
oracle's 17/24 and the exclusive oracle's 11/24. Every fragment sees the whole
prompt, so several mention the term. Anyone "fixing" the planner to allocate
terms properly would have made things worse — there is now a number for it, in
both directions.

**Half of `comp-final`'s stated limit is removed.** The 7.96 paragraphs are a
**brief defect**: telling a fragment "write paragraph 1 of 2 and nothing else"
produces exactly 2.00, in all three oracle arms, on all twelve prompts. That is
fixable in the shipped planner and is worth doing regardless of the rest —
though note it is worth *fewer points than it looks*, since `paragraph_count`
and `words_per_paragraph` are excluded from the comparable score precisely
because the assembler already handles them.

---

## What this changes

* **The composition cost is a fact about parallel prose, not about this
  planner.** 98.6 % of it survives a perfect allocation. Stop looking for it in
  the planner.
* **`term_once` belongs to the assembler.** Measured at 14/24 against 6/24,
  above the unfragmented ceiling, and now preregistered.
* **The lever, if there is one, is fragment size.** Both surviving classes get
  worse as fragments get smaller, and `v0` says the same thing from the other
  end. N=2 and N=4 are indistinguishable; N=8 is where the cost appears.
* **The planner should keep its accidental redundancy.**

## Honest limits

Twelve dev prompts, no interval, no verdict — this decomposes a number that has
its own interval, it does not carry one. The dedup arm at 0.652 against real's
0.649 is a 0.3-point difference on twelve prompts and means nothing on its own;
what means something is the **class-level** table underneath it, where the
mechanisms have denominators.

And the whole thing is measured with 3B models. A larger model that followed
"mention this term" reliably would move `must_mention` and leave
`no_repeated_ngram` exactly where it is — which would make the parallelism share
*larger*, not smaller.

## Next

```bash
bash scripts/run_ollama.sh comp-dev-once     # ~1 h, preregistered
```
