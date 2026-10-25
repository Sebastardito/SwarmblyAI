---
status: current
lang: es
kind: confirmatory
---

# Resultados — C2-bis (placebo igualado en instrucción): no prueba H-C17a

**11 de octubre de 2026 · preregistro `PREREGISTRATION_BENCH_R1X_ES.md`,
sección 2.8, con las Enmiendas 14 (antes de la re-corrida) y 15.5
(después) · commit `9fd3a1a` (`1e363f2` en la procedencia, anterior a la
purga de pesos: ver `COMMIT_MAP_2026-10-11.md`) · Python 3.9.6 (Enmienda
15.1) · 5 usuarios × 20 temas × 3 semillas, qwen2.5:3b por el endpoint
nativo con semilla, Γ completa del Projector (petición vacía) y placebo de
la misma cantidad de tokens**

Salidas en `results/bench_c2bis/results.json`.

## 1. Cifra

Diferencia de homogeneidad placebo − Γ = **+0.0652 [+0.0557, +0.0742]**
(100 celdas usuario × tema, bootstrap sobre celdas, 10.000 remuestreos,
semilla 20261005). Homogeneidad media: con Γ 0.844, con placebo 0.910. La Γ
mide 21–45 tokens según el usuario; el placebo, lo mismo.

## 2. Qué mide y qué no

La sección 2.8 pide probar H-C17a: que la proyección reduzca la
homogeneidad **entre usuarios** (textos de personas distintas sobre el
mismo tema se parecen menos) más que un placebo igualado en cantidad de
instrucción. La implementación (`lce_validation/bench_c2bis.py`) calcula
otra cosa: la homogeneidad entre las **tres semillas de un mismo usuario y
tema**. Lo que el +0.065 muestra es que, con su Γ, las tres muestras de un
usuario se parecen menos entre sí que con el placebo. Eso es variabilidad
dentro del usuario, no diferenciación entre usuarios.

Hay dos problemas más. No hay brazo sin contrato, así que no se puede decir
si Γ reduce la homogeneidad o si el placebo la aumenta; y el placebo pide
explícitamente «un registro neutral» y «un vocabulario general y común»,
es decir, empuja hacia la homogeneidad. Finalmente, la Enmienda 14 decía
que los números de la primera corrida se reportarían como comprobación del
instrumento, pero no se conservaron (Enmienda 15.5).

| Hipótesis | Veredicto |
|---|---|
| H-C17a (sección 2.8) | **sin veredicto**: la corrida no mide la cantidad que la hipótesis define |

H-C17a queda como estaba tras la corrida 2 de C1/C2: se sostiene con el
matiz de que su placebo igualaba la forma de Γ y no su cantidad de
instrucción. El matiz no queda cerrado.

## 3. Lo que exige una re-corrida

Homogeneidad entre usuarios por tema (los cinco usuarios con la misma
semilla), tres brazos (sin contrato, Γ, placebo igualado) y un placebo
neutro que no prescriba registro ni vocabulario.

## 4. Lo que sustituye este documento

La primera versión declaraba que «H-C17a se sostiene» y que la reducción
de la corrida 2 «era efecto real de la Γ, no de la longitud del contrato».
Esa conclusión se retira.

*Texto CC BY 4.0.*
