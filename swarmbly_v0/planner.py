"""Prompt -> global contract + micro-task DAG.

Two artefacts come out of this module:

``global_contract(prompt, backend) -> Contract``
    The contract ``Gamma``: the small block of shared state that must travel
    with *every* packet for the fragments to be mutually consistent. Its size
    is one of the two things that drives ``rho`` (the other is the predecessor
    summaries), and every token in it is paid ``N`` times.

``plan(prompt, backend) -> Plan``
    A DAG whose nodes are micro-tasks and whose edges are *real* data
    dependencies. The edge set matters twice over: it decides which packets
    need a predecessor summary at all, and its level decomposition is the
    critical path that bounds any achievable speedup.

Both functions accept a backend so a real model can be used for extraction.
By default they run a deterministic heuristic path, because V0 must be
reproducible and runnable with no API keys; pass ``refine=True`` to let the
backend rewrite the objective.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Sequence

from .schema import Contract, Plan, Task
from .textutil import (
    count_tokens,
    extract_entities,
    keywords,
    split_into_token_chunks,
    split_sentences,
    truncate_tokens,
)

__all__ = ["BASELINE_FORMAT_DIRECTIVE", "carry_values", "consumes_predecessor",
           "global_contract", "plan",
           "split_enumerated", "summarize_fragment", "suggest_n_tasks"]

_AUDIENCE_RE = re.compile(
    r"\bfor (?:an?|the)?\s*([a-z][a-z \-]{3,60}?)(?:\s+audience)?\s*(?:[.,;]|$)", re.I
)
_LENGTH_RE = re.compile(r"\b(\d{2,5})\s*(word|token)s?\b", re.I)
_FORBID_RE = re.compile(
    r"(?:do not use|don't use|avoid(?: using)?|never mention|without using)\s+([^.;\n]{3,80})", re.I
)
_ENUM_SPLIT_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)]|[\[(]\d{1,3}[\])])\s*", re.M)
"""Bullet, ``1.``/``1)``, or a bracketed ``[01]``/``(01)`` item label.

