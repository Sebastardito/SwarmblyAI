"""Grading instruments: coverage, constraints, answer-key QA, numeric
precision/recall, repetition, seam-free fraction — and the coherence tax.
The baseline floor (0.20) and the refusal rules from the whitepaper apply
here.

The numeric and repetition components exist to give the delta axis (M4)
resolution that binary item-presence cannot: a hallucinated total (precision)
and template repetition (continuous, not binary) are exactly the damage a
bad cut produces.
"""

import re

from . import units


def _norm(s):
    return re.sub(r"[^a-z0-9\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1\u00fc]", "",
                  s.lower())


def coverage(text, items):
    """Fraction of required items present in the output."""
    if not items:
        return 1.0
    return sum(1 for it in items
               if re.search(re.escape(it), text, re.IGNORECASE)) / len(items)


def qa_score(text, answer_keys):
    """Exact-normalized match per question."""
    if not answer_keys:
        return 1.0
    hits = 0
    for key in answer_keys:
        keys = key if isinstance(key, (list, tuple)) else [key]
        if any(_norm(k) in _norm(text) for k in keys):
            hits += 1
    return hits / len(answer_keys)


def numeric_grade(text, task):
    """Numeric fidelity: 0.6*precision + 0.4*key_recall.

    Precision = of every number the answer MENTIONS, how many exist in the
    ground-truth set (a hallucinated total like 1044.8 is punished).
    Key recall = of the KEY numbers (total + top movers' value and change),
    how many appear. Only for tasks that carry `numeric_keys`."""
    gt = set(task.get("numeric_keys", []))
    keys = set(task.get("key_numeric", []))
    if not gt:
        return None
    # los nombres de entidad con dígitos (Coupling D-8, Tranche M-1) no son
    # números: se eliminan antes de extraer
    clean = text
    for e in task.get("entities", {}):
        clean = re.sub(re.escape(e), " ", clean, flags=re.IGNORECASE)
    mentioned = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", clean)]

    def close(a, b):
        # redondeo legítimo: tolerancia absoluta mínima 0.05, relativa 2%
        return abs(a - b) <= max(0.05, 0.02 * max(abs(a), abs(b), 1.0))

    gtf = [float(x) for x in gt]
    used = set()
    tp = 0
    for m in mentioned:
        best = None
        for g in gtf:
            if g in used or not close(m, g):
                continue
            if best is None or abs(m - g) < abs(m - best):
                best = g
        if best is not None:
            used.add(best)
            tp += 1
    precision = tp / max(1, len(mentioned))
    keyf = [float(x) for x in keys]
    key_hits = sum(1 for k in keyf
                   if any(close(m, k) for m in mentioned))
    key_recall = key_hits / max(1, len(keyf))
    return round(0.6 * precision + 0.4 * key_recall, 4)


def repetition_score(text):
    """Continuous repetition penalty: 1 at zero repeated 5-grams, decaying
    to 0 at >= 10 repeats (the mechanical half of `no_repeated_ngram`)."""
    r = repeated_5grams(text)
    return max(0.0, 1.0 - r / 10.0)


def constraint_score(text, task):
    """term_once + no_repeated_ngram compliance (the irreducible class)."""
    score = 0.0
    n = 0
    uniq = task.get("unique_terms", [])
    if uniq:
        n += 1
        counts = [len(re.findall(re.escape(t), text, re.IGNORECASE)) for t in uniq]
        score += sum(1 for c in counts if c == 1) / len(uniq)
    if task.get("no_repeat", False):
        n += 1
        score += 1.0 if repeated_5grams(text) == 0 else 0.0
    return (score / n) if n else 1.0


def repeated_5grams(text):
    words = [w.lower() for w in re.findall(r"[a-z0-9]+", text)]
    seen, repeats = set(), set()
    for i in range(len(words) - 4):
        g = tuple(words[i:i + 5])
        if g in seen:
            repeats.add(g)
        seen.add(g)
    return len(repeats)


def seam_free_fraction(text):
    """Fraction of consecutive sentence pairs with no repeated 5-gram and no
    duplicated sentence (mechanical seam detection)."""
    sents = units.split_sentences(text)
    if len(sents) < 2:
        return 1.0
    ok = 0
    for i in range(len(sents) - 1):
        pair = sents[i] + " " + sents[i + 1]
        if repeated_5grams(pair) == 0 and _norm(sents[i]) != _norm(sents[i + 1]):
            ok += 1
    return ok / (len(sents) - 1)


def grade(task, text):
    """Composite per-task score in [0, 1], with the pieces kept separate."""
    w = task["weights"]
    out = {
        "coverage": coverage(text, task.get("required_items", [])),
        "qa": qa_score(text, task.get("answer_keys", [])),
        "constraints": constraint_score(text, task),
        "seam_free": seam_free_fraction(text),
        "repetition": repetition_score(text),
    }
    num = numeric_grade(text, task)
    if num is not None:
        out["numeric"] = num
    score = sum(out[k] * w[k] for k in w if k in out)
    out["score"] = round(score, 4)
    return out


def coherence_tax(mono_score, frag_score):
    """Tax in percentage points: positive = fragmentation is worse.
    Refuses (returns None) if the monolithic baseline is below the floor."""
    if mono_score is None or mono_score < 0.20:
        return None, f"baseline below floor ({mono_score:.3f}): nothing to compare"
    return round((mono_score - frag_score) / mono_score * 100.0, 2), "ok"
