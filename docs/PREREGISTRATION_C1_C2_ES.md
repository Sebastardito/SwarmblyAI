---
status: current
lang: es
---

# Preregistro — C1 y C2 de la LCE de Swarmbly con modelos reales

**5 de octubre de 2026 · escrito ANTES de cualquier corrida con modelos reales**

Este documento fija las hipótesis, el diseño, la estadística, las condiciones de rechazo y las condiciones de muerte de las primeras corridas de la extensión cognitiva local (LCE) de Swarmbly con modelos de lenguaje reales, antes de que exista una sola respuesta real. Remite al whitepaper versión 0.1 (doi:10.5281/zenodo.23150478), secciones 11.1 a 11.5, y se publicará junto con sus resultados, sean cuales sean. Una hipótesis que muera aquí se reporta muerta.

Las reglas de decisión no están solo escritas aquí: son código en `lce_validation/decide.py`, confirmado junto con este documento, para que no puedan moverse una vez vistos los datos. `run_real` registra en cada resultado el SHA-256 de este archivo, el del conjunto de preguntas y el commit de git.

Versión en inglés: `PREREGISTRATION_C1_C2_EN.md`.

---

## 1. Declaración de origen: tres defectos encontrados antes de medir

No se ha hecho ninguna corrida de la LCE con modelos reales. Al preparar este protocolo, leyendo el arnés de la versión 0.1 frente a las hipótesis que dice servir, aparecieron tres defectos que habrían producido resultados ininterpretables. Se encontraron en el código, no en datos, y este documento existe en parte para dejarlos registrados.

**La línea base de homogeneidad era idéntica por construcción.** La versión 0.1 comparaba las respuestas que reciben tres usuarios con y sin proyección de tarea, pero generaba la condición sin proyección a temperatura 0 con el mismo prompt para todos. Con un decodificador determinista las tres respuestas son idénticas, la homogeneidad vale 1 por construcción y cualquier proyección parece reducirla. La corrida simulada imprimió exactamente 1,000 y en su momento la cifra no pareció sospechosa. El diseño corregido muestrea cada respuesta a temperatura 0,7 con la misma semilla por usuario en todas las condiciones, y añade un placebo no personal.

**La métrica de concordancia de errores estaba sesgada hacia cero y no tenía potencia.** La versión 0.1 comparaba respuestas de texto libre a diez preguntas fácticas por coincidencia exacta de sus primeras ocho palabras normalizadas. Dos modelos que dan la misma entidad equivocada con palabras distintas cuentan como discrepantes, de modo que la métrica no puede detectar los errores compartidos que pretende medir, y con diez preguntas casi no habría pares equivocados a la vez. El diseño corregido usa preguntas de opción múltiple, como Kim et al. (2025), donde la misma respuesta equivocada es inequívoca y tiene un nivel de azar calculable, y fija el número de preguntas a partir de una simulación del instrumento (sección 7).

**C1 no puede falsar H-C1.** Las diez preguntas de C1 piden términos que prefiere el usuario sintético, y ningún modelo base puede conocerlos. Se espera que un modelo sin memoria acierte casi nada y uno con recuperación casi todo, sea cual sea el mérito de la LCE. Por eso C1 se reclasifica como control positivo de la tubería (digestión por un modelo real, anclaje, recuperación) y no como prueba de H-C1. Un fallo de C1 acusa a la tubería; un acierto no dice nada sobre H-C1 a escala.

Se cierra además un hueco menor: la adherencia al léxico (H-C2) se medía solo con proyección, sin línea base. Ahora se compara con las mismas escrituras sin proyección.

## 2. Qué se prueba y qué no

| Hipótesis | Parte que se prueba aquí | Estado en esta corrida |
|---|---|---|
| H-C1, memoria local | tubería de recuperación sobre una wiki digerida por un modelo real | solo control positivo |
| H-C2, proyección de tarea | términos preferidos respetados con Γ frente a sin Γ | parte léxica; la tasa de redundancia ρ **no se prueba** |
| H-C17 (a), diversidad entre usuarios | homogeneidad de las respuestas entre usuarios, con y sin proyección | confirmatoria |
| H-C17 (b), correlación de errores sin cambio | concordancia entre familias en la misma respuesta equivocada, con y sin proyección | confirmatoria (equivalencia) |
| Kim et al. (2025) en modelos pequeños | errores compartidos por encima del azar entre familias | descriptiva |
| Conjunto canario (C8) | masa en las colas y violaciones de identidad | solo descriptiva; los ítems no están verificados |

