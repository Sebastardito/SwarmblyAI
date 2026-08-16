"""Guards on the labelled prompt corpus itself.

These exist because the corpus broke silently once. In the run of 14 August 2026
``rag_summarization_filings`` produced a monolithic baseline of one sentence and
six tokens, its twelve cells were excluded, and the coherence-tax table was
computed over seven categories while being reported as eight. The cause was one
phrase: the prompt said *"the 12 regulatory filings listed below"* and there was
nothing below.

That is the corpus's one structural hazard. Every prompt deliberately names a
body of material it does not enclose -- the Northwind Ledger export, the
Meridian compliance bundle, the Helios evaluation batch -- so that prompts stay
inside the length band ``_length_note`` requires for the low-rho end of the
sweep to be reachable. A model instantiates plausible material and the
tax compares monolithic against fragmented on the same instantiation, which
keeps it a valid relative statistic.

Naming a corpus is fine. *Pointing* at one is not: deixis promises an enclosure,
and a small model correctly answers that it cannot see it. The difference
between the two is invisible on a read-through and fatal to a cell, so it is
asserted here instead.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from swarmbly_v0.textutil import count_tokens

CORPUS_PATH = Path(__file__).resolve().parent.parent / "prompts" / "prompts.json"

# Expressed in *canonical* tokens -- what ``textutil.count_tokens`` counts, and
# therefore what ``packing.py`` divides by when it computes rho. These are
# roughly words, not BPE pieces; a model tokenizer reports about 1.3x more.
# The corpus as shipped sits at 124-160. The guard is set wider than that so it
# catches drift rather than bikeshedding, and narrow enough that a prompt which
# has quietly become a document trips it.
#
# Below the band, per-packet framing pushes the reachable rho floor above 1.0 --
# which is not hypothetical: the run of 14 August 2026 targeted rho = 1.00 and
# achieved 1.17. Above it, the prompt stops resembling the workload under study.
MIN_TOKENS = 120
MAX_TOKENS = 250

# Words that promise material enclosed with the prompt. "following" is included
# because "the following series" reads exactly like "the series below".
DEIXIS = re.compile(
    r"\b(?:listed\s+below|shown\s+below|below|above|as\s+follows|the\s+following|attached|enclosed)\b",
    re.IGNORECASE,
)


def _corpus() -> dict:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def _prompts() -> list[dict]:
    payload = _corpus()
    return payload["prompts"] if isinstance(payload, dict) else payload


def _ids(entries: list[dict]) -> list[str]:
    return [e["id"] for e in entries]


@pytest.fixture(scope="module")
def prompts() -> list[dict]:
    return _prompts()


def test_corpus_parses_and_is_not_empty(prompts: list[dict]) -> None:
    assert prompts, "the prompt corpus is empty"
    for entry in prompts:
        for field in ("id", "category", "expected_decomposable", "prompt"):
            assert field in entry, f"{entry.get('id', '<no id>')} is missing '{field}'"


def test_prompt_ids_are_unique(prompts: list[dict]) -> None:
    ids = _ids(prompts)
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    assert not duplicates, f"duplicate prompt ids: {duplicates}"


@pytest.mark.parametrize("entry", _prompts(), ids=_ids(_prompts()))
def test_prompt_does_not_point_at_absent_material(entry: dict) -> None:
    """No prompt may promise an enclosure the file does not contain.

    A prompt may *name* a corpus ("the Meridian compliance bundle"); it may not
    *point* at one ("the filings listed below"). The first lets a model proceed,
    which is what the measurement needs. The second produces a refusal, a
    near-zero baseline, and a silently excluded row.
    """
    hits = sorted({m.group(0).lower() for m in DEIXIS.finditer(entry["prompt"])})
    assert not hits, (
        f"{entry['id']} points at material that is not in the file: {hits}. "
        "Name the corpus instead of pointing at it -- see the module docstring, "
        "and prompts.json '_corpus_note'."
    )


@pytest.mark.parametrize("entry", _prompts(), ids=_ids(_prompts()))
def test_prompt_length_stays_in_the_documented_band(entry: dict) -> None:
    n = count_tokens(entry["prompt"])
    assert MIN_TOKENS <= n <= MAX_TOKENS, (
        f"{entry['id']} is {n} tokens, outside the {MIN_TOKENS}-{MAX_TOKENS} band "
        "that prompts.json '_length_note' requires. Too short and packet framing "
        "pushes the reachable rho floor above 1.0; too long and the prompt stops "
        "being the workload under study."
    )


def test_both_router_labels_are_represented(prompts: list[dict]) -> None:
    """The corpus doubles as the router evaluation set, so it needs both classes."""
    labels = {bool(e["expected_decomposable"]) for e in prompts}
    assert labels == {True, False}, (
        "the corpus must contain both decomposable and non-decomposable prompts; "
        f"found only {labels}"
    )


def test_the_corpus_note_is_present() -> None:
    """The reasoning must travel with the data, or the hazard returns."""
    payload = _corpus()
    assert isinstance(payload, dict), "corpus lost its metadata wrapper"
    note = payload.get("_corpus_note", "")
    assert "deixis" in note.lower(), (
        "'_corpus_note' should record why prompts name a corpus rather than "
        "enclosing one; without it the next author reintroduces the bug"
    )
