---
status: current
lang: es
---

# Swarmbly AI — Extensión del whitepaper

## Fundamentos de fragmentación: homologías con instrumento

**Extiende el whitepaper v1, al que supone leído.** Su objeto son los fundamentos nuevos: de qué tamaño es un fragmento, qué
comparten los fragmentos vecinos, qué restricciones cruzan el conjunto, cómo se
coordina, y cuál es el precio teórico de todo ello.

---

## 0. Qué es este documento y qué no

El whitepaper v1 describe una arquitectura. Este documento examina sus
**fundamentos**: las analogías biológicas de las que salieron las decisiones de
diseño, cuáles de ellas resisten, y qué las reemplaza cuando no resisten.

Tres cosas conviene decir de entrada.

**Se escribe contra la bibliografía, no contra la intuición.** Cada transferencia
se contrasta con la literatura primaria del campo de origen. Cuatro hipótesis
entraron a ese contraste; **dos no sobrevivieron**, y las secciones 5 y 8
documentan su caída con más detalle que su reemplazo, porque la caída es el
resultado.

**Cita la evidencia propia donde sostiene una decisión.** No es un catálogo de
mediciones —ésas viven en el registro de resultados— pero cuando una medición
del proyecto justifica un cambio de fundamento, aparece.

**No está listo para publicarse.** Varios de los modelos que propone son
falsables y no han sido falsados todavía. La sección 10 enuncia qué predice cada
uno y cómo se lo mata.

---

## 1. El método: qué hace que una homología sirva

### 1.1 El problema con las analogías

Swarmbly nació de una analogía: una petición demasiado grande para un modelo
pequeño se parece a un genoma demasiado largo para un secuenciador. Se rompe, se
lee por partes, se reconstruye.

Las analogías de ese tipo son productivas al principio y peligrosas después. Son
productivas porque importan vocabulario maduro para un problema nuevo. Son
peligrosas porque el vocabulario viene con connotaciones que no se transfieren,
y porque una analogía que suena bien resiste el escrutinio precisamente por eso.

El whitepaper v1 ya enuncia la cautela —ningún algoritmo de ensamblaje genómico
corre dentro de Swarmbly— pero no ofrece un criterio para decidir cuándo una
transferencia es real. Esta sección propone uno.

### 1.2 La prueba del instrumento

> **Una homología sirve cuando trae un instrumento: un procedimiento, una
> desigualdad o un número que se puede aplicar al problema nuevo. No sirve
> cuando trae sólo una manera de hablar.**

El caso claro es la ecuación de cobertura. Lander & Waterman (1988) derivan, para
el mapeo genómico por clones aleatorios, que el número esperado de islas es
`N·e^(−cθ)` con `c = LN/G`. Esa derivación entrega un número —cuántas réplicas
hacen falta— que antes era una conjetura. Es un instrumento.

El caso contrario, y hay que decirlo porque es del propio proyecto: llamar
*contig* a un fragmento de respuesta no hace nada. Es vocabulario.

### 1.3 La prueba del modo de fallo, que resultó ser la más discriminante

Al aplicar la prueba del instrumento a las cinco homologías que el proyecto usa,
emergió un patrón que no se había buscado:

> **Las homologías que transfieren vienen acompañadas de su modo de fallo. Las
> que no transfieren traen un mecanismo sin su patología asociada.**

El criterio de solapamiento mínimo viene con el *mis-assembly*: si el
solapamiento no excede la repetición, el ensamblador pega los tramos
equivocados. El dominio proteico viene con su condición de interfaz: la
independencia se pierde cuando la interfaz es grande y empaquetada. El triage de
chaperonas viene con la degradación: lo irrecuperable se destruye, no se acopla.

En cambio el codón —que la sección 2 descarta— se propuso como «la unidad mínima
de significado» sin ningún enunciado sobre qué ocurre cuando se la viola. Los
*fountain codes* —sección 8— se propusieron por su propiedad de recuperación sin
ninguna condición sobre cuándo esa propiedad deja de existir.

La razón es que un campo maduro no descubre un mecanismo aislado: descubre un
mecanismo **y** los casos donde falla, y suele publicar los segundos con más
cuidado que los primeros. Una transferencia que sólo trae la parte buena está
importando la conclusión sin el trabajo.

Esto da una prueba operativa, y es la que organiza el resto del documento:

| pregunta | si la respuesta es no |
|---|---|
| ¿Trae un procedimiento, una desigualdad o un número? | Es vocabulario. Úsese como vocabulario. |
| ¿Trae el enunciado de qué ocurre cuando la condición se viola? | Está importada a medias. Búsquese el modo de fallo antes de construir sobre ella. |
| ¿Las condiciones del campo de origen se cumplen aquí? | Transferencia inválida. Dígase por qué, que suele ser informativo. |

---

## 2. La unidad semántica: dos homólogos para dos cosas distintas

### 2.1 El codón no es el homólogo

La propuesta original tomó el **codón** —tres nucleótidos que se traducen a un
aminoácido— como homólogo de la unidad mínima de significado del texto, y de ahí
derivó que existe un tamaño mínimo de fragmento por debajo del cual se destruye
significado.

La conclusión es correcta. La derivación no. El codón tiene tres propiedades
estructurales, y la oración no tiene ninguna:

| propiedad del codón | la oración |
|---|---|
| **Ancho fijo** — exactamente 3 nucleótidos | Variable. Medido sobre el corpus del proyecto: p25 = 9 tokens, p75 = 25. Casi 3× de rango. |
| **Marco de lectura** — no se solapa; un corrimiento arruina todo río abajo | No hay marco. Un corte desplazado no destruye el resto del texto. |
| **Mapa determinista** — `GGA` es siempre glicina | La misma idea admite infinitas superficies textuales. |

Tres de tres. La transferencia no es parcial: es nula en las tres propiedades
que definen al codón.

### 2.2 El aminoácido es el homólogo de la unidad de alineamiento

La tercera fila señala dónde sí encaja. El aminoácido es una unidad de **ancho
variable**, **auto-delimitada**, con **propiedades propias**, y es **la unidad de
la estructura plegada**. La oración comparte las cuatro.

Y la distinción no es terminológica, porque la biología computacional tiene **dos
tecnologías de alineamiento** y la elección del homólogo determina cuál se
hereda:

- **Alineamiento de nucleótidos** — identidad o no. `A` frente a `G` es un
  desacuerdo y punto.
- **Alineamiento de proteínas** — matrices de sustitución. Henikoff & Henikoff
  (1992) construyen BLOSUM contando pares de aminoácidos alineados en bloques
  ungapped y calculando, para cada par, `s_ij = log₂(q_ij / e_ij)`, el logaritmo
  de la razón entre la frecuencia observada y la esperada, en unidades de medio
  bit.

Esa fórmula es el instrumento. Dice que la intercambiabilidad de dos unidades no
se postula: **se cuenta**, sobre casos que ya se sabe que son homólogos.

Para Swarmbly la consecuencia es directa. Dos nodos que responden

> «The tide window closes at noon.»
> «The channel shuts at midday.»

no están en desacuerdo. Bajo comparación tipo nucleótido son un desacuerdo
total; bajo una matriz de sustitución son una **sustitución conservativa**.

### 2.3 El dominio es el homólogo del fragmento

Aquí está la corrección más importante de este documento, y es una que la
propuesta original no contenía.

El aminoácido no es el homólogo del **fragmento**. Ningún aminoácido se pliega
solo ni tiene función solo. La unidad que sí lo hace es el **dominio**.

Porter & Rose (2012) dan la definición rigurosa: un dominio es *«un segmento
contiguo de la proteína plegada cuyo valor-m queda mayormente inalterado cuando
ese segmento se extrae de su estructura madre»*, y equivalen dominio a *«unidad
cooperativa de plegado; es decir, su cooperatividad depende principalmente de
interacciones intra-segmento, no inter-segmento»*.

Léase la segunda cláusula con cuidado, porque **es la especificación de un buen
fragmento de tarea**: una pieza cuya resolución depende de lo que tiene dentro y
no de lo que tienen sus vecinas.

El trabajo de referencia sobre proteínas multidominio (Han et al., 2007)
confirma que más del 70 % de las proteínas eucariotas son multidominio y que el
plegado de los dominios es independiente — **pero con una condición explícita**:
*«donde la interfaz es pequeña y poco empaquetada, o no estructurada, el plegado
de los dominios es independiente»*.

### 2.4 La condición de interfaz es la regla de corte

Esa condición no es una salvedad a pie de página. Es el instrumento:

> **Fragméntese donde el acoplamiento entre fragmentos es débil. El límite de
> fragmento es una decisión sobre la interfaz, no sobre el tamaño.**

Esto reordena el diseño. El planificador no debe cortar cada `L` oraciones y
esperar que salga bien: debe **buscar los puntos de acoplamiento débil** y cortar
ahí, con `L` como objetivo y no como regla. Un corte que parte una dependencia
fuerte produce dos fragmentos que no son dominios, y la garantía de
independencia no aplica a ninguno de los dos.

El proyecto ya tiene un incidente que es exactamente este fallo: el segmentador
separó una pregunta del material que la respondía. Eso no fue un error de
implementación, fue un corte a través de una interfaz fuerte. Con la formulación
anterior —cortar en N partes de tamaño parecido— ese fallo es estructural y
recurrente. Con la regla de interfaz, es detectable antes de despachar.

### 2.5 La autonomía funcional está cuantificada, y no es total

Bashton & Chothia (2007) comparan dominios homólogos que aparecen tanto en
proteínas de un dominio como en multidominio, sobre 70 pares únicos de dominios
en 45 conjuntos de proteínas: aproximadamente **tres cuartas partes conservan su
función** al cambiar de contexto; **poco menos de un sexto cambia
sustancialmente**.

El número es útil porque acota la expectativa. «Un fragmento resuelto
aisladamente vale igual que en contexto» es cierto la mayoría de las veces y
falso una de cada seis o siete. Un diseño que asuma autonomía total está
asumiendo algo que la naturaleza no cumple ni en el sistema del que se tomó
prestada la idea.

