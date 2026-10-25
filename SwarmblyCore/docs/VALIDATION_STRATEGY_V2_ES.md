---
status: current
lang: es
---

# Swarmbly AI — Estrategia de validación, versión 2

## Qué hay que probar para demostrar que la arquitectura tiene futuro, es factible y es escalable

**Acompaña a `WHITEPAPER_V2_ES.md` y reemplaza
la estrategia implícita en el whitepaper v1.4. Está escrito en lenguaje llano a
propósito: su función es decidir en qué orden gastar el tiempo, no argumentar.

---

## 0. La respuesta corta

La estrategia **sí se modifica**, pero no en el objetivo. Cambia en tres cosas:
**el orden**, **el precio** y **qué cuenta como aprobar**.

| | antes (v1.4) | ahora (v2) |
|---|---|---|
| Primera prueba | Medir el impuesto de coherencia | **Arreglar el corpus.** Sin él, ninguna medición del impuesto discrimina |
| Qué se mide | Una pregunta: ¿fragmentar es caro? | Una superficie: ¿*dónde* es caro? `D(ρ, δ)` |
| Pruebas disponibles | El impuesto, H2, H3, verificación, rotación, SCI | Las mismas, **más cinco pruebas baratas** que antes no existían |
| Línea base de comparación | Monolítico de una pasada | Monolítico **y** un solo agente con self-consistency |
| Qué significa escalable | Más nodos → más cobertura | Dos ejes: cobertura **y** resolubilidad, que son independientes |
| Criterio de abandono | 5 %, cota superior del IC, preregistrado | **Sin cambios.** No se reescribe |
| Estado de la agenda | por ejecutar | **ejecutada**: 13 pruebas contra 341 corridas reales sobre cinco familias (§11) |

**El efecto neto en una línea:** lo barato pasa al frente, lo caro queda detrás
de un solo bloqueo, y una prueba se cancela. Es mejor agenda que la anterior —
pero conviene ser claro sobre por qué: no es que la arquitectura sea ahora más
probable, es que ahora se puede descartar antes de gastar.

---

## 1. Por qué cambia: la razón de fondo

La versión 1.4 trataba la fragmentación como una acción con un costo. Medías el costo y
decidías.

Los fundamentos nuevos dicen que ese costo **no es un número, es una función de
tres cosas que el diseño elige**: dónde cortas (δ, la densidad de dependencias
que cruzan el corte), de qué tamaño (L) y cuánto flanco pagas (F).

Eso tiene una consecuencia incómoda y una cómoda.

**La incómoda:** todas las mediciones anteriores del impuesto de coherencia
mezclaban las tres. No están mal, pero no son interpretables como «el costo de
fragmentar» — son el costo de fragmentar *de una manera concreta que nadie
eligió a propósito*.

**La cómoda:** si el costo depende de dónde cortas, entonces **hay cortes buenos
y cortes malos**, y encontrar los buenos es una decisión de ingeniería en lugar
de una propiedad fija de la arquitectura. Eso convierte un resultado negativo
—«fragmentar cuesta 2.30 %»— en una pregunta contestable: ¿cuál de los dos
regímenes estabas midiendo?

Y el propio dato ya lo insinúa, que es lo que hace que valga la pena perseguirlo.

---

## 2. La observación que reorganiza todo

En la medición del criterio de abandono, sobre 16 prompts reservados:

- El impuesto medio fue **+2.30 %**, IC 95 % **[−2.05 %, +7.49 %]** — criterio
  **no cumplido** por 2.49 puntos en la cota superior.
- Pero el prompt **mediano pierde exactamente 0.00 %**, y **11 de 16 quedan en
  cero o por debajo**.
- Y **dos prompts** —`tbl24_outturn` (+28.50 %) y `tbl24_bonded` (+23.08 %)— son
  entre los dos el **140 % de la media**. Sin ellos, los otros catorce promedian
  **−1.06 %**: fragmentar en dos fue levemente *mejor* que no fragmentar.

La descripción honesta no es «fragmentar cuesta 2.3 %». Es: **en 11 de 16
prompts fue gratis, y en 2 fue caro.**

