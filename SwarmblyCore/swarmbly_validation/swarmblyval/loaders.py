"""Real-data loaders. Replaces golden fixtures with the project's own artefacts.

Every loader REFUSES rather than guesses: if the artefact is missing, has the
wrong shape, or does not reproduce the figure the documents claim, it raises
``DataRefusal`` with the reason. That is the project's instrument discipline
applied to the harness's own inputs (WHITEPAPER_V2 §9, §15.7).

The repository root is located once, from ``SWARMBLY_REPO`` or by walking up
from this file looking for ``prompts/`` and ``results/``.
"""

import csv
import json
import os
import re

__all__ = [
    "DataRefusal", "repo_root", "have_repo", "bench_path",
    "load_tables24", "load_tax_16", "load_lcurve_prompts", "load_lcurve_rows",
]


class DataRefusal(Exception):
    """Raised when an input is missing or does not match its declared shape."""


# --- locating the repository --------------------------------------------------

_HARNESS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_CANDIDATES = (
    os.environ.get("SWARMBLY_REPO"),
    # el arnés vive DENTRO del repositorio: la raíz es su directorio padre
    os.path.dirname(_HARNESS),
    os.path.join(_HARNESS, "repo"),
    os.path.join(_HARNESS, "..", "Swarmbly-AI_Clean"),
)


def repo_root():
    for cand in _CANDIDATES:
        if not cand:
            continue
        cand = os.path.abspath(cand)
        if os.path.isdir(os.path.join(cand, "prompts")) and \
           os.path.isdir(os.path.join(cand, "results")):
            return cand
    raise DataRefusal(
        "repository not found: set SWARMBLY_REPO to the Swarmbly-AI_Clean checkout "
        "(needs prompts/ and results/)"
    )


def have_repo():
    try:
        repo_root()
        return True
    except DataRefusal:
        return False


def bench_path():
    """Ruta del corpus de referencia `benchmark.jsonl`, o None.

    Un solo resolutor para todo el arnés: antes había tres copias de esta
    búsqueda en tres tests, y la que tenía la ruta mal cargaba cero registros
    sin distinguirse de «no hay datos».
    """
    here = os.path.join("swarmbly_ref", "data", "benchmark.jsonl")
    for cand in (os.environ.get("SWARMBLY_BENCH"),
                 os.path.join(_HARNESS, here),
                 os.path.join(os.path.dirname(_HARNESS), here),
                 os.path.join(_HARNESS, "refbench", here)):
        if cand and os.path.exists(cand):
            return os.path.abspath(cand)
    return None


# --- tables24: the 16 held-out prompts ---------------------------------------

def load_tables24():
    """The frozen 24-prompt table corpus, with its declared dev/final split.

    Refuses if the frozen split is absent — without it there is no held-out
    half and any figure computed here would be an in-sample figure.
    """
    path = os.path.join(repo_root(), "prompts", "tables24.json")
    if not os.path.exists(path):
        raise DataRefusal(f"missing {path}")
    d = json.load(open(path))
    frozen = d.get("_frozen") or {}
    if "final" not in frozen or "dev" not in frozen:
        raise DataRefusal("tables24.json has no _frozen dev/final split: refuse")
    by_id = {p["id"]: p for p in d["prompts"]}
    missing = [i for i in frozen["final"] if i not in by_id]
    if missing:
        raise DataRefusal(f"prompts named in _frozen.final are absent: {missing}")
    return {
        "all": by_id,
        "dev": list(frozen["dev"]),
        "final": list(frozen["final"]),
        "sha256": frozen.get("sha256"),
    }


# --- the coherence-tax measurement -------------------------------------------

#: The cell the abandonment criterion was judged on (WHITEPAPER_V2 §15.3).
TAX_CELL = {"condition": "fragmented", "rho_target": "3.5", "n_tasks": "2", "k": "1"}

#: What the documents say this cell contains. The loader cross-checks and
#: refuses on mismatch, so a changed artefact cannot silently move a figure.
TAX_EXPECTED = {"n": 16, "mean": 2.30, "median": 0.00, "at_or_below_zero": 11,
                "expensive": {"tbl24_outturn": 28.50, "tbl24_bonded": 23.08}}


def load_tax_16(run_dir=None, tol=0.02):
    """Per-prompt coherence tax for the 16 held-out prompts, from results.csv.

    Returns ``{prompt_id: tax_percent}``. Refuses if the cell does not have
    exactly 16 prompts, or if the reconstructed mean/median/expensive prompts
    disagree with what the documents state by more than ``tol`` points.
    """
    root = repo_root()
    if run_dir is None:
        runs = sorted(d for d in os.listdir(os.path.join(root, "results"))
                      if d.startswith("tables-final-"))
        if not runs:
            raise DataRefusal("no results/tables-final-* run found")
        run_dir = runs[-1]
    path = os.path.join(root, "results", run_dir, "results.csv")
    if not os.path.exists(path):
        raise DataRefusal(f"missing {path}")

    rows = list(csv.DictReader(open(path)))
    sel = [r for r in rows if all(r.get(k) == v for k, v in TAX_CELL.items())]
    if len(sel) != TAX_EXPECTED["n"]:
        raise DataRefusal(
            f"cell {TAX_CELL} has {len(sel)} rows, expected {TAX_EXPECTED['n']}: refuse"
        )

    tax = {}
    for r in sel:
        raw = r.get("coherence_tax_booook", "")
        if raw in ("", "None", None):
            raise DataRefusal(f"{r['prompt_id']} has no coherence_tax_booook: refuse")
        tax[r["prompt_id"]] = float(raw) * 100.0

    _crosscheck_tax(tax, tol)
    return tax, run_dir


