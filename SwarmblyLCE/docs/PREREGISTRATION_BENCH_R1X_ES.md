---
status: current
lang: es
---

# Preregistro consolidado — benchmarks R14, R13 y R11 de la Swarmbly LCE

**5 de octubre de 2026 · escrito ANTES de cualquier corrida real de estos benchmarks**

Este documento congela los diseños de las tres fases siguientes del plan de
validación de la LCE, con sus hipótesis, rúbricas, márgenes, presupuestos y
condiciones de rechazo, antes de que exista un solo dato. Se refiere al
whitepaper LCE v0.1 (secciones 11.1–11.5) y a los resultados ya publicados
(corrida confirmatoria 2; benchmarks exploratorios F1a–F1d con su alcance
declarado). Todo cambio posterior se registra como enmienda numerada en la
sección 7; un cambio silencioso no cuenta.

**Qué cubre:** R14 (reproducibilidad — el entorno que todo lo demás usa),
R13 (la pregunta decisiva de H-C1: ¿una wiki anclada supera a una memoria
simple?), R11 (el adaptador justo: H-C6, H-C10 y el olvido por regeneración),
y el cierre de H-C2 (ρ frente a su ganancia), plegado en R13. **R12 (plano
social) se preregistra por separado** cuando el conjunto canario esté
verificado por hablantes nativos, porque su bloqueante es de calendario, no
de cómputo.

English: `PREREGISTRATION_BENCH_R1X_EN.md`.

---

## 1. R14 — Reproducibilidad (se aplica a todo lo demás)

### 1.1 Entorno fijado

1. El repositorio congelará un archivo de bloqueo de dependencias con las
   versiones exactas y la versión de Python (3.11).
2. Los digests de los modelos de Ollama (las cinco familias y
   `nomic-embed-text`) pasan de ser registrados a ser una COMPROBACIÓN: la
   corrida se DETIENE si un modelo no coincide con el preregistrado, y el
   rechazo se registra como fallo de infraestructura, no como resultado.

### 1.2 Muestreo

1. **Temperatura 0** para toda medida que no dependa de la diversidad:
   preguntas de opción múltiple, respuestas de H-C1 y R13, adherencia de
   léxico, sondas de identidad.
2. Para las medidas que SÍ dependen de la diversidad (homogeneidad entre
   usuarios), se guardan las muestras crudas y el análisis no asume
   apareamiento por semilla (bootstrap por tema, como en la corrida 2).
3. La adopción de un servidor con semilla efectiva (candidato: llama.cpp)
   requiere antes un **test A/A preregistrado**: la diferencia media entre
   dos corridas idénticas debe ser ≤ 0.01 en las medidas estocásticas. Solo
   si pasa se adopta, y se registra como enmienda.

### 1.3 Regeneración y anclaje de cifras

1. Un solo comando (`python -m lce_validation.run_derive`, a construir)
   regenera TODAS las tablas de los documentos RESULTS desde las salidas
   crudas guardadas, sin modelos, y termina con código distinto de cero si
   una cifra no coincide.
2. Los bloques de cifras de los documentos RESULTS pasan a ser GENERADOS
   desde el JSON (nunca editados a mano), y una prueba de CI compara cada
   cifra publicada con su JSON (patrón de `test_published_figures_recompute`
   de Swarmbly).
3. Un ayudante `provenance()` común registra en cada benchmark: versión de
   Ollama, digests de modelos, commit de git y SHA-256 de este preregistro.
4. **Criterio de cierre de R14:** un clon nuevo reproduce las tablas byte a
   byte desde las salidas crudas; al re-ejecutar, los brazos deterministas
   salen idénticos y los estocásticos quedan dentro del ruido A/A (±0.01).

### 1.4 Publicación

Release v0.1.1 en GitHub y depósito en Zenodo (DOI de software), con las
salidas crudas incluidas y el preregistro citado.

---

## 2. R13 — H-C1 decisivo: ¿la wiki anclada supera a una memoria simple?

### 2.1 La pregunta

«¿La memoria ayuda?» ya está respondida (F1a: +0.477 por pregunta, IC95
[+0.407, +0.543]). La pregunta nueva es: **¿una wiki anclada, tipada y
versionada supera a las alternativas simples —documento completo en el
contexto y RAG de fragmentos crudos—, y en qué tipos de pregunta?**

### 2.2 Brazos (misma presupuesto de tokens T por pregunta; T se reporta)

| Brazo | Qué recibe el modelo que responde |
|---|---|
| A0 — sin memoria | solo la pregunta |
| A1 — documento completo | las fuentes del usuario completas, truncadas al presupuesto |
| A2 — RAG crudo | los k fragmentos más cercanos por embeddings (mismos embeddings que la wiki) |
| A3 — wiki LCE | claims ancladas recuperadas de la wiki (BM25), con su tipo y madurez |
| A4 — wiki + Γ | A3 más la proyección en el contrato (el producto completo de la LCE) |

