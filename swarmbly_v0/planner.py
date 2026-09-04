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
           "global_contract", "ordering_text", "plan", "reference_map",
           "references_are_recoverable",
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


def ordering_text(prompt: str) -> str:
    """The part of ``prompt`` that says in what ORDER the work must be done.

    Used for the dependency decision in :func:`plan`, and for nothing else. An
    enumerated batch has three parts (see :func:`split_enumerated`) and only two
    of them are about the work: the preamble states the operation and the items
    carry the data. The **postamble states the shape of the answer**, and reading
    a dependency out of it is a category error with a measured cost.

    ``prompts/ground_truth.json`` writes its format block as *"Begin the line
    with the item number in square brackets, exactly as given, **then** a single
    space, **then** the value."* That ``then`` means "next character", not "after
    the previous step has finished". ``router._SEQUENTIAL_CUES`` contains
    ``\\bthen\\b``, one cue is enough to clear the 0.45 gate
    (``_saturate(1, 1.5) = 0.487``), and so **all fifteen** prompts of that
    corpus were planned as four-deep CHAINS -- on a corpus whose every prompt
    says, in as many words: *"Items are independent: the answer to one must not
    depend on the answer to any other, and you must not reconcile them against
    each other."*

    Two things follow from the wrong topology, and the second is a measurement
    defect rather than an inefficiency:

    * ``n_levels`` is ``N`` instead of 2, so the critical path -- the thing that
      bounds any achievable speedup -- is reported as admitting no parallelism
      for a bag of items that is nothing but parallel.
    * every task acquires a dependency edge, so **every fragment but the first**
      is handed its predecessor's reply as context. On an answer sheet that reply
      is a block of *answer lines* (``[01] 576``), sitting directly above a task
      block that says "answer only the items listed here". In the v3c-gt cell
      (rho 2.5, N=4) that put a predecessor's answers into **42 of 60**
      dispatched packets, against **0 of 15** monolithic prompts. The harm is the
      one :func:`~swarmbly_v0.packing.carry_block` already documents for the
      mandatory path -- "the successor restates them as its own, and an
      enumerated corpus reported 379 graded items against a key holding 150" --
      arriving through the optional path instead.

    The router's own feature vector is deliberately left alone: it reads the
    whole prompt, its evaluation is published, and this is a question about the
    plan, not about whether to fragment at all.
    """
    parts = split_enumerated(prompt or "")
    if parts is None:
        return prompt or ""
    preamble, items, postamble = parts
    if not postamble.strip():
        return prompt or ""
    return "\n".join([preamble, *items]).strip()


_LABELLED_LINE_RE = re.compile(r"^\s*[\[(]([A-Za-z][\w\-]{0,30}|\d{1,3})[\])]\s*(.*)$")
"""A line that opens with a bracketed label. Alphanumeric, unlike
:data:`_ITEM_LABEL_RE`, which requires digits and is why the fact-graph corpus
fell through to sentence packing."""

_VALUE_RE = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?(?![\w])")
"""A standalone numeric VALUE, not a digit.

The first version of this classifier asked whether a line contained a digit at
all, and every ask line in the fact-graph corpus contains one -- ``[c_s1] the
total for Depot group 1`` has two, in the label and in the ordinal. It
classified every question as data, found no questions, and returned ``None``:
the repair silently did nothing while its tests passed. What separates a
question from a row of data is not the presence of digits but **how many
values** it carries, and a value is a whole token, so ``c_s1`` and ``s1`` do not
count and ``440`` does."""

MAX_VALUES_IN_AN_ASK: int = 1
"""Above this many numeric values a labelled line is data, not a question.

One admits the ordinal a question needs -- "the total for Depot group 1" -- and
excludes a table row. It is a crude line and it FAILS CLOSED: a
misclassification leaves fewer than two asks or no material,
:func:`reference_map` returns ``None``, and the segmenter behaves exactly as it
did before. The risk this threshold carries is under-firing, which costs the
repair; not over-firing, which would move an existing partition."""

