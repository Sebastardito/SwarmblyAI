---
status: current
lang: en
note: >
  The run says nothing about L. It is published because the defect it found is
  one of method, not of result.
---
# lcurve-dev — the instrument has no range, and the control did not say so

**Run:** `results/lcurve-dev-20260922-080202`. Corpus `prompts/lcurve.json`,
digest `a21100e2…` verified before starting. 24 dev documents, six sizes, 12
cells of the L × N grid. Five model families over Ollama.

**The run finished clean and says nothing about L.** That second half took a
while to see, and how long it took is the result.

---

## 1. What it printed

```
CELDA DECLARADA: REHUSADA -- 16 clusters, y el piso son 20.
CONTROL `local`: +0.000 (tolerancia 0.05)
```

No invalidation condition fired. The refusal of the cell was expected: the dev
half holds 16 documents with an L contrast and the floor is 20, so dev was
never going to return a verdict — that is what the final half is for.

Read that way, the report says: *the pipeline ran, the control passed, go on to
the final.* And that would have been false.

## 2. What was underneath

Monolithic accuracy, which is the ceiling on any reading:

| | `global` | `local` |
|---|---|---|
| monolithic, all sizes | **1 / 72** | 14 / 48 |
| fragmented, all sizes | 3 / 144 | 10 / 96 |

And by size, monolithic on `global`: **0.08 at S = 10**, zero at every other
size. S = 10 is a **ten-row** table that fits whole in the window of any model
in the pool.

The twelve cells of the grid read between 0.000 and 0.083 on `global`. There is
no curve. There is nothing to measure.

## 3. Why the control read zero

The declared control was the `local` questions: if fragment size moves accuracy
on a named row, what is broken is in the pipeline. It read **+0.000**.

It read zero because **both ends were at the floor**. A paired difference
between two fragmentations that score zero and zero is zero, and it is zero
whether the pipeline is sound or broken.

**A control that passes at the floor is not a control.**

That is the defect, and it belongs to the pre-registration, not to the run:
four refutation conditions written before looking at data, and none that asked
whether the instrument has any dynamic range. The run did exactly what it was
asked and reported it exactly as it was asked to.

## 4. It is not the format, and it is not the corpus

The probe on `lc_010_00` — ten rows, the easiest task in the design — closes
both alternative hypotheses at once.

**The model follows the format instruction to the letter:**

```
[01] seals
[02] Eastdock
[03] 3053
[04] 3
[05] 4
```

**`extract_items` pulls all five ids with their five values, losing none.**
There is no label misalignment. The shape `given='[03] 215'` I saw in the
artefacts was an artefact of truncation to 80 characters, not a parsing defect
— and saying so corrects what I wrote before looking.

**The key is correct.** Checked by hand against the material: `R-002` has
`on_hand=570`; the sum of the ten rows is 5889; the largest `on_hand` is 979 at
`R-007`; no row has `on_hand` below its own `reorder_at`, which is why the
count is 0. All five key values are the right ones.

**The grading is sound.** A perfect answer built from the key scores 100 % on
all 72 documents. That is a test, not an opinion, and it stays in the suite.

So it is capability. But the shape of the failure matters more than the label:

| question | asks for | answered |
|---|---|---|
| `[01]` local | `on_hand` of `R-002` → 570 | `seals` |
| `[03]` global | the sum of ten numbers → 5889 | 3053 |
| `[04]` global | the row id with the largest `on_hand` → `R-007` | `3` |
| `[05]` global | how many rows meet a threshold → 0 | 4 |

`[01]` and `[04]` are not arithmetic errors. In `[01]` the model returned the
**category** instead of the `on_hand`; in `[04]` it returned a bare number where
a row id was asked for. On a row like
`R-002 | Northgate | seals | on_hand=570 | reorder_at=175`, the model is not
locating the field it is being named.

That points at the **difficulty per row**, not at the difficulty of the
question. The generator already treats the two as separate dials — that was the
declared intent: *more rows is more material without changing the difficulty
per row* — but nobody calibrated the second before building the grid on the
first.

## 5. The condition that was missing

`BASELINE_FLOOR = 0.20`. If the monolithic arm scores below that on `global`,
no figure in the run speaks about L.

Evaluated against this same run, it fires:

> PISO DEL BASELINE: el brazo monolítico acierta 1/72 = 0.014 en preguntas
> globales, por debajo de 0.2.

It was added **after** seeing the data, and that is written into the
pre-registration with its date and its reason. It does not rescue this run and
changes no verdict — there was none — and it governs from the next one.

## 6. What comes next

**The check the pre-registration should have demanded before the grid was
built:** a design that varies X has to show first that the instrument responds.
It was not there, and that is this run's methodological lesson.

```bash
python3 scripts/probe_lcurve.py --calibrate
```

Monolithic, S = 10, the five families of the pool, over the four dev documents
of that size. Twenty calls. It answers one question: **does any family clear
the floor of 0.20 at the easiest point of the design?**

- **If one clears it:** the floor is not the whole pool and the corpus is fine.
  The repair is in which models are used, and the grid can be re-run as it is.
- **If none clears it:** this corpus cannot measure L with this pool, and more
  runs will not fix it. The difficulty **per row** has to come down — a
  material format that does not require locating one field among five — and it
  has to be **calibrated again before** another grid is built. The axis under
  test is still L; what is adjusted is what surrounds L.

What does **not** come next is `lcurve-final`. The split is still unused, and
that is the one asset of this run worth keeping intact.

## 7. A correction about this same page

The first version of `--calibrate` read the family pool from the backend, which
is empty outside a tier. It silently degraded to **one** family
(`llama3.2:3b`, 0/12 on `global` and 2/8 on `local` over ten-row tables) and
then printed a conclusion about *the whole pool*.

That figure is real and it is bad, but it is **one** family out of five. The
conclusion it printed was not supported by what it measured.

It is the same defect this page describes in the control: a check that claims
more than it measured. That it appeared twice in one day, the second time in
the code written to catch the first, says something about how easily it slips
in.

Fixed in two places:

- The probe derives the pool from `MODELS_DEFAULT` in `scripts/run_ollama.sh`,
  where it lives, rather than copying it or accepting whatever it is handed.
- With fewer than two families it **refuses** instead of concluding, and says
  how to give it the pool.

Two tests hold it: one that the derivation returns the five distinct families,
one that with a single family the calibration returns a failure rather than a
verdict.

The calibration **has still not been run**. What is known today is that one
family of five is at the floor.
