# The first composition measurement — and the coherence tax cannot see it

**Run:** `results/v3c-ff-20260903-224021`. `prompts/free_form.json`, 11 prompts —
six free-form answer items, three two-paragraph compositions, two grounded
summaries — at ρ = 2.5, N = 3, k ∈ {1, 3, 5}, five model families. 44 rows.

> **Provenance.** `harness_validation_only: false`, `embeddings_degraded: false`,
> τ_sem 0.640 fitted on 128 pairs (F₀.₅ 0.933, P 0.964, R 0.828), seed 0,
> `rows_excluded_below_floor: 0`, ρ achieved 2.49–2.51 against 2.50.
> `n_families_mean` 3.0 at k=3 and 5.0 at k=5.

**Prose composition is the workload this architecture is pitched on, and until
this run it had never been measured.** It now has been, and the result is not
about fragmentation being expensive. It is about the instrument.

---

## 1. The finding

Mechanical constraint satisfaction — counted from the text, no judge, no model:

| arm | constraint score (comparable) |
|---|---|
| **monolithic** | **1.000** |
| fragmented N=3, k=1 | 0.864 |
| fragmented N=3, k=3 | 0.786 |
| fragmented N=3, k=5 | 0.857 |

The monolithic arm satisfies **every checkable constraint on every composition**.
Fragmenting into three costs **14 to 21 points**.

Now the same texts, on the metric this project has been built around:

| composition prompt | coherence tax at k=1 | at k=3 | at k=5 |
|---|---|---|---|
| `comp_harbour` | +0.000 | +0.000 | +0.000 |
| `comp_archive` | +0.000 | +0.000 | +0.000 |
| `comp_relay` | +0.000 | +0.000 | +0.000 |

**Zero. On every composition, at every k.**

The BooookScore-like coherence tax — the quantity the go/no-go criterion is
written against, the quantity four withdrawn documents reported — says
fragmentation costs *nothing* on exactly the texts where a mechanical count finds
a 14-point failure.

## 2. What actually broke

The failed constraints name the mechanism:

| kind | which failed | what it means |
|---|---|---|
| `term_once` | `retention_once`, `tide_once`, `battery_once` | a required term appears **more than once** — two workers each introduced it |
| `no_repeated_ngram` | `no_repeated_phrase` | a phrase is duplicated across the splice |
| `must_mention` | `mentions_reading`, `mentions_heaviest` | a required thing was **dropped** — no fragment covered it |
| `words_per_paragraph` | `length` | the assembled text is the wrong size |
| `paragraph_count` | `paragraphs` | the splice produced the wrong number of paragraphs |

Two failure families, and they are opposites: **duplication** (three of the five
`*_once` checks) and **omission** (`must_mention`). Both are precisely what
assembly from independent fragments should produce, and both are invisible to a
transition-based coherence score — because each duplicated passage is locally
fluent and an omission leaves no seam.

**One refinement worth having:** `repeated_sentences_cross_task` is **0** in every
condition. No two workers wrote the same *sentence*. The duplication is at the
term and phrase level. The project's design notes describe the signature failure
as "two workers each conclude" — sentence-level restatement. On this evidence it
is finer than that, which matters for anything trying to detect or repair it.

## 3. The arm-neutrality fix, and the direction nobody expected

The raw and comparable scores differ sharply:

| arm | raw | comparable | gap |
|---|---|---|---|
| fragmented k=1 | 0.633 | 0.864 | **+23 points** |
| fragmented k=3 | 0.711 | 0.786 | +7 |
| fragmented k=5 | 0.756 | 0.857 | +10 |

The comparable score, which excludes `paragraph_count` and `words_per_paragraph`,
is **higher** — so the raw score was penalising the *fragmented* arm on the
assembler-enforced checks.

That is the inverted case the fix's own comment predicted and this run confirms:
where a prompt describes its structure without naming a paragraph count,
`requested_paragraphs` returns `None`, `select_then_splice` puts the pieces into
one paragraph, and the fragmented arm fails `paragraph_count` **by
construction**. On the table corpus the same two checks were a guaranteed *pass*
for that arm. Same instrument, opposite bias, decided by prompt wording — which
is exactly why they cannot be in a cross-arm figure at all.

Read the comparable score. The raw one overstates the cost here by up to 23
points and understated it elsewhere.

## 4. The coherence tax has no room to move on this corpus

