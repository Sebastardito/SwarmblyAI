"""LCE level C1: retrieval over the user's own documents, on their device.

* ``readers`` — plain text from text, Markdown, Word, HTML and PDF files.
* ``passages`` — paragraphs, tokens and BM25.
* ``index`` — :class:`SourceIndex`: retrieval over folders, the personal
  glossary, and stable citations (``doc:<sha12>#p<n>``).

C1 never writes the user's files and never sends a passage anywhere: what an
application does with the passages (and where it sends them) is its own
policy, reported to the user.
"""

from .index import SourceIndex, citation, doc_id, parse_citation
from .readers import READABLE_SUFFIXES, read_source

__all__ = ["SourceIndex", "citation", "doc_id", "parse_citation",
           "READABLE_SUFFIXES", "read_source"]