Y hay una pista más, que es la que convierte esto en una hipótesis y no en una
curiosidad: **esos dos prompts son los únicos dos donde `N` = 2 es peor que
`N` = 8** (outturn +28.50 % frente a +13.57 %; bonded +23.08 % frente a
+14.00 %). Que *más* fragmentos ayuden no es lo que predice una historia de
impuesto de coherencia. Sí es lo que predice un fallo de **calidad de
partición**: un corte en dos que puso una costura en un sitio caro, y que cortar
en ocho evitó por casualidad.

> **La hipótesis que organiza la agenda:** el costo no es del fragmentar, es del
> *dónde*. Los dos prompts caros son prompts de δ alta mal cortados.

Si eso es cierto, la arquitectura no necesita ser más barata — necesita un
router que sepa reconocer el caso caro. Y eso es exactamente lo que ya hace
(P2), sólo que hoy decide con los rasgos equivocados.

---

## 3. El bloqueo único: el corpus

Antes de nada, hay un problema de instrumento y hay que resolverlo primero
porque **dos pruebas caras dependen de él**.

**Qué pasó.** Se construyó y se corrió el experimento de la curva L. El brazo
monolítico responde **1 de 72** preguntas globales, incluso con el material más
pequeño. Con la línea base en el suelo no hay diferencia que medir.

**Lo que salvó la corrida fue verificar el instrumento antes de concluir:**

- Una respuesta perfecta construida a mano puntúa **100 % en los 72 documentos**.
  El calificador no es el problema.
- Se sondearon cinco familias de modelo: **4 de 5 hacen las búsquedas locales a
  ~0.84**. Los modelos no son el problema.
- Las preguntas globales salen **4 de 60** en todas las familias.
- La hipótesis de que el envoltorio de contrato estrangulaba la respuesta global
  se probó con un A/B y **quedó refutada por su propia medición**: 4/60 en ambos
  sentidos, delta **0.000**.

**El diagnóstico es de diseño de corpus, no de arquitectura ni de instrumento.**
El corpus necesita una pregunta *global* que este parque de modelos pueda
responder sobre material pequeño.

**La regla operativa, y es importante:** la mitad reservada del corpus **no debe
correrse**. Gastar la partición reservada contra un instrumento que no
discrimina destruye la única reserva que queda, y no se puede recuperar.

**Qué hace falta.** Una pregunta global respondible es una que exija combinar
información de dos o tres lugares del documento, no de doce. La prueba de que
sirve es simple: el brazo monolítico debe acertarla claramente por encima del
piso — digamos 0.5 o más — porque si el monolítico no puede, no hay nada contra
qué comparar.

---

## 4. Las pruebas baratas, en orden de ataque

Estas cinco no necesitan corpus nuevo. Tres de ellas no necesitan medición
nueva en absoluto.

### 4.1 Separar `k` en tres — coste: cero medición

Hoy `k` paga por tres cosas distintas al precio de la más cara:

| propósito | qué compra | mecanismo correcto |
|---|---|---|
| `k_avail` — disponibilidad | que la tarea se complete aunque un nodo se caiga | sobre-despacho con umbral |
| `k_verif` — verificación | que un nodo deshonesto no imponga un resultado falso | *spot-checking* con credibilidad |
| `k_epist` — redundancia epistémica | que el mapa de divergencia tenga algo que alinear | réplicas de familias distintas |

**Es una separación conceptual de un parámetro que ya existe.** Se implementa y
se observa. No hay experimento que correr.

*Predice:* se puede bajar el costo total manteniendo las tres garantías.
*Se mata si:* resultan tan acoplados en la práctica que separarlos no ahorra
nada.

### 4.2 La compuerta de triage — coste: barato, predicción binaria

Un predicado mecánico por nivel: *¿el acarreo que llegó responde a la tarea que
lo pidió?* Sin juez, sin modelo.

*Predice:* el radio de daño de un fragmento defectuoso queda contenido en ese
fragmento. El incidente registrado de **42 de 60 paquetes que llevaban las
respuestas de otro paquete** se vuelve imposible.
*Se mata si:* rechaza tanto trabajo legítimo que el costo de reintento supera el
daño que evita.

La predicción es binaria — el incidente ocurre o no ocurre — y por eso es la
segunda más barata de resolver.

