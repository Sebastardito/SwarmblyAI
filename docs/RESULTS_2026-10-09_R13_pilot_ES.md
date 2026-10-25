---
status: current
lang: es
kind: exploratory
---

# Resultados — piloto exploratorio de R13 (la pregunta decisiva de H-C1)

**9 de octubre de 2026 · preregistro `PREREGISTRATION_BENCH_R1X_ES.md` con
Enmienda 1 · corrida PILOTO EXPLORATORIA: no emite veredictos preregistrados**

> **Aviso (11 de octubre de 2026).** Este piloto queda superado por la corrida confirmatoria de R13 (`RESULTS_2026-10-11_R13_confirm_ES.md`, 251 preguntas). Sus cifras, incluidas las de la sección 7, se conservan como registro del ciclo piloto; las vigentes son las de la confirmatoria.
>
> **Aviso (10 de octubre de 2026).** Las secciones 1 a 6 conservan el historial del ciclo piloto y contienen cifras RETIRADAS por los defectos E1–E3 de la revisión (A3 de un solo digestor, vigencia ordenada al revés, fuente borrada digerida en la wiki). No deben citarse. Las cifras vigentes son las de la sección 7.

**Qué dice el piloto en una línea.** La tubería de los cinco brazos funciona
de punta a punta y la rúbrica por tipo se comporta (abstención en
sin-respuesta ≈ 0.95). La comparación decisiva todavía NO es justa: los
brazos corrieron con presupuestos desiguales (A1 913 tokens, A2 206, A3 111)
y la wiki perdió frente al RAG crudo en casi todo — pero su eficiencia POR
TOKEN es igual a la del RAG (0.380 vs 0.375 por 100 tokens), lo que apunta a
la política de recuperación de la wiki, no a la representación, como el
defecto a corregir.

Modelos: digestores y respondedores qwen2.5:3b, llama3.2:3b, gemma2:2b.
Salidas crudas en `results/bench_r13/results.json` (SHA en el commit).

## 1. Cifras

Exactitud por brazo (91 preguntas × 3 respondedores; A3/A4 con cruzado):

| Brazo | Exactitud | Tokens medios |
|---|---|---|
| A0 sin memoria | 0.117 | 47 |
| A1 documento completo | **0.813** | 913 |
| A2 RAG crudo | 0.773 | 206 |
| A3 wiki | 0.454 | 111 |
| A4 wiki + Γ | 0.476 | 138 |

Por tipo de pregunta (A1 / A2 / A3):

| Tipo | A1 | A2 | A3 | Lectura |
|---|---|---|---|---|
| simple | 0.88 | 0.78 | 0.42 | la wiki pierde en hechos simples |
| cross | 0.67 | **0.80** | 0.20 | el RAG combina mejor dos fuentes |
| updated | 0.73 | **1.00** | 0.22 | el RAG es perfecto en hechos actualizados; la wiki recupera la claim antigua |
| contradiction | 0.33 | 0.20 | 0.22 | todos bajos |
| deleted | 0.53 | 0.80 | 0.56 | el RAG se abstiene más que la wiki |
| unanswerable | 0.93 | 0.93 | 0.98 | todos se abstienen bien |

Cruzado: A3 diagonal 0.458 vs A3 cruzado 0.421 — el digestor ajeno cuesta
~4 puntos; efecto pequeño, requiere la corrida confirmatoria para decidir la
compuerta del digestor.

## 2. Lectura honesta (qué prueba y qué no)

**Lo que el piloto prueba.** La tubería completa (digestión → anclaje → wiki
→ recuperación → los cinco brazos → rúbrica por tipo → contabilidad de
tokens) corre sin errores, la abstención funciona, y las diferencias entre
brazos son grandes y estables.

**Lo que NO prueba (confundidos identificados, todos corregibles antes de la
confirmatoria):**

1. **Presupuestos desiguales.** A3 recibió 111 tokens de contexto frente a
   206 (A2) y 913 (A1). El preregistro exige el mismo presupuesto; el piloto
   no lo igualó y la ordenación A1 > A2 > A3 correlaciona con el tamaño del
   contexto. La eficiencia por token (A3 0.380 ≈ A2 0.375) sugiere que a
   presupuesto igual la brecha se cierra en buena parte.