"""A reference is a token that names exactly ONE material unit.

The first formulation required two consecutive shared content words, on the
reasoning that one shared word is noise -- "total", "group", "value" appear in
every prompt this project has. It was the wrong axis. It matched "depot group"
against all four sections and nothing at all in the chain class, whose questions
name a single proper noun: "the running total after adding Mombasa".

What makes a token a reference is not its length but whether it DISCRIMINATES.
A token appearing in exactly one material unit is that unit's name, whether it
is ``mombasa`` or ``4``; a token appearing in all of them says only that they
are the same kind of thing. So the rule is uniqueness, and it covers both cases
with one mechanism instead of two thresholds."""


def _content_sequence(text: str) -> list[str]:
    """Content words AND standalone numerals, in order.

    ``textutil.content_words`` drops any token not starting with a letter, and
    that dropped the only token that discriminates. The four section titles of a
    fact-graph instance are "Depot group 1" ... "Depot group 4", and the four
    questions say "the total for Depot group N": on content words alone every
    question shares "depot group" with every section, every referent set is
    identical, and the partition cannot be built. The numeral is the name.
    """
    from .textutil import STOPWORDS

    out: list[str] = []
    for token in re.findall(r"[\w']+", text.lower()):
        if token.isdigit():
            out.append(token)
        elif token[0].isalpha() and token not in STOPWORDS and len(token) > 2:
            out.append(token)
    return out


def _discriminating_tokens(material: dict[int, str]) -> dict[str, int]:
    """``{token: the one material unit it names}``, for tokens naming exactly one.

    A token in every unit ("group", "units", "dwell") carries no information
    about which is meant; a token in exactly one is that unit's name. Computed
    over the material as a whole rather than per unit, because uniqueness is a
    property of the set.
    """
    owners: dict[str, set[int]] = {}
    for index, text in material.items():
        for token in set(_content_sequence(text)):
            owners.setdefault(token, set()).add(index)
    return {token: next(iter(units)) for token, units in owners.items()
            if len(units) == 1}


def _labelled_units(prompt: str) -> dict[int, str]:
    """``{line index: that unit's full text}`` for every bracket-labelled line.

    A unit is the labelled line plus the unlabelled lines beneath it, because a
    table's rows sit under their section header and carry no label of their own.
    Attaching them BEFORE anything is counted is what lets a section be told
    from a question at all: the header alone carries one value, the header with
    its four rows carries five.
    """
    units: dict[int, str] = {}
    current: int | None = None
    for index, line in enumerate((prompt or "").split("\n")):
        match = _LABELLED_LINE_RE.match(line)
        if match is not None:
            units[index] = line.strip()
            current = index
        elif current is not None and line.strip():
            units[current] += " " + line.strip()
        elif not line.strip():
            current = None
    return units


