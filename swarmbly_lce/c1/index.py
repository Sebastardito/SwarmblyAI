"""C1 retrieval over folders of the user's documents (local, read-only).

``SourceIndex`` reads every readable file under a set of folders (the
"roots"), cuts it into paragraphs, and answers a question with the best
paragraphs: BM25 over the user's words, plus model keywords and glossary
equivalents at half weight, optionally fused with local embeddings
(reciprocal-rank fusion). Files are read, never written; the index of a file
is rebuilt only when its content hash changes.

Every paragraph carries a **stable citation**: ``doc:<sha12>#p<n>``, where
``sha12`` is the first 12 hex digits of the SHA-256 of the file's bytes and
``n`` the paragraph's position in that file. It does not depend on where the
folder lives, so a project moved or restored on another computer still
resolves the citations of its old answers (``resolve``). If the file changes,
its old citations no longer resolve, which is reported, never guessed.

Moved from Swarmbly App 0.3.1 into SwarmblyLCE 0.2.0; one index can serve
several sets of roots (personal sources, each project) with one cache.
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from . import passages as P
from .readers import READABLE_SUFFIXES, read_source

Skip = Callable[[Path, Path], bool]          # (root, path) -> leave this file out


def doc_id(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def citation(span: dict[str, Any]) -> str:
    return f"doc:{span['doc_id']}#{span['anchor']}"


def parse_citation(cite: str) -> tuple[str, str] | None:
    if not cite.startswith("doc:") or "#" not in cite:
        return None
    doc, anchor = cite[4:].split("#", 1)
    return (doc, anchor) if doc and anchor else None


@dataclass
class _Cache:
    spans: dict[tuple[str, str], list[dict[str, Any]]] = field(default_factory=dict)
    glossary: dict[tuple[str, str], list[tuple[str, str]]] = field(default_factory=dict)
    vectors: dict[str, tuple[float, ...] | list[float]] = field(default_factory=dict)
    unreadable: dict[str, str] = field(default_factory=dict)
    index: tuple[tuple[int, ...], Any] | None = None
    dense_off_until: float = 0.0


class SourceIndex:
    def __init__(self, skip: Skip | None = None):
        self.skip = skip
        self._cache = _Cache()
        self.last_candidates: list[dict[str, Any]] = []

    # -- files -----------------------------------------------------------------
    def _files(self, roots: Iterable[Path]) -> Iterable[tuple[Path, Path]]:
        for root in roots:
            root = Path(root).expanduser()
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*")):
                if (not path.is_file() or path.suffix.lower() not in READABLE_SUFFIXES
                        or any(p.startswith(".") for p in path.relative_to(root).parts)
                        or (self.skip is not None and self.skip(root, path))):
                    continue
                yield root, path

    @property
    def unreadable(self) -> dict[str, str]:
        return self._cache.unreadable

    def spans(self, roots: Iterable[Path]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for root, path in self._files(roots):
            if P.is_glossary(path):
                continue
            try:
                data = path.read_bytes()
            except OSError:
                continue
            digest = hashlib.sha256(data).hexdigest()
            key = (str(path), digest)
            if key not in self._cache.spans:
                text, reason = read_source(path, data)
                rel = path.relative_to(root).as_posix()
                found = P.paragraphs(path.name, text, label=rel) if text else []
                for n, sp in enumerate(found, 1):
                    sp.update(doc_id=digest[:12], anchor=f"p{n}", rel=rel)
                self._cache.spans[key] = found
                if text is None:
                    self._cache.unreadable[str(path)] = reason
                else:
                    self._cache.unreadable.pop(str(path), None)
            out.extend(self._cache.spans[key])
        return out

    def list_sources(self, roots: Iterable[Path]) -> list[dict[str, Any]]:
        """Files C1 reads, with how many passages each gave and, if none, why."""
        roots = [Path(r).expanduser() for r in roots]
        counts: dict[tuple[str, str], int] = {}
        for sp in self.spans(roots):
            counts[(sp["rel"], sp["doc_id"])] = counts.get((sp["rel"], sp["doc_id"]), 0) + 1
        out: list[dict[str, Any]] = []
        for root, path in self._files(roots):
            try:
                data = path.read_bytes()
                size = len(data)
            except OSError:
                data, size = b"", 0
            rel = path.relative_to(root).as_posix()
            entry = {"name": path.name, "path": str(path), "rel": rel, "size_bytes": size,
                     "folder": str(root), "glossary": P.is_glossary(path),
                     "doc_id": doc_id(data) if data else "",
                     "passages": 0 if P.is_glossary(path)
                     else counts.get((rel, doc_id(data) if data else ""), 0)}
            if str(path) in self._cache.unreadable:
                entry["unreadable"] = self._cache.unreadable[str(path)]
            out.append(entry)
        return out

    # -- retrieval ---------------------------------------------------------------
    def retrieve(self, roots: Iterable[Path], query: str, k: int = 4, expansion: str = "",
                 embed: Callable[[list[str], str], list[list[float]]] | None = None
                 ) -> list[dict[str, Any]]:
        """Top paragraphs for ``query``. ``expansion`` holds extra terms (the local
        model's keywords in another language); the user's words weigh fully and
        added terms half, so they widen the search without taking it over."""
        roots = [Path(r).expanduser() for r in roots]
        spans = self.spans(roots)
        if not spans or not (query or "").strip():
            return []
        key = tuple(id(s) for s in spans)
        if self._cache.index is None or self._cache.index[0] != key:
            self._cache.index = (key, P.BM25([s.get("index") or s["text"] for s in spans]))
        index = self._cache.index[1]
        extra = f"{expansion} {self.glossary_terms(f'{query} {expansion}', roots)}"
        ranked = index.search(query, k * 4, extra=extra, extra_weight=P.EXTRA_WEIGHT)
        # Paragraphs that only share function words score far below a real
        # match: keep those within 35 % of the best one.
        top = ranked[0][1] if ranked else 0.0
        if embed is not None:
            fused = self._hybrid(spans, ranked, f"{query} {extra}", embed)
            if fused:
                ranked, top = fused, 0.0      # RRF scores: no BM25 floor
        self.last_candidates = [{"source": spans[i]["source"], "start": spans[i]["start"],
                                 "cite": citation(spans[i]), "score": round(sc, 4)}
                                for i, sc in ranked[:P.CANDIDATES_KEPT]]
        hits, seen = [], set()
        per_file: dict[str, int] = {}
        for i, score in ranked:
            if score < P.RELATIVE_FLOOR * top or len(hits) >= k:
                continue
            doc = spans[i]["doc_id"]
            if per_file.get(doc, 0) >= max(P.MAX_PER_FILE, (2 * k) // 3):
                continue          # one long file must not fill every slot
            same = " ".join(P.tokens(spans[i]["text"]))[:200]
            if same in seen:          # the same paragraph in two files (ES/EN copies)
                continue
            seen.add(same)
            per_file[doc] = per_file.get(doc, 0) + 1
            hit = {key_: v for key_, v in spans[i].items() if key_ != "index"}
            hit["score"] = round(score, 3)
            hit["cite"] = citation(spans[i])
            hits.append(hit)
        return hits

    def _hybrid(self, spans: list[dict[str, Any]], bm25: list[tuple[int, float]],
                query: str, embed) -> list[tuple[int, float]]:
        """Reciprocal-rank fusion of BM25 and dense similarity; any failure of
        the embedding model falls back to BM25 alone for five minutes."""
        if self._cache.dense_off_until > time.monotonic():
            return []
        cache = self._cache.vectors
        try:
            missing = [s["text"] for s in spans if s["text"] not in cache]
            for i in range(0, len(missing), 64):
                batch = missing[i:i + 64]
                for text, vec in zip(batch, embed(batch, "document")):
                    cache[text] = vec
            qv = embed([query[:2000]], "query")[0]
        except Exception:
            self._cache.dense_off_until = time.monotonic() + 300.0
            return []

        def norm(v):
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            return [x / n for x in v]
        qv = norm(qv)
        sims = []
        for i, s in enumerate(spans):
            v = cache.get(s["text"])
            if v is None:
                continue
            if not isinstance(v, tuple):
                v = cache[s["text"]] = tuple(norm(v))
            sims.append((sum(a * b for a, b in zip(qv, v)), i))
        sims.sort(reverse=True)
        lexical = {i for i, _ in bm25}
        best = sims[0][0] if sims else 0.0
        score: dict[int, float] = {}
        for rank, (i, _) in enumerate(bm25):
            score[i] = score.get(i, 0.0) + 1.0 / (P.RRF_K + rank + 1)
        for rank, (sim, i) in enumerate(sims[:P.DENSE_CANDIDATES]):
            if i not in lexical and sim < best - P.DENSE_MARGIN:
                continue          # no word in common and not close in meaning
            score[i] = score.get(i, 0.0) + 1.0 / (P.RRF_K + rank + 1)
        return sorted(score.items(), key=lambda x: -x[1])

    # -- citations ----------------------------------------------------------------
    def resolve(self, roots: Iterable[Path], cite: str) -> dict[str, Any] | None:
        """The paragraph a stable citation points to, or None if no file with
        that content exists under ``roots`` any more."""
        parsed = parse_citation(cite)
        if parsed is None:
            return None
        doc, anchor = parsed
        for sp in self.spans(roots):
            if sp["doc_id"] == doc and sp["anchor"] == anchor:
                return {key: v for key, v in sp.items() if key != "index"}
        return None

    # -- personal glossary ---------------------------------------------------------
    def glossary_entries(self, roots: Iterable[Path]) -> list[tuple[str, str]]:
        """Lines ``term = equivalent, equivalent`` (also ``→``, ``->``) of files
        named ``glosario*`` / ``glossary*``: the user's own vocabulary."""
        out: list[tuple[str, str]] = []
        for _root, path in self._files(roots):
            if not P.is_glossary(path):
                continue
            try:
                data = path.read_bytes()
            except OSError:
                continue
            key = (str(path), hashlib.sha256(data).hexdigest())
            if key not in self._cache.glossary:
                pairs = []
                for line in data.decode("utf-8", "replace").splitlines():
                    m = P.GLOSS_LINE.match(line)
                    if m:
                        pairs.append((m.group(1).strip(), m.group(2).strip()))
                self._cache.glossary[key] = pairs
            out.extend(self._cache.glossary[key])
        return out

    def glossary_terms(self, text: str, roots: Iterable[Path]) -> str:
        """Equivalents from the glossary for terms present in ``text``, applied
        in both directions."""
        entries = self.glossary_entries(roots)
        if not entries:
            return ""
        have = set(P.tokens(text))

        def present(tok: str) -> bool:
            # single long terms also match inflections: "muestrear" ~ "muestrearon"
            if tok in have or (len(tok) >= 6 and any(h.startswith(tok) for h in have)):
                return True
            # Spanish gender: "extinto" ~ "extinta", "público" ~ "pública"
            return len(tok) >= 5 and tok[-1] in "oa" and any(
                len(h) == len(tok) and h[:-1] == tok[:-1] and h[-1] in "oa" for h in have)
        added: list[str] = []
        for side_a, side_b in entries:
            for left, right in ((side_a, side_b), (side_b, side_a)):
                toks = P.tokens(left)
                if toks and all(present(t) for t in toks) and right not in added:
                    added.append(right)
        return " ".join(added)
