"""Packet construction and ``rho`` control -- the independent variable of V0.

Definition (master document, section 5.4.3)::

    rho = ( sum_i |K_i| ) / |P|

where ``K_i`` is the packet dispatched for micro-task ``i`` and ``P`` is the
original prompt. ``rho = 1.0`` means the swarm collectively reads exactly one
prompt's worth of tokens -- the fragments and nothing else. ``rho = 2.0`` means
it reads two, the second one being pure contextual redundancy paid for
coherence.

Because ``rho`` is the quantity under study, it cannot be an emergent
side-effect of prompt formatting: this module *targets* it. Each packet gets a
token budget of ``rho_target * |P| / N``, its task text is mandatory, and the
context blocks are then added by priority and trimmed -- or synthetically
expanded -- until the budget is met.

The achievable floor
--------------------
A packet must always contain its own task, so::

    rho_floor = ( sum_i |task_i| + N * |header_i| ) / |P|

which sits slightly above 1.0. :func:`packing_floor` reports it, and
:func:`build_packets` records whether the requested target was reachable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Sequence

from .planner import consumes_predecessor
from .schema import Contract, Packet, Plan, Task
from .textutil import count_tokens, truncate_tokens

__all__ = [
    "packing_ceiling",
    "PackingResult",
    "build_packet",
    "build_packets",
    "measure_rho",
    "packing_floor",
    "task_budget_weights",
    "task_budget_floors",
    "answers_by_item_label",
    "assert_packet_invariants",
    "PacketInvariantError",
    "build_monolithic_prompt",
]

_TASK_MARKER = "[TASK {task_id}]"


def _task_block(task: Task) -> str:
    """The mandatory, never-trimmed part of a packet."""
    return f"{_TASK_MARKER.format(task_id=task.task_id)}\n{task.instruction}"


def _contract_header(contract: Contract, *, verbose: bool) -> str:
    """The minimal (or verbose) rendering of the global contract."""
    lines = [
        "[GLOBAL CONTRACT]",
        f"session: {contract.session_id}",
        f"objective: {contract.objective}",
        f"register: {contract.register}",
        f"output_format: {contract.output_format}",
    ]
    if verbose:
        lines.insert(3, f"audience: {contract.audience}")
    return "\n".join(lines)


def _length_block(target_tokens: int) -> str:
    return f"target_length_tokens: {target_tokens}"


def _forbidden_block(contract: Contract) -> str:
    if not contract.forbidden_terms:
        return ""
    return "forbidden: " + ", ".join(contract.forbidden_terms)


def _glossary_block(contract: Contract) -> str:
    lines = contract.glossary_lines()
    if not lines:
        return ""
    return "glossary:\n" + "\n".join(lines)


def _predecessor_block(task: Task, summaries: Mapping[str, str]) -> str:
    relevant = [(dep, summaries[dep]) for dep in task.depends_on if summaries.get(dep)]
    if not relevant:
        return ""
    lines = "\n".join(f"- {dep}: {text}" for dep, text in relevant)
    return "[PREDECESSOR SUMMARIES]\n" + lines


_ITEM_KEYED_RE = re.compile(r"(?:^|\s)[\[(]\d{1,3}[\])]\s", re.MULTILINE)


def answers_by_item_label(task: Task) -> bool:
    """Does this task's answer belong to numbered items rather than to prose?

    A packet whose task block names its own items as ``[04]``, ``[05]`` is an
    **answer sheet**: what the grader reads back is one labelled line per item,
    and ``swarmbly_v0.experiment.task_item_scope`` will confine it to exactly the
    labels appearing here.

    For such a packet a predecessor's summary is not context. It is *the answers
    to somebody else's items*, in the same notation, immediately above a task
    block that says "answer only the items listed here" -- and a fragment that
    reads on and restates them has its restatements thrown away by the scope
    filter while its own items go unanswered. :func:`carry_block` already refuses
    to make that block mandatory, and says why: "forcing a predecessor's answers
    into packets with no use for them is actively harmful ... an enumerated
    corpus reported 379 graded items against a key holding 150". The *optional*
    path was ungated, so at any rho with slack -- which is every cell above the
    packing floor -- the same content went in anyway.

    Prose fragments are untouched. There the predecessor summary is a sentence
    about what the previous section said, which is the shared context rho exists
    to buy, and it stays exactly where it was.
    """
    return bool(_ITEM_KEYED_RE.search(_task_text(task)))


def _task_text(task: Task) -> str:
    """Whatever this Task carries as its instruction, across field spellings."""
    for field in ("text", "instruction", "body", "description", "prompt"):
        value = getattr(task, field, "")
        if value:
            return str(value)
    return ""


def carry_block(task: Task, summaries: Mapping[str, str], sequential: bool) -> str:
    """The predecessor block a dependent task may not be rationed out of.

    A task that consumes a predecessor's *value* -- "divide the net value from
    step 2" -- is unanswerable without it. Until now that block was optional
    context, third in priority behind the contract header and the length note,
    funded out of whatever slack remained after the task text. On the V4 chain
    corpus at rho = 2.0 the slack ran out first and **not one packet carried it**:
    every successor was asked to divide a number nobody had told it.

    That is the real cause of V4's dependency-chain result -- +47.2 % coherence
    tax at the widest fragment, accuracy falling to 0.091, the tax saturating near
    +76 %. It was read as "an ordered chain is expensive to fragment". It is not.
    The packet was unanswerable by construction, and no fragment size fixes a
    packet that is missing the one thing it needs.

    So a carry is mandatory, on the same footing as the task text. What makes
    that affordable rather than a new tax on rho is the typed form: ``[02]=2247``
    is four tokens where the prose summary it replaces is forty. The mechanism
    and the budget argument are the same mechanism.

    Gated on the task *text*, via
    :func:`~swarmbly_v0.planner.consumes_predecessor`, rather than on the plan's
    shape. ``Plan.sequential`` is true for any enumerated segmentation, an
    independent item batch included, and forcing a predecessor's answers into
    packets with no use for them is actively harmful: the successor restates them
    as its own, and an enumerated corpus reported 379 graded items against a key
    holding 150.

    "Divide the net value **from step 2**" consumes a value. "[01] pallet R752,
    251 kg" does not. So: mandatory where the text says a value is needed, absent
    where the items are independent.

    Returns the block, or "" when the task consumes nothing, or when it depends
    on nothing yet produced.
    """
    if not consumes_predecessor(_task_text(task)):
        return ""
    return _predecessor_block(task, summaries)


def _context_blocks(
    contract: Contract, task: Task, predecessor_summaries: Mapping[str, str]
) -> list[tuple[str, str]]:
    """Context blocks in **priority order**, highest first.

    The ordering is a design decision with consequences the sweep will measure.
    Predecessor summaries sit above the glossary and the forbidden list because
    a dependent task that does not know what its predecessor said produces the
    chimeric join that assembly cannot repair, whereas a missing glossary
    degrades naming consistency -- bad, but locally detectable and locally
    fixable. Tasks with no dependencies have no predecessor block at all, so
    for them the whole budget goes to the contract.
    """
    # An answer sheet is the exception, and it is not a rationing decision: see
    # `answers_by_item_label`. A predecessor's reply to an item batch is a block
    # of answer lines, and handing it to the next packet contaminates the arm
    # whose denominator this run reads.
    predecessors = ("" if answers_by_item_label(task)
                    else _predecessor_block(task, predecessor_summaries))
    return [
        ("contract_header", _contract_header(contract, verbose=False)),
        ("length", _length_block(contract.target_length_tokens)),
        ("predecessors", predecessors),
        ("glossary", _glossary_block(contract)),
        ("forbidden", _forbidden_block(contract)),
    ]


def _desired_context_tokens(
    contract: Contract, task: Task, predecessor_summaries: Mapping[str, str]
) -> int:
    """Tokens this packet would use if its context were not rationed at all."""
    return sum(
        count_tokens(text)
        for _, text in _context_blocks(contract, task, predecessor_summaries)
        if text
    )


def _expansion_blocks(contract: Contract, task: Task, needed: int) -> list[str]:
    """Deterministic filler used when the budget exceeds the natural context.

    This is not padding for its own sake: at high ``rho`` a real orchestrator
    would spend the extra budget on exactly this kind of material -- style
    exemplars, entity disambiguation, negative constraints. Generating it
    deterministically keeps the sweep reproducible.
    """
    blocks: list[str] = []
    if needed <= 0:
        return blocks
    exemplars = [
        "[STYLE EXEMPLARS]",
        f"- Write in a {contract.register} register aimed at {contract.audience}.",
        f"- Output shape must remain a coherent {contract.output_format}.",
        "- Open with an explicit connective that ties this part to the previous one.",
        "- Do not re-introduce material that an earlier part already introduced.",
        "- Keep tense and person consistent with the rest of the answer.",
    ]
    blocks.append("\n".join(exemplars))
    if contract.canonical_entities:
        disambiguation = ["[ENTITY DISAMBIGUATION]"]
        for entity in contract.canonical_entities:
            disambiguation.append(
                f"- {entity}: refer to it as '{entity}' every time; do not coin variants, "
                "abbreviations or synonyms for it."
            )
        blocks.append("\n".join(disambiguation))
    scope = ["[SCOPE GUARD]"]
    for entity in task.expected_entities:
        scope.append(f"- This part must actually mention {entity}.")
    scope.append("- Introduce no entity that is absent from the contract glossary.")
    blocks.append("\n".join(scope))
    return blocks


def build_packet(
    contract: Contract,
    task: Task,
    predecessor_summaries: Mapping[str, str],
    rho_budget: float,
    sequential: bool = False,
) -> Packet:
    """Build one packet ``K_i`` targeting a share of the global ``rho`` budget.

    Args:
        contract: The global contract ``Gamma``.
        task: The micro-task this packet carries.
        predecessor_summaries: ``task_id -> summary`` for already-generated
            predecessors. Only the summaries of this task's actual
            dependencies are attached; that is the point of having a DAG
            rather than a list.
        rho_budget: Target packet size **expressed as a multiple of the
            original prompt length**, i.e. the packet aims for
            ``rho_budget * contract.prompt_tokens`` tokens. A caller targeting
            a global ``rho`` over ``N`` tasks passes ``rho_target / N``.

    Returns:
        A :class:`~swarmbly_v0.schema.Packet` with its realised token counts.

    The task block is mandatory and never trimmed: a packet without its task
    is not a packet. Context blocks are added in priority order (contract
    header, length, predecessor summaries, forbidden terms, glossary, then
    synthetic expansion) and the first block that does not fit is truncated at
    a token boundary.
    """
    task_block = _task_block(task)
    task_tokens = count_tokens(task_block)

    # The carry is mandatory, not context: see is_carry_mandatory. It is added to
    # the floor rather than funded from slack, so a budget too small to hold it
    # overshoots rho_target visibly instead of silently dropping the one block
    # that makes the task answerable.
    carry = carry_block(task, predecessor_summaries, sequential)
    carry_tokens = count_tokens(carry) if carry else 0

    # The contract header is mandatory too, on the same footing as the task
    # block and the carry. It used to be the highest-priority *context* block --
    # kept first, but still fundable from slack and therefore droppable when the
    # slack ran out. On `multi_hop_math_supply` at rho 2.0, N=4 a packet came
    # back without it, and a fragment scored against a contract it never
    # received measures the contract's absence: exactly the V6 defect that
    # invalidated long_prose in two runs.
    #
    # This is also what makes packing_floor honest. The floor has always been
    # DEFINED as tasks plus one header each; with the header rationable, a
    # below-floor target produced packets cheaper than the floor and the two
    # disagreed.
    header = _contract_header(contract, verbose=False)
    header_tokens = count_tokens(header)

    mandatory_tokens = task_tokens + carry_tokens + header_tokens
    budget = max(mandatory_tokens,
                 int(round(rho_budget * max(contract.prompt_tokens, 1))))
    remaining = budget - mandatory_tokens

    candidates = [(name, text) for name, text in
                  _context_blocks(contract, task, predecessor_summaries)
                  if name != "contract_header"
                  and not (carry and name == "predecessors")]
    natural_tokens = sum(count_tokens(text) for _, text in candidates if text)
    if remaining > natural_tokens:
        for i, block in enumerate(_expansion_blocks(contract, task, remaining - natural_tokens)):
            candidates.append((f"expansion_{i}", block))

    included: list[str] = [header]
    names: list[str] = ["contract_header"]
    if carry:
        included.append(carry)
        names.append("predecessors")
    truncated = False
    for name, text in candidates:
        if not text:
            continue
        cost = count_tokens(text)
        if cost <= remaining:
            included.append(text)
            names.append(name)
            remaining -= cost
        elif remaining > 0:
            clipped = truncate_tokens(text, remaining)
            if clipped.strip():
                included.append(clipped)
                names.append(f"{name}(trimmed)")
                remaining -= count_tokens(clipped)
                truncated = True
            break
        else:
            break

    context_text = "\n".join(included)
    packet_text = f"{context_text}\n{task_block}" if context_text else task_block
    return Packet(
        task_id=task.task_id,
        text=packet_text,
        token_count=count_tokens(packet_text),
        context_tokens=count_tokens(context_text),
        task_tokens=task_tokens,
        blocks_included=tuple(names),
        truncated=truncated,
        # What this packet could not be talked out of carrying. Recorded here,
        # where it is computed, so no caller has to re-derive it and get a
        # different answer -- which is exactly how the floor and the packer
        # disagreed twice.
        mandatory_tokens=mandatory_tokens,
    )


@dataclass
class PackingResult:
    """All packets for one plan, plus the achieved-vs-target ``rho``."""

    packets: list[Packet]
    rho_target: float
    rho_achieved: float
    rho_floor: float
    reachable: bool

    @property
    def total_input_tokens(self) -> int:
        return sum(p.token_count for p in self.packets)

    @property
    def rho_error(self) -> float:
        """Signed error ``achieved - target``."""
        return self.rho_achieved - self.rho_target


def packing_floor(
    contract: Contract,
    plan: Plan,
    summaries: Mapping[str, str] | None = None,
) -> float:
    """Smallest ``rho`` reachable for this plan (tasks + markers, no context).

    On a sequential plan the mandatory carry is part of the floor, because it is
    part of what a packet must contain to be answerable. Passing ``summaries``
    gives the truthful figure once they exist; without them the floor is the
    optimistic one, which is what a caller planning before generation can know.
    Reporting the optimistic floor as if it were final would let a run announce
    ``rho_reachable=true`` for a cell that then overshoots.
    """
    # The module docstring has always defined this as
    #
    #     rho_floor = ( sum_i |task_i| + N * |header_i| ) / |P|
    #
    # and the implementation summed only the task blocks. The header term was
    # missing, so the floor was under-reported by one header per packet and
    # `rho_reachable` came back true for cells whose target could not in fact be
    # hit. Those cells then overshot -- and because nothing checked, the overshoot
    # was invisible. On `bulk_extraction_invoices` at rho 1.25, N=4, the run
    # achieved 1.962 while reporting the target as reachable.
    #
    # A packet always carries its task block AND one contract header. That is
    # what a packet minimally is; a fragment without the header is not a cheaper
    # packet, it is a fragment that cannot be scored against its contract.
    header = count_tokens(_contract_header(contract, verbose=False))
    total = sum(count_tokens(_task_block(task)) + header for task in plan.tasks)
    if summaries and getattr(plan, "sequential", False):
        total += sum(
            count_tokens(carry_block(task, summaries, True)) for task in plan.tasks
        )
    return total / max(contract.prompt_tokens, 1)


def measure_rho(packets: Sequence[Packet], prompt: str) -> float:
    """Achieved ``rho = sum_i |K_i| / |P|`` for a set of dispatched packets."""
    prompt_tokens = max(count_tokens(prompt), 1)
    return sum(p.token_count for p in packets) / prompt_tokens


def packing_ceiling(
    contract: Contract,
    plan: Plan,
    summaries: Mapping[str, str] | None = None,
) -> float:
    """Largest ``rho`` reachable for this plan -- the other bound, added 4 Sept 2026.

    ``packing_floor`` says a target below it is not a measurement of ``rho``,
    because every packet collapses to its bare task and two labels give
    byte-identical output. **The same is true above the ceiling and nothing
    said so.** A packet cannot hold more than its mandatory blocks plus its
    natural context plus :func:`_expansion_blocks`, and that last list is
    FINITE: six style exemplars, one line per canonical entity, one per
    expected entity. It takes ``needed`` as an argument and ignores it. So a
    packet asked for three times the prompt simply cannot spend it.

    The cost of not having this: the v0 tier of 4 September asked for rho 5.5
    at N=2, where the worst prompt tops out at 4.90. It ran for five hours,
    reached ``long_report_energy`` at the fifth of six rho points, undershot by
    6.5 %, and the drift invariant -- correctly, on its own terms -- aborted the
    whole tier. One cell out of 144 was unreachable and 143 measured cells were
    thrown away with it.

    The grid was mine and I checked one bound and not the other, which is the
    same mistake the floor was added to fix, on the other side.

    **Measured, not derived.** It builds the packets at an absurd target and
    reads what the packer actually achieved, rather than re-deriving the sum of
    block sizes. A derived ceiling can disagree with the packer, and that has
    already happened once on this file: ``packing_floor`` was defined as tasks
    plus one header each and implemented as tasks alone, so it under-reported by
    one header per packet and ``rho_reachable`` came back true for cells that
    then overshot. One packing pass costs no model calls and cannot drift.
    """
    return build_packets(contract, plan, rho_target=_UNREACHABLY_HIGH_RHO,
                         summaries=summaries).rho_achieved


_UNREACHABLY_HIGH_RHO: float = 999.0
"""A target no plan can reach, used to ask the packer for everything it has.

