"""Shared, dependency-free text utilities.

Everything in the V0 harness that needs to count tokens, split sentences or
guess at entities goes through this module, so that a single (documented,
crude) tokenisation convention is used consistently when computing ``rho``.

The tokeniser is deliberately *not* a BPE tokeniser: V0 measures a ratio
(``rho = sum(|K_i|) / |P|``), and a ratio is invariant to a constant
tokens-per-word factor. Using a word-ish tokeniser keeps the harness free of
model downloads while leaving the reported ratio meaningful.
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence

__all__ = [
    "STOPWORDS",
    "tokenize",
    "count_tokens",
    "truncate_tokens",
    "split_into_token_chunks",
    "split_sentences",
    "content_words",
    "keywords",
    "extract_entities",
    "extract_entity_surfaces",
    "normalize_entity",
    "ngrams",
    "jaccard",
]

# Tokens are word-ish runs (letters, digits, underscore, apostrophe) plus
# standalone punctuation marks. Whitespace is never a token.
_TOKEN_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_']*|[^\sA-Za-z0-9_]")

# Sentence boundary: terminal punctuation followed by whitespace and an
# opening-ish character, or an explicit newline / bullet break.
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[\"'(\[]*[A-Z0-9])|\n+")

STOPWORDS: frozenset[str] = frozenset(
    """
    a an the and or but if then than that this these those there here of to in on at by for with
    from as is are was were be been being do does did doing have has had having it its it's i you
    he she they we me him her them us my your his their our not no nor so such very can could
    should would will shall may might must about into over under again further once because while
    during before after above below between both each few more most other some any all only own
    same too s t just don now which who whom whose what when where why how also however therefore
    thus per via using use used one two three against another through within across without upon
    among whether since unless until toward towards rather every either neither much many several
    various given still even well back down out off across along above beside besides yet already
    """.split()
)

# Words that look like entities to a capitalisation heuristic but are not.
_ENTITY_STOP: frozenset[str] = frozenset(
    """
    the a an this that these those it they we you i he she there here first second third finally
    however therefore moreover furthermore additionally consequently overall in on at for to of and
    but or so if when while because after before during since although though next then also
    """.split()
)


def tokenize(text: str) -> list[str]:
    """Split ``text`` into the harness' canonical token list."""
    return _TOKEN_RE.findall(text or "")


def count_tokens(text: str) -> int:
    """Number of canonical tokens in ``text``."""
    return len(_TOKEN_RE.findall(text or ""))


def truncate_tokens(text: str, max_tokens: int) -> str:
    """Return the prefix of ``text`` holding at most ``max_tokens`` tokens.

    Truncation happens at a token boundary in the *original* string, so
    formatting (newlines, bullets) inside the retained prefix is preserved.
    """
    if max_tokens <= 0:
        return ""
    spans = [m.end() for m in _TOKEN_RE.finditer(text or "")]
    if len(spans) <= max_tokens:
        return text
    return text[: spans[max_tokens - 1]]


def split_into_token_chunks(text: str, n_chunks: int) -> list[str]:
    """Cut ``text`` into ``n_chunks`` contiguous slices of near-equal token mass.

    Used when a prompt has fewer natural units (sentences, bullets) than the
    requested number of micro-tasks. Slicing by tokens rather than duplicating
    sentences keeps ``sum(|task_i|) ~ |P|``, which is what makes ``rho = 1.0``
    reachable as a genuine no-redundancy floor.
    """
    if n_chunks <= 1:
        return [text]
    spans = [m.span() for m in _TOKEN_RE.finditer(text or "")]
    if len(spans) < n_chunks:
        return [text] * n_chunks
    per = len(spans) / n_chunks
    chunks: list[str] = []
    start_char = 0
    for i in range(n_chunks):
        end_token = len(spans) - 1 if i == n_chunks - 1 else int(round((i + 1) * per)) - 1
        end_token = max(0, min(end_token, len(spans) - 1))
        end_char = spans[end_token][1]
        chunk = text[start_char:end_char].strip()
        chunks.append(chunk if chunk else text[start_char:end_char])
        start_char = end_char
    return chunks


def split_sentences(text: str) -> list[str]:
    """Split ``text`` into sentences with a regex heuristic.

    Bullet lines and hard line breaks count as sentence boundaries, which
    matters because fragment outputs are often list-shaped.
    """
    if not text or not text.strip():
        return []
    parts = _SENT_SPLIT_RE.split(text.strip())
    out: list[str] = []
    for part in parts:
        if part is None:
            continue
        cleaned = part.strip()
        if cleaned:
            out.append(cleaned)
    return out


def content_words(text: str) -> list[str]:
    """Lower-cased alphabetic tokens that are not stopwords."""
    return [
        tok.lower()
        for tok in tokenize(text)
        if tok[0].isalpha() and tok.lower() not in STOPWORDS and len(tok) > 2
    ]


def keywords(text: str, limit: int = 12) -> list[str]:
    """Most frequent content words, ties broken by first appearance.

    Deterministic: no randomness, no set iteration order dependence.
    """
    counts: dict[str, int] = {}
    order: dict[str, int] = {}
    for idx, word in enumerate(content_words(text)):
        counts[word] = counts.get(word, 0) + 1
        order.setdefault(word, idx)
    ranked = sorted(counts, key=lambda w: (-counts[w], order[w]))
    return ranked[:limit]


