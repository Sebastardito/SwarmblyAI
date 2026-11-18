"""3.3, recipe 2: a table built by code from values each document supports."""

from __future__ import annotations

from conftest import FakeBackend
from swarmbly_app import tables as T

AB1 = {"rel": "informe_lote_AB1.md", "passages": [
    ("D1 p2", "El lote AB1 se sembró en tres sitios: Parcela Norte, Parcela Sur y Ladera Este."),
    ("D1 p16", "| Sitio | Rendimiento medio (t/ha) |\n|---|---|\n| Parcela Norte | 2,8 |\n| Parcela Sur | 2,4 |"),
    ("D1 p17", "El costo de producción fue de 1.150 dólares por hectárea.")]}
AB2 = {"rel": "informe_lote_AB2.md", "passages": [
    ("D2 p2", "El lote AB2 se sembró en tres sitios: Parcela Norte, Parcela Sur y Ladera Este."),
    ("D2 p16", "| Sitio | Rendimiento medio (t/ha) |\n|---|---|\n| Parcela Norte | 3,1 |\n| Parcela Sur | 2,2 |"),
    ("D2 p17", "El costo de producción fue de 1.080 dólares por hectárea.")]}
ENT = ["AB1", "AB2", "Parcela Norte", "Parcela Sur", "Ladera Este"]
HEAD = ["Sitio", "Rendimiento AB1 (t/ha)", "Rendimiento AB2 (t/ha)", "Diferencia"]


def test_header_and_rows_are_read_from_what_the_model_writes():
    assert T.parse_header("Aquí está:\n| **Sitio** | AB1 | AB2 | Fuente |\n|---|---|---|---|") == ["Sitio", "AB1", "AB2"]
    assert T.parse_header("No puedo.") is None
    rows = T.parse_rows("| Parcela Norte | 2,8 [D1 p16] | — |\nNINGUNA\n|---|---|---|\nParcela Sur | 2,4", 4)
    assert rows == [["Parcela Norte", "2,8", "—", "—"], ["Parcela Sur", "2,4", "—", "—"]]
    prompt = T.header_prompt("Compara AB1 y AB2 en los tres sitios con una tabla.", {"entities": ENT})
    assert "una fila por cada uno de: Parcela Norte, Parcela Sur, Ladera Este" in prompt
    assert "una columna por cada uno de: AB1, AB2" in prompt


def test_only_values_the_document_supports_are_kept():
    rows = [["Parcela Norte", "2,8", "—", "—"],
            ["Parcela Sur", "2,4", "9,9", "0,5"],          # a value for the other lot, a calculation
            ["Parcela Oeste", "3,0", "—", "—"],            # an invented row
            ["Ladera Este", "7,7", "—", "—"]]              # a real site, an invented value
    kept, dropped = T.validate(rows, HEAD, AB1, ENT)
    assert [k["cells"] for k in kept] == [["Parcela Norte", "2,8", "", ""], ["Parcela Sur", "2,4", "", ""]]
    assert kept[0]["labels"] == ["D1 p16"]
    assert {d["why"] for d in dropped} == {"column of another entity", "key not in the document",
                                           "value not in the document", "no value in the document"}


def test_rows_of_two_documents_are_merged_and_the_difference_is_computed():
    a, _ = T.validate([["Parcela Norte", "2,8", "—", "—"], ["Parcela Sur", "2,4", "—", "—"]], HEAD, AB1, ENT)
    b, _ = T.validate([["la Parcela Norte", "—", "3,1", "—"], ["Parcela Sur", "—", "2,2", "—"]], HEAD, AB2, ENT)
    rows = T.merge(a + b, ENT)
    header, rows, computed = T.derive(HEAD, rows)
    assert [r["cells"] for r in rows] == [["Parcela Norte", "2,8", "3,1", "0,3"], ["Parcela Sur", "2,4", "2,2", "0,2"]]
    assert computed == 2
    md = T.render(header, rows)
    assert md.split("\n")[0] == "| Sitio | Rendimiento AB1 (t/ha) | Rendimiento AB2 (t/ha) | Diferencia | Fuente |"
    assert "| Parcela Norte | 2,8 | 3,1 | 0,3 | [D1 p16] [D2 p16] |" in md


