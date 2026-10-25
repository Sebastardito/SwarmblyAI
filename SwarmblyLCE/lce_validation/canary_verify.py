"""Merge native-speaker verification sheets into the canary set (SPEC 15.3).

    python -m lce_validation.canary_verify verificador_A.csv verificador_B.csv verificador_C.csv
    python -m lce_validation.canary_verify sheets/*.csv --out lce_validation/data/canary_es-EC.json

Rule (fixed in data/canary_verification/INSTRUCCIONES.md): an item is
**verified** when at least ``--min-confirm`` verifiers (default 2) know the term
and confirm its gloss ("si"), and none marks it as offensive. "parcial" counts
as knowing the term but not as confirming the gloss; corrected glosses are
listed for manual review and never merged automatically. Candidate and new
terms enter the set only if verified. At least three sheets are required.

Verifiers are pseudonymous: only counts and regions are recorded.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import defaultdict
from pathlib import Path

from .experiments import DATA

DEFAULT_OUT = DATA / "canary_es-EC.json"
YES = {"si", "sí", "yes", "s", "y"}


def _norm(v: str | None) -> str:
    return (v or "").strip().lower()


def merge(sheets: list[Path], current: Path, min_confirm: int = 2) -> tuple[dict, list[dict]]:
    if len(sheets) < 3:
        raise ValueError("at least three verification sheets are required")
    rows: dict[str, list[dict]] = defaultdict(list)
    proposed: dict[str, dict] = {}
    for s in sheets:
        with open(s, newline="", encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                term = _norm(r.get("termino"))
                if not term:
                    continue
                rows[term].append(r)
                proposed.setdefault(term, r)
    cur = json.loads(Path(current).read_text(encoding="utf-8"))
    by_term = {i["term"].lower(): i for i in cur["items"]}
    review: list[dict] = []
    items = []
    for term, rs in rows.items():
        know = sum(_norm(r.get("lo_conoce (si/no)")) in YES for r in rs)
        confirm = sum(_norm(r.get("lo_conoce (si/no)")) in YES and _norm(r.get("significado_correcto (si/no/parcial)")) in YES for r in rs)
        offensive = sum(_norm(r.get("ofensivo_o_vulgar (si/no)")) in YES for r in rs)
        regions = sorted({r.get("region_donde_se_usa", "").strip() for r in rs if r.get("region_donde_se_usa", "").strip()})
        corrections = [r.get("glosa_corregida_es", "").strip() for r in rs if r.get("glosa_corregida_es", "").strip()]
        verified = confirm >= min_confirm and offensive == 0
        if corrections or offensive:
            review.append({"term": term, "corrections": corrections, "offensive_marks": offensive})
        base = by_term.get(term)
        if base is None:
            p = proposed[term]
            glosses = [g.strip() for g in (p.get("glosa_propuesta_es", "") + "," + p.get("glosa_propuesta_en", "")).split(",") if g.strip()]
            base = {"variety": cur.get("variety", "es-EC"), "term": term, "glosses": glosses}
        if base is not None and (term in by_term or verified):
            items.append({**base, "verified": verified,
                          "verification": {"sheets": len(rs), "know": know, "confirm": confirm, "offensive": offensive, "regions": regions}})
    # Items in the current set that no sheet mentions stay unverified.
    for term, it in by_term.items():
        if term not in rows:
            items.append({**it, "verified": False})
    out = {**cur, "items": sorted(items, key=lambda i: i["term"]),
           "status": ("VERIFIED SUBSET — only items with verified:true may be used to report a result."
                      if any(i["verified"] for i in items) else cur.get("status")),
           "verification_rule": f">= {min_confirm} of {len(sheets)} pseudonymous native speakers know the term and confirm the gloss; none marks it offensive",
           "verified_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    return out, review


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sheets", nargs="+")
    ap.add_argument("--current", default=str(DEFAULT_OUT))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--min-confirm", type=int, default=2)
    args = ap.parse_args(argv)
    out, review = merge([Path(s) for s in args.sheets], Path(args.current), args.min_confirm)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    n_ver = sum(i["verified"] for i in out["items"])
    print(f"{n_ver}/{len(out['items'])} items verified -> {args.out}")
    for r in review:
        print(f"  review: {r['term']}: corrections={r['corrections']} offensive_marks={r['offensive_marks']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
