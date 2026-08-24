"""Generation and embedding backends for the V0 coherence-tax harness.

Three things live here:

``Backend``
    A minimal protocol -- ``generate(prompt, **kw) -> str`` and
    ``embed(texts) -> np.ndarray`` -- so the experiment never depends on a
    particular model vendor.

``MockBackend``
    A deterministic, offline, seeded pseudo-LLM.

``OpenAICompatBackend``
    A thin client for any OpenAI-compatible ``/v1/chat/completions`` endpoint
    (Ollama, llama.cpp ``server``, vLLM, LM Studio, or the OpenAI API itself).

.. warning::
   **MockBackend is a HARNESS-VALIDATION tool, NOT evidence about real
   models.** It does not do inference. It composes sentences from the packet's
   keywords and *deliberately injects* the failure modes the experiment is
   built to detect (register drift, entity renaming, duplicated content,
   missing transitions, contradictions, dangling references), with an injection
   probability that decreases as the packet carries more context.

   Consequently, running the sweep against ``MockBackend`` produces a
   coherence-vs-``rho`` curve *by construction*. The purpose of that curve is to
   prove the plumbing works -- that the planner, the packer's ``rho``
   targeting, the seam detector, the entity grid and the BooookScore-style
   taxonomy all respond to the variable under study with the expected sign and
   without crashing. **No number produced with MockBackend may be cited as a
   result about language models.** The go/no-go criterion in the master
   document (section 14, "there must exist a ``rho`` with <5% relative
   coherence degradation") can only be adjudicated with a real backend.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import re
from dataclasses import dataclass, field, replace
from random import Random
from typing import Any, Protocol, Sequence, runtime_checkable

import numpy as np

from .textutil import content_words, count_tokens, keywords, ngrams, split_sentences, tokenize

__all__ = [
    "Backend",
    "Embedder",
    "BackendUnavailable",
    "HashEmbedder",
    "SentenceTransformerEmbedder",
    "ServerEmbedder",
    "MockBackend",
    "OpenAICompatBackend",
    "MOCK_FAMILY_POOL",
    "get_backend",
    "get_embedder",
    "select_diverse_nodes",
    "replica_backends",
]


class BackendUnavailable(RuntimeError):
    """Raised when a remote backend cannot be reached or is misconfigured."""


@runtime_checkable
class Embedder(Protocol):
    """Anything that maps texts to unit-norm row vectors."""

    def embed(self, texts: Sequence[str]) -> np.ndarray:  # pragma: no cover - protocol
        ...


@runtime_checkable
class Backend(Protocol):
    """Generation + embedding surface used by every stage of the pipeline."""

    name: str

    def generate(self, prompt: str, **kw: Any) -> str:  # pragma: no cover - protocol
        """Return a completion for ``prompt``."""
        ...

    def embed(self, texts: Sequence[str]) -> np.ndarray:  # pragma: no cover - protocol
        """Return an ``(len(texts), d)`` array of unit-norm embeddings."""
        ...


# --------------------------------------------------------------------------
# Embedders
# --------------------------------------------------------------------------


def _stable_hash(text: str) -> int:
    """Process-stable hash (``hash()`` is salted per process; this is not)."""
    return int.from_bytes(hashlib.blake2b(text.encode("utf-8"), digest_size=8).digest(), "big")


@dataclass
class HashEmbedder:
    """Deterministic hashing bag-of-words embedder.

    Unigrams and bigrams are hashed into ``dim`` buckets with a hashed sign
    (the signed "hashing trick"), then the vector is L2-normalised so that a
    dot product is a cosine similarity.

    This exists so cosine-based seam detection and ``tau_sem`` calibration run
    with **zero downloads**. It is a lexical-overlap proxy, not a semantic
    model: it will score paraphrases with disjoint vocabulary as dissimilar.
    That limitation is acceptable for V0 -- the master document (section 5.6)
    restricts the cosine to seam detection, explicitly not to fraud detection
    or to a claim about meaning -- but it is another reason the calibrated
    ``tau_sem`` must be re-derived when a real embedder is plugged in.
    """

    dim: int = 256
    use_bigrams: bool = True
    name: str = "hash"

    def _features(self, text: str) -> list[tuple[str, float]]:
        words = content_words(text)
        feats: list[tuple[str, float]] = [(w, 1.0) for w in words]
        if self.use_bigrams:
            feats.extend(("_".join(bg), 0.5) for bg in ngrams(words, 2))
        return feats

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        """Embed ``texts`` into an ``(n, dim)`` array of unit vectors."""
        out = np.zeros((len(texts), self.dim), dtype=np.float64)
        for row, text in enumerate(texts):
            for feature, weight in self._features(text):
                h = _stable_hash(feature)
                idx = h % self.dim
                sign = 1.0 if (h >> 61) & 1 else -1.0
                out[row, idx] += sign * weight
            norm = float(np.linalg.norm(out[row]))
            if norm > 0.0:
                out[row] /= norm
        return out


@dataclass
class SentenceTransformerEmbedder:
    """Optional embedder backed by ``sentence_transformers``.

    Falls back to :class:`HashEmbedder` if the package (or the model download)
    is unavailable, so importing this module never fails offline.
    """

    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    name: str = "sentence-transformers"
    _model: Any = field(default=None, repr=False)
    _fallback: HashEmbedder = field(default_factory=HashEmbedder, repr=False)

    def __post_init__(self) -> None:
        try:  # pragma: no cover - depends on optional extra
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        except Exception:  # pragma: no cover - offline default path
            self._model = None
            self.name = "sentence-transformers(unavailable->hash)"

    @property
    def available(self) -> bool:
        """True when the transformer model actually loaded."""
        return self._model is not None

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        if self._model is None:
            return self._fallback.embed(texts)
        vecs = np.asarray(  # pragma: no cover - depends on optional extra
            self._model.encode(list(texts), normalize_embeddings=True), dtype=np.float64
        )
        return vecs


# --------------------------------------------------------------------------
# MockBackend
# --------------------------------------------------------------------------

_TASK_MARKER = "[TASK"
_BRIDGE_MARKER = "[BRIDGE]"
_GLOSSARY_LINE = re.compile(r"^-\s*(.+?):\s*canonical name", re.MULTILINE)
_FIELD_RE = {
    "register": re.compile(r"^register:\s*(\S+)", re.MULTILINE),
    "target_length_tokens": re.compile(r"^target_length_tokens:\s*(\d+)", re.MULTILINE),
    "output_format": re.compile(r"^output_format:\s*(\S+)", re.MULTILINE),
}

_FORMAL_TEMPLATES = (
    "{E} governs how {K} is evaluated against {K2}.",
    "The specification requires that {E} record every {K} observed during the {K2} stage.",
    "{E} therefore constrains the admissible range of {K}.",
    "Each {K} produced by {E} is validated before the {K2} step proceeds.",
    "{E} reports {K} alongside the corresponding {K2} budget.",
    "The {K} threshold applied by {E} remains stable across the {K2} interval.",
    "{E} exposes {K} so that downstream consumers can audit the {K2} decision.",
    "Where {K} is ambiguous, {E} defers to the {K2} convention already established.",
    "{E} treats {K} as authoritative and derives {K2} from it rather than the reverse.",
    "The measured {K} attributable to {E} falls well inside the {K2} tolerance.",
    "{E} records {K} at each checkpoint, which makes the {K2} trace reconstructible.",
    "Because {E} owns {K}, no separate {K2} reconciliation is required.",
    "The {K2} outcome depends on whether {E} observed a valid {K} in the first place.",
    "{E} distinguishes {K} from {K2} explicitly, and the distinction is load-bearing.",
    "Any {K} that {E} cannot attribute is escalated rather than folded into {K2}.",
    "The relationship between {K} and {K2} is mediated entirely by {E}.",
    "{E} publishes {K} on a fixed schedule so that {K2} consumers are never stale.",
    "For {E}, the cost of {K} is dominated by the {K2} term.",
)

_NEUTRAL_TEMPLATES = (
    "{E} handles {K} and passes the result to the {K2} step.",
    "The {K} value comes from {E} and feeds the {K2} calculation.",
    "{E} keeps a record of {K} for later {K2} checks.",
    "We compute {K} from {E} before looking at {K2}.",
    "{E} groups {K} by {K2} and reports the totals.",
    "The {K2} check runs after {E} has settled the {K} figure.",
)

# Casual templates trip BOTH the register detector (contractions, second
# person, hedging) and the tense detector (simple past).
_CASUAL_TEMPLATES = (
    "Honestly, {E} was kind of a mess once you looked at {K}.",
    "You'll probably just want to eyeball the {K} numbers and move on.",
    "So yeah, {K2} didn't really work and we didn't bother fixing it.",
    "It's pretty wild how much {K} stuff {E} was doing back then!",
    "We kinda skipped {K2} because it wasn't worth the hassle.",
)

_CONNECTIVES = (
    "Consequently,",
    "In addition,",
    "Building on the previous section,",
    "Moreover,",
    "Accordingly,",
    "Following from the above,",
    "Taken together with the preceding analysis,",
)

_REINTRO_TEMPLATES = (
    "In this report we introduce {E} and explain its role.",
    "This section introduces {E} for the first time.",
    "To begin, we define {E} and its purpose.",
)

_DANGLING_TEMPLATES = (
    "This confirms the point made earlier.",
    "They therefore remain unchanged.",
    "Such an outcome was expected.",
    "It follows directly from that result.",
)

# (assertion, negation) pairs used to fabricate a detectable contradiction.
_CONTRADICTION_PAIRS = (
    ("{E} increases the observed {K}.", "{E} decreases the observed {K}."),
    ("{E} always validates {K}.", "{E} never validates {K}."),
    ("The {K} budget is sufficient for {E}.", "The {K} budget is insufficient for {E}."),
)

_ALIEN_ENTITIES = (
    "Hyperion Ledger",
    "Marlowe Index",
    "Quantum Broker",
    "Vesper Registry",
    "Orion Cache",
)

# --------------------------------------------------------------------------
# Replica diversity (micro-level assembly)
# --------------------------------------------------------------------------
#
# Micro-level assembly dispatches k COMPLETE replicas of the same micro-task to
# nodes of different model families and resolves them by consensus
# (swarmbly_v0.consensus). For that to be worth anything the replicas must differ
# the way replies from different families actually differ -- same content,
# different words, different order, and occasionally a different factual slot --
# rather than being identical strings (which would make every agreement score
# 1.0 by construction) or unrelated noise (which would make every score 0).
#
# Families share the sentence *skeleton* produced by the drift machinery above
# and then diverge lexically, positionally and, at a controlled rate, factually.

MOCK_FAMILY_POOL: tuple[tuple[str, str], ...] = (
    ("llama", "mock-llama-3b"),
    ("mistral", "mock-mistral-7b"),
    ("qwen", "mock-qwen-3b"),
    ("gemma", "mock-gemma-2b"),
    ("phi", "mock-phi-3-mini"),
    ("llama", "mock-llama-8b"),
)
"""``(family, model)`` pairs the mock swarm can draw replicas from.

