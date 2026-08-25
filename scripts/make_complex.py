#!/usr/bin/env python3
"""Generate the V4 corpus: long prose, enclosed tables, and dependency chains.

Why a fourth corpus
-------------------

The three that exist each answer one question and cannot answer this one.

``prompts.json`` is 124-160 canonical tokens per prompt. Sweeping N from 2 to 8
over it produces fragments of 133 down to 33 tokens -- so the interesting end of
the fragment-size curve, the part *above* 133 tokens where the cost was still
falling, has never been reachable. A corpus that cannot express the independent
variable cannot measure it.

``ground_truth.json`` and ``free_form.json`` grade short answers, where two
independent nodes writing "830" agree trivially. Six runs saturated the
agreement predictor at 0.85-0.96 for exactly this reason.

So this corpus is built to three specifications, each aimed at a failure the
previous runs actually produced:

**Long enough to sweep.** 231-356 canonical tokens, so N in (2, 4, 8, 16) spans
roughly 14 to 178 tokens per fragment. The top of that range is above the 133
tokens that was V0's widest fragment -- the point where its curve was still
falling when the corpus ran out of prompt -- so for the first time the sweep has
observations on both sides of the plausible knee.

**Enclosed data, never named data.** Every figure a correct answer may state is
*in* the prompt. The deixis rule from `_corpus_note` is inverted here on purpose:
the earlier corpora name a corpus they do not enclose, which is what keeps them
short; these enclose theirs, which is what makes per-figure grading possible.

**Three task shapes, because S* should not be one number.** The claim under test
is that the effective fragment is a *semantic unit*, not a token count -- so it
should differ by shape:

* ``long_prose`` -- the unit is a topic. Fragments should degrade gracefully.
* ``table_summary`` -- the unit is a row group. A fragment holding half a table
  can still summarise its half.
* ``dependency_chain`` -- the unit is a step, and steps are *not* independent:
  step 3 consumes step 2's output. This is the axis the orchestrator cannot
  currently fragment along, and the prediction is that it degrades far faster in
  N than the other two.

Every answer key here is computed by this script from the same numbers the
prompt encloses, so no key can drift from its prompt.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarmbly_v0.constraints import derived_aggregates  # noqa: E402
from swarmbly_v0.textutil import count_tokens  # noqa: E402

SEED = 20260826

DEPOTS = ["Ostend", "Valparaiso", "Tromso", "Saskatoon", "Cebu", "Quito",
          "Osaka", "Nairobi", "Lisbon", "Hobart", "Bergen", "Recife",
          "Gdansk", "Mombasa", "Halifax", "Trieste", "Busan", "Antofagasta",
          "Reykjavik", "Durban", "Split", "Nantes"]
GOODS = ["valve kits", "cable reels", "pump seals", "filter packs",
         "gasket sets", "drive belts", "bearing sets", "relay boards"]
TOPICS = [
    ("harbour scheduling", "a duty manager at a small commercial harbour",
     ["tide window", "berth", "manifest", "pilotage"]),
    ("archive digitisation", "the head of a municipal records office",
     ["condition survey", "retention", "reading room", "provenance"]),
    ("relay maintenance", "the supervisor of a rural signalling network",
     ["battery", "line fault", "inspection round", "spare inventory"]),
    ("cold-chain handover", "the night supervisor at a regional depot",
     ["temperature log", "dock door", "seal record", "excursion window"]),
    ("survey fieldwork", "the coordinator of a two-team field survey",
     ["control point", "instrument drift", "field book", "reoccupation"]),
    ("kiln scheduling", "the works manager of a small ceramics plant",
     ["firing curve", "shelf position", "kiln log", "cooling ramp"]),
    ("ferry rostering", "the operations lead of an island ferry service",
     ["crew rest", "sailing slot", "roster board", "relief cover"]),
    ("herbarium intake", "the curator of a regional herbarium",
     ["accession", "mounting sheet", "loan register", "quarantine"]),
]
"""Eight topics rather than three.

