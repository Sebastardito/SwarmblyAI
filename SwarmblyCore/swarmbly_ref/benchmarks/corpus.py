"""Benchmark corpus: diverse, complex, deterministic tasks with answer keys.

Design rules:
- Material is generated deterministically so grading has exact ground truth.
- Tables are rendered as full sentences (one per row) so the sentence-based
  planner applies uniformly and rows are the natural semantic units.
- Every task carries `unique_terms`, `answer_keys`, `required_items` and
  `weights` so grading is mechanical and arm-neutral.
"""



def _table_numeric(rows, total, top_a, top_b):
    """Ground-truth numbers: every value and change, plus the key numbers
    (total + top movers) for the key-recall side of the numeric grade."""
    all_nums = {f"{r[2]:.1f}" for r in rows} | {f"{abs(r[3]):.1f}" for r in rows} | {f"{total:.1f}"}
    def row(name):
        return next(r for r in rows if r[0] == name)
    a, b = row(top_a), row(top_b)
    key = {f"{total:.1f}", f"{a[2]:.1f}", f"{abs(a[3]):.1f}",
           f"{b[2]:.1f}", f"{abs(b[3]):.1f}"}
    return sorted(all_nums), sorted(key)



def _new_table(tid, rows, preamble, req_extra, name):
    """Tabla nueva con top movers AUTOMÁTICOS (mayor subida, mayor bajada)."""
    total = round(sum(r[2] for r in rows), 1)
    top_inc = max(rows, key=lambda r: r[3])[0]
    top_dec = min(rows, key=lambda r: r[3])[0]
    return _make_table_task(tid, name,
                            "One coherent paragraph summarising the table: the total value, the largest increase and the largest decrease, and the pattern by category.",
                            rows, total, top_inc, top_dec, preamble, req_extra)

# ---------------------------------------------------------------- helpers ---

def _row_sentence(name, category, value, change):
    direction = "up" if change >= 0 else "down"
    return (f"{name}, a {category} position, closed the quarter at {value:.1f} "
            f"million, {direction} {abs(change):.1f} percent.")


def _table_material(preamble, rows):
    return " ".join(preamble) + " " + " ".join(_row_sentence(*r) for r in rows)


# ------------------------------------------------------- 1. table outturn ---

OUTTURN_ROWS = [
    ("Harborline", "equity", 42.1, +3.4),
    ("Cantabric", "equity", 36.8, +9.2),
    ("Meridian", "bonds", 30.5, -1.1),
    ("Altamira", "bonds", 27.4, -0.8),
    ("Northgate", "equity", 26.2, +2.6),
    ("Verdeplata", "commodities", 24.9, +5.7),
    ("Eastdock", "bonds", 22.8, -2.4),
    ("Solaris", "equity", 21.5, +7.8),
    ("Brisamar", "commodities", 19.7, +1.9),
    ("Cobrejil", "commodities", 18.4, +11.2),
    ("Llanura", "bonds", 17.9, -3.3),
    ("Petroandina", "commodities", 16.2, +4.1),
    ("Celmar", "equity", 15.0, +2.2),
    ("Valleazul", "bonds", 14.6, -0.5),
    ("Ribera", "equity", 13.3, +1.4),
    ("Montiel", "commodities", 12.1, +6.6),
]
OUTTURN_TOTAL = round(sum(r[2] for r in OUTTURN_ROWS), 1)  # 359.4

TABLE_OUTTURN = {
    "id": "table_outturn",
    "name": "Resumen trimestral de cartera (16 posiciones)",
    "kind": "table_summary",
    "decomposable": True,
    "sequential": False,
    "objective": "One coherent paragraph (6-8 sentences) summarising the quarterly outturn: the total value, the two largest movers, and the overall trend by asset class. Use only the material given.",
    "format": "prose",
    "entities": {r[0]: r[1] for r in OUTTURN_ROWS},
    "global_constraints": ["use exact entity names and numbers from the material",
                           "do not invent rows that are not in the material"],
    "unique_terms": [],
    "no_repeat": False,
    "answer_keys": [[f"{OUTTURN_TOTAL:.1f}"], ["Cobrejil"], ["Cantabric"]],
    "required_items": [f"{OUTTURN_TOTAL:.1f}", "Cobrejil", "Cantabric",
                       "Harborline", "Eastdock"],
    "weights": {"coverage": 0.25, "qa": 0.25, "numeric": 0.2,
                "seam_free": 0.2, "repetition": 0.1},
    "numeric_keys": _table_numeric(OUTTURN_ROWS, OUTTURN_TOTAL,
                                   "Cobrejil", "Cantabric")[0],
    "key_numeric": _table_numeric(OUTTURN_ROWS, OUTTURN_TOTAL,
                                  "Cobrejil", "Cantabric")[1],
    "L_target": 10, "F": 2,
    "max_out_tokens": 220,
    "explicit_crossings": 2,
    "preamble": [
        "The third-quarter outturn report covers sixteen positions across equity, bonds and commodities.",
        "The figures below are final and replace the provisional numbers circulated in August.",
        "The totals combine the equity and fixed-income books with the commodities sleeve.",
        "All values are in millions and all changes are against the previous quarter.",
    ],
    "material": _table_material([
        "The third-quarter outturn report covers sixteen positions across equity, bonds and commodities.",
        "The figures below are final and replace the provisional numbers circulated in August.",
        "The totals combine the equity and fixed-income books with the commodities sleeve.",
        "All values are in millions and all changes are against the previous quarter.",
    ], OUTTURN_ROWS),
    "instruction_mono": "Read the material above. Write ONE coherent paragraph of 6-8 sentences summarising the quarterly outturn: state the total value, the two positions with the largest changes (with their numbers), and the overall trend by asset class.",
    "instruction_frag": "You are assigned PART of an outturn table. Summarise YOUR assigned statements in 2-3 sentences: report the exact names, values and changes mentioned there. Do not invent rows you were not given and do not write an overall conclusion.",
    "perfect_answer": "The third-quarter outturn totalled 359.4 million. Cobrejil rose 11.2 percent to 18.4 million, the largest move, and Cantabric rose 9.2 percent to 36.8 million. Harborline led the book at 42.1 million. Eastdock fell 2.4 percent to 22.8 million.",
}

# ------------------------------------------------------- 2. bonded table ---

BONDED_ROWS = [
    ("Tranche A-1", "secured", 31.4, +1.2),
    ("Tranche B-2", "unsecured", 28.9, -2.7),
    ("Tranche C-3", "secured", 25.6, +3.9),
    ("Tranche D-1", "convertible", 22.3, +6.8),
    ("Tranche E-4", "unsecured", 20.8, -0.9),
    ("Tranche F-2", "secured", 19.1, +2.4),
    ("Tranche G-5", "convertible", 17.7, -3.6),
    ("Tranche H-3", "secured", 15.2, +5.1),
    ("Tranche I-1", "unsecured", 13.9, -1.4),
    ("Tranche J-6", "convertible", 12.0, +4.3),
    ("Tranche K-2", "secured", 11.4, +0.8),
    ("Tranche L-4", "unsecured", 10.6, -2.1),
    ("Tranche M-1", "convertible", 9.8, +7.4),
    ("Tranche N-5", "secured", 9.1, -0.4),
    ("Tranche O-3", "unsecured", 8.5, +1.7),
    ("Tranche P-2", "convertible", 7.6, +2.9),
]
BONDED_TOTAL = round(sum(r[2] for r in BONDED_ROWS), 1)  # 263.9

