#!/usr/bin/env python3
"""Loopback stand-in for ORCID, OpenAlex and PubMed (v4 bank harness).

The sealed v4 bank carries fictitious author records in
``01_MATERIALES/autores/{orcid,openalex,pubmed}.json``. This server reads
those files and answers the exact requests the App's author tools make, while
the App is launched with ``--test-host-map``:

* ``pub.orcid.org``     -> ``/v3.0/expanded-search/`` and ``/v3.0/<iD>/works``
* ``api.openalex.org``  -> ``/authors`` and ``/works``
* ``eutils.ncbi.nlm.nih.gov`` -> ``/entrez/eutils/esearch.fcgi`` and
  ``/entrez/eutils/esummary.fcgi``

The declared ``Host`` header is kept by the test seam, so one server can answer
all three. Every request is logged (host, path, query terms and the exact
values sent); the harness compares that log with the card's
``Envíos permitidos``. Nothing reaches the internet. Standard library only.

    author_fake.py --data 01_MATERIALES/autores --http 0 --log calls.jsonl
"""

from __future__ import annotations

import argparse
import json
import threading
import unicodedata
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

SERVICE_HOSTS = {
    "orcid": "pub.orcid.org",
    "openalex": "api.openalex.org",
    "pubmed": "eutils.ncbi.nlm.nih.gov",
}


def fold(text: Any) -> str:
    value = unicodedata.normalize("NFKD", str(text or "").casefold())
    return "".join(ch for ch in value if not unicodedata.combining(ch)).strip()


def load_records(data_dir: Path) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for service in ("orcid", "openalex", "pubmed"):
        path = data_dir / f"{service}.json"
        if not path.is_file():
            out[service] = []
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError(f"{path}: the records must be a JSON list")
        out[service] = [item for item in raw if isinstance(item, dict)]
    return out


def works_of(person: dict[str, Any], service: str) -> list[dict[str, Any]]:
    works = [item for item in person.get("obras") or [] if isinstance(item, dict)]
    out = []
    for work in works:
        out.append({
            "title": str(work.get("titulo") or work.get("title") or ""),
            "year": work.get("anio", work.get("year")),
            "venue": str(work.get("revista") or work.get("venue") or ""),
            "doi": str(work.get("doi") or ""),
            "source": service,
        })
    return [work for work in out if work["title"]]


def same_name(left: Any, right: Any) -> bool:
    return fold(left) == fold(right)


