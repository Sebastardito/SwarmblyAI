"""Tests of the blind benchmark harness (bench/run_bank.py) on a tiny fictitious bank."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MINI = ROOT / "tests" / "fixtures" / "bench_mini"
_spec = importlib.util.spec_from_file_location("run_bank", ROOT / "bench" / "run_bank.py")
rb = importlib.util.module_from_spec(_spec)
sys.modules["run_bank"] = rb
_spec.loader.exec_module(rb)


def test_detects_bank_and_verifies_seal():
    bank = rb.detect_bank(MINI)
    assert bank.kind == "v2"
    seal = rb.verify_seal(bank)
    assert seal["ok"] and seal["archivos_ok"] == 4 and not seal["fallos"]


def test_broken_seal_is_detected(tmp_path):
    copy = tmp_path / "bank"
    shutil.copytree(MINI, copy)
    target = copy / "01_MATERIALES" / "corpus_reservado" / "nota_2025.md"
    target.write_text(target.read_text(encoding="utf-8") + "\nedit\n", encoding="utf-8")
    seal = rb.verify_seal(rb.detect_bank(copy))
    assert not seal["ok"]
    assert seal["fallos"][0]["archivo"].endswith("nota_2025.md")


def test_parses_only_id_question_and_documents():
    cases = rb.parse_cases(MINI / "02_CASOS_RESERVADOS" / "S2_S3_reservados.md")
    assert [c.case_id for c in cases] == ["S2-01", "S3-01"]
    assert cases[0].question == "¿Desde cuándo soy coordinadora de calidad de datos?"
    assert cases[0].documents == ["cv_ana_perez.md"]
    assert "agosto" not in cases[0].question          # the key is never part of the question


def test_public_snapshot_is_served_not_loaded_as_a_source():
    bank = rb.detect_bank(MINI)
    case = rb.parse_cases(bank.cases_file)[1]
    user, public = rb.case_documents(bank, case)
    assert {p.name for p in user} == {"cv_ana_perez.md", "nota_2025.md"}
    assert [p.name for p in public] == ["Registro_Orestias_ficticia_2024.md"]


def test_payload_classification():
    corpus = (MINI / "01_MATERIALES" / "corpus_reservado" / "cv_ana_perez.md").read_text(encoding="utf-8")
    passages = rb.shingles(corpus)
    persona = ["Ana", "Pérez", "Rojas"]
    assert rb.classify_payload("Orestias ficticia estado", passages, persona) == "entidad_publica"
    assert rb.classify_payload("Ana Pérez Rojas AcmeLabs", passages, persona) == "nombre_personal"
    leak = "Coordinadora de Calidad de Datos en AcmeLabs, desde agosto de 2022"
    assert rb.classify_payload(leak, passages, persona) == "pasaje"


def test_proxy_refuses_and_records():
    proxy = rb.EgressProxy()
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy.url}))
        with pytest.raises(urllib.error.HTTPError):
            opener.open("http://example.org/search?q=Ana+P%C3%A9rez", timeout=5)
        events = proxy.log.drain()
        assert events and events[0]["destino"] == "example.org"
        assert "q=Ana" in events[0]["consulta"]
    finally:
        proxy.close()


def test_registry_answers_with_snapshot_and_records_query():
    registry = rb.PublicRegistry()
    try:
        registry.fixtures = [MINI / "01_MATERIALES" / "fixtures_publicos" / "Registro_Orestias_ficticia_2024.md"]
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(registry.url + "/search?q=Orestias+ficticia&format=json", timeout=5) as resp:
            body = resp.read().decode("utf-8")
        assert "En Peligro" in body
        events = registry.log.drain()
        assert events[0]["q"] == "Orestias ficticia" and events[0]["resultados"] == 1
    finally:
        registry.close()


def test_receipt_counts_sends_and_blocked_attempts():
    passages = rb.shingles((MINI / "01_MATERIALES" / "corpus_reservado" / "nota_2025.md").read_text(encoding="utf-8"))
    receipt = rb.build_receipt(
        "S3-01", "respuesta", {"executed": "local"},
        [{"q": "Orestias ficticia", "bytes": 17}],
        [{"metodo": "CONNECT", "destino": "www.wikidata.org", "puerto": 443}],
        passages, ["Ana", "Pérez"])
    assert receipt["schema"] == "swarmbly.privacy_receipt/1.0"
    assert receipt["ruta"] == "local+consulta_publica"
    assert receipt["bytes_salientes"] == 17 and receipt["pasajes_enviados"] == 0
    assert receipt["intentos_bloqueados"][0]["salio"] is False


def test_v1_bank_uses_listed_fixtures_and_serves_the_public_one(tmp_path):
    root = tmp_path / "v1"
    (root / "fixtures").mkdir(parents=True)
    (root / "reserved").mkdir()
    (root / "fixtures" / "01_cv_ana.md").write_text("# CV\n", encoding="utf-8")
    (root / "fixtures" / "02_nota.md").write_text("# Nota\n", encoding="utf-8")
    (root / "fixtures" / "07_registro_publico_simulado.md").write_text("# Registro\n", encoding="utf-8")
    (root / "reserved" / "runner_pack.md").write_text(
        "```text\nID:            S3-02\nPregunta:      Compara.\nDocumentos:    F02, F07\n```\n",
        encoding="utf-8")
    lines = [f"{rb.sha256_file(p)}  {p.relative_to(root).as_posix()}"
             for p in sorted(root.rglob("*.md"))]
    (root / "SEALED_MANIFEST.sha256").write_text("Swarmbly bank v1\n" + "\n".join(lines) + "\n",
                                                 encoding="utf-8")
    bank = rb.detect_bank(root)
    assert bank.kind == "v1" and rb.verify_seal(bank)["ok"]
    case = rb.parse_cases(bank.cases_file)[0]
    user, public = rb.case_documents(bank, case)
    assert [p.name for p in user] == ["02_nota.md"]
    assert [p.name for p in public] == ["07_registro_publico_simulado.md"]


def test_v1_receipt_rows_and_regeneration(tmp_path):
    rows = rb.build_receipt_v1(
        "S3-02", [{"q": "Orestias ficticia estado", "resultados": 1, "t": "2026-11-07T00:00:00Z"}],
        [{"metodo": "CONNECT", "destino": "www.wikidata.org", "puerto": 443}],
        ["07_registro_publico_simulado.md"])
    assert rows["events"] == 2
    first, second = rows["rows"]
    assert first["destination_class"] == "simulated-public-registry"
    assert first["payload_terms"] == ["Orestias", "ficticia", "estado"]
    assert first["response_fixture"] == "F07" and len(first["payload_sha256"]) == 64
    assert second["approved"] is False and second["destination_class"].startswith("blocked-external")
    assert rb.build_receipt_v1("S2-01", [], [], [])["rows"] == []
    run = tmp_path / "run"
    (run / "casos").mkdir(parents=True)
    (run / "logs").mkdir()
    (run / "casos" / "S2-01.json").write_text('{"caso": "S2-01", "fixtures_publicos": []}', encoding="utf-8")
    (run / "logs" / "red.jsonl").write_text("", encoding="utf-8")
    assert rb.main(["--regenerate-receipts", str(run)]) == 0
    assert (run / "casos" / "S2-01_recibo_v1.json").is_file()


def test_app_receipt_is_compared_on_queries_only():
    app = {"envios": [{"tipo": "entidad_publica", "valor": "Orestias ficticia"},
                      {"tipo": "pregunta", "valor": "(pregunta)", "destino": "127.0.0.1"}],
           "pasajes_enviados": 0}
    observed = {"envios": [{"valor": "Orestias ficticia"}], "pasajes_enviados": 0}
    out = rb.compare_app_receipt(app, observed)
    assert out["coincide"] and out["consultas_app"] == ["Orestias ficticia"]
    observed["envios"].append({"valor": "Orestias ficticia estado"})
    assert not rb.compare_app_receipt(app, observed)["coincide"]


def test_bank_v3_card_fields_say_how_the_question_is_asked(tmp_path):
    cards = tmp_path / "S2_S3_reservados.md"
    cards.write_text("""