TABLE_BONDED = {
    "id": "table_bonded",
    "name": "Resumen de deuda emitida (16 tramos)",
    "kind": "table_summary",
    "decomposable": True,
    "sequential": False,
    "objective": "One coherent paragraph summarising the bonded debt book: total outstanding, the tranche with the largest increase and the largest decrease, and the split between secured and unsecured.",
    "format": "prose",
    "entities": {r[0]: r[1] for r in BONDED_ROWS},
    "global_constraints": ["use exact tranche names and numbers",
                           "do not invent tranches"],
    "unique_terms": [],
    "no_repeat": False,
    "answer_keys": [[f"{BONDED_TOTAL:.1f}"], ["Tranche M-1"], ["Tranche G-5"]],
    "required_items": [f"{BONDED_TOTAL:.1f}", "Tranche M-1", "Tranche G-5",
                       "Tranche A-1", "Tranche D-1"],
    "weights": {"coverage": 0.25, "qa": 0.25, "numeric": 0.2,
                "seam_free": 0.2, "repetition": 0.1},
    "numeric_keys": _table_numeric(BONDED_ROWS, BONDED_TOTAL,
                                   "Tranche M-1", "Tranche G-5")[0],
    "key_numeric": _table_numeric(BONDED_ROWS, BONDED_TOTAL,
                                  "Tranche M-1", "Tranche G-5")[1],
    "L_target": 10, "F": 2,
    "max_out_tokens": 220,
    "explicit_crossings": 2,
    "preamble": [
        "The bonded-debt registry lists sixteen tranches issued under the 2025 programme.",
        "The registry below is the audited version, reconciled with the trustee's ledger.",
        "Secured tranches are backed by pooled collateral; unsecured and convertible tranches are not.",
        "All amounts are in millions and changes are against the previous quarter.",
    ],
    "material": _table_material([
        "The bonded-debt registry lists sixteen tranches issued under the 2025 programme.",
        "The registry below is the audited version, reconciled with the trustee's ledger.",
        "Secured tranches are backed by pooled collateral; unsecured and convertible tranches are not.",
        "All amounts are in millions and changes are against the previous quarter.",
    ], BONDED_ROWS),
    "instruction_mono": "Read the material above. Write ONE coherent paragraph summarising the bonded debt book: state the total outstanding, the tranche with the largest increase and the one with the largest decrease (with numbers), and the secured versus unsecured split.",
    "instruction_frag": "You are assigned PART of a bond registry. Summarise YOUR assigned tranches in 2-3 sentences with their exact names, values and changes. Do not invent tranches and do not write an overall conclusion.",
    "perfect_answer": "The bonded debt book totals 263.9 million. Tranche M-1 rose 7.4 percent to 9.8, the largest increase, and Tranche G-5 fell 3.6 percent to 17.7, the largest decrease. Tranche A-1 leads at 31.4 million and Tranche D-1 adds 22.3 million.",
}

# ------------------------------------------------------- 3. long report ---

REPORT_SECTIONS = [
    ("Market context", [
        "AndesGrid operates three regional interconnections feeding the northern grid.",
        "Demand on the northern grid grew 4.2 percent year on year, led by industrial consumers.",
        "The Quinde Line, a 220-kilovolt corridor, was commissioned in March of this year.",
        "Spot prices averaged 61 dollars per megawatt-hour over the period.",
        "Imports through the T\u00e9rminos Consortium interconnector covered 8 percent of demand.",
        "Regulatory changes shortened the connection queue from fourteen to nine months.",
        "Two new solar parks totalling 190 megawatts entered commercial operation.",
        "The market context above sets the frame for the operational results below.",
    ]),
    ("Operations", [
        "AndesGrid's availability index reached 98.1 percent across its three lines.",
        "The Quinde Line operated at 87 percent utilisation during peak hours.",
        "Maintenance campaigns reduced forced outages by 22 percent versus last year.",
        "The C\u00f3ndor Peak substation expansion added 300 megawatts of transformation capacity.",
        "Dispatch coordination with the T\u00e9rminos Consortium avoided 41 hours of curtailment.",
        "A new remote-fault locator cut average restoration time to 3.1 hours.",
        "Field crews completed 94 percent of scheduled inspections on time.",
        "The operational figures above feed directly into the financial results below.",
    ]),
    ("Financial results", [
        "AndesGrid posted EBITDA of 412 million for the year, a 6.1 percent rise.",
        "The Quinde Line contributed 118 million of that EBITDA in its first year.",
        "Net margin reached 14.6 percent, up from 13.9 percent the year before.",
        "Capital expenditure of 260 million was concentrated in the C\u00f3ndor Peak expansion.",
        "The Delta Fund subscribed a 90-million mezzanine tranche in June.",
        "Financing costs fell 30 basis points after the refinancing in April.",
        "Dividend policy was maintained at 40 percent of net income.",
        "The financial results above are the basis for the risk and outlook sections below.",
    ]),
    ("Risk", [
        "Hydrology risk remains the largest single exposure for the generation fleet.",
        "A dry sequence of twelve consecutive months would cut hydro output 18 percent.",
        "Counterparty exposure to the T\u00e9rminos Consortium is capped at 6 percent of revenue.",
        "Currency exposure is hedged at 71 percent of the twelve-month forecast.",
        "Cyber drills in the second half found two findings, both since remediated.",
        "Insurance for the Quinde Line covers business interruption up to 90 days.",
        "The Delta Fund facility includes covenants tested quarterly.",
        "The risk section above informs the outlook below.",
    ]),
    ("Outlook", [
        "AndesGrid guides to 4.4 percent demand growth for the coming year.",
        "The C\u00f3ndor Peak expansion is scheduled for completion in the third quarter.",
        "Two further interconnections with the T\u00e9rminos Consortium are under study.",
        "The Delta Fund has signalled willingness to extend the facility by 40 million.",
        "Tariff reviews in the northern region are scheduled for the first half.",
        "Management expects EBITDA growth of 5 to 7 percent for the coming year.",
        "The board will present the full-year guidance at the January meeting.",
        "This concludes the outlook and the report.",
    ]),
]
REPORT_MATERIAL = " ".join(s for _, sents in REPORT_SECTIONS for s in sents)