Los tokens enviados se reportan por brazo y por pregunta: son exposición y ρ.

### 2.3 Tipos de pregunta (fijados antes de correr)

1. **Hecho simple** — una clave en una fuente.
2. **Entre documentos** — la respuesta exige combinar dos fuentes.
3. **Hecho actualizado** — una fuente nueva corrige a una antigua; correcto
   = el valor vigente.
4. **Contradicción** — dos fuentes vigentes discrepan; correcto = la versión
   vigente o señalar explícitamente el desacuerdo.
5. **Fuente borrada** — el usuario olvidó la fuente; correcto = ABSTENERSE
   (responder con el hecho borrado = error, peor que equivocarse).
6. **Sin respuesta en memoria** — la pregunta no tiene respuesta en las
   fuentes; correcto = ABSTENERSE.

Rúbrica por tipo en la tabla 2.3-R (parte normativa de este documento):

| Tipo | Correcto | Incorrecto |
|---|---|---|
| 1, 2 | clave de oro presente | ausente o errónea |
| 3 | valor vigente | valor antiguo |
| 4 | versión vigente O desacuerdo señalado | versión antigua sin señalarlo |
| 5, 6 | abstención (o «no está en mis fuentes») | cualquier respuesta con contenido |

### 2.4 Datos

1. **Usuarios propios congelados**: los cinco usuarios del corpus del
   benchmark (SHA congelado), extendidos con una versión 2 por usuario que
   añade: una fuente actualizada, una contradicción, una fuente borrada y
   una pregunta sin respuesta. El generador se congela en el commit de datos.
2. **Subconjunto público**: LongMemEval o LoCoMo, elegido tras verificar su
   licencia; la elección, el SHA-256 del subconjunto y su licencia se fijan
   en la Enmienda 1, antes de correr. Sirve para responder a la crítica de
   que los usuarios sintéticos los escribe el autor.

### 2.5 Diseño cruzado

- **3 digestores** × **3 respondedores** (qwen2.5:3b, llama3.2:3b, gemma2:2b
  — las tres familias con mayor ganancia en F1a) para el brazo A3: separa la
  calidad del digestor de la capacidad de responder y decide la compuerta
  del digestor con datos, no con correlaciones confundidas.
- Los brazos A0–A2 usan los 3 respondedores. A4 usa el cruzado de A3 más Γ.

### 2.6 Tamaño y estadística

- **≥250 preguntas emparejadas** (todas las preguntas pasan por todos los
  brazos), con **≥30 por tipo** para intervalos por tipo.
- Estadístico primario: diferencia emparejada **A3 − A2** (wiki − RAG crudo)
  por pregunta, con bootstrap agrupado por pregunta (10.000 remuestreos,
  semilla 20261005). Secundarios: A3 − A1, A4 − A3, y el desglose por tipo.
- Potencia declarada: con pares discordantes ≈ 30 %, n = 250 detecta una
  diferencia de 0.10 con margen holgado.

### 2.7 Reglas de decisión

| Hipótesis | Se sostiene | Muere | Si no |
|---|---|---|---|
| R13-H1: la wiki supera al RAG crudo | CI95 de A3−A2 > 0 en el total | estimación puntual ≤ 0 | no concluyente |
| R13-H2: la wiki gana en actualización y olvido | CI95 > 0 en los tipos 3 y 5 | punto ≤ 0 en ambos | no concluyente |
| R13-H3 (compuerta del digestor): un piso de claims ancladas explica la utilidad | la utilidad cae bajo el piso propuesto en el cruzado | sin relación monotónica incluso en el cruzado | la compuerta se retira como regla |
| H-C1 muerte global | — | RAG crudo ≥ wiki en el total Y la wiki no gana en 3 ni 5 | el diseño se simplifica (resultado publicable) |

### 2.8 C2-bis (misma corrida)

Placebo igualado en CANTIDAD de instrucción (no solo en forma) y ≥5 usuarios
que difieren en ≥2 rasgos. H-C17a se sostiene si la reducción de homogeneidad
por proyección supera al placebo con CI95 > 0. Cierra el matiz principal de
la corrida 2.

### 2.9 Cierre de H-C2: ρ frente a su ganancia (misma corrida)

Con las wikis digeridas en R13 y el camino de despacho de Swarmbly
(planificador + packer reales, ruta parametrizable), se mide por tarea el par
**(ganancia de adherencia con Γ, Δρ)**. Regla de compensación preregistrada:
**la proyección sobrevive si la fracción de tareas con ganancia > 0 Y
Δρ ≤ 10 % es ≥ 0.8**; se reporta el diagrama completo por tarea. Sin
umbrales adicionales.

