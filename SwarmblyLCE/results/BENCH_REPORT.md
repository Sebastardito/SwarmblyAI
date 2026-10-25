---
status: current
lang: es
kind: exploratory
---

# Reporte integrado de benchmarks — Swarmbly LCE

*Generado por `lce_validation/bench_report.py` desde los resultados guardados de cada benchmark (regenerable byte a byte con `run_derive`). Ningún número de este reporte proviene de simulaciones: solo de corridas reales (benchmarks) y de la corrida confirmatoria preregistrada (C1/C2).*

## 1. Estado exploratorio agregado

| Pregunta | Evidencia | Estado exploratorio |
|---|---|---|
| H-C1 a escala: ¿la memoria local mejora al modelo del usuario? | ganancia media por pregunta **+0.500** IC95 [+0.420, +0.578] sobre 60 preguntas × 5 familias | **se sostiene (descriptivo)** |
| C1 (control positivo, preregistrado) | exactitud 0.80 con memoria vs 0.00 sin ella | **se sostiene** |
| H-C2 léxico (preregistrado) | adherencia 0.667 con Γ vs 0.033 sin Γ | **se sostiene** |
| H-C17a / H-C17b (preregistrado) | reducción de homogeneidad 0.073 supera placebo; Δ acuerdo de errores 0.039 dentro de ±0.10 | **se sostiene, con matices** |
| H-C2 ρ: ¿la proyección encarece la redundancia? | Δρ por paquete +7.8% (peor, medido); por solicitud ≈+2.6% (estimación aritmética, diseño no implementado) | **con el protocolo actual (Γ en cada paquete) la proyección añade +5.8–7.8 % de ρ (mediana +7 %); la comparación con su ganancia (la condición de muerte real de H-C2) y el costo del diseño por-solicitud o con caché quedan pendientes** |
| H-C6 (adaptador real) | LoRA rank 8 en 36 s; adherencia bruta 0.62 vs 0.38 (brazos NO comparables) | **no concluyente (lote contaminado, brazos no comparables); factibilidad demostrada** |
| H-C11 (dirección, C9-lite) | circuito de adopción por utilidad ejercitado; identidad 1+1 es la misma respuesta dos veces | **señal insuficiente (violaciones totales < 5)** |
| R13 (piloto): ¿la wiki anclada supera a un RAG crudo? | A3 − A2 = **−0.256** [−0.317, −0.194] sobre 126 preguntas, tres digestores × tres respondedores | **el RAG crudo gana en exactitud; la pérdida está en la cobertura de la digestión** |
| R11 (piloto): adaptador justo | conclusiones retiradas (E6: adaptador colapsado, tareas inválidas, sin Γ en el brazo de recuperación) | **sin evidencia; rediseño en la siguiente fase** |
| R12 (exploratorio): plano social | 0/40 por construcción; utilidad implementada como novedad; sin F_ST (E7) | **compatible con la I4, no la mide** |
| R13 CONFIRMATORIA: ¿la wiki anclada supera a un RAG crudo? | A3 − A2 = **−0.146** [−0.186, −0.106] sobre 251 preguntas | **R13-H1 muere**; H2 no concluyente (el tipo `deleted` no mide olvido, N2); H3: la compuerta se retira como regla |
| F-forget: ¿olvidar una fuente borra lo aprendido de ella? | residuo 0, colateral 0; abstención W_full → W_forget ≈ W_never | **el olvido se sostiene (mecanismo)** |
| A/A de reproducibilidad (R14) | generación casi idéntica, digestión no reproducible entre corridas | **R14 abierto (negativo documentado)** |
| C2-bis | mide la homogeneidad entre SEMILLAS de un mismo usuario, no entre usuarios | **no prueba H-C17a (constructo distinto)** |
| Cierre H-C2 (2.9) | ganancia medida en exactitud de QA, no en adherencia; regla inalcanzable con ganancias binarias por tarea | **descriptivo: Γ cuesta ρ y no mejora QA; H-C2 sin decidir para escritura** |
| R11 CONFIRMATORIA: adaptador justo | adaptador y base dan texto idéntico byte a byte en las 720 tareas y los mismos aciertos en las 1454 celdas | **rechazada: falla de manipulación (el adaptador no se aplicó en la evaluación)** |

## 2. Detalle por benchmark


### 2.1 H-C1 a escala (memoria local, 5 familias × 5 usuarios)