LONG_REPORT = {
    "id": "long_report",
    "name": "Reporte anual multi-sección (5 secciones, 40 oraciones)",
    "kind": "report",
    "decomposable": True,
    "sequential": False,
    "objective": "An annual report in five sections (Market context, Operations, Financial results, Risk, Outlook), 2-3 sentences per section, using the exact entity names given.",
    "format": "prose",
    "entities": {"AndesGrid": "operator", "Quinde Line": "corridor",
                 "Delta Fund": "lender", "C\u00f3ndor Peak": "substation",
                 "T\u00e9rminos Consortium": "partner"},
    "global_constraints": ["use exact entity names", "do not repeat any five-word phrase"],
    "unique_terms": ["AndesGrid", "Quinde Line", "Delta Fund", "C\u00f3ndor Peak"],
    "no_repeat": False,
    "answer_keys": [["412"], ["14.6"], ["98.1"]],
    "required_items": ["AndesGrid", "Quinde Line", "Delta Fund", "C\u00f3ndor Peak",
                       "T\u00e9rminos Consortium"],
    "weights": {"coverage": 0.3, "constraints": 0.3, "qa": 0.2, "seam_free": 0.2},
    "L_target": 8, "F": 2,
    "max_out_tokens": 500,
    "explicit_crossings": 4,   # the "above/below" bridge sentences
    "material": REPORT_MATERIAL,
    "instruction_mono": "Read the material above. Write the annual report: five short sections (Market context, Operations, Financial results, Risk, Outlook), 2-3 sentences each, using the exact entity names and the key figures.",
    "instruction_frag": "You are assigned PART of the source material for an annual report. Summarise YOUR assigned sentences in 2-3 sentences per theme, preserving exact entity names and figures. Do not write sections you were not given material for.",
    "perfect_answer": "AndesGrid operates the northern grid through the Quinde Line. EBITDA reached 412 million with a net margin of 14.6 percent and availability of 98.1 percent. The Delta Fund subscribed the mezzanine tranche in June. The C\u00f3ndor Peak expansion anchors the capital programme, and the T\u00e9rminos Consortium remains the partner for future interconnections.",
}

# ------------------------------------------------------- 4. fan QA ---------

FAN_FACTS = [
    ("logistics", "Eastdock processes 2400 pallets per day on average.", ["2400"]),
    ("logistics", "Harborline processes 1800 pallets per day on average.", ["1800"]),
    ("logistics", "Meridian processes 2000 pallets per day on average.", ["2000"]),
    ("logistics", "The three warehouses together move 6200 pallets every working day.", ["6200"]),
    ("logistics", "Northgate is the only warehouse that closes on Sundays.", ["Northgate"]),
    ("logistics", "Route R7 connects Eastdock to Meridian and is 85 kilometres long.", ["85", "R7"]),
    ("logistics", "The fleet consists of 42 trucks, of which 30 are refrigerated.", ["42", "30"]),
    ("logistics", "Quarter-four volumes typically run 30 percent above the annual average.", ["30"]),
    ("logistics", "The Meridian yard can stage 120 trailers at any one time.", ["120"]),
    ("logistics", "Fuel consumption averages 2.1 kilometres per litre across the fleet.", ["2.1"]),
    ("logistics", "The Eastdock cross-dock opened in 2019 and was expanded in 2023.", ["2019", "2023"]),
    ("logistics", "Driver shifts are limited to 9 hours by the new safety directive.", ["9"]),
    ("logistics", "Perishable shipments through Eastdock account for 55 percent of its volume.", ["55"]),
    ("logistics", "The R7 corridor carries 410 tonnes of cargo on a peak day.", ["410"]),
    ("logistics", "Scheduled maintenance takes the fleet offline for 2 days each quarter.", ["2"]),
    ("logistics", "The control tower tracks 99.2 percent of shipments in real time.", ["99.2"]),
    ("logistics", "Last year the network delivered 1.3 million pallets in total.", ["1.3"]),
    ("logistics", "The Portside depot was decommissioned in January and its volume moved to Harborline.", ["Portside", "Harborline"]),
    ("logistics", "Average dock-to-stock time at Meridian is 6 hours and 20 minutes.", ["6"]),
    ("logistics", "The network operates 19 hours a day, six days a week.", ["19", "6"]),
    ("logistics", "Cross-dock throughput at Eastdock peaks at 340 pallets per hour.", ["340"]),
    ("logistics", "Refrigerated trailers are fitted with dual-zone temperature control.", ["dual-zone"]),
    ("logistics", "The safety directive also mandates a 45-minute break after 4 hours of driving.", ["45", "4"]),
    ("logistics", "Harborline serves the western corridor exclusively.", ["western"]),
    ("logistics", "The eastern corridor is served by Eastdock and Northgate.", ["eastern"]),
    ("logistics", "Route R9 links Harborline to the Portside area and remains open for overflow.", ["R9"]),
    ("logistics", "The control tower upgraded its software stack in May.", ["May"]),
    ("logistics", "Average utilisation of the refrigerated fleet is 78 percent.", ["78"]),
    ("logistics", "The network plan for next year adds 12 electric trucks to the fleet.", ["12"]),
    ("logistics", "All warehouses run on the same warehouse-management system since 2021.", ["2021"]),
]
FAN_DOC = " ".join(s for _, s, _ in FAN_FACTS)

FAN_QUESTIONS = [
    ("What is the total daily volume across the three main warehouses?", ["6200"]),
    ("Which warehouse closes on Sundays?", ["Northgate"]),
    ("How long is Route R7?", ["85"]),
    ("How many trucks does the fleet have?", ["42"]),
    ("By how much do quarter-four volumes rise above the annual average?", ["30"]),
    ("Which route connects Eastdock to Meridian?", ["R7"]),
]

FAN_QA = {
    "id": "fan_qa",
    "name": "QA en abanico sobre documento logístico (6 preguntas, 30 oraciones)",
    "kind": "qa",
    "decomposable": True,
    "sequential": False,
    "objective": "Answer six independent questions about the logistics network, each from the material, with a short factual answer.",
    "format": "line-list",
    "entities": {"Eastdock": "warehouse", "Harborline": "warehouse",
                 "Meridian": "warehouse", "Northgate": "warehouse"},
    "global_constraints": ["answer each question on its own line",
                           "give short factual answers"],
    "unique_terms": [],
    "no_repeat": False,
    "answer_keys": [k for _, k in FAN_QUESTIONS],
    "required_items": ["Eastdock", "Harborline", "Meridian", "Northgate"],
    "weights": {"qa": 0.8, "seam_free": 0.2},
    "L_target": 6, "F": 1,
    "max_out_tokens": 60,   # per question
    "explicit_crossings": 1,
    "material": FAN_DOC,
    "questions": FAN_QUESTIONS,
    "instruction_mono": "Answer each of the following questions in one short factual line, using only the material above. Number your lines 1-6.\n" + "\n".join(f"{i+1}. {q}" for i, (q, _) in enumerate(FAN_QUESTIONS)),
    "instruction_frag": "Using only your assigned material, answer THIS question in one short factual line: {question}",
    "schema": "line-list", "min_lines": 1,
    "perfect_answer": "1. 6200 pallets per working day. 2. Northgate. 3. 85 kilometres. 4. 42 trucks. 5. 30 percent. 6. R7.",
}

# ------------------------------------------------------- 5. composition ----

COMPOSITION_SPEC = [
    "The coastal flood defence program covers three phases of construction.",
    "The first phase reinforces the seawall along the northern shore.",
    "The second phase builds the tidal gate system at the river mouth.",
    "The third phase raises the southern embankments by two metres.",
    "The program budget is 412 million, disbursed over five years.",
    "Completion of all three phases is scheduled for 2028.",
    "The Delta Fund provides 60 percent of the financing.",
    "The T\u00e9rminos Consortium holds the engineering contract.",
    "The C\u00f3ndor Peak observatory monitors storm surges for the program.",
    "Local fishing cooperatives were consulted in the design of the tidal gates.",
    "The northern shore seawall protects twelve thousand residents.",
    "The tidal gate system is designed for a one-in-two-hundred-year storm.",
]