Nada de esto prueba adaptadores (C4, C10), cápsulas, afinidad ni el plano social.

## 3. Diseño

**Modelos.** `qwen2.5:3b`, `llama3.2:3b` y `gemma2:2b`, servidos por Ollama en la máquina Apple Silicon del autor a través de su interfaz compatible con OpenAI. El primero digiere los corpus y escribe todas las respuestas abiertas; los tres actúan como réplicas de familias distintas en las preguntas de opción múltiple. Los embeddings para la homogeneidad proceden de `nomic-embed-text`. `run_real` registra la versión de Ollama y el digest de cada modelo. Estas elecciones quedan fijadas ahora; cambiar un modelo después de ver resultados es una desviación.

**Materiales.** Para C1, el corpus de un usuario sintético (`lce_validation/fixtures/corpus/`, política de aprendizaje `policy.json`) y sus diez preguntas (`questions.json`). Para H-C2 y H-C17 (a), tres usuarios sintéticos (`fixtures/users/u1–u3/`, política `users_policy.json`) que difieren en registro y en un término preferido cada uno, y los veinte temas abiertos de `fixtures/open_queries.json`. Para H-C17 (b), 1.500 preguntas del conjunto de prueba de MMLU (Hendrycks et al., 2021; licencia MIT), extraídas de manera uniforme sin reemplazo con la semilla 20261005 mediante `python -m lce_validation.fetch_mcq`. El archivo de preguntas se extrae una sola vez, después de confirmar este documento y antes de cualquier llamada a un modelo, y se confirma con su SHA-256; volver a extraerlo es una desviación.

**Generación.** Cada respuesta abierta se muestrea a temperatura 0,7 con un máximo de 160 tokens y la semilla 1000+u para el usuario u, idéntica en todas las condiciones, de modo que las condiciones solo difieren en el contrato. Las respuestas de opción múltiple y de C1 usan temperatura 0 (8 y 96 tokens). Las tres condiciones de escritura son la **línea base** (sin campos de Γ), la **proyección** (el Γ propio del usuario: registro, léxico preferido y semilla de estilo, tal como los produce el proyector a partir de la wiki digerida por el modelo real) y el **placebo** (uno de tres contratos genéricos sin información personal: "Write in plain language.", "Use a measured tone.", "Be direct and brief.", cada uno con registro neutro). En las preguntas de opción múltiple, la condición con proyección rota el Γ de los tres usuarios entre preguntas.

## 4. Medidas y estadística

**C1.** Exactitud con y sin recuperación (el término de referencia aparece en la respuesta) y las estadísticas descriptivas de la digestión (afirmaciones, tasa de rechazo del anclaje, salidas malformadas del digestor).

**H-C2, léxico.** Para cada usuario y tema, la fracción de los términos preferidos del usuario que aparecen en la respuesta con proyección y en la respuesta de línea base; el estadístico es la diferencia media sobre las sesenta celdas, con un intervalo bootstrap de percentiles al 95 % (10.000 remuestreos, semilla 20261005).

**H-C17 (a).** Para cada tema y condición, la homogeneidad entre usuarios es la similitud coseno media por pares de los embeddings de las tres respuestas. El estadístico principal es la media sobre temas de línea base menos proyección, con un intervalo bootstrap sobre los veinte temas. El estadístico secundario, que matiza pero no decide, es placebo menos proyección.

**H-C17 (b).** Para cada par de familias y cada pregunta, una pregunta conjuntamente equivocada es la que ambos responden con una letra válida y equivocada. La concordancia es la fracción agregada de pares-pregunta conjuntamente equivocados con la misma letra. El azar se calcula pregunta por pregunta a partir de la distribución de letras equivocadas de cada modelo sobre los tres distractores de esa pregunta. El estadístico principal es la diferencia de concordancia con menos sin proyección, con un bootstrap pareado sobre preguntas (las mismas preguntas remuestreadas entran en ambas condiciones; 10.000 remuestreos, semilla 20261005). El margen de equivalencia es ±0,10. Es menos de la mitad del exceso sobre el azar que reportan Kim et al. (alrededor de 0,27, de un 60 % frente a un azar de un tercio), de modo que un cambio dentro del margen no puede alterar la conclusión de que los errores son compartidos.

## 5. Reglas de decisión

