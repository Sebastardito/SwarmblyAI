"""Run C1 and C2 against real models through an OpenAI-compatible endpoint (e.g. Ollama).

Confirmatory run (the one PREREGISTRATION_C1_C2 describes):

    python -m lce_validation.fetch_mcq                       # once, then commit the data file
    python -m lce_validation.run_real \\
        --models qwen2.5:3b,llama3.2:3b,gemma2:2b --embed-model nomic-embed-text \\
        --prereg docs/PREREGISTRATION_C1_C2_EN.md

The first model digests the corpus and writes; all models are replicas of
different families for the error-agreement metric. A run is labelled
**confirmatory** only if the pre-registration and the MCQ item file exist and
are committed, the code tree is clean, an embedding model is given and at least
three families respond. Otherwise it runs as **exploratory** and ``decide``
reports no verdicts. Outputs: ``results_real.json`` (with raw answers),
``REPORT_REAL.md`` and the verdicts of ``lce_validation.decide``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import urllib.request
from pathlib import Path

from swarmbly_lce.backends import BackendUnavailable, OpenAICompatBackend
from swarmbly_lce.report import run_header

from . import experiments as E
from .decide import decide

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MCQ = E.DATA / "mmlu_test_1500.json"
# Directories that must be clean for a confirmatory run, and the run's own outputs inside them.
GUARDED = ("swarmbly_lce", "lce_validation", "docs")
OWN_OUTPUTS = ("results_real.json", "REPORT_REAL.md", "run_real.log")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def _committed_and_clean(paths: list[Path]) -> tuple[bool, list[str]]:
    problems = []
    if not _git("rev-parse", "HEAD"):
        return False, ["not a git checkout"]
    for p in paths:
        rel = str(p.resolve().relative_to(ROOT)) if p.resolve().is_relative_to(ROOT) else str(p)
        if not _git("ls-files", rel):
            problems.append(f"{rel} is not committed")
    dirty = [l[3:] for l in _git("status", "--porcelain", "--", *GUARDED).splitlines() if not l.endswith(OWN_OUTPUTS)]
    if dirty:
        problems.append("uncommitted changes in swarmbly_lce/, lce_validation/ or docs/: " + ", ".join(dirty))
    return not problems, problems


def _ollama_info(url: str) -> dict:
    root = url.rstrip("/").removesuffix("/v1")
    info: dict = {}
    for key, path in (("version", "/api/version"), ("tags", "/api/tags")):
        try:
            with urllib.request.urlopen(root + path, timeout=10) as r:
                info[key] = json.loads(r.read().decode("utf-8"))
        except Exception as exc:
            info[key] = f"unavailable: {exc}"
    if isinstance(info.get("tags"), dict):
        info["models"] = {m.get("name"): m.get("digest") for m in info["tags"].get("models", [])}
        info.pop("tags")
    return info


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default="http://localhost:11434/v1")
    ap.add_argument("--models", required=True, help="comma-separated; at least two families (three for a confirmatory run)")
    ap.add_argument("--embed-model", default="")
    ap.add_argument("--mcq", default=str(DEFAULT_MCQ))
    ap.add_argument("--prereg", default="", help="path to the committed pre-registration (required for a confirmatory run)")
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--anchor-mode", choices=["offsets", "quote"], default="offsets",
                    help="how the digester anchors claims (amendment 2 fixes the value for run 2)")
    ap.add_argument("--span-projection", action="store_true",
                    help="read lexicon/register from the user's anchored words (amendment 2)")
    ap.add_argument("--reconcile-types", action="store_true",
                    help="reconcile proposed claim types with first-person cues in the anchored span (amendment 3)")
    ap.add_argument("--preflight", action="store_true",
                    help="stop before generating outcomes if the projection fails the manipulation check (amendment 3)")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent))
    args = ap.parse_args(argv)

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if len(models) < 2:
        ap.error("at least two models of different families are required")
    mcq = Path(args.mcq)
    if not mcq.exists():
        print(f"MCQ item file {mcq} not found. Draw it once with `python -m lce_validation.fetch_mcq` and commit it.", file=sys.stderr)
        return 2
    backends = [OpenAICompatBackend(model=m, base_url=args.url, embed_model=args.embed_model) for m in models]
    for b in backends:
        try:
            b.generate("Reply with OK.", max_tokens=4)
        except BackendUnavailable as exc:
            print(f"model {b.model} unreachable: {exc}", file=sys.stderr)
            return 2
    if args.embed_model:
        try:
            backends[0].embed(["probe"])
        except BackendUnavailable as exc:
            print(f"embedding model {args.embed_model} unreachable: {exc}", file=sys.stderr)
            return 2
    families = {b.family for b in backends}
    if len(families) < 2:
        print("all models resolve to one family; the error-agreement metric needs distinct families", file=sys.stderr)
        return 2

    prereg = Path(args.prereg) if args.prereg else None
    guarded = [mcq] + ([prereg] if prereg else [])
    clean, problems = _committed_and_clean(guarded)
    if prereg is None or not prereg.exists():
        problems.append("no pre-registration given")
    confirmatory = bool(prereg and prereg.exists() and clean and args.embed_model and len(families) >= 3)
    print(f"run type: {'CONFIRMATORY' if confirmatory else 'EXPLORATORY'}" + ("" if confirmatory else f" ({'; '.join(problems) or 'see header'})"))

    header = run_header("real", ",".join(models), url=args.url, embed_model=args.embed_model or "hash-fallback",
                        confirmatory=confirmatory, problems=problems, distinct_families=len(families),
                        prereg=str(prereg) if prereg else "", prereg_sha256=_sha(prereg) if prereg and prereg.exists() else "",
                        mcq_file=str(mcq), mcq_sha256=_sha(mcq), git_commit=_git("rev-parse", "HEAD"),
                        platform=platform.platform(), machine=platform.machine(), ollama=_ollama_info(args.url),
                        temperature=args.temperature, anchor_mode=args.anchor_mode, span_projection=args.span_projection,
                        reconcile_types=args.reconcile_types, preflight=args.preflight)
    lead = backends[0]
    wiki, wstats = E.build_wiki(E.FIXTURES / "corpus", E.FIXTURES / "policy.json", lead, anchor_mode=args.anchor_mode,
                                reconcile_types=args.reconcile_types)
    try:
        c2 = E.c2_projection(backends, lead, mcq_path=mcq, temperature=args.temperature,
                             anchor_mode=args.anchor_mode, span_projection=args.span_projection,
                             reconcile_types=args.reconcile_types, preflight=args.preflight)
    except E.ManipulationCheckFailed as exc:
        out = Path(args.out)
        stopped = {"header": header, "build_wiki": wstats, "C2": {"preflight_failed": True, **exc.stats}}
        stopped["verdicts"] = decide(stopped)
        (out / "results_real.json").write_text(json.dumps(stopped, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
        print(f"STOPPED BEFORE ANY OUTCOME: {exc}. Nothing was measured; see results_real.json.", file=sys.stderr)
        return 3
    results = {
        "header": header,
        "build_wiki": wstats,
        "C1": E.c1_memory(lead, wiki),
        "C2": c2,
        "canary": E.canary_check(lead, wiki),
        "scope": ("fixture corpus (1 synthetic user) for C1; 3 synthetic users x 20 topics for H-C2/H-C17a; "
                  f"{results_items(mcq)} MMLU items x {len(families)} families for H-C17b; canary unverified (descriptive only)"),
    }
    results["verdicts"] = decide(results)
    out = Path(args.out)
    (out / "results_real.json").write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    v = results["verdicts"]
    lines = ["# lce_validation — real-model run", "",
             f"**Run type: {'confirmatory' if confirmatory else 'exploratory'}.** Models: {', '.join(models)} · {header['utc']} · commit {header['git_commit'][:10]}",
             "", f"Pre-registration sha256 `{header['prereg_sha256'][:16]}…` · MCQ sha256 `{header['mcq_sha256'][:16]}…`", "",
             f"Scope: {results['scope']}.", "",
             f"- Wiki: {wstats['claims']} claims; anchor rejection rate {wstats['anchor_verification']['rejection_rate']:.2f}; "
             f"malformed digester outputs {wstats['digest']['malformed']}.",
             f"- C1 (positive control): accuracy with memory {results['C1']['acc_with_memory']:.2f} vs without {results['C1']['acc_without_memory']:.2f}.",
             *E.format_c2(results["C2"]),
             f"- Canary (unverified, descriptive only): tail mass {results['canary']['tail_mass']:.2f}; identity violations {results['canary']['identity_violation_rate']:.2f}.",
             "", "## Verdicts (lce_validation.decide)", ""]
    for k, r in v.items():
        if isinstance(r, dict) and "verdict" in r:
            lines.append(f"- **{k}: {r['verdict']}** — {r['reason']}" + (f" ({r['qualification']})" if r.get("qualification") else ""))
    if v.get("global_refusals"):
        lines.append(f"- Global refusals: {'; '.join(v['global_refusals'])}")
    lines.append(f"- Replication of Kim et al. (2025), descriptive: {v['replication_Kim2025']['statement']}.")
    lines.append("")
    (out / "REPORT_REAL.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


def results_items(mcq: Path) -> int:
    try:
        return len(json.loads(mcq.read_text(encoding="utf-8"))["items"])
    except Exception:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
