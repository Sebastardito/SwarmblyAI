# Changelog — SwarmblyLCE

Earlier versions are described in their release notes (v0.1.0, v0.1.1) and in `docs/`.

## 0.2.0 — Level C1 in the package (unreleased)

- **`swarmbly_lce.c1`**: retrieval over the user's own documents, moved from Swarmbly App 0.3.1 so that every client uses the same C1, unchanged in behaviour.
  - `readers`: plain text from text, Markdown, Word, HTML and PDF (with `pdftotext`).
  - `passages`: paragraphs (headings kept with the paragraph below them), tokens, BM25.
  - `index.SourceIndex`: retrieval over a set of folders, with model keywords and glossary equivalents at half weight and optional fusion with local embeddings; the personal glossary; one cache for several sets of folders (personal sources, each project).
- **Stable citations.** Every paragraph carries `doc:<sha12>#p<n>`: the first 12 hex digits of the SHA-256 of the file and the paragraph's position. A citation does not depend on where the folder lives, so a project moved or restored on another computer still resolves its old citations (`SourceIndex.resolve`). If the file changes, its old citations stop resolving, and that is reported.
- **PDF without poppler.** Where `pdftotext` is not installed (a Mac without Homebrew), PDFs are read with `pypdf` (extra `pdf`) instead of being left out; `pdftotext` stays the first choice.
- **Fusion keeps unrelated passages out.** With local embeddings, a passage that shares no word with the question enters only if its meaning is close to the best match (cosine within 0.10); before, fusion always returned *k* passages, related or not.
- **Glossary equivalents one by one.** In `term = eq1, eq2, eq3`, any single equivalent in a question now brings the term and the others (before, all of them had to appear together).
- **Corrected forms.** A glossary line `term = equivalents | no: wrong, wrong` lists forms the user corrected: they are never equivalents (they do not widen a search) and `SourceIndex.glossary_avoid` returns them as `{wrong: right}` for the application to enforce.
- **Glossary metadata.** After `|`, a glossary line may also carry `distinto: X` (a different concept the user does not want confused with this one), `wd: Q…` (the Wikidata item the user chose) and `en:`/`es:` labels. None of them is ever an equivalent; `SourceIndex.glossary_meta` returns them per term.
- Tests: `tests/test_c1.py`, on fictitious data.