CONSTRAINED_COMPOSITION = {
    "id": "constrained_composition",
    "name": "Composición con restricciones globales (4 términos exactamente-una-vez, sin frases repetidas)",
    "kind": "composition",
    "decomposable": True,
    "sequential": False,
    "objective": "A four-paragraph briefing on the coastal flood defence program, one paragraph per phase plus an opening paragraph, using the background facts provided.",
    "format": "prose",
    "entities": {"Delta Fund": "lender", "T\u00e9rminos Consortium": "contractor",
                 "C\u00f3ndor Peak": "observatory"},
    "global_constraints": ["mention each unique term exactly once in the whole briefing",
                           "do not repeat any five-word phrase"],
    "unique_terms": ["Delta Fund", "T\u00e9rminos Consortium", "C\u00f3ndor Peak"],
    "no_repeat": True,
    "answer_keys": [["412"], ["2028"]],
    "required_items": ["412", "2028", "three phases"],
    "weights": {"coverage": 0.25, "constraints": 0.4, "qa": 0.1, "seam_free": 0.25},
    "L_target": 4, "F": 1,
    "max_out_tokens": 300,
    "explicit_crossings": 1,
    "material": " ".join(COMPOSITION_SPEC),
    "instruction_mono": "Using the background facts, write a four-paragraph briefing on the coastal flood defence program. Constraints: mention 'Delta Fund', 'T\u00e9rminos Consortium' and 'C\u00f3ndor Peak' EXACTLY ONCE EACH in the whole briefing, and do not repeat any five-word phrase.",
    "instruction_frag": "Write ONE paragraph of the briefing using ONLY your assigned background sentences. Mention your assigned unique terms EXACTLY ONCE and only in this paragraph. Do not repeat any five-word phrase.",
}

# ------------------------------------------------------- 6. extraction -----

EXTRACTION_RECORDS = [
    ("SH-1001", "Eastdock", "Harborline", 12.4, "delivered"),
    ("SH-1002", "Meridian", "Eastdock", 8.1, "in-transit"),
    ("SH-1003", "Harborline", "Northgate", 5.7, "delivered"),
    ("SH-1004", "Eastdock", "Meridian", 9.9, "held"),
    ("SH-1005", "Northgate", "Eastdock", 6.3, "delivered"),
    ("SH-1006", "Meridian", "Harborline", 11.2, "in-transit"),
    ("SH-1007", "Harborline", "Meridian", 4.8, "delivered"),
    ("SH-1008", "Eastdock", "Northgate", 7.5, "held"),
]

def _record_sentence(r):
    return (f"Shipment {r[0]} travels from {r[1]} to {r[2]} with a declared "
            f"weight of {r[3]} tonnes and current status {r[4]}.")

EXTRACTION_MATERIAL = " ".join(_record_sentence(r) for r in EXTRACTION_RECORDS)

EXTRACTION_GRID = {
    "id": "extraction_grid",
    "name": "Extracción estructurada de 8 manifiestos (JSON verificable)",
    "kind": "extraction",
    "decomposable": True,
    "sequential": False,
    "objective": "Extract the structured fields of every shipment manifest into a single JSON array.",
    "format": "json",
    "entities": {r[0]: r[1] for r in EXTRACTION_RECORDS},
    "global_constraints": ["output one JSON array with one object per shipment"],
    "unique_terms": [],
    "no_repeat": False,
    "answer_keys": [["SH-1001"], ["SH-1002"], ["SH-1003"], ["SH-1004"],
                    ["SH-1005"], ["SH-1006"], ["SH-1007"], ["SH-1008"],
                    ["12.4"], ["8.1"], ["5.7"], ["9.9"], ["6.3"], ["11.2"],
                    ["4.8"], ["7.5"]],
    "required_items": [r[0] for r in EXTRACTION_RECORDS],
    "weights": {"qa": 0.6, "coverage": 0.4},
    "L_target": 2, "F": 0,
    "max_out_tokens": 60,
    "explicit_crossings": 0,
    "material": EXTRACTION_MATERIAL,
    "records": EXTRACTION_RECORDS,
    "instruction_mono": "Extract every shipment from the material into ONE JSON array. Each object must have fields: shipment, origin, destination, weight_tonnes, status. Output only JSON.",
    "instruction_frag": "Extract the shipment(s) in your assigned material into a JSON array of objects with fields: shipment, origin, destination, weight_tonnes, status. Output only JSON.",
    "schema": "json",
}

# ------------------------------------------------------- 7. longform -------

LONGFORM_SECTIONS = [
    ("Production", [
        "The Planta Uno facility produced 5200 units this year, a 3.1 percent increase.",
        "Planta Dos produced 4800 units, essentially flat against last year.",
        "The two plants together produced 10000 units, a new company record.",
        "Yield at Planta Uno reached 94.2 percent of nameplate capacity.",
        "Yield at Planta Dos reached 91.7 percent, constrained by a March overhaul.",
        "The March overhaul at Planta Dos replaced the main conveyor system.",
        "Downtime across both plants totalled 212 hours for the year.",
        "The average production cost per unit fell 4.4 percent to 118 dollars.",
        "Quality rejects were held below 0.8 percent of total output.",
        "A third shift at Planta Uno began in September and added 220 units.",
        "The new finishing line at Planta Dos came online in November.",
        "Supplier lead times averaged 26 days over the year.",
        "Raw-material inventory turns improved from 9.2 to 10.6 times.",
        "The production plan for next year targets 10600 combined units.",
        "The production figures above are the basis for the financial section below.",
    ]),
    ("Finance", [
        "Company revenue reached 412 million this year, up 5.6 percent.",
        "Gross margin widened to 38.2 percent from 37.1 percent.",
        "Operating expenses rose 3.9 percent, below the inflation rate.",
        "Net income came to 58 million, a 9.4 percent improvement.",
        "Capital expenditure was 64 million, mostly in Planta Dos automation.",
        "Free cash flow was 47 million after working-capital changes.",
        "Net debt fell to 96 million from 121 million a year earlier.",
        "The interest coverage ratio improved to 8.4 times.",
        "Return on capital employed reached 14.6 percent.",
        "The board approved a dividend of 1.10 per share.",
        "Foreign-exchange effects subtracted 2.1 million from operating profit.",
        "Working capital days improved from 54 to 49 over the year.",
        "The effective tax rate was 23.1 percent for the year.",
        "Cash conversion reached 91 percent of net income.",
        "The finance figures above feed the workforce and outlook sections below.",
    ]),
    ("Workforce", [
        "The company employed 1250 people at year end, up 4 percent.",
        "Safety performance improved with a lost-time rate of 0.31.",
        "Training hours averaged 41 per employee for the year.",
        "Apprenticeship intake doubled to 36 positions in September.",
        "Absenteeism fell to 2.8 percent from 3.4 percent.",
        "The night-shift allowance was raised 6 percent in July.",
        "Employee retention improved to 89 percent.",
        "Union negotiations concluded in October with a two-year agreement.",
        "The graduate program recruited 14 engineers across both plants.",
        "Ergonomics assessments covered 92 percent of production workstations.",
        "Internal promotions filled 71 percent of supervisory vacancies.",
        "The employee suggestion scheme generated 230 implemented improvements.",
        "Average tenure rose to 6.8 years.",
        "Health insurance uptake reached 96 percent of eligible staff.",
        "The workforce figures above support the outlook section below.",
    ]),
    ("Outlook", [
        "Management guides to 5 to 7 percent revenue growth next year.",
        "The Planta Dos automation program continues into the second quarter.",
        "Two new export markets are scheduled for entry in the first half.",
        "Energy costs are hedged at 61 percent of the coming year's forecast.",
        "The company expects the combined production target of 10600 units to hold.",
        "A capacity study for a possible third plant will conclude in June.",
        "The board will review the dividend policy at the annual meeting.",
        "The export push focuses on the two new markets in the Pacific basin.",
        "Product development will launch three upgraded lines in April.",
        "The automation roadmap runs to the end of next year.",
        "Procurement savings of 4.5 million are budgeted for the first half.",
        "A dividend increase remains conditional on free cash flow above 50 million.",
        "Weather-related logistics risk is monitored through the quarterly supply review.",
        "The next annual review will be published in February.",
        "This concludes the outlook and the annual review.",
    ]),
]
LONGFORM_MATERIAL = " ".join(s for _, sents in LONGFORM_SECTIONS for s in sents)

