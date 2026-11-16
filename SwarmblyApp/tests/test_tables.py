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
    system = " ".join(m["content"] for m in fake.calls[-1]["messages"] if m["role"] == "system")
    assert "ya armó esta tabla" in system