| Hipótesis | Se sostiene | Queda falsada | En otro caso |
|---|---|---|---|
| C1 (control positivo) | exactitud con memoria ≥ 0,70 y ganancia ≥ 0,50 | — | rechazada: falló la tubería, H-C1 no es comprobable |
| H-C2, léxico | IC 95 % de la diferencia > 0 | estimación puntual ≤ 0 | no concluyente |
| H-C17 (a) | IC 95 % de la reducción > 0 | estimación puntual ≤ 0 | no concluyente |
| H-C17 (b) | IC 95 % de Δ dentro de [−0,10, +0,10] | el IC excluye 0 y \|Δ\| > 0,10 | no concluyente |

H-C17 (a) se reporta siempre con su matiz: si la reducción por proyección no supera al placebo (IC de placebo menos proyección no mayor que 0), la reducción se atribuye a la variación del prompt por usuario y no a la personalización, y el whitepaper debe decirlo así.

## 6. Condiciones de rechazo

El análisis rechaza en lugar de adivinar. La corrida entera se etiqueta exploratoria, y `decide` no emite veredictos, si este documento o el archivo de preguntas no están confirmados, si el árbol de código tiene cambios, si no se da un modelo de embeddings o si responden menos de tres familias. C1 se rechaza si la wiki digerida tiene menos de cinco afirmaciones, porque nada de lo que sigue sería interpretable. H-C17 (b) se rechaza si alguna de las dos condiciones tiene menos de 200 pares-pregunta conjuntamente equivocados, o si más del 10 % de las respuestas de alguna condición no pueden leerse como una letra.

## 7. Evidencia sobre el instrumento antes de la corrida

Siguiendo el método del whitepaper v2 de Swarmbly, la medida nueva se probó antes de usarla. El instrumento `error_agreement` de `lce_validation/instruments.py` simula tres familias con dificultad correlacionada y una probabilidad ajustable de elegir una opción equivocada compartida. En simulación, las respuestas equivocadas independientes quedan en el nivel de azar calculado (cerca de un tercio) y las compartidas por encima, y un aumento real de la compartición de 0,4 a 0,8 se detecta en todas las réplicas. El número de preguntas se fijó a partir de la fracción de réplicas en que, sin cambio real, el intervalo bootstrap de Δ cae dentro de ±0,10: 0,30 con 600 preguntas, 0,78 con 1.000, 0,90 con 1.500 y 1,00 con 2.000. La simulación es pesimista, porque vuelve a sortear todas las respuestas equivocadas en la segunda condición, mientras que a temperatura 0 una respuesta solo cambia si el contrato la cambia. Con 1.500 preguntas un veredicto de equivalencia es alcanzable y la corrida dura del orden de una a dos horas en una máquina de consumo; esa es la razón del número. Son simulaciones y no son evidencia sobre modelos.

## 8. Protocolo de corrida

Hay una sola corrida confirmatoria. Si falla por razones de infraestructura (el servidor se detiene, un modelo no carga), la salida parcial se descarta, el fallo se registra en las enmiendas y la corrida se repite sin cambios. Ninguna corrida se repite por sus resultados, ningún modelo ni ajuste se cambia después de verlos, y cualquier corrida adicional se etiqueta exploratoria. Las respuestas brutas se conservan en `results_real.json` y se publican.

## 9. Qué no decide esta corrida

No prueba la LCE con usuarios reales: los tres usuarios son sintéticos y difieren en pocos rasgos. No prueba H-C1 a escala, ni la tasa de redundancia que H-C2 también nombra. No generaliza más allá de modelos de 2–3B servidos localmente, ni más allá de preguntas de opción múltiple en inglés, aunque los usuarios escriben en español. Y una reducción de la homogeneidad entre usuarios sintéticos muestra que el mecanismo puede funcionar, no que funcione en una población.

## 10. Enmiendas

Cualquier cambio a este documento después de su primera confirmación se registra aquí con fecha y razón. Una enmienda declarada cuenta; una silenciosa no.

**Enmienda 1 — 5 de octubre de 2026, antes de cualquier corrida con modelos reales.** La proyección se calcula una vez por petición, para cada usuario y tema y para cada usuario y pregunta de opción múltiple, en lugar de una sola vez por usuario sobre los veinte temas juntos. La razón es que el carril de privacidad se clasifica por petición, y una proyección única sobre todos los temas ponía a todos los usuarios en el carril sensible porque un tema menciona la salud. Las peticiones clasificadas como sensibles se quedarían en el cliente en uso real; aquí se escriben igualmente con su Γ, nunca se descartan, y se reporta su número (`local_only_writes`, `local_only_items`). No cambia ningún estadístico, umbral ni regla de decisión.

