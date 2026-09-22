---
status: superseded
superseded_by: RESULTS_TABLES_FINAL_CORRECTED.md
reason: >
  Corrida sobre un instrumento defectuoso. El veredicto no cambia -- NO SE
  CUMPLE -- pero todas las cifras se movieron, y la distribución detrás de la
  cifra se movió mucho más.
lang: es
---
# tables-final — el criterio preinscrito NO SE CUMPLE

> **La corrida de abajo (27 de agosto) se hizo con un instrumento DEFECTUOSO y
> se conserva como historia. La medición que se sostiene es
> [`RESULTS_TABLES_FINAL_CORRECTED.md`]
> (RESULTS_TABLES_FINAL_CORRECTED.md), vuelta a correr el 3 de septiembre una
> vez corregidos doce defectos del instrumento. Su veredicto es el mismo — NO SE
> CUMPLE — pero todas las cifras se movieron, y la distribución detrás de la
> cifra se movió mucho más.**
>
> No cite ninguna cifra de este archivo. Los defectos, y por qué cada uno era
> unilateral en la dirección de la hipótesis del propio proyecto, están en
> [`REVISION_2026-08-12.md`](REVISION_2026-08-12.md).

## La corrida retirada del 27 de agosto, sin alterar más abajo

**Corrida:** `results/tables-final-20260827-102014`. La mitad final de
`prompts/tables24.json`, digest `0c5cb7e2…`, verificado antes de la corrida.
Dieciséis prompts, ρ = 3.5, N ∈ {2, 8}, k ∈ {1, 3}. τ_sem **heredado** de
`tables-dev-20260827-095758` en 0.680, sin reajustar. Transporte `openai-sdk`,
**0 reintentos**, embeddings no degradados, `harness_validation_only: false`.
80 filas.

**Esta mitad está gastada. No hay una segunda.**

---

## El veredicto

**Declarado antes de la corrida, sin cambios desde la preinscripción original:**
`table_summary` a ρ=3.5, N=2, k=1 cuesta menos de 5 %, con el **límite
superior** de un intervalo al 95 % agrupado por prompt por debajo de 0.05.

| celda | punto | IC 95 % (16 prompts) | veredicto |
|---|---|---|---|
| **N=2, k=1** — *bajo prueba* | **+3.26 %** | **[−0.02 %, +6.93 %]** | **FALLA** |
| N=8, k=1 — *control, debe fallar* | +17.64 % | [+13.33 %, +21.55 %] | falla ✓ |
| N=2, k=3 | +25.80 % | [+17.54 %, +34.43 %] | falla |
| N=8, k=3 | +32.25 % | [+27.90 %, +36.70 %] | falla |

**El criterio no se cumple.** El límite superior es 6.93 % contra un umbral de
5 % — corto por 1.93 puntos, sobre la métrica, la celda, el umbral y el
estimador declarados de antemano.

**El control se portó.** N=8 cuesta +17.6 % con un intervalo que no se acerca al
de N=2. El instrumento discrimina, así que la falla en N=2 es una medición y no
un instrumento que falla todo.

---

## Qué se midió en realidad

El veredicto de arriba es la respuesta a la pregunta que se hizo. No es lo mismo
que «la fragmentación es cara», y la distinción importa.

| estadístico | valor |
|---|---|
| estimación puntual | **+3.26 %** — por debajo del umbral |
| **prompt mediano** | **+1.16 %** |
| límite inferior del intervalo | **−0.02 %** — en cero |
| prompts que cuestan ≤ 0 | **8 de 16** |
| prompts que cuestan < 5 % | 9 de 16 |
| impuesto sobre el puntaje **completo**, costuras incluidas | **−1.19 %** |
| errores de costura por oración | fragmentado **0.062**, baseline **0.081** |

Partir en dos el resumen de una tabla, con este presupuesto de contexto, cuesta
**entre nada y siete por ciento**, lo más probable alrededor de uno a tres. La
mitad de los prompts no muestra costo alguno, y sobre el puntaje que incluye los
defectos de costura la respuesta fragmentada es *mejor* que el baseline sin
fragmentar — con **menos** errores locales de costura por oración que un texto
que no tiene costuras.

El criterio preinscrito exigía certeza de que el costo está por debajo del cinco
por ciento. Dieciséis prompts no entregan esa certeza. Las dos cosas son ciertas
y las dos pertenecen al registro.

### La distribución por prompt

| prompt | impuesto | | prompt | impuesto |
|---|---|---|---|---|
| returns | −7.7 % | | closeout | +5.6 % |
| layover | −5.8 % | | clearance | +6.7 % |
| backlog | −2.5 % | | demurrage | +7.1 % |
| salvage | −2.4 % | | holdover | +8.3 % |
| transit | 0.0 % | | outturn | +8.3 % |
| quarantine | 0.0 % | | transhipment | +9.1 % |
| overspill | 0.0 % | | **bonded** | **+23.1 %** |
| prealert | 0.0 % | | dispatch | +2.3 % |