def test_a_difference_between_two_rows_becomes_a_row():
    head = ["Lote", "Costo de producción", "Diferencia"]
    a, _ = T.validate([["AB1", "1.150 dólares", "—"]], head, AB1, ENT)
    b, _ = T.validate([["AB2", "1.080 dólares", "—"], ["AB1", "1.150 dólares", "—"]], head, AB2, ENT)
    assert len(b) == 1                                       # AB1's row is not AB2's document's to give
    header, rows, computed = T.derive(head, T.merge(a + b, ENT))
    assert header == ["Lote", "Costo de producción"] and computed == 1
    assert rows[-1]["cells"] == ["Diferencia", "70 dólares"]


def test_two_values_for_the_same_cell_stay_apart():
    head = ["Dato", "Valor"]
    a = {"cells": ["Cosecha", "segunda semana de junio"], "labels": ["D1 p4"]}
    b = {"cells": ["Cosecha", "tercera semana de junio"], "labels": ["D2 p2"]}
    assert len(T.merge([a, b], [])) == 2


def test_audit_reports_cells_that_are_in_no_passage():
    src = [{"text": t} for _, t in AB1["passages"] + AB2["passages"]]
    answer = ("Texto.\n\n| Sitio | AB1 | AB2 | Diferencia |\n|---|---|---|---|\n"
              "| Parcela Norte | 2,8 | 3,1 | 0,3 |\n| Parcela Sur | 2,4 | 2,2 | 0,2 |\n| Parcela Oeste | 9,9 | 3,1 | 6,8 |\n")
    out = T.audit(answer, src)
    assert out["cells"] == 9 and [c["value"] for c in out["unsupported"]] == ["9,9", "6,8"]
    assert T.audit("Sin tabla.", src) is None
    assert T.strip_tables(answer) == "Texto."
    assert T.place("Uno.\n\nDos.", "|T|", "Escribe un informe con una tabla.") == "Uno.\n\n|T|\n\nDos."
    assert T.place("Uno.", "|T|", "Haz una tabla y explícala en un párrafo.").startswith("|T|")


class _Recipe(FakeBackend):
    """Answers each short job of the recipe as a small model would, with an
    invented row and a value of its own on the way."""

    def stream_chat(self, messages, **kw):
        last = messages[-1]["content"]
        if "fila de encabezado" in last:
            self.reply = "| Lote | Costo de producción (dólares/ha) | Diferencia |"
        elif "permite llenar" in last and "informe_lote_AB1" in last:
            self.reply = "| AB1 | 1.150 | — |\n| AB3 | 999 | — |"
        elif "permite llenar" in last and "informe_lote_AB2" in last:
            self.reply = "AB2 | 1.080 | 70"
        elif "permite llenar" in last:
            self.reply = "NINGUNA"
        else:
            self.reply = ("El lote AB1 costó más que el AB2 [D1 p1].\n\n| Lote | Costo |\n|---|---|\n| AB1 | 1.200 |\n")
        return super().stream_chat(messages, **kw)


def test_recipe_2_in_the_chat(app_state, tmp_path):
    fake = _Recipe()
    app_state.backends.resolve = lambda config=None: fake      # type: ignore[method-assign]
    p = app_state.projects.create("T", parent=tmp_path / "p")
    (p.sources / "informe_lote_AB1.md").write_text(
        "El costo de producción del lote AB1 fue de 1.150 dólares por hectárea.\n", encoding="utf-8")
    (p.sources / "informe_lote_AB2.md").write_text(
        "El costo de producción del lote AB2 fue de 1.080 dólares por hectárea.\n", encoding="utf-8")
    app_state.config.update({"lce.enabled": True, "lce.level": "C1", "compose.table_by_code": True})
    conv = app_state.chat.create_conversation(mode="local", project_id=p.id)
    app_state.chat.send(conv["id"], "Haz una tabla con el costo de producción de AB1 y AB2 y la diferencia entre "
                        "ambos, y explícala en un párrafo de unas 40 palabras.", mode="local", run_async=False)
    msg = app_state.chat.get_messages(conv["id"])[-1]
    text, meta = msg["content"], msg["meta"]
    assert "| AB1 | 1.150 |" in text and "| AB2 | 1.080 |" in text and "| Diferencia | 70 |" in text
    assert "1.200" not in text and "AB3" not in text            # the model's own table and its invented row are gone
    assert text.startswith("| Lote |") and "costó más" in text
    assert meta["table"]["rows"] == 3 and meta["table"]["computed"] == 1
    assert any(d["why"] == "key not in the document" for d in meta["table"]["dropped"])
    assert meta["table_audit"]["unsupported"] == []
    system = " ".join(m["content"] for m in [c for c in fake.calls if not c["messages"][-1]["content"].startswith("Párrafos:")][-1]["messages"] if m["role"] == "system")
    assert "ya armó esta tabla" in system


