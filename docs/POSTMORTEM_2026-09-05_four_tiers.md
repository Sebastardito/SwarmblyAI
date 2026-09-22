---
status: current
lang: en
---
# Post-mortem — four tiers failed in a row, and the pattern is mine

**Written:** 5 September 2026, after Seb asked the right question: *what
happened to the review process, and why are there suddenly so many errors?*

**Cost:** roughly fifteen hours of his compute, across four aborted runs, none
of which produced a usable figure.

This is not an apology. It is a diagnosis, because the answer turned out to be
specific and testable rather than "I was careless".

---

## 1. The four failures

| # | tier | what happened | class |
|---|---|---|---|
| 1 | `v0` | ρ 5.5 asked at N=2, packing **ceiling** 4.90. Undershot, invariant aborted at hour five. | grid meets corpus |
| 2 | `v0` | grid moved; ρ 3.95 at N=8 on a **chain**, whose mandatory carries force an overshoot in the band above its floor. +5.6 %, aborted at hour five. | grid meets corpus |
| 3 | *(found while diagnosing #1)* | `tables-dev`/`tables-final` had been running their **declared** cell above the ceiling all along, undershooting a systematic −3.4 % that passed the fidelity check. | grid meets corpus |
| 4 | `v0` | the sweep **completed** — `results.csv`, `summary.json`, `report.html` all written — and `run_tier` marked it FAILED because I had not created the per-N subdirectory it tees `run.log` into. | shell |

## 2. What the review process actually covered, and what it did not

The `/engineering:*` and `/data:*` review of late August was real and it worked:
it found twelve instrument defects, all one-sided toward the project's own
hypothesis, and it produced `REVISION_2026-08-12.md`, ADR-001 and most of the
gates now in the harness.

**It reviewed code that already existed.** In the twenty-four hours before this
post-mortem I wrote nine commits and roughly two thousand new lines — a
composition criterion, a corpus generator, a benchmark runner, a segmenter
repair, a ρ ceiling, a ρ predictor, a grid checker — and applied nothing like
that review depth to any of it.

That alone would be an ordinary answer ("review the new code too"). It is not
the real answer, because **a code review would not have caught any of the
four.** Failures 1–3 are about how a grid meets a corpus, which no reading of
the code reveals; failure 4 is shell, which the Python suite cannot execute.

## 3. The actual gap, and it is one line

**I verified everything except the thing I was shipping.**

For each of the four I ran: the unit suite (648 tests, all passing), and for the
grid failures `check_grid.py`, which packs cells correctly and says nothing
about the rest of the pipeline. **I never once ran `bash scripts/run_ollama.sh
v0`.**

The evidence is clean, and it is the reason this post-mortem exists rather than
a general resolution to be more careful:

| tier | did I run it end to end before shipping? | outcome |
|---|---|---|
| `comp-dev` | **yes** | worked first time |
| `comp-final` | **yes** | worked first time, produced the verdict |
| `v0` | no | failed three times |
| `smoke` | no | shipped with stale guidance and no wrapper |

Two rehearsed, two not. Two worked, two did not. That is not a coincidence and
it is not about effort — nothing but running the tier runs the tier.

## 4. What was built in response

**Rehearsal mode.** `SWARMBLY_REHEARSE=1 bash scripts/run_ollama.sh <tier>` runs
the tier end to end against the mock backend, with no Ollama and no models, in
seconds. The same functions, the same invocations, the same `run_tier` wrapper,
the same post-conditions — only the backend and the preflight are stubbed, and
the swap happens **inside `run_tier`** so a tier cannot be rehearsed with a
different command than it ships with. Every run is stamped
`harness_validation_only: true`.

**It is now a test.** `test_every_tier_rehearses_clean` runs all seven tiers
through the real runner as part of the suite. It is slow by the standards of
that file — 84 seconds against 25 — and that is the correct trade against five
hours.

**And it immediately found two more**, before either reached Seb:

* `v3c` would have aborted at ρ 2.5, N=4 on the same chain, +8.6 %. Moved to
  3.0, which `check_grid` says is inside the usable range. **That is three hours
  it did not cost.**
* `smoke` was the one tier dispatching `python3 -m swarmbly_v0` directly rather
  than through `run_tier`, so the tier an operator runs *first* — to find out
  whether anything is wrong — was the only one with no FAILED marker and no
  post-condition. An abort there would have printed a traceback and then
  "Done".

**`run_tier` now creates its own output directory**, so no caller can repeat
failure 4.

### And then rehearsal produced a defect of its own

The first seven rehearsals wrote into `results/` under the tiers' real names.
One of them was `results/comp-dev-20260905-045427` — newer than
`results/comp-dev-20260904-122727`, which is the run the declared composition
verdict was calibrated against. Every reader in this project selects a run by
glob and takes the last one, including the snippet in the runbook I wrote
myself. **A mock run had become the newest `comp-dev` on disk.**

`harness_validation_only: true` was in its metadata and would have caught it if
anyone read the metadata first. That is precisely the assumption this project
has been wrong about four times. The stamp is a label; the guard has to be a
fact. Rehearsals now write to `results/rehearsal/`, which `results/<tier>-*`
does not match, and `test_every_tier_rehearses_clean` asserts after each tier
that no new `results/<tier>-*` directory appeared.

That the fix for a verification gap immediately opened a provenance hole is
worth stating plainly: **new safety machinery is new code, and new code gets no
exemption from the gates.** The seven stray directories have been moved out of
`results/` on the working copy.

## 5. The thing I got wrong twice, separately from the process

On failures 1 and 2 I patched the ρ grid **from a hypothesis about the cause**,
shipped it, and was wrong both times. I then tried three more explanations for
failure 2 — quantisation, separator accounting, a realised floor from mandatory
tokens — and measured each one false.

The fix that worked was to stop hypothesising: `predict_rho` packs a cell
exactly as the sweep does and returns the achieved ρ in milliseconds, as an
upper bound rather than a sample. I should have written it after the first
failure, not the third. A guard I had built on the realised-floor hypothesis
was reverted before shipping, because I could not demonstrate it firing — that
part, at least, was the right instinct applied too late.

## 6. What this says about the project, which is the part worth keeping

Every one of these was caught by a gate. Failures 1, 2 and 4 aborted rather than
producing a plausible number; failure 3 was found while diagnosing failure 1 and
had been silently mislabelling a **published** cell for two days.

That is the harness working as designed, and it is worth stating plainly against
the frustration: **the alternative to fifteen wasted hours was fifteen hours
that produced a figure nobody could trust.** This project has withdrawn four
documents already, and every one was withdrawn because a number reached a table
that should never have been computed.

What changed today is that the gates now fire in **seconds** instead of hours.

## 7. The rule

> No tier is handed over until it has been rehearsed end to end.

It costs seconds. The four failures above cost fifteen hours, and every one of
them would have been caught by it.
