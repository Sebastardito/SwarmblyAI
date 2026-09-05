# Preregistration — `term_once` at the assembler

> **CERRADA 5 septiembre 2026.** Endpoint primario CUMPLIDO con el doble del
> margen: +8.61 contra el +13.40 exigido. La condición de refutación 2 SÍ se
> disparó (27/36 contra 29/36) y estaba mal especificada — cualquier método
> basado en borrar oraciones cuesta algo en `must_mention`. Las dos lecturas
> quedan registradas. Ver `docs/RESULTS_2026-09-05_term_once.md`.

**Written:** 5 September 2026, after `comp-oracle` and **before** `comp-dev-once`
is run. Nothing below may be changed after that run starts.

## The claim

> Enforcing `term_once` **mechanically at assembly** — keep the first sentence
> carrying each once-term, drop the rest — moves the declared composition cell
> (ρ = 4.0, N = 3, k = 1) by **at least 5 points**, from the k=1 dev run's
> **+18.40** to **+13.40 or better**.

Judged on `mean_delta` of `composition_criterion[composition@rho=4.0@N=3@k=1]`,
dev split, against the `comp-dev` run of 4 September. **Dev to dev.** Twelve
prompts is below `MIN_CLUSTERS_FOR_A_VERDICT`, so this is a point estimate and
the tier will print no verdict; the interval must not be quoted as a bound.

## Why 5 points, and where the number comes from

`comp-oracle` measured the mechanism directly, on this corpus, on this split:

| arm | `term_once` |
|---|---|
| monolithic | 13/24 |
| shipped pipeline | 6/24 |
| oracle, redundant briefs | 6/24 |
| **oracle, redundant + mechanical dedup** | **14/24** |

Eight constraints gained out of 24. It cost **two** `must_mention` and **two**
`words_per_paragraph`, both from deleted sentences that carried something else —
and `words_per_paragraph` is assembler-enforced and excluded from the headline
score anyway.

Eight gained, two costed, on a denominator of roughly 60 comparable checks per
arm. Five points is deliberately less than that arithmetic suggests, because the
oracle's fragments are not the shipped pipeline's fragments.

## Why it should do better here than in the oracle, and why that is a risk

The oracle applied dedup to its **own redundant text**, which scored 17/24 on
the also-`term_once` `must_mention` bucket. The **shipped pipeline scores 21/24
on the same bucket**, because every fragment sees the whole prompt and several
mention the term. Dedup does not touch `must_mention` except through deleted
sentences, so applied to the shipped arm it should keep 21/24 *and* gain the
`term_once`.

That is the reasoning, and it is exactly the kind of reasoning this project has
been wrong about before. It assumes the deletions behave the same on real
fragments as on oracle ones. They may not: the shipped arm writes 8.9 paragraphs
where the oracle writes 2, so there are more sentences to delete and more
chances for a deletion to take a required term with it.

## What would refute it

Any one of these:

* `mean_delta` at or above **+18.40** — the change bought nothing;
* the `must_mention` rate at or below the shipped pipeline's — the deletions
  cost more on real fragments than on oracle ones, and the interaction is the
  finding;
* `term_once_sentences_removed` at **0 everywhere** in `results.csv` — the pass
  did not fire and the comparison is void, whatever the scores say.

The control at N = 8 must still fail, as in every composition tier.

## What is NOT claimed

* Nothing about the **final** split. This is a dev-to-dev comparison and it
  decides whether the change is worth a preregistered final run, not whether it
  works.
* Nothing about the other 19.2 points. `comp-oracle` put **1.4%** of the
  end-to-end loss within reach of allocation; the residual is `must_mention`
  (−9 checks) and `no_repeated_ngram` (−7 checks) against monolithic, and this
  change addresses neither.
* Nothing about **quality**. Deleting a sentence to satisfy a counting rule
  makes the text shorter and may make it worse in ways no constraint in this
  corpus checks. The score is a count of satisfied constraints, and that is all
  it is.

## The flag, and why it is off by default

`--enforce-term-once` changes the **delivered answer** for every cell. Every
published composition figure was produced without it, so a default that
reclassified the record silently would be the stale-instruction defect with a
worse blast radius.

It is also a **flag and not a paired arm**, unlike `--editor` and
`--typed-carry`. Those exist as tuples in `SweepConfig` because both halves are
meant to run together against one baseline. This one cannot: a sweep producing
both would carry two `fragmented` conditions under one label, which is the
pooling defect this project has corrected four times (ρ over N, N over k, a rate
without its denominator, `_full` over `comparable`). To compare, run two tiers.

The function the assembler calls is `swarmbly_v0.constraints.enforce_term_once`
— the same object `comp-oracle` measured, asserted by a test. Two
implementations of one behaviour drift, and the drift gets attributed to
whichever arm notices second.

## The run

```bash
bash scripts/run_ollama.sh comp-dev-once     # ~1 h
```
