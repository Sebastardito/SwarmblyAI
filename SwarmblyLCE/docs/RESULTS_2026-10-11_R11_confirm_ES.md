---
status: current
lang: es
kind: confirmatory
---

# Resultados — R11 confirmatoria (el adaptador justo): RECHAZADA por falla de manipulación

**11 de octubre de 2026 · preregistro `PREREGISTRATION_BENCH_R1X_ES.md`,
sección 3, con las Enmiendas 9 y 13 (antes de evaluar) y 15.4 (después) ·
commit `b836e84` (`b8b474e` en la procedencia, anterior a la purga de pesos:
ver `COMMIT_MAP_2026-10-11.md`) · Python 3.9.6 (Enmienda 15.1) · 48
entrenamientos LoRA con MLX (2 familias base × 3 usuarios × 2 semillas × 2
repasos × 2 presupuestos) y 1454 celdas de evaluación**

Salidas en `results/bench_r11_confirm/results.json` (todas las celdas con
el texto de base y adaptador). Los adaptadores y sus lotes se generaron
localmente y no se versionan: derivan en parte de Qwen2.5-3B-Instruct, cuya
licencia (qwen-research) no permite redistribuirlos (Enmienda 15.8).

## 1. Qué se midió

| Usuario | base | recuperación + Γ | adaptador | adaptador + recuperación + Γ |
|---|---|---|---|---|
| mara | 0.050 | 0.617 | 0.050 | 0.617 |
| julian | 0.133 | 0.650 | 0.133 | 0.650 |
| carmen | 0.000 | 0.633 | 0.000 | 0.633 |

(30 tareas por usuario × 8 configuraciones de presupuesto completo; 720
filas.)

## 2. Por qué la corrida se rechaza

El adaptador y el modelo base producen **el mismo texto, byte a byte, en
las 720 tareas**, y los mismos aciertos en **las 1454 celdas** (tareas
principales, I1, LC6 y H-C10). Los pesos LoRA entrenados son distintos de
cero, así que el adaptador existe pero no llegó a la evaluación. Dos causas
probables en `lce_validation/bench_r11.py`: el servidor MLX se arranca con
`--adapter-path`, pero cada petición envía `"model": base_model`, lo que
puede hacer que el servidor sirva el modelo base; y la evaluación usa
`/v1/completions` sin la plantilla de chat con que se entrenó el adaptador.

Esto es una falla de manipulación, como la corrida 1 de C2: el tratamiento
no llegó. Un «adaptador − base = +0.000 exacto» no dice que el adaptador sea
inerte; dice que no se aplicó. Por eso:

| Hipótesis | Veredicto |
|---|---|
| H-C6 (adaptador frente a recuperación + Γ) | **sin veredicto**: corrida rechazada. La capa 2 NO se retira con esta corrida |
| I1 (fuga de hechos) | **sin veredicto**: la equivalencia +0.000 es la de dos salidas idénticas |
| LC6 (olvido en el adaptador) | **sin veredicto** |
| H-C10 (repaso) | **sin veredicto** |

Lo único que la corrida sí muestra es que la recuperación con Γ (0.62–0.65)
lleva la conducta del usuario muy por encima del base (0.00–0.13) en estas
tareas, lo que coincide con R13 y con F1a.

## 3. Qué exige la próxima corrida

Una comprobación de manipulación ANTES de evaluar nada (Enmienda 15.4): el
adaptador debe cambiar la salida en sus propios ejemplos de entrenamiento
frente al base, con la misma plantilla de chat del entrenamiento y la
petición dirigida al adaptador. Si no la cambia, la corrida se niega. Debe
registrar además la diferencia de texto base/adaptador por celda, para
que un tratamiento que no llega se vea en el resumen.

Dos observaciones del diseño para esa corrida: los lotes son pequeños (6–15
ejemplos por usuario, de las claims entrenables de la wiki canónica), y la
Enmienda 9 cuenta «24 entrenamientos» cuando su propia fórmula (2 × 3 × 2 ×
2 × 2) da 48, que son los que se corrieron.

## 4. Lo que sustituye este documento

La primera versión de este documento declaraba que «la regla de muerte
preregistrada dispara» y que «la capa 2 se retira». Esa conclusión se
retira: una regla de decisión no se aplica sobre una corrida cuyo
tratamiento no se administró.

*Texto CC BY 4.0.*
