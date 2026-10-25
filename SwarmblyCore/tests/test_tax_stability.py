"""The headline tax is a ratio. These tests are about its denominator.

The first real run against Ollama reported an entity-grid "coherence tax" of
**-180 %** — fragmentation supposedly tripling coherence. It was not a finding
about the architecture. The entity grid legitimately returns near zero for a
short answer with few repeated entities, and a ratio over a near-zero
denominator is not a measurement.

Two separate confounds are pinned here, because both were live in that run:
a denominator small enough to make the ratio meaningless, and k=1 and k>1 cells
averaged into a single number that belongs to neither.
"""

from __future__ import annotations

from swarmbly_v0.experiment import MIN_BASELINE, summarize


def _cell(**kw):
    row = {
        "condition": "fragmented", "prompt_id": "p1", "category": "bulk_extraction",
        "rho_target": 1.0, "rho_achieved": 1.08, "n_tasks": 2, "k": 1,
        "booook_like_score": 0.5, "entity_grid": 0.5,
        "baseline_booook": 0.9, "baseline_entity_grid": 0.9,
        "coherence_tax_booook": 0.0, "coherence_tax_entity_grid": 0.0,
    }
    row.update(kw)
    return row


# --------------------------------------------------------------------------
# The denominator
# --------------------------------------------------------------------------


def test_the_reported_minus_180_percent_case_is_excluded_and_counted():
    """baseline 0.05, fragmented 0.14 -> -180 %. Not a measurement."""
    rows = [
        _cell(baseline_entity_grid=0.05, entity_grid=0.14,
              coherence_tax_entity_grid=-1.8),
        _cell(prompt_id="p2", baseline_entity_grid=0.80, entity_grid=0.60,
              coherence_tax_entity_grid=0.25),
    ]
    stats = summarize(rows)
    point = stats["curve"][0]

    assert point["coherence_tax_entity_grid"] == 0.25, "the unstable cell must not average in"
    assert point["n_cells_entity_grid"] == 1
    assert stats["unstable_cells"]["excluded_entity_grid"] == 1
    assert stats["unstable_cells"]["min_baseline"] == MIN_BASELINE


def test_the_absolute_difference_survives_a_degenerate_denominator():
    """abs_delta is the denominator-free version and keeps every cell."""
    rows = [_cell(baseline_entity_grid=0.05, entity_grid=0.14,
                  coherence_tax_entity_grid=-1.8)]
    point = summarize(rows)["curve"][0]
    assert point["abs_delta_entity_grid"] == -0.09
    assert point["coherence_tax_entity_grid"] is None, "no stable cell: absent, not zero"


def test_a_healthy_denominator_is_untouched():
    rows = [_cell(baseline_entity_grid=0.90, entity_grid=0.45,
                  coherence_tax_entity_grid=0.5)]
    stats = summarize(rows)
    assert stats["curve"][0]["coherence_tax_entity_grid"] == 0.5
    assert stats["unstable_cells"]["excluded_entity_grid"] == 0


def test_negative_taxes_are_reported_not_clipped():
    """Fragmentation genuinely helping must survive; clipping would bias it."""
    rows = [_cell(baseline_booook=0.90, booook_like_score=0.99,
                  coherence_tax_booook=-0.1)]
    assert summarize(rows)["curve"][0]["coherence_tax_booook"] == -0.1


def test_rows_without_a_recorded_denominator_are_kept():
    """Older CSVs carry no baseline column; dropping them would be silent loss."""
    row = _cell(coherence_tax_entity_grid=0.3)
    del row["baseline_entity_grid"]
    stats = summarize([row])
    assert stats["curve"][0]["coherence_tax_entity_grid"] == 0.3
    assert stats["unstable_cells"]["excluded_entity_grid"] == 0


# --------------------------------------------------------------------------
# The k confound
# --------------------------------------------------------------------------


def test_headline_comes_from_k1_when_a_run_spans_several_k():
    rows = [
        _cell(k=1, coherence_tax_booook=0.00),
        _cell(k=3, coherence_tax_booook=0.40, prompt_id="p2"),
    ]
    stats = summarize(rows)
    assert stats["headline_k"] == 1
    assert stats["headline_restricted_to_k"] is True
    assert stats["ks_present"] == [1, 3]
    assert stats["curve"][0]["coherence_tax_booook"] == 0.0, "k=3 must not drag the headline"


