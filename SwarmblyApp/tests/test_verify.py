"""3.3, recipe 3: labelled sentences checked against the paragraphs they cite."""

from __future__ import annotations

from conftest import FakeBackend
from swarmbly_app import verify as V
from swarmbly_app.inference.base import GenerationResult

TABLE = ("| Sitio | Repeticiones | Rendimiento medio (t/ha) | Desviación estándar | |---|---|---|---| "
         "| Parcela Norte | 4 | 2,8 | 0,3 | | Parcela Sur | 4 | 2,4 | 0,4 |")     # on one line, as the search gives it
SOURCES = [
    {"label": "D1 p16", "rel": "informe_lote_AB1.md", "text": TABLE},
    {"label": "D1 p17", "rel": "informe_lote_AB1.md",
     "text": "El rendimiento medio del lote AB1 en los tres sitios fue de 2,37 t/ha. El costo de producción "
             "fue de 1.150 dólares por hectárea."},
    {"label": "D2 p16", "rel": "informe_lote_AB2.md",
     "text": "| Sitio | Repeticiones | Rendimiento medio (t/ha) |\n|---|---|---|\n| Parcela Norte | 4 | 3,1 |\n| Parcela Sur | 4 | 2,2 |"},
    {"label": "D2 p17", "rel": "informe_lote_AB2.md", "text": "El costo de producción fue de 1.080 dólares por hectárea."},
    {"label": "D2 p9", "rel": "informe_lote_AB2.md",
     "text": "| Fecha | Mínima (°C) | Máxima (°C) | Lluvia (mm) |\n|---|---|---|---|\n| 1 de marzo | 12 | 22 | 70 |"},
    {"label": "D3 p3", "rel": "acta_reunion_abril.md", "doc_title": "Acta de la reunión técnica del 15 de abril de 2026",
     "text": "Jorge Salas informó del estado del presupuesto de la temporada y del calendario de compras."},
    {"label": "D3 p4", "rel": "acta_reunion_abril.md", "doc_title": "Acta de la reunión técnica del 15 de abril de 2026",
     "text": "1. Se acordó aplicar 40 kg N/ha en el sector oeste de la Parcela Sur antes de la siembra de 2027. "
             "3. Marta Ibáñez presentará en junio una propuesta de enmienda para bajar el pH."},
    {"label": "W1", "title": "Registro público de variedades: Kanela",
     "snippet": "Su rendimiento de referencia en el registro es de 2,6 t/ha."},
]


def test_sentences_with_a_label_are_the_claims():
    answer = ("# Informe\n\nSegún el informe [D1 p16], el rendimiento medio fue de 2,37 t/ha. Fue un buen año.\n\n"
              "| Sitio | t/ha | Fuente |\n|---|---|---|\n| Parcela Norte | 2,8 | [D1 p16] |\n\n"
              "El costo fue de 1.150 dólares. [D1 p17] La referencia pública es de 2,6 t/ha [W1].\n\n"
              "Fuera de tus fuentes: la quinua es un cultivo andino [D1 p2].")
    claims = V.split(answer)
    assert [c["labels"] for c in claims] == [["D1 p16"], ["D1 p17"], ["W1"]]
    assert claims[1]["text"].startswith("El costo fue")       # a label after the full stop belongs to its sentence


def test_a_figure_has_to_be_in_the_paragraph_the_sentence_cites():
    # in no paragraph that was given: flagged
    public = V.check("El registro da un rendimiento de referencia de 3,6 t/ha [W1].", ["W1"], SOURCES)
    assert public["ok"] is False and public["why"] == "figure_not_in_cited" and public["figures"] == ["3.6"]
    right = V.check("La Parcela Norte rindió 2,8 t/ha y la Parcela Sur 2,4 t/ha [D1 p16].", ["D1 p16"], SOURCES)
    assert right["ok"] is None and right["by"] == "code" and "added" not in right    # nothing against it
    # a difference of two figures the paragraphs give needs no paragraph of its own
    # (a rain table that happens to hold a 70 is not where it comes from)
    diff = V.by_code("AB1 costó 1.150 dólares y AB2 1.080, una diferencia de 70 dólares [D1 p17][D2 p17].",
                     ["D1 p17", "D2 p17"], SOURCES)
    assert diff["missing_figures"] == [] and diff["derived"] == ["70"] and diff["complete"] == []
    # the date of the meeting is in the title of the minutes
    dated = V.check("En la reunión del 15 de abril de 2026 se acordó aplicar 40 kg N/ha [D3 p4].", ["D3 p4"], SOURCES)
    assert dated["ok"] is None and "added" not in dated


