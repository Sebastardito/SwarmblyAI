"""Request language: detection and the few strings the pipeline adds itself.

Everything a worker reads that does not come from the user's own text — the
contract header, the task heading, the batch directive — used to be English
whatever language the request was in. Small models follow the language of the
scaffolding as much as the language of the request, so a Spanish essay came
back half in English (diagnosis 2026-10-15, finding 3). This module keeps
those strings in the request's language.

Detection is a stopword vote: deterministic, dependency-free and good enough
for the four languages listed. Anything it cannot tell defaults to English,
which reproduces the previous behaviour exactly.
"""

from __future__ import annotations

import re

DEFAULT_LANG = "en"

_STOPWORDS: dict[str, frozenset[str]] = {
    "en": frozenset("the and of to in is that for with on as are this be it by "
                    "from or an which each write about their your".split()),
    "es": frozenset("el la los las de del y que en un una por con para es se "
                    "su sus al lo como más sobre cada escribe redacta texto "
                    "incluye".split()),
    "pt": frozenset("o os as de do da dos das e que em um uma por com para é "
                    "não seu sua ao como mais sobre cada escreva texto".split()),
    "fr": frozenset("le la les de des du et que en un une pour avec est sur "
                    "au aux ce qui dans chaque écrivez rédigez texte".split()),
}
# Words shared by several languages carry no signal.
_SHARED = frozenset(w for lang, words in _STOPWORDS.items() for w in words
                    if sum(w in other for other in _STOPWORDS.values()) > 1)
_WORD = re.compile(r"[a-záéíóúñüçàâêôãõèëïîû]+", re.I)


def detect_language(text: str) -> str:
    """ISO 639-1 code of ``text`` among en/es/pt/fr; ``en`` when unsure."""
    words = [w.lower() for w in _WORD.findall(text or "")]
    if not words:
        return DEFAULT_LANG
    scores = {lang: sum(1 for w in words if w in vocab and w not in _SHARED)
              for lang, vocab in _STOPWORDS.items()}
    best = max(scores, key=lambda k: scores[k])
    ranked = sorted(scores.values(), reverse=True)
    if ranked[0] < 2 or ranked[0] < 1.5 * ranked[1]:
        return DEFAULT_LANG
    return best


# Strings the pipeline itself writes into a worker prompt. English entries
# reproduce the historical wording byte for byte (the ρ figures depend on it),
# except "batch", reworded on 23 Oct 2026 (P3i/P3j): "answer only the numbered
# items …, keeping each item's number" made phi3.5 and qwen2.5:3b re-list the
# items; an example line ("1. answer") made them renumber or write "respuesta".
# In 8 model × fragment cells (n = 1 each) the plain wording below was the only
# one parsed and translated in all eight.
STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "contract": "[GLOBAL CONTRACT]", "objective": "objective",
        "audience": "audience", "register": "register", "format": "format",
        "target_len": "target_len", "prefer": "prefer", "avoid": "avoid",
        "entities": "use these exact names", "style": "style",
        "context": "CONTEXT", "task": "[TASK]",
        "respond_format": "Respond in {fmt} format.",
        "respond_lang": "",
        "batch": ("For each item, write one line with its number and your answer. "
                  "Do not repeat the item."),
        "no_answer": "(no verified answer)",
    },
    "es": {
        "contract": "[CONTRATO GLOBAL]", "objective": "objetivo",
        "audience": "audiencia", "register": "registro", "format": "formato",
        "target_len": "longitud objetivo", "prefer": "preferir", "avoid": "evitar",
        "entities": "usa exactamente estos nombres", "style": "estilo",
        "context": "CONTEXTO", "task": "[TAREA]",
        "respond_format": "Responde en formato {fmt}.",
        "respond_lang": "Responde en español.",
        "batch": ("Para cada elemento, escribe una línea con su número y tu respuesta. "
                  "No repitas el elemento."),
        "no_answer": "(sin respuesta verificada)",
    },
    "pt": {
        "contract": "[CONTRATO GLOBAL]", "objective": "objetivo",
        "audience": "público", "register": "registro", "format": "formato",
        "target_len": "extensão alvo", "prefer": "preferir", "avoid": "evitar",
        "entities": "use exatamente estes nomes", "style": "estilo",
        "context": "CONTEXTO", "task": "[TAREFA]",
        "respond_format": "Responda em formato {fmt}.",
        "respond_lang": "Responda em português.",
        "batch": ("Para cada item, escreva uma linha com o número e a sua resposta. "
                  "Não repita o item."),
        "no_answer": "(sem resposta verificada)",
    },
    "fr": {
        "contract": "[CONTRAT GLOBAL]", "objective": "objectif",
        "audience": "public", "register": "registre", "format": "format",
        "target_len": "longueur cible", "prefer": "préférer", "avoid": "éviter",
        "entities": "utilise exactement ces noms", "style": "style",
        "context": "CONTEXTE", "task": "[TÂCHE]",
        "respond_format": "Réponds au format {fmt}.",
        "respond_lang": "Réponds en français.",
        "batch": ("Pour chaque élément, écris une ligne avec son numéro et ta réponse. "
                  "Ne répète pas l'élément."),
        "no_answer": "(pas de réponse vérifiée)",
    },
}

_VALUES: dict[str, dict[str, str]] = {
    "es": {"prose": "prosa", "code": "código", "casual": "informal"},
    "pt": {"prose": "prosa", "code": "código", "casual": "informal"},
    "fr": {"prose": "prose", "code": "code", "casual": "familier"},
}


def strings(lang: str | None) -> dict[str, str]:
    return STRINGS.get(lang or DEFAULT_LANG, STRINGS[DEFAULT_LANG])


def value(lang: str | None, raw: object) -> str:
    """A contract value (format, register) in the request's language."""
    text = str(raw)
    return _VALUES.get(lang or DEFAULT_LANG, {}).get(text, text)
