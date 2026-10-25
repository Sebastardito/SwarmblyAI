---
status: current
lang: en
---

# Consolidated pre-registration — benchmarks R14, R13 and R11 of Swarmbly LCE

**5 October 2026 · written BEFORE any real run of these benchmarks**

This document freezes the designs of the next three phases of the LCE
validation plan — hypotheses, rubrics, margins, budgets and refusal
conditions — before a single datum exists. It refers to whitepaper LCE v0.1
(Sections 11.1–11.5) and to the already published results (confirmatory run
2; exploratory benchmarks F1a–F1d with their declared scope). Any later
change is recorded as a numbered amendment in Section 7; a silent change
does not count.

**Covered:** R14 (reproducibility — the environment everything else runs
on), R13 (the decisive question of H-C1: does an anchored wiki beat a simple
memory?), R11 (the fair adapter: H-C6, H-C10 and forgetting by
regeneration), and the closure of H-C2 (ρ against its gain), folded into
R13. **R12 (the social plane) is pre-registered separately** once the canary
set is verified by native speakers, because its blocker is calendar time,
not compute.

Spanish: `PREREGISTRATION_BENCH_R1X_ES.md`.

---

## 1. R14 — Reproducibility (applies to everything else)

### 1.1 Frozen environment

1. The repository freezes a dependency lock file with exact versions and the
   Python version (3.11).
2. Ollama model digests (the five families and `nomic-embed-text`) go from
   being recorded to being a CHECK: the run STOPS if a model does not match
   the pre-registered one, and the refusal is recorded as an infrastructure
   failure, not as a result.

### 1.2 Sampling

1. **Temperature 0** for every measure that does not depend on diversity:
   multiple-choice items, H-C1 and R13 answers, lexicon adherence, identity
   probes.
2. For measures that DO depend on diversity (cross-user homogeneity), the
   raw samples are stored and the analysis assumes no pairing by seed
   (bootstrap over topics, as in run 2).
3. Adopting a server with an effective seed (candidate: llama.cpp) requires
   a pre-registered **A/A test** first: the mean difference between two
   identical runs must be ≤ 0.01 on the stochastic measures. Only if it
   passes is it adopted, recorded as an amendment.

### 1.3 Regeneration and figure anchoring

1. A single command (`python -m lce_validation.run_derive`, to be built)
   regenerates ALL tables of the RESULTS documents from the stored raw
   outputs, without models, and exits non-zero if any figure mismatches.
2. The figure blocks of the RESULTS documents become GENERATED from the JSON
   (never hand-edited), and a CI test compares each published figure with
   its JSON (the `test_published_figures_recompute` pattern of Swarmbly).
3. A shared `provenance()` helper records in every benchmark: Ollama
   version, model digests, git commit and the SHA-256 of this
   pre-registration.
4. **R14 closure criterion:** a fresh clone reproduces the tables
   byte-identical from the raw outputs; on re-running, deterministic arms
   come out identical and stochastic ones stay within the A/A noise (±0.01).

### 1.4 Publication

Release v0.1.1 on GitHub and Zenodo deposit (software DOI), with the raw
outputs included and this pre-registration cited.

---

## 2. R13 — Decisive H-C1: does the anchored wiki beat a simple memory?

### 2.1 The question

"Does memory help?" is answered (F1a: +0.477 per question, 95 % CI [+0.407,
+0.543]). The new question is: **does an anchored, typed, versioned wiki
beat the simple alternatives — the full document in context and raw-chunk
RAG — and on which question types?**

### 2.2 Arms (same token budget T per question; T is reported)

| Arm | What the answering model receives |
|---|---|
| A0 — no memory | the question only |
| A1 — full document | the user's complete sources, truncated to the budget |
| A2 — raw RAG | the k nearest fragments by embeddings (same embeddings as the wiki) |
| A3 — LCE wiki | anchored claims retrieved from the wiki (BM25), with type and maturity |
| A4 — wiki + Γ | A3 plus the projection into the contract (the full LCE product) |

Tokens sent are reported per arm and per question: they are exposure and ρ.

### 2.3 Question types (fixed before running)

1. **Simple fact** — one key in one source.
2. **Cross-document** — the answer requires combining two sources.
3. **Updated fact** — a newer source corrects an older one; correct = the
   current value.
4. **Contradiction** — two current sources disagree; correct = the current
   version or explicitly flagging the disagreement.