### 2.6 El tamaño: hay una banda, no hay un número

La pregunta natural es si existe un tamaño natural de dominio que sugiera un `L`
natural para el texto. La respuesta honesta es que **existe una banda
característica y no existe un número**, y la razón por la que no existe es
instructiva.

Zhang et al. (2005) mapean dominios definidos por secuencia contra dominios
definidos por estructura, sobre las mismas proteínas: **Pfam promedia 96
residuos; SCOP promedia 174**. Casi el doble, sobre el mismo material, en el
mismo trabajo. La diferencia no es ruido: es que Pfam corta por familia de
secuencia y SCOP por estructura. **La definición determina el número.**

Schaeffer et al. (2023), clasificando dominios sobre estructuras predichas,
reportan **99.8 ± 64.8 residuos** — una desviación estándar que es el 65 % de la
media.

El piso, en cambio, sí es nítido. Porter & Rose fijan **25 residuos** como mínimo,
*«aproximando el tamaño de una unidad de estructura supersecundaria»*; UniDoc
(Zhu et al., 2023) usa 30 como restricción de parseo.

Las dos lecciones transfieren limpiamente:

1. **El piso es duro y principiado.** Por debajo de cierto tamaño nada pliega
   cooperativamente. Para el texto, esto predice que existe un `L_min` por
   debajo del cual un fragmento no es independientemente resoluble, y que ese
   piso es más nítido que el óptimo.
2. **El óptimo es una banda ancha y dependiente de la definición.** Cualquier
   afirmación de que `L* = 50` es un número es una sobre-lectura. Lo que se
   puede esperar es una banda de factor 3 a 6, y la definición de «unidad» que
   se elija moverá su centro.

### 2.7 Los fundamentos revisados de la unidad semántica

1. La unidad mínima de alineamiento es la **oración**, homóloga del aminoácido:
   ancho variable, auto-delimitada, con significado propio, y la unidad sobre la
   que se calcula sustitución.
2. La unidad de fragmentación es el **dominio de tarea**, homólogo del dominio
   proteico: el segmento cuya resolución depende de interacciones internas y no
   de sus vecinos.
3. El límite de fragmento se elige **donde el acoplamiento es débil**, con `L`
   como objetivo en oraciones y no como regla de división.
4. `L` es una propiedad de la **clase de nodo**, medida y revisable. `N` se
   deriva: `N = ⌈material / L⌉`.
5. Existe un `L_min` duro; el óptimo es una banda.

---

## 3. El alineamiento y el mapa de confianza

### 3.1 Qué es el mapa de confianza, en términos del diseño

Cuando una micro-tarea se despacha a `k` nodos de familias distintas, vuelven `k`
respuestas al mismo problema. El mapa de confianza es la anotación, **unidad por
unidad**, de dónde esas respuestas convergieron y dónde se separaron.

La propiedad estructural que lo hace interesante es que **un proveedor con un
solo modelo no tiene nada que alinear**. Puede dar la probabilidad interna del
modelo sobre su propia salida, que es una medida de confianza en sí mismo, no una
corroboración independiente.

### 3.2 El estado del arte: se agrupa, no se alinea

La literatura reciente sobre incertidumbre en generación es abundante y buena, y
conviene situarse frente a ella con precisión.

**Entropía semántica** (Kuhn, Gal & Farquhar, ICLR 2023; Farquhar et al.,
*Nature* 2024) muestrea varias respuestas, las agrupa por equivalencia semántica
mediante **implicación bidireccional** —A implica B y B implica A, luego mismo
grupo— y calcula la entropía sobre los grupos de significado en vez de sobre las
secuencias de tokens. AUROC promedio 0.790 sobre 30 combinaciones de modelo y
tarea.

**SelfCheckGPT** (Manakul, Liusie & Gales, EMNLP 2023) produce puntuaciones de
factualidad **por oración** comparando cada oración contra muestras completas.

**Acuerdo semántico entre modelos distintos** (Soiffer, Kolawole & Smith, 2025 —
preprint) usa el acuerdo entre un conjunto de modelos más pequeños como señal de
derivación hacia un modelo mayor: *«cuando salidas generadas independientemente
son semánticamente consistentes —aunque léxicamente distintas— su acuerdo
sugiere que el significado subyacente es fiable»*. Es, arquitectónicamente, el
vecino más cercano a Swarmbly.

**Lo que todos comparten, y es la apertura:** tratan las `k` respuestas como **una
bolsa que se agrupa**. Ninguno las trata como **secuencias que se alinean**. Esa
diferencia no es estilística: agrupar da un escalar por respuesta (o, en
SelfCheckGPT, una puntuación por oración obtenida comparando contra muestras
enteras); alinear da una correspondencia **posición a posición** entre las
respuestas, que es lo que permite decir *dónde* divergieron y no sólo *cuánto*.

### 3.3 El instrumento: alineamiento múltiple con costo de sustitución

La maquinaria existe y está madura.

**El costo de sustitución se aprende, no se postula.** Es la lección de BLOSUM
(§2.2), y en el dominio del texto ya está resuelta a nivel de cadenas: Ristad &
Yianilos (1998) dan *«un algoritmo eficiente para aprender los costos primitivos
de edición a partir de un corpus de ejemplos»*, mediante un transductor
estocástico ajustado por EM.

**Y está resuelta a nivel de frases.** PPDB 2.0 (Pavlick et al., ACL 2015) es una
base de paráfrasis re-puntuada discriminativamente: recogieron juicios humanos
sobre **26.455 pares**, cada uno evaluado por 5 personas en escala Likert de 5
puntos, y ajustaron una regresión ridge sobre **209 rasgos** (los 33 de PPDB 1.0
más 176 nuevos).

El resultado es el dato más útil de toda esta investigación para el proyecto:

> **El ranking heurístico correlacionaba con el juicio humano a ρ = 0.41. El
> modelo ajustado empíricamente alcanzó ρ = 0.71. Y en ese modelo el coseno de
> embedding es un rasgo entre 209.**

Eso es evidencia publicada y cuantificada de que **la distancia cruda de
embedding no es el instrumento correcto** para juzgar intercambiabilidad
semántica, que es exactamente lo que el mapa de confianza necesita juzgar.

**El alineamiento por consistencia es el diseño que Swarmbly quiere.** T-Coffee
(Notredame, Higgins & Heringa, 2000) construye una biblioteca primaria de
alineamientos por pares y después la **extiende**: para cada par de residuos,
examina su alineamiento con residuos de las demás secuencias, y *«el peso
asociado a un par de residuos será la suma de todos los pesos reunidos mediante
el examen de todos los tripletes que involucran a ese par»*.

Traducido: **un acuerdo corroborado a través de una tercera respuesta
independiente pesa más que un acuerdo entre dos.** Y la fase progresiva usa
*«puntuación específica de posición»* en lugar de una matriz fija.

Un acuerdo ponderado por consistencia, específico de posición, calculado sobre
`k` respuestas independientes, **es** un mapa de confianza. T-Coffee lleva
veinticinco años produciendo exactamente ese objeto para secuencias biológicas.

**Y la formalización del producto también existe.** Un perfil HMM (Eddy, 1998)
*«convierte un alineamiento múltiple de secuencias en un sistema de puntuación
específico de posición»*. La guía de HMMER lo define como *«un modelo de
puntuación específico de posición que describe qué símbolos es probable observar
y con qué frecuencia ocurren inserciones/deleciones en cada posición (columna) de
un alineamiento múltiple»*.

Un modelo de puntuación específico de posición construido desde un conjunto de
respuestas alineadas es, otra vez, la descripción formal de un mapa de confianza.

### 3.4 El modelo propuesto

Reuniendo las piezas verificadas:

**M1 — Alineamiento múltiple de respuestas con sustitución semántica aprendida.**

1. **Segmentar** cada una de las `k` respuestas en oraciones (la unidad de
   alineamiento de §2.7).
2. **Alinear** las `k` secuencias de oraciones con programación dinámica y
   penalización de hueco afín (Gotoh, 1982), usando una matriz de sustitución
   semántica.
3. **Construir esa matriz empíricamente**, al modo BLOSUM: contar pares de
   oraciones que aparecen como sustituciones mutuas en casos verificados como
   correctos, y puntuar `log(q_obs / e_esp)`. El embedding entra como rasgo, no
   como veredicto — la lección cuantificada de PPDB 2.0.
4. **Extender por consistencia** al modo T-Coffee: ponderar cada correspondencia
   por su corroboración a través de las demás respuestas.
5. **Emitir** un perfil específico de posición sobre el alineamiento resultante.
   Ése es el mapa.

**Qué es nuevo y qué no.** Nada de los pasos 2, 3 y 4 es invención: son
Needleman-Wunsch con Gotoh, Henikoff con Ristad, y Notredame. Lo nuevo es
**aplicarlos a salidas de modelos distintos en lugar de a secuencias
biológicas**, y hacerlo para producir una anotación por unidad en vez de un
escalar por respuesta. La contribución es el ensamblaje del instrumento, no sus
partes, y así hay que enunciarla.

---

## 4. Flancos, repeticiones y el piso informacional

### 4.1 El solapamiento resuelve aquí un problema distinto

En ensamblaje *de novo* el solapamiento existe sobre todo para **descubrir el
orden**: nadie sabe de qué parte del genoma vino cada lectura. Swarmbly no tiene
ese problema — el orquestador crea los fragmentos y conoce su orden.

Dos razones quedan, y sólo una es genómica: **continuidad de transición** (que el
final de un fragmento encaje con el principio del siguiente) y **detección de
repeticiones**.

### 4.2 El criterio de solapamiento mínimo tiene dos formas, y la fuerte es la interesante

El enunciado folclórico —«el solapamiento debe exceder la repetición más larga»—
es correcto pero débil. La literatura informacional lo precisa en dos condiciones
distintas (Bresler, Bresler & Tse, 2013):

**Condición suficiente para un algoritmo voraz:**