### 2.10 Rechazos

Se niega si: un modelo no coincide con su digest; menos de 3 respondedores
responden; alguna wiki tiene < 5 claims ancladas; hay < 200 preguntas
analizables; más del 10 % de las respuestas no se pueden calificar.

---

## 3. R11 — El adaptador justo (H-C6, H-C10, LC6)

Corre DESPUÉS de R13: el lote sale de las afirmaciones entrenables de una
wiki ya validada.

### 3.1 Lote y tareas

1. El lote se construye SOLO con `ExampleBuilder` a partir de afirmaciones
   TRAINABLE (preferencia, estilo, procedimiento) — nunca hechos (I1) — y con
   repaso entremezclado.
2. Las tareas de prueba están redactadas de otra forma y no se cruzan con el
   lote: **≥30 por usuario × 3 usuarios** (los tres primeros del corpus), con
   intervalo de confianza.
3. El sub-brazo **sin repaso** (H-C10) entrena el mismo lote sin los
   ejemplos de repaso: una configuración extra por adaptador.

### 3.2 Familias base y semillas

- Dos familias: **qwen2.5-3b** (pesos no distribuidos; licencia
  qwen-research) y **granite-3.1-2b** (Apache-2.0; verificar antes de
  congelar — enmienda).
- **2 semillas de entrenamiento** por adaptador; la tercera se corre solo si
  las dos primeras discrepan en más de 0.05 (MLX no es determinista; la
  varianza entre semillas se reporta).
- Presupuesto declarado: 2 familias × 3 usuarios × 2 semillas × 2 (repaso)
  = **24 entrenamientos** de ≤ 500 iteraciones.

### 3.3 Brazos (misma información por brazo)

base · recuperación + Γ (BM25 sobre la wiki completa del usuario) ·
adaptador · adaptador + recuperación.

### 3.4 Reglas de decisión

| Hipótesis | Se sostiene | Muere |
|---|---|---|
| H-C6 | la diferencia adaptador − recuperación tiene cota inferior del IC > 0 y media ≥ +0.10 en ≥2 de 3 usuarios | cota ≤ 0 en 2 de 3 → la capa 2 se retira (condición de muerte del roadmap) |
| H-C10 (repaso) | el brazo sin repaso olvida ANTES el material consolidado que el brazo con repaso (punto de cruce posterior con repaso) | sin diferencia → la homología CLS vuelve a vocabulario |
| LC6 (olvido) | tras `forget` de una fuente y regeneración, el hecho olvidado vuelve al nivel del base (equivalencia ±0.10) y la adherencia de estilo persiste | el hecho persiste en el adaptador → «olvido verificable» se retira |
| I1 (fuga) | SIN recuperación, el adaptador no responde hechos del usuario mejor que el base (equivalencia ±0.10) | el adaptador supera al base en hechos → I1 violada y el lote se reconstruye |

### 3.5 Opción pública

Un subconjunto de LaMP (el benchmark de personalización de OPPU [5]) si su
licencia lo permite y sus temas no se solapan con las wikis; se fija por
enmienda con SHA. Hace el resultado comparable con la literatura.

### 3.6 Instrumentos que se prueban en simulación ANTES de medir

El calificador de abstención (tipos 5–6 de R13), el calificador de
contradicción (tipo 4), el procedimiento de equivalencia de I1/LC6 (debe
detectar una fuga inyectada), el test A/A del muestreador, y el anclaje de
cifras generadas (1.3.2). Ninguno decide nada antes de pasar su simulación.

---

## 4. Qué NO cubre este preregistro

R12 (plano social) — requiere el canario verificado; se preregistra aparte.
La selección del subconjunto público (R13) y de la segunda familia base
(R11) — pendientes de licencia; entran por enmienda antes de correr. El
juicio de modelos sobre la calidad de redacción queda fuera: la calificación
es determinista cuando el oro lo permite, y un juez LLM solo se usará como
medida secundaria con auditoría humana de una muestra, y con una familia
distinta de las respondedoras.

---

## 5. Orden de ejecución

R14 (entorno y regeneración) → R13 (corrida decisiva + C2-bis + ρ) → R11
(adaptador, con los lotes de las wikis de R13) → R12 (aparte). Cada corrida
confirmatoria exige el árbol limpio, los digests verificados y este
preregistro confirmado, como en la corrida 2.

---

## 6. Referencias