5. **Deleted source** — the user forgot the source; correct = ABSTAIN
   (answering with the deleted fact = error, worse than being wrong).
6. **No answer in memory** — the sources do not answer the question; correct
   = ABSTAIN.

Rubric per type (normative part of this document):

| Type | Correct | Incorrect |
|---|---|---|
| 1, 2 | gold key present | absent or wrong |
| 3 | current value | old value |
| 4 | current version OR disagreement flagged | old version without flagging |
| 5, 6 | abstention (or "not in my sources") | any answer with content |

### 2.4 Data

1. **Frozen own users**: the five benchmark-corpus users (frozen SHA),
   extended with a version 2 per user that adds: an updated source, a
   contradiction, a deleted source and an unanswerable question. The
   generator is frozen in the data commit.
2. **Public subset**: LongMemEval or LoCoMo, chosen after verifying its
   licence; the choice, the SHA-256 of the subset and its licence are fixed
   in Amendment 1, before running. It answers the criticism that the author
   writes the synthetic users.

### 2.5 Crossed design

- **3 digesters × 3 responders** (qwen2.5:3b, llama3.2:3b, gemma2:2b — the
  three families with the highest gain in F1a) for arm A3: it separates
  digester quality from answering ability and decides the digester gate with
  data, not with confounded correlations.
- Arms A0–A2 use the 3 responders. A4 uses the A3 cross plus Γ.

### 2.6 Size and statistics

- **≥250 paired questions** (every question goes through every arm), with
  **≥30 per type** for per-type intervals.
- Primary statistic: paired difference **A3 − A2** (wiki − raw RAG) per
  question, with a bootstrap clustered by question (10,000 resamples, seed
  20261005). Secondary: A3 − A1, A4 − A3, and the per-type breakdown.
- Declared power: with discordant pairs ≈ 30 %, n = 250 detects a difference
  of 0.10 with comfortable margin.

### 2.7 Decision rules

| Hypothesis | Holds | Dies | Otherwise |
|---|---|---|---|
| R13-H1: the wiki beats raw RAG | 95 % CI of A3−A2 > 0 overall | point estimate ≤ 0 | inconclusive |
| R13-H2: the wiki wins on updates and forgetting | CI > 0 on types 3 and 5 | point ≤ 0 on both | inconclusive |
| R13-H3 (digester gate): a floor on anchored claims explains utility | utility falls below the proposed floor in the crossed design | no monotone relation even crossed | the gate is withdrawn as a rule |
| H-C1 global death | — | raw RAG ≥ wiki overall AND the wiki does not win on 3 and 5 | the design is simplified (publishable) |

### 2.8 C2-bis (same run)

Placebo matched in instruction AMOUNT (not only form) and ≥5 users differing
in ≥2 traits. H-C17a holds if the homogeneity reduction by projection
exceeds the placebo with a 95 % CI > 0. It closes the main qualification of
run 2.

### 2.9 Closure of H-C2: ρ against its gain (same run)

With the wikis digested in R13 and Swarmbly's dispatch path (real planner +
packer, parametrisable path), the pair **(adherence gain with Γ, Δρ)** is
measured per task. Pre-registered tradeoff rule: **the projection survives
if the fraction of tasks with gain > 0 AND Δρ ≤ 10 % is ≥ 0.8**; the full
per-task scatter is reported. No additional thresholds.

### 2.10 Refusals

Refuse if: a model digest mismatches; fewer than 3 responders answer; any
wiki has < 5 anchored claims; fewer than 200 analysable questions; more than
10 % of answers cannot be scored.

---

## 3. R11 — The fair adapter (H-C6, H-C10, LC6)

Runs AFTER R13: the training batch comes from the trainable claims of an
already validated wiki.

### 3.1 Batch and tasks

1. The batch is built ONLY with `ExampleBuilder` from TRAINABLE claims
   (preference, style, procedure) — never facts (I1) — and with interleaved
   replay.
2. The test tasks are reworded and do not cross the batch: **≥30 per user ×
   3 users** (the first three of the corpus), with confidence intervals.
3. The **no-replay** sub-arm (H-C10) trains the same batch without the
   replay examples: one extra configuration per adapter.

### 3.2 Base families and seeds

- Two families: **qwen2.5-3b** (weights not distributed; qwen-research
  licence) and **granite-3.1-2b** (Apache-2.0; verify before freezing —
  amendment).
