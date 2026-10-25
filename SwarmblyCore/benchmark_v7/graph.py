"""The fact graph: instances whose answers are canonical and whose facts are traceable.

Why a graph and not a corpus of prompts
---------------------------------------

Every corpus this project has used stated its answer key as a flat list, which
answers *was this claim right* and nothing else. When a fragment got a claim
wrong, there was no way to tell whether the worker was incapable, or whether the
packet it received never contained the fact the claim needed. Six runs were spent
on questions of that shape, and the answer in at least three cases turned out to
be the second.

A fact graph makes the difference mechanical. Each instance carries:

* **facts**, each with an id, a value, and the source section it lives in;
* **claims**, each naming the facts it requires;
* **sections**, the natural partition of the source material;

so an evaluator can compute, for any run, three separate quantities that the flat
key conflated into one:

* was the claim **correct**;
* was the claim **answerable** by the packet that was asked for it -- did that
  packet contain every fact the claim requires;
* which packet **should** have carried each missing fact.

"Wrong" and "unanswerable" are different failures with different fixes. The first
is a model problem, the second is a packing problem, and telling them apart is
the whole reason this file exists.

The four task classes
---------------------

``map``       one claim per section, each needing only facts from that section.
              The easy case, and the floor: if this degrades, nothing else
              measured downstream means anything.
``reduce``    claims requiring facts from several sections at once. The class
              where the protocol is weakest -- aggregate claims have been wrong
              36 % of the time against 8 % for local ones, consistently, across
              every run that measured them separately.
``chain``     claim *i* requires the answer to claim *i-1*. Carry and error
              propagation.
``compose``   a final prose answer with coverage and format constraints over the
              whole instance.

Determinism
-----------

Every instance is a pure function of its seed, and every value in it is computed
here rather than asserted, so a key cannot drift from the material it describes.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Sequence

__all__ = [
    "Fact",
    "Claim",
    "Section",
    "Instance",
    "TaskClass",
    "build_instance",
    "instance_digest",
]

TaskClass = Literal["map", "reduce", "chain", "compose"]

_SITES = [
    "Ostend", "Valparaiso", "Tromso", "Saskatoon", "Cebu", "Quito", "Osaka",
    "Nairobi", "Lisbon", "Hobart", "Bergen", "Recife", "Gdansk", "Mombasa",
    "Halifax", "Trieste", "Busan", "Antofagasta", "Reykjavik", "Durban",
]
_GOODS = [
    "valve kits", "cable reels", "pump seals", "filter packs", "gasket sets",
    "drive belts", "bearing sets", "relay boards",
]


@dataclass(frozen=True)
class Fact:
    """One atomic, checkable statement, and where it lives in the source."""

    fact_id: str
    section_id: str
    subject: str
    attribute: str
    value: float
    unit: str = ""

    def as_line(self) -> str:
        """How the fact appears in the source material."""
        value = f"{self.value:g}"
        return f"{self.subject} | {self.attribute} | {value}{(' ' + self.unit) if self.unit else ''}"


@dataclass(frozen=True)
class Claim:
    """A statement the answer must make, and exactly what it needs to make it.

    ``requires`` is the load-bearing field. It is what lets an evaluator say
    "this packet could not have produced this claim" rather than only "this
    claim is wrong", and the distinction between those two is the difference
    between a model problem and a packing problem.
    """

    claim_id: str
    kind: Literal["local", "aggregate", "derived"]
    requires: tuple[str, ...]
    answer: float
    unit: str = ""
    requires_claims: tuple[str, ...] = ()
    prose: str = ""

    @property
    def sections_needed(self) -> int:
        """How many distinct sections this claim's facts come from."""
        return len({f.rsplit(":", 1)[0] for f in self.requires})


@dataclass(frozen=True)
class Section:
    """One natural partition of the source material."""

    section_id: str
    title: str
    facts: tuple[Fact, ...]

    def as_text(self) -> str:
        lines = "\n".join(f"  {f.as_line()}" for f in self.facts)
        return f"[{self.section_id}] {self.title}\n{lines}"


