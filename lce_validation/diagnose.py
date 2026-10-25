"""Exploratory diagnosis of digestion, anchoring and projection with a real model (NOT a confirmatory run).

    python -m lce_validation.diagnose --model qwen2.5:3b

Written after confirmatory run 1, in which every projection came out empty
(2 bytes). For the fixture corpus and each synthetic user it digests the
sources twice, with offset anchoring (v0.1) and with quote anchoring, and
prints every claim (type, anchored or not, the span it points to) and the
projection that results with and without reading the anchored span. It decides
nothing: it shows where the treatment is lost. Output: results/diagnostics/.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from swarmbly_lce.backends import OpenAICompatBackend
from swarmbly_lce.projection import Projector

from . import experiments as E

ROOT = Path(__file__).resolve().parents[1]


def _project(wiki, span: bool) -> dict:
    sp = wiki.space
    pr = Projector(span_text=(lambda c: sp.read(c.anchors[0].source)[c.anchors[0].start:c.anchors[0].end]) if span else None)
    r = pr.project("escribe sobre la genética de poblaciones", list(wiki.claims.values()))
    return {"gamma": r.projection.gamma_fields(), "bytes": r.projection.size_bytes(), "lane": r.lane_final.name}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", default="qwen2.5:3b")
    ap.add_argument("--url", default="http://localhost:11434/v1")
    ap.add_argument("--out", default=str(ROOT / "results" / "diagnostics"))
    args = ap.parse_args(argv)
    b = OpenAICompatBackend(model=args.model, base_url=args.url)
    corpora = [("corpus", E.FIXTURES / "corpus", E.FIXTURES / "policy.json")]
    corpora += [(p.name, p, E.FIXTURES / "users_policy.json") for p in sorted((E.FIXTURES / "users").iterdir()) if p.is_dir()]
    report: dict = {"model": args.model, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "label": "EXPLORATORY DIAGNOSIS - not a confirmatory run, decides nothing", "corpora": {}}
    lines = [f"# Diagnosis of digestion and projection ({args.model})", "", "Exploratory; decides nothing.", ""]
    for name, path, pol in corpora:
        report["corpora"][name] = {}
        lines.append(f"## {name}")
        for mode in ("offsets", "quote"):
            wiki, st = E.build_wiki(path, pol, b, anchor_mode=mode)
            av = st["anchor_verification"]
            entry = {"claims": st["claims"], "verified": av["verified"], "rejected_support": av["rejected_support"],
                     "malformed": st["digest"]["malformed"], "quote_not_found": st["digest"].get("quote_not_found", 0),
                     "claims_detail": st["claims_detail"]}
            if name != "corpus":
                entry["projection_claim_text"] = _project(wiki, False)
                entry["projection_span_text"] = _project(wiki, True)
            report["corpora"][name][mode] = entry
            lines.append(f"- **{mode}**: {st['claims']} claims, {av['verified']} anchored, {av['rejected_support']} rejected for support, "
                         f"{st['digest']['malformed']} malformed, {entry['quote_not_found']} quotes not found")
            for c in st["claims_detail"]:
                lines.append(f"  - [{c['type']}, {'anchored' if c['anchored'] else 'NOT anchored'}] {c['text']}  ⟵ span: «{c['span'][:90]}»")
            if name != "corpus":
                lines.append(f"  - projection from claim text: {entry['projection_claim_text']['gamma']}")
                lines.append(f"  - projection from anchored span: {entry['projection_span_text']['gamma']}")
        lines.append("")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"diagnose_{args.model.replace(':', '_').replace('/', '_')}"
    (out / f"{stem}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (out / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
