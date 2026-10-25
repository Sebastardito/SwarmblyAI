---
status: current
lang: es
kind: confirmatory
---

# Resultados — R13 confirmatoria: ¿la wiki anclada supera a una memoria simple?

**11 de octubre de 2026 · preregistro `PREREGISTRATION_BENCH_R1X_ES.md`,
sección 2, con las Enmiendas 7–12 (antes de correr) y 15 (declaraciones de
la revisión, después) · commit `5d0edea` con el árbol limpio, digests
verificados contra `lce_validation/data/model_digests.json`, servidor
Ollama exclusivo · Python 3.9.6 (desviación del 3.11 bloqueado; Enmienda
15.1) · 251 preguntas**

Salidas crudas en `results/bench_r13_confirm/` (`results.json`, con todas
las respuestas; `wikis_cache/`, las 18 wikis digeridas). Las cifras de este
documento salen de `analysis.json`, que regenera
`python -m lce_validation.r13_analysis --dir bench_r13_confirm`; las
comprueban `run_derive` y `tests/test_doc_figures.py`. Este documento
sustituye a la versión del mismo día que declaraba que la wiki «gana el
olvido» y que, por eso, la muerte global «no dispara»; la sección 4
explica por qué.

## 1. Diseño

251 preguntas emparejadas: simples 100, cruzadas 30, actualizadas 31,
contradicciones 30, borradas 30 y sin respuesta 30 (Enmienda 8). Seis
usuarios: los cinco sintéticos propios (v1–v4) y un subconjunto congelado
de LongMemEval (licencia MIT, 8 preguntas). Las 3 preguntas de N1 se
retiraron antes de correr. Cinco brazos con el mismo presupuesto de 200
tokens de contexto: A0 sin memoria, A1 primeras 200 palabras de las
fuentes, A2 RAG crudo (BM25 sobre oraciones; Enmienda 15.9), A3 wiki LCE
(3 digestores × 3 respondedores, cruzado completo) y A4 wiki + Γ (diagonal).
Digestión por el endpoint nativo con semilla y parser tolerante
(Enmiendas 7 y 10); respuestas a temperatura 0.

## 2. Cifras

| Brazo | Exactitud | Tokens de contexto por pregunta |
|---|---|---|
| A0 sin memoria | 0.238 | 54.3 |
| A1 primeras 200 palabras | 0.316 | 257.7 |
| A2 RAG crudo | 0.608 | 245.7 |
| A3 wiki (media del cruzado) | 0.462 | 209.2 |
| A4 wiki + Γ (diagonal) | 0.434 | 235.7 |

A3 por digestor: gemma2 0.510, qwen2.5 0.495, llama3.2 0.381.

**Estadístico primario: A3 − A2 = −0.146 [−0.186, −0.106] por pregunta**
(bootstrap agrupado por pregunta, 10.000 remuestreos, semilla 20261005).
Por digestor: qwen2.5 −0.113 [−0.159, −0.066], llama3.2 −0.227 [−0.286,
−0.170], gemma2 −0.098 [−0.141, −0.057]. Ningún digestor empata.

| Tipo | n | A3 − A2 |
|---|---|---|
| simples | 100 | −0.231 [−0.292, −0.169] |
| cruzadas | 30 | −0.304 [−0.419, −0.189] |
| actualizadas | 31 | −0.222 [−0.358, −0.082] |
| contradicciones | 30 | −0.056 [−0.148, +0.030] |
| borradas | 30 | +0.115 [+0.044, +0.189] |
| sin respuesta | 30 | +0.022 [−0.015, +0.070] |

**Abstención junto con exactitud** (Enmienda 6 b: nunca sola):

| Brazo | Exactitud en preguntas con respuesta | Abstención en `deleted` | Abstención en `unanswerable` |
|---|---|---|---|
| A0 | 0.000 | 1.000 | 0.989 |
| A1 | 0.162 | 0.633 | 0.978 |
| A2 | 0.581 | 0.456 | 0.933 |
| A3 qwen2.5 | 0.401 | 0.633 | 0.956 |
| A3 llama3.2 | 0.257 | 0.578 | 0.978 |
| A3 gemma2 | 0.445 | 0.500 | 0.933 |

**La memoria local ayuda; la wiki ayuda menos que el RAG.** En las 191
preguntas con respuesta, A3 − A0 = +0.368 [+0.323, +0.412] y A2 − A0 =
+0.581 [+0.525, +0.637].

**Dónde se pierde: la cobertura de la digestión.** Fracción de las 191
preguntas con respuesta cuya clave llega al contexto: RAG 94.8 %; wikis de
gemma2 84.3 %, qwen2.5 82.7 % y llama3.2 45.5 %. El orden de la cobertura es
el orden de la exactitud.