Note the two ``llama`` entries: a real pool contains several models from one
family, and family diversity is therefore a *selection* problem, not a
by-product of picking distinct models. See :func:`select_diverse_nodes`.
"""

# One alternative per family index, so a family's vocabulary is systematic
# rather than random: the same family always says "regulates" where another
# always says "controls".
_FAMILY_SYNONYMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("governs", ("regulates", "controls", "determines", "dictates")),
    ("records", ("logs", "registers", "captures", "notes")),
    ("requires", ("mandates", "obliges", "demands", "compels")),
    ("reports", ("publishes", "surfaces", "returns", "emits")),
    ("validated", ("checked", "verified", "confirmed", "audited")),
    ("threshold", ("cutoff", "limit", "bound", "ceiling")),
    ("stage", ("phase", "step", "pass", "leg")),
    ("outcome", ("result", "verdict", "output", "finding")),
    ("constrains", ("bounds", "restricts", "limits", "narrows")),
    ("exposes", ("publishes", "reveals", "surfaces", "advertises")),
)

# The divergent factual slot: the same claim with a different number in it.
# This is the failure the agreement score exists to catch -- two families that
# confidently disagree about a value, which no amount of fluency reveals.
_DIVERGENT_FACT = "The measured {K} for {E} settles at {V} percent of the budget."
_DIVERGENT_VALUES: tuple[int, ...] = (12, 19, 27, 34, 41, 58)


def _family_index(family: str) -> int:
    """Stable small integer for a family name (process-independent)."""
    return _stable_hash(family) % 4096


def select_diverse_nodes(
    pool: Sequence[tuple[str, str]], k: int
) -> list[tuple[str, str]]:
    """Choose ``k`` ``(family, model)`` pairs maximising family diversity.

    Round-robin over families in order of first appearance, taking one model
    per family per pass. So ``k <= n_families`` returns ``k`` **distinct**
    families, and larger ``k`` only starts repeating a family once every family
    has been used -- and then prefers a *different model* of that family over
    the same one twice.

    Why diversity and not quality: agreement between replicas is only evidence
    to the extent that the replicas could have disagreed. Models sharing
    training data share errors and will agree confidently on the same mistake,
    so a pool drawn from one family produces a high agreement score that means
    nothing at all. Diversity is what converts redundancy into information.

    Args:
        pool: Available ``(family, model)`` pairs. Order is significant and the
            selection is deterministic.
        k: Number of replicas required.

    Returns:
        Exactly ``k`` pairs (fewer only when the pool is empty).
    """
    if k <= 0 or not pool:
        return []
    by_family: dict[str, list[tuple[str, str]]] = {}
    for family, model in pool:
        by_family.setdefault(family, []).append((family, model))

    selected: list[tuple[str, str]] = []
    round_index = 0
    while len(selected) < k:
        added = False
        for family, entries in by_family.items():
            if len(selected) >= k:
                break
            selected.append(entries[round_index % len(entries)])
            added = True
        if not added:  # pragma: no cover - unreachable while pool is non-empty
            break
        round_index += 1
    return selected[:k]


def replica_backends(
    base: Any, k: int, pool: Sequence[tuple[str, str]] | None = None
) -> list[Any]:
    """``k`` per-replica backends drawn from a family-diverse selection.

    Each returned backend is a copy of ``base`` bound to one ``(family, model)``
    pair, so the caller dispatches the *same* packet to ``k`` differently
    configured nodes. Backends that cannot be specialised (anything without a
    ``for_replica`` method) are returned unchanged, which degrades to ``k``
    identical replicas -- correct, but with an agreement score that means
    nothing, so the caller should record ``n_families`` alongside it.
    """
    if k <= 0:
        return []
    default_pool = pool if pool is not None else getattr(base, "family_pool", None)
    if not default_pool:
        default_pool = MOCK_FAMILY_POOL if isinstance(base, MockBackend) else ()
    chosen = select_diverse_nodes(list(default_pool), k)
    if not chosen:
        return [base for _ in range(k)]
    specialise = getattr(base, "for_replica", None)
    if specialise is None:
        return [base for _ in range(k)]
    return [specialise(family, model) for family, model in chosen]


@dataclass
class MockBackend:
    """Deterministic offline pseudo-LLM that simulates fragmentation damage.

    **This is a harness-validation tool, not a language model.** See the module
    docstring. It composes sentences from the packet's own keywords, then
    injects the coherence failures under study with probability

    ``p(channel) = floor + (base[channel] - floor) * (1 - c) ** gamma``

    where ``c = min(1, context_tokens / task_tokens)`` is how much context the
    packet carried relative to its own task. ``c = 0`` (a bare fragment, the
    ``rho = 1.0`` regime) yields maximum drift; ``c = 1`` (``rho ~ 2.0``, or the
    monolithic condition, which has no ``[TASK]`` marker and is scored at
    ``c = 1``) yields only the floor rate.

    Determinism: every call seeds a private ``random.Random`` from
    ``(self.seed, family, prompt)``, so the same prompt always yields the same
    output regardless of call order or parallelism, and two families always
    differ in the same way.

    Replica diversity: when :attr:`family` is set, the fragment is additionally
    passed through a family-specific transform -- a systematic lexical
    substitution, a positional swap, and a factual slot that diverges at
    :attr:`divergence_rate`. That is what gives micro-level consensus something
    to align and a non-trivial spread of agreement scores to score. With
    ``family=""`` (the default) the transform is skipped entirely and the
    backend behaves exactly as it did before replicas existed.
    """

    seed: int = 0
    gamma: float = 1.4
    floor: float = 0.02
    name: str = "mock"
    family: str = ""
    model: str = ""
    divergence_rate: float = 0.35
    omission_rate: float = 0.30
    family_pool: tuple[tuple[str, str], ...] = MOCK_FAMILY_POOL
    drift_base: dict[str, float] = field(
        default_factory=lambda: {
            "register": 0.45,
            "entity": 0.50,
            "repeat": 0.40,
            "transition": 0.65,
            "contradiction": 0.30,
            "dangling": 0.35,
            "reintro": 0.35,
        }
    )
    _embedder: HashEmbedder = field(default_factory=HashEmbedder, repr=False)

    # -- helpers ----------------------------------------------------------

    def _rng(self, prompt: str) -> Random:
        return Random(_stable_hash(f"{self.seed}::{prompt}") % (2**63))

    def _style_rng(self, prompt: str) -> Random:
        """Private stream for the family transform.

        Kept separate from :meth:`_rng` on purpose. The *content* of a fragment
        must not depend on which family produced it -- two nodes asked the same
        question are answering the same question, and if their skeletons were
        independently random there would be nothing to align. Family membership
        therefore perturbs only the surface (wording, order, one factual slot,
        one occasional omission), which is how replies from different families
        actually differ and what makes the agreement score informative rather
        than uniformly low.
        """
        return Random(_stable_hash(f"{self.seed}::{self.family}::style::{prompt}") % (2**63))

    def for_replica(self, family: str, model: str = "") -> "MockBackend":
        """A copy of this backend bound to one ``(family, model)`` node.

        ``name`` is deliberately left as ``"mock"``: the replicas are still the
        mock, and nothing downstream may be allowed to read a family name as
        evidence that a real model was involved.
        """
        return replace(self, family=family, model=model)

    def drift_probability(self, channel: str, context_strength: float) -> float:
        """Probability of injecting ``channel`` at the given context strength.

        Monotonically non-increasing in ``context_strength``; this is the
        signal the whole V0 harness is built to recover.
        """
        base = self.drift_base.get(channel, 0.3)
        c = min(1.0, max(0.0, context_strength))
        return self.floor + (base - self.floor) * (1.0 - c) ** self.gamma

    @staticmethod
    def _parse_packet(prompt: str) -> dict[str, Any]:
        """Split a packet into context / task and read the contract fields."""
        idx = prompt.find(_TASK_MARKER)
        if idx == -1:
            context, task = "", prompt
            monolithic = True
        else:
            context = prompt[:idx]
            task = prompt[idx:]
            monolithic = False
        ctx_tokens = count_tokens(context)
        task_tokens = count_tokens(task)
        if monolithic:
            strength = 1.0
        else:
            strength = min(1.0, ctx_tokens / max(task_tokens, 1))
        glossary = [m.group(1).strip() for m in _GLOSSARY_LINE.finditer(context)]
        register_m = _FIELD_RE["register"].search(prompt)
        target_m = _FIELD_RE["target_length_tokens"].search(prompt)
        return {
            "context": context,
            "task": task,
            "context_tokens": ctx_tokens,
            "task_tokens": task_tokens,
            "context_strength": strength,
            "glossary": glossary,
            "register": (register_m.group(1) if register_m else "formal"),
            "target_tokens": int(target_m.group(1)) if target_m else 160,
            "monolithic": monolithic,
        }

    # -- generation -------------------------------------------------------

    def generate(self, prompt: str, **kw: Any) -> str:
        """Produce a deterministic pseudo-fragment for ``prompt``.

        Recognised keyword arguments: ``max_tokens`` (caps the target length)
        and ``variant`` (an integer that perturbs the seed so a caller can ask
        for several distinct candidates for the same packet).
        """
        variant = int(kw.get("variant", 0))
        rng = self._rng(f"{prompt}::v{variant}")
        if _BRIDGE_MARKER in prompt:
            return self._generate_bridge(prompt, rng)

        spec = self._parse_packet(prompt)
        max_tokens = int(kw.get("max_tokens", spec["target_tokens"]) or spec["target_tokens"])
        target_tokens = max(40, min(spec["target_tokens"], max_tokens))
        c = spec["context_strength"]

        topic_words = keywords(spec["task"], limit=18) or ["context", "fragment", "coherence"]
        if len(topic_words) < 4:
            topic_words = (topic_words + keywords(prompt, limit=18))[:18] or ["context"]
        entities = list(spec["glossary"])
        if not entities:
            entities = [w.capitalize() for w in topic_words[:2]] or ["Subject"]

        # Drift coin flips (one per channel, per fragment).
        fired = {ch: rng.random() < self.drift_probability(ch, c) for ch in self.drift_base}

        register = spec["register"]
        sentences: list[str] = []

        # -- repeated introduction ---------------------------------------
        if fired["reintro"] and not spec["monolithic"]:
            sentences.append(
                rng.choice(_REINTRO_TEMPLATES).format(E=entities[0])
            )

        # -- dangling reference at the fragment head ---------------------
        if fired["dangling"] and not spec["monolithic"]:
            sentences.append(rng.choice(_DANGLING_TEMPLATES))

        n_sent = max(3, round(target_tokens / 15))
        body_budget = max(2, n_sent - len(sentences))

        # Entity plan: normally reuse the contract entities; on entity drift,
        # rename one canonically-named entity and smuggle in an alien one.
        entity_pool = list(entities)
        if fired["entity"]:
            # Replace (not augment) the canonical form: the fragment now names
            # the same thing differently, so the assembled answer shows both an
            # inconsistent naming and, for the owning task, an entity omission.
            # Same normalised identity, different surface form -- which is what
            # the inconsistent-naming detector is built to catch.
            alias = entities[0].upper()
            alien = _ALIEN_ENTITIES[rng.randrange(len(_ALIEN_ENTITIES))]
            entity_pool = [alias] + entities[1:] + [alien]

        # Coherent text keeps an entity in focus for a run of sentences (a topic
        # chain); that local structure is exactly what the entity grid rewards.
        # Entity drift shortens the chain to 1, scattering mentions at random.
        chain_length = 1 if fired["entity"] else 4

        for i in range(body_budget):
            if chain_length > 1:
                chain = i // chain_length
                ent = entity_pool[chain % len(entity_pool)]
                # Lexical cohesion: a chain also keeps to a local topic window.
                window = [
                    topic_words[(chain * 2 + k) % len(topic_words)]
                    for k in range(min(4, len(topic_words)))
                ]
            else:
                ent = entity_pool[rng.randrange(len(entity_pool))]
                window = topic_words  # scattered vocabulary, no local cohesion
            kw1 = window[rng.randrange(len(window))]
            kw2 = window[rng.randrange(len(window))]
            if kw2 == kw1 and len(window) > 1:
                kw2 = window[(window.index(kw1) + 1) % len(window)]
            use_casual = fired["register"] and (i % 3 == 1)
            if use_casual:
                template = _CASUAL_TEMPLATES[rng.randrange(len(_CASUAL_TEMPLATES))]
            elif register == "casual":
                template = _NEUTRAL_TEMPLATES[rng.randrange(len(_NEUTRAL_TEMPLATES))]
            else:
                template = _FORMAL_TEMPLATES[rng.randrange(len(_FORMAL_TEMPLATES))]
            sentences.append(template.format(E=ent, K=kw1, K2=kw2))

        # -- contradiction ------------------------------------------------
        if fired["contradiction"] and sentences:
            pair = _CONTRADICTION_PAIRS[rng.randrange(len(_CONTRADICTION_PAIRS))]
            ent = entity_pool[0]
            kw1 = topic_words[0]
            sentences.append(pair[0].format(E=ent, K=kw1))
            sentences.append(pair[1].format(E=ent, K=kw1))

        # -- duplicated content -------------------------------------------
        if fired["repeat"] and len(sentences) >= 2:
            dup_idx = rng.randrange(len(sentences) - 1)
            sentences.append(sentences[dup_idx])

        # -- missing transition -------------------------------------------
        # With enough context the fragment opens with an explicit connective
        # tying it to what came before; without context it just starts.
        if not fired["transition"] and not spec["monolithic"] and sentences:
            connective = _CONNECTIVES[rng.randrange(len(_CONNECTIVES))]
            head = sentences[0]
            sentences[0] = f"{connective} {head[0].lower()}{head[1:]}" if head else head

        if self.family:
            sentences = self._apply_family_style(
                sentences, self._style_rng(f"{prompt}::v{variant}"),
                entity_pool[0], topic_words[0],
            )

        return " ".join(sentences)

    # -- replica diversity ------------------------------------------------

    def _apply_family_style(
        self, sentences: list[str], rng: Random, entity: str, topic: str
    ) -> list[str]:
        """Rewrite a fragment the way a different model family would produce it.

        Four systematic differences, all deterministic given
        ``(seed, family, prompt, variant)``:

        1. **Lexical.** A fixed synonym table indexed by family, so one family
           consistently writes "regulates" where another writes "controls".
           Alignment must therefore match units by meaning, not by string.
        2. **Positional.** One adjacent pair of sentences is swapped, at a
           family-determined offset, so replicas do not arrive in a common
           order. This is what makes positional zipping wrong and multiple
           alignment necessary.
        3. **Omission.** At :attr:`omission_rate` one unit is dropped, so some
           columns are covered by a strict subset of the replicas. An aligner
           that cannot open a gap misreads this as everything after it
           disagreeing.
        4. **Factual.** At :attr:`divergence_rate` a claim carrying a *number*
           is appended, and the number differs by family. This is the case the
           agreement score exists for: fluent, confident, mutually
           contradictory.
        """
        index = _family_index(self.family)
        styled = [self._substitute(sentence, index) for sentence in sentences]

        if len(styled) >= 3:
            pivot = index % (len(styled) - 1)
            styled[pivot], styled[pivot + 1] = styled[pivot + 1], styled[pivot]

        if len(styled) >= 4 and rng.random() < self.omission_rate:
            del styled[rng.randrange(1, len(styled))]

        if rng.random() < self.divergence_rate:
            value = _DIVERGENT_VALUES[index % len(_DIVERGENT_VALUES)]
            styled.append(_DIVERGENT_FACT.format(K=topic, E=entity, V=value))
        return styled

    @staticmethod
    def _substitute(sentence: str, family_index: int) -> str:
        """Apply the family's lexical choices, preserving capitalisation."""
        out = sentence
        for base, alternatives in _FAMILY_SYNONYMS:
            replacement = alternatives[family_index % len(alternatives)]
            out = re.sub(
                rf"\b{base}\b",
                lambda m, r=replacement: r.capitalize() if m.group(0)[0].isupper() else r,
                out,
            )
        return out

    def _generate_bridge(self, prompt: str, rng: Random) -> str:
        """One transition sentence linking the two halves of a bridge prompt."""
        halves = prompt.split(_BRIDGE_MARKER)
        left = halves[0] if halves else ""
        right = halves[-1] if len(halves) > 1 else ""
        left_kw = (keywords(left, limit=3) or ["the preceding analysis"])[0]
        right_kw = (keywords(right, limit=3) or ["the next topic"])[0]
        opener = _CONNECTIVES[rng.randrange(len(_CONNECTIVES))]
        return (
            f"{opener} the discussion of {left_kw} leads directly into "
            f"the treatment of {right_kw} that follows."
        )

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        """Delegate to the deterministic :class:`HashEmbedder`."""
        return self._embedder.embed(texts)