V4 left long_prose and table_summary plausibly under the 5 % threshold at the
widest fragment -- point estimates of +4.2 % and +3.1 % -- with intervals too
wide to conclude anything: 12 observations per cell gave a 95 % CI running from
-3.5 % to +10.3 %. Nothing about the design needs changing to settle that, only
the count. Eight prompts per shape at two rho values and two k values is 32
observations per cell, which shortens the interval by roughly the square root of
that ratio."""


def _rows(rng: random.Random, n: int) -> list[dict]:
    depots = rng.sample(DEPOTS, n)
    return [
        {"ref": f"{rng.choice('ABCDEFGH')}{rng.randint(1000, 9999)}",
         "destination": depot,
         "weight": rng.choice(range(120, 960, 5)),
         "goods": rng.choice(GOODS)}
        for depot in depots
    ]


def _table(rows: list[dict]) -> str:
    lines = ["  ref | destination | weight | goods"]
    lines += [f"  {r['ref']} | {r['destination']} | {r['weight']} kg | {r['goods']}"
              for r in rows]
    return "\n".join(lines)


def long_prose(rng: random.Random) -> list[dict]:
    """Topic-structured prose. The semantic unit is a topic, and there are six.

    Six named aspects rather than a free brief: it gives the planner something a
    semantic segmenter could cut along, and it gives the constraint checker
    something to count. A prompt that says only "write about harbours" cannot
    distinguish a good fragmentation from a bad one.
    """
    out = []
    for topic, audience, terms in TOPICS:
        aspects = [
            (f"what {terms[0]} constrains, why it cannot be worked around, and what "
             f"happens to the day's plan when it closes earlier than forecast, given "
             f"that the site is staffed thinly enough that one absence changes what "
             f"can be attempted at all"),
            (f"how {terms[1]} is allocated when demand exceeds supply, who arbitrates "
             f"between competing claims, and what makes an allocation final"),
            (f"what the {terms[2]} records, who reads it, how often it is reconciled "
             f"against what actually happened, and what a discrepancy triggers"),
            (f"how {terms[3]} changes the ordering of work, and which decisions must be "
             f"revisited once it changes rather than merely noted"),
            ("which failures are recoverable within a shift and which are not, and how "
             "that distinction is made in the moment rather than in hindsight"),
            ("what a handover to the next shift must contain for the incoming staff to "
             "act without re-deriving the day, what is safe to leave out, and where "
             "judgement rather than rule decides -- naming whose judgement and what "
             "they weigh"),
            ("what a newcomer reliably gets wrong in the first month, and which of "
             "those mistakes the process absorbs versus which one propagates"),
            ("what would have to change for the site to run a third shift, and which "
             "current practice would stop working first"),
        ]
        # Deliberately short. Whatever stands before the first item is the
        # preamble, and split_enumerated copies the preamble into *every* packet
        # -- so a long shared context multiplies by N and is exactly what raises
        # rho_floor. A first draft of this corpus carried a six-line preamble and
        # the sweep came back with rho_floor 2.92 against a target of 1.5, every
        # cell unreachable. Length belongs in the items, which are divisible.
        context = "The site runs two shifts and keeps its own records."
        body = "\n".join(f"  [{i:02d}] {a}" for i, a in enumerate(aspects, 1))
        prompt = (
            f"Write a briefing on {topic} for {audience}. Cover each of the eight "
            f"aspects below, in the order given, devoting one paragraph to each.\n\n"
            f"{context}\n\n"
            f"{body}\n\n"
            f"Write exactly eight paragraphs separated by blank lines, each between 70 and "
            f"130 words. Mention {terms[0]!r} exactly once and {terms[2]!r} exactly once. "
            f"Do not repeat any sentence, and do not repeat any phrase of eight words or "
            f"more. Write continuous prose: no headings, no bullet points, no tables. "
            f"Do not state any numeric figure at all -- this briefing is qualitative."
        )
        out.append({
            "id": f"long_{topic.split()[0]}",
            "category": "long_prose",
            "level": 3,
            "expected_decomposable": True,
            "prompt": prompt,
            "constraints": [
                {"id": "paragraphs", "kind": "paragraph_count", "count": 8},
                {"id": "length", "kind": "words_per_paragraph", "min": 70, "max": 130},
                {"id": f"{terms[0].split()[0]}_once", "kind": "term_once", "term": terms[0]},
                {"id": f"{terms[2].split()[0]}_once", "kind": "term_once", "term": terms[2]},
                {"id": "mentions_handover", "kind": "must_mention", "term": "handover"},
                {"id": "no_repeated_sentence", "kind": "no_repeated_sentence"},
                {"id": "no_repeated_phrase", "kind": "no_repeated_ngram", "size": 8},
            ],
            "notes": ("Eight topics, one paragraph each. The semantic unit is a topic, so "
                      "N=8 should be the cheapest fragmentation and any larger N must "
                      "split inside a topic. Eight rather than six so that every shape "
                      "in this corpus reaches N=8 and the curve compares like with like."),
        })
    return out


def table_summary(rng: random.Random) -> list[dict]:
    """A twelve-row table, enclosed. The semantic unit is a row group."""
    out = []
    for name in ("manifest", "backlog", "dispatch", "intake", "transit",
                 "holdover", "consolidation", "clearance"):
        rows = _rows(rng, 20)
        weights = [float(r["weight"]) for r in rows]
        allowed = sorted(set(weights) | derived_aggregates(weights))
        heaviest = max(rows, key=lambda r: r["weight"])
        prompt = (
            f"Summarise the {name} table below for a duty manager.\n\n"
            f"{_table(rows)}\n\n"
            f"Write exactly four paragraphs separated by blank lines, each between 70 and "
            f"130 words. Name the heaviest consignment and give the total weight, each "
            f"exactly once. Every figure you state must come from the table above or be an "
            f"arithmetic aggregate of it -- a total, a count, an average, the heaviest or "
            f"the lightest. Do not estimate and do not round to a figure the table does not "
            f"support. Write continuous prose only: do not reproduce the table, do not emit "
            f"rows or pipe characters, and do not use bullet points or headings. Do not "
            f"repeat any sentence or any phrase of eight words or more."
        )
        out.append({
            "id": f"table_{name}",
            "category": "table_summary",
            "level": 3,
            "expected_decomposable": True,
            "prompt": prompt,
            "constraints": [
                {"id": "paragraphs", "kind": "paragraph_count", "count": 4},
                {"id": "length", "kind": "words_per_paragraph", "min": 70, "max": 130},
                {"id": "mentions_total", "kind": "must_mention", "term": "total"},
                {"id": "heaviest_once", "kind": "term_once", "term": "heaviest"},
                {"id": "no_repeated_sentence", "kind": "no_repeated_sentence"},
                {"id": "no_repeated_phrase", "kind": "no_repeated_ngram", "size": 8},
            ],
            "numeric_facts": {
                "allowed": allowed,
                "total": sum(weights),
                "heaviest_ref": heaviest["ref"],
            },
            "notes": ("Twenty rows so a fragment can hold a coherent subset at every N in the "
                      "sweep, including N=8. Every figure "
                      "in allowed[] is either a row or a legitimate aggregate, so a "
                      "sentence citing the table correctly cannot be graded a fabrication."),
        })
    return out


def dependency_chain(rng: random.Random) -> list[dict]:
    """A chain where step i consumes step i-1's output.

    The axis the orchestrator cannot fragment along, and the one the whole
    dependency question turns on. Each step is checkable because this script
    computes it, so a run can say *which* step the chain broke at rather than
    only that the final figure was wrong.

    The arithmetic is deliberately simple, and the first draft was not simple
    enough. It put a percentage reduction at step 2 and a percentage increase at
    step 5, and the run of 25 August scored those two steps at **3.6 % and
    0.0 %** against 58 % and 51 % for the division and addition around them. Two
    of eight steps were unanswerable by these models regardless of what the
    packet contained -- and sitting at positions 2 and 5 they poisoned every step
    downstream, which is most of the chain.

    That makes a corpus a bad instrument for the question it exists to ask. A
    carry can only be measured by whether a *carriable* value survives a packet
    boundary; a step the model could not compute while holding the entire prompt
    says nothing about carrying. So every operation here is now one the 2-4B
    class demonstrably performs -- add, subtract, multiply by a small integer,
    divide with no remainder -- and the rebate is nudged so step 3's division
    comes out whole without introducing a rounding rule.

    Two invariants, both enforced by tests rather than by hope: the chain is
    strictly linear, step i naming step i-1, and no two intermediates coincide.
    A repeated value would let a model that merely echoes an earlier step score a
    later one right by accident, which is precisely the reading that would make a
    broken carry look like a working one.
    """
    out = []
    for name in ("ardent", "northwind", "meridian", "kestrel"):
        steps = None
        for _attempt in range(400):
            candidate = _chain_steps(rng)
            values = [value for _, value in candidate]
            if len(set(values)) == len(values):
                steps = candidate
                break
        if steps is None:  # pragma: no cover - 400 draws without a clean chain
            raise RuntimeError(f"could not build a collision-free chain for {name}")

        body = "\n".join(f"  [{i:02d}] {text}" for i, (text, _) in enumerate(steps, 1))
        prompt = (
            f"Work through the {name.title()} costing chain below, one step at a time. "
            f"Every figure given is exact and every division comes out whole; no step "
            f"requires rounding.\n\n"
            f"{body}\n\n"
            f"Each step uses the numeric result of the step before it, so you must carry "
            f"every intermediate value forward explicitly. Give one line per step, as [NN] "
            f"followed by the value alone."
        )
        out.append({
            "id": f"chain_{name}",
            "category": "dependency_chain",
            "level": 3,
            "expected_decomposable": True,
            "prompt": prompt,
            "key": {
                f"{i:02d}": {"expected": str(value), "mode": "numeric", "level": i,
                             "source": text}
                for i, (text, value) in enumerate(steps, 1)
            },
            "notes": ("Depth 8, strictly linear, every intermediate distinct. Step i is "
                      "unanswerable without step i-1, so a partition that puts them in "
                      "different packets must either carry the value or fail. Which step "
                      "fails is the measurement."),
        })
    return out


def _chain_steps(rng: random.Random) -> list[tuple[str, int]]:
    """One candidate chain: eight linear steps, exact arithmetic throughout."""
    weeks = rng.choice((2, 4, 5))
    depots_n = rng.choice((2, 3, 4))
    price = rng.choice(range(6, 20, 2))
    units = rng.choice(range(20, 90))
    fee = rng.choice(range(50, 200, 25))
    uplift = rng.choice(range(20, 120, 20))
    reserve = rng.choice(range(10, 50, 10))

    gross = units * price
    rebate = rng.choice(range(10, 60, 10))
    rebate += (gross - rebate) % weeks  # keeps step 3 exact, no rounding rule

    net = gross - rebate
    weekly = net // weeks
    final = weekly + fee
    loaded = final + uplift
    fleet = loaded * depots_n
    allocation = fleet - reserve

    return [
        (f"Multiply {units} units by the unit price of {price} to get the gross value.",
         gross),
        (f"Subtract the fixed rebate of {rebate} from the gross value in step 1 to get "
         f"the net value.", net),
        (f"Divide the net value from step 2 by {weeks} weeks to get the weekly figure. "
         f"The division is exact.", weekly),
        (f"Add the fixed handling fee of {fee} to the weekly figure from step 3 to get "
         f"the loaded weekly figure.", final),
        (f"Add the fixed uplift of {uplift} to the loaded weekly figure from step 4 to "
         f"get the surcharged figure.", loaded),
        (f"Multiply the surcharged figure from step 5 by the {depots_n} depots to get "
         f"the fleet figure.", fleet),
        (f"Subtract the reserve of {reserve} from the fleet figure in step 6 to get the "
         f"allocation.", allocation),
        (f"Add the rebate of {rebate} back to the allocation from step 7 to get the "
         f"total.", allocation + rebate),
    ]



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="prompts/complex.json")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    prompts = long_prose(rng) + table_summary(rng) + dependency_chain(rng)

    sizes = [count_tokens(p["prompt"]) for p in prompts]
    payload = {
        "_seed": args.seed,
        "_length_note": (
            f"Canonical tokens per prompt: min {min(sizes)}, max {max(sizes)}, "
            f"mean {sum(sizes) // len(sizes)}. Long on purpose. The fragment-size sweep "
            f"needs prompts big enough that N in (2,4,8,16) produces fragments spanning "
            f"roughly 25 to 350 tokens, and the earlier corpora at 124-160 tokens could "
            f"not reach the upper half of that range at all."
        ),
        "_corpus_note": (
            "Every figure a correct answer may state is enclosed in its prompt, which is "
            "the opposite of prompts.json and is what makes per-figure grading possible "
            "here. Three shapes -- long_prose, table_summary, dependency_chain -- because "
            "the claim under test is that the effective fragment is a semantic unit rather "
            "than a token count, and a semantic unit differs by shape: a topic, a row "
            "group, a step. dependency_chain is the only one whose units are ordered, and "
            "the prediction is that it degrades fastest in N."
        ),
        "prompts": prompts,
    }
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {path} ({len(prompts)} prompts, {min(sizes)}-{max(sizes)} canonical tokens)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
