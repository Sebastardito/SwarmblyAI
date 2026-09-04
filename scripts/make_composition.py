#!/usr/bin/env python3
"""Thirty-six prose compositions, split dev/final, for the composition criterion.

Deterministic at a fixed seed; the output is committed and digested.

Why this corpus exists
----------------------

The free-form run of 3 September produced the strongest measurement this project
has. A monolithic arm satisfied **every** checkable constraint on **every**
composition -- 1.000 -- while fragmenting into three cost 14 to 21 points, and
on the same texts the BooookScore-like coherence tax read **+0.000**. No judge,
no model in the verdict: every check is a fact about a string.

And it rested on **three prompts**. There was no pre-registered cell, no control
and no corpus split, which is exactly the apparatus ``tables24.json`` was built
to give the coherence tax. The stronger instrument had the weaker method behind
it, and a description of three prompts is not evidence about a workload.

Three prompts also cannot carry an interval. A cluster bootstrap over three
clusters is an ornament, and the same run showed what happens when one is
published anyway: an AUC interval excluding chance by 0.0014 on eight clusters,
with the caveat in the prose and the number in the reader's memory.
``experiment.MIN_CLUSTERS_FOR_A_VERDICT`` is 20, so a corpus that wants a
verdict needs a final half of at least twenty prompts. This one has
twenty-four.

The split, and why it is in the file
------------------------------------

Written into the corpus by this script, before any of it is run, exactly as
``make_tables.py`` does it:

* ``split: "dev"`` -- twelve prompts. Everything that has to be chosen by
  looking at data is chosen here: tau_sem, which arm to report, whether the
  constraint families behave as intended.
* ``split: "final"`` -- twenty-four prompts. Evaluated once, afterwards, with
  nothing left to choose.

``_frozen`` carries a SHA-256 over id, split, tier and prompt text. Freezing a
split is a claim about which prompt sits on which side, and a claim that cannot
be checked is not a claim.

The threshold is **not** in this file. ``experiment.COMPOSITION_THRESHOLD_POINTS``
is 0.05 -- five points, the existing 5 % go/no-go translated onto a metric that
is counted rather than judged -- and it was frozen knowing the pilot put the gap
at 14 to 21 points. It is declared at a value the pilot data fails, so that no
one can later say it was set where the answer landed.

Difficulty is a design variable, not an accident
------------------------------------------------

Ten of the eleven monolithic baselines on 3 September scored exactly 1.000. A
saturated baseline is survivable for a *paired absolute* difference -- there is
no denominator to be sensitive to -- but it means the measurement can only ever
show fragmentation costing something, never show it costing nothing, and a
metric with no room above the arm under test cannot be checked for
arm-neutrality either.

So the corpus is built in three tiers, and the knobs are the checks the pilot
showed actually bind:

* ``term_once`` on one, two or three of the required terms. This is the
  hardest family in the pilot -- three of the five failures were ``*_once`` --
  and it is hard for a *monolithic* model too, because a writer covering a
  term across two paragraphs naturally names it twice.
* ``no_repeated_ngram`` at size 8, 7 or 5. Smaller is stricter.
* two, three or four ``must_mention`` terms, which raises the coverage load
  without touching repetition.

Twelve prompts per tier, and the split is balanced across tiers by construction:
four of each tier in dev, eight of each in final. A split that put the hard
prompts on one side would make the two halves incomparable, which is a way of
breaking a split that leaves the digest intact.

The two assembler-enforced checks are still generated
-----------------------------------------------------

``paragraph_count`` and ``words_per_paragraph`` stay in every prompt, because a
composition instruction that does not say how long or how many paragraphs is an
underspecified task and the model's reply would vary for reasons nothing here
measures. They are excluded from the *figure* by
``experiment.ASSEMBLER_ENFORCED``, not from the prompt: the assembler satisfies
them for the fragmented arm and the model has to earn them alone in the
baseline, and the sign of that bias is decided by prompt wording -- +23 points
in favour of the fragmented arm on the free-form corpus, the other way on the
table corpus. ``constraint_score_comparable`` is the only score that may cross
arms.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SEED = 20260904
OUT = Path(__file__).resolve().parent.parent / "prompts" / "composition.json"

TIERS: dict[str, dict[str, int]] = {
    "easy": {"mentions": 2, "once": 1, "ngram": 8},
    "mid": {"mentions": 3, "once": 2, "ngram": 7},
    "hard": {"mentions": 4, "once": 3, "ngram": 5},
}
"""Three difficulty settings, so the monolithic baseline has room to move.

