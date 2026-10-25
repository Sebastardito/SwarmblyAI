"""Provenance común de los benchmarks (preregistro R14, sec.1.3.3).

Cada benchmark real registra con esto: commit de git, SHA-256 del
preregistro, versión de Ollama y digests de los modelos usados. La
comprobación dura (rechazo si un modelo no coincide con el preregistrado)
la hace ``check_digests``; sin ella no hay corrida confirmatoria.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args],
                          capture_output=True, text=True).stdout.strip()


def _ollama(url: str, path: str) -> dict:
    base = url.rstrip("/").removesuffix("/v1")
    with urllib.request.urlopen(f"{base}{path}", timeout=30) as r:
        return json.loads(r.read())


def record(prereg: Path, models: list[str], url: str = "http://localhost:11434/v1",
           extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Metadatos de procedencia de una corrida."""
    info = _ollama(url, "/api/version")
    digests: dict[str, str] = {}
    try:
        tags = _ollama(url, "/api/tags")["models"]
        by_name = {t.get("name", ""): t for t in tags}
        for m in models:
            digests[m] = (by_name.get(m) or {}).get("digest", "") or "n/d"
            if m not in by_name:
                for n, t in by_name.items():
                    if n.split(":")[0] == m.split(":")[0]:
                        digests[m] = t.get("digest", "") or "n/d"
                        break
    except Exception:
        for m in models:
            digests[m] = "n/d"
    out: dict[str, Any] = {
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain", "--", "swarmbly_lce",
                               "lce_validation", "docs")),
        "prereg": str(prereg),
        "prereg_sha256": _sha(prereg),
        "ollama_version": info.get("version", "n/d"),
        "models": digests,
        "python": sys.version.split()[0],
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if extra:
        out.update(extra)
    return out


def _sha(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


MANIFEST = ROOT / "lce_validation" / "data" / "model_digests.json"


def expected_digests(path: Path = MANIFEST) -> dict[str, str]:
    """Digests preregistrados (manifiesto versionado)."""
    try:
        return dict(json.loads(path.read_text(encoding="utf-8"))["models"])
    except Exception:
        return {}


def check_digests(prov: dict, expected: dict[str, str] | None = None,
                  models: list[str] | None = None) -> list[str]:
    """Lista de problemas de digest; vacía solo si TODOS los modelos usados
    están en el manifiesto y coinciden. Un manifiesto vacío es un problema
    (antes devolvía [] y la comprobación no comprobaba nada: N3)."""
    expected = expected_digests() if expected is None else expected
    used = models if models is not None else list(prov.get("models", {}))
    if not expected:
        return ["manifiesto de digests vacío o ausente"]
    if not used:
        return ["la procedencia no registra modelos"]
    problems = []
    for m in used:
        want = expected.get(m)
        got = prov.get("models", {}).get(m)
        if want is None:
            problems.append(f"{m}: no está en el manifiesto")
        elif got is None or got == "n/d":
            problems.append(f"{m}: sin digest")
        elif got != want:
            problems.append(f"{m}: {got[:12]}… != {want[:12]}…")
    return problems
