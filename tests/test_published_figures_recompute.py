"""Every figure the published documents quote is a figure the harness produces.

This is the mechanical answer to the defect the project keeps hitting: *a check
that claims more than it measured*. The variant that survives review is a number
written into a document by hand, which was true on the day it was written and
quietly stops being true the next time the corpus or the code moves.

So the loop is closed here. The harness is run, its results are read, and each
headline figure is rebuilt from them and required to appear **verbatim in both
languages**. A document that drifts from the measurement fails this test and
names the figure; a measurement that moves fails it too, which is the point --
the document is then wrong and has to be updated, not the test.

What this does NOT check: prose, interpretation, or whether the right figure was
chosen. It checks that the number in the document is the number the instrument
returns.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
HARNESS = ROOT / "swarmbly_validation"


@pytest.fixture(scope="module")
def results() -> dict[str, dict]:
    """Run the empirical battery and return its results keyed by test id."""
    finished = subprocess.run(
        [sys.executable, str(HARNESS / "run_real.py")],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert finished.returncode == 0, (
        "the empirical battery did not run:\n" + finished.stdout + finished.stderr
    )
    payload = json.loads((HARNESS / "results_real.json").read_text(encoding="utf-8"))
    rows = payload["results"] if isinstance(payload, dict) else payload
    return {row["id"]: row for row in rows}


def _text(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def _blob(row: dict) -> str:
    """Everything a test emitted, as one searchable string."""
    parts = [row.get("summary", "")] + list(row.get("details", []))
    parts += list(row.get("notes", []))
    for _title, (header, body) in (row.get("tables") or {}).items():
        parts += [str(cell) for cell in header]
        parts += [str(cell) for line in body for cell in line]
    return " | ".join(parts)


#: (test id, the figure as the documents write it, the form the harness emits).
#: The two spellings differ only in typography -- the documents use a Unicode
#: minus and the harness an ASCII hyphen -- so both are given rather than
#: normalised, which would let a real difference through.
CLAIMS = [
    ("T07R", "32/32", "32/32"),
    ("T07R", "19/32", "19/32"),
    ("T04R", "−0.13", "-0.13"),
    ("T04R", "127", "127"),
    ("T03R", "6/35", "6/35"),
    ("T03R", "35/35", "35/35"),
    ("T09R", "−18.32", "-18.32"),
    ("T09R", "−31.00", "-31.00"),
    ("T09R", "−6.95", "-6.95"),
    ("T0RR", "0.38", "0.38"),
    ("T0RR", "−41.9", "-41.9"),
    ("T0RR", "+7.6", "+7.6"),
    ("T0RR", "−10.1", "-10.1"),
    ("T0RR", "−10.5", "-10.5"),
    ("T0RR2", "0.47", "0.47"),
    ("T05R", "7.5", "7.5"),
    ("T06R", "21/21", "21/21"),
    ("T0LR", "+0.015", "+0.015"),
]

#: The documents that quote the campaign. Both languages of each pair, because a
#: figure that drifts in one language only is the failure mode this catches.
QUOTING = [
    "WHITEPAPER_V2_ES.md", "WHITEPAPER_V2_EN.md",
    "RESULTS_2026-09-25_refbench_ES.md", "RESULTS_2026-09-25_refbench_EN.md",
]


@pytest.mark.parametrize(
    "test_id,in_docs,in_harness",
    CLAIMS,
    ids=[f"{t}:{d}" for t, d, _ in CLAIMS],
)
def test_the_harness_still_produces_the_published_figure(
    results: dict, test_id: str, in_docs: str, in_harness: str
) -> None:
    row = results.get(test_id)
    assert row is not None, (
        f"{test_id} is quoted in the documents and the harness no longer emits "
        "it. Either the test was renamed -- update the citation -- or it stopped "
        "running, which is worse."
    )
    blob = _blob(row)
    assert in_harness in blob, (
        f"{test_id} no longer produces {in_harness!r}, which the published "
        f"documents quote. The measurement moved; the documents have to move "
        f"with it.\n  harness now says: {row.get('summary')!r}"
    )


@pytest.mark.parametrize(
    "test_id,in_docs,in_harness",
    CLAIMS,
    ids=[f"{t}:{d}" for t, d, _ in CLAIMS],
)
def test_some_document_quotes_each_checked_figure(
    results: dict, test_id: str, in_docs: str, in_harness: str
) -> None:
    # A claim list that drifts out of the documents stops protecting anything,
    # so the list itself is checked against them.
    citing = [name for name in QUOTING if in_docs in _text(name)]
    assert citing, (
        f"no published document quotes {in_docs!r} ({test_id}) any more. Either "
        "the citation was removed -- drop it from CLAIMS -- or it was rewritten "
        "into a form this test cannot see, which defeats the check."
    )


@pytest.mark.parametrize("name", QUOTING, ids=lambda n: n)
def test_the_campaign_size_is_stated_consistently(name: str) -> None:
    assert "341" in _text(name), (
        f"{name} no longer states the size of the corpus it rests on."
    )


def test_the_favourable_aggregate_never_travels_without_its_refusal(
    results: dict,
) -> None:
    """The one mistake the project must never make by accident.

    The aggregate tax favours fragmenting (−18.32 %) and is confounded with the
    output budget, so it settles nothing. The risk is not that a document says
    "criterion met" in those words -- several say it precisely to reject it, and
    a substring search for the phrase reports them all, which is a test that
    cries wolf and gets satisfied rather than believed.

    The risk is the **number travelling alone**. So that is what is checked: any
    document that quotes the favourable figure must also carry the refusal in
    the same document. This is the check that would have caught the funding case
    reporting "se cumple con margen" under a verdict of REFUSED.
    """
    verdict = results["T09R"]["verdict"].upper()
    if verdict != "REFUSE":
        pytest.skip(f"T09R now reports {verdict}; this guard applies while it refuses")

    # Deliberately narrow. A bare "refuse" matches a section heading about
    # unrelated refusal conditions, which would pass a document for the wrong
    # reason -- and a guard that passes for the wrong reason is worse than none.
    caveats = ("rehusado", "sin medir", "no se ha medido", "no se puede usar",
               "refused", "not been measured", "cannot be used",
               "confundido", "confounded")
    offenders = []
    for path in sorted(DOCS.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if "18.32" not in text:
            continue
        lowered = text.lower()
        if not any(word in lowered for word in caveats):
            offenders.append(path.name)
    assert not offenders, (
        "these documents quote the favourable aggregate (−18.32 %) without "
        "saying anywhere that the harness refuses to rule on it. The number "
        "alone reads as a result and is not one:\n  " + "\n  ".join(offenders)
    )
