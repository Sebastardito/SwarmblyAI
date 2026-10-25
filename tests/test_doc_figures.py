"""Cada cifra vigente citada en los documentos sale de los JSON guardados."""

from lce_validation.doc_figures import expected, missing


def test_every_cited_figure_matches_the_stored_results():
    assert len(expected()) > 40
    assert missing() == []
