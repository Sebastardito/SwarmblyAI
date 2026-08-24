#!/usr/bin/env python3
"""Generate ``prompts/ground_truth.json`` -- the V3c calibration corpus.

Run it to regenerate; the output is committed so a reader can grade by hand
without running anything. Deterministic: one fixed seed, integer arithmetic,
no wall-clock. The same seed must give the same corpus, byte for byte, or the
calibration numbers stop being comparable across runs.

Why this corpus is built rather than borrowed
--------------------------------------------

A public benchmark would carry more authority, and for a headline result it
should be used. It cannot be used *first*, for one reason: this experiment needs
per-item answers inside a single batch request, so that ``k`` replicas of one
micro-task can be aligned and each aligned unit can be graded against a key.
Almost no public set is shaped that way, and reshaping one silently changes what
it measures. A purpose-built corpus keeps the shape honest and the grading
mechanical; the next step after this run is to reproduce it on a public set.

Why the difficulty is mixed on purpose
--------------------------------------

The previous calibration failed because the dependent variable had no variance:
the judge accepted 93.3 % of everything, so no correlation could appear whether
or not the signal existed. Repeating that with accuracy instead of acceptance
would be the same mistake in a new costume. So the five families are chosen to
land at different difficulties for a 2-3B model -- field lookup is nearly free,
two-step arithmetic and date offsets are genuinely hard -- which spreads
accuracy away from both ceiling and floor and lets Section 11.4's per-category
calibration curves actually be drawn.

Every prompt encloses its data. That is the opposite of the rule for
``prompts.json``, and deliberately so: there, a prompt names a corpus it does
not enclose to stay inside the token band the coherence-tax sweep needs. Here
there must be a fact of the matter, so the facts travel with the question.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20260816
N_ITEMS = 20
OUT = Path(__file__).resolve().parent.parent / "prompts" / "ground_truth.json"

FORMAT_RULE = (
    "Answer every item, one per line, formatted exactly as \"[NN] answer\" where NN is the "
    "item number as given. Emit the answer only: no working, no units unless the item asks "
    "for them, no commentary before or after the list. Items are independent: the answer to "
    "one must not depend on the answer to any other, and you must not reconcile them against "
    "each other."
)

CITIES = ["Quito", "Saskatoon", "Lisbon", "Osaka", "Nairobi", "Valparaiso", "Tromso", "Cebu"]
GOODS = ["cable reels", "valve kits", "pump seals", "filter packs", "gasket sets", "relay boards"]
STATUSES = ["cleared", "held", "in transit", "returned", "inspected"]


def _fmt_items(lines: list[str]) -> str:
    return "\n".join(lines)


def arith_orders(rng: random.Random) -> dict:
    rows, key = [], {}
    for i in range(1, N_ITEMS + 1):
        crates = rng.randint(7, 39)
        per = rng.randint(6, 24)
        removed = rng.randint(1, 5) * per
        rows.append(f"[{i:02d}] {crates} crates of {rng.choice(GOODS)}, {per} units per crate, {removed} units removed for inspection")
        key[f"{i:02d}"] = {"expected": str(crates * per - removed), "mode": "numeric"}
    return {
        "id": "gt_arith_orders",
        "category": "arithmetic_two_step",
        "expected_decomposable": True,
        "prompt": (
            "For each consignment below, give the number of units that remain available for "
            "dispatch: multiply the crate count by the units per crate, then subtract the units "
            "removed for inspection. Give an integer.\n\n"
            + _fmt_items(rows) + "\n\n" + FORMAT_RULE
        ),
        "key": key,
        "notes": "Two-step integer arithmetic. Hard for a 2-3B model; the source of the low end of the accuracy range.",
    }


def unit_convert(rng: random.Random) -> dict:
    rows, key = [], {}
    for i in range(1, N_ITEMS + 1):
        metres = rng.randint(120, 9800)
        rows.append(f"[{i:02d}] {metres} m")
        key[f"{i:02d}"] = {"expected": f"{metres / 1000:.3f}", "mode": "numeric"}
    return {
        "id": "gt_unit_convert",
        "category": "unit_conversion",
        "expected_decomposable": True,
        "prompt": (
            "Convert each length below from metres to kilometres. Give the value to exactly "
            "three decimal places, with no unit symbol.\n\n"
            + _fmt_items(rows) + "\n\n" + FORMAT_RULE
        ),
        "key": key,
        "notes": "Single-step conversion with a fixed precision. Medium difficulty; the precision rule is what most failures come from.",
    }


def date_offset(rng: random.Random) -> dict:
    rows, key = [], {}
    for i in range(1, N_ITEMS + 1):
        start = date(2026, 1, 1) + timedelta(days=rng.randint(0, 330))
        offset = rng.randint(9, 96)
        rows.append(f"[{i:02d}] shipped {start.isoformat()}, transit {offset} days")
        key[f"{i:02d}"] = {"expected": (start + timedelta(days=offset)).isoformat(), "mode": "date_iso"}
    return {
        "id": "gt_date_offset",
        "category": "date_arithmetic",
        "expected_decomposable": True,
        "prompt": (
            "For each shipment below, give the arrival date: the shipping date plus the transit "
            "days. Answer in ISO 8601 form, YYYY-MM-DD.\n\n"
            + _fmt_items(rows) + "\n\n" + FORMAT_RULE
        ),
        "key": key,
        "notes": "Month-boundary arithmetic. Hard for small models and unambiguous to grade.",
    }


def field_lookup(rng: random.Random) -> dict:
    rows, key = [], {}
    for i in range(1, N_ITEMS + 1):
        city, status = rng.choice(CITIES), rng.choice(STATUSES)
        ref = f"{rng.choice('ABCDEFGH')}{rng.randint(1000, 9999)}"
        rows.append(f"[{i:02d}] ref {ref} | destination {city} | customs {status} | weight {rng.randint(40, 900)} kg")
        key[f"{i:02d}"] = {"expected": city, "mode": "exact_norm"}
    return {
        "id": "gt_field_lookup",
        "category": "field_extraction",
        "expected_decomposable": True,
        "prompt": (
            "For each record below, give the destination city and nothing else. Copy it exactly "
            "as written in the record.\n\n"
            + _fmt_items(rows) + "\n\n" + FORMAT_RULE
        ),
        "key": key,
        "notes": "Near-free for any model that reads the record. Anchors the high end of the accuracy range so the sweep is not floor-bound.",
    }


def threshold_check(rng: random.Random) -> dict:
    rows, key = [], {}
    limit = 500
    for i in range(1, N_ITEMS + 1):
        weight = rng.randint(380, 620)
        rows.append(f"[{i:02d}] pallet {rng.choice('PQRSTU')}{rng.randint(100, 999)}, {weight} kg")
        key[f"{i:02d}"] = {"expected": "true" if weight > limit else "false", "mode": "boolean"}
    return {
        "id": "gt_threshold_check",
        "category": "threshold_decision",
        "expected_decomposable": True,
        "prompt": (
            f"For each pallet below, answer whether its weight exceeds the {limit} kg single-pallet "
            "limit. Answer exactly \"true\" or \"false\".\n\n"
            + _fmt_items(rows) + "\n\n" + FORMAT_RULE
        ),
        "key": key,
        "notes": "Comparison against one fixed threshold, with values clustered near it so guessing does not pay.",
    }


def main() -> None:
    rng = random.Random(SEED)
    prompts = [
        arith_orders(rng),
        unit_convert(rng),
        date_offset(rng),
        field_lookup(rng),
        threshold_check(rng),
    ]
    payload = {
        "_about": (
            "Ground-truth corpus for the V3c agreement calibration specified in Section 11.4 of the "
            "whitepaper. Each prompt is a batch of independent items with a canonical answer, so that "
            "k replicas of one micro-task can be aligned and each aligned unit graded against a key by "
            "swarmbly_v0.grading -- no judge, no embeddings, no model in the verdict."
        ),
        "_why_ground_truth": (
            "The calibration of 14 August 2026 reported r = -0.030 between agreement and judged "
            "acceptability and could not interpret it, because the judge accepted 93.3 % of everything "
            "and the dependent variable had no variance. That measurement leaves the confidence map "
            "unsupported rather than refuted. This corpus replaces the judge with an answer key."
        ),
        "_difficulty_note": (
            "Difficulty is mixed on purpose. Field extraction is near-free, two-step arithmetic and "
            "date offsets are hard for a 2-3B model. The point is to keep accuracy away from both "
            "ceiling and floor, because a dependent variable with no variance is what made the "
            "previous attempt unreadable -- repeating that with accuracy would be the same error."
        ),
        "_enclosure_note": (
            "Unlike prompts.json, every prompt here encloses its data. There the rule is the opposite: "
            "a prompt names a corpus it does not enclose, to stay inside the token band the "
            "coherence-tax sweep needs. Here there has to be a fact of the matter, so the facts travel "
            "with the question. Do not merge the two files."
        ),
        "_format": (
            "Answers are keyed as [NN]. swarmbly_v0.grading.extract_items parses them, tolerating "
            "(07) and 07. as well. A unit with no parsable label is counted as unlabelled and reported, "
            "never dropped silently."
        ),
        "_generator": f"scripts/make_ground_truth.py, seed {SEED}, {N_ITEMS} items per prompt",
        "prompts": prompts,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    total = sum(len(p["key"]) for p in prompts)
    print(f"wrote {OUT} -- {len(prompts)} prompts, {total} graded items")


if __name__ == "__main__":
    main()
