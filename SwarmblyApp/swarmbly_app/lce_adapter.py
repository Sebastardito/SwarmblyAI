"""LCE adapter — C0 active, C1 retrieval over sources for local answers.

C0 is "Swarmbly unchanged": the app works without any LCE component. When LCE
is enabled, the adapter prepares the local plane (source space, conservative
learning policy) with ``swarmbly_lce`` itself, and provides the WorkerGuard
that keeps the worker role conformant with invariant I2 (workers serve the
base model; personal adapters never travel).

C1 itself (reading documents, paragraphs, BM25, glossary, stable citations)
lives in ``swarmbly_lce.c1`` since 3.1; this adapter only decides which
folders a request may read: the personal sources, or a project's folders
(3.1), never both unless the project allows it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from swarmbly_lce.c1 import SourceIndex
from swarmbly_lce.c1 import passages as _passages
from swarmbly_lce.c1.passages import (  # noqa: F401  (kept for older imports)
    _BM25, _fold, _is_glossary, _paragraphs, _stem, _tokens, CANDIDATES_KEPT,
    DENSE_CANDIDATES, EXTRA_WEIGHT, MAX_PER_FILE, RELATIVE_FLOOR, RRF_K, SPAN_MAX_CHARS)
from swarmbly_lce.c1.readers import READABLE_SUFFIXES  # noqa: F401

from .paths import DataDirs

LEVELS = {
    "C0": {"active": True, "status": "active",
           "note": "Swarmbly unchanged; no LCE components applied."},
    "C1": {"active": True, "status": "active (local answers)",
           "note": "Retrieval over your raw sources (text, Word, HTML and PDF; "
                  "keyword and local-embedding search, with your glossary) is added "
                  "to answers produced on this device, with the source cited. "
                  "Passages never leave the device; projection into Γ needs "
                  "digested claims (C2) and stays empty at C1."},
    "C2": {"active": False, "status": "disabled",
           "note": "Automatic digestion — later phase (digester exists in SwarmblyLCE)."},
    "C3": {"active": False, "status": "disabled",
           "note": "Social capsules — implemented upstream but not validated on a real "
                  "network; not exposed as a product feature."},
    "C4": {"active": False, "status": "disabled",
           "note": "LoRA fine-tuning — experimental, no verdict (R11). Training stays off "
                  "by default (invariant I8)."},
}

# Conservative default per invariant I8: what is not declared does not train.
# Format follows swarmbly_lce.policy.LearningPolicy.from_mapping (v0.1):
# a mapping with "v", "defaults" (SourceRule fields) and "sources" (prefix rules).
DEFAULT_POLICY = {
    "v": "0.1",
    "defaults": {"reference_only": True, "train": True},
    "sources": {},
}


class LCEAdapter:
    def __init__(self, dirs: DataDirs):
        self.dirs = dirs
        # The README the app writes into its own source folder is not a document
        self.index = self._new_index()
        # The embedding identity the index's vectors were built with.  The
        # SourceIndex cache is keyed by text, so a different model (or a
        # different vector size) must get a fresh index: zip() would silently
        # truncate mismatched vectors instead of failing.
        self._embedding: dict[str, Any] = {"identity": "", "model": "", "dim": 0}
        self.last_embedding_meta: dict[str, Any] = {}

    def _new_index(self) -> SourceIndex:
        from .projects import is_app_note
        return SourceIndex(
            skip=lambda root, path: (path.name == "README.md" and path.parent == self.dirs.sources)
            or is_app_note(path))

    # -- package availability -------------------------------------------------
    def package_info(self) -> dict[str, Any]:
        info: dict[str, Any] = {"installed": False, "version": None,
                                "crypto": False}
        try:
            import swarmbly_lce
            info["installed"] = True
            info["version"] = swarmbly_lce.__version__
            info["spec_version"] = swarmbly_lce.SPEC_VERSION
            info["capsule_version"] = swarmbly_lce.CAPSULE_VERSION
        except Exception:
            pass
        try:
            from swarmbly_lce.crypto import crypto_available
            info["crypto"] = crypto_available()
        except Exception:
            pass
        return info

    # -- lifecycle -------------------------------------------------------------
    def status(self, enabled: bool, level: str) -> dict[str, Any]:
        meta = LEVELS.get(level, LEVELS["C0"])
        return {
            "enabled": enabled,
            "level": level,
            "active": enabled and bool(meta["active"]),
            "state": meta["status"] if enabled else "disabled",
            "note": meta["note"],
            "levels": LEVELS,
            "package": self.package_info(),
            "paths": {"sources": str(self.dirs.sources),
                      "wiki": str(self.dirs.wiki),
                      "adapters": str(self.dirs.adapters),
                      "capsules": str(self.dirs.capsules)},
        }

    def activate(self, level: str = "C1") -> dict[str, Any]:
        """Prepare the local plane for the chosen level (C0/C1 in v0.1)."""
        if level not in LEVELS:
            raise ValueError(f"unknown LCE level {level!r} (allowed: {', '.join(LEVELS)})")
        if level not in ("C0", "C1"):
            raise ValueError(
                f"level {level} is not available in this version; "
                f"see its documented status: {LEVELS[level]['note']}")
        self.dirs.ensure()
        (self.dirs.sources / "README.md").write_text(
            "# Swarmbly LCE — sources\n\n"
            "Place your documents here (or add folders in Settings → LCE).\n"
            "Sources are immutable: the app only reads them. Removing a source "
            "from LCE is done with the *forget* action, never by editing files.\n",
            encoding="utf-8")
        policy_path = self.dirs.wiki / "policy.json"
        if not policy_path.exists():
            policy_path.parent.mkdir(parents=True, exist_ok=True)
            policy_path.write_text(json.dumps(DEFAULT_POLICY, indent=2),
                                   encoding="utf-8")
        if level == "C1":
            self._init_source_space()
        return self.status(True, level)

    def _init_source_space(self) -> None:
        """Validate the LCE SourceSpace / policy through swarmbly_lce itself."""
        try:
            from swarmbly_lce.sources import SourceSpace
            from swarmbly_lce.policy import LearningPolicy
            space = SourceSpace(root=str(self.dirs.sources))
            policy = LearningPolicy.from_mapping(DEFAULT_POLICY)
            # Probe-only: nothing is digested yet.
            _ = space.files()
            _ = policy.fingerprint("probe")
        except Exception as exc:  # upstream package is a dependency; report honestly
            raise RuntimeError(f"could not initialize LCE C1: {exc}") from exc

    # -- embeddings (3.4, carried over from 3.3) --------------------------------
    def prepare_embeddings(self, identity: str, model: str, dim: int = 0) -> dict[str, Any]:
        """Make the index safe for ``identity``'s vectors; rebuild if needed.

        ``identity`` names the backend, model and endpoint; ``dim`` is the
        vector size last observed for it (0 before the first call).  A change
        in either discards every cached vector by starting a new SourceIndex,
        so vectors from two models never share a cache.  Returns what the
        answer's meta should say.
        """
        previous = dict(self._embedding)
        reason = ""
        if previous["identity"] and previous["identity"] != identity:
            reason = "model changed"
        elif dim and previous["dim"] and dim != previous["dim"]:
            reason = "dimension changed"
        rebuilt = bool(reason)
        if rebuilt:
            self.index = self._new_index()
        self._embedding = {"identity": identity, "model": model,
                           "dim": dim or int(previous.get("dim") or 0)}
        meta = {"model": model, "identity": identity,
                "rebuilt": rebuilt, "dimension": self._embedding["dim"]}
        if rebuilt:
            meta["reason"] = reason
            meta["previous_model"] = previous.get("model", "")
        self.last_embedding_meta = meta
        return dict(meta)

    def note_embeddings(self, meta: dict[str, Any]) -> None:
        """Record what this request did for its meta/receipt."""
        self.last_embedding_meta = dict(meta)

    # -- C1 (swarmbly_lce.c1) ------------------------------------------------
    def personal_roots(self, extra_dirs: list[str] | tuple[str, ...] = ()) -> list[Path]:
        return [self.dirs.sources, *[Path(d).expanduser() for d in extra_dirs or ()]]

    def _roots(self, extra_dirs, roots) -> list[Path]:
        return list(roots) if roots is not None else self.personal_roots(extra_dirs)

    @property
    def last_candidates(self) -> list[dict[str, Any]]:
        return self.index.last_candidates

    def list_sources(self, extra_dirs: list[str] | tuple[str, ...] = (),
                     roots: list[Path] | None = None) -> list[dict[str, Any]]:
        """Files C1 reads, with how many passages each gave and, if none, why
        ("pdftotext is not installed", "no text layer")."""
        return self.index.list_sources(self._roots(extra_dirs, roots))

    def retrieve(self, query: str, k: int = 4,
                 extra_dirs: list[str] | tuple[str, ...] = (),
                 expansion: str = "",
                 embed: Callable[[list[str], str], list[list[float]]] | None = None,
                 roots: list[Path] | None = None) -> list[dict[str, Any]]:
        """Top paragraphs of the user's sources for ``query`` (local only).
        ``roots`` replaces the personal folders (a project's folders)."""
        all_roots = self._roots(extra_dirs, roots)
        return _with_csv_tables(all_roots, self.index.retrieve(all_roots, query, k=k,
                                                               expansion=expansion, embed=embed))

    def document_spans(self, doc_id: str, extra_dirs: list[str] | tuple[str, ...] = (),
                       roots: list[Path] | None = None) -> list[dict[str, Any]]:
        """Every paragraph of one document (by content hash), in order, each
        with ``doc_title``: the document's first Markdown heading (C1 keeps it
        only in its search index; the claim verifier shows it with the
        paragraph, "Acta de la reunión técnica del 15 de abril de 2026")."""
        all_roots = self._roots(extra_dirs, roots)
        spans = [{k: v for k, v in s.items() if k != "index"}
                 for s in self.index.spans(all_roots) if s.get("doc_id") == doc_id]
        if spans:
            title = _first_heading(all_roots, str(spans[0].get("rel") or ""))
            for s in spans:
                s["doc_title"] = title
        return _with_csv_tables(all_roots, spans)

    def resolve(self, cite: str, extra_dirs: list[str] | tuple[str, ...] = (),
                roots: list[Path] | None = None) -> dict[str, Any] | None:
        all_roots = self._roots(extra_dirs, roots)
        found = self.index.resolve(all_roots, cite)
        return _with_csv_tables(all_roots, [found])[0] if found else found

    def glossary_terms(self, text: str, extra_dirs: list[str] | tuple[str, ...] = (),
                       roots: list[Path] | None = None) -> str:
        return self.index.glossary_terms(text, self._roots(extra_dirs, roots))

    def glossary_avoid(self, extra_dirs: list[str] | tuple[str, ...] = (),
                       roots: list[Path] | None = None) -> dict[str, str]:
        """Forms the user corrected, ``{wrong: right}`` (glossary ``| no:``)."""
        getter = getattr(self.index, "glossary_avoid", None)
        return getter(self._roots(extra_dirs, roots)) if getter else {}

    def glossary_meta(self, extra_dirs: list[str] | tuple[str, ...] = (),
                      roots: list[Path] | None = None) -> dict[str, dict[str, list[str]]]:
        getter = getattr(self.index, "glossary_meta", None)
        return getter(self._roots(extra_dirs, roots)) if getter else {}

    def glossary_private_terms(self, extra_dirs: list[str] | tuple[str, ...] = (),
                               roots: list[Path] | None = None) -> list[str]:
        """Terms whose glossary line carries the App's ``| privado`` mark (T9.17).

        LCE's ``_split_meta`` drops a bare ``privado`` segment (it is not one of
        its metadata keys), so the App reads the raw lines here, from the same
        files and roots the adapter already reads.  Only the term list leaves
        this method; the mark itself never changes what LCE does locally.
        """
        from .memory_capture import split_private_mark
        out: list[str] = []
        for root in self._roots(extra_dirs, roots):
            root = Path(root).expanduser()
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*")):
                if (not path.is_file() or not _passages.is_glossary(path)
                        or any(p.startswith(".") for p in path.relative_to(root).parts)):
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for term, right in _passages.glossary_lines(text):
                    if term not in out and split_private_mark(right)[1]:
                        out.append(term)
        return out

    # a shorter name for callers that only ask "which terms are private?"
    glossary_private = glossary_private_terms

    def glossary_entries(self, extra_dirs: list[str] | tuple[str, ...] = (),
                         roots: list[Path] | None = None) -> list[tuple[str, str]]:
        roots = self._roots(extra_dirs, roots)
        entries = list(self.index.glossary_entries(roots))
        private = set(self.glossary_private_terms(roots=roots))
        if not private:
            return entries
        from .memory_capture import split_private_mark
        out: list[tuple[str, str]] = []
        for term, right in entries:
            clean, marked = split_private_mark(right)
            # The mark travels in the entry's existing two-field shape: every
            # caller keeps working, and the proposal can read it App-side even
            # though LCE itself dropped it.
            if term in private or marked:
                out.append((term, f"{clean} | privado" if clean else "privado"))
            else:
                out.append((term, right))
        return out

    def worker_guard(self, declared_model: str):
        """WorkerGuard (invariant I2) bound to the base model this node
        advertises; it refuses to run if the serving backend differs or carries
        a personal adapter. None only if swarmbly_lce is missing."""
        try:
            from swarmbly_lce.worker import WorkerGuard
            return WorkerGuard(declared_model=declared_model)
        except Exception:
            return None


# ---- CSV files as tables (3.3, sealed banks v3) --------------------------------
# C1 reads a CSV file as text and joins the lines of a paragraph, so a budget
# reached the model and the code as "partida,categoria,monto_usd Sensores,
# equipos,12600 Colonias,…": no table to read (the table by code was built in
# 0 of 8 cases with documents like these) and sums the model had to guess. The
# paragraph is given back as the Markdown table the file holds, read with the
# csv module from the file itself; the citation, the paragraph and its figures
# are the same.
_CSV_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_CSV_MAX_ROWS = 400


def _csv_blocks(path: Path) -> list[dict[str, Any]]:
    """Each block of lines of a CSV file: the paragraph as C1 joins it
    (``flat``), where each line starts in it (``starts``), and its rows."""
    import csv
    import io
    try:
        stamp = path.stat().st_mtime
    except OSError:
        return []
    key = str(path)
    if key in _CSV_CACHE and _CSV_CACHE[key][0] == stamp:
        return _CSV_CACHE[key][1]
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for block in re.split(r"\n\s*\n", raw.replace("\r\n", "\n")):
        lines = [" ".join(ln.split()) for ln in block.split("\n") if ln.strip()]
        if len(lines) < 2:
            continue
        try:
            delimiter = csv.Sniffer().sniff("\n".join(lines[:20]), delimiters=",;\t").delimiter
        except csv.Error:
            delimiter = ","
        rows = [r for r in csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter)]
        width = len(rows[0]) if rows else 0
        if width < 2 or len(rows) != len(lines) or any(len(r) != width for r in rows):
            continue          # a quoted field over two lines, or not a table: left as it is
        starts, pos = [], 0
        for ln in lines:
            starts.append(pos)
            pos += len(ln) + 1
        out.append({"flat": " ".join(lines), "starts": starts, "rows": rows})
    _CSV_CACHE[key] = (stamp, out)
    return out