### 4.3 Unicidad asignada en el plan — coste: corpus que ya existe

Hoy se pide `term_once` en el contrato y se impone mecánicamente en el
ensamblador. Funciona, y está medido: subió el cumplimiento de **6/24 a 18/24**,
por encima del monolítico en 13/24.

La propuesta es computar el conjunto de unicidad **antes** de despachar y asignar
cada elemento a exactamente un fragmento, como propiedad del plan.

*Predice:* la tasa de violación cae **a cero**, no mejora. Un nodo no puede
cumplir «exactamente una vez» porque no sabe qué escribieron los demás; el
planificador sí.
*Se mata si:* no baja de 18/24, que es lo que ya logra la imposición mecánica.

La predicción es deliberadamente fuerte para que sea fácil de refutar. Y hay una
línea base ya medida contra la que compararla, que es lo que la hace barata.

### 4.4 Explicar la bimodalidad con δ — coste: los 16 prompts que ya corriste

Ésta es la que más información da por lo que cuesta, y no existía en la
estrategia anterior.

**Procedimiento.** Para cada uno de los 16 prompts ya medidos, calcular δ — una
medida de cuántas relaciones necesarias cruzan el corte que se hizo,
normalizada por el número de fragmentos. Después mirar si los dos prompts caros
tienen δ alta y los once gratuitos δ baja.

*Predice:* sí, y con separación clara.
*Se mata si:* δ no separa los dos grupos. Entonces la bimodalidad tiene otra
causa, el segundo eje del §6.8 del whitepaper es decoración, y M4 pierde su
motivación empírica antes de haber gastado un corpus en él.

**Por qué es valiosa:** es la prueba más barata que puede matar el modelo más
caro. Si δ no explica la bimodalidad, no vale la pena construir el corpus
calibrado que M4 necesita.

### 4.5 La ley de escala de ρ — coste: registros que ya existen

La derivación nueva dice:

```
ρ ≈ (L + 2F) / L  +  H / (L · s)
```

con `H ≈ 39` tokens de cabecera por paquete y `s ≈ 15` tokens por oración.

Eso es una **predicción de escalabilidad comprobable contra datos históricos**:
el costo por unidad de material debe *bajar* al crecer `L`, tendiendo
asintóticamente a `1 + 2F/L`.

Y hay un caso límite ya vivido: las mediciones de composición se hicieron con
fragmentos de **35 tokens** y cabecera de **39**. En ese régimen la cabecera
pesa más que el material. Si la derivación es correcta, **explica sin ajuste por
qué ρ parecía tener un piso alto** — no era una propiedad del protocolo, era
fragmentar demasiado fino.

*Procedimiento:* recuperar de los registros la ρ observada a distintos tamaños
de fragmento y superponerla a la curva predicha.
*Se mata si:* la ρ observada no sigue esa forma. Entonces la derivación está mal
y el ahorro del 29 % es ficticio.

Esta prueba no requiere correr nada. Es leer datos que ya están escritos.

---

## 5. Las pruebas caras, y de qué dependen

### 5.1 La superficie `D(ρ, δ)` — depende del corpus (§3)

Tres mediciones, todas sobre corpus con dificultad calibrada:

- **Fijar δ, variar ρ** (mismo corte, distinto flanco) → debe dar una curva
  monótona decreciente en distorsión.
- **Fijar ρ, variar δ** (mismo presupuesto, cortes de distinto acoplamiento) →
  debe dar variación de distorsión **a tasa constante**. Éste es el resultado
  que decide: si no hay variación, ρ basta como eje y el marco nuevo no aporta.
- **Buscar la región inalcanzable** → un suelo de distorsión que ningún ρ mejora.

### 5.2 La curva `L` — depende del corpus (§3)

Es la prueba que hoy no se puede correr. Lo que busca:

- **`L_min`**: existe un piso duro por debajo del cual un fragmento no es
  independientemente resoluble. Se predice que es más nítido que el óptimo.
- **La banda óptima**: se predice ancha, de factor 3 a 6, y dependiente de cómo
  definas «unidad». La analogía de origen lo respalda: sobre el mismo material,
  Pfam promedia 96 residuos y SCOP 174 — casi el doble, porque cortan con
  definiciones distintas.