[W] Whitepaper LCE v0.1, secciones 11.1–11.5. [5] Tan et al. 2024 (OPPU).
[LaMP] Salemi et al. 2024. [LongMemEval / LoCoMo] a confirmar con licencia
(enmienda). [Swarmbly] whitepaper v2, secciones 5 y 15, para la ruta de
despacho y la definición de ρ.

---

## 7. Enmiendas

**Enmienda 1 — 9 de octubre de 2026, antes de correr.** La primera corrida de
R13 es un PILOTO EXPLORATORIO sobre los usuarios propios v1+v2 (91 preguntas:
60 de F1a + 31 etiquetadas por tipo), con los cinco brazos, el cruzado 3×3 y
la rúbrica por tipo. No emite veredictos preregistrados: su función es
validar la tubería y calibrar costos. La corrida CONFIRMATORIA de ≥250
preguntas queda condicionada a las enmiendas 2 (corpus ampliado a ≥30 por
tipo, con SHA) y 3 (subconjunto público con licencia verificada — LongMemEval
es MIT y es el candidato; LoCoMo tiene términos propios sin licencia estándar
y queda descartada salvo revisión legal). El presupuesto de tokens del brazo
A1 (documento completo) se fija en 2.400 palabras truncadas para el piloto y
se reporta por pregunta. Cualquier cambio se registra aquí con fecha y razón antes
de correr; un cambio silencioso no cuenta.*

**Enmienda 2 — 9 de octubre de 2026, después del piloto y antes del
re-piloto.** El piloto identificó dos confundidos; se corrigen así:
(a) presupuesto de contexto IGUAL para todos los brazos: 200 tokens (el del
RAG del piloto), incluido A1 que se trunca a las primeras 200 palabras;
(b) recuperación de la wiki POR VIGENCIA: entre las 10 claims más cercanas
por BM25 se ordena por la fecha explícita más tardía de su fuente (las
fuentes con fecha van antes de las que no la tienen), luego por madurez y
luego por score. El re-piloto re-corre solo los brazos A1, A3 y A4 (A0 y A2
no cambian y sus celdas se heredan del piloto) con las wikis ya cacheadas.
La Enmienda 3 (subconjunto público) sigue pendiente antes de la
confirmatoria.

**Enmienda 3 — 9 de octubre de 2026, después del re-piloto y antes del
re-piloto de verificación.** El re-piloto (Enmienda 2) midió A3−A2 = −0.322
a presupuesto igual y localizó dos defectos de implementación y un régimen
ausente. Se reparan antes de juzgar: (a) ATOMICIDAD — el digestor procesa
sub-pasajes de 3 oraciones y el prompt prohíbe fundir hechos de oraciones
distintas (el piloto midió una claim con ambos valores de una actualización,
contra el principio atómico del propio whitepaper); (b) RECUPERACIÓN POR
HECHO — entre las claims recuperadas, si una claim fechada comparte ≥2
palabras de contenido con otra, la anterior se descarta (la actualización
sustituye a la antigua); (c) CORPUS LARGO — cada usuario gana un documento
de 193–408 palabras con 7 preguntas cuyas respuestas están más allá del
presupuesto de 200 palabras de A1 (el régimen donde la compresión puede
pagar; los documentos multi-mil palabras entran en la ampliación de la
confirmatoria). El re-piloto de verificación re-digiere las wikis (el
digestor cambió) y re-corre los cinco brazos sobre las 126 preguntas.

**Enmienda 4 — 9 de octubre de 2026, después del re-piloto de
verificación y antes de la re-medición limpia.** Se encontró CONTAMINACIÓN
de fuentes: el espacio de fuentes escaneaba todo el directorio del usuario e
ingirió los archivos de preguntas del benchmark (`questions*.json`, con sus
claves de oro) como fuentes de la wiki — la wiki contenía respuestas
filtradas y la comparación no era limpia. Se corrige: las fuentes del
usuario son SOLO documentos `.md` (`build_wiki(suffixes={".md"})`). La
misma contaminación afecta al benchmark F1a (mismo `build_wiki`): su cifra
central (+0.477) queda SUPERSEDIDA hasta la re-medición limpia, que se
relanza junto con el re-piloto de R13. `bench_rho` usó las mismas wikis pero
mide TAMAÑO de proyección (aritmética), no contenido: su veredicto se
mantiene y se re-ejecuta por limpieza. Además: la abstención de los brazos
de wiki exige ahora que el contexto contenga la respuesta EXACTA (apunta al
tipo `deleted`, donde la wiki respondía con la claim vigente relacionada).

