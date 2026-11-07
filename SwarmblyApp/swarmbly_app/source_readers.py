"""Readers moved to ``swarmbly_lce.c1.readers`` in 3.1; kept for older imports."""

from swarmbly_lce.c1.readers import *  # noqa: F401,F403
from swarmbly_lce.c1.readers import (  # noqa: F401
    DOC_SUFFIXES, PDF_HINT, READABLE_SUFFIXES, TEXT_SUFFIXES, docx_text, html_text, pdftotext_path,
    read_source, reflow)
