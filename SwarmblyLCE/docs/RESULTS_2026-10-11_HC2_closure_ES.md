---
status: current
lang: es
kind: descriptive
---

# Resultados — cierre de H-C2 (ρ frente a su ganancia): descripción, sin veredicto

**11 de octubre de 2026 · preregistro `PREREGISTRATION_BENCH_R1X_ES.md`,
sección 2.9, con la Enmienda 15.6 · commit `c614fd1` · Python 3.9.6
(Enmienda 15.1) · 251 tareas, las celdas de la confirmatoria de R13**

Salidas en `results/bench_hc2_closure/results.json`; código en
`lce_validation/bench_hc2_closure.py`.

## 1. Cifras

| Medida | Valor |
|---|---|
| tareas | 251 |
| ganancia media con Γ (A4 − A3, exactitud de QA) | +0.0159 |
| tareas con ganancia > 0 | 14 (fracción 0.0558); 10 con ganancia < 0; 227 sin cambio |
| Δρ mediana | 40.98 % (rango 15.0–96.2 %) |
| fracción con ganancia > 0 y Δρ ≤ 10 % | 0.0 |

## 2. Por qué es una descripción y no un veredicto

La sección 2.9 pide, por tarea, la ganancia de **adherencia** con Γ y el Δρ
medido con el **planificador y el packer reales** de Swarmbly. La corrida
midió otra cosa en los dos ejes (Enmienda 15.6):

1. La ganancia es exactitud de pregunta-respuesta (A4 − A3), no adherencia
   a las preferencias del usuario, que es lo que H-C2 afirma.
2. Δρ no pasa por el packer: se calcula como los tokens de Γ añadidos a
   cada fragmento sobre los tokens del contexto recuperado. Es una cota
   aritmética, no una medida de despacho; la medida con el packer real
   (+5.8 a +7.8 % por paquete, mediana +7 %) está en `results/bench_rho/`.
3. La ganancia por tarea sale de un solo par digestor = respondedor, porque
   el diccionario por pregunta conserva la última celda de la diagonal.
4. La regla «fracción de tareas con ganancia > 0 y Δρ ≤ 10 % ≥ 0.8» es casi
   inalcanzable con ganancias binarias por tarea: exige que el 80 % de las
   tareas mejoren. El error es de este preregistro, no de los datos.

## 3. Lectura

En pregunta-respuesta, añadir Γ cuesta contexto y casi no cambia la
exactitud (también A4 − A3 en la confirmatoria de R13: −0.036, −0.024 y
+0.016 por digestor). Eso es coherente con el diseño: Γ transporta
preferencias de forma, no hechos, y no se espera que mejore la exactitud de
QA. **H-C2 queda sin decidir para su caso de uso, la escritura**: la medida
que lo decide (adherencia por tarea frente a Δρ con el packer real) sigue
pendiente, y su regla de compensación debe reescribirse por enmienda antes
de correr.

## 4. Lo que sustituye este documento

El commit de la corrida y la primera versión de la SWIP y del reporte
declaraban que «la proyección NO sobrevive la regla de compensación» y
hablaban de «ganancia de adherencia». Esa conclusión se retira.

*Texto CC BY 4.0.*