```
L > ℓ_repeat + 1
```

*«GREEDY reconstruye la secuencia original si toda repetición está puenteada.»*
Es un enunciado sobre **un algoritmo particular**.

**Condición necesaria, informacional:**

```
L > max{ℓ_interleaved, ℓ_triple} + 1
```

donde una repetición *entrelazada* es un par de repeticiones cuyas posiciones se
intercalan, y una *triple* es una subsecuencia que aparece tres veces. Por debajo
de ese umbral **ningún algoritmo** puede reconstruir, porque dos secuencias
distintas producen conjuntos de lecturas idénticos.

La distinción importa para Swarmbly más de lo que parece. La primera forma dice
«hazlo mejor». La segunda dice **que existe una clase de entradas donde los
fragmentos simplemente no contienen la información necesaria para reensamblar
correctamente, por listo que sea el ensamblador.**

Motahari, Bresler & Tse (2013) formalizan el umbral: para secuencias i.i.d., hay
una transición neta según si la longitud de lectura normalizada supera la entropía
de Rényi de orden 2 de la fuente. Por encima, *«la condición obvia de cobertura
es también suficiente para la reconstrucción»*; por debajo, no hay cobertura que
alcance.

**El paralelo que esto habilita, y que el proyecto debería adoptar:** la
cobertura —cuántas réplicas— y la resolubilidad —si los fragmentos contienen la
información— son **dos preguntas distintas**, y la primera no implica la segunda.
Un diseño que sólo razona sobre `k` está razonando sobre cobertura y guardando
silencio sobre resolubilidad.

### 4.3 La repetición es una propiedad de un par, y el proyecto ya la midió

El homólogo semántico de una repetición genómica es **una frase o plantilla
recurrente**. Dos fragmentos que no se ven repiten la misma estructura, y el
ensamblador no puede detectarlo porque **la repetición es una propiedad de un par,
no de un fragmento**.

Esto no es especulación: la definición formal de Bresler et al. es inherentemente
relacional — una repetición *«es una subsecuencia que aparece dos veces»* en
posiciones `t₁` y `t₂`. Ninguna lectura individual puede inspeccionarse para
saber si está en una repetición.

Y el proyecto **ya midió el mismo fenómeno**. La restricción `no_repeated_ngram`
es la clase irreducible de sus mediciones de composición: **4 de 12 frente a 11
de 12 del brazo monolítico**, y ninguna política de asignación de contexto la
alcanza. Era el defecto que no cedía. La razón, ahora nombrable, es que ninguna
asignación *puede* alcanzarla: un fragmento no puede evitar repetir lo que no
puede ver.

### 4.4 El flanco F, definido por medición

De ahí el criterio operativo:

> **`F` es el máximo entre dos cantidades medidas sobre el corpus: la unidad
> repetible más larga que el ensamblador deba poder detectar, y la dependencia
> más larga que cruza un límite de fragmento.**

Estimación de referencia para el corpus del proyecto: **`F ≈ 5–10` oraciones**.

### 4.5 El pago

El presupuesto de contexto se deriva de `L`, `F` y el costo de cabecera:

```
ρ ≈ (L + 2F) / L  +  H / (L · s)
```

donde `H` es el costo fijo por paquete —contrato, glosario, instrucciones de
formato— medido en **≈ 39 tokens** sobre el corpus del proyecto, y `s ≈ 15`
tokens por oración.

Con `L = 50`, `F = 10`: **ρ ≈ 1.45**. Con un flanco heredado por analogía,
`F = 25`: **ρ ≈ 2.05**.

**Un 29 % del cómputo de toda la red**, por la única decisión de medir el flanco
en vez de copiar un porcentaje. Y como §4.2 dice exactamente qué medir, el ahorro
no relaja ninguna garantía.

El segundo término merece una nota, porque explica algo que el proyecto observó
sin poder nombrar: la cabecera se paga **entera por paquete**, así que su peso
relativo es inversamente proporcional a `L`. Con fragmentos de 35 tokens —el
tamaño real de los fragmentos en las mediciones de composición del proyecto— la
cabecera de 39 tokens **pesa más que el material**. Ése es el régimen en el que
se midió durante meses, y explica por qué ρ parecía tener un piso alto: no era
una propiedad del protocolo, era una propiedad de fragmentar demasiado fino.

---

## 5. La restricción de aparición única

### 5.1 Una hipótesis que no sobrevivió

La hipótesis era: *los mate pairs son el homólogo de las restricciones globales
—«menciona este término exactamente una vez», «no repitas una formulación»—
porque son el mecanismo que la genómica inventó para información que ninguna
lectura individual contiene.*

> **Concepto base.** Un *mate pair* o lectura pareada es un par de lecturas
> secuenciadas desde los dos extremos de un mismo fragmento de ADN de longitud
> aproximadamente conocida. Weber & Myers (1997) lo introdujeron precisamente
> porque *«los pares de lecturas de ambos extremos tienen espaciado y orientación
> conocidos»*, lo que *«ayuda al ensamblaje de secuencias que contienen elementos
> repetitivos dispersos»*.

La mitad de la hipótesis es correcta: las restricciones que cruzan fragmentos son
reales, son la dificultad central, y la genómica sí inventó maquinaria explícita
para información que ninguna pieza contiene.

La otra mitad es errónea, y lo es en cuatro ejes a la vez:

| eje | mate pair | «exactamente una vez en toda la salida» |
|---|---|---|
| **Aridad** | Binaria y pre-identificada: nombra dos lecturas concretas, y el par existe antes del ensamblaje porque lo creó la preparación de la biblioteca | n-aria y cuantificada: no nombra ningún par; cuantifica sobre todos los fragmentos |
| **Contenido métrico** | Es fundamentalmente una **distancia**, con distribución — Myers et al. (2000) reportan longitudes de inserto *«normalmente distribuidas con 10 % de varianza»* | No tiene distancia ni orientación |
| **Dureza** | **Blanda**: Opera (Gao, Sung & Nagarajan, 2011) define concordancia como un predicado que el optimizador **maximiza**; un mate pair discordante se tolera | **Dura**: una sola violación es un fallo, no un dato a ser superado en votación |
| **Dirección de la información** | **Evidencia**: una observación adicional muestreada de un genoma que ya existe, que reduce ambigüedad sobre cuál reconstrucción es la verdadera | **Especificación**: no hay una respuesta verdadera que recuperar; es una condición impuesta sobre la salida |

El cuarto eje es el más profundo. El ensamblaje genómico es **inferencia de
máxima verosimilitud hacia una respuesta correcta que preexiste**. Swarmbly hace
**satisfacción de restricciones sobre un espacio de salidas aceptables**. Los
mate pairs viven del lado de la inferencia.

### 5.2 El homólogo correcto está en la misma literatura

La genómica sí tiene un mecanismo cuya forma es «esto debe aparecer exactamente
N veces en toda la salida». No son los mate pairs. Son la **multiplicidad** y la
**unicidad**.

**Multiplicidad de k-meros.** Compeau, Pevzner & Tesler (2011) lo enuncian como
una operación de conteo que entra en la estructura del grafo: hay que determinar
*«cuántas veces aparece cada k-mero»*, y *«si la multiplicidad de un k-mero es m,
conectaremos su prefijo a su sufijo usando m aristas dirigidas (en lugar de una
sola)»*.

Eso es una restricción de cardinalidad global sobre la reconstrucción, impuesta
**estructuralmente** y no como una comprobación posterior.

**U-unitigs.** Myers et al. (2000), en el ensamblaje de *Drosophila*, describen
que aquellas unidades *«que con certeza representan ADN único fueron designadas
U-unitigs»* — y sobre ellas ancla todo el andamiaje.

Es literalmente el mecanismo de «exactamente una vez en toda la salida»: el
ensamblador **computa el conjunto de secuencias que deben aparecer una sola vez**
y construye alrededor de ellas.

**El modo de fallo, que confirma la transferencia.** Myers (1995) nombra la
patología cuando se hace mal: buscar la cadena más corta que contenga todos los
fragmentos hace que *«en el caso de secuencias objetivo repetitivas este objetivo
produzca respuestas sobre-comprimidas»*.

**Sobre-compresión** es exactamente el fallo de un ensamblador que funde dos
pasajes que debían permanecer distintos. Y su dual —emitir dos veces algo que
debía aparecer una— es el fallo que `no_repeated_ngram` mide.

### 5.3 El modelo propuesto

**M2 — Restricciones de cardinalidad resueltas en la representación, no en la
salida.**

La lección arquitectónica más fuerte viene de Medvedev et al. (2011), que
argumentan contra el tratamiento posterior: los mate pairs se han incorporado
*«como varios pasos heurísticos de post-procesamiento»*, lo que *«todavía puede
fallar en resolver repeticiones complejas»*; su propuesta es incorporar la
información **en la estructura del grafo misma**.

Aplicado a Swarmbly:

1. **Computar el conjunto de unicidad antes de despachar.** Qué términos,
   entidades y formulaciones deben aparecer exactamente una vez en la salida
   final. Es el análogo de identificar U-unitigs.
2. **Asignar cada elemento de ese conjunto a exactamente un fragmento**, como
   propiedad del plan y no como instrucción a los nodos. Un nodo no puede
   cumplir «exactamente una vez» porque no sabe qué escribieron los demás; el
   planificador sí.
3. **Verificar la cardinalidad en el ensamblado**, contra el conjunto computado
   en el paso 1, no contra una regla enunciada en el contrato.
4. **Registrar los dos modos de fallo por separado**: sobre-compresión (se fundió
   lo que debía distinguirse) y sobre-expansión (se repitió lo que debía
   aparecer una vez). Son errores distintos con causas distintas, y medirlos
   juntos los oculta.

El punto 2 es el cambio real. Hoy el proyecto pide `term_once` en el contrato y
lo impone mecánicamente en el ensamblador. Eso funciona, y su medición lo
confirma —la imposición mecánica subió el cumplimiento de 6/24 a 18/24, por
encima del monolítico en 13/24. Pero es una corrección posterior. **Asignar la
unicidad en el plan hace que la restricción sea imposible de violar en vez de
detectable después**, que es precisamente el argumento de Medvedev et al.

