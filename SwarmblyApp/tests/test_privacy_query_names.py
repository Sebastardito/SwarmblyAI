"""T11.1: a private name is private in every form, the public entity survives.

Neutral fixtures only: a bird-ringing site, ``Roca Tiburcia``, and a public
coastal station, ``Marisma Alta``.  The private site appears in one project
document that calls it private, and in no document in the other cases.
"""

from __future__ import annotations

from swarmbly_app import recipes as R
from swarmbly_app import web_search as W
from swarmbly_app.memory_capture import split_private_mark
from swarmbly_app.lce_adapter import _table_private_rows

DOC = ("Nuestro punto privado Roca Tiburcia queda en la quebrada; "
       "allí anillamos aves durante la migración.")


def _words(text: str) -> list[str]:
    return str(text or "").split()


def test_a_sentence_initial_fragment_is_removed_and_the_public_entity_kept():
    question = ("Tiburcia anilló muchos pájaros en marzo; ¿el registro público "
                "de Marisma Alta dice algo de anillamiento?")
    detail = W.propose_query_details(question, passages=[DOC])
    assert "Tiburcia" not in _words(detail["query"])
    assert "Marisma" in detail["query"] and "Alta" in detail["query"]
    assert detail["removed_terms"] == ["Tiburcia"]
    assert "Marisma Alta" not in detail["removed_terms"]


def test_the_same_fragment_is_removed_when_no_document_mentions_the_name():
    question = ("Tiburcia anilló muchos pájaros en marzo; ¿el registro público "
                "de Marisma Alta dice algo de anillamiento?")
    detail = R.propose_query_details(question)
    assert "Tiburcia" not in _words(detail["query"])
    assert "Marisma Alta" in detail["query"]
    assert detail["removed_terms"] == ["Tiburcia"]


def test_a_fragment_after_a_possessive_is_removed_and_reported():
    detail = R.propose_query_details(
        "Mi Tiburcia registra aves; compara Marisma Alta con el registro público.")
    assert "Tiburcia" not in _words(detail["query"])
    assert "Marisma Alta" in detail["query"]
    assert detail["removed_terms"] == ["Tiburcia"]


def test_a_quoted_private_name_is_removed_and_the_public_entity_kept():
    detail = R.propose_query_details(
        "¿Qué diferencia hay entre «Roca Tiburcia» y el dato público de Marisma Alta?")
    assert "Roca" not in _words(detail["query"])
    assert "Tiburcia" not in _words(detail["query"])
    assert "Marisma Alta" in detail["query"]
    assert detail["removed_terms"] == ["Roca Tiburcia"]


def test_the_public_entity_after_compara_survives_a_private_name():
    detail = R.propose_query_details(
        "Roca Tiburcia es importante para mí; compara Marisma Alta con su "
        "registro público de 2025.")
    assert "Roca" not in _words(detail["query"])
    assert "Tiburcia" not in _words(detail["query"])
    assert "Marisma Alta" in detail["query"]
    assert detail["removed_terms"] == ["Roca Tiburcia"]


def test_the_public_entity_after_a_colon_survives():
    detail = R.propose_query_details(
        "Mi Roca Tiburcia describe otra cosa: contrasta Marisma Alta con el "
        "registro público actual.")
    assert "Roca" not in _words(detail["query"])
    assert "Tiburcia" not in _words(detail["query"])
    assert "describe" not in detail["removed_terms"]
    assert "Marisma Alta" in detail["query"]
    assert detail["removed_terms"] == ["Roca Tiburcia"]


def test_the_public_entity_at_the_end_after_de_survives():
    detail = R.propose_query_details(
        "Roca Tiburcia está en mi contexto; verifica la diferencia entre "
        "Marisma Alta interno y público sin compartir lo privado.")
    assert "Roca" not in _words(detail["query"])
    assert "Tiburcia" not in _words(detail["query"])
    assert "Marisma Alta" in detail["query"]
    assert detail["removed_terms"] == ["Roca Tiburcia"]


def test_a_private_run_never_crosses_a_comma_into_a_public_name():
    detail = R.propose_query_details("Mi estación Roca Tiburcia, Marisma Alta")
    for term in detail["removed_terms"]:
        assert not ("Roca" in term and "Marisma" in term), term
    assert "Roca" not in _words(detail["query"])
    assert "Tiburcia" not in _words(detail["query"])


def test_the_full_name_in_a_private_document_removes_a_bare_fragment():
    question = "Tiburcia aparece en el registro de anillamiento de marzo."
    detail = W.propose_query_details(question, passages=[DOC])
    assert "Tiburcia" not in _words(detail["query"])
    assert "Tiburcia" in detail["removed"]


# ---- T11.1: a Markdown table's third column says private ---------------------

TABLE = """| Término | Definición | Estado |
|---|---|---|
| Roca Tiburcia | Sitio propio de anillamiento | privado |
| Marisma Alta | Estación costera de conteo | público |
"""


