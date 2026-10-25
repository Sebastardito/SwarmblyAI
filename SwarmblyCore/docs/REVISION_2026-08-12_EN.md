---
status: current
lang: en
---
# Full project review — 12 August 2026

Audit of foundations, code, architecture, documentation and scripts, ahead of
the full run. **Twelve defects found, all of them in the instrument and none in
the protocol.** Eleven are fixed with regression tests; one stays open and is
documented below.

This is the document to read before running. The operational conclusion is in
§7.

---

## 1. The finding that shapes everything else

The twelve defects share two properties, and neither one is chance.

**First: the failure was always in the instrument, never in the architecture.**
Across six runs, Swarmbly's proposal has not been contradicted by the evidence
yet. What has been contradicted is the measurement of that proposal. That is
good news and a warning at the same time: it means the project does not yet know
whether its hypothesis is true, and that it has believed it knew four times.

**Second, and this one is the serious one: every defect pushed in the direction
of the project's own hypothesis.** A symmetric error inflates the variance and
shows up as noise. These inflated the answer the project wanted.

| Defect | Bias | Direction |
|---|---|---|
| Coherence metric not neutral between arms | +46.7% on identical text | against the fragmented arm → in favour of "there is a tax" |
| ρ axis below the packing floor | 83 of 96 cells | manufactures the "more context, less loss" descent |
| Scope filter applied to records and not to totals | one-sided, grows with N | inflates the precision of the typed-carry arm |
| `paragraph_count` imposed by the assembler | 2 of 7 checks | guaranteed pass for one arm, near-certain failure for the other |
| `_CARRY_RE` reads a decimal point as a label | only in the typed-carry arm | injects a phantom value that the successor repeats "correctly" |
| `no_repeated_ngram` blind to end of sentence | one-sided under-detection | hides the repetition between fragments, which is *the* failure of assembly |

That pattern — an error in the instrument, always in favour — is exactly the
shape confirmation bias takes when the one who measures and the one who proposes
are the same person. It is not an accusation: it is the reason ADR-001 exists
and the reason the new `benchmark_v7` cannot import the harness's scorer.

## 2. The twelve defects

### Fixed with a regression test

**Class A — representation invariance** (`tests/test_invariance.py`)

`normalise_text` keeps the `.` on purpose, because otherwise `42.5` folds into
`425` and numeric grading breaks. But the checks built on top of it compare
space-separated tokens, and a word at the end of a sentence carries the period
with it: `window.` is never equal to `window`. That broke four distinct checks.

1. **`term_once`** counted one occurrence where there were two if the first one
   closed a sentence, and suspended a correct single mention that closed a
   sentence. Bidirectional error: it does not cancel.
2. **`no_repeated_ngram`** did not see a repeated phrase whose first occurrence
   closed a sentence. The same 6-gram gave `observed=0` with the period and
   `observed=2` without it.
3. **`any_of`** scored "251 kg is under." wrong and "251 kg is under the limit"
   right — the same statement.
4. **`boolean`** returned `None` for "the consignment was cleared: no.", and a
   `None` does not score wrong: it takes the answer out of the precision
   denominator and puts it into `items_unintelligible`.

`_as_number` already trimmed the trailing period, which is the tell: the failure
class was known and had been fixed in one site out of five. Now there is a
single site, `grading.content_tokens`, and all five go through it.

**Class B — the label grammar depends on the content of the answer**

5. **`ITEM_LABEL_RE`** read a decimal point as a label terminator: `[05] 42500 m
   is 42.5 km` was interpreted as item 05 plus a phantom item 42. The correct
   answer, 42.5, left the denominator and landed in `items_echoed` — the
   statistic that was used to argue that fragmented workers repeat their input
   instead of answering it.
6. **`planner._CARRY_RE`**, the sibling regex, had the identical defect, and
   there it is worse, because `carry_values` **writes**: a phantom `[42]=5`
   enters the successor's packet as if a predecessor had produced it. Verified:
   `carry_values("42.5 km is the distance travelled")` returned `{'42': '5'}`.

