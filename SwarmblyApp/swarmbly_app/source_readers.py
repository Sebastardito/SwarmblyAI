"""Plain text from the user's documents for LCE C1 (local only, read-only).

Text formats are decoded as UTF-8. Word (.docx) and HTML are read with the
standard library. PDF needs ``pdftotext`` (poppler), found on the PATH or in
the usual Homebrew folders; without it a PDF is listed as not readable and
the reason is shown, rather than silently ignored. Nothing is written and no
file leaves the device.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import zipfile
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

TEXT_SUFFIXES = frozenset({".md", ".txt", ".markdown", ".rst", ".org", ".csv"})
DOC_SUFFIXES = frozenset({".pdf", ".docx", ".html", ".htm"})
READABLE_SUFFIXES = TEXT_SUFFIXES | DOC_SUFFIXES
PDF_HINT = "pdftotext (poppler) is not installed: brew install poppler / apt install poppler-utils"


def pdftotext_path() -> str | None:
    found = shutil.which("pdftotext")
    if found:
        return found
    for d in ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"):
        if os.access(f"{d}/pdftotext", os.X_OK):
            return f"{d}/pdftotext"
    return None


def read_source(path: Path, data: bytes) -> tuple[str | None, str]:
    """``(text, "")`` or ``(None, reason)`` for a file's bytes."""
    suffix = path.suffix.lower()
    try:
        if suffix in TEXT_SUFFIXES:
            return data.decode("utf-8", "replace"), ""
        if suffix in (".html", ".htm"):
            return html_text(data.decode("utf-8", "replace")), ""
        if suffix == ".docx":
            return docx_text(data), ""
        if suffix == ".pdf":
            exe = pdftotext_path()
            if not exe:
                return None, PDF_HINT
            proc = subprocess.run([exe, "-enc", "UTF-8", "-", "-"], input=data,
                                  capture_output=True, timeout=120)
            if proc.returncode != 0:
                return None, (proc.stderr.decode("utf-8", "replace").strip() or "pdftotext failed")[:200]
            text = reflow(proc.stdout.decode("utf-8", "replace"))
            return (text, "") if text.strip() else (None, "no text layer (scanned PDF?)")
    except Exception as exc:          # a broken file must not break retrieval
        return None, str(exc)[:200]
    return None, "unsupported format"


def reflow(raw: str) -> str:
    """pdftotext lines → paragraphs separated by blank lines: joins wrapped
    lines, mends hyphenation, merges paragraphs split by a page break, drops
    page numbers and number-only debris."""
    import unicodedata
    # NFKC turns ligatures (the "fi" glyph in "Artificial") into letters a search matches
    raw = unicodedata.normalize("NFKC", raw).replace("\f", "\n\n").replace("\u00ad", "")
    paras, cur = [], []
    for line in raw.splitlines():
        s = " ".join(line.split())
        if not s:
            if cur:
                paras.append(cur)
                cur = []
            continue
        cur.append(s)
    if cur:
        paras.append(cur)
    out: list[str] = []
    for p in paras:
        text = ""
        for s in p:
            if text.endswith("-") and s[:1].islower():
                text = text[:-1] + s
            else:
                text = f"{text} {s}".strip()
        if re.fullmatch(r"[\d\s.,%±()\-–/]+", text) or not re.search(r"[^\W\d_]{3}", text):
            continue                  # page numbers, axis ticks
        if out and not re.search(r"[.!?:;)\]]$", out[-1]) and text[:1].islower():
            out[-1] += " " + text     # a paragraph broken by a page break
        else:
            out.append(text)
    return "\n\n".join(out)


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_text(data: bytes) -> str:
    """Paragraphs of a Word document (body text, headings and table rows)."""
    with zipfile.ZipFile(BytesIO(data)) as z:
        root = ElementTree.fromstring(z.read("word/document.xml"))
    body = root.find(f"{_W}body")
    out: list[str] = []
    for el in (body if body is not None else []):
        if el.tag == f"{_W}p":
            text = "".join(t.text or "" for t in el.iter(f"{_W}t")).strip()
            if text:
                out.append(text)
        elif el.tag == f"{_W}tbl":
            for row in el.iter(f"{_W}tr"):
                cells = ["".join(t.text or "" for t in c.iter(f"{_W}t")).strip()
                         for c in row.iter(f"{_W}tc")]
                if any(cells):
                    out.append(" | ".join(cells))
    return "\n\n".join(out)


class _HTMLText(HTMLParser):
    BLOCK = {"p", "div", "section", "article", "li", "tr", "br", "h1", "h2", "h3", "h4",
             "h5", "h6", "blockquote", "pre", "td", "th", "dd", "dt", "header", "footer"}
    SKIP = {"script", "style", "noscript", "template", "svg"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_text(html: str) -> str:
    parser = _HTMLText()
    parser.feed(html)
    blocks = [" ".join(b.split()) for b in "".join(parser.parts).split("\n\n")]
    return "\n\n".join(b for b in blocks if b)
