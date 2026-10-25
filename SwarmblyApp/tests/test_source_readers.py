"""LCE C1 source readers: Word, HTML, PDF reflow, and unreadable files listed with a reason."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from swarmbly_app import source_readers as sr
from swarmbly_app.lce_adapter import LCEAdapter
from swarmbly_app.paths import DataDirs

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _docx(paragraphs, rows=()):
    from xml.sax.saxutils import escape
    paragraphs = [escape(p) for p in paragraphs]
    rows = [[escape(c) for c in r] for r in rows]
    body = "".join(f'<w:p><w:r><w:t>{p}</w:t></w:r></w:p>' for p in paragraphs)
    if rows:
        body += "<w:tbl>" + "".join(
            "<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t>{c}</w:t></w:r></w:p></w:tc>" for c in r) + "</w:tr>"
            for r in rows) + "</w:tbl>"
    xml = f'<?xml version="1.0"?><w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


def test_docx_paragraphs_and_table_rows():
    text, why = sr.read_source(Path("perfil.docx"), _docx(
        ["Gerente de I+D (R&D Manager)", "Lideré el programa de la mosca soldado negra."],
        rows=[["2014", "PUCE"]]))
    assert why == "" and text.split("\n\n") == [
        "Gerente de I+D (R&D Manager)", "Lideré el programa de la mosca soldado negra.", "2014 | PUCE"]


def test_html_blocks_without_scripts():
    text, _ = sr.read_source(Path("a.html"), b"<html><script>x=1</script><h1>Title</h1>"
                                            b"<p>First <b>para</b>.</p><p>Second.</p></html>")
    assert text.split("\n\n") == ["Title", "First para.", "Second."]


def test_pdf_reflow_joins_lines_mends_hyphens_and_drops_page_numbers():
    assert sr.reflow("Inteligencia Arti\ufb01cial distribuida") == "Inteligencia Artificial distribuida"
    out = sr.reflow("A heading\n\nThe effective popu-\nlation size\n\n12\n\fwas small.")
    assert out == "A heading\n\nThe effective population size was small."


def test_pdf_without_pdftotext_is_listed_with_the_reason(tmp_path, monkeypatch):
    monkeypatch.setattr(sr, "pdftotext_path", lambda: None)
    d = DataDirs(tmp_path / "data")
    d.ensure()
    (d.sources / "tesis.pdf").write_bytes(b"%PDF-1.4 fake")
    (d.sources / "notas.md").write_text("Una nota larga sobre los cucuves de Floreana y su historia.",
                                        encoding="utf-8")
    (d.sources / "glosario.md").write_text("cucuve = mockingbird", encoding="utf-8")
    listing = {f["name"]: f for f in LCEAdapter(d).list_sources()}
    assert listing["tesis.pdf"]["passages"] == 0 and "pdftotext" in listing["tesis.pdf"]["unreadable"]
    assert listing["notas.md"]["passages"] == 1 and "unreadable" not in listing["notas.md"]
    assert listing["glosario.md"]["glossary"] is True


def test_word_file_is_retrieved(tmp_path):
    d = DataDirs(tmp_path / "data")
    d.ensure()
    (d.sources / "perfil.docx").write_bytes(_docx(
        ["Gerente de I+D (R&D Manager) — Sep 2024", "AcmeLabs Inc.",
         "Lideré los programas de mejoramiento de la mosca soldado negra con un equipo de doce personas."]))
    hits = LCEAdapter(d).retrieve("¿Qué cargo ocupé en AcmeLabs y con qué insecto?", k=2)
    assert hits and "Gerente de I+D" in hits[0]["text"] and "mosca soldado negra" in hits[0]["text"]
