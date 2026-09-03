# Runbook

The commands, in order, and the check that has to pass before each one. Written
after a session in which a metric defect invalidated four documents and a
threshold nearly travelled across a corpus change — both of which a mechanical
check now refuses rather than a human having to remember.

**Read `## 0` before anything.** Everything else assumes it passed.

---

## 0. Is the tree sound?

```bash
cd ~/Desktop/Dev/P2PAI/Swarmbly-AI_Clean
python -m pytest
```

Expected: **558 passed, 9 skipped**. Anything else — stop, and say so. Failures
here are not flaky; the suite has no network, no models and no clock.

```bash
python scripts/make_tables.py --verify
```

Expected: `verified prompts/tables24.json: 0c5cb7e2a041cd231b020bb24d65f55251ece8fccce6a421638eccd953566b4b`

A mismatch means the corpus on disk is not what the generator builds, and any
threshold frozen against the stored digest no longer applies. Regenerate with
`python scripts/make_tables.py` and expect every downstream threshold to be void.

---

## 1. Dry run — seconds, no GPU, no Ollama

```bash
python -m swarmbly_v0 run --prompts prompts/tables24.json --split dev \
  --rho 3.5 --n 2 --k 3 --backend mock --embedder hash --out /tmp/smoke
```

Look for three lines and nothing else:

| line | must read |
|---|---|
| `corpus split:` | `dev (8 prompts)` |
| the footer | `*** MockBackend: ... NOT evidence about real models ***` |
| `wrote /tmp/smoke/results.csv` | present |

If `corpus split` says anything but `dev`, the split is not being applied and the
run would fit thresholds on the data it then judges. Stop.

---

## 2. `tables-dev` — the run that decides, ~1 h

```bash
bash scripts/run_ollama.sh tables-dev
```

Never `./scripts/...` — the executable bit does not survive file delivery.

**The script now checks its own preconditions before it starts generating.** It
refuses to proceed unless at least five distinct model families are present in
`SWARMBLY_MODELS`, *and* unless the highest *k* the requested tier sweeps is
within the family count — `tables-dev`, `tables-final` and `v4` sweep to *k* = 3,
the `v3c` tiers to *k* = 5. Read the `max k here:` line it prints. Below that
count `select_diverse_nodes` repeats a family to fill *k*, and replicas from one
lineage agree confidently on the same mistake, which biases the *k* arm upward.
That has already happened once, so this is a hard refusal and not a warning.

**A tier that fails now aborts loudly and leaves a marker.** If an invariant is
violated mid-sweep, the tier's directory gets a `FAILED` file naming the tier and
exit status, the script warns at the time, remaining independent tiers still run,
and the script exits non-zero with an `ABORTED TIERS:` summary naming what broke.
Two consequences for this runbook:

- **Check for `FAILED` in the run directory before reading anything else.** A
  directory carrying that marker holds partial output from a run the harness
  refused to complete; it has no `results.csv`, and no number in it is quotable.
- **A non-zero exit is now meaningful.** Previously a broken tier surfaced only
  as a stack trace in the middle of a log nobody reads after a six-hour sweep.

**Before quoting any number from it**, check `run_metadata.json`:

| field | must be |
|---|---|
| `harness_validation_only` | `false` — `true` means the mock ran |
| `embeddings_degraded` | `false` — otherwise τ_sem means nothing |
| `transport_retries` | low; a high count means the endpoint was struggling |
| `corpus_split` | `dev` |
| `corpus_frozen_sha256` | **the digest `## 0` printed** — `0c5cb7e2…` |

There are two digests and they are not interchangeable.
`corpus_frozen_sha256` is over id, split and prompt text — the corpus's own
`_frozen.sha256`, the one `--verify` prints, and the one a frozen threshold is
pinned to. `corpus_file_sha256` is over the raw bytes and moves when a comment
moves. Compare the **frozen** one.

Then:

```bash
python scripts/reanalyse.py results/tables-dev-<stamp>
```

Read in this order:

1. **`rho fidelity`** — every cell `ok`. An `OUT` cell did not run at the budget
   its label names, so its comparison is not the one the label describes. On the
   run of 26 August, N=8 sat at ρ 3.91 against a target of 3.5.
   **Below-floor rows no longer reach any figure.** `publishable()` is now the
   single gate every figure passes through, and it drops rows whose `rho_target`
   sits below that prompt's `rho_floor` rather than annotating them — a
   below-floor cell holds no information about ρ, because every packet in it
   collapses to its mandatory content and two ρ labels produce identical
   packets. So expect a reanalysis to report *fewer* rows than the CSV holds,
   and read a drop in `prompts=` as the gate working rather than as data loss.
   If a cell you expected is missing entirely, its whole ρ row was below floor;
   the fix is a higher ρ, not a re-run at the same target.
2. **`go/no-go`** — the declared cell is `table_summary@rho=3.5@N=2@k=1`.
   **`prompts=`, not `n_observations`, is the sample size**: rows from one prompt
   share its difficulty.
