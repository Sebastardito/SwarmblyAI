#!/usr/bin/env python3
"""Build the whitepaper PDFs (pandoc -> HTML5 -> headless Chromium).

Same stylesheet and engine as the Swarmbly whitepaper v2 PDFs. The YAML front
matter (status/lang) is stripped before conversion so it does not print as
text, and the PDF metadata (title, author, subject, keywords) is set afterwards.

Requirements: pandoc, playwright (with a Chromium build), pypdf.
Usage:  python scripts/build_pdfs.py            # both v0.2 whitepapers (v0.1 is frozen)
        python scripts/build_pdfs.py docs/X.md  # specific files
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTHOR = "Sebastián A. Espinoza-Ulloa"
KEYWORDS = "local-first; personalization; small language models; continual learning; LoRA; model collapse; cultural evolution; population genetics; decentralized AI; Swarmbly"
META = {
    "WHITEPAPER_LCE_EN": ("Local Cognition and Anchored Transmission", "Swarmbly LCE — whitepaper v0.1, draft (2026-10-04)"),
    "WHITEPAPER_LCE_ES": ("Cognición local y transmisión anclada", "Swarmbly LCE — whitepaper v0.1, borrador (2026-10-04)"),
    "WHITEPAPER_LCE_v0.2_EN": ("Local Cognition and Anchored Transmission", "Swarmbly LCE — whitepaper v0.2, draft with results (2026-10-11)"),
    "WHITEPAPER_LCE_v0.2_ES": ("Cognición local y transmisión anclada", "Swarmbly LCE — whitepaper v0.2, borrador con resultados (2026-10-11)"),
}

CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm; }
body { font-family: "DejaVu Serif", Georgia, serif; font-size: 10.5pt; line-height: 1.45; color: #111; }
h1 { font-size: 19pt; line-height: 1.2; margin: 0 0 0.4em 0; }
h2 { font-size: 14pt; margin: 1.4em 0 0.4em 0; border-bottom: 1px solid #ccc; padding-bottom: 2px; break-after: avoid; }
h3 { font-size: 11.5pt; margin: 1.1em 0 0.3em 0; break-after: avoid; }
h4 { font-size: 10.5pt; margin: 0.9em 0 0.2em 0; break-after: avoid; }
p { margin: 0 0 0.6em 0; text-align: justify; hyphens: auto; }
code, pre { font-family: "DejaVu Sans Mono", monospace; font-size: 8.8pt; }
pre { background: #f6f6f6; border: 1px solid #e0e0e0; padding: 6px 8px; white-space: pre-wrap; word-wrap: break-word; font-size: 7.4pt; line-height: 1.25; break-inside: avoid; }
table { border-collapse: collapse; width: 100%; font-size: 9.2pt; margin: 0.5em 0 0.9em 0; }
tr { break-inside: avoid; }
th, td { border: 1px solid #ccc; padding: 3px 6px; text-align: left; vertical-align: top; }
th { background: #f0f0f0; }
blockquote { border-left: 3px solid #ccc; margin: 0.5em 0; padding: 0.2em 0 0.2em 10px; color: #333; }
hr { border: 0; border-top: 1px solid #ddd; margin: 1.2em 0; }
a { color: #1a4f8b; text-decoration: none; }
"""

FOOTER = '<div style="font-size:7pt;width:100%;text-align:right;padding-right:16mm;color:#555"><span class="pageNumber"></span>/<span class="totalPages"></span></div>'


def strip_front_matter(text: str) -> tuple[str, str]:
    lang = "en"
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if m:
        lm = re.search(r"^lang:\s*(\S+)", m.group(1), re.M)
        lang = lm.group(1) if lm else lang
        text = text[m.end():]
    return text, lang


def build(md: Path, page) -> Path:
    from pypdf import PdfReader, PdfWriter

    name = md.stem
    title, subject = META.get(name, (name, name))
    body, lang = strip_front_matter(md.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        src, css, html = Path(tmp, "in.md"), Path(tmp, "pdf.css"), Path(tmp, "out.html")
        src.write_text(body, encoding="utf-8")
        css.write_text(CSS, encoding="utf-8")
        subprocess.run(["pandoc", str(src), "-f", "gfm", "-t", "html5", "-s", "--metadata", f"pagetitle={title}",
                        "--metadata", f"lang={lang}", "-c", str(css), "--embed-resources", "-o", str(html)], check=True)
        page.goto(html.as_uri())
        raw = Path(tmp, "raw.pdf")
        page.pdf(path=str(raw), format="A4", print_background=True, display_header_footer=True,
                 header_template="<div></div>", footer_template=FOOTER, prefer_css_page_size=True)
        reader = PdfReader(str(raw))
        writer = PdfWriter(clone_from=reader)
        writer.add_metadata({"/Title": title, "/Author": AUTHOR, "/Subject": subject, "/Keywords": KEYWORDS})
        out = md.with_suffix(".pdf")
        with open(out, "wb") as fh:
            writer.write(fh)
    return out


def main(argv: list[str]) -> int:
    from playwright.sync_api import sync_playwright

    files = [Path(a) for a in argv] or [ROOT / "docs/WHITEPAPER_LCE_v0.2_EN.md", ROOT / "docs/WHITEPAPER_LCE_v0.2_ES.md"]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for f in files:
            print("built", build(f.resolve(), page))
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
