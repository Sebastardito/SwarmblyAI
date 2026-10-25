"""Multiple-choice instrument for cross-family error agreement (H-C17, second clause).

Why multiple choice. The first version of C2 compared free-text answers by
exact match of their first eight normalised words. Two models that give the
same wrong entity in different words then count as disagreeing, so the metric
is biased towards zero and cannot decide whether projection changes error
correlation. Kim et al. (2025) measure agreement on multiple-choice items,
where "same wrong answer" is unambiguous and has a known chance level. This
module does the same.

Item set. A fixed random sample of the MMLU test split (Hendrycks et al.,
2021; MIT licence), drawn by ``fetch_mcq.py`` with a recorded seed and stored
with its SHA-256. A small synthetic set (``fixtures/mcq_synthetic.json``) exists
only to exercise the code with ``MockBackend``.

Statistics.
* ``agreement``: P(same letter | both wrong), pooled over model pairs.
* ``chance``: the agreement expected if the two models chose wrong letters
  independently, from each model's own distribution of wrong letters on that
  item's three distractors (falls back to 1/3).
* ``delta``: agreement with projection minus without, with a paired bootstrap
  over items (the same resampled items enter both conditions).
"""

from __future__ import annotations

import hashlib
import itertools
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

LETTERS = "ABCD"
MCQ_MARKER = "TASK: MCQ"
_LETTER = re.compile(r"\b([ABCD])\b")

__all__ = ["MCQItem", "load_items", "file_sha256", "mcq_prompt", "parse_letter", "AgreementResult",
           "pairwise_agreement", "bootstrap_delta", "MCQ_MARKER"]


@dataclass(frozen=True)
class MCQItem:
    idx: int
    subject: str
    question: str
    choices: tuple[str, str, str, str]
    answer: str  # "A".."D"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_items(path: Path) -> list[MCQItem]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = []
    for it in data["items"]:
        ch = tuple(it["choices"])
        if len(ch) != 4 or it["answer"] not in LETTERS:
            raise ValueError(f"malformed MCQ item {it.get('idx')}")
        items.append(MCQItem(int(it["idx"]), it.get("subject", ""), it["question"], ch, it["answer"]))  # type: ignore[arg-type]
    return items


def mcq_prompt(item: MCQItem, extra: str = "") -> str:
    lines = [MCQ_MARKER, "Answer the multiple-choice question with a single letter (A, B, C or D) and nothing else."]
    if extra:
        lines.append(f"STYLE: {extra}")
    lines.append(f"QUESTION: {item.question}")
    lines += [f"{L}. {c}" for L, c in zip(LETTERS, item.choices)]
    lines.append("ANSWER:")
    return "\n".join(lines)


def parse_letter(text: str) -> str | None:
    t = text.strip().upper()
    if t[:1] in LETTERS and (len(t) == 1 or not t[1].isalpha()):
        return t[0]
    m = _LETTER.search(t)
    return m.group(1) if m else None


@dataclass
class AgreementResult:
    agreement: float | None
    chance: float | None
    jointly_wrong: int
    invalid_rate: float
    per_pair: dict[str, dict[str, Any]]


def _wrong_dist(answers: Sequence[str | None], items: Sequence[MCQItem]) -> dict[str, float]:
    counts = {L: 1.0 for L in LETTERS}  # add-one smoothing
    for a, it in zip(answers, items):
        if a is not None and a != it.answer:
            counts[a] += 1.0
    tot = sum(counts.values())
    return {L: v / tot for L, v in counts.items()}


def _pair_stats(a: Sequence[str | None], b: Sequence[str | None], items: Sequence[MCQItem],
                qa: dict[str, float], qb: dict[str, float]) -> tuple[int, int, float]:
    both = agree = 0
    chance_sum = 0.0
    for x, y, it in zip(a, b, items):
        if x is None or y is None or x == it.answer or y == it.answer:
            continue
        both += 1
        agree += int(x == y)
        wrong = [L for L in LETTERS if L != it.answer]
        pa = np.array([qa[L] for L in wrong]); pa /= pa.sum()
        pb = np.array([qb[L] for L in wrong]); pb /= pb.sum()
        chance_sum += float(pa @ pb)
    return both, agree, chance_sum


