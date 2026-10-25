"""Source space: layer 0 (SPEC 5.1).

The source space is a set of local folders whose files the LCE treats as
immutable. This module scans them, fingerprints each file, and segments text
into spans whose byte offsets anchors can point to. It never writes into the
source space.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .canonical import text_digest

__all__ = ["SourceFile", "Span", "SourceSpace", "TEXT_SUFFIXES"]

TEXT_SUFFIXES = frozenset({".md", ".txt", ".markdown", ".rst", ".org", ".tex", ".csv", ".json", ".py"})


@dataclass(frozen=True)
class SourceFile:
    rel: str  # POSIX path relative to the source-space root
    sha256: str
    size: int


@dataclass(frozen=True)
class Span:
    source: str
    start: int  # character offsets into the decoded text
    end: int
    text: str

    @property
    def digest(self) -> str:
        return text_digest(self.text)


class SourceSpace:
    """Read-only view of one source-space root."""

    def __init__(self, root: str | Path, suffixes: frozenset[str] = TEXT_SUFFIXES) -> None:
        self.root = Path(root).resolve()
        self.suffixes = suffixes
        if not self.root.is_dir():
            raise NotADirectoryError(self.root)

    def files(self) -> Iterator[SourceFile]:
        for p in sorted(self.root.rglob("*")):
            if p.is_file() and p.suffix.lower() in self.suffixes and not any(part.startswith(".") for part in p.relative_to(self.root).parts):
                data = p.read_bytes()
                yield SourceFile(rel=p.relative_to(self.root).as_posix(), sha256=hashlib.sha256(data).hexdigest(), size=len(data))

    def read(self, rel: str) -> str:
        path = (self.root / rel).resolve()
        if self.root not in path.parents and path != self.root:
            raise PermissionError(f"{rel!r} escapes the source space")
        return path.read_text(encoding="utf-8", errors="replace")

    def file_hash(self, rel: str) -> str:
        return hashlib.sha256((self.root / rel).read_bytes()).hexdigest()

    def spans(self, rel: str, max_chars: int = 600) -> list[Span]:
        """Paragraph spans, split further when longer than ``max_chars``."""
        text = self.read(rel)
        out: list[Span] = []
        pos = 0
        for block in text.split("\n\n"):
            start = text.find(block, pos)
            if start < 0:
                start = pos
            end = start + len(block)
            pos = end
            stripped = block.strip()
            if not stripped:
                continue
            lead = start + (len(block) - len(block.lstrip()))
            seg_start = lead
            seg_text = stripped
            while len(seg_text) > max_chars:
                cut = seg_text.rfind(". ", 0, max_chars)
                cut = cut + 1 if cut > max_chars // 3 else max_chars
                out.append(Span(rel, seg_start, seg_start + cut, seg_text[:cut]))
                rest = seg_text[cut:]
                shift = len(rest) - len(rest.lstrip())
                seg_start += cut + shift
                seg_text = rest.lstrip()
            if seg_text:
                out.append(Span(rel, seg_start, seg_start + len(seg_text), seg_text))
        return out
