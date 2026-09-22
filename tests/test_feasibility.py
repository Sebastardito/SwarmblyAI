"""La frontera de factibilidad: el corpus, los brazos y el presupuesto.

Es la primera prueba del proyecto en la que la arquitectura PUEDE ganar, y la
diseñé yo después de escribir un documento que decía que el planteamiento estaba
inclinado en su contra. Estos tests existen sobre las dos formas concretas en
que eso podría corromperse: elegir `W` para que el resultado salga, y darle al
baseline obvio una versión de paja.

Ver `docs/PREREGISTRATION_feasibility.md`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "scripts" / "run_ollama.sh"


def _load(name: str):
    # Registrado en sys.modules ANTES de ejecutarlo: `@dataclass` con
    # `field(default_factory=...)` resuelve anotaciones mirando
    # `sys.modules[cls.__module__]`, y un modulo cargado a mano que no este ahi
    # revienta con un AttributeError que no menciona ninguna de las dos cosas.
    import sys
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


gen = _load("make_longform")
feas = _load("run_feasibility")


# --------------------------------------------------------------------------
# El corpus: la frontera se mide, no se supone
# --------------------------------------------------------------------------


def test_the_corpus_straddles_the_declared_budget():
    """Dos tamaños por debajo del presupuesto y tres por encima.

    Si todo cupiera, el diseño no probaría nada -- que es exactamente la
    condición de invalidación 2. Si nada cupiera, no habría con qué comparar.
    """
    prompts = gen.build()
    fits = {n for n in gen.SIZES
            if all(p["prompt_tokens"] <= gen.NODE_BUDGET_TOKENS
                   for p in prompts if p["n_rows"] == n)}
    over = {n for n in gen.SIZES
            if all(p["prompt_tokens"] > gen.NODE_BUDGET_TOKENS
                   for p in prompts if p["n_rows"] == n)}
    assert len(fits) >= 2, f"solo {len(fits)} tamaños caben en W"
    assert len(over) >= 2, f"solo {len(over)} tamaños exceden W"
    assert fits | over == set(gen.SIZES), (
        "algún tamaño cae a los dos lados según el documento; la frontera "
        "tiene que ser una propiedad del tamaño, no de la muestra")


def test_the_declared_size_is_well_above_the_frontier():
    prompts = gen.build()
    declared = [p for p in prompts if p["n_rows"] == feas.DECLARED_ROWS]
    assert declared, f"la celda declarada {feas.DECLARED_ROWS} no está en el corpus"
    for p in declared:
        assert p["prompt_tokens"] > gen.NODE_BUDGET_TOKENS * 2, (
            "la celda declarada tiene que estar MUY por encima del presupuesto, "
            "no rozándolo: un tamaño al filo mide el redondeo del tokenizador")


def test_the_split_has_the_same_size_distribution_on_both_halves():
    """Un split donde dev tuviera los cortos y final los largos no es un split:
    son dos experimentos con una etiqueta."""
    prompts = gen.build()
    for n_rows in gen.SIZES:
        group = [p for p in prompts if p["n_rows"] == n_rows]
        assert sum(1 for p in group if p["split"] == "dev") == 2
        assert sum(1 for p in group if p["split"] == "final") == 4


def test_the_answer_key_is_computed_from_the_rows():
    """Sin juez y sin modelo en el veredicto: cada respuesta sale del material."""
    import random
    rng = random.Random(0)
    rows = gen._rows(40, rng)
    questions = gen._questions(rows, rng)
    total = next(q for q in questions if q["id"] == "03")
    assert int(total["expected"]) == sum(r["on_hand"] for r in rows)
    largest = next(q for q in questions if q["id"] == "04")
    assert largest["expected"] == max(rows, key=lambda r: (r["on_hand"], r["id"]))["id"]


def test_every_document_has_both_question_classes():
    """La hipótesis se juzga sobre `global`; `local` es el control. Un documento
    sin una de las dos no aporta a ninguno de los dos papeles."""
    for p in gen.build():
        kinds = {q["kind"] for q in p["questions"]}
        assert kinds == {"local", "global"}, f"{p['id']}: {kinds}"


def test_the_digest_covers_the_answer_key():
    """En composición la clave no entraba en el digest porque no existía. Aquí
    la clave ES el veredicto: una clave que cambiara en silencio movería cada
    resultado sin mover un solo prompt."""
    prompts = gen.build()
    before = gen.digest(prompts)
    prompts[0]["key"]["03"]["expected"] = "999999"
    assert gen.digest(prompts) != before


# --------------------------------------------------------------------------
# El baseline obvio, en su mejor versión
# --------------------------------------------------------------------------


def test_chunking_never_splits_a_row():
    """Un troceado que partiera un registro por la mitad estaría amañado a favor
    del protocolo. La prerregistración se compromete a no hacer eso."""
    import random
    rng = random.Random(1)
    rows = gen._rows(300, rng)
    material = gen._table(rows)
    head = "Questions:\n[Q1] ...\n"
    chunks = feas.chunk_rows(material, head, 2048)
    assert len(chunks) > 1
    rebuilt = "\n".join(chunks)
    assert rebuilt == material, "el troceado perdió o alteró material"
    for chunk in chunks:
        for line in chunk.splitlines():
            assert line.startswith("R-") and "reorder_at=" in line, (
                f"fila partida por la mitad: {line[:60]!r}")


def test_the_naive_arm_has_a_reduce_step():
    """Concatenar los parciales y llamarlo respuesta sería un hombre de paja: las
    preguntas globales fallarían por construcción. El map-reduce que escribiría
    cualquiera pasa los parciales a un nodo más."""
    source = (ROOT / "scripts" / "run_feasibility.py").read_text(encoding="utf-8")
    body = source[source.index("def run_naive_chunk"):]
    body = body[:body.index("\ndef ")]
    assert body.count("recorder.generate") >= 2, (
        "el brazo ingenuo debe hacer una llamada de combinación, no concatenar")
    assert "Combine" in body


def test_the_reduce_step_uses_no_oracle_knowledge_of_question_type():
    """Sumar cuando la pregunta es una suma y maximizar cuando es un máximo
    exigiría saber de qué TIPO es cada pregunta -- conocimiento que este brazo
    no tiene y que lo volvería injustamente fuerte."""
    source = (ROOT / "scripts" / "run_feasibility.py").read_text(encoding="utf-8")
    body = source[source.index("def run_naive_chunk"):]
    body = body[:body.index("\ndef ")]
    for leak in ('"kind"', "['kind']", '["expected"]', "doc['key']", 'doc["key"]'):
        assert leak not in body, (
            f"el brazo ingenuo lee {leak}: está usando la clave o el tipo de "
            f"pregunta, que es conocimiento de oráculo")


# --------------------------------------------------------------------------
# El presupuesto: medido, no supuesto
# --------------------------------------------------------------------------


def test_the_monolithic_arm_is_infeasible_and_not_zero_above_the_budget():
    """Un cero se promedia. Un infactible no."""
    doc = {"prompt": "x " * 5000, "key": {}}
    result = feas.run_monolithic_capped(doc, None, budget=2048)
    assert result["feasible"] is False
    assert result["n_nodes"] == 0
    assert "reason" in result


def test_swarmbly_raises_N_until_the_MEASURED_peak_fits():
    """El primer diseño calculaba N desde el troceado ingenuo y daba por hecho
    que los paquetes cabrían. No cabían: 2113 contra 2048 en material de 900
    filas, y la condición 3 se disparó antes de gastar una hora. Un paquete del
    protocolo lleva su cabecera y sus acarreos, así que pesa más."""
    source = (ROOT / "scripts" / "run_feasibility.py").read_text(encoding="utf-8")
    body = source[source.index("def run_swarmbly"):]
    body = body[:body.index("\n\ndef ")]
    assert "recorder.peak_context <= budget" in body
    assert "n_attempts" in body
    assert feas.MAX_NODE_ATTEMPTS >= 2


def test_the_invalidation_conditions_are_evaluated_in_code():
    """Una condición de invalidación que hay que acordarse de comprobar es una
    que se comprueba cuando el resultado no gusta."""
    per_arm = {
        "naive-chunk": {"accuracy_by_kind": {"local": {"rate": 0.5}},
                        "feasible_rate": 1.0, "cells_over_budget": 0},
        "monolithic-capped": {"accuracy_by_kind": {}, "feasible_rate": 1.0,
                              "cells_over_budget": 0},
        "swarmbly": {"accuracy_by_kind": {}, "feasible_rate": 1.0,
                     "cells_over_budget": 3},
    }
    result = feas._invalidations(per_arm, {}, 2048)
    assert result["run_is_readable"] is False
    joined = " ".join(result["conditions_met"])
    assert "1:" in joined and "2:" in joined and "3:" in joined


def test_a_clean_run_reports_itself_readable():
    per_arm = {
        "naive-chunk": {"accuracy_by_kind": {"local": {"rate": 0.95}},
                        "feasible_rate": 1.0, "cells_over_budget": 0},
        "monolithic-capped": {"accuracy_by_kind": {}, "feasible_rate": 0.4,
                              "cells_over_budget": 0},
        "swarmbly": {"accuracy_by_kind": {}, "feasible_rate": 1.0,
                     "cells_over_budget": 0},
    }
    assert feas._invalidations(per_arm, {}, 2048)["run_is_readable"] is True


def test_feasibility_and_accuracy_are_never_combined():
    """Un brazo infactible no es un brazo con puntaje cero, y un solo numero que
    los mezclara diria que a medio camino esta bien."""
    source = (ROOT / "scripts" / "run_feasibility.py").read_text(encoding="utf-8")
    body = source[source.index("def summarise"):]
    body = body[:body.index("\ndef ")]
    assert "feasible_rate" in body and "accuracy_by_kind" in body
    assert "for c in feasible" in body, (
        "la exactitud debe calcularse SOLO sobre las celdas factibles")


# --------------------------------------------------------------------------
# Los tiers
# --------------------------------------------------------------------------


def test_the_feas_tiers_read_the_longform_corpus_and_gate_on_the_dev_run():
    script = RUNNER.read_text(encoding="utf-8")
    for tier in ("run_feas_dev()", "run_feas_final()"):
        start = script.index(tier)
        body = script[start:script.index("\n}\n", start)]
        assert "longform.json" in body
        assert "--budget 2048" in body, "el presupuesto declarado va en la invocación"
    final = script[script.index("run_feas_final()"):]
    final = final[:final.index("\n}\n")]
    assert 'read_dev_run "$dev" "false" "prompts/longform.json"' in final


def test_the_tier_says_out_loud_what_a_null_result_would_mean():
    """Si swarmbly ~= naive-chunk, el hallazgo es que el valor esta en trocear.
    Decirlo antes de correr es lo que impide reescribirlo despues."""
    script = RUNNER.read_text(encoding="utf-8")
    body = script[script.index("run_feas_dev()"):]
    body = body[:body.index("\n}\n")]
    assert "naive-chunk" in body
    assert "EL VALOR ESTA EN" in body or "valor esta en trocear" in body


# --------------------------------------------------------------------------
# El test que faltaba, y que costó tres horas de computo
#
# El corpus salió con ids `[Q1]`..`[Q5]`. `grading.extract_items` -- el unico
# lector de respuestas del proyecto -- reconoce `\d{1,3}` y NO reconoce letras,
# asi que devolvia lista vacia y CADA respuesta de CADA brazo se califico mal.
# monolithic-capped saco 0/2 en preguntas locales sobre documentos de 24 filas
# que tenia enteros en un solo nodo, que es un resultado imposible como fallo de
# capacidad.
#
# La condicion de invalidacion 1 lo atrapo y nada se publico. El ENSAYO no pudo:
# un mock que no sabe contestar produce 0/5 tanto si el calificador funciona
# como si esta ciego, y las dos cosas se ven identicas.
#
# La leccion que no estaba en la doctrina: EL ENSAYO VALIDA LA FONTANERIA, NO LA
# SEMANTICA. Para lo segundo hace falta una respuesta correcta escrita a mano,
# que es lo que sigue.
# --------------------------------------------------------------------------


def _perfect_answer(doc: dict) -> str:
    return "\n".join(f"[{qid}] {spec['expected']}"
                     for qid, spec in doc["key"].items())


def test_a_perfect_answer_scores_five_of_five():
    """Ningun mock puede dar este test: hay que escribir la respuesta correcta.

    Si esto falla, el calificador esta ciego y TODA cifra de este tier es cero
    por construccion, sin importar lo que hagan los modelos.
    """
    for doc in gen.build()[:3]:
        result = feas.grade(_perfect_answer(doc), doc["key"])
        total = sum(c["correct"] for c in result["by_kind"].values())
        asked = sum(c["asked"] for c in result["by_kind"].values())
        assert asked == 5, f"{doc['id']}: se esperaban 5 preguntas, hay {asked}"
        assert total == 5, (
            f"{doc['id']}: una respuesta PERFECTA saco {total}/5. El "
            f"calificador no esta leyendo las respuestas: "
            f"{result['detail']}")


def test_a_wrong_answer_scores_zero():
    """La imagen espejo: un calificador que aceptara cualquier cosa daria 5/5 a
    una respuesta perfecta igual que uno que funciona."""
    doc = gen.build()[0]
    wrong = "\n".join(f"[{qid}] ZZZ-nonsense" for qid in doc["key"])
    result = feas.grade(wrong, doc["key"])
    assert sum(c["correct"] for c in result["by_kind"].values()) == 0


def test_every_question_id_is_one_extract_items_can_read():
    """El corpus y el calificador tienen que hablar el mismo idioma, y el
    calificador es el que no se puede cambiar."""
    from swarmbly_v0.grading import extract_items
    for doc in gen.build()[:5]:
        line = " ".join(f"[{qid}] 1" for qid in doc["key"])
        read = {item_id for item_id, _ in extract_items(line)}
        assert read == set(doc["key"]), (
            f"{doc['id']}: extract_items leyo {sorted(read)} de "
            f"{sorted(doc['key'])}. Las que faltan se califican mal siempre.")


def test_the_prompt_shows_the_same_ids_the_key_uses():
    """Pedirle al modelo `[Q1]` y calificar contra `01` es el mismo defecto con
    un paso mas."""
    for doc in gen.build()[:5]:
        for qid in doc["key"]:
            assert f"[{qid}]" in doc["prompt"], (
                f"{doc['id']}: la clave usa {qid!r} y el prompt no lo pide")
