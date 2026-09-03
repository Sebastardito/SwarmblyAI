# ADR-001: The instrument must not import the thing it measures

**Status:** Accepted
**Date:** 12 August 2026
**Scope:** `swarmbly_v0/` (the harness) and `benchmark_v7/` (the benchmark)

## Context

This project measures whether splitting a prompt across several small models
degrades the answer. Its output is not a running system — it is a number, and
that number is published. So the failure that matters here is not a crash. It is
a figure that is wrong in a direction nobody checked.

That has now happened repeatedly, and the pattern is consistent enough to be
treated as a property of the design rather than a run of bad luck:

| | What went wrong | How it was found |
|---|---|---|
| Coherence metric | Not arm-neutral: expected entities grew with N, omissions attributed round-robin across fragment heads, seam-local classes could only fire where seams existed. The same text scored 0.9375 monolithic and 0.5000 at N=8. | Only after four documents had quoted it |
| ρ axis | 13 of 96 cells were above their own packing floor; the two rows anchoring the published descent had none | Only after the curve was the headline |
| Item grader | A decimal point read as an item label; a correct answer left the accuracy denominator and landed in `items_echoed` | Adversarial review, 526 tests later |
| Carry regex | The same defect in the sibling regex, but this one *writes* — a phantom `[42]=5` entered the successor's packet | Verifying the item-grader fix |
| Four token checks | A sentence-final full stop made a token invisible; `term_once`, `no_repeated_ngram`, `any_of`, `boolean` all affected | Generalising one fix |
| Scope filter | Records filtered, report totals not; both printed side by side | Adversarial review |
| Assembler asymmetry | `paragraph_count` satisfied by the formatter in one arm and by the model in the other | Adversarial review |
| Runner gates | `\| tee … \|\| true` on every tier discarded every `PacketInvariantError` and reported an aborted run as complete | Pipeline audit |

Two things are common to all of them. First, **the defect was in the
instrument, never in the protocol** — the architecture under test has not yet
been contradicted by evidence; only the measurement of it has. Second, **each
defect was one-sided in the direction of the project's own hypothesis.** That is
the part that cannot be dismissed as noise. A symmetric error inflates variance;
these inflated the answer the project wanted.

The question this ADR settles is where the instrument's boundary should be, now
that `benchmark_v7/` is being built and could reuse the harness's scoring.

## Decision

**`benchmark_v7/` imports nothing from `swarmbly_v0/`, and the ban is asserted
by a test that parses the import graph rather than by convention.**

Concretely:

1. `benchmark_v7.evaluate` has no dependency on `swarmbly_v0.metrics`,
   `swarmbly_v0.grading`, or `swarmbly_v0.constraints`. It has its own parser,
   its own tolerance, its own verdict type.
2. The benchmark's *first* test is the invariant that broke in the harness — the
   same answer scores the same however the prompt was cut — asserted before the
   evaluator is used for anything.
3. The benchmark separates three questions the harness's flat answer key
   conflated: `correct` (did it match), `answerable` (did the packet hold every
   fact the claim requires), and `owed_by` (which packet should have carried a
   missing fact). "Wrong" and "unanswerable" have different owners — the model
   and the packer — and six runs were spent on questions where they were
   indistinguishable.

## Options considered

### Option A — Reuse the harness's scorer in the benchmark

| Dimension | Assessment |
|---|---|
| Complexity | Lowest. Nothing new to write. |
| Comparability | Highest — benchmark and harness figures are on one scale |
| Failure mode | **A defect in the scorer invalidates both at once** |
| Team familiarity | Highest |

**Pros:** one scorer, one set of tests, figures directly comparable across V0–V6
and V7.

**Cons:** it makes the two measurements *dependent*. The arm-neutrality defect
would have propagated silently into V7, and V7 would have "confirmed" V0 —
which is the worst possible outcome, because agreement between a measurement and
its own instrument reads as replication.

