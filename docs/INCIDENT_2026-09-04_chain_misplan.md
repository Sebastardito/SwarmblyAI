# Incident — every enumerated prompt was planned as a dependency chain

**Found:** 4 September 2026, diagnosing why a single fragmented worker produced a
parsable answer for one item in six while the monolithic arm produced 150 of 150.
**Severity:** two published results withdrawn, one partially. The 16-hour `v4`
tier was correctly held back on this suspicion and must stay held until a re-run.
**Class:** arm asymmetry in the **stimulus**. Every previous defect in this
project was in the instrument. This one changed what the models were asked.

---

## What happened

`swarmbly_v0/router.py:58` lists `\bthen\b` among `_SEQUENTIAL_CUES`. Every
prompt in `prompts/ground_truth.json`, and every enumerated prompt in
`free_form.json`, ends with an output-format directive reading:

> Give one line per item. Begin the line with the item number in square brackets,
> exactly as given, **then** a single space, **then** the value. […] **Items are
> independent: the answer to one must not depend on the answer to any other, and
> you must not reconcile them against each other.**

The two `then`s are typography. They are in the same sentence as the statement
that the items are independent. One cue clears the gate — `_saturate(1, 1.5) =
0.487 ≥ 0.45` — so **all 15 ground-truth prompts were planned as four-deep
chains**.

The consequence is not subtle. At ρ = 2.5, N = 4, **42 of 60 fragment packets
carried a `[PREDECESSOR SUMMARIES]` block holding another packet's answer
lines** — `- t0: [01] 576` — sitting directly above a task block that reads
*"Answer only the items listed here."* The monolithic prompt carried none.

A worker shown another packet's answers restates them. `task_item_scope`
correctly discards the restatements as out of scope, so the item is neither
answered nor recoverable — which is exactly the 16 % seen at k = 1, and why it
recovers with k: consensus merges replicas and only some families restate.

`carry_block`'s own docstring already named the consequence: *"the successor
restates them as its own, and an enumerated corpus reported 379 graded items
against a key holding 150."* The mechanism was documented. The trigger was not.

A second, independent defect made it unconditional: `swarmbly_v0/packing.py:196`
placed the *optional* predecessor block with no gate, while the *mandatory* path
(`carry_block`) is gated on `consumes_predecessor` precisely to prevent this.
Above the packing floor there is always slack, so the block went in anyway —
which is why this surfaced in the first run ever conducted above the floor.

## Why it was not caught

The router's decomposability evaluation is published and was not wrong: it reads
a feature vector over the whole prompt, and "then" is a real sequential cue in
prose. The error was using the *whole prompt* — including the block that
describes the output format — to decide the **dependency topology**. A format
directive is not a statement about data dependencies, and no test asserted that.

## The fix

- `planner.ordering_text()` — the dependency decision now reads the preamble and
  items of an enumerated batch, never its output-format block. `plan()` uses it.
  The router's own feature vector is untouched, so its published evaluation is
  unaffected.
- `packing.answers_by_item_label()` — a packet whose task block names its own
  items as `[NN]` receives no predecessor summary as *optional* context. Prose
  fragments are untouched; genuine chains still get their mandatory carry.

**Scope of the change**, measured rather than assumed:

| corpus | prompts planned as chains, before → after |
|---|---|
| `ground_truth.json` | **15/15 → 0/15** |
| `free_form.json` (enumerated half) | **6/11 → 0/11** |
| `tables24.json` | 0/24 → 0/24 |
| `prompts.json` | 4/8 → 4/8 |
| `complex.json` | 5/20 → 5/20 — every `chain_*` still a chain |

Five regression tests, each verified to fail against the pre-fix code with each
fix reverted in isolation and both together.

## What is withdrawn

**`RESULTS_V3C_GT_CORRECTED.md` — entirely, in both directions.** Not only the
arm comparisons. At k > 1 every replica of one task receives the *same* packet,
so a shared predecessor block gives them something to converge on: mean agreement
0.966 may be inflated by the defect. If it is, then "the predictor has no
variance, AUC 0.525, the map is retired" rests on variance that was artificially
suppressed. **The conclusion is not safe in either direction**, including §2's
mechanism claim about five families agreeing and being wrong 29 % of the time.

**`RESULTS_V3C_FF_COMPOSITION.md` — §5 only.** Six of the eight prompts feeding
the agreement calibration are the affected enumerated ones. AUC 0.602, lift 2.15,
p = 0.0026 and the clustered interval are all withdrawn. **§1–4 stand**: the three
`comp_*` prompts match no sequential cue before or after the fix, so the
14-to-21-point constraint gap, the coherence tax reading zero on the same texts,
and the duplication-and-omission mechanism are unaffected.

**Not affected:** `tables-final` and `tables-dev`. `tables24.json` plans 0 chains
before and after, so the declared cell — +2.30 %, CI [−2.05 %, +7.49 %], NOT MET
— stands.

## What this costs and what it is worth

Two nights of compute, and the first non-null result in six measurements of the
confidence map. That one was the most tempting result of the session and the one
most worth doubting; this is why.

Against that: the composition finding survives, and it is the larger result. And
the defect is the first this project has found in the **stimulus** rather than
the instrument — a category nothing in the harness was watching. The gates added
this week (`publishable`, `run_tier`'s post-condition, the k-vs-families check)
all watch the measurement. None of them could have seen this.

**What would have caught it:** an assertion that the two arms are dispatched the
same question. There is now one — `test_no_answer_sheet_fragment_is_handed_another_packets_answers`
— and it is the property, not the instance.
