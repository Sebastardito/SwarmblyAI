---
status: current
note: >
  The preregistration stands. Its measurement does not exist yet: the
  feas-dev and feas-final runs of 5 September were invalidated by the corpus
  item ids, and the corrected corpus (digest 8f6c3565) has not been run.
lang: en
---
# Preregistration — the feasibility frontier

> **RUN 1 INVALID (5 Sep, 23:47 and 23:52).** Condition 1 was met in both
> halves: `naive-chunk` 0% on `local`. The diagnosis was not the chunking but
> **the grader**: the corpus came out with ids `[Q1]`..`[Q5]` and
> `grading.extract_items` only recognises numeric labels, so it returned an
> empty list and **every** answer from **every** arm was graded wrong.
> `monolithic-capped` scored 0/2 on documents of 24 rows that it held whole in a
> single node — impossible as a capacity failure.
>
> Corrected to numeric ids; corpus regenerated (digest `8f6c3565…`, the previous
> one was never validly used). Nothing of the hypothesis, of the budget or of
> the arms changes. **The invalidation condition did its job: three hours lost
> and zero numbers published.**

**Written on 5 September 2026, BEFORE building the corpus and before running
anything.** It is the first measurement in the project that can come out in
favour of the architecture, and that is why the design is fixed first.

---

## Why it exists

`REVISION_2026-09-05_que_hemos_medido.md` established the fact that reframes
everything before it: **the largest prompt in the project measures 375 tokens
and the smallest model has a window of 8,192.** No task, in no corpus, has
needed to be fragmented. Three weeks measuring what it costs to split something
that did not need splitting, and the only possible answer to that question was
"it costs".

This test changes the question from **"how much quality is lost?"** to **"does
the answer exist?"**.

## How a task is made not to fit

**Not** by choosing documents that exceed the window of a particular model —
that depends on which model, and `llama3.2:3b` has 128k while `gemma2:2b` has
8k. A measurement that depends on that lottery does not measure the
architecture.

**Yes** by declaring a **per-node budget `W`**: an input context cap that **all
the arms respect equally, the monolithic one included**. That is what a P2P
network of small, heterogeneous devices really is, and it is the architecture's
claim stated as a measurable constraint.

`W = 2048` input tokens (prompt + material + contract header). Declared here and
not adjustable afterwards.

The monolithic arm **fails by construction** when `|P| > W`. That is not a low
score: it is **infeasible**, and it is recorded as such.

## The three arms, and the third is the one that matters

| arm | what it does |
|---|---|
| `monolithic-capped` | one node, budget `W`. Infeasible above `W`. |
| **`naive-chunk`** | **the obvious baseline**: split the material into chunks of `W`, ask each one, concatenate. No router, no planner, no packer, no assembler. |
| `swarmbly` | the shipped protocol. |

**`naive-chunk` is the only comparison that matters.** Without it, the result
would be "fragmenting beats not-fragmenting on tasks that do not fit", which is
trivially true and worth nothing. The real question is whether **the protocol
beats the obvious thing**.

If `swarmbly` ≈ `naive-chunk`, the finding is that the value is in chunking, and
the router, the planner, the packer and the assembler are not paying their cost.
That result is as publishable as the opposite one, and it has to be said now.

## The hypothesis

> There exists a material size `S*` above which `monolithic-capped` is
> infeasible and `swarmbly` goes on answering with an accuracy **at least equal
> to `naive-chunk`'s**, on **global** questions — the ones no chunk can answer
> on its own.

Two parts, and they are judged separately:

* **Feasibility (H-F):** above `S*`, `swarmbly` produces an answer and
  `monolithic-capped` does not. This is packing arithmetic, not an empirical
  result, and it is verified before running with `check_grid`.
* **Utility (H-U):** above `S*`, the accuracy of `swarmbly` on global questions
  **is not inferior** to that of `naive-chunk`, judged on the **lower bound** of
  a bootstrap clustered by document, against a non-inferiority margin of **−5
  percentage points**.

