---
status: current
lang: es
---
# tables-final sobre un instrumento corregido — el criterio NO SE CUMPLE, y la media es el estadístico equivocado

**Corrida:** `results/tables-final-20260903-153237`. La mitad final de
`prompts/tables24.json`, digest congelado `0c5cb7e2…`, verificado antes de la
corrida. Dieciséis prompts reservados, ρ = 3.5, N ∈ {2, 8}, k ∈ {1, 3}. τ_sem
**heredado** en 0.680 de `tables-dev-20260903-150427` — el runner lo lee de los
metadatos de esa corrida y se niega a arrancar si el digest del corpus o la
partición no coinciden. 80 filas.

**Esta mitad está gastada. No hay una segunda.**

> **Procedencia, revisada antes de leer nada de lo de abajo.**
> `harness_validation_only: false`, `embeddings_degraded: false` — modelos
> reales, embeddings reales. `rows_excluded_below_floor: 0` — toda celda quedó
> por encima de su propio piso de empaquetado, así que ρ aquí es un eje y no una
> etiqueta. `rho_fidelity.within_tolerance: true`. Huella del código
> `4abed34a…`, semilla 0. Cinco familias de modelos distintas, `n_families_mean`
> 3.0 en las filas con k > 1.

> # ⚠ LA CELDA DECLARADA ESTABA POR ENCIMA DEL TECHO DE EMPAQUETADO — 4 de septiembre de 2026
>
> **La celda nombrada en la preinscripción, `table_summary@rho=3.5@N=2@k=1`, no
> se puede correr. Está por encima de lo que el empaquetador puede producir, y
> lo que se midió es la celda del techo, con ρ ≈ 3.38.**
>
> `packing_ceiling` se agregó el 4 de septiembre, después de que el tramo v0
> muriera pidiendo un ρ que ningún paquete podía contener. Aplicado a este
> corpus dice que el brazo N=2 sobre `tables24` tope en **3.37**: un paquete no
> puede contener más que sus bloques obligatorios más su contexto natural más
> `_expansion_blocks`, y esa lista es finita.
>
> Los propios números de la corrida coinciden, y el patrón es inconfundible una
> vez que se lo busca:
>
> | brazo | objetivo | alcanzado | deriva |
> |---|---|---|---|
> | **N=2, k=1** | 3.5 | 3.358 – 3.386 | **−3.42 % de media, ni una sola vez por encima** |
> | N=2, k=3 | 3.5 | 3.370 – 3.386 | −3.30 %, nunca por encima |
> | N=8, k=1 | 3.5 | **3.506** | +0.17 % |
> | N=8, k=3 | 3.5 | **3.506** | +0.17 % |
>
> Toda fila N=2 quedó corta. Ninguna se pasó. Una celda que apenas deriva se
> dispersa hacia ambos lados; una celda clavada en su techo solo puede quedarse
> corta. El brazo N=8, con un techo de 10.5, dio en su objetivo exactamente.
>
> **`rho_fidelity.within_tolerance: true` no está equivocado** — la deriva es de
> 3.4 % contra una tolerancia de 5 %. El chequeo preguntaba si el empaquetador
> se había portado mal, y no. Nada preguntaba si el objetivo era *alcanzable*, y
> ahí está el hueco.
>
> **Qué cuesta esto, dicho con precisión y sin inflarlo.**
>
> - **La etiqueta está mal.** La celda no es "ρ = 3.5, N = 2". Es "N = 2 con el
>   mayor contexto que puede contener una partición en dos de este corpus".
>   Cualquier ρ por encima de 3.37 habría producido los mismos paquetes, que es
>   el mismo argumento sobre el que se apoya el piso, desde el otro lado.
> - **La preinscripción nombró una celda que no existe.** Esa es la descripción
>   honesta, y es incómoda: el aparato se construyó para impedir que una celda
>   se eligiera después de los hechos, y lo logró — solo que no revisó que la
>   celda elegida de antemano fuera alcanzable.
> - **Los dos brazos no estaban con el mismo ρ.** N=2 corrió con 3.38 y N=8 con
>   3.51, así que el brazo bajo prueba recibió alrededor de 4 % menos de
>   contexto que su control.
> - **La dirección es la incómoda.** Menos contexto empeora al brazo
>   fragmentado, lo que empuja el impuesto hacia arriba, lo que empuja hacia NO
>   CUMPLIDO. El veredicto y el artefacto apuntan al mismo lado. Esa es
>   exactamente la configuración que exige cautela y no confianza, y por eso
>   esto es un aviso y no una nota al pie.
>
> **Qué NO queda afectado.**
>
> - El control N=8, que no estaba ni cerca de su techo.
> - `comp-dev` y `comp-final` del 4 de septiembre. Revisado: su ρ alcanzado se
>   dispersa **simétricamente** alrededor de 4.000 — 7 celdas por encima y 6 por
>   debajo con N=3, media 4.0004 — y una celda clavada en el techo solo puede
>   quedarse corta. El veredicto de composición se sostiene.
> - El hallazgo cualitativo de §2 en adelante, que la media es aquí el
>   estadístico equivocado. Ese argumento es sobre la distribución entre prompts
>   y no depende del ρ exacto.
>
> **No retirado, y la distinción es deliberada.** La curva de ρ de V0 se retiró
> porque sus celdas quedaban *por debajo* del piso, donde el eje ρ está muerto y
> una curva graficada contra él es una curva contra nada. Este documento reporta
> una celda y no una curva, así que un eje muerto no lo vacía — la comparación
> que hace fue real, con un ρ que no nombró correctamente. **Vuelva a correr la
> celda con ρ = 3.0, dentro de la ventana [1.20, 3.35], antes de citar la cifra
> como una prueba del criterio declarado.** Unas tres horas, dev y final.
>
> Encontrado porque falló el tramo v0, que es la segunda vez esta semana que una
> compuerta disparándose ha valido más que la corrida que detuvo.