**Class C — conservation**

7. **`_truth_records`** filtered the records by scope and summed the report
   counters *unfiltered*, and published the two together. A real case:
   `items_graded: 6, accuracy: 0.833` next to four records with a precision of
   1.000.

**Class D — neutrality between arms**

8. **`_composition_summary`**: `paragraph_count` and `words_per_paragraph` are
   satisfied by the *assembler* in the fragmented arm (`select_then_splice`
   receives `paragraph_join` and emits exactly that number of paragraphs) and by
   the model only in the baseline (`run_monolithic` is a bare generation). The
   same joined text scored 1.000 and 0.750.

**Class E — the gates were all warnings**

9. **`run_ollama.sh` ended every tier with `| tee "$out/run.log" || true`.**
   `set -o pipefail` is on and the Python layer raises `PacketInvariantError`
   when a packet loses its contract header, when a dependent task loses its
   carry, or when the achieved ρ fails its target — the three gates that exist
   to stop an invalid run from reaching a table. `|| true` discarded all of
   them, the tier printed `-> report.html` and `== Done ==`, and `all` moved on
   to the next one. **An aborted run was reported to the operator as
   completed.**
10. **The k-vs-families check that the script's header has promised since it was
    written did not exist.** That is the contamination that ruined the k=5 arm
    of 24 August: three families loaded, k swept up to 5,
    `select_diverse_nodes` silently repeating two of them, and the mean
    agreement moving 0.705 → 0.700 from k=3 to k=5, which is the signature of
    adding echoes instead of independent estimators.
11. **`rho_reachable` was written on every row and exactly ONE function in the
    whole analysis read it** — `fragment_size_curve`, which used it to pick a
    cut and then *fell back* to the full set when there was no reachable cut.
    `summarize`, `falsifiable_go_no_go`, `paired_absolute_effect`, `go_no_go`
    and all of `report.py` ignored it. The flag was not missing: nothing
    consulted it.
12. **On the Ollama path the seed never reached the sampler.** The shim reads
    its settings from `options`, which carried only `num_predict`, while
    `metadata["seed"]` recorded it as if it had controlled generation.
    `--candidates 2` at k=1 dispatches variant 0 and variant 1, which at
    temperature 0.0 differ **only** by the seed — so the two candidates were
    plausibly the same draw and the candidate axis measured nothing.

### Open

**The `rho` target of <2.0 in SPEC §11.5 is not reachable on any corpus.** The
packing floor at N=2 is 1.20 in `tables24` and 1.42–1.68 in the V0 corpus. A
target of 2.0 leaves almost no context above the mandatory task and its header.
It is marked *not derivable* in the metrics table instead of asserted; it has to
be recomputed from the floor, and that is a design decision, not a mechanical
fix.

## 3. Why 526 tests did not catch them

None of the 526 tests related **two** evaluations of the instrument to each
other. All of them were single-shot: one input against a literal, or one broken
mechanism against a metric.

Fault injection (`test_instrument.py`, 14 faults with their clean control) tests
**sensitivity** — the metric moves when the mechanism breaks. It cannot test
**specificity** — that it moves *only* then. And defects 2, 4, 8 and 12 are
movements with no broken mechanism at all.

What is notable is that the harness already had **exactly one** test of the
right shape — `test_identical_text_scores_identically_however_it_was_partitioned`
— for one metric. It caught its defect and was never generalised. Seven more
defects of that shape went through the gap.

`tests/test_invariance.py` (31 tests) now asserts the four *classes* of property
instead of the twelve instances, over the real corpus of 150 items in four label
styles — 600 round trips, 20 of them with decimals — so that a fifth call site
cannot silently reintroduce any of them.

## 4. Architecture: ADR-001

Decision: **`benchmark_v7` imports nothing from the harness's scorer, and the
boundary is checked against the import graph, not against a docstring.**

