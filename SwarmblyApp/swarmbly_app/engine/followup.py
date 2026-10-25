"""Follow-up messages in the distributed path: make them standalone, locally.

The local path sends the model the last messages of the conversation; the
distributed path used to send only the last message (diagnosis 2026-10-15,
finding 6). A follow-up such as "now make it shorter" reached the planner and
the workers with nothing to refer to, and came back as an essay about the
global contract itself.

Workers must not receive the conversation (SPEC §4: decontextualised
packets), so the conversation is resolved *on this device*: the local model
rewrites the last message as one self-contained request, and that request —
not the history — is what is classified, planned and fragmented. When the
message needs context and no local model can rewrite it, the request is not
distributed at all: it is answered locally, with the full history.
"""

from __future__ import annotations

import re
from typing import Any

MAX_TURNS = 6
MAX_TURN_CHARS = 600
SHORT_MESSAGE_WORDS = 6
FOLLOWUP_MAX_WORDS = 40

# Words that point back into the conversation (es / en / pt / fr).
_ANAPHORA = re.compile(
    r"\b(eso|esto|esta|este|ese|esa|ello|lo anterior|anterior|lo mismo|"
    r"contin[uú]a|sigue|ampl[ií]a|res[uú]me(?:lo)?|trad[uú]ce(?:lo)?|hazlo|"
    r"m[aá]s corto|m[aá]s largo|otra vez|de nuevo|ahora|"
    r"that|this|it|them|those|above|previous|again|continue|expand|shorten|"
    r"rewrite|translate|now|isso|isto|aquilo|cela|ça|ceci|pr[ée]c[ée]dent|encore)\b",
    re.I)


def needs_context(text: str, history: list[dict[str, Any]] | None) -> bool:
    """Whether ``text`` probably refers to earlier turns of ``history``."""
    if not history:
        return False
    words = (text or "").split()
    if len(words) <= SHORT_MESSAGE_WORDS:
        return True
    if len(words) > FOLLOWUP_MAX_WORDS:
        return False
    return bool(_ANAPHORA.search(" ".join(words[:12])))


def _clip(text: str) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= MAX_TURN_CHARS else text[:MAX_TURN_CHARS] + "…"


def rewrite_prompt(text: str, history: list[dict[str, Any]]) -> str:
    turns = [m for m in history if m.get("role") in ("user", "assistant")][-MAX_TURNS:]
    convo = "\n".join(f"{'User' if m['role'] == 'user' else 'Assistant'}: "
                      f"{_clip(str(m.get('content') or ''))}" for m in turns)
    return ("Rewrite the user's LAST message as one self-contained request that can "
            "be understood without the conversation. Resolve every reference (it, "
            "that, the previous text) using the conversation. Keep the user's "
            "language and every constraint they gave. Do not answer the request. "
            "Output only the rewritten request.\n\n"
            f"Conversation:\n{convo}\n\nLast message: {text}\n\n"
            "Self-contained request:")


_LABEL = re.compile(r"^(?:self-contained request|request|solicitud|petici[óo]n)\s*:\s*",
                    re.I)


def standalone(text: str, history: list[dict[str, Any]] | None,
               backend: Any) -> tuple[str | None, str]:
    """``(request, source)``: the request to plan and how it was obtained.

    ``source`` is ``as_is`` (no context needed), ``local_rewrite`` (rewritten
    by the local model) or ``unavailable`` (context needed, no rewrite; the
    caller must not distribute and returns ``None`` as the request).
    """
    if not needs_context(text, history):
        return text, "as_is"
    out = ""
    if backend is not None:
        out = (backend.generate(rewrite_prompt(text, history or []),
                                max_tokens=300, temperature=0.0) or "").strip()
    out = _LABEL.sub("", out).strip().strip('"“”«»').strip()
    if not out or len(out) > max(4 * len(text), len(text) + 1500):
        return None, "unavailable"
    return out, "local_rewrite"