### 5.4 Qué sí es un mate pair

La transferencia no es nula: es de alcance más estrecho de lo propuesto. Los
mate pairs son el homólogo correcto de una clase real de restricción de Swarmbly:
**«el fragmento A y el fragmento B deben ser mutuamente consistentes en una
posición relativa conocida»**.

Ejemplos con forma de mate pair: la conclusión debe retomar la anécdota de la
introducción; la sección 4 debe recoger el hilo que dejó abierto la sección 2;
una referencia a una figura en un fragmento debe corresponder a una figura
definida en otro. Son binarias, tienen componente posicional, se conocen de
antemano porque el plan las creó, y degradan con gracia cuando se violan
parcialmente.

Para ésas, el argumento de Medvedev et al. transfiere con la homología.

---

## 6. El grafo, los niveles y el triage

### 6.1 Lo que la homología de la proteína aporta, y lo que no

El planificador **ya es** un grafo acíclico dirigido con niveles topológicos. La
analogía del plegado de proteínas lo justifica bien pero no propone nada nuevo
ahí, y conviene decirlo para no confundir una narrativa mejor con una capacidad
nueva.

Lo que **sí** aporta está en una cláusula que la versión anterior no tenía: *las
tareas de un nivel sólo comienzan cuando sus predecesoras han regresado **y han
sido verificadas***.

### 6.2 El triage es la especificación que faltaba

La biología tiene nombre para ese control, y es preciso. Gottesman, Wickner &
Maurizi (1997) lo llaman literalmente así:

> *«proponemos […] un modelo general para lo que puede pensarse como un sistema
> de **triage** para manejar proteínas mal plegadas in vivo, asegurando el
> **replegado rápido de proteínas con potencial funcional y la degradación rápida
> de proteínas irreversiblemente desnaturalizadas o dañadas**.»*

Esa frase es casi una especificación de la etapa de control de calidad de
Swarmbly: clasificar cada fragmento devuelto como **recuperable → reintentar** o
**irrecuperable → descartar y regenerar**, y **nunca empalmar uno malo en el
ensamblado**.

El mecanismo es igual de instructivo. La chaperonina GroEL/GroES no repara la
pieza en su sitio: la **aísla**. Xu, Horwich & Sigler (1997) describen cómo la
unión de GroES *«estabiliza una cámara de plegado»* cuya elevación y torsión de
los dominios apicales *«duplica el volumen de la cavidad central y entierra los
residuos hidrofóbicos de unión a péptido»*, dejando un revestimiento hidrofílico
*«propicio para el plegado»*.

**Aislar y reintentar**, no parchear en contexto.

### 6.3 La evidencia de que los niveles importan

Hay un resultado que va más allá de justificar el DAG: lo prefiere sobre el
paralelismo plano.

Netzer & Hartl (1997) encontraron que polipéptidos de dos dominios *«pliegan
eficientemente mediante plegado secuencial y cotraduccional»* en traducción
eucariota, mientras que las mismas proteínas plegadas post-traduccionalmente en
*E. coli* sufren *«mal plegamiento intramolecular de dominios que pliegan
concurrentemente»*.

Es decir: **plegar los dominios de a uno, en orden, tuvo éxito donde plegarlos
concurrentemente produjo interferencia**. El argumento no es que el paralelismo
sea malo; es que el paralelismo **irrestricto** lo es, y que la estructura que
ordena es lo que lo vuelve seguro.

Y Marsh et al. (2013) muestran que el orden de ensamblaje de complejos proteicos
*«puede predecirse simplemente a partir de sus estructuras tridimensionales»* y
que hay **selección evolutiva para conservar el orden de ensamblaje**. El orden
no es una conveniencia de ingeniería: en el sistema del que se toma la analogía,
está bajo selección.

### 6.4 Una complicación honesta: el ensamblaje empieza antes de terminar

Shiber et al. (2018), mediante perfilado ribosomal, encontraron que **nueve de
doce** complejos hetero-oligoméricos estudiados se ensamblan cotraduccionalmente,
y *«el ensamblaje cotraduccional ocurre a menudo unidireccionalmente, con una
subunidad completamente sintetizada acoplándose a su subunidad compañera
naciente»*.

Esto complica el cuadro «pliega todo, después ensambla», y en una dirección que
Swarmbly puede aprovechar: **un fragmento de nivel n puede consumirse mientras el
nivel n+1 todavía se está generando**, siempre que el que se consume esté
completo. Es un argumento a favor de ensamblado en streaming con una condición
de completitud, no de espera de barrera.

### 6.5 El modelo propuesto

**M3 — Compuerta de triage por nivel topológico.**

1. Un nivel no arranca hasta que los acarreos de sus predecesoras han pasado un
   **predicado mecánico**: *¿el acarreo que llegó responde a la tarea que lo
   pidió?* Sin juez, sin modelo, barato.
2. Un fragmento que no pasa se **aísla y se reintenta**, no se parchea en
   contexto ni se empalma con una advertencia.
3. Un fragmento que no pasa tras `r` reintentos se **descarta y se regenera** con
   un plan distinto. La degradación es una salida legítima del triage, no un
   fallo del sistema.
4. El consumo puede empezar **antes de que el nivel esté completo**, si el
   fragmento consumido está completo y verificado.

**Por qué importa.** El proyecto tiene un incidente que esta compuerta atrapa: 42
de 60 paquetes despachados llevaban las respuestas de otro paquete. Sin
compuerta, los acarreos pasan hacia adelante sin revisión y un error de un nivel
se multiplica en el siguiente. Con compuerta, el radio de daño es un fragmento.

---

## 7. ρ como problema de tasa-distorsión indirecto

### 7.1 Por qué formalizarlo

ρ ha funcionado como una cantidad empírica: se mide, se compara, se reporta. La
sección 4 la deriva de `L`, `F` y `H`, lo que ya es un avance sobre tratarla como
dial. Pero derivarla no dice **si existe un piso**, ni de qué depende.

La teoría de tasa-distorsión es el marco donde esa pregunta tiene respuesta.

### 7.2 La teoría, enunciada con precisión

> **Concepto base.** La teoría de tasa-distorsión (Shannon, 1959) responde: dado
> que voy a transmitir una versión imperfecta de algo, ¿cuál es la tasa mínima de
> información necesaria para que la imperfección no exceda un nivel dado?
>
> Shannon define una matriz de distorsión donde *«d_ij mide el "costo" o
> "distorsión" si la letra i se reproduce en el receptor como la letra j»*, y
> `R(d*)` como la mínima tasa sujeta a que la distorsión promedio no exceda `d*`.
> Cover & Thomas lo escriben como
>
> ```
> R(D) = min I(X; X̂)
> ```
>
> minimizado sobre distribuciones condicionales `p(x̂|x)` que cumplen la
> restricción de distorsión esperada. Su Teorema 13.2.1 establece que la función
> de tasa-distorsión de una fuente i.i.d. con distorsión acotada **es igual** a la
> función informacional asociada.
>
> La forma de la curva es lo esencial: `R(D)` decrece con `D`. Menos fidelidad
> exigida, menos información necesaria. Y hay un piso: por debajo de `R(D)` la
> distorsión `D` es inalcanzable, haga uno lo que haga.

### 7.3 El encuadre ya existe para prompts, y hay que decirlo

Nagle et al. (NeurIPS 2024) formalizan la **compresión de prompts** como un
problema de tasa-distorsión para modelos de lenguaje de caja negra. Su tasa es

```
E[ len(M) / len(X) ]
```

—longitud esperada del prompt comprimido sobre longitud esperada del original—
que es **estructuralmente la misma cantidad que ρ**. Su distorsión es la
degradación del rendimiento del modelo bajo pérdida logarítmica o 0/1. Derivan la
función distorsión-tasa mediante el dual de un programa lineal y reportan una
brecha grande entre los métodos actuales de compresión y la estrategia óptima.

**Consecuencia para Swarmbly:** la contribución no puede ser «ρ es un problema de
tasa-distorsión». Eso está publicado. La contribución tiene que ser ρ **bajo
fragmentación con reensamblado distribuido**, que es un problema distinto y más
duro, y que Nagle et al. no cubren.

### 7.4 Por qué el problema de Swarmbly es *indirecto*

La objeción natural es que la tasa-distorsión clásica supone una fuente que se
reconstruye, y Swarmbly no reconstruye el prompt: produce una respuesta.

La teoría tiene un nombre para esa situación: el problema de tasa-distorsión
**indirecto** o **remoto**, donde *«el codificador no puede observar la fuente
directamente sino que obtiene sólo observaciones ruidosas»* (la formulación se
remonta a Wolf & Ziv).

El mapeo es exacto, y es el aporte formal de esta sección:

| elemento de la teoría | en Swarmbly |
|---|---|
| **Fuente** `Y*` | La respuesta ideal a la petición. **Nunca se observa**, ni por el orquestador ni por ningún nodo. |
| **Observación** `X` | La petición `P`. Es lo que el codificador *sí* ve: una descripción de `Y*`, no `Y*`. |
| **Codificador** | La política de fragmentación: router, planificador, empaquetador. Produce `{K₁ … K_N}`. |
| **Canal** | La red de nodos. Cada nodo aplica una transformación estocástica `K_i → R_i`. |
| **Decodificador** | El ensamblador local, que produce `Ŷ` a partir de `{R_i}`. |
| **Tasa** | `ρ = Σ|K_i| / |P|` |
| **Distorsión** | `d(Y*, Ŷ)` — pérdida de tarea, no fidelidad de reconstrucción. Es el movimiento de Nagle et al., y es el correcto. |

Con esto, la afirmación defendible queda enunciada:

> **M4 — ρ es la tasa de un problema de tasa-distorsión indirecto cuya distorsión
> es pérdida de tarea. De ahí se hereda la existencia de una cota inferior y la
> monotonía cualitativa de la curva. No se hereda una cota computable.**