3. **`accuracy at each distinct agreement value`** and **`the declared test`** —
   **withdrawn, not merely undeclared.** Three ground-truth runs put the common
   odds ratio at 3.47, 0.26 and 1.24 — above, below and astride 1 on the same
   question — so the confidence map is withdrawn and dropped from the V7
   benchmark. These lines are still printed as instrument diagnostics. Do not
   set a threshold against them, do not report them as a result, and do not
   treat a favourable value in some future run as a revival: reopening the
   question needs a new instrument and a fresh pre-registration.

If a banner appears saying the results.csv **predates the metric correction**, the
coherence taxes printed are the old, arm-dependent figures. Run:

```bash
python scripts/rescore.py results/<run>
```

which re-scores the run's own assembled answers through the current metric.

It refuses on any run written before **27 August**, because those traces do not
store the assembler's sentence offsets and the seam-local error classes fire at
exactly those indices. Reconstructing them as an even split moved the recomputed
score by up to 0.15 — enough to invalidate the correction it would be reporting.
For such a run there is no shortcut: **run it again.**

---

## 3. `tables-final` — spent once, and only once

```bash
bash scripts/run_ollama.sh tables-final results/tables-dev-<stamp>
```

**Name the dev run, not a τ value.** The script reads τ_sem *and* the corpus
digest from that run's metadata and refuses if:

- the corpus changed since that run — a threshold fitted on other prompts;
- that run has no `corpus_frozen_sha256` — it predates the digest, so there is no
  way to confirm what it was fitted on;
- that run was not on the `dev` split — a threshold fitted on the data it judges.

> ## ⚠ THIS HALF HAS BEEN SPENT — 27 August 2026
>
> `results/tables-final-20260827-102014`. The declared cell came back at
> **+3.26 %, CI [−0.02 %, +6.93 %]** on 16 prompts. The criterion requires the
> upper bound below 5 %; it is 6.93 %. **NOT MET.** The control behaved —
> N=8 at +17.6 %, no overlap.
>
> See `docs/RESULTS_TABLES_FINAL.md`.
>
> **Do not run this tier again on this corpus.** Appending prompts to a spent
> split is the same study, and this study is finished. A further test needs a
> new corpus with its own split, pre-declared before it runs, and reported as a
> second study rather than as a continuation of this one.

---

## Things that have gone wrong, and what now catches them

| what happened | what catches it now |
|---|---|
| The metric scored identical text differently depending on the partition | `test_identical_text_scores_identically_however_it_was_partitioned` |
| Single-replica rows entered the agreement calibration at a 0.0 sentinel | `excluded_single_replica`, and the filter is on `k`, not on the value |
| A percentile flag split a tie group on a four-valued predictor | tie groups taken whole; `achieved_rate` reports what that came to |
| The declared cell averaged two arms (first N, then k) | the cell is `(category, ρ, N, k)`; `n_cells_examined` states the chances |
| A cell ran at ρ 3.91 against a target of 3.5 and nothing said so | `rho_fidelity`, `within_tolerance` |
| Intervals treated 8 400 sentences from 20 prompts as 8 400 draws | `cluster_bootstrap`; `n_clusters` printed beside `n_records` |
| τ_sem fitted inside the run it then evaluated | `--split final` refuses without a dev run; digests compared |
| A stale CSV reproduced a corrected figure's predecessor | `reanalyse.py` banner + `rescore.py` |
| A ρ curve was published across cells whose ρ target was below the packing floor, so the axis had never moved | `publishable()`, the one gate every figure passes through; below-floor rows are dropped, not annotated |
| The packing floor omitted the contract header and the mandatory carry, so `rho_reachable` came back true for cells that then overshot | `packing_floor` counts header and carry; `assert_packet_invariants` refuses to dispatch |
| A tier died mid-sweep and the only trace was a stack trace in a log nobody read | `run_tier` stamps `FAILED`, warns at the time, and the script exits non-zero with an `ABORTED TIERS:` summary |
| k swept to 5 with three families loaded, so two replicas repeated a lineage | `run_ollama.sh` refuses when a tier's max k exceeds the distinct family count |

---

## Operational notes that keep biting

- **`bash scripts/...`, never `./scripts/...`.** Delivered files lose `+x`.
- **Never run a git write command through the device bridge.** It leaves a
  `.git/index.lock` that the mount cannot delete. Even
  `git status --untracked-files=all` writes the index. `git ls-files` and
  `git check-ignore` are read-only and safe.
- **The bridge cannot delete files.** Anything to be removed is moved to a
  `_to_delete/` folder for you to delete yourself.
- **`docs/AUDIT_V0.md`, `RESOLUCIONES.md`, `DISCUSION_PUNTOS.md`, `NAMING.md`
  and everything in `publication/` stay private.** They are not part of the
  public repository.