**Conviene decir esto con todas sus letras:** `L_min` y la banda están
**predichos, no medidos**. Cualquier `L` que el proyecto use hoy es una conjetura
informada.

### 5.3 El alineador con sustitución aprendida — el más caro

Construir M1: segmentar en oraciones, alinear con hueco afín, matriz de
sustitución contada empíricamente al modo BLOSUM, extensión por consistencia,
perfil específico de posición.

*Predice:* separa correcto de incorrecto mejor que el conteo de coincidencias y
mejor que un escalar por respuesta — **en régimen no saturado**.
*Se mata si:* con el instrumento correcto y en un régimen donde los modelos
genuinamente discrepan, el acuerdo por unidad no supera al azar.

**La cláusula del régimen hay que declararla ahora, y por qué.** La primera
medición falló en parte porque el juez aceptaba el 93.3 % de las unidades — no
quedaba varianza contra la que pudiera aparecer una correlación. Declarar la
condición por adelantado es lo único que impide usarla como excusa después. Si
se enuncia cuando el resultado ya llegó, no vale.

**Y lo que no cambia:** la afirmación de fiabilidad del mapa de confianza
**sigue retirada**. M1 es un instrumento distinto, no una reinterpretación de
aquel resultado. Las etiquetas se reportan como *acuerdo*, nunca como
*exactitud*.

### 5.4 Re-test del criterio de abandono — depende del corpus y del tamaño de muestra

Dos condiciones, y ninguna es opcional:

**Tamaño de muestra.** La celda declarada del experimento de composición dio
media −0.35 con desviación entre grupos de 20.36 y error estándar de 4.16, para
un IC de [−8.49, +7.80] contra un umbral de 5.0 — contiene el umbral y el cero,
no decide nada. El cálculo, contrastado contra el error estándar medido, pide
**60 prompts mínimo, 72 con margen**.

**Repetir no compra nada.** El pipeline es determinista a temperatura 0. Más
corridas del mismo prompt no reducen la varianza *entre* prompts, que es la que
domina. Es un resultado negativo útil: ahorra gastar cómputo en la dirección
equivocada.

### 5.5 Lo que ya estaba y sigue igual

H2 (sustitución de capacidad), H3 (conversión), la detección de nodos
deshonestos, la latencia bajo rotación, y la medición ambiental SCI. Ninguno de
los fundamentos nuevos los toca. Toda la agenda de privacidad y verificación
queda **intacta**.

---

## 6. Qué significan ahora «factible» y «escalable»

Ésta es la parte de la pregunta que más cambia, y conviene separarla.

### 6.1 Factible

**Antes:** ¿puede un modelo de 3–8B resolver una subtarea atómica tan bien como
un modelo frontera? (H2)

**Ahora hay una pregunta anterior:** ¿este material *se deja cortar en dominios*?

Si las dependencias no se pueden evitar —si δ no baja haga uno lo que haga—
entonces ninguna calidad de trabajador salva la situación. El fragmento deja de
ser un dominio, y la garantía de independencia no aplica.

Eso mueve al router del margen al centro. La factibilidad pasa a ser, en gran
parte, **enrutabilidad**: no «¿es barato fragmentar?» sino «¿puede el sistema
reconocer de antemano los casos donde no lo es?». Y como el costo de equivocarse
es asimétrico —fragmentar algo que no debía es peor que negarse de más—, el
router se calibra con F_β y β < 1, que ya estaba, pero ahora con δ entre sus
rasgos.

### 6.2 Escalable

**Antes:** más nodos → más cobertura → mejor.

**Ahora son dos ejes independientes, y el segundo es nuevo:**

| eje | pregunta | qué lo gobierna |
|---|---|---|
| **Cobertura** | ¿llegará respuesta? | `c ≥ ln(1/ε)/(1−p)`, con *p* medido |
| **Resolubilidad** | ¿contiene la respuesta la información necesaria? | el piso informacional: `L > max{ℓ_entrelazada, ℓ_triple} + 1` |

Y son **independientes**. Puedes añadir todos los nodos que quieras y seguir en
una región donde ningún ensamblaje correcto es posible, porque los fragmentos
simplemente no contienen la información — por listo que sea el ensamblador.