def reference_map(prompt: str) -> dict[int, set[int]] | None:
    """Which material lines each ASK line refers to, or ``None`` if unrecoverable.

    The repair for the defect of 4 September, and the honest half of it is the
    ``None``.

    ``_segment`` partitions a prompt by position and token count. On a prompt
    that states its questions in one place and its material in another -- a
    brief plus an appendix, a question list plus a document -- a contiguous cut
    falls between them. Measured on ``benchmark_v7``'s ``map`` class, the most
    partitionable task available: one packet received all four questions and
    none of the data, the three holding the data were asked nothing, and one
    section was split across two of them. The oracle arm scored 1.000 on the
    same instances with the same worker, so the partition was viable and the
    implementation lost everything.

    Six versions did not see it because every corpus this project has run puts a
    question and its data in the SAME item -- ``[01] 21 crates, 16 units per
    crate`` -- so a contiguous cut keeps them together by accident of format.

    **The rule.** A line is an *ask* when it carries a bracketed label and no
    digit; it is *material* when it carries a label and a digit, or sits under
    one that does. An ask REFERS to a material line when the two share a phrase
    of :data:`MIN_REFERENCE_PHRASE_WORDS` consecutive content words -- a name,
    not a keyword. No model, no semantics, and nothing that can drift.

    **The refusal.** ``None`` whenever the shape is not present, and -- this is
    the load-bearing case -- whenever the shape IS present but some ask refers
    to nothing. A prompt whose questions cannot be linked to their material
    must not be fragmented at all, and :func:`plan` propagates that: see
    :func:`references_are_recoverable`.

    Returns:
        ``{ask line index: {material line indices}}`` over the prompt's lines,
        or ``None``. An empty dict is never returned: no asks means no shape.
    """
    units = _labelled_units(prompt)
    asks = {index: text for index, text in units.items()
            if len(_VALUE_RE.findall(text)) <= MAX_VALUES_IN_AN_ASK}
    material = {index: text for index, text in units.items() if index not in asks}

    # Both kinds must exist, or there is nothing to keep together. Two asks and
    # one material unit is the smallest shape where a contiguous cut can
    # separate a question from its data.
    if len(asks) < 2 or not material:
        return None

    names = _discriminating_tokens(material)
    if not names:
        # Nothing in the material is nameable, so no map over it is
        # trustworthy -- four identical-looking sections, say.
        return None

    mapping: dict[int, set[int]] = {}
    for ask_index, ask_text in asks.items():
        hits = {names[token] for token in set(_content_sequence(ask_text))
                if token in names}
        if not hits:
            # One ask with no recoverable referent poisons the whole map. Not a
            # partial map: a partition that keeps three questions with their
            # data and strands the fourth is worse than refusing, because it
            # produces a figure with one silently unanswerable claim in it.
            return None
        mapping[ask_index] = hits
    return mapping


def references_are_recoverable(prompt: str) -> bool:
    """``False`` only when the question/material shape is present and unlinkable.

    The gate half of the fused repair, and the asymmetry is deliberate. A prompt
    with no such shape returns ``True``: it is the ordinary case, six corpora
    are built that way, and refusing it would withdraw every figure this project
    has. A prompt WITH the shape returns ``True`` when every ask can be linked
    to its material and ``False`` when one cannot.

    So the scope is preserved wherever the dependency is recoverable and
    narrowed only where it is not, which is the difference between saying "this
    architecture fragments problems" and "this architecture fragments problems
    whose items are self-contained".
    """
    if not _has_question_material_shape(prompt):
        return True
    mapping = reference_map(prompt)
    if mapping is None:
        return False
    # A map is not enough: the partition has to be BUILDABLE. Two questions
    # that need the same rows cannot both have them without emitting those rows
    # twice, and duplicating a unit inflates ``sum(|task_i|)`` above ``|P|`` and
    # raises the reachable rho floor -- which is why `_segment` has always
    # refused to do it.
    #
    # This is the residual of the repair and it is worth naming precisely. The
    # ORACLE partition duplicates freely: `_oracle_partition` hands each claim
    # exactly the facts it requires and those sets overlap. So the partition
    # that is viable in principle is a COVERING, not a partition, and rho --
    # defined as sum(|K_i|)/|P| -- charges for every duplicated token. The
    # architecture's low-rho pitch and its own oracle are in tension, and no
    # segmenter can resolve that; it is an architecture decision. Until it is
    # made, a prompt whose questions need overlapping material is refused rather
    # than mis-packed.
    return _segment_by_reference(prompt, 2, mapping) is not None


def _has_question_material_shape(prompt: str) -> bool:
    """Are there at least two label-only lines and one line carrying data?

    Cheap and deliberately separate from :func:`reference_map`, because "the
    shape is absent" and "the shape is present and unlinkable" are different
    answers and the router treats them differently.
    """
    units = _labelled_units(prompt)
    asks = sum(1 for text in units.values()
               if len(_VALUE_RE.findall(text)) <= MAX_VALUES_IN_AN_ASK)
    return asks >= 2 and (len(units) - asks) >= 1


