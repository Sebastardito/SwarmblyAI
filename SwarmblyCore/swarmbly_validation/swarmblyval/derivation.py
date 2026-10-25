"""Core derivations from the whitepaper, as testable functions.

Every function reproduces a formula stated in the documents so the harness can
verify that the documents' own arithmetic is internally consistent. Where a
function returns a number that the documents also state, the test asserts the
two agree within a documented tolerance.
"""

import math

from . import constants as C


def rho_from(L, F, H=C.H_TOKENS, s=C.S_TOKENS):
    """Context budget derived from fragment size and flank. WHITEPAPER_V2 §6.5.

    rho ~= (L + 2F)/L + H/(L*s)
    """
    return (L + 2 * F) / L + H / (L * s)


def n_fragments(material_sentences, L):
    """Fragment count derived from material and fragment size. §5.7: N = ceil(material/L)."""
    return math.ceil(material_sentences / L)


def header_implied_H(P_tokens, N, floor_rho):
    """Invert the floor rho_floor ~= 1 + N*H/|P| to recover H. FUNDAMENTOS §0.B."""
    return (floor_rho - 1.0) * P_tokens / N


def rho_saving(F_higher, F_lower, L=C.L_REF, H=C.H_TOKENS, s=C.S_TOKENS):
    """Relative compute saving from measuring the flank instead of inheriting it."""
    rho_hi = rho_from(L, F_higher, H, s)
    rho_lo = rho_from(L, F_lower, H, s)
    return (rho_hi - rho_lo) / rho_hi, rho_hi, rho_lo


def coverage_c(p_loss, eps):
    """Redundancy requirement c >= ln(1/eps)/(1-p). WHITEPAPER_V2 §7.4."""
    return math.log(1.0 / eps) / (1.0 - p_loss)


def p_uncovered(c_eff):
    """P(semantic unit uncovered) = exp(-c_eff). §7.4."""
    return math.exp(-c_eff)


def expected_uncovered_units(M, c_eff):
    return M * math.exp(-c_eff)


def sample_size_for_upper_bound(sd_between, mean, threshold, z=C.Z_95, margin=1.0):
    """Prompt count so the 95% CI upper bound sits margin points below threshold.

    Upper bound ~ mean + z * sd_between/sqrt(n). Solve for n:
        n >= (z * sd_between / (threshold - mean - margin))^2
    Reproduces the documented 60 minimum / 72 with margin (§15.5).
    """
    allowed_se = threshold - mean - margin
    if allowed_se <= 0:
        return math.inf
    n = (z * sd_between / allowed_se) ** 2
    return n


def coverage_table(loss_rates=C.LOSS_RATES, epsilons=C.EPSILONS):
    """Reproduce the c >= ln(1/eps)/(1-p) table of WHITEPAPER_V2 §7.4."""
    rows = []
    for p in loss_rates:
        row = {"p": p}
        for eps in epsilons:
            row[f"eps={eps}"] = round(coverage_c(p, eps), 1)
        rows.append(row)
    return rows


def tax_distribution_stats():
    """Reproduce the bimodality arithmetic of the 16-prompt measurement."""
    from . import fixtures as F

    t = F.TAX_16
    total = t["mean"] * t["n"]                                   # 2.30 * 16 = 36.8
    expensive_sum = sum(t["expensive"].values())                 # 51.58
    expensive_share_of_mean = expensive_sum / total              # 1.40 = 140%
    rest_sum = total - expensive_sum                             # -14.78
    rest_mean = rest_sum / (t["n"] - len(t["expensive"]))        # -1.0557
    return {
        "total_points": total,
        "expensive_sum": expensive_sum,
        "expensive_share_of_mean": expensive_share_of_mean,
        "rest_mean": rest_mean,
        "n_rest": t["n"] - len(t["expensive"]),
    }