2. **La política de recuperación de la wiki es el defecto.** En `updated`, la
   wiki tiene DOS claims (la antigua y la nueva) y el BM25 sin criterio de
   vigencia recupera la antigua (0.22 vs 1.00 del RAG). La capa epistémica
   (maturidad, versionado) existe pero el piloto no la usó al recuperar.
   Corrección: recuperación con preferencia por la claim más reciente o de
   mayor madurez, y presupuesto igualado al RAG.
3. **A4 (wiki+Γ) empeora los tipos factuales** (updated 0.20, contradiction
   0.13) — consistente con el costo de exactitud de Γ medido en la corrida 2;
   con el presupuesto igualado y la recuperación corregida se re-mide.

## 3. Consecuencia para el plan

El piloto NO dispara la condición de muerte (es exploratorio y con
presupuestos desiguales), pero deja claro que la confirmatoria sin las dos
correcciones la dispararía por la razón equivocada. La Enmienda 2 congela:
(a) presupuesto de contexto igual para todos los brazos (200 tokens, el del
RAG del piloto); (b) recuperación de la wiki con preferencia de vigencia
(claim más reciente del mismo hecho primero, luego madurez); (c) re-piloto
rápido con las wikis ya cacheadas antes de la confirmatoria de ≥250.

## 4. Re-piloto con presupuesto igual (Enmienda 2)

**Cifras.** A1 0.308 (250 tokens; el documento completo colapsa a 200
palabras — solo funciona cuando cabe entero), A2 0.773 (206), A3 0.451
(226), A4 0.399 (252). Diferencia emparejada **A3 − A2 = −0.322, IC95
[−0.392, −0.253]** (n=273); A4 − A2 = −0.374.

**Por tipo.** `updated`: A2 1.00 vs A3 0.20 (−0.733) — la recuperación por
vigencia NO lo arregló: la claim de la actualización contiene AMBOS valores
en un solo texto («fue 0.036; el valor corregido es 0.041») y el modelo
responde el primero. El defecto es la GRANULARIDAD de la claim (el digestor
propuso una claim por span y el span cubre dos oraciones), lo que viola el
principio de atomicidad que el propio whitepaper exige. `deleted`: A2 0.80
vs A3 0.58 (−0.533) — la wiki recupera la claim vigente relacionada y el
modelo responde en lugar de abstenerse. `unanswerable`: empate (0.93 vs
0.91). `contradiction`: ambos en el piso.

**Lectura.** A presupuesto igual la brecha NO se cerró: la ventaja del RAG
crudo es real en este material (400–700 tokens por usuario, donde el trozo
verbatim gana). La condición de muerte del preregistro («RAG ≥ wiki en el
total Y la wiki no gana en actualización ni olvido») se cumpliría HOY en
este régimen si esto fuera la confirmatoria. Dos defectos de implementación
—no de diseño— quedan identificados antes de juzgar: (a) atomicidad de
claims (dividir por oración), (b) recuperación por hecho (agrupar claims del
mismo hecho y tomar la más reciente). El tercer elemento pendiente es el
subconjunto de corpus largo que el preregistro ya declara: donde el
documento completo NO cabe es el único lugar donde la compresión de la wiki
puede pagar, y el corpus v2 aún no lo incluye.

## 5. Re-piloto de verificación (Enmienda 3: atomicidad + por-hecho + corpus largo)

**Cifras.** A0 0.085 · A1 0.222 (colapsa a 200 palabras) · A2 0.780 · **A3
0.598** · A4 0.365. Emparejado **A3 − A2 = −0.183, IC95 [−0.241, −0.127]**
(n=378). La brecha bajó de −0.322 a −0.183: las reparaciones recuperaron ~14
puntos.

