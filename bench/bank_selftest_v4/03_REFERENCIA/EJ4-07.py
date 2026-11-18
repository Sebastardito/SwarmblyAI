#!/usr/bin/env python3
"""Reference for EJ4-07: mean and sample standard deviation of each station.

Reads ``01_MATERIALES/corpus_reservado/mediciones_estaciones.csv`` and prints
one line per station plus the station with the largest sample deviation. The
harness never runs this script; the card copies its numbers.
"""

from __future__ import annotations

import csv
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "01_MATERIALES" / "corpus_reservado" / "mediciones_estaciones.csv"


def main() -> int:
    values: dict[str, list[float]] = {}
    with open(CSV, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            values.setdefault(row["estacion"], []).append(float(row["caudal_m3s"]))
    ordered = sorted(values)
    means = {station: statistics.mean(values[station]) for station in ordered}
    deviations = {station: statistics.stdev(values[station]) for station in ordered}
    for station in ordered:
        print(f"{station}: media {means[station]:.4f} m3/s, "
              f"desviacion tipica {deviations[station]:.4f}")
    most = max(ordered, key=lambda station: deviations[station])
    print(f"mayor variacion: {most}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
