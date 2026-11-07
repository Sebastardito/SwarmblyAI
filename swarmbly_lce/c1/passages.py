"""C1 passages: paragraphs of the user's documents, tokens and BM25.

Moved from Swarmbly App 0.3.1 (``lce_adapter.py``) into SwarmblyLCE in 0.2.0,
unchanged in behaviour; the comments keep the rounds (P2e, R13) that set each
constant. Everything here is local and read-only.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .readers import READABLE_SUFFIXES

SOURCE_SUFFIXES = READABLE_SUFFIXES   # text, Word, HTML and (with pdftotext) PDF
SPAN_MAX_CHARS = 600
RELATIVE_FLOOR = 0.35
SHORT_BLOCK_CHARS = 60   # shorter blocks are headings ("NRGene Canada Inc.", "Methods")
TITLE_LINE_CHARS = 160   # longer title lines with dashes count too (see _title_line)
EXTRA_WEIGHT = 0.5       # weight of added query terms (model keywords, glossary)
RRF_K = 60               # reciprocal-rank fusion constant
DENSE_CANDIDATES = 40    # dense ranks that enter the fusion
DENSE_MARGIN = 0.10      # a passage with no word in common must be this close to the best
#                          dense match (cosine) to enter; otherwise fusion always returned k
#                          passages, related or not (a memory note in every answer, 3.1 test)
CANDIDATES_KEPT = 15     # ranked candidates kept for the metadata
MAX_PER_FILE = 3         # passages per file, at least (2 cut a needed third, round 4);
#                          two thirds of k when larger (round 10c: the Ne paragraph was
#                          5th of its chapter with k = 6 and a cap of 3)
_GLOSS_LINE = re.compile(r"^\s*[-*]?\s*([^=→#<>|]{2,80}?)\s*(?:=|→|->)\s*([^=→]{2,200})$")


_TITLE_SEP = re.compile(r"\s[—–]\s")     # not "|": author lists use it


def _title_line(body: str) -> bool:
    """A longer title line, as in a CV: "Entomólogo Jefe de I+D (Investigador
    Principal) — Fenotipado… — Nov 2022 – Sep 2024". No sentence end, parts
    joined by dashes, under TITLE_LINE_CHARS: shown with the paragraph
    below it, like a heading (round 13: the role was its own passage, apart
    from the duties under it)."""
    return (len(body) < TITLE_LINE_CHARS and not body.endswith((".", "?", "!", ":", ";", ","))
            and bool(_TITLE_SEP.search(body)) and not body.startswith(("-", "*", "•")))


def _is_glossary(path: Path) -> bool:
    return (path.suffix.lower() in SOURCE_SUFFIXES
            and path.stem.lower().startswith(("glosario", "glossary", "glossaire", "glossário")))


_SENTENCE_END = re.compile(r"(?<=[.!?;])\s+")


def _paragraphs(name: str, text: str, label: str = "") -> list[dict[str, Any]]:
    """Paragraph spans (≤ 600 characters, as SwarmblyLCE's SourceSpace.spans).

    Long paragraphs are cut at sentence ends rather than mid-word. Each span
    carries an ``index`` text: the file's path words and its title (first
    Markdown heading) followed by the paragraph, so a question that names the
    document ("mi tesis", "artículo de 2024 sobre el rascón") finds it.
    """
    title = next((ln.lstrip("# ").strip() for ln in text.splitlines()
                  if ln.startswith("# ")), "")
    header = " ".join(re.split(r"[\W_]+", re.sub(r"\.\w+$", "", label or name)) + [title])
    # "M. melanotis" is indexed as "Mimus melanotis" when the file spells the
    # genus out somewhere, so a question with the full name finds it.
    genus_of = {}
    for g, e in re.findall(r"\b([A-Z][a-z]{3,})\s([a-z]{4,})\b", text):
        genus_of.setdefault((g[0], e), g)

    def unabbreviate(piece: str) -> str:
        return re.sub(r"\b([A-Z])\.\s([a-z]{4,})\b",
                      lambda m: f"{genus_of.get((m.group(1), m.group(2)), m.group(1))} {m.group(2)}",
                      piece)
    out: list[dict[str, Any]] = []
    pos = 0
    heading = ""
    heading_start = -1           # >= 0: a heading sits right before this block
    for block in text.split("\n\n"):
        start = text.find(block, pos)
        start = pos if start < 0 else start
        pos = start + len(block)
        body = " ".join(block.split())
        if not body or body.startswith("<!--"):
            continue
        if (len(body) < SHORT_BLOCK_CHARS and (not body.endswith((".", "?", "!"))
                                               or len(body.split()) <= 4)) or _title_line(body):
            # a heading: context for what follows; stacked headings ("Gerente de
            # I+D (R&D Manager) — Sep 2024…" then "NRGene Canada Inc. (NAIC)")
            # are kept together, up to three
            title_ = body.lstrip("#").strip()
            if block.lstrip().startswith("# "):
                heading, heading_start = title_, -1   # the document title: in the header
                continue
            if heading_start >= 0:
                heading = " · ".join((heading.split(" · ") + [title_])[-3:])
            else:
                heading = title_
            heading_start = start
            continue
        # The paragraph right under a heading is shown with it: the heading can
        # carry the fact ("Gerente de I+D (R&D Manager) — Sep 2024 – …" above
        # the duties, round 11: K6 was never answerable).
        lead = heading if heading_start >= 0 else ""
        heading_start = -1
        previous = ""            # last sentence of the previous piece, for the index
        while body:
            if len(body) <= SPAN_MAX_CHARS:
                piece, body = body, ""
            else:
                cuts = [m.start() for m in _SENTENCE_END.finditer(body, 0, SPAN_MAX_CHARS)]
                cut = cuts[-1] if cuts and cuts[-1] > SPAN_MAX_CHARS // 3 else body.rfind(" ", 0, SPAN_MAX_CHARS)
                cut = cut if cut > 0 else SPAN_MAX_CHARS
                piece, body = body[:cut].rstrip(), body[cut:].lstrip()
            full = unabbreviate(piece)
            # The passage shown to the model also spells the genus out: a 3B
            # model read "M. trifasciatus (IUCN: Critical Endangered)" as saying
            # nothing about Mimus trifasciatus (round 4).
            shown = f"{lead} — {full}" if lead else full
            # A piece cut from a long paragraph is indexed with the previous
            # piece's last sentence (an overlap, as reads in an assembly): "These
            # two populations, Champion (Ne ~30)…" follows "…the two remnant
            # populations of M. trifasciatus on Champion and Gardner" (K3).
            out.append({"source": name, "start": start, "end": pos,
                        "text": shown, "index": f"{header} {heading} {previous} {shown}"})
            sentences = _SENTENCE_END.split(full)
            previous = sentences[-1] if sentences else ""
            lead = ""
    return out


# Function words (es/en/pt/fr) carry no topic; folded, as the tokens are.
# French "ne" is left out: "Ne" is the effective population size (K3).
_STOPWORDS = frozenset("""
a al algo ante antes asi aun cada como con contra cual cuales cuando cuanto cuantos de del desde donde
dos durante e el ella ellas ellos en entre era eran es esa ese eso esta estaba este esto estos fue fueron
ha han hasta hay la las le les lo los mas me mi mis muy ni no nos o os otra otro para pero poco por porque
que quien se segun ser si sin sobre son su sus tambien tan tanto te tiene tienen todo todos tu un una uno
unos y ya yo usted cual
an and are as at be been but by can could did do does for from had has have how i if in into is it its
may more most my no not of on or our she should so such than that the their them then there these they
this those to was we were what when where which while who why will with would you your
um uma os as ao aos da das do dos em na nas no nos pelo pela ou
au aux ce ces dans des du est et il ils je la le les leur mais nous ou par pas pour qu que qui sa se ses son sur un une vous
""".split())


def _fold(word: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", word.lower())
                   if not unicodedata.combining(c))


def _stem(word: str) -> str:
    """Light plural folding shared by Spanish and English ("cucuves" → "cucuve")."""
    if len(word) > 4 and word.endswith("es") and word[-3] in "lnrdzj":
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _tokens(text: str) -> list[str]:
    out = []
    for w in re.findall(r"[^\W_]+(?:[+-][^\W_]+)*", text):
        f = _fold(w)
        if len(f) > 1 and f not in _STOPWORDS:
            out.append(_stem(f))
    return out


class _BM25:
    """BM25 (k1 1.5, b 0.75), the same scoring as SwarmblyLCE's retriever,
    over folded, stop-word-free, plural-folded tokens."""

    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75):
        import math
        from collections import Counter
        self._tok = _tokens
        self.k1, self.b, self._log = k1, b, math.log
        self.tf = [Counter(self._tok(d)) for d in docs]
        self.df: Counter = Counter()
        for tf in self.tf:
            self.df.update(tf.keys())
        self.avg = sum(sum(tf.values()) for tf in self.tf) / max(1, len(self.tf))

    def search(self, query: str, k: int, extra: str = "",
               extra_weight: float = 0.5) -> list[tuple[int, float]]:
        weights = {t: 1.0 for t in self._tok(query)}
        for t in self._tok(extra):
            weights.setdefault(t, extra_weight)
        n = len(self.tf)
        scored = []
        for i, tf in enumerate(self.tf):
            dl = sum(tf.values()) or 1
            s = 0.0
            for t, w in weights.items():
                if t in tf:
                    idf = self._log(1 + (n - self.df[t] + 0.5) / (self.df[t] + 0.5))
                    s += w * idf * tf[t] * (self.k1 + 1) / (
                        tf[t] + self.k1 * (1 - self.b + self.b * dl / (self.avg or 1)))
            if s > 0:
                scored.append((i, s))
        scored.sort(key=lambda x: -x[1])
        return scored[:k]


# Public names (the leading-underscore ones are kept for code moved from the app)
is_glossary = _is_glossary
paragraphs = _paragraphs
tokens = _tokens
fold = _fold
BM25 = _BM25
GLOSS_LINE = _GLOSS_LINE
