---
status: current
lang: es
---

# Preregistro — R12: el plano social (C9, H-C11, H-C8)

**9 de octubre de 2026 · escrito ANTES de cualquier corrida de R12**

Preregistro separado del plano social, como declara `PREREGISTRATION_BENCH_R1X_ES.md`
sección 4. **El conjunto canario debe estar VERIFICADO por hablantes nativos para la
corrida confirmatoria** (≥2 de 3 verificadores seudónimos confirman cada
glosa y ninguno la marca ofensiva; regla en `canary_verify.py`). La corrida
EXPLORATORIA con el canario sin verificar está permitida y reporta solo el
MECANISMO, nunca cifras sobre los términos.

## 1. Rediseño (corrige los límites declarados del C9-lite)

1. **Sonda de identidad CON las cápsulas adoptadas en el contexto** — la
   versión anterior la pasaba sin contexto y contaba la misma respuesta dos
   veces en ambos brazos.
2. **Brazo PREVALENCIA real**: adopta la VARIANTE MAYORITARIA entre las
   glosas de los nodos (aunque sea errónea) — no coincidencias con la clave.
3. **Utilidad juzgada por beneficio posterior, sin la clave**: un nodo adopta
   si la glosa de la cápsula no está contenida en su propia respuesta previa.
4. **Cápsulas con el conocimiento del nodo fuente**: la glosa de la cápsula
   es la respuesta del modelo del nodo fuente, no la del archivo.
5. **Varias rondas** (2 rondas de intercambio) y **F_ST** sobre las
   frecuencias de variantes por ronda, con Nm = rondas.

## 2. Diseño

5 nodos (una familia cada uno: qwen2.5:3b, llama3.2:3b, gemma2:2b,
phi3.5:3.8b, granite3.1-dense:2b), 8 términos canarios. Pre-test: cada nodo
glosa cada término con su modelo base. Ronda 1: cada nodo publica cápsulas
con SUS glosas (las correctas según la clave o las suyas propias: se registra
cuál). Los demás adoptan según el brazo. Post-test e identidad por ronda.
Ronda 2: se repite con el almacén acumulado.

## 3. Reglas de decisión

| Hipótesis | Se sostiene | Muere | Si no |
|---|---|---|---|
| H-C11 (dirección) | violaciones de identidad UTILIDAD < PREVALENCIA con ≥5 violaciones totales | UTILIDAD ≥ PREVALENCIA | señal insuficiente |
| H-C5 (persistencia por uso) | la masa de colas no cae entre rondas en el brazo utilidad | cae de forma sostenida | — |
| H-C8 (banda de migración) | la utilidad en contenido raro es máxima en un Nm intermedio | monótona en Nm | la homología de Wright vuelve a vocabulario |

**Rechazos**: canario sin verificar (solo en confirmatoria), <5 nodos
respondiendo, >10 % de respuestas no calificables.

## 4. Alcance declarado

Exploratorio (canario sin verificar): solo mecanismo. Confirmatorio
(canario verificado): las cifras de H-C11/H-C5/H-C8.

*Texto CC BY 4.0.*