**Enmienda 5 — 9 de octubre de 2026, antes del piloto R11.** La segunda
familia base es granite-3.1-2b-instruct, licencia **Apache-2.0** (verificada
en la ficha del modelo). LC6 (olvido por regeneración) se difiere a la
confirmatoria de R11: requiere el flujo de olvido completo (`forget` +
regeneración) y se declara aquí en lugar de improvisarlo. El piloto R11
cubre H-C6 (cuatro brazos), H-C10 (repaso sí/no) y la prueba de fuga I1
(equivalencia ±0.10, instrumento probado en simulación).

**Enmienda 6 — 10 de octubre de 2026, después de la revisión de R13 y
ANTES de correr la prueba de olvido y la prueba A/A.** Tiene tres partes.

*(a) Declaración de reparaciones posteriores a los datos.* La revisión
del 9–10 de octubre encontró defectos de implementación que cambiaban cifras
publicadas, y se repararon después de ver los datos: E1 (el resumen de R13
sobrescribía digestores y A3 quedaba solo con gemma2), E2 (la recuperación
por vigencia ordenaba al revés y A3 no usaba la recuperación por hecho de la
Enmienda 3), E3 (la fuente borrada se digería en la wiki y no en el RAG), E4
(F1a seguía ingiriendo los `questions*.json`) y E5 (A4 se comparaba contra
A3 de un solo digestor). Las cifras afectadas se retiran y se sustituyen por
las re-medidas el 10 de octubre; ninguna de estas reparaciones cambió la
rúbrica ni los umbrales. Desde ahora cada reparación lleva una prueba que
falla si el defecto vuelve (`tests/test_r13_repairs.py`).

*(b) Dos defectos del material, declarados y no corregidos en silencio.*
N1: tres preguntas «simples» de la v1 (andres: razón de riesgos 0.85;
carmen: Manantial +6.8; mara: F_ST 0.036) tienen como clave el valor que
`actualizacion.md` declara superado; la clave no se cambia (sería editar el
oro después de ver los datos): F1a y R13 se reportan con y sin esas tres
preguntas, y la confirmatoria las retira del corpus antes de correr. N2: en
R13, el tipo `deleted` no mide olvido, porque ningún brazo vio nunca la
fuente borrada; se reinterpreta como «sin respuesta con información
relacionada» y, como en `unanswerable`, la abstención premia al brazo que
recupera menos (A0, sin memoria, obtiene 1.00). Desde ahora la abstención se
reporta junto con la exactitud en las preguntas con respuesta del mismo
brazo, nunca sola.

*(c) Prueba de olvido (F-forget) y prueba A/A, preregistradas aquí.*

**F-forget.** Para cada usuario (5) y digestor (qwen2.5:3b, llama3.2:3b,
gemma2:2b): W_full = wiki digerida con TODAS las fuentes `.md`, incluida
`borrada.md`; W_forget = W_full tras `Wiki.forget_source` de esa fuente (el
mecanismo de la SPEC 7.8.1); W_never = wiki digerida en la misma corrida sin
esa fuente. Medidas estructurales (sin respondedores; principales): S1
comprobación de manipulación, W_full tiene ≥1 claim anclada a la fuente (si
no, la celda se rechaza); S2 residuo, claims de W_forget ancladas a la fuente
olvidada (debe ser 0 en el 100 % de las celdas); S3 daño colateral, claims de
W_full no ancladas a esa fuente que faltan o cambian en W_forget (debe ser 0
en el 100 %); S4 equivalencia, igualdad del conjunto de claims de W_forget y
W_never y del contexto que cada una entrega a las 126 preguntas de R13
(descriptiva: depende del determinismo de la digestión, que mide la A/A).
Barrido: S2 y S3 se repiten olvidando cada una de las fuentes de cada W_full.
Medidas de conducta (secundarias, potencia baja: 5 preguntas × 3 × 3): tasa
de abstención en las preguntas sobre la fuente borrada con W_full, W_forget
y W_never, mismo prompt y rúbrica que R13. B1 (manipulación): la abstención
con W_full debe ser al menos 0.10 menor que con W_never; si no, la prueba de
conducta no es informativa y se declara así. B2: el olvido es completo en
conducta si la abstención con W_forget supera a la de W_full y queda a
±0.10 de la de W_never. **Veredictos:** el olvido estructural se sostiene si
S2 = 0 y S3 = 0 en todas las celdas no rechazadas y en todo el barrido; se
falsifica si alguna celda deja residuo o daño colateral.