**Ten of the eleven monolithic baselines score exactly 1.000**; the eleventh is
0.875. A tax defined as *(monolithic − fragmented) / monolithic* against a
baseline pinned at the ceiling can only be **≥ 0**. It cannot detect an
improvement, and it has almost no resolution to detect a small degradation.

The reported +2.74 % at k=1 is therefore a one-sided measurement made against a
saturated denominator. It is not wrong, but it is not the cost of fragmentation
on this corpus — the constraint score is, and it says 14 to 21 points.

Combined with §1: on the workload the architecture exists for, the coherence tax
is both **saturated** and **blind to the failures that actually occur**. That is a
finding about the project's primary instrument, and it is more consequential than
any figure the instrument has produced.

## 5. Agreement — the first non-null in six measurements, and its exact limits

| | v3c-gt (answer key) | **v3c-ff (free-form)** |
|---|---|---|
| mean agreement | 0.966 | **0.932** |
| items outside the top bin | 8 of 183 | **18 of 158** |
| **AUC** | 0.525 | **0.602** |
| flagging lift at 10 % | 1.12 | **2.15** |
| accuracy | 0.694 | 0.652 |

Flagging the lowest-agreement 10 % of items catches errors at **2.15× the base
rate**. On the answer-key corpus the same statistic was 1.12.

**This is what the mechanism was designed for and it is the first time it has
been given the conditions to work.** The free-form corpus supplies answers that
can be phrased differently and still be right, so replicas *can* disagree; the
predictor has variance, and with variance it carries some information. It is
exactly the direction predicted from the v3c-gt bins: agreement is informative
where it is not pinned at 1.0.

**The declared measurement has now been made, on this stored run, before
generating anything new.** Bootstrap clustered by prompt, 10 000 resamples, and a
permutation test that shuffles the correctness labels *within* each prompt:

| | |
|---|---|
| AUC, point | **0.602** |
| 95 % CI, bootstrap clustered by prompt | **[0.5014, 0.7243]** |
| permutation test (labels shuffled within prompt) | **p = 0.0026** |
| prompts contributing items | **8** |
| items | 158 (103 right, 55 wrong) |

**The two tests do not say the same thing, and the difference is the result.**

The permutation test asks: *within these prompts, does agreement order items
better than chance?* It answers clearly — **p = 0.0026**. Agreement is not
inert here.

The clustered bootstrap asks a harder question: *would this survive a different
draw of prompts?* Its lower bound is **0.5014** — chance to three decimal places.
It excludes 0.5 by 0.0014, on **eight clusters**, where a cluster bootstrap is
not trustworthy at all; twenty is the usual floor.

**The honest statement is therefore narrow and it is worth stating precisely:**
on this corpus, agreement carries real information about which items are wrong.
Whether that generalises beyond these eight prompts is not established, and this
run cannot establish it.

Three further limits, stated now rather than after someone objects:

1. **90 of 248 items were excluded as single-replica** and 45 more as
   unintelligible. The surviving 158 are not a random subset.
2. This is the **sixth** measurement of this question and the first that is not
   null. That deserves more scepticism, not less — though this run was scheduled
   before v3c-gt returned 0.525, so it is not a design chosen after seeing them.
3. The effect is where theory said it would be, which is reassuring and is also
   how a spurious result looks when it happens to agree with a prior.

**What this changes.** The confidence map was withdrawn on five nulls. It is not
un-withdrawn by this: the claim that agreement predicts correctness *in general*
is still not supported. What is now supported, on eight prompts, is a **bounded**
version — **where answers can be phrased differently, agreement is not inert.**
Establishing whether that bound is real needs more prompts, not more replicas:
the limiting quantity is clusters, and going from 8 to 25 free-form prompts would
do more than any number of extra items inside the existing ones.

## 6. What this run settles and what it opens

**Settles:** fragmentation has a real, measurable cost on prose composition —
14 to 21 points of constraint satisfaction against a monolithic arm that scores
perfectly — and the cost is duplication and omission, not sentence-level
restatement.

**Opens, and this is the larger item:** the coherence tax is not a usable
instrument for this workload. It is saturated against a ceiling baseline and it
reports zero on texts with a 14-point mechanical failure. Every figure this
project has produced, withdrawn or standing, was measured with it.

The constraint score is a better instrument for composition and it already
exists. What it lacks is a pre-registered cell, a control, and a corpus split —
the apparatus `tables-final` has. Building that for composition is now a more
valuable use of a night than any further coherence-tax run.
