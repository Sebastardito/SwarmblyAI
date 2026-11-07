# Changelog — SwarmblyLCE

Earlier versions are described in their release notes (v0.1.0, v0.1.1) and in `docs/`.

## 0.2.0 — Level C1 in the package (unreleased)

- **`swarmbly_lce.c1`**: retrieval over the user's own documents, moved from Swarmbly App 0.3.1 so that every client uses the same C1, unchanged in behaviour.
  - `readers`: plain text from text, Markdown, Word, HTML and PDF (with `pdftotext`).
  - `passages`: paragraphs (headings kept with the paragraph below them), tokens, BM25.
  - `index.SourceIndex`: retrieval over a set of folders, with model keywords and glossary equivalents at half weight and optional fusion with local embeddings; the personal glossary; one cache for several sets of folders (personal sources, each project).
- **Stable citations.** Every paragraph carries `doc:<sha12>#p<n>`: the first 12 hex digits of the SHA-256 of the file and the paragraph's position. A citation does not depend on where the folder lives, so a project moved or restored on another computer still resolves its old citations (`SourceIndex.resolve`). If the file changes, its old citations stop resolving, and that is reported.
- **PDF without poppler.** Where `pdftotext` is not installed (a Mac without Homebrew), PDFs are read with `pypdf` (extra `pdf`) instead of being left out; `pdftotext` stays the first choice.
- Tests: `tests/test_c1.py`, on fictitious data.