The alternative that looks best on paper — a shared scorer behind a neutrality
contract test — is rejected *on evidence*: a contract test catches the failure
class it was written for, and the history in §3 is precisely the record of that
imagination falling short.

The trade-off is **comparability for independence**. V7's figures will not be
plottable against V0's, and a reader will want that plot. But the point of
independence is that V7 can **disagree** with the harness; with a shared scorer
it cannot, and the neutrality defect would have propagated into V7, which would
then have "confirmed" V0 — the worst outcome available, because agreement
between a measurement and its own instrument reads as replication.

Full detail, with the three options and their consequences, in
[`ADR-001_instrument_boundary.md`](ADR-001_instrument_boundary.md).

## 5. What was withdrawn from the documentation

Two results, in every document in both languages, including the Zenodo deposit
description, the arXiv abstract and the two HTML explainers.

**The coherence tax falling 24.1% → 13.7% with ρ.** Withdrawn for two
independent reasons. The ρ axis never moved: recomputed from the code, the floor
of the V0 corpus is 1.42–1.68 at N=2, 1.85–2.35 at N=4 and 2.70–3.71 at N=8,
against a sweep from 1.00 to 2.00, so **13 of 96 cells** were at or above their
floor and the two rows that anchor the descent — ρ=1.00 and ρ=1.25 — **contained
none of them**: 48 cells, zero measurements of ρ. The overshoot was printed in
the published table the whole time — achieved ρ 1.17 against a target of 1.00 —
and it was read as tolerance instead of as a packet that does not fit. And the
metric was not neutral between arms.

**The confidence map.** This is not a correction but a change of verdict. It
stood at "unproven, not disproven", which was fair against a judge that accepted
93.3% of everything. The answer-key experiment that section pointed to has been
run three times and has returned Mantel-Haenszel common odds ratios of **3.47,
then 0.26, then 1.24** — above, below and straddling 1 on the same question.
That is not weak signal; it is no signal, measured three times.

The withdrawn tables are kept in place, unaltered, under a banner. A withdrawn
result that has been deleted cannot be checked.

**What replaces both:** `table_summary` at ρ=3.5, N=2, k=1 over 16 held-out
prompts — **+2.30%, 95% CI [−2.05%, +7.49%], criterion NOT MET**, short by 2.49
points at the upper bound, with the control at N=8, k=1 failing as it was
required to (**+16.23%**, CI [+11.33%, +20.28%]).

> These figures are the ones from the 3 September 2026 re-run on the corrected
> instrument (`docs/RESULTS_TABLES_FINAL_CORRECTED.md`). The 27 August run, made
> on the defective instrument, gave +3.26% with CI [−0.02%, +6.93%] and a
> control at +17.6%; it is superseded and is kept only as history in
> `docs/RESULTS_TABLES_FINAL.md`. The verdict did not change.

## 6. Discussion: what this result means

**The criterion was not met, and it is not going to be rewritten.** The point
estimate passes 5%; the interval does not. The criterion was written against the
interval precisely so that a favourable estimate could not carry it on its own,
and changing the estimator after it returned an uncomfortable answer is the way
a project convinces itself.

**But the interesting result is not the average, it is the shape.** The median
prompt loses nothing at all — **exactly 0.00%** — and **11 of 16 prompts land at
zero or below** (6 negative, 5 exactly zero). The mean is manufactured by two
prompts: `tbl24_outturn` (+28.50%) and `tbl24_bonded` (+23.08%) are between them
140% of it, and without them the remaining fourteen average −1.06%.
"Fragmenting costs 2.3%" is a poor reading of that. The correct reading is: *in
11 of 16 table-summary prompts, splitting the work in two was free, and in two
of them it was expensive.*

Identifying that split is a better question than the one the criterion asks. A
threshold criterion asks "is the cost acceptable on average?", which for a
routing protocol is the wrong question — the router does not have to accept the
average, it has to **decide per request**. A bimodal cost with an identifiable
boundary is more valuable for design than a low and uniform cost, because it is
routable. V1's decomposability classifier goes from being an optimisation to
being the mechanism the rest depends on.

