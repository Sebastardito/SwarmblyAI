---
status: current
lang: es
kind: exploratory
---

# Resultados — prueba de olvido (F-forget) y prueba A/A de reproducibilidad

**10–11 de octubre de 2026 · Enmienda 6 (c) de
`PREREGISTRATION_BENCH_R1X_ES.md`, confirmada antes de correr, con las
Enmiendas 7, 10–12 y 15 · pruebas exploratorias de mecanismo y
reproducibilidad: no emiten veredictos sobre H-C1 · digests verificados
contra `lce_validation/data/model_digests.json`**

Este documento reemplaza la versión del 10 de octubre, que reportaba una
corrida anterior a las Enmiendas 7–12 (13 celdas válidas, abstención
0.359 → 0.718, AA1 100 % idénticas) y la equivalencia «15 de 15 con las
wikis de R13». Esas cifras se retiran; las vigentes salen de las corridas
de la configuración confirmatoria y se describen abajo.

| Corrida | Commit | Python | Salidas |
|---|---|---|---|
| F-forget | `a210e57` | 3.11.17 (`.venv` bloqueado) | `results/bench_forget/` |
| A/A | `a05b234` | 3.9.6 (desviación; Enmienda 15.1) | `results/aa_test/` |

Ambas usan la digestión nativa con semilla y el parser tolerante
(Enmiendas 7 y 10), en una sola pasada (la doble pasada de la Enmienda 11
se revirtió en la 12). Las cifras de conducta conformes al preregistro y
la comparación con la confirmatoria de R13 están en
`results/bench_forget/analysis.json`; `run_derive` y
`tests/test_doc_figures.py` las comprueban.

## 1. F-forget: ¿olvidar una fuente borra lo aprendido de ella?

Para cada usuario (5) y digestor (qwen2.5:3b, llama3.2:3b, gemma2:2b) se
construyeron tres wikis: W_full, digerida con todas las fuentes `.md`;
W_forget, la misma tras `Wiki.forget_source("teach/knowledge/borrada.md")`;
y W_never, digerida en la misma corrida sin esa fuente.

**Estructura.** Las 15 celdas pasan S1 (cada W_full tiene entre 1 y 7
claims ancladas a la fuente borrada). En todas, W_forget no conserva
ninguna claim anclada a la fuente olvidada (S2 = 0) y no pierde ni cambia
ninguna claim de otras fuentes (S3 = 0). Lo mismo en el barrido que olvida,
una por una, cada fuente de cada W_full: 116 olvidos, residuo 0 y daño
colateral 0. Como `forget_source` borra por anclaje, cero es lo esperado:
S2 y S3 verifican que la implementación hace lo que la especificación dice
sobre wikis reales, no un efecto empírico. **Veredicto estructural
preregistrado: se sostiene.**

**Equivalencia con no haberla digerido nunca (S4, descriptiva).** W_forget
coincide con la W_never de la misma corrida en 8 de 15 wikis (Jaccard medio
0.956), y el contexto que ambas entregan a las preguntas es idéntico en el
70.8 % de los casos. Un análisis posterior a los datos compara además con
las wikis de la confirmatoria de R13, digeridas en otra corrida sin la
fuente: coinciden 0 de 15 (W_forget) y 0 de 15 (W_never). Las diferencias
vienen de que la digestión no es reproducible corrida a corrida en este
stack (AA2, sección 2; Enmienda 12), no del olvido: S2 y S3 muestran que
`forget_source` no deja nada de la fuente ni toca lo demás, pero la
igualdad exacta con una wiki que nunca la vio no se puede comprobar
mientras la digestión no sea determinista.

**Conducta.** Abstención en las 5 preguntas sobre la fuente borrada, con el
prompt, la recuperación y la rúbrica de R13 (15 celdas × 3 respondedores):

| Wiki | Abstención |
|---|---|
| W_full | 0.289 |
| W_forget | 0.778 |
| W_never | 0.756 |

forget − full = **+0.489 [+0.333, +0.644]** y forget − never = +0.022
[+0.000, +0.067] (bootstrap agrupado por pregunta). B1 (la wiki completa se
abstiene al menos 0.10 menos que la que nunca vio la fuente) y B2 (el
olvido es completo en conducta: la abstención con W_forget supera a la de
W_full y queda a ±0.10 de la de W_never) se cumplen. El 88.9 % de las
respuestas con W_forget y W_never son idénticas.

**Lectura.** Esto es lo que el tipo `deleted` de R13 no podía medir (N2):
aquí la wiki sí había aprendido de la fuente, la olvidó y se comporta como
si nunca la hubiera tenido. Son 5 preguntas, así que la potencia es baja y
el resultado es de mecanismo, no de magnitud. Tampoco es una comparación
con el RAG: en un RAG, olvidar una fuente es quitar el archivo del índice.
Lo que F-forget muestra es que la wiki, que transforma las fuentes en
claims, conserva esa propiedad.

## 2. A/A de reproducibilidad (R14 1.2–1.4)

AA1 y AA2 se evalúan contra las salidas de la confirmatoria (Enmienda
10 c); AA2 compara dos corridas de la digestión nativa con semilla
(Enmienda 7).

| Prueba | Resultado | Criterio |
|---|---|---|
| AA1 generación a T = 0 (brazo A2 repetido sobre las preguntas v1–v3 de los usuarios propios que la confirmatoria contiene: las 126 de la Enmienda 6 sin las 3 de N1, 123 × 3 respondedores = 369 respuestas) | 98.4 % idénticas en los primeros 200 caracteres; exactitud 0.707 → 0.710 (Δ +0.0027) | **falla** (requiere ≥ 99 %) |
| AA2 digestión (segunda digestión de las 15 wikis frente a las W_never de F-forget) | 8 de 15 conjuntos idénticos; Jaccard medio 0.961 | **falla** (requiere ≥ 14 de 15) |
| AA3 semilla a T = 0.7 (qwen2.5:3b, 20 temas × 3 semillas × 2 repeticiones) | endpoint nativo 100 % idénticas (efectiva); compatible con OpenAI 80 % (no efectiva) | la semilla nativa se adoptó para la digestión (Enmienda 7) |
| AA4 homogeneidad entre repeticiones | Δ media −0.0011 [−0.0067, +0.0047] | **pasa** (≤ 0.01) |

**El criterio de re-corrida de R14 no queda cerrado** (Enmienda 12, como
negativo documentado). La medida estocástica (AA4) es estable; la
generación a T = 0 casi lo es, pero no alcanza el umbral contra una
corrida hecha horas antes (en la corrida del 10 de octubre, contra el
piloto, fue 100 %); la digestión no es reproducible corrida a corrida
aun con semilla. La AA2 de esta tabla además compara una digestión con
Python 3.11.17 (F-forget) con otra con 3.9.6 (A/A), así que mezcla el
no determinismo del servidor con un cambio de entorno.

## 3. Desviaciones declaradas

1. La A/A corrió con Python 3.9.6, no con el 3.11 bloqueado que pide la
   Enmienda 6 (Enmienda 15.1); F-forget sí usó el `.venv`.
2. La comparación de W_forget con las wikis de R13 no estaba
   preregistrada; se reporta como análisis posterior a los datos.
3. El script de corrida se ajustó antes de empezar para aceptar el nombre
   `nomic-embed-text:latest` (commit `eca8f88`; `586eb21` en la
   procedencia, anterior a la purga de pesos: ver
   `COMMIT_MAP_2026-10-10.md`); no afecta a ninguna medida.

*Texto CC BY 4.0.*
