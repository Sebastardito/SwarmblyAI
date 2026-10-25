# Swarmbly AI — Validation harness

*Versión en español: [`README.md`](README.md).*

An executable harness in **Python 3 stdlib** (zero dependencies) that validates
the reasoning of `docs/WHITEPAPER_V2_EN.md` and its companion documents, and
implements the falsification tests of the five models M1–M5 with their declared
refusal conditions.

It runs two batteries:

- **derivation** (T00–T12) — reproduces the arithmetic of the documents, tests
  its own refusal predicates, and measures δ, output length and the interaction
  over the repository's artifacts.
- **empirical** (T0R–T10R, T0RR, T0RR2, T0LR) — judges M1–M5 against the **341
  real runs** in `swarmbly_ref/data/benchmark.jsonl`.

## Running it

```bash
python3 swarmbly_validation/run_all.py            # derivation → REPORT.md
python3 swarmbly_validation/run_all.py --real     # empirical  → REPORT_REAL.md
python3 swarmbly_validation/run_all.py --all      # both       → REPORT_COMBINED.md
python3 swarmbly_validation/tests/t4_delta.py     # a single test
```

It exits non-zero if any test fails, so it is usable in CI without anyone having
to read the summary.

## What reproduces from a clone, and what does not

The reference campaign's corpus **is version-controlled**
(`swarmbly_ref/data/benchmark.jsonl`, sha256 anchored in T00), so the thirteen
empirical tests run as they are from a clean clone.

The earlier runs cited by whitepaper v1.4 **are not**: the repository does not
version `results/`. Three derivation tests — T00, T04 and T06 — depend on those
directories and, in a clone, return `REFUSE` with the reason written out, rather
than passing or failing over data that is not there. To enable them, point
`SWARMBLY_REPO` at a checkout that still holds its run directories:

```bash
export SWARMBLY_REPO=/path/to/checkout/with/results
export SWARMBLY_BENCH=/path/to/benchmark.jsonl   # optional; auto-detected
```

That a check refuses rather than guesses is the point, not a defect: §15.7 of
the whitepaper explains why.

## Verdicts

| Verdict | Meaning |
|---|---|
| `PASS` | the reasoning or the mechanism verifies (or the arithmetic reproduces) |
| `FAIL` | the prediction is refuted |
| `REFUSE` | the instrument does not discriminate, or its input is missing: it declines to issue a verdict |
| `BLOCKED` | an input for the empirical verdict is missing |
| `CONCEPTUAL` | a reasoning check with no new measurement |

`REFUSE` and `FAIL` are not the same and the harness does not conflate them: a
**missing** artifact produces `REFUSE`; an artifact that is **present and does
not reproduce its figure** produces `FAIL`.

## Layout

```
swarmbly_validation/
├── run_all.py               # orchestrator for both batteries
├── run_real.py              # empirical battery over benchmark.jsonl
├── make_corpus.py           # candidate corpus generator (T06)
├── funding_case.py          # generates FUNDING_CASE.md from the JSONL
├── swarmblyval/
│   ├── constants.py         # declared constants and thresholds
│   ├── fixtures.py          # figures transcribed from the documents
│   ├── loaders.py           # loads real artifacts; refuses if they disagree
│   ├── delta.py             # δ estimator with declared components
│   ├── corpus.py            # generator + admission gate
│   ├── interaction.py       # H-INT with a leave-one-out predictor
│   ├── derivation.py        # derived formulas (ρ, coverage, sample size, …)
│   ├── stats.py             # bootstrap, exact tests, refusal predicates
│   └── report.py            # result schema + console/Markdown rendering
└── tests/
    ├── t0_provenance.py     # reconciliation + self-test + corpus anchor
    ├── t1_split_k.py        # M5 — splitting k into three
    ├── t2_triage.py         # M3 — triage gate (42/60)
    ├── t3_uniqueness.py     # M2 — uniqueness in the plan
    ├── t4_delta.py          # M4 — δ explains the bimodality
    ├── t5_rho_scaling.py    # ρ scaling law
    ├── t6_corpus.py         # corpus with a global question (blocker)
    ├── t7_rd_surface.py     # M4 — D(ρ,δ) surface
    ├── t8_l_curve.py        # L curve
    ├── t9_criterion.py      # abandonment-criterion re-test
    ├── t10_aligner.py       # M1 — aligner with semantic substitution
    ├── t11_length.py        # output-length confound
    └── t12_interaction.py   # H-INT, withdrawn reproducibly
```

## What it establishes and what it does not

**What the harness supports.** M4 is falsified in two independent instruments,
with a controlled experiment at constant ρ (T04R, T07R). M2 survives corrected
(T03R). M3 survives (T02R). The ρ scaling law is verified against real data
(T05R). The router is refuted at the cell level (T0RR, T0RR2). `L*` varies by
node class (T0LR).

**What the harness refuses to support.** The abandonment criterion. The
aggregate tax is confounded with the output budget (T11), so T09R `REFUSE`s
rather than reporting a criterion met. The run that settles it is
`swarmbly_ref/benchmarks/run_benchmark.py --matched`.

**Self-testing.** The refusal predicates are tested with cases of known answer
(T00). Two failed silently and their regressions are pinned:
`withdraw_if_largest_cell_undoes` went quiet exactly when the reversal was
large, and removed only one contributor — so it missed the documented case,
where the mean is manufactured by two prompts together — and
`bimodality_summary` mixed list and dict semantics, so it crashed on both. T12
keeps a **withdrawn** hypothesis so that the withdrawal is reproducible rather
than a footnote.

## Related documents

- `docs/WHITEPAPER_V2_EN.md` §15.9 — the campaign analysis.
- `docs/RESULTS_2026-09-25_refbench_EN.md` — the campaign record.
- `docs/VALIDATION_STRATEGY_V2_EN.md` — the agenda this harness executes.