**Γ.** A4 − A3 en la diagonal: qwen2.5 −0.036, llama3.2 −0.024, gemma2
+0.016. El costo de Γ en exactitud de QA es pequeño y depende del digestor.

**LongMemEval.** En las 8 preguntas públicas, A3 − A2 = −0.194 (A2 0.375,
A3 0.181): la misma dirección que en el corpus propio. Con n = 8 es una
comprobación de que el resultado no es un artefacto del corpus sintético,
no una estimación.

**Rechazos (sección 2.10).** No se dispara ninguno: los digests coinciden,
responden los 3 respondedores, la wiki más pequeña tiene 39 claims
ancladas (piso 5) y las 251 preguntas son analizables.

## 3. Veredictos preregistrados (sección 2.7)

| Hipótesis | Regla | Veredicto |
|---|---|---|
| R13-H1: la wiki supera al RAG crudo | muere si la estimación ≤ 0 | **muere**: −0.146 [−0.186, −0.106] |
| R13-H2: la wiki gana en actualización y olvido | se sostiene si CI95 > 0 en los tipos 3 y 5; muere si el punto ≤ 0 en ambos | **no concluyente** por la regla: pierde en actualización (−0.222, IC negativo); el +0.115 de `deleted` es el artefacto N2 (sección 4) y no cuenta como victoria en olvido |
| R13-H3: un piso de claims ancladas explica la utilidad | muere sin relación monotónica; si no, la compuerta se retira | **la compuerta se retira como regla**: ninguna celda queda bajo el piso de 5 (mínimo 39, máximo 90 en los usuarios propios), así que el piso no discrimina; hay relación monotónica moderada entre claims ancladas y exactitud (Spearman 0.584, sin LongMemEval) |
| H-C1 muerte global | RAG ≥ wiki en el total Y la wiki no gana en 3 ni 5 | **no dispara por la letra**, y solo por el tipo 5, inválido (N2); sin ese tipo la condición se cumple (sección 4) |

## 4. Lectura

**El tipo `deleted` no mide olvido.** La Enmienda 6 (b) lo declaró antes
de esta corrida (N2) y la confirmatoria mantiene el defecto: ningún brazo
vio nunca la fuente borrada, y A0, sin memoria, se abstiene en el 100 % de
esas preguntas. El +0.115 de A3 sobre A2 en `deleted` mide que la wiki
recupera menos información relacionada que el RAG, que es la misma pérdida
de cobertura vista desde el otro lado (la tabla de abstención la muestra
junto a la exactitud). El olvido se mide en F-forget
(`RESULTS_2026-10-10_Fforget_AA_ES.md`).

**La muerte global.** El texto en español del preregistro, que es el que
firma la procedencia, dice «la wiki no gana en 3 ni 5»; el inglés dice
«does not win on 3 and 5», que se lee como «no gana en ambos» (Enmienda
15.3: las dos versiones divergen). Por la letra del texto en español la
regla no dispara, pero solo por el tipo 5, que es inválido como medida de
olvido. Por el texto en inglés, dispara. Sin el artefacto N2, el RAG crudo
es mejor que la wiki en el total y la wiki no gana en actualización, que
es la situación para la que el preregistro prevé «el diseño se simplifica
(resultado publicable)». La simplificación de la sección siguiente se
apoya en R13-H1 y en la causa medida (la cobertura), no en que la regla
haya disparado.

**Qué se retira y qué queda.** Se retira la justificación de la wiki por
exactitud de pregunta-respuesta: en este material, con modelos de 2–3 B y
un presupuesto de 200 tokens, recuperar oraciones crudas es mejor que
recuperar claims digeridas, y la diferencia se explica por lo que la
digestión pierde. Queda medido, en otras pruebas, lo que la wiki aporta y
el RAG no tiene por construcción: el olvido verificable de una fuente
(F-forget, mecanismo) y la trazabilidad por anclaje. Que esas propiedades
justifiquen el costo de la digestión es una decisión de diseño, no un
resultado de esta corrida. Simplificar el diseño significa que la
recuperación por defecto debe ser sobre las fuentes, con la wiki como capa
de gobierno (procedencia, olvido, entrenamiento) y no como el contexto
principal de respuesta.

## 5. Desviaciones declaradas

1. Python 3.9.6 en lugar del 3.11 bloqueado (Enmienda 15.1).
2. A2 usa BM25 sobre oraciones, no embeddings (Enmienda 15.9).
3. La primera versión de este documento y la del analizador trataban el
   tipo 5 como victoria en olvido y la muerte global con una sola lectura,
   y no advertían que los textos en español e inglés de la regla divergen;
   se corrigieron en la revisión del 11 de octubre (Enmienda 15.2–15.3),
   sin tocar ninguna celda.

*Texto CC BY 4.0.*
