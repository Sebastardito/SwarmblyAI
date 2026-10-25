#!/usr/bin/env python3
"""Verify that every mirror folder is exactly the commit recorded in components.lock.

A mirror is a squashed copy of a component's commit, so the folder's git tree
must equal that commit's tree. A difference means someone edited the mirror
here (changes belong in the component's own repository) or the lock is stale.

    python scripts/check_components.py            # compare with the recorded tree
    python scripts/check_components.py --fetch    # also fetch each commit and
                                                  # compare with its real tree (CI)
Exit code 0 when everything matches.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          check=True).stdout.strip()


def main() -> int:
    fetch = "--fetch" in sys.argv
    lock = json.loads((ROOT / "components.lock").read_text(encoding="utf-8"))
    bad = 0
    for name, comp in lock["components"].items():
        if comp.get("source") != "mirror":
            print(f"  {name:13} in-tree")
            continue
        folder = comp["folder"]
        try:
            here = git("rev-parse", f"HEAD:{folder}")
        except subprocess.CalledProcessError:
            print(f"✗ {name:13} folder {folder}/ is not committed")
            bad += 1
            continue
        want = comp["tree"]
        if fetch:
            git("fetch", "--quiet", "--depth", "1", comp["repository"], comp["commit"])
            want = git("rev-parse", f"{comp['commit']}^{{tree}}")
            if want != comp["tree"]:
                print(f"✗ {name:13} lock tree {comp['tree'][:12]} ≠ commit tree {want[:12]}")
                bad += 1
                continue
        dirty = git("status", "--porcelain", "--untracked-files=no", "--", folder)
        if here != want or dirty:
            print(f"✗ {name:13} {folder}/ differs from {comp['commit'][:12]}"
                  + (" (uncommitted changes)" if dirty else ""))
            bad += 1
        else:
            print(f"✓ {name:13} {comp['commit'][:12]}  ({comp.get('version', '?')})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
