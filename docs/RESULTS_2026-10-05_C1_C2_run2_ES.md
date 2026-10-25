---
status: current
lang: es
---

# Resultados — corrida confirmatoria 2 de C1 y C2 (LCE)

**5 de octubre de 2026 · preregistro `PREREGISTRATION_C1_C2_ES.md` con enmiendas 1–3 (sha256 `508ba8f9…`) · commit `99a1d52`**

**Las tres hipótesis de C2 que se podían decidir se sostienen, con matices que importan.** La proyección de tarea hace que los textos respeten los términos preferidos del usuario (H-C2, parte léxica) y reduce la homogeneidad entre usuarios más allá de un placebo no personal (H-C17 a). La concordancia de errores entre familias queda dentro del margen de equivalencia de ±0,10 (H-C17 b), pero no sin cambio: sube 0,039 con un intervalo que excluye el cero. C1, el control positivo, pasa con holgura. La tasa de redundancia ρ, la otra mitad de H-C2, no se probó.

La corrida se hizo después de ver la corrida 1, que falló porque la proyección salió vacía, y después de un diagnóstico exploratorio que llevó a la enmienda 3. Ese orden se declara aquí y en el preregistro, y limita lo que esta corrida puede afirmar (sección 5).

Modelos: `qwen2.5:3b` (digiere y escribe), `llama3.2:3b` y `gemma2:2b`, en Ollama 0.35.1; embeddings `nomic-embed-text`; máquina Apple Silicon del autor. Ajustes de la enmienda 3: anclaje por cita literal, léxico y registro leídos del fragmento anclado, reconciliación de tipos y comprobación previa. Salidas sin modificar en `results/2026-10-05_C1C2_run2/` (`results_real.json` sha256 `4c6d0b2f…`).

---

## 1. El tratamiento llegó

La comprobación de manipulación pasó. La proyección midió 97 bytes en promedio y fue no vacía en el 100 % de las 60 escrituras y de las 1.500 preguntas. Las 60 llevaron el léxico preferido del usuario; 32 llevaron además su registro, y ninguna llevó semilla de estilo, porque el proyector asigna la afirmación de estilo al registro antes de considerarla como semilla. La digestión ancló las 12 afirmaciones del corpus de C1 (tasa de rechazo 0,00, frente a 0,67 en la corrida 1), y la regla de reconciliación cambió el tipo de 2 de ellas. Tres escrituras y 67 preguntas quedaron en el carril sensible, que en uso real no saldría del cliente; se escribieron igual y cuentan en todas las cifras.

## 2. Veredictos

| Hipótesis | Veredicto | Estimación | IC 95 % |
|---|---|---|---|
| C1 (control positivo) | se sostiene | exactitud 0,80 con memoria frente a 0,00 sin ella | — |
| H-C2, léxico | se sostiene | adherencia 0,667 con Γ frente a 0,033 sin Γ; diferencia 0,633 | [0,500, 0,750] |
| H-C2, ρ | no probada | requiere la ruta de despacho de Swarmbly | — |
| H-C17 (a) | se sostiene | homogeneidad 0,879 → 0,806; reducción 0,073 | [0,052, 0,096] |
| H-C17 (a), matiz | supera al placebo | proyección frente a placebo: 0,048 | [0,023, 0,070] |
| H-C17 (b) | se sostiene (equivalencia) | concordancia 0,563 → 0,602; Δ = 0,039 | [0,009, 0,069] |

## 3. Lectura

**El léxico.** Con la proyección, los términos preferidos aparecen en dos de cada tres textos; sin ella, casi nunca (dos textos de sesenta). La adherencia varía por usuario: 0,95 para "evolución cultural", 0,65 para "inferencia descentralizada" y 0,40 para "modelo pequeño", que el modelo que escribe tiende a sustituir. La prueba mide que un modelo de 3B respeta un campo de Γ que nombra el término explícitamente; no mide preferencias implícitas.

**La homogeneidad.** La reducción por proyección aparece en los 20 temas y es casi tres veces la del placebo (0,025), que repite el valor de la corrida 1. La proyección supera al placebo en 0,048, de modo que la reducción no se explica solo por variar el prompt de un usuario a otro. Hay un límite que conviene decir: el placebo igualaba la forma del contrato, no la cantidad de instrucción, y la proyección lleva un término concreto que cambia el vocabulario del texto. Que la diferencia venga de la información personal y no de instrucciones más específicas no está separado en este diseño.

**Los errores compartidos.** Con Γ, los tres modelos se equivocan en más preguntas (exactitud de 0,606 a 0,597 en qwen2.5, de 0,579 a 0,545 en llama3.2 y de 0,535 a 0,519 en gemma2), y Γ cambia la respuesta en 664 de 4.500 casos. La concordancia cuando ambos se equivocan sube de 0,563 a 0,602. El veredicto preregistrado es de equivalencia, porque todo el intervalo cae dentro de ±0,10, pero el intervalo excluye el cero: Γ no deja intacta la correlación de errores, la aumenta un poco. Un análisis no preregistrado sugiere de dónde viene: el nivel de azar calculado también sube, de 0,354 a 0,396, porque con Γ las respuestas equivocadas se concentran en menos letras, y el exceso sobre el azar queda prácticamente igual (0,206 con Γ frente a 0,209 sin él). La lectura prudente es que un contrato compartido por todas las réplicas homogeneiza un poco sus respuestas, incluidas las equivocadas, sin cambiar la estructura de errores compartidos que viene del preentrenamiento. Es coherente con las secciones 2.6 y 6.4 del whitepaper, y añade algo que no decían: la proyección tiene un pequeño costo de exactitud en tareas fácticas.

**Reproducibilidad.** Las 4.500 respuestas sin proyección son idénticas, letra por letra, a las de la corrida 1, y la línea base y el placebo de homogeneidad repiten sus valores (0,879 frente a 0,880; 0,854 frente a 0,853). Los errores compartidos entre familias sin proyección, que la corrida 1 ya midió, se reproducen exactamente: exceso de 0,209 (IC 95 % [0,178, 0,241]) sobre el azar.

## 4. Lo que no cambia de la corrida 1

C1 sigue siendo un control positivo y no una prueba de H-C1. El conjunto canario, sin verificar, vuelve a dar masa en las colas de 0,00 y es solo descriptivo.

## 5. Límites de esta corrida

Es la segunda corrida confirmatoria y se hizo después de ver la primera. Los ajustes de la enmienda 3 corrigen si Γ llega al modelo que escribe, no las medidas de resultado, pero la regla de reconciliación de tipos se escribió viendo estos fixtures y solo está validada sobre ellos. Los usuarios son tres, sintéticos, y difieren en un término y un registro. Los modelos son de 2–3B y locales; las preguntas de opción múltiple están en inglés y los usuarios escriben en español. Las semillas no reprodujeron el muestreo en Ollama, de modo que las condiciones de escritura son muestras independientes emparejadas solo por tema. Y una reducción de homogeneidad entre tres usuarios sintéticos muestra que el mecanismo puede funcionar, no que funcione en una población.

## 6. Qué sigue

Para la versión 0.2 del whitepaper: reportar H-C2 (léxico) y H-C17 como sostenidas con estos matices, añadir el costo de exactitud de Γ y el pequeño aumento de la concordancia de errores como hallazgos, e incorporar la medición propia de errores compartidos entre familias. Para una prueba más fuerte: usuarios reales o al menos más numerosos y variados, un placebo igualado en cantidad de instrucción, y la tasa ρ dentro del flujo de despacho de Swarmbly.

---

*Texto bajo CC BY 4.0.*
