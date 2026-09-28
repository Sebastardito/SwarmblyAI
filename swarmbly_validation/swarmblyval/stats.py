"""Statistical instruments, implemented in pure stdlib.

The whitepaper's instrument discipline requires *refusal conditions* (§9,
§15.7): a check that cannot decide must refuse, not guess. These helpers
implement the instruments the tests use, plus the refusal predicates.
"""

import math
import random
from statistics import fmean, median

from . import constants as C


def clustered_bootstrap(data, clusters, n_resample=4000, seed=0, ci=0.95):
    """Bootstrap a mean with resampling at the CLUSTER level.

    ``data`` is a flat sequence of per-unit values; ``clusters`` is a sequence,
    the same length as ``data``, of cluster ids. Resampling is done by cluster
    (prompt), which is what the whitepaper means by "clustered by prompt".
    Returns (mean, low, high, se) of the resampled mean distribution.
    """
    rng = random.Random(seed)
    # group values by cluster
    groups = {}
    for value, cid in zip(data, clusters):
        groups.setdefault(cid, []).append(value)
    cluster_ids = list(groups.keys())
    n = len(cluster_ids)

    means = []
    for _ in range(n_resample):
        sample_ids = [cluster_ids[rng.randrange(n)] for _ in range(n)]
        vals = [v for cid in sample_ids for v in groups[cid]]
        means.append(fmean(vals) if vals else 0.0)
    means.sort()
    lo = means[int((1 - ci) / 2 * n_resample)]
    hi = means[int((1 + ci) / 2 * n_resample) - 1]
    m = fmean(data)
    # SE of the bootstrap mean
    se = _std(means)
    return m, lo, hi, se


def _std(xs):
    m = fmean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def rank_sum_test(a, b):
    """Mann-Whitney U (rank-sum) with normal approximation; two-sided.

    Returns (U, z, p_value). Pure stdlib. Used by the delta-separation test.
    """
    all_vals = sorted(a + b)
    ranks = {}
    for i, v in enumerate(all_vals, start=1):
        # average ranks for ties
        ranks.setdefault(v, []).append(i)
    rank_of = {v: fmean(rs) for v, rs in ranks.items()}

    n1, n2 = len(a), len(b)
    r1 = sum(rank_of[v] for v in a)
    U1 = r1 - n1 * (n1 + 1) / 2.0
    # use the smaller U for symmetry
    U2 = n1 * n2 - U1
    U = min(U1, U2)

    mu = n1 * n2 / 2.0
    # tie correction
    n = n1 + n2
    tie_sum = 0.0
    for v, rs in ranks.items():
        t = len(rs)
        tie_sum += t ** 3 - t
    sigma2 = (n1 * n2 / 12.0) * ((n + 1) - tie_sum / (n * (n - 1)))
    sigma = math.sqrt(max(sigma2, 1e-12))
    z = (U - mu) / sigma
    p = 2 * (1 - _normal_cdf(abs(z)))
    return U, z, p


def _normal_cdf(x):
    # Abramowitz-Stegun 7.1.26 — CDF (P(X <= x)), no la PDF.
    if x < 0:
        return 1 - _normal_cdf(-x)
    t = 1.0 / (1.0 + 0.2316419 * x)
    poly = ((((1.330274429 * t - 1.821255978) * t + 1.781477937) * t
             - 0.356563782) * t + 0.319381530) * t
    return 1.0 - 0.3989422804014327 * math.exp(-x * x / 2.0) * poly


# --- Refusal predicates (WHITEPAPER_V2 §9, §15.7) -----------------------------

def refuse_below_clusters(n_clusters, minimum=C.MIN_CLUSTERS):
    return n_clusters < minimum, (
        f"{n_clusters} clusters < {minimum}: refuse to issue a verdict"
    )


def refuse_below_families(n_families, minimum=C.FAMILY_LIST_MIN):
    return n_families < minimum, (
        f"{n_families} model families < {minimum}: refuse to conclude about the pool"
    )


def refuse_baseline_floor(monolithic_score, floor=C.BASELINE_FLOOR):
    return monolithic_score < floor, (
        f"monolithic arm {monolithic_score:.2f} < floor {floor}: nothing to compare"
    )


def refuse_se_mismatch(se_planned, se_measured, tol=C.SE_CROSSCHECK_TOL):
    """Refuse if the sample-size plan and the measured SE differ by > tol."""
    if se_measured <= 0:
        return True, "measured SE is zero or negative: refuse"
    ratio = abs(se_planned - se_measured) / se_measured
    return ratio > tol, (
        f"planned/measured SE differ by {ratio:.1%} > {tol:.0%}: refuse"
    )


def withdraw_if_largest_cell_undoes(cells, top=1):
    """Pooled-conclusion guard: withdraw if dropping the ``top`` largest
    contributors reverses the sign of the pooled effect. Returns (withdraw, reason).

    FIXED 2026-09-24. The previous version carried two defects and both made it
    fail in exactly the cases it exists to catch:

    1. It also required ``abs(rest) < abs(total)``, so the guard stayed silent
       whenever the reversal was LARGE (total=+1, rest=-100 was reported as
       "survives"). The magnitude of the remainder is irrelevant; a sign flip
       is a sign flip.
    2. It dropped only ONE contributor, so it could not see the documented case
       this project actually has -- the 16-prompt mean is manufactured by TWO
       prompts together (WHITEPAPER_V2 §15.3), and removing either alone leaves
       the sign intact.
    """
    if not cells:
        return True, "no cells: refuse"
    total = sum(cells)
    ordered = sorted(cells, key=abs, reverse=True)
    dropped = ordered[:max(1, top)]
    rest = total - sum(dropped)
    if (total >= 0) != (rest >= 0):
        names = ", ".join(f"{d:+.2f}" for d in dropped)
        return True, (
            f"dropping the {len(dropped)} largest contributor(s) [{names}] flips "
            f"the pooled sign ({total:+.2f} -> {rest:+.2f}): withdraw pooled conclusion"
        )
    return False, (
        f"pooled conclusion survives dropping the {len(dropped)} largest "
        f"contributor(s) ({total:+.2f} -> {rest:+.2f})"
    )