def load_tax_cell(n_tasks, k="1", rho="3.5", condition="fragmented",
                  run_prefix="tables-final-", run_dir=None):
    """Per-prompt coherence tax for an arbitrary cell. No cross-check.

    Used by the paired analysis, which needs the N=8 cell alongside N=2.
    Refuses if the cell is empty rather than returning a silent {}.
    """
    root = repo_root()
    if run_dir is None:
        runs = sorted(d for d in os.listdir(os.path.join(root, "results"))
                      if d.startswith(run_prefix))
        if not runs:
            raise DataRefusal(f"no results/{run_prefix}* run found")
        run_dir = runs[-1]
    path = os.path.join(root, "results", run_dir, "results.csv")
    if not os.path.exists(path):
        raise DataRefusal(f"missing {path}")
    want = {"condition": condition, "rho_target": rho,
            "n_tasks": str(n_tasks), "k": str(k)}
    out = {}
    for r in csv.DictReader(open(path)):
        if all(r.get(key) == val for key, val in want.items()):
            raw = r.get("coherence_tax_booook", "")
            if raw not in ("", "None", None):
                out[r["prompt_id"]] = float(raw) * 100.0
    if not out:
        raise DataRefusal(f"cell {want} is empty in {run_dir}: refuse")
    return out, run_dir


def _crosscheck_tax(tax, tol):
    xs = sorted(tax.values())
    n = len(xs)
    mean = sum(xs) / n
    med = xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2
    below = sum(1 for x in xs if x <= 0)
    if abs(mean - TAX_EXPECTED["mean"]) > tol:
        raise DataRefusal(
            f"reconstructed mean {mean:.4f} != documented {TAX_EXPECTED['mean']} "
            f"(tol {tol}): the artefact and the documents disagree"
        )
    if abs(med - TAX_EXPECTED["median"]) > tol:
        raise DataRefusal(f"reconstructed median {med:.4f} != documented "
                          f"{TAX_EXPECTED['median']}")
    if below != TAX_EXPECTED["at_or_below_zero"]:
        raise DataRefusal(f"{below} prompts at/below zero != documented "
                          f"{TAX_EXPECTED['at_or_below_zero']}")
    for pid, val in TAX_EXPECTED["expensive"].items():
        if pid not in tax:
            raise DataRefusal(f"documented expensive prompt {pid} absent from the cell")
        if abs(tax[pid] - val) > tol:
            raise DataRefusal(f"{pid} tax {tax[pid]:.2f} != documented {val}")


# --- the L-curve corpus and its run ------------------------------------------

def load_lcurve_prompts():
    path = os.path.join(repo_root(), "prompts", "lcurve.json")
    if not os.path.exists(path):
        raise DataRefusal(f"missing {path}")
    d = json.load(open(path))
    return d["prompts"], {k: v for k, v in d.items() if k != "prompts"}


def load_lcurve_rows(run_dir=None):
    root = repo_root()
    if run_dir is None:
        runs = sorted(d for d in os.listdir(os.path.join(root, "results"))
                      if d.startswith("lcurve-dev-"))
        if not runs:
            raise DataRefusal("no results/lcurve-dev-* run found")
        run_dir = runs[-1]
    path = os.path.join(root, "results", run_dir, "rows.json")
    if not os.path.exists(path):
        raise DataRefusal(f"missing {path}")
    return json.load(open(path)), run_dir


# --- the real segmenter -------------------------------------------------------

def real_segmenter():
    """Import the project's own ``_segment``. Refuses if it cannot be loaded.

    The cut has to be the cut the run actually made, not a reimplementation of
    it: a delta computed against a different partition measures nothing.
    """
    import sys
    root = repo_root()
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from swarmbly_v0.planner import _segment  # noqa: E402
    except Exception as exc:  # pragma: no cover - environment dependent
        raise DataRefusal(
            f"cannot import swarmbly_v0.planner._segment ({exc}); "
            "delta must be computed against the real partition, not a copy"
        )
    return _segment


# --- table parsing ------------------------------------------------------------

_ROW_RE = re.compile(r"^\s*([A-Z]\d{4})\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*kg\s*\|\s*(.+?)\s*$")


def parse_table_rows(prompt):
    """Rows of an enclosed table prompt as ``(ref, destination, kg, goods)``."""
    out = []
    for line in prompt.split("\n"):
        m = _ROW_RE.match(line)
        if m:
            out.append((m.group(1), m.group(2).strip(),
                        int(m.group(3)), m.group(4).strip()))
    return out