**Esto ya se midió sin saberlo.** La restricción `no_repeated_ngram` se quedó en
**4/12 frente a 11/12** del monolítico bajo *toda* política de asignación de
contexto probada. Era el defecto que no cedía. La razón, ahora nombrable: una
repetición es una propiedad de *un par* de fragmentos, no de un fragmento, y un
fragmento no puede evitar repetir lo que no puede ver. Ninguna asignación
*puede* alcanzarla. Por eso la solución es M2 — resolverlo en el plan — y no más
contexto.

**Consecuencia para las pruebas de escala:** una prueba de escalabilidad tiene
que medir las dos cosas. Que la calidad aguante al crecer el material, *y* que
los fragmentos sigan siendo resolubles. Medir sólo la primera da un sistema que
escala confiadamente hacia respuestas equivocadas.

### 6.3 Con futuro

El criterio no cambia: **debe existir un ρ al que la degradación esté por debajo
del 5 % frente al monolítico, en al menos una categoría de tarea**, juzgado
contra la **cota superior** del IC del 95 % agrupado por prompt.

Lo que cambia es la lectura de un fallo. Bajo el marco nuevo, «no se cumplió» ya
no significa «la arquitectura no sirve». Significa «en el punto de la superficie
donde se midió, no se cumplió» — y la pregunta siguiente es si existe otro
punto. Eso **no es una escapatoria** siempre y cuando el punto se declare antes
de medir, que es precisamente lo que exige la preregistración.

---

## 7. Las líneas base correctas

Cambio pequeño de enunciado y grande de consecuencia.

| comparación | estado |
|---|---|
| vs. monolítico de una pasada | sigue |
| vs. **un solo agente con self-consistency** | **nuevo, obligatorio** |
| vs. decodificación especulativa | sigue, como comparador honesto de velocidad |

La razón: el trabajo de Zhang et al. encuentra que los métodos multi-agente
«fallan en superar de forma fiable a líneas base de un solo agente como
Chain-of-Thought y Self-Consistency, incluso cuando consumen cómputo adicional en
inferencia», sobre 9 benchmarks, 4 modelos y 5 métodos.

Su crítica apunta al **debate** —agentes que discuten para converger— y Swarmbly
no debate, descompone. Pero la lección transfiere igual: **el cómputo adicional
hay que justificarlo contra el rival correcto**, y el monolítico de una pasada no
lo es. Una arquitectura que sólo bate a ése se está comparando contra el rival
fácil.

Esto endurece la vara. Todas las comparaciones pasadas se ven algo menos
favorables de lo que parecían.

---

## 8. Lo que no cambia

Conviene tenerlo escrito para no rediscutirlo:

- **El criterio del 5 %**, contra la cota superior del intervalo, preregistrado.
  No se reescribe ahora que arrojó un fallo.
- **La descomposición cobertura/conversión.** El enjambre da cobertura, el
  cliente da conversión, y el techo lo pone el selector del cliente.
- **La aritmética del tamaño de muestra:** 60 prompts mínimo, 72 con margen, y
  repetir no compra nada.
- **H2 y H3** tal como están enunciadas.
- **Toda la agenda de privacidad, verificación y adversarios.** Intacta.
- **Las dos retiradas del v1.4.** La curva de impuesto decreciente en ρ y la
  afirmación de fiabilidad del mapa de confianza siguen retiradas. Nada de lo
  nuevo las levanta.

Y una prueba **se cancela**: V3c, la calibración del acuerdo, está cerrada. Se
corrió tres veces contra clave de respuesta y devolvió razones de momios comunes
de **3.47, 0.26 y 1.24** — por encima, por debajo y a caballo de 1 en la misma
pregunta. Tres estimaciones mutuamente contradictorias no son señal débil: son
ninguna señal, medida tres veces. Reabrirla exigiría un instrumento nuevo, no una
re-corrida del mismo.

---

## 9. La disciplina del instrumento

Una nota que no es sobre la arquitectura sino sobre cómo se la mide, y que vale
más que cualquiera de las mediciones individuales.

El defecto recurrente de este proyecto tiene nombre:

> **Una comprobación que afirma más de lo que midió.**

