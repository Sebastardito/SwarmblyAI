"""3.2 grounded composition: F1, the requirement inventory."""

from __future__ import annotations

from conftest import FakeBackend
from swarmbly_app import compose as C

PASSAGES = ["El lote AB1 se sembró el 12 de febrero en tres sitios: Parcela Norte, Parcela Sur y Ladera Este.",
            "Se acordó aplicar 40 kg N/ha en el sector oeste."]


def test_compositions_are_told_apart_from_questions():
    assert C.is_composition("Escribe un informe de 300 a 400 palabras sobre AB1.")
    assert C.is_composition("Prepara una nota para el comité con las tres recomendaciones principales.")
    assert C.is_composition("Haz una tabla con el costo de AB1 y AB2.")
    assert not C.is_composition("¿Qué densidad de siembra se usó en el lote AB2?")
    assert not C.is_composition("¿Cuál es la capital de Perú?")


def test_the_inventory_reads_length_table_items_entities_and_audience():
    inv = C.inventory("Escribe un informe de 300 a 400 palabras que compare AB1 y AB2 en los tres sitios, "
                      "con una tabla.", PASSAGES)
    assert inv["words"] == [300, 400] and inv["table"]
    assert inv["entities"] == ["AB1", "AB2", "Parcela Norte", "Parcela Sur", "Ladera Este"]
    note = C.inventory("Prepara una nota de unas 200 palabras para el comité con las tres recomendaciones "
                       "principales.", PASSAGES)
    assert note["words"] == [170, 229] and note["items"] == {"n": 3, "noun": "recomendaciones"}
    assert note["audience"] == "el comité"
    each = C.inventory("Escribe un párrafo de 150 palabras sobre la germinación en cada sitio.", PASSAGES)
    assert {"Parcela Norte", "Ladera Este"} <= set(each["entities"])
    assert C.inventory("Resume en máximo 100 palabras el informe.", [])["words"] == [0, 100]


def test_the_checklist_and_the_check():
    inv = C.inventory("Prepara una nota de unas 200 palabras con las tres recomendaciones para AB1.", PASSAGES)
    text = C.checklist(inv)
    assert "entre 170 y 229 palabras" in text and "3 recomendaciones" in text and "no inventes" in text
    answer = ("Para el comité:\n\n1. Aplicar 40 kg N/ha en el sector oeste [D1 p3].\n"
              "2. No sembrar AB1 en la Ladera Este [D1 p3].\n\nEstas recomendaciones vienen de la reunión de abril "
              "y del análisis de suelo, sin otras fuentes en este momento.")
    out = C.check(answer, inv)
    assert out["items"] == {"want": 3, "got": 2, "ok": False}
    assert out["length"]["ok"] is False and out["entities"]["ok"] is True
    assert out["citations"]["ok"] is False and out["ok"] is False


def test_f1_is_off_by_default_and_on_with_its_setting(app_state, tmp_path):
    fake = FakeBackend(reply="1. Aplicar 40 kg N/ha [D1 p1].")
    app_state.backends.resolve = lambda config=None: fake      # type: ignore[method-assign]
    p = app_state.projects.create("C", parent=tmp_path / "p")
    (p.sources / "acta.md").write_text("Se acordó aplicar 40 kg N/ha en el sector oeste de la Parcela Sur.\n",
                                       encoding="utf-8")
    app_state.config.update({"lce.enabled": True, "lce.level": "C1"})
    q = "Prepara una nota de unas 200 palabras con las tres recomendaciones del acta."
    conv = app_state.chat.create_conversation(mode="local", project_id=p.id)
    app_state.chat.send(conv["id"], q, mode="local", run_async=False)
    system = " ".join(m["content"] for m in fake.calls[-1]["messages"] if m["role"] == "system")
    assert "Requisitos de esta solicitud" not in system
    assert "requirements" not in app_state.chat.get_messages(conv["id"])[-1]["meta"]
    app_state.config.update({"compose.inventory": True})
    conv = app_state.chat.create_conversation(mode="local", project_id=p.id)
    app_state.chat.send(conv["id"], q, mode="local", run_async=False)
    system = " ".join(m["content"] for m in fake.calls[-1]["messages"] if m["role"] == "system")
    assert "Requisitos de esta solicitud" in system and "3 recomendaciones" in system
    req = app_state.chat.get_messages(conv["id"])[-1]["meta"]["requirements"]
    assert req["check"]["items"]["got"] == 1 and req["check"]["ok"] is False