def test_a_single_k_run_is_not_restricted():
    rows = [_cell(k=1, coherence_tax_booook=0.2)]
    stats = summarize(rows)
    assert stats["headline_restricted_to_k"] is False
    assert stats["curve"][0]["coherence_tax_booook"] == 0.2


def test_the_consensus_curve_still_sees_every_k():
    """Restricting the headline must not delete the axis k exists to measure."""
    rows = [
        _cell(k=1, mean_agreement=0.0, n_families=1),
        _cell(k=3, prompt_id="p2", mean_agreement=0.6, n_families=3),
    ]
    ks = {int(c["k"]) for c in summarize(rows)["consensus_curve"]}
    assert ks == {1, 3}


def test_go_no_go_is_judged_on_the_headline_k_only():
    """A k=3 cell must not be able to fail a criterion about the assembly pipeline."""
    rows = [
        _cell(k=1, category="bulk_extraction", coherence_tax_booook=0.01),
        _cell(k=3, category="bulk_extraction", prompt_id="p2",
              coherence_tax_booook=0.45),
    ]
    stats = summarize(rows)
    assert stats["go_no_go"]["passed"] is True


# --------------------------------------------------------------------------
# "Not measured" must never render as "no degradation"
# --------------------------------------------------------------------------


def test_a_curve_point_with_no_surviving_cell_is_none_not_zero():
    """0.0 would read as 'fragmentation cost nothing'. It means nothing at all."""
    rows = [_cell(baseline_booook=0.02, baseline_entity_grid=0.02,
                  coherence_tax_booook=-3.0, coherence_tax_entity_grid=-4.0)]
    point = summarize(rows)["curve"][0]
    assert point["coherence_tax_booook"] is None
    assert point["coherence_tax_entity_grid"] is None
    assert point["abs_delta_booook"] is not None, "the stable statistic survives"


def test_an_unmeasured_cell_cannot_pass_the_go_no_go():
    rows = [_cell(baseline_booook=0.02, coherence_tax_booook=-3.0)]
    stats = summarize(rows)
    assert stats["go_no_go"]["passed"] is False
    assert stats["go_no_go"]["passing_cells"] == []
    assert stats["best_overall"] is None


def test_measured_and_unmeasured_cells_coexist():
    rows = [
        _cell(prompt_id="p1", baseline_booook=0.02, coherence_tax_booook=-3.0),
        _cell(prompt_id="p2", category="synthetic_data",
              baseline_booook=0.90, coherence_tax_booook=0.01),
    ]
    stats = summarize(rows)
    assert stats["go_no_go"]["passed"] is True
    assert len(stats["go_no_go"]["passing_cells"]) == 1


def test_the_html_report_survives_an_unmeasured_curve_point():
    """The chart used to crash on None. A gap must be drawn as a gap."""
    import pathlib, tempfile
    from swarmbly_v0.experiment import write_csv
    from swarmbly_v0.report import render_report

    rows = [_cell(baseline_booook=0.02, baseline_entity_grid=0.02, judge_score=0.5,
                  baseline_judge=0.5, quality_tax_judge=0.0,
                  coherence_tax_booook=-3.0, coherence_tax_entity_grid=-4.0)]
    out = pathlib.Path(tempfile.mkdtemp())
    csv = write_csv(rows, out / "r.csv")
    render_report(csv, out / "r.html", {"backend": "openai-compat"}, None)
    body = (out / "r.html").read_text()
    assert len(body) > 1000
    # The aggregate must not present it: no chart point, and "-" in the curve table.
    assert "-300.00%" not in body, "an unmeasured cell must not be rendered as a headline"
    # The raw per-cell table must still carry it, next to the denominator that
    # explains it. That table is the audit surface; hiding the input would be
    # the worse failure.
    assert "-3.0" in body and "0.02" in body