Un agregado se reporta sin preguntar de dónde viene. Apareció **cuatro veces en
un solo día**, y cada vez dentro de código escrito para atrapar la aparición
anterior: un veredicto que leía una clave que la función de bootstrap no
devolvía —y que por tanto habría dicho «no cumplido» sobre cualquier dato—; una
sonda que se degradó en silencio a una familia de modelo y concluyó sobre cinco;
un diagnóstico de dificultad derivado de un solo modelo y presentado como
propiedad del corpus; y un umbral que se disparaba por el efecto de una sola
celda.

**La defensa que funcionó no fue más cuidado. Fue hacer que la comprobación se
niegue.** Derivar la lista de familias del propio lanzador y rehusar por debajo
de dos. Retirar una conclusión agrupada si quitar el mayor contribuyente la
deshace. Cruzar el plan de tamaño de muestra contra el error estándar medido y
rehusar si difieren más de un 25 %.

Un instrumento que puede negarse vale más que uno que acierta más a menudo.

Cuatro umbrales existen por esa razón y se declaran: **20 grupos mínimo para
emitir veredicto**; **piso de línea base de 0.20**, añadido *después* de ver los
datos y etiquetado como tal en la preregistración —porque una enmienda declarada
vale y una silenciosa no—; y las dos tolerancias de control anteriores.

**Regla para todo lo que sigue:** cada prueba de este documento se implementa con
su propia condición de rechazo antes de correrla. Si no se sabe qué la haría
negarse, no está lista para correr.

---

## 10. Cuadro resumen

| # | prueba | predice | se mata si | costo | depende de | **estado** |
|---|---|---|---|---|---|---|
| 1 | Separar `k` en tres | baja el costo total manteniendo las tres garantías | los tres están tan acoplados que separarlos no ahorra | **ninguno** | nada | sin medir |
| 2 | Compuerta de triage | daño contenido en un fragmento; el incidente 42/60 imposible | rechaza tanto trabajo legítimo que el reintento cuesta más | muy bajo | nada | **sobrevive** (T02R) |
| 3 | Unicidad en el plan | violaciones a cero, no «mejor» | no baja de 18/24 | bajo | corpus de composición existente | **sobrevive corregida** (T03R) |
| 4 | δ explica la bimodalidad | los 2 caros tienen δ alta, los 11 gratis δ baja | δ no separa los grupos | **ninguno** | los 16 prompts ya corridos | **falsada** (T04, T04R) |
| 5 | Ley de escala de ρ | costo/material baja con `L` hacia `1+2F/L` | la ρ observada no sigue la curva | **ninguno** | registros existentes | **verificada** (T05R) |
| 6 | Corpus con pregunta global | el monolítico supera el piso claramente | — (es construcción, no prueba) | medio | — | **construido y verificado** (T06, T06R) |
| 7 | Superficie `D(ρ, δ)` | δ mueve la distorsión a ρ constante | la distorsión depende sólo de ρ | alto | 6 | **falsada, y es la decisiva** (T07R) |
| 8 | Curva `L` | existe `L_min` duro; óptimo en banda ancha | no hay piso ni banda discernible | alto | 6 | **medida; la banda no aparece** (T08R, T0LR) |
| 9 | Re-test del criterio | — | — | alto | 6 + 72 prompts | **rehusado**: confundido con la longitud (T09R, T11) |
| 10 | Alineador M1 | localiza mejor que agrupar, en régimen no saturado | el acuerdo no supera al azar donde hay discrepancia real | **el más alto** | 6, y construir el alineador | construido; **sin régimen** en este corpus (T10, T10R) |
| 11 | Enrutabilidad | el router anticipa las celdas caras | AUC no supera el azar | bajo | registros existentes | **falsada por celda; separa por clase** (T0RR, T0RR2) |

**Orden recomendado:** 1 → 2 → 4 → 5 → 3 → 6 → 7 → 8 → 9 → 10.

Las cuatro primeras cuestan entre nada y muy poco, y dos de ellas (4 y 5) pueden
**matar los modelos caros antes de construir nada**. Ése es el punto entero de
este reordenamiento.

---


## 11. Lo que devolvió la ejecución