The bracketed form was missing until 24 August 2026, and its absence is what
made the enumerated-batch case fail. A prompt of ten ``[NN]`` items split into
one unit, fell through to sentence packing, and produced fragments where the
task holding the data held no operation -- workers echoed ``30000 m`` back
instead of converting it -- while four of the ten items appeared in no fragment
at all.
"""

_ITEM_LABEL_RE = re.compile(r"^\s*[\[(]?(\d{1,3})[\]).:]\s+", re.M)
"""Start of an enumerated item, used to find where the item block begins and ends."""

_FORMAT_CUES: tuple[tuple[str, str], ...] = (
    ("json", r"\bjson\b|\bschema\b"),
    ("code", r"\bcode\b|\bfunction\b|\bclass\b|\bmodule\b|\bpython\b|\bimplement\b"),
    ("table", r"\btable\b|\bcsv\b|\bcolumns?\b|\bspreadsheet\b"),
    ("list", r"\bbullet\b|\blist\b|\benumerate\b|\bitemi[sz]e\b"),
    ("report", r"\breport\b|\bsections?\b|\bwhitepaper\b|\bmemo\b|\bbrief\b"),
    ("narrative", r"\bstory\b|\bnarrative\b|\bpoem\b|\bscene\b"),
)

_REGISTER_CUES: tuple[tuple[str, str], ...] = (
    ("casual", r"\bcasual\b|\binformal\b|\bconversational\b|\bfriendly\b|\bplain english\b"),
    ("formal", r"\bformal\b|\bacademic\b|\bprofessional\b|\btechnical\b|\bexecutive\b|\brigorous\b"),
)

_DEFAULT_FORBIDDEN = ("obviously", "as an AI language model", "in conclusion")


def _session_id(prompt: str) -> str:
    """Stable 12-hex-char id for a prompt (used to tie packets to a session)."""
    return hashlib.blake2b(prompt.encode("utf-8"), digest_size=6).hexdigest()


_NEGATION_WINDOW = re.compile(
    r"(?:do not|don't|never|without|no|avoid|rather than|instead of)\s+(?:\w+\s+){0,3}$",
    re.IGNORECASE,
)


def _detect(cues: Sequence[tuple[str, str]], prompt: str, default: str) -> str:
    """First cue whose match is not inside a negation.

    ``output_format`` is replicated into every packet and into the baseline
    prompt, so a wrong value is an instruction the whole run obeys. Matching
    without looking left produced exactly that: every ``table_summary`` prompt in
    the V5 corpus says "do not reproduce the table, do not emit rows or pipe
    characters" and was assigned ``output_format: table``, while every
    ``long_prose`` prompt says "no headings, no bullet points" and was assigned
    ``list``. The contract was telling the models to do the thing the prompt
    forbade -- and then the graders scored them for doing it.
    """
    # An explicit prohibition outranks a mention. A summarisation prompt says
    # "Summarise the manifest table below" *and* "do not reproduce the table":
    # the first is what the input is, the second is what the output must not be,
    # and only the second is about the format to produce.
    forbidden = {
        label for label, pattern in cues
        for match in re.finditer(pattern, prompt, re.I)
        if _NEGATION_WINDOW.search(prompt[:match.start()])
    }
    for label, pattern in cues:
        if label in forbidden:
            continue
        for match in re.finditer(pattern, prompt, re.I):
            if not _NEGATION_WINDOW.search(prompt[:match.start()]):
                return label
    return default


def global_contract(
    prompt: str,
    backend: Any | None = None,
    *,
    refine: bool = False,
    target_length_tokens: int | None = None,
) -> Contract:
    """Derive the global contract ``Gamma`` from ``prompt``.

    Args:
        prompt: The raw user prompt.
        backend: Optional backend, used only when ``refine`` is set.
        refine: Ask the backend to rewrite the objective. Off by default
            because it makes the contract non-deterministic across backends.
        target_length_tokens: Override the inferred answer length.

    Returns:
        A frozen :class:`~swarmbly_v0.schema.Contract`.
    """
    sentences = split_sentences(prompt)
    # Kept short on purpose: the objective is replicated into every packet, so
    # each of its tokens is paid N times and directly raises rho.
    objective = truncate_tokens(sentences[0] if sentences else prompt, 24).strip()

    if refine and backend is not None:
        try:
            refined = backend.generate(
                "Restate the following request as a single imperative objective "
                f"sentence.\n\n{prompt}\n",
                max_tokens=60,
            ).strip()
            if refined:
                objective = truncate_tokens(refined, 40)
        except Exception:
            pass  # A backend hiccup must never break planning.

    # Only the opening sentence states the audience. Searching the whole prompt
    # captured "site to run a third shift" out of item [08] of the long_prose
    # briefs -- a fragment of a task description presented to every packet as
    # who the answer is for.
    audience_match = _AUDIENCE_RE.search(sentences[0] if sentences else prompt)
    audience = (audience_match.group(1).strip() if audience_match else "a technical reader")

    register = _detect(_REGISTER_CUES, prompt, "formal")
    output_format = _detect(_FORMAT_CUES, prompt, "report")

    if target_length_tokens is not None:
        target = int(target_length_tokens)
    else:
        length_match = _LENGTH_RE.search(prompt)
        if length_match:
            value = int(length_match.group(1))
            # Words -> tokens with the conventional ~1.3 factor.
            target = int(value * 1.3) if length_match.group(2).lower() == "word" else value
        else:
            target = 320
    target = max(120, min(target, 2000))

    forbidden = [m.group(1).strip().strip("\"'") for m in _FORBID_RE.finditer(prompt)]
    forbidden.extend(_DEFAULT_FORBIDDEN)
    seen: set[str] = set()
    unique_forbidden: list[str] = []
    for term in forbidden:
        key = term.lower()
        if key not in seen:
            seen.add(key)
            unique_forbidden.append(term)

    entities = extract_entities(prompt, min_mentions=1)[:6]
    if not entities:
        # Fall back to salient common nouns, left in their natural case: forcing
        # title case here would invent proper nouns the prompt never contained.
        entities = keywords(prompt, limit=3)

    return Contract(
        objective=objective,
        audience=audience,
        register=register,
        output_format=output_format,
        target_length_tokens=target,
        forbidden_terms=tuple(unique_forbidden[:6]),
        canonical_entities=tuple(entities),
        session_id=_session_id(prompt),
        prompt_tokens=count_tokens(prompt),
    )


def suggest_n_tasks(prompt: str, minimum: int = 2, maximum: int = 16) -> int:
    """Heuristic micro-task count when the caller does not specify ``N``.

    Explicit enumeration in the prompt wins; otherwise the count scales with
    prompt length at roughly one micro-task per 60 tokens.
    """
    enum_units = len([u for u in _ENUM_SPLIT_RE.split(prompt) if u.strip()]) - 1
    if enum_units >= minimum:
        return max(minimum, min(enum_units, maximum))
    return max(minimum, min(round(count_tokens(prompt) / 60) or minimum, maximum))


_SHORT_FORMAT_DIRECTIVE = (
    "Give one line per item, as [NN] followed by the value alone. "
    "Answer only the items listed here."
)

BASELINE_FORMAT_DIRECTIVE = (
    "Give one line per item, as [NN] followed by the value alone."
)
"""The same format contract, minus the clause that only makes sense per packet.