SUELO = {"rel": "analisis_suelo_2026.md", "passages": [
    ("D1 p4", "| Sitio | Nitrógeno total (%) | Fósforo (ppm) | pH |\n|---|---|---|---|\n"
              "| Parcela Norte | 0,21 | 18 | 6,8 |\n| Parcela Sur, sector oeste | 0,09 | 14 | 7,9 |"),
    ("D1 p9", "| Fecha | Mínima (°C) | Lluvia (mm) |\n|---|---|---|\n| 1 de marzo | 12 | 0 |")]}


def test_a_source_table_is_read_by_code_not_by_the_model():
    rows = T.rows_from_tables(["Sitio", "Nitrógeno total (%)", "pH"], SUELO, [])
    assert rows == [["Parcela Norte", "0,21", "6,8"], ["Parcela Sur, sector oeste", "0,09", "7,9"]]
    # the same source column wanted for two lots: only this document's lot gets it
    rows = T.rows_from_tables(HEAD, AB2, ENT)
    assert rows == [["Parcela Norte", "—", "3,1", "—"], ["Parcela Sur", "—", "2,2", "—"]]
    called = []

    def generate(prompt, n):
        called.append(prompt)
        return "| Sitio | Rendimiento AB1 (kg) | Rendimiento AB2 (kg) | Diferencia |" if "encabezado" in prompt else "NINGUNA"
    src = [{"label": lab, "rel": d["rel"], "doc_id": d["rel"], "text": t} for d in (AB1, AB2) for lab, t in d["passages"]]
    q = "Escribe un informe que compare los rendimientos de AB1 y AB2 por sitio, con una tabla y la diferencia."
    built = T.build(q, src, {"entities": ENT}, generate)
    assert len(called) == 1 and built["rows_by_code"] == 4            # only the header was asked of the model
    assert "| Parcela Norte | 2,8 | 3,1 | 0,3 | [D1 p16] [D2 p16] |" in built["markdown"]
    assert "(t/ha)" in built["markdown"] and "(kg)" not in built["markdown"]   # the unit is the source's


def test_header_is_tidied_and_values_are_as_the_document_writes_them():
    docs = [SUELO]
    assert T.tidy_header(["Sitio", "Nitrógeno total (mg/kg)", "pH", "Diferencia"],
                         "Tabla con el nitrógeno total y el pH de cada sitio.", docs) == \
        ["Sitio", "Nitrógeno total (%)", "pH"]
    cv = ("- Coordinadora de ensayos de campo en AcmeLabs, desde agosto de 2022. Dirijo los ensayos.\n"
          "- Técnica de laboratorio en AcmeLabs, de marzo de 2019 a julio de 2022: análisis de suelo.")
    assert T._as_written("Ago 2022 -", cv, "Coordinadora de ensayos de campo") == "desde agosto de 2022"
    assert T._as_written("Mar 2019 - Jul 2022", cv, "Técnica de laboratorio") == "de marzo de 2019 a julio de 2022"
    assert T._as_written("1150", "costó 1.150 dólares") == "1.150" and T._as_written("87", "del 87 % en") == "87 %"
    assert T.parse_rows("| Sitio | pH |\n| Norte | 6,8 |", 2, ["Sitio", "pH"]) == [["Norte", "6,8"]]
    doc = {"rel": "informe.md", "passages": [("D1 p3", "El caudal medio se mantuvo estable."),
                                              ("D1 p17", "El costo de producción fue de 1.150 dólares.")]}
    assert [lab for lab, _ in T.relevant_passages("Tabla con el costo de producción de AB1 y AB2.",
                                                  ["Lote", "Costo"], doc, ["AB1", "AB2"])] == ["D1 p17"]


