"""T06 — building a corpus whose global questions the model pool can answer.

WHY THE CURRENT ONE DOES NOT WORK
=================================
Measured from ``results/lcurve-dev-*/rows.json``, per question, monolithic arm:

    Q03  total on_hand across every row     0/24
    Q05  count rows below their reorder_at  0/24
    Q04  which row has the largest on_hand  1/24

All three are **N-ary aggregates**: their answer is a function of every row.
A 2-3B model asked to sum ten four-digit numbers does not fail at the protocol,
it fails at the arithmetic. With the baseline on the floor there is no
difference left for fragmentation to make, which is why the L curve could not
be measured (WHITEPAPER_V2 §15.4, L15).

THE FIX
=======
A question is **global** when no single fragment can answer it. That does NOT
require it to touch every row -- it requires it to touch rows that the cut
separates. Two rows are enough.

So the generator emits **k-ary questions with k = 2 or 3**, over rows it has
verified land in different fragments for every declared cell. They stay global
by construction while the arithmetic drops from "sum twenty numbers" to "add
two". Guessability is controlled by preferring forms whose answer space is
large (a sum) over forms with a coin-flip answer space (a yes/no).

WHAT THIS MODULE DOES AND DOES NOT ESTABLISH
============================================
It establishes, mechanically and without a model: that each question's
referenced rows straddle a real cut, that its key is computable and unique,
and that its arithmetic stays within the declared ceiling.

It does NOT establish that the pool can answer them. That needs a run, and the
admission gate below reports it as PENDING rather than assuming it. A corpus
that passes the mechanical pre-flight and then fails the monolithic floor is
still a rejected corpus.
"""

import json
import random

__all__ = ["QUESTION_FORMS", "generate_questions", "preflight",
           "AdmissionReport", "fragment_of", "build_document"]

#: Maximum number of rows a generated question may depend on.
ARITY_CEILING = 3
#: Maximum number of arithmetic operands in a generated answer.
OPERAND_CEILING = 3
#: The monolithic arm must clear this on the global questions (§15.4).
MONOLITHIC_FLOOR = 0.5


def fragment_of(row_index, L):
    """Which fragment a row falls in, for a row-block split of size ``L``."""
    return row_index // L


def _straddles(indices, cells):
    """True when ``indices`` land in different fragments for EVERY declared cell."""
    for _n, L in cells:
        if len({fragment_of(i, L) for i in indices}) < 2:
            return False
    return True


# --- question forms -----------------------------------------------------------
# Each form: (id, arity, operands, builder). The builder returns (text, expected,
# mode) given the chosen rows. `operands` is the arithmetic load, which is what
# the current corpus gets wrong.

def _f_pair_sum(rows):
    a, b = rows
    return (f"What is the combined on_hand of {a['id']} and {b['id']}?",
            str(a["on_hand"] + b["on_hand"]), "numeric")


def _f_pair_diff(rows):
    a, b = rows
    hi, lo = (a, b) if a["on_hand"] >= b["on_hand"] else (b, a)
    return (f"How much larger is the on_hand of {hi['id']} than that of {lo['id']}?",
            str(hi["on_hand"] - lo["on_hand"]), "numeric")


def _f_pair_argmax(rows):
    a, b = rows
    win = a if a["on_hand"] > b["on_hand"] else b
    return (f"Of {a['id']} and {b['id']}, which row id has the larger on_hand?",
            win["id"], "exact_norm")


def _f_triple_sum(rows):
    a, b, c = rows
    return (f"What is the combined on_hand of {a['id']}, {b['id']} and {c['id']}?",
            str(a["on_hand"] + b["on_hand"] + c["on_hand"]), "numeric")


def _f_triple_argmax(rows):
    a, b, c = rows
    win = max(rows, key=lambda r: r["on_hand"])
    return (f"Among {a['id']}, {b['id']} and {c['id']}, which row id has the "
            f"largest on_hand?", win["id"], "exact_norm")


def _f_pair_warehouse_of_larger(rows):
    a, b = rows
    win = a if a["on_hand"] > b["on_hand"] else b
    return (f"Which warehouse holds whichever of {a['id']} and {b['id']} has the "
            f"larger on_hand?", win["warehouse"], "exact_norm")


QUESTION_FORMS = {
    "pair_sum":            (2, 2, _f_pair_sum),
    "pair_diff":           (2, 2, _f_pair_diff),
    "pair_argmax":         (2, 1, _f_pair_argmax),
    "triple_sum":          (3, 3, _f_triple_sum),
    "triple_argmax":       (3, 1, _f_triple_argmax),
    "pair_warehouse":      (2, 1, _f_pair_warehouse_of_larger),
}