---

## 1. El veredicto

Declarado antes de la corrida y sin cambios desde la preinscripción original:
`table_summary` con ρ = 3.5, N = 2, k = 1 cuesta menos de 5 %, juzgado sobre la
**cota superior** de un intervalo bootstrap del 95 % agrupado por prompt.

| celda | punto | IC del 95 % (16 prompts) | veredicto |
|---|---|---|---|
| **N = 2, k = 1 — bajo prueba** | **+2.30 %** | **[−2.05 %, +7.49 %]** | **NO CUMPLIDO** — corto por 2.49 puntos en la cota superior |
| N = 8, k = 1 — control, debe fallar | +16.23 % | [+11.33 %, +20.28 %] | falla como se requiere |

El control se comporta: su intervalo excluye el cero, queda entero por encima
del umbral, y **no se solapa** con el brazo bajo prueba. El instrumento separa
N = 2 de N = 8. Sin eso, ninguna de las dos cifras sería evidencia.

El criterio no se cumple y no se lo está reescribiendo. La estimación puntual
supera el 5 % con holgura; el intervalo no, y el criterio se escribió contra el
intervalo precisamente para que una estimación puntual favorable no pudiera
sostenerlo sola.

## 2. La media es el estadístico equivocado para este resultado

El titular esconde el hallazgo. Por prompt, con N = 2, k = 1:

| | conteo |
|---|---|
| impuesto de coherencia **negativo** (fragmentar fue mejor) | 6 |
| impuesto de coherencia **exactamente cero** | 5 |
| impuesto de coherencia positivo | 5 |
| **en cero o por debajo** | **11 de 16** |

**El prompt mediano no pierde nada.** Y la media no está apenas jalada por los
prompts positivos — está *fabricada* por dos de ellos:

| prompt | impuesto con N = 2 |
|---|---|
| `tbl24_outturn` | **+28.50 %** |
| `tbl24_bonded` | **+23.08 %** |
| `tbl24_demurrage` | +7.14 % |
| `tbl24_clearance` | +6.67 % |
| `tbl24_holdover` | +4.55 % |

Esos dos suman **+0.516 contra un total de +0.368 — el 140 % de él.** Quítelos y
la media sobre los catorce prompts restantes es **−1.06 %**: fragmentar en dos
es, sobre esos, muy levemente *mejor* que no fragmentar en absoluto.

Así que "la fragmentación cuesta 2.3 %" es una mala descripción de lo que pasó.
Lo que pasó es: **en once de dieciséis prompts de resumen de tablas, partir el
trabajo en dos salió gratis, y en dos de ellos salió caro.** El corpus todavía
no dice qué los distingue — pero §4 tiene una pista fuerte.

## 3. El control, y cuánto cuesta N = 8

| | N = 2 | N = 8 |
|---|---|---|
| media | +2.30 % | +16.23 % |
| mediana | **0.00 %** | +18.59 % |
| prompts en cero o por debajo | 11 / 16 | **1 / 16** |

Con ocho fragmentos el costo es real, consistente y grande: quince de dieciséis
prompts quedan peor que su baseline monolítico, la mediana es +18.6 %, y el
intervalo no está ni cerca del umbral. Lo que es gratis con N = 2 no es
enfáticamente gratis con N = 8.

Esta es la forma que la arquitectura necesita: un ancho de partición donde el
costo se desvanece para la mayor parte del trabajo, y un ancho donde no. Es
también la primera vez que los dos se miden lado a lado sobre un instrumento
corregido, con un control que pudo haber fallado y no falló.

## 4. La inversión, que es una pista de mecanismo y no ruido

Ordenar por costo con N = 2 pone los dos prompts caros al fondo — y son **los
dos únicos prompts donde N = 2 es PEOR que N = 8**:

| prompt | N = 2 | N = 8 | |
|---|---|---|---|
| `tbl24_outturn` | **+28.50 %** | +13.57 % | N=2 peor por 15 puntos |
| `tbl24_bonded` | **+23.08 %** | +14.00 % | N=2 peor por 9 puntos |
| todos los demás prompts | ≤ +7.14 % | ≥ +7.68 % | N=8 peor, siempre |

