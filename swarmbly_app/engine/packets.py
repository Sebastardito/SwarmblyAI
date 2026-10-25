"""SPEC §8 packets built from structured fields (never from packed text).

``swarmbly_v0.packing`` renders a packet as one text block whose contract
header contains ``session: <id>`` — and that id is ``BLAKE2b(prompt)``, the
same for every fragment of a request and for every user who sends the same
prompt. Sending that text would hand workers a linkage identifier that SPEC §4
forbids. This module builds the wire packet field by field instead:

- ``contract`` is Γ *minimised* (SPEC §5 SHOULD): the operation, register,
  format, and only the canonical entities that appear in this fragment. The
  full request never travels as Γ.objective.
- ``predecessors`` carry a typed carry only when the task text consumes a
  predecessor value (SPEC §9.1, upstream ``consumes_predecessor``).
- ``task.instruction`` is the fragment's own text.
- ``deadline_ms`` is a duration.

ρ is measured on exactly what the worker will see (the rendered packet), with
upstream ``count_tokens``. In v0.1 packets carry their mandatory content only;
following whitepaper v2 §9.7, ρ is *derived and reported*, not configured.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from ..lang import DEFAULT_LANG, strings
from ..p2p.messages import WIRE_VERSION, attempt_id_for, packet as wire_packet, task_id_for
from ..p2p.worker import render_packet_prompt

OBJECTIVE_MAX_CHARS = 240
_WORDS = re.compile(r"\w+", re.U)
_FIRST_SENTENCE = re.compile(r"^(.+?[.!?:])(\s|$)", re.S)


def minimal_objective(admission, contract) -> str:
    """The operation shared by every fragment — never the whole request."""
    if admission.path == "enumerated" and admission.preamble.strip():
        text = admission.preamble.strip()
    else:
        objective = (contract.objective or "").strip()
        match = _FIRST_SENTENCE.match(objective)
        text = match.group(1) if match else objective
    text = " ".join(text.split())
    return text[:OBJECTIVE_MAX_CHARS]


# Upstream ``planner.plan`` closes the last task of a fan-in with this English
# directive. It is meant for sections of one composition; an enumerated batch
# or a reference map has independent units, and the sentence only adds English
# scaffolding to a packet that may be in another language.
UPSTREAM_INTEGRATION_SUFFIX = " Close the answer; do not repeat earlier parts."


_LANGUAGES = (r"ingl[ée]s|english|anglais|espa[ñn]ol|spanish|espagnol|franc[ée]s|french|"
              r"fran[çc]ais|portugu[ée]s|portuguese|alem[áa]n|german|allemand|alem[ãa]o|"
              r"italiano|italian|italien|chino|chinese|japon[ée]s|japanese|quechua|kichwa")
# The request names the language of the answer ("traducción al inglés",
# "translate into French"): "respond in <request language>" would contradict it.
_TARGET_LANGUAGE = re.compile(
    r"\b(?:al|a|en|para|into|to|in|en|vers|para o|em)\s+(?:el\s+|la\s+|l')?(?:"
    + _LANGUAGES + r")\b", re.I)


def answer_language_named(text: str) -> bool:
    return bool(_TARGET_LANGUAGE.search(text or ""))


def localise_instruction(instruction: str, lang: str, path: str) -> str:
    """The task text a worker receives, with directives in the request's language.

    - independent units (``enumerated`` / ``reference``) lose the upstream
      integration suffix;
    - an enumerated batch gets the localised batch directive (it replaces the
      upstream ``[NN]`` answer-sheet directive, which is never used: the
      user's own format instructions travel instead);
    - a non-English request gets "respond in <language>" *inside the task*,
      so workers running an older renderer still see it.
    """
    text = instruction
    if path in ("enumerated", "reference") and text.endswith(UPSTREAM_INTEGRATION_SUFFIX):
        text = text[: -len(UPSTREAM_INTEGRATION_SUFFIX)]
    s = strings(lang)
    if path == "enumerated":
        text = f"{text.rstrip()}\n\n{s['batch']}"
    if lang != DEFAULT_LANG and s["respond_lang"] and not answer_language_named(text):
        # P3h.1 (23 Oct 2026): "da solo su traducción al inglés … Responde en
        # español." Small models obeyed the last line and echoed the Spanish
        # words — the main source of the echo rejections since P3b.
        text = f"{text.rstrip()}\n{s['respond_lang']}"
    return text


def gamma_for(contract, objective: str, fragment_text: str,
              max_out_tokens: int, lang: str = DEFAULT_LANG) -> dict[str, Any]:
    """Γ for one fragment (SPEC §5 fields; required ones always present).

    ``lang`` is an app extension (SWIP draft): the request's language, so the
    worker renders its scaffolding in that language. Omitted for English
    (the default), so English Γ is unchanged from v0.2.0.
    """
    lowered = fragment_text.lower()
    entities = [e for e in contract.canonical_entities if e.lower() in lowered]
    gamma = {
        "v": WIRE_VERSION,
        "objective": objective,
        "audience": contract.audience,
        "register": contract.register,
        "format": _spec_format(contract.output_format),
        "target_len": None,
        "lexicon": {"prefer": [], "forbid": list(contract.forbidden_terms)},
        "entities": [{"name": e, "canonical": e, "role": ""} for e in entities],
        "style_seed": "",
        "budget": {"max_out_tokens": int(max_out_tokens)},
    }
    if lang and lang != DEFAULT_LANG:
        gamma["lang"] = lang
    return gamma


def _spec_format(fmt: str) -> str:
    """SPEC §5 allows prose|markdown|json|code; upstream also says 'list'."""
    return fmt if fmt in ("prose", "markdown", "json", "code") else "markdown"


@dataclass
class PacketPlan:
    task_id: str            # upstream plan id (t0…) — local only
    wire_task_id: str       # one-way BLAKE2b id (SPEC §4) — what workers see
    level: int
    index: int
    instruction: str
    consumes: bool
    depends_on: tuple[str, ...]
    lane: str


def build_message(pp: PacketPlan, gamma: dict[str, Any], session_id: bytes,
                  attempt: int, carries: dict[str, str],
                  positions: dict[str, tuple[int, int]], *, max_tokens: int,
                  deadline_ms: int, tier: str, temperature: float,
                  model_family: str | None, model: str | None = None) -> dict[str, Any]:
    """Assemble one wire packet for one attempt of one micro-task."""
    task_id = task_id_for(session_id, pp.level, pp.index)
    predecessors = []
    if pp.consumes:
        for dep in pp.depends_on:
            summary = carries.get(dep)
            if summary:
                predecessors.append({
                    "task_id": task_id_for(session_id, *positions[dep]),
                    "summary": summary, "tokens": len(summary.split())})
    constraints: dict[str, Any] = {"temperature": temperature, "top_p": 0.95,
                                   "stop": []}
    if model_family:
        constraints["model_family"] = model_family  # app extension (SWIP draft)
    if model:
        constraints["model"] = model                # exact model wanted (app extension)
    return wire_packet(
        attempt_id=attempt_id_for(task_id, attempt),
        contract=gamma,
        predecessors=predecessors,
        task={"instruction": pp.instruction, "kind": "generate",
              "expects": {"format": gamma["format"], "min_tokens": 0,
                          "max_tokens": int(max_tokens)}},
        deadline_ms=int(deadline_ms), lane=pp.lane, tier=tier,
        constraints=constraints, commitment_request=None)


def measure_rho(messages: list[dict[str, Any]], prompt: str) -> dict[str, Any]:
    """ρ = Σ|K_i| / |P| over what the workers actually receive (SPEC §9)."""
    from swarmbly_v0.textutil import count_tokens
    p_tokens = max(1, count_tokens(prompt))
    packet_tokens = [count_tokens(render_packet_prompt(m)) for m in messages]
    total = sum(packet_tokens)
    gamma_bytes = [len(str(m.get("contract", ""))) for m in messages]
    # How much of the request one packet carries: the share of the request's
    # words (as a multiset) found in that packet's task text. A packet near
    # 1.0 is the whole request in all but name — what the privacy self-check
    # (exact match only) did not see in the diagnosis of 2026-10-15
    # (finding 8). Reported, not enforced.
    request_words = Counter(_WORDS.findall(prompt.lower()))
    n_words = max(1, sum(request_words.values()))
    task_fraction = [
        sum((Counter(_WORDS.findall(str((m.get("task") or {}).get("instruction") or "")
                                    .lower())) & request_words).values()) / n_words
        for m in messages]
    return {
        "rho_achieved": round(total / p_tokens, 4),
        # Packets carry mandatory content only (task + Γ_min + consumed carry),
        # so the floor and the achieved value coincide by construction.
        "rho_floor": round(total / p_tokens, 4),
        "rho_target": None,
        "rho_reachable": None,
        "rho_policy": "derived (whitepaper v2 §9.7): mandatory content only; "
                      "no ρ target is pursued in v0.1",
        "prompt_tokens": p_tokens,
        "packet_tokens": packet_tokens,
        "gamma_chars_max": max(gamma_bytes) if gamma_bytes else 0,
        "max_packet_prompt_fraction": round(max(task_fraction), 4) if task_fraction else 0.0,
        "max_packet_prompt_fraction_note": "largest share of the request's words "
                                           "carried by one packet's task text",
    }


def contains_identifier(message: dict[str, Any], session_hex: str,
                        prompt: str) -> list[str]:
    """Privacy self-check run before dispatch: returns what leaked, if anything."""
    text = render_packet_prompt(message) + str(message.get("contract", ""))
    leaks = []
    if session_hex and session_hex in text:
        leaks.append("session identifier")
    if len(prompt) > 80 and prompt.strip() in text:
        leaks.append("the complete request")
    return leaks
