"""Every document declares whether it may be quoted, and the index agrees.

This project's documents contradict each other on purpose: a result is
measured, then re-measured on a corrected instrument, and the first document
stays in the repository so that the correction is visible rather than tidied
away. That only works if a reader can tell, without opening a file, which of
two figures is the one that stands.

Before these tests that lived in prose -- twelve documents carried a withdrawal
notice in six different wordings, and nothing connected them. Here the status
is a declared field, the successor has to exist, and ``docs/STATUS.md`` is
generated from the documents rather than maintained beside them.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

sys.path.insert(0, str(ROOT / "scripts"))
from make_status import VALID, front_matter  # noqa: E402

DOCUMENTS = sorted(p for p in DOCS.glob("*.md") if p.name != "STATUS.md")


def _ids(path: Path) -> str:
    return path.name


@pytest.mark.parametrize("path", DOCUMENTS, ids=_ids)
def test_every_document_declares_a_status(path: Path) -> None:
    status = front_matter(path).get("status")
    assert status in VALID, (
        f"{path.name} declares status {status!r}. A document without a declared "
        f"status is one a reader has to open to find out whether it may be "
        f"quoted. Use one of: {', '.join(VALID)}."
    )


@pytest.mark.parametrize("path", DOCUMENTS, ids=_ids)
def test_a_superseded_document_names_a_successor_that_exists(path: Path) -> None:
    fields = front_matter(path)
    if fields.get("status") != "superseded":
        return
    successor = fields.get("superseded_by", "")
    assert successor, f"{path.name} is superseded by nothing named."
    assert (DOCS / successor).exists(), (
        f"{path.name} points at {successor}, which is not in docs/. A successor "
        "that does not exist sends the reader nowhere -- worse than no notice, "
        "because it looks like one."
    )
    assert successor != path.name, f"{path.name} supersedes itself."


@pytest.mark.parametrize("path", DOCUMENTS, ids=_ids)
def test_a_withdrawal_says_why(path: Path) -> None:
    fields = front_matter(path)
    status = fields.get("status")
    if status not in ("withdrawn", "partially_withdrawn", "superseded", "historical"):
        return
    assert fields.get("reason", "").strip(), (
        f"{path.name} is {status} without a reason. The reason is the part that "
        "stops the figure being quoted again by someone who does not know why "
        "it fell."
    )
    if status == "partially_withdrawn":
        assert fields.get("stands", "").strip(), (
            f"{path.name} is partially withdrawn without saying which part "
            "stands, which leaves the reader unable to use either half."
        )


def test_no_chain_of_successors_ends_in_a_withdrawn_document() -> None:
    status = {p.name: front_matter(p) for p in DOCUMENTS}
    for name, fields in status.items():
        seen = [name]
        current = fields
        while current.get("status") == "superseded":
            successor = current.get("superseded_by", "")
            assert successor not in seen, f"supersession cycle: {' -> '.join(seen)}"
            seen.append(successor)
            current = status.get(successor, {})
        if len(seen) == 1:
            continue  # nothing redirected here; a withdrawal can be terminal
        assert current.get("status") != "withdrawn", (
            f"following {name} leads to {seen[-1]}, which is withdrawn. "
            "A reader redirected from one document to another expects to arrive "
            "somewhere quotable."
        )


def test_the_index_matches_the_documents() -> None:
    finished = subprocess.run(
        [sys.executable, "scripts/make_status.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert finished.returncode == 0, (
        "docs/STATUS.md no longer describes the documents. It is generated, not "
        "maintained -- run `python3 scripts/make_status.py`.\n" + finished.stdout
    )
