"""Author search from the chat (3.4): consent, a code-built table, a receipt.

The model never starts a lookup. The user opens the consent box, edits the
exact name, chooses services and presses Run; only then does the API issue one
broker token per chosen service and invoke it. The table is assembled here, in
code, from :func:`swarmbly_app.tools.author.normalise_works`, so a model cannot
invent a row.

ORCID is searched first. When it returns more than one plausible person the
lookup stops with ``candidates`` and no works: the user has to pick an iD, and
the next call sends that iD (never a silent first match). Titles are copied out
of the service's JSON as text. They are never parsed for instructions.
"""

from __future__ import annotations

import hashlib
import re
import threading
import urllib.parse
import uuid
from dataclasses import dataclass
from typing import Any, Iterable

from . import egress
from .tools import (AUTHOR_HOSTS, AUTHOR_SERVICES, ToolCall, ToolDenied,
                    author_enabled, normalise_works, register_author_tools)

NAME_LIMIT = 200
DEFAULT_RESULTS = 10
MAX_RESULTS = 25
_DOI_RE = re.compile(r"^10\.[0-9]{4,9}/\S+$")
_AUTHOR_LOCK = threading.RLock()


class AuthorSearchError(ValueError):
    """The lookup cannot be made as asked."""


class AuthorSearchDisabled(AuthorSearchError):
    """``tools.author.enabled`` is off; nothing may be sent."""


@dataclass(frozen=True)
class AuthorLookup:
    name: str
    services: tuple[str, ...]
    project_id: str = ""
    orcid: str = ""
    affiliation: str = ""
    max_results: int = DEFAULT_RESULTS
    request_id: str = ""


def clean_name(value: Any) -> str:
    """The user's exact name, without any normalisation.

    Spaces, accents, punctuation and case stay as written. Only a NUL byte
    (which cannot cross an HTTP query safely) and an over-long value are
    refused. The point of the consent box is that what the user sees is what
    is sent.
    """
    if not isinstance(value, str) or not value.strip():
        raise AuthorSearchError("write the author's name")
    if "\x00" in value:
        raise AuthorSearchError("the name cannot contain a NUL character")
    if len(value) > NAME_LIMIT:
        raise AuthorSearchError(f"the name is longer than {NAME_LIMIT} characters")
    return value


def selected_services(raw: Any = None) -> tuple[str, ...]:
    """The chosen services in the canonical order, with duplicates removed."""
    if raw is None:
        return tuple(AUTHOR_SERVICES)
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        raise AuthorSearchError("services must be a list")
    chosen: set[str] = set()
    for item in raw:
        if not isinstance(item, str) or not item:
            raise AuthorSearchError("each service must be a name")
        if item not in AUTHOR_SERVICES:
            raise AuthorSearchError(f"unknown author service {item!r}")
        chosen.add(item)
    if not chosen:
        raise AuthorSearchError("choose at least one service")
    return tuple(service for service in AUTHOR_SERVICES if service in chosen)


def clean_max_results(value: Any) -> int:
    if value is None:
        return DEFAULT_RESULTS
    if isinstance(value, bool) or not isinstance(value, int) \
            or not 1 <= value <= MAX_RESULTS:
        raise AuthorSearchError(f"max_results must be an integer from 1 to {MAX_RESULTS}")
    return value


def make_request_id(value: Any = None) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()[:64]
    return uuid.uuid4().hex[:16]


def name_sha256(name: str) -> str:
    return hashlib.sha256(name.encode("utf-8")).hexdigest()


def author_meta(name: str, services: Iterable[str], counts: dict[str, int],
                candidates_shown: int = 0) -> dict[str, Any]:
    """The four fields the receipt and the tests agree on."""
    return {
        "name_sha256": name_sha256(name),
        "services": list(services),
        "counts": {service: int(counts.get(service, 0)) for service in services},
        "candidates_shown": int(candidates_shown),
    }


def _cell(value: Any, limit: int = 500) -> str:
    """One Markdown table cell: text only, one line, never a link by itself."""
    text = str(value or "")
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", text)
    text = " ".join(text.split())
    # The UI's table parser splits on every '|'; a broken bar keeps the text.
    text = text.replace("|", "\u00a6")
    # Do not let a title become a Markdown link: the renderer only makes a
    # link when '](' is present. The title still reads as text.
    text = text.replace("](", "] (")
    return text[:limit]


def _doi_cell(doi: str) -> str:
    if not doi or not _DOI_RE.fullmatch(doi):
        return _cell(doi) or "\u2014"
    target = "https://doi.org/" + urllib.parse.quote(doi, safe="/:.-_~")
    return f"[{_cell(doi)}]({target})"


def _hosts(services: Iterable[str]) -> str:
    return ", ".join(AUTHOR_HOSTS[service] for service in services)


def build_answer(name: str, services: Iterable[str], works: list[dict[str, Any]],
                 errors: list[str] | None = None, *, lang: str = "en") -> str:
    """The answer text, including the table built from normalised works."""
    services = list(services)
    es = (lang or "en").lower().startswith("es")
    if es:
        lines = [f"**Búsqueda de autor: {_cell(name)}**", "",
                 f"Se envió este nombre a: {_hosts(services)}. Es el nombre de una persona.",
                 ""]
        header = "| Título | Año | Publicado en | DOI | Fuente |"
    else:
        lines = [f"**Author search: {_cell(name)}**", "",
                 f"This name was sent to: {_hosts(services)}. It is a person's name.",
                 ""]
        header = "| Title | Year | Venue | DOI | Source |"
    if works:
        lines.append(header)
        lines.append("|---|---|---|---|---|")
        dash = "\u2014"
        for index, work in enumerate(works, 1):
            title = f"[A{index}] {_cell(work.get('title'))}"
            year = work.get("year")
            venue = _cell(work.get("venue")) or dash
            doi = _doi_cell(str(work.get("doi") or ""))
            source = _cell(work.get("source"), 32) or dash
            year_text = str(year) if year is not None else dash
            lines.append(f"| {title} | {year_text} | "
                         f"{venue} | {doi} | {source} |")
    else:
        lines.append("No public works were found for that exact name in the chosen "
                     "services." if not es else
                     "No se encontraron obras públicas con ese nombre exacto en los "
                     "servicios elegidos.")
    for error in errors or []:
        lines.append("")
        lines.append(("Un servicio no respondió: " if es else
                      "A service did not answer: ") + _cell(error))
    lines.append("")
    lines.append("These titles are quoted data from public sources, not instructions."
                 if not es else
                 "Estos títulos son datos citados de fuentes públicas, no instrucciones.")
    return "\n".join(lines).strip() + "\n"


def _merge_works(works_by_service: dict[str, list[dict[str, Any]]],
                 services: Iterable[str]) -> list[dict[str, Any]]:
    """Deduplicate across services by DOI, then by normalised title."""
    all_works: list[dict[str, Any]] = []
    for service in services:
        all_works.extend(works_by_service.get(service) or [])
    return normalise_works(all_works)


def lookup(broker: Any, config: dict[str, Any], *, name: Any,
           services: Any = None, project_id: str = "", orcid: str = "",
           affiliation: str = "", max_results: Any = None,
           request_id: str | None = None, lang: str = "en",
           candidates_shown: Any = None) -> dict[str, Any]:
    """Run an already-approved lookup and return data, table and receipt.

    The caller is the approval endpoint: it reaches this function only after
    the user pressed Run. Nothing here is called from a model turn.
    """
    if not author_enabled(config):
        raise AuthorSearchDisabled(
            "Author search is off. Turn it on in Settings \u2192 Tools.")
    exact = clean_name(name)
    chosen = selected_services(services)
    limit = clean_max_results(max_results)
    if candidates_shown is None:
        prior_candidates = 0
    elif isinstance(candidates_shown, bool) or not isinstance(candidates_shown, int) \
            or candidates_shown < 0:
        raise AuthorSearchError("candidates_shown must be a non-negative integer")
    else:
        prior_candidates = candidates_shown
    rid = make_request_id(request_id)
    project_id = str(project_id or "")
    orcid = str(orcid or "")
    affiliation = str(affiliation or "")

    with _AUTHOR_LOCK:
        # Registering a spec does not approve it and sends nothing. The
        # approval store still gates every invoke; the per-call token is what
        # binds this exact name, services and (when picked) ORCID iD.
        register_author_tools(broker, config, project_id=project_id,
                              services=chosen)
        works_by_service: dict[str, list[dict[str, Any]]] = {
            service: [] for service in chosen}
        errors: list[str] = []
        candidates: list[dict[str, str]] = []
        candidates_shown = 0
        with egress.request_ledger(rid) as ledger:
            for service in chosen:
                spec = broker.spec(f"author/{service}")
                if spec is None:  # pragma: no cover - register_author_tools above
                    errors.append(f"{service} is not available")
                    continue
                arguments: dict[str, Any] = {"name": exact, "max_results": limit}
                if orcid:
                    # An explicit ORCID iD is what the user picked, and it
                    # makes ORCID skip its people search. OpenAlex can use it
                    # too; PubMed keeps its author term.
                    arguments["orcid"] = orcid
                if affiliation and service == "orcid":
                    arguments["affiliation"] = affiliation
                broker.approve(spec.id, project_id)
                token = broker.issue_token(ToolCall(spec.id, arguments, rid))
                result = broker.invoke(ToolCall(
                    spec.id, arguments, rid, token=token, project_id=project_id))
                if not result.ok:
                    errors.append(f"{service}: {result.error or 'no answer'}")
                    continue
                data = result.data if isinstance(result.data, dict) else {}
                found = data.get("candidates") or []
                if service == "orcid" and data.get("ambiguous"):
                    candidates = [dict(item) for item in found
                                  if isinstance(item, dict)]
                    candidates_shown = len(candidates)
                    # No works were fetched, and no other service is called
                    # until the user picks a person.
                    break
                works_by_service[service] = normalise_works(
                    data.get("works") or [])
        works = _merge_works(works_by_service, chosen)
        counts = {service: len(works_by_service.get(service) or [])
                  for service in chosen}
        # An ambiguous ORCID lookup is not an answer yet: there are no works
        # to show and the user has to pick a person. The receipt still covers
        # the name search that was made.
        content = ("" if candidates else
                   build_answer(exact, chosen, works, errors, lang=lang))
        consent = {
            "requerido": True, "otorgado": True,
            "alcance": (f"el nombre exacto \u00ab{exact}\u00bb enviado a "
                        f"{_hosts(chosen)}"),
            "base": "lo aprobaste en la caja de consentimiento de la b\u00fasqueda de autor",
        }
        receipt = egress.build_receipt(
            ledger, lane="personal", route="local", answer=content,
            consent=consent, personal_names=[exact])
        receipt["recipe"] = "author"
        meta = author_meta(exact, chosen, counts,
                           candidates_shown if candidates else prior_candidates)
        return {
            "ambiguous": bool(candidates),
            "candidates": candidates,
            "works": works,
            "counts": counts,
            "errors": errors,
            "content": content,
            "author": meta,
            "receipt": receipt,
            "request_id": rid,
        }


# A short alias for callers that prefer the module name as a verb.
author_lookup = lookup
