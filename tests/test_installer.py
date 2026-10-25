"""Installer helpers and the mirror check (run from the repository root: python -m pytest tests)."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("install", ROOT / "installer" / "install.py")
install = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install)


def test_models_fit_the_memory():
    assert install.plan_models(32)[0][0] == "qwen2.5:7b"
    assert install.plan_models(16)[0][0] == "qwen2.5:3b"
    assert install.plan_models(6)[0][0] == "qwen2.5:1.5b"
    assert install.plan_models(16)[1][0] == "nomic-embed-text"
    assert len(install.plan_models(16, extra=True)) == 3


def test_app_dependencies_exclude_swarmbly_pins():
    deps = install._app_dependencies()
    assert deps and not any(d.lower().startswith("swarmbly") for d in deps)
    assert any(d.startswith("fastapi") for d in deps)


def test_both_languages_have_the_same_messages():
    assert set(install.T["es"]) == set(install.T["en"])


def test_dry_run_changes_nothing(tmp_path):
    out = subprocess.run([sys.executable, str(ROOT / "installer" / "install.py"), "--quick", "--yes",
                          "--dry-run", "--lang", "en", "--venv", str(tmp_path / "venv"),
                          "--skip", "ollama,models,pdf,searxng,shortcuts"],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "[dry run]" in out.stdout and not (tmp_path / "venv").exists()


def test_mirrors_match_the_lock():
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_components.py")],
                         capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stdout