def test_a_citation_is_completed_with_the_paragraph_that_has_the_figure():
    # the fact is right, its citation is not: 2,37 is in the next paragraph
    wrong = V.check("Según el informe [D1 p16], el rendimiento medio del lote AB1 fue de 2,37 t/ha.", ["D1 p16"], SOURCES)
    assert wrong["ok"] is None and wrong["added"] == ["D1 p17"]
    # 3,1 is in AB2's table, though it is also 2,8 plus the 0,3 of a deviation in the cited one
    both = V.check("En la Parcela Norte, el rendimiento medio del lote AB2 fue de 3,1 t/ha, 0,3 más que el AB1, "
                   "con 2,8 [D1 p16].", ["D1 p16"], SOURCES)
    assert both["added"] == ["D2 p16"]
    seen = []
    V.check("En la Parcela Norte, el rendimiento medio del lote AB2 fue de 3,1 t/ha, 0,3 más que el AB1, con 2,8 [D1 p16].",
            ["D1 p16"], SOURCES, lambda prompt, n: seen.append(prompt) or "SÍ")
    assert "[D2 p16] (informe lote AB2)" in seen[0] and "Nota: 0,3 se calcula" in seen[0]
    # the model is told which figures the code computed
    V.check("AB1 costó 1.150 dólares y AB2 1.080, una diferencia de 70 dólares [D1 p17][D2 p17].",
            ["D1 p17", "D2 p17"], SOURCES, lambda prompt, n: seen.append(prompt) or "SÍ")
    assert "Nota: 70 se calcula con cifras de los párrafos" in seen[1]
    assert V._with_labels("Rindió 3,1 t/ha [D1 p16].", ["D2 p16"]) == "Rindió 3,1 t/ha [D1 p16][D2 p16]."


def test_a_paragraph_about_something_else_and_a_label_that_was_not_given():
    other = V.check("Esto nos ayudará a optimizar la nutrición de nuestras plantas [D3 p3].", ["D3 p3"], SOURCES)
    assert other["ok"] is False and other["why"] == "unrelated_paragraph"
    unknown = V.check("La cosecha se hará en la segunda semana de junio [D9 p2].", ["D9 p2"], SOURCES)
    assert unknown["ok"] is False and unknown["why"] == "unknown_label"


def test_the_model_reads_the_cited_paragraphs_only_and_answers_with_one_word():
    asked = []

    def judge(prompt, max_tokens):
        asked.append((prompt, max_tokens))
        return "PARTE: dicen una parte" if "presentó" in prompt else "Sí."

    sentence = "Marta Ibáñez presentó una propuesta para bajar el pH [D3 p4]."
    out = V.check(sentence, ["D3 p4"], SOURCES, judge)
    assert out["ok"] is False and out["why"] == "partly" and out["by"] == "model"
    prompt, max_tokens = asked[0]
    assert max_tokens <= 8
    assert "[D3 p4] (Acta de la reunión técnica del 15 de abril de 2026)" in prompt
    assert "presupuesto" not in prompt and "1.150" not in prompt          # only what the sentence cites
    assert f"Frase: {sentence}" in prompt
    ok = V.check("Se acordó aplicar 40 kg N/ha en el sector oeste de la Parcela Sur [D3 p4].", ["D3 p4"], SOURCES, judge)
    assert ok["ok"] is True
    assert V.parse("SÍ") == V.YES and V.parse("**No**, no lo dicen") == V.NO and V.parse("Partly.") == V.PARTLY
    assert V.parse("Los párrafos…") is None
    # a table reaches the model with its lines
    assert "| Parcela Norte | 4 | 2,8 | 0,3 |\n" in V.prompt("La Parcela Norte rindió 2,8 [D1 p16].", ["D1 p16"], SOURCES)
    assert "Do the paragraphs say" in V.prompt("The north plot gave 2.8 [D1 p16].", ["D1 p16"], SOURCES, "en")


def test_the_report_counts_and_the_code_goes_first():
    asked = []

    def judge(prompt, max_tokens):
        asked.append(prompt)
        return "NO" if "optimizar" in prompt else "SÍ"

    answer = ("El rendimiento medio del lote AB1 fue de 2,37 t/ha [D1 p16]. La Parcela Norte rindió 2,8 t/ha [D1 p16]. "
              "El registro da un rendimiento de referencia de 3,6 t/ha [W1]. "
              "Se acordó aplicar 40 kg N/ha, lo que permitirá optimizar el cultivo [D3 p4].")
    report = V.verify(answer, SOURCES, judge)
    assert report["claims"] == 4 and report["supported"] == 2 and report["asked"] == 3    # the 3,6 never reached the model
    assert [f["why"] for f in report["flagged"]] == ["figure_not_in_cited", "not_in_cited"]
    assert report["completed"] == [{"text": "El rendimiento medio del lote AB1 fue de 2,37 t/ha [D1 p16].",
                                    "added": ["D1 p17"]}]
    assert report["text"].startswith("El rendimiento medio del lote AB1 fue de 2,37 t/ha [D1 p16][D1 p17]. La Parcela")
    assert report["text"].replace("[D1 p17]", "", 1) == answer                            # labels only
    # past the limit the sentences are left unchecked, not passed
    limited = V.verify(answer, SOURCES, judge, limit=1)
    assert limited["asked"] == 1 and limited["unchecked"] == 2
    # without a model the code still flags and completes
    alone = V.verify(answer, SOURCES)
    assert alone["asked"] == 0 and len(alone["flagged"]) == 1 and len(alone["completed"]) == 1


class _Writer(FakeBackend):
    """Writes the answer; as a verifier, says NO to the sentence with the opinion."""

    def stream_chat(self, messages, *, model, max_tokens=1024, **kw):
        prompt = messages[-1]["content"]
        self.calls.append({"messages": messages, "model": model, "max_tokens": max_tokens})
        if prompt.startswith("Párrafos:"):
            text = "NO" if "nos ayudará" in prompt else "SÍ"
        else:
            text = ("El costo de producción del lote AB1 fue de 1.150 dólares por hectárea [D1 p1]. "
                    "Ese costo de producción nos ayudará a planificar mejor la próxima temporada [D1 p1].")
        return GenerationResult(text=text, model=model, completion_tokens=len(text.split()), total_ms=5)


def test_verification_in_the_chat(app_state, tmp_path):
    fake = _Writer()
    app_state.backends.resolve = lambda config=None: fake      # type: ignore[method-assign]
    p = app_state.projects.create("T", parent=tmp_path / "p")
    (p.sources / "informe_lote_AB1.md").write_text(
        "# Informe de campo del lote AB1, temporada 2025-2026\n\nResponsable: Ana Pérez. Variedad Kanela.\n\n"
        "El costo de producción del lote AB1 fue de 1.150 dólares por hectárea.\n", encoding="utf-8")
    app_state.config.update({"lce.enabled": True, "lce.level": "C1", "compose.verify": True})
    conv = app_state.chat.create_conversation(mode="local", project_id=p.id)
    app_state.chat.send(conv["id"], "¿Cuánto costó producir el lote AB1?", mode="local", run_async=False)
    msg = app_state.chat.get_messages(conv["id"])[-1]
    found = msg["meta"]["verification"]
    assert found["claims"] == 2 and found["supported"] == 1 and found["asked"] == 2
    assert [f["why"] for f in found["flagged"]] == ["not_in_cited"]
    assert found["flagged"][0]["text"].startswith("Ese costo de producción nos ayudará")
    assert "nos ayudará" in msg["content"]                       # nothing is rewritten
    judged = [c["messages"][-1]["content"] for c in fake.calls if c["messages"][-1]["content"].startswith("Párrafos:")]
    assert judged and all("(Informe de campo del lote AB1, temporada 2025-2026)" in j for j in judged)
    assert not any("(Responsable" in j for j in judged)            # the first paragraph is not the title
    # off by default
    app_state.config.update({"compose.verify": False})
    conv = app_state.chat.create_conversation(mode="local", project_id=p.id)
    app_state.chat.send(conv["id"], "¿Cuánto costó producir el lote AB1?", mode="local", run_async=False)
    assert "verification" not in app_state.chat.get_messages(conv["id"])[-1]["meta"]


def test_what_the_sources_do_not_say_is_not_a_claim_and_computed_figures_are_named():
    answer = ("Según el informe [D1 p17], no se menciona clorosis en la Parcela Norte. "
              "En la Parcela Norte, el lote AB2 rindió 3,1 t/ha frente a 2,8 t/ha del AB1, una diferencia de 0,3 t/ha "
              "[D2 p16][D1 p16].")
    seen = []
    report = V.verify(answer, SOURCES, lambda prompt, n: seen.append(prompt) or "SÍ")
    assert report["claims"] == 1 and report["about_sources"] == 1 and report["asked"] == 1
    # 0,3 is also a deviation of the cited table; in the sentence it is 3,1 minus 2,8
    assert "Nota: 0,3 se calcula" in seen[0]
    assert V.split("Las fuentes no mencionan el riego [D1 p2].")[0]["absence"] is True
    assert "absence" not in V.split("Se observó clorosis en la Ladera Este, pero no en la Parcela Norte [D1 p11].")[0]


def test_several_labels_in_one_bracket_are_all_cited():
    claims = V.split("Ajustar nuestras prácticas será crucial para el próximo año [D1 p3, D1 p4; D1 p5].")
    assert claims[0]["labels"] == ["D1 p3", "D1 p4", "D1 p5"]


def test_figures_the_program_computed_and_sentences_on_disagreeing_sources():
    report = V.verify("El costo del lote AB1 fue de 1.150 dólares, un 6 % más que el de AB2 [D1 p17]. "
                      "Las fuentes no coinciden en este punto. [D1 p17]", SOURCES, computed=["70 6 %"])
    assert report["claims"] == 1 and report["about_sources"] == 1 and report["flagged"] == []
    flagged = V.verify("El costo del lote AB1 fue de 1.150 dólares, un 6 % más que el de AB2 [D1 p17].", SOURCES)
    assert flagged["flagged"][0]["figures"] == ["6"]


def test_saying_that_two_sources_disagree_is_about_the_sources():
    assert V.split("No coinciden en esta recomendación [D1 p6] [W1].")[0].get("absence") is True


def test_a_label_of_an_earlier_turn_and_more_sentences_about_the_sources():
    r = V.check("Se acordó aplicar 40 kg N/ha en el sector oeste [D7 p4].", ["D7 p4"], SOURCES, earlier={"D7 p4"})
    assert r["ok"] is None and r["why"] == "earlier_turn"
    assert V.check("Se acordó aplicar 40 kg N/ha en el sector oeste [D7 p4].", ["D7 p4"], SOURCES)["ok"] is False
    for s in ("Solo se indica que en la Parcela Sur se observó clorosis [D1 p11].",
              "No se encuentra información relevante sobre la variedad Zafira en la fuente consultada [W1]."):
        assert V.split(s)[0].get("absence") is True, s


# ---- 3.3: false alarms seen in the sealed banks v3 -------------------------------

def test_a_date_written_with_numbers_matches_the_paragraphs_month_name():
    sources = [{"label": "D3 p2", "rel": "acta_reunion.md",
                "text": "La cosecha se adelanta al 10 de enero de 2026 por acuerdo de la reunión."}]
    code = V.by_code("La cosecha se adelantó al 10/01/2026 según la reunión [D3 p2].", ["D3 p2"], sources)
    assert code["missing_figures"] == []
    code = V.by_code("La cosecha se adelantó al 12/01/2026 según la reunión [D3 p2].", ["D3 p2"], sources)
    assert code["missing_figures"] == ["12"]


def test_a_label_after_the_full_stop_counts_for_the_uncited_check():
    from swarmbly_app.chat import _unsupported
    answer = ("La cuaja de la parcela alta fue del 78 por ciento en el ensayo. [D1 p3] "
              "La parcela media quedó algo por debajo de ese valor. [D1 p3]")
    assert _unsupported(answer, []) == []
    assert V.sentences("Uno dos tres. [D1 p2] Cuatro cinco.") == ["Uno dos tres. [D1 p2]", "Cuatro cinco."]