#: Forms whose answer space is a coin flip or near it are excluded by default:
#: a 0.5 baseline cannot show a difference. ``pair_argmax`` is kept because it
#: is exact-graded over row ids and is paired with a sum in every document.
DEFAULT_FORMS = ("pair_sum", "pair_diff", "triple_sum", "pair_argmax",
                 "triple_argmax", "pair_warehouse")


# --- generation ---------------------------------------------------------------

def generate_questions(rows, cells, n_local=2, n_global=3, seed=0,
                       forms=DEFAULT_FORMS):
    """Build local controls and provably-global questions for one document.

    ``rows`` is a list of dicts with id/warehouse/goods/on_hand/reorder_at.
    ``cells`` is the list of ``(N, L)`` pairs this document will be run at.
    Raises ``ValueError`` if no row set straddles every declared cell -- the
    generator refuses rather than emitting a question that one fragment could
    answer alone.
    """
    rng = random.Random(seed)
    n = len(rows)
    out = []
    qid = 1
    local_rows = set()

    # local controls: single-row lookups, the check that chunking works at all
    for _ in range(n_local):
        r = rows[rng.randrange(n)]
        local_rows.add(r["id"])
        if rng.random() < 0.5:
            text, exp, mode = f"What is on_hand for {r['id']}?", str(r["on_hand"]), "numeric"
        else:
            text, exp, mode = (f"Which warehouse holds {r['id']}?",
                               r["warehouse"], "exact_norm")
        out.append({"id": f"{qid:02d}", "kind": "local", "text": text,
                    "expected": exp, "mode": mode, "rows": [r["id"]],
                    "form": "local_lookup", "operands": 1})
        qid += 1

    # global questions: verified to straddle every declared cell.
    # Stratified: the first one is always arithmetic, so that no document can
    # end up made entirely of forms with a small answer space.
    numeric_forms = tuple(f for f in forms
                          if f in ("pair_sum", "pair_diff", "triple_sum"))
    if not numeric_forms:
        raise ValueError("no numeric global form available: refuse")
    tried = 0
    while sum(1 for q in out if q["kind"] == "global") < n_global:
        tried += 1
        if tried > 4000:
            raise ValueError(
                f"no row set straddles every declared cell {cells} after {tried} "
                f"attempts: refuse to emit a question a single fragment could answer"
            )
        made = sum(1 for q in out if q["kind"] == "global")
        pool = numeric_forms if made == 0 else forms
        form = pool[rng.randrange(len(pool))]
        arity, operands, builder = QUESTION_FORMS[form]
        if arity > ARITY_CEILING or operands > OPERAND_CEILING:
            continue
        idx = rng.sample(range(n), arity)
        if not _straddles(idx, cells):
            continue
        chosen = [rows[i] for i in idx]
        # A global question must not reuse a row a local control already
        # answered: the local answer would hand over the value the global one
        # is supposed to require reading the material for.
        if any(r["id"] in local_rows for r in chosen):
            continue
        text, exp, mode = builder(chosen)
        if any(q["text"] == text for q in out):
            continue
        out.append({"id": f"{qid:02d}", "kind": "global", "text": text,
                    "expected": exp, "mode": mode,
                    "rows": [r["id"] for r in chosen], "form": form,
                    "operands": operands, "row_indices": idx})
        qid += 1
    return out


def build_document(doc_id, rows, cells, seed=0, n_local=2, n_global=3):
    """Assemble one corpus document in the schema ``prompts/lcurve.json`` uses."""
    qs = generate_questions(rows, cells, n_local=n_local, n_global=n_global, seed=seed)
    material = "\n".join(
        f"{r['id']} | {r['warehouse']} | {r['goods']} | on_hand={r['on_hand']} | "
        f"reorder_at={r['reorder_at']}" for r in rows)
    qlines = "\n".join(f"[{q['id']}] {q['text']}" for q in qs)
    prompt = (f"Answer the questions from the inventory below.\n\nQuestions:\n"
              f"{qlines}\n\nInventory:\n{material}\n")
    key = {q["id"]: {"expected": q["expected"], "mode": q["mode"],
                     "kind": q["kind"]} for q in qs}
    return {"id": doc_id, "category": "lcurve", "n_rows": len(rows),
            "expected_decomposable": True, "prompt": prompt, "material": material,
            "questions": qs, "key": key, "cells": [list(c) for c in cells],
            "notes": ("Global questions are k-ary with k<=3 over rows verified to "
                      "fall in different fragments for every declared cell. They "
                      "stay unanswerable by any single fragment while the "
                      "arithmetic stays within reach of the node pool.")}


# --- admission gate -----------------------------------------------------------

def _chance_of(q):
    """Probability of answering ``q`` correctly without reading the material.

    A selection form is guessable at 1/arity. A numeric answer is not
    meaningfully guessable, but it is not zero either -- small integers recur --
    so it is charged a conservative 1/100 rather than 0.
    """
    if q.get("mode") == "numeric":
        return 0.01
    arity = max(2, len(q.get("rows", [])) or 2)
    return 1.0 / arity


