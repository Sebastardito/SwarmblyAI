---
status: current
lang: en
---
# The segmenter splits a question away from the data that answers it

**Found:** 4 September 2026, on the first instance the V7 oracle arm was pointed
at.
**Class:** an architectural limitation, not a bug. Nothing misbehaves relative
to its own docstring. What is wrong is a claim made on top of it.
**Status:** **repaired**, on the author's decision, as a fusion of two of the
three options in §6 — teach the segmenter the dependency where it is
recoverable, and refuse to fragment where it is not. §9 records what the
repair covers, what it refuses, and the one tension it cannot resolve.

---

## 1. What was measured

`benchmark_v7`'s `map` class is the most trivially partitionable task available:
four independent per-section totals, no cross-section dependency anywhere. One
instance, ρ = 3.0, N = 4, against a packing floor of **1.62** — so well above
the floor, and *not* the degenerate below-floor condition that invalidated three
v3c tiers.

The worker is a **compliant worker**: it answers the claims its packet names,
correctly, in the asked format, and answers nothing whose facts it was not
given. That removes "the model cannot do the task" by construction.

| arm | accuracy | coverage | unanswerable |
|---|---|---|---|
| monolithic | **1.000** | 1.000 | 0.000 |
| oracle | **1.000** | 1.000 | 0.000 |
| **real** | — | **0.000** | **1.000** |

The task is fine. The partition is fine. **Every claim in the real arm was
unanswerable**, and here is why — the four packets actually dispatched:

```
t0   all four QUESTIONS, and none of the data
       [c_s1] the total for Depot group 1  ... [c_s4] the total for Depot group 4
t1   the output-format directive, and section 1's rows
t2   sections 2 and 3's rows, and no question
t3   the tail of section 3, section 4's rows, and no question
```

`t0` owns every claim and holds zero facts. The three packets holding all the
data were asked nothing. And `s3` is split across `t2` and `t3`, so even a
packet that *had* been asked for `c_s3` could not have answered it.

## 2. The mechanism, exactly

`planner._segment` says what it does, and it does it:

> Enumerated prompts split on their own bullets; otherwise sentences are packed
> into `n_tasks` roughly equal-token groups.

Two steps, both verified:

1. `split_enumerated` returns `None` on this prompt. The item list is indented
   under a preamble and is not recognised as an enumerated batch.
2. The fallback is a **contiguous, token-balanced** partition over sentences.

So the decomposition is decided by **position and token count**. The segmenter
has **no representation of the dependency between a question and the material
that answers it**. A contiguous cut through a prompt that states its questions
first and its material second necessarily separates them.

## 3. Why six versions did not see it

Because of the corpus format, not because of the code.

Every corpus this project has run puts a question and its data **in the same
item**:

```
[01] 21 crates, 16 units per crate, 80 removed
```

A contiguous partition keeps them together — by accident of format. The
`tables24` corpus does the same, one row per line. `free_form` does the same.
The fact-graph shape is the first corpus where the questions are stated
separately from the material, and it is the first to cut between them.

**That accident is doing load-bearing work.** The architecture claims to
fragment a problem; what the implementation can fragment is a prompt whose
questions and data are co-located, item by item. That is a much narrower class,
and it excludes some of the most ordinary real shapes: a brief plus an appendix,
a set of questions plus a document, a request plus an attachment.

## 4. Why the oracle arm is the reason this was found in one look

Without it, `real` at zero coverage is indistinguishable from four other things:
a model that cannot add, a grader that cannot parse, a corpus whose key is
wrong, a packing floor violation. Each has cost this project days.

With it, the reading is one line, and the runner prints it:

> oracle 1.000 against real 0.000: the partition is viable and the
> implementation loses 100.0 points — planning, packing or assembly

`unanswerable_rate` then localises it further, and it is **the packer's number,
not the model's**: a claim whose packet did not hold the facts it requires could
not have been answered correctly by any model. The distinction is what
`Claim.requires` exists for, and it is the thing a flat answer key can never
express.

`benchmark_v7/__init__` predicted this, before the arm existed:

> **The oracle arm is the point.** Every packaging failure this project spent
> weeks on would have read as *oracle fine, real broken*, which localises the
> fault to planning, packing or assembly in a single reading.

It read exactly that, on the first instance.

## 5. Two smaller defects found on the way, both fixed