**A/A.** AA1 (generación determinista): se repite el brazo A2 de R13 (126
preguntas × 3 respondedores, temperatura 0, mismo contexto) y se compara con
las respuestas guardadas (primeros 200 caracteres, que es lo que guardó la
corrida); pasa si ≥ 99 % son idénticas y la exactitud no cambia más de 0.01.
AA2 (digestión determinista): las W_never de F-forget se comparan con las
wikis guardadas de R13 (mismo digestor, mismas fuentes); pasa si el conjunto
de claims coincide en ≥ 14 de 15 wikis. AA3 (semilla): qwen2.5:3b escribe a
T = 0.7 los 20 temas de C2 con las semillas 1000–1002, dos veces con las
mismas semillas, por el endpoint compatible con OpenAI y por el nativo
(`/api/generate`, `options.seed`); la semilla es efectiva en un endpoint si
≥ 95 % de los textos se repiten idénticos. AA4 (medida estocástica): la
homogeneidad entre las tres semillas por tema (embeddings
`nomic-embed-text`) se calcula en las dos repeticiones del endpoint
compatible con OpenAI; pasa si la diferencia media entre repeticiones es
≤ 0.01 en valor absoluto (IC por bootstrap sobre temas, reportado). **R14
queda cerrado en su criterio de re-corrida** si AA1, AA2 y AA4 pasan; un
servidor con semilla se adopta solo si AA3 pasa, por enmienda.

**Comunes.** Ambas pruebas corren con el entorno bloqueado (Python 3.11 del
`.venv` del repositorio), comprueban los digests contra
`lce_validation/data/model_digests.json` antes de empezar y se niegan si no
coinciden, registran su procedencia y guardan todas las respuestas
completas. Son exploratorias de mecanismo y reproducibilidad: no emiten
veredictos sobre H-C1.

**Enmienda 7 — 10 de octubre de 2026, ANTES de la re-corrida de AA2.** AA3
mostró que la semilla del endpoint nativo (`/api/generate`, `options.seed`)
es efectiva (100 % idénticas) y la del compatible OpenAI no (80 %). Conforme
a la regla de la Enmienda 6 («un servidor con semilla se adopta solo si AA3
pasa, por enmienda»), la DIGESTIÓN pasa al endpoint nativo con una semilla
derivada del texto del prompt (mismo prompt, misma semilla, mismo orden de
llamadas); los respondedores siguen con el endpoint compatible OpenAI (AA1
lo mostró reproducible). AA2 se redefine como la comparación de DOS corridas
de la digestión determinista (las W_never de F-forget contra una segunda
digestión de las mismas 15 wikis con el mismo backend); su criterio no
cambia (≥14 de 15 conjuntos de claims idénticos). El criterio de re-corrida
de R14 sigue siendo AA1 + AA2 + AA4.

**Enmienda 8 — 10 de octubre de 2026, ANTES de la confirmatoria de R13.**
Congela los datos de la confirmatoria: (a) el corpus propio se extiende con
una versión 4 (120 preguntas: 13 simples, 16 cruzadas, 16 actualizadas, 25
contradicciones, 25 borradas, 25 sin respuesta) y con las fuentes
correspondientes (borrada.md y actualizacion.md extendidas y una nueva
revision_interna.md por usuario); (b) las 3 preguntas de N1 se excluyen de
todas las corridas; (c) el subconjunto público es LongMemEval
(xiaowu0162/longmemeval, licencia MIT, split longmemeval_s, SHA-256 de la
fuente 08d8dad4be43ee20…, verificado): 8 preguntas (7 simples, 1
actualizada) con su sesión relevante + 2 distractoras, y la pregunta
actualizada conserva además la sesión con el valor anterior; el recorte del
haystack completo (~50 sesiones) se declara aquí como decisión de
presupuesto, no como mejora del corpus. El subconjunto congelado está en
lce_validation/fixtures/bench_users/lme/ con SHA-256 ae727be6ff7f29ba… en
lce_validation/data/lme_subset.json. Totales confirmatorios: 251 preguntas
— simples 100, cruzadas 30, actualizadas 31, contradicciones 30, borradas
30, sin respuesta 30 (≥30 por tipo).

**Enmienda 9 — 10 de octubre de 2026, ANTES de la confirmatoria de R11.**
Repara los seis defectos de E6 y fija el diseño de la confirmatoria: (1) el
lote sale de ExampleBuilder SOLO sobre claims entrenables de la wiki
CANÓNICA del usuario (digerida por qwen2.5:3b, el digestor validado de R13)
para ambas familias base; (2) sin colapso: 2 épocas (iters = 2 x ceil(n/2)),
batch 2, lr 1e-4; (3) tareas VÁLIDAS: léxico por preferencia del propio
usuario, registro con oro alcanzable (reglas concretas) y procedimiento con
los umbrales del propio protocolo — nunca reglas completas normalizadas ni
preguntas de otro dominio; ≥30 tareas por usuario con IC por bootstrap
agrupado por tarea; (4) el brazo de recuperación lleva Γ REAL (Projector
sobre las claims recuperadas); (5) I1 usa 10 hechos DEL USUARIO (sus
factuales), adaptador sin recuperación vs base, equivalencia ±0.10; (6)
LC6 se ejecuta: se olvida teach/style de mara, se re-entrena sin sus claims
y la adherencia a las tareas de estilo debe caer hacia el base; (7) H-C10
es una curva de 2 puntos (25 % y 100 % del presupuesto) sobre tareas de
material consolidado (estilo), con y sin repaso. Presupuesto: 2 familias x
3 usuarios x 2 semillas x 2 repasos x 2 puntos = 24 entrenamientos + 2 de
LC6.