LONGFORM = {
    "id": "longform",
    "name": "Revisión anual extensa (60 oraciones, para la curva-L)",
    "kind": "longform",
    "decomposable": True,
    "sequential": False,
    "objective": "A faithful summary of the annual review, preserving all key figures and entity names.",
    "format": "prose",
    "entities": {"Planta Uno": "plant", "Planta Dos": "plant"},
    "global_constraints": ["preserve exact figures and names"],
    "unique_terms": [],
    "no_repeat": False,
    "answer_keys": [["10000"], ["412"], ["1250"], ["10600"]],
    "required_items": ["Planta Uno", "Planta Dos", "10000", "412", "1250", "10600"],
    "weights": {"coverage": 0.4, "qa": 0.4, "seam_free": 0.2},
    "L_target": 15, "F": 2,
    "max_out_tokens": 500,
    "explicit_crossings": 4,
    "material": LONGFORM_MATERIAL,
    "instruction_mono": "Read the annual review above. Answer this question with ONE short factual answer, using only the material: What is the combined annual production of the two plants, and what is the company revenue?",
    "instruction_frag": "You are assigned PART of an annual review. Summarise YOUR assigned sentences faithfully, preserving every figure and entity name. Do not draw conclusions about parts you were not given.",
}

# ------------------------------------------------------- 8. chain ----------

CHAIN = {
    "id": "chain_refusal",
    "name": "Cómputo secuencial (el router debe rechazar)",
    "kind": "chain",
    "decomposable": False,
    "sequential": True,
    "depth": 3,
    "objective": "Compute quarterly totals from monthly revenues, then the annual total, then write a one-paragraph analysis.",
    "format": "prose",
    "entities": {},
    "global_constraints": [],
    "unique_terms": [],
    "no_repeat": False,
    "answer_keys": [["1179"]],
    "required_items": ["1179"],
    "weights": {"qa": 0.8, "seam_free": 0.2},
    "L_target": 4, "F": 0,
    "max_out_tokens": 200,
    "explicit_crossings": 0,
    "material": ("Monthly revenues: Jan 88, Feb 92, Mar 101, Apr 95, May 99, "
                 "Jun 104, Jul 97, Aug 93, Sep 102, Oct 98, Nov 105, Dec 105. "
                 "The quarterly totals are the sums of each three-month block. "
                 "The annual total is the sum of the four quarterly totals."),
    "instruction_mono": "Step 1: compute the four quarterly totals from the monthly revenues. Step 2: compute the annual total. Step 3: write one paragraph analysing the revenue pattern. Show all numbers.",
    "instruction_frag": "",
    "perfect_answer": "Quarterly totals are 281, 298, 292 and 308, and the annual total is 1179. Revenue rose through mid-year, dipped in late summer, and finished strongest in the fourth quarter.",
}



# ------------------------------------------- 3b/3c. más variantes de tabla --

PORTFOLIO_Q1_ROWS = [
    ("Aurora", "equity", 58.3, +2.1), ("Borealis", "equity", 51.7, +8.4),
    ("Caravel", "bonds", 47.2, -1.6), ("Dorado", "commodities", 43.9, +6.2),
    ("Estuario", "equity", 39.5, -0.7), ("Farallón", "bonds", 36.8, +3.3),
    ("Glaciar", "commodities", 33.4, +10.1), ("Helios", "equity", 30.6, +1.9),
    ("Islote", "bonds", 28.9, -2.8), ("Jácara", "commodities", 26.4, +5.5),
    ("Kaizen", "equity", 24.7, +4.6), ("Levante", "bonds", 22.1, -3.4),
    ("Mirador", "equity", 20.8, +0.9), ("Nautilus", "commodities", 19.2, +7.7),
    ("Orilla", "bonds", 17.5, -1.2), ("Pampero", "equity", 15.6, +2.9),
]
PORTFOLIO_TOTAL = round(sum(r[2] for r in PORTFOLIO_Q1_ROWS), 1)   # 516.6

INVENTORY_ROWS = [
    ("Bearing K-77", "spares", 34.2, +1.4), ("Gasket H-12", "spares", 31.8, +5.9),
    ("Panel Z-40", "electrical", 29.6, -2.2), ("Coupling D-8", "mechanical", 27.1, +8.3),
    ("Valve V-9", "mechanical", 25.4, -0.9), ("Relay R-3", "electrical", 23.7, +4.4),
    ("Motor M-22", "electrical", 21.9, -3.6), ("Sensor S-5", "instrumentation", 20.3, +6.8),
    ("Pump P-14", "mechanical", 18.6, +2.7), ("Filter F-31", "spares", 17.2, -1.8),
    ("Cable C-60", "electrical", 15.8, +7.6), ("Bracket B-2", "mechanical", 14.4, +0.8),
    ("Switch W-7", "electrical", 13.1, -2.9), ("Gauge G-18", "instrumentation", 11.9, +5.2),
    ("Hose H-4", "mechanical", 10.7, -1.1), ("Seal S-11", "spares", 9.4, +3.3),
]
INVENTORY_TOTAL = round(sum(r[2] for r in INVENTORY_ROWS), 1)     # 325.1


