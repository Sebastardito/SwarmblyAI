"""Interval estimation that respects how the observations were produced.

The unit problem
----------------

Every confidence interval this project has reported treats its rows as
independent. They are not, and the error runs in the direction that flatters:

* ``by_claim`` in the run of 26 August reports n = 2 359 aggregate claims and
  n = 6 041 local ones. Those are *sentences*. Sentences from one answer share a
  model, a packet, a contract and a source table -- a bad packet makes all of its
  sentences wrong together. Counting them as 8 400 independent observations
  inflates the effective sample by roughly the number of sentences per answer,
  and every interval and every AUC standard error computed from them is too
  narrow by about its square root.

* ``falsifiable_go_no_go`` resamples *cells*, and cells that share a prompt share
  its difficulty. On the corpus as it stands a cell is nearly a prompt, so the
  damage there is small -- but "nearly" is not a property to rely on, and it stops
  being true the moment a sweep varies anything within a prompt.

The fix is a **cluster bootstrap**: resample whole prompts with replacement, keep
every observation belonging to a drawn prompt, and recompute the statistic. The
interval then reflects the variability of the thing that was actually sampled
independently -- the prompt -- rather than of the sentences inside it.

What this costs is honesty about power. The intervals get wider, sometimes much
wider, and some findings will stop clearing their threshold. That is the point:
they were never clearing it, the arithmetic just said they were.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

import numpy as np

__all__ = [
    "cluster_bootstrap",
    "clustered_mean_ci",
    "effective_sample_size",
]

DEFAULT_DRAWS = 4000


def cluster_bootstrap(
    records: Sequence[Mapping[str, Any]],
    statistic: Callable[[Sequence[Mapping[str, Any]]], float | None],
    cluster_key: str = "prompt_id",
    draws: int = DEFAULT_DRAWS,
    alpha: float = 0.05,
    seed: int = 0,
) -> dict[str, Any]:
    """Percentile interval for ``statistic``, resampling whole clusters.

    Args:
        records: One record per observation. Each must carry ``cluster_key``.
        statistic: Computed on a resampled record list. May return ``None`` for
            a draw it cannot evaluate -- an all-one-class resample, say -- and
            those draws are counted and excluded rather than silently treated as
            zero.
        cluster_key: The field that identifies what was sampled independently.
            ``prompt_id`` for anything measured per answer; a chain id for chain
            steps; never a sentence index.
        draws: Bootstrap resamples.
        alpha: 1 - coverage. 0.05 gives a 95 % interval.
        seed: Fixed so a reported interval can be reproduced exactly.

    Returns:
        The point estimate, the interval, the number of clusters (the sample size
        that matters), the number of records, and how many draws were unusable.
        ``n_clusters`` is reported beside ``n_records`` precisely so a reader can
        see the difference between them -- 8 400 sentences from 20 prompts is a
        sample of 20.
    """
    by_cluster: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        by_cluster.setdefault(str(record.get(cluster_key, "")), []).append(record)

    clusters = sorted(by_cluster)
    point = statistic(list(records)) if records else None
    if len(clusters) < 2:
        return {
            "point": point, "ci95": None, "n_clusters": len(clusters),
            "n_records": len(records), "draws_unusable": 0,
            "note": "fewer than two clusters: no interval is estimable",
        }

    rng = np.random.default_rng(seed)
    values: list[float] = []
    unusable = 0
    index = np.arange(len(clusters))
    for _ in range(max(1, draws)):
        picked = rng.choice(index, size=len(clusters), replace=True)
        resample = [r for i in picked for r in by_cluster[clusters[i]]]
        result = statistic(resample)
        if result is None or not np.isfinite(result):
            unusable += 1
            continue
        values.append(float(result))

    if not values:
        return {
            "point": point, "ci95": None, "n_clusters": len(clusters),
            "n_records": len(records), "draws_unusable": unusable,
            "note": "every resample was unusable",
        }

    lo = float(np.quantile(values, alpha / 2))
    hi = float(np.quantile(values, 1 - alpha / 2))
    return {
        "point": round(point, 6) if point is not None else None,
        "ci95": [round(lo, 6), round(hi, 6)],
        "n_clusters": len(clusters),
        "n_records": len(records),
        "draws_unusable": unusable,
        "cluster_key": cluster_key,
    }


def clustered_mean_ci(
    records: Sequence[Mapping[str, Any]],
    field: str,
    cluster_key: str = "prompt_id",
    **kwargs: Any,
) -> dict[str, Any]:
    """Cluster bootstrap of a simple mean -- the common case."""
    def _mean(rows: Sequence[Mapping[str, Any]]) -> float | None:
        values = [float(r[field]) for r in rows
                  if isinstance(r.get(field), (int, float))]
        return (sum(values) / len(values)) if values else None

    return cluster_bootstrap(records, _mean, cluster_key=cluster_key, **kwargs)


def effective_sample_size(
    records: Sequence[Mapping[str, Any]],
    field: str,
    cluster_key: str = "prompt_id",
) -> dict[str, Any]:
    """How many independent observations the records are actually worth.

    ``n_eff = n / (1 + (m - 1) * ICC)`` with ``m`` the mean cluster size and
    ``ICC`` the intraclass correlation estimated from a one-way decomposition.
    Reported so that a claim resting on "n = 8 400" can be read next to the
    number of prompts that produced it.

    A negative ICC estimate -- possible when between-cluster variance is smaller
    than within -- is clamped to zero, which makes ``n_eff`` at most ``n`` rather
    than larger. Inflating an effective sample above its record count would be
    the opposite of what this function is for.
    """
    groups: dict[str, list[float]] = {}
    for record in records:
        if isinstance(record.get(field), (int, float)):
            groups.setdefault(str(record.get(cluster_key, "")), []).append(
                float(record[field]))
    groups = {k: v for k, v in groups.items() if v}
    n = sum(len(v) for v in groups.values())
    if len(groups) < 2 or n < 2:
        return {"n_records": n, "n_clusters": len(groups), "icc": None,
                "n_effective": float(n)}

    sizes = [len(v) for v in groups.values()]
    grand = sum(sum(v) for v in groups.values()) / n
    between = sum(len(v) * (sum(v) / len(v) - grand) ** 2 for v in groups.values())
    within = sum((x - sum(v) / len(v)) ** 2 for v in groups.values() for x in v)

    df_between = len(groups) - 1
    df_within = n - len(groups)
    ms_between = between / df_between if df_between else 0.0
    ms_within = within / df_within if df_within else 0.0
    # The usual unbiased m0 for unequal cluster sizes.
    m0 = (n - sum(s * s for s in sizes) / n) / df_between if df_between else 1.0

    icc = 0.0
    if m0 > 0 and ms_between + (m0 - 1) * ms_within > 0:
        icc = max(0.0, (ms_between - ms_within) / (ms_between + (m0 - 1) * ms_within))

    mean_size = n / len(groups)
    n_eff = n / (1 + (mean_size - 1) * icc) if (1 + (mean_size - 1) * icc) > 0 else n
    return {
        "n_records": n,
        "n_clusters": len(groups),
        "mean_cluster_size": round(mean_size, 4),
        "icc": round(icc, 6),
        "n_effective": round(min(float(n), n_eff), 2),
    }