### Option B — Independent evaluator, enforced (chosen)

| Dimension | Assessment |
|---|---|
| Complexity | Moderate. A second parser and scorer, ~200 lines. |
| Comparability | Reduced — V7 figures are not on V0's scale |
| Failure mode | A defect in one instrument leaves the other standing |
| Team familiarity | Lower; two conventions to hold in mind |

**Pros:** V7 can *disagree* with the harness, and a disagreement is
informative rather than a bug. The AST test makes the boundary a fact about the
code rather than an intention.

**Cons:** real cost. Two parsers means two places a parser bug can live, and the
project has already had four parser bugs. Mitigated by keeping the benchmark's
parser deliberately stricter and much smaller — it accepts only bracketed claim
ids, where the harness's grader had to tolerate whatever a small model emitted.

### Option C — Shared scorer behind an arm-neutrality contract test

| Dimension | Assessment |
|---|---|
| Complexity | Moderate |
| Comparability | Highest |
| Failure mode | Only the faults the contract test anticipates are caught |
| Team familiarity | High |

This is the option that looks best on paper and is rejected on evidence. A
contract test catches the fault class it was written for. `test_instrument.py`
already had exactly one arm-neutrality test, for one metric — it caught its
defect and was never generalised, and seven more defects of that shape went
through the gap. A contract is only as good as the imagination of whoever wrote
it, and the entire history above is a record of that imagination falling short.

## Trade-off analysis

The decision trades **comparability for independence**, and that is the right
trade only because of what this project's numbers are for. If the goal were
tracking a metric over time, one scorer would be correct: a consistent
instrument beats an accurate one for trend detection. But the goal is a
falsifiable claim with a pre-registered abandonment threshold, and there the
question is whether the measurement is *true*, not whether it is consistent with
last month's.

Independence buys one specific thing: when V7 and the harness disagree, at least
one of them is wrong, and the project finds out. Under Option A they cannot
disagree.

The cost is honest and should not be minimised. V7's figures will not be
plottable against V0's, and a reader will want that plot. The answer is that
V0's figures are withdrawn anyway, so there is less continuity to preserve than
it appears.

## Consequences

**Easier**

- A defect in one instrument no longer invalidates every result at once.
- The packer can be blamed. `answerable` and `owed_by` mean a bad figure can be
  attributed to the planner, the packer or the model, instead of being reported
  as "quality lost".
- The oracle arm becomes meaningful: fragmented packets with perfect context
  separate *the task is too hard for a 3B model* from *the packer starved it*.

**Harder**

- Two parsers, two tolerances, two conventions. Every future scoring change has
  to be considered twice, and the temptation to unify them will recur.
- Cross-version narrative. Any document comparing V7 to earlier runs has to say
  explicitly that the instruments differ.
- The AST test is load-bearing and looks trivial. It needs a comment explaining
  why deleting it is not a cleanup.

**To revisit**

- If V7 and the harness are ever shown to agree across a wide grid on the same
  corpus, the case for two instruments weakens and Option C becomes defensible.
  That agreement has to be *measured*, not assumed.
- The benchmark corpus is synthetic — a fact graph, not prose. That bounds what
  V7 can conclude, and it is stated in `benchmark_v7/__init__.py` rather than
  discovered later.

## Action items

1. [x] `benchmark_v7.evaluate` written with no harness imports
2. [x] Arm-neutrality asserted as the benchmark's first test
3. [x] `correct` / `answerable` / `owed_by` separated in `ClaimVerdict`
4. [x] AST test that fails if `benchmark_v7/` ever imports the harness's
       scoring — `tests/test_benchmark_v7.py`, verified to fail against a
       deliberate violation rather than assumed to work
5. [ ] Instance generation with a frozen dev/final split and `--verify`
6. [ ] `benchmark_v7/run.py`: Map and Chain first, oracle arm included from the
       start rather than added once a result looks wrong
