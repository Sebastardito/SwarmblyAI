"""The public/private boundary, enforced mechanically rather than remembered.

Two rules, and the second is the one that does the work.

1. Nothing on the private list is in this tree or in the index. The list lives
   in ``.gitignore`` and is parsed from there, so there is exactly one place to
   add a document and no second list to forget.

2. **A document is public if some public artifact points at it.** Stated as a
   test: no tracked file may cite a document that is not in the tree. This is
   what makes the boundary self-enforcing. Moving a document to the vault is
   allowed only when nothing public cites it -- and if something does, this
   test says which file and which line, instead of a reader finding a dead
   link after the repository is public.

   A citation of a document that is *on the private list* is not a dangling
   link: it is the policy naming what must never travel. That is why the two
   lists are read from the same place.
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Start of the block in .gitignore that declares the private set. Everything
# from this marker to the end of the file is the list.
_PRIVATE_MARKER = "# Process and decision records"

_REFERENCE = re.compile(r"[\w.\-]+\.md\b")

# Names that end in .md, are named by a tracked file, and are deliberately not
# documents in this tree. Each one carries its reason, because an allowlist
# without reasons becomes a place to hide a real dangling link.
_NOT_IN_THIS_TREE = {
    # Named in CONTRIBUTING.md in the negative: the project deliberately does
    # not publish a security policy it cannot staff. Adding the file would make
    # the sentence false, not fix it.
    "SECURITY.md": "named in prose as a file this project chose not to have",
    # The four research dossiers REFERENCES.md was consolidated *from*. They
    # are inputs to a document in this tree, never files of it.
    "raw_p2p.md": "source dossier, merged into REFERENCES.md",
    "raw_decomposition.md": "source dossier, merged into REFERENCES.md",
    "raw_genomics.md": "source dossier, merged into REFERENCES.md",
    "raw_governance.md": "source dossier, merged into REFERENCES.md",
    # Written by a run into its results directory. `experiment.TRACE_NAME`.
    "composition_traces.md": "generated per run, not committed",
}


def _tracked() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    return [ROOT / p for p in out]


def private_patterns() -> list[str]:
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert _PRIVATE_MARKER in text, (
        ".gitignore no longer declares the private set. This test reads the "
        "list from there on purpose -- restore the block rather than "
        "duplicating the list here."
    )
    tail = text.split(_PRIVATE_MARKER, 1)[1]
    return [
        line.strip()
        for line in tail.splitlines()
        if line.strip() and not line.startswith("#")
    ]


def _is_private(relative: str) -> bool:
    return any(
        fnmatch.fnmatch(relative, pattern) or relative.startswith(pattern.rstrip("/") + "/")
        for pattern in private_patterns()
    )


def test_the_private_list_is_not_empty() -> None:
    # A list that silently became empty would make every other assertion here
    # pass for the wrong reason.
    assert len(private_patterns()) >= 10


def test_no_private_document_is_tracked() -> None:
    offenders = [
        p.relative_to(ROOT).as_posix()
        for p in _tracked()
        if _is_private(p.relative_to(ROOT).as_posix())
    ]
    assert not offenders, (
        "These files are on the private list and are in the git index. They "
        "are not in the tree by accident -- remove them from the index "
        "(`git rm --cached <path>`) and keep the copy in the vault:\n  "
        + "\n  ".join(offenders)
    )


def test_no_private_document_is_in_the_working_tree() -> None:
    offenders = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git/" in path.as_posix():
            continue
        relative = path.relative_to(ROOT).as_posix()
        if _is_private(relative):
            offenders.append(relative)
    assert not offenders, (
        "These files are on the private list and have reappeared in the "
        "working tree. git will refuse to commit them, but they should not be "
        "here at all -- the copy of record is in ../Swarmbly-Private/:\n  "
        + "\n  ".join(offenders)
    )


def _is_placeholder(name: str) -> bool:
    # Templates spell the future filename out: SWIP-XXXX-short-title.md, and
    # code builds one a piece at a time: f"{stem[:-3]}_ES.md". A fragment is a
    # shape, not a reference.
    return "XXXX" in name or name.startswith(("-", "_"))


def _document_exists(name: str, citing: Path) -> bool:
    if any(
        candidate.exists()
        for candidate in (citing.parent / name, ROOT / "docs" / name, ROOT / name)
    ):
        return True
    # A bare basename may name a tracked file anywhere -- .github templates are
    # cited as `swip.md` from three different directories.
    return any(p.name == name for p in _tracked())


@pytest.mark.parametrize(
    "path",
    [p for p in _tracked() if p.suffix in {".md", ".py", ".sh"}],
    ids=lambda p: p.relative_to(ROOT).as_posix(),
)
def test_no_public_document_cites_a_document_that_is_not_here(path: Path) -> None:
    if not path.exists():  # staged deletion, not yet committed
        pytest.skip("not in the working tree")
    dangling: list[str] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for name in _REFERENCE.findall(line):
            if name in _NOT_IN_THIS_TREE or _is_placeholder(name):
                continue  # deliberate, and argued where the name is listed
            if _is_private(f"docs/{name}") or _is_private(name):
                continue  # the policy naming what must never travel
            if "://" in line and name in line.split("://", 1)[1][:200]:
                continue  # part of a URL
            if not _document_exists(name, path):
                dangling.append(f"line {number}: {name}")
    assert not dangling, (
        f"{path.relative_to(ROOT).as_posix()} points at documents that are not "
        "in this tree. Either the document belongs in the repository after all "
        "-- something public points at it -- or this citation has to be "
        "rewritten before the document leaves:\n  " + "\n  ".join(dangling)
    )