# --------------------------------------------------------------------------
# The relative headline and the absolute must be the SAME comparison
#
# On the v3c-gt run of 4 September every monolithic baseline was exactly 1.000
# -- the case where a relative difference and an absolute difference must
# coincide -- and the summary printed +21.15 % beside +0.4335.
#
# The gap was not the denominator. `coherence_tax_booook` is computed on
# `booook_comparable`, which drops the seam-anchored and assembler-enforced
# classes because a monolithic text has no seams and so cannot incur them; the
# absolute was computed on `booook_like_score`, which does. Those classes charge
# the fragmented arm more the more it is fragmented -- 5.7 points at N=2 and
# 10.1 at N=8 on the table run of 26 August -- so the "denominator-free version
# of the same comparison" was silently the biased figure the comparable score
# was introduced to retire.
# --------------------------------------------------------------------------


def _paired(**kw):
    """A cell whose baseline is 1.0, where relative and absolute must agree."""
    row = {
        "booook_like_score": 0.40, "booook_comparable": 0.70,
        "baseline_booook": 1.0, "baseline_booook_comparable": 1.0,
        "coherence_tax_booook": 0.30,     # 1.0 -> 0.70 on the comparable score
    }
    row.update(kw)
    return _cell(**row)


def test_the_absolute_difference_uses_the_same_score_as_the_headline():
    point = summarize([_paired()])["curve"][0]
    assert point["coherence_tax_booook"] == 0.30
    assert point["abs_delta_booook"] == 0.30, (
        "with a baseline of exactly 1.0 the relative and absolute figures are "
        "arithmetically the same number; a disagreement means they are not the "
        "same score, and the summary calls them the same comparison")


def test_the_full_score_absolute_is_kept_but_under_its_own_name():
    """The figure of record from before 26 August is not deleted, only named."""
    point = summarize([_paired()])["curve"][0]
    assert point["abs_delta_booook_full"] == 0.60, (
        "the full score keeps the seam and assembler-enforced classes, so it "
        "must still be available -- it is simply not the headline's absolute")
    assert point["abs_delta_booook_full"] != point["abs_delta_booook"]


def test_a_run_without_the_comparable_column_falls_back_to_the_full_score():
    """Runs recorded before booook_comparable existed must still summarise.

    Both sides fall back together. Taking the comparable baseline against a
    missing comparable score would read the absent column as 0.0 and report a
    total loss of 1.0000 for a cell that scored 0.4.
    """
    row = _cell(booook_like_score=0.4, baseline_booook=1.0,
                coherence_tax_booook=0.6)
    row.pop("booook_comparable", None)
    point = summarize([row])["curve"][0]
    assert point["abs_delta_booook"] == 0.6, (
        "a legacy row must fall back on both sides at once")


# --------------------------------------------------------------------------
# A criterion that cannot fire is not a criterion that passed
#
# v0's corpus holds one prompt per category and the declared cell is
# (category, rho, N, k). `falsifiable_go_no_go` needs two clusters to form an
# interval, so on that corpus it returns `passed: null` for every cell -- forty
# of them on the run of 4 September -- while the tier printed "read
# falsifiable_go_no_go instead" and a superseded maximum statistic reading
# "passes (20 passing cells)".
# --------------------------------------------------------------------------


def test_a_census_counts_the_cells_that_returned_no_verdict():
    """One prompt per category: every cell refuses, and the count says so."""
    rows = [_cell(category="bulk_extraction", prompt_id="p1"),
            _cell(category="long_report", prompt_id="p2")]
    census = summarize(rows)["falsifiable_go_no_go_census"]
    assert census["with_a_verdict"] == 0
    assert census["refused"] == census["cells"] > 0
    assert census["max_observations_in_any_cell"] == 1, (
        "1 is the diagnosis: no grid and no rerun can form an interval here")


def test_the_census_records_a_verdict_when_the_cell_can_form_one():
    rows = [_cell(category="bulk_extraction", prompt_id="p1",
                  coherence_tax_booook=0.01),
            _cell(category="bulk_extraction", prompt_id="p2",
                  coherence_tax_booook=0.02)]
    census = summarize(rows)["falsifiable_go_no_go_census"]
    assert census["with_a_verdict"] == 1
    assert census["max_observations_in_any_cell"] == 2