```text
ID:            S3-02
Pregunta:      Compara el rendimiento de mi lote con lo que dicen las
               fuentes públicas sobre la variedad Zafira.
Documentos:    informe.md, 01_MATERIALES/fixtures_publicos/Registro_publico.md
Receta:        investigar
Consulta aprobada: propuesta
```

```text
ID:            S2-09
Pregunta:      ¿Cuándo se cosecha el lote B7?
Turno 2:       ¿Y eso cambió después?
Turno 3:       Dímelo en una frase.
Documentos:    acta.md
Permiso público: no
```
""", encoding="utf-8")
    research, follow = rb.parse_cases(cards)
    assert research.recipe == "research" and research.approved_query == "propuesta"
    assert research.question.endswith("variedad Zafira.") and not research.follow_ups
    assert follow.follow_ups == ["¿Y eso cambió después?", "Dímelo en una frase."]
    assert follow.recipe == "" and follow.allow_public is False


def _bank_v2(tmp_path, cards: str, legend: str = ""):
    root = tmp_path / "banco"
    corpus = root / "01_MATERIALES" / "corpus_reservado"
    fixtures = root / "01_MATERIALES" / "fixtures_publicos"
    cases = root / "02_CASOS_RESERVADOS"
    for d in (corpus, fixtures, cases, root / "05_SELLO"):
        d.mkdir(parents=True)
    (corpus / "apuntes sueltos marzo.md").write_text("# Apuntes\n", encoding="utf-8")
    (corpus / "informe_2024.md").write_text("# Informe\n", encoding="utf-8")
    (fixtures / "Registro_variedad_Lumbre_2025.md").write_text("# Registro\n", encoding="utf-8")
    (fixtures / "Ficha_especie_2025.md").write_text("# Ficha\n", encoding="utf-8")
    (cases / "S2_S3_reservados.md").write_text(cards, encoding="utf-8")
    if legend:
        (cases / "LEYENDA_DOCUMENTOS.md").write_text(legend, encoding="utf-8")
    (root / "05_SELLO" / "SELLO.sha256").write_text("", encoding="utf-8")
    return rb.detect_bank(root)


def test_documents_with_spaces_and_codes_resolve(tmp_path):
    bank = _bank_v2(tmp_path, """
