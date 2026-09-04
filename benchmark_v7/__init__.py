"""V7 — the frozen benchmark. Deliberately separate from the diagnostic harness.

V0 through V6 were a cumulative line of research and they earned their keep by
finding real instrument defects: a grader that inverted a baseline, a contract
that never reached a fragment, a coherence metric that was not arm-neutral, a
packing floor that disagreed with its own definition. That is what a laboratory
is for. It is not what evidence looks like, because the corpus, the metrics, the
contracts and the criteria all moved while the questions were being asked.

So this package is a benchmark, not a laboratory:

* **Its own instances**, generated from a fact graph with canonical answers and
  full traceability, so that for every claim a grader can say whether it is
  correct, whether the worker had the data needed to produce it, and which
  packet was supposed to carry that data.
* **Its own evaluator**, which does NOT import ``swarmbly_v0.metrics``. That is
  the single most important boundary here. The defect that cost this project
  four documents was a scorer whose behaviour depended on metadata about the
  partition; a benchmark sharing that scorer inherits the risk. The first test
  in ``test_evaluate.py`` is the arm-neutrality invariant.
* **A minimal runner** over the protocol's public interfaces. Router, packing,
  assembler and consensus are reused, not rewritten -- and the runner therefore
  lives in ``scripts/run_benchmark_v7.py``, **outside this package**, because a
  file inside it may not import any of them. Read together with the bullet
  above that looks like a contradiction, and the first person to hit
  ``test_the_benchmark_does_not_import_the_harness_it_is_checking`` will be
  tempted to widen the ban. They should not: the *benchmark* must be able to
  disagree with the harness, and the *runner* must drive the shipped protocol
  and nothing else. Those are different requirements and they need different
  files. ``test_the_runner_is_outside_the_package_and_stays_there`` states the
  intended shape so that the tempting repair is obviously wrong.

What V7 can and cannot establish
--------------------------------

A fact-graph corpus is synthetic and its answers are canonical by construction.
That is what makes it measurable, and it is also the limit. V7 can establish
**the protocol does not lose information it was given**; it cannot establish
**the protocol works on your documents**. This is stated here, before the first
result, so that it is a property of the design rather than a caveat added under
pressure.

The arms
--------

``monolithic``      the model's ceiling on this instance.
``oracle``          fragmented, every packet handed exactly the facts its task
                    needs. Whether the partition is viable *in principle*.
``real``            fragmented through router, packer and assembler.
``real+carry``      the causal effect of state transport.
``real+editor``     the causal effect of formal repair.

There is deliberately no consensus arm. The confidence map was declared, tested
and failed three times -- odds ratios of 3.47, 0.26 and 1.24 with an interval
straddling 1.0 on the largest sample -- and the plan's own rule was that a lift
which does not clearly exceed 1 leaves consensus as a diversity mechanism, not a
risk signal. k>1 remains available and its cost is measured; it is no longer
asked to predict error.

**The oracle arm is the point.** Every packaging failure this project spent weeks
on would have read as *oracle fine, real broken*, which localises the fault to
planning, packing or assembly in a single reading. It is implemented first.

It read exactly that, on the first instance it was pointed at. On the ``map``
class -- four independent per-section totals, the most partitionable task here
-- at rho 3.0, N=4, well above the packing floor, with a worker that answers
what it is asked and answers it correctly: monolithic 1.000, oracle 1.000, real
**0.000 coverage and 1.000 unanswerable**. The segmenter had put all four
questions in one packet and all the data in the other three, because it
partitions by position and token count and has no representation of the
dependency between a question and the material that answers it.

That is an architectural limitation rather than a bug -- ``planner._segment``
does what it documents -- and it is left unfixed on purpose, because the three
available repairs are not equivalent and choosing between them is an
architecture decision. See
``docs/FINDING_2026-09-04_segmenter_splits_question_from_data.md``.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
