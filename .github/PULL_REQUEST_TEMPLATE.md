<!--
Thanks for contributing to Swarmbly.

Two things are non-negotiable and are checked below:
  1. DCO sign-off on every commit (`git commit -s`)
  2. Every performance or quality claim cites a measurement

Everything else is a normal review conversation. Full details: CONTRIBUTING.md
-->

## What this changes

<!-- One or two sentences. What is different after this PR, and why. -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Performance
- [ ] Refactor (no behaviour change)
- [ ] Documentation
- [ ] Tests
- [ ] Build / CI / tooling
- [ ] **Protocol change — requires an accepted SWIP** (see below)

## Related

<!-- Fixes #123 / Implements SWIP-0042 / Part of #456 -->

Closes:
Implements SWIP:

---

## Required checks

### DCO sign-off

- [ ] **Every commit in this PR is signed off under the Developer Certificate
      of Origin 1.1** (`git commit -s`; the `Signed-off-by:` trailer is present
      on every commit, with my real name and a reachable email).

<details>
<summary>What I am certifying, and how to fix a missing sign-off</summary>

By signing off you certify the DCO 1.1: that you wrote the contribution or
have the right to submit it under the project's licence, and that you
understand the contribution and your sign-off are public and kept
indefinitely. The full text is quoted in `CONTRIBUTING.md` Section 2.

This project uses a DCO and **not** a CLA. You keep your copyright; you are
not assigning it to anyone. `CONTRIBUTING.md` Section 2 explains why.

Missing sign-offs:

```bash
# last commit
git commit -s --amend

# whole branch
git rebase --signoff main

git push --force-with-lease
```

No need to open a new PR — amend and force-push this one.
</details>

### Measurement

- [ ] **Any performance, quality, latency, cost, bandwidth, accuracy, or
      scalability claim in this PR — in code, comments, description, or docs —
      is backed by a cited measurement**, *or* this PR makes no such claim.

<details>
<summary>What counts as a cited measurement</summary>

At minimum:

- the command or script that produces the number (committed and runnable)
- the hardware and model configuration (CPU/GPU, RAM, which SLM at which
  quantisation, node count)
- number of runs and the spread — not a single figure
- what it was compared against, if the claim is comparative

**Not acceptable:** "faster", "significantly reduces latency", "scales well",
"improves quality". Unfalsifiable as written.

**Acceptable:** "reduces median end-to-end latency for the 8-micro-task
workload from 4.2 s to 2.9 s (n=20, p95 5.1 s → 3.6 s) on
`bench/configs/local_8node.yaml`; reproduce with `make bench-latency`."

**Also acceptable:** *"expected to reduce latency; not measured."* Saying you
did not measure it is completely fine. Claiming it without the number is not.

`CONTRIBUTING.md` Section 5.
</details>

**Measurement, if this PR makes a claim:**

<!--
Claim:
Command:
Configuration:
Result (n, median, p95, spread):
Baseline compared against:

...or write "No performance or quality claims made in this PR."
-->

---

## Standard checks

- [ ] Branched from `main` and the branch is focused on one thing
- [ ] `ruff format` and `ruff check` pass with no new findings
- [ ] Type annotations on public functions and module boundaries
- [ ] Tests pass locally
- [ ] A bug fix includes a test that fails without the fix
- [ ] New concurrency or network behaviour is tested deterministically
      (injected clocks and transports, no `sleep()`)
- [ ] Public functions, classes, and modules have docstrings stating what they
      do **and what they assume**
- [ ] No bare `except:` and no `except Exception: pass`
- [ ] Domain vocabulary used precisely and consistently (`read`, `contig`,
      `overlap`, `scaffold`, `consensus`, `coverage`) — no new synonyms for
      concepts that already have names
- [ ] Commit messages: imperative mood, ≤72-char subject, component prefix
      (`assembler:`, `orchestrator:`, `node:`, `spec:`, `docs:`, `ci:`)
- [ ] Bilingual docs (EN/ES) updated together — or the gap is noted below so
      it can be tracked rather than drift silently

## Protocol changes only

<!-- Skip this section if this is not a protocol change. -->

- [ ] An accepted SWIP covers this change, and it is linked above
- [ ] The specification (`docs/SPEC_EN.md` / `docs/SPEC_ES.md`) is updated to
      match
- [ ] Backwards compatibility is addressed: mixed old/new networks behave as
      the SWIP describes
- [ ] The SWIP's security and privacy section still holds for what was actually
      implemented

## Dependencies

<!-- Only if this PR adds or changes a dependency. -->

- [ ] No new dependencies, **or** each new dependency is listed below with its
      licence, and its compatibility with AGPL-3.0-or-later is confirmed

<!-- name — version — licence — why it is needed -->

## Anything reviewers should know

<!--
Trade-offs you are aware of, things you are unsure about, parts you would
particularly like a second opinion on, or things you deliberately left out of
scope. Flagging your own uncertainty makes review faster, not weaker.
-->
