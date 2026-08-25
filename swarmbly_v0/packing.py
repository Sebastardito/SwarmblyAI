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

from dataclasses import dataclass
from typing import Mapping, Sequence

from .planner import consumes_predecessor
from .schema import Contract, Packet, Plan, Task
from .textutil import count_tokens, truncate_tokens

__all__ = [
    "PackingResult",
    "build_packet",
    "build_packets",
    "measure_rho",
    "packing_floor",
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
    return [
        ("contract_header", _contract_header(contract, verbose=False)),
        ("length", _length_block(contract.target_length_tokens)),
        ("predecessors", _predecessor_block(task, predecessor_summaries)),
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

    budget = max(task_tokens + carry_tokens,
                 int(round(rho_budget * max(contract.prompt_tokens, 1))))
    remaining = budget - task_tokens - carry_tokens

    candidates = [(name, text) for name, text in
                  _context_blocks(contract, task, predecessor_summaries)
                  if not (carry and name == "predecessors")]
    natural_tokens = sum(count_tokens(text) for _, text in candidates if text)
    if remaining > natural_tokens:
        for i, block in enumerate(_expansion_blocks(contract, task, remaining - natural_tokens)):
            candidates.append((f"expansion_{i}", block))

    included: list[str] = [carry] if carry else []
    names: list[str] = ["predecessors"] if carry else []
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
    total = sum(count_tokens(_task_block(task)) for task in plan.tasks)
    if summaries and getattr(plan, "sequential", False):
        total += sum(
            count_tokens(carry_block(task, summaries, True)) for task in plan.tasks
        )
    return total / max(contract.prompt_tokens, 1)


def measure_rho(packets: Sequence[Packet], prompt: str) -> float:
    """Achieved ``rho = sum_i |K_i| / |P|`` for a set of dispatched packets."""
    prompt_tokens = max(count_tokens(prompt), 1)
    return sum(p.token_count for p in packets) / prompt_tokens


def build_packets(
    contract: Contract,
    plan: Plan,
    rho_target: float,
    summaries: Mapping[str, str] | None = None,
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
    n = max(len(plan.tasks), 1)
    summaries = dict(summaries or {})
    prompt_tokens = max(contract.prompt_tokens, 1)
    floor = packing_floor(contract, plan)
    reachable = rho_target >= floor

    mandatory = [count_tokens(_task_block(task)) for task in plan.tasks]
    desired = [_desired_context_tokens(contract, task, summaries) for task in plan.tasks]
    total_desired = sum(desired)
    total_budget = rho_target * prompt_tokens
    slack = max(0.0, total_budget - sum(mandatory))

    if total_desired > 0:
        shares = [slack * d / total_desired for d in desired]
    else:
        shares = [slack / n] * n

    packets = [
        build_packet(contract, task, summaries,
                     (mandatory[i] + shares[i]) / prompt_tokens,
                     sequential=bool(getattr(plan, "sequential", False)))
        for i, task in enumerate(plan.tasks)
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
                packets[i] = build_packet(contract, plan.tasks[i], summaries, new_budget)

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