``once`` is the count of required terms that must appear exactly once, and it is
the binding family: a writer covering a term across two paragraphs names it
twice without noticing, so ``hard`` is hard for the baseline as well as for an
assembly of fragments. That is the point -- a metric where the baseline is
pinned at 1.000 cannot show fragmentation costing nothing, and cannot be
checked for arm-neutrality either."""

TIER_ORDER = ("easy", "mid", "hard")

HEDGES = ("obviously", "clearly", "simply", "essentially", "basically", "of course")
"""One forbidden word per prompt, cycled. A hedge rather than a content word: a
model that avoids it has lost nothing from the answer, so the check measures
instruction-following and not knowledge."""

TOPICS: list[tuple[str, str, list[str]]] = [
    ("harbour_storm",
     "Describe how a small harbour reschedules cargo when a storm closes the outer channel.",
     ["tide window", "berth", "manifest", "pilot boat"]),
    ("archive_digitise",
     "Explain how a municipal archive decides which paper records to digitise first.",
     ["retention period", "condition survey", "reading room", "shelf mark"]),
    ("relay_winter",
     "Explain how a mountain relay station keeps a radio link open through a winter outage.",
     ["battery bank", "line of sight", "duty cycle", "ice load"]),
    ("depot_night",
     "Describe how a bus depot rebuilds the morning roster after a night of breakdowns.",
     ["spare vehicle", "shift handover", "route pairing", "depot yard"]),
    ("ferry_fog",
     "Explain how a river ferry runs a reduced service in persistent fog.",
     ["sailing slot", "radar watch", "vehicle deck", "slack water"]),
    ("orchard_frost",
     "Describe how an orchard co-operative allocates frost protection over one cold week.",
     ["frost fan", "bud stage", "block rotation", "water draw"]),
    ("clinic_intake",
     "Explain how a rural clinic triages a morning's walk-in patients with one doctor.",
     ["waiting list", "triage nurse", "referral note", "dressing room"]),
    ("bakery_supply",
     "Describe how a bakery adjusts production when a flour delivery arrives two days late.",
     ["proving time", "standing order", "flour blend", "day count"]),
    ("quarry_haul",
     "Explain how a quarry sequences haulage when one of two weighbridges fails.",
     ["load ticket", "haul road", "tare weight", "queue bay"]),
    ("library_move",
     "Describe how a branch library plans a move into a smaller building.",
     ["shelf run", "loan history", "study space", "crate label"]),
    ("hatchery_water",
     "Explain how a fish hatchery manages tank stocking through a low-water summer.",
     ["oxygen level", "grading run", "inflow rate", "holding tank"]),
    ("theatre_turnaround",
     "Describe how a small theatre turns the stage around between two productions in a day.",
     ["fly bar", "get-out call", "focus session", "crew break"]),
    ("cannery_line",
     "Explain how a cannery reallocates a shift when one filling line stops.",
     ["seam check", "batch code", "line speed", "cold store"]),
    ("kennels_intake",
     "Describe how boarding kennels absorb an unplanned intake over a holiday weekend.",
     ["quarantine pen", "feed chart", "exercise slot", "handover sheet"]),
    ("vineyard_pick",
     "Explain how a vineyard orders its picking when rain is forecast midweek.",
     ["sugar reading", "picking gang", "press capacity", "row block"]),
    ("sawmill_dry",
     "Describe how a sawmill schedules kiln loads after a wet felling season.",
     ["moisture target", "kiln charge", "stack spacing", "grading bench"]),
    ("laundry_hospital",
     "Explain how a hospital laundry keeps ward supply steady when a washer is down.",
     ["clean side", "trolley count", "wash cycle", "linen pack"]),
    ("marina_lift",
     "Describe how a marina sequences winter lift-outs with one travel hoist.",
     ["cradle stock", "keel depth", "lift window", "yard space"]),
    ("printworks_run",
     "Explain how a printworks re-plans a week when a press needs an unplanned service.",
     ["make-ready", "plate set", "run length", "paper stock"]),
    ("dairy_collect",
     "Describe how a dairy re-routes tanker collection when a bridge closes.",
     ["cooling limit", "collection round", "tank volume", "farm gate"]),
    ("museum_loan",
     "Explain how a museum prepares an outgoing loan of fragile objects.",
     ["condition report", "courier trip", "crate design", "display case"]),
    ("brewery_tanks",
     "Describe how a brewery allocates fermenting capacity before a seasonal peak.",
     ["tank turn", "yeast pitch", "conditioning time", "keg fill"]),
    ("airfield_light",
     "Explain how a small airfield manages movements while runway lighting is repaired.",
     ["daylight limit", "circuit pattern", "notice period", "apron space"]),
    ("recycling_sort",
     "Describe how a recycling depot handles a week of contaminated loads.",
     ["reject rate", "picking line", "bale weight", "tip floor"]),
    ("nursery_plants",
     "Explain how a plant nursery stages potting-on through a short labour shortage.",
     ["root ball", "potting bench", "hardening off", "sales window"]),
    ("smokehouse_batch",
     "Describe how a smokehouse plans batches around a single kiln.",
     ["brine time", "smoke cycle", "core temperature", "chill room"]),
    ("boatyard_survey",
     "Explain how a boatyard fits an unexpected insurance survey into its schedule.",
     ["slip booking", "hull access", "survey list", "launch date"]),
    ("granary_dry",
     "Describe how a granary manages intake during a damp harvest.",
     ["drying floor", "intake pit", "moisture test", "bin rotation"]),
    ("tramway_track",
     "Explain how a heritage tramway plans track work between running days.",
     ["running day", "rail joint", "possession slot", "depot road"]),
    ("cheese_cave",
     "Describe how a cheese maker allocates cave space across two maturing batches.",
     ["turning schedule", "rind wash", "shelf board", "humidity range"]),
    ("post_sorting",
     "Explain how a sorting office absorbs a parcel surge with fixed van capacity.",
     ["walk sequence", "van load", "cut-off time", "hold area"]),
    ("hostel_rooms",
     "Describe how a hostel reallocates rooms when a heating zone fails in winter.",
     ["room block", "booking hold", "heat zone", "linen change"]),
    ("windfarm_access",
     "Explain how a small wind farm plans turbine access in a short weather window.",
     ["access track", "crane pad", "wind limit", "spares run"]),
    ("abattoir_chill",
     "Describe how an abattoir schedules chilling capacity after a delivery backlog.",
     ["chill space", "kill floor", "carcass weight", "cutting room"]),
    ("stables_feed",
     "Explain how a livery yard plans feed and turnout through a wet month.",
     ["turnout paddock", "feed store", "ground condition", "rug change"]),
    ("cablecar_service",
     "Describe how a cable car plans its annual inspection around visitor numbers.",
     ["haul rope", "cabin count", "inspection day", "queue hall"]),
]
"""Thirty-six mundane operational subjects, four domain terms each.

