#!/usr/bin/env python3
"""If this script were executed, it would leave a marker file.

The harness checks that importing the skill never runs it: the marker must not
appear anywhere in the project, the app data folder or the skill copy.
"""

from pathlib import Path

for folder in (Path.cwd(), Path(__file__).resolve().parents[1]):
    try:
        (folder / "MARCADOR_SKILL.txt").write_text(
            "el script de la skill se ejecutó\n", encoding="utf-8")
    except OSError:
        pass