def _make_table_task(tid, name, objective, rows, total, top_a, top_b,
                     preamble, req_extra):
    return {
        "id": tid, "name": name, "kind": "table_summary",
        "decomposable": True, "sequential": False,
        "objective": objective, "format": "prose",
        "entities": {r[0]: r[1] for r in rows},
        "global_constraints": ["use exact entity names and numbers from the material",
                               "do not invent rows that are not in the material"],
        "unique_terms": [], "no_repeat": False,
        "answer_keys": [[f"{total:.1f}"], [top_a], [top_b]],
        "required_items": [f"{total:.1f}", top_a, top_b, rows[0][0], req_extra],
        "weights": {"coverage": 0.25, "qa": 0.25, "numeric": 0.2,
                "seam_free": 0.2, "repetition": 0.1},
        "numeric_keys": _table_numeric(rows, total, top_a, top_b)[0],
        "key_numeric": _table_numeric(rows, total, top_a, top_b)[1],
        "L_target": 10, "F": 2, "max_out_tokens": 220,
        "explicit_crossings": 2,
        "preamble": preamble,
        "material": _table_material(preamble, rows),
        "instruction_mono": ("Read the material above. Write ONE coherent paragraph "
                             "of 6-8 sentences summarising it: state the total value, "
                             "the two entries with the largest changes (with their "
                             "numbers), and the overall pattern."),
        "instruction_frag": ("You are assigned PART of a table. Summarise YOUR "
                             "assigned statements in 2-3 sentences: report the exact "
                             "names, values and changes mentioned there. Do not invent "
                             "entries and do not write an overall conclusion."),
        "perfect_answer": (f"The table totals {total:.1f}. {top_a} moved "
                           f"{abs(next(r for r in rows if r[0] == top_a)[3]):.1f} "
                           f"percent to {next(r for r in rows if r[0] == top_a)[2]:.1f}, "
                           f"and {top_b} moved "
                           f"{abs(next(r for r in rows if r[0] == top_b)[3]):.1f} "
                           f"percent to {next(r for r in rows if r[0] == top_b)[2]:.1f}. "
                           f"{rows[0][0]} leads the list at {rows[0][2]:.1f}, while "
                           f"{req_extra} also appears in the material. The pattern "
                           "splits between advancing and retreating entries."),
    }


PORTFOLIO_Q1 = _make_table_task(
    "portfolio_q1", "Snapshot de cartera Q1 (16 posiciones)",
    "One coherent paragraph summarising the first-quarter portfolio: the total value, the two largest movers, and the pattern by asset class.",
    PORTFOLIO_Q1_ROWS, PORTFOLIO_TOTAL, "Glaciar", "Borealis",
    ["The first-quarter snapshot covers sixteen positions across the mandate.",
     "The figures below are final and audited against the custodian statement.",
     "The snapshot combines the equity book with the bond sleeve and the commodities overlay.",
     "All values are in millions and all changes are against the previous quarter."],
    "Caravel")

INVENTORY_SNAPSHOT = _make_table_task(
    "inventory_snapshot", "Inventario técnico (16 repuestos y equipos)",
    "One coherent paragraph summarising the technical inventory: the total stock value, the two items with the largest changes, and the pattern by category.",
    INVENTORY_ROWS, INVENTORY_TOTAL, "Coupling D-8", "Cable C-60",
    ["The technical inventory lists sixteen stock lines across spares, electrical, mechanical and instrumentation.",
     "The counts below were verified during the November stocktake.",
     "The inventory is valued in thousands of units and changes are against the previous quarter.",
     "Electrical lines dominate the list while instrumentation remains the smallest category."],
    "Motor M-22")



# ------------------------------------------- 3d–3g. más variantes de tabla --

PORTFOLIO_Q2_ROWS = [
    ("Aster", "equity", 61.2, +1.8), ("Bernal", "equity", 57.9, +7.6),
    ("Camelia", "bonds", 53.4, -2.2), ("Delfín", "commodities", 49.8, +5.9),
    ("Eucalipto", "equity", 46.1, -0.6), ("Fucsia", "bonds", 42.7, +3.1),
    ("Gardenia", "commodities", 39.3, +9.4), ("Hortensia", "equity", 36.5, +1.2),
    ("Iris", "bonds", 33.8, -3.7), ("Jazmín", "commodities", 30.4, +6.3),
    ("Laurel", "equity", 28.2, +4.4), ("Magnolia", "bonds", 25.9, -1.5),
    ("Nardo", "equity", 23.1, +0.7), ("Olivo", "commodities", 20.6, +8.8),
    ("Palmera", "bonds", 18.4, -2.6), ("Quinoa", "equity", 16.7, +3.9),
]

PORTFOLIO_Q3_ROWS = [
    ("Albatros", "equity", 74.6, +2.4), ("Balandra", "bonds", 70.1, -1.9),
    ("Cormorán", "commodities", 66.8, +6.7), ("Duna", "equity", 62.3, +10.2),
    ("Estrella", "bonds", 58.9, -3.1), ("Faro", "commodities", 54.4, +4.5),
    ("Gaviota", "equity", 51.7, +1.3), ("Horizonte", "bonds", 47.9, -0.8),
    ("Isla", "commodities", 44.2, +7.9), ("Junco", "equity", 41.6, +2.8),
    ("Kril", "bonds", 38.5, -4.4), ("Llano", "commodities", 35.9, +5.6),
    ("Marea", "equity", 32.4, +0.9), ("Niebla", "commodities", 29.8, +8.1),
    ("Ola", "bonds", 27.3, -2.2), ("Pluma", "equity", 24.7, +3.5),
]

INVENTORY_MACHINERY_ROWS = [
    ("Actuator A-12", "mechanical", 41.3, +2.2), ("Bearing B-9", "mechanical", 38.7, -1.4),
    ("Compressor C-4", "mechanical", 35.2, +9.6), ("Drive D-15", "electrical", 32.8, +3.7),
    ("Exciter E-2", "electrical", 30.4, -2.8), ("Flywheel F-7", "mechanical", 28.9, +5.3),
    ("Gearbox G-11", "mechanical", 26.5, +1.1), ("Hoist H-3", "mechanical", 24.6, -0.7),
    ("Impeller I-8", "mechanical", 22.7, +8.4), ("Jack J-5", "mechanical", 20.9, +4.2),
    ("Kiln K-1", "mechanical", 19.4, -3.5), ("Latch L-10", "mechanical", 18.1, +6.9),
    ("Motor M-16", "electrical", 16.8, +2.6), ("Nozzle N-6", "mechanical", 15.2, -1.9),
    ("Oiler O-13", "mechanical", 13.7, +5.8), ("Pinion P-4", "mechanical", 12.3, +0.8),
]

INVENTORY_SPARES_ROWS = [
    ("Adapter S-21", "spares", 28.4, +1.6), ("Belt B-14", "spares", 26.9, +7.3),
    ("Clip C-7", "spares", 24.5, -2.1), ("Disc D-18", "spares", 22.6, +4.8),
    ("Elbow E-9", "spares", 20.8, +0.9), ("Flange F-23", "spares", 19.3, -3.2),
    ("Gasket G-16", "spares", 17.7, +6.4), ("Hub H-5", "spares", 16.2, +2.5),
    ("Insert I-11", "spares", 14.8, -1.3), ("Joint J-19", "spares", 13.4, +5.1),
    ("Key K-8", "spares", 12.1, +0.4), ("Lock L-15", "spares", 10.9, -2.7),
    ("Mount M-2", "spares", 9.7, +8.2), ("Nut N-12", "spares", 8.6, +3.3),
    ("O-Ring O-6", "spares", 7.5, -0.9), ("Plug P-17", "spares", 6.4, +2.1),
]