**Cifra central.** 60 preguntas (12 por usuario: 5 factuales, 4 de léxico, 3 de procedimiento, con preguntas entre documentos), 5 familias por pregunta. Ganancia media por PREGUNTA **+0.500** con IC95 [+0.420, +0.578] (agrupado por pregunta; por celda: +0.500 [+0.439, +0.561]). Las estadísticas de la wiki por familia y usuario están guardadas en el resultado.

**Por familia:**

- `llama3.2:3b`: ganancia media +0.317 (n=60); afirmaciones ancladas por usuario 24–47 (media 36.2), tasa de anclaje 0.90–1.00
- `qwen2.5:3b`: ganancia media +0.700 (n=60); afirmaciones ancladas por usuario 47–64 (media 54.6), tasa de anclaje 0.98–1.00
- `gemma2:2b`: ganancia media +0.717 (n=60); afirmaciones ancladas por usuario 53–84 (media 63.8), tasa de anclaje 0.98–1.00
- `phi3.5:3.8b`: ganancia media +0.083 (n=24); afirmaciones ancladas por usuario 7–8 (media 7.5), tasa de anclaje 1.00–1.00
- `granite3.1-dense:2b`: ganancia media +0.433 (n=60); afirmaciones ancladas por usuario 30–44 (media 38.4), tasa de anclaje 0.58–0.85

**Por usuario:**

- `andres`: ganancia media +0.533 (n=60)
- `carmen`: ganancia media +0.500 (n=48)
- `julian`: ganancia media +0.417 (n=48)
- `luisa`: ganancia media +0.583 (n=48)
- `mara`: ganancia media +0.467 (n=60)

**Explicación.** La memoria convierte en recuperables preguntas que ningún modelo base puede responder (hechos del usuario, umbrales de su protocolo, términos preferidos). La variación entre familias mezcla dos cosas —la familia digiere Y responde— y la atribución al digestor la separa el diseño cruzado de R13 (sección 2.8), que la explica por la cobertura de la digestión. Solo phi3.5 se separa aquí por el tamaño de su wiki (muchas menos afirmaciones ancladas); entre las otras cuatro, ni el número de afirmaciones ancladas ni la tasa de anclaje ordenan la ganancia. R13-H3 retiró el piso de afirmaciones ancladas como regla: una compuerta, si se adopta, debe medir cobertura contra preguntas reservadas.

**Ajuste propuesto.** Un usuario real; el brazo «memoria + proyección Γ» y el diseño cruzado digestor/respuesta se hicieron en R13 (sección 2.8).

### 2.2 ρ de la proyección (camino de despacho real)

**Cifra central.** Sobre el documento de procedimientos de cada usuario (19-32 oraciones, 391-718 tokens de material), fragmentado con P9 (L=10, F=2), con el PROYECTOR real de la LCE: la proyección sube ρ **+7.0%** (mediana) y **+7.8%** (peor) con el protocolo actual (Γ replicado en cada paquete).

**Explicación.** Δρ es estructural: ≈ tamaño de Γ / tamaño de cada paquete, y no se diluye con documentos más largos.

**Qué NO concluye.** La condición de muerte real de H-C2 («muere si el aumento de ρ supera la ganancia») exige comparar este costo con la ganancia de adherencia; esa comparación y los diseños por-solicitud o con caché quedan pendientes.

**Estimación, no medición.** Si Γ se inyectara una sola vez por solicitud, la misma aritmética sobre estos conteos de tokens daría +1.5% a +2.6% (mediana +2.3%). Ese diseño no existe en el protocolo y la cifra no está medida; una caché de Γ por usuario en el nodo podría acercarla a cero, lo que es una hipótesis.

### 2.3 C9-lite social (5 nodos reales)

**Cifras.** Masa de colas post: utilidad 0.00 vs prevalencia 0.00 (la del brazo de utilidad sale del diseño: nadie conocía los términos y todos copian la glosa del contexto). Identidad: 2+2 — la sonda no recibe las cápsulas, así que es la misma respuesta dos veces. Estado: **señal insuficiente (violaciones totales < 5)**.

**Alcance y desviaciones.** términos canarios SIN verificar: descriptivo del mecanismo, no evidencia sobre los términos. Dos desviaciones post-corrida están declaradas en el encabezado de `bench_social.py`.

**Ajuste propuesto.** La versión justa (siguiente fase): sonda con cápsulas en contexto, prevalencia que adopta la variante mayoritaria aunque sea errónea, utilidad juzgada por beneficio posterior, cápsulas con el conocimiento del nodo fuente, varias rondas, y el canario verificado por hablantes nativos.

### 2.4 Adaptador real (factibilidad, MLX LoRA)