def _segment_by_reference(prompt: str, n_tasks: int,
                          mapping: dict[int, set[int]]) -> list[str] | None:
    """Group the prompt's lines so every ask travels with what it refers to.

    Each group is one ask plus the material it names. ``n_tasks`` is honoured
    exactly, as everywhere else in this module -- the sweep needs ``N`` to be the
    independent variable and not a suggestion -- so groups are merged when there
    are more asks than tasks, and the largest is split when there are fewer.

    ``None`` when a material line is referred to by more than one ask. Emitting
    it twice would inflate ``sum(|task_i|)`` above ``|P|`` and raise the
    reachable ``rho`` floor -- the same reason ``_segment`` refuses to duplicate
    a unit -- and emitting it once would strand the other ask. Refusing is the
    honest answer and the router turns it into a refusal to fragment.
    """
    seen: set[int] = set()
    for referents in mapping.values():
        if seen & referents:
            return None
        seen |= referents

    lines = prompt.split("\n")
    blocks: list[list[int]] = []
    for ask_index in sorted(mapping):
        blocks.append([ask_index, *sorted(mapping[ask_index])])
    if not blocks:
        return None

    # Lines belonging to no block -- the preamble and the format directive --
    # ride with the nearest block rather than becoming a task of their own. A
    # packet holding only an output-format directive is the t1 of the V7 map
    # instance: it was dispatched, it cost tokens, and it could answer nothing.
    claimed = {i for block in blocks for i in block}
    for index, line in enumerate(lines):
        if index in claimed or not line.strip():
            continue
        nearest = min(blocks, key=lambda b: min(abs(index - i) for i in b))
        nearest.append(index)

    groups = [sorted(set(block)) for block in blocks]
    while len(groups) > n_tasks:
        smallest = min(range(len(groups) - 1),
                       key=lambda i: len(groups[i]) + len(groups[i + 1]))
        groups[smallest] = sorted(set(groups[smallest] + groups[smallest + 1]))
        del groups[smallest + 1]
    while len(groups) < n_tasks:
        largest = max(range(len(groups)), key=lambda i: len(groups[i]))
        block = groups[largest]
        if len(block) < 2:
            return None
        half = len(block) // 2
        groups[largest:largest + 1] = [block[:half], block[half:]]

    return ["\n".join(lines[i] for i in group).strip() or "Answer the request."
            for group in groups]


def _segment(prompt: str, n_tasks: int, answer_sheet: bool = True) -> list[str]:
    """Split ``prompt`` into exactly ``n_tasks`` non-empty units of work.

    Three paths, in order of how much they know about the prompt:

    1. **An enumerated batch** splits on its own bullets. The preamble travels
       with every fragment (see :func:`split_enumerated`).
    2. **A question/material shape** splits so that every question travels with
       the material it refers to (see :func:`reference_map`). Added 4 September
       2026, after the token-balanced path below put all four questions of a
       ``map`` instance in one packet and all the data in the other three.
    3. **Otherwise** sentences are packed into ``n_tasks`` roughly equal-token
       groups.

    When there is less material than requested tasks, the prompt is sliced by
    *tokens* instead of duplicating sentences: duplicating would inflate
    ``sum(|task_i|)`` above ``|P|`` and make ``rho = 1.0`` unreachable,
    destroying the floor of the sweep. ``N`` is always honoured exactly -- the
    sweep needs ``N`` to be the independent variable, not a suggestion.

    Path 2 is **never** reached on a prompt that has no such shape, which is
    every corpus this project has run: their questions and data sit in the same
    item. That is asserted rather than assumed --
    ``test_no_existing_corpus_prompt_changes_partition`` compares the partition
    before and after on all five corpora, because a segmenter change that moved
    an existing partition would silently invalidate every published figure.
    """
    enumerated = split_enumerated(prompt)
    if enumerated is not None:
        return _segment_enumerated(enumerated, n_tasks, answer_sheet=answer_sheet)

    mapping = reference_map(prompt)
    if mapping is not None:
        grouped = _segment_by_reference(prompt, n_tasks, mapping)
        if grouped is not None:
            return grouped

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


