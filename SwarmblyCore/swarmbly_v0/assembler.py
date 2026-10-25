"""Select-then-splice assembly.

The v0.1 design generated a bridge at every junction whose cosine fell below a
fixed ``tau_sem = 0.85``. Two things are wrong with that and both are fixed
here:

1. **The threshold is calibrated, not fixed.** ``tau_sem`` is an argument, and
   :func:`~swarmbly_v0.metrics.calibrate_tau` is what produces it.
2. **Synthesis is the exception, not the rule.** Every bridge is an extra
   generation call *and* an extra opportunity to introduce an error, so the
   assembler splices by default and only synthesises when the seam is measured
   to be bad. This is the "select-then-splice, synthesise on conflict" policy:
   selection is cheap and lossless, synthesis is expensive and lossy.

The cosine is used for exactly one job -- **detecting seams** -- and for
nothing else. The master document is explicit that cosine similarity cannot
serve as a fraud or quality check (a node can trivially clear a cosine
threshold with cheap plausible text); that job belongs to TOPLOC-style
commitments and sampled auditing in later phases.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from .schema import Assembly, Contract, Fragment, Plan, SeamRecord
from .metrics import quality_judge
from .textutil import split_sentences, tokenize, truncate_tokens

__all__ = ["select_then_splice", "boundary_windows", "DEFAULT_WINDOW_TOKENS"]

DEFAULT_WINDOW_TOKENS = 40
"""Tokens of context on each side of a junction used for seam detection."""

_BRIDGE_MARKER = "[BRIDGE]"


def _tail(text: str, n_tokens: int) -> str:
    """Last ``n_tokens`` tokens of ``text``, at a token boundary."""
    spans = [m for m in _iter_token_spans(text)]
    if len(spans) <= n_tokens:
        return text
    return text[spans[-n_tokens][0]:]


def _iter_token_spans(text: str) -> list[tuple[int, int]]:
    from .textutil import _TOKEN_RE  # single source of truth for tokenisation

    return [m.span() for m in _TOKEN_RE.finditer(text or "")]


def boundary_windows(
    left: str, right: str, window_tokens: int = DEFAULT_WINDOW_TOKENS
) -> tuple[str, str]:
    """The two text windows that straddle a junction.

    Seam detection compares the *end* of what came before with the *start* of
    what comes next. Comparing whole fragments would mostly measure "are these
    about the same document", which every fragment of one answer trivially is.
    """
    return _tail(left, window_tokens), truncate_tokens(right, window_tokens)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _ensure_terminated(text: str) -> str:
    stripped = text.rstrip()
    if not stripped:
        return stripped
    return stripped if stripped[-1] in ".!?:;" else stripped + "."


def _order_fragments(fragments: Sequence[Fragment], plan: Plan | None) -> list[Fragment]:
    """Order fragments by the plan's topological order when available.

    Falls back to the fragments' own ``order`` field. Any fragment not named by
    the plan is appended in a stable way rather than dropped -- losing a
    fragment silently would corrupt the experiment.
    """
    by_id = {f.task_id: f for f in fragments}
    ordered: list[Fragment] = []
    if plan is not None:
        for task_id in plan.topological_order():
            if task_id in by_id:
                ordered.append(by_id.pop(task_id))
    leftovers = sorted(by_id.values(), key=lambda f: (f.order, f.task_id))
    ordered.extend(leftovers)
    return ordered


def _join(pieces: Sequence[str], paragraph_join: bool | int) -> str:
    """Splice the fragments, inserting the requested number of paragraph breaks.

    The rule this replaces tied the two together: a composition asking for P
    paragraphs was planned as P fragments and every junction became a break.
    That fixed a real defect -- on 24 August every k>=3 composition came back as
    one block where two were required -- but it did so by making the number of
    *workers* equal the number of *paragraphs*, and those are different things.
    The cost only became visible when fragment size became the variable under
    study: the sweep asked for N in (2, 4, 8, 16) and every cell came back at
    N = 6, because the prompt said "exactly six paragraphs" and the planner
    obeyed the prompt instead of the experiment.

    So the two are decoupled here. ``paragraph_join`` may be:

    * ``False`` -- splice with spaces, the plain case;
    * ``True`` -- a break at every junction, the old behaviour;
    * an integer P -- produce exactly P paragraphs, by grouping the fragments
      into P contiguous, balanced buckets.

    With N > P the extra fragments join inside a paragraph, which is what a
    paragraph made of several workers' output should look like. With N < P the
    breaks available are fewer than the breaks required, and the shortfall is
    left to fail honestly rather than being papered over: a partition too coarse
    to express the requested shape *is* a finding about the partition.
    """
    if not pieces:
        return ""
    if paragraph_join is True:
        return "\n\n".join(pieces)
    if not paragraph_join:
        return " ".join(pieces)

    wanted = max(1, min(int(paragraph_join), len(pieces)))
    per_group, remainder = divmod(len(pieces), wanted)
    groups: list[str] = []
    cursor = 0
    for index in range(wanted):
        size = per_group + (1 if index < remainder else 0)
        groups.append(" ".join(pieces[cursor:cursor + size]))
        cursor += size
    return "\n\n".join(g for g in groups if g)


def select_then_splice(
    fragments: Sequence[Fragment],
    contract: Contract,
    backend: Any,
    tau_sem: float,
    plan: Plan | None = None,
    embedder: Any | None = None,
    window_tokens: int = DEFAULT_WINDOW_TOKENS,
    paragraph_join: bool | int = False,
) -> Assembly:
    """Assemble fragments into one answer, bridging only where the seam is bad.

    Args:
        fragments: One :class:`~swarmbly_v0.schema.Fragment` per micro-task,
            each holding one or more candidate generations.
        contract: The global contract, used to judge candidates.
        backend: Used for embeddings (seam detection) and, only when a seam
            fails the threshold, for bridge synthesis.
        tau_sem: Seam threshold. A junction whose boundary-window cosine is
            **below** ``tau_sem`` is declared a seam and gets a bridge. Obtain
            this from :func:`~swarmbly_v0.metrics.calibrate_tau`; do not hardcode.
        plan: Supplies the assembly order (topological).
        embedder: Overrides ``backend`` for embeddings.
        window_tokens: Size of the boundary windows.

    Returns:
        An :class:`~swarmbly_v0.schema.Assembly` with the text, one
        :class:`~swarmbly_v0.schema.SeamRecord` per junction, the per-fragment
        judge scores, and the sentence offset at which each fragment starts
        (which lets the taxonomy attribute seam-local errors exactly).
    """
    embed_source = embedder if embedder is not None else backend
    ordered = _order_fragments(fragments, plan)
    if not ordered:
        return Assembly(text="", seams=[], selected={}, judge_scores={},
                        fragment_sentence_offsets=[], order=[])

    # -- select -----------------------------------------------------------
    selected: dict[str, str] = {}
    judge_scores: dict[str, float] = {}
    for fragment in ordered:
        candidates = [c for c in fragment.candidates if c and c.strip()]
        if not candidates:
            selected[fragment.task_id] = ""
            judge_scores[fragment.task_id] = 0.0
            continue
        if len(candidates) == 1:
            best, best_score = candidates[0], quality_judge(
                candidates[0], contract, embed_source
            )
        else:
            scored = [(quality_judge(c, contract, embed_source), i, c)
                      for i, c in enumerate(candidates)]
            # Ties break toward the earlier candidate for determinism.
            best_score, _, best = max(scored, key=lambda t: (t[0], -t[1]))
        selected[fragment.task_id] = best
        judge_scores[fragment.task_id] = float(best_score)

    # -- splice -----------------------------------------------------------
    pieces: list[str] = []
    offsets: list[int] = []
    seams: list[SeamRecord] = []
    sentence_cursor = 0
    previous_task = ""

    for index, fragment in enumerate(ordered):
        text = _ensure_terminated(selected[fragment.task_id])
        if not text:
            offsets.append(sentence_cursor)
            continue

        if pieces:
            left_window, right_window = boundary_windows(pieces[-1], text, window_tokens)
            vectors = np.asarray(
                embed_source.embed([left_window, right_window]), dtype=np.float64
            )
            similarity = _cosine(vectors[0], vectors[1])
            bridged = similarity < tau_sem
            bridge_text = ""
            if bridged:
                bridge_prompt = (
                    f"{left_window}\n{_BRIDGE_MARKER}\n{right_window}\n"
                    f"register: {contract.register}\n"
                    "Write one sentence that links the passage above to the passage below."
                )
                try:
                    bridge_text = _ensure_terminated(
                        backend.generate(bridge_prompt, max_tokens=48).strip()
                    )
                except Exception:
                    bridge_text = ""  # never let a bridge failure lose a fragment
                if bridge_text:
                    pieces.append(bridge_text)
                    sentence_cursor += len(split_sentences(bridge_text))
                else:
                    bridged = False
            seams.append(
                SeamRecord(
                    index=index - 1,
                    left_task=previous_task,
                    right_task=fragment.task_id,
                    similarity=float(similarity),
                    tau_sem=float(tau_sem),
                    bridged=bool(bridged),
                    bridge_text=bridge_text,
                )
            )

        offsets.append(sentence_cursor)
        pieces.append(text)
        sentence_cursor += len(split_sentences(text))
        previous_task = fragment.task_id

    assembled = _join(pieces, paragraph_join)
    total_sentences = len(split_sentences(assembled))
    offsets = [min(o, max(total_sentences - 1, 0)) for o in offsets]

    return Assembly(
        text=assembled,
        seams=seams,
        selected=selected,
        judge_scores=judge_scores,
        fragment_sentence_offsets=offsets,
        order=[f.task_id for f in ordered],
    )


def fragments_from_mapping(
    mapping: Mapping[str, Sequence[str]], plan: Plan | None = None
) -> list[Fragment]:
    """Convenience: build :class:`Fragment` objects from ``task_id -> candidates``."""
    order_lookup = {tid: i for i, tid in enumerate(plan.task_ids)} if plan else {}
    return [
        Fragment(task_id=task_id, candidates=list(candidates),
                 order=order_lookup.get(task_id, i))
        for i, (task_id, candidates) in enumerate(mapping.items())
    ]


def _token_len(text: str) -> int:  # diagnostics helper
    return len(tokenize(text))