### 7.5 Lo que no se puede afirmar, y por qué

Tres límites, enunciados antes de que un revisor los enuncie.

**La cota existe pero no es computable aquí.** Nagle et al. obtienen un número
porque restringen a borrado de tokens sobre un prompt conocido con un LLM de caja
negra, y resuelven un programa lineal finito. El codificador de Swarmbly es una
política de descomposición y su decodificador es un modelo de lenguaje; no hay
`p(x)` tratable sobre el espacio de tareas ni una distorsión de letra única. Se
puede afirmar que la cota **existe**; no que se ha calculado.

**El teorema es asintótico en bloques i.i.d.** Una petición de usuario es una
realización, no una secuencia larga. El recíproco no da garantía por petición.

**Y el más importante: la distorsión no está causada sólo por la tasa.**

### 7.6 El segundo eje: densidad de dependencias

Éste es el aporte propio de la sección, y sale de un dato del arte previo.

Skeleton-of-Thought (Ning et al., ICLR 2024) genera un esqueleto y expande los
puntos en paralelo. Logra aceleraciones de hasta **2.39×**. Y su degradación de
calidad **no es uniforme**: mejora *«diversidad y relevancia mientras perjudica
la inmersión y la coherencia»*, y **falla en matemáticas y programación**.

Ésas son precisamente las tareas donde las sub-respuestas son interdependientes.
La degradación no sigue a la tasa: sigue a **cuánto se cortó a través de
dependencias**.

Una curva `D(ρ)` indexada sólo por ρ no puede capturar eso. Se necesita al menos
un segundo eje:

```
D = D(ρ, δ)
```

donde **δ es la densidad de dependencias de la descomposición**: alguna medida de
cuántas relaciones necesarias cruzan un límite de fragmento, normalizada por el
número de fragmentos.

Esto conecta con §2.4 de manera que cierra el argumento del documento: **la regla
de corte por interfaz débil es, en este lenguaje, la minimización de δ**. Cortar
donde el acoplamiento es débil es exactamente elegir la descomposición de menor
densidad de dependencias para un ρ dado.

Y con §4.2: el piso informacional de Bresler et al. —la condición `L >
max{ℓ_interleaved, ℓ_triple} + 1`— es el enunciado, en el lenguaje del
ensamblaje, de que **existe una región del plano (ρ, δ) donde ninguna distorsión
aceptable es alcanzable**, porque los fragmentos no contienen la información.

Las tres formulaciones —interfaz débil, piso informacional, densidad de
dependencias— son la misma afirmación en tres vocabularios. Que converjan desde
tres literaturas independientes es la razón para creerla.

### 7.7 Qué se puede medir de esto

La superficie `D(ρ, δ)` es falsable sin teoría adicional:

- Fijar δ variando sólo ρ (mismo corte, distinto flanco) debería producir una
  curva monótona decreciente en distorsión.
- Fijar ρ variando δ (mismo presupuesto, cortes de distinto acoplamiento)
  debería producir variación de distorsión **a tasa constante** — que es el
  resultado que mataría la idea de que ρ basta como eje.
- La región de inalcanzabilidad debería manifestarse como un suelo de distorsión
  que ningún ρ mejora.

**Se midió lo segundo, que es lo decisivo, y el resultado es negativo.**
El experimento corta el **mismo prompt** dos veces con el **mismo `L`**: una vez
en interfaces de acoplamiento débil y otra maximizando el acoplamiento que cruza
el corte. δ sube en los **32** pares y ρ queda igual dentro de un **5 %**, de modo
que el único eje que se movió es δ. La predicción es que el corte fuerte empeora
la distorsión en todos los pares; empeora en **19 de 32**. Una medición
observacional sobre **127** celdas intra-categoría converge: Spearman(δ,
distorsión) = **−0.13**, con el signo contrario al predicho.

> **Estado de la superficie `D(ρ, δ)`.** El primer eje se sostiene: la
contabilidad de ρ predice el tamaño de paquete con **7.5 %** de error y la curva
cae al crecer `L` como está derivado. **El segundo eje no.** Ésta no es una
aclaración de alcance: es la condición de muerte de §10 cumpliéndose. δ se
conserva como magnitud descriptiva del plan —se calcula, se registra y ordena los
cortes— y **se retira como eje explicativo de la distorsión y como rasgo
predictivo del router**.

---

## 8. Redundancia: una hipótesis refutada y su reemplazo

### 8.1 La hipótesis

*En lugar de enviar el mismo paquete a `k` nodos, enviar `N + m` fragmentos
codificados de los cuales cualesquiera `N` basten para reconstruir.*

La motivación era buena y está bien fundada en la literatura de almacenamiento.
Weatherspoon & Kubiatowicz (2002) muestran que los códigos de borrado *«usan un
orden de magnitud menos de ancho de banda y almacenamiento que la replicación
para sistemas con MTTF similar»*: con un millón de máquinas y 10 % caídas, dos
réplicas completas dan *«sólo dos nueves de disponibilidad»*, mientras que una
codificación en 32 fragmentos da *«más de ocho nueves»* con el mismo
almacenamiento.

Los *fountain codes* llevan eso al límite. Luby (2002) demuestra que los `k`
símbolos de entrada se recuperan *«de cualesquiera `k + O(√k · ln²(k/δ))` de los
símbolos de codificación con probabilidad `1 − δ`»*. Shokrollahi (2006) lo mejora
a *«cualquier subconjunto de símbolos de tamaño `(1+ε)k` es suficiente»* con
`O(1)` operaciones por símbolo. En la práctica, RaptorQ: dos símbolos extra dan
probabilidad de fallo ~10⁻⁵, *«válido para todos los valores soportados de k»* y
*«para todas las probabilidades de pérdida: 1 % a 99 %»*.

### 8.2 Por qué no transfiere

La razón es limpia y no admite matiz.

**Los fountain codes son códigos lineales sobre incógnitas compartidas.** La
definición de Shokrollahi lo dice: *«cada símbolo de salida es la suma de algunos
de los símbolos de entrada»*, y la decodificación es eliminación gaussiana o
*peeling* sobre ese sistema lineal. Todo el mecanismo por el que «cualesquiera
`k(1+ε)` bastan» **es** que los símbolos recibidos son **ecuaciones lineales en
las mismas incógnitas**.

Los fragmentos de Swarmbly no son ecuaciones en incógnitas compartidas. Cada nodo
**genera texto nuevo**. No hay XOR, no hay cuerpo algebraico, no hay inversa. No
hay nada que despejar.

Y ésta no es una inferencia propia: es la limitación explícita de la literatura
de *coded computing*. Kosaian, Rashmi & Venkataraman constatan que muchos
trabajos emplean códigos de borrado para cómputo de **funciones lineales**, y que
*«hasta donde sabemos, ninguno de los trabajos existentes es aplicable a clases
más amplias de cómputos no lineales»*.

Lo que sí existe confirma el diagnóstico por el lado positivo. Mallick et al.
(2019) aplican códigos rateless a multiplicación matriz-vector distribuida y
obtienen hasta **3× de aceleración** con redundancia asintóticamente nula,
usando el trabajo parcial de los rezagados en vez de descartarlo. Funciona
**porque la multiplicación matriz-vector es lineal**. Y el único intento serio de
codificar inferencia no lineal —ApproxIFER (AAAI-22)— logra recuperación
**aproximada** sobre salidas de clasificación de baja dimensión, con pérdidas de
exactitud reportadas de hasta ~6–9 % en modo degradado. Ése es el techo honesto
de «codificar sobre salidas de modelo» hoy: aproximación sobre clasificación, no
recuperación exacta de texto generado.

Se buscó específicamente trabajo previo aplicando códigos fountain a redundancia
de agentes LLM o a inferencia descentralizada de LLM. **No existe.** La
transferencia no está intentada, y la linealidad explica por qué.

### 8.3 Qué sí transfiere: la economía, no el mecanismo

La lección real de la literatura de almacenamiento no es sobre XOR. Es sobre
**umbrales y quórums**: para una fiabilidad objetivo, `(N, N+m)` bate a la
duplicación `k` veces.

Eso sí transfiere:

**M5 — Sobre-despacho con terminación temprana.** Despachar `N` sub-tareas
distintas más `m` extras, aceptar las primeras `N` que vuelvan, descartar
rezagados. Es un esquema de umbral, entrega el ahorro de ρ que se buscaba, **y no
es un fountain code**. Llamarlo así sería el error que este documento existe para
evitar.

**Con una condición que hay que enunciar, porque es el núcleo del compromiso:**
las `m` extras sólo son gratis si las sub-tareas son **genuinamente
intercambiables**. El punto entero de la codificación de borrado es que
*cualesquiera* `k` símbolos sirven. Los fragmentos de Swarmbly no son
intercambiables: si el contenido del fragmento `j` es necesario, recibir los
otros `N−1` no lo sustituye. Hacerlos intercambiables exige redundancia de
contenido, que cuesta exactamente el ρ que se quería ahorrar.

### 8.4 Separar disponibilidad de verificación

La investigación dejó un hallazgo que reordena el papel de `k`, y que es
probablemente más valioso que la hipótesis original.

`k` sirve hoy a **dos propósitos distintos** que el diseño no separa:

- **Disponibilidad** — que la tarea se complete aunque un nodo se caiga.
- **Verificación** — que un nodo deshonesto no imponga un resultado falso.

Sarmenta (2002) mide el costo de cada vía en computación voluntaria: la votación
*«reduce las tasas de error exponencialmente con la redundancia, pero requiere
que todo el trabajo se haga varias veces, y no funciona bien cuando hay muchos
saboteadores»*; el *spot-checking* *«reduce la tasa de error linealmente con la
cantidad de trabajo a realizar, mientras sólo cuesta una fracción extra del
tiempo original»*; y la combinación acreditada da *«niveles de corrección
garantizables matemáticamente con mucho menor ralentización»*.

