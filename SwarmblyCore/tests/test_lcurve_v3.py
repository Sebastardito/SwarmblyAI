"""The v3 L-curve assembler answers every question form it is given.

The v2 assembler implemented 3 of the corpus's 6 global question forms, and the
other three were scored as failures by construction — 44 % of the questions the
fragmented arm could never get right, whatever the fragments returned. The
curve that run produced measured the assembler's coverage, and it was read as a
measurement of fragmentation.

These tests pin the property that matters: with perfect extraction, the
fragmented arm answers every global question in the admitted corpus. And a form
the assembler does not know is recorded as *not computable*, never silently as
wrong.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swarmbly_ref.benchmarks import run_lcurve_v3 as v3  # noqa: E402

CORPUS = ROOT / "prompts" / "lcurve_v2.json"


@pytest.fixture(scope="module")
def corpus() -> dict:
    if not CORPUS.exists():
        pytest.fail("prompts/lcurve_v2.json is missing: the admitted corpus has "
                    "to be version-controlled, or nothing built on it reproduces")
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def test_every_form_in_the_corpus_is_known_to_the_assembler(corpus) -> None:
    forms = {q["form"] for p in corpus["prompts"] for q in p["questions"]
             if q["kind"] == "global"}
    unknown = forms - v3.FORMS
    assert not unknown, (
        f"the corpus has global forms the assembler does not compute: {unknown}. "
        "They would be recorded as not computable and the comparison would "
        "refuse — implement them in run_lcurve_v3.assemble")


def test_perfect_extraction_answers_every_global_question(corpus) -> None:
    wrong = []
    for doc in corpus["prompts"]:
        truth = [v3.parse_row(l) for l in v3.rows_of(doc)]
        on_hand = {r["id"]: r["on_hand"] for r in truth if r}
        wh = {r["id"]: r["warehouse"] for r in truth if r}
        for qid, rec in v3.assemble(doc, on_hand, wh).items():
            if not rec["ok"]:
                wrong.append((doc["id"], qid, rec["form"], rec["got"], rec["expected"]))
    assert not wrong, f"perfect extraction still misses: {wrong[:5]}"


def test_an_unknown_form_is_not_computable_rather_than_wrong() -> None:
    doc = {"questions": [{"id": "01", "kind": "global", "form": "median_of_five",
                          "rows": ["R-001"], "expected": "1", "mode": "numeric"}]}
    rec = v3.assemble(doc, {"R-001": 1}, {})["01"]
    assert rec["computable"] is False and rec["ok"] is False


def test_the_partial_sum_is_read_from_an_equation() -> None:
    rows = ["R-001 | Harbour | seals | on_hand=10 | reorder_at=1",
            "R-002 | Eastdock | gaskets | on_hand=20 | reorder_at=2"]
    text = "1: 10\n2: 20\n3: Harbour\n4: Eastdock\n5: 10 + 20 = 30"
    on_hand, wh, total = v3.parse_fragment(text, rows)
    assert on_hand == {"R-001": 10, "R-002": 20}
    assert wh == {"R-001": "Harbour", "R-002": "Eastdock"}
    assert total == 30


def test_the_mock_pipeline_runs_end_to_end(tmp_path) -> None:
    out = tmp_path / "mock.jsonl"
    v3.main(["--mock-error", "0", "--sizes", "80", "--out", str(out)])
    recs = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    assert recs and all(r["global_ok"] == r["global_n"] == r["global_computable"]
                        for r in recs)
    assert {r["L"] for r in recs} == {5, 10, 20, 40}
    assert all(r["fragments"] and "raw" in r["fragments"][0] for r in recs)


def test_the_full_control_extracts_the_whole_document_in_one_call(tmp_path) -> None:
    """The N=1 arm uses the same extraction and the same assembler; only the
    fragment size changes. That is what lets T08R4 separate splitting from
    aggregating with code."""
    out = tmp_path / "full.jsonl"
    v3.main(["--full-control", "--mock-error", "0", "--out", str(out)])
    recs = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    assert recs and all(r["N"] == 1 and r["L"] == r["n_rows"] for r in recs)
    assert all(r["global_ok"] == r["global_n"] for r in recs)


def test_unnumbered_answers_are_read_by_position() -> None:
    """A model that answers correctly but ignores the 'N: answer' format must
    not score zero: that would measure the format, not the extraction."""
    rows = ["R-001 | Harbour | seals | on_hand=10 | reorder_at=1",
            "R-002 | Eastdock | gaskets | on_hand=20 | reorder_at=2"]
    on_hand, wh, total, mode = v3.parse_fragment("10\n20\nHarbour\nEastdock",
                                                 rows, with_mode=True)
    assert mode == "positional"
    assert on_hand == {"R-001": 10, "R-002": 20}
    assert wh == {"R-001": "Harbour", "R-002": "Eastdock"}
    assert total is None