**What has to be resisted:** presenting the bimodality as if it rescued the
criterion. It does not. The criterion was declared publicly before there was
data and came out NOT MET; that is what the documentation says now, on its first
line, and the bimodality is an *additional* finding, not a way out.

**On the confidence map.** It was the contribution the project was proudest of,
and it is withdrawn on its own evidence, measured four times. The mechanism
still works: there is still a degree of agreement per unit, and a provider with
a single model has nothing to align. What cannot be asserted is that that
agreement predicts quality. Keeping it as a declared mechanism and not as a
reliability signal is the honest position.

## 7. Status and operational recommendation

**Ready:** 559 tests pass, 9 skip. Eleven of twelve defects fixed with
regression. The runner's gates are blocking now. Rows below the floor are
discarded from every published figure, through a single control point
(`experiment.publishable`). The public documentation says what the evidence
supports, in both languages.

**Before running, a real warning.** The changes of this day are substantial and
**none of them has been exercised against real models yet**. In particular:

- The runner now **aborts** where it used to continue. A tier that used to
  "finish" may now legitimately stop, and that will be the gate working, not a
  regression. If it happens, the directory carries a `FAILED` marker and the end
  of `run.log` names the violated invariant.
- The seed now **does** reach the Ollama sampler, so the results will not be
  identical to those of earlier runs even at temperature 0. That is correct and
  has to be anticipated before it is read as instability.
- Rows below the floor **disappear** from the figures. A tier whose ρ sweep is
  under the floor will produce empty curves with
  `rows_excluded_below_floor > 0`. That too is the gate working.

**Recommended order**, and the reason for each step:

1. `bash scripts/run_ollama.sh smoke` — ~5 min. It measures nothing; it tests
   that the new wiring works against real models. **Do not go past here without
   it**, because twelve defects of this day were found by reading code and none
   has been seen against the network.
2. `bash scripts/run_ollama.sh tables-dev` — ~1 h. One hypothesis, 8 prompts,
   tunes τ. It is the tier with the strictest gates and the one that confirms
   that the new `publishable()` does not empty a legitimate run.
3. `bash scripts/run_ollama.sh tables-final --tau <the one from dev>` — ~2 h.
   The declared verdict, over the 16 held-out prompts.
4. `bash scripts/run_ollama.sh v3c-gt` — ~4–6 h. The fourth measurement of the
   confidence map, already withdrawn. It is worth running anyway: four
   concordant measurements of "there is no signal" is a publishable result in
   its own right.
5. `v0`, `v3c`, `v3c-ff`, `v4` only afterwards, and with the explicit
   expectation that **v0's ρ sweep is almost entirely below the floor** and is
   going to produce empty figures. That is not a failure of the tier; it is the
   reason its original result is withdrawn. If a real ρ curve is wanted, v0's
   sweep has to be redefined above the floor (≥2.7 at N=8) before running it.

**What is still pending and is not code** (verified on 4 September 2026, and
this note corrects itself): **archiving the obsolete repositories and removing
the token from their remote URLs is already done.** The three working
directories -- `Swarmbly-AI_Clean` and the two in `_archive/` -- point at
`https://github.com/Sebastardito/Swarmbly-AI.git` with no embedded credential,
and no `.git/config`, `.git-credentials` or `.netrc` under `P2PAI` contains the
string. The two obsolete ones are already in `_archive/`.

What **is** still pending is **revoking the two tokens on GitHub**. That is an
action on the web and no run and no commit does it.

This document and `STATE_2026-09-04.md` name the tokens **by prefix only**: both
are versioned, and a note that records a live credential inside the repository
is a second copy of the problem. Verified: the `ghp_` strings left in the tree
are 8 and 10 characters long -- prefixes, not tokens.
