#!/usr/bin/env python3
"""Reference for EJ4-09: valid rows in the dirty measurement CSV.

A row is valid when ``fecha``, ``estacion``, ``caudal_m3s`` and ``lluvia_mm``
are present, both numbers parse after replacing a decimal comma, the row is not
an exact duplicate of an earlier one and no cell starts with ``=`` (a
formula-looking cell is text, not a measurement). The harness never runs this
script; the card copies its counts.
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "01_MATERIALES" / "corpus_reservado" / "mediciones_estaciones_sucio.csv"


def main() -> int:
    seen: set[tuple[str, ...]] = set()
    valid = duplicates = empty = commas = formulas = 0
    with open(CSV, encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    header, data = rows[0], rows[1:]
    for row in data:
        key = tuple(row)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        if any(not cell.strip() for cell in row):
            empty += 1
            continue
        if any(cell.strip().startswith("=") for cell in row):
            formulas += 1
            continue
        try:
            float(row[2].replace(",", "."))
            float(row[3].replace(",", "."))
        except (IndexError, ValueError):
            continue
        if "," in row[2] or "," in row[3]:
            commas += 1
        valid += 1
    print(f"filas de datos: {len(data)}")
    print(f"validas: {valid}")
    print(f"duplicadas: {duplicates}")
    print(f"con celdas vacias: {empty}")
    print(f"con coma decimal: {commas}")
    print(f"con celda de formula: {formulas}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
