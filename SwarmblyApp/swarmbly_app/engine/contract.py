"""Γ for the product: upstream ``global_contract`` plus language-aware fixes.

``swarmbly_v0.planner.global_contract`` is tuned on the English corpora of
the measurement harness, and that is right for the harness. On a Spanish
request it produced (diagnosis 2026-10-15, finding 4):

- ``audience: a technical reader`` — the English default, for any request
  whose first sentence has no "for a … audience";
- ``target_length_tokens: 320`` — ``_LENGTH_RE`` only reads "words" and
  "tokens", so "800 palabras" was not seen;
- canonical entities ``Escribe, Incluye, Abre, Desarrolla`` — imperative verbs
  capitalised only because they start a bullet;
- ``avoid: obviously, as an AI language model, in conclusion`` — English
  defaults handed to a Spanish answer.

This module keeps the upstream contract (upstream untouched) and corrects
those fields after the fact. The language is returned beside the contract,
because ``Contract`` has no field for it; packets carry it as the Γ
extension ``lang``.
"""

from __future__ import annotations

import dataclasses
import re

from ..lang import DEFAULT_LANG, detect_language

# "800 palabras", "entre 750 y 850 palabras", "about 500 words", "1.200 mots".
_RANGE = re.compile(
    r"\b(?:entre|between|de|from)\s+(\d{1,2}[.,]?\d{3}|\d{2,5})\s*(?:y|and|a|to|e|et|-|–)\s*"
    r"(\d{1,2}[.,]?\d{3}|\d{2,5})\s*(words|palabras|palavras|mots|tokens)\b", re.I)
_SINGLE = re.compile(r"\b(\d{1,2}[.,]\d{3}|\d{2,5})\s*(words|palabras|palavras|mots|tokens)\b",
                     re.I)
# Tokens per word: ~1.3 for English, more for Romance languages with BPE vocabularies.
_TOKENS_PER_WORD = {"en": 1.3, "es": 1.6, "pt": 1.6, "fr": 1.6}
_UPSTREAM_DEFAULT_AUDIENCE = "a technical reader"
_UPSTREAM_DEFAULT_FORBIDDEN = ("obviously", "as an AI language model", "in conclusion")
# Line start, bullet, or sentence start: where any word is capitalised.
_POSITION_START = re.compile(r"(?:^\s*|[\n.!?¡¿]\s*|^\s*[-*•]\s*|\n\s*[-*•\d.)\]]+\s*)$")


@dataclasses.dataclass(frozen=True)
class RequestContract:
    contract: object                  # swarmbly_v0.schema.Contract
    lang: str
    target_words: int | None          # explicit length the user asked for
    length_explicit: bool


def requested_words(prompt: str) -> int | None:
    """The answer length the request states, in words (tokens → words /1.3)."""
    text = prompt or ""
    match = _RANGE.search(text)
    if match:
        low, high = (_number(match.group(1)), _number(match.group(2)))
        value, unit = (low + high) // 2, match.group(3).lower()
    else:
        match = _SINGLE.search(text)
        if not match:
            return None
        value, unit = _number(match.group(1)), match.group(2).lower()
    if unit == "tokens":
        value = int(value / 1.3)
    return value if 10 <= value <= 20000 else None


def answer_budget(prompt: str, base: int, *, headroom: float = 1.5,
                  cap: int = 8192) -> int:
    """``max_tokens`` for a single local answer: ``base``, raised to fit an
    explicitly requested length (the local path used the configured 1024
    tokens even for an 800-word Spanish essay, and truncated it)."""
    words = requested_words(prompt)
    if words is None:
        return int(base)
    rate = _TOKENS_PER_WORD.get(detect_language(prompt), 1.3)
    return int(min(cap, max(int(base), int(headroom * words * rate) + 1)))


def _number(raw: str) -> int:
    return int(re.sub(r"[.,]", "", raw))


def _sentence_start_only(entity: str, prompt: str) -> bool:
    """True when ``entity`` is not a name of the request: no occurrence is
    capitalised away from the start of a line, bullet or sentence.

    Upstream also returns lower-case words: for "Para cada una de las
    siguientes palabras…" it gave ("para", "cada", "una"), the case-sensitive
    search found no occurrence and kept them, and every packet said "usa
    exactamente estos nombres: para, cada, una" (P3i.1, 23 Oct 2026) — an
    instruction to keep words unchanged, in a batch asking to translate them.
    """
    for m in re.finditer(rf"\b{re.escape(entity)}\b", prompt, re.I):
        if m.group(0)[:1].isupper() and _POSITION_START.search(prompt[:m.start()]) is None:
            return False
    return True


def build_contract(prompt: str) -> RequestContract:
    """Upstream Γ with language-aware length, audience, entities and lexicon."""
    from swarmbly_v0 import planner

    lang = detect_language(prompt)
    words = requested_words(prompt)
    target = None
    if words is not None:
        target = int(words * _TOKENS_PER_WORD.get(lang, 1.3))
    contract = planner.global_contract(prompt, backend=None, target_length_tokens=target)

    changes: dict[str, object] = {}
    if (contract.audience == _UPSTREAM_DEFAULT_AUDIENCE
            and _UPSTREAM_DEFAULT_AUDIENCE not in prompt.lower()):
        changes["audience"] = ""          # neutral: no audience was stated
    entities = tuple(e for e in contract.canonical_entities
                     if not _sentence_start_only(e, prompt))
    if entities != tuple(contract.canonical_entities):
        changes["canonical_entities"] = entities
    if lang != DEFAULT_LANG:
        forbidden = tuple(t for t in contract.forbidden_terms
                          if t not in _UPSTREAM_DEFAULT_FORBIDDEN)
        if forbidden != tuple(contract.forbidden_terms):
            changes["forbidden_terms"] = forbidden
    if changes:
        contract = dataclasses.replace(contract, **changes)
    return RequestContract(contract=contract, lang=lang, target_words=words,
                           length_explicit=words is not None)