**Enmienda 10 — 10 de octubre de 2026, ANTES de la confirmatoria.** (a) El
parser del digestor se hace tolerante: acepta la SECUENCIA de objetos JSON
({..},{..}) que el modelo emite a veces y fusiona sus claims — elimina la
pérdida de sub-pasajes completos por forma de salida. (b) Condición
ambiental de reproducibilidad: la digestión nativa con semilla es
reproducible SOLO con el servidor exclusivo (sin otras solicitudes
concurrentes: la contención de GPU altera la decodificación); la
confirmatoria de R13 y la evaluación de AA2 corren con Ollama sin carga
concurrente, y se declara aquí. (c) AA1 y AA2 se evalúan contra las SALIDAS
DE LA CONFIRMATORIA (el cambio de corpus de la Enmienda 8 invalida la
comparación contra el piloto); el criterio de re-corrida de R14 sigue
siendo AA1 + AA2 + AA4 con sus umbrales (≥99 % idénticas; ≥14/15 wikis;
|Δ homogeneidad| ≤ 0.01).

**Enmienda 11 — 10 de octubre de 2026, ANTES de la confirmatoria.** La
decodificación de Ollama no es bit-reproducible para salidas largas aun con
semilla (AA2: 12-13/15 wikis idénticas, Jaccard 0.985). La digestión pasa a
DOBLE PASADA: cada sub-pasaje se decodifica dos veces (misma semilla) y se
conservan solo las claims presentes en AMBAS decodificaciones; la
intersección filtra la parte variable de la decodificación. Costo: el doble
de llamadas de digestión. El criterio de AA2 (≥14/15) no cambia.

**Enmienda 12 — 10 de octubre de 2026, ANTES de la confirmatoria.** La
doble pasada con intersección (Enmienda 11) EMPEORÓ el acuerdo entre
corridas (AA2: 8/15) y se revierte: la intersección filtra la parte
variable DENTRO de una corrida pero no entre corridas, y reduce el conjunto
de claims. Resultado honesto del ciclo: la digestión de Ollama no es
reproducible corrida a corrida en este stack (AA2 en cuatro configuraciones:
8-13/15 conjuntos idénticos, Jaccard 0.943-0.992); la generación (AA1) y
las medidas estocásticas (AA4) SÍ lo son. **El criterio de re-corrida de
R14 queda ABIERTO como resultado negativo documentado** (limitación del
stack, no del diseño). La confirmatoria de R13 procede con la digestión
nativa con semilla y parser tolerante (la mejor configuración: 12-13/15) y
sus wikis se guardan como artefactos auditables; el preregistro no
condiciona la confirmatoria al cierre de R14.

**Enmienda 13 — 11 de octubre de 2026, durante la confirmatoria de R11
(antes de re-evaluar; no toca el diseño).** La evaluación de R11 migra de la
CLI de MLX a un SERVIDOR MLX persistente por (modelo, adaptador): mismos
pesos, mismos prompts, temperatura 0 y mismos umbrales de oro. La CLI
recargaba el modelo por llamada y granite (2B) tardaba ~45 s por llamada
(~20 h de evaluación); el servidor reutiliza la carga (~1-2 s por llamada).
Los 26 entrenamientos ya completados se reutilizan (reanudación por
adaptador existente); solo se re-ejecutan las evaluaciones. Es un cambio de
mecanismo de ejecución, no del diseño preregistrado.

**Enmienda 14 — 11 de octubre de 2026, después de la PRIMERA corrida de
C2-bis y ANTES de la re-corrida.** La primera corrida quedó INVALIDADA como
instrumentación: la petición al Projector («escribir un texto breve del
usuario») solo recuperaba la claim de registro y producía una Γ de 4 tokens
(verificado: la petición vacía activa el fallback de rasgos amplios del
Projector y produce la Γ completa con el léxico en los 5 usuarios; la
petición «estilo y vocabulario del usuario» aún dejaba el léxico vacío en
un usuario). La re-corrida usa la petición vacía;
el placebo sigue pareado en longitud; los números de la primera corrida se
reportan como comprobación del instrumento, no como veredicto.