**Cifras.** LoRA rank 8 entrenado en 36 s (200 iters, 13 pares) sobre Qwen2.5-3B-Instruct. Adherencia bruta: base 0.12, recuperación 0.38, adaptador 0.62. Facticidad: base 0.90 vs adaptador 0.80.

**Qué NO concluye.** La adherencia no compara brazos justos (el lote contamina las tareas; la recuperación solo recibió el documento de estilo; sin intervalo de confianza): **no concluyente (lote contaminado, brazos no comparables); factibilidad demostrada**. Los pesos no se distribuyen (licencia qwen-research del modelo base); el manifiesto con su SHA-256 y la receta están en el resultado. Reentrenar con la receta da un adaptador funcionalmente equivalente, no necesariamente idéntico bit a bit (MLX no garantiza determinismo); el manifiesto permite comprobarlo.

**Alcance.** exploratorio de FACTIBILIDAD: lote sintético de un usuario, 200 iters, Qwen2.5-3B-Instruct; la adherencia bruta no compara brazos justos (ver límites en bench_adapter.py).

**Ajuste propuesto (siguiente fase).** Tareas separadas del lote con otra redacción, lote solo de afirmaciones entrenables (I1) con ExampleBuilder, repaso y prueba nueva, ≥30 tareas con IC, y una segunda familia base de licencia permisiva.

### 2.5 R13 (piloto exploratorio, superado por la confirmatoria de la sección 2.8)

**Cifra central.** A3 − A2 = **−0.256** [−0.317, −0.194] por pregunta (126 preguntas; bootstrap agrupado por pregunta). Por digestor: `qwen2.5:3b` −0.212 [−0.288, −0.138]; `llama3.2:3b` −0.442 [−0.529, −0.354]; `gemma2:2b` −0.114 [−0.183, −0.045].

**Por tipo:** `simple` −0.257 [−0.329, −0.186] (n=83); `cross` −0.508 [−0.603, −0.405] (n=14); `updated` −0.341 [−0.563, −0.135] (n=14); `contradiction` −0.044 [−0.400, +0.267] (n=5); `deleted` +0.156 [−0.067, +0.378] (n=5); `unanswerable` +0.089 [−0.067, +0.333] (n=5).

**Memoria frente a nada (preguntas con respuesta):** A3 − A0 = +0.479 [+0.420, +0.537]; A2 − A0 = +0.767 [+0.704, +0.828].

**Dónde pierde la wiki.** Clave presente en el contexto (preguntas con respuesta): A2 0.991; A3|qwen2.5:3b 0.810; A3|llama3.2:3b 0.345; A3|gemma2:2b 0.836. La diferencia está en la cobertura de la digestión.

**Qué NO concluye.** `deleted` no mide olvido (ningún brazo vio la fuente borrada) y la abstención premia al brazo que recupera menos; la prueba de olvido real es F-forget (Enmienda 6). Sin las tres claves superadas (N1): −0.260 [−0.323, −0.198].

### 2.6 F-forget (olvido real, Enmienda 6 c)

**Estructura.** 15 celdas válidas (usuario × digestor): residuo S2 = 0 y daño colateral S3 = 0; barrido de 116 olvidos sin residuo ni daño. `forget_source` borra por anclaje, así que S2 y S3 verifican la implementación sobre wikis reales. **Veredicto estructural: se sostiene.** W_forget coincide con la W_never de la misma corrida en 8/15 wikis: la diferencia es el no determinismo de la digestión (AA2).

**Conducta.** Abstención en las preguntas sobre la fuente borrada: W_full 0.289, W_forget 0.778, W_never 0.756; forget − full = +0.489 [+0.333, +0.644], forget − never = +0.022 [+0.000, +0.067] (5 preguntas; mecanismo).

### 2.7 A/A de reproducibilidad (R14)

AA1 generación a T = 0 contra la confirmatoria de R13: 98.4 % de 369 respuestas idénticas, Δ exactitud +0.0027 (falla, el umbral es 99 %). AA2 digestión: 8/15 wikis idénticas entre corridas, Jaccard 0.961 (falla). AA3: semilla del endpoint nativo 100 % idéntica, compatible con OpenAI 80 %. AA4 homogeneidad: Δ −0.001 [−0.007, +0.005] (pasa).

**R14 queda abierto como negativo documentado (Enmienda 12):** la digestión con Ollama no es reproducible entre corridas en este equipo en ninguna de las cuatro configuraciones probadas.

### 2.8 R13 confirmatoria (preregistro 2.7, enmiendas 7–12)