class AdmissionReport:
    def __init__(self):
        self.checks = []          # (name, ok, detail)
        self.pending = []         # checks that need a run

    def add(self, name, ok, detail):
        self.checks.append((name, bool(ok), detail))

    def defer(self, name, detail):
        self.pending.append((name, detail))

    @property
    def failures(self):
        return [(n, d) for n, ok, d in self.checks if not ok]

    @property
    def admitted(self):
        return not self.failures and not self.pending

    def __str__(self):
        lines = []
        for n, ok, d in self.checks:
            lines.append(f"  {'PASS' if ok else 'FAIL'}  {n}: {d}")
        for n, d in self.pending:
            lines.append(f"  PEND  {n}: {d}")
        return "\n".join(lines)


def preflight(documents, monolithic_global_rate=None,
              floor=MONOLITHIC_FLOOR):
    """Mechanical admission checks for a candidate corpus.

    Everything here is decidable without a model. The one check that is not --
    whether the pool can actually answer the questions -- is DEFERRED, not
    assumed, and the corpus is not admitted until it is supplied.
    """
    rep = AdmissionReport()
    if not documents:
        rep.add("non-empty", False, "no documents")
        return rep

    # 1. every global question provably straddles every declared cell
    bad = []
    for d in documents:
        cells = [tuple(c) for c in d["cells"]]
        index_of = {r.split(" | ")[0]: i
                    for i, r in enumerate(d["material"].split("\n")) if r.strip()}
        for q in d["questions"]:
            if q["kind"] != "global":
                continue
            idx = [index_of[r] for r in q["rows"] if r in index_of]
            if len(idx) != len(q["rows"]) or not _straddles(idx, cells):
                bad.append((d["id"], q["id"]))
    rep.add("global questions straddle every declared cell", not bad,
            "all verified" if not bad else f"{len(bad)} do not: {bad[:5]}")

    # 2. arity and arithmetic ceilings
    over = [(d["id"], q["id"], q.get("operands"))
            for d in documents for q in d["questions"]
            if q.get("operands", 1) > OPERAND_CEILING
            or len(q.get("rows", [])) > ARITY_CEILING]
    rep.add(f"arity <= {ARITY_CEILING} and operands <= {OPERAND_CEILING}",
            not over, "within ceiling" if not over else f"{len(over)} exceed: {over[:5]}")

    # 3. keys computable, unique, non-empty
    empty = [(d["id"], qid) for d in documents for qid, k in d["key"].items()
             if k["expected"] in ("", None)]
    rep.add("every key computable and non-empty", not empty,
            "all present" if not empty else f"{len(empty)} empty")

    # 4. local controls present (without them a global failure is uninterpretable)
    noloc = [d["id"] for d in documents
             if not any(q["kind"] == "local" for q in d["questions"])]
    rep.add("local control questions present", not noloc,
            "present in every document" if not noloc else f"missing in {noloc[:5]}")

    # 5. chance baseline: what a model scores by guessing, without reading.
    #    Counting one form was not enough -- a document made of 3-way argmax
    #    questions has a 33% floor and would have passed a form count. The
    #    guessable mass is measured directly instead.
    globals_ = [q for d in documents for q in d["questions"] if q["kind"] == "global"]
    chance = sum(_chance_of(q) for q in globals_) / max(1, len(globals_))
    rep.add("chance baseline below 0.20", chance < 0.20,
            f"guessing scores {chance:.3f} across {len(globals_)} global questions")

    # 5b. at least one arithmetic global question per document
    noarith = [d["id"] for d in documents
               if not any(q["kind"] == "global" and q["mode"] == "numeric"
                          for q in d["questions"])]
    rep.add("every document has an arithmetic global question", not noarith,
            "present" if not noarith else f"missing in {len(noarith)}: {noarith[:5]}")

    # 5c. local controls must not leak the rows a global question depends on
    leaks = []
    for d in documents:
        loc = {r for q in d["questions"] if q["kind"] == "local"
               for r in q.get("rows", [])}
        for q in d["questions"]:
            if q["kind"] == "global" and loc.intersection(q.get("rows", [])):
                leaks.append((d["id"], q["id"],
                              sorted(loc.intersection(q["rows"]))))
    rep.add("local controls do not leak rows used by global questions", not leaks,
            "disjoint" if not leaks else f"{len(leaks)} leak: {leaks[:3]}")

    # 6. the check that needs a run
    if monolithic_global_rate is None:
        rep.defer("monolithic arm clears the floor",
                  f"needs a run; corpus is NOT admitted until the monolithic arm "
                  f"scores >= {floor:.2f} on the global questions")
    else:
        rep.add("monolithic arm clears the floor",
                monolithic_global_rate >= floor,
                f"{monolithic_global_rate:.3f} vs floor {floor:.2f}")
    return rep
