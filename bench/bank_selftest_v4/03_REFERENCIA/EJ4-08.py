#!/usr/bin/env python3
"""Reference for EJ4-08: sum the Quilén Medio aforos in aforos_2025.xlsx.

The data is in the second sheet (``Aforos``), not in ``Resumen``. The XLSX is
read with the standard library (zip + XML) so this script runs without
openpyxl. The harness never runs this script; the card copies its number.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
XLSX = ROOT / "01_MATERIALES" / "corpus_reservado" / "aforos_2025.xlsx"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def shared_strings(book: zipfile.ZipFile) -> list[str]:
    try:
        raw = book.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(raw)
    out = []
    for item in root.findall("m:si", NS):
        out.append("".join(node.text or "" for node in item.iter(
            "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")))
    return out


def sheet_rows(book: zipfile.ZipFile, name: str, shared: list[str]) -> list[list[str]]:
    workbook = ET.fromstring(book.read("xl/workbook.xml"))
    rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
    targets = {rel.get("Id"): rel.get("Target") for rel in rels}
    rel_id = ""
    for sheet in workbook.findall("m:sheets/m:sheet", NS):
        if sheet.get("name") == name:
            rel_id = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
    target = targets.get(rel_id, "")
    if not target:
        raise SystemExit(f"sheet {name!r} not found")
    path = target if target.startswith("xl/") else "xl/" + target.lstrip("/")
    root = ET.fromstring(book.read(path))
    rows = []
    for row in root.findall("m:sheetData/m:row", NS):
        cells = {}
        for cell in row.findall("m:c", NS):
            ref = cell.get("r") or ""
            column = re.match(r"[A-Z]+", ref).group(0) if ref else ""
            kind = cell.get("t")
            if kind == "inlineStr":
                value = "".join(node.text or "" for node in cell.iter(
                    "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"))
            else:
                node = cell.find("m:v", NS)
                value = node.text if node is not None and node.text else ""
                if kind == "s" and value:
                    value = shared[int(value)]
            cells[column] = value
        ordered = [cells[key] for key in sorted(cells, key=lambda x: (len(x), x))]
        rows.append(ordered)
    return rows


def main() -> int:
    with zipfile.ZipFile(XLSX) as book:
        shared = shared_strings(book)
        rows = sheet_rows(book, "Aforos", shared)
    header = rows[0]
    station_col = header.index("estacion")
    flow_col = header.index("caudal_m3s")
    total = 0.0
    count = 0
    for row in rows[1:]:
        if len(row) <= max(station_col, flow_col):
            continue
        if row[station_col].strip() != "Quilén Medio":
            continue
        total += float(row[flow_col].replace(",", "."))
        count += 1
    print(f"Quilen Medio: {count} aforos, suma {total:.4f} m3/s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