# --------------------------------------------------------------------------
# OpenAI-compatible backend
# --------------------------------------------------------------------------


def _env_family_pool() -> tuple[tuple[str, str], ...]:
    """Parse ``SWARMBLY_REPLICA_MODELS`` into ``(family, model)`` pairs.

    Format: ``family:model`` entries separated by commas. Model names may
    themselves contain colons (``qwen2.5:3b``), so only the **first** colon
    separates the family from the model.
    """
    raw = os.environ.get("SWARMBLY_REPLICA_MODELS", "").strip()
    if not raw:
        return ()
    pairs: list[tuple[str, str]] = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        family, _, model = entry.partition(":")
        if family and model:
            pairs.append((family.strip(), model.strip()))
    return tuple(pairs)


@dataclass
class OpenAICompatBackend:
    """Client for any OpenAI-compatible chat-completions endpoint.

    Configuration is read from the environment so the same code runs against a
    local Ollama, a llama.cpp server, vLLM, or the hosted OpenAI API::

        export OPENAI_BASE_URL=http://localhost:11434/v1   # Ollama
        export OPENAI_API_KEY=ollama                       # any non-empty string
        export SWARMBLY_MODEL=llama3.2:3b

    Transport is chosen in order of preference: the ``openai`` SDK, then
    ``httpx``, then the standard library's ``urllib.request``. The stdlib path
    means the backend still works when neither optional package is installed --
    it is slower and has no connection pooling, and a warning is recorded in
    :attr:`transport`.

    Temperature defaults to 0 and a seed is forwarded when the server supports
    it, because V0 requires reproducible runs.
    """

    model: str = field(default_factory=lambda: os.environ.get("SWARMBLY_MODEL", "llama3.2:3b"))
    base_url: str = field(
        default_factory=lambda: os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1")
    )
    api_key: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", "not-needed"))
    embed_model: str = field(
        default_factory=lambda: os.environ.get("SWARMBLY_EMBED_MODEL", "nomic-embed-text")
    )
    temperature: float = 0.0
    seed: int = 0
    timeout: float = 120.0
    name: str = "openai-compat"
    family: str = ""
    """Model family this instance speaks for, when used as one micro-level replica.

    Purely descriptive -- it is recorded on the replica so the consensus result
    can report which families contributed, and so a run with ``n_families = 1``
    is visibly not evidence of anything (see :func:`select_diverse_nodes`).
    """
    family_pool: tuple[tuple[str, str], ...] = field(default_factory=lambda: _env_family_pool())
    """``(family, model)`` pairs available for replica dispatch.

    Read from ``SWARMBLY_REPLICA_MODELS`` as a comma-separated list of
    ``family:model`` entries, e.g.
    ``llama:llama3.2:3b,qwen:qwen2.5:3b,gemma:gemma2:2b``. Empty by default, in
    which case every replica is the same model and the agreement score is not
    interpretable.
    """
    max_retries: int = 2
    """Extra attempts after the first on a transport failure. 0 disables retry."""
    retry_backoff_s: float = 1.0
    """Base of the exponential backoff. Tests set it to 0."""
    transport: str = field(default="", init=False)
    retries: int = field(default=0, init=False)
    """Transport retries consumed this run. Reported in the run metadata."""
    retry_events: list[str] = field(default_factory=list, init=False, repr=False)
    embed_degraded: str = field(default="", init=False)
    """Non-empty once :meth:`embed` has fallen back to hashing, with the reason."""
    _fallback_embedder: HashEmbedder = field(default_factory=HashEmbedder, repr=False)
    _client: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self._is_ollama = any(
            marker in str(self.base_url).lower() for marker in ("11434", "ollama")
        )
        """Whether to send ``options.num_predict`` alongside ``max_tokens``.

        Detected from the endpoint rather than configured, because the field is
        harmless to Ollama and fatal to the OpenAI API.
        """
        try:
            from openai import OpenAI  # type: ignore[import-not-found]

            self._client = OpenAI(base_url=self.base_url, api_key=self.api_key)
            self.transport = "openai-sdk"
            return
        except Exception:
            self._client = None
        try:
            import httpx  # type: ignore[import-not-found]  # noqa: F401

            self.transport = "httpx"
            return
        except Exception:
            pass
        self.transport = "urllib(stdlib fallback: install `httpx` or `openai` for pooling)"

    def for_replica(self, family: str, model: str = "") -> "OpenAICompatBackend":
        """A copy of this client bound to one ``(family, model)`` replica node."""
        return replace(self, family=family, model=model or self.model)

    # -- transport --------------------------------------------------------

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST with a bounded retry, because a sweep is hours long.

        A single transient transport failure — a connection refused while the
        server swaps a model out of memory, a timeout under memory pressure —
        used to abort the whole run. On a laptop juggling three models that is
        not a hypothetical, and losing five hours to one dropped socket is a
        worse outcome than waiting two seconds.

        Retries are **bounded and counted**, never unlimited: :attr:`retries`
        and :attr:`retry_events` are reported in the run metadata, so a run
        held together by retries is visibly different from a clean one. Only
        transport failures are retried; a malformed response is a real error
        and is raised immediately.
        """
        attempts = max(1, self.max_retries + 1)
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                return self._post_once(path, payload)
            except BackendUnavailable as exc:
                last = exc
                self.retries += 1
                self.retry_events.append(f"{path}: {exc}")
                if attempt + 1 < attempts:
                    time.sleep(self.retry_backoff_s * (2 ** attempt))
        assert last is not None
        raise BackendUnavailable(
            f"{last} (gave up after {attempts} attempts; "
            f"{self.retries} transport retries so far this run)"
        ) from last

    def _post_once(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """One POST to ``base_url + path``, returning the parsed JSON."""
        url = f"{self.base_url}{path}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        body = json.dumps(payload).encode("utf-8")
        if self.transport == "httpx":
            import httpx  # type: ignore[import-not-found]

            try:
                response = httpx.post(url, content=body, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                return dict(response.json())
            except Exception as exc:  # pragma: no cover - network path
                raise BackendUnavailable(f"httpx POST {url} failed: {exc}") from exc

        import urllib.error
        import urllib.request

        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:  # pragma: no cover - network path
            with urllib.request.urlopen(request, timeout=self.timeout) as handle:
                return dict(json.loads(handle.read().decode("utf-8")))
        except urllib.error.URLError as exc:  # pragma: no cover - network path
            raise BackendUnavailable(
                f"cannot reach {url}: {exc}. Is the server running? "
                "Set OPENAI_BASE_URL / OPENAI_API_KEY / SWARMBLY_MODEL."
            ) from exc

    # -- API --------------------------------------------------------------

    def generate(self, prompt: str, **kw: Any) -> str:
        """Return the assistant message for ``prompt`` (temperature 0 by default)."""
        max_tokens = int(kw.get("max_tokens", 512))
        payload: dict[str, Any] = {
            "model": kw.get("model", self.model),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": float(kw.get("temperature", self.temperature)),
            "max_tokens": max_tokens,
            "seed": int(kw.get("seed", self.seed)) + int(kw.get("variant", 0)),
        }
        # Ollama's OpenAI-compatible shim accepts `max_tokens` and does not act
        # on it; the knob it honours is `options.num_predict`. Fragments
        # dispatched with max_tokens=61 came back with 91 to 177 tokens, so the
        # assembled compositions ran 1.5x to 2.3x over length and failed the
        # length constraint in every fragmented condition.
        #
        # It has to be delivered differently on each path. The raw HTTP path puts
        # it in the request body. The SDK path cannot: `create()` validates its
        # keyword arguments and raises TypeError on anything it does not know, so
        # the field travels in `extra_body`, which exists for exactly this. Only
        # the HTTP body was exercised before, which is why this surfaced at run
        # time instead of in the tests.
        extra: dict[str, Any] = {"options": {"num_predict": max_tokens}} if self._is_ollama else {}

        if self._client is not None:  # pragma: no cover - needs the SDK
            try:
                completion = self._client.chat.completions.create(
                    **payload, **({"extra_body": extra} if extra else {})
                )
                return (completion.choices[0].message.content or "").strip()
            except Exception as exc:
                raise BackendUnavailable(f"openai SDK call failed: {exc}") from exc

        data = self._post("/chat/completions", {**payload, **extra})
        try:
            return str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:  # pragma: no cover - network path
            raise BackendUnavailable(f"unexpected response shape: {data!r}") from exc

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        """Embed via the server's ``/embeddings`` route, falling back to hashing.

        The fallback keeps a sweep alive against an endpoint with no embeddings
        route, but it is **not** a silent substitution: the first degradation
        sets :attr:`embed_degraded`, which the run metadata reports, because a
        tau calibrated on hashed embeddings is meaningless and a reader must be
        able to see that from the output rather than infer it.
        """
        if not texts:
            return np.zeros((0, self._fallback_embedder.dim))
        try:
            data = self._post("/embeddings", {"model": self.embed_model, "input": list(texts)})
            vectors = np.asarray([row["embedding"] for row in data["data"]], dtype=np.float64)
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            norms[norms == 0.0] = 1.0
            return vectors / norms
        except Exception as exc:
            # An endpoint without embeddings support must not kill the sweep;
            # seam detection degrades to lexical overlap and is reported as such.
            if not self.embed_degraded:
                self.embed_degraded = f"{type(exc).__name__}: {exc}"
            return self._fallback_embedder.embed(texts)


# --------------------------------------------------------------------------
# Factories
# --------------------------------------------------------------------------


def get_backend(name: str = "mock", *, seed: int = 0, **kw: Any) -> Backend:
    """Construct a backend by short name (``mock`` or ``openai``/``ollama``)."""
    key = name.lower()
    if key == "mock":
        return MockBackend(seed=seed, **kw)
    if key in {"openai", "openai-compat", "ollama", "vllm", "llamacpp"}:
        return OpenAICompatBackend(seed=seed, **kw)
    raise ValueError(f"unknown backend {name!r}; expected 'mock' or 'openai'")


@dataclass
class ServerEmbedder:
    """Embedder backed by the generation server's own ``/embeddings`` route.

    On a local Ollama this is ``nomic-embed-text`` or similar, which means the
    sweep needs no second model stack and no download from a model hub. It is
    the recommended embedder for a real run: :class:`HashEmbedder` is a
    deterministic stand-in whose cosine values carry no semantics, so a
    ``tau_sem`` calibrated on it is not a threshold, it is a number.

    :attr:`name` is rewritten to record a degradation the moment one happens,
    so the run metadata cannot claim server embeddings it did not get.
    """

    backend: "OpenAICompatBackend" = field(default_factory=lambda: OpenAICompatBackend())
    name: str = "server-embeddings"

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        vectors = self.backend.embed(texts)
        if self.backend.embed_degraded and "degraded" not in self.name:
            self.name = f"server-embeddings(degraded->hash: {self.backend.embed_degraded})"
        return vectors

    @property
    def available(self) -> bool:
        """False once the server route has failed at least once."""
        return not self.backend.embed_degraded


def get_embedder(name: str = "hash", **kw: Any) -> Embedder:
    """Construct an embedder by short name (``hash``, ``st`` or ``api``)."""
    key = name.lower()
    if key == "hash":
        return HashEmbedder(**kw)
    if key in {"st", "sentence-transformers", "sbert"}:
        return SentenceTransformerEmbedder(**kw)
    if key in {"api", "server", "ollama", "openai"}:
        return ServerEmbedder(**kw)
    raise ValueError(f"unknown embedder {name!r}; expected 'hash', 'st' or 'api'")


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two 1-D vectors (0.0 if either is degenerate)."""
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _sentence_count(text: str) -> int:  # small helper used by tests/diagnostics
    return len(split_sentences(text))


def _token_count(text: str) -> int:  # small helper used by tests/diagnostics
    return len(tokenize(text))
