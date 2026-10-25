"""The delta estimator: dependency density of a decomposition.

WHITEPAPER_V2 §6.8 defines delta as "how many necessary relations cross a
fragment boundary, normalised by the number of fragments". This module turns
that sentence into a mechanical count with **no free parameters**, so that the
number cannot be tuned against the outcome it is meant to predict.

DECLARED BEFORE COMPUTING
=========================
The component list below is fixed. It was written from the definition in §6.8
and from the constraint vocabulary the corpus itself declares, before any
correlation with the coherence tax was examined. Adding a component after
seeing the result would make this a fitted quantity, not a test, so the
component list is asserted against ``COMPONENT_IDS`` at import time.

Structural components (one per global constraint that no single fragment can
discharge on its own):

  S1  aggregate_sum        a requested total spans every row
  S2  aggregate_extremum   a requested extremum spans every row
  S3  term_once            a uniqueness constraint quantifies over the output
  S4  must_mention         a presence constraint quantifies over the output
  S5  no_repeated_ngram    a repeat is a property of a pair of fragments
  S6  no_repeated_sentence  idem
  S7  paragraph_budget     a global structural budget is divided across fragments

Instantiated components (relations the actual data realises against the actual
cut; these are the ones that can vary between prompts of identical shape):

  D1  extremum_separated       the argmax row and the instruction requesting it
                               land in different fragments
  D2  rows_span_cut            data rows appear on both sides of the cut
  D3  goods_crossing           count of goods categories with >=1 row each side
  D4  destination_crossing     count of destinations with >=1 row each side
  D5  extremum_tie             the maximum is achieved by more than one row

delta = (sum of components) / N_fragments
"""

from . import loaders as L

COMPONENT_IDS = (
    "S1_aggregate_sum", "S2_aggregate_extremum", "S3_term_once",
    "S4_must_mention", "S5_no_repeated_ngram", "S6_no_repeated_sentence",
    "S7_paragraph_budget",
    "D1_extremum_separated", "D2_rows_span_cut", "D3_goods_crossing",
    "D4_destination_crossing", "D5_extremum_tie",
)

STRUCTURAL = tuple(c for c in COMPONENT_IDS if c.startswith("S"))
INSTANTIATED = tuple(c for c in COMPONENT_IDS if c.startswith("D"))


def _which_segment(segments, needle):
    """Index of the first segment containing ``needle``; -1 if none."""
    for i, s in enumerate(segments):
        if needle in s:
            return i
    return -1


def components_for(prompt_obj, segments):
    """Count every declared component for one prompt against one partition."""
    prompt = prompt_obj["prompt"]
    constraints = prompt_obj.get("constraints") or []
    kinds = {c["kind"] for c in constraints}
    rows = L.parse_table_rows(prompt)
    n = len(segments)

    c = {k: 0 for k in COMPONENT_IDS}

    # --- structural ----------------------------------------------------------
    low = prompt.lower()
    c["S1_aggregate_sum"] = 1 if ("total weight" in low or "total" in
                                  {x.get("term") for x in constraints}) else 0
    c["S2_aggregate_extremum"] = 1 if ("heaviest" in low or "lightest" in low) else 0
    c["S3_term_once"] = sum(1 for x in constraints if x["kind"] == "term_once")
    c["S4_must_mention"] = sum(1 for x in constraints if x["kind"] == "must_mention")
    c["S5_no_repeated_ngram"] = 1 if "no_repeated_ngram" in kinds else 0
    c["S6_no_repeated_sentence"] = 1 if "no_repeated_sentence" in kinds else 0
    c["S7_paragraph_budget"] = 1 if "paragraph_count" in kinds else 0

    # --- instantiated --------------------------------------------------------
    if rows:
        seg_of = {r[0]: _which_segment(segments, r[0]) for r in rows}
        sides = {s for s in seg_of.values() if s >= 0}
        c["D2_rows_span_cut"] = 1 if len(sides) > 1 else 0

        max_kg = max(r[2] for r in rows)
        argmax = [r for r in rows if r[2] == max_kg]
        c["D5_extremum_tie"] = 1 if len(argmax) > 1 else 0

        # the fragment that is *told* to name the heaviest
        asker = _which_segment(segments, "heaviest")
        if asker >= 0 and argmax:
            c["D1_extremum_separated"] = 1 if all(
                seg_of.get(r[0], -1) != asker for r in argmax) else 0

        c["D3_goods_crossing"] = _crossing(rows, 3, seg_of)
        c["D4_destination_crossing"] = _crossing(rows, 1, seg_of)

    return c, n


def _crossing(rows, field, seg_of):
    """Number of distinct values of ``field`` present on both sides of the cut."""
    by_val = {}
    for r in rows:
        by_val.setdefault(r[field], set()).add(seg_of.get(r[0], -1))
    return sum(1 for v, segs in by_val.items() if len({s for s in segs if s >= 0}) > 1)


def delta_for(prompt_obj, segments):
    """Return (delta_total, delta_struct, delta_data, components)."""
    c, n = components_for(prompt_obj, segments)
    if n <= 0:
        return float("inf"), float("inf"), float("inf"), c
    s = sum(c[k] for k in STRUCTURAL)
    d = sum(c[k] for k in INSTANTIATED)
    return (s + d) / n, s / n, d / n, c


def delta_boundary_weighted(prompt_obj, segments):
    """delta_B: a global constraint crosses EVERY boundary, not just one.

    DECLARED AS A SECOND OPERATIONALISATION, after delta_A failed and for a
    stated reason: with N varying, delta_A's 1/N term dominates and its value
    falls for every prompt at N=8, which carries no per-prompt information.
    delta_B counts a structural relation once per boundary (N-1 of them) before
    normalising, so it rises with N as the coordination burden does.

    Testing a second estimator after the first one fails inflates the
    false-positive rate. Any result from this one is therefore reported at a
    Bonferroni-corrected alpha of 0.025, and treated as exploratory rather than
    as a second independent chance for M4 to pass.
    """
    c, n = components_for(prompt_obj, segments)
    if n <= 0:
        return float("inf")
    s = sum(c[k] for k in STRUCTURAL)
    d = sum(c[k] for k in INSTANTIATED)
    return (s * (n - 1) + d) / n


def delta_table(prompt_ids, prompts, segmenter, n_tasks=2):
    """Compute delta for every prompt against the real partition."""
    out = {}
    for pid in prompt_ids:
        segs = segmenter(prompts[pid]["prompt"], n_tasks)
        total, struct, data, comps = delta_for(prompts[pid], segs)
        out[pid] = {"delta": total, "delta_struct": struct, "delta_data": data,
                    "delta_boundary": delta_boundary_weighted(prompts[pid], segs),
                    "components": comps, "n_segments": len(segs)}
    return out
