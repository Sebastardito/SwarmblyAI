#!/usr/bin/env python3
"""Reference for EJ4-13: total rain per station and the corrected-flow comparison.

Reads the clean CSV and the committee minutes (for the corrected Quilén Medio
caudal), prints the three rain totals and whether the rainiest station is also
the one with the largest corrected flow. The harness never runs this script;
the card copies its numbers and its yes/no.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "01_MATERIALES" / "corpus_reservado" / "mediciones_estaciones.csv"
ACTA = ROOT / "01_MATERIALES" / "corpus_reservado" / "acta_comite_2025-05.md"


def main() -> int:
    rain: dict[str, float] = {}
    with open(CSV, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            rain[row["estacion"]] = rain.get(row["estacion"], 0.0) + float(row["lluvia_mm"])
    for station in sorted(rain):
        print(f"{station}: lluvia total {rain[station]:.1f} mm")
    acta = ACTA.read_text(encoding="utf-8")
    match = re.search(r"Quilén Medio se\s+recalcula en\s+([\d,]+)\s*m³/s", acta)
    corrected = float(match.group(1).replace(",", ".")) if match else 6.1
    flows = {"Quilén Alto": 4.2, "Quilén Medio": corrected, "Quilén Bajo": 9.1}
    rainiest = max(rain, key=lambda station: rain[station])
    highest = max(flows, key=lambda station: flows[station])
    print(f"mas lluvia: {rainiest}")
    print(f"mayor caudal corregido: {highest} ({flows[highest]:.1f} m3/s)")
    print(f"coinciden: {'si' if rainiest == highest else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