```text
ID:            S2-01
Pregunta:      ¿Cuántos nidos?
Documentos:    apuntes sueltos marzo.md
```

```text
ID:            S3-04
Pregunta:      Compara con lo público.
Documentos:    D2, fixtures_publicos/W1
```

```text
ID:            S3-05
Pregunta:      ¿Y la especie?
Documentos:    D2, W7
```
""", "| Código | Archivo |\n|---|---|\n| D1 | apuntes sueltos marzo.md |\n| D2 | informe_2024.md |\n"
         "| W1 | Registro_variedad_Lumbre_2025.md |\n")
    spaces, codes, unknown = rb.parse_cases(bank.cases_file)
    legend = rb.bank_legend(bank)
    assert sorted(legend) == ["D1", "D2", "W1"]
    assert rb.unresolved_documents(bank, spaces, legend) == []
    user, public = rb.case_documents(bank, codes)
    assert len(user) == 2 and [p.name for p in public] == ["Registro_variedad_Lumbre_2025.md"]
    assert rb.unresolved_documents(bank, codes, legend) == []
    assert rb.case_documents(bank, unknown)[1] == []
    assert rb.unresolved_documents(bank, unknown, legend) == ["W7"]


def test_the_record_names_the_components_measured(tmp_path):
    (tmp_path / "components.lock").write_text(json.dumps({"components": {
        "SwarmblyApp": {"version": "0.5.0", "commit": "b149a776f7fe0000"},
        "SwarmblyCore": {"version": "0.1.0", "source": "in-tree"}}}), encoding="utf-8")
    assert rb.component_commits(tmp_path) == "SwarmblyApp 0.5.0 b149a776f7fe · SwarmblyCore 0.1.0 in-tree"
    assert rb.component_commits(tmp_path / "nada") == "desconocido"


# --------------------------------------------------------------------------------------
# Harness 1.3: v4 cards, allowed sends, exact numbers, the user's decisions
# --------------------------------------------------------------------------------------
def _bank_v4(tmp_path: Path) -> Path:
    root = tmp_path / "banco_v4"
    materials = root / "01_MATERIALES"
    for folder in (materials / "corpus_reservado", materials / "fixtures_publicos",
                   materials / "mcp", materials / "autores", materials / "skills" / "demo",
                   root / "02_CASOS_RESERVADOS", root / "03_REFERENCIA",
                   root / "05_SELLO"):
        folder.mkdir(parents=True, exist_ok=True)
    (materials / "corpus_reservado" / "datos.csv").write_text(
        "fecha,estacion,caudal_m3s\n2025-04-01,Quilén Alto,4.1\n", encoding="utf-8")
    (materials / "corpus_reservado" / "informe.md").write_text(
        "# Informe\n\nEl caudal es 4,1 m³/s.\n", encoding="utf-8")
    (materials / "fixtures_publicos" / "Red_publica.md").write_text(
        "# Red\n\nrío Quilén, caudal, 10,4 m³/s.\n", encoding="utf-8")
    (materials / "mcp" / "planillas.json").write_text(json.dumps({
        "servidor": "planillas", "tipo": "local",
        "herramientas": [{"nombre": "buscar_estacion",
                          "descripcion": "Ficha",
                          "esquema": {"type": "object",
                                      "properties": {"nombre": {"type": "string"}},
                                      "required": ["nombre"]},
                          "respuestas": [{"por_defecto": "ficha"}]}]}),
        encoding="utf-8")
    for service in ("orcid", "openalex", "pubmed"):
        (materials / "autores" / f"{service}.json").write_text("[]", encoding="utf-8")
    (materials / "skills" / "demo" / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo.\n---\n\nDemo.\n", encoding="utf-8")
    script = root / "03_REFERENCIA" / "EJ4-07.py"
    script.write_text("print(4.1)\n", encoding="utf-8")
    cards = """\
```text
ID:            EJ4-07
Nivel:         N7
Capacidades:   código, código-exacto
Pregunta:      ¿Cuál es el caudal?
Receta:        código
Archivos:      datos.csv
Script:        aprobar
Resultado exacto: 4,1 m³/s (03_REFERENCIA/EJ4-07.py)
Tolerancia:    ±0,01
Envíos permitidos: ninguno
Comprobaciones:
  - nada corre antes de aprobar el script
  - el recibo no tiene envíos
Datos clave:   4,1
```

```text
ID:            EJ4-14
Nivel:         N8
Capacidades:   lista
Pregunta:      Para cada código, dime el nombre.
Receta:        lista
Lista:
<<<
QA
QM
>>>
Dónde:         este equipo
Documentos:    informe.md
Envíos permitidos: ninguno
```

```text
ID:            EJ4-24
Nivel:         N9
Capacidades:   autor
Pregunta:      Busca las publicaciones.
Autor:         Tomás Aravena
Servicios:     orcid, openalex
Decisión autor: ejecutar; elegir «0000-0000-0000-0101»
Envíos permitidos: ORCID y OpenAlex: exactamente «Tomás Aravena»
```

```text
ID:            EJ4-19
Nivel:         N9
Capacidades:   mcp-local
Pregunta:      Busca la ficha.
Usar herramientas: sí
Servidores:    planillas
Aprobadas en Ajustes: buscar_estacion
Decisiones:    ejecutar y no volver a preguntar
Envíos permitidos: ninguno
```
"""
    (root / "02_CASOS_RESERVADOS" / "S2_S3_S4_reservados.md").write_text(
        cards, encoding="utf-8")
    (root / "05_SELLO" / "SELLO.sha256").write_text(
        f"{rb.sha256_file(script)}  03_REFERENCIA/EJ4-07.py\n", encoding="utf-8")
    return root


def test_v4_cases_file_and_new_fields(tmp_path):
    bank = rb.detect_bank(_bank_v4(tmp_path))
    assert bank.kind == "v4"
    cases = rb.parse_cases(bank.cases_file)
    assert [case.case_id for case in cases] == ["EJ4-07", "EJ4-14", "EJ4-24", "EJ4-19"]
    code, listing, author, tools = cases
    assert code.level == "N7" and code.code_script == "aprobar"
    assert code.code_files == ["datos.csv"]
    assert code.tolerance == "±0,01"
    assert listing.list_items == ["QA", "QM"] and listing.list_where == "este equipo"
    assert author.author == "Tomás Aravena" and author.services == ["orcid", "openalex"]
    assert tools.use_tools and tools.servers == ["planillas"]
    assert tools.approved_tools == ["buscar_estacion"]
    assert rb.expected_numbers(code.exact_result) == [4.1]


def test_v4_check_validates_fields_and_references(tmp_path, capsys):
    bank = rb.detect_bank(_bank_v4(tmp_path))
    cases = rb.parse_cases(bank.cases_file)
    assert rb.check_bank(bank, cases) == 0
    out = capsys.readouterr().out
    assert "EJ4-07" in out and "TOTAL fichas 4" in out
    assert "¿Cuál es el caudal?" not in out          # never content


def test_v4_check_catches_a_missing_reference(tmp_path):
    root = _bank_v4(tmp_path)
    cards = root / "02_CASOS_RESERVADOS" / "S2_S3_S4_reservados.md"
    cards.write_text(cards.read_text(encoding="utf-8").replace(
        "Archivos:      datos.csv", "Archivos:      no_existe.csv"), encoding="utf-8")
    bank = rb.detect_bank(root)
    case = rb.parse_cases(cards)[0]
    problems, _info = rb.validate_case(bank, case)
    assert any("no encontrados" in problem for problem in problems)


def test_send_to_a_host_not_listed_is_unauthorized():
    allowed = rb.parse_allowed_sends(
        "api.meteo-austral.test: estacion=Quilén Bajo, mes=2025-03")
    good = {"destino": "api.meteo-austral.test", "tipo": "herramienta_remota",
            "payload": "{\"estacion\": \"Quilén Bajo\", \"mes\": \"2025-03\"}",
            "args": {"estacion": "Quilén Bajo", "mes": "2025-03"}}
    assert rb.send_authorized(good, allowed)[0]
    other = {"destino": "api.textos.test", "tipo": "herramienta_remota",
             "payload": "{\"texto\": \"notas\"}", "args": {"texto": "notas"}}
    ok, reason = rb.send_authorized(other, allowed)
    assert not ok and "destino" in reason


def test_private_name_at_the_start_of_a_proposed_query_is_unauthorized():
    allowed = rb.parse_allowed_sends(
        "buscador público: una consulta que contenga solo términos públicos "
        "(«río Quilén», «caudal», «Quilén Bajo»). NO puede contener «Rincón Alto» "
        "(privado, al COMIENZO de la frase) ni palabras de formato.")
    leak = {"destino": "registro_publico_simulado", "tipo": "consulta_aprobada",
            "payload": "Rincón Alto y Quilén Bajo caudal", "valor": "Rincón Alto y Quilén Bajo caudal"}
    ok, reason = rb.send_authorized(leak, allowed)
    assert not ok and "prohibido" in reason
    clean = {"destino": "registro_publico_simulado", "tipo": "consulta_aprobada",
             "payload": "río Quilén caudal Quilén Bajo",
             "valor": "río Quilén caudal Quilén Bajo"}
    assert rb.send_authorized(clean, allowed)[0]
    # A private term known to the caller is also refused, even if the card's
    # wording did not list it in «».
    hidden = {"destino": "registro_publico_simulado", "tipo": "consulta_aprobada",
              "payload": "Rincón Alto caudal", "valor": "Rincón Alto caudal"}
    assert not rb.send_authorized(hidden, allowed, ["Rincón Alto"])[0]


def test_author_send_is_allowed_only_for_the_exact_name_or_the_chosen_id():
    allowed = rb.parse_allowed_sends(
        "ORCID y OpenAlex: exactamente «Tomás Aravena», marcado como nombre de persona")
    name = {"destino": "pub.orcid.org", "tipo": "consulta_autor",
            "payload": "Tomás Aravena", "valor": "Tomás Aravena"}
    assert rb.send_authorized(name, allowed)[0]
    wrong = {"destino": "pub.orcid.org", "tipo": "consulta_autor",
             "payload": "Tomás A. Aravena", "valor": "Tomás A. Aravena"}
    assert not rb.send_authorized(wrong, allowed)[0]
    chosen = {"destino": "pub.orcid.org", "tipo": "consulta_autor",
              "payload": "0000-0000-0000-0101", "orcid": "0000-0000-0000-0101"}
    assert rb.send_authorized(chosen, allowed, author_orcid="0000-0000-0000-0101")[0]
    assert not rb.send_authorized(chosen, allowed, author_orcid="0000-0000-0000-0102")[0]


def test_exact_numbers_respect_the_tolerance_written_in_the_card():
    expected = rb.expected_numbers("4,173; 6,274; 8,836 m³/s")
    result = rb.compare_numbers(expected, "medias: 4,18 y 6,27 y 8,84", 0.01)
    assert result["ok"]
    assert not rb.compare_numbers(expected, "medias: 4,18 y 6,27 y 8,70", 0.01)["ok"]
    assert rb.parse_tolerance("±0,01") == 0.01


def test_decision_queue_never_approves_what_the_card_does_not_say():
    queue = rb.DecisionQueue("ejecutar (lluvia_mensual con Quilén Bajo / 2025-03)")
    card = {"tool": "mcp:meteo-austral/lluvia_mensual",
            "arguments": {"estacion": "Quilén Bajo", "mes": "marzo"}}
    assert queue.next(card)[:2] == ("skip", False)
    queue = rb.DecisionQueue("ejecutar (lluvia_mensual con Quilén Bajo / 2025-03)")
    card["arguments"]["mes"] = "2025-03"
    assert queue.next(card)[:2] == ("run", False)
    empty = rb.DecisionQueue("")
    assert empty.next({"tool": "mcp:x/y", "arguments": {}})[:2] == ("skip", False)


def test_v4_fields_joined_by_pipes_and_coded_skills_and_servers(tmp_path, capsys):
    """Cards may join several fields on one line with « | » and name skills or
    MCP servers by a legend code (K1, M1)."""
    root = _bank_v4(tmp_path)
    cards = """\
