---
status: current
lang: es
---

# Resultados — corrida confirmatoria 1 de C1 y C2 (LCE)

**5 de octubre de 2026 · preregistro `PREREGISTRATION_C1_C2_ES.md` (sha256 `f60937a5…`) · commit `f7a8919`**

**Veredicto de la corrida: la manipulación falló.** La proyección sobre Γ salió vacía en todas las peticiones, de modo que la condición "con Γ" fue idéntica a la línea base. Los veredictos de H-C17 (a) y H-C17 (b) que emitió el código se produjeron por construcción y se declaran ininterpretables; con la comprobación de manipulación de la enmienda 2 las tres hipótesis de C2 quedan rechazadas. Lo que la corrida sí mide, porque no depende de Γ, se reporta abajo como descriptivo.

Modelos: `qwen2.5:3b`, `llama3.2:3b` y `gemma2:2b` en Ollama 0.35.1, embeddings `nomic-embed-text`, en la máquina Apple Silicon del autor. Salidas sin modificar en `results/2026-10-05_C1C2_run1/` (`results_real.json` sha256 `0d32f365…`), con todas las respuestas brutas.

---

## 1. Qué pasó con el tratamiento

La proyección tuvo un tamaño medio de 2 bytes, que es el objeto vacío `{}`, en las 60 escrituras (3 usuarios por 20 temas) y en las 1.500 preguntas. Las 4.500 respuestas de opción múltiple con Γ son idénticas, letra por letra, a las 4.500 sin Γ, porque los prompts fueron idénticos. Ningún usuario llegó a tener términos preferidos en su proyección, y por eso H-C2 quedó rechazada por el propio código.

La causa más probable está en la digestión. Sobre el corpus de C1, el verificador rechazó 8 de 12 afirmaciones propuestas por el modelo (tasa de rechazo 0,67), todas por falta de soporte: el ancla apuntaba a un fragmento que no contenía la afirmación. El digestor de la versión 0.1 pide al modelo los offsets de carácter de cada afirmación, y los modelos pequeños cuentan caracteres mal; una afirmación con offsets equivocados no se ancla, y el proyector solo usa afirmaciones ancladas. A eso se suma que el proyector busca el léxico y el registro con patrones sobre el texto de la afirmación, que el modelo parafrasea, en lugar de sobre las palabras del usuario. El diagnóstico exploratorio (`lce_validation.diagnose`) confirmará o descartará estas dos causas antes de la corrida 2.

## 2. Veredictos

| Hipótesis | Emitido por el código del preregistro | Con la enmienda 2 | Lectura |
|---|---|---|---|
| C1 (control positivo) | se sostiene | se sostiene | exactitud 0,70 con memoria frente a 0,00 sin ella; justo en el umbral |
| H-C2, léxico | rechazada | rechazada | ningún término preferido llegó a la proyección |
| H-C2, ρ | no probada | no probada | requiere la ruta de despacho de Swarmbly |
| H-C17 (a) | falsada | rechazada | sin tratamiento; ininterpretable |
| H-C17 (b) | se sostiene | rechazada | Δ = 0 exacto por prompts idénticos; ininterpretable |

El error de diseño es del protocolo, no de los datos: el preregistro no incluía una comprobación de que el tratamiento llegara. Se deja escrito aquí, con los veredictos originales a la vista, para que nadie pueda citar "H-C17 (a) falsada" ni "H-C17 (b) se sostiene" a partir de esta corrida.

## 3. Lo que la corrida sí mide (descriptivo)

**Errores compartidos entre familias.** Sin proyección, cuando dos de los tres modelos se equivocan en la misma pregunta eligen la misma letra equivocada el 56,3 % de las veces, frente a un azar calculado de 35,4 %: un exceso de 0,209 (IC 95 % [0,178, 0,241]) sobre 1.264 pares-pregunta conjuntamente equivocados. Por pares: gemma2 y qwen2.5 0,608 (azar 0,360), gemma2 y llama3.2 0,576 (0,356), llama3.2 y qwen2.5 0,496 (0,344). Las exactitudes fueron 0,606 (qwen2.5), 0,579 (llama3.2) y 0,535 (gemma2), con 0,2 % de respuestas ilegibles. El resultado reproduce en modelos de 2–3B lo que Kim et al. (2025) reportan en modelos grandes, y es la primera medición propia del proyecto que respalda la nota `FINDING_2026-10-04` de Swarmbly y la limitación L23 que propone. No depende de Γ, porque usa solo la condición sin proyección.

**Una prueba A/A involuntaria del instrumento de homogeneidad.** Como la proyección estaba vacía, las condiciones "línea base" y "proyección" fueron dos muestras independientes de la misma condición. Su diferencia fue −0,003 (IC 95 % [−0,010, +0,003]) sobre 20 temas, lo que fija el piso de ruido del instrumento en cerca de ±0,01 de similitud coseno. Un efecto real de la proyección tendrá que superar eso.

**El placebo sí redujo la homogeneidad.** Los tres contratos genéricos sin información personal bajaron la homogeneidad entre usuarios de 0,880 a 0,853, una reducción de 0,026 (IC 95 % [0,006, 0,049]). Es una observación exploratoria, porque el placebo era un control y no una hipótesis: cualquier variación del prompt por usuario reduce la homogeneidad, y la proyección personal tendrá que superarla para atribuirse a la personalización.

**Las semillas no fijaron el muestreo.** Con prompts idénticos y la misma semilla, la línea base y la proyección vacía produjeron textos distintos, de modo que la interfaz compatible con OpenAI de Ollama no reprodujo el muestreo por semilla en esta configuración. El diseño sigue siendo válido como muestreo aleatorio por condición, pero el emparejamiento por semilla que describe la sección 3 del preregistro no se cumplió, y así se declara.

**Digestión y canario.** El anclaje rechazó el 67 % de las afirmaciones del digestor real (sección 1). El conjunto canario, todavía sin verificar, dio masa en las colas 0,00: `qwen2.5:3b` no glosó correctamente ninguno de los ocho regionalismos ecuatorianos. Es solo descriptivo hasta la verificación por hablantes nativos.

## 4. Qué sigue

La enmienda 2 del preregistro añade la comprobación de manipulación. El diagnóstico exploratorio muestra, afirmación por afirmación, dónde se pierde el tratamiento con cada modo de anclaje. Con su resultado, una enmienda 3 fija la corrección antes de la corrida 2, que repite el protocolo con los mismos modelos, preguntas, temas, estadísticos y umbrales. Esta corrida queda publicada tal cual, incluidas sus partes fallidas.

---

**Referencias**

Kim, E. M., Garg, A., Peng, K., & Garg, N. (2025). Correlated errors in large language models. En *Proceedings of ICML 2025*, PMLR 267, 30038–30066. https://proceedings.mlr.press/v267/kim25e.html

*Texto bajo CC BY 4.0.*