def test_a_table_that_arrives_on_one_line_gets_its_lines_back():
    from swarmbly_app.compose import _units, unflatten_tables
    flat = ("Resultados — | Sitio | Nitrógeno total (%) | pH | |---|---|---| | Parcela Norte | 0,21 | 6,8 | "
            "| Parcela Sur, sector oeste | 0,09 | 7,9 |")
    assert unflatten_tables(flat).split("\n") == [
        "Resultados", "| Sitio | Nitrógeno total (%) | pH |", "|---|---|---|",
        "| Parcela Norte | 0,21 | 6,8 |", "| Parcela Sur, sector oeste | 0,09 | 7,9 |"]
    assert unflatten_tables("Sin tabla | ni regla.") == "Sin tabla | ni regla."
    assert unflatten_tables(unflatten_tables(flat)) == unflatten_tables(flat)
    assert _units(flat)[0] == "Sitio: Parcela Norte · Nitrógeno total (%): 0,21 · pH: 6,8"
    doc = T.documents("Tabla con el nitrógeno total y el pH de cada sitio.",
                      [{"label": "D1 p4", "rel": "suelo.md", "doc_id": "s", "text": flat}])[0]
    assert T.rows_from_tables(["Sitio", "Nitrógeno total", "pH"], doc, []) == [
        ["Parcela Norte", "0,21", "6,8"], ["Parcela Sur, sector oeste", "0,09", "7,9"]]


def test_the_layout_is_the_models_unless_the_request_names_both_sides():
    # told "one row for each of AB1, AB2", a 7B model wrote "| Lote | Sitio 1 | Sitio 2 | Sitio 3 |"
    codes = T.header_prompt("Tabla con el rendimiento medio de cada lote por sitio, AB1 y AB2.", {"entities": ["AB1", "AB2"]})
    people = T.header_prompt("Compara a Ana Pérez y Luis Soto en una tabla.", {"entities": ["Ana Pérez", "Luis Soto"]})
    assert "Usa una" not in codes and "Usa una" not in people


def test_a_column_named_only_after_a_lot_takes_what_the_request_asks_about():
    request = ("Compara los rendimientos de los lotes AB1 y AB2. Incluye una tabla con el rendimiento medio "
               "de cada lote por sitio y la diferencia absoluta.")
    weather = "| Fecha | Mínima (°C) | Máxima (°C) | Lluvia (mm) |\n|---|---|---|---|\n| 1 de marzo | 12 | 22 | 0 |"
    yields = ("| Sitio | Repeticiones | Rendimiento medio (t/ha) | Desviación estándar | |---|---|---|---| "
              "| Parcela Norte | 4 | {} | 0,3 | | Parcela Sur | 4 | {} | 0,4 |")   # on one line, as the search gives it
    sources = []
    for n, (lot, a, b) in enumerate((("AB1", "2,8", "2,4"), ("AB2", "3,1", "2,2")), 1):
        for p, text in ((5, weather), (16, yields.format(a, b)),
                        (17, f"El rendimiento medio del lote {lot} fue alto; el otro lote se describe en su informe.")):
            sources.append({"rel": f"informe_lote_{lot}.md", "doc_id": lot, "label": f"D{n} p{p}", "text": text})
    asked = []

    def generate(prompt, max_tokens):
        asked.append(prompt)
        return "| Sitio | Lote AB1 | Lote AB2 | Diferencia |"

    built = T.build(request, sources, {"entities": ["AB1", "AB2"], "table": True}, generate)
    assert len(asked) == 1 and built["rows_by_code"] == 4            # the model wrote the header, nothing else
    assert built["header"] == ["Sitio", "Rendimiento medio AB1 (t/ha)", "Rendimiento medio AB2 (t/ha)", "Diferencia"]
    assert "| Parcela Norte | 2,8 | 3,1 | 0,3 | [D1 p16] [D2 p16] |" in built["markdown"]
    assert "| Parcela Sur | 2,4 | 2,2 | 0,2 | [D1 p16] [D2 p16] |" in built["markdown"]
    assert "marzo" not in built["markdown"]


def test_a_header_that_mixes_a_measure_with_columns_per_lot_keeps_the_measure():
    header = ["Cultivo", "Costo de Producción por Hectárea", "AB1", "AB2", "Diferencia"]
    request = "Haz una tabla con el costo de producción por hectárea de AB1 y AB2 y la diferencia entre ambos."
    assert T.tidy_header(header, request, [AB1, AB2], ["AB1", "AB2"]) == [
        "Cultivo", "Costo de Producción por Hectárea", "Diferencia"]
    assert T.tidy_header(["Sitio", "Lote AB1", "Lote AB2", "Diferencia"], request, [AB1, AB2], ["AB1", "AB2"]) == [
        "Sitio", "Lote AB1", "Lote AB2", "Diferencia"]
    prompt = T.header_prompt(request, {"entities": ["AB1", "AB2"]})
    assert "  " not in prompt and prompt.endswith("columna «Diferencia». No escribas filas de datos ni nada más.")


