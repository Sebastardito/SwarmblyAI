"""Assembly (P4, E7): discount flanks, select-then-splice, bridge only at a
failed seam, cardinality verification (M2), and the seam audit (P6)."""

import re

from . import llm, units


def discount_flanks(fragment_text, flank_lead_text, flank_trail_text):
    """Remove flank sentences that were duplicated from neighbours, so the
    flank enables continuity without reappearing as repetition."""
    keep = units.split_sentences(fragment_text)
    drop_lead = len(units.split_sentences(flank_lead_text)) if flank_lead_text else 0
    drop_trail = len(units.split_sentences(flank_trail_text)) if flank_trail_text else 0
    if drop_lead:
        keep = keep[drop_lead:]
    if drop_trail:
        keep = keep[:-drop_trail]
    return " ".join(keep)


def seam_similarity(tail_text, head_text, embed_cache=None):
    """Embedding cosine between the end of one fragment and the start of the
    next (v1.4 tau_sem instrument, retained for the macro level)."""
    tv = units.split_sentences(tail_text)[-2:]
    hv = units.split_sentences(head_text)[:2]
    if not tv or not hv:
        return 1.0
    a, b = " ".join(tv), " ".join(hv)
    if embed_cache is not None:
        e = llm.embed([a, b])
        return llm.cosine(e[0], e[1])
    return 1.0


def assemble(plan, results, gamma, task, tau_sem=0.55, embed=True,
             bridge_fn=None, discard_flanks=True):
    """Splice fragments in plan order; record every seam (P6)."""
    pieces, seams = [], []
    sentences = plan["sentences"]
    for i, (a, b) in enumerate(plan["ranges"]):
        frag_text = " ".join(sentences[a:b + 1])
        lead = " ".join(sentences[max(0, a - 1):a]) if a > 0 else ""
        trail = " ".join(sentences[b + 1:b + 2]) if b + 1 < len(sentences) else ""
        body = results[i]
        if discard_flanks:
            body = discount_flanks(body, lead, trail)
        if pieces:
            sim = seam_similarity(pieces[-1], body, embed_cache=llm if embed else None)
            if sim >= tau_sem or bridge_fn is None:
                pieces.append(body)
                seams.append((i, "splice", round(sim, 3)))
            else:
                bridge = bridge_fn(pieces[-1], body, gamma)
                pieces.append(bridge)
                pieces.append(body)
                seams.append((i, "bridge", round(sim, 3)))
        else:
            pieces.append(body)
    text = " ".join(pieces)

    # cardinality (M2): each unique term must appear exactly once
    card = {}
    for term in task.get("unique_terms", []):
        count = len(re.findall(re.escape(term), text, re.IGNORECASE))
        card[term] = count
    card_report = {
        "over_compression": sum(1 for c in card.values() if c == 0),
        "over_expansion": sum(1 for c in card.values() if c > 1),
        "exactly_once": sum(1 for c in card.values() if c == 1),
        "per_term": card,
    }
    # M2 corregido: ejecución mecánica EN el ensamblador (sobre-expansión se
    # recorta; la sobre-compresión se reporta para re-dispatch del dueño)
    text, enforced_counts = enforce_cardinality(text, task.get("unique_terms", []))
    card_report["enforced"] = enforced_counts
    card_report["enforced_exactly_once"] = sum(
        1 for c in enforced_counts.values() if c == 1)
    card_report["enforced_missing"] = [
        t for t, c in enforced_counts.items() if c == 0]

    # seam audit: repeated long n-grams across the assembled output
    seam_report = {"n": len(seams), "seams": seams,
                   "repeated_5grams": repeated_ngrams(text, 5)}

    return {"text": text, "seams": seam_report, "cardinality": card_report}


def enforce_cardinality(text, terms):
    """Mechanical over-expansion repair (the v1.4 assembler pass): keep the
    FIRST occurrence of each unique term and delete every later one.

    Over-compression (a term absent entirely) is NOT repairable from the text:
    the plan assignment is what must prevent it. Returns (repaired_text,
    {term: final_count}).
    """
    repaired = text
    counts = {}
    for term in terms:
        pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
        occurrences = list(pattern.finditer(repaired))
        if len(occurrences) > 1:
            # delete all but the first, replacing with '' to preserve spacing
            for m in reversed(occurrences[1:]):
                repaired = repaired[:m.start()] + repaired[m.end():]
        counts[term] = len(pattern.findall(repaired))
    return repaired, counts


def repeated_ngrams(text, n=5):
    """Count distinct n-grams (content words) that repeat — the mechanical
    half of `no_repeated_ngram`."""
    words = [w.lower() for w in re.findall(r"[a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1\u00fc0-9]+", text)]
    seen, repeats = set(), set()
    for i in range(len(words) - n + 1):
        g = tuple(words[i:i + n])
        if g in seen:
            repeats.add(g)
        seen.add(g)
    return len(repeats)