The **lower** bound and not the upper: the claim here is "it is not worse", so
the conservative side is the one below. It is the mirror image of the
composition criterion, and it is declared this way for the same reason.

## The questions, and why two classes

Each document is a table of records. Each question is graded mechanically
against a key computed at generation time — no judge, no model in the verdict.

| class | example | why it is there |
|---|---|---|
| `local` | the value of record `R-047` | a single chunk answers it. **Control:** if `naive-chunk` fails here, the chunking is broken and nothing else can be read. |
| `global` | the total of the column, which record holds the maximum, how many exceed a threshold | **no chunk answers it alone.** This is where a protocol can add something over concatenating. |

**H-U is judged only on `global`.** The `local` ones are the control that the
chunking works.

## What would invalidate the run

| # | condition | consequence |
|---|---|---|
| 1 | `naive-chunk` fails the `local` ones below 80% | the chunking is broken **or the grader is blind**; nothing below it can be read. In run 1 it was the second. |
| 2 | `monolithic-capped` turns out feasible at every size | `W` is not biting; the design proved nothing |
| 3 | Any arm exceeds `W` at some node | the budget is not being enforced, and the measured feasibility is fictitious |
| 4 | fewer than 20 documents with a global question | no verdict, as in every declared measurement of this project |

Condition 3 is checked **by measuring the real context of each dispatched
packet**, not by trusting that the packer respected its target. It is the same
pattern as `packing_ceiling`: measure, do not derive.

## What is NOT claimed

* **Nothing about prose quality.** This corpus is graded against a key.
* **Nothing about cost or latency.** Tokens per node and peak context per node
  are recorded because they are the axes where fragmenting ought to win, but
  they form no part of any hypothesis declared here. Measuring without declaring
  is describing.
* **Nothing about large models.** It is still 3B, and a model that followed
  instructions better would move both branches at once.
* **Nothing about a `W` other than 2048.** A sweep of `W` would be another
  preregistration.

## What the rehearsal cannot prove, and why there is a fixture

The rehearsal with the mock backend shows that the tier **runs**: the functions,
the invocations, the wrapper, the post-conditions. It cannot show that the
grader **reads**, because a mock that cannot answer produces 0/5 whether the
grader works or is blind, and the two things look identical.

That is the gap that cost run 1, and it was not in the rehearsal doctrine. The
remedy is a **fixture**: a correct answer written by hand, graded, that has to
score 5/5 — and its mirror image, an absurd answer that has to score 0/5. No
backend can give those two tests.

> **The rehearsal validates the plumbing, not the semantics.**

## The axes that are recorded without declaring a hypothesis

Because they have never been measured and because they are half of the
proposal:

* `tokens_per_node` — total and maximum across nodes.
* `peak_node_context` — the largest input context any node saw.
* `feasible` — boolean per cell and per arm.
* `n_nodes` — how many were needed.

They go to the CSV and to the summary. They do not become a headline in this
run.

## The bias to watch for, said beforehand

This is the first designed test where the architecture **can** win, and I
designed it myself after writing a document that said the setup was tilted
against it. The two concrete risks:

1. **Choosing `W` so that the result comes out.** `W = 2048` is fixed here,
   before generating the corpus, and is not touched. If the result is ugly with
   2048, the remedy is to publish it with 2048.
2. **That the obvious baseline is a straw man.** `naive-chunk` must be the best
   reasonable simple chunking — chunks that respect record boundaries, the same
   question to each chunk, concatenation in order — and not a clumsy version
   chosen to lose. Its implementation is reviewed against that standard before
   running, and the review stays in the results document.

## The sequence

```bash
python scripts/make_longform.py                    # genera y congela el corpus
python scripts/make_longform.py --verify
bash scripts/run_ollama.sh feas-dev                # ~1 h, fija W y valida las clases
bash scripts/run_ollama.sh feas-final results/feas-dev-<stamp>    # ~2 h
```

Dev/final split as in composition: the question class, the declared size `S*`
and any adjustment are fixed in dev; the final one is evaluated once.