def test_one_value_per_place_in_a_sentence_is_read_by_code():
    ab1 = {"rel": "informe_lote_AB1.md", "passages": [
        ("D1 p2", "Siembra y germinación — El lote AB1 se sembró el 12 de febrero de 2026 en tres sitios: Parcela Norte, "
                  "Parcela Sur y Ladera Este. La germinación fue del 87 % en la Parcela Norte, del 81 % en la Parcela Sur "
                  "y del 74 % en la Ladera Este.")]}
    request = "Compara la germinación de AB1 y AB2 en cada sitio."
    header = ["Sitio", "AB1", "AB2", "Diferencia"]
    rows = T.rows_from_prose(header, ab1, ENT, request)
    assert rows == [["Parcela Norte", "87 %", "—", "—"], ["Parcela Sur", "81 %", "—", "—"], ["Ladera Este", "74 %", "—", "—"]]
    assert ab1["named_after"] == {1: "Germinación"}
    # a document about no single code, or a sentence off the topic, gives nothing
    assert T.rows_from_prose(header, dict(ab1, rel="notas.md"), ENT, request) == []
    assert T.rows_from_prose(header, dict(ab1), ENT, "Compara el costo de AB1 y AB2.") == []


def test_the_differences_the_program_computed_are_listed():
    header = ["Sitio", "Germinación AB1", "Germinación AB2", "Diferencia"]
    rows = [{"key": "n", "cells": ["Parcela Norte", "87 %", "90 %", ""], "labels": ["D1 p2"]},
            {"key": "s", "cells": ["Parcela Sur", "81 %", "85 %", ""], "labels": ["D1 p2"]}]
    sources = [{"label": "D1 p2", "rel": "informe_lote_AB1.md", "doc_id": "a",
                "text": "La germinación fue del 87 % en la Parcela Norte y del 81 % en la Parcela Sur."},
               {"label": "D2 p2", "rel": "informe_lote_AB2.md", "doc_id": "b",
                "text": "La germinación fue del 90 % en la Parcela Norte y del 85 % en la Parcela Sur."}]
    built = T.build("Compara la germinación de AB1 y AB2 por sitio y la diferencia, en una tabla.", sources,
                    {"entities": ["AB1", "AB2", "Parcela Norte", "Parcela Sur"], "table": True},
                    lambda p, n: "| Sitio | AB1 | AB2 | Diferencia |" if "encabezado" in p else "NINGUNA")
    assert built["computed_values"] == ["3", "4"]


# ---- 3.3: corrections, a header from the source, and why no table (banks v3) ----

_CORR_REQ = "Ponme la cuaja de las tres parcelas y del testigo, con el valor corregido donde lo haya."
_CORR_SOURCES = [
    {"rel": "informe_ensayo.md", "label": "D1 p3", "doc_id": "a",
     "text": "Resultados — | Parcela | Cuaja con abejorros (%) | |---|---| | Alta | 78 | | Media | 71 | "
             "| Baja | 64 | | Testigo sin abejorros | 52 |"},
    {"rel": "acta_reunion.md", "label": "D2 p2", "doc_id": "b",
     "text": "Las colonias efectivas fueron 10, no 12. La cuaja de la Parcela Baja se recalcula en 61 %."},
]


def _inv(req):
    from swarmbly_app import compose
    inv = compose.inventory(req, [s["text"] for s in _CORR_SOURCES])
    inv["table"] = True
    return inv


def test_a_value_a_later_paragraph_corrects_replaces_the_one_read():
    from swarmbly_app import tables
    out = tables.build(_CORR_REQ, _CORR_SOURCES, _inv(_CORR_REQ),
                       lambda p, n: "| Parcela | Cuaja (%) |" if "encabezado" in p else "NINGUNA")
    assert "| Baja | 61 (antes 64) | [D1 p3] [D2 p2] |" in out["markdown"]
    assert out["corrections"] == [{"row": "Baja", "col": "Cuaja (%)", "old": "64", "new": "61", "label": "D2 p2"}]
    assert "| Alta | 78 | [D1 p3] |" in out["markdown"]


def test_a_date_after_a_correction_word_is_not_a_corrected_value():
    from swarmbly_app import tables
    rows = [{"key": "baja", "cells": ["Baja", "64"], "labels": ["D1 p3"]},
            {"key": "alta", "cells": ["Alta", "78"], "labels": ["D1 p3"]}]
    found = tables.apply_corrections(["Parcela", "Cuaja (%)"], rows, [
        {"label": "D2 p2", "text": "La cuaja de la Parcela Baja fue revisada por el técnico el 15 de marzo de 2025."}])
    assert found == [] and rows[0]["cells"][1] == "64"


