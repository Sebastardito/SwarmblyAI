"""Tests of the two loopback servers the v4 harness starts (no App needed)."""

from __future__ import annotations

import importlib.util
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mcp_srv = _load("mcp_catalog_server", ROOT / "bench" / "mcp_catalog_server.py")
author_fake = _load("author_fake", ROOT / "bench" / "author_fake.py")


def _post(port: int, body: dict, path: str = "/") -> tuple[dict, dict]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode(),
        method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode()), dict(response.headers)


def test_mcp_catalog_server_http_manifest_call_and_change(tmp_path):
    catalog = tmp_path / "meteo.json"
    catalog.write_text(json.dumps({
        "servidor": "meteo", "tipo": "remoto", "host": "api.meteo.test",
        "herramientas": [{
            "nombre": "lluvia", "descripcion": "Lluvia",
            "esquema": {"type": "object",
                        "properties": {"mes": {"type": "string"}},
                        "required": ["mes"]},
            "respuestas": [{"si": {"mes": "2025-03"}, "texto": "142 mm"},
                           {"por_defecto": "sin datos"}],
        }]}), encoding="utf-8")
    changed = tmp_path / "meteo.cambio.json"
    changed.write_text(json.dumps({
        "servidor": "meteo", "tipo": "remoto", "host": "api.meteo.test",
        "herramientas": [
            {"nombre": "lluvia", "descripcion": "Lluvia",
             "esquema": {"type": "object",
                         "properties": {"mes": {"type": "string"}},
                         "required": ["mes"]},
             "respuestas": [{"si": {"mes": "2025-03"}, "texto": "142 mm"}]},
            {"nombre": "exportar", "descripcion": "Exporta",
             "esquema": {"type": "object", "properties": {}},
             "respuestas": [{"por_defecto": "ok"}]},
        ]}), encoding="utf-8")
    server, port = mcp_srv.serve_http(
        mcp_srv.Catalogue(catalog, changed), mcp_srv.CallLog(None), 0)
    try:
        init, headers = _post(port, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                     "params": {"protocolVersion": "2025-06-18"}})
        assert init["result"]["capabilities"]["tools"]["listChanged"]
        assert headers.get("Mcp-Session-Id")
        listed, _ = _post(port, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert [tool["name"] for tool in listed["result"]["tools"]] == ["lluvia"]
        called, _ = _post(port, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                 "params": {"name": "lluvia",
                                            "arguments": {"mes": "2025-03"}}})
        assert called["result"]["content"][0]["text"] == "142 mm"
        changed_body, _ = _post(port, {}, path="/__control/change")
        assert changed_body["changed"] is True
        listed, _ = _post(port, {"jsonrpc": "2.0", "id": 4, "method": "tools/list"})
        assert [tool["name"] for tool in listed["result"]["tools"]] == ["lluvia", "exportar"]
    finally:
        server.shutdown()


def _get(port: int, path: str, host: str) -> dict:
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                     headers={"Host": host})
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode())


def test_author_fake_serves_the_three_protocols(tmp_path):
    (tmp_path / "orcid.json").write_text(json.dumps([{
        "nombre": "Tomás Aravena", "orcid": "0000-0000-0000-0101",
        "afiliacion": "El Roble", "obras": [
            {"titulo": "Caudal base", "anio": 2024, "revista": "Revista",
             "doi": "10.0000/fict.2024.1"}]}]), encoding="utf-8")
    (tmp_path / "openalex.json").write_text(json.dumps([{
        "nombre": "Tomás Aravena", "openalex_id": "A1", "obras": [
            {"titulo": "Caudal base", "anio": 2024, "revista": "Revista",
             "doi": "10.0000/fict.2024.1"}]}]), encoding="utf-8")
    (tmp_path / "pubmed.json").write_text(json.dumps([{
        "nombre": "Tomás Aravena", "obras": [
            {"titulo": "Sensores", "anio": 2023, "revista": "Cuadernos",
             "doi": "10.0000/fict.2023.1"}]}]), encoding="utf-8")
    server, port = author_fake.serve(tmp_path, 0, None)
    try:
        orcid = _get(port, "/v3.0/expanded-search/?q=Tom%C3%A1s+Aravena",
                     "pub.orcid.org")
        assert orcid["expanded-result"][0]["orcid-id"] == "0000-0000-0000-0101"
        works = _get(port, "/v3.0/0000-0000-0000-0101/works", "pub.orcid.org")
        assert works["group"][0]["work-summary"][0]["title"]["title"]["value"] == "Caudal base"
        authors = _get(port, "/authors?search=Tom%C3%A1s+Aravena",
                       "api.openalex.org")
        assert authors["results"][0]["display_name"] == "Tomás Aravena"
        openalex = _get(port, "/works?filter=author.id:A1", "api.openalex.org")
        assert openalex["results"][0]["title"] == "Caudal base"
        search = _get(port, "/entrez/eutils/esearch.fcgi?db=pubmed&"
                            "term=Tom%C3%A1s+Aravena%5BAuthor%5D",
                      "eutils.ncbi.nlm.nih.gov")
        ids = search["esearchresult"]["idlist"]
        assert ids
        summary = _get(port, f"/entrez/eutils/esummary.fcgi?db=pubmed&id={ids[0]}",
                       "eutils.ncbi.nlm.nih.gov")
        assert summary["result"][ids[0]]["title"] == "Sensores."
    finally:
        server.shutdown()