NEW_TABLES = {
    "portfolio_q2": (PORTFOLIO_Q2_ROWS, "Gardenia", "Iris",
                     ["The second-quarter snapshot covers sixteen positions across the mandate.",
                      "The figures below are final and reconciled with the custodian statement.",
                      "The snapshot combines the equity book with the bond sleeve and the commodities overlay.",
                      "All values are in millions and all changes are against the previous quarter."],
                     "Camelia"),
    "portfolio_q3": (PORTFOLIO_Q3_ROWS, "Duna", "Kril",
                     ["The third-quarter snapshot covers sixteen positions across the mandate.",
                      "The figures below are final and audited against the custodian statement.",
                      "The snapshot mixes the equity book, the bond sleeve and the commodities overlay.",
                      "All values are in millions and all changes are against the previous quarter."],
                     "Estrella"),
    "inventory_machinery": (INVENTORY_MACHINERY_ROWS, "Compressor C-4", "Kiln K-1",
                            ["The machinery inventory lists sixteen stock lines across mechanical and electrical equipment.",
                             "The counts below were verified during the November stocktake.",
                             "The inventory is valued in thousands of units and changes are against the previous quarter.",
                             "Mechanical lines dominate the list while electrical lines remain the smaller category."],
                            "Exciter E-2"),
    "inventory_spares": (INVENTORY_SPARES_ROWS, "Mount M-2", "Flange F-23",
                         ["The spares inventory lists sixteen stock lines of replacement parts.",
                          "The counts below were verified during the November stocktake.",
                          "The inventory is valued in thousands of units and changes are against the previous quarter.",
                          "Mounting hardware dominates the list while sealing parts remain the smaller category."],
                         "Disc D-18"),
}

for tid, (rows, top_inc, top_dec, preamble, req_extra) in NEW_TABLES.items():
    total = round(sum(r[2] for r in rows), 1)
    globals()[tid.upper()] = _make_table_task(
        tid, f"Tabla {tid} (16 entradas)",
        "One coherent paragraph summarising the table: the total value, the largest increase and the largest decrease, and the pattern by category.",
        rows, total, top_inc, top_dec, preamble, req_extra)



# ------------------------------------------- 3h–3o. escala de enrutabilidad --