def normalize_entity(name: str) -> str:
    """Normalise an entity surface form for identity comparison.

    ``"Swarmbly-AI"``, ``"swarmbly ai"`` and ``"Swarmbly AI"`` all normalise to
    ``"swarmbly ai"``; this is what makes *inconsistent naming* detectable.
    """
    cleaned = re.sub(r"[^A-Za-z0-9]+", " ", name).strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if cleaned.endswith("s") and len(cleaned) > 3:
        cleaned = cleaned[:-1]
    return cleaned


def extract_entities(text: str, min_mentions: int = 1) -> list[str]:
    """Extract candidate entity surface forms without a parser.

    Two cheap signals are combined:

    1. Capitalised tokens (and capitalised multi-token runs) that are not
       sentence-initial function words -- proper nouns and named concepts.
    2. Frequently repeated content words -- the salient nouns of the text.

    ``min_mentions`` filters to entities mentioned at least that many times,
    which mirrors the *salience* filter of the entity-grid model.
    """
    surface_counts: dict[str, int] = {}
    surface_first: dict[str, int] = {}
    canonical: dict[str, str] = {}

    sentences = split_sentences(text)

    def _capitalised_runs(tokens: Sequence[str]) -> list[tuple[int, list[str]]]:
        runs: list[tuple[int, list[str]]] = []
        run: list[str] = []
        start = 0
        for idx, tok in enumerate(tokens):
            if tok and tok[0].isalpha() and tok[0].isupper():
                if not run:
                    start = idx
                run.append(tok)
            elif run:
                runs.append((start, run))
                run = []
        if run:
            runs.append((start, run))
        return runs

    # A single capitalised word at the start of a sentence is usually just
    # orthography ("Write a report..."), not an entity. Accept it only if the
    # same form is also capitalised somewhere it did not have to be.
    mid_sentence_forms: set[str] = set()
    for sentence in sentences:
        for start, run in _capitalised_runs(tokenize(sentence)):
            if start > 0:
                for tok in run:
                    mid_sentence_forms.add(normalize_entity(tok))
                mid_sentence_forms.add(normalize_entity(" ".join(run)))

    def _record(surface: str, position: int) -> None:
        norm = normalize_entity(surface)
        if not norm or norm in _ENTITY_STOP:
            return
        surface_counts[norm] = surface_counts.get(norm, 0) + 1
        if norm not in surface_first:
            surface_first[norm] = position
            canonical[norm] = surface

    for position, sentence in enumerate(sentences):
        tokens = tokenize(sentence)
        for start, run in _capitalised_runs(tokens):
            if start == 0 and len(run) == 1:
                if normalize_entity(run[0]) not in mid_sentence_forms:
                    continue  # sentence-initial capitalisation only
            if start == 0 and len(run) > 1:
                # Drop a leading function word: "The Northwind Ledger" -> "Northwind Ledger".
                if normalize_entity(run[0]) in _ENTITY_STOP:
                    run = run[1:]
                if not run:
                    continue
            _record(" ".join(run), position)

    # Repeated content words as fallback entities.
    word_counts: dict[str, int] = {}
    for word in content_words(text):
        word_counts[word] = word_counts.get(word, 0) + 1
    for word, count in word_counts.items():
        if count >= 2:
            norm = normalize_entity(word)
            if norm and norm not in surface_counts and norm not in _ENTITY_STOP:
                surface_counts[norm] = count
                surface_first[norm] = 10_000 + len(surface_first)
                canonical[norm] = word

    selected = [n for n, c in surface_counts.items() if c >= min_mentions]
    selected.sort(key=lambda n: (surface_first[n], n))
    return [canonical[n] for n in selected]


def extract_entity_surfaces(text: str) -> dict[str, list[str]]:
    """Map each normalised entity to **every distinct surface form** used for it.

    :func:`extract_entities` collapses an entity to one canonical surface, which
    is what callers usually want -- but it therefore cannot see that a document
    called the same thing two different things. This function keeps the
    variants, which is what makes *inconsistent naming* detectable.
    """
    surfaces: dict[str, list[str]] = {}
    sentences = split_sentences(text)

    for sentence in sentences:
        tokens = tokenize(sentence)
        run: list[str] = []
        start = 0
        runs: list[tuple[int, list[str]]] = []
        for idx, tok in enumerate(tokens):
            if tok and tok[0].isalpha() and tok[0].isupper():
                if not run:
                    start = idx
                run.append(tok)
            elif run:
                runs.append((start, run))
                run = []
        if run:
            runs.append((start, run))

        for begin, tokens_in_run in runs:
            candidate = list(tokens_in_run)
            if begin == 0:
                if len(candidate) == 1:
                    continue
                if normalize_entity(candidate[0]) in _ENTITY_STOP:
                    candidate = candidate[1:]
            if not candidate:
                continue
            surface = " ".join(candidate)
            norm = normalize_entity(surface)
            if not norm or norm in _ENTITY_STOP:
                continue
            bucket = surfaces.setdefault(norm, [])
            if surface not in bucket:
                bucket.append(surface)
    return surfaces


def ngrams(tokens: Sequence[str], n: int) -> list[tuple[str, ...]]:
    """All contiguous ``n``-grams of ``tokens`` (empty if too short)."""
    if n <= 0 or len(tokens) < n:
        return []
    return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def jaccard(a: Iterable[object], b: Iterable[object]) -> float:
    """Jaccard similarity of two iterables treated as sets (0.0 if both empty)."""
    set_a, set_b = set(a), set(b)
    if not set_a and not set_b:
        return 0.0
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)