The baseline exists to isolate *fragmentation*, so everything else must be held
equal -- and the answer format is not "everything else", it is the thing the
grader reads. On 24 August it was not held equal: fragments carried
``_SHORT_FORMAT_DIRECTIVE`` and the baseline carried nothing, so the baseline
answered in sentences, the ``any_of`` grader required equality, and the control
scored zero. Two independent defects, but they compounded in the same direction
and produced an inverted result, which is the failure mode a control is supposed
to prevent rather than cause.

"Answer only the items listed here" is dropped because the baseline is given all
the items; keeping it would be a different instruction, not the same one.
"""
"""Compressed stand-in for the prompt's format block, attached to every fragment.

The full block runs to sixty tokens and would be paid ``N`` times, since every
fragment needs it. Mandatory per-packet content is exactly what raises the
reachable ``rho`` floor -- ``rho_floor = (sum|task_i| + N*|header_i|) / |P|`` --
so the long form would push the low end of the sweep out of reach. The
directive also drops the word "answer" as a literal, which the models copied
into their replies on 24 August: 8.8 % of fragmented items came back as
"answer Osaka", right content graded wrong.
"""


def _segment_enumerated(parts: tuple[str, list[str], str], n_tasks: int,
                        answer_sheet: bool = True) -> list[str]:
    """Partition an enumerated batch by item, not by text.

    Every fragment gets the preamble, a contiguous and disjoint slice of the
    items, and a short format directive. Two invariants hold and are asserted by
    ``tests/test_item_partition.py``: **every item appears in exactly one
    fragment**, and **every fragment carries the operation**.

    The preamble is duplicated across fragments and that is a real cost, paid in
    the ``rho`` floor: mandatory per-packet content is counted ``N`` times. It is
    the right trade anyway. A fragment without the operation cannot do the task
    at any ``rho``, which is not a worse floor but a wrong answer.
    """
    preamble, items, postamble = parts
    n = max(1, min(int(n_tasks), len(items)))

    groups: list[list[str]] = [[] for _ in range(n)]
    for index, item in enumerate(items):
        groups[index * n // len(items)].append(item)

    head = preamble.strip()
    segments: list[str] = []
    for group in groups:
        body = "\n".join(group)
        # An answer sheet's postamble is boilerplate and is replaced by the
        # compressed directive. A *composition's* postamble is the contract --
        # "exactly eight paragraphs, each between 70 and 130 words, mention X
        # once, continuous prose" -- and replacing it deleted every constraint
        # the run then scored the fragments against, while the monolithic
        # baseline kept them. That is the same unequal-instruction defect that
        # inverted the baseline on 24 August, and it invalidated long_prose in
        # both V4 and V5.
        tail = _SHORT_FORMAT_DIRECTIVE if answer_sheet else postamble.strip()
        segments.append(f"{head}\n\n{body}\n\n{tail}".strip())

    # N is the independent variable of the sweep and must be honoured exactly;
    # when there are fewer items than tasks the tail fragments would be empty,
    # so the item count caps N and the caller sees the smaller number.
    return segments


_PARA_REQUEST_RE = re.compile(
    r"\bexactly\s+(one|two|three|four|five|six|\d{1,2})\s+paragraphs?\b", re.IGNORECASE)

_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}


def requested_paragraphs(prompt: str) -> int | None:
    """The paragraph count a prompt demands, when it demands one.

    A prompt that says "write exactly two paragraphs" has stated the shape of
    its own answer, and the plan should honour it: two fragments, one paragraph
    each, joined by a paragraph break. Planning three fragments for a two
    paragraph answer guarantees a structural failure no amount of context budget
    can repair -- on 24 August every fragmented composition failed
    ``paragraph_count``, at k=1 by producing four paragraphs and at k>=3 by
    producing one.

    Returns ``None`` when no count is stated, which leaves N to the sweep.
    """
    m = _PARA_REQUEST_RE.search(prompt or "")
    if not m:
        return None
    token = m.group(1).lower()
    value = _NUMBER_WORDS.get(token)
    if value is None:
        try:
            value = int(token)
        except ValueError:
            return None
    return value if 1 <= value <= 12 else None


def split_enumerated(prompt: str) -> tuple[str, list[str], str] | None:
    """Split an enumerated batch into ``(preamble, items, postamble)``.

    An enumerated prompt has three parts and they are not interchangeable. The
    **preamble** states the operation ("convert each length from metres to
    kilometres"); the **items** carry the data; the **postamble** states the
    output format. Only the items are divisible. The preamble must travel with
    every fragment, because a worker holding data and no operation cannot do the
    task -- on 24 August such a worker restated its input and the item was
    graded wrong, which is how ``unit_conversion`` fell from 80 % unfragmented
    to 3.5 % fragmented.

    Returns ``None`` when the prompt is not an enumerated batch, which leaves
    the general segmenter in charge. The bar is deliberately low -- three
    labelled items -- because the failure this prevents is severe and the cost
    of treating a two-item prompt as prose is not.
    """
    matches = list(_ITEM_LABEL_RE.finditer(prompt or ""))
    if len(matches) < 3:
        return None

    preamble = prompt[: matches[0].start()].strip()
    items: list[str] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(prompt)
        items.append(prompt[m.start():end].strip())

    # The last item's block runs to the end of the prompt and so swallows any
    # trailing format instructions. Cut it back at the first blank line: an
    # answer sheet's items are single lines, and boilerplate is what follows.
    tail = items[-1]
    if "\n\n" in tail:
        body, _, rest = tail.partition("\n\n")
        items[-1] = body.strip()
        postamble = rest.strip()
    else:
        postamble = ""
    return preamble, items, postamble


def _segment(prompt: str, n_tasks: int, answer_sheet: bool = True) -> list[str]:
    """Split ``prompt`` into exactly ``n_tasks`` non-empty units of work.

    Enumerated prompts split on their own bullets; otherwise sentences are
    packed into ``n_tasks`` roughly equal-token groups. When there is less
    material than requested tasks, the prompt is sliced by *tokens* instead of
    duplicating sentences: duplicating would inflate ``sum(|task_i|)`` above
    ``|P|`` and make ``rho = 1.0`` unreachable, destroying the floor of the
    sweep. ``N`` is always honoured exactly -- the sweep needs ``N`` to be the
    independent variable, not a suggestion.
    """
    enumerated = split_enumerated(prompt)
    if enumerated is not None:
        return _segment_enumerated(enumerated, n_tasks, answer_sheet=answer_sheet)

    units = [u.strip() for u in _ENUM_SPLIT_RE.split(prompt) if u.strip()]
    if len(units) < n_tasks:
        units = [s for s in split_sentences(prompt) if s.strip()]
    if not units:
        units = [prompt.strip() or "Answer the request."]

    if len(units) >= n_tasks:
        # Contiguous balanced partition. Every group gets at least one unit and
        # no unit is ever emitted twice -- duplicating a unit would inflate
        # sum(|task_i|) and silently raise the reachable rho floor.
        total = sum(count_tokens(u) for u in units)
        quota = total / n_tasks
        groups: list[list[str]] = []
        cursor = 0
        for group_index in range(n_tasks):
            groups_left = n_tasks - group_index - 1
            take = 1
            acc = count_tokens(units[cursor])
            while (
                cursor + take < len(units)
                and (len(units) - (cursor + take)) > groups_left
                and acc < quota
            ):
                acc += count_tokens(units[cursor + take])
                take += 1
            groups.append(units[cursor : cursor + take])
            cursor += take
        if cursor < len(units):  # sweep up any remainder
            groups[-1].extend(units[cursor:])
        return [" ".join(group) for group in groups]

    # Fewer natural units than requested tasks: slice the prompt by tokens.
    chunks = split_into_token_chunks(prompt.strip(), n_tasks)
    return [
        chunk.strip() or f"Part {i + 1} of {n_tasks} of the request."
        for i, chunk in enumerate(chunks)
    ]


def plan(
    prompt: str,
    backend: Any | None = None,
    *,
    n_tasks: int | None = None,
    contract: Contract | None = None,
    force_sequential: bool | None = None,
    answer_sheet: bool = True,
) -> Plan:
    """Build the micro-task DAG for ``prompt``.

    Two dependency topologies are produced, chosen by whether the prompt
    contains sequential-dependency markers:

    * **Chain** (sequential prompts): ``t0 -> t1 -> ... -> t{N-1}``. One task
      per level, so the DAG admits no parallelism at all -- which is exactly
      the honest answer for a prompt whose step ``i`` needs step ``i-1``.
    * **Fan-in** (parallel prompts): ``t0 .. t{N-2}`` are mutually independent
      and sit on level 0; the final task integrates them and sits on level 1.

    Args:
        prompt: The raw user prompt.
        backend: Optional backend (forwarded to :func:`global_contract`).
        n_tasks: Number of micro-tasks. Defaults to :func:`suggest_n_tasks`.
        contract: Reuse an already-computed contract.
        force_sequential: Override the sequential/parallel detection.

    Returns:
        A validated :class:`~swarmbly_v0.schema.Plan`.
    """
    from .router import extract_features  # local import avoids a cycle

    count = n_tasks if n_tasks is not None else suggest_n_tasks(prompt)
    count = max(1, int(count))
    gamma = contract or global_contract(prompt, backend)

    if force_sequential is None:
        features = extract_features(prompt)
        sequential = features["sequential_cues"] >= 0.45 or features["continuity_cues"] >= 0.55
    else:
        sequential = bool(force_sequential)

    segments = _segment(prompt, count, answer_sheet=answer_sheet)
    canonical = list(gamma.canonical_entities)

    tasks: list[Task] = []
    for i, segment in enumerate(segments):
        task_id = f"t{i}"
        local_entities = extract_entities(segment, min_mentions=1)[:3]
        expected = [e for e in canonical if e.lower() in segment.lower()] or local_entities
        if not expected and canonical:
            expected = [canonical[i % len(canonical)]]

        if sequential:
            deps = (f"t{i - 1}",) if i > 0 else ()
            kind = "step"
        elif count > 1 and i == count - 1:
            deps = tuple(f"t{j}" for j in range(count - 1))
            kind = "integration"
        else:
            deps = ()
            kind = "section"

        # The integration node's extra directive is kept deliberately short:
        # it is mandatory (untrimmable) packet content, so every token of it is
        # paid N-independently and pushes up the reachable rho floor.
        instruction = f"{segment} Close the answer; do not repeat earlier parts." \
            if kind == "integration" else segment

        tasks.append(
            Task(
                task_id=task_id,
                instruction=instruction,
                depends_on=deps,
                expected_entities=tuple(expected[:3]),
                kind=kind,
            )
        )

    return Plan(prompt=prompt, tasks=tasks, sequential=sequential)


_CONSUMES_RE = re.compile(
    r"\b(?:"
    r"from step\s+\d+|in step\s+\d+|of step\s+\d+|step\s+\d+'s|"
    r"the previous step|the step before|the preceding step|"
    r"you (?:derived|computed|calculated|obtained|just found)|"
    r"the (?:result|value|figure|total|output) (?:from|of) (?:the )?(?:previous|preceding|step)"
    r")\b", re.IGNORECASE)
"""Does this task text consume a value another task produces?

The signal that decides whether a predecessor's output is mandatory context or
merely useful context, and it has to be read from the text rather than from the
plan's shape. ``Plan.sequential`` is true for *any* enumerated segmentation,
including an item batch whose items are wholly independent -- so gating on it
forced a predecessor's answers into packets that had no use for them, and the
successors restated those answers as their own: an enumerated corpus reported 379
graded items against a key holding 150.

"Divide the net value **from step 2**" consumes. "[01] pallet R752, 251 kg" does
not. The distinction is in the words, so that is where it is read.
"""


def consumes_predecessor(task_text: str) -> bool:
    """True when this task cannot be answered without a prior task's output."""
    return bool(_CONSUMES_RE.search(task_text or ""))


_CARRY_RE = re.compile(r"^\s*[\[(]?(\d{1,3})[\]).:]\s*(.+?)\s*$", re.MULTILINE)
_CARRY_VALUE_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def carry_values(text: str) -> dict[str, str]:
    """The labelled values a fragment produced, keyed by item id.

    A *typed carry*, as opposed to the prose summary below. The distinction is
    the whole dependency-axis argument in one function.

    On V4's chain corpus, step 3 says "divide the net value from step 2 by four".
    What the successor needs from step 2 is the number 2247 -- and what it got
    was :func:`summarize_fragment`'s output: a lead sentence plus an entity list,
    forty tokens of prose, competing for a rationed context budget with the
    glossary and the contract header. A chain whose carried value can be
    truncated away is a chain that breaks, and V4 measured it breaking: +47.2 %
    coherence tax at the widest fragment, where prose cost +5.1 % and tables
    +3.3 % on fragments of identical size, with accuracy falling monotonically
    0.259 -> 0.091 as the partition got finer.

    The gain is **completeness, not cheapness** -- an earlier draft of this
    docstring predicted that rho would fall, and measurement said otherwise.
    :func:`summarize_fragment` is extractive: it keeps the *lead sentence* and
    drops everything after it. A fragment that produced steps 3, 4 and 5 hands
    its successor step 3 and an entity list. The typed carry hands over all
    three, for 10 tokens against the prose summary's 4 on a terse fragment and
    15 against 16 on a verbose one.

    So the honest prediction is one-sided on accuracy and explicit about its
    cost: chain accuracy should rise sharply because the successor now receives
    the value it is told to consume, and rho may rise modestly because delivering
    three values costs more than delivering one. A version of this that were
    also cheaper would be better; this one is not, and reporting it as if it were
    would misdescribe the trade.

    Returns an empty mapping when the fragment has no labelled items, which is
    every prose fragment -- so the caller can ask for a typed carry
    unconditionally and get the prose summary wherever typing does not apply.
    """
    out: dict[str, str] = {}
    for match in _CARRY_RE.finditer(text or ""):
        item_id, body = match.group(1).zfill(2), match.group(2).strip()
        if not body:
            continue
        # The *last* number in the line, for the same reason grade_answer takes
        # it: a model that shows its work ends on the answer.
        numbers = _CARRY_VALUE_RE.findall(body)
        out[item_id] = numbers[-1].replace(",", "") if numbers else body
    return out


def summarize_fragment(text: str, max_tokens: int = 40, typed: bool = False) -> str:
    """Compress a produced fragment into a predecessor summary.

    This is the *other* knob on ``rho``: the summary length is what a
    successor packet pays to know what its predecessors already said. The
    implementation is extractive (lead sentence plus the entity list), which
    keeps the harness deterministic and backend-independent.
    """
    if typed:
        carried = carry_values(text)
        if carried:
            return " ".join(f"[{item}]={value}" for item, value in sorted(carried.items()))

    sentences = split_sentences(text)
    if not sentences:
        return ""
    lead = sentences[0]
    entities = extract_entities(text, min_mentions=1)[:4]
    tail = f" Entities covered: {', '.join(entities)}." if entities else ""
    return truncate_tokens(f"{lead}{tail}", max_tokens).strip()
