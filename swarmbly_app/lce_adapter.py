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
        from .projects import is_app_note
        self.index = SourceIndex(
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
        return self.index.retrieve(self._roots(extra_dirs, roots), query, k=k,
                                   expansion=expansion, embed=embed)

    def document_spans(self, doc_id: str, extra_dirs: list[str] | tuple[str, ...] = (),
                       roots: list[Path] | None = None) -> list[dict[str, Any]]:
        """Every paragraph of one document (by content hash), in order."""
        return [{k: v for k, v in s.items() if k != "index"}
                for s in self.index.spans(self._roots(extra_dirs, roots))
                if s.get("doc_id") == doc_id]

    def resolve(self, cite: str, extra_dirs: list[str] | tuple[str, ...] = (),
                roots: list[Path] | None = None) -> dict[str, Any] | None:
        return self.index.resolve(self._roots(extra_dirs, roots), cite)

    def glossary_terms(self, text: str, extra_dirs: list[str] | tuple[str, ...] = (),
                       roots: list[Path] | None = None) -> str:
        return self.index.glossary_terms(text, self._roots(extra_dirs, roots))

    def glossary_avoid(self, extra_dirs: list[str] | tuple[str, ...] = (),
                       roots: list[Path] | None = None) -> dict[str, str]:
        """Forms the user corrected, ``{wrong: right}`` (glossary ``| no:``)."""
        getter = getattr(self.index, "glossary_avoid", None)
        return getter(self._roots(extra_dirs, roots)) if getter else {}

    def glossary_entries(self, extra_dirs: list[str] | tuple[str, ...] = (),
                         roots: list[Path] | None = None) -> list[tuple[str, str]]:
        return self.index.glossary_entries(self._roots(extra_dirs, roots))

    def worker_guard(self, declared_model: str):
        """WorkerGuard (invariant I2) bound to the base model this node
        advertises; it refuses to run if the serving backend differs or carries
        a personal adapter. None only if swarmbly_lce is missing."""
        try:
            from swarmbly_lce.worker import WorkerGuard
            return WorkerGuard(declared_model=declared_model)
        except Exception:
            return None
