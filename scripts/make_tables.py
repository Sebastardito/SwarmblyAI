#!/usr/bin/env python3
"""Twenty-four enclosed-table prompts, split into a development half and a
final half that is not to be looked at until the thresholds are frozen.

Why this corpus exists
----------------------

``table_summary`` at N=2 is the only cell this project has ever produced that
came close to the 5 % threshold. The run of 26 August put it at **+5.8 %** with a
95 % interval of ``[-2.2 %, +14.5 %]`` -- not a pass, not a refutation, and the
narrowest live question left. The interval is that wide for one reason: it rests
on **eight prompts**. Eight is also what every agreement figure in that run rests
on, which is why their intervals span chance.

Sixteen more prompts of the same construction roughly halve the interval. That
is the whole purpose of this file.

Why a separate script and a separate corpus file
------------------------------------------------

``scripts/make_complex.py`` draws all three shapes from one RNG in sequence.
Adding table prompts there would consume draws that currently produce the
dependency chains, silently replacing the chain corpus that V6 measured. So this
script owns its own generator and writes its own file, and imports the *builder*
from ``make_complex`` so the two cannot drift: the prompt text, the constraint
set and the numeric key are produced by the identical function.

The split, and why it is in the file
------------------------------------

Every threshold this project has used was calibrated on the same data it then
evaluated. ``tau_sem`` is the clearest case -- fitted from labelled pairs drawn
from the runs it goes on to judge -- but the go/no-go threshold, the agreement
bin edges and the flagging rate are all in the same position. That is leakage,
and it flatters.

So the split is written **into the corpus**, by this script, before any of it is
run:

* ``split: "dev"`` -- eight prompts. Everything that has to be chosen by looking
  at data is chosen here: thresholds, bin edges, flagging rates, tau_sem, and
  any decision about which arm to report.
* ``split: "final"`` -- sixteen prompts. Evaluated once, with everything already
  fixed. A number that moves after seeing these is not an estimate.

The assignment is interleaved -- every third prompt is dev -- rather than "the
first eight". Sequential assignment would put dev and final in different regions
of the generator's stream, and while nothing here should drift along that stream,
"should not" is not a control.

``_frozen`` carries a SHA-256 of the prompt payload. Freezing a split is a claim
about *when* something was decided, and a claim about time needs a mechanism, not
a note in a changelog. Regenerate this file with a different seed or a different
builder and the digest changes; ``--verify`` fails, and any result quoted against
the old digest is visibly quoting a corpus that no longer exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from make_complex import table_prompt  # noqa: E402
from swarmbly_v0.textutil import count_tokens  # noqa: E402

SEED = 20260827
"""Deliberately not make_complex's seed. Sharing a seed between two generators
that draw different sequences is a coincidence waiting to be mistaken for a
control."""

# The tense and register directive, added 27 August, and the reason it is a
# CORPUS change rather than a metric change.
#
# `register_tense_shift` flags any sentence deviating from the document's own
# majority tense or register. On the run of 26 August it fired on 0.00 of the
# monolithic baseline's sentences and 0.44 of the fragmented arm's at N=8, k=3 --
# it is a homogeneity penalty, and an answer assembled from N independent
# generations is inherently less homogeneous than one written in a single pass.
#
# A register shift mid-document IS a coherence defect, so removing the detector
# would be moving the goalposts. But no fragment was ever TOLD which tense to
# use, so the penalty was for a failure to coordinate that the instructions never
# asked for. Naming the tense in the contract turns a dispute about the metric
# into a measurement: if the tax falls, the penalty was uncoordinated formatting;
# if it does not, the detector was measuring something real.
#
# Frozen with the corpus, so the sha256 changes and no threshold set against the
# old digest silently carries over.

# Twenty-four names, so every prompt id is distinct and legible in a results
# table. The first eight repeat the shared corpus's names on purpose: those eight
# prompts are *not* the same prompts -- different seed, different rows -- and the
# ids therefore carry a corpus prefix so the two can never be confused in a join.
NAMES = (
    "manifest", "backlog", "dispatch", "intake", "transit", "holdover",
    "consolidation", "clearance", "quarantine", "reconciliation", "outturn",
    "layover", "drayage", "demurrage", "transhipment", "groupage",
    "bonded", "overspill", "recall", "returns", "salvage", "staging",
    "prealert", "closeout",
)

# Forty-four destinations against twenty rows per table, so two tables share
# fewer than half their destinations on average. The shared corpus draws 20 of
# 22, which makes its eight tables near-identical on that column.
DEPOT_POOL = [
    "Ostend", "Valparaiso", "Tromso", "Saskatoon", "Cebu", "Quito",
    "Osaka", "Nairobi", "Lisbon", "Hobart", "Bergen", "Recife",
    "Gdansk", "Mombasa", "Halifax", "Trieste", "Busan", "Antofagasta",
    "Reykjavik", "Durban", "Split", "Nantes", "Tallinn", "Iquique",
    "Napier", "Rijeka", "Kotka", "Paranagua", "Sfax", "Batumi",
    "Klaipeda", "Manzanillo", "Dakar", "Fremantle", "Aarhus", "Constanta",
    "Vigo", "Larvik", "Tuticorin", "Puntarenas", "Kaohsiung", "Bilbao",
    "Aqaba", "Nakhodka",
]

DEV_EVERY = 3
"""Every third prompt is dev: 8 of 24, interleaved through the draw order."""


def build(seed: int = SEED) -> list[dict]:
    rng = random.Random(seed)
    prompts: list[dict] = []
    for index, name in enumerate(NAMES):
        prompt = table_prompt(rng, name, pool=DEPOT_POOL)
        prompt["id"] = f"tbl24_{name}"
        prompt["split"] = "dev" if index % DEV_EVERY == 0 else "final"
        prompts.append(prompt)
    return prompts


def digest(prompts: list[dict]) -> str:
    """SHA-256 over id, split and prompt text, in order.

    Deliberately not over the whole record: the notes and the derived numeric key
    are reproducible from the prompt, and hashing them would make an
    inconsequential edit to a comment look like a corpus change. What must not
    move silently is which prompt carries which text and which side of the split
    it sits on.
    """
    payload = "\n".join(f"{p['id']}\t{p['split']}\t{p['prompt']}" for p in prompts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="prompts/tables24.json")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument(
        "--verify", action="store_true",
        help="Rebuild and compare against the digest already in --out. Exit 1 on "
             "a mismatch. Run this before quoting a result against this corpus.")
    args = parser.parse_args()

    prompts = build(args.seed)
    sizes = [count_tokens(p["prompt"]) for p in prompts]
    dev = [p for p in prompts if p["split"] == "dev"]
    final = [p for p in prompts if p["split"] == "final"]
    current = digest(prompts)
    path = Path(args.out)

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

    payload = {
        "_seed": args.seed,
        "_frozen": {
            "sha256": current,
            "dev": sorted(p["id"] for p in dev),
            "final": sorted(p["id"] for p in final),
            "rule": (
                "Thresholds, bin edges, flagging rates, tau_sem and any choice of "
                "which arm to report are fixed on the dev prompts alone. The final "
                "prompts are evaluated once, afterwards, with nothing left to "
                "choose. A figure that moves after the final half is seen is not an "
                "estimate of anything."
            ),
        },
        "_length_note": (
            f"Canonical tokens per prompt: min {min(sizes)}, max {max(sizes)}, "
            f"mean {sum(sizes) // len(sizes)}."
        ),
        "_corpus_note": (
            "Twenty-four enclosed-table prompts, built by make_complex.table_prompt "
            "-- the identical builder the shared corpus uses -- from an independent "
            "generator and a wider destination pool. It exists to answer one "
            "question: whether table_summary at N=2 clears the 5 % threshold. The "
            "run of 26 August put that cell at +5.8 % with an interval of "
            "[-2.2 %, +14.5 %] on eight prompts; sixteen more roughly halve it. "
            "Nothing else should be swept on this corpus, because a corpus swept "
            "over many cells answers the maximum-statistic question, not this one."
        ),
        "prompts": prompts,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {path}: {len(prompts)} prompts "
          f"({len(dev)} dev / {len(final)} final), "
          f"{min(sizes)}-{max(sizes)} canonical tokens")
    print(f"frozen sha256 {current}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