NEW_SCALE = {
    "portfolio_q4": (
        [("Auriga", "equity", 63.4, +2.9), ("Betelgeuse", "equity", 59.8, +7.1),
         ("Cassiopeia", "bonds", 55.2, -1.7), ("Deneb", "commodities", 51.6, +5.4),
         ("Electra", "equity", 48.9, -0.4), ("Fomalhaut", "bonds", 44.3, +3.8),
         ("Gacrux", "commodities", 41.7, +9.9), ("Hadar", "equity", 38.2, +1.5),
         ("Izar", "bonds", 35.6, -3.9), ("Jabbah", "commodities", 32.9, +6.1),
         ("Kochab", "equity", 29.4, +4.7), ("Lesath", "bonds", 26.8, -1.2),
         ("Mimosa", "equity", 24.1, +0.6), ("Nunki", "commodities", 21.5, +8.3),
         ("Polaris", "bonds", 18.9, -2.5), ("Regulus", "equity", 16.3, +3.4)],
        ["The fourth-quarter snapshot covers sixteen positions across the mandate.",
         "The figures below are final and reconciled with the custodian statement.",
         "The snapshot combines the equity book with the bond sleeve and the commodities overlay.",
         "All values are in millions and all changes are against the previous quarter."],
        "Cassiopeia"),
    "portfolio_q5": (
        [("Alder", "equity", 68.7, +1.3), ("Birch", "equity", 64.2, +8.6),
         ("Cedar", "bonds", 60.8, -2.9), ("Dogwood", "commodities", 57.4, +4.2),
         ("Elm", "equity", 53.1, -0.9), ("Fir", "bonds", 49.6, +2.7),
         ("Ginkgo", "commodities", 46.3, +10.4), ("Hawthorn", "equity", 42.8, +0.8),
         ("Ironwood", "bonds", 39.5, -4.6), ("Juniper", "commodities", 36.2, +5.9),
         ("Kapok", "equity", 33.7, +3.6), ("Larch", "bonds", 30.4, -1.8),
         ("Maple", "equity", 27.9, +2.1), ("Nutmeg", "commodities", 24.5, +7.7),
         ("Oak", "bonds", 21.8, -3.1), ("Poplar", "equity", 19.2, +4.4)],
        ["The fifth-quarter snapshot covers sixteen positions across the mandate.",
         "The figures below are final and audited against the custodian statement.",
         "The snapshot mixes the equity book, the bond sleeve and the commodities overlay.",
         "All values are in millions and all changes are against the previous quarter."],
        "Cedar"),
    "bond_municipal": (
        [("Muni A-201", "general-obligation", 44.6, +1.9), ("Muni B-205", "revenue", 41.2, -2.4),
         ("Muni C-208", "general-obligation", 38.7, +4.6), ("Muni D-211", "revenue", 36.1, +8.9),
         ("Muni E-214", "general-obligation", 33.5, -1.1), ("Muni F-217", "revenue", 31.8, +3.2),
         ("Muni G-220", "general-obligation", 29.4, -3.7), ("Muni H-223", "revenue", 27.9, +6.4),
         ("Muni I-226", "general-obligation", 25.3, +0.7), ("Muni J-229", "revenue", 23.6, -2.8),
         ("Muni K-232", "general-obligation", 21.4, +5.1), ("Muni L-235", "revenue", 19.8, +2.5),
         ("Muni M-238", "general-obligation", 18.2, -1.6), ("Muni N-241", "revenue", 16.7, +7.3),
         ("Muni O-244", "general-obligation", 15.1, +0.9), ("Muni P-247", "revenue", 13.6, -2.2)],
        ["The municipal bond book lists sixteen issues across general-obligation and revenue credits.",
         "The registry below is the audited version, reconciled with the trustee's ledger.",
         "All amounts are in millions and changes are against the previous quarter.",
         "General-obligation credits dominate the book while revenue credits remain the smaller sleeve."],
        "Muni A-201"),
    "bond_corporate": (
        [("Corp 2026-A", "investment-grade", 52.3, +2.2), ("Corp 2026-B", "high-yield", 48.7, -3.3),
         ("Corp 2027-A", "investment-grade", 45.9, +5.8), ("Corp 2027-B", "high-yield", 42.4, +9.7),
         ("Corp 2028-A", "investment-grade", 39.8, -1.4), ("Corp 2028-B", "high-yield", 37.1, +4.1),
         ("Corp 2029-A", "investment-grade", 34.6, -2.6), ("Corp 2029-B", "high-yield", 32.2, +6.9),
         ("Corp 2030-A", "investment-grade", 29.7, +0.4), ("Corp 2030-B", "high-yield", 27.3, -4.2),
         ("Corp 2031-A", "investment-grade", 25.8, +3.5), ("Corp 2031-B", "high-yield", 23.4, +1.6),
         ("Corp 2032-A", "investment-grade", 21.9, -1.9), ("Corp 2032-B", "high-yield", 20.1, +5.4),
         ("Corp 2033-A", "investment-grade", 18.6, +0.8), ("Corp 2033-B", "high-yield", 16.9, -2.1)],
        ["The corporate bond book lists sixteen issues across investment-grade and high-yield credits.",
         "The registry below is the audited version, reconciled with the trustee's ledger.",
         "All amounts are in millions and changes are against the previous quarter.",
         "Investment-grade credits dominate the book while high-yield credits remain the smaller sleeve."],
        "Corp 2026-A"),
    "inventory_tools": (
        [("Wrench W-4", "hand-tools", 36.8, +1.7), ("Saw S-9", "hand-tools", 34.2, -1.3),
         ("Drill D-12", "power-tools", 32.5, +7.4), ("Grinder G-3", "power-tools", 30.1, +3.9),
         ("Hammer H-7", "hand-tools", 28.6, -2.5), ("Router R-11", "power-tools", 26.4, +5.2),
         ("Pliers P-2", "hand-tools", 24.9, +0.9), ("Sander S-6", "power-tools", 22.7, -3.8),
         ("Chisel C-8", "hand-tools", 21.3, +6.6), ("Lathe L-5", "power-tools", 19.8, +2.4),
         ("File F-10", "hand-tools", 18.4, -1.5), ("Press P-13", "power-tools", 17.1, +8.1),
         ("Vice V-1", "hand-tools", 15.7, +0.5), ("Welder W-14", "power-tools", 14.2, -2.9),
         ("Cutter C-15", "hand-tools", 12.8, +4.3), ("Hoist H-16", "power-tools", 11.4, +1.1)],
        ["The tool inventory lists sixteen stock lines across hand-tools and power-tools.",
         "The counts below were verified during the November stocktake.",
         "The inventory is valued in thousands of units and changes are against the previous quarter.",
         "Hand-tools dominate the list while power-tools remain the smaller category."],
        "Drill D-12"),
    "inventory_electrical": (
        [("Breaker B-8", "protection", 40.6, +2.6), ("Contactor C-3", "control", 38.4, -1.8),
         ("Fuse F-12", "protection", 36.9, +5.3), ("Relay R-17", "control", 34.5, +8.8),
         ("Switchgear S-2", "protection", 32.8, -0.7), ("Timer T-6", "control", 30.2, +4.7),
         ("Capacitor C-11", "protection", 28.7, -3.4), ("Inverter I-4", "control", 26.3, +6.2),
         ("Rectifier R-9", "protection", 24.8, +1.9), ("Solenoid S-13", "control", 22.4, -2.6),
         ("Transformer T-1", "protection", 20.9, +7.5), ("Regulator R-5", "control", 19.3, +0.6),
         ("Meter M-7", "protection", 17.8, -1.2), ("Choke C-14", "control", 16.2, +3.7),
         ("Battery B-10", "protection", 14.9, +0.3), ("Starter S-16", "control", 13.5, -2.3)],
        ["The electrical inventory lists sixteen stock lines across protection and control equipment.",
         "The counts below were verified during the November stocktake.",
         "The inventory is valued in thousands of units and changes are against the previous quarter.",
         "Protection equipment dominates the list while control equipment remains the smaller category."],
        "Contactor C-3"),
    "fleet_metrics": (
        [("Vehicle V-01", "truck", 41.7, +1.4), ("Vehicle V-02", "van", 39.2, -2.1),
         ("Vehicle V-03", "truck", 37.6, +6.8), ("Vehicle V-04", "van", 35.4, +3.2),
         ("Vehicle V-05", "truck", 33.9, -0.8), ("Vehicle V-06", "van", 31.5, +5.9),
         ("Vehicle V-07", "truck", 29.8, -3.6), ("Vehicle V-08", "van", 27.4, +8.4),
         ("Vehicle V-09", "truck", 25.6, +2.3), ("Vehicle V-10", "van", 23.8, -1.7),
         ("Vehicle V-11", "truck", 21.4, +7.1), ("Vehicle V-12", "van", 19.9, +0.5),
         ("Vehicle V-13", "truck", 18.3, -2.4), ("Vehicle V-14", "van", 16.8, +4.6),
         ("Vehicle V-15", "truck", 15.2, +1.2), ("Vehicle V-16", "van", 13.7, -1.1)],
        ["The fleet report lists sixteen vehicles with their utilisation scores.",
         "The figures below were compiled from the telematics system in November.",
         "Scores are in percent of available kilometres and changes are against the previous quarter.",
         "Trucks dominate the fleet while vans remain the smaller group."],
        "Vehicle V-01"),
    "sales_regions": (
        [("North Region", "retail", 45.3, +3.1), ("South Region", "wholesale", 42.8, -1.6),
         ("East Region", "retail", 40.4, +7.9), ("West Region", "wholesale", 38.6, +2.7),
         ("Central Region", "retail", 36.1, -2.3), ("Coastal Region", "wholesale", 34.7, +5.4),
         ("Highland Region", "retail", 32.2, -3.9), ("Valley Region", "wholesale", 30.5, +8.6),
         ("Border Region", "retail", 28.9, +1.1), ("Island Region", "wholesale", 26.4, -0.9),
         ("Metro Region", "retail", 24.7, +6.3), ("Rural Region", "wholesale", 22.3, +2.5),
         ("Northern Belt", "retail", 20.8, -1.4), ("Southern Belt", "wholesale", 19.4, +4.8),
         ("Eastern Belt", "retail", 17.6, +0.7), ("Western Belt", "wholesale", 15.9, -2.8)],
        ["The sales report lists sixteen regions with their quarterly revenue.",
         "The figures below were compiled from the billing system in November.",
         "Revenue is in millions and changes are against the previous quarter.",
         "Retail regions dominate the list while wholesale regions remain the smaller group."],
        "South Region"),
}

for tid, (rows, preamble, req_extra) in NEW_SCALE.items():
    globals()[tid.upper()] = _new_table(
        tid, rows, preamble, req_extra,
        f"Tabla {tid} (16 entradas)")

ALL_TASKS = {
    "table_outturn": TABLE_OUTTURN,
    "table_bonded": TABLE_BONDED,
    "long_report": LONG_REPORT,
    "fan_qa": FAN_QA,
    "constrained_composition": CONSTRAINED_COMPOSITION,
    "extraction_grid": EXTRACTION_GRID,
    "longform": LONGFORM,
    "chain_refusal": CHAIN,
    "portfolio_q1": PORTFOLIO_Q1,
    "inventory_snapshot": INVENTORY_SNAPSHOT,
    "portfolio_q2": PORTFOLIO_Q2,
    "portfolio_q3": PORTFOLIO_Q3,
    "inventory_machinery": INVENTORY_MACHINERY,
    "inventory_spares": INVENTORY_SPARES,
    "portfolio_q4": PORTFOLIO_Q4,
    "portfolio_q5": PORTFOLIO_Q5,
    "bond_municipal": BOND_MUNICIPAL,
    "bond_corporate": BOND_CORPORATE,
    "inventory_tools": INVENTORY_TOOLS,
    "inventory_electrical": INVENTORY_ELECTRICAL,
    "fleet_metrics": FLEET_METRICS,
    "sales_regions": SALES_REGIONS,
}
