"""Verdicts for C1 and C2, exactly as fixed by PREREGISTRATION_C1_C2 (2026-10-05).

The rules live in code so that the decision cannot drift after the data are
seen. ``decide(results)`` takes the dict written by ``run_real`` and returns,
for each hypothesis, one of ``holds``, ``falsified``, ``inconclusive``,
``refused`` (the instrument cannot decide) or ``not_tested``, with the reason.

Changing a threshold here after the first confirmatory run is a protocol
deviation and must be declared in the pre-registration's amendments section.

Amendment 2 (5 October 2026, after run 1 and before run 2) adds the manipulation
check: if the projection did not reach the writer, the C2 verdicts are refused.
"""

from __future__ import annotations

from typing import Any

# Thresholds fixed by the pre-registration.
C1_MIN_ACC_WITH = 0.70
C1_MIN_GAIN = 0.50
MIN_CLAIMS = 5
EQUIV_MARGIN = 0.10
MIN_JOINTLY_WRONG = 200
MAX_INVALID = 0.10
MIN_FAMILIES = 3
# Amendment 2 (after run 1): manipulation check. Γ must actually reach the writer.
MIN_PROJ_BYTES = 20
MIN_NONEMPTY = 0.80

__all__ = ["decide", "EQUIV_MARGIN"]


def _v(verdict: str, reason: str, **kw: Any) -> dict[str, Any]:
    return {"verdict": verdict, "reason": reason, **kw}