BOINC implementa la versión desplegada de eso: replicación adaptativa que logra
*«una cota baja en la tasa de error […] incluso en presencia de voluntarios
maliciosos, imponiendo sólo una pequeña sobrecarga de rendimiento»*.

**La consecuencia de diseño:**

> Si `k` existe por **verificación**, los códigos de borrado nunca fueron la
> herramienta; el *spot-checking* con credibilidad lo es. Si `k` existe por
> **disponibilidad**, el sobre-despacho con umbral lo resuelve. Y si `k` existe
> por el **mapa de confianza** —redundancia epistémica— entonces no es
> reemplazable por ninguna de las dos, porque su producto no es tolerancia a
> fallos sino señal.

Tres propósitos, tres mecanismos, y hoy un solo parámetro. Separarlos es una
mejora inmediata del protocolo, disponible sin medir nada.

### 8.5 El dato de campo que calibra todo esto

Anderson & Fedak (2006), sobre más de 330.000 hosts de SETI@home: fracción media
de encendido **0.81**, fracción de conexión **0.83**, fracción activa media
**0.84**, **vida media del host 91 días**. La versión de 2018 reporta ~700.000
dispositivos y disponibilidad de **~60 %** para equipos de escritorio y **~40 %**
para móviles.

Ésos son los números con los que la ecuación de cobertura debe alimentarse. No
son catastróficos: una tasa de pérdida del 16–40 % es exactamente el régimen para
el que la redundancia por umbral está diseñada.

---

## 9. Arte previo y posicionamiento

### 9.1 Lo que hay que reconocer

**Paralelismo por capas sobre voluntarios.** Petals (Borzunov et al., 2022)
reparte BLOOM-176B **por capas** entre máquinas participantes, ~1 paso/segundo.
SWARM (Ryabinin et al., ICML 2023) es *«un algoritmo de entrenamiento con
paralelismo de modelo diseñado para dispositivos mal conectados, heterogéneos y
poco fiables»* con *«tuberías aleatorizadas temporales»* — pero es
**entrenamiento**, no inferencia.

Ambos reparten **el modelo**. Swarmbly reparte **el problema**. Es la distinción
del whitepaper v1 y sigue en pie.

**Descomposición de tareas.** Skeleton-of-Thought (ICLR 2024) es el vecino más
cercano en el eje de fragmentación: esqueleto y expansión paralela, hasta 2.39×.
Decomposed Prompting (Khot et al.) delega sub-tareas a *«una biblioteca
compartida de LLMs basados en prompting»*. Chain of Agents (NeurIPS 2024) procesa
segmentos secuencialmente con un agente gestor que sintetiza. Mixture-of-Agents
(2024) apila proponentes y agregadores, 65.1 % en AlpacaEval 2.0.

**Y el más cercano de todos:** SWARM-LLM (Dahshan, Mamun & Debnath, VTC 2026)
enruta una consulta a un SLM local, a varios SLM pares en el borde con **consenso
ponderado donde los nodos de menor incertidumbre pesan más**, o escala a la nube.
Reporta ~28 % de uso de nube y exactitud en preguntas difíciles de 0 % a 15 %
sobre una carga de **50 consultas**. Es evidencia empírica débil —50 consultas—
pero reclama el territorio, y hay que citarlo y diferenciarse.

**La garantía que Swarmbly no tiene.** La decodificación especulativa (Leviathan
et al., ICML 2023; Chen et al., 2023) logra 2–3× *«con salidas idénticas»*, por
un esquema de muestreo por rechazo que **preserva la distribución del modelo
objetivo**. Es el único esquema de descomposición en la literatura con garantía
demostrable de no distorsión. Swarmbly no tiene análogo, y un revisor lo notará.
Conviene decirlo antes que él.

### 9.2 La evidencia adversa que hay que enfrentar

Dos trabajos recientes son la crítica más seria a toda la familia de arquitecturas
multi-agente, y el whitepaper debe responderlos, no rodearlos.

**«Why Do Multi-Agent LLM Systems Fail?»** (Cemri et al., 2025) construye la
taxonomía MAST: **14 modos de fallo en 3 categorías** —problemas de diseño del
sistema, desalineación entre agentes, verificación de tareas— a partir de más de
1600 trazas anotadas sobre **7 frameworks**, con 150 trazas validadas por
anotadores expertos a **κ = 0.88**.

**«If Multi-Agent Debate is the Answer, What is the Question?»** (Zhang et al.,
2025) encuentra que los métodos de debate multi-agente *«fallan en superar de
forma fiable a líneas base de un solo agente como Chain-of-Thought y
Self-Consistency, incluso cuando consumen cómputo adicional en inferencia»*, sobre
9 benchmarks, 4 modelos y 5 métodos.

**La respuesta honesta de Swarmbly a esto** no es que su arquitectura sea
inmune. Es que **las tres categorías de MAST son exactamente las tres que este
documento aborda**:

| categoría MAST | dónde se aborda aquí |
|---|---|
| Problemas de diseño del sistema | §2.4 regla de corte por interfaz; §5.3 unicidad asignada en el plan |
| Desalineación entre agentes | §3 alineamiento con sustitución semántica; §1 contrato global |
| Verificación de tareas | §6.5 compuerta de triage por nivel |

Que una taxonomía construida independientemente sobre 1600 trazas coincida con
las tres áreas donde las homologías biológicas apuntaron es, si no una
validación, al menos una convergencia que vale la pena declarar.

Y la crítica de Zhang et al. es más específica de lo que parece: apunta al
**debate** —agentes que discuten para converger— no a la **descomposición** —
agentes que resuelven partes disjuntas. Swarmbly no debate. Pero la lección
transfiere igual: **el cómputo adicional debe justificarse contra una línea base
de un solo agente con self-consistency**, y ése es el baseline correcto, no el
modelo monolítico ingenuo.

---

## 10. Qué predice cada modelo, y cómo se lo mata

Los cinco modelos de este documento son falsables. Enunciarlo aquí es lo que
separa una extensión de whitepaper de un manifiesto.

**M1 — Alineamiento con sustitución semántica aprendida.**
*Predice:* un mapa de confianza construido por alineamiento con costo aprendido
separa correcto de incorrecto mejor que uno construido por conteo de
coincidencias, y mejor que un escalar por respuesta, **en régimen no saturado**.
*Se mata si:* con el instrumento correcto y en un régimen donde los modelos
genuinamente discrepan, el acuerdo por unidad no supera al azar. Entonces la
localización no crea señal y el mapa de confianza pierde su afirmación de
fiabilidad, aunque conserve su capacidad de reportar divergencia.

**M2 — Cardinalidad resuelta en la representación.**
*Predice:* asignar la unicidad en el plan hace `no_repeated_ngram` y `term_once`
inviolables por construcción, no sólo detectables. La tasa de violación debe caer
a cero, no mejorar.
*Se mata si:* la asignación en el plan no reduce las violaciones por debajo de lo
que ya logra la imposición mecánica en el ensamblador (18/24).

**M3 — Compuerta de triage por nivel.**
*Predice:* el radio de daño de un fragmento defectuoso queda contenido en ese
fragmento. Un incidente del tipo «42 de 60 paquetes contaminados» se vuelve
imposible.
*Se mata si:* la compuerta rechaza tanto trabajo legítimo que el costo de
reintento supera el daño que evita.

**M4 — ρ como tasa-distorsión indirecta con segundo eje δ.**
*Predice:* a ρ constante, variar la densidad de dependencias del corte mueve la
distorsión. Y existe una región donde ninguna ρ alcanza una distorsión
aceptable.
*Se mata si:* la distorsión resulta ser función sólo de ρ, con δ sin efecto
medible. Entonces el segundo eje es decoración y el encuadre no aporta sobre la
derivación empírica de §4.

**M5 — Sobre-despacho con umbral, y `k` separado en tres.**
*Predice:* separar disponibilidad, verificación y redundancia epistémica permite
bajar el costo total manteniendo las tres garantías, porque hoy un solo
parámetro paga por las tres al precio de la más cara.
*Se mata si:* las tres resultan estar tan acopladas en la práctica que
separarlas no ahorra nada.

**Estado tras la campaña de referencia** (341 corridas, cinco familias de
modelos locales; el detalle está en §15.9 del whitepaper v2):

| Modelo | Veredicto | Sobre qué |
|---|---|---|
| **M1** | sin instrumento | el alineador está construido y verificado en banco, pero el corpus no produjo el régimen no saturado que M1 exige |
| **M2** | sobrevive, corregido | **6/35** por obediencia del nodo; **35/35** con la imposición mecánica del ensamblador. «Cero por construcción» se retira: lo que es cero por construcción es la sobre-compresión |
| **M3** | sobrevive | los paquetes contaminados no pasan la compuerta |
| **M4** | **falsado** | dos instrumentos independientes y un experimento controlado a ρ constante (§7.7) |
| **M5** | sin medir | sigue siendo una separación conceptual |

Dos de los cinco modelos que este documento propone quedan falsados o
corregidos por la primera medición seria que se les hizo. Es el resultado que
justifica haberlos escrito como condiciones de muerte y no como afirmaciones.

### 10.1 El orden en que conviene atacarlos

Por costo creciente y por lo que cada uno desbloquea:

1. **M5** no necesita medición: es una separación conceptual de un parámetro que
   ya existe. Se implementa y se observa.
2. **M3** es barato y su predicción es binaria: el incidente ocurre o no ocurre.
3. **M2** se mide sobre el corpus de composición que ya existe.
4. **M4** necesita el corpus con dificultad calibrada del que depende toda la
   agenda experimental actual.
5. **M1** necesita construir el alineador, y es el más caro. También es el que
   produce la propiedad más distintiva.

---

## 11. Lo que este documento cambia respecto del whitepaper v1