@dataclass
class Instance:
    """One benchmark instance: source material, claims, and the canonical answer."""

    instance_id: str
    task_class: TaskClass
    seed: int
    sections: tuple[Section, ...]
    claims: tuple[Claim, ...]
    instruction: str
    split: str = ""
    constraints: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    @property
    def facts(self) -> dict[str, Fact]:
        return {f.fact_id: f for s in self.sections for f in s.facts}

    def source_text(self) -> str:
        return "\n\n".join(s.as_text() for s in self.sections)

    def prompt(self) -> str:
        return f"{self.instruction}\n\n{self.source_text()}"

    def facts_in_sections(self, section_ids: Sequence[str]) -> set[str]:
        wanted = set(section_ids)
        return {f.fact_id for s in self.sections if s.section_id in wanted
                for f in s.facts}

    def answerable_from(self, claim: Claim, available: set[str]) -> bool:
        """Could a packet holding exactly ``available`` produce this claim?

        The question the flat answer key could never ask.
        """
        return set(claim.requires).issubset(available)

    def as_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "task_class": self.task_class,
            "seed": self.seed,
            "split": self.split,
            "instruction": self.instruction,
            "constraints": list(self.constraints),
            "sections": [
                {"section_id": s.section_id, "title": s.title,
                 "facts": [asdict(f) for f in s.facts]}
                for s in self.sections
            ],
            "claims": [asdict(c) for c in self.claims],
        }


def _asked(preamble: str, claims: Sequence[Claim],
           trailer: str = "") -> str:
    """An instruction that NAMES the item ids the answer key uses.

    Found while building ``scripts/run_benchmark_v7.py``, and it is the defect
    this project keeps finding in a new place: a key whose identifiers are not
    the ones the prompt asks the model to emit.

    The instructions used to read "Give one line per group as **[group id]**
    followed by the value alone", and the group ids in the material are ``s1``,
    ``s2`` -- ``Section.as_text`` writes them. The claim ids are ``c_s1``,
    ``c_s2``. So a **perfectly compliant** answer was ``[s1] 440``, which
    ``parse_claims`` cannot read: its pattern accepts ``c_``-prefixed ids and
    bare digits, and ``s1`` is neither. The benchmark's evaluator could not parse
    the answer the benchmark's own instruction asked for, and every arm would
    have scored zero coverage for a reason that has nothing to do with
    fragmentation.

    It was invisible because ``test_the_parser_accepts_the_shapes_a_model
    _actually_emits`` fed the parser ``c_``-prefixed ids by hand instead of the
    shape the corpus asks for. A round-trip over the real corpus is now asserted
    instead -- the same repair, and for the same reason, as
    ``test_every_answer_in_the_corpus_round_trips_through_every_label_style`` in
    the harness's own suite.

    The claim namespace stays distinct from the section namespace on purpose: a
    model that echoes the section header ``[s1] Depot group 1`` must not have
    that read as an answer, which is the strictness ``parse_claims`` exists for.
    Naming the ids in the instruction is what makes both true at once.

    It also makes the *packets* name them, which is what lets a runner attribute
    a claim to the packet that was asked for it. Without that the localisation
    the oracle arm exists to provide has nothing to attribute to.
    """
    listed = "\n".join(f"  [{c.claim_id}] {c.prose}" for c in claims)
    tail = trailer or ("Give one line per item, beginning with the item id in "
                       "square brackets exactly as written above, followed by "
                       "the value alone.")
    return (f"{preamble}\n\nState each of these, using the item id given:\n"
            f"{listed}\n\n{tail}")


def _sections(rng: random.Random, n_sections: int, rows: int) -> tuple[Section, ...]:
    sites = rng.sample(_SITES, min(n_sections * rows, len(_SITES)))
    out: list[Section] = []
    cursor = 0
    for index in range(n_sections):
        section_id = f"s{index + 1}"
        facts: list[Fact] = []
        for row in range(rows):
            site = sites[cursor % len(sites)]
            cursor += 1
            facts.append(Fact(
                fact_id=f"{section_id}:f{row + 1}",
                section_id=section_id,
                subject=site,
                attribute=rng.choice(["throughput", "backlog", "dwell"]),
                value=float(rng.choice(range(120, 960, 5))),
                unit="units",
            ))
        out.append(Section(section_id=section_id,
                           title=f"Depot group {index + 1}",
                           facts=tuple(facts)))
    return tuple(out)


