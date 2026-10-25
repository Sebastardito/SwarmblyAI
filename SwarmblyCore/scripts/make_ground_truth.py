#!/usr/bin/env python3
"""Generate ``prompts/ground_truth.json`` -- the V3c calibration corpus.

Run it to regenerate; the output is committed so a reader can grade by hand
without running anything. Deterministic: one fixed seed, integer arithmetic, no
wall-clock. The same seed must give the same corpus byte for byte, or the
calibration numbers stop being comparable across runs.

Why this corpus is built rather than borrowed
--------------------------------------------

A public benchmark would carry more authority, and for a headline result it
should be used. It cannot be used *first*: this experiment needs per-item
answers inside a single batch request, so that ``k`` replicas of one micro-task
can be aligned and each aligned unit graded against a key. Almost no public set
is shaped that way, and reshaping one silently changes what it measures. A
purpose-built corpus keeps the shape honest and the grading mechanical; the next
step after a clean run is to reproduce it on a public set.

What changed after the run of 24 August 2026
--------------------------------------------

That run graded 176 items and returned AUC 0.468, 95 % CI [0.368, 0.567] -- a
null, but on an instrument with two visible defects, so not an answer. Three
things changed here in response.

**Difficulty is now an explicit factor, not a hope.** The first corpus mixed
difficulty across five families and got 1.6 % accuracy on two-step arithmetic
and 69 % on threshold decisions -- a spread so wide that the pooled number was
meaningless and most per-category cells were too thin to read. Each family now
ships three graded levels in separate prompts, so difficulty is a column you can
group by. This matters for the actual question: if agreement predicts
correctness anywhere, it should be in the middle of the range. Where every model
is right, there is nothing to discriminate; where every model is wrong, likewise.
A calibration that cannot separate those regions cannot find the signal even if
it is there.

**Every key entry carries its source line.** The grader uses it to tell a
restatement from an answer. In the last run a model replied to item 01 with the
item, copied back; numeric grading took the last number it found and scored the
item *wrong* rather than *unanswered*, which deflated accuracy and filled the
error class the flagging metric exists to catch.

**Answers are asked for in a form that survives segmentation.** The last run lost
73 % of its control category because ``1. Osaka`` splits at the full stop into a
label with no answer and an answer with no label. The pipeline now segments
answer sheets by line, and the format rule asks for the bracketed style that
never split.

Every prompt encloses its data. That is the opposite of the rule for
``prompts.json``, and deliberately so: there, a prompt names a corpus it does not
enclose to stay inside the token band the coherence-tax sweep needs. Here there
must be a fact of the matter, so the facts travel with the question.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20260824
N_ITEMS = 10          # per (family, level)
LEVELS = (1, 2, 3)
OUT = Path(__file__).resolve().parent.parent / "prompts" / "ground_truth.json"

FORMAT_RULE = (
    # No literal placeholder word here. The earlier rule read 'formatted exactly as "[NN] answer"'
    # and models copied the word: 8.8 % of fragmented items came back as "answer Osaka", the right
    # content graded wrong for its wrapper.
    "Give one line per item. Begin the line with the item number in square brackets, exactly as "
    "given, then a single space, then the value. Emit the value only: no working, no "
    "restatement of the item, no units unless the item asks for them, and no commentary before "
    "or after the list. Items are independent: the answer to one must not depend on the answer "
    "to any other, and you must not reconcile them against each other."
)

CITIES = ["Quito", "Saskatoon", "Lisbon", "Osaka", "Nairobi", "Valparaiso", "Tromso", "Cebu",
          "Bergen", "Mendoza", "Kaunas", "Hobart"]
GOODS = ["cable reels", "valve kits", "pump seals", "filter packs", "gasket sets", "relay boards"]
STATUSES = ["cleared", "held", "in transit", "returned", "inspected"]


def _entry(expected: str, mode: str, level: int, source: str) -> dict:
    return {"expected": expected, "mode": mode, "level": level, "source": source}


def _spec(fid: str, category: str, level: int, instruction: str, rows: list[str], key: dict,
          notes: str) -> dict:
    return {
        "id": f"{fid}_L{level}",
        "category": category,
        "level": level,
        "expected_decomposable": True,
        "prompt": instruction + "\n\n" + "\n".join(rows) + "\n\n" + FORMAT_RULE,
        "key": key,
        "notes": notes,
    }


# --------------------------------------------------------------------------- #
# families. Each returns one prompt per level; the task stays the same and only
# the number of steps, the precision demanded, or the amount of distraction
# moves. Changing the *task* between levels would make the level a confound.
# --------------------------------------------------------------------------- #

def arith_orders(rng: random.Random, level: int) -> dict:
    rows, key = [], {}
    for i in range(1, N_ITEMS + 1):
        crates, per = rng.randint(7, 39), rng.randint(6, 24)
        if level == 1:
            src = f"[{i:02d}] {crates} crates of {rng.choice(GOODS)}, {per} units per crate"
            answer = crates * per
        elif level == 2:
            removed = rng.randint(1, 5) * per
            src = (f"[{i:02d}] {crates} crates of {rng.choice(GOODS)}, {per} units per crate, "
                   f"{removed} units removed for inspection")
            answer = crates * per - removed
        else:
            removed, returned = rng.randint(1, 5) * per, rng.randint(2, 9)
            src = (f"[{i:02d}] {crates} crates of {rng.choice(GOODS)}, {per} units per crate, "
                   f"{removed} units removed for inspection, {returned} units returned to stock")
            answer = crates * per - removed + returned
        rows.append(src)
        key[f"{i:02d}"] = _entry(str(answer), "numeric", level, src)
    steps = {1: "one multiplication", 2: "a multiplication and a subtraction",
             3: "a multiplication, a subtraction and an addition"}[level]
    return _spec("gt_arith", "arithmetic", level,
                 "For each consignment below, give the number of units available for dispatch. "
                 "Give an integer.", rows, key,
                 f"Integer arithmetic, {steps}. The step count is the only thing that moves "
                 "between levels.")


def unit_convert(rng: random.Random, level: int) -> dict:
    rows, key = [], {}
    for i in range(1, N_ITEMS + 1):
        if level == 1:
            metres = rng.randint(2, 40) * 1000
            src, answer = f"[{i:02d}] {metres} m", str(metres // 1000)
        elif level == 2:
            metres = rng.randint(120, 9800)
            src, answer = f"[{i:02d}] {metres} m", f"{metres / 1000:.3f}"
        else:
            grams = rng.randint(1250, 98000)
            src, answer = f"[{i:02d}] {grams} g", f"{grams / 1000:.2f}"
        rows.append(src)
        key[f"{i:02d}"] = _entry(answer, "numeric", level, src)
    asks = {1: "Convert each length from metres to kilometres. The answers are whole numbers; "
               "give an integer, with no unit symbol.",
            2: "Convert each length from metres to kilometres. Give the value to exactly three "
               "decimal places, with no unit symbol.",
            3: "Convert each mass from grams to kilograms, rounded to exactly two decimal "
               "places, with no unit symbol."}[level]
    return _spec("gt_convert", "unit_conversion", level, asks, rows, key,
                 "Single-step conversion. Level moves the precision demanded, which is where "
                 "most failures come from rather than the arithmetic.")


def date_offset(rng: random.Random, level: int) -> dict:
    rows, key = [], {}
    for i in range(1, N_ITEMS + 1):
        if level == 1:
            start = date(2026, rng.randint(1, 12), rng.randint(1, 10))
            offset = rng.randint(3, 17)          # stays inside the month
        elif level == 2:
            start = date(2026, rng.randint(1, 11), rng.randint(18, 28))
            offset = rng.randint(9, 30)          # crosses one boundary
        else:
            start = date(2026, rng.randint(1, 8), rng.randint(15, 28))
            offset = rng.randint(64, 120)        # crosses several
        src = f"[{i:02d}] shipped {start.isoformat()}, transit {offset} days"
        rows.append(src)
        key[f"{i:02d}"] = _entry((start + timedelta(days=offset)).isoformat(), "date_iso", level, src)
    crossings = {1: "no month boundary", 2: "one month boundary", 3: "two or more"}[level]
    return _spec("gt_date", "date_arithmetic", level,
                 "For each shipment below, give the arrival date: the shipping date plus the "
                 "transit days. Answer in ISO 8601 form, YYYY-MM-DD.", rows, key,
                 f"Calendar arithmetic crossing {crossings}. Unambiguous to grade.")


def field_lookup(rng: random.Random, level: int) -> dict:
    rows, key = [], {}
    for i in range(1, N_ITEMS + 1):
        city = rng.choice(CITIES)
        ref = f"{rng.choice('ABCDEFGH')}{rng.randint(1000, 9999)}"
        if level == 1:
            src = f"[{i:02d}] ref {ref} | destination {city}"
        elif level == 2:
            src = (f"[{i:02d}] ref {ref} | origin {rng.choice(CITIES)} | destination {city} | "
                   f"customs {rng.choice(STATUSES)} | weight {rng.randint(40, 900)} kg")
        else:
            other = rng.choice([c for c in CITIES if c != city])
            src = (f"[{i:02d}] ref {ref} | origin {other} | routed via {other} | destination "
                   f"{city} | customs {rng.choice(STATUSES)} | consignee office {other} | "
                   f"weight {rng.randint(40, 900)} kg")
        rows.append(src)
        key[f"{i:02d}"] = _entry(city, "exact_norm", level, src)
    distract = {1: "one field", 2: "five fields", 3: "seven fields, three of them naming a "
                                                     "different city"}[level]
    return _spec("gt_lookup", "field_extraction", level,
                 "For each record below, give the destination city and nothing else. Copy it "
                 "exactly as written in the record.", rows, key,
                 f"Extraction from {distract}. Level 1 is the control: a model that fails it has "
                 "not read the record, and the run is measuring the pipeline rather than the "
                 "models.")


def threshold_check(rng: random.Random, level: int) -> dict:
    rows, key = [], {}
    limit = 500
    for i in range(1, N_ITEMS + 1):
        if level == 1:
            weight = rng.choice([rng.randint(180, 380), rng.randint(620, 880)])
            src = f"[{i:02d}] pallet {rng.choice('PQRSTU')}{rng.randint(100, 999)}, {weight} kg"
            answer = weight > limit
        elif level == 2:
            weight = rng.randint(470, 530)
            src = f"[{i:02d}] pallet {rng.choice('PQRSTU')}{rng.randint(100, 999)}, {weight} kg"
            answer = weight > limit
        else:
            weight, status = rng.randint(470, 530), rng.choice(STATUSES)
            src = (f"[{i:02d}] pallet {rng.choice('PQRSTU')}{rng.randint(100, 999)}, {weight} kg, "
                   f"customs {status}")
            answer = weight > limit and status == "cleared"
        rows.append(src)
        key[f"{i:02d}"] = _entry("true" if answer else "false", "boolean", level, src)
    asks = {1: f"For each pallet below, answer whether its weight exceeds the {limit} kg limit.",
            2: f"For each pallet below, answer whether its weight exceeds the {limit} kg limit.",
            3: f"For each pallet below, answer whether it may ship: it may ship only if its "
               f"weight exceeds the {limit} kg consolidation floor AND its customs status is "
               f"cleared."}[level]
    return _spec("gt_threshold", "threshold_decision", level,
                 asks + " Answer exactly \"true\" or \"false\".", rows, key,
                 {1: "Values far from the limit.", 2: "Values within 30 kg of the limit, so "
                     "guessing does not pay.", 3: "Two conditions conjoined."}[level])


FAMILIES = (arith_orders, unit_convert, date_offset, field_lookup, threshold_check)


def main() -> None:
    rng = random.Random(SEED)
    prompts = [family(rng, level) for family in FAMILIES for level in LEVELS]
    payload = {
        "_about": (
            "Ground-truth corpus for the V3c agreement calibration specified in Section 11.4 of "
            "the whitepaper. Each prompt is a batch of independent items with a canonical answer, "
            "so that k replicas of one micro-task can be aligned and each aligned unit graded "
            "against a key by swarmbly_v0.grading -- no judge, no embeddings, no model in the "
            "verdict."
        ),
        "_why_ground_truth": (
            "The calibration of 14 August 2026 reported r = -0.030 between agreement and judged "
            "acceptability and could not interpret it: the judge accepted 93.3 % of everything, so "
            "the dependent variable had no variance. Replacing the judge with an answer key fixed "
            "that -- accuracy on 24 August was 23.3 % -- but that run had its own defects and is "
            "not an answer either. See _what_changed."
        ),
        "_levels": (
            "Every family ships three levels as separate prompts, with the task held constant and "
            "only the step count, the precision demanded, or the amount of distraction moving. "
            "Level is an experimental factor, not decoration: if agreement predicts correctness "
            "anywhere it should be mid-range, because where every model is right there is nothing "
            "to discriminate and where every model is wrong, likewise. gt_lookup_L1 is the "
            "control -- a model that fails it has not read the record, and the run is measuring "
            "the pipeline rather than the models."
        ),
        "_what_changed": (
            "After the run of 24 August 2026 (AUC 0.468, CI [0.368, 0.567], on 176 graded items): "
            "(1) three levels per family replace mixed difficulty, which had produced 1.6 % "
            "accuracy on two-step arithmetic against 69 % on threshold decisions and cells too "
            "thin to read; (2) every key entry now carries its source line, so the grader can tell "
            "a restatement from an answer -- previously a model that copied the item back was "
            "scored wrong rather than unanswered; (3) the format rule asks for the bracketed "
            "style, and the pipeline segments answer sheets by line, because '1. Osaka' split at "
            "the full stop and cost the control category 73 % of its items."
        ),
        "_enclosure_note": (
            "Unlike prompts.json, every prompt here encloses its data. There the rule is the "
            "opposite: a prompt names a corpus it does not enclose, to stay inside the token band "
            "the coherence-tax sweep needs. Here there has to be a fact of the matter, so the "
            "facts travel with the question. Do not merge the two files."
        ),
        "_format": (
            "Answers are keyed as [NN]. swarmbly_v0.grading.extract_items parses them, tolerating "
            "(07) and 07. as well. A unit with no parsable label is counted as unlabelled and "
            "reported, never dropped silently."
        ),
        "_generator": (
            f"scripts/make_ground_truth.py, seed {SEED}, {len(FAMILIES)} families x "
            f"{len(LEVELS)} levels x {N_ITEMS} items"
        ),
        "prompts": prompts,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    total = sum(len(p["key"]) for p in prompts)
    print(f"wrote {OUT} -- {len(prompts)} prompts, {total} graded items")


if __name__ == "__main__":
    main()