| en v1 | tras esta extensión |
|---|---|
| El codón como unidad mínima de significado | **Retirado.** Tres de tres propiedades no transfieren. La oración es homóloga del aminoácido (unidad de alineamiento); el dominio es homólogo del fragmento (unidad de trabajo) |
| Fragmentar en `N` partes de tamaño parecido | **Reemplazado** por corte en interfaces de acoplamiento débil, con `L` como objetivo y `N` derivado |
| Solapamiento como porcentaje del fragmento | **Reemplazado** por `F` = máximo entre repetición más larga y dependencia más larga que cruza. Ahorro medido: 29 % |
| ρ como parámetro que se ajusta | **Reemplazado** por ρ derivada de `L`, `F`, `H`; y formalizada como tasa de un problema indirecto |
| Mapa de confianza por conteo de coincidencias | **Reemplazado** por alineamiento múltiple con costo de sustitución aprendido y extensión por consistencia |
| `term_once` impuesto en el ensamblador | **Complementado** por asignación de unicidad en el plan, al modo U-unitig |
| DAG sin control entre niveles | **Extendido** con compuerta de triage, por analogía con chaperonas |
| `k` réplicas como un parámetro | **Separado** en disponibilidad, verificación y redundancia epistémica |
| Analogía genómica como vocabulario | **Formalizada** como método: prueba del instrumento y prueba del modo de fallo |
| Los modelos M1–M5 enunciados | **Medidos.** M4 falsado, M2 corregido, M3 sobrevive, M1 sin régimen, M5 sin medir (§10) |

---

## 12. Bibliografía

Todas las referencias fueron verificadas contra la fuente en línea indicada.
Cuando sólo se pudo confirmar el resumen y no el texto completo, se indica.

### Alineamiento y matrices de sustitución

1. Henikoff, S. & Henikoff, J. G. (1992). «Amino acid substitution matrices from protein blocks.» *PNAS* 89(22): 10915–10919. https://www.pnas.org/doi/10.1073/pnas.89.22.10915
2. Needleman, S. B. & Wunsch, C. D. (1970). «A general method applicable to the search for similarities in the amino acid sequence of two proteins.» *J. Mol. Biol.* 48(3): 443–453. DOI 10.1016/0022-2836(70)90057-4
3. Smith, T. F. & Waterman, M. S. (1981). «Identification of common molecular subsequences.» *J. Mol. Biol.* 147(1): 195–197. DOI 10.1016/0022-2836(81)90087-5
4. Gotoh, O. (1982). «An improved algorithm for matching biological sequences.» *J. Mol. Biol.* 162(3): 705–708. DOI 10.1016/0022-2836(82)90398-9
5. Altschul, S. F. & Erickson, B. W. (1986). «Optimal sequence alignment using affine gap costs.» *Bull. Math. Biol.* 48: 603–616. DOI 10.1007/BF02462326
6. Notredame, C., Higgins, D. G. & Heringa, J. (2000). «T-Coffee: A novel method for fast and accurate multiple sequence alignment.» *J. Mol. Biol.* 302(2): 205–217. https://tcoffee.org/Publications/Ps_pdf/tcoffee.pdf
7. Thompson, J. D., Higgins, D. G. & Gibson, T. J. (1994). «CLUSTAL W…» *Nucleic Acids Research* 22(22): 4673–4680. DOI 10.1093/nar/22.22.4673
8. Eddy, S. R. (1998). «Profile hidden Markov models.» *Bioinformatics* 14(9): 755–763. DOI 10.1093/bioinformatics/14.9.755
9. Eddy, S. R. et al. *HMMER User's Guide*, v3.2.1, 2018. http://eddylab.org/software/hmmer/Userguide.pdf

### Costos aprendidos y alineamiento de texto

10. Ristad, E. S. & Yianilos, P. N. (1998). «Learning String-Edit Distance.» *IEEE TPAMI* 20(5): 522–531.
11. Pavlick, E., Rastogi, P., Ganitkevitch, J., Van Durme, B. & Callison-Burch, C. (2015). «PPDB 2.0…» *ACL-IJCNLP 2015*, pp. 425–430. DOI 10.3115/v1/P15-2070
12. MacCartney, B., Galley, M. & Manning, C. D. (2008). «A Phrase-Based Alignment Model for Natural Language Inference.» *EMNLP 2008*, pp. 802–811. https://aclanthology.org/D08-1084.pdf
13. Sultan, M. A., Bethard, S. & Sumner, T. (2014). «Back to Basics for Monolingual Alignment…» *TACL* 2: 219–230. https://aclanthology.org/Q14-1018.pdf
14. Barzilay, R. & Lee, L. (2003). «Learning to Paraphrase: An Unsupervised Approach Using Multiple-Sequence Alignment.» *HLT-NAACL 2003*, pp. 16–23.
15. Barzilay, R. & Elhadad, N. (2003). «Sentence Alignment for Monolingual Comparable Corpora.» *EMNLP 2003*. https://aclanthology.org/W03-1004.pdf
16. Cer, D., Diab, M., Agirre, E., Lopez-Gazpio, I. & Specia, L. (2017). «SemEval-2017 Task 1…» *SemEval-2017*, pp. 1–14. DOI 10.18653/v1/S17-2001

### Incertidumbre y acuerdo entre generaciones

17. Kuhn, L., Gal, Y. & Farquhar, S. (2023). «Semantic Uncertainty…» *ICLR 2023*. arXiv:2302.09664
18. Farquhar, S., Kossen, J., Kuhn, L. & Gal, Y. (2024). «Detecting hallucinations in large language models using semantic entropy.» *Nature* 630: 625–630. DOI 10.1038/s41586-024-07421-0
19. Manakul, P., Liusie, A. & Gales, M. (2023). «SelfCheckGPT…» *EMNLP 2023*, pp. 9004–9017. DOI 10.18653/v1/2023.emnlp-main.557
20. Soiffer, D., Kolawole, S. & Smith, V. (2025). «Semantic Agreement Enables Efficient Open-Ended LLM Cascades.» arXiv:2509.21837. *(preprint, no revisado por pares)*
21. Wang, X. et al. (2023). «Self-Consistency Improves Chain of Thought Reasoning in Language Models.» *ICLR 2023*. arXiv:2203.11171
22. Jiang, D., Ren, X. & Lin, B. Y. (2023). «LLM-Blender…» *ACL 2023*, pp. 14165–14178.

### Ensamblaje, cobertura y repeticiones

23. Lander, E. S. & Waterman, M. S. (1988). «Genomic Mapping by Fingerprinting Random Clones: A Mathematical Analysis.» *Genomics* 2(3): 231–239.
24. Motahari, A. S., Bresler, G. & Tse, D. N. C. (2013). «Information Theory of DNA Shotgun Sequencing.» *IEEE Trans. Inf. Theory* 59(10): 6273–6288. https://web.stanford.edu/~dntse/papers/mbt.pdf
25. Bresler, G., Bresler, M. & Tse, D. (2013). «Optimal assembly for high throughput shotgun sequencing.» *BMC Bioinformatics* 14(Suppl 5): S18. arXiv:1301.0068
26. Pevzner, P. A., Tang, H. & Waterman, M. S. (2001). «An Eulerian path approach to DNA fragment assembly.» *PNAS* 98(17): 9748–9753. DOI 10.1073/pnas.171285098
27. Compeau, P. E. C., Pevzner, P. A. & Tesler, G. (2011). «How to apply de Bruijn graphs to genome assembly.» *Nature Biotechnology* 29(11): 987–991. DOI 10.1038/nbt.2023
28. Miller, J. R., Koren, S. & Sutton, G. (2010). «Assembly algorithms for next-generation sequencing data.» *Genomics* 95(6): 315–327.
29. Myers, E. W. (1995). «Toward Simplifying and Accurately Formulating Fragment Assembly.» *J. Comput. Biol.* 2(2): 275–290. DOI 10.1089/cmb.1995.2.275
30. Nagarajan, N. & Pop, M. (2009). «Parametric Complexity of Sequence Assembly…» *J. Comput. Biol.* 16(7): 897–908. DOI 10.1089/cmb.2009.0005
31. Shomorony, I., Kim, S., Courtade, T. & Tse, D. (2016). «Information-optimal genome assembly via sparse read-overlap graphs.» *Bioinformatics* 32(17): i494.
32. Treangen, T. J. & Salzberg, S. L. (2012). «Repetitive DNA and next-generation sequencing…» *Nature Reviews Genetics* 13(1): 36–46. *(sólo resumen verificado)*

### Restricciones de largo alcance y andamiaje

33. Weber, J. L. & Myers, E. W. (1997). «Human Whole-Genome Shotgun Sequencing.» *Genome Research* 7(5): 401–409.
34. Myers, E. W. et al. (2000). «A Whole-Genome Assembly of Drosophila.» *Science* 287(5461): 2196–2204.
35. Pop, M., Kosack, D. S. & Salzberg, S. L. (2004). «Hierarchical Scaffolding With Bambus.» *Genome Research* 14: 149–159. DOI 10.1101/gr.1536204
36. Medvedev, P., Pham, S., Chaisson, M., Tesler, G. & Pevzner, P. (2011). «Paired de Bruijn Graphs…» *RECOMB 2011*, LNCS 6577: 238–251. DOI 10.1007/978-3-642-20036-6_22
37. Gao, S., Sung, W.-K. & Nagarajan, N. (2011). «Opera: Reconstructing Optimal Genomic Scaffolds…» *J. Comput. Biol.* 18(11): 1681–1691. DOI 10.1089/cmb.2011.0170

### Corrección previa al ensamblaje

38. Tammi, M. T., Arner, E., Kindlund, E. & Andersson, B. (2003). «Correcting errors in shotgun sequences.» *Nucleic Acids Research* 31(15): 4663–4672. DOI 10.1093/nar/gkg653
39. Kelley, D. R., Schatz, M. C. & Salzberg, S. L. (2010). «Quake: quality-aware detection and correction of sequencing errors.» *Genome Biology* 11(11): R116.
40. Yang, X., Chockalingam, S. P. & Aluru, S. (2013). «A survey of error-correction methods for next-generation sequencing.» *Briefings in Bioinformatics* 14(1): 56–66.

### Plegado, dominios y control de calidad

