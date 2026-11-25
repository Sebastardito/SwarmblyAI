"""Shared helpers for the live bench tests.

The App under test is installed in the repository's ``.venv``.  Depending on
how Python processes ``.pth`` files, the editable install may not be on
``sys.path``; the App source folder is added explicitly so a live test skips
only when the App really cannot be imported.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
APP_SRC = ROOT / ".venv" / "app-src"


def app_environment() -> dict[str, str]:
    env = dict(os.environ)
    parts = []
    if APP_SRC.is_dir():
        parts.append(str(APP_SRC))
    if env.get("PYTHONPATH"):
        parts.append(env["PYTHONPATH"])
    if parts:
        env["PYTHONPATH"] = os.pathsep.join(parts)
    return env


def app_importable() -> bool:
    """Whether the installed App can be imported by its interpreter."""
    if not VENV_PYTHON.is_file():
        return False
    try:
        done = subprocess.run(
            [str(VENV_PYTHON), "-c", "import swarmbly_app"],
            env=app_environment(), stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0


def require_app_python(monkeypatch) -> str:
    """Return the venv Python or skip; export its PYTHONPATH to the children."""
    if not app_importable():
        import pytest
        pytest.skip("the installed App is not importable in this clone")
    env = app_environment()
    monkeypatch.setenv("PYTHONPATH", env.get("PYTHONPATH", ""))
    return str(VENV_PYTHON)
