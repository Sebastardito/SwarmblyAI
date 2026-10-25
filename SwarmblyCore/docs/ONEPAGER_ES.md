---
status: current
lang: es
---
# Swarmbly AI

### La barrera para servir inteligencia artificial deja de ser el capital y pasa a ser la participación

**Sebastián A. Espinoza-Ulloa, Ph.D.** · Investigador independiente
Whitepaper v2.0 (doi:10.5281/zenodo.23031305) · especificación v0.2 · implementaciones de referencia, arnés de validación y mediciones publicadas
AGPL-3.0-or-later (software) · CC BY 4.0 (texto) · `github.com/Sebastardito/Swarmbly-AI`

---

## La asimetría

El conocimiento para construir inteligencia artificial es público. Los pesos de los modelos, las recetas de entrenamiento y los motores de inferencia se publican abiertamente y mejoran cada mes. **El capital para operarla no lo es.** Los centros de datos consumieron 415 TWh en 2024 —cerca del 1.5 % de la electricidad mundial— con proyecciones de 945 TWh para 2030, y esa curva de crecimiento pasa por la construcción, que solo está al alcance de quien puede financiarla.

De modo que una tecnología cuyo conocimiento es de todos termina controlada por quien puede pagar los edificios. No por una patente. Por un contrato de energía.

**Mientras tanto, el hardware ya existe, encendido y ocioso.** La plataforma insignia del cómputo voluntario agrega hoy alrededor de **700000 dispositivos activos, 4 millones de núcleos de CPU, 560000 GPU y 93 PetaFLOPS**, desde una comunidad que ha *encogido* un 80 % en dos décadas. Esa cifra es un suelo, tomado de un único nicho en declive, no una proyección. A nivel de una sola máquina, se reporta que una RTX 4090 ociosa sirve inferencia de modelos de lenguaje a **$0.111–0.149 por millón de tokens**, al 62–78 % del rendimiento de una H100 por aproximadamente la mitad del costo.

La capacidad de inferencia ociosa del mundo no es una hipótesis. Lo que faltaba era un protocolo bajo el cual pudiera usarse.

## Por qué nadie lo ha logrado todavía

Todos los intentos serios hasta ahora han repartido el **modelo**: distribuyen capas del transformer entre máquinas, de modo que las activaciones intermedias cruzan la internet pública en cada token generado. Ese diseño choca de frente con un muro físico: la interconexión de un centro de datos mueve 900 GB/s; la subida doméstica mueve unos 60 Mbps. **Una razón de aproximadamente 120000×**, y de cuatro a cinco órdenes de magnitud en latencia.

Los resultados medidos coinciden con la predicción. Petals, la implementación de referencia de ese enfoque, pierde el 31 % de su rendimiento solo por la red al pasar de un enlace de laboratorio a uno realista; un enjambre geodistribuido real de catorce servidores alcanza 0.83 pasos por segundo.

Eso no es una mala implementación. Es la respuesta correcta a la pregunta equivocada.

## El replanteamiento

Swarmbly hace otra pregunta: no *cómo ejecutar un modelo grande repartido entre muchas máquinas*, sino **cómo ejecutar muchos modelos pequeños completos sobre un problema grande.**

Un orquestador pequeño, en el computador del propio usuario, descompone la petición en microtareas semánticas. Cada una se despacha **una sola vez**, de forma asíncrona, a un nodo voluntario que ejecuta un modelo pequeño completo. Los fragmentos devueltos —*contigs*, en el vocabulario del ensamblaje de genomas que el diseño toma prestado deliberadamente— se verifican, se seleccionan y se empalman localmente.

**La red se cruza una vez por fragmento y por sesión, en lugar de una vez por capa y por token.** Ese único cambio mueve la arquitectura del lado del muro de 120000× donde pierde, al lado donde el hardware doméstico puede siquiera participar. Repartir un modelo crea una cadena, donde cada máquina espera a la anterior. Repartir un problema crea un conjunto, donde todas trabajan a la vez. Ese contraste es arquitectónico: el rendimiento y la latencia de Swarmbly todavía no se han medido, y esta página no hace ninguna afirmación de velocidad en su nombre.

## Lo que ya está medido

Hay dos cosas medidas, y apuntan en direcciones distintas. Las dos se dicen aquí.

**Fragmentar tiene un costo, y el propio criterio de abandono del proyecto todavía no puede pronunciarse.** Se registró públicamente un criterio de continuar o abandonar *antes de que existiera dato alguno*: si la pérdida no bajaba del 5 % en ninguna categoría de tarea, había que descartar la arquitectura. En la primera prueba sobre un corpus reservado, 16 prompts, la pérdida fue de **+2.30 %**, IC 95 % **[−2.05 %, +7.49 %]**. El criterio se escribió contra la cota superior, que queda por encima del umbral, así que el veredicto fue **no alcanzado**, y el umbral no se movió. El costo fue bimodal: 11 de 16 prompts no perdieron nada o ganaron, y dos prompts cargaron toda la media. Una segunda campaña, **473 corridas** sobre cinco familias de modelos pequeños, midió el costo con presupuesto de salida igualado: **+11.17 %**, IC 95 % **[+4.80, +17.34]**. Ese agregado sigue confundido con cuánto escribe cada brazo, así que el arnés publicado **se niega** a declarar el criterio cumplido o incumplido. Se reporta como *no medido*.

