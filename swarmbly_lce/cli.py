"""Command-line interface: ``swarmbly-lce``.

    swarmbly-lce init DIR                       create DIR/.lce with a conservative policy
    swarmbly-lce ingest --sources DIR [--backend mock|ollama --model M]
    swarmbly-lce cycle                          run one consolidation cycle
    swarmbly-lce status                         maturity counts, stale nodes, trainable claims
    swarmbly-lce project "request text"         Task Projection → Γ fields and lanes
    swarmbly-lce forget SOURCE                  remove a source and its claims
    swarmbly-lce export-md OUT_DIR              human-readable pages
    swarmbly-lce replicas [--eps E] [--t-host D] [--window D]
    swarmbly-lce capsule keygen KEYFILE | make ... | verify FILE
    swarmbly-lce validate [--out DIR]           run the instrument harness
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .anchors import AnchorVerifier, ModelSupport
from .backends import get_backend
from .canonical import text_digest
from .persistence import annual_loss, replicas_for, window_loss_q
from .policy import LearningPolicy
from .projection import Projector
from .sources import SourceSpace
from .wiki import Wiki

DEFAULT_POLICY = {
    "learning_policy": {
        "v": "0.1",
        "defaults": {"reference_only": True},
        "sources": {
            "teach/style": {"authored_by_user": True, "learn_style": True, "learn_preference": True},
            "teach/procedures": {"authored_by_user": True, "learn_procedure": True},
            "teach/knowledge": {"authored_by_user": False, "wiki": True},
            "reference_only": {"wiki": True, "train": False},
        },
    }
}


def _state(args: argparse.Namespace) -> tuple[Path, Path]:
    home = Path(args.home)
    return home / "policy.json", home / "wiki.json"


def _load(args: argparse.Namespace) -> Wiki:
    pol_path, wiki_path = _state(args)
    policy = LearningPolicy.load(pol_path) if pol_path.exists() else LearningPolicy.from_mapping(DEFAULT_POLICY)
    return Wiki.load(wiki_path, policy=policy) if wiki_path.exists() else Wiki(policy=policy)


def _backend(args: argparse.Namespace):
    if args.backend == "mock":
        return get_backend("mock")
    return get_backend("ollama", model=args.model, base_url=args.url)


def cmd_init(args: argparse.Namespace) -> int:
    home = Path(args.dir) / ".lce"
    home.mkdir(parents=True, exist_ok=True)
    pol = home / "policy.json"
    if not pol.exists():
        pol.write_text(json.dumps(DEFAULT_POLICY, indent=2) + "\n", encoding="utf-8")
    for sub in ("teach/style", "teach/procedures", "teach/knowledge", "reference_only"):
        (Path(args.dir) / sub).mkdir(parents=True, exist_ok=True)
    print(f"initialised {home} (policy: what is not declared does not train)")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    from .digest import Digester

    wiki = _load(args)
    space = SourceSpace(args.sources)
    backend = _backend(args)
    support = ModelSupport(get_backend("ollama", model=args.verifier_model, base_url=args.url)) if args.verifier_model else None
    verifier = AnchorVerifier(space, support) if support else AnchorVerifier(space)
    dig = Digester(backend, space, verifier)
    claims = dig.digest_all(wiki)
    wiki.save(_state(args)[1])
    print(json.dumps({"added": len(claims), "digest": dig.stats.__dict__, "anchors": verifier.stats.__dict__}, indent=1))
    return 0


def cmd_cycle(args: argparse.Namespace) -> int:
    wiki = _load(args)
    rep = wiki.consolidation_cycle()
    wiki.save(_state(args)[1])
    print(json.dumps({"cycle": wiki.cycle, "advanced": rep.advanced, "blocked": len(rep.blocked), "stale": sorted(rep.stale)}, indent=1, ensure_ascii=False))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    wiki = _load(args)
    counts: dict[str, int] = {}
    for c in wiki.claims.values():
        counts[c.maturity.value] = counts.get(c.maturity.value, 0) + 1
    print(json.dumps({"claims": len(wiki.claims), "maturity": counts, "trainable": len(wiki.trainable()),
                      "stale": len(wiki.graph.stale), "cycle": wiki.cycle}, indent=1))
    return 0


def cmd_project(args: argparse.Namespace) -> int:
    wiki = _load(args)
    res = Projector().project(args.request, list(wiki.claims.values()))
    print(json.dumps({"gamma": res.projection.gamma_fields(), "bytes": res.projection.size_bytes(),
                      "lane_initial": res.lane_initial.name, "lane_final": res.lane_final.name,
                      "local_only": res.local_only}, indent=1, ensure_ascii=False))
    return 0


def cmd_forget(args: argparse.Namespace) -> int:
    wiki = _load(args)
    stale = wiki.forget_source(args.source)
    wiki.save(_state(args)[1])
    print(json.dumps({"forgotten": args.source, "stale": sorted(stale),
                      "note": "adapters trained on these examples must be regenerated (SPEC 7.8)"}, indent=1))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    for p in _load(args).export_markdown(args.out):
        print(p)
    return 0


def cmd_replicas(args: argparse.Namespace) -> int:
    q = window_loss_q(args.t_host, args.window)
    r = replicas_for(args.eps, q)
    print(json.dumps({"q": q, "r": r, "annual_loss": {k: annual_loss(k, q, 365.0 / args.window) for k in (1, 2, 3, 4, 5)}}, indent=1))
    return 0


def cmd_capsule(args: argparse.Namespace) -> int:
    from .capsules import Capsule, make_capsule
    from .crypto import generate_keypair, keypair_from_seed, b64u, unb64u

    if args.op == "keygen":
        kp = generate_keypair()
        Path(args.path).write_text(json.dumps({"public": kp.public, "seed": b64u(kp.private_bytes)}) + "\n", encoding="utf-8")
        Path(args.path).chmod(0o600)
        print(kp.public)
        return 0
    if args.op == "make":
        key = json.loads(Path(args.key).read_text())
        kp = keypair_from_seed(unb64u(key["seed"]))
        c = make_capsule(kp, kind=args.kind, topics=args.topics.split(","), statement=args.statement,
                         anchor_kind=args.anchor_kind, anchor_digest=text_digest(args.anchor_text),
                         permissions={"cache": args.cache, "redistribute": args.redistribute, "train": args.train},
                         preserve=args.preserve)
        Path(args.path).write_text(c.to_json() + "\n", encoding="utf-8")
        print(c.capsule_id)
        return 0
    if args.op == "verify":
        c = Capsule.from_dict(json.loads(Path(args.path).read_text()))
        c.validate()
        c.verify_signature()
        print(json.dumps({"capsule_id": c.capsule_id, "valid": True, "epistemic_distance": c.epistemic_distance}, indent=1))
        return 0
    return 2


def cmd_validate(args: argparse.Namespace) -> int:
    from lce_validation.run_all import main as run_all

    return run_all(["--out", args.out] if args.out else [])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="swarmbly-lce", description="Swarmbly Local Cognitive Extension")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--home", default=".lce", help="state directory (policy.json, wiki.json)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init"); s.add_argument("dir"); s.set_defaults(fn=cmd_init)
    s = sub.add_parser("ingest"); s.add_argument("--sources", required=True)
    s.add_argument("--backend", choices=["mock", "ollama"], default="mock"); s.add_argument("--model", default="qwen2.5:3b")
    s.add_argument("--url", default="http://localhost:11434/v1"); s.add_argument("--verifier-model", default="")
    s.set_defaults(fn=cmd_ingest)
    s = sub.add_parser("cycle"); s.set_defaults(fn=cmd_cycle)
    s = sub.add_parser("status"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("project"); s.add_argument("request"); s.set_defaults(fn=cmd_project)
    s = sub.add_parser("forget"); s.add_argument("source"); s.set_defaults(fn=cmd_forget)
    s = sub.add_parser("export-md"); s.add_argument("out"); s.set_defaults(fn=cmd_export)
    s = sub.add_parser("replicas"); s.add_argument("--eps", type=float, default=1e-3)
    s.add_argument("--t-host", type=float, default=91.0); s.add_argument("--window", type=float, default=7.0); s.set_defaults(fn=cmd_replicas)
    s = sub.add_parser("capsule"); s.add_argument("op", choices=["keygen", "make", "verify"]); s.add_argument("path")
    s.add_argument("--key"); s.add_argument("--kind", default="term"); s.add_argument("--topics", default="")
    s.add_argument("--statement", default=""); s.add_argument("--anchor-kind", default="user_source"); s.add_argument("--anchor-text", default="")
    s.add_argument("--cache", action="store_true"); s.add_argument("--redistribute", action="store_true")
    s.add_argument("--train", action="store_true"); s.add_argument("--preserve", action="store_true"); s.set_defaults(fn=cmd_capsule)
    s = sub.add_parser("validate"); s.add_argument("--out", default=""); s.set_defaults(fn=cmd_validate)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.fn(args) or 0)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