def _csv_markdown(rows: list[list[str]]) -> str:
    def cell(c: str) -> str:
        return " ".join(c.replace("|", "/").split()) or "—"
    width = len(rows[0])
    return "\n".join(["| " + " | ".join(cell(c) for c in rows[0]) + " |", "|" + "---|" * width]
                     + ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows[1:_CSV_MAX_ROWS + 1]])


def _with_csv_tables(roots: list[Path], spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The paragraphs of CSV files as Markdown tables, read with the csv module
    from the file itself. A long block is cut by C1 into several paragraphs:
    each keeps the header and the rows it holds."""
    for s in spans:
        rel = str(s.get("rel") or "")
        if not rel.lower().endswith(".csv"):
            continue
        piece = " ".join(str(s.get("text", "")).split())
        path = next((Path(r).expanduser() / rel for r in roots if (Path(r).expanduser() / rel).is_file()), None)
        if path is None or not piece:
            continue
        for block in _csv_blocks(path):
            at = block["flat"].find(piece)
            if at < 0:
                continue
            end = at + len(piece)
            starts = block["starts"] + [len(block["flat"]) + 1]
            covered = [i for i in range(1, len(block["rows"]))
                       if starts[i] < end and starts[i + 1] - 1 > at]
            if covered:
                s["text"] = _csv_markdown([block["rows"][0]] + [block["rows"][i] for i in covered])
                s["csv_table"] = True
            break
    return spans


def _first_heading(roots: list[Path], rel: str) -> str:
    """The first "# " line of a Markdown or text file under one of the roots."""
    if not rel or Path(rel).suffix.lower() not in (".md", ".markdown", ".txt"):
        return ""
    for root in roots:
        path = Path(root).expanduser() / rel
        try:
            with path.open(encoding="utf-8", errors="replace") as fh:
                for n, line in enumerate(fh):
                    if line.startswith("# "):
                        return line[2:].strip()[:200]
                    if n > 40:
                        break
        except OSError:
            continue
    return ""