**Donde el diseño dice que fragmentar debería ganar, gana.** En extracción estructurada —leer los registros de un documento largo y responder preguntas sobre todos ellos—, un modelo pequeño que extrae las piezas, con código que las agrega, supera al mismo modelo respondiendo solo por **+46.9 puntos**, IC 95 % **[+33.3, +59.4]**. Un control que extrae el documento entero en una sola llamada separa los dos mecanismos. Con 80 filas toda la ganancia viene de sacarle la aritmética al modelo, y partir no añade nada. Con 160 filas la extracción en una sola llamada colapsa y sólo partir la sostiene, por **+77.1 puntos**. Un nodo pequeño extrae bien hasta cierto tamaño de tarea, y fragmentar es lo que mantiene cada tarea por debajo de ese tamaño. Es la tesis del diseño, medida directamente por primera vez. Es también estrecha —8 documentos, una familia de modelos, dos tamaños— y se dice que lo es.

**Una versión anterior de esta página reportaba una pérdida que caía de 24.1 % a 13.7 % al subir el contexto compartido, y decía que la predicción se había cumplido. Esa tabla queda retirada**: el eje de contexto no se había movido de verdad, y la métrica no era neutral entre brazos. La retirada se conserva íntegra, con su aritmética, en `docs/RESULTS_V0_V3C.md`.

## Lo que no está demostrado — dicho aquí, no escondido

Una de las contribuciones publicadas **no** sobrevivió. La arquitectura devuelve
un *mapa de confianza*: como familias de modelo independientes responden la
misma microtarea, su acuerdo puede puntuarse por unidad, y un proveedor
centralizado único no tiene nada que alinear. El mecanismo funciona. La
afirmación de que el acuerdo predice la calidad, no. La primera medición no
encontró **relación alguna** (*r* = −0.030 sobre 597 unidades) contra un juez
débil que aceptaba el 93 % de todo, así que el veredicto honesto entonces era
*sin sustento, no refutada*. Tres ejecuciones posteriores, calificadas contra una
clave de respuestas, dieron en cambio razones de momios comunes de **3.47, luego
0.26, luego 1.24**: por encima, por debajo y a caballo del 1 en la misma
pregunta. Eso no es una señal débil; es ninguna señal, medida tres veces. El
mapa de confianza queda **retirado**, no degradado, y no se le atribuye ningún
beneficio de fiabilidad.

Las mediciones son además pequeñas: modelos de 2–4 B parámetros en hardware
local, y familias de tareas elegidas porque se pueden comprobar. Una señal sobre
la que actuar, no un banco de referencia.

**Cuatro cosas que este proyecto no afirma.** **No es más rápido que una API comercial** para quien ya tiene el equipo para usarla: la decodificación especulativa en un solo nodo le gana en latencia a cualquier esquema de fragmentación, y la latencia propia de Swarmbly ni siquiera está medida. **No ofrece contexto ilimitado**, solo un límite mucho más alto que vive en la máquina del usuario en vez de en el plan de precios de un proveedor. **No es cifrado**: fragmentar encarece la reconstrucción y nada más, y por eso el trabajo realmente sensible se enruta a un círculo cerrado o se mantiene enteramente local. Y **no ha demostrado un beneficio ambiental**: el argumento es sólido, la medición todavía no está hecha, y el proyecto se compromete a publicarla sea cual sea el resultado.

Esta sección existe porque un proyecto que esconde su primer resultado negativo no se ha ganado el primero positivo.

## Por qué ahora, y qué existe hoy

Los modelos pequeños cruzaron hace poco la línea de capacidad que hace esto posible; la brecha de ancho de banda que mató al reparto de modelos no se está cerrando. La oportunidad es de temporización.

Publicado y público a septiembre de 2026: la versión 2 del whitepaper, en español e inglés, con 135 referencias; una especificación completa del protocolo; dos implementaciones de referencia; un arnés de validación que se niega a dar veredicto cuando su instrumento no puede decidir; un banco de 473 corridas que cualquiera puede volver a ejecutar; y todas las mediciones completas, incluidas las retiradas. Todo bajo AGPL-3.0-or-later para que un despliegue alojado no pueda cerrarlo, con un registro de anterioridad fechado.

**Lo que necesita a continuación es un equipo y los medios para correrlo a escala.** Las siguientes preguntas —dónde está el umbral de extracción para cada clase de nodo, y si existe un presupuesto de contexto que satisfaga a la vez coherencia, privacidad, verificabilidad y capacidad del trabajador— necesitan más que el hardware de una sola persona. Y la forma más probable de que esto fracase no es un fallo de ingeniería; es que nadie se conecte. El cómputo voluntario lleva veinte años en declive, y el mejor protocolo del mundo no vale nada en una red vacía.

El conocimiento ya es público. El hardware ya está construido. Lo que faltaba es el protocolo, y ya está sobre la mesa, donde cualquiera puede revisarlo.

---

*Argumento técnico completo: `docs/WHITEPAPER_V2_ES.md`. Versión divulgativa: `docs/DIVULGACION_ES.md`. Resultados actuales completos: `docs/RESULTS_2026-09-25_refbench_ES.md`; la primera prueba sobre corpus reservado: `docs/RESULTS_TABLES_FINAL_CORRECTED.md`. Las primeras mediciones, retiradas y conservadas con su aritmética: `docs/RESULTS_V0_V3C.md`. Versión en inglés de esta página: `ONEPAGER_EN.md`.*
