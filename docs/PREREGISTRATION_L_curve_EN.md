---
status: current
lang: en
note: >
  Written before the corpus was generated and before the runner was written.
  The measurement does not exist yet.
---
# Pre-registration — the L curve

`docs/FUNDAMENTOS_2026-09-21_unidad_semantica.md` (private) proposed redesigning
the protocol's semantic unit by analogy with genomics: that there is a
**minimum fragment size** below which a piece stops being able to carry an
answer, the way a read that is too short stops being placeable in a genome. The
proposal asked for fragments of about 50 sentences.

That proposal cannot be implemented without first measuring whether the premise
holds in this architecture. This document defines that measurement, and defines
which result kills it.

---

## 1. What cannot be separated today

The harness has no fragment-size dial. It has `n_tasks`, and `_segment` splits
the material into exactly `n_tasks` groups of roughly equal token count. With
the prompt fixed, **L and N are the same variable written backwards**:
L = S / N.

Every earlier run moved N over a corpus of fixed size. So every conclusion
about N in this project's record is also a conclusion about L, and neither is
identifiable on its own.

## 2. How they separate

The `longform` corpus has a dial the earlier corpora did not: the number of
rows, `n_rows`. With material of size S and N fragments, L = S / N in rows per
fragment. Choosing S = L · N builds a complete factorial:

| | N = 2 | N = 4 | N = 8 |
|---|---|---|---|
| **L = 5** | S = 10 | S = 20 | S = 40 |
| **L = 10** | S = 20 | S = 40 | S = 80 |
| **L = 20** | S = 40 | S = 80 | S = 160 |
| **L = 40** | S = 80 | S = 160 | S = 320 |

Each L appears at three values of N and each N at four values of L, so the
effect of L is identifiable with N held fixed.

The cleanest comparison in the design is on the diagonals. **S = 40 is
fragmented at L = 5 (N = 8), L = 10 (N = 4) and L = 20 (N = 2)**: the same
document, the same questions, the same key, the same monolithic baseline, and
the only thing that changes is the fragment size. The same holds at S = 20,
S = 80 and S = 160.

## 3. What this measurement CANNOT see

Declared before running, not after reading.

An inventory row **is already the atomic unit** of this corpus. Grouping 5 or
40 rows does not change what a fragment means; it changes how much it weighs.
So this experiment measures the **mechanical component** of L — the header cost
per packet, the cost of re-integrating more pieces — and **cannot see** the
semantic component the genomic proposal asserts.

That does not invalidate it: it bounds it. The mechanical component is a
**lower bound** on the total effect of L. If not even the mechanical cost of
fragmenting into small pieces is distinguishable from zero, then "fragment size
matters" has no support at all in this architecture, and a semantic corpus —
expensive to build and to grade — is the only hope the premise has left. If the
mechanical cost is real, this curve gives its shape and its knee, which is the
number `L*` the redesign needs.

## 4. The declared cell

> **Amendment, before anything was run.** The first draft of this section
> declared the cell at a single size: S = 80, L = 40 against L = 10. With 12
> documents per size and 8 in the final half, that cell has **8 clusters**, and
> `MIN_CLUSTERS_FOR_A_VERDICT` is 20: the verdict would have been refused in
> code after the runs had been spent. It is corrected here, with the corpus
> still ungenerated and not one datum in sight.

**The within-document L contrast, pooled over the sizes that admit more than
one L, on `global` questions.**

Four sizes offer that contrast: S = 20 (L = 10 against 5), S = 40 (20 against
5), S = 80 (40 against 10) and S = 160 (40 against 20). Eight final documents
per size give **32 clusters**.

Prediction: the large L scores higher than the small L of the same document.

- **Estimator:** the per-document paired difference in accuracy on `global`
  items, between the larger-L and the smaller-L fragmentation of the **same**
  document. Same text, same questions, same key, same baseline: the only thing
  that changes is the fragment size.
- **Verdict on the LOWER bound** of a cluster bootstrap, where the cluster is
  the document. This is a claim that an effect exists, so the bound that
  decides is the lower one.
- **Threshold:** `L_CURVE_THRESHOLD_POINTS = 0.05` in accuracy. Fixed before
  seeing data, at the same value the composition criterion uses, so as not to
  invent a new threshold for convenience.
- **Cluster floor:** 20, refused in code below that.

**S = 80, L = 40 against L = 10** is still reported separately, being the
widest-range contrast in the design, but with 8 clusters it **carries no
verdict** and is printed as descriptive.

## 5. The control that has to be able to fail

**The `local` questions.**

A `local` question asks for the value of a named row. It is answered by the
fragment that contains that row, and answered just as well whether that
fragment holds 5 rows or 40. If L moves `local` accuracy, what is being
measured is not the size of the semantic unit: it is something breaking in the
pipeline — the segmenter, the router, the assembler — and the whole experiment
is invalid.

The control is declared with its own threshold: if `local` accuracy varies with
L by more than **0.05**, the run is not read.

## 6. Refutation conditions

Evaluated in code by `_invalidations()`, not in prose after the fact.

1. **Control failed.** `local` varies with L above 0.05 → invalid run, no
   figure published.
2. **Criterion NOT MET.** The lower bound of the declared cell does not exceed
   0.05 → the prediction fails in its own cell.
3. **The L axis is dead.** If at all three values of N the interval on the L
   effect contains zero, then fragment size moves nothing mechanically, and the
   genomic redesign loses its cheapest support. This is the condition that can
   kill the premise in one night.
4. **No frontier.** If every S fits under the declared node budget, the
   monolithic arm never fails and the comparison is about cost, not
   feasibility. Recorded beside the result, because it changes how it reads.

5. **Baseline at the floor.** `BASELINE_FLOOR = 0.20`. If the monolithic arm
   scores below that on `global` questions, no figure in the run speaks about
   L: with both ends at the floor, the paired difference between two
   fragmentations is noise around zero.

   > **Added on 22 September, AFTER the first run.** Said here because adding
   > a refutation condition after seeing data is exactly the freedom a
   > pre-registration exists to remove.
   >
   > `lcurve-dev` finished without firing any of the four earlier conditions
   > and with the control reading +0.000, which reads as "nothing broke". The
   > monolithic arm had scored **1 of 72** on global questions, even at S = 10
   > -- a ten-row table that fits whole in any window. The control read zero
   > because both ends were at the floor. **A control that passes at the floor
   > is not a control**, and that was the defect: four conditions and none
   > asking whether the instrument has any dynamic range.
   >
   > This condition does not rescue that run and changes no verdict -- there
   > was none, the cell was refused on cluster count. It governs from the next
   > one.

## 7. What is frozen before running

- The corpus and its SHA-256 digest, with the key inside the digest.
- The dev/final split, and the `read_dev_run` gate that already refuses a final
  without a dev.
- The code fingerprint, compared by `assert_same_code_as_dev`.
- This document.