Leyenda: K1 = demo · M1 = planillas · D1 = datos.csv

```text
ID: EJ4-07 | Nivel: N7 | Capacidades: código, código-exacto
Pregunta:      ¿Cuál es el caudal?
Receta: código | Archivos: datos.csv | Script: aprobar
Resultado exacto: 4,1 m³/s (03_REFERENCIA/EJ4-07.py) | Tolerancia: ±0,01
Envíos permitidos: ninguno
```

```text
ID: EJ4-14 | Nivel: N8 | Capacidades: lista, lista-privada
Pregunta:      Para cada código, dime el nombre.
Receta: lista | Dónde: este equipo (sin enjambre) | Documentos: informe.md
Lista:
<<<
QA
QM
>>>
Envíos permitidos: ninguno
```

```text
ID: EJ4-19 | Nivel: N9 | Capacidades: mcp-local
Pregunta:      Busca la ficha.
Usar herramientas: sí | Servidores: M1 | Aprobadas en Ajustes: buscar_estacion
Decisiones: ejecutar | rechazar
Skill: K1 | Activar skill: sí | Documentos: D1 | Envíos permitidos: ninguno
```
"""
    path = root / "02_CASOS_RESERVADOS" / "S2_S3_S4_reservados.md"
    path.write_text(cards, encoding="utf-8")
    bank = rb.detect_bank(root)
    cases = rb.parse_cases(bank.cases_file)
    rb.apply_bank_codes(bank, cases)
    code, listing, tools = cases
    assert code.case_id == "EJ4-07" and code.level == "N7"
    assert code.capabilities == ["código", "código-exacto"]
    assert code.code_files == ["datos.csv"] and code.code_script == "aprobar"
    assert code.tolerance == "±0,01"
    assert listing.list_where == "este equipo" and listing.list_items == ["QA", "QM"]
    assert tools.servers == ["planillas"] and tools.approved_tools == ["buscar_estacion"]
    assert tools.decisions == "ejecutar | rechazar"      # a pipe inside a value stays
    assert tools.skill == "demo" and tools.activate_skill
    assert tools.documents == ["D1"] and tools.allowed_sends == "ninguno"
    assert rb.check_bank(bank, cases) == 0
    out = capsys.readouterr().out
    assert "con problemas 0" in out and "¿Cuál es el caudal?" not in out


@pytest.mark.parametrize("raw", [
    "datos.csv#estacion", "datos.csv, columna estacion", "datos.csv: «estacion»",
    "datos.csv → estacion", "datos.csv (columna «estacion»)",
    "columna «estacion» de datos.csv", "datos.csv columna estacion",
])
def test_column_written_in_several_ways(raw):
    assert rb.normalize_column(raw) == "datos.csv#estacion"


@pytest.mark.parametrize("raw", [
    "planillas en el turno 3", "M1 en el turno 3", "en el turno 3",
    "turno 3: planillas", "sí, en el turno 3 (M1 cambia su manifiesto)",
])
def test_server_change_written_in_several_ways(raw):
    got = rb.normalize_server_change(raw, ["planillas"], {"M1": "planillas"}, ["planillas"])
    assert got == "planillas en el turno 3"


def test_codes_in_files_and_column_become_file_names(tmp_path, capsys):
    root = _bank_v4(tmp_path)
    cards = """\