`bonded` es un valor atípico: él solo levanta la media en 1.3 puntos, y sin él la
media es **+1.94 %** con un límite superior que pasaría el umbral.

**Esa cifra queda registrada y no se usa.** Quitar un valor atípico después de
que un criterio falló, para que pase, es la forma de manual de exactamente
aquello que la partición, el digest congelado y el estimador declarado existen
para impedir. El criterio se nombró de antemano, se aplicó tal como estaba
escrito, y falló. El baseline de `bonded` sacó un 1.000 perfecto, lo que vuelve
cualquier déficit una razón máximamente sensible — un argumento para revisar el
estimador *en un estudio futuro*, declarado antes de que ese estudio corra, y
para nada más aquí.

---

## El mapa de confianza: muerto, ahora sobre dieciséis prompts

Reportado, no declarado — fue degradado tras fallar su primera prueba
independiente.

| clase | dev-1 | dev-2 | **final (n=16)** |
|---|---|---|---|
| agregado *(estaba bajo prueba)* | OR 3.47 | OR 0.26 | **OR 1.24**, IC [0.25, 3.75] |
| local *(control)* | OR 0.56 | OR 0.89 | OR 0.50, IC [0.13, 1.49] |

Tres valores que abarcan un orden de magnitud a lo largo de tres corridas, y un
intervalo que cruza 1.0 sobre la muestra más grande. La exactitud por valor de
acuerdo para las afirmaciones agregadas ahora va 1.000 (n=2) / 0.556 / 0.661 /
0.637 — **más acuerdo no significa más exactitud**.

Declarar esto el 26 de agosto y verlo morir en la mitad dev es lo más claro que
ha comprado la partición: costó una hora de GPU y nunca tocó estos dieciséis
prompts.

---

## Notas del instrumento

- **ρ en N=8 es 3.911 contra un objetivo de 3.5** — 11.7 % por encima, tercera
  corrida consecutiva. El empaquetador se pasa; `rho_floor` es 1.13, así que
  nada lo está forzando. El control N=8 recibió por lo tanto *más* contexto que
  N=2 y aun así costó cinco veces más, lo que es conservador para la conclusión
  que se saca de él. N=2, la celda declarada, queda en 3.392 — dentro de
  tolerancia.
- **`scripts/rescore.py` hace el ida y vuelta de esta corrida en 0.0000.** Los
  offsets guardados del 27 de agosto vuelven exactamente re-puntuable una
  corrida terminada; una corrección futura de la métrica se puede aplicar a
  estas generaciones sin volver a correrlas.
- **El juez aceptó el 100 %** de 1 502 unidades. Cuarta corrida consecutiva. No
  es un instrumento sobre prosa fundamentada y ahí debería retirarse.
- **k=3 cuesta +25.8 % en N=2 y +32.3 % en N=8.** El consenso es caro en toda
  partición medida, y más cuanto más fina la división.

---

## Qué zanja esto, y qué no

**Zanjado.** H1 tal como fue preinscrita — *existe una configuración cuyo costo
de coherencia está por debajo de 5 %* — **no queda demostrada**. La mejor celda
que este proyecto haya producido, medida con un instrumento corregido sobre un
corpus partido antes de que se fijaran los umbrales, cae en +3.3 % con un
intervalo que llega a 6.9 %. El criterio se escribió para poder fallar y falló.

**Sin zanjar, y no reclamable en ninguna dirección.** Si el costo verdadero está
por debajo de 5 %. La estimación puntual dice que probablemente; el intervalo
dice que no demostrablemente. La mitad de los prompts no cuesta nada.

**Lo que lo zanjaría** es un estudio nuevo: un corpus nuevo, más prompts, un
estimador declarado de antemano que sea robusto a un baseline en 1.000, y todo
eso preinscrito antes de correrlo. No ocho prompts más agregados a este — eso es
el mismo estudio, y este estudio está terminado.

**Lo que cambió en los cimientos del proyecto** está en
`docs/RESULTS_TABLES_DEV.md` §8 y se sostiene: el costo es mucho menor de lo que
reportaron cuatro corridas anteriores, porque esas corridas midieron un
instrumento defectuoso; lo que se degrada bajo la fragmentación es la *forma*,
no el *hecho*; y los defectos de costura del brazo fragmentado son menos que los
del baseline en N=2. Un protocolo que parte un documento en dos y pierde entre
uno y tres por ciento de un puntaje de forma, con la fidelidad numérica intacta,
no es el protocolo que describían esos documentos anteriores.