Que más fragmentos *ayuden* no es lo que predice una historia de impuesto de
coherencia. Lo que salió mal en `outturn` y `bonded` con N = 2 es por tanto poco
probable que sea "la fragmentación degrada la coherencia" — eso empeoraría con
N, no mejoraría. Parece una falla de **calidad de partición**: la partición en
dos que el planner hace de esos prompts en particular pone una costura en algún
lugar costoso, y cortar en ocho da la casualidad de evitarla.

Esa es una afirmación comprobable y es lo más valioso que produjo esta corrida.
**No** se comprueba aquí.

Una fila más que vale nombrar: `tbl24_closeout` es negativo en *ambos* brazos
(−11.1 % con N = 2, −11.5 % con N = 8) y tiene el baseline monolítico más débil
del corpus (0.583). Un prompt que el brazo monolítico maneja mal es un prompt
donde fragmentar solo puede ayudar, y debe leerse como una falla del baseline y
no como un éxito de la fragmentación.

## 5. Contra la medición retirada

| | 27 ago (instrumento defectuoso) | 3 sep (corregido) |
|---|---|---|
| punto | +3.26 % | **+2.30 %** |
| IC del 95 % | [−0.02 %, +6.93 %] | **[−2.05 %, +7.49 %]** |
| mediana | +1.16 % | **0.00 %** |
| prompts ≤ 0 | 8 / 16 | **11 / 16** |
| veredicto | NO CUMPLIDO | **NO CUMPLIDO** |

El veredicto no cambia y la estimación puntual bajó alrededor de un punto, como
predecía la dirección de los defectos — cada uno de los doce estaba sesgado a un
solo lado, hacia un impuesto aparente mayor. El intervalo es levemente *más
ancho*, no más angosto, que es la consecuencia honesta de quitar un instrumento
que fabricaba acuerdo entre prompts.

La distribución se movió mucho más que la media: la mediana pasó de +1.16 % a
exactamente cero, y tres prompts más cruzaron al lado gratis. **El instrumento
corregido no cambió la respuesta a la pregunta declarada. Cambió de qué se
tratan los datos.**

## 6. Lo que se reporta y no se declara

**k = 3 es caro y no compra nada medible.** El consenso por alineamiento
múltiple cuesta alrededor de 14 puntos con N = 2 y 25 con N = 8 contra las
mismas celdas con k = 1. Contra cuatro mediciones de si el acuerdo predice la
calidad — una correlación plana y tres razones de momios contra ground truth de
3.47, 0.26 y 1.24 — eso es un cuarto de la calidad de salida gastado en una
señal para la que no hay evidencia.

**El juez aceptó el 100 % de 1517 unidades.** Saturación total. El harness
retuvo la correlación en vez de imprimir un número ininterpretable, que es el
comportamiento que debió haber existido el 14 de agosto. Toda cifra basada en el
juez de esta corrida está ausente, no en cero.

**La grilla de entidades sigue siendo inutilizable en este corpus:** 24 celdas
excluidas por un denominador monolítico cercano a cero. Lea las diferencias
absolutas, nunca la razón.

## 7. Qué autoriza y qué no autoriza esto

**No autoriza la afirmación que el criterio prueba.** Con ρ = 3.5, N = 2, sobre
16 prompts reservados, la cota superior del intervalo es 7.49 % contra un umbral
de 5 %. La arquitectura no ha superado la barra que se puso a sí misma.

**Sí autoriza una afirmación más estrecha y más útil**, que el criterio no fue
diseñado para preguntar: en este corpus, con dos fragmentos, **el costo mediano
de la fragmentación es cero**, y la media la cargan dos prompts de dieciséis.

Esa diferencia importa para el diseño y no para el paper. Un criterio de umbral
pregunta "¿es aceptable el costo promedio?", que es la pregunta equivocada para
un protocolo de ruteo — el router no tiene que aceptar el promedio, decide por
petición. Un costo bimodal con una frontera identificable vale más que uno
uniforme y bajo, porque es **enrutable**. El clasificador de descomponibilidad
de V1 deja de ser una optimización y pasa a ser el mecanismo del que depende el
resto del diseño.

**Enseguida, en orden de valor:**

1. **Diagnosticar `outturn` y `bonded`.** Dos prompts cargan el 140 % de la
   media y son los dos únicos donde N = 2 le gana a N = 8. Lea sus costuras y su
   plan en dos. Si es una falla de calidad de partición el planner se puede
   arreglar, y la celda declarada probablemente superaría entonces su umbral —
   lo cual es una razón para tener cuidado, no para animarse: arreglar el
   planner *después* de ver qué prompts duelen es ajustar sobre la mitad final.
   Todo cambio del planner debe evaluarse sobre un corpus nuevo, no sobre estos
   dieciséis.
2. **Ampliar el corpus** antes de volver a probar el criterio. Con una varianza
   entre prompts de este tamaño, dieciséis prompts no pueden bajar un intervalo
   de 9.5 puntos por debajo de un umbral de 5 puntos, sea cual sea el efecto
   verdadero. Eso es un hecho aritmético sobre el diseño, no un resultado.
3. **Sacar k > 1 de la grilla de coherencia.** Cuesta un cuarto de la calidad y
   responde una pregunta que ha sido retirada.
