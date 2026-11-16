"""Recipe 2 (3.3): compare documents into a table built by code.

In the sealed banks the compositions that ask for a table are still annulled
for serious errors: an invented row, a wrong value (3.2 measurement). In the
open battery the lexical scaffolding of 3.2 invented a lot's rows when its
facts were not chosen. A table written freely by a model has no guard.

The flow, in code, with the model doing only short jobs:

1. **Header.** One short generation writes the header row the request asks
   for; the code tells it which entities the request names.
2. **Extraction by document.** For each document that bears on the request,
   one short generation fills the rows that document gives, copying values.
3. **Validation by code.** A cell is kept only if its value is in that
   document (figures compared as numbers, words as stems); a row whose key is
   not in the document, or with no valid cell, is dropped; a cell in a column
   named after another of the request's entities, which the document does not
   mention, is dropped.
4. **Assembly by code.** Rows of several documents are merged by their key,
   differences are computed, a "Fuente" column carries the labels of the
   paragraphs each row came from, and what the sources do not give is "—".
5. The model then writes the text around the finished table.

Whatever writes the table, ``audit`` checks every numeric cell of an answer's
table against the passages and reports the ones that are in none of them.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from .compose import (_GROUP_STEMS, _NUMBER, _canon, _figures, _fold, _request_stems, _stems,
                      unflatten_tables)

_DERIVED = re.compile(r"\b(diferenc\w*|difference|variaci[oó]n|cambio|change|delta)\b", re.I)
_SOURCE_COL = re.compile(r"^\s*(fuentes?|sources?|citas?|referenc\w*)\s*$", re.I)
_EMPTY = {"", "—", "-", "–", "n/a", "na", "nd", "s/d", "no consta", "ninguno", "ninguna", "none", "?"}
_NONE = re.compile(r"^\W*(ninguna|ninguno|none|no hay|sin filas)\b", re.I)


# --- reading tables -----------------------------------------------------------------

def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_rule(line: str) -> bool:
    cells = _cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c or "-") for c in cells)


def find_tables(text: str) -> list[tuple[int, int, list[str], list[list[str]]]]:
    """Markdown tables in a text: (first line, last line + 1, header, rows)."""
    lines = (text or "").split("\n")
    out, i = [], 0
    while i < len(lines):
        if lines[i].strip().startswith("|") and i + 1 < len(lines) and _is_rule(lines[i + 1]) \
                and lines[i + 1].strip().startswith("|"):
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                j += 1
            out.append((i, j, _cells(lines[i]), [_cells(x) for x in lines[i + 2:j]]))
            i = j
        else:
            i += 1
    return out


def strip_tables(text: str) -> str:
    """The text without its Markdown tables (the code's table replaces them)."""
    lines = (text or "").split("\n")
    for a, b, _, _ in reversed(find_tables(text)):
        del lines[a:b]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


# --- prompts ------------------------------------------------------------------------

def header_prompt(request: str, inv: dict[str, Any], lang: str = "es") -> str:
    codes = [e for e in inv.get("entities") or [] if re.fullmatch(r"[A-Z]{1,4}-?\d{1,4}", e)]
    group = [e for e in inv.get("entities") or [] if e not in codes]
    es = lang == "es"
    hint = ""
    if len(codes) >= 2 and len(group) >= 2:
        hint = (f"Usa una fila por cada uno de: {', '.join(group)}; y una columna por cada uno de: "
                f"{', '.join(codes)}." if es else
                f"Use one row for each of: {', '.join(group)}; and one column for each of: {', '.join(codes)}.")
    elif len(codes) >= 2:
        hint = (f"Usa una fila por cada uno de: {', '.join(codes)}." if es else
                f"Use one row for each of: {', '.join(codes)}.")
    elif len(group) >= 2:
        hint = (f"Usa una fila por cada uno de: {', '.join(group)}." if es else
                f"Use one row for each of: {', '.join(group)}.")
    wants_difference = bool(_DERIVED.search(request or ""))
    if es:
        diff = " Añade al final una columna «Diferencia»." if wants_difference else ""
        return (f"Solicitud del usuario: {request}\n\nEscribe solo la fila de encabezado de la tabla que pide, en "
                "Markdown (| Columna 1 | Columna 2 | …). La primera columna nombra lo que distingue cada fila. "
                f"{hint}{diff} No escribas filas de datos ni nada más.")
    diff = " Add a last column \"Difference\"." if wants_difference else ""
    return (f"User's request: {request}\n\nWrite only the header row of the table it asks for, in Markdown "
            "(| Column 1 | Column 2 | …). The first column names what tells the rows apart. "
            f"{hint}{diff} Write no data rows and nothing else.")


def parse_header(text: str) -> list[str] | None:
    for line in (text or "").split("\n"):
        if line.count("|") >= 2 and not _is_rule(line):
            cols = [re.sub(r"[*_`]", "", c).strip() for c in _cells(line)]
            cols = [c for c in cols if c and not _SOURCE_COL.match(c)]
            if 2 <= len(cols) <= 8:
                return cols
    return None


def tidy_header(header: list[str], request: str, docs: list[dict[str, Any]]) -> list[str]:
    """The header the model wrote, without what it added on its own: a
    "difference" column the request does not ask for (it answered the
    example of the prompt), and units of its own in brackets ("Nitrógeno
    total (mg/kg)" for a source column "Nitrógeno total (%)": the unit comes
    from the source's table, or goes)."""
    if not _DERIVED.search(request or ""):
        header = [c for i, c in enumerate(header) if i == 0 or not _DERIVED.search(c)]
    source_cols = [c for d in docs for _, text in d["passages"] for _, _, head, _ in find_tables(text) for c in head]
    out = []
    for i, col in enumerate(header):
        m = re.search(r"\s*\(([^)]*)\)\s*$", col)
        if i and m and _fold(m.group(1)) not in _fold(request or ""):
            name = col[:m.start()].strip()
            unit = ""
            for sc in source_cols:
                sm = re.search(r"\(([^)]*)\)\s*$", sc)
                if sm and _stems(name) and _stems(name) <= _stems(sc):
                    unit = sm.group(1)
                    break
            col = f"{name} ({unit})" if unit else name
        out.append(col)
    return out


def relevant_passages(request: str, header: list[str], doc: dict[str, Any],
                      entities: list[str]) -> list[tuple[str, str]]:
    """The paragraphs of a document given to the extraction: those that share
    a word with the request's topic or the table's columns; without any,
    those that name one of the request's entities; without any, all. With a
    whole report of filler, a 7B model answered that the document gave no
    row (open battery, recipe 2, first run); with the two paragraphs that
    bear on the table it filled it right."""
    wanted = (_request_stems(request) | _stems(" ".join(header[1:]))) - _GROUP_STEMS \
        - _stems(" ".join(entities))
    by_topic = [(label, text) for label, text in doc["passages"] if _stems(text) & wanted]
    if by_topic:
        return by_topic
    named = [(label, text) for label, text in doc["passages"]
             if any(_fold(e) in _fold(text) for e in entities)]
    return named or list(doc["passages"])


def extract_prompt(request: str, header: list[str], doc: dict[str, Any], lang: str = "es",
                   entities: list[str] | None = None) -> str:
    head = "| " + " | ".join(header) + " |"
    body = "\n".join(f"[{label}] {text}"
                     for label, text in relevant_passages(request, header, doc, entities or []))
    if lang == "es":
        return (f"Solicitud del usuario: {request}\n\nLa tabla tendrá estas columnas:\n{head}\n\n"
                f"Documento «{doc['rel']}»:\n{body}\n\n"
                "Escribe solo las filas de esa tabla que este documento permite llenar, una por línea, con las "
                "celdas separadas por «|» y en el mismo orden de columnas. Copia cada valor tal como aparece en "
                "el documento, sin redondear. Si un dato de una fila no está en este documento, o es un cálculo, "
                "pon «—» en su celda. No inventes filas. Si el documento no da ninguna fila, responde solo: NINGUNA.")
    return (f"User's request: {request}\n\nThe table will have these columns:\n{head}\n\n"
            f"Document \"{doc['rel']}\":\n{body}\n\n"
            "Write only the rows of that table this document can fill, one per line, cells separated by \"|\", in "
            "the same column order. Copy each value as it appears in the document, without rounding. If a value of "
            "a row is not in this document, or is a calculation, put \"—\" in its cell. Do not invent rows. If the "
            "document gives no row, answer only: NONE.")


def table_done_block(markdown: str, lang: str = "es") -> str:
    if lang == "es":
        return ("El programa ya armó esta tabla con los datos de las fuentes y la insertará en la respuesta:\n\n"
                f"{markdown}\n\nNo la repitas ni hagas otra tabla. Escribe solo el texto que pide la solicitud, "
                "usando estos valores y los de los párrafos, con sus etiquetas.")
    return ("The program has already built this table from the sources and will insert it in the answer:\n\n"
            f"{markdown}\n\nDo not repeat it or make another table. Write only the text the request asks for, "
            "using these values and those of the paragraphs, with their labels.")


# --- documents, validation, assembly --------------------------------------------------

def documents(request: str, sources: list[dict[str, Any]], limit: int = 4) -> list[dict[str, Any]]:
    """The documents among the passages that share a word of the request's
    topic, in retrieval order, each with all its passages."""
    topic = _request_stems(request) - _GROUP_STEMS
    docs: dict[str, dict[str, Any]] = {}  # in retrieval order
    for s in sources:
        key = str(s.get("doc_id") or s.get("rel") or s.get("source") or "")
        d = docs.setdefault(key, {"rel": str(s.get("rel") or s.get("source") or ""), "passages": [], "hit": False})
        text = unflatten_tables(str(s.get("text", "")))
        d["passages"].append((" ".join(str(s.get("label", "")).split()), text))
        if _stems(text) & topic:
            d["hit"] = True
    # a document the search brought with several paragraphs counts too: a CV
    # holds the user's positions without the word "cargo"
    return [d for d in docs.values() if d["hit"] or len(d["passages"]) >= 2][:limit]


def _name(col: str) -> str:
    return _fold(re.sub(r"\([^)]*\)", " ", col)).strip()


def _match(target: str, source: str, entities: list[str]) -> float:
    """How well a column of the wanted table matches a column of a table in
    the source: shared word stems, or the same short name ("pH")."""
    t = _name(target)
    for e in entities:
        t = t.replace(_fold(e), " ")
    t = " ".join(t.split())
    src = _name(source)
    if not t:
        return 0.0
    if t == src or (len(t) <= 3 and re.search(rf"\b{re.escape(t)}\b", src)):
        return 1.0
    ts, ss = _stems(t), _stems(src)
    return len(ts & ss) / len(ts | ss) if ts and ss else 0.0


def rows_from_tables(header: list[str], doc: dict[str, Any], entities: list[str]) -> list[list[str]]:
    """Rows read by code from the tables a document already has. Asked to
    fill a table from a source table, a 7B model answered that the document
    gave no row, or copied one row of four (open battery, recipe 2); a source
    table needs no model. Each wanted column takes the source column it
    matches best; a source column wanted by two columns named after
    different entities goes to the one this document mentions."""
    whole = _fold(re.sub(r"[_.-]+", " ", doc["rel"]) + "\n" + "\n".join(t for _, t in doc["passages"]))
    mentioned = [e for e in entities if _fold(e) in whole]
    out: list[list[str]] = []
    for _, text in doc["passages"]:
        for _, _, head, rows in find_tables(text):
            if len(head) < 2 or not rows:
                continue
            mapping: dict[int, int] = {}
            for j, col in enumerate(header[1:], 1):
                if _DERIVED.search(col):
                    continue
                best = max(range(1, len(head)), key=lambda k: _match(col, head[k], entities))
                if _match(col, head[best], entities) > 0:
                    mapping[j] = best
            # the same source column for two wanted columns: only the one named
            # after an entity this document mentions
            for src_col in set(mapping.values()):
                wanting = [j for j, k in mapping.items() if k == src_col]
                if len(wanting) > 1:
                    mine = [j for j in wanting if any(_fold(e) in _fold(header[j]) for e in mentioned)]
                    for j in wanting:
                        if len(mine) != 1 or j != mine[0]:
                            del mapping[j]
            if not mapping:
                continue
            key_ok = (_match(header[0], head[0], []) > 0
                      or any(_fold(e) in _fold(r[0]) for r in rows for e in entities))
            if not key_ok:
                continue
            for r in rows:
                cells = ["—"] * len(header)
                cells[0] = r[0]
                for j, k in mapping.items():
                    if k < len(r):
                        cells[j] = r[k]
                out.append(cells)
    return out


def parse_rows(text: str, ncols: int, header: list[str] | None = None) -> list[list[str]]:
    rows = []
    head = [_fold(c) for c in header or []]
    for line in (text or "").split("\n"):
        line = line.strip()
        if not line or _NONE.match(line) or _is_rule(line) or "|" not in line:
            continue
        cells = [re.sub(r"\*\*|`", "", c).strip() for c in _cells(line)]
        cells = [re.sub(r"\s*\[[A-Z]\d+\s*p\d+\]", "", c).strip() for c in cells]
        if head and [_fold(c) for c in cells[:len(head)]] == head:
            continue                     # the header again
        if len(cells) > ncols:
            cells = cells[:ncols]
        if len(cells) < ncols:
            cells += ["—"] * (ncols - len(cells))
        rows.append(cells)
    return rows


def _blank(cell: str) -> bool:
    return _fold(cell).strip(" .") in _EMPTY


def _in_text(cell: str, text: str, figs: set[str], stems: set[str]) -> bool:
    """The cell's value is in the document: its figures as numbers, its words
    as stems (or the whole cell as written)."""
    if _fold(cell) in _fold(text):
        return True
    cell_figs = {_canon(m.group(1)) for m in _NUMBER.finditer(cell)}
    words = _stems(cell)
    if not cell_figs and not words:
        return False
    if cell_figs - figs - {_canon(m.group(1)) for m in _NUMBER.finditer(text)}:
        return False
    return not words or len(words & stems) / len(words) >= 0.8


def _as_written(cell: str, text: str, key: str = "") -> str:
    """The value as the document writes it: a bare number ("1150" → "1.150",
    "87" → "87 %"), or dates the model abbreviated ("Mar 2019 - Jul 2022" →
    "de marzo de 2019 a julio de 2022": the clause of the row's line that
    holds the cell's figures)."""
    if re.fullmatch(r"\d+(?:[.,]\d+)*", cell.strip()):
        for m in _NUMBER.finditer(text):
            if _canon(m.group(1)) == _canon(cell.strip()):
                return m.group(1) + (" %" if m.group(2) else "")
        return cell
    figs = {_canon(m.group(1)) for m in _NUMBER.finditer(cell)}
    if not figs or _fold(cell) in _fold(text) or not key:
        return cell
    for line in text.split("\n"):
        if _fold(key) not in _fold(line):
            continue
        for clause in re.split(r"[,.;:()]\s+|\s[—–-]\s", line):
            if figs <= {_canon(m.group(1)) for m in _NUMBER.finditer(clause)} and len(clause) <= 80:
                return clause.strip(" -.")
    return cell


def _label_for(cell: str, key: str, doc: dict[str, Any]) -> str:
    """The paragraph of the document that holds the cell (with the row's key,
    when one holds both)."""
    best = ""
    for label, text in doc["passages"]:
        if _in_text(cell, text, _figures(text), _stems(text)):
            if _fold(key) in _fold(text):
                return label
            best = best or label
    return best


def validate(rows: list[list[str]], header: list[str], doc: dict[str, Any],
             entities: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rows of one document with only the cells that document supports."""
    text = "\n".join(t for _, t in doc["passages"])
    whole = f"{re.sub(r'[_.-]+', ' ', doc['rel'])}\n{text}"
    figs, stems = _figures(text), _stems(whole)
    mentioned = [e for e in entities if _fold(e) in _fold(whole)]
    kept, dropped = [], []
    for row in rows:
        key = row[0]
        if _blank(key) or not _in_text(key, whole, figs, stems):
            dropped.append({"row": key, "why": "key not in the document", "doc": doc["rel"]})
            continue
        cells, labels = [key], []
        for col, cell in zip(header[1:], row[1:]):
            if _blank(cell) or _DERIVED.search(col):
                cells.append("")
                continue
            # a column named after another of the request's entities, which
            # this document does not mention: not this document's to fill
            named = [e for e in entities if _fold(e) in _fold(col)]
            if named and not any(e in mentioned for e in named):
                cells.append("")
                dropped.append({"row": key, "col": col, "value": cell, "why": "column of another entity",
                                "doc": doc["rel"]})
                continue
            if not _in_text(cell, text, figs, stems):
                cells.append("")
                dropped.append({"row": key, "col": col, "value": cell, "why": "value not in the document",
                                "doc": doc["rel"]})
                continue
            cell = _as_written(cell, text, key)
            cells.append(cell)
            label = _label_for(cell, key, doc)
            if label and label not in labels:
                labels.append(label)
        if any(cells[1:]):
            kept.append({"cells": cells, "labels": labels})
        else:
            dropped.append({"row": key, "why": "no value in the document", "doc": doc["rel"]})
    return kept, dropped


def _key(cell: str, entities: list[str]) -> str:
    folded = re.sub(r"^(el|la|los|las|the)\s+", "", _fold(cell).strip())
    for e in entities:
        fe = _fold(e)
        if fe == folded or (len(folded) >= 4 and (folded in fe or fe in folded)):
            return fe
    return folded


def merge(found: list[dict[str, Any]], entities: list[str]) -> list[dict[str, Any]]:
    """Rows of several documents with the same key become one row; a cell
    already filled is not overwritten (a second, different value is a
    disagreement, kept apart as its own row)."""
    out: list[dict[str, Any]] = []
    for row in found:
        k = _key(row["cells"][0], entities)
        target = next((r for r in out if r["key"] == k and all(
            not a or not b or _fold(a) == _fold(b) for a, b in zip(r["cells"][1:], row["cells"][1:]))), None)
        if target is None:
            out.append({"key": k, "cells": list(row["cells"]), "labels": list(row["labels"])})
            continue
        target["cells"] = [a or b for a, b in zip(target["cells"], row["cells"])]
        target["labels"] += [x for x in row["labels"] if x not in target["labels"]]
    return out


def _number(cell: str) -> tuple[float, int, bool] | None:
    m = _NUMBER.search(cell or "")
    if not m:
        return None
    raw, canon = m.group(1), _canon(m.group(1))
    try:
        value = float(canon)
    except ValueError:
        return None
    decimals = len(canon.split(".")[1]) if "." in canon else 0
    return value, decimals, ("," in raw and "." in canon)


def _format(value: float, decimals: int, comma: bool, like: str) -> str:
    text = f"{abs(value):.{decimals}f}"
    if comma:
        text = text.replace(".", ",")
    unit = _NUMBER.sub("", like, count=1).strip()
    return f"{text} {unit}".strip() if unit and len(unit) <= 12 else text


def derive(header: list[str], rows: list[dict[str, Any]], lang: str = "es") -> tuple[list[str], list[dict[str, Any]], int]:
    """Differences computed by code: a "difference" column between the two
    other numeric columns, or a "difference" row between two rows."""
    derived = [i for i, c in enumerate(header) if i and _DERIVED.search(c)]
    if not derived:
        return header, rows, 0
    d = derived[0]
    numeric = [i for i in range(1, len(header)) if i not in derived
               and rows and all(_number(r["cells"][i]) for r in rows if r["cells"][i])
               and any(r["cells"][i] for r in rows)]
    done = 0
    if len(numeric) == 2:
        for r in rows:
            a, b = _number(r["cells"][numeric[0]]), _number(r["cells"][numeric[1]])
            if a and b:
                r["cells"][d] = _format(a[0] - b[0], max(a[1], b[1]), a[2] or b[2], "")
                done += 1
        return header, rows, done
    if len(numeric) == 1 and len(rows) == 2:
        a, b = _number(rows[0]["cells"][numeric[0]]), _number(rows[1]["cells"][numeric[0]])
        header = [c for i, c in enumerate(header) if i not in derived]
        for r in rows:
            r["cells"] = [c for i, c in enumerate(r["cells"]) if i not in derived]
        if a and b:
            col = numeric[0] - sum(1 for x in derived if x < numeric[0])
            cells = [""] * len(header)
            cells[0] = "Diferencia" if lang == "es" else "Difference"
            cells[col] = _format(a[0] - b[0], max(a[1], b[1]), a[2] or b[2], rows[0]["cells"][col])
            rows = [*rows, {"key": "_derived", "cells": cells,
                            "labels": [x for r in rows for x in r["labels"]]}]
            done = 1
        return header, rows, done
    return header, rows, 0


def render(header: list[str], rows: list[dict[str, Any]], lang: str = "es") -> str:
    head = [*header, "Fuente" if lang == "es" else "Source"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        labels = " ".join(f"[{x}]" for x in dict.fromkeys(r["labels"]))
        lines.append("| " + " | ".join([*(c or "—" for c in r["cells"]), labels or "—"]) + " |")
    return "\n".join(lines)


def build(request: str, sources: list[dict[str, Any]], inv: dict[str, Any],
          generate: Callable[[str, int], str], lang: str = "es") -> dict[str, Any] | None:
    """The table the request asks for, built from the sources, or None when
    the code cannot build one (the request is then answered as before).
    ``generate(prompt, max_tokens)`` is one short generation."""
    header = parse_header(generate(header_prompt(request, inv, lang), 80))
    docs = documents(request, sources)
    if not header or not docs:
        return None
    header = tidy_header(header, request, docs)
    if len(header) < 2:
        return None
    entities = list(inv.get("entities") or [])
    found, dropped = [], []
    by_code = 0
    for doc in docs:
        rows = rows_from_tables(header, doc, entities)      # a source table needs no model
        if rows:
            by_code += len(rows)
        else:
            rows = parse_rows(generate(extract_prompt(request, header, doc, lang, entities), 400),
                              len(header), header)
        kept, bad = validate(rows, header, doc, entities)
        found += kept
        dropped += bad
    rows = merge(found, entities)
    if len(rows) < 2:
        return None
    header, rows, computed = derive(header, rows, lang)
    empty = sum(1 for r in rows for c in r["cells"][1:] if not c)
    return {"markdown": render(header, rows, lang), "header": header, "rows": len(rows),
            "documents": [d["rel"] for d in docs], "computed": computed, "empty": empty,
            "rows_by_code": by_code,
            "dropped": dropped[:12]}


def place(text: str, table: str, request: str) -> str:
    """The table goes first when the request asks for it first ("Haz una
    tabla… y explícala"), otherwise after the first paragraph."""
    low = _fold(request)
    t_pos = min((low.find(w) for w in ("tabla", "cuadro", "table") if w in low), default=-1)
    k_pos = min((low.find(w) for w in ("informe", "parrafo", "texto", "resumen", "report", "paragraph",
                                       "summary") if w in low), default=10 ** 6)
    paragraphs = [p for p in re.split(r"\n\s*\n", (text or "").strip()) if p.strip()]
    if not paragraphs:
        return table
    if 0 <= t_pos < k_pos:
        return "\n\n".join([table, *paragraphs])
    return "\n\n".join([paragraphs[0], table, *paragraphs[1:]])


# --- audit --------------------------------------------------------------------------

def audit(answer: str, sources: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Every numeric cell of the answer's tables against the passages: a
    figure that is in no passage, and is not the difference or sum of two
    other cells of its row or column, is reported."""
    found = find_tables(answer)
    if not found:
        return None
    known: set[str] = set()
    for s in sources:
        known |= {_canon(m.group(1)) for m in _NUMBER.finditer(str(s.get("text", "")))}
    cells = 0
    bad: list[dict[str, str]] = []
    for _, _, header, rows in found:
        # only cells whose own figures are in the passages can explain another
        # cell (an invented row is consistent with itself)
        def supported(c: str) -> float | None:
            figs = {_canon(m.group(1)) for m in _NUMBER.finditer(c)}
            return (_number(c) or (None,))[0] if figs and figs <= known else None
        grid = [[supported(c) for c in row] for row in rows]
        for i, row in enumerate(rows):
            for j, cell in enumerate(row):
                if j == 0 or (j < len(header) and _SOURCE_COL.match(header[j])):
                    continue
                figs = {_canon(m.group(1)) for m in _NUMBER.finditer(re.sub(r"\[[A-Z]\d+\s*p\d+\]", "", cell))}
                if not figs:
                    continue
                cells += 1
                if figs <= known:
                    continue
                value = (_number(cell) or (None,))[0]
                same_row = [v for k, v in enumerate(grid[i]) if k != j and v is not None]
                same_col = [g[j] for k, g in enumerate(grid) if k != i and j < len(g) and g[j] is not None]
                def computed(others: list[float]) -> bool:
                    return any(abs(abs(a - b) - abs(value)) < 0.006 or abs(a + b - value) < 0.006
                               for x, a in enumerate(others) for b in others[x + 1:])
                if value is not None and (computed(same_row) or computed(same_col)):
                    continue
                bad.append({"row": row[0][:60], "column": header[j][:60] if j < len(header) else "",
                            "value": cell[:40]})
    return {"cells": cells, "unsupported": bad[:12]}