**`run_fragmented` did not keep its own output.** `run_monolithic` has always
carried `_text`; the fragmented arm did not. On a composition corpus `_trace`
carried the text, which hid the gap — and `_trace` exists only when the prompt
has constraints, so on every answer-key and fact-graph corpus **the fragmented
arm's output was unrecoverable from a completed row**. An independent scorer
would have seen one arm and not the other, and scored the fragmented arm as
having produced nothing. That is the shape of asymmetry this project has
withdrawn results for twice, in a place nobody was looking: not in the metric,
in what the row keeps. Fixed; `_text` stays out of `CSV_COLUMNS`.

**V7's instructions asked for ids its own evaluator could not parse.** The
instructions read *"Give one line per group as **[group id]** followed by the
value alone"*. The group ids in the material are `s1`, `s2` — `Section.as_text`
writes them. The claim ids are `c_s1`, `c_s2`. So a **perfectly compliant**
answer was `[s1] 440`, and `parse_claims` accepts `c_`-prefixed ids and bare
digits: `s1` is neither. Every arm would have scored zero coverage for a reason
with nothing to do with fragmentation.

It was invisible because the parser test fed it `c_`-prefixed ids by hand
instead of the shape the corpus asks for. The repair is `graph._asked`, which
names the ids in the instruction, plus a **round-trip over the real corpus** —
the same repair, for the same reason, as
`test_every_answer_in_the_corpus_round_trips_through_every_label_style` in the
harness's own suite. The claim namespace stays distinct from the section
namespace, so echoing `[s1] Depot group 1` from the material still parses as
nothing, and there is a control test that says so.

That fix has a second effect worth naming: because the packets now carry the
claim ids, a runner can attribute a claim to the packet that was **asked** for
it. Without that, the localisation above has nothing to attribute to.

## 6. What is not being claimed here

- **Not** that the planner is broken. It does what it documents.
- **Not** a figure about any model. Every number above comes from a compliant
  worker; the point of that worker is that it has no capability to measure.
- **Not** a result about real prompts. The fact-graph corpus is synthetic, and
  `benchmark_v7/__init__` states the limit before the first result: V7 can
  establish *the protocol does not lose information it was given*; it cannot
  establish *the protocol works on your documents*.
- **Not** fixed *at the time this was written*. Three repairs were visible from
  here and they are not equivalent — teach the segmenter that a question needs
  its material; require every packet to carry the questions and partition only
  the data; or restrict the router to prompts whose questions and data are
  co-located and say so. Choosing between them was an architecture decision and
  it belonged to the author. **It has since been made — a fusion of the first
  and third — and §9 records what was built.** This paragraph is left as it was
  written so that the decision reads as a decision and not as something the
  measurement implied.

## 7. Where it is pinned

`tests/test_benchmark_v7_runner.py`:

- `test_the_segmenter_splits_the_questions_away_from_their_data` — the
  behaviour, on the shape that produces it. It **pins** rather than approves; if
  it starts failing because the segmenter learned about the dependency, delete
  it.
- `test_the_real_arm_is_starved_and_the_oracle_arm_is_not` — the localisation,
  with an assertion that ρ is above the floor so the result cannot be
  re-explained as the below-floor condition.
- `test_the_assembled_text_is_recoverable_from_a_fragmented_row`
- `test_a_fact_graph_prompt_names_every_claim_it_asks_for`, and
  `test_a_section_header_is_not_read_as_an_answer` as its control.
- `test_the_runner_is_outside_the_package_and_stays_there` — the ADR-001
  boundary. The runner drives the shipped protocol and scores through the
  independent evaluator; it lives in `scripts/` because a runner inside
  `benchmark_v7/` cannot do the first without breaking the second, and the
  tempting repair — widening the import ban — would delete the ADR.

## 8. How to reproduce

```bash
python scripts/run_benchmark_v7.py --seeds 4 --backend mock     # wiring only
python -m pytest tests/test_benchmark_v7_runner.py -q           # the finding
```

The mock backend emits no parsable answers by design, so the wiring run reports
zero coverage in every arm and measures nothing. The compliant worker lives in
the test file, where a stand-in for model behaviour belongs.

---

## 9. The repair, and exactly what it does not cover

Decided by the author on 4 September: a **fusion of options 1 and 3**, so that
scope is narrowed only where the dependency is genuinely unrecoverable rather
than everywhere.

### The rule

`planner.reference_map` links each **ask** to the **material** it names.

* A labelled line is an *ask* when it carries at most
  `MAX_VALUES_IN_AN_ASK` numeric values, and *material* otherwise. A unit is a
  labelled line plus the unlabelled lines under it, so a section header is
  counted together with its rows — which is what lets one be told from the
  other at all: a header alone carries one value, a header with four rows
  carries five.
