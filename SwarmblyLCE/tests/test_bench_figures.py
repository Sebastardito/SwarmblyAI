"""Anclaje de las cifras publicadas (prerregistro R14 §1.3.2).

Cada cifra de ``results/BENCH_REPORT.md`` debe derivar de los JSON
guardados: la prueba regenera el reporte y exige igualdad byte a byte, y
re-ejecuta ``run_derive`` (que recalcula las cifras desde las celdas
crudas). Una deriva rompe la prueba, no la conversación.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_run_derive_recomputes_every_published_figure() -> None:
    r = subprocess.run([sys.executable, "-m", "lce_validation.run_derive"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, (
        "run_derive detectó deriva entre las cifras derivadas y las "
        "guardadas:\n" + r.stdout + r.stderr)


def test_the_benchmark_report_regenerates_byte_identical() -> None:
    import importlib
    import lce_validation.bench_report as br
    importlib.reload(br)
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "BENCH_REPORT.md"
        saved = br.OUT
        br.OUT = tmp
        try:
            assert br.main() == 0
        finally:
            br.OUT = saved
        want = (ROOT / "results" / "BENCH_REPORT.md").read_text(encoding="utf-8")
        got = tmp.read_text(encoding="utf-8")
        assert got == want, ("el reporte versionado no se regenera byte a "
                             "byte: hay una cifra editada a mano o un "
                             "generador no determinista")