Deliberately dull, and deliberately knowledge-free: any competent writer can
produce two coherent paragraphs on how a bakery handles a late flour delivery
without knowing anything about baking. A corpus that needed facts would confuse
"the model does not know this" with "assembly from fragments broke this", which
is the confound the answer-key corpora exist to avoid and this one must not
reintroduce."""


def composition(topic_id: str, instruction: str, terms: list[str],
                tier: str, forbidden: str) -> dict:
    """One two-paragraph task with its constraint set, at one difficulty tier.

    The constraints are not stylistic. Each names a way that assembly from
    independent fragments fails: dropped contract terms, a seam that produces
    the wrong number of paragraphs, a fragment that came back thin, and above
    all repetition -- two workers each introducing the subject, each locally
    fluent, the whole visibly stitched. The pilot confirmed the shape and
    refined it: ``repeated_sentences_cross_task`` was 0 everywhere, so the
    duplication is at the term and phrase level, which is what ``term_once``
    and ``no_repeated_ngram`` catch and ``no_repeated_sentence`` does not.
    """
    knobs = TIERS[tier]
    required = terms[: knobs["mentions"]]
    once = required[: knobs["once"]]
    constraints: list[dict] = [
        {"id": "paragraphs", "kind": "paragraph_count", "count": 2},
        {"id": "length", "kind": "words_per_paragraph", "min": 60, "max": 140},
        *[{"id": f"mentions_{_slug(term)}", "kind": "must_mention", "term": term}
          for term in required],
        {"id": "avoids_forbidden", "kind": "must_not_mention", "term": forbidden},
        {"id": "no_repeated_sentence", "kind": "no_repeated_sentence"},
        {"id": "no_repeated_phrase", "kind": "no_repeated_ngram",
         "size": knobs["ngram"]},
        *[{"id": f"{_slug(term)}_once", "kind": "term_once", "term": term}
          for term in once],
    ]
    once_clause = (
        f"Each of these must appear exactly once, not twice: {_join(once)}. "
        if once else "")
    return {
        "id": topic_id,
        "category": "composition",
        "tier": tier,
        "level": 2,
        "expected_decomposable": True,
        "prompt": (
            instruction + "\n\n"
            "Write exactly two paragraphs, separated by a blank line, each between 60 "
            "and 140 words. "
            f"Mention all of these: {_join(required)}. "
            + once_clause
            + f"Do not use the word \"{forbidden}\" anywhere. "
            "Do not repeat any sentence, and do not repeat any phrase of "
            f"{knobs['ngram']} words or more: the two paragraphs must not each "
            "introduce the subject and must not each conclude."
        ),
        "constraints": constraints,
        "notes": (
            f"Tier {tier}: {knobs['mentions']} required terms, {knobs['once']} of them "
            f"exactly once, repeated-phrase window {knobs['ngram']}. Graded by "
            "swarmbly_v0.constraints -- no judge and no key, every check is a fact "
            "about the string. Read constraint_score_comparable across arms: "
            "paragraph_count and words_per_paragraph are enforced by the assembler "
            "in one arm and by the model alone in the other."
        ),
    }


def _slug(term: str) -> str:
    """First word of a term, lowercased -- a stable constraint id.

    Constraint ids are read by a human comparing two runs, so they must not move
    when a term is rephrased in the prompt text. Collisions inside one prompt
    would be a corpus bug and `main` asserts they do not happen, rather than
    disambiguating them silently and leaving two checks that look like one.
    """
    return "".join(ch for ch in term.split()[0].lower() if ch.isalnum())


def _join(terms: list[str]) -> str:
    return ", ".join(terms)


def build(seed: int = SEED) -> list[dict]:
    """The corpus, with tier and split assigned by position.

    No randomness is needed and none is used: the topics are written out in
    order and the tier and split follow from the index. ``seed`` is accepted so
    the invocation matches the other generators and so a future variant that
    does draw can keep the signature.

    Tier cycles every prompt and the split changes every third *group* of three,
    so each split holds every tier in equal proportion: dev gets four of each,
    final gets eight of each. Assigning tiers to splits any other way makes the
    two halves incomparable -- a way of breaking a split that leaves the digest
    intact and would not be visible in a diff.
    """
    prompts: list[dict] = []
    for index, (topic_id, instruction, terms) in enumerate(TOPICS):
        tier = TIER_ORDER[index % len(TIER_ORDER)]
        prompt = composition(
            f"comp36_{topic_id}", instruction, terms, tier,
            HEDGES[index % len(HEDGES)])
        prompt["split"] = "dev" if (index // len(TIER_ORDER)) % 3 == 0 else "final"
        prompts.append(prompt)
    return prompts


def digest(prompts: list[dict]) -> str:
    """SHA-256 over id, split, tier and prompt text, in order.

    Not over the whole record: the notes are reproducible from the tier and
    hashing them would make an edit to a comment look like a corpus change. What
    must not move silently is which prompt carries which text, at which
    difficulty, on which side of the split.
    """
    payload = "\n".join(f"{p['id']}\t{p['split']}\t{p['tier']}\t{p['prompt']}"
                        for p in prompts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument(
        "--verify", action="store_true",
        help="Rebuild and compare against the digest already in --out. Exit 1 on "
             "a mismatch. Run this before quoting a result against this corpus.")
    args = parser.parse_args()

    prompts = build(args.seed)
    path = Path(args.out)
    current = digest(prompts)

    if args.verify:
        if not path.exists():
            print(f"{path} does not exist; nothing to verify", file=sys.stderr)
            return 1
        stored = json.loads(path.read_text()).get("_frozen", {}).get("sha256")
        if stored != current:
            print(f"DIGEST MISMATCH\n  stored {stored}\n  rebuilt {current}\n"
                  f"The corpus on disk is not the one this script builds. Any "
                  f"threshold frozen against the stored digest no longer applies.",
                  file=sys.stderr)
            return 1
        print(f"verified {path}: {current}")
        return 0

    # A corpus bug that ships is worse than a generator that refuses to write.
    ids = [p["id"] for p in prompts]
    assert len(set(ids)) == len(ids), "duplicate prompt id"
    for prompt in prompts:
        cids = [c["id"] for c in prompt["constraints"]]
        assert len(set(cids)) == len(cids), (
            f"{prompt['id']}: two constraints share an id, so two different "
            f"checks would be reported as one: {sorted(cids)}")

    dev = [p for p in prompts if p["split"] == "dev"]
    final = [p for p in prompts if p["split"] == "final"]
    by_tier = {t: sum(1 for p in prompts if p["tier"] == t) for t in TIER_ORDER}
    dev_tiers = {t: sum(1 for p in dev if p["tier"] == t) for t in TIER_ORDER}
    final_tiers = {t: sum(1 for p in final if p["tier"] == t) for t in TIER_ORDER}
    assert len(set(dev_tiers.values())) == 1 and len(set(final_tiers.values())) == 1, (
        f"the split is not balanced across tiers: dev {dev_tiers}, final "
        f"{final_tiers}. A split whose halves differ in difficulty is not a "
        f"split, whatever the digest says.")

    payload = {
        "_seed": args.seed,
        "_frozen": {
            "sha256": current,
            "dev": sorted(p["id"] for p in dev),
            "final": sorted(p["id"] for p in final),
            "rule": (
                "tau_sem, any choice of which arm to report, and any check on "
                "whether the constraint families behave as intended are fixed on "
                "the dev prompts alone. The final prompts are evaluated once, "
                "afterwards, with nothing left to choose. A figure that moves "
                "after the final half is seen is not an estimate of anything."
            ),
            "threshold": (
                "NOT stored here. experiment.COMPOSITION_THRESHOLD_POINTS is 0.05 "
                "-- five points of constraint satisfaction, the existing 5% "
                "go/no-go translated onto a metric that is counted rather than "
                "judged. It was frozen knowing the pilot of 3 September put the "
                "gap at 14 to 21 points, so it is declared at a value that data "
                "fails."
            ),
        },
        "_about": (
            "Thirty-six two-paragraph compositions in three difficulty tiers, checked "
            "mechanically by swarmbly_v0.constraints. Built for one declared question: "
            "how many points of constraint satisfaction fragmentation costs on prose."
        ),
        "_why": (
            "The composition finding of 3 September -- monolithic 1.000, fragmented "
            "N=3 at 0.864, and a coherence tax of +0.000 on the same texts -- rested on "
            "three prompts with no pre-registered cell, no control and no split. The "
            "coherence tax had that apparatus and the better instrument did not. "
            "experiment.MIN_CLUSTERS_FOR_A_VERDICT is 20, so a corpus that wants a "
            "verdict needs a final half of at least twenty prompts; this one has "
            "twenty-four."
        ),
        "_difficulty_note": (
            "Ten of eleven monolithic baselines in the pilot scored exactly 1.000. A "
            "saturated baseline survives a paired absolute difference -- there is no "
            "denominator -- but it can never show fragmentation costing nothing, and it "
            "cannot be checked for arm-neutrality. The three tiers vary the checks the "
            "pilot showed actually bind: how many required terms must appear exactly "
            "once (1/2/3), the repeated-phrase window (8/7/5), and how many terms are "
            "required at all (2/3/4). term_once is hard for the monolithic arm too, "
            "which is the point."
        ),
        "_scope_note": (
            "Nothing else should be swept on this corpus. A corpus swept over many "
            "cells answers the maximum-statistic question -- does SOME cell clear the "
            "threshold -- which has P(pass) = 100% under its own null. One cell, named "
            "before the run, plus a control required to fail."
        ),
        "_generator": f"scripts/make_composition.py, seed {args.seed}",
        "prompts": prompts,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    n_constraints = sum(len(p["constraints"]) for p in prompts)
    print(f"wrote {path}: {len(prompts)} prompts "
          f"({len(dev)} dev / {len(final)} final), tiers {by_tier}, "
          f"{n_constraints} constraints\n  dev tiers {dev_tiers}, "
          f"final tiers {final_tiers}\n  sha256 {current}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