**Enmienda 2 — 5 de octubre de 2026, después de la corrida confirmatoria 1 y antes de cualquier otra corrida.** La corrida 1 (commit `f7a8919`, salidas en `results/2026-10-05_C1C2_run1/`) no aplicó el tratamiento: la proyección salió vacía en las 60 escrituras y en las 1.500 preguntas de opción múltiple (tamaño medio de 2 bytes, el objeto vacío). La condición "con Γ" fue, por tanto, la línea base. Con las reglas de la sección 5 el código emitió H-C17 (a) *falsada* y H-C17 (b) *se sostiene*, y rechazó H-C2; los dos primeros veredictos salieron por construcción y no dicen nada sobre las hipótesis. La omisión es de este protocolo: no tenía comprobación de manipulación. Esos veredictos se conservan en el registro tal como se emitieron y se declaran ininterpretables. Esta enmienda añade la comprobación a la sección 6 y a `decide.py`: los veredictos de H-C2, H-C17 (a) y H-C17 (b) se rechazan salvo que la proyección mida en promedio al menos 20 bytes y que al menos el 80 % de las escrituras y de las preguntas lleven un Γ no vacío. Reevaluada con ella, la corrida 1 rechaza las tres. La causa se localizará con un diagnóstico exploratorio (`python -m lce_validation.diagnose`), que no decide nada; la corrección de la entrega que ese diagnóstico respalde (anclar por cita literal en lugar de por offsets que informa el modelo, y leer léxico y registro de las palabras ancladas del usuario) se fijará en una tercera enmienda, antes de la corrida 2. La corrida 2 reutiliza los mismos modelos, preguntas, temas, estadísticos y umbrales. Los datos de homogeneidad y de concordancia de errores de la corrida 1 ya se vieron; la corrección afecta solo a si Γ llega al modelo que escribe, no a las medidas de resultado.

**Enmienda 3 — 5 de octubre de 2026, después del diagnóstico exploratorio y antes de la corrida 2.** El diagnóstico (`results/diagnostics/diagnose_qwen2.5_3b.md`, exploratorio, no decide nada) localizó dos causas. La primera, el anclaje por offsets que informa el modelo falló: con `qwen2.5:3b` no se ancló ninguna de las seis afirmaciones de los tres usuarios y solo 4 de las 12 del corpus de C1, porque los offsets cortaban los fragmentos; el anclaje por cita literal, con los offsets calculados por código, ancló las 18. La segunda, la tipificación: el modelo tipificó cada preferencia explícita ("Prefiero el término X en lugar de Y") como `user_claim`, un tipo que el proyector excluye, de modo que el léxico nunca llegó a Γ ni siquiera con anclaje por cita, que solo entregó el registro. La corrida 2 fija por tanto cuatro ajustes: `--anchor-mode quote`; `--span-projection` (léxico y registro se leen de las palabras ancladas del usuario); `--reconcile-types`, una regla determinista que convierte un `user_claim`, `opinion`, `belief` o `fact` propuesto en `preference` cuando el fragmento anclado de una fuente escrita por el usuario contiene una marca de preferencia en primera persona ("prefiero", "I prefer"), o en `style` cuando contiene una marca de escritura en primera persona ("escribo", "I write"), y nunca en la dirección contraria; y `--preflight`, que detiene la corrida antes de generar cualquier resultado si la proyección no pasa la comprobación de manipulación de la enmienda 2. C1 se digiere con los mismos ajustes. La regla se escribió después de ver estos fixtures y solo está validada sobre ellos; se declara como limitación de la corrida 2. Como Ollama no reprodujo el muestreo por semilla en la corrida 1, el análisis no supone emparejamiento por semilla; los estadísticos, que emparejan por tema, no cambian. Todo lo demás queda como se preregistró: modelos, el archivo de preguntas confirmado (sha256 `c8991d3b…`), temas, estadísticos, umbrales y reglas de decisión. La corrida 2 es la confirmatoria; la corrida 1 queda publicada como corrida fallida.

---

**Referencias**

Hendrycks, D., Burns, C., Basart, S., Zou, A., Mazeika, M., Song, D., & Steinhardt, J. (2021). Measuring massive multitask language understanding. En *International Conference on Learning Representations (ICLR 2021)*. https://arxiv.org/abs/2009.03300

Kim, E. M., Garg, A., Peng, K., & Garg, N. (2025). Correlated errors in large language models. En *Proceedings of ICML 2025*, PMLR 267, 30038–30066. https://proceedings.mlr.press/v267/kim25e.html

*Texto bajo CC BY 4.0; código bajo AGPL-3.0-or-later.*
