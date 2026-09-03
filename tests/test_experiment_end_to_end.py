"""End-to-end: the sweep runs, the CSV is tidy, the report renders, the CLI works."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from swarmbly_v0 import get_backend, get_embedder, load_prompts, render_report, run_sweep
from swarmbly_v0.cli import main
from swarmbly_v0.experiment import CSV_COLUMNS, SweepConfig, summarize, write_csv


@pytest.fixture(scope="module")
def sweep(tmp_path_factory: pytest.TempPathFactory):
    prompts = load_prompts()[:3]
    # rho 2.5 and 3.5, not 1.25 and 2.0. The honest packing floors on these three
    # prompts run 1.425 to 2.228, so EVERY rho=1.25 cell was below floor, as was
    # rho=2.0 at N=4 on the widest prompt. Below the floor `build_packet` sets
    # `budget = max(mandatory_tokens, ...)` and each packet collapses to its bare
    # task, so those cells measured "no context at all", not "a context budget of
    # 1.25". This grid is entirely reachable, which is what makes the rho axis an
    # axis.
    config = SweepConfig(rhos=(2.5, 3.5), ns=(2, 4), seed=0)
    rows, metadata = run_sweep(
        prompts, config, get_backend("mock", seed=0), get_embedder("hash")
    )
    out = tmp_path_factory.mktemp("results")
    csv_path = write_csv(rows, out / "results.csv")
    return prompts, rows, metadata, csv_path


def test_sweep_produces_one_baseline_and_every_cell(sweep) -> None:
    prompts, rows, _, _ = sweep
    monolithic = [r for r in rows if r["condition"] == "monolithic"]
    fragmented = [r for r in rows if r["condition"] == "fragmented"]

    assert len(monolithic) == len(prompts)
    assert len(fragmented) == len(prompts) * 2 * 2


def test_csv_has_the_expected_columns_and_is_non_empty(sweep) -> None:
    _, rows, _, csv_path = sweep
    with open(csv_path, encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        data = list(reader)

    assert header == CSV_COLUMNS
    assert len(data) == len(rows)
    assert csv_path.stat().st_size > 0
    for column in ("rho_target", "rho_achieved", "booook_like_score", "entity_grid",
                   "coherence_tax_booook", "err_missing_transition"):
        assert column in header
    assert "_text" not in header  # internal field must not leak into results


def test_tau_is_calibrated_not_hardcoded(sweep) -> None:
    _, _, metadata, _ = sweep
    assert 0.0 < metadata["tau_sem"] < 1.0
    assert metadata["tau_calibration"] is not None
    assert metadata["tau_calibration"]["beta"] < 1.0
    assert metadata["harness_validation_only"] is True


def test_coherence_tax_is_defined_for_every_fragmented_cell(sweep) -> None:
    _, rows, _, _ = sweep
    for row in rows:
        if row["condition"] != "fragmented":
            continue
        assert isinstance(row["coherence_tax_booook"], float)
        assert isinstance(row["coherence_tax_entity_grid"], float)
        assert row["n_seams"] == row["n_tasks"] - 1
        assert row["n_bridges"] <= row["n_seams"]
        assert row["output_tokens"] > 0


def test_rho_achieved_tracks_the_target_when_reachable(sweep) -> None:
    _, rows, _, _ = sweep
    for row in rows:
        if row["condition"] != "fragmented" or not row["rho_reachable"]:
            continue
        assert row["rho_achieved"] == pytest.approx(row["rho_target"], rel=0.06)


def test_the_curve_has_one_point_per_reachable_rho_and_no_others(sweep) -> None:
    """What this fixture can honestly assert about the rho axis.

    It used to read ``test_coherence_tax_falls_as_rho_rises`` -- "the headline
    relationship the harness exists to measure" -- and assert
    ``curve[1].tax < curve[0].tax`` on a grid of rho 1.25 and 2.0 where every
    1.25 cell was below its packing floor. Below the floor a packet holds its
    bare task and nothing else, so the low-rho point was not a starved context
    budget, it was NO context budget, and it manufactured the descent the
    assertion then read as the headline result. Run the same fixture on a
    reachable grid and the mock backend's tax *rises* with rho, at every grid
    tried.

    That is not a finding about fragmentation -- it is a mock backend, and it
    says nothing about models. It is a finding about the test: the direction of
    the coherence-tax curve is a claim about a real run, and a harness-validation
    fixture cannot carry it. What the fixture can assert is that the axis exists:
    one point per rho, ordered, both defined, none of them below floor.
    """
    _, rows, _, _ = sweep
    stats = summarize(rows)
    curve = stats["curve"]

    assert stats["rows_excluded_below_floor"] == 0, \
        "the fixture grid must sit above the packing floor, or it measures nothing"
    assert [c["rho"] for c in curve] == [2.5, 3.5]
    assert all(isinstance(c["coherence_tax_booook"], float) for c in curve)
    # rho_achieved tracks the target because the target was reachable. This is
    # the property that was false for every dropped cell.
    assert all(c["rho_achieved_mean"] == pytest.approx(c["rho"], rel=0.06) for c in curve)


def test_a_below_floor_cell_is_dropped_from_every_figure(sweep) -> None:
    """The guard itself, on the grid that exposed it.

    V0 swept rho 1.0 to 2.0 on a corpus whose floors ran 1.85 to 2.35 at N=4.
    Every fragmented cell was written ``rho_reachable: False``; nothing in the
    analysis read the field; a coherence-tax curve was published against an axis
    that had never moved. The flag was not missing -- nothing consulted it.
    """
    prompts, _, _, _ = sweep
    below, _ = run_sweep(prompts, SweepConfig(rhos=(1.25,), ns=(4,), seed=0),
                         get_backend("mock", seed=0), get_embedder("hash"))
    assert not any(r["rho_reachable"] for r in below if r["condition"] == "fragmented"), \
        "this grid is supposed to be entirely below floor"

    stats = summarize(below)
    assert stats["rows_excluded_below_floor"] > 0
    assert stats["curve"] == [], "a curve built only from below-floor cells must be empty"
    assert stats["fragment_size_curve"]["points"] == [], \
        "fragment_size_curve fell back to the unreachable rows when no reachable slice existed"


def test_summary_reports_a_go_no_go_verdict(sweep) -> None:
    prompts, rows, _, _ = sweep
    stats = summarize(rows, prompts)

    assert "passed" in stats["go_no_go"]
    assert isinstance(stats["go_no_go"]["passed"], bool)
    assert stats["best_overall"] is not None
    assert "router" in stats


def test_sweep_is_reproducible_under_a_seed() -> None:
    prompts = load_prompts()[:2]
    config = SweepConfig(rhos=(1.5,), ns=(2,), seed=11)
    first, _ = run_sweep(prompts, config, get_backend("mock", seed=11), get_embedder("hash"))
    second, _ = run_sweep(prompts, config, get_backend("mock", seed=11), get_embedder("hash"))

    keys = ("booook_like_score", "entity_grid", "rho_achieved", "coherence_tax_booook")
    assert [[r[k] for k in keys] for r in first] == [[r[k] for k in keys] for r in second]


def test_report_is_self_contained_html(sweep, tmp_path: Path) -> None:
    prompts, _, metadata, csv_path = sweep
    html_path = render_report(csv_path, tmp_path / "report.html", metadata, prompts)
    html = html_path.read_text(encoding="utf-8")

    assert html_path.stat().st_size > 5000
    assert html.startswith("<!DOCTYPE html>")
    assert "<svg" in html and "</svg>" in html
    assert "HARNESS VALIDATION ONLY" in html
    # Self-contained: no external fetches of any kind.
    for forbidden in ("http://", "https://", "cdn.", "<link", "src="):
        assert forbidden not in html, f"report must not reference {forbidden}"
    # Chart conventions.
    assert "#2a78d6" in html and "#3987e5" in html
    assert 'stroke-width="2"' in html
    assert 'r="5"' in html
    assert "<table" in html


def test_cli_run_and_report(tmp_path: Path) -> None:
    out = tmp_path / "results"
    code = main([
        "run", "--rho", "1.25,2.0", "--n", "2", "--backend", "mock",
        "--out", str(out), "--max-prompts", "2", "--quiet", "--no-report",
    ])
    assert code == 0

    csv_path = out / "results.csv"
    assert csv_path.exists() and csv_path.stat().st_size > 0
    assert json.loads((out / "summary.json").read_text(encoding="utf-8"))["curve"]
    assert json.loads((out / "run_metadata.json").read_text(encoding="utf-8"))["tau_sem"]

    assert main(["report", str(csv_path), "--out", str(out / "report.html")]) == 0
    assert (out / "report.html").stat().st_size > 5000


def test_cli_route_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["route"]) == 0
    captured = capsys.readouterr().out
    assert "accuracy=" in captured
    assert "bulk_extraction_invoices" in captured


def test_cli_report_missing_file_fails_cleanly(tmp_path: Path) -> None:
    assert main(["report", str(tmp_path / "nope.csv")]) == 2


def test_prompt_corpus_is_well_formed() -> None:
    prompts = load_prompts()
    categories = {spec.category for spec in prompts}

    assert len(prompts) == 8
    assert len(categories) == 8
    assert {"bulk_extraction", "synthetic_data", "long_report", "multi_hop_math",
            "code_shared_state", "rag_summarization", "evaluation_judging",
            "creative_writing"} == categories
    assert any(spec.expected_decomposable for spec in prompts)
    assert any(not spec.expected_decomposable for spec in prompts)
    assert len({spec.prompt_id for spec in prompts}) == 8
