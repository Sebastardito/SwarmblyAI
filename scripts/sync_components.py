#!/usr/bin/env python3
"""Update a mirror (SwarmblyLCE, SwarmblyApp, …) to a tag or commit of its repository.

    python scripts/sync_components.py SwarmblyApp v0.3.0
    python scripts/sync_components.py SwarmblyLCE main          # edge branch
    python scripts/sync_components.py --all                     # every mirror to its "ref"
    python scripts/sync_components.py SwarmblyApp v0.3.0 --repo ../SwarmblyApp   # local clone

Runs `git subtree pull --squash` into the component's folder, then records the
commit, its tree and the package version in components.lock and commits it.
Rules: the main branch takes tags only (releases); the edge branch may follow
the components' main branches. Never edit a mirror folder by hand.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "components.lock"


def git(*args: str, check: bool = True) -> str:
    proc = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if check and proc.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{proc.stderr.strip()}")
    return proc.stdout.strip()


def version_of(folder: Path) -> str:
    text = (folder / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    return m.group(1) if m else "?"


def sync(lock: dict, name: str, ref: str, repo: str | None) -> None:
    comp = lock["components"].get(name)
    if not comp or comp.get("source") != "mirror":
        sys.exit(f"{name} is not a mirror in components.lock")
    if git("status", "--porcelain", "--untracked-files=no"):
        sys.exit("the working tree has uncommitted changes; commit or stash them first")
    source = repo or comp["repository"]
    git("fetch", "--quiet", source, ref)
    commit = git("rev-parse", "FETCH_HEAD")
    if commit == comp.get("commit"):
        print(f"{name}: already at {commit[:12]}")
        return
    git("subtree", "pull", "--squash", f"--prefix={comp['folder']}", source, ref,
        "-m", f"Sync {name} to {ref} ({commit[:12]})")
    tree = git("rev-parse", f"HEAD:{comp['folder']}")
    comp.update(ref=ref, commit=commit, tree=tree, version=version_of(ROOT / comp["folder"]))
    LOCK.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    git("add", "components.lock")
    git("commit", "-q", "-s", "-m", f"components.lock: {name} {comp['version']} at {commit[:12]}")
    print(f"{name}: {ref} → {commit[:12]} (version {comp['version']})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("component", nargs="?")
    ap.add_argument("ref", nargs="?", help="tag (releases) or branch (edge)")
    ap.add_argument("--repo", help="fetch from this URL or local clone instead of the lock's repository")
    ap.add_argument("--all", action="store_true", help="every mirror to the ref in the lock")
    a = ap.parse_args()
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    if a.all:
        for name, comp in lock["components"].items():
            if comp.get("source") == "mirror":
                sync(lock, name, comp.get("ref", "main"), None)
        return 0
    if not a.component or not a.ref:
        ap.error("give a component and a ref, or --all")
    sync(lock, a.component, a.ref, a.repo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