class AuthorFake:
    def __init__(self, records: dict[str, list[dict[str, Any]]], log_path: Path | None) -> None:
        self.records = records
        self.log_path = log_path
        self._lock = threading.Lock()

    def people(self, service: str, name: str) -> list[dict[str, Any]]:
        return [person for person in self.records.get(service) or []
                if same_name(person.get("nombre"), name)]

    def add_log(self, **entry: Any) -> None:
        if self.log_path is None:
            return
        with self._lock:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # -- ORCID ---------------------------------------------------------------
    def orcid_search(self, name: str) -> dict[str, Any]:
        rows = []
        for person in self.people("orcid", name):
            given, _, family = str(person.get("nombre") or "").partition(" ")
            rows.append({
                "given-names": {"value": given},
                "family-names": {"value": family},
                "orcid-id": str(person.get("orcid") or ""),
                "institution-name": [str(person.get("afiliacion") or "")],
            })
        return {"expanded-result": rows, "num-found": len(rows)}

    def orcid_works(self, orcid: str) -> dict[str, Any]:
        person = next((item for item in self.records.get("orcid") or []
                       if str(item.get("orcid") or "").upper() == orcid.upper()), None)
        groups = []
        for work in works_of(person or {}, "orcid"):
            groups.append({"work-summary": [{
                "title": {"title": {"value": work["title"]}},
                "publication-date": {"year": {"value": str(work["year"] or "")}},
                "journal-title": {"value": work["venue"]},
                "external-ids": {"external-id": [{
                    "external-id-type": "doi",
                    "external-id-value": work["doi"],
                }]} if work["doi"] else {"external-id": []},
                "url": {"value": f"https://doi.org/{work['doi']}" if work["doi"]
                        else f"https://orcid.org/{orcid}"},
            }]})
        return {"group": groups}

    # -- OpenAlex ------------------------------------------------------------
    @staticmethod
    def openalex_id(person: dict[str, Any], index: int) -> str:
        raw = str(person.get("openalex_id") or "")
        if raw:
            return raw.rstrip("/").rsplit("/", 1)[-1]
        return f"A{index + 1:06d}"

    def openalex_authors(self, name: str) -> dict[str, Any]:
        results = []
        for index, person in enumerate(self.records.get("openalex") or []):
            if same_name(person.get("nombre"), name):
                results.append({
                    "id": f"https://openalex.org/{self.openalex_id(person, index)}",
                    "display_name": str(person.get("nombre") or ""),
                })
        return {"results": results, "count": len(results)}

    def openalex_works(self, *, author_id: str = "", orcid: str = "") -> dict[str, Any]:
        results = []
        for index, person in enumerate(self.records.get("openalex") or []):
            if author_id and self.openalex_id(person, index) != author_id:
                continue
            if orcid and str(person.get("orcid") or "").upper() != orcid.upper():
                continue
            for work in works_of(person, "openalex"):
                doi = work["doi"].removeprefix("https://doi.org/").removeprefix("http://doi.org/")
                results.append({
                    "id": f"https://openalex.org/W{index + 1:06d}",
                    "title": work["title"],
                    "publication_year": work["year"],
                    "doi": f"https://doi.org/{doi}" if doi else "",
                    "primary_location": {"source": {"display_name": work["venue"]}},
                })
        return {"results": results, "count": len(results)}

    # -- PubMed --------------------------------------------------------------
    @staticmethod
    def pmid(person_index: int, work_index: int) -> str:
        return f"9{person_index + 1:03d}{work_index + 1:03d}"

    def pubmed_people(self, term: str) -> list[tuple[int, dict[str, Any]]]:
        name = term.replace("[Author]", "").strip()
        return [(index, person) for index, person in enumerate(self.records.get("pubmed") or [])
                if same_name(person.get("nombre"), name)]

    def pubmed_search(self, term: str) -> dict[str, Any]:
        ids = []
        for index, person in self.pubmed_people(term):
            for work_index, _ in enumerate(works_of(person, "pubmed")):
                ids.append(self.pmid(index, work_index))
        return {"esearchresult": {"idlist": ids, "count": str(len(ids))}}

    def pubmed_summary(self, ids: list[str]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for index, person in enumerate(self.records.get("pubmed") or []):
            for work_index, work in enumerate(works_of(person, "pubmed")):
                key = self.pmid(index, work_index)
                if key not in ids:
                    continue
                result[key] = {
                    "title": work["title"] + ".",
                    "pubdate": str(work["year"] or ""),
                    "fulljournalname": work["venue"],
                    "source": work["venue"],
                    "articleids": ([{"idtype": "doi", "value": work["doi"]}]
                                   if work["doi"] else []),
                }
        result["uids"] = list(ids)
        return {"result": result}


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    fake: AuthorFake

    def log_message(self, *args: Any) -> None:      # silent
        return

    def _json(self, status: int, body: Any) -> None:
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:                       # noqa: N802
        parsed = urllib.parse.urlsplit(self.path)
        params = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
        host = (self.headers.get("Host") or "").split(":")[0].lower().rstrip(".")
        service = next((key for key, value in SERVICE_HOSTS.items() if value == host), "")
        entry = {"host": host, "service": service, "path": parsed.path,
                 "query": params, "bytes": len(parsed.path.encode())
                 + len(parsed.query.encode())}
        if not service:
            self._json(404, {"error": f"unknown test host {host!r}"})
            return
        try:
            if service == "orcid":
                self._orcid(parsed.path, params, entry)
            elif service == "openalex":
                self._openalex(params, entry)
            else:
                self._pubmed(parsed.path, params, entry)
        except Exception as exc:                    # a malformed fixture is a test error
            self._json(500, {"error": f"{type(exc).__name__}: {exc}"})

    def _orcid(self, path: str, params: dict[str, str], entry: dict[str, Any]) -> None:
        if path.rstrip("/").endswith("/expanded-search"):
            name = params.get("q", "")
            entry.update(valor=name, campo="q")
            body = self.fake.orcid_search(name)
        else:
            parts = [part for part in path.split("/") if part]
            # /v3.0/<orcid>/works
            if len(parts) >= 3 and parts[-1] == "works":
                orcid = parts[-2]
                entry.update(valor=orcid, campo="orcid")
                body = self.fake.orcid_works(orcid)
            else:
                self._json(404, {"error": "unknown ORCID path"})
                return
        self.fake.add_log(**entry)
        self._json(200, body)

    def _openalex(self, params: dict[str, str], entry: dict[str, Any]) -> None:
        path = urllib.parse.urlsplit(self.path).path.rstrip("/")
        if path.endswith("/authors"):
            name = params.get("search", "")
            entry.update(valor=name, campo="search")
            body = self.fake.openalex_authors(name)
        elif path.endswith("/works"):
            filt = params.get("filter", "")
            author_id = ""
            orcid = ""
            for part in filt.split(","):
                key, _, value = part.partition(":")
                if key.strip() == "author.id":
                    author_id = value.strip().rsplit("/", 1)[-1]
                elif key.strip() == "author.orcid":
                    orcid = value.strip().rsplit("/", 1)[-1]
            entry.update(valor=author_id or orcid, campo="filter", filtro=filt)
            body = self.fake.openalex_works(author_id=author_id, orcid=orcid)
        else:
            self._json(404, {"error": "unknown OpenAlex path"})
            return
        self.fake.add_log(**entry)
        self._json(200, body)

    def _pubmed(self, path: str, params: dict[str, str], entry: dict[str, Any]) -> None:
        if path.endswith("esearch.fcgi"):
            term = params.get("term", "")
            entry.update(valor=term, campo="term")
            body = self.fake.pubmed_search(term)
        elif path.endswith("esummary.fcgi"):
            ids = [item for item in params.get("id", "").split(",") if item]
            entry.update(valor=",".join(ids), campo="id")
            body = self.fake.pubmed_summary(ids)
        else:
            self._json(404, {"error": "unknown PubMed path"})
            return
        self.fake.add_log(**entry)
        self._json(200, body)


def serve(data_dir: Path, port: int, log_path: Path | None) -> tuple[ThreadingHTTPServer, int]:
    fake = AuthorFake(load_records(data_dir), log_path)
    handler = type("Handler", (_Handler,), {"fake": fake})
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Loopback fake of the three author services")
    ap.add_argument("--data", required=True, help="01_MATERIALES/autores")
    ap.add_argument("--http", type=int, default=0, metavar="PORT")
    ap.add_argument("--log", default="")
    ap.add_argument("--print-port", action="store_true")
    args = ap.parse_args(argv)
    server, port = serve(Path(args.data).expanduser().resolve(), args.http,
                         Path(args.log).expanduser().resolve() if args.log else None)
    if args.print_port:
        print(port, flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