Not ``inf``: the budget is multiplied by the prompt length and rounded to an
int, and an infinity there is a crash rather than a large number."""


def build_packets(
    contract: Contract,
    plan: Plan,
    rho_target: float,
    summaries: Mapping[str, str] | None = None,
    budget_tokens: float | None = None,
    only_tasks: Sequence[str] | None = None,
) -> PackingResult:
    """Build every packet for ``plan`` so the *global* ``rho`` hits ``rho_target``.

    Budgeting is **not** a uniform ``rho_target / N`` per packet. Micro-tasks
    are not equally long, a packet can never go below its own task text, and
    packets do not all want the same amount of context -- a node with three
    predecessors needs their summaries, a node with none does not. So the total
    budget ``B = rho_target * |P|`` is allocated as

    ``budget_i = |task_i| + slack * desired_i / sum_j desired_j``

    where ``slack = B - sum_j |task_j|`` and ``desired_i`` is what packet ``i``
    would consume with no rationing at all. Uniform sharing would starve
    exactly the packets that carry dependencies. When the slack is negative the
    target sits below :func:`packing_floor` and every packet collapses to its
    bare task; the result is flagged ``reachable=False``. A correction pass then
    absorbs the residue left by atomic block boundaries.
    """
    summaries = dict(summaries or {})
    prompt_tokens = max(contract.prompt_tokens, 1)
    floor = packing_floor(contract, plan)
    reachable = rho_target >= floor

    # Which tasks this call is responsible for, and what budget they share.
    #
    # Both parameters exist because of a defect that put achieved rho at 3.91
    # against a target of 3.5 in four consecutive runs. The sweep calls this
    # function ONCE PER TOPOLOGICAL LEVEL, each time with the summaries produced
    # so far -- but each call budgeted all N tasks against the FULL budget, while
    # only the tasks of that level were dispatched. On a plan of seven sections
    # plus one integration node that meant the integration node was budgeted
    # twice, and the second time its `desired` had grown (it now had seven
    # predecessor summaries to want), so it took a much larger share of the slack
    # than the first pass had reserved for it. The overshoot was exactly that
    # extra, and it grew with N because the number of predecessors does.
    #
    # A caller sweeping levels now passes the tasks it is about to dispatch and
    # the budget that remains, so the total across levels is the total that was
    # asked for.
    tasks = [t for t in plan.tasks
             if only_tasks is None or str(t.task_id) in set(only_tasks)]
    n = max(len(tasks), 1)

    mandatory = [count_tokens(_task_block(task)) for task in tasks]
    desired = [_desired_context_tokens(contract, task, summaries) for task in tasks]
    total_desired = sum(desired)
    total_budget = (rho_target * prompt_tokens if budget_tokens is None
                    else max(0.0, float(budget_tokens)))
    slack = max(0.0, total_budget - sum(mandatory))

    if total_desired > 0:
        shares = [slack * d / total_desired for d in desired]
    else:
        shares = [slack / n] * n

    packets = [
        build_packet(contract, task, summaries,
                     (mandatory[i] + shares[i]) / prompt_tokens,
                     sequential=bool(getattr(plan, "sequential", False)))
        for i, task in enumerate(tasks)
    ]

    # Correction pass: atomic blocks and truncation boundaries leave residue.
    if slack > 0:
        for _ in range(2):
            residual = total_budget - sum(p.token_count for p in packets)
            if abs(residual) <= max(1.0, 0.005 * total_budget):
                break
            elastic = [i for i, p in enumerate(packets)
                       if residual > 0 or p.context_tokens > 0]
            if not elastic:
                break
            bonus = residual / len(elastic)
            for i in elastic:
                new_budget = max(mandatory[i], packets[i].token_count + bonus) / prompt_tokens
                packets[i] = build_packet(contract, tasks[i], summaries, new_budget)

    achieved = measure_rho(packets, plan.prompt)
    return PackingResult(
        packets=packets,
        rho_target=rho_target,
        rho_achieved=achieved,
        rho_floor=floor,
        reachable=reachable,
    )


def build_monolithic_prompt(contract: Contract, prompt: str) -> str:
    """The baseline: one packet, whole prompt, full contract, no fragmentation.

    Deliberately contains **no** ``[TASK ...]`` marker, which is how the
    downstream mock backend recognises the monolithic condition and scores it
    at maximum context strength.
    """
    parts = [
        _contract_header(contract, verbose=True),
        _length_block(contract.target_length_tokens),
        _forbidden_block(contract),
        _glossary_block(contract),
        "[REQUEST]",
        prompt,
    ]
    return "\n".join(part for part in parts if part)


def task_budget_floors(contract: Contract, plan: Plan) -> dict[str, float]:
    """The tokens each task must have: its own block plus one contract header.

    A level allocated less than the sum of these cannot carry its headers, and a
    fragment without its contract measures the contract's absence. The global
    ``packing_floor`` guarantees this in aggregate; splitting a budget between
    levels has to guarantee it per level, which is a stricter requirement and was
    the one a proportional split quietly broke.
    """
    header = count_tokens(_contract_header(contract, verbose=False))
    return {str(task.task_id): float(count_tokens(_task_block(task)) + header)
            for task in plan.tasks}


def task_budget_weights(contract: Contract, plan: Plan) -> dict[str, float]:
    """How the global budget should divide between tasks, before any run.

    Computed once, from the plan alone with no summaries, so that a level
    dispatched later cannot claim a larger share merely because predecessor
    summaries now exist for it to want. That is precisely what went wrong: the
    integration node's `desired` grew between the first pass and the second, and
    it took slack the first pass had reserved for the sections.

    A task's weight is its mandatory block plus what it would consume unrationed.
    Never zero, so a task can always be packed.
    """
    weights: dict[str, float] = {}
    for task in plan.tasks:
        mandatory = count_tokens(_task_block(task))
        desired = _desired_context_tokens(contract, task, {})
        weights[str(task.task_id)] = float(max(1, mandatory + desired))
    return weights


class PacketInvariantError(RuntimeError):
    """A run was about to dispatch packets that cannot answer their own question.

    Raised BEFORE generation, not after. A post-hoc warning is what the harness
    had, and it did not work: ``rho_fidelity`` reported the same N=8 drift in
    four consecutive runs and every one of them completed, was analysed, and had
    a figure quoted from it. A check that has to be read is a check that gets
    skipped; a check that costs seconds and refuses to start cannot be.
    """


def assert_packet_invariants(
    packets: Sequence[Packet],
    plan: Plan,
    contract: Contract,
    rho_target: float,
    prompt: str,
    tolerance: float = 0.05,
    summaries: Mapping[str, str] | None = None,
    reachable: bool = True,
) -> None:
    """Refuse to dispatch a set of packets that is not what the run claims.

    Three conditions, each of which has silently corrupted a result:

    1. **A packet without its contract.** V6: ``long_prose`` fragments received
       an answer-sheet directive instead of their format block, so the
       eight-paragraph, 70-to-130-word contract reached no fragment while the
       baseline kept all of it. That invalidated long_prose in two runs and read,
       downstream, as a cost of fragmentation.

    2. **Achieved rho outside tolerance of target.** rho is the independent
       variable, so a cell that did not run at its budget is not the cell its
       label names.

    3. **A dependent task without its mandatory carry.** V4: at rho = 2.0 not one
       packet carried a predecessor block, so every successor was asked to divide
       a number nobody had told it. That was reported as "+47.2 % coherence tax
       for an ordered chain".

    Raises:
        PacketInvariantError: naming the packet and the condition, so the failure
            is actionable rather than a bare assertion.
    """
    summaries = dict(summaries or {})
    by_id = {str(p.task_id): p for p in packets}

    # A target below packing_floor cannot carry the contract header in every
    # packet -- the floor is DEFINED as the task text plus one header each. So
    # an unreachable cell is not a defect, it is a cell the budget forbids, and
    # `rho_reachable` already records it. Checking the header there would refuse
    # every low-rho run for doing exactly what low rho means.
    if not reachable:
        return

    for task in plan.tasks:
        packet = by_id.get(str(task.task_id))
        if packet is None:
            continue
        if "[GLOBAL CONTRACT]" not in packet.text:
            raise PacketInvariantError(
                f"packet {task.task_id} carries no [GLOBAL CONTRACT] header. A "
                f"fragment scored against a contract it never received measures "
                f"the contract's absence, not the cost of fragmenting.")
        if consumes_predecessor(_task_text(task)):
            expected = [d for d in task.depends_on if summaries.get(d)]
            if expected and "[PREDECESSOR SUMMARIES]" not in packet.text:
                raise PacketInvariantError(
                    f"packet {task.task_id} consumes a predecessor value and its "
                    f"carry is absent (depends on {expected}). The packet is "
                    f"unanswerable by construction, and no fragment size fixes "
                    f"a packet missing the one thing it needs.")

    achieved = measure_rho(packets, prompt)
    if rho_target > 0:
        deviation = (achieved - rho_target) / rho_target
        if abs(deviation) > tolerance:
            raise PacketInvariantError(
                f"achieved rho {achieved:.3f} against a target of {rho_target:.3f} "
                f"({deviation:+.1%}, tolerance {tolerance:.0%}). rho is the "
                f"independent variable; this cell would not measure what its "
                f"label says.")