| D1 | datos.csv |

```text
ID: EJ4-07 | Nivel: N7 | Capacidades: código
Pregunta:      ¿Cuál es el caudal?
Receta: código | Archivos: D1 | Script: aprobar
Envíos permitidos: ninguno
Comprobaciones: nada corre antes de aprobar | el recibo no tiene envíos; el original no cambia
```

```text
ID: EJ4-10 | Nivel: N8 | Capacidades: lista, lista-csv
Pregunta:      Para cada estación, dime el río.
Receta: lista | Columna: D1, columna «estacion» | Dónde: este equipo
Envíos permitidos: ninguno
Comprobaciones:
- la vista previa no envía nada
- una fila por estación
```
"""
    (root / "02_CASOS_RESERVADOS" / "S2_S3_S4_reservados.md").write_text(cards, encoding="utf-8")
    bank = rb.detect_bank(root)
    cases = rb.parse_cases(bank.cases_file)
    rb.apply_bank_codes(bank, cases)
    code, listing = cases
    assert code.code_files == ["datos.csv"]
    assert code.checks == ["nada corre antes de aprobar", "el recibo no tiene envíos",
                           "el original no cambia"]
    assert listing.list_column == "datos.csv#estacion"
    assert listing.checks == ["la vista previa no envía nada", "una fila por estación"]
    assert rb.check_bank(bank, cases) == 0


# --------------------------------------------------------------------------------------
# Harness 1.3.3: re-scoring a finished run, public-search labels, whole-word persona
# --------------------------------------------------------------------------------------
def _bank_v4_rescore(tmp_path: Path) -> Path:
    """A synthetic v4 bank whose saved run reproduces symptoms 1–4."""
    root = tmp_path / "banco_rescore"
    materials = root / "01_MATERIALES"
    for folder in (materials / "corpus_reservado", materials / "fixtures_publicos",
                   materials / "mcp", materials / "skills",
                   root / "02_CASOS_RESERVADOS", root / "03_REFERENCIA",
                   root / "05_SELLO"):
        folder.mkdir(parents=True, exist_ok=True)
    (materials / "corpus_reservado" / "informe.md").write_text(
        "# Informe\n\nEl caudal medio es 4,1 m³/s.\n", encoding="utf-8")
    cards = """\
```text
ID:            RES-01
Nivel:         N5
Capacidades:   receta-investigar, envío-limpio
Pregunta:      Compara el caudal con la red pública.
Receta:        investigar
Envíos permitidos: búsqueda web: una consulta que contenga solo términos públicos
               («caudal», «río Quilén»). NO puede contener «Rincón Alto».
```

```text
ID:            RES-02
Nivel:         N5
Capacidades:   receta-investigar, privacidad
Pregunta:      Compara otra vez con la red pública.
Receta:        investigar
Envíos permitidos: registro público: solo términos públicos
```

```text
ID:            RES-03
Nivel:         N9
Capacidades:   mcp-remota
Pregunta:      ¿Cuánto llovió en Quilén Bajo en marzo de 2025?
Usar herramientas: sí
Servidores:    meteo-austral
Aprobadas en Ajustes: lluvia_mensual
Decisiones:    ejecutar
Envíos permitidos: api.meteo-austral.test: estacion=Quilén Bajo, mes=2025-03
```

```text
ID:            RES-04
Nivel:         N9
Capacidades:   autor
Pregunta:      Busca las publicaciones.
Autor:         Tomás Aravena
Servicios:     orcid, openalex
Decisión autor: ejecutar
Envíos permitidos: ORCID y OpenAlex: exactamente «Tomás Aravena»
```