def build_instance(
    task_class: TaskClass,
    seed: int,
    n_sections: int = 4,
    rows_per_section: int = 4,
    split: str = "",
) -> Instance:
    """One instance, a pure function of its arguments.

    Every answer is computed here from the facts, so a key cannot drift from the
    material it describes -- the failure that made the V5 corpus rebuild
    necessary.
    """
    rng = random.Random(seed)
    sections = _sections(rng, n_sections, rows_per_section)
    all_facts = [f for s in sections for f in s.facts]
    claims: list[Claim] = []

    if task_class == "map":
        # One claim per section, needing only that section: the easy case.
        for section in sections:
            total = sum(f.value for f in section.facts)
            claims.append(Claim(
                claim_id=f"c_{section.section_id}",
                kind="local",
                requires=tuple(f.fact_id for f in section.facts),
                answer=total,
                unit="units",
                prose=f"the total for {section.title}",
            ))
        instruction = _asked(
            "For each depot group below, state its total.", claims)

    elif task_class == "reduce":
        # Claims spanning sections. No packet holding one section can answer.
        grand = sum(f.value for f in all_facts)
        claims.append(Claim(
            claim_id="c_grand", kind="aggregate",
            requires=tuple(f.fact_id for f in all_facts),
            answer=grand, unit="units", prose="the total across every group"))
        heaviest = max(all_facts, key=lambda f: f.value)
        claims.append(Claim(
            claim_id="c_max", kind="aggregate",
            requires=tuple(f.fact_id for f in all_facts),
            answer=heaviest.value, unit="units",
            prose="the single largest value anywhere in the material"))
        claims.append(Claim(
            claim_id="c_mean", kind="aggregate",
            requires=tuple(f.fact_id for f in all_facts),
            answer=round(grand / len(all_facts), 2), unit="units",
            prose="the mean value across every group"))
        instruction = _asked(
            "State the overall total, the single largest value, and the mean, "
            "using every group below.", claims)

    elif task_class == "chain":
        # Step i consumes step i-1. Arithmetic the models solve monolithically:
        # measuring state transport, not arithmetic ability.
        first = sections[0].facts[0]
        running = first.value
        claims.append(Claim(
            claim_id="c_1", kind="local", requires=(first.fact_id,),
            answer=running, unit="units",
            prose=f"the {first.attribute} at {first.subject}"))
        for step in range(2, min(len(all_facts), 6) + 1):
            source = all_facts[step - 1]
            running = running + source.value
            claims.append(Claim(
                claim_id=f"c_{step}", kind="derived",
                requires=(source.fact_id,),
                requires_claims=(f"c_{step - 1}",),
                answer=running, unit="units",
                prose=f"the running total after adding {source.subject}"))
        instruction = _asked(
            "Work the chain below one step at a time. Each step adds one value "
            "to the running total from the step before it.", claims)

    else:  # compose
        grand = sum(f.value for f in all_facts)
        claims.append(Claim(
            claim_id="c_grand", kind="aggregate",
            requires=tuple(f.fact_id for f in all_facts),
            answer=grand, unit="units", prose="the total across every group"))
        for section in sections[:2]:
            claims.append(Claim(
                claim_id=f"c_{section.section_id}", kind="local",
                requires=tuple(f.fact_id for f in section.facts),
                answer=sum(f.value for f in section.facts), unit="units",
                prose=f"the total for {section.title}"))
        instruction = _asked(
            "Write a short operational brief covering the material below. "
            "Write continuous prose in the present tense, in a neutral "
            "professional register. Do not reproduce the table and do not "
            "repeat any sentence.", claims,
            trailer="State each figure on its own line after the brief.")

    constraints: tuple[dict[str, Any], ...] = ()
    if task_class == "compose":
        constraints = (
            {"id": "no_repeated_sentence", "kind": "no_repeated_sentence"},
            {"id": "no_repeated_phrase", "kind": "no_repeated_ngram", "size": 8},
        )

    return Instance(
        instance_id=f"v7_{task_class}_{seed}",
        task_class=task_class,
        seed=seed,
        sections=sections,
        claims=tuple(claims),
        instruction=instruction,
        split=split,
        constraints=constraints,
    )


def instance_digest(instances: Sequence[Instance]) -> str:
    """SHA-256 over id, split, prompt and canonical answers, in order.

    Frozen the same way ``prompts/tables24.json`` is, and for the same reason: a
    threshold fitted against a corpus is only valid for the corpus it was fitted
    on, and a bare filename cannot carry that.
    """
    digest = hashlib.sha256()
    for instance in instances:
        digest.update(instance.instance_id.encode("utf-8"))
        digest.update(instance.split.encode("utf-8"))
        digest.update(instance.prompt().encode("utf-8"))
        digest.update(json.dumps(
            [[c.claim_id, c.answer] for c in instance.claims],
            sort_keys=True).encode("utf-8"))
    return digest.hexdigest()
