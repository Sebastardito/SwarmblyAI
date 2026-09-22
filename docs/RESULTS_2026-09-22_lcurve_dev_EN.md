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

## 4. What was ruled out, and with what

**The grading is sound.** A perfect answer built from each document's own key
scores **100 % on all 72 documents** in the corpus. That is not an opinion: it
is a test, and it stays in the suite. The defect that killed two feasibility
runs — the corpus writing `[Q1]` where the grader expected `01` — is not here.

**Still open** is whether the models produce correct values in a format the
extractor rejects. Among the wrong answers are shapes like `given='[03] 215'`
for a question that was not 03, which smells of label misalignment. It cannot
be decided from this run's artefacts **because it did not keep the model text**,
and that is a second defect: a run that cannot be debugged from its own output
forces a repeat in order to look at it.

Both are fixed: the runner now persists the text, and
`scripts/probe_lcurve.py` looks at one document in a single call.

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

In order, and the first is cheap:

1. `python3 scripts/probe_lcurve.py` against the real pool. One call. It
   decides whether the floor is one of capability or of format, which are two
   different repairs.
2. If it is format: fix it in the corpus or in the extractor and re-run dev. Do
   not change models over a parsing defect.
3. If it is capability: the `global` questions of this corpus — sums and counts
   over dozens of rows — are out of reach for a pool of 2–3.8 B. The question
   has to change, not the protocol: a maximum, a count under a threshold, a row
   that dominates. The axis under test is still L; what is adjusted is the
   difficulty per row, which the generator already treats as a dial separate
   from size.

What does **not** come next is `lcurve-final`. The split is still unused, and
that is the one asset of this run worth keeping intact.
