"""Backend-driven experiments of the whitepaper (section 11.2).

Every function takes the backend(s) explicitly. With ``MockBackend`` the
results validate the plumbing and are labelled ``mock`` downstream; only
``run_real.py`` with real models produces candidate evidence.

* ``build_wiki``      — layers 0–1 end to end on the fixture corpus.
* ``c1_memory``       — H-C1: retrieval over the wiki vs no memory.
* ``c2_projection``   — H-C2 and H-C17: lexicon adherence and bytes added to Γ;
  cross-user homogeneity with vs without projection; cross-family error
  agreement within a request with vs without projection.
* ``c10_selection``   — H-C15 through ``AdapterManager`` (simulation trainer).
* ``canary_check``    — canary terms never reach training data; tail mass and
  identity-violation rate of a backend's glosses.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from swarmbly_lce.anchors import AnchorVerifier
from swarmbly_lce.backends import PROMPT_MARKERS, Backend
from swarmbly_lce.claims import Maturity
from swarmbly_lce.digest import Digester
from swarmbly_lce.diversity import CanarySet, homogeneity
from swarmbly_lce.policy import LearningPolicy
from swarmbly_lce.projection import Projector
from swarmbly_lce.retrieval import BM25Retriever
from swarmbly_lce.sources import SourceSpace
from swarmbly_lce.training import AdapterManager, Example, ExampleBuilder, MockEvaluator, MockTrainer, Recipe
from swarmbly_lce.wiki import Wiki

FIXTURES = Path(__file__).resolve().parent / "fixtures"
DATA = Path(__file__).resolve().parent / "data"

__all__ = ["build_wiki", "c1_memory", "c2_projection", "c10_selection", "canary_check", "format_c2", "FIXTURES", "DATA"]


def _norm(ans: str) -> str:
    return " ".join(re.sub(r"[^\w\s:]", " ", ans.lower()).split()[:8])


def build_wiki(corpus: Path, policy_path: Path, backend: Backend, cycles: int = 4,
               anchor_mode: str = "offsets", reconcile_types: bool = False,
               suffixes: frozenset[str] | None = None,
               exclude_names: frozenset[str] = frozenset(),
               double_pass: bool = False) -> tuple[Wiki, dict[str, Any]]:
    # suffixes: las fuentes del usuario son documentos (.md); los archivos de
    # preguntas del benchmark (.json) NO son fuentes y contaminaban la wiki
    # con sus claves (Enmienda 4). exclude_names: fuentes olvidadas que no
    # deben digerirse (E3: borrada.md).
    space = SourceSpace(corpus) if suffixes is None else SourceSpace(corpus, suffixes=suffixes)
    space._excluded = exclude_names
    policy = LearningPolicy.load(policy_path)
    wiki = Wiki(policy=policy)
    verifier = AnchorVerifier(space)
    dig = Digester(backend, space, verifier, anchor_mode=anchor_mode, reconcile_types=reconcile_types, double_pass=double_pass)
    t0 = time.perf_counter()
    dig.digest_all(wiki)
    digest_ms = (time.perf_counter() - t0) * 1000
    # Deterministic linking: consecutive claims of the same source are linked (CONNECTED needs one link).
    by_source: dict[str, list[str]] = {}
    for c in wiki.claims.values():
        by_source.setdefault(c.anchors[0].source, []).append(c.claim_id)
    for ids in by_source.values():
        for a, b in zip(ids, ids[1:]):
            wiki.link(a, b)
    for _ in range(cycles):
        wiki.consolidation_cycle()
    maturity = {m.value: 0 for m in Maturity}
    for c in wiki.claims.values():
        maturity[c.maturity.value] += 1
    stats = {
        "claims": len(wiki.claims),
        "maturity": maturity,
        "trainable": len(wiki.trainable()),
        "digest": dig.stats.__dict__,
        "anchor_verification": {**verifier.stats.__dict__, "rejection_rate": verifier.stats.rejection_rate},
        "digest_ms": digest_ms,
        "anchor_mode": anchor_mode,
        "reconcile_types": reconcile_types,
        "claims_detail": [{"text": c.text, "type": c.type.value, "anchored": c.anchored, "maturity": c.maturity.value,
                           "span": space.read(c.anchors[0].source)[c.anchors[0].start:c.anchors[0].end] if c.anchors else ""}
                          for c in wiki.claims.values()],
    }
    wiki.space = space  # type: ignore[attr-defined]  # kept for span-reading projections
    return wiki, stats


def _answer(backend: Backend, question: str, context: str = "", extra: str = "") -> str:
    prompt = f"{PROMPT_MARKERS['answer']}\nAnswer briefly using the context if it is relevant.\n"
    if extra:
        prompt += f"STYLE: {extra}\n"
    if context:
        prompt += f"CONTEXT: {context}\n"
    prompt += f"QUESTION: {question}\n"
    return backend.generate(prompt, temperature=0.0, max_tokens=96)


def c1_memory(backend: Backend, wiki: Wiki, questions_path: Path = FIXTURES / "questions.json", k: int = 3) -> dict[str, Any]:
    qs = json.loads(questions_path.read_text(encoding="utf-8"))["questions"]
    retr = BM25Retriever().index(wiki.claims.values())
    with_mem, without = [], []
    for item in qs:
        hits = retr.search(item["q"], k=k)
        ctx = " ".join(h.text for h in hits)
        a1 = _answer(backend, item["q"], ctx)
        a0 = _answer(backend, item["q"])
        with_mem.append(item["gold"].lower() in a1.lower())
        without.append(item["gold"].lower() in a0.lower())
    acc1, acc0 = float(np.mean(with_mem)), float(np.mean(without))
    return {"hypothesis": "H-C1", "n": len(qs), "acc_with_memory": acc1, "acc_without_memory": acc0, "gain": acc1 - acc0}


def _write(backend: Backend, topic: str, gamma: dict[str, Any], temperature: float = 0.0, seed: int = 0) -> str:
    lex = gamma.get("lexicon", {})
    preferred = [t for t, v in lex.items() if v == "preferred"]
    prompt = (f"{PROMPT_MARKERS['write']}\nWrite two sentences about the topic. Follow the contract fields if present.\n"
              f"TOPIC: {topic}\n")
    if gamma.get("register"):
        prompt += f"REGISTER: {gamma['register']}\n"
    if preferred:
        prompt += f"LEXICON: {', '.join(preferred)}\n"
    if gamma.get("style_seed"):
        prompt += f"STYLE_SEED: {gamma['style_seed']}\n"
    return backend.generate(prompt, temperature=temperature, max_tokens=160, seed=seed)


# Placebo contracts: per-user prompt variation of similar form that carries no
# personal information. They separate "personalisation lowers homogeneity"
# from "any per-user variation in the prompt lowers homogeneity".
PLACEBO_GAMMAS = [
    {"register": "neutral", "style_seed": "Write in plain language."},
    {"register": "neutral", "style_seed": "Use a measured tone."},
    {"register": "neutral", "style_seed": "Be direct and brief."},
]


class ManipulationCheckFailed(RuntimeError):
    """Γ would not reach the writer; raised before any outcome is generated (amendment 3)."""

    def __init__(self, stats: dict[str, Any]):
        super().__init__(f"manipulation check failed: {stats['projection_bytes_mean']:.0f} bytes, "
                         f"non-empty writes {stats['nonempty_gamma_writes']:.2f}, items {stats['nonempty_gamma_items']:.2f}")
        self.stats = stats


def _boot_ci(values: Sequence[float], B: int = 10_000, seed: int = 20261005) -> list[float] | None:
    v = np.asarray(values, dtype=float)
    if len(v) < 2:
        return None
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, len(v), (B, len(v)))].mean(axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def c2_projection(families: Sequence[Backend], digest_backend: Backend, users_dir: Path = FIXTURES / "users",
                  users_policy: Path = FIXTURES / "users_policy.json", queries_path: Path = FIXTURES / "open_queries.json",
                  mcq_path: Path = FIXTURES / "mcq_synthetic.json", temperature: float = 0.7,
                  bootstrap_B: int = 10_000, anchor_mode: str = "offsets", span_projection: bool = False,
                  reconcile_types: bool = False, preflight: bool = False) -> dict[str, Any]:
    """C2: H-C2 (lexicon adherence, bytes) and H-C17 (homogeneity across users; error agreement within a request).

    Design fixed by PREREGISTRATION_C1_C2 (2026-10-05):
    * every write is sampled at ``temperature`` > 0 with seed 1000+u for user slot u, in all
      conditions, so the baseline without Γ is not identical by construction;
    * homogeneity is compared per topic between baseline (no Γ), projection (user Γ) and
      placebo (generic Γ), with a bootstrap CI over topics;
    * error agreement uses multiple-choice items (lce_validation.mcq), Γ rotated across users.
    """
    from . import mcq as M

    if temperature <= 0:
        raise ValueError("homogeneity needs temperature > 0: at temperature 0 the baseline outputs are identical by construction")
    topics = json.loads(queries_path.read_text(encoding="utf-8"))["topics"]
    writer = families[0]
    # One projection per request, as in real use: (user, topic) for the writes and
    # (user, item) for the multiple-choice items, so that each request gets its own
    # lane classification. Requests classified SENSITIVE would stay on the client
    # (local_only); they are still written with Γ and counted, never dropped.
    claims_by_user, spaces, user_wikis = {}, {}, {}
    for udir in sorted(p for p in users_dir.iterdir() if p.is_dir()):
        wiki, ws = build_wiki(udir, users_policy, digest_backend, anchor_mode=anchor_mode, reconcile_types=reconcile_types)
        claims_by_user[udir.name] = list(wiki.claims.values())
        spaces[udir.name] = wiki.space  # type: ignore[attr-defined]
        user_wikis[udir.name] = ws
    users = list(claims_by_user)

    def projector_for(u: str) -> Projector:
        if not span_projection:
            return Projector()
        sp = spaces[u]
        return Projector(span_text=lambda c, sp=sp: sp.read(c.anchors[0].source)[c.anchors[0].start:c.anchors[0].end])

    projectors = {u: projector_for(u) for u in users}
    projections = {(u, t): projectors[u].project("escribe sobre " + t, claims_by_user[u]) for u in users for t in topics}
    gammas = {k: r.projection.gamma_fields() for k, r in projections.items()}
    seeds = {u: 1000 + k for k, u in enumerate(users)}

    # Multiple-choice items and their projections (used in (c)); computed first so the
    # preflight can check that Γ reaches the writer before any outcome is generated.
    items = M.load_items(mcq_path)
    item_proj = {i: projectors[users[i % len(users)]].project(it.question, claims_by_user[users[i % len(users)]]) for i, it in enumerate(items)}
    if preflight:
        # Amendment 3: stop before any outcome is generated if Γ would not reach the writer.
        from .decide import MIN_NONEMPTY, MIN_PROJ_BYTES
        stats = {"projection_bytes_mean": float(np.mean([r.projection.size_bytes() for r in projections.values()])),
                 "nonempty_gamma_writes": float(np.mean([bool(r.projection.gamma_fields()) for r in projections.values()])),
                 "nonempty_gamma_items": float(np.mean([bool(r.projection.gamma_fields()) for r in item_proj.values()])),
                 "gamma": {f"{u}|{t}": g for (u, t), g in gammas.items()}, "user_wikis": user_wikis}
        if (stats["projection_bytes_mean"] < MIN_PROJ_BYTES or stats["nonempty_gamma_writes"] < MIN_NONEMPTY
                or stats["nonempty_gamma_items"] < MIN_NONEMPTY):
            raise ManipulationCheckFailed(stats)

    # Generate every write once: three conditions x users x topics.
    outs: dict[str, dict[tuple[str, str], str]] = {"baseline": {}, "projection": {}, "placebo": {}}
    for t in topics:
        for k, u in enumerate(users):
            outs["baseline"][(u, t)] = _write(writer, t, {}, temperature, seeds[u])
            outs["projection"][(u, t)] = _write(writer, t, gammas[(u, t)], temperature, seeds[u])
            outs["placebo"][(u, t)] = _write(writer, t, PLACEBO_GAMMAS[k % len(PLACEBO_GAMMAS)], temperature, seeds[u])

    # (a) H-C2 lexicon adherence, with vs without Γ, per (user, topic) cell.
    cells = []
    for u in users:
        for t in topics:
            preferred = [w for w, v in gammas[(u, t)].get("lexicon", {}).items() if v == "preferred"]
            if not preferred:
                continue
            w = float(np.mean([p.lower() in outs["projection"][(u, t)].lower() for p in preferred]))
            o = float(np.mean([p.lower() in outs["baseline"][(u, t)].lower() for p in preferred]))
            cells.append((w, o))
    adh_diff = [w - o for w, o in cells]

    # (b) H-C17 cross-user homogeneity per topic.
    hom = {c: [] for c in outs}
    for t in topics:
        for c in outs:
            hom[c].append(homogeneity(writer.embed([outs[c][(u, t)] for u in users])))
    d_proj = [b - p for b, p in zip(hom["baseline"], hom["projection"])]
    d_plac = [b - p for b, p in zip(hom["baseline"], hom["placebo"])]
    d_spec = [pl - pr for pl, pr in zip(hom["placebo"], hom["projection"])]

    # (c) H-C17 cross-family error agreement within a request (MCQ), Γ rotated across users.
    without = {b.family: [M.parse_letter(b.generate(M.mcq_prompt(it), temperature=0.0, max_tokens=8)) for it in items] for b in families}
    with_ = {b.family: [M.parse_letter(b.generate(M.mcq_prompt(it, item_proj[i].projection.as_text()), temperature=0.0, max_tokens=8))
                        for i, it in enumerate(items)] for b in families}
    agree = M.bootstrap_delta(without, with_, items, B=bootstrap_B)
    inv_o = M.pairwise_agreement(without, items).invalid_rate
    inv_w = M.pairwise_agreement(with_, items).invalid_rate

    return {
        "hypothesis": "H-C2 (partial: rho not measured), H-C17",
        "users": len(users),
        "topics": len(topics),
        "temperature": temperature,
        "projection_bytes_mean": float(np.mean([r.projection.size_bytes() for r in projections.values()])),
        "local_only_writes": sum(r.local_only for r in projections.values()),
        "nonempty_gamma_writes": float(np.mean([bool(r.projection.gamma_fields()) for r in projections.values()])),
        "nonempty_gamma_items": float(np.mean([bool(r.projection.gamma_fields()) for r in item_proj.values()])),
        "anchor_mode": anchor_mode, "span_projection": span_projection,
        "user_wikis": user_wikis,
        "local_only_items": sum(r.local_only for r in item_proj.values()),
        "lanes_final": {ln: sum(r.lane_final.name == ln for r in projections.values()) for ln in ("PUBLIC", "SANITISABLE", "SENSITIVE")},
        "lexicon": {"cells": len(cells),
                    "adherence_with": float(np.mean([w for w, _ in cells])) if cells else None,
                    "adherence_without": float(np.mean([o for _, o in cells])) if cells else None,
                    "difference": float(np.mean(adh_diff)) if cells else None,
                    "difference_ci95": _boot_ci(adh_diff, bootstrap_B)},
        "homogeneity": {"per_topic": {c: [float(x) for x in v] for c, v in hom.items()},
                        "mean": {c: float(np.mean(v)) for c, v in hom.items()},
                        "reduction_projection": float(np.mean(d_proj)), "reduction_projection_ci95": _boot_ci(d_proj, bootstrap_B),
                        "reduction_placebo": float(np.mean(d_plac)), "reduction_placebo_ci95": _boot_ci(d_plac, bootstrap_B),
                        "projection_beyond_placebo": float(np.mean(d_spec)), "projection_beyond_placebo_ci95": _boot_ci(d_spec, bootstrap_B)},
        "error_agreement": {"items": len(items), "mcq_sha256": M.file_sha256(mcq_path), **agree,
                            "invalid_rate_without": inv_o, "invalid_rate_with": inv_w,
                            "accuracy_without": {f: M.accuracy(v, items) for f, v in without.items()},
                            "accuracy_with": {f: M.accuracy(v, items) for f, v in with_.items()}},
        "prediction": "projection lowers cross-user homogeneity and leaves within-request error agreement unchanged (|delta| <= 0.10)",
        "raw": {"writes": {c: {f"{u}|{t}": s for (u, t), s in d.items()} for c, d in outs.items()},
                "mcq_items": [it.idx for it in items], "mcq_without": without, "mcq_with": with_,
                "gamma": {f"{u}|{t}": g for (u, t), g in gammas.items()}},
    }


def _ci(x: list[float] | None) -> str:
    return f"[{x[0]:+.3f}, {x[1]:+.3f}]" if x else "n/a"


def format_c2(c2: dict[str, Any]) -> list[str]:
    lx, hm, ea = c2["lexicon"], c2["homogeneity"], c2["error_agreement"]
    f = lambda v: "n/a" if v is None else f"{v:.3f}"
    return [
        f"- C2 / H-C2 lexicon adherence: {f(lx['adherence_with'])} with Γ vs {f(lx['adherence_without'])} without "
        f"(difference {f(lx['difference'])}, 95% CI {_ci(lx['difference_ci95'])}; {lx['cells']} cells). Projection bytes {c2['projection_bytes_mean']:.0f}.",
        f"- C2 / H-C17 homogeneity across users (mean cosine, {c2['topics']} topics, T={c2['temperature']}): baseline {hm['mean']['baseline']:.3f}, "
        f"projection {hm['mean']['projection']:.3f}, placebo {hm['mean']['placebo']:.3f}. Reduction by projection {hm['reduction_projection']:+.3f} "
        f"{_ci(hm['reduction_projection_ci95'])}; by placebo {hm['reduction_placebo']:+.3f} {_ci(hm['reduction_placebo_ci95'])}; "
        f"projection beyond placebo {hm['projection_beyond_placebo']:+.3f} {_ci(hm['projection_beyond_placebo_ci95'])}.",
        f"- C2 / H-C17 error agreement given both wrong ({ea['items']} MCQ items): without Γ {f(ea['agreement_without'])} "
        f"(chance {f(ea['chance_without'])}, excess {_ci(ea['excess_ci95'])}); with Γ {f(ea['agreement_with'])}; "
        f"delta {f(ea['delta'])} {_ci(ea['delta_ci95'])}; invalid answers {ea['invalid_rate_without']:.3f}/{ea['invalid_rate_with']:.3f}.",
    ]


def c10_selection(generations: int = 6, k: int = 5, reliability: float = 0.5, seed: int = 0) -> dict[str, Any]:
    """Runs the real AdapterManager with simulated trainer/evaluator (SIMULATION)."""
    from swarmbly_lce.claims import Anchor, Claim, ClaimType, Provenance
    policy = LearningPolicy.from_mapping({"learning_policy": {"sources": {"s": {"authored_by_user": True, "learn_style": True, "learn_procedure": True}}}})
    wiki = Wiki(policy=policy)
    for i in range(40):
        c = Claim(text=f"Suelo usar la construcción número {i} al escribir informes técnicos.", type=ClaimType.STYLE,
                  anchors=[Anchor("s/f.md", 0, 10, "h", verified=True)], provenance=Provenance(epistemic_distance=0))
        wiki.add(c)
    ids = list(wiki.claims)
    for a, b in zip(ids, ids[1:]):
        wiki.link(a, b)
    for _ in range(4):
        wiki.consolidation_cycle()
    new = ExampleBuilder(wiki).from_claims()
    replay = [Example("replay", f"old {i}", f"old answer {i}") for i in range(20)]
    general = [Example("general", f"gen {i}", f"general {i}") for i in range(20)]
    mgr = AdapterManager(wiki, "base-3b", MockTrainer(seed=seed), MockEvaluator(reliability=reliability, seed=seed))
    import random
    rng = random.Random(seed)
    for _ in range(generations):
        recipes = [Recipe(rank=rng.choice([4, 8, 16]), lr=rng.choice([5e-5, 1e-4, 2e-4]), seed=rng.randrange(10**6)) for _ in range(k)]
        mgr.run_generation(new, replay, general, recipes)
    accepted = [h for h in mgr.history if h["winner"]]
    return {"hypothesis": "H-C15 (simulation through AdapterManager)", "generations": generations, "candidates_per_generation": k,
            "accepted": len(accepted), "distinct_test_sets": len({h["test_id"] for h in mgr.history}),
            "history": mgr.history, "examples_eligible": len(new)}


def canary_check(backend: Backend, wiki: Wiki, canary_path: Path = DATA / "canary_es-EC.json") -> dict[str, Any]:
    canary = CanarySet.load(canary_path)
    examples = ExampleBuilder(wiki).from_claims()
    canary.guard_training(e.response for e in examples)  # raises if violated
    answers = {}
    for item in canary.items:
        q = f"¿Qué significa '{item.term}' en el español de Ecuador?"
        answers[item.term] = _answer(backend, q)
    return {
        "items": len(canary.items),
        "verified_items": sum(i.verified for i in canary.items),
        "tail_mass": canary.tail_mass(answers),
        "identity_violation_rate": canary.identity_violation_rate(answers.values()),
        "training_guard": "passed",
        "note": "items are unverified drafts until a native speaker confirms them; do not report as a result",
    }