**Por tipo.** `updated`: A3 subió de 0.20 a 0.43 y la diferencia emparejada
quedó en **−0.143 [−0.310, +0.000]** — la atomicidad y la recuperación por
hecho arreglaron exactamente el defecto que apuntaban (el IC toca el cero).
`deleted`: sigue en −0.533 (la wiki recupera la claim vigente relacionada y
el modelo responde en lugar de abstenerse). `cross`: −0.405. `simple`:
−0.153. `unanswerable`: empate.

**Corpus largo (v3): A3 − A2 = −0.286 [−0.390, −0.181]** — la premisa de que
la compresión paga donde el documento no cabe NO se materializó en este
material: el BM25 sobre oraciones crudas encuentra los hechos enterrados
mejor que las claims atómicas. El régimen largo sigue abierto, pero ahora
en contra de la wiki.

**Veredicto del ciclo de pilotos.** Con tres rondas de reparaciones
declaradas, la wiki queda por detrás del RAG crudo en exactitud de respuesta
sobre este material (−0.183), y la condición de muerte del preregistro
(RAG ≥ wiki en el total; sin victoria en actualización ni olvido) se
cumpliría. Lo que el benchmark mide es SOLO exactitud: el valor de la wiki
que queda intacto es el que no se midió —anclaje auditable, tipado,
versionado, capa epistémica, base segura de entrenamiento (I1) y de la
proyección Γ—. La v0.2 debe decir ambas cosas: en QA pura, el RAG simple
gana; la wiki se justifica por su capa epistémica, no por compresión.

## 6. Re-piloto limpio (Enmienda 4: fuentes solo .md + abstención exacta)

**Cifras.** A0 0.079 · A1 0.206 · A2 0.765 · **A3 0.611** · A4 0.378.
Emparejado **A3 − A2 = −0.153, IC95 [−0.209, −0.098]** (n=378).

**Trayectoria de las cuatro rondas declaradas** (A3−A2 por tipo):

| tipo | ronda 1-2 | verificación | LIMPIO |
|---|---|---|---|
| updated | −0.733 | −0.143 | **−0.071 [−0.238, +0.095]** |
| unanswerable | 0.000 | 0.000 | **+0.067** |
| total | −0.322 | −0.183 | **−0.153** |
| deleted | −0.533 | −0.533 | −0.600 |
| v3 largo | — | −0.286 | −0.219 |

**Lectura final del ciclo.** Cada reparación convergió sobre su objetivo: la
atomicidad y la recuperación por hecho llevaron `updated` de −0.733 a un
empate estadístico con el RAG (el IC incluye el cero), y la abstención
exacta volvió a la wiki MEJOR absteniéndose en sin-respuesta (+0.067). El
residuo es estructural: en `cross` (−0.381), `deleted` (−0.600) y el
material largo (−0.219), el trozo verbatim del RAG conserva la respuesta
literal que la claim comprimida no conserva. La condición de muerte se
mantiene en dirección —RAG ≥ wiki en el total; sin victoria de la wiki en
actualización (empate) ni olvido— y el veredicto del preregistro para la
v0.2 es: la justificación por compresión muere; la capa epistémica queda
intacta y sin medir por un benchmark de exactitud.

## 7. Cifras vigentes (re-medidas el 10 de octubre, con E1, E2 y E3 reparados)

Corrida en el commit `ea04c81` (`7363881` en la procedencia, anterior a la purga de pesos: ver `COMMIT_MAP_2026-10-10.md`) con el árbol limpio, digests verificados y las
15 wikis digeridas de nuevo sin la fuente borrada. El intérprete fue Python
3.9.6, una desviación de R14 (el lock fija 3.11). Todas las cifras de esta
sección salen de `results/bench_r13/analysis.json`, que `run_derive`
recalcula desde las celdas guardadas; el intervalo es un bootstrap agrupado
por pregunta (10.000 remuestreos, semilla 20261005).

| Brazo | Exactitud |
|---|---|
| A0 sin memoria | 0.079 |
| A1 primeras 200 palabras | 0.206 |
| A2 RAG crudo | 0.765 |
| A3 wiki (tres digestores) | 0.509 (qwen2.5 0.553 · llama3.2 0.323 · gemma2 0.651) |
| A4 wiki + Γ | 0.471 |

