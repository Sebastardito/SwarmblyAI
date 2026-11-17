"""Recipes: the "¿Qué quieres hacer?" entry (3.3).

A recipe is a way of working the user picks before writing: it fills the
request with a template the user completes, and it turns on what that kind of
work needs. The answer then goes through the same chat as any other message;
what the recipe changed is recorded in the answer (``meta.recipe``) and in its
receipt. A recipe never widens what may leave the computer: research with
public sources still sends only the query the user approves, word for word.

- ``documents`` · ask your documents: the user's sources only, no public lookup
  offered for that answer.
- ``table`` · compare documents in a table: the table built by code (recipe 2),
  even when the request does not use the word "tabla".
- ``research`` · research with public sources: the query proposed before the
  answer and approved by the user; the documents and the results, the
  comparison by code, the disagreements and the claim verifier (recipe 3).
- ``list`` · process a list on the swarm: not available yet (roadmap).
"""

from __future__ import annotations

import re
from typing import Any

RECIPES = ("documents", "table", "research", "list")
AVAILABLE = ("documents", "table", "research")


def valid(recipe: str | None) -> str:
    """The recipe's id when it can run, otherwise ""."""
    recipe = str(recipe or "").strip().lower()
    return recipe if recipe in AVAILABLE else ""


def listing() -> list[dict[str, Any]]:
    """The recipes and whether each can run (the names and templates are the
    interface's, in its language)."""
    return [{"id": r, "available": r in AVAILABLE} for r in RECIPES]


# what the research template says around the user's words
_TOPIC = re.compile(r"(?:fuentes\s+p[uú]blicas|public\s+sources)\s+(?:dicen\s+|say\s+)?(?:sobre|acerca\s+de|de|about|on)\s+"
                    r"(.+?)(?:,|\s+y\s+di\b|\s+and\s+say\b|[.?!]|$)", re.I)
_NAME = re.compile(r"(?<=[^\W\d_])[\s,;:(«\"']+([A-ZÁÉÍÓÚÑ][\wáéíóúñü-]{2,})")


def propose_query(text: str, glossary: list[tuple[str, str]] | None = None) -> str:
    """The query offered to the user before a research answer: nothing is sent
    until the user approves it (and may edit it). The template's own words
    ("Compara … con lo que dicen las fuentes públicas sobre …") are not the
    topic: the query is what follows "sobre", and the names the request gives
    ("la variedad Kanela")."""
    from .web_search import propose_query as propose
    m = _TOPIC.search(text or "")
    if m:
        # only the topic the user wrote for the public sources: the rest of the
        # request is about their documents ("el rendimiento del lote AB2"), and a
        # lot code or a name from it does not belong in a public query
        return propose(m.group(1), "", glossary or [])[:200]
    query = propose(text or "", "", glossary or [])
    words = {w.lower() for w in query.split()}
    names = [n for n in _NAME.findall(text or "") if n.lower() not in words]
    return " ".join([query, *names]).strip()[:200]
