"""C1 retrieval over folders (moved from Swarmbly App in 0.2.0). Fictitious data."""

from __future__ import annotations

import shutil

from swarmbly_lce.c1 import SourceIndex, citation, parse_citation
from swarmbly_lce.c1 import passages as P

CV = """# CV de Ana Pérez Rojas

Coordinadora de Calidad de Datos — AcmeLabs — 2022 – presente

Dirige la validación de datos genómicos y el control de calidad de los lotes de secuenciación.

Analista de Datos — Laboratorio Norte — 2018 – 2022

Mantuvo las bases de datos de muestras de campo y los informes trimestrales.
"""

NOTE = """# Nota de campo 2025

El rascón ficticio se observó en tres lagunas del altiplano durante el muestreo de marzo.
"""


def _folder(tmp_path, name="docs"):
    root = tmp_path / name
    root.mkdir()
    (root / "cv_ana.md").write_text(CV, encoding="utf-8")
    (root / "notas").mkdir()
    (root / "notas" / "campo_2025.md").write_text(NOTE, encoding="utf-8")
    (root / "glosario.md").write_text("rascón ficticio = Rallus fictus\n", encoding="utf-8")
    (root / ".oculto.md").write_text("no debe leerse\n", encoding="utf-8")
    return root


def test_paragraphs_keep_heading_with_the_paragraph_below():
    spans = P.paragraphs("cv_ana.md", CV)
    assert spans[0]["text"].startswith("Coordinadora de Calidad de Datos — AcmeLabs")
    assert "validación de datos genómicos" in spans[0]["text"]


def test_retrieval_cites_stable_ids(tmp_path):
    root = _folder(tmp_path)
    index = SourceIndex()
    hits = index.retrieve([root], "¿Desde cuándo coordino la calidad de datos?", k=2)
    assert hits and hits[0]["source"] == "cv_ana.md"
    assert hits[0]["rel"] == "cv_ana.md" and hits[0]["anchor"] == "p1"
    assert parse_citation(hits[0]["cite"]) == (hits[0]["doc_id"], "p1")
    assert all("oculto" not in h["text"] for h in hits)


def test_glossary_widens_the_query_and_is_not_a_passage(tmp_path):
    root = _folder(tmp_path)
    index = SourceIndex()
    assert index.glossary_terms("¿Dónde vimos el rascón ficticio?", [root]) == "Rallus fictus"
    assert index.glossary_terms("Rallus fictus", [root]) == "rascón ficticio"
    names = {s["name"]: s for s in index.list_sources([root])}
    assert names["glosario.md"]["glossary"] and names["glosario.md"]["passages"] == 0
    assert names["campo_2025.md"]["rel"] == "notas/campo_2025.md"
    assert ".oculto.md" not in names


def test_citation_survives_a_move_and_dies_with_an_edit(tmp_path):
    root = _folder(tmp_path)
    index = SourceIndex()
    cite = index.retrieve([root], "rascón altiplano lagunas", k=1)[0]["cite"]
    moved = tmp_path / "otra_computadora" / "proyecto"
    shutil.copytree(root, moved)
    fresh = SourceIndex()                      # another app, another path
    found = fresh.resolve([moved], cite)
    assert found and "tres lagunas" in found["text"] and found["rel"] == "notas/campo_2025.md"
    (moved / "notas" / "campo_2025.md").write_text(NOTE + "\nAñadido.\n", encoding="utf-8")
    assert fresh.resolve([moved], cite) is None


def test_skip_rule_and_roots_stay_apart(tmp_path):
    a, b = _folder(tmp_path, "a"), tmp_path / "b"
    b.mkdir()
    (b / "README.md").write_text("Instrucciones de la carpeta, no un documento.\n", encoding="utf-8")
    (b / "informe.md").write_text("El informe del proyecto B trata de lotes de semillas.\n",
                                  encoding="utf-8")
    index = SourceIndex(skip=lambda root, path: path.name == "README.md")
    assert {h["source"] for h in index.retrieve([b], "informe lotes semillas", k=4)} == {"informe.md"}
    assert all(h["source"] != "informe.md" for h in index.retrieve([a], "lotes", k=4))
    assert {s["name"] for s in index.list_sources([b])} == {"informe.md"}