**Cifra central.** A3 − A2 = **−0.146** [−0.186, −0.106] sobre 251 preguntas (≥ 30 por tipo, LongMemEval incluido, N1 excluido). Por digestor: `qwen2.5:3b` −0.113 [−0.159, −0.066]; `llama3.2:3b` −0.227 [−0.286, −0.170]; `gemma2:2b` −0.098 [−0.141, −0.057].

**Por tipo:** `simple` −0.231 [−0.292, −0.169] (n=100); `cross` −0.304 [−0.419, −0.189] (n=30); `updated` −0.222 [−0.358, −0.082] (n=31); `contradiction` −0.056 [−0.148, +0.030] (n=30); `deleted` +0.115 [+0.044, +0.189] (n=30); `unanswerable` +0.022 [−0.015, +0.070] (n=30).

**Cobertura de la respuesta en el contexto (preguntas con respuesta):** A2 0.948; A3|qwen2.5:3b 0.827; A3|llama3.2:3b 0.455; A3|gemma2:2b 0.843.

**Veredictos.** R13-H1 muere. R13-H2 no concluyente: la wiki pierde en actualización y su «victoria» en `deleted` es el artefacto N2 (A0, sin memoria, se abstiene en el 100 %). R13-H3: la compuerta se retira como regla. Muerte global de H-C1: no dispara con la lectura «no gana en ninguno», dispara con «no gana en ambos» (el texto en español dice «ni», el inglés «and»: Enmienda 15.3); por la letra en español no dispara solo por el tipo 5, que no mide olvido. La justificación de la wiki por exactitud cae por R13-H1.

### 2.9 C2-bis (placebo igualado en instrucción)

Diferencia de homogeneidad placebo − Γ = +0.065 [+0.056, +0.074] (100 celdas usuario × tema). La homogeneidad se calculó entre las tres SEMILLAS de un mismo usuario y tema, no entre usuarios: mide la variedad de muestreo dentro de un usuario, no lo que H-C17a pregunta (la convergencia de la población). **No prueba H-C17a**; el rediseño necesita homogeneidad entre usuarios, brazo sin contrato y un placebo neutro que no prescriba registro ni vocabulario. Los números de la primera corrida (invalidada por la Enmienda 14) no se conservaron. Ver `docs/RESULTS_2026-10-11_C2bis_ES.md`.

### 2.10 Cierre de H-C2 (preregistro 2.9)

251 tareas: ganancia media +0.016 (A4 − A3 en exactitud de QA), Δρ mediana 41 % con contextos de 200 tokens (cota aritmética: tokens de Γ por fragmento, sin el packer); fracción con ganancia > 0 y Δρ ≤ 10 % = 0.00. La regla dispara mecánicamente, pero mide otra cosa: la ganancia preregistrada era de adherencia (léxico) y aquí es exactitud de QA, y con ganancias binarias por tarea la regla del 80 % es casi inalcanzable. **Descriptivo:** en QA, Γ añade ρ sin mejorar la exactitud; H-C2 queda sin decidir para su uso propio, la escritura. Ver `docs/RESULTS_2026-10-11_HC2_closure_ES.md`.

### 2.11 R11 confirmatoria (Enmiendas 9 y 13)

En 720 de 720 tareas el texto del adaptador es idéntico byte a byte al del modelo base, y en 1454 de 1454 celdas (tareas, I1, LC6, H-C10) coinciden los aciertos; el brazo adaptador + recuperación coincide exactamente con recuperación. Con pesos LoRA distintos de cero, eso indica que el adaptador no se aplicó en la evaluación (servidor MLX con el nombre del modelo base en cada petición; además, la evaluación usa completions sin la plantilla de chat con la que se entrenó). **La corrida se rechaza por falla de manipulación**, como la corrida 1 de C2: no dice nada sobre H-C6, H-C10, I1 ni LC6, y la capa 2 no queda retirada por esta evidencia.

## 3. Cierre

Lo confirmado: la corrida 2 de C1/C2 (léxico, homogeneidad entre usuarios frente a placebo, equivalencia de errores compartidos) y R13-H1 (la wiki anclada pierde frente a un RAG crudo en exactitud, por la cobertura de la digestión). Lo medido como mecanismo: la memoria local ayuda (F1a), el olvido funciona (F-forget). Lo abierto: R14 (digestión no reproducible), H-C17a con un placebo igualado entre usuarios, H-C2 para escritura, y la capa 2, cuya confirmatoria se rechazó por falla de manipulación.