# --- exact tests, for the small groups this project actually has --------------

def exact_rank_sum(a, b):
    """Two-sided exact permutation p for the Mann-Whitney statistic.

    The harness's group sizes are 11 vs 2. A normal approximation is not valid
    there and overstates the p-value by ~17% at perfect separation (0.0299 vs
    the exact 0.0256), so the exact test is the instrument and the normal one
    is kept only for large groups.
    """
    from itertools import combinations
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        raise ValueError("empty group")
    allv = list(a) + list(b)
    idx = range(len(allv))

    def stat(bset):
        aa = [allv[i] for i in idx if i not in bset]
        bb = [allv[i] for i in bset]
        greater = sum(1 for x in aa for y in bb if x > y)
        equal = sum(1 for x in aa for y in bb if x == y)
        u1 = greater + 0.5 * equal
        return min(u1, n1 * n2 - u1)

    observed = stat(set(range(n1, n1 + n2)))
    total = extreme = 0
    for comb in combinations(idx, n2):
        total += 1
        if stat(set(comb)) <= observed:
            extreme += 1
    return observed, extreme / total, total


def p_value_ceiling(n1, n2):
    """Smallest two-sided p the exact rank-sum can return for these sizes,
    **assuming no ties**.

    A test whose ceiling exceeds alpha cannot reach significance even on
    perfect separation. Reporting that BEFORE running is the difference between
    a null result and an underpowered one.

    With ties the bound moves, and on this project's data it does: delta takes
    only four distinct values over sixteen prompts. Use
    :func:`attainable_min_p` on the actual values instead of this formula
    whenever the data is available -- this one is the best case, not the case.
    """
    from math import comb
    return 2.0 / comb(n1 + n2, min(n1, n2))


def attainable_min_p(a, b):
    """Smallest two-sided p actually attainable given THESE values, ties included.

    Enumerates the permutation distribution once and returns the proportion of
    arrangements attaining its most extreme statistic. When that number exceeds
    alpha, no arrangement of this data could have been significant, and a null
    result carries no information at all.
    """
    from itertools import combinations
    n1, n2 = len(a), len(b)
    allv = list(a) + list(b)
    idx = range(len(allv))

    def stat(bset):
        aa = [allv[i] for i in idx if i not in bset]
        bb = [allv[i] for i in bset]
        greater = sum(1 for x in aa for y in bb if x > y)
        equal = sum(1 for x in aa for y in bb if x == y)
        u1 = greater + 0.5 * equal
        return min(u1, n1 * n2 - u1)

    stats = [stat(set(c)) for c in combinations(idx, n2)]
    best = min(stats)
    return sum(1 for s in stats if s <= best) / len(stats), best


def spearman(xs, ys):
    """Spearman rho with tie-corrected ranks. Pure stdlib."""
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = rank(list(xs)), rank(list(ys))
    n = len(rx)
    mx, my = fmean(rx), fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else 0.0


def spearman_permutation_p(xs, ys, n_perm=20000, seed=0):
    """Two-sided permutation p for Spearman rho.

    Uses all information in the sample rather than collapsing it into two
    groups, which is what makes it usable where a 2-vs-11 comparison is not.
    """
    rho = spearman(xs, ys)
    rng = random.Random(seed)
    ys = list(ys)
    hits = 0
    for _ in range(n_perm):
        rng.shuffle(ys)
        if abs(spearman(xs, ys)) >= abs(rho) - 1e-12:
            hits += 1
    return rho, (hits + 1) / (n_perm + 1)


def variance_refusal(values, label="predictor"):
    """Refuse when the predictor has no variance: nothing can be tested against it."""
    vals = list(values)
    if not vals:
        return True, f"{label} is empty: refuse"
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-12:
        return True, (
            f"{label} is constant at {lo:g} across all {len(vals)} units: "
            f"zero variance, no association can be estimated -- refuse"
        )
    return False, f"{label} varies over [{lo:g}, {hi:g}]"


def bimodality_summary(values, expensive_ids=()):
    """Summarise a bimodal distribution given ``{id: value}``.

    FIXED 2026-09-24: the previous version treated ``values`` as a list for
    ``len``/``fmean``/iteration and as a dict for ``.items()``, so it raised on
    both shapes. It was never called, which is how it survived -- dead code in
    a harness is a check that claims to exist and does not.
    """
    if not isinstance(values, dict):
        raise TypeError("bimodality_summary expects a {id: value} mapping")
    vals = list(values.values())
    if not vals:
        raise ValueError("no values")
    return {
        "n": len(vals),
        "mean": fmean(vals),
        "median": median(vals),
        "at_or_below_zero": sum(1 for v in vals if v <= 0),
        "max": max(vals),
        "min": min(vals),
        "expensive": {k: v for k, v in values.items() if k in set(expensive_ids)},
    }