def pairwise_agreement(answers: dict[str, Sequence[str | None]], items: Sequence[MCQItem],
                       subset: Iterable[int] | None = None) -> AgreementResult:
    """Pooled P(same letter | both wrong) over all family pairs.

    ``subset`` (indices into ``items``) lets the bootstrap resample items; the
    wrong-letter distributions are always estimated on the full set.
    """
    idx = list(range(len(items))) if subset is None else list(subset)
    q = {f: _wrong_dist(ans, items) for f, ans in answers.items()}
    tot_both = tot_agree = 0
    tot_chance = 0.0
    per_pair: dict[str, dict[str, Any]] = {}
    for fa, fb in itertools.combinations(sorted(answers), 2):
        a = [answers[fa][i] for i in idx]
        b = [answers[fb][i] for i in idx]
        its = [items[i] for i in idx]
        both, agree, ch = _pair_stats(a, b, its, q[fa], q[fb])
        per_pair[f"{fa}|{fb}"] = {"jointly_wrong": both, "agreement": agree / both if both else None,
                                  "chance": ch / both if both else None}
        tot_both += both
        tot_agree += agree
        tot_chance += ch
    n_ans = sum(len(v) for v in answers.values())
    invalid = sum(1 for v in answers.values() for x in v if x is None)
    return AgreementResult(agreement=tot_agree / tot_both if tot_both else None,
                           chance=tot_chance / tot_both if tot_both else None,
                           jointly_wrong=tot_both, invalid_rate=invalid / n_ans if n_ans else 0.0,
                           per_pair=per_pair)


def _item_arrays(answers: dict[str, Sequence[str | None]], items: Sequence[MCQItem]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-item sums over family pairs: jointly-wrong count, agreements, chance mass."""
    q = {f: _wrong_dist(ans, items) for f, ans in answers.items()}
    n = len(items)
    both = np.zeros(n); agree = np.zeros(n); chance = np.zeros(n)
    for fa, fb in itertools.combinations(sorted(answers), 2):
        for i, it in enumerate(items):
            x, y = answers[fa][i], answers[fb][i]
            if x is None or y is None or x == it.answer or y == it.answer:
                continue
            both[i] += 1
            agree[i] += float(x == y)
            wrong = [L for L in LETTERS if L != it.answer]
            pa = np.array([q[fa][L] for L in wrong]); pa /= pa.sum()
            pb = np.array([q[fb][L] for L in wrong]); pb /= pb.sum()
            chance[i] += float(pa @ pb)
    return both, agree, chance


def bootstrap_delta(without: dict[str, Sequence[str | None]], with_: dict[str, Sequence[str | None]],
                    items: Sequence[MCQItem], B: int = 10_000, seed: int = 20261005) -> dict[str, Any]:
    """Paired bootstrap over items of agreement(with) − agreement(without).

    Each resample draws item indices with replacement and applies them to both
    conditions, so the comparison is paired by item. Vectorised: per-item
    counts are precomputed and resamples are weight vectors.
    """
    rng = np.random.default_rng(seed)
    n = len(items)
    bw, aw, _ = _item_arrays(with_, items)
    bo, ao, co = _item_arrays(without, items)
    W = np.stack([np.bincount(rng.integers(0, n, n), minlength=n) for _ in range(B)]).astype(float)
    sw, so = W @ bw, W @ bo
    ok = (sw > 0) & (so > 0)
    agr_w = (W @ aw)[ok] / sw[ok]
    agr_o = (W @ ao)[ok] / so[ok]
    chn_o = (W @ co)[ok] / so[ok]
    d = agr_w - agr_o
    e = agr_o - chn_o
    point_w = aw.sum() / bw.sum() if bw.sum() else None
    point_o = ao.sum() / bo.sum() if bo.sum() else None
    chance_o = co.sum() / bo.sum() if bo.sum() else None
    q = lambda v, p: float(np.quantile(v, p))
    return {
        "agreement_with": point_w,
        "agreement_without": point_o,
        "chance_without": chance_o,
        "delta": (point_w - point_o) if point_w is not None and point_o is not None else None,
        "delta_ci95": [q(d, 0.025), q(d, 0.975)] if len(d) else None,
        "excess_over_chance_without": (point_o - chance_o) if point_o is not None and chance_o is not None else None,
        "excess_ci95": [q(e, 0.025), q(e, 0.975)] if len(e) else None,
        "jointly_wrong_with": int(bw.sum()),
        "jointly_wrong_without": int(bo.sum()),
        "bootstrap_B": int(ok.sum()),
        "seed": seed,
    }


def accuracy(answers: Sequence[str | None], items: Sequence[MCQItem]) -> float:
    return float(np.mean([a == it.answer for a, it in zip(answers, items)])) if items else 0.0