def test_a_private_markdown_table_row_is_private_app_side(app_state, tmp_path):
    project = app_state.projects.create("Aves", parent=tmp_path / "p")
    (project.memory / "glosario.md").write_text(TABLE, encoding="utf-8")
    roots = project.roots()
    assert app_state.lce.glossary_private_terms(roots=roots) == ["Roca Tiburcia"]
    entries = app_state.lce.glossary_entries(roots=roots)
    assert ("Roca Tiburcia", "Sitio propio de anillamiento | privado") in entries
    assert ("Marisma Alta", "Estación costera de conteo") in entries
    detail = R.propose_query_details(
        "Roca Tiburcia y Marisma Alta: ¿qué dice el registro público de Marisma Alta?",
        entries)
    assert "Roca" not in _words(detail["query"])
    assert "Tiburcia" not in _words(detail["query"])
    assert "Sitio" not in _words(detail["query"])
    assert "Marisma Alta" in detail["query"]
    assert "Roca Tiburcia" in detail["removed_terms"]
    assert "Marisma Alta" not in detail["removed_terms"]


def test_the_third_column_variants_are_all_private():
    variants = [
        "| Término | Definición | Estado |\n|---|---|---|\n"
        "| Boya Azul | Fondeadero | PRIVATE |\n",
        "| Término | Definición | privado |\n|---|---|---|\n"
        "| Boya Azul | Fondeadero | sí |\n",
        "| Término | Definición | notas |\n|---|---|---|\n"
        "| Boya Azul | Fondeadero | privado: sí |\n",
    ]
    for text in variants:
        rows = _table_private_rows(text)
        assert rows and rows[0][0] == "Boya Azul", text
        assert rows[0][1] == "Fondeadero", text


def test_a_line_suffix_and_equals_form_stay_private():
    assert split_private_mark("Boya Azul | privado") == ("Boya Azul", True)
    assert split_private_mark("Boya Azul = Fondeadero | privado") == \
        ("Boya Azul = Fondeadero", True)
    assert split_private_mark("Boya Azul = Fondeadero | privado: no") == \
        ("Boya Azul = Fondeadero", False)


def test_the_query_api_reads_a_private_name_from_the_project_documents(
        app_state, tmp_path):
    from test_api_lce import make_client

    project = app_state.projects.create("Aves", parent=tmp_path / "p")
    (project.sources / "nota.md").write_text(DOC, encoding="utf-8")
    client = make_client(app_state)
    body = client.post("/api/recipes/query", json={
        "text": "Tiburcia anilló muchos pájaros en marzo; ¿el registro público "
                "de Marisma Alta dice algo?",
        "project_id": project.id}).json()
    assert "Tiburcia" not in _words(body["query"])
    assert "Marisma Alta" in body["query"]
    assert "Tiburcia" in body["removed_terms"]


ENTITY_DOC = DOC + (" El registro público de Marisma Alta se publica cada año.")


def test_project_passages_do_not_split_or_reorder_the_public_entity():
    """Regression: a capitalised entity word ending in -a was read as a genus
    from the passages, splitting "Marisma Alta" and reversing its words."""
    cases = {
        "Roca Tiburcia es importante para mí; compara Marisma Alta con su "
        "registro público de 2025.":
            "Marisma Alta registro público 2025",
        "Mi Roca Tiburcia describe otra cosa: contrasta Marisma Alta con el "
        "registro público actual.":
            "Marisma Alta registro público actual",
        "¿Qué diferencia hay entre «Roca Tiburcia» y el dato público de Marisma Alta?":
            "dato público Marisma Alta",
        "Tiburcia anilló mi ave; compara nuestra cobertura de Marisma Alta con "
        "el registro público.":
            "Marisma Alta registro público",
        "Roca Tiburcia está en mi contexto; verifica la diferencia entre "
        "Marisma Alta interno y público sin compartir lo privado.":
            "Marisma Alta interno público",
    }
    for question, expected in cases.items():
        without = W.propose_query_details(question)
        with_docs = W.propose_query_details(question, passages=[ENTITY_DOC])
        assert with_docs["query"] == expected, question
        assert with_docs["query"] == without["query"], question
        words = with_docs["query"].split()
        assert words.index("Marisma") + 1 == words.index("Alta"), question
        assert "Roca" not in words and "Tiburcia" not in words, question
        assert with_docs["removed_terms"] == ["Roca Tiburcia"] or \
            with_docs["removed_terms"] == ["Tiburcia"], question


def test_a_sentence_initial_imperative_is_not_glued_to_a_private_term():
    question = "Georreferencia Roca Tiburcia en el registro público de Marisma Alta."
    detail = W.propose_query_details(
        question, glossary=[("Roca Tiburcia", "Sitio privado | privado")])
    assert detail["removed_terms"] == ["Roca Tiburcia"]
    assert "Georreferencia" not in detail["removed"]
    assert "Roca" not in detail["query"] and "Tiburcia" not in detail["query"]