- **2 training seeds** per adapter; the third runs only if the first two
  disagree by more than 0.05 (MLX is not deterministic; the between-seed
  variance is reported).
- Declared budget: 2 families × 3 users × 2 seeds × 2 (replay) = **24
  trainings** of ≤ 500 iterations.

### 3.3 Arms (same information per arm)

base · retrieval + Γ (BM25 over the user's full wiki) · adapter · adapter +
retrieval.

### 3.4 Decision rules

| Hypothesis | Holds | Dies |
|---|---|---|
| H-C6 | adapter − retrieval has CI lower bound > 0 and mean ≥ +0.10 in ≥2 of 3 users | bound ≤ 0 in 2 of 3 → layer 2 is withdrawn (the roadmap death condition) |
| H-C10 (replay) | the no-replay arm forgets consolidated material EARLIER than the replay arm (later crossing point with replay) | no difference → the CLS homology reverts to vocabulary |
| LC6 (forgetting) | after `forget` of a source and regeneration, the forgotten fact returns to the base level (equivalence ±0.10) and style adherence persists | the fact persists in the adapter → "verifiable forgetting" is withdrawn |
| I1 (leak) | WITHOUT retrieval, the adapter does not answer user facts better than the base (equivalence ±0.10) | the adapter beats the base on facts → I1 violated and the batch is rebuilt |

### 3.5 Public option

A subset of LaMP (the personalization benchmark of OPPU [5]) if its licence
allows and its topics do not overlap the wikis; fixed by amendment with SHA.
It makes the result comparable with the literature.

### 3.6 Instruments tested in simulation BEFORE measuring

The abstention scorer (R13 types 5–6), the contradiction scorer (type 4),
the I1/LC6 equivalence procedure (it must detect an injected leak), the A/A
sampler test, and the generated-figure anchoring (1.3.2). None of them
decides anything before passing its simulation.

---

## 4. What this pre-registration does NOT cover

R12 (social plane) — requires the verified canary; pre-registered
separately. The public-subset choice (R13) and the second base family (R11)
— licence pending; they enter by amendment before running. Style-quality
judging is out of scope: grading is deterministic when the gold allows it,
and an LLM judge is only a secondary measure with human audit of a sample,
from a family different from the responders.

---

## 5. Execution order

R14 (environment and regeneration) → R13 (decisive run + C2-bis + ρ) → R11
(adapter, with batches from the R13 wikis) → R12 (separately). Every
confirmatory run requires a clean tree, verified digests and this committed
pre-registration, as in run 2.

---

## 6. References

[W] Whitepaper LCE v0.1, Sections 11.1–11.5. [5] Tan et al. 2024 (OPPU).
[LaMP] Salemi et al. 2024. [LongMemEval / LoCoMo] licence to confirm
(amendment). [Swarmbly] whitepaper v2, Sections 5 and 15, for the dispatch
path and the definition of ρ.

---

## 7. Amendments

**Amendment 1 — 9 October 2026, before running.** The first R13 run is an
EXPLORATORY PILOT over the own users v1+v2 (91 questions: 60 from F1a + 31
type-tagged), with the five arms, the 3×3 cross and the per-type rubric. It
emits no pre-registered verdicts: its purpose is to validate the pipeline and
calibrate costs. The CONFIRMATORY run of ≥250 questions is conditioned on
amendments 2 (corpus expanded to ≥30 per type, with SHA) and 3 (public subset
with verified licence — LongMemEval is MIT and is the candidate; LoCoMo has
custom terms without a standard licence and is discarded barring legal
review). The A1 (full-document) token budget is fixed at 2,400 truncated
words for the pilot and reported per question.

**Amendment 2 — 9 October 2026, after the pilot and before the
re-pilot.** The pilot identified two confounds; they are corrected as
follows: (a) EQUAL context budget for all arms: 200 tokens (the pilot's RAG
budget), including A1 truncated to the first 200 words; (b) recency-aware
wiki retrieval: among the 10 closest BM25 claims, order by the latest
explicit date of their source (dated sources before undated ones), then by
maturity, then by score. The re-pilot re-runs only arms A1, A3 and A4 (A0
and A2 are unchanged and their cells are inherited from the pilot) with the
already cached wikis. Amendment 3 (public subset) remains pending before
the confirmatory run.

**Amendment 3 — 9 October 2026, after the re-pilot and before the
verification re-pilot.** The re-pilot (Amendment 2) measured A3−A2 = −0.322
at equal budget and located two implementation defects and one missing
regime. They are repaired before judging: (a) ATOMICITY — the digester
processes sub-passages of 3 sentences and the prompt forbids merging facts
from different sentences (the pilot measured one claim containing both
values of an update, against the whitepaper's own atomic principle); (b)
PER-FACT RETRIEVAL — among retrieved claims, if a dated claim shares ≥2
content words with another, the earlier one is discarded (the update
supersedes the old one); (c) LONG CORPUS — each user gains a 193–408-word
document with 7 questions whose answers lie beyond A1's 200-word budget
(the regime where compression can pay; multi-thousand-word documents enter
in the confirmatory's expansion). The verification re-pilot re-digests the
wikis (the digester changed) and re-runs the five arms over the 126
questions.

**Amendment 4 — 9 October 2026, after the verification re-pilot and
before the clean re-measurement.** SOURCE CONTAMINATION was found: the
source space scanned the whole user directory and ingested the benchmark's
question files (`questions*.json`, with their gold keys) as wiki sources —
the wiki contained leaked answers and the comparison was not clean.
Corrected: the user's sources are ONLY `.md` documents
(`build_wiki(suffixes={".md"})`). The same contamination affects benchmark
F1a (same `build_wiki`): its central figure (+0.477) is SUPERSEDED until
the clean re-measurement, relaunched together with the R13 re-pilot.
`bench_rho` used the same wikis but measures projection SIZE (arithmetic),
not content: its verdict stands and is re-run for cleanliness. In addition:
the wiki arms' abstention now requires the context to contain the EXACT
answer (targeting the `deleted` type, where the wiki answered with the
related current claim).

**Amendment 5 — 9 October 2026, before the R11 pilot.** The second base
family is granite-3.1-2b-instruct, licence **Apache-2.0** (verified on the
model card). LC6 (forgetting by regeneration) is deferred to the R11
confirmatory run: it requires the full forgetting flow (`forget` +
regeneration) and is declared here rather than improvised. The R11 pilot
covers H-C6 (four arms), H-C10 (replay yes/no) and the I1 leak test
(equivalence ±0.10, instrument tested in simulation).

**Amendment 6 — 10 October 2026, after the R13 review and BEFORE running
the forgetting test and the A/A test.** It has three parts.

*(a) Declaration of post-data repairs.* The 9–10 October review found
implementation defects that changed published figures, and they were
repaired after seeing the data: E1 (the R13 summary overwrote digesters and
A3 reflected gemma2 only), E2 (recency retrieval sorted in reverse and A3
did not use the per-fact retrieval of Amendment 3), E3 (the deleted source
was digested into the wiki but not into RAG), E4 (F1a still ingested the
`questions*.json` files) and E5 (A4 was compared against A3 of a single
digester). The affected figures are retracted and replaced by those
re-measured on 10 October; none of these repairs changed the rubric or the
thresholds. From now on every repair carries a test that fails if the defect
returns (`tests/test_r13_repairs.py`).

*(b) Two defects of the material, declared rather than silently fixed.* N1:
three v1 "simple" questions (andres: risk ratio 0.85; carmen: Manantial
+6.8; mara: F_ST 0.036) have as their key the value that
`actualizacion.md` declares superseded; the key is not changed (that would
be editing the gold after seeing the data): F1a and R13 are reported with
and without those three questions, and the confirmatory run removes them
from the corpus before running. N2: in R13 the `deleted` type does not
measure forgetting, because no arm ever saw the deleted source; it is
reinterpreted as "unanswerable with related information" and, as with
`unanswerable`, abstention rewards the arm that retrieves less (A0, without
memory, scores 1.00). From now on abstention is reported together with the
same arm's accuracy on answerable questions, never alone.

*(c) Forgetting test (F-forget) and A/A test, pre-registered here.*

**F-forget.** For each user (5) and digester (qwen2.5:3b, llama3.2:3b,
gemma2:2b): W_full = wiki digested with ALL `.md` sources, `borrada.md`
included; W_forget = W_full after `Wiki.forget_source` of that source (the
SPEC 7.8.1 mechanism); W_never = wiki digested in the same run without that
source. Structural measures (no responders; primary): S1 manipulation check,
W_full has ≥1 claim anchored to the source (otherwise the cell is refused);
S2 residue, claims of W_forget anchored to the forgotten source (must be 0 in
100 % of cells); S3 collateral damage, claims of W_full not anchored to that
source that are missing or changed in W_forget (must be 0 in 100 %); S4
equivalence, equality of the claim sets of W_forget and W_never and of the
context each gives to the 126 R13 questions (descriptive: it depends on the
determinism of digestion, which the A/A measures). Sweep: S2 and S3 are
repeated forgetting each source of each W_full. Behavioural measures
(secondary, low power: 5 questions × 3 × 3): abstention rate on the
questions about the deleted source with W_full, W_forget and W_never, same
prompt and rubric as R13. B1 (manipulation): abstention with W_full must be
at least 0.10 lower than with W_never; otherwise the behavioural test is
uninformative and is declared so. B2: forgetting is behaviourally complete
if abstention with W_forget exceeds that of W_full and lies within ±0.10 of
that of W_never. **Verdicts:** structural forgetting holds if S2 = 0 and
S3 = 0 in every non-refused cell and across the whole sweep; it is falsified
if any cell leaves residue or collateral damage.

**A/A.** AA1 (deterministic generation): arm A2 of R13 is repeated (126
questions × 3 responders, temperature 0, same context) and compared with the
stored answers (first 200 characters, which is what that run stored); it
passes if ≥ 99 % are identical and accuracy changes by no more than 0.01. AA2
(deterministic digestion): the W_never wikis of F-forget are compared with
the stored R13 wikis (same digester, same sources); it passes if the claim
set matches in ≥ 14 of 15 wikis. AA3 (seed): qwen2.5:3b writes the 20 C2
topics at T = 0.7 with seeds 1000–1002, twice with the same seeds, through
the OpenAI-compatible endpoint and the native one (`/api/generate`,
`options.seed`); the seed is effective on an endpoint if ≥ 95 % of the texts
repeat identically. AA4 (stochastic measure): homogeneity across the three
seeds per topic (`nomic-embed-text` embeddings) is computed on the two
repetitions of the OpenAI-compatible endpoint; it passes if the mean
difference between repetitions is ≤ 0.01 in absolute value (bootstrap CI over
topics, reported). **R14 is closed on its re-run criterion** if AA1, AA2 and
AA4 pass; a seeded server is adopted only if AA3 passes, by amendment.

**Common.** Both tests run in the locked environment (Python 3.11 from the
repository's `.venv`), check digests against
`lce_validation/data/model_digests.json` before starting and refuse if they
do not match, record their provenance and store every answer in full. They
are exploratory tests of mechanism and reproducibility: they emit no verdict
on H-C1.

**Amendment 7 — 10 October 2026, BEFORE the AA2 re-run.** AA3 showed the
native endpoint's seed (`/api/generate`, `options.seed`) is effective (100 %
identical) and the OpenAI-compatible one is not (80 %). Per the Amendment 6
rule ("a seeded server is adopted only if AA3 passes, by amendment"),
DIGESTION moves to the native endpoint with a seed derived from the prompt
text (same prompt, same seed, same call order); responders keep the
OpenAI-compatible endpoint (AA1 showed it reproducible). AA2 is redefined as
the comparison of TWO runs of the deterministic digestion (F-forget's
W_never versus a second digestion of the same 15 wikis with the same
backend); its criterion is unchanged (≥14 of 15 identical claim sets). The
R14 re-run criterion remains AA1 + AA2 + AA4.

**Amendment 8 — 10 October 2026, BEFORE the R13 confirmatory run.**
Freezes the confirmatory's data: (a) the own corpus is extended with a
version 4 (120 questions: 13 simple, 16 cross, 16 updated, 25 contradiction,
25 deleted, 25 unanswerable) and the corresponding sources (extended
borrada.md and actualizacion.md plus a new revision_interna.md per user);
(b) the 3 N1 questions are excluded from all runs; (c) the public subset is
LongMemEval (xiaowu0162/longmemeval, MIT licence, split longmemeval_s,
source SHA-256 08d8dad4be43ee20…, verified): 8 questions (7 simple, 1
updated) with their relevant session + 2 distractors, the updated question
also keeping the session with the previous value; trimming the full
haystack (~50 sessions) is declared here as a budget decision, not a corpus
improvement. The frozen subset lives in
lce_validation/fixtures/bench_users/lme/ with SHA-256 ae727be6ff7f29ba… in
lce_validation/data/lme_subset.json. Confirmatory totals: 251 questions —
simple 100, cross 30, updated 31, contradiction 30, deleted 30,
unanswerable 30 (≥30 per type).

**Amendment 9 — 10 October 2026, BEFORE the R11 confirmatory run.**
Repairs the six E6 defects and fixes the confirmatory's design: (1) the
batch comes from ExampleBuilder ONLY over trainable claims of the user's
CANONICAL wiki (digested by qwen2.5:3b, R13's validated digester) for both
base families; (2) no collapse: 2 epochs (iters = 2 x ceil(n/2)), batch 2,
lr 1e-4; (3) VALID tasks: lexicon per the user's own preferences, register
with reachable golds (concrete rules) and procedure with the user's own
protocol thresholds — never whole normalized rules or other-domain
questions; >=30 tasks per user with task-clustered bootstrap CIs; (4) the
retrieval arm carries REAL Gamma (Projector over the retrieved claims);
(5) I1 uses 10 USER facts (their factuals), adapter without retrieval vs
base, equivalence +-0.10; (6) LC6 runs: mara's teach/style is forgotten,
re-trained without its claims and style-task adherence must fall toward
base; (7) H-C10 is a 2-point curve (25 % and 100 % of budget) on
consolidated-material (style) tasks, with and without replay. Budget: 2
families x 3 users x 2 seeds x 2 replay x 2 points = 24 trainings + 2 for
LC6.

**Amendment 10 — 10 October 2026, BEFORE the confirmatory run.** (a) The
digester's parser becomes tolerant: it accepts the SEQUENCE of JSON objects
({..},{..}) the model sometimes emits and merges their claims — removing the
loss of whole sub-passages to output shape. (b) Environmental
reproducibility condition: native seeded digestion is reproducible ONLY
with an exclusive server (no concurrent requests: GPU contention alters the
decode); the R13 confirmatory and the AA2 evaluation run with Ollama under
no concurrent load, declared here. (c) AA1 and AA2 are evaluated against
the CONFIRMATORY's outputs (Amendment 8's corpus change invalidates the
comparison against the pilot); the R14 re-run criterion remains AA1 + AA2 +
AA4 with their thresholds (>=99 % identical; >=14/15 wikis; |homogeneity
delta| <= 0.01).

**Amendment 11 — 10 October 2026, BEFORE the confirmatory run.** Ollama's
decode is not bit-reproducible for long outputs even with a seed (AA2:
12-13/15 identical wikis, Jaccard 0.985). Digestion becomes DOUBLE-PASS:
each sub-passage is decoded twice (same seed) and only claims present in
BOTH decodes are kept; the intersection filters the variable part of the
decode. Cost: twice the digestion calls. AA2's criterion (>=14/15) is
unchanged.

**Amendment 12 — 10 October 2026, BEFORE the confirmatory run.** The
double-pass intersection (Amendment 11) WORSENED cross-run agreement (AA2:
8/15) and is reverted: the intersection filters the variable part WITHIN a
run but not between runs, and shrinks the claim set. Honest cycle result:
Ollama digestion is not reproducible run to run on this stack (AA2 across
four configurations: 8-13/15 identical claim sets, Jaccard 0.943-0.992);
generation (AA1) and the stochastic measures (AA4) ARE reproducible. **The
R14 re-run criterion stays OPEN as a documented negative result** (a stack
limitation, not a design one). The R13 confirmatory proceeds with native
seeded digestion plus the tolerant parser (the best configuration:
12-13/15) and its wikis are saved as auditable artifacts; the
pre-registration does not condition the confirmatory on R14's closure.

**Amendment 13 — 11 October 2026, during the R11 confirmatory run
(before re-evaluating; does not touch the design).** R11's evaluation moves
from the MLX CLI to a persistent MLX SERVER per (model, adapter): same
weights, same prompts, temperature 0 and the same gold thresholds. The CLI
reloaded the model per call and granite (2B) took ~45 s per call (~20 h of
evaluation); the server reuses the load (~1-2 s per call). The 26 already
completed trainings are reused (resume per existing adapter); only the
evaluations re-run. This is an execution-mechanism change, not a change to
the pre-registered design.

**Amendment 14 — 11 October 2026, after the FIRST C2-bis run and BEFORE the
re-run.** The first run is INVALIDATED as instrumentation: the request to
the Projector ("escribir un texto breve del usuario") retrieved only the
register claim and produced a 4-token Γ (verified: the empty request
triggers the Projector's broad-traits fallback and produces the full Γ with
the lexicon in all 5 users; the "estilo y vocabulario" request still left
one user's lexicon empty). The re-run uses the empty request; the placebo
stays length-matched; the
first run's numbers are reported as an instrument check, not a verdict.

**Amendment 15 — 11 October 2026, AFTER the confirmatory runs: review
declarations.** It changes no design or threshold; it declares what the
review found in the runs of 10 and 11 October and how they are reported.

1. *Environment.* The R13 and R11 confirmatory runs, C2-bis, the H-C2
   closure and the A/A ran with Python 3.9.6, not with the locked 3.11
   (R14 1.1); only F-forget used the 3.11 `.venv`. It is a deviation of the
   environment, not of the measures, and every document declares it.
2. *R13, type 5.* The confirmatory `deleted` type keeps defect N2
   (Amendment 6 b): no arm ever saw the deleted source, the questions have
   related information in other sources, and A0, without memory, abstains
   100 % of the time. Its +0.115 is not a win on forgetting. Forgetting is
   measured in F-forget.
3. *R13, global death.* The Spanish text of Section 2.7, which is the one
   the runs' provenance hashes, says «no gana en 3 ni 5» (the wiki wins on
   neither); the English text says "does not win on 3 and 5", which reads
   as "does not win on both". The two versions diverge and the divergence
   had not been noticed. By the letter of the Spanish text the rule does
   not fire, and only because of type 5, which Amendment 6 (b) declared
   invalid before running (point 2); by the English text, it fires. Both
   readings are reported, and no design decision rests on the rule having
   fired.
4. *R11.* In the 1454 cells of the confirmatory run the adapter and the base
   model score identically, and in the 720 tasks they produce byte-identical
   text, although the LoRA weights are non-zero: the adapter was not applied
   during evaluation (the MLX server receives the base model's name in every
   request, and the evaluation uses completions without the chat template
   used in training). The run is refused for a manipulation failure, like
   run 1 of C2. The next run requires a prior check: the adapter must change
   the output on its own training examples before anything is evaluated.
5. *C2-bis.* The implementation computes homogeneity across the three seeds
   of one user and topic, not across users, and has no no-contract arm; it
   does not test H-C17a as Section 2.8 defines it. The numbers of the first
   run, which Amendment 14 says are reported, were not kept.
6. *H-C2 closure.* The gain was measured as QA accuracy (A4 − A3), not as
   adherence; and the rule "fraction of tasks with gain > 0 and Δρ ≤ 10 % ≥
   0.8", written in this pre-registration, is almost unattainable with binary
   per-task gains. Moreover, the implementation does not use the Swarmbly
   planner and packer that Section 2.9 requires: Δρ is computed by word
   arithmetic (Γ tokens per fragment over the context tokens); each task's
   gain comes from a single digester = responder pair (the per-question
   dictionary keeps the last diagonal cell), and Γ is projected with the
   request "resumir el material del usuario" over the qwen2.5 wiki. The
   result is reported as a description (in QA, Γ adds ρ without improving
   accuracy) and H-C2 remains undecided for writing.
7. *A/A.* AA1 against the confirmatory run: 98.4 % identical (n = 369),
   below the 99 % threshold; AA2: 8 of 15. R14 remains open (Amendment 12).
8. *History.* The weights of the 50 R11 adapters (partly derived from
   Qwen2.5-3B-Instruct, qwen-research licence) and their batches had been
   committed to the repository; they were purged from history before
   publication. `docs/COMMIT_MAP_2026-10-11.md` maps the identifiers.
9. *Arm A2.* Section 2.2 defines A2 as the k nearest chunks by
   embeddings; since the pilot, A2 retrieves raw sentences with BM25 (the
   same lexical retriever A3 uses over claims). The deviation had not been
   declared. It makes the A3 − A2 comparison fairer (same retriever,
   different material), but A2 is not the embedding RAG the
   pre-registration describes; an embedding RAG remains unmeasured.

*Text CC BY 4.0; code AGPL-3.0-or-later.*