**La wiki frente al RAG.** A3 − A2 = **−0.256 [−0.317, −0.194]** (126
preguntas). Ningún digestor empata con el RAG: gemma2 −0.114 [−0.183,
−0.045], qwen2.5 −0.212 [−0.288, −0.138] y llama3.2 −0.442 [−0.529,
−0.354]. Por tipo: `simple` −0.257 [−0.329, −0.186] (83 preguntas), `cross`
−0.508 [−0.603, −0.405] (14), `updated` −0.341 [−0.563, −0.135] (14),
`contradiction` −0.044 [−0.400, +0.267] (5), `deleted` +0.156 [−0.067,
+0.378] (5) y `unanswerable` +0.089 [−0.067, +0.333] (5). Sin las tres
preguntas con clave superada (N1, Enmienda 6 b) la cifra apenas cambia:
−0.260 [−0.323, −0.198] (123 preguntas).

**La memoria frente a nada.** En las 116 preguntas con respuesta, A3 − A0 =
+0.479 [+0.420, +0.537] y A2 − A0 = +0.767 [+0.704, +0.828]. Tener memoria
local ayuda mucho; la wiki ayuda menos que el RAG crudo.

**El costo de Γ.** A4 frente a la diagonal de A3 del mismo digestor: gemma2
+0.016, llama3.2 −0.008, qwen2.5 −0.063. Es pequeño y depende del
digestor; A4 no se aísla del todo porque comparte la recuperación de A3.

**La abstención, siempre junto con la exactitud (N2).**

| Brazo | Exactitud con respuesta | Abstención `deleted` | Abstención `unanswerable` |
|---|---|---|---|
| A0 | 0.000 | 1.000 | 1.000 |
| A2 | 0.767 | 0.600 | 0.867 |
| A3 qwen2.5 | 0.520 | 0.933 | 0.933 |
| A3 llama3.2 | 0.276 | 0.733 | 1.000 |
| A3 gemma2 | 0.641 | 0.600 | 0.933 |

El brazo que no sabe nada se abstiene siempre, y la wiki de gemma2, la que
más recupera, se abstiene igual que el RAG en `deleted`. El +0.156 viene de
las wikis que recuperan menos. Además, ningún brazo vio nunca la fuente
borrada: `deleted` mide abstención ante información relacionada, no olvido.
Esta sección no afirma que la wiki gane en olvido; eso lo mide la prueba
F-forget (Enmienda 6 c).

**Dónde pierde la wiki.** En las preguntas con respuesta, la clave aparece
en el contexto del RAG en el 99.1 % de los casos y en el de la wiki en el
83.6 % (gemma2), el 81.0 % (qwen2.5) y el 34.5 % (llama3.2). Con esa
cobertura, la wiki de gemma2 convierte casi como el RAG (0.641 sobre 0.836
frente a 0.767 sobre 0.991). La pérdida está en la digestión, que deja fuera
entre el 16 % y el 65 % de las respuestas según el digestor, no en la
representación ni en la respuesta. La cobertura necesita las wikis en caché
(no versionadas) y por eso es la única cifra de esta sección que
`run_derive` no recalcula.

**Nota sobre la Enmienda 4.** Su texto dice que la abstención exacta se aplicó a los brazos de wiki; en el código, el cambio de prompt se aplicó a todos los brazos, y todos se volvieron a correr con él. Las cifras de esta sección son, por tanto, comparables entre brazos.

**Lectura.** En exactitud de preguntas y respuestas sobre este material, el
RAG crudo supera a la wiki y la wiki no gana en actualizaciones: la
dirección de la condición de muerte se mantiene, como piloto y sin
veredicto preregistrado. La causa medida es la cobertura de la digestión,
que depende mucho del digestor. Lo que justifica la wiki (anclaje,
versionado, olvido verificable, base segura para Γ y para entrenar) no lo
mide un benchmark de exactitud. La confirmatoria necesita al menos 250
preguntas, al menos 30 por tipo, el subconjunto de LongMemEval, el corpus
sin las tres claves superadas y la prueba de olvido real.

*Texto CC BY 4.0.*