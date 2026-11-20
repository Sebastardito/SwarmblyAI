"""Author search through the broker (3.4).

The author's name is the payload. It is never stripped, lowercased or replaced:
the user approves one exact name string and the services (ORCID, OpenAlex,
PubMed), the broker binds that approval to the arguments with a one-time
token, and only then does a handler send it. Calls use the fixed
``AUTHOR_QUERY`` egress kind (never ``PUBLIC_QUERY``), so the receipt marks the
send as a personal name.

The three services are separate tools, registered only when
``tools.author.enabled`` is true:

* ``author/orcid``
* ``author/openalex``
* ``author/pubmed``

Each returns a JSON object with a normalised ``works`` list
``{title, year, venue, doi, source, url}``. ORCID first searches people; when
more than one plausible person matches it returns ``candidates`` and does not
pick one silently. An optional ORCID iD skips that search, and an optional
affiliation hint narrows candidates locally (it is not sent). Results are data:
the broker wraps their text as quoted material with a source and hash.

No network call is made by importing this module. ``_get`` from
``engine.providers`` is reused for JSON, but inside a fresh context without a
request ledger: that helper also records a *public* query, which an author
lookup must never be. The author event is recorded explicitly, once per real
send, before the request leaves.
"""

from __future__ import annotations

import contextvars
import json
import re
import unicodedata
import urllib.error
import urllib.parse
from typing import Any, Iterable

from .. import egress
from ..engine.providers import USER_AGENT, _get
from .broker import ToolBroker, ToolResult, ToolSpec

AUTHOR_SERVICES = ("orcid", "openalex", "pubmed")
AUTHOR_HOSTS = {
    "orcid": "https://pub.orcid.org",
    "openalex": "https://api.openalex.org",
    "pubmed": "https://eutils.ncbi.nlm.nih.gov",
}
AUTHOR_TIMEOUT_S = 15.0
AUTHOR_MAX_RESULTS = 25
AUTHOR_DEFAULT_RESULTS = 10
AUTHOR_RESULT_CHARS = 8000
_FIELD_CHARS = 1000

AUTHOR_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 200},
        "orcid": {"type": "string", "minLength": 1, "maxLength": 64},
        "affiliation": {"type": "string", "minLength": 1, "maxLength": 200},
        "max_results": {"type": "integer", "minimum": 1, "maximum": AUTHOR_MAX_RESULTS},
    },
    "required": ["name"],
}

_AUTHOR_DESCRIPTIONS = {
    "orcid": "Search an author's public works in ORCID. The exact approved name is sent.",
    "openalex": "Search an author's public works in OpenAlex. The exact approved name is sent.",
    "pubmed": "Search an author's publications in PubMed. The exact approved name is sent.",
}
_SPEC_IDS = {service: f"author/{service}" for service in AUTHOR_SERVICES}
_ORCID_ID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
_ORCID_URL = "https://orcid.org/"


class AuthorError(ValueError):
    """A lookup cannot be made or the service answered with an error."""


class AuthorRateLimited(AuthorError):
    """The service asked us to slow down."""


def author_enabled(config: Any) -> bool:
    """Whether ``tools.author.enabled`` is true; absent or malformed means off."""
    if not isinstance(config, dict):
        return False
    flat = config.get("tools.author.enabled")
    if flat is not None:
        return flat is True
    tools = config.get("tools")
    if not isinstance(tools, dict):
        return False
    author = tools.get("author")
    return isinstance(author, dict) and author.get("enabled") is True


def author_specs() -> list[ToolSpec]:
    """The three specs, with no registration or approval side effects."""
    return [
        ToolSpec(
            _SPEC_IDS[service], "author", AUTHOR_HOSTS[service],
            AUTHOR_INPUT_SCHEMA, _AUTHOR_DESCRIPTIONS[service],
        )
        for service in AUTHOR_SERVICES
    ]


def register_author_tools(broker: ToolBroker, config: Any, *,
                          project_id: str = "", services: Iterable[str] | None = None,
                          approve: bool | Iterable[str] = False) -> list[ToolSpec]:
    """Register the enabled author tools and optionally approve services.

    ``services`` limits what the user has chosen; the default is all three.
    ``approve=True`` records the broker approval for each registered service.
    A name is never part of registration: it is supplied, and bound to a
    one-time token, only for a concrete call.
    """
    if not author_enabled(config):
        return []
    if services is None:
        selected = list(AUTHOR_SERVICES)
    elif isinstance(services, str):
        selected = [services]
    else:
        selected = list(services)
    for service in selected:
        if service not in AUTHOR_SERVICES:
            raise ValueError(f"unknown author service {service!r}")
    if approve is True:
        approve_names = set(selected)
    elif approve:
        approve_names = {str(name) for name in approve}
    else:
        approve_names = set()

    registered: list[ToolSpec] = []
    for service in selected:
        spec = ToolSpec(
            _SPEC_IDS[service], "author", AUTHOR_HOSTS[service],
            AUTHOR_INPUT_SCHEMA, _AUTHOR_DESCRIPTIONS[service],
        )
        broker.register(spec, _handler(service))
        if service in approve_names:
            broker.approve(spec.id, project_id)
        registered.append(spec)
    return registered


def _handler(service: str):
    def run(call, ctx):
        name = _name(call.arguments)
        if service == "orcid":
            return _search_orcid(name, call.arguments, ctx)
        if service == "openalex":
            return _search_openalex(name, call.arguments, ctx)
        return _search_pubmed(name, call.arguments, ctx)
    return run


def _name(arguments: dict[str, Any]) -> str:
    name = arguments.get("name")
    if not isinstance(name, str) or not name.strip():
        raise AuthorError("name is required")
    # Exact payload: no strip, no case folding, no punctuation removal.
    return name


def _max_results(arguments: dict[str, Any]) -> int:
    value = arguments.get("max_results", AUTHOR_DEFAULT_RESULTS)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= AUTHOR_MAX_RESULTS:
        raise AuthorError(f"max_results must be an integer from 1 to {AUTHOR_MAX_RESULTS}")
    return value


def _quiet_get(url: str, timeout: float = AUTHOR_TIMEOUT_S) -> Any:
    """Call the existing provider helper without a ledger in this context.

    ``providers._get`` records a public query. An author name must never be a
    public query, so the call runs with an empty ``Context``: the helper still
    fetches and parses exactly as before, but nothing is recorded as
    ``PUBLIC_QUERY``. The author event is recorded explicitly before this.
    """
    return contextvars.Context().run(_get, url, timeout, USER_AGENT)


def _author_get(ctx: Any, service: str, name: str, url: str, *,
                personal_name: bool, timeout: float = AUTHOR_TIMEOUT_S) -> Any:
    # ``valor`` is the name only when the name itself is in the query; a
    # works-by-ORCID request carries an iD, not the text. The ledger still
    # marks every send of an author lookup with ``personal_name=True``: the
    # receipt says this call is about a person, and its bytes are the real
    # path+query bytes of the request, not just the name's length.
    valor = name if personal_name else ""
    parts = urllib.parse.urlsplit(url)
    nbytes = (len((parts.path or "").encode("utf-8"))
              + len((parts.query or "").encode("utf-8")))
    # Mark the attempt before the policy check, as ToolContext._send does:
    # a denied check already records its blocked event, and the broker's
    # finally block must not add a second, non-blocked zero-byte one.
    ctx.attempted = True
    try:
        egress.check_call(
            url, nbytes, reason=f"author search ({service})",
            kind=egress.AUTHOR_QUERY, spec_id=ctx.spec.id,
            aprobado_por=ctx.approved_by, valor=valor,
            personal_name=True,
        )
    except egress.EgressDenied:
        raise
    try:
        return _quiet_get(url, timeout)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise AuthorRateLimited(
                f"{service} rate limit (HTTP 429); try again later") from None
        if exc.code in (500, 502, 503, 504):
            raise AuthorError(
                f"{service} is temporarily unavailable (HTTP {exc.code}); try later") from None
        raise AuthorError(f"{service} returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AuthorError(f"{service} is unreachable: {exc}") from None
    except ValueError as exc:
        raise AuthorError(f"{service} returned an unreadable response: {exc}") from None


def _fold(text: Any) -> str:
    value = unicodedata.normalize("NFKD", str(text or "").casefold())
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def _clean(value: Any, limit: int = _FIELD_CHARS) -> str:
    if value is None:
        return ""
    text = str(value).replace("\x00", "").strip()
    return text[:limit]


def _clean_doi(value: Any) -> str:
    text = _clean(value, 500)
    low = text.lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/",
                   "http://dx.doi.org/", "doi:"):
        if low.startswith(prefix):
            text = text[len(prefix):]
            break
    return text.strip().rstrip(".").strip()


def _title_key(title: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", _fold(title)))


def _year(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if 1 <= value <= 9999 else None
    match = re.search(r"\b(\d{4})\b", str(value))
    return int(match.group(1)) if match else None


def normalise_works(works: Iterable[Any]) -> list[dict[str, Any]]:
    """Normalise and deduplicate by DOI first, then by normalised title."""
    out: list[dict[str, Any]] = []
    seen_dois: set[str] = set()
    seen_titles: set[str] = set()
    for raw in works:
        if not isinstance(raw, dict):
            continue
        title = _clean(raw.get("title"))
        if not title:
            continue
        doi = _clean_doi(raw.get("doi"))
        title_key = _title_key(title)
        if not title_key:
            continue
        doi_key = doi.casefold()
        if doi_key and doi_key in seen_dois:
            continue
        if title_key in seen_titles:
            continue
        if doi_key:
            seen_dois.add(doi_key)
        seen_titles.add(title_key)
        out.append({
            "title": title,
            "year": _year(raw.get("year")),
            "venue": _clean(raw.get("venue")),
            "doi": doi,
            "source": _clean(raw.get("source"), 32),
            "url": _clean(raw.get("url")),
        })
    return out


# Historical name some code may naturally use.
dedupe_works = normalise_works


def _json_result(ctx: Any, payload: dict[str, Any]) -> ToolResult:
    def encode(value: dict[str, Any]) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)

    text = encode(payload)
    truncated = False
    if len(text) > AUTHOR_RESULT_CHARS:
        # Keep the text valid JSON: shrink the result lists instead of cutting
        # a string in the middle. The broker still applies its own quoted cap.
        payload = dict(payload)
        for key in ("works", "candidates"):
            items = list(payload.get(key) or [])
            while items and len(text) > AUTHOR_RESULT_CHARS:
                items = items[:-1]
                payload[key] = items
                text = encode(payload)
        if len(text) > AUTHOR_RESULT_CHARS:
            payload = {"service": payload.get("service", ""), "ambiguous":
                       bool(payload.get("ambiguous")), "candidates": [], "works": []}
            text = encode(payload)
        truncated = True
    return ToolResult(
        spec_id=ctx.spec.id, ok=True, content=text, data=payload, truncated=truncated,
    )


def _works_result(service: str, works: list[dict[str, Any]], *,
                  candidates: list[dict[str, str]] | None = None,
                  ambiguous: bool = False) -> dict[str, Any]:
    return {
        "service": service,
        "ambiguous": bool(ambiguous),
        "candidates": list(candidates or []),
        "works": works,
    }


def _normalise_orcid(value: Any) -> str:
    if value is None or value == "":
        return ""
    raw = _clean(value, 100)
    low = raw.lower()
    if "orcid.org/" in low:
        raw = raw.rsplit("/", 1)[-1]
    raw = raw.strip().upper()
    if not _ORCID_ID_RE.fullmatch(raw):
        raise AuthorError(f"invalid ORCID iD {value!r}")
    return raw


def _orcid_candidates(data: Any) -> list[dict[str, str]]:
    rows = (data or {}).get("expanded-result") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        rows = []
    out: list[dict[str, str]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        given = _orcid_value(row.get("given-names"))
        family = _orcid_value(row.get("family-names"))
        name = " ".join(part for part in (given, family) if part).strip()
        if not name:
            name = _clean(row.get("name"), 200)
        orcid = _orcid_value(row.get("orcid-id") or row.get("orcid") or row.get("id"))
        if "orcid.org/" in orcid.lower():
            orcid = orcid.rsplit("/", 1)[-1]
        institutions = row.get("institution-name") or []
        if isinstance(institutions, str):
            institutions = [institutions]
        affiliation = "; ".join(
            dict.fromkeys(_clean(_orcid_value(item), 200) for item in institutions
                          if _clean(_orcid_value(item), 200))
        )
        if name or orcid:
            out.append({"name": name, "orcid": orcid.strip().upper(),
                        "affiliation": affiliation})
    return out[:AUTHOR_MAX_RESULTS]


def _orcid_value(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("value") or value.get("content") or ""
    return _clean(value, 300)


def _search_orcid(name: str, arguments: dict[str, Any], ctx: Any) -> ToolResult:
    max_results = _max_results(arguments)
    orcid = _normalise_orcid(arguments.get("orcid"))
    if orcid:
        works = _orcid_works(orcid, name, ctx, max_results)
        return _json_result(ctx, _works_result("orcid", works))

    url = "https://pub.orcid.org/v3.0/expanded-search/?" + urllib.parse.urlencode(
        {"q": name, "rows": str(AUTHOR_MAX_RESULTS)})
    data = _author_get(ctx, "orcid", name, url, personal_name=True)
    candidates = _orcid_candidates(data)
    affiliation = _clean(arguments.get("affiliation"), 200)
    if affiliation and len(candidates) > 1:
        needle = _fold(affiliation)
        matching = [item for item in candidates if needle and needle in _fold(item["affiliation"])]
        if matching:
            candidates = matching
    if len(candidates) > 1:
        return _json_result(ctx, _works_result(
            "orcid", [], candidates=candidates[:max(max_results, 2)], ambiguous=True))
    if not candidates:
        return _json_result(ctx, _works_result("orcid", []))
    works = _orcid_works(candidates[0]["orcid"], name, ctx, max_results)
    return _json_result(ctx, _works_result("orcid", works))


def _orcid_works(orcid: str, name: str, ctx: Any, max_results: int) -> list[dict[str, Any]]:
    url = f"https://pub.orcid.org/v3.0/{orcid}/works"
    data = _author_get(ctx, "orcid", name, url, personal_name=False)
    works: list[dict[str, Any]] = []
    groups = (data or {}).get("group") if isinstance(data, dict) else None
    for group in groups if isinstance(groups, list) else []:
        summaries = group.get("work-summary") if isinstance(group, dict) else None
        if not isinstance(summaries, list) or not summaries:
            continue
        summary = summaries[0]
        if not isinstance(summary, dict):
            continue
        title = _nested(summary, "title", "title", "value")
        if not title:
            continue
        doi = ""
        external = (summary.get("external-ids") or {}).get("external-id") or []
        for item in external if isinstance(external, list) else []:
            if not isinstance(item, dict):
                continue
            if _fold(item.get("external-id-type")) == "doi":
                doi = _clean(item.get("external-id-value"), 500)
                break
        url_value = _nested(summary, "url", "value") or (
            f"https://doi.org/{doi}" if doi else f"{_ORCID_URL}{orcid}")
        works.append({
            "title": _clean(title),
            "year": _nested(summary, "publication-date", "year", "value"),
            "venue": _nested(summary, "journal-title", "value"),
            "doi": _clean_doi(doi),
            "source": "orcid",
            "url": _clean(url_value),
        })
        if len(works) >= max_results:
            break
    return normalise_works(works)


def _nested(node: Any, *keys: str) -> str:
    current = node
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return _clean(current)


def _openalex_id(value: Any) -> str:
    text = _clean(value, 300)
    if not text:
        return ""
    return text.rstrip("/").rsplit("/", 1)[-1]


def _search_openalex(name: str, arguments: dict[str, Any], ctx: Any) -> ToolResult:
    max_results = _max_results(arguments)
    orcid = _normalise_orcid(arguments.get("orcid"))
    if orcid:
        query = {"filter": f"author.orcid:{orcid}", "per-page": str(max_results),
                 "sort": "publication_year:desc"}
        data = _author_get(
            ctx, "openalex", name,
            "https://api.openalex.org/works?" + urllib.parse.urlencode(query),
            personal_name=True)
        return _json_result(ctx, _works_result(
            "openalex", _openalex_works(data, max_results)))

    authors_url = "https://api.openalex.org/authors?" + urllib.parse.urlencode(
        {"search": name, "per-page": "5"})
    authors = _author_get(ctx, "openalex", name, authors_url, personal_name=True)
    results = (authors or {}).get("results") if isinstance(authors, dict) else None
    if not isinstance(results, list) or not results:
        return _json_result(ctx, _works_result("openalex", []))
    chosen = next((item for item in results
                   if _fold(item.get("display_name")) == _fold(name)), results[0])
    author_id = _openalex_id(chosen.get("id") if isinstance(chosen, dict) else "")
    if not author_id:
        return _json_result(ctx, _works_result("openalex", []))
    works_url = "https://api.openalex.org/works?" + urllib.parse.urlencode(
        {"filter": f"author.id:{author_id}", "per-page": str(max_results),
         "sort": "publication_year:desc"})
    data = _author_get(ctx, "openalex", name, works_url, personal_name=False)
    return _json_result(ctx, _works_result(
        "openalex", _openalex_works(data, max_results)))


def _openalex_works(data: Any, max_results: int) -> list[dict[str, Any]]:
    results = (data or {}).get("results") if isinstance(data, dict) else None
    works: list[dict[str, Any]] = []
    for item in results if isinstance(results, list) else []:
        if not isinstance(item, dict):
            continue
        title = _clean(item.get("title") or item.get("display_name"))
        if not title:
            continue
        doi = _clean_doi(item.get("doi"))
        location = item.get("primary_location") or {}
        source = (location.get("source") or {}) if isinstance(location, dict) else {}
        venue = _clean(source.get("display_name") if isinstance(source, dict) else "")
        url = f"https://doi.org/{doi}" if doi else _clean(item.get("id"))
        works.append({
            "title": title,
            "year": _year(item.get("publication_year")),
            "venue": venue,
            "doi": doi,
            "source": "openalex",
            "url": url,
        })
        if len(works) >= max_results:
            break
    return normalise_works(works)


def _search_pubmed(name: str, arguments: dict[str, Any], ctx: Any) -> ToolResult:
    max_results = _max_results(arguments)
    term = f"{name}[Author]"
    esearch_url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"
        + urllib.parse.urlencode({
            "db": "pubmed", "term": term, "retmode": "json",
            "retmax": str(max_results), "sort": "relevance", "tool": "SwarmblyApp",
        })
    )
    search = _author_get(ctx, "pubmed", name, esearch_url, personal_name=True)
    ids = (((search or {}).get("esearchresult") or {}).get("idlist") or []) \
        if isinstance(search, dict) else []
    if not isinstance(ids, list) or not ids:
        return _json_result(ctx, _works_result("pubmed", []))
    summary_url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?"
        + urllib.parse.urlencode({
            "db": "pubmed", "id": ",".join(str(item) for item in ids),
            "retmode": "json", "tool": "SwarmblyApp",
        })
    )
    data = _author_get(ctx, "pubmed", name, summary_url, personal_name=False)
    works: list[dict[str, Any]] = []
    result = (data or {}).get("result") if isinstance(data, dict) else None
    for pmid in ids:
        row = (result or {}).get(str(pmid)) if isinstance(result, dict) else None
        if not isinstance(row, dict):
            continue
        title = _clean(row.get("title"))
        if not title:
            continue
        doi = ""
        for item in row.get("articleids") or []:
            if isinstance(item, dict) and _fold(item.get("idtype")) == "doi":
                doi = _clean(item.get("value"), 500)
                break
        works.append({
            "title": title.rstrip("."),
            "year": _year(row.get("pubdate")),
            "venue": _clean(row.get("fulljournalname") or row.get("source")),
            "doi": _clean_doi(doi),
            "source": "pubmed",
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })
        if len(works) >= max_results:
            break
    return _json_result(ctx, _works_result("pubmed", normalise_works(works)))
