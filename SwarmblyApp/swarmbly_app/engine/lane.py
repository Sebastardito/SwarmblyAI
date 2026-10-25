"""Lane classification with context for ambiguous words (P2e follow-up).

SwarmblyLCE's ``HeuristicClassifier`` is a conservative regex baseline: any
"legal", "salud" or "médico" sends a request to the SENSITIVE lane. That keeps
personal matters on the device, but also keeps out public questions such as
"inicio de la protección legal del lobo peletero" (P2e round 8b) or "¿qué es
la salud pública?".

Here the upstream verdict is refined, never loosened for strong terms:
- strong terms (password, card, IBAN, passport, diagnosis, salary, debt) are
  SENSITIVE wherever they appear;
- context terms (legal, lawyer, health, medical) are SENSITIVE only when a
  first-person marker ("mi", "tengo", "my", "I") sits in the same clause;
- otherwise the text is classified again with the context terms masked, so
  e-mails, phone numbers and "mi jefe" still make it SANITISABLE.
"""

from __future__ import annotations

import re

_STRONG = re.compile(
    r"\b(diagn[oó]stic|diagnos|salario|salary|deuda|debt|contraseña|password|tarjeta|"
    r"credit card|iban|ssn|pasaporte|passport)\w*", re.I)
_CONTEXT = re.compile(r"\b(legal|abogad|lawyer|salud|health|m[eé]dic|medical)\w*", re.I)
_PERSONAL = re.compile(
    r"\b(mi|mis|me|yo|tengo|estoy|mío|mía|conmigo|nuestr\w*|my|mine|i|i'm|i've|me|our|"
    r"meu|minha|tenho|mon|ma|mes|j'ai)\b", re.I)
_CLAUSE_SPLIT = re.compile(r"[.;:!?¿¡\n]|,\s")


def classify(text: str) -> str:
    try:
        from swarmbly_lce.projection import HeuristicClassifier
        upstream = HeuristicClassifier()
        lane = upstream.classify(text).name
    except Exception:
        return "SENSITIVE"                 # cannot classify → never leave the device
    if lane != "SENSITIVE" or _STRONG.search(text):
        return lane
    for clause in _CLAUSE_SPLIT.split(text):
        if _CONTEXT.search(clause) and _PERSONAL.search(clause):
            return "SENSITIVE"
    masked = _CONTEXT.sub("asunto", text)
    return upstream.classify(masked).name