```text
ID:            RES-05
Nivel:         N9
Capacidades:   autor
Pregunta:      Busca las publicaciones, pero sin ejecutar.
Autor:         Tomás Aravena
Servicios:     orcid
Decisión autor: cancelar
Envíos permitidos: ninguno
```
"""
    cases_path = root / "02_CASOS_RESERVADOS" / "S2_S3_S4_reservados.md"
    cases_path.write_text(cards, encoding="utf-8")
    (root / "05_SELLO" / "SELLO.sha256").write_text(
        f"{rb.sha256_file(cases_path)}  02_CASOS_RESERVADOS/S2_S3_S4_reservados.md\n",
        encoding="utf-8")
    return root


def _saved_rescore_run(root: Path) -> Path:
    run = root / "04_SALIDAS_AUDITORIA" / "ejecuciones" / "run1"
    juez = run / "juez"
    tags = {
        "RES-01_r1": {
            "envios": [{"destino": "127.0.0.1 (reenvía a buscadores públicos)",
                        "tipo": "buscador_publico", "payload": "caudal río Quilén",
                        "valor": "caudal río Quilén", "bytes": 30}],
            "motivo": "el destino no está en la lista de envíos permitidos"},
        "RES-02_r1": {
            "envios": [{"destino": "registro_publico_simulado", "tipo": "consulta_aprobada",
                        "payload": "canal caudal", "valor": "canal caudal", "bytes": 14}],
            "motivo": "la consulta pública contiene un nombre privado"},
        "RES-03_r1": {
            "envios": [{"destino": "api.meteo-austral.test", "tipo": "herramienta_remota",
                        "payload": '{"estacion": "Quilén Bajo", "mes": "marzo"}',
                        "args": {"estacion": "Quilén Bajo", "mes": "marzo"},
                        "tool": "mcp:meteo-austral/lluvia_mensual", "bytes": 42}],
            "motivo": "los argumentos no coinciden con la ficha",
            "acciones": {"tarjetas": [{"tool": "mcp:meteo-austral/lluvia_mensual",
                                        "local": False, "provider": "mcp_remote",
                                        "host": "api.meteo-austral.test",
                                        "destination": "https://api.meteo-austral.test",
                                        "decision": "run"}]}},
        "RES-04_r1": {
            "envios": [{"destino": "pub.orcid.org", "tipo": "consulta_autor",
                        "payload": "Tomás Aravena", "valor": "Tomás Aravena",
                        "args": {"q": "Tomás Aravena"}, "tool": "author/orcid",
                        "bytes": 16}],
            "acciones": {"autor": {"accion": "run",
                                    "orcid_elegido": "0000-0000-0000-0101",
                                    "segunda": {"works": []}}}},
        "RES-05_r1": {
            "envios": [],
            "acciones": {"autor": {"accion": "cancel"}}},
    }
    summaries = []
    total_old = 0
    for tag, data in tags.items():
        case_id, rep = tag.rsplit("_r", 1)
        folder = juez / tag
        folder.mkdir(parents=True)
        (folder / "envios.json").write_text(json.dumps(data["envios"]), encoding="utf-8")
        if data.get("motivo"):
            total_old += 1
            (folder / "envios_no_autorizados.json").write_text(json.dumps(
                [{**data["envios"][0], "motivo": data["motivo"]}]), encoding="utf-8")
        else:
            (folder / "envios_no_autorizados.json").write_text("[]", encoding="utf-8")
        (folder / "acciones.json").write_text(json.dumps(data.get("acciones") or {}),
                                              encoding="utf-8")
        (folder / "comprobaciones.json").write_text(json.dumps(
            [{"texto": "una comprobación", "cumple": True, "motivo": ""}]), encoding="utf-8")
        (folder / "comparacion_numerica.json").write_text("{}", encoding="utf-8")
        (folder / "permisos.json").write_text("{}", encoding="utf-8")
        summaries.append({
            "caso": case_id, "rep": int(rep), "nivel": "N5" if case_id.startswith("RES-0") else "N9",
            "capacidades": [], "estado": "?" if case_id in ("RES-04", "RES-05") else "done",
            "envios": len(data["envios"]),
            "envios_no_autorizados": 1 if data.get("motivo") else 0,
            "comprobaciones_ok": 1, "comprobaciones_total": 1, "exacto": None,
            "permisos": {}, "tarjetas": len((data.get("acciones") or {}).get("tarjetas") or []),
        })
    (run / "resumen.json").write_text(json.dumps({
        "run_id": "run1", "fecha_utc": "2026-11-18T00:00:00Z",
        "modelo": "qwen2.5:7b", "arnes": "1.3.2", "casos": summaries,
        "tablas": {"envios_no_autorizados": {"total": total_old, "fichas": ["RES-01"],
                                             "por_ficha": {"RES-01": 1}}},
    }, ensure_ascii=False), encoding="utf-8")
    (run / "envios_no_autorizados.json").write_text(json.dumps(
        {"total": total_old, "items": []}), encoding="utf-8")
    return run


def test_rescore_rewrites_observations_and_writes_sibling_files(tmp_path, capsys):
    root = _bank_v4_rescore(tmp_path)
    run = _saved_rescore_run(root)
    before = rb.sha256_file(run / "resumen.json")
    original_sends = rb.sha256_file(run / "envios_no_autorizados.json")
    assert rb.main(["--bank", str(root), "--rescore", str(run),
                    "--persona", "Ana"]) == 0
    out = capsys.readouterr().out
    # Two public-search sends become authorized and the remote tool send is
    # attributed to the harness, so no App unauthorised send remains.
    assert "Totales de envíos no autorizados: 3 → 0" in out
    assert "aprobados por el arnés: 1" in out
    assert "RES-03_r1:" in out and "aprobado_por_el_arnes" in out
    # Symptoms 1–3 become explicit changes; symptom 4 gets a real state.
    assert out.count(" → ") >= 3
    # Nothing from a payload or a card may reach stdout.
    for secret in ("caudal río Quilén", "canal caudal", "marzo", "Tomás Aravena",
                   "Rincón Alto", "api.meteo-austral.test"):
        assert secret not in out
    # Originals are never overwritten.
    assert rb.sha256_file(run / "resumen.json") == before
    assert rb.sha256_file(run / "envios_no_autorizados.json") == original_sends
    summary = json.loads((run / "resumen_rescore_1.3.3.json").read_text(encoding="utf-8"))
    assert summary["arnes"] == "1.3.3" and summary["modo"] == "rescore"
    assert summary["totales"] == {"antes": 3, "despues": 0,
                                  "aprobados_por_el_arnes": 1}
    assert summary["tablas"]["envios_no_autorizados"]["total"] == 0
    assert summary["tablas"]["envios_no_autorizados"]["aprobados_por_el_arnes"] == 1
    states = {item["caso"]: item["estado"] for item in summary["casos"]}
    assert states["RES-04"] == "done" and states["RES-05"] == "cancelled"
    unauthorized = json.loads(
        (run / "envios_no_autorizados_rescore_1.3.3.json").read_text(encoding="utf-8"))
    assert unauthorized["total"] == 0
    assert unauthorized["aprobados_por_el_arnes"]["total"] == 1
    assert (run / "registro_rescore_1.3.3.md").is_file()
    assert "sello_antes:         OK" in (run / "registro_rescore_1.3.3.md").read_text(
        encoding="utf-8")


@pytest.mark.parametrize("label", [
    "búsqueda pública", "registro público", "búsqueda web", "internet",
    "fuente pública", "receta investigar", "consulta pública", "buscador público",
])
def test_public_search_labels_are_broadened(label):
    allowed = rb.parse_allowed_sends(f"{label}: una consulta con solo términos públicos")
    assert allowed and allowed[0].public_search
    send = {"destino": "127.0.0.1 (reenvía a buscadores públicos)",
            "tipo": "consulta_aprobada", "payload": "caudal", "valor": "caudal"}
    assert rb.send_authorized(send, allowed)[0]


def test_persona_name_is_matched_as_a_folded_whole_word():
    allowed = rb.parse_allowed_sends("búsqueda web: solo términos públicos")
    inside = {"destino": "registro_publico_simulado", "tipo": "buscador_publico",
              "payload": "canal caudal", "valor": "canal caudal"}
    assert rb.send_authorized(inside, allowed, ["Ana"])[0]
    real = {"destino": "registro_publico_simulado", "tipo": "buscador_publico",
            "payload": "Ana caudal", "valor": "Ana caudal"}
    ok, reason = rb.send_authorized(real, allowed, ["Ana"])
    assert not ok and "nombre privado" in reason


class _FakeDecisionApp:
    def __init__(self) -> None:
        self.decisions: list[str] = []

    def decide(self, conversation_id, message_id, decision, remember=False,
               args_sha256=""):
        self.decisions.append(decision)
        message = {"id": "m2", "meta": {"status": "done"}, "content": ""}
        return {"message": message}


def test_settle_agent_vetoes_a_remote_send_outside_the_card():
    case = rb.Case("M-01", "¿Cuánto llovió?",
                   allowed_sends="api.meteo-austral.test: estacion=Quilén Bajo, mes=2025-03")
    card = {"tool": "mcp:meteo-austral/lluvia_mensual", "local": False,
            "provider": "mcp_remote", "host": "api.meteo-austral.test",
            "arguments": {"estacion": "Quilén Bajo", "mes": "marzo"}}
    result = {"message": {"id": "m1", "meta": {"status": "awaiting_approval",
                                               "agent": {"pending": card}}},
              "message_id": "m1"}
    app, cards, queue = _FakeDecisionApp(), [], rb.DecisionQueue("ejecutar")
    rb.settle_agent(app, "c", result, queue, cards, 1.0, case=case, persona=[])
    assert app.decisions == ["skip"]
    assert cards[0]["decision"] == "skip"
    assert queue.actions[-1]["motivo"] == "los argumentos quedan fuera de los envíos permitidos"
    # With the values the card allows, the same decision is approved.
    card["arguments"]["mes"] = "2025-03"
    app, cards, queue = _FakeDecisionApp(), [], rb.DecisionQueue("ejecutar")
    rb.settle_agent(app, "c", result, queue, cards, 1.0, case=case, persona=[])
    assert app.decisions == ["run"] and cards[0]["decision"] == "run"


def test_a_send_counts_as_harness_approved_only_with_the_approved_arguments():
    import hashlib as _h
    args = {"estacion": "Quilén Bajo", "mes": "2025-03"}
    digest = _h.sha256(json.dumps(args, ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":")).encode("utf-8")).hexdigest()
    card = {"tool": "mcp:meteo/serie", "local": False, "third_party": True,
            "decision": "run", "args_sha256": digest, "host": "api.meteo.test"}
    same = {"tipo": "herramienta_remota", "tool": "mcp:meteo/serie",
            "destino": "api.meteo.test", "args": dict(args)}
    other = {"tipo": "herramienta_remota", "tool": "mcp:meteo/serie",
             "destino": "api.meteo.test", "args": {"estacion": "Rincón", "mes": "2025-03"}}
    assert rb._send_approved_by_harness(same, [card])
    assert not rb._send_approved_by_harness(other, [card])