La agenda se ejecutó. El instrumento son dos artefactos publicados —una
implementación de referencia y un arnés de falsación— y un registro de **341
corridas** sobre cinco familias de modelos locales. El detalle está en §15.9 del
whitepaper; aquí va lo que le pasa a **esta estrategia**.

**Tres de las cuatro pruebas baratas hicieron exactamente lo que se les pidió.**
La 4 (δ y la bimodalidad) y la 5 (ley de escala de ρ) se declararon capaces de
matar los modelos caros antes de construir nada. La 4 mató M4 sin gastar corpus.
La 5 verificó la derivación de ρ con 7.5 % de error de contabilidad. La 2
confirmó la contención del triage. El reordenamiento se pagó solo.

**Una de las predicciones de la estrategia era falsa, y conviene decirlo.** §4.4
afirmaba que la prueba 4 era gratis y podía matar M4 *antes* de construir el
corpus. No del todo: sobre los 16 prompts reservados, δ resultó **constante**
—3.50 en las 24 celdas—, y un predictor sin varianza no separa nada. La prueba 4
se pudo correr, pero su fuerza vino de un corpus de tablas mucho mayor (127
celdas intra-categoría) y del experimento controlado de la prueba 7, que **sí**
dependía del corpus. La afirmación «gratis y suficiente» era optimista.

**La prueba 7 resultó ser la decisiva, como estaba previsto, y falló.** Cortar el
mismo prompt dos veces al mismo `L` —una vez minimizando δ y otra
maximizándola— deja ρ igual y mueve sólo δ. M4 predice que el corte malo
empeora la distorsión en todos los pares; empeora en 19 de 32. Ésta es la
medición que la estrategia declaró decisiva por adelantado, y es la que decide.

**La prueba 9 no da veredicto, y el motivo es una lección de método.** El
agregado salía a favor de fragmentar, pero el brazo fragmentado recibía más
presupuesto de salida que el monolítico. El arnés **rehúsa** en vez de reportar
un criterio cumplido. La corrección está implementada y la corrida pendiente es
una sola orden.

**Y hay una prueba que esta estrategia no tenía: la 11.** No estaba en la
agenda porque la v2 daba por buena la premisa de que un router puede anticipar
el costo de una celda. Medida, no puede: AUC 0.38 con δ y reputación, 0.47 con
sondas de capacidad. Lo que sí separa es la clase de nodo. La lección para esta
estrategia es general: **las premisas que no están en la lista de pruebas son
las que más riesgo acumulan**, precisamente porque nadie las escribió como
falsables.

**Qué queda por hacer, en orden:** (1) la corrida con presupuesto de salida
igualado, que desbloquea la prueba 9; (2) un corpus que produzca desacuerdo real
entre familias, que desbloquea la 10; (3) la prueba 1, que sigue sin costar
nada y sigue sin hacerse.

---

## 12. Cierre honesto

Esta estrategia es mejor que la anterior en un sentido preciso y limitado:
**permite descartar antes de gastar**. Cuatro pruebas que cuestan entre nada y
poco pasan al frente; dos de ellas pueden falsar los modelos caros sin construir
corpus; una prueba se cancela; y el bloqueo se concentra en un solo punto — el
corpus — en lugar de estar repartido.

Lo que **no** hace es mejorar las probabilidades de la arquitectura. El criterio
de abandono no se ha cumplido ni incumplido: **no se ha medido**, y hasta igualar
el presupuesto de salida no se puede afirmar nada sobre él. La curva `L` ya es
medible y se midió: `L*` varía por familia, y la banda ancha predicha **no
aparece**. De los cinco modelos, dos quedan falsados, dos sobreviven corregidos y
uno sigue sin instrumento. Y el riesgo dominante del proyecto sigue sin ser técnico: la computación
voluntaria lleva dos décadas contrayéndose, y ningún diseño de incentivos de este
proyecto es todavía una respuesta demostrada a por qué eso se revierte.

Lo que esta agenda compra es **saberlo antes y más barato**. Que es, en un
proyecto de una sola persona, probablemente lo que más vale.

---

*Swarmbly AI — Sebastián A. Espinoza-Ulloa · Compañero en inglés:
`VALIDATION_STRATEGY_V2_EN.md`. Documento principal: `WHITEPAPER_V2_ES.md`.*