def test_the_source_tables_header_when_the_model_writes_none_and_why_otherwise():
    from swarmbly_app import tables
    why = {}
    out = tables.build(_CORR_REQ, _CORR_SOURCES, _inv(_CORR_REQ), lambda p, n: "no sé", "es", why)
    assert out and why.get("header_from_source") is True
    assert out["header"][:2] == ["Parcela", "Cuaja con abejorros (%)"]
    why = {}
    assert tables.build(_CORR_REQ, [_CORR_SOURCES[1]], _inv(_CORR_REQ), lambda p, n: "no sé", "es", why) is None
    assert why["reason"] in ("no_header", "fewer_than_two_rows")


def test_a_csv_file_reaches_the_answer_as_its_table(tmp_path):
    from swarmbly_app import lce_adapter as A
    from swarmbly_lce.c1 import SourceIndex
    rows = ["partida,categoria,monto_usd"] + [f"Partida número {i},cat{i % 3},{1000 + 37 * i}" for i in range(40)]
    (tmp_path / "presupuesto.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    spans = A._with_csv_tables([tmp_path], SourceIndex().spans([tmp_path]))
    assert len(spans) >= 2 and all(s.get("csv_table") for s in spans)
    assert all(s["text"].startswith("| partida | categoria | monto_usd |\n|---|---|---|") for s in spans)
    body = "\n".join(s["text"] for s in spans)
    assert "| Partida número 39 | cat0 | 2443 |" in body and "| Partida número 0 | cat0 | 1000 |" in body


def test_a_header_that_says_nothing_of_the_request_gives_way_to_the_source_tables():
    from swarmbly_app import tables
    why = {}
    out = tables.build(_CORR_REQ + " Hazlo en una tabla.", _CORR_SOURCES, _inv(_CORR_REQ),
                       lambda p, n: "| Descripción | Valor |" if "encabezado" in p else "NINGUNA", "es", why)
    assert out and why.get("header_from_source") is True
    assert "| Baja | 61 (antes 64) | [D1 p3] [D2 p2] |" in out["markdown"]


def test_a_source_table_with_one_column_per_lot_is_read_turned():
    """Sealed bank v3.1: the report gave one column per lot and one row per
    variable; the request wanted one row per lot."""
    from swarmbly_app import compose, tables
    req = "Haz una tabla con el rendimiento y el costo de cada lote."
    src = [{"rel": "informe_comparativo.md", "label": "D1 p2", "doc_id": "a",
            "text": "Resumen — | Variable | Lote AB1 | Lote AB2 | |---|---|---| "
                    "| Rendimiento (t/ha) | 2,8 | 3,1 | | Costo (USD/ha) | 1.150 | 1.080 |"}]
    inv = compose.inventory(req, [src[0]["text"]])
    inv["table"] = True
    calls = []

    def gen(prompt, n):
        calls.append(prompt[:40])
        return "| Lote | Rendimiento (t/ha) | Costo (USD/ha) |" if "encabezado" in prompt else "NINGUNA"
    out = tables.build(req, src, inv, gen)
    assert out and out["rows_by_code"] == 2
    assert "| Lote AB1 | 2,8 | 1.150 | [D1 p2] |" in out["markdown"]
    assert "| Lote AB2 | 3,1 | 1.080 | [D1 p2] |" in out["markdown"]
    assert len(calls) == 1                     # no extraction by the model was needed


def test_a_list_that_repeats_the_built_table_is_left_out():
    from swarmbly_app import tables
    table = ("| Parcela | Cuaja con abejorros (%) | Fuente |\n|---|---|---|\n| Alta | 78 | [D2 p3] |\n"
             "| Media | 71 | [D2 p3] |\n| Baja | 61 (antes 64) | [D2 p3] [D1 p4] |")
    answer = ("La cuaja de las tres parcelas es la siguiente:\n\n- Parcela Alta: 78%\n- Parcela Media: 71%\n"
              "- Parcela Baja: 61% (antes 64%) [D1 p4]\n\nLa Baja bajó tras la muerte de dos colonias [D1 p4].")
    out = tables.drop_repeated_list(answer, table)
    assert "- Parcela Alta" not in out and "murte" not in out and "dos colonias" in out
    other = "Pasos siguientes:\n\n- Revisar las colonias cada semana.\n- Pedir presupuesto de cajas."
    assert tables.drop_repeated_list(other, table) == other