41. Anfinsen, C. B. (1973). «Principles that Govern the Folding of Protein Chains.» *Science* 181(4096): 223–230. DOI 10.1126/science.181.4096.223
42. Levinthal, C. (1969). «How to Fold Graciously.» *Mössbauer Spectroscopy in Biological Systems*, Univ. of Illinois Bulletin 67(41): 22–24.
43. Dill, K. A. & Chan, H. S. (1997). «From Levinthal to pathways to funnels.» *Nature Struct. Mol. Biol.* 4(1): 10–19. DOI 10.1038/nsb0197-10
44. Porter, L. L. & Rose, G. D. (2012). «A thermodynamic definition of protein domains.» *PNAS* 109(24): 9420–9425. DOI 10.1073/pnas.1202604109
45. Han, J.-H., Batey, S., Nickson, A. A., Teichmann, S. A. & Clarke, J. (2007). «The folding and evolution of multidomain proteins.» *Nature Rev. Mol. Cell Biol.* 8(4): 319–330. DOI 10.1038/nrm2144
46. Bashton, M. & Chothia, C. (2007). «The Generation of New Protein Functions by the Combination of Domains.» *Structure* 15(1): 85–99. DOI 10.1016/j.str.2006.11.009
47. Zhang, Y., Chandonia, J.-M., Ding, C. & Holbrook, S. R. (2005). «Comparative mapping of sequence-based and structure-based protein domains.» *BMC Bioinformatics* 6:77. DOI 10.1186/1471-2105-6-77
48. Schaeffer, R. D. et al. (2023). «ECOD domain classification of 48 whole proteomes from AlphaFold Structure Database using DPAM2.» *PLoS Comput. Biol.*
49. Hubbard, T., Murzin, A., Brenner, S. & Chothia, C. (1997). «SCOP: a Structural Classification of Proteins database.» *Nucleic Acids Research* 25(1): 236–239. DOI 10.1093/nar/25.1.236
50. Orengo, C. et al. (1997). «CATH – a hierarchic classification of protein domain structures.» *Structure* 5(8): 1093–1109. DOI 10.1016/S0969-2126(97)00260-8
51. Zhu, K., Su, H., Peng, Z. & Yang, J. (2023). «A unified approach to protein domain parsing with inter-residue distance matrix.» *Bioinformatics* 39(2): btad070. DOI 10.1093/bioinformatics/btad070
52. Wheelan, S. J., Marchler-Bauer, A. & Bryant, S. H. (2000). «Domain size distributions can predict domain boundaries.» *Bioinformatics* 16(7): 613–618. DOI 10.1093/bioinformatics/16.7.613
53. Gottesman, S., Wickner, S. & Maurizi, M. R. (1997). «Protein quality control: triage by chaperones and proteases.» *Genes & Development* 11: 815–823.
54. Hartl, F. U., Bracher, A. & Hayer-Hartl, M. (2011). «Molecular chaperones in protein folding and proteostasis.» *Nature* 475(7356): 324–332. DOI 10.1038/nature10317
55. Xu, Z., Horwich, A. L. & Sigler, P. B. (1997). «The crystal structure of the asymmetric GroEL–GroES–(ADP)₇ chaperonin complex.» *Nature* 388(6644): 741–750. DOI 10.1038/41944
56. Rosenzweig, R., Nillegoda, N. B., Mayer, M. P. & Bukau, B. (2019). «The Hsp70 chaperone network.» *Nature Rev. Mol. Cell Biol.* 20(11): 665–680. DOI 10.1038/s41580-019-0133-3
57. Netzer, W. J. & Hartl, F. U. (1997). «Recombination of protein domains facilitated by co-translational folding in eukaryotes.» *Nature* 388(6640): 343–349. DOI 10.1038/41024
58. Frydman, J., Erdjument-Bromage, H., Tempst, P. & Hartl, F. U. (1999). «Co-translational domain folding as the structural basis for the rapid de novo folding of firefly luciferase.» *Nature Struct. Mol. Biol.* 6(7): 697–705. DOI 10.1038/10754
59. Cassaignau, A. M. E., Cabrita, L. D. & Christodoulou, J. (2020). «How Does the Ribosome Fold the Proteome?» *Annu. Rev. Biochem.* 89: 389–415. DOI 10.1146/annurev-biochem-062917-012226
60. Marsh, J. A. et al. (2013). «Protein Complexes Are under Evolutionary Selection to Assemble via Ordered Pathways.» *Cell* 153(2): 461–470. DOI 10.1016/j.cell.2013.02.044
61. Shiber, A. et al. (2018). «Cotranslational assembly of protein complexes in eukaryotes revealed by ribosome profiling.» *Nature* 561(7722): 268–272. DOI 10.1038/s41586-018-0462-y

### Teoría de la información y codificación

62. Shannon, C. E. (1959). «Coding Theorems for a Discrete Source With a Fidelity Criterion.» *IRE Int. Convention Record* 7: 325–350.
63. Cover, T. M. & Thomas, J. A. (1991). *Elements of Information Theory*, cap. 13, «Rate Distortion Theory». Wiley.
64. Nagle, A., Girish, A., Bondaschi, M., Gastpar, M., Makkuva, A. V. & Kim, H. (2024). «Fundamental Limits of Prompt Compression: A Rate–Distortion Framework for Black-Box Language Models.» *NeurIPS 2024*. arXiv:2407.15504
65. Luby, M. (2002). «LT Codes.» *FOCS 2002*, pp. 271–282. DOI 10.1109/SFCS.2002.1181950
66. Shokrollahi, A. (2006). «Raptor Codes.» *IEEE Trans. Inf. Theory* 52(6): 2551–2567.
67. Luby, M., Shokrollahi, A., Watson, M., Stockhammer, T. & Minder, L. (2011). *RFC 6330: RaptorQ Forward Error Correction Scheme for Object Delivery*.
68. Weatherspoon, H. & Kubiatowicz, J. D. (2002). «Erasure Coding vs. Replication: A Quantitative Comparison.» *IPTPS 2002*, LNCS 2429: 328–337.
69. Rodrigues, R. & Liskov, B. (2005). «High Availability in DHTs: Erasure Coding vs. Replication.» *IPTPS 2005*, LNCS 3640: 226–239.
70. Huang, C. et al. (2012). «Erasure Coding in Windows Azure Storage.» *USENIX ATC 2012*.
71. Mallick, A., Chaudhari, M., Palanikumar, G., Sheth, U. & Joshi, G. (2019). «Rateless Codes for Near-Perfect Load Balancing in Distributed Matrix-Vector Multiplication.» *Proc. ACM Meas. Anal. Comput. Syst.* 3(3), art. 58.
72. Kosaian, J., Rashmi, K. V. & Venkataraman, S. «Learning a Code: Machine Learning for Approximate Non-Linear Coded Computation.» arXiv:1806.01259
73. Soleymani, M., Ali, R. E., Mahdavifar, H. & Avestimehr, A. S. (2022). «ApproxIFER: A Model-Agnostic Approach to Resilient and Robust Prediction Serving Systems.» *AAAI-22*, pp. 8342–8350.

### Computación voluntaria

74. Anderson, D. P. (2004). «BOINC: A System for Public-Resource Computing and Storage.» *5th IEEE/ACM Int. Workshop on Grid Computing*. DOI 10.1109/GRID.2004.14
75. Anderson, D. P. & Fedak, G. (2006). «The Computational and Storage Potential of Volunteer Computing.» arXiv:cs/0602061
76. Anderson, D. P. (2018). «BOINC: A Platform for Volunteer Computing.» arXiv:1903.01699
77. Sarmenta, L. F. G. (2002). «Sabotage-tolerance mechanisms for volunteer computing systems.» *Future Generation Computer Systems* 18(4): 561–572.

### Inferencia descentralizada y descompuesta

78. Ning, X. et al. (2024). «Skeleton-of-Thought: Prompting LLMs for Efficient Parallel Generation.» *ICLR 2024*. arXiv:2307.15337
79. Borzunov, A. et al. (2022). «Petals: Collaborative Inference and Fine-tuning of Large Models.» arXiv:2209.01188
80. Ryabinin, M., Dettmers, T., Diskin, M. & Borzunov, A. (2023). «SWARM Parallelism…» *ICML 2023*, PMLR 202: 29416–29440
81. Leviathan, Y., Kalman, M. & Matias, Y. (2023). «Fast Inference from Transformers via Speculative Decoding.» *ICML 2023*, PMLR 202: 19274–19286
82. Chen, C. et al. (2023). «Accelerating Large Language Model Decoding with Speculative Sampling.» arXiv:2302.01318
83. Shazeer, N. et al. (2017). «Outrageously Large Neural Networks: The Sparsely-Gated Mixture-of-Experts Layer.» arXiv:1701.06538
84. Fedus, W., Zoph, B. & Shazeer, N. (2022). «Switch Transformers…» *JMLR* 23(120): 1–39
85. Khot, T. et al. «Decomposed Prompting: A Modular Approach for Solving Complex Tasks.» arXiv:2210.02406
86. Zhang, Y. et al. (2024). «Chain of Agents: Large Language Models Collaborating on Long-Context Tasks.» *NeurIPS 2024*
87. Wang, J. et al. (2024). «Mixture-of-Agents Enhances Large Language Model Capabilities.» arXiv:2406.04692
88. Dahshan, M., Mamun, Q. & Debnath, T. (2026). «SWARM-LLM: Collaborative Inference for Edge-based Small Language Models.» *IEEE VTC2026-Spring*
89. Li, J. et al. (2024). «More Agents Is All You Need.» *TMLR*

### Modos de fallo de sistemas multi-agente

90. Cemri, M. et al. (2025). «Why Do Multi-Agent LLM Systems Fail?» arXiv:2503.13657
91. Zhang, H. et al. (2025). «If Multi-Agent Debate is the Answer, What is the Question?» arXiv:2502.08788

---

*Swarmbly AI — Sebastián A. Espinoza-Ulloa · Compañero en inglés:
`WHITEPAPER_EXT_EN.md`. Documento principal: `WHITEPAPER_V2_ES.md`.*
