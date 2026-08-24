#!/usr/bin/env python3
"""Generate ``prompts/free_form.json`` -- the corpus the confidence map needs.

Deterministic at a fixed seed; the output is committed.

Why a second corpus
-------------------

The ground-truth corpus asks for canonical answers: ``30``, ``Osaka``, ``true``.
That was the right instrument for establishing whether the pipeline delivers the
work intact, and on 24 August it finally did -- fragmented accuracy 68.6 %
against 76.8 % unfragmented, with the control category at 100 % in both.

It is the wrong instrument for the question it was built to answer. Independent
models that get a canonical item right emit *the same string*, so the agreement
score degenerates: 260 of 280 items came back at agreement exactly 1.0, the
variable took four distinct values in total, and at *k* = 3 it was 1.0
everywhere, carrying no information at all. The whole apparatus the confidence
map rests on -- embeddings, tau_sem, multiple alignment -- exists for answers
that can be **phrased differently and still be right**. A corpus of canonical
answers cannot exercise it, and cannot refute it either.

Two shapes, then.

**Free-form short answers.** The answer is a word or a short phrase with
genuinely equivalent variants, enumerated generously in the key under the
``any_of`` mode. Grading stays mechanical; agreement gets something to measure.
The accepted sets are written wide on purpose -- a correct answer graded wrong
because the author did not think of that phrasing is the same class of mistake
that has cost this project three runs already.

**Composition.** Two paragraphs against checkable constraints, graded by
``swarmbly_v0.constraints``. This is the workload the architecture is actually
pitched on and it has never been measured. There is no answer key for prose, but
there are facts about a string: how many paragraphs, how many words each,
whether the required things are named, and -- the one that matters for assembly
-- whether anything is said twice. Two workers who each introduce the topic and
each conclude produce a text where every sentence is locally fluent and the
whole is visibly seam-stitched. A transition-based coherence score can miss
that; a repetition check cannot.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from swarmbly_v0.constraints import derived_aggregates  # noqa: E402

SEED = 20260825
OUT = Path(__file__).resolve().parent.parent / "prompts" / "free_form.json"

SHORT_FORMAT = (
    "Give one line per item. Begin the line with the item number in square brackets, exactly as "
    "given, then a single space, then your answer. Keep each answer to at most three words. "
    "Items are independent."
)

CITIES = ["Quito", "Saskatoon", "Lisbon", "Osaka", "Nairobi", "Valparaiso", "Tromso", "Cebu"]
GOODS = ["cable reels", "valve kits", "pump seals", "filter packs", "gasket sets"]

OVER = "over|above|exceeds|over limit|above limit|too heavy|overweight|heavier|over the limit"
UNDER = "under|below|within|under limit|below limit|within limit|not over|lighter|under the limit"
YES = "yes|it does|correct|true|affirmative|it is"
NO = "no|it does not|incorrect|false|negative|it is not"


def _spec(pid: str, category: str, level: int, instruction: str, rows: list[str],
          key: dict, notes: str) -> dict:
    return {
        "id": pid, "category": category, "level": level, "expected_decomposable": True,
        "prompt": instruction + "\n\n" + "\n".join(rows) + "\n\n" + SHORT_FORMAT,
        "key": key, "notes": notes,
    }


def over_under(rng: random.Random, level: int) -> dict:
    """Is the pallet over the limit? One or two words, many ways to say it."""
    rows, key, limit = [], {}, 500
    for i in range(1, 11):
        weight = rng.randint(180, 880) if level == 1 else rng.randint(465, 535)
        src = f"[{i:02d}] pallet {rng.choice('PQRSTU')}{rng.randint(100, 999)}, {weight} kg"
        rows.append(src)
        key[f"{i:02d}"] = {"expected": OVER if weight > limit else UNDER,
                           "mode": "any_of", "level": level, "source": src}
    margin = "far from" if level == 1 else "within 35 kg of"
    return _spec(f"ff_overunder_L{level}", "over_under", level,
                 f"For each pallet below, say in your own words whether its weight is over or "
                 f"under the {limit} kg limit. Answer in at most three words.", rows, key,
                 f"Values {margin} the limit. Two answer classes, many phrasings each -- which is "
                 "the point: canonical answers make every correct reply identical and leave the "
                 "agreement score nothing to measure.")


def field_name(rng: random.Random, level: int) -> dict:
    """Name the field that carries a given value. Synonyms are real here."""
    fields = [("destination", "destination|destination city|the destination|city|dest"),
              ("origin", "origin|origin city|the origin|source|from"),
              ("consignee", "consignee|the consignee|receiver|recipient")]
    rows, key = [], {}
    for i in range(1, 11):
        name, accepted = fields[rng.randrange(len(fields))]
        city = rng.choice(CITIES)
        parts = {"origin": rng.choice(CITIES), "destination": rng.choice(CITIES),
                 "consignee": rng.choice(CITIES)}
        parts[name] = city
        extra = f" | weight {rng.randint(40, 900)} kg" if level == 2 else ""
        src = (f"[{i:02d}] origin {parts['origin']} | destination {parts['destination']} | "
               f"consignee {parts['consignee']}{extra} -- which field holds {city}?")
        rows.append(src)
        key[f"{i:02d}"] = {"expected": accepted, "mode": "any_of", "level": level, "source": src}
    return _spec(f"ff_fieldname_L{level}", "field_naming", level,
                 "For each record below, name the field that holds the city named at the end of "
                 "the line. Answer with the field name only, in at most three words.", rows, key,
                 "Ambiguous items are avoided: the named city appears in exactly one field. Level "
                 "2 adds an irrelevant field as distraction.")


def rule_check(rng: random.Random, level: int) -> dict:
    """Does the shipment satisfy the rule? Free phrasing of yes and no."""
    rows, key = [], {}
    for i in range(1, 11):
        weight = rng.randint(200, 900)
        cleared = rng.random() < 0.5
        status = "cleared" if cleared else rng.choice(["held", "in transit", "returned"])
        ok = weight < 600 and cleared if level == 2 else weight < 600
        tail = f", customs {status}" if level == 2 else ""
        src = f"[{i:02d}] consignment of {rng.choice(GOODS)}, {weight} kg{tail}"
        rows.append(src)
        key[f"{i:02d}"] = {"expected": YES if ok else NO, "mode": "any_of",
                           "level": level, "source": src}
    rule = ("the consignment weighs less than 600 kg" if level == 1
            else "the consignment weighs less than 600 kg AND its customs status is cleared")
    return _spec(f"ff_rulecheck_L{level}", "rule_check", level,
                 f"For each consignment below, say whether it may ship. It may ship only if "
                 f"{rule}. Answer in at most three words, in your own words.", rows, key,
                 "Level 2 conjoins two conditions. The answer is binary but its wording is not.")


# --------------------------------------------------------------------------- #
# composition: two paragraphs, checked mechanically
# --------------------------------------------------------------------------- #

def composition(topic_id: str, instruction: str, terms: list[str], forbidden: str) -> dict:
    """One two-paragraph task with its constraint set.

    The constraints are not stylistic. Each one names a way that assembly from
    fragments fails: dropped contract terms, a seam that produces four
    paragraphs instead of two, a fragment that came back thin, and above all
    repetition -- two workers each introducing the topic, each locally fluent,
    the whole visibly stitched.
    """
    constraints = [
        {"id": "paragraphs", "kind": "paragraph_count", "count": 2},
        {"id": "length", "kind": "words_per_paragraph", "min": 60, "max": 140},
        *[{"id": f"mentions_{t.split()[0].lower()}", "kind": "must_mention", "term": t}
          for t in terms],
        {"id": "avoids_forbidden", "kind": "must_not_mention", "term": forbidden},
        {"id": "no_repeated_sentence", "kind": "no_repeated_sentence"},
        {"id": "no_repeated_phrase", "kind": "no_repeated_ngram", "size": 8},
        {"id": f"{terms[0].split()[0].lower()}_once", "kind": "term_once", "term": terms[0]},
    ]
    return {
        "id": topic_id,
        "category": "composition",
        "level": 2,
        "expected_decomposable": True,
        "prompt": (
            instruction + "\n\n"
            f"Write exactly two paragraphs, separated by a blank line, each between 60 and 140 "
            f"words. Mention each of these once and only once: {', '.join(terms)}. "
            f"Do not use the word \"{forbidden}\" anywhere. Do not repeat any sentence or phrase: "
            f"the two paragraphs must not each introduce the subject and must not each conclude."
        ),
        "constraints": constraints,
        "notes": (
            "Composition graded by swarmbly_v0.constraints. No judge and no key: every check is a "
            "fact about the string. The repetition checks are the ones the coherence tax cannot "
            "make, because each duplicated passage is locally fluent."
        ),
    }


def grounded(rng: random.Random, topic_id: str, subject: str, terms: list[str]) -> dict:
    """Two paragraphs summarising an enclosed table -- prose with per-sentence truth.

    The synthesis the first four runs argued their way to. Item corpora gave
    correctness with no spread in agreement: 260 of 280 items came back at
    exactly 1.0, because a model that gets "30" right emits the same string as
    every other model that gets it right. Compositions gave the opposite --
    agreement spread across every bin, mean 0.610, labels 50/27/47 -- but no
    ground truth below the level of the whole text.

    A summary of a table has both. Consensus scores the agreement of each
    sentence; the sentence's figures either appear in the table, or are an
    aggregate of it, or were invented. Two variables with variance at the same
    time, which is what V3c has needed since the first run.
    """
    rows, weights = [], []
    for i in range(1, 7):
        weight = rng.randrange(120, 960, 5)
        weights.append(float(weight))
        rows.append(f"  {rng.choice('ABCDEFGH')}{rng.randint(1000, 9999)} | "
                    f"{rng.choice(CITIES)} | {weight} kg | {rng.choice(GOODS)}")
    allowed = sorted(set(weights) | derived_aggregates(weights))
    return {
        "id": topic_id,
        "category": "grounded_prose",
        "level": 3,
        "expected_decomposable": True,
        "prompt": (
            f"{subject}\n\n"
            "  ref | destination | weight | goods\n" + "\n".join(rows) + "\n\n"
            "Write exactly two paragraphs, separated by a blank line, each between 60 and 140 "
            f"words. Mention each of these once and only once: {', '.join(terms)}. "
            "Every figure you state must come from the table above or be an arithmetic aggregate "
            "of it -- a total, a count, an average, the heaviest or the lightest. Do not estimate "
            "and do not round to a figure the table does not support. Do not repeat any sentence "
            "or phrase."
        ),
        "constraints": [
            {"id": "paragraphs", "kind": "paragraph_count", "count": 2},
            {"id": "length", "kind": "words_per_paragraph", "min": 60, "max": 140},
            *[{"id": f"mentions_{x.split()[0].lower()}", "kind": "must_mention", "term": x}
              for x in terms],
            {"id": "no_repeated_sentence", "kind": "no_repeated_sentence"},
            {"id": "no_repeated_phrase", "kind": "no_repeated_ngram", "size": 8},
        ],
        "numeric_facts": {
            "allowed": allowed,
            "note": (
                "Table values plus the aggregates a summary may legitimately state. A sentence "
                "whose figures all fall in this set is correct on this measure; one that states "
                "any other figure invented it. A sentence with no figure is graded None -- not "
                "correct and not incorrect -- because counting it either way would move the "
                "accuracy toward whichever verdict was chosen."
            ),
        },
        "notes": (
            "Grounded prose: per-sentence numeric ground truth paired with per-sentence "
            "agreement. The first corpus in which both variables can vary at once."
        ),
    }


COMPOSITIONS = [
    composition(
        "comp_harbour",
        "Describe how a small harbour schedules cargo when a storm closes the outer channel.",
        ["tide window", "berth", "manifest"], "obviously"),
    composition(
        "comp_archive",
        "Explain how a municipal archive decides which paper records to digitise first.",
        ["retention period", "condition survey", "reading room"], "clearly"),
    composition(
        "comp_relay",
        "Explain how a mountain relay station keeps a radio link open through a winter outage.",
        ["battery bank", "line of sight", "duty cycle"], "simply"),
]


def main() -> None:
    rng = random.Random(SEED)
    prompts = [f(rng, level) for f in (over_under, field_name, rule_check) for level in (1, 2)]
    prompts.extend(COMPOSITIONS)
    prompts.extend([
        grounded(rng, "grounded_manifest",
                 "Summarise the consignment table below for a duty manager.",
                 ["heaviest consignment", "total weight"]),
        grounded(rng, "grounded_backlog",
                 "Summarise the backlog table below for the morning stand-up.",
                 ["average weight", "number of consignments"]),
    ])
    n_items = sum(len(p.get("key", {})) for p in prompts)
    n_constraints = sum(len(p.get("constraints", [])) for p in prompts)
    payload = {
        "_about": (
            "Second V3c corpus. Short free-form answers with several accepted phrasings, plus "
            "two-paragraph compositions checked mechanically by swarmbly_v0.constraints."
        ),
        "_why": (
            "The canonical-answer corpus saturated the predictor: 260 of 280 items came back at "
            "agreement exactly 1.0, the variable took four distinct values, and at k=3 it was 1.0 "
            "everywhere and carried no information. Independent models that get '30' right emit "
            "the same string. The agreement machinery exists for answers that can be phrased "
            "differently and still be right, and this corpus supplies them."
        ),
        "_composition_note": (
            "The composition prompts are the workload the architecture is pitched on and have "
            "never been measured. Prose has no answer key, but it has checkable properties: "
            "paragraph count, words per paragraph, required and forbidden terms, and repetition. "
            "The repetition checks matter most -- two fragments that each introduce the subject "
            "produce a text that is locally fluent everywhere and stitched together visibly."
        ),
        "_accepted_sets_are_wide_on_purpose": (
            "A correct answer graded wrong because the author did not think of that phrasing is "
            "the same class of error that cost this project three runs. When in doubt the "
            "phrasing is accepted; a grader that is too generous understates the difference "
            "between conditions, which is the safer direction to be wrong in."
        ),
        "_generator": f"scripts/make_free_form.py, seed {SEED}",
        "prompts": prompts,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} -- {len(prompts)} prompts, {n_items} graded items, "
          f"{n_constraints} constraints across {len(COMPOSITIONS)} compositions")


if __name__ == "__main__":
    main()