* An ask **refers** to a material unit when it shares a token that appears in
  **exactly one** material unit. Uniqueness, not length.

The first formulation required two consecutive shared content words, on the
reasoning that one shared word is noise. It was the wrong axis, and measuring
it said so twice: `depot group` matched all four sections, making every
referent set identical and the partition unbuildable; and nothing at all
matched in the `chain` class, whose questions name a single proper noun
(*"the running total after adding Mombasa"*). A token in exactly one unit is
that unit's name, whether it is `mombasa` or `4`. One mechanism, no thresholds
to tune.

### What it covers

| class | before | after |
|---|---|---|
| `map` | 4 questions in one packet, data in the other three; **1.000 unanswerable** | one question per packet with exactly the section it names; **0.000 unanswerable, accuracy = oracle** |
| `reduce` | same defect | **refused** — every claim needs every fact |
| `chain` | same defect | **refused** — several steps need the same section |
| `compose` | same defect | **refused** — one claim is an aggregate |

### What it refuses, and why refusing is the answer

`plan` returns a **single task** when the shape is present and the link is not
recoverable. Two cases:

1. **No ask names anything.** An aggregate question — *"the total across every
   group"* — needs all the material and names none of it.
2. **Two asks name the same material.** They cannot both hold it without that
   material being emitted twice, and duplicating a unit inflates
   `sum(|task_i|)` above `|P|` and raises the reachable ρ floor. `_segment` has
   always refused to duplicate, for that reason.

A *partial* map is not used. A partition that kept three questions with their
data and stranded the fourth would produce a figure with one silently
unanswerable claim in it, which is worse than no figure.

### The tension it cannot resolve, stated plainly

**The oracle partition duplicates.** `_oracle_partition` hands each claim
exactly the facts it requires, and those sets overlap freely. So the partition
that is viable *in principle* is a **covering**, not a partition — and ρ,
defined as `sum(|K_i|)/|P|`, charges for every duplicated token.

The architecture's low-ρ pitch and its own oracle are therefore in direct
tension, and no segmenter can resolve it. Allowing duplication buys the
`chain`, `reduce` and `compose` classes at the cost of a ρ floor that rises
with the overlap; forbidding it means those classes are not fragmentable. That
is the same architecture decision, one level down, and it is now the open item
in `STATE_2026-09-04.md` §7 rather than this one.

### A refused row is not a fragmented measurement

This is the half most likely to be got wrong, and it is the direction that
matters. A refused plan holds the whole prompt in one packet, so the row
labelled `fragmented` scores whatever the monolithic arm scores — 1.000 with a
compliant worker. Left in a cross-arm figure it reads as *fragmentation is
cheap*, on a prompt that was never fragmented. That is the wrong direction, and
it is the direction all twelve instrument defects in `REVISION_2026-08-12.md`
leaned.

Three guards, deliberately at three different levels:

* `row["plan_refused"]`, dropped by **`is_reachable`** — the same chokepoint as
  a below-floor row, extended rather than duplicated, because `rho_reachable`
  was once written to every row and read by one function out of eight.
* the ρ-drift invariant is **skipped** on a refused row. One packet has ρ near
  1 whatever the target says, so the check would turn a deliberate refusal into
  a crash and an operator would read the traceback as a harness fault.
* the V7 runner files it under **`real-refused`**, a separate arm name. A mean
  over one label mixing fragmented and unfragmented cells is the shape of every
  pooling defect this project has corrected — ρ pooled over N, N pooled over k,
  a rate without its denominator.

### The measurement that says the repair is safe

**456 partitions, six corpora, N ∈ {2, 3, 4, 8}: zero moved.** Zero existing
plans collapsed, and the question/material path fires on **0 of 150** existing
prompts — which is also the answer to why six versions never saw the defect.

That is the property that matters more than the repair itself. Every published
figure in this project was measured on a partition; a segmenter change that
re-partitioned an existing prompt would have silently changed what those
figures were about, and a gate that refused one would have emptied a cell that
used to be full. Neither shows up as an error.

`test_no_existing_corpus_partition_moves` compares all six corpora prompt by
prompt and N by N, asserts every prompt is still recoverable, and asserts the
segment count — so silently shrinking the comparison is not the easy way to
make it pass. `test_the_reference_path_fires_on_no_existing_corpus_prompt`
fails the moment a new corpus arrives in this shape, which is when the operator
needs to know: before a night is spent on it.

Both halves of the repair were verified to fail against reverted code —
removing the reference path breaks the `map` tests, removing the gate breaks
the refusal tests.