**Enmienda 15 — 11 de octubre de 2026, DESPUÉS de las confirmatorias:
declaraciones de la revisión.** No cambia ningún diseño ni umbral; declara
lo que la revisión encontró en las corridas del 10 y 11 de octubre y cómo
se reportan.

1. *Entorno.* La confirmatoria de R13, la de R11, C2-bis, el cierre de H-C2
   y la A/A corrieron con Python 3.9.6, no con el 3.11 bloqueado (R14 1.1);
   solo F-forget usó el `.venv` 3.11. Es una desviación del entorno, no de
   las medidas, y se declara en cada documento.
2. *R13, tipo 5.* El tipo `deleted` de la confirmatoria mantiene el defecto
   N2 (Enmienda 6 b): ningún brazo vio nunca la fuente borrada, las
   preguntas tienen información relacionada en otras fuentes y A0, sin
   memoria, se abstiene en el 100 %. Su +0.115 no es una victoria en
   olvido. El olvido se mide en F-forget.
3. *R13, muerte global.* El texto en español de la sección 2.7, que es el
   que firma la procedencia de las corridas, dice «RAG crudo ≥ wiki en el
   total Y la wiki no gana en 3 ni 5» (no gana en ninguno); el texto en
   inglés dice «does not win on 3 and 5», que se lee como «no gana en
   ambos». Las dos versiones divergen y la divergencia no se había
   advertido. Por la letra del texto en español la regla no dispara, y
   solo por el tipo 5, que la Enmienda 6 (b) declaró inválido antes de
   correr (punto 2); por la del texto en inglés, dispara. Se reportan las
   dos lecturas y ninguna decisión de diseño se apoya en que la regla haya
   disparado.
4. *R11.* En las 1454 celdas de la confirmatoria el adaptador y el modelo
   base dan los mismos aciertos, y en las 720 tareas el mismo texto byte a
   byte, aunque los pesos LoRA son distintos de cero: el adaptador no se
   aplicó en la evaluación (el servidor MLX recibe el nombre del modelo
   base en cada petición, y la evaluación usa completions sin la plantilla
   de chat del entrenamiento). La corrida se rechaza por falla de
   manipulación, como la corrida 1 de C2. La próxima corrida exige una
   comprobación previa: el adaptador debe cambiar la salida en sus propios
   ejemplos de entrenamiento antes de evaluar nada.
5. *C2-bis.* La implementación calcula la homogeneidad entre las tres
   semillas de un mismo usuario y tema, no entre usuarios, y no tiene brazo
   sin contrato; no prueba H-C17a tal como la define la sección 2.8. Los
   números de la primera corrida, que la Enmienda 14 dice reportar, no se
   conservaron.
6. *Cierre de H-C2.* La ganancia se midió como exactitud de QA (A4 − A3), no
   como adherencia; y la regla «fracción de tareas con ganancia > 0 y Δρ ≤
   10 % ≥ 0.8», escrita en este preregistro, es casi inalcanzable con
   ganancias binarias por tarea. Además, la implementación no usa el
   planificador ni el packer de Swarmbly que pide la sección 2.9: Δρ se
   calcula por aritmética de palabras (tokens de Γ por fragmento sobre los
   tokens del contexto); la ganancia por tarea sale de un solo par
   digestor = respondedor (el diccionario por pregunta conserva la última
   celda de la diagonal), y la Γ se proyecta con la petición «resumir el
   material del usuario» sobre la wiki de qwen2.5. El resultado se reporta
   como descripción (en QA, Γ añade ρ sin mejorar la exactitud) y H-C2
   queda sin decidir para la escritura.
7. *A/A.* AA1 contra la confirmatoria: 98.4 % idénticas (n = 369), por
   debajo del umbral del 99 %; AA2: 8 de 15. R14 sigue abierto (Enmienda 12).
8. *Historial.* Los pesos de los 50 adaptadores de R11 (derivados en parte
   de Qwen2.5-3B-Instruct, licencia qwen-research) y sus lotes se habían
   confirmado en el repositorio; se purgaron del historial antes de
   publicar. `docs/COMMIT_MAP_2026-10-11.md` traduce los identificadores.
9. *Brazo A2.* La sección 2.2 define A2 como los k fragmentos más cercanos
   por embeddings; desde el piloto, A2 recupera oraciones crudas con BM25
   (el mismo recuperador léxico que A3 usa sobre las claims). La desviación
   no se había declarado. Hace la comparación A3 − A2 más pareja (mismo
   recuperador, distinto material), pero A2 no es el RAG por embeddings
   que el preregistro describe; un RAG por embeddings queda sin medir.

*Texto CC BY 4.0; código AGPL-3.0-or-later.*