def test_unreadable_files_are_reported(tmp_path):
    root = tmp_path / "docs"
    root.mkdir()
    (root / "roto.docx").write_bytes(b"not a zip")
    index = SourceIndex()
    entry = index.list_sources([root])[0]
    assert entry["passages"] == 0 and entry.get("unreadable")
    assert citation({"doc_id": "abc", "anchor": "p2"}) == "doc:abc#p2"


def test_pdf_without_pdftotext_is_read_with_pypdf(tmp_path, monkeypatch):
    import pytest
    pytest.importorskip("pypdf")
    reportlab = pytest.importorskip("reportlab.pdfgen.canvas")
    from swarmbly_lce.c1 import readers
    path = tmp_path / "manual.pdf"
    c = reportlab.Canvas(str(path))
    c.drawString(72, 720, "Instrucciones de acceso movil al equipo ficticio AB1.")
    c.drawString(72, 700, "Descarga la aplicacion de escritorio remoto y usa la clave del laboratorio.")
    c.save()
    monkeypatch.setattr(readers, "pdftotext_path", lambda: None)
    text, reason = readers.read_source(path, path.read_bytes())
    assert reason == "" and "acceso movil" in text
    hits = SourceIndex().retrieve([tmp_path], "acceso movil AB1 escritorio remoto", k=1)
    assert hits and hits[0]["source"] == "manual.pdf"


def test_dense_fusion_leaves_out_unrelated_passages(tmp_path):
    root = tmp_path / "docs"
    root.mkdir()
    (root / "manual.md").write_text(
        "Descarga la aplicación de acceso remoto y el visor VNC en el móvil.\n\n"
        "Desactiva la VPN del móvil cuando no uses la unidad de cría AB1.\n", encoding="utf-8")
    (root / "notas.md").write_text("Me gusta el color naranja y mi nombre es Ana.\n",
                                   encoding="utf-8")

    def embed(texts, kind):        # toy vectors: "remote" topic vs "personal" topic
        out = []
        for t in texts:
            t = t.lower()
            remote = sum(w in t for w in ("vnc", "remoto", "móvil", "vpn", "aplicaciones", "app"))
            personal = sum(w in t for w in ("naranja", "nombre", "color"))
            out.append([float(remote), float(personal), 0.1])
        return out
    index = SourceIndex()
    hits = index.retrieve([root], "¿Qué aplicaciones necesito?", k=4, embed=embed)
    assert hits and {h["source"] for h in hits} == {"manual.md"}


def test_any_equivalent_brings_the_term(tmp_path):
    root = tmp_path / "docs"
    root.mkdir()
    (root / "glosario.md").write_text("cucujo = cucuyo, Pyrophorus, Elateridae\n", encoding="utf-8")
    index = SourceIndex()
    assert index.glossary_terms("¿Qué es un cucuyo?", [root]) == "cucuyo, Pyrophorus, Elateridae cucujo"
    assert index.glossary_terms("el cucujo brilla", [root]) == "cucuyo, Pyrophorus, Elateridae"
    assert index.glossary_terms("un pez", [root]) == ""


def test_corrected_forms_are_never_equivalents(tmp_path):
    root = tmp_path / "docs"
    root.mkdir()
    (root / "glosario.md").write_text("introgresión = introgression | no: introgradión, introgracion\n"
                                      "TRU = Trial Rearing Unit\n", encoding="utf-8")
    index = SourceIndex()
    assert index.glossary_avoid([root]) == {"introgradión": "introgresión", "introgracion": "introgresión"}
    assert ("introgresión", "introgression") in index.glossary_entries([root])
    assert "introgradión" not in index.glossary_terms("¿Qué es la introgresión?", [root])
    assert index.glossary_terms("¿Qué es la introgresión?", [root]) == "introgression"