def decide(results: dict[str, Any]) -> dict[str, Any]:
    hdr = results.get("header", {})
    out: dict[str, Any] = {}
    global_refusals = []
    if not hdr.get("confirmatory"):
        global_refusals.append("run is exploratory (no committed pre-registration, or dirty tree)")
    if hdr.get("embed_model") in (None, "", "hash-fallback"):
        global_refusals.append("no real embedding model: homogeneity is measured with the hash fallback")
    if int(hdr.get("distinct_families", 0)) < MIN_FAMILIES:
        global_refusals.append(f"fewer than {MIN_FAMILIES} model families")

    # C1 — positive control of retrieval over a wiki digested by a real model.
    bw = results.get("build_wiki", {})
    c1 = results.get("C1", {})
    if bw.get("claims", 0) < MIN_CLAIMS:
        out["C1"] = _v("refused", f"wiki has fewer than {MIN_CLAIMS} claims: digestion/anchoring failed, nothing downstream is interpretable")
    elif c1.get("acc_with_memory", 0) >= C1_MIN_ACC_WITH and c1.get("gain", 0) >= C1_MIN_GAIN:
        out["C1"] = _v("holds", "positive control passed: retrieval over the real-model wiki answers user-specific questions")
    else:
        out["C1"] = _v("refused", "positive control failed: the pipeline, not H-C1, is at fault; H-C1 is not testable with this setup")

    c2 = results.get("C2", {})
    lx, hm, ea = c2.get("lexicon", {}), c2.get("homogeneity", {}), c2.get("error_agreement", {})

    # Manipulation check (amendment 2): with an empty projection the "with Γ" condition
    # is the baseline, and every C2 verdict would be produced by construction.
    manip = []
    if c2.get("projection_bytes_mean", 0) < MIN_PROJ_BYTES:
        manip.append(f"mean projection size {c2.get('projection_bytes_mean', 0):.0f} bytes < {MIN_PROJ_BYTES}")
    for key in ("nonempty_gamma_writes", "nonempty_gamma_items"):
        if key in c2 and c2[key] < MIN_NONEMPTY:
            manip.append(f"{key} = {c2[key]:.2f} < {MIN_NONEMPTY:.2f}")
    if manip:
        reason = "treatment not delivered (manipulation check failed: " + "; ".join(manip) + ")"
        for k in ("H-C2_lexicon", "H-C17a", "H-C17b"):
            out[k] = _v("refused", reason)
        out["H-C2_rho"] = _v("not_tested", "redundancy rate rho needs the Swarmbly dispatch path; not part of this run")
        out["manipulation_check"] = {"passed": False, "problems": manip}
        _replication(out, ea)
        return _apply_global(out, global_refusals)
    out["manipulation_check"] = {"passed": True}

    # H-C2 — lexicon part only (rho is not measured in this run).
    ci = lx.get("difference_ci95")
    if not ci:
        out["H-C2_lexicon"] = _v("refused", "no user with preferred terms in the projection")
    elif ci[0] > 0:
        out["H-C2_lexicon"] = _v("holds", "preferred terms appear more often with Γ than without (CI excludes 0)")
    elif lx.get("difference", 0) <= 0:
        out["H-C2_lexicon"] = _v("falsified", "preferred terms do not appear more often with Γ")
    else:
        out["H-C2_lexicon"] = _v("inconclusive", "positive point estimate, CI includes 0")
    out["H-C2_rho"] = _v("not_tested", "redundancy rate rho needs the Swarmbly dispatch path; not part of this run")

    # H-C17 (a) — homogeneity across users.
    ci = hm.get("reduction_projection_ci95")
    if not ci:
        out["H-C17a"] = _v("refused", "fewer than two topics")
    elif ci[0] > 0:
        out["H-C17a"] = _v("holds", "projection lowers cross-user homogeneity (CI excludes 0)")
    elif hm.get("reduction_projection", 0) <= 0:
        out["H-C17a"] = _v("falsified", "homogeneity across users does not decrease with projection")
    else:
        out["H-C17a"] = _v("inconclusive", "positive point estimate, CI includes 0")
    spec = hm.get("projection_beyond_placebo_ci95")
    out["H-C17a"]["qualification"] = (
        "reduction exceeds a non-personal placebo" if spec and spec[0] > 0 else
        "reduction NOT shown to exceed a non-personal placebo: attribute it to prompt variation, not to personalisation")

    # H-C17 (b) — error agreement unchanged (equivalence within ±margin).
    refuse_b = []
    if min(ea.get("jointly_wrong_with", 0), ea.get("jointly_wrong_without", 0)) < MIN_JOINTLY_WRONG:
        refuse_b.append(f"fewer than {MIN_JOINTLY_WRONG} jointly-wrong pair-items")
    if max(ea.get("invalid_rate_with", 1), ea.get("invalid_rate_without", 1)) > MAX_INVALID:
        refuse_b.append(f"more than {MAX_INVALID:.0%} unparseable answers")
    ci, d = ea.get("delta_ci95"), ea.get("delta")
    if refuse_b or not ci or d is None:
        out["H-C17b"] = _v("refused", "; ".join(refuse_b) or "no estimate")
    elif -EQUIV_MARGIN <= ci[0] and ci[1] <= EQUIV_MARGIN:
        out["H-C17b"] = _v("holds", f"error agreement unchanged within ±{EQUIV_MARGIN} (equivalence)")
    elif (ci[0] > 0 or ci[1] < 0) and abs(d) > EQUIV_MARGIN:
        out["H-C17b"] = _v("falsified", "projection changes error agreement beyond the margin: Sections 2.6 and 6.4 must be revised")
    else:
        out["H-C17b"] = _v("inconclusive", "CI neither inside the margin nor clearly outside it")
    _replication(out, ea)
    return _apply_global(out, global_refusals)


def _replication(out: dict[str, Any], ea: dict[str, Any]) -> None:
    exc = ea.get("excess_ci95")
    out["replication_Kim2025"] = {
        "descriptive": True,
        "statement": ("errors shared above chance across families (excess CI excludes 0)" if exc and exc[0] > 0 else
                      "excess over chance not established in this run"),
    }


def _apply_global(out: dict[str, Any], global_refusals: list[str]) -> dict[str, Any]:
    if global_refusals:
        for k, v in out.items():
            if isinstance(v, dict) and v.get("verdict") in {"holds", "falsified", "inconclusive"}:
                v["verdict_if_confirmatory"] = v["verdict"]
                v["verdict"] = "exploratory_only"
        out["global_refusals"] = global_refusals
    return out
