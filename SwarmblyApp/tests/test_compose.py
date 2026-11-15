"""3.2 grounded composition: F1 requirement inventory, F2 labels by code, F4 repair."""

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


_SRC = [
    {"label": "D1 p2", "text": "La germinación a los diez días fue del 87 % en la Parcela Norte, del 81 % en "
                               "la Parcela Sur y del 74 % en la Ladera Este."},
    {"label": "D2 p2", "text": "La germinación a los diez días fue del 90 % en la Parcela Norte, del 85 % en "
                               "la Parcela Sur y del 79 % en la Ladera Este."},
    {"label": "D1 p16", "text": "El rendimiento medio del lote AB1 fue de 2,37 t/ha. El costo de producción "
                                "fue de 1.150 dólares por hectárea."},
    {"label": "D2 p16", "text": "El rendimiento medio del lote AB2 fue de 2,53 t/ha. El costo de producción "
                                "fue de 1.080 dólares por hectárea."},
]


def test_attach_citations_traces_figures_to_passages():
    text = ("En la Parcela Norte, AB1 mostró una germinación del 87%, mientras que AB2 alcanzó el 90%. "
            "Estos datos indican que AB2 fue ligeramente mejor en todos los sitios.")
    out, attached = C.attach_citations(text, _SRC)
    assert "90% [D1 p2][D2 p2]." in out
    assert len(attached) == 1 and attached[0]["by"] == "figures"
    assert out.endswith("en todos los sitios.")          # no figures, few shared words: left alone


def test_attach_citations_accepts_a_computed_difference_but_not_an_invented_cause():
    text = ("El costo del lote AB1 fue de 1,150 USD/ha y el del lote AB2 de 1,080 USD/ha, una diferencia "
            "de 70 USD/ha. Esto se debe a que AB2 rindió más (2,53 frente a 2,37 t/ha), lo que abarató todo.")
    out, attached = C.attach_citations(text, _SRC)
    assert "70 USD/ha [D1 p16][D2 p16]." in out
    assert [a["labels"] for a in attached] == [["D1 p16", "D2 p16"]]


def test_attach_citations_leaves_tables_labels_and_outside_alone():
    text = ("| Sitio | AB1 |\n|---|---|\n| Norte | 87 % |\n\n"
            "La germinación de AB1 en la Parcela Norte fue del 87 % [D1 p2].\n\n"
            "Fuera de tus fuentes: la germinación de AB1 en la Parcela Sur fue del 81 % según otros.")
    out, attached = C.attach_citations(text, _SRC)
    assert out == text and attached == []


def test_repair_is_kept_only_when_closer_and_without_new_figures():
    inv = {"words": [30, 40], "table": False, "entities": [], "items": None}
    draft = "La germinación de AB1 fue del 87 % en la Parcela Norte [D1 p2]."
    longer = ("La germinación de AB1 fue del 87 % en la Parcela Norte, del 81 % en la Parcela Sur y del "
              "74 % en la Ladera Este [D1 p2]. La de AB2 fue mayor en los tres sitios: 90 %, 85 % y 79 % "
              "respectivamente [D2 p2].")
    invented = longer.replace("79 %", "77 %")
    passages = [s["text"] for s in _SRC]
    chk = C.check(draft, inv)
    assert C.needs_repair(chk) == "length"
    assert "entre 30 y 40" in C.repair_message(chk, "es")
    assert C.accept_repair(draft, longer, inv, passages) == (True, "")
    ok, why = C.accept_repair(draft, invented, inv, passages)
    assert not ok and "77" in why
    assert C.accept_repair(draft, draft, inv, passages)[0] is False


class _TwoReplies(FakeBackend):
    """The draft, and the longer text when the repair message comes."""
    def __init__(self, replies):
        super().__init__(reply=replies[0])
        self.replies = list(replies)

    def stream_chat(self, messages, **kw):
        self.reply = self.replies[1 if "Tu texto tiene" in messages[-1]["content"] else 0]
        return super().stream_chat(messages, **kw)


def test_f2_and_f4_in_the_chat(app_state, tmp_path):
    draft = "La germinación de AB1 fue del 87 % en la Parcela Norte y la de AB2 del 90 % en el mismo sitio."
    longer = ("La germinación de AB1 fue del 87 % en la Parcela Norte, del 81 % en la Parcela Sur y del 74 % "
              "en la Ladera Este. La de AB2 fue del 90 %, del 85 % y del 79 % en los mismos sitios, "
              "siempre algo mayor que la de AB1 en cada uno de los tres sitios del ensayo de este año.")
    fake = _TwoReplies([draft, longer])
    app_state.backends.resolve = lambda config=None: fake      # type: ignore[method-assign]
    p = app_state.projects.create("G", parent=tmp_path / "p")
    (p.sources / "ab1.md").write_text(_SRC[0]["text"] + "\n", encoding="utf-8")
    (p.sources / "ab2.md").write_text(_SRC[1]["text"] + "\n", encoding="utf-8")
    app_state.config.update({"lce.enabled": True, "lce.level": "C1", "compose.repair": True,
                             "compose.attach_citations": True})
    conv = app_state.chat.create_conversation(mode="local", project_id=p.id)
    app_state.chat.send(conv["id"], "Escribe un párrafo de 40 a 60 palabras que compare la germinación "
                        "de AB1 y AB2 en cada sitio.", mode="local", run_async=False)
    msg = app_state.chat.get_messages(conv["id"])[-1]
    meta = msg["meta"]
    assert meta["repair"]["kept"] is True
    assert "Tu texto tiene" in fake.calls[-1]["messages"][-1]["content"]
    assert meta["repair"]["before"]["ok"] is False and meta["repair"]["after"]["ok"] is True
    assert meta["citations_attached"] and "[D" in msg["content"]
    system = " ".join(m["content"] for m in fake.calls[-1]["messages"] if m["role"] == "system")
    assert "Requisitos de esta solicitud" not in system          # the checklist needs compose.inventory


def test_attach_citations_years_order_and_brackets():
    src = _SRC + [{"label": "D3 p1", "text": "Informe de la temporada 2025-2026 de los lotes AB1 y AB2."},
                  {"label": "D3 p2", "text": "Calendario de siembra 2025-2026 para la cooperativa."}]
    out, attached = C.attach_citations(
        "En esta comparación de los lotes se analizan las parcelas durante la temporada 2025-2026. "
        "En la Parcela Sur, AB2 tuvo 85 % y AB1 81 % de germinación a los diez días. "
        "Marta presentará una enmienda para bajar el pH del sector (D1 p2).", [*src[1:], src[0]])
    assert "temporada 2025-2026." in out                       # years alone, few shared words
    assert "81 % de germinación a los diez días [D2 p2][D1 p2]." in out
    assert "(D1 p2)" not in out and "sector [D1 p2]." in out
    assert [a["by"] for a in attached] == ["format", "figures"]