def expected_entities_for(text: str, limit: int = 3) -> list[str]:
    """The entities a correct answer about ``text`` should name.

    One extraction rule, applied either to a whole prompt or to one segment of
    it, so that the standard a coherence metric holds an answer to can be
    computed *without reference to the partition*. Applied to a segment it gives
    that task's expected entities; applied to the whole prompt it gives the
    arm-independent set both the monolithic and the fragmented arm are scored
    against.

    Before this existed the omission detector took its standard from the union
    over ``plan.tasks[].expected_entities`` -- three per task, so the standard
    grew with N: 6 entities at N=2 and 17 at N=8 on the table corpus, against 0
    for a baseline that passes no plan at all.
    """
    return extract_entities(text, min_mentions=1)[:limit]


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

    # The gate half of the fused repair of 4 September. See
    # `references_are_recoverable`.
    #
    # A prompt that states its questions apart from its material can only be
    # fragmented if each question can be linked to the material that answers
    # it. Where the link is recoverable, `_segment` builds the partition and
    # nothing here changes. Where it is NOT -- every question needs every
    # section, or one question refers to nothing nameable -- the honest plan is
    # a single task, because the alternative is what was measured on 4
    # September: one packet holding four questions and no data, three holding
    # the data and asked nothing, and a claim split across two of them.
    #
    # N is otherwise honoured exactly everywhere in this module, and this is the
    # one place it is not. That is deliberate and it is visible: `plan.n_tasks`
    # comes back as 1, `rho_achieved` follows, and a sweep cell that collapsed
    # says so in its own row rather than reporting a fragmented figure for a
    # prompt that was never fragmented.
    #
    # It fires on NOTHING in any existing corpus: 0 of 456 partitions move
    # across five corpora at N in {2,3,4,8}, asserted by
    # `test_no_existing_corpus_partition_moves`. A gate that silently re-planned
    # published cells would invalidate every figure this project has.
    if count > 1 and not references_are_recoverable(prompt):
        count = 1

    if force_sequential is None:
        # From the work, not from the answer's format block. See `ordering_text`:
        # "then a single space, then the value" is typography, and reading it as
        # a dependency made every prompt in the ground-truth corpus a chain.
        features = extract_features(ordering_text(prompt))
        sequential = features["sequential_cues"] >= 0.45 or features["continuity_cues"] >= 0.55
    else:
        sequential = bool(force_sequential)

    segments = _segment(prompt, count, answer_sheet=answer_sheet)
    canonical = list(gamma.canonical_entities)

    tasks: list[Task] = []
    for i, segment in enumerate(segments):
        task_id = f"t{i}"
        local_entities = expected_entities_for(segment)
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


# The bracketed form may be followed by anything. The BARE form -- ``07.`` or
# ``07:`` with no bracket -- must be followed by whitespace, and that is not
# cosmetic: written with ``\s*`` the pattern reads the decimal point of a number
# as a label terminator, so a line reading "42.5 km is the remainder" is parsed
# as item 42 with the value 5.
#
# This is the same defect as ``ITEM_LABEL_RE`` in grading.py, in the sibling
# regex, and here it is worse. ``ITEM_LABEL_RE`` only mis-scores; this one
# *writes*. ``carry_values`` feeds ``summarize_fragment(typed=True)``, whose
# output goes into the successor's packet as its predecessor block -- so a
# phantom ``[42]=5`` is handed to the next model as though a predecessor had
# produced it. The successor then restates it, which is exactly the restatement
# ``task_item_scope`` exists to remove, and the bias is one-sided, grows with N,
# and exists only in the typed-carry arm: it points the same way as the headline
# that arm was built to produce.
_CARRY_RE = re.compile(
    r"^\s*(?:[\[(](\d{1,3})[\])]|(\d{1,3})[.:](?=\s))\s*(.+?)\s*$", re.MULTILINE)
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
        # Two id groups: the bracketed form and the bare form.
        item_id = (match.group(1) or match.group(2)).zfill(2)
        body = match.group(3).strip()
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
