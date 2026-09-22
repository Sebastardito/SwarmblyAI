"""La rejilla de L, el veredicto y el control, comprobados sin modelos.

La lección más cara de este proyecto está en `docs/POSTMORTEM_2026-09-05_four_tiers.md`
y se resume en una frase: *el ensayo valida la fontanería, no la semántica*. Dos
corridas de feasibility murieron porque el corpus escribía `[Q1]` donde el
calificador esperaba `01`, y el ensayo contra el backend simulado pasó igual,
porque la tubería funcionaba perfectamente sobre datos que nadie podía
calificar.

Así que estas comprobaciones no miran si el runner corre. Miran si la rejilla
separa lo que dice separar, si el veredicto se rehúsa cuando debe, y si el
control puede fallar.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from make_lcurve import L_VALUES, N_VALUES, SIZES, build, cells, digest  # noqa: E402
from run_lcurve import (BASELINE_FLOOR, CONTROL_TOLERANCE,  # noqa: E402
                        L_CURVE_THRESHOLD_POINTS, _invalidations,
                        paired_contrast, verdict)
from swarmbly_v0.experiment import MIN_CLUSTERS_FOR_A_VERDICT  # noqa: E402


# --------------------------------------------------------------------------- #
# La rejilla

def test_every_L_appears_at_more_than_one_N() -> None:
    """Si un L viviera en un solo N, su efecto seguiría confundido con el de N.

    Ésta es la propiedad por la que el corpus existe, así que se comprueba
    aquí y no se confía a la tabla del documento.
    """
    seen: dict[int, set[int]] = {size: set() for size in L_VALUES}
    for n_rows in SIZES:
        for count, size in cells(n_rows):
            seen[size].add(count)
    for size, counts in seen.items():
        assert len(counts) >= 2, (
            f"L={size} sólo aparece con N={counts}. Con un único N, el efecto "
            "de L no es identificable y el corpus no sirve para lo que se "
            "construyó.")


def test_every_N_appears_at_more_than_one_L() -> None:
    seen: dict[int, set[int]] = {count: set() for count in N_VALUES}
    for n_rows in SIZES:
        for count, size in cells(n_rows):
            seen[count].add(size)
    for count, sizes in seen.items():
        assert len(sizes) >= 2, f"N={count} sólo aparece con L={sizes}."


def test_the_declared_cell_has_enough_clusters() -> None:
    """La celda declarada se agrupa sobre los tamaños con más de un L.

    La primera redacción de la prerregistración declaraba la celda en un solo
    tamaño, que da 8 clusters contra un piso de 20: el veredicto se habría
    rehusado en código DESPUÉS de gastar las corridas. Esta comprobación existe
    para que ese error no pueda volver en silencio.
    """
    final = [p for p in build() if p["split"] == "final"]
    with_contrast = [p for p in final if len(cells(p["n_rows"])) > 1]
    assert len(with_contrast) >= MIN_CLUSTERS_FOR_A_VERDICT, (
        f"{len(with_contrast)} documentos finales admiten un contraste de L, y "
        f"el piso son {MIN_CLUSTERS_FOR_A_VERDICT}.")


def test_a_size_only_enters_a_cell_when_the_division_is_exact() -> None:
    for n_rows in SIZES:
        for count, size in cells(n_rows):
            assert count * size == n_rows
            assert size in L_VALUES and count in N_VALUES


def test_the_grid_is_part_of_the_digest() -> None:
    """Cambiar la rejilla sin cambiar el texto tiene que mover el digest.

    La rejilla es parte de lo que se congela. Si no entrara en el digest, el
    gate del tramo final aceptaría una corrida dev hecha sobre otro diseño.
    """
    prompts = build()
    before = digest(prompts)
    prompts[0]["cells"] = [(2, 5), (4, 99)]
    assert digest(prompts) != before


# --------------------------------------------------------------------------- #
# El veredicto

def _rows(n_documents: int, *, high: float, low: float, kind: str = "global",
          asked: int = 4) -> list[dict]:
    out: list[dict] = []
    for index in range(n_documents):
        for label, score, size in (("hi", high, 40), ("lo", low, 10)):
            out.append({
                "prompt_id": f"doc_{index:02d}", "arm": "fragmented",
                "n_rows": 80, "n_tasks": 2 if label == "hi" else 8, "L": size,
                "over_budget": False,
                "by_kind": {kind: {"correct": round(score * asked),
                                   "asked": asked}},
            })
    return out


def test_a_verdict_is_refused_below_the_cluster_floor() -> None:
    contrast = paired_contrast(_rows(5, high=1.0, low=0.0), "global")
    outcome = verdict(contrast)
    assert outcome["refused"]
    assert str(MIN_CLUSTERS_FOR_A_VERDICT) in outcome["why"]


def test_a_real_effect_is_met_on_the_lower_bound() -> None:
    contrast = paired_contrast(_rows(30, high=1.0, low=0.25), "global")
    outcome = verdict(contrast)
    assert not outcome["refused"]
    assert outcome["lower"] > L_CURVE_THRESHOLD_POINTS
    assert outcome["met"]


def test_no_effect_is_not_met() -> None:
    contrast = paired_contrast(_rows(30, high=0.5, low=0.5), "global")
    outcome = verdict(contrast)
    assert not outcome["met"], (
        "Un efecto de cero exacto no puede dar CUMPLIDO. Si esto falla, el "
        "criterio no está mirando la cota inferior.")


def test_a_document_run_at_one_L_contributes_no_contrast() -> None:
    """Un documento con una sola celda no aporta una diferencia de cero.

    Incluirlo con diferencia cero diluiría el efecto hacia cero sin que ningún
    dato lo dijera -- que es la forma más silenciosa de no encontrar nada.
    """
    rows = _rows(3, high=1.0, low=0.0)
    alone = dict(rows[0], prompt_id="solo")  # copia: mutar la original lo aliasa
    assert paired_contrast(rows + [alone], "global") == paired_contrast(rows, "global")


# --------------------------------------------------------------------------- #
# El control

def test_the_control_can_fail() -> None:
    """Un control que no puede fallar no es un control.

    `local` moviéndose con L significa que algo de la tubería se rompe al
    cambiar el tamaño del trozo, y entonces el efecto observado en `global` no
    es sobre la unidad semántica. La corrida tiene que quedar inválida.
    """
    rows = _rows(24, high=1.0, low=0.0, kind="local")
    control = paired_contrast(rows, "local")
    notes = _invalidations(rows, control, budget=2048)
    assert any("CONTROL FALLADO" in note for note in notes), notes


def test_the_control_passes_when_local_is_flat() -> None:
    rows = _rows(24, high=0.75, low=0.75, kind="local")
    control = paired_contrast(rows, "local")
    assert not any("CONTROL FALLADO" in note
                   for note in _invalidations(rows, control, budget=2048))


def test_the_control_tolerance_is_the_declared_one() -> None:
    assert CONTROL_TOLERANCE == pytest.approx(0.05)
    assert L_CURVE_THRESHOLD_POINTS == pytest.approx(0.05)


def test_a_run_where_nothing_exceeds_the_budget_says_so() -> None:
    """Sin frontera, la comparación es de coste y no de factibilidad.

    No invalida nada. Se registra porque cambia cómo se lee el resultado, y
    porque la prerregistración lo manda registrar.
    """
    rows = _rows(24, high=0.9, low=0.5)
    rows.append({"prompt_id": "doc_00", "arm": "monolithic", "n_rows": 80,
                 "n_tasks": 1, "L": 80, "over_budget": False, "by_kind": {}})
    notes = _invalidations(rows, paired_contrast(rows, "local"), budget=2048)
    assert any("SIN FRONTERA" in note for note in notes)


def test_a_baseline_at_the_floor_invalidates_the_run() -> None:
    """La condición que faltaba, y que la primera corrida necesitaba.

    `lcurve-dev` del 22 de septiembre terminó sin disparar ninguna condición y
    con el control marcando +0.000, que se lee como "nada se rompió". El brazo
    monolítico había sacado 1 de 72 en preguntas globales. El control marcaba
    cero porque los dos extremos estaban en el piso, no porque la tubería
    estuviera sana: un control que pasa en el piso no es un control.
    """
    rows = _rows(24, high=0.9, low=0.5)
    for index in range(24):
        rows.append({"prompt_id": f"doc_{index:02d}", "arm": "monolithic",
                     "n_rows": 80, "n_tasks": 1, "L": 80, "over_budget": True,
                     "by_kind": {"global": {"correct": 0, "asked": 6}}})
    notes = _invalidations(rows, paired_contrast(rows, "local"), budget=2048)
    assert any("PISO DEL BASELINE" in note for note in notes), notes


def test_a_baseline_with_room_to_move_does_not_invalidate() -> None:
    rows = _rows(24, high=0.9, low=0.5)
    for index in range(24):
        rows.append({"prompt_id": f"doc_{index:02d}", "arm": "monolithic",
                     "n_rows": 80, "n_tasks": 1, "L": 80, "over_budget": True,
                     "by_kind": {"global": {"correct": 4, "asked": 6}}})
    notes = _invalidations(rows, paired_contrast(rows, "local"), budget=2048)
    assert not any("PISO DEL BASELINE" in note for note in notes)
    assert BASELINE_FLOOR == pytest.approx(0.20)
