"""Every tracked path must be valid on Windows (pip installs from a git clone)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from lce_validation.fsnames import cache_file, model_token, split_cache_name

ROOT = Path(__file__).resolve().parent.parent
_INVALID = re.compile(r'[<>:"|?*\x00-\x1f]|[. ]$')
_RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?$", re.I)


def test_no_tracked_path_is_invalid_on_windows():
    try:
        names = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                               text=True, check=True).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    bad = [n for n in names
           if any(_INVALID.search(part) or _RESERVED.match(part) for part in n.split("/"))]
    assert bad == [], f"paths invalid on Windows: {bad[:5]}"


def test_model_token_roundtrip():
    assert model_token("gemma2:2b") == "gemma2%3A2b"
    assert split_cache_name("mara__gemma2%3A2b_wiki.json", "_wiki.json") == ("mara", "gemma2:2b")
    assert split_cache_name("mara__granite3.1-dense%3A2b__full.json", "__full.json") == \
        ("mara", "granite3.1-dense:2b")


def test_reader_prefers_portable_and_falls_back_to_legacy(tmp_path, monkeypatch):
    monkeypatch.setattr("os.name", "posix")
    legacy = tmp_path / "mara__qwen2.5:3b_wiki.json"
    legacy.write_text("{}")
    assert cache_file(tmp_path, "mara", "qwen2.5:3b", "_wiki.json") == legacy
    portable = tmp_path / "mara__qwen2.5%3A3b_wiki.json"
    portable.write_text("{}")
    assert cache_file(tmp_path, "mara", "qwen2.5:3b", "_wiki.json") == portable


def test_confirmatory_wikis_are_found_under_portable_names():
    cache = ROOT / "results" / "bench_r13_confirm" / "wikis_cache"
    if not cache.exists():
        pytest.skip("results not present")
    path = cache_file(cache, "mara", "qwen2.5:3b", "_wiki.json")
    assert path.exists() and ":" not in path.name
