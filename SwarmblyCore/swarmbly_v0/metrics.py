"""Coherence metrics: entity grid, BooookScore-style taxonomy, redundancy, tau.

The master document is explicit that an aggregate "which answer is better?"
judgement **hides** the damage fragmentation does -- Skeleton-of-Thought
improves relevance while degrading coherence, and a single scalar preference
score cannot see that. So V0 measures coherence as a first-class quantity, with
two independent instruments:

* :func:`entity_grid_coherence` -- a simplified Barzilay & Lapata entity grid.
  It is sensitive to *reordering and insertion* damage, which is precisely the
  failure mode of splice-based assembly.
* :func:`seam_error_taxonomy` -- the mechanically detectable subset of the
  BooookScore error classes, scored as "fraction of sentences free of detected
  errors", which is how BooookScore itself defines its metric.

Plus two supporting instruments: :func:`redundancy` (are fragments saying the
same thing twice?) and :func:`calibrate_tau`, which implements the
"calibrate, do not fix" requirement for ``tau_sem``.

Scope note
----------
These are *mechanical* detectors over surface form. They do not read. They
under-detect (a subtle contradiction with no lexical antonym is invisible) and
they can over-detect (a legitimately repeated definition looks duplicated).
They are appropriate as a **relative** instrument comparing conditions that
were generated the same way, which is exactly what a coherence-*tax*
measurement needs, and inappropriate as an absolute quality score.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np

from .schema import Contract, Plan
from .textutil import (
    content_words,
    count_tokens,
    extract_entities,
    extract_entity_surfaces,
    ngrams,
    normalize_entity,
    split_sentences,
    tokenize,
)

__all__ = [
    "ERROR_CLASSES",
    "EntityGridResult",
    "TaxonomyReport",
    "TauCalibration",
    "AlphaCalibration",
    "entity_grid_coherence",
    "entity_grid",
    "seam_error_taxonomy",
    "redundancy",
    "redundancy_between",
    "calibrate_tau",
    "calibrate_alpha",
    "effective_coverage",
    "expected_uncovered",
    "expected_islands",
    "required_coverage",
    "contract_compliance",
    "quality_judge",
]

# --------------------------------------------------------------------------
# Entity grid (simplified Barzilay & Lapata)
# --------------------------------------------------------------------------

_ROLES = ("S", "O", "X", "-")

# Transition weights. Continuity in a salient grammatical role is the signal
# the entity-grid model rewards; an entity dropping out and reappearing is the
# signal it penalises.
_TRANSITION_WEIGHTS: dict[tuple[str, str], float] = {
    ("S", "S"): 1.00,
    ("S", "O"): 0.80,
    ("O", "S"): 0.80,
    ("O", "O"): 0.70,
    ("S", "X"): 0.50,
    ("X", "S"): 0.50,
    ("O", "X"): 0.40,
    ("X", "O"): 0.40,
    ("X", "X"): 0.30,
}

_VERB_HINTS = frozenset(
    """
    is are was were be been being has have had do does did governs govern requires require
    records record reports report exposes expose keeps keep handles handle passes pass comes come
    feeds feed remains remain constrains constrain validates validate produces produce computes
    compute increases increase decreases decrease shows show means mean includes include provides
    provide describes describe explains explain must will can should would may might confirms
    confirm follows follow introduces introduce defines define leads lead applies apply
    """.split()
)


@dataclass
class EntityGridResult:
    """Full entity grid plus its scalar coherence score."""

    entities: list[str]
    sentences: int
    grid: dict[str, list[str]]
    transition_counts: dict[tuple[str, str], int]
    score: float

    def transition_distribution(self) -> dict[str, float]:
        """Informative transitions as probabilities (``'--'`` excluded)."""
        total = sum(self.transition_counts.values())
        if not total:
            return {}
        return {f"{a}{b}": c / total for (a, b), c in sorted(self.transition_counts.items())}


def _role_of(entity_norm: str, sentence: str) -> str:
    """Grammatical role of ``entity_norm`` in ``sentence``: S, O, X or '-'.

    Without a parser, "subject" is approximated as *appearing before the first
    verb-like token*, which is a good approximation for English declaratives
    and is the standard simplification when the entity grid is implemented
    without syntactic annotation.
    """
    tokens = tokenize(sentence)
    if not tokens:
        return "-"
    lowered = [t.lower() for t in tokens]

    entity_tokens = entity_norm.split()
    first_hit = -1
    for i in range(len(lowered)):
        window = lowered[i : i + len(entity_tokens)]
        if normalize_entity(" ".join(window)) == entity_norm:
            first_hit = i
            break
    if first_hit == -1:
        # Single-token fallback (handles the de-pluralised normal form).
        for i, tok in enumerate(lowered):
            if normalize_entity(tok) == entity_norm:
                first_hit = i
                break
    if first_hit == -1:
        return "-"

    verb_index = next((i for i, tok in enumerate(lowered) if tok in _VERB_HINTS), -1)
    if verb_index == -1:
        return "X"
    return "S" if first_hit < verb_index else "O"


def entity_grid(text: str, min_mentions: int = 2) -> EntityGridResult:
    """Build the entity grid for ``text`` and score it.

    Args:
        text: The document to score.
        min_mentions: Salience filter -- entities mentioned fewer times are
            dropped, as in the original model. Relaxed automatically when the
            filter would leave fewer than two entities.

    Returns:
        An :class:`EntityGridResult`. ``score`` is in ``[0, 1]``: the mean
        transition weight over all *informative* adjacent-sentence transitions
        (pairs where the entity is absent from both sentences carry no
        information and are excluded, otherwise the score would be dominated
        by the grid's overwhelming sparsity).
    """
    sentences = split_sentences(text)
    entities = extract_entities(text, min_mentions=min_mentions)
    if len(entities) < 2:
        entities = extract_entities(text, min_mentions=1)
    if not sentences or not entities:
        return EntityGridResult(entities=[], sentences=len(sentences), grid={},
                                transition_counts={}, score=0.0)

    grid: dict[str, list[str]] = {}
    for entity in entities:
        norm = normalize_entity(entity)
        grid[entity] = [_role_of(norm, sentence) for sentence in sentences]

    counts: dict[tuple[str, str], int] = {}
    for roles in grid.values():
        for a, b in zip(roles, roles[1:]):
            if a == "-" and b == "-":
                continue  # uninformative: entity absent from both sentences
            counts[(a, b)] = counts.get((a, b), 0) + 1

    total = sum(counts.values())
    if not total:
        return EntityGridResult(entities=entities, sentences=len(sentences), grid=grid,
                                transition_counts=counts, score=0.0)
    weighted = sum(_TRANSITION_WEIGHTS.get(pair, 0.0) * n for pair, n in counts.items())
    return EntityGridResult(entities=entities, sentences=len(sentences), grid=grid,
                            transition_counts=counts, score=weighted / total)


def entity_grid_coherence(text: str, min_mentions: int = 2) -> float:
    """Scalar entity-grid coherence of ``text`` in ``[0, 1]`` (higher is better)."""
    return entity_grid(text, min_mentions=min_mentions).score


# --------------------------------------------------------------------------
# BooookScore-style seam error taxonomy
# --------------------------------------------------------------------------

ERROR_CLASSES: tuple[str, ...] = (
    "entity_omission",
    "duplicated_content",
    "contradiction",
    "register_tense_shift",
    "dangling_reference",
    "missing_transition",
    "repeated_introduction",
    "inconsistent_naming",
)
"""The mechanically detectable subset of the BooookScore error taxonomy."""

SEAM_LOCAL_CLASSES: frozenset[str] = frozenset({
    "missing_transition",
    "dangling_reference",
})
"""Classes that can only fire where one fragment meets the next.

A monolithic answer has no seams, so it cannot incur these however incoherent it
is. Including them in a ratio against that baseline charges the fragmented arm
for a category the baseline is exempt from -- and the charge grows with N,
because there are N-1 seams. On the table run of 26 August that alone moved the
N=8 figure from +24.7 % to +14.6 %.

They are reported through ``TaxonomyReport.seam_error_rate`` instead: the damage
assembly does, in its own column, where a reader can see it rather than find it
folded into a coherence score."""

_CONNECTIVE_RE = re.compile(
    r"^(consequently|in addition|additionally|moreover|furthermore|accordingly|therefore|thus|"
    r"however|nevertheless|meanwhile|building on|following from|taken together|by contrast|"
    r"in turn|next|finally|similarly|conversely|as a result|having established|"
    r"with that in place|returning to|turning to)\b",
    re.I,
)

_DEMONSTRATIVE_RE = re.compile(
    r"^(this|that|these|those|it|they|such|he|she|his|her|their|its)\b", re.I
)
_NOUN_AFTER_DEMONSTRATIVE = frozenset(
    """
    section report part chapter document analysis table figure approach method paper study
    result results finding findings step stage phase example examples list summary
    """.split()
)

_CASUAL_MARKERS = (
    r"n't\b", r"'ll\b", r"'re\b", r"'ve\b", r"\bgonna\b", r"\bwanna\b", r"\bkinda\b",
    r"\byeah\b", r"\bhonestly\b", r"\bpretty much\b", r"\bstuff\b", r"\bwild\b",
    r"\bhassle\b", r"\beyeball\b", r"\bbother\b", r"\bbasically\b", r"\bmess\b",
    r"\bkind of\b", r"\byou\b", r"\bwe kinda\b", r"!",
)

_PAST_MARKERS = re.compile(
    r"\b(was|were|had|did|didn't|wasn't|weren't|went|came|took|made|got|used to|"
    r"looked|skipped|bothered)\b", re.I
)
_PRESENT_MARKERS = re.compile(
    r"\b(is|are|does|do|has|have|remains|requires|governs|reports|exposes|keeps|handles|"
    r"comes|feeds|constrains|validates|produces|computes|must|will|can|shall)\b", re.I
)

_REINTRO_RE = re.compile(
    r"^(in this (?:report|section|document|analysis)|this (?:section|report|chapter) "
    r"introduces|to begin|first(?:ly)?,|we (?:will )?(?:introduce|begin)|"
    r"let us begin|as an introduction)\b",
    re.I,
)

_ANTONYMS: tuple[tuple[str, str], ...] = (
    ("increases", "decreases"), ("increase", "decrease"), ("always", "never"),
    ("sufficient", "insufficient"), ("supports", "refutes"), ("valid", "invalid"),
    ("possible", "impossible"), ("required", "optional"), ("improves", "degrades"),
    ("rises", "falls"), ("more", "less"), ("consistent", "inconsistent"),
    ("stable", "unstable"), ("present", "absent"),
)


@dataclass
class TaxonomyReport:
    """Per-class counts, per-sentence flags and the BooookScore-like scalar."""

    counts: dict[str, int]
    sentence_flags: list[bool]
    errors_by_sentence: list[list[str]]
    booook_like_score: float
    n_sentences: int
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def comparable_score(self) -> float:
        """The same rate, over the error classes **both arms can incur**.

        ``booook_like_score`` includes the seam-local classes, and a monolithic
        answer has no seams: it cannot score ``missing_transition`` or a
        seam-anchored ``dangling_reference`` however bad it is. Comparing the two
        arms on the full score therefore charges the fragmented arm for a
        category the baseline is structurally exempt from, and the charge grows
        with N because the number of seams is N-1.

        Measured on the table run of 26 August: the full score put N=8 k=1 at
        +24.7 % against its baseline; on this one it reads +14.6 %.

        This is not an argument that seam defects do not matter -- they are the
        specific damage assembly does, and ``seam_error_rate`` reports them
        beside this. It is an argument that they belong in their own column
        rather than inside a ratio whose denominator cannot contain them.
        """
        if not self.n_sentences:
            return 0.0
        clean = sum(1 for errors in self.errors_by_sentence
                    if not [e for e in errors if e not in SEAM_LOCAL_CLASSES])
        return clean / self.n_sentences

    @property
    def seam_error_rate(self) -> float:
        """Seam-local errors per sentence -- the cost specific to assembly."""
        if not self.n_sentences:
            return 0.0
        return sum(self.counts.get(cls, 0)
                   for cls in SEAM_LOCAL_CLASSES) / self.n_sentences

    @property
    def total_errors(self) -> int:
        return sum(self.counts.values())

    @property
    def dirty_sentences(self) -> int:
        return sum(1 for flag in self.sentence_flags if flag)


def _casual_score(sentence: str) -> int:
    return sum(1 for pattern in _CASUAL_MARKERS if re.search(pattern, sentence, re.I))


def _tense_of(sentence: str) -> str:
    past = len(_PAST_MARKERS.findall(sentence))
    present = len(_PRESENT_MARKERS.findall(sentence))
    if past == present:
        return "none"
    return "past" if past > present else "present"


def _default_offsets(n_sentences: int, n_tasks: int) -> list[int]:
    """Even sentence offsets for fragment starts when the caller has none."""
    if n_tasks <= 1 or n_sentences == 0:
        return [0]
    per = n_sentences / n_tasks
    return [min(n_sentences - 1, int(round(i * per))) for i in range(n_tasks)]


def seam_error_taxonomy(
    text: str,
    plan: Plan | None = None,
    fragment_sentence_offsets: Sequence[int] | None = None,
    contract: Contract | None = None,
    expected_entities: Sequence[str] | None = None,
) -> TaxonomyReport:
    """Detect BooookScore-style coherence errors in an assembled answer.

    Args:
        text: The assembled answer.
        plan: The plan it was assembled from. Supplies the expected entities
            (for omission) and the fragment count (for seam locations).
        fragment_sentence_offsets: Sentence index at which each fragment
            starts. When supplied (the assembler does supply it), seam-local
            errors are attributed exactly instead of being estimated from an
            even split.
        contract: Optional contract, used to widen the expected-entity set.
        expected_entities: The entities a correct answer must mention. **Pass
            this whenever two arms are going to be compared, and pass the same
            value to both.** Omitting it falls back to the union of
            ``plan.tasks[].expected_entities``, which is a function of the
            partition: plan=None gives the contract's entities alone, N=2 gave 6
            on the table corpus, N=8 gave 17. Scoring one identical
            16-sentence answer through both conventions produced 0.9375 against
            0.5000 -- an apparent "coherence tax" of +46.7 % on text that never
            changed. The fallback is retained only so the detector can be used
            standalone on a single answer, where no comparison is at stake.

    Returns:
        A :class:`TaxonomyReport`. ``booook_like_score`` is the fraction of
        sentences carrying **no** detected error -- BooookScore's own
        definition, restricted to the mechanically detectable classes.
    """
    sentences = split_sentences(text)
    n = len(sentences)
    counts = {cls: 0 for cls in ERROR_CLASSES}
    errors_by_sentence: list[list[str]] = [[] for _ in range(n)]

    if n == 0:
        return TaxonomyReport(counts=counts, sentence_flags=[], errors_by_sentence=[],
                              booook_like_score=0.0, n_sentences=0)

    def flag(index: int, error: str) -> None:
        if 0 <= index < n and error not in errors_by_sentence[index]:
            errors_by_sentence[index].append(error)
            counts[error] += 1

    n_tasks = len(plan.tasks) if plan is not None else 1
    if fragment_sentence_offsets is not None:
        offsets = [o for o in fragment_sentence_offsets if 0 <= o < n]
    else:
        offsets = _default_offsets(n, n_tasks)
    seam_starts = sorted({o for o in offsets if o > 0})

    sentence_words = [set(content_words(s)) for s in sentences]
    sentence_ngrams = [set(ngrams(content_words(s), 3)) for s in sentences]

    # -- 1. entity omission ------------------------------------------------
    # The standard a correct answer is held to must NOT depend on how the prompt
    # was partitioned, and until now it did. The expected set was the union of
    # `plan.tasks[].expected_entities`, so:
    #
    #   * the monolithic baseline passes plan=None and was held to the
    #     contract's canonical entities alone -- 6 on the table corpus;
    #   * the fragmented arm was held to the union over its tasks -- 6 at N=2,
    #     10 at N=4, 17 at N=8.
    #
    # Scoring one identical 16-sentence answer through both conventions gives
    # 0.9375 against 0.5000, an apparent "coherence tax" of +46.7 % on text that
    # never changed. That is not a measurement of anything.
    #
    # Worse, the entities the plan contributes are table row refs and
    # destinations -- and the prompt forbids reproducing the table. The
    # fragmented arm was required to name entities its own instructions
    # prohibited.
    #
    # The contract defines the standard, because the contract is what both arms
    # receive. The plan is used only for ATTRIBUTION below: which fragment head
    # should have carried a missing entity.
    expected: list[str] = list(expected_entities) if expected_entities is not None else [
        entity for task in (plan.tasks if plan is not None else [])
        for entity in task.expected_entities
    ]
    if contract is not None:
        expected.extend(contract.canonical_entities)
    present_norms = {normalize_entity(e) for e in extract_entities(text, min_mentions=1)}
    text_lower = text.lower()
    missing: list[str] = []
    for entity in dict.fromkeys(expected):
        norm = normalize_entity(entity)
        if norm and norm not in present_norms and entity.lower() not in text_lower:
            missing.append(entity)
    # An omission is a property of the DOCUMENT -- there is no sentence in which
    # a missing entity fails to appear -- so it is counted, and attributed for
    # the trace, but it does not flag a sentence.
    #
    # It used to. `anchor = offsets[i % len(offsets)]` spread the missing
    # entities round-robin across the fragment heads, so the identical set of
    # omissions dirtied ONE sentence with plan=None and up to N with a plan of N
    # tasks. The score is clean/n_sentences, so the same document lost 1/n at
    # monolithic and N/n at N fragments. That is the partition changing the
    # score through the attribution, which attribution must never do.
    counts["entity_omission"] = len(missing)
    omission_anchors = [offsets[i % len(offsets)] if offsets else 0
                        for i in range(len(missing))]

    # -- 2. duplicated content --------------------------------------------
    for j in range(1, n):
        for i in range(j):
            if not sentence_ngrams[j] or not sentence_ngrams[i]:
                continue
            overlap = len(sentence_ngrams[i] & sentence_ngrams[j]) / max(
                1, min(len(sentence_ngrams[i]), len(sentence_ngrams[j]))
            )
            if overlap >= 0.8 or sentences[i].strip() == sentences[j].strip():
                flag(j, "duplicated_content")
                break

    # -- 3. contradiction --------------------------------------------------
    for j in range(1, n):
        for i in range(j):
            shared = sentence_words[i] & sentence_words[j]
            if len(shared) < 2:
                continue
            for pos, neg in _ANTONYMS:
                a_has = pos in sentence_words[i] and neg in sentence_words[j]
                b_has = neg in sentence_words[i] and pos in sentence_words[j]
                if a_has or b_has:
                    flag(j, "contradiction")
                    break
            else:
                # Negation flip over otherwise near-identical content.
                union = sentence_words[i] | sentence_words[j]
                if union and len(shared) / len(union) >= 0.6:
                    neg_i = bool(re.search(r"\b(not|never|no)\b", sentences[i], re.I))
                    neg_j = bool(re.search(r"\b(not|never|no)\b", sentences[j], re.I))
                    if neg_i != neg_j:
                        flag(j, "contradiction")
            if "contradiction" in errors_by_sentence[j]:
                break

    # -- 4. abrupt register / tense shift ----------------------------------
    casual = [_casual_score(s) for s in sentences]
    doc_casual_rate = sum(1 for c in casual if c > 0) / n
    tenses = [_tense_of(s) for s in sentences]
    informative = [t for t in tenses if t != "none"]
    doc_tense = "present"
    if informative:
        doc_tense = max({"past", "present"}, key=informative.count)
    for i in range(n):
        shifted = False
        if doc_casual_rate <= 0.5 and casual[i] >= 1:
            shifted = True
        elif doc_casual_rate > 0.5 and casual[i] == 0:
            shifted = True
        if tenses[i] != "none" and tenses[i] != doc_tense:
            shifted = True
        if shifted:
            flag(i, "register_tense_shift")

    # -- 5. dangling reference ---------------------------------------------
    for i in range(n):
        match = _DEMONSTRATIVE_RE.match(sentences[i])
        if not match:
            continue
        rest = tokenize(sentences[i])[1:2]
        if rest and rest[0].lower() in _NOUN_AFTER_DEMONSTRATIVE:
            continue  # determiner use ("This section ..."), not a dangling pronoun
        no_antecedent = i == 0 or not (sentence_words[i - 1] & sentence_words[i])
        if i in seam_starts or no_antecedent:
            flag(i, "dangling_reference")

    # -- 6. missing transition ---------------------------------------------
    for i in seam_starts:
        if _CONNECTIVE_RE.match(sentences[i]):
            continue
        prev_words = sentence_words[i - 1]
        cur_words = sentence_words[i]
        union = prev_words | cur_words
        overlap = len(prev_words & cur_words) / len(union) if union else 0.0
        if overlap < 0.15:
            flag(i, "missing_transition")

    # -- 7. repeated introduction ------------------------------------------
    intro_hits = [i for i in range(n) if _REINTRO_RE.match(sentences[i])]
    for i in intro_hits[1:]:
        flag(i, "repeated_introduction")
    if intro_hits and intro_hits[0] not in seam_starts and intro_hits[0] != 0:
        flag(intro_hits[0], "repeated_introduction")

    # -- 8. inconsistent naming --------------------------------------------
    by_norm = extract_entity_surfaces(text)
    inconsistent_forms: list[str] = []
    for _norm, forms in by_norm.items():
        if len(forms) > 1:
            # The first form seen is treated as canonical; the rest are variants.
            inconsistent_forms.extend(forms[1:])
    for form in inconsistent_forms:
        for i, sentence in enumerate(sentences):
            if form in sentence:
                flag(i, "inconsistent_naming")
                break

    sentence_flags = [bool(errors) for errors in errors_by_sentence]
    clean = sum(1 for flagged in sentence_flags if not flagged)
    return TaxonomyReport(
        counts=counts,
        sentence_flags=sentence_flags,
        errors_by_sentence=errors_by_sentence,
        booook_like_score=clean / n,
        n_sentences=n,
        details={
            "missing_entities": missing,
            "omission_anchors": omission_anchors,
            "seam_starts": seam_starts,
            "doc_tense": doc_tense,
            "doc_casual_rate": doc_casual_rate,
            "inconsistent_forms": inconsistent_forms,
        },
    )


# --------------------------------------------------------------------------
# Redundancy
# --------------------------------------------------------------------------


def redundancy(text: str | Sequence[str], n: int = 4) -> float:
    """Redundancy of an answer, in ``[0, 1]`` (lower is better).

    * Given a single string: the **self-repetition** rate, i.e. the fraction of
      ``n``-grams that are not unique.
    * Given a sequence of fragments: the mean pairwise ``n``-gram Jaccard
      overlap **between** fragments -- the quantity that says "these two nodes
      independently wrote the same paragraph", which is the waste that ``rho``
      is supposed to buy down and can equally well inflate.
    """
    if isinstance(text, str):
        grams = ngrams(content_words(text), n)
        if not grams:
            return 0.0
        return 1.0 - (len(set(grams)) / len(grams))
    return redundancy_between(list(text), n=n)


def redundancy_between(fragments: Sequence[str], n: int = 4) -> float:
    """Mean pairwise ``n``-gram Jaccard overlap between fragments."""
    grams = [set(ngrams(content_words(f), n)) for f in fragments]
    pairs = [(i, j) for i in range(len(grams)) for j in range(i + 1, len(grams))]
    if not pairs:
        return 0.0
    total = 0.0
    for i, j in pairs:
        union = grams[i] | grams[j]
        total += (len(grams[i] & grams[j]) / len(union)) if union else 0.0
    return total / len(pairs)


# --------------------------------------------------------------------------
# tau_sem calibration
# --------------------------------------------------------------------------


@dataclass
class TauCalibration:
    """Result of calibrating the seam threshold ``tau_sem``."""

    tau: float
    beta: float
    f_beta: float
    precision: float
    recall: float
    curve: list[dict[str, float]]
    n_pairs: int

    def as_dict(self) -> dict[str, float]:
        return {
            "tau": self.tau,
            "beta": self.beta,
            "f_beta": self.f_beta,
            "precision": self.precision,
            "recall": self.recall,
            "n_pairs": float(self.n_pairs),
        }


def _cosine_rows(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    num = np.sum(a * b, axis=1)
    den = np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1)
    den[den == 0.0] = 1.0
    return num / den


def calibrate_tau(
    pairs: Sequence[tuple[str, str, bool]],
    embedder: Any,
    *,
    beta: float = 0.5,
    n_grid: int = 199,
) -> TauCalibration:
    """Derive ``tau_sem`` from labelled seam / non-seam pairs.

    This is the "calibrate, do not fix" requirement of the master document
    (section 5.6) made executable. ``tau_sem = 0.85`` is rejected there as a
    magic number: embedding spaces are anisotropic, random text can already
    show high cosine, and no embedding model dominates across tasks. The only
    defensible threshold is one fitted on labelled data **for the model and
    domain in use**, and re-fitted whenever either changes.

    Args:
        pairs: ``(left_text, right_text, is_seam)`` triples. ``is_seam=True``
            marks a genuine discontinuity that ought to receive a bridge.
        embedder: Anything with ``.embed(texts) -> np.ndarray``.
        beta: F-beta weight. **Must be < 1**, which weights *precision* above
            recall. The asymmetry is deliberate and matches the router's: an
            unnecessary synthesis call rewrites text that was already fine
            (and a rewrite can introduce its own errors), whereas a missed
            seam leaves a rough join that the taxonomy will at least report.
        n_grid: Resolution of the threshold sweep over ``(0, 1)``.

    Returns:
        A :class:`TauCalibration` with the chosen ``tau`` -- always strictly
        inside ``(0, 1)`` -- and the full precision/recall/F-beta curve.
    """
    if not pairs:
        raise ValueError("calibrate_tau needs at least one labelled pair")
    if not 0.0 < beta < 1.0:
        raise ValueError(f"beta must be in (0, 1) for an asymmetric loss, got {beta}")

    left = [p[0] for p in pairs]
    right = [p[1] for p in pairs]
    labels = np.array([bool(p[2]) for p in pairs])

    vec_left = np.asarray(embedder.embed(left), dtype=np.float64)
    vec_right = np.asarray(embedder.embed(right), dtype=np.float64)
    sims = _cosine_rows(vec_left, vec_right)

    beta_sq = beta * beta
    curve: list[dict[str, float]] = []
    best = {"tau": 0.5, "f_beta": -1.0, "precision": 0.0, "recall": 0.0}

    for k in range(1, n_grid + 1):
        tau = k / (n_grid + 1)  # strictly inside (0, 1)
        predicted = sims < tau  # below threshold => call it a seam, bridge it
        tp = int(np.sum(predicted & labels))
        fp = int(np.sum(predicted & ~labels))
        fn = int(np.sum(~predicted & labels))
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        denom = beta_sq * precision + recall
        f_beta = ((1 + beta_sq) * precision * recall / denom) if denom > 0 else 0.0
        curve.append({"tau": tau, "precision": precision, "recall": recall, "f_beta": f_beta})
        # Ties break toward the SMALLER tau: fewer predicted seams, fewer
        # unnecessary synthesis calls. Same asymmetry as beta < 1.
        if f_beta > best["f_beta"] + 1e-12:
            best = {"tau": tau, "f_beta": f_beta, "precision": precision, "recall": recall}

    if best["f_beta"] <= 0.0:
        # Degenerate labelling: fall back to the median similarity, clamped.
        median = float(np.median(sims)) if len(sims) else 0.5
        best["tau"] = min(0.99, max(0.01, median))

    tau = min(0.99, max(0.01, float(best["tau"])))
    return TauCalibration(
        tau=tau,
        beta=beta,
        f_beta=float(best["f_beta"]),
        precision=float(best["precision"]),
        recall=float(best["recall"]),
        curve=curve,
        n_pairs=len(pairs),
    )


# --------------------------------------------------------------------------
# alpha calibration (micro-level consensus thresholds)
# --------------------------------------------------------------------------


@dataclass
class AlphaCalibration:
    """Result of calibrating the consensus routing thresholds."""

    alpha_high: float
    alpha_low: float
    beta: float
    f_beta_high: float
    precision_high: float
    recall_high: float
    recall_low: float
    curve: list[dict[str, float]]
    n_units: int
    base_rate: float

    def as_dict(self) -> dict[str, float]:
        return {
            "alpha_high": self.alpha_high,
            "alpha_low": self.alpha_low,
            "beta": self.beta,
            "f_beta_high": self.f_beta_high,
            "precision_high": self.precision_high,
            "recall_high": self.recall_high,
            "recall_low": self.recall_low,
            "n_units": float(self.n_units),
            "base_rate": self.base_rate,
        }


def calibrate_alpha(
    observations: Sequence[tuple[float, bool]],
    *,
    beta: float = 0.5,
    n_grid: int = 199,
) -> AlphaCalibration:
    """Derive ``alpha_high`` and ``alpha_low`` from labelled consensus units.

    This is :func:`calibrate_tau`'s sibling and exists for the same reason:
    ``alpha_high = 0.80`` and ``alpha_low = 0.55`` are magic numbers. An
    agreement score is a function of the embedder, the consistency threshold and
    the diversity of the family pool, none of which are portable, so the
    defaults in :mod:`swarmbly_v0.consensus` are placeholders and the thresholds
    that get used must be fitted **for the model set and domain in use** and
    re-fitted whenever either changes.

    Args:
        observations: ``(agreement, is_acceptable)`` pairs, one per aligned
            column, where ``is_acceptable`` is an external quality label for
            what consensus would have emitted there. Human labels are the point;
            the harness bootstraps them from the judge, which makes the fitted
            alphas only as good as the judge.
        beta: F-beta weight for ``alpha_high``. **Must be < 1**, which weights
            precision above recall. The asymmetry mirrors the tau calibration
            and the router: above ``alpha_high`` the consensus takes the medoid
            *without* consulting the judge, so a false "high agreement" ships an
            unreviewed unit, while a false "not high enough" only spends a judge
            call that was not strictly needed.
        n_grid: Resolution of the threshold sweep over ``(0, 1)``.

    Returns:
        An :class:`AlphaCalibration`. ``alpha_high`` maximises the
        precision-weighted F-beta of "agreement predicts acceptable"; ties break
        toward the **larger** threshold, which is the conservative direction
        here (fewer units skip the judge). ``alpha_low`` is then the largest
        threshold that still catches at least 90% of the unacceptable units --
        the opposite asymmetry, deliberately: failing to *flag* a bad region is
        the error that reaches the user unannounced. ``alpha_low`` is clamped to
        be no greater than ``alpha_high``.
    """
    if not observations:
        raise ValueError("calibrate_alpha needs at least one labelled observation")
    if not 0.0 < beta < 1.0:
        raise ValueError(f"beta must be in (0, 1) for an asymmetric loss, got {beta}")

    agreements = np.array([float(a) for a, _ in observations], dtype=np.float64)
    labels = np.array([bool(ok) for _, ok in observations])
    beta_sq = beta * beta

    curve: list[dict[str, float]] = []
    best = {"alpha": 0.5, "f_beta": -1.0, "precision": 0.0, "recall": 0.0}
    low_candidates: list[tuple[float, float]] = []

    for k in range(1, n_grid + 1):
        alpha = k / (n_grid + 1)  # strictly inside (0, 1)
        predicted = agreements >= alpha  # at/above threshold => call it acceptable
        tp = int(np.sum(predicted & labels))
        fp = int(np.sum(predicted & ~labels))
        fn = int(np.sum(~predicted & labels))
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        denom = beta_sq * precision + recall
        f_beta = ((1 + beta_sq) * precision * recall / denom) if denom > 0 else 0.0

        # Flagging view: how many genuinely unacceptable units fall below alpha.
        bad_total = int(np.sum(~labels))
        bad_flagged = int(np.sum(~predicted & ~labels))
        flag_recall = bad_flagged / bad_total if bad_total else 0.0

        curve.append({
            "alpha": alpha, "precision": precision, "recall": recall,
            "f_beta": f_beta, "flag_recall": flag_recall,
        })
        # Ties break toward the LARGER alpha: fewer units skip the judge.
        if f_beta > best["f_beta"] - 1e-12:
            if f_beta > best["f_beta"] + 1e-12 or alpha > best["alpha"]:
                best = {"alpha": alpha, "f_beta": f_beta,
                        "precision": precision, "recall": recall}
        if flag_recall >= 0.90:
            low_candidates.append((alpha, flag_recall))

    if best["f_beta"] <= 0.0:
        median = float(np.median(agreements)) if len(agreements) else 0.5
        best = {"alpha": min(0.99, max(0.01, median)), "f_beta": 0.0,
                "precision": 0.0, "recall": 0.0}

    alpha_high = min(0.99, max(0.01, float(best["alpha"])))
    if low_candidates:
        alpha_low, recall_low = max(low_candidates, key=lambda pair: pair[0])
    else:
        alpha_low, recall_low = alpha_high, 0.0
    alpha_low = min(alpha_low, alpha_high)

    return AlphaCalibration(
        alpha_high=alpha_high,
        alpha_low=float(alpha_low),
        beta=beta,
        f_beta_high=float(best["f_beta"]),
        precision_high=float(best["precision"]),
        recall_high=float(best["recall"]),
        recall_low=float(recall_low),
        curve=curve,
        n_units=len(observations),
        base_rate=float(np.mean(labels)) if len(labels) else 0.0,
    )


# --------------------------------------------------------------------------
# Coverage model (availability under packet loss)
# --------------------------------------------------------------------------
#
# The Lander-Waterman coverage equations describe how many random reads are
# needed before every base of a genome is seen at least once. Swarmbly reuses the
# *shape* of those equations and changes what is random, which is the whole of
# the substantive difference:
#
#   genomics  -- reads land at random positions on a pre-existing sequence; the
#                stochastic element is SAMPLE PLACEMENT, and coverage buys you
#                protection against the gaps that random placement leaves.
#   Swarmbly   -- packets are dispatched deliberately, one per micro-task, by a
#                planner that knows exactly which unit each packet covers. There
#                is no placement lottery. What is random is whether a dispatched
#                packet COMES BACK: a volunteer node drops out, times out, is
#                behind a NAT that closes, or simply returns nothing.
#
# So the model below is a packet-loss model wearing a coverage model's clothes,
# and every function here bounds AVAILABILITY -- "did at least one usable reply
# for this unit arrive?" -- and nothing else. It says nothing about whether the
# replies that did arrive are correct, coherent, or on-task. Semantic
# correctness is measured by the taxonomy, the entity grid and the judge; the
# agreement score is what speaks to cross-replica reliability. Reporting a
# coverage number as if it were a quality number would be exactly the category
# error this repository exists to avoid.


def effective_coverage(c: float, p: float) -> float:
    """Coverage that actually returns, ``c_eff = c * (1 - p)``.

    Args:
        c: Nominal coverage -- replicas dispatched per semantic unit. ``c = 3``
            means every unit was asked for three times.
        p: Per-packet loss probability in ``[0, 1)``: the chance that a
            dispatched packet yields nothing usable (node offline, timeout,
            refusal, empty reply).

    Returns:
        The expected number of *arriving* replicas per unit. Loss is treated as
        independent across packets, which is optimistic: correlated failure
        (one flaky peer holding several packets, a regional outage) is the
        realistic case and makes this an upper bound.
    """
    if not 0.0 <= p < 1.0:
        raise ValueError(f"p must be in [0, 1), got {p}")
    if c < 0.0:
        raise ValueError(f"c must be non-negative, got {c}")
    return c * (1.0 - p)


def expected_uncovered(M: float, c: float, p: float) -> float:
    """Expected number of semantic units with **no** surviving replica.

    ``expected_uncovered_fraction = exp(-c_eff)``, and this returns
    ``M * exp(-c_eff)``, so ``M = 1`` gives the fraction directly.

    Args:
        M: Number of semantic units in the plan (the analogue of genome length).
        c: Nominal coverage per unit.
        p: Per-packet loss probability.

    Returns:
        Expected count of units left with nothing to assemble from. An
        uncovered unit is a **hole in the answer**, not a wrong answer: the
        orchestrator knows which unit it is and can retry, degrade gracefully,
        or report the gap. That is the only failure mode this bounds.
    """
    if M < 0.0:
        raise ValueError(f"M must be non-negative, got {M}")
    return float(M) * math.exp(-effective_coverage(c, p))


def expected_islands(n_packets: float, c: float, p: float, theta: float) -> float:
    """Expected number of disconnected assembled regions ("islands").

    ``E[islands] = n_packets * exp(-c_eff * theta)``, the Lander-Waterman island
    count with the loss-adjusted coverage substituted for the raw one.

    Args:
        n_packets: Number of packets dispatched.
        c: Nominal coverage per unit.
        p: Per-packet loss probability.
        theta: Minimum detectable overlap fraction -- how much two neighbouring
            fragments must share before the assembler can tell they belong
            together. In Swarmbly this is a property of the *packing*: the
            flanking context each packet carries is what creates detectable
            overlap, so ``theta`` and ``rho`` are two views of one budget.
            ``theta -> 0`` (any overlap detectable) recovers the textbook
            ``n * exp(-c_eff)``.

    Returns:
        Expected island count. More than one island means the answer arrives in
        pieces that cannot be joined with confidence -- a *structural* failure
        of assembly, again distinct from being wrong.
    """
    if not 0.0 <= theta <= 1.0:
        raise ValueError(f"theta must be in [0, 1], got {theta}")
    if n_packets < 0.0:
        raise ValueError(f"n_packets must be non-negative, got {n_packets}")
    return float(n_packets) * math.exp(-effective_coverage(c, p) * theta)


def required_coverage(epsilon: float, p: float) -> float:
    """Coverage needed to leave at most a fraction ``epsilon`` uncovered.

    Inverting ``exp(-c(1-p)) = epsilon``::

        required_coverage(epsilon, p) = ln(1 / epsilon) / (1 - p)

    Args:
        epsilon: Target uncovered fraction, in ``(0, 1)``. ``0.01`` means "at
            most 1% of semantic units come back with nothing".
        p: Per-packet loss probability in ``[0, 1)``.

    Returns:
        The nominal coverage to dispatch. With ``p = 0`` this is the familiar
        ``ln(1/epsilon)``: 4.6x for 1%, 6.9x for 0.1%, and the genomics rule of
        thumb ``8x -> e^-8 ~ 0.034%``. Loss inflates it by ``1/(1-p)``, so 10%
        packet loss turns a 4.61x requirement into ``4.61 / 0.9 ~ 5.12x``.

        This is a **cost** statement, not a quality statement: it says how many
        redundant dispatches availability costs, and nothing about whether the
        replies that arrive are any good.
    """
    if not 0.0 < epsilon < 1.0:
        raise ValueError(f"epsilon must be in (0, 1), got {epsilon}")
    if not 0.0 <= p < 1.0:
        raise ValueError(f"p must be in [0, 1), got {p}")
    return math.log(1.0 / epsilon) / (1.0 - p)


# --------------------------------------------------------------------------
# Contract compliance / global quality judge
# --------------------------------------------------------------------------


def contract_compliance(text: str, contract: Contract) -> dict[str, float]:
    """Per-axis compliance of ``text`` with the global contract, each in [0, 1]."""
    lowered = text.lower()
    entities = contract.canonical_entities
    if entities:
        hits = sum(1 for e in entities if e.lower() in lowered)
        entity_coverage = hits / len(entities)
    else:
        entity_coverage = 1.0

    forbidden = contract.forbidden_terms
    if forbidden:
        violations = sum(1 for term in forbidden if term.lower() in lowered)
        forbidden_clean = 1.0 - (violations / len(forbidden))
    else:
        forbidden_clean = 1.0

    sentences = split_sentences(text)
    casual_rate = (sum(1 for s in sentences if _casual_score(s) > 0) / len(sentences)
                   if sentences else 0.0)
    register_match = (1.0 - casual_rate) if contract.register == "formal" else casual_rate
    register_match = min(1.0, max(0.0, register_match))

    produced = count_tokens(text)
    target = max(contract.target_length_tokens, 1)
    length_match = math.exp(-abs(produced - target) / target)

    return {
        "entity_coverage": entity_coverage,
        "forbidden_clean": forbidden_clean,
        "register_match": register_match,
        "length_match": length_match,
    }


def quality_judge(
    text: str,
    contract: Contract,
    embedder: Any | None = None,
    weights: Mapping[str, float] | None = None,
) -> float:
    """A cheap, deterministic stand-in for an LLM judge, in ``[0, 1]``.

    Combines contract compliance with topical relevance to the objective. It
    is deliberately *not* a coherence measure -- keeping "is it on-task?" and
    "does it hang together?" separate is the whole point of measuring
    coherence as a first-class metric.
    """
    axes = contract_compliance(text, contract)
    if embedder is not None and contract.objective.strip() and text.strip():
        vectors = np.asarray(embedder.embed([contract.objective, text]), dtype=np.float64)
        axes["relevance"] = max(0.0, float(_cosine_rows(vectors[:1], vectors[1:])[0]))
    else:
        axes["relevance"] = 0.5

    default_weights = {
        "entity_coverage": 0.25,
        "forbidden_clean": 0.15,
        "register_match": 0.20,
        "length_match": 0.15,
        "relevance": 0.25,
    }
    used = dict(default_weights)
    if weights:
        used.update(weights)
    total_weight = sum(used[k] for k in axes)
    return sum(axes[k] * used[k] for k in axes) / total_weight if total_weight else 0.0
