"""Planner and router (P2, P9, E20): weak-interface cuts, DAG, delta,
uniqueness assignment (M2), and the refusal decision."""

from . import units


def weak_interface_cuts(sentences, L_target, maximize=False):
    """Cut with L_target sentences per fragment (P9).

    Weak mode: walk accumulating L_target sentences, cut at the local minimum
    of interface coupling. Strong mode (anti-P9, for the D(rho, delta)
    experiment): SAME number of cuts and SAME neighbourhoods as the weak plan,
    each swapped to the most-coupled boundary nearby — only delta changes
    while L (and hence rho) stays comparable.
    """
    n = len(sentences)
    if n <= L_target:
        return []
    bc = [units.coupling(sentences[i], sentences[i + 1]) for i in range(n - 1)]
    window = max(1, L_target // 3)
    if not maximize:
        cuts = []
        pos = L_target
        while pos < n - 1:
            lo = max(1, pos - window)
            hi = min(n - 1, pos + window)
            candidates = sorted(range(lo, hi + 1), key=lambda i: bc[i - 1])
            best = next((i for i in candidates if i not in cuts), None)
            if best is None:
                break
            cuts.append(best)
            pos = best + L_target
        return sorted(cuts)
    weak_cuts = weak_interface_cuts(sentences, L_target, maximize=False)
    strong = []
    for c in weak_cuts:
        lo = max(1, c - window)
        hi = min(n - 1, c + window)
        cands = [i for i in range(lo, hi + 1) if i not in strong]
        strong.append(max(cands, key=lambda i: bc[i - 1]) if cands else c)
    strong = sorted(set(strong))
    if len(strong) != len(weak_cuts):
        return weak_cuts   # manipulation collapsed a cut: fall back (no variance)
    return strong


def fragment_ranges(sentences, cuts):
    """(start, end) inclusive sentence ranges from cut boundaries."""
    bounds = [0] + [c for c in cuts] + [len(sentences)]
    return [(bounds[i], bounds[i + 1] - 1) for i in range(len(bounds) - 1)]


def compute_delta(sentences, cuts, chains, explicit_crossings):
    """delta = necessary relations crossing a cut, normalised per fragment.

    Two components: (a) interface coupling AT the cut — shared content words
    between the two adjacent sentences, which is the direct measure of how
    much dependency the cut severed; (b) entity-chain crossings and explicit
    cross-references. The boundary-coupling term is what discriminates a P9
    cut from an anti-P9 cut at the same L.
    """
    n_frag = len(cuts) + 1
    interface = 0.0
    for c in cuts:
        if 0 < c < len(sentences):
            interface += units.coupling(sentences[c - 1], sentences[c])
    chain_crossings = 0
    for chain in chains.values():
        if len(chain) < 2:
            continue
        s = sorted(chain)
        for i in range(len(s) - 1):
            if any(s[i] < c <= s[i + 1] for c in cuts):
                chain_crossings += 1
    return (interface + chain_crossings + explicit_crossings) / n_frag


def plan(material, entities, L_target, F, unique_terms, explicit_crossings=0,
         cut_mode="weak"):
    """Full plan: sentences, cuts, fragments, delta, uniqueness.

    cut_mode: "weak" (P9, minimises delta) or "strong" (anti-P9, maximises
    delta at the same L — the D(rho, delta) experiment)."""
    sentences = units.split_sentences(material)
    cuts = weak_interface_cuts(sentences, L_target,
                               maximize=(cut_mode == "strong"))
    ranges = fragment_ranges(sentences, cuts)
    chains = units.entity_chains(sentences, entities)
    delta = compute_delta(sentences, cuts, chains, explicit_crossings)

    # M2: assign each uniqueness element to exactly one fragment (round-robin)
    unique_here = {i: [] for i in range(len(ranges))}
    for k, term in enumerate(unique_terms):
        unique_here[k % max(1, len(ranges))].append(term)

    return {
        "sentences": sentences,
        "cuts": cuts,
        "ranges": ranges,
        "delta": round(delta, 3),
        "n_fragments": len(ranges),
        "unique_here": unique_here,
        "chains": chains,
    }


def router(task, material, min_sentences=8):
    """Decide whether to fragment (P2: may refuse). Deterministic features.

    Refuses when: material too short, task is sequential (result-dependency
    chain), or the task kind is not decomposable.
    """
    sentences = units.split_sentences(material)
    n = len(sentences)
    if task.get("sequential"):
        return False, f"result-dependency chain: refuse (depth {task.get('depth', 1)})"
    if n < min_sentences:
        return False, f"material too short ({n} sentences < {min_sentences})"
    if not task.get("decomposable", True):
        return False, "task kind not decomposable"
    return True, f"decomposable: {n} sentences, kind={task['kind']}"
