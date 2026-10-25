---
status: draft
lang: es
---

# Cognición local y transmisión anclada

## Una extensión cognitiva local-first para Swarmbly: memoria personal, aprendizaje del modelo del usuario y transferencia ligera de conocimiento sobre nodos voluntarios no confiables

**Sebastián A. Espinoza-Ulloa, Ph.D.**\
Investigador independiente\
ORCID: [0000-0003-1497-356X](https://orcid.org/0000-0003-1497-356X) · GitHub: [@Sebastardito](https://github.com/Sebastardito)

> **Nota sobre afiliación e independencia.** Este trabajo se realiza íntegramente
> a título personal como investigador independiente. El autor mantiene
> afiliaciones académicas —Pontificia Universidad Católica del Ecuador y
> University of Saskatchewan— y un empleo en NRGene Canada, ajenos al objeto de
> este trabajo. **Ninguna de esas instituciones ha aportado financiación, materiales,
> recursos de cómputo, personal ni apoyo institucional a este proyecto, y no se
> reclama ni se implica respaldo institucional alguno.**
>
> **Antecedente relevante.** El autor es Ph.D. en Biología (University of
> Saskatchewan) en genómica de poblaciones, y trabaja en mejoramiento genético
> por selección. Las homologías de genética de poblaciones, genética
> cuantitativa y evolución cultural que usa este documento proceden de ese
> antecedente; la sección 3 aplica a cada una el criterio del whitepaper v2 por
> el cual una analogía se acepta o se descarta.

**Versión 0.1 (borrador) — 4 de octubre de 2026**

---

> ## Estado de este documento: BORRADOR
>
> Versión 0.1, del 4 de octubre de 2026. **Preprint en borrador; no revisado por pares.**
> Es la extensión del protocolo descrito en el whitepaper v2 [1] y no lo
> modifica: nada de lo que aquí se propone forma parte de la especificación v0.2
> ni de la v0.3.
>
> **Nada de lo que este documento propone se ha medido todavía.** Cada
> mecanismo llega con su hipótesis, su experimento y su condición de abandono
> (sección 11), y el documento se publicará con los veredictos dentro, igual que
> el whitepaper v2. Las cifras que aparecen son cálculos derivados de
> parámetros publicados o hallazgos de la literatura citada, nunca resultados
> propios.
>
> **Código y arnés.** Esta versión se publica con una implementación de
> referencia (`swarmbly_lce/`) y un arnés de validación (`lce_validation/`).
> Seis instrumentos simulados pasan su prueba y los experimentos C1, C2 y C10
> corren de extremo a extremo con un backend simulado (sección 11.6). **Nada de
> eso es evidencia**: muestra que las medidas responden a lo que miden. Las
> corridas con modelos reales están pendientes y se reportarán en la versión 0.2.
>
> **Documentos complementarios.** `SPEC_LCE_ES.md` (arquitectura y
> especificación normativa), `swips/SWIP-XXXX-local-cognitive-extension.md`
> (propuesta formal en inglés para el repositorio del protocolo),
> `REFERENCES_LCE.md` (bibliografía anotada) y los borradores de trabajo en
> `_archive/drafts/`.

---

## Índice

0. Qué es este documento y de dónde viene
1. Introducción
2. Antecedentes y trabajo relacionado
3. El método aplicado: qué homologías sirven aquí
4. Principios de diseño
5. El plano local
6. Integración con el protocolo Swarmbly
7. El plano social
8. Arquitectura completa e invariantes
9. Economía e incentivo
10. Privacidad, seguridad y modelo adversario
11. Evaluación: hipótesis, experimentos y criterio de abandono
12. Limitaciones
13. Elementos a declarar como arte previo
14. Hoja de ruta
15. Conclusión
16. Referencias

---

## 0. Qué es este documento y de dónde viene

Swarmbly fragmenta el problema y no el modelo: un orquestador en el cliente descompone la petición en microtareas semánticas, las despacha una vez a nodos voluntarios que ejecutan modelos pequeños completos, y ensambla los resultados en local [1]. En ese diseño los workers son deliberadamente casi sin estado, y el cliente es la única unidad que conserva memoria entre peticiones. Este documento propone qué hacer con esa memoria. Describe una **extensión cognitiva local (LCE)** en la que cada usuario mantiene en su propio dispositivo una memoria legible y portable, un modelo que aprende de él lo que él decide enseñarle, y una forma opcional y barata de compartir con otros nodos el conocimiento que quiera hacer público.

La propuesta nació de una pregunta del autor: cómo afinar un modelo local con la información de su usuario sin supervisión, y si los modelos de una red podrían aprender entre sí hasta formar algo parecido a un organismo, con vecindarios de identidad y conocimiento que sobrevive a la desaparición de los nodos que lo originaron. Esa pregunta pasó por cuatro borradores de trabajo, conservados en `_archive/drafts/`. El primero construía una red cognitiva paralela a Swarmbly, con grafo de conocimiento global, enrutamiento de conocimiento, motor de confianza, gossip y replicación activa, y el autor lo rechazó por contradecir el principio que hace viable al protocolo. El segundo (v0.2) reescribió la propuesta como una extensión local-first que reutiliza las primitivas existentes. El tercero (v0.3) sometió sus analogías al método del whitepaper v2 y cerró seis huecos, entre ellos el colapso de modelos y el choque con la verificación. El cuarto (v0.4) rescató siete ideas de la fase exploratoria que pasaban ese mismo método. Este documento consolida los cuatro en un texto continuo, con una revisión bibliográfica nueva que añade evidencia adversa que los borradores no tenían.

**Tabla de cambios respecto de los borradores.**

| en los borradores | en este documento |
|---|---|
| 200 secciones en formato de notas, con listas y pseudocódigo intercalados | **Reescrito** como paper continuo de 16 secciones; el detalle normativo pasa a `SPEC_LCE_ES.md` |
| Principios P12–P16 enunciados como propuestas sueltas (v0.2) | **Consolidados** con tres principios nuevos, P17–P19 (sección 4) |
| La diversidad de familias de modelo como garantía de independencia de errores | **Matizada** por la evidencia de errores correlacionados entre familias y de homogeneidad entre modelos [35, 36] (secciones 2.6, 6.4 y LC3) |
| El conformismo como riesgo teórico tomado de la evolución cultural humana | **Respaldado** por mediciones de conformismo en LLM [45] y por simulaciones de dinámica de opiniones con agentes LLM [46] (sección 7.4) |
| La regla "lo social es minoritario" justificada por un solo resultado [29] | **Respaldada** por la condición formal de estabilidad del reentrenamiento iterativo [31] y por el resultado de autoconsumo con datos nuevos [30] (sección 7.3) |
| La regla de anclaje sin instrumento de verificación | **Instrumentada** con la evaluación por afirmaciones atómicas [20] y con la evidencia de que los modelos no citan de forma fiable [21] (sección 5.2) |
| El olvido en pesos como regeneración opcional | **Convertido** en la única vía verificable, a la vista de los resultados negativos de desaprendizaje [59, 60] (sección 5.8) |
| La diversidad del aprendizaje local como posible remedio de la correlación entre familias | **Descartada** como remedio dentro de una petición; reconocida como reducción de la homogeneidad entre usuarios (secciones 2.6 y 6.4, H-C17) |
| Sin código ni arnés | **Implementación de referencia** con 77 pruebas, una por invariante, y **arnés** con seis instrumentos probados en simulación (sección 11.6) |
| Hipótesis H-C1–H-C15 dispersas en tres secciones | **Reunidas**, más H-C16 y H-C17, con los experimentos C0–C12 y sus condiciones de muerte (sección 11) |

Dos ideas de la fase exploratoria entraron a la revisión y no sobrevivieron como mecanismo: la neurona hebbiana como modelo de la red, que aporta solo su modo de fallo, y la transferencia genética horizontal como modelo del intercambio entre nodos, que no trae un instrumento aplicable. Las dos se documentan en la sección 3, porque el diagnóstico de por qué fallan orienta el diseño tanto como las homologías que sí transfieren.

---

## 1. Introducción

### 1.1 Un nodo sin memoria y una red sin incentivo

El whitepaper v2 declara que el riesgo dominante del proyecto no es técnico [1, sección 16, L10]. La computación voluntaria ha pasado de atraer del orden de un millón de participantes a unos doscientos mil, y ofrecer "créditos de red" a cambio de ciclos ociosos no explica por qué Swarmbly tendría un destino distinto. El diagnóstico de fondo es que la computación voluntaria clásica pedía altruismo: el voluntario cedía su máquina a un problema ajeno y no recibía nada que quisiera para sí.

Al mismo tiempo, el diseño de Swarmbly deja sin usar el recurso más personal del sistema. El cliente es el único componente con estado, y cada petición que procesa contiene información sobre su usuario (su vocabulario, su registro, sus temas, sus correcciones) que hoy se descarta al terminar. Los asistentes comerciales resuelven esa pérdida guardando el historial del usuario en sus servidores, de modo que la personalización se convierte en otra forma de concentración: quien tiene la memoria tiene al usuario. Un protocolo cuyo propósito es democratizar el acceso a la inferencia no puede resolverla así.

Hay una tercera tensión, menos visible. El valor que el autor atribuye a una red como Swarmbly no es solo el acceso al cómputo sino **la diversidad de respuestas**: modelos de familias distintas, usuarios distintos, culturas distintas. Esa diversidad está amenazada desde dos lados. Los modelos de lenguaje actuales tienden a homogeneizar lo que producen, entre sí y respecto de sus datos de entrenamiento [33, 34, 35], y cualquier mecanismo de aprendizaje entre nodos que entrene modelos con la salida de otros modelos corre el riesgo de colapsar precisamente las variantes raras que hacían valiosa a la red [28, 32].

### 1.2 La tesis

La tesis de este documento es que **un estado cognitivo local, portable y controlado por el usuario puede reducir trabajo repetido, mejorar la personalización y conservar conocimiento útil entre nodos sin destruir la economía, la privacidad y la diversidad que hacen viable a Swarmbly**. La pregunta es medible, y está formulada para poder fallar.

La arquitectura que sostiene esa tesis tiene tres planos. En el plano local, que vive entero en el dispositivo, una wiki legible aprende rápido y un adaptador ligero aprende despacio, con una capa epistémica que decide qué puede pasar de la memoria al comportamiento. En el plano de inferencia, Swarmbly no cambia: la personalización entra solo a través del contrato global Γ que el protocolo ya define, y los workers sirven su modelo base. En el plano social, que es opcional, los nodos se piden pequeñas cápsulas de conocimiento escrito, no pesos, y las conservan si les resultan útiles, de modo que lo usado sobrevive a la desaparición de su origen sin un servicio de replicación.

La forma de esa arquitectura no es arbitraria. Cada pieza viene de una homología que pasa el método del whitepaper v2 o de un resultado empírico de la literatura, y cada una trae su modo de fallo enunciado: la interferencia catastrófica para el aprendizaje local, el colapso de modelos y el conformismo para el aprendizaje entre nodos, la sobreestimación por reutilización de pruebas para la selección de adaptadores, la confianza transitiva para la procedencia. Gran parte del diseño consiste en las reglas que evitan esos fallos.

### 1.3 Alcance de las afirmaciones

Cinco afirmaciones que un lector podría esperar están deliberadamente ausentes, y la sección 12 desarrolla cada una.

No afirmo que **el modelo personal aprenda hechos**. La evidencia es que ajustar un modelo con conocimiento nuevo rinde menos que recuperarlo y aumenta la alucinación [13, 14], de modo que en este diseño los hechos viven en la wiki y a los pesos va solo el comportamiento.

No afirmo **olvido verificable en los pesos** salvo por regeneración del adaptador. Los métodos de desaprendizaje disponibles no logran un olvido efectivo ni soportan solicitudes sucesivas [59, 60].

No afirmo que **la diversidad de familias de modelo garantice errores independientes**. La evidencia más reciente muestra errores correlacionados entre modelos de arquitecturas y desarrolladores distintos [36] y homogeneidad entre modelos en tareas abiertas [35]. La LCE hereda esa limitación del protocolo y no la resuelve.

No afirmo que **la red se vuelva más inteligente porque se comunica**. Esa frase de la fase exploratoria se conserva solo como hipótesis medible sobre ahorro de trabajo repetido (H-C4).

No afirmo **resolver el problema de incentivo de la computación voluntaria**. La extensión ofrece un mecanismo candidato y una métrica que puede refutarlo (sección 9), no una solución.

### 1.4 Aportaciones y estructura

La sección 2 sitúa la propuesta frente al trabajo previo, incluida la evidencia adversa. La sección 3 aplica el método del whitepaper v2 a las siete homologías candidatas y descarta tres. La sección 4 añade ocho principios a los once del protocolo. Las secciones 5 a 7 describen los tres planos, y la 8 los reúne en una arquitectura con ocho invariantes que cualquier implementación debe preservar. La sección 9 trata la economía y el incentivo; la 10, la privacidad y el modelo adversario. La sección 11 especifica los experimentos y las condiciones bajo las cuales se abandonaría cada componente. La 12 lista las limitaciones, la 13 los elementos que se declararán como arte previo al publicar, y la 14 la hoja de ruta.

Las aportaciones sustantivas son cuatro. La primera es una regla de reparto entre memoria y pesos derivada de la literatura de inyección de conocimiento y formalizada como una capa epistémica con tipos de afirmación y estados de madurez. La segunda es la traducción de tres resultados de genética de poblaciones y evolución cultural a reglas de diseño cuantitativas: un presupuesto de migración entre vecindarios, una regla contra el conformismo, y una persistencia ponderada por rareza con un número de réplicas derivado de una tolerancia. La tercera es la variación anclada, que reconcilia la idea de que el conocimiento compartido evolucione con la restricción, impuesta por el colapso de modelos, de no entrenar con derivados de derivados. La cuarta es la selección de adaptadores tratada como selección artificial, con la ecuación del criador como instrumento y la reutilización de pruebas como modo de fallo.

---

## 2. Antecedentes y trabajo relacionado

### 2.1 Personalización de modelos de lenguaje

La personalización de LLM se ha consolidado como campo con taxonomías propias [3] y benchmarks de evaluación como LaMP, que mide la generación personalizada en siete tareas y muestra que la recuperación de perfil mejora a los modelos base [4]. El arte previo más cercano a la capa local de esta propuesta es OPPU, que asigna a cada usuario un módulo de ajuste eficiente en parámetros (PEFT) para almacenar sus patrones de comportamiento y preferencias, y lo combina con recuperación para el conocimiento que cambia [5]. Esa división del trabajo, parámetros para el comportamiento y recuperación para el conocimiento, es la misma que la LCE adopta, y llegar a ella por dos caminos independientes es un indicio a favor. Per-Pcs extiende la idea a un régimen colaborativo en el que los usuarios descomponen sus adaptadores en piezas que otros pueden combinar [6]. La LCE toma la dirección contraria por defecto, compartir conocimiento escrito y no parámetros, por razones de privacidad, verificación y diversidad que la sección 7 desarrolla.

### 2.2 Memoria de agentes y wikis mantenidas por modelos

Los agentes con memoria en lenguaje natural son el segundo antecedente. Generative Agents guarda un flujo completo de experiencias, las sintetiza periódicamente en reflexiones de mayor nivel y las recupera para planificar [8]; MemGPT gestiona niveles de memoria con técnicas inspiradas en sistemas operativos [9]; A-MEM organiza las memorias como una red de notas enlazadas al modo Zettelkasten, en la que una nota nueva puede modificar las existentes [10]. El patrón de wiki mantenida por un LLM que propone Karpathy [7] es la versión más simple y más legible de esta familia: fuentes en bruto inmutables, una wiki en Markdown que el modelo escribe y mantiene, y tres operaciones (ingerir, consultar y revisar contradicciones). La LCE adopta ese patrón como capa 1 porque su representación es legible por humanos, versionable y desacoplada del modelo, tres propiedades que coinciden con los principios del software local-first: los datos son del usuario, funcionan sin red y sobreviven a la herramienta que los creó [11].

### 2.3 Inyección de conocimiento: recuperación frente a ajuste

La pregunta de qué debe ir a los pesos tiene ahora respuesta empírica. En la comparación directa entre ajuste no supervisado y generación aumentada por recuperación [12], la recuperación supera de forma consistente al ajuste tanto para conocimiento visto en el preentrenamiento como para conocimiento nuevo [13]. Gekhman et al. muestran además que los ejemplos con conocimiento nuevo se aprenden bastante más despacio que los consistentes con lo que el modelo sabe y que, una vez aprendidos, aumentan de forma lineal la tendencia del modelo a alucinar [14]. Para fijar un hecho en los parámetros cuando el usuario lo exige, el preentrenamiento continuo sintético genera muchas reformulaciones del mismo contenido y produce un conocimiento que se suma a la recuperación en lugar de sustituirla [15]. En cuanto al mecanismo, LoRA [16] y su variante cuantizada [17] hacen viable el ajuste en hardware de consumo, y la comparación sistemática con el ajuste completo muestra que LoRA aprende menos pero olvida menos de lo que el modelo base sabía [18]. La optimización directa de preferencias permite usar pares "preferido / rechazado" sin un modelo de recompensa separado [19].

La atribución es la otra cara de la memoria. FActScore descompone un texto en afirmaciones atómicas y mide qué fracción está soportada por una fuente fiable, y encontró que un modelo comercial de referencia alcanzaba solo el 58 % en biografías [20]. En la generación con citas, incluso los mejores modelos carecían de soporte completo la mitad de las veces [21]. Ambos resultados importan para una wiki escrita por un modelo: el digestor puede inventar, y su anclaje a las fuentes debe verificarse con código.

### 2.4 Aprendizaje continuo y sistemas complementarios

La teoría de los sistemas de aprendizaje complementarios explica por qué el cerebro de los mamíferos separa un sistema hipocampal de aprendizaje rápido de un sistema neocortical de consolidación lenta: una red distribuida que aprende rápido información nueva la incorpora a costa de lo que ya sabía [22]. Ese costo, la interferencia catastrófica, se documentó antes que la teoría [23], y la actualización de la teoría para agentes artificiales la conecta con el repaso de experiencias en aprendizaje profundo [24]. En modelos de lenguaje el olvido catastrófico se observa de forma general en el rango de 1B a 7B parámetros durante el ajuste continuo [26], que es exactamente el rango de los nodos de Swarmbly, y el aprendizaje continuo con repaso conserva las tareas previas en modelos ajustados por instrucciones [27]. La alternativa por regularización, que penaliza el cambio de los pesos importantes para tareas previas [25], exige conservar el estado del adaptador anterior, y la sección 5.6 explica por qué la LCE prefiere regenerar cada adaptador desde cero.

### 2.5 Colapso de modelos y homogeneización

Entrenar modelos generativos de forma recursiva con datos producidos por modelos anteriores causa defectos irreversibles, y el primer síntoma es la desaparición de las colas de la distribución original [28]; el fenómeno puede describirse como un cambio en las leyes de escala que empieza por la pérdida de lo infrecuente [32]. Sin datos reales nuevos en cada generación de un bucle autoconsumidor, la calidad o la diversidad de los modelos decaen progresivamente [30]. Hay, sin embargo, dos resultados que acotan el problema. El reentrenamiento iterativo es estable si el modelo inicial aproxima bien los datos y la proporción de datos limpios es suficientemente grande [31], y cuando los datos sintéticos se acumulan junto a los reales, en lugar de reemplazarlos, el error queda acotado con independencia del número de iteraciones [29].

La homogeneización tiene también una dimensión que no depende del reentrenamiento. Escribir con un modelo ajustado con retroalimentación reduce la diversidad entre los textos de autores distintos [33]; los modelos estrechan su diversidad respecto de sus propios datos de entrenamiento, y cambiar el muestreo o el prompt no lo corrige [34]; y modelos distintos producen respuestas sorprendentemente parecidas en tareas abiertas, un efecto que sus autores llaman "mente colmena artificial" [35]. En el plano del bienestar colectivo, que todos los agentes usen el mismo algoritmo puede empeorar el resultado conjunto aunque ese algoritmo sea el mejor individualmente [37], y los modelos actuales reflejan de forma desigual las opiniones de los grupos humanos, con una desalineación que persiste al intentar dirigirlos [38].

### 2.6 La evidencia adversa principal: errores correlacionados

El resultado que más afecta a esta propuesta no trata de personalización sino del supuesto en que descansa la redundancia de Swarmbly. El despacho preservador de diversidad (E12) asigna réplicas a familias de modelo distintas porque supone que sus errores son aproximadamente independientes [1]. Kim et al. evaluaron más de 350 modelos y encontraron que, en uno de los leaderboards estudiados, **dos modelos coinciden en la respuesta el 60 % de las veces cuando ambos se equivocan**, y que los modelos más grandes y capaces correlacionan sus errores incluso cuando tienen arquitecturas distintas y vienen de desarrolladores distintos [36]. El efecto de mente colmena en tareas abiertas apunta en la misma dirección [35]. La LCE no puede corregir este problema, que pertenece al protocolo, pero sí puede evitar agravarlo, y la regla de servir el modelo base (sección 6.3) existe en parte por eso: si nodos de familias distintas entrenaran adaptadores con las mismas cápsulas, añadirían una fuente de correlación más.

Cabe preguntarse si la diversidad que genera el propio aprendizaje local de cada usuario corrige el problema, y la respuesta es que no dentro de una misma petición. Por diseño, los workers sirven su modelo base (sección 6.3), de modo que lo que cada cliente aprende no llega a las réplicas que E16 alinea. Aunque llegara, no cambiaría la estructura de los errores: el adaptador aprende comportamiento y no hechos (sección 5.3), y LoRA conserva el conocimiento del modelo base [18], y con él sus errores. La correlación de Kim et al. procede en buena parte de lo que los modelos comparten antes de cualquier personalización. En términos de genética de poblaciones es **identidad por descendencia**: los modelos comparten ancestría porque se preentrenaron sobre corpus muy solapados, y un adaptador local se parece más a una plasticidad fenotípica, que cambia la expresión, que a la incorporación de alelos nuevos. La independencia que necesita un consenso exige otra fuente de variación, y si alguna la aporta es la evidencia sobre la que razona cada réplica, no sus pesos. Esa hipótesis pertenece al protocolo y no a la LCE, y se ha registrado aparte como nota para la próxima versión del whitepaper (`Swarmbly-AI/docs/FINDING_2026-10-04_correlated_errors_across_families_ES.md`).

### 2.7 Aprendizaje descentralizado

El aprendizaje federado entrena un modelo global a partir de actualizaciones locales coordinadas en rondas [62], y el gossip learning elimina el coordinador intercambiando modelos entre pares, con rendimiento competitivo [63]. Ambos convergen, por diseño, hacia un modelo común, que es lo contrario de lo que esta propuesta busca, y ambos generan tráfico permanente. La composición dinámica de adaptadores permite combinar módulos LoRA para tareas nuevas [64], pero exige la misma familia y versión de modelo, una condición que una red heterogénea por diseño no cumple. La sección 7.1 recoge estas alternativas como descartadas.

### 2.8 Evolución cultural de máquinas

La teoría cuantitativa de la evolución cultural distingue transmisión vertical, oblicua y horizontal, con dinámicas distintas [39], y modela sesgos de transmisión como el conformismo, en el que una variante se adopta con probabilidad desproporcionada a su frecuencia [40], que reduce la variación dentro de los grupos y aumenta la diferencia entre ellos [41]. El programa de investigación sobre "cultura de máquinas" sostiene que los sistemas inteligentes ya alteran los tres procesos de la evolución cultural, variación, transmisión y selección, y que los chatbots funcionan como modelos culturales nuevos [42]. Existen marcos abiertos para simular evolución cultural en poblaciones de LLM [43], y las normas que emergen en sociedades de agentes LLM dependen fuertemente del modelo base [44]. Dos mediciones recientes hacen concreto el riesgo para esta propuesta. Los LLM muestran conformismo medible en entornos colaborativos, creciente con el tamaño de la mayoría y con el tiempo de interacción [45], y las redes de agentes LLM tienden a converger hacia el consenso por un sesgo propio del modelo, mientras que con un sesgo de confirmación inducido se fragmentan [46]. El resultado de una red de modelos depende, por tanto, de los sesgos de sus agentes y no solo de su topología.

---

## 3. El método aplicado: qué homologías sirven aquí

El whitepaper v2 establece que una homología sirve cuando trae un instrumento (un procedimiento, una desigualdad o un número aplicable al problema nuevo) y que las homologías que transfieren vienen acompañadas de su modo de fallo [1, sección 3]. Su prueba operativa tiene tres preguntas: si la homología trae instrumento, si trae el enunciado de qué ocurre cuando su condición se viola, y si las condiciones del campo de origen se cumplen aquí. La propuesta original de la LCE llegó cargada de analogías biológicas, y esta sección las somete a esa prueba antes de construir sobre ninguna.

| homología candidata | instrumento | modo de fallo | condiciones | veredicto |
|---|---|---|---|---|
| Sistemas de aprendizaje complementarios [22, 24] | repaso intercalado; dos velocidades de aprendizaje | interferencia catastrófica [23] | parcial: el repaso es muestreo deliberado, no reactivación espontánea | **transfiere** (sección 5.5) |
| Modelo de islas de Wright [47] | F_ST ≈ 1/(1+4Nm); presupuesto de migración | la inversión falla fuera de equilibrio, con selección o con islas finitas [48] | parcial: las cápsulas no son neutras y la "generación" debe definirse | **transfiere como punto de partida** (sección 7.5) |
| Transmisión cultural y conformismo [39, 40, 41] | contabilidad de vías; Δp = D·p(1−p)(2p−1) | el conformismo elimina variantes minoritarias | sí, y medido en LLM [45, 46] | **transfiere** (sección 7.4) |
| Selección dependiente de la frecuencia [50] | la selección negativa mantiene polimorfismos | mantiene también variantes sin valor | sí, con condiciones de entrada | **transfiere** (sección 7.6) |
| Selección artificial [51] | ecuación del criador; índice restringido | respuesta correlacionada; sobreajuste al criterio | sí | **transfiere** (sección 5.6) |
| Neurona hebbiana [52] | ninguno aplicable a la red | crecimiento sin cota, corregido por normalización [53, 54] | no: los nodos tienen dueños, no hay integración central, viven 91 días de media | **solo el modo de fallo** (sección 7.7) |
| Transferencia genética horizontal | ninguno | no se enunció | no | **vocabulario** |
| "Organismo" o "cerebro" | ninguno | ninguno | no | **vocabulario**; la lectura exacta es "población con memoria cultural" |

Tres observaciones sobre la tabla. La primera es que las dos homologías descartadas como mecanismo fallan por la misma razón que el whitepaper v2 encontró en el codón y los *fountain codes*: traen un mecanismo atractivo sin la patología que lo acompaña. La neurona hebbiana se propuso como "los nodos que se comunican se conectan más", sin decir que esa regla, sin normalización, crece sin cota; y ese crecimiento sin cota es, en una red de nodos, exactamente la cámara de eco. La segunda observación es que la homología neuronal deja, aun descartada, una regla útil: la afinidad entre nodos decae y se normaliza por dominio. La tercera es que dos de las homologías que transfieren, Wright y la selección dependiente de la frecuencia, lo hacen con salvedades sobre sus condiciones que el documento enuncia completas, y por eso se usan para fijar puntos de partida y predicciones cualitativas, nunca valores exactos.

La lectura que sobrevive de la palabra "organismo", que acompañó a la propuesta desde su origen, es la de **una población con memoria cultural**: individuos con dueño que aprenden verticalmente de sus usuarios y horizontalmente entre sí, cuya diversidad se gobierna con un presupuesto de migración, y cuya memoria sobrevive al recambio de individuos por redundancia derivada de una tolerancia. Es menos evocadora que un cerebro y bastante más exacta.

---
## 4. Principios de diseño

El whitepaper v2 enuncia once principios, P1 a P11 [1, sección 4], y la LCE no modifica ninguno. Los añade bajo la misma regla: cada principio nuevo sale de una sección del documento y decide algo concreto. Los cinco primeros proceden del borrador v0.2; los tres últimos, de las revisiones v0.3 y v0.4.

**P12 — Aprender primero en local; transmitir solo la abstracción que paga su costo de red.** La red se usa cuando su beneficio medido supera su costo. Por defecto, la extensión no añade ningún mensaje al protocolo. (Secciones 5 y 7)

**P13 — La memoria personal es estado; la ejecución del worker es trabajo. No se confunden.** Un nodo que trabaja para otros sirve su modelo base sin adaptador, ejecuta, devuelve y descarta. El cerebro personal del dueño del nodo nunca toca las tareas ajenas. (Sección 6.3)

**P14 — La repetición mide prevalencia, no verdad, y no decide la adopción.** Que muchos nodos repitan algo es una etiqueta que puede mostrarse; no es evidencia factual ni criterio para cachear, consolidar o entrenar. (Sección 7.4)

**P15 — Preservar la diversidad antes de optimizar la convergencia, y reportarla.** La diversidad se presupuesta con un número (la migración entre vecindarios) y se mide con un estadístico que la red puede publicar, en el espíritu de P6. (Sección 7.5)

**P16 — La cognición compartida es opcional y retrocompatible.** Un nodo sin LCE sigue siendo un worker Swarmbly plenamente válido, y un nodo con LCE se comporta ante uno sin ella exactamente como el protocolo actual. (Sección 6.6)

**P17 — Hechos en la wiki, comportamiento en los pesos.** A los parámetros van la voz, el registro, la terminología, los procedimientos y los formatos. Los hechos se recuperan. (Sección 5.3)

**P18 — Acumular, nunca reemplazar; la variación viene de personas.** El material de otros nodos es siempre minoritario, trazable a un origen humano, y solo puede tener descendientes si trae evidencia humana nueva. (Secciones 7.3 y 7.8)

**P19 — Lo no declarado no entrena.** La política de aprendizaje es explícita por fuente, y su valor por defecto produce un sistema que recuerda pero no aprende. (Sección 5.7)

---

## 5. El plano local

### 5.1 Tres capas que aprenden a distinto ritmo

El plano local tiene tres capas, y su separación responde a la homología de los sistemas complementarios de la sección 3. La capa 0 es el espacio de fuentes del usuario: una carpeta de trabajo en la que deposita documentos, escritos, conversaciones, transcripciones o código, que se conserva inmutable y sirve de única verdad de origen. La capa 1 es la wiki: páginas Markdown que un modelo local escribe y mantiene a partir de las fuentes, siguiendo el patrón de ingerir, consultar y revisar contradicciones [7]. Es la capa que aprende rápido, el papel hipocampal. La capa 2 es el adaptador LoRA: aprende despacio, se entrena solo cuando el dispositivo está ocioso, y recibe únicamente lo que la capa 1 ha consolidado. Es la capa neocortical.

Entre las capas rige el principio que el whitepaper v2 midió en su experimento T08R3: el modelo extrae y el código agrega [1, sección 15.4]. En la LCE el modelo digiere fuentes y propone afirmaciones, mientras que el índice, los enlaces, los anclajes, las dependencias y las revisiones son código determinista. Esta separación importa porque los modelos no citan de forma fiable [21] y porque cualquier decisión que deba auditarse después (qué entró al entrenamiento, por qué, desde qué fuente) tiene que ser reproducible.

### 5.2 La capa epistémica

La wiki no es una colección de notas sin tipo. Cada afirmación que contiene lleva cuatro atributos, y en conjunto forman lo que este documento llama la capa epistémica local.

El primero es el **anclaje**: cada afirmación apunta al fragmento exacto de la fuente en bruto del que se extrajo. La regla responde a un fallo conocido del patrón de wiki mantenida por un modelo, que puede almacenar una alucinación y recuperarla después como si fuera un hecho. Su verificación usa la lógica de FActScore [20]: una afirmación atómica está anclada si el fragmento citado la soporta según un verificador, y solo las afirmaciones ancladas son elegibles para cualquier uso posterior en entrenamiento.

El segundo atributo es el **tipo**. Una afirmación puede ser un hecho sobre el mundo con fuente externa (`fact`), una afirmación, opinión o creencia del usuario (`user_claim`, `opinion`, `belief`), una hipótesis abierta (`hypothesis`), una experiencia episódica (`experience`), o un patrón de comportamiento (`preference`, `style`, `procedure`). El tipo decide el destino. Si el usuario anota que una sustancia causa una enfermedad, el sistema lo conserva como afirmación del usuario con su fuente, lo recupera atribuido ("el usuario sostiene que…") y nunca lo trata como hecho ni lo entrena como aserción. Solo los tres tipos de comportamiento son elegibles para el adaptador.

El tercero es el **estado de madurez**. Una afirmación recorre los estados RAW, DIGESTED, ANCHORED, CONNECTED, CORROBORATED, CONSOLIDATED y, únicamente para los tipos de comportamiento, TRAINABLE. Para un hecho, CORROBORATED exige dos fuentes humanas independientes; para un patrón de estilo, estabilidad a lo largo de varios ciclos de consolidación. Los estados hacen explícita la consolidación lenta: nada pasa de la memoria al comportamiento por haber sido visto una vez.

El cuarto es la **procedencia**, que registra la distancia epistémica de la afirmación a una fuente humana y la vía por la que llegó (vertical, del propio usuario; horizontal, de otro nodo; oblicua, de nodos establecidos hacia uno nuevo). La sección 7 desarrolla ambas.

La capa epistémica incluye además dos estructuras. Un **grafo de dependencias** une fuentes, afirmaciones, conceptos, ejemplos de entrenamiento y adaptadores con la semántica de un sistema de compilación: cuando una fuente cambia, se corrige o se olvida, todo lo que depende de ella queda marcado como obsoleto y se reconstruye en el siguiente ciclo. Y un **historial versionado**: como la wiki es Markdown, vive en un repositorio Git local con un commit por ciclo de consolidación, de modo que un `diff` entre dos fechas muestra cómo cambió lo que el modelo del usuario entiende y un `revert` deshace una consolidación equivocada.

### 5.3 Qué va a los pesos y qué no

La decisión más importante del plano local es el reparto entre memoria y parámetros, y la literatura de la sección 2.3 la resuelve. Como la recuperación supera al ajuste para incorporar conocimiento [13] y el ajuste sobre conocimiento nuevo aumenta la alucinación [14], **los hechos permanecen en la wiki y se sirven por recuperación**. A los pesos van los patrones que la recuperación no transmite bien porque no son enunciados sino maneras: la voz y el registro del usuario, su terminología preferida, sus procedimientos recurrentes y sus formatos. La elección de LoRA como mecanismo descansa en que aprende menos y olvida menos [18], el compromiso correcto para un adaptador entrenado con poco material sobre un modelo base que debe conservar su capacidad general. Si el usuario insiste en fijar un hecho en el modelo, la vía es el preentrenamiento continuo sintético [15], tratado como opción explícita y costosa.

Esta regla coincide con la que OPPU llegó por otro camino [5], y tiene una consecuencia de diseño que conviene subrayar: la wiki es el activo principal del usuario y el adaptador es una caché de comportamiento que se puede regenerar. Si mañana aparece un modelo base mejor, el usuario no pierde nada; se entrena un adaptador nuevo desde la misma wiki.

### 5.4 Datos de entrenamiento sin etiquetar

El aprendizaje es no supervisado en el sentido de que nadie etiqueta datos, y los ejemplos de entrenamiento provienen de tres fuentes de naturaleza distinta. La primera es el texto escrito por el propio usuario, y solo por él, para entrenar su voz; un documento de otro autor depositado en la carpeta enseñaría el estilo de ese autor. La segunda son pares pregunta-respuesta generados desde afirmaciones ancladas de la wiki, cada uno con su puntero a la fuente y aceptado solo si un verificador comprueba que la respuesta se deduce del fragmento citado. La tercera son las correcciones del usuario: cada edición de una página o reescritura de una respuesta produce un par "antes / después" utilizable para optimización directa de preferencias [19]. Es la única supervisión del sistema y no cuesta nada adicional.

### 5.5 Consolidación con repaso intercalado

El ciclo de consolidación se ejecuta cuando el dispositivo está ocioso, conectado a la corriente y con suficiente material nuevo elegible; no hay obligación de entrenar con ninguna periodicidad. Por la homología de la sección 3, cada lote de entrenamiento **mezcla ejemplos nuevos con una muestra de ejemplos ya consolidados y con texto general**, en una proporción que se registra. El modo de fallo que el repaso previene, la interferencia catastrófica [23], está documentado en el rango de tamaños de Swarmbly [26], y el aprendizaje continuo con repaso ha mostrado conservar tareas previas en modelos ajustados por instrucciones [27]. La predicción falsable es directa: un adaptador entrenado sin repaso debe degradarse en preguntas sobre material consolidado antes, y uno entrenado con repaso no (H-C10).

### 5.6 Selección de adaptadores como selección artificial

Un adaptador nuevo no reemplaza al anterior por existir. Se entrenan varios candidatos con distintas recetas y la compuerta de evaluación elige, lo que convierte cada ciclo en una generación de selección artificial. La genética cuantitativa da el instrumento [51]: la respuesta a la selección es el producto de la intensidad de selección, la exactitud del criterio y la variabilidad disponible. Elegir el mejor de 3 candidatos equivale a una intensidad de unas 0.85 desviaciones estándar, el mejor de 5 a 1.16 y el mejor de 10 a 1.54. La exactitud, la correlación entre la puntuación de la compuerta y la calidad real del adaptador, es la que manda: con exactitud 0.3 la ganancia esperada eligiendo el mejor de 5 es de unas 0.35 desviaciones estándar, y con 0.8 sube a unas 0.93. **Entrenar más candidatos rinde poco si la evaluación es ruidosa**, y el esfuerzo debe ir primero a la evaluación.

La compuerta tiene tres condiciones: el candidato mejora en preguntas derivadas de la wiki; no empeora más allá de un umbral en un benchmark general (los umbrales provisionales del SWIP, al menos 10 puntos de mejora y como máximo 2 de pérdida, son un punto de partida); y se abstiene ante preguntas sobre contenido que no está en la wiki. La tercera condición vigila el efecto de Gekhman et al. [14] y no puede omitirse. En conjunto, la compuerta funciona como un índice de selección restringido, que maximiza una característica sin permitir que otras caigan por debajo de un límite [51]; esa es la forma en que la mejora genética controla la respuesta correlacionada, el segundo modo de fallo de la homología.

El primer modo de fallo es el sobreajuste al criterio. Seleccionar siempre contra el mismo conjunto de prueba hace que la ganancia observada del ganador sobreestime la real, que es el problema del análisis adaptativo de datos [55]. La LCE tiene aquí una ventaja poco común: la wiki es una fuente prácticamente inagotable de preguntas nuevas, de modo que **cada generación se evalúa con un conjunto de prueba recién generado** desde afirmaciones ancladas que ningún candidato ha visto.

Hay una tercera regla, y conecta esta sección con el colapso de modelos. Lo que se hereda entre generaciones es la receta (los datos elegibles, su mezcla con repaso y los hiperparámetros ganadores), no los pesos: **cada adaptador se entrena desde el modelo base y la wiki, nunca desde el adaptador anterior ni con texto generado por él**. Así no hay recursión de un modelo sobre su propia salida, el olvido verificable de la sección 5.8 es la operación normal, y cambiar de modelo base cuesta lo mismo que una generación más. Es también la razón por la que la regularización tipo EWC [25], que exige el estado del adaptador anterior, no es el mecanismo por defecto.

### 5.7 Política de aprendizaje

El usuario decide qué aprende su modelo, y esa decisión se escribe. Cada fuente o carpeta declara en un archivo de política qué puede extraerse de ella: si el texto es de autoría del usuario, si puede entrenar estilo o procedimientos, si alimenta solo la wiki, si conserva memoria episódica. El valor por defecto es "solo referencia", de modo que el error más común, olvidar declarar una carpeta, produce un sistema que recuerda pero no aprende, en lugar de uno que aprende lo que no debía. El campo de autoría hace cumplir la regla de la sección 5.4, y como la política se registra en el grafo de dependencias, cambiarla marca como obsoletos los ejemplos que dependían de ella.

### 5.8 Olvido

Olvidar una fuente en la wiki es inmediato: se elimina, se marcan sus derivados y se reconstruyen las páginas afectadas. Olvidarla en un adaptador ya entrenado no lo es. Los benchmarks de desaprendizaje muestran que los métodos base no logran que un modelo se comporte como si nunca hubiera visto los datos [59], y que los algoritmos disponibles degradan la utilidad general y no soportan solicitudes sucesivas [60]. Por eso **el único olvido verificable en los pesos es regenerar el adaptador sin los ejemplos afectados**, que la sección 5.6 convierte en la operación normal. El historial Git añade un modo de fallo propio: un repositorio conserva en su historia lo que se borró del árbol actual, de modo que olvidar exige reescribir la historia afectada, y los respaldos deben respetarlo.

---

## 6. Integración con el protocolo Swarmbly

### 6.1 La personalización entra por Γ

El contrato global Γ del protocolo ya incluye los campos que una personalización necesita: audiencia, registro, léxico, entidades y una semilla de estilo [2]. La LCE no añade un paquete de personalización; produce, para cada petición, una **proyección de tarea**: la mínima información personal relevante para esa tarea, proyectada sobre esos campos. Si el usuario prefiere ciertos términos, van a `Γ.lexicon`; su registro va a `Γ.register`; sus nombres canónicos, a `Γ.entities`. Los workers reciben lo que la tarea necesita y nunca el estado cognitivo completo. La proyección compite con el resto del contexto por el presupuesto *S* del protocolo, y por eso debe ser una compresión relevante, no una biografía.

### 6.2 Doble clasificación de privacidad

La clasificación de sensibilidad del protocolo se ejecuta en local antes de que el contenido salga del dispositivo [1, sección 13.4]. La LCE introduce un riesgo nuevo: una pregunta inocua puede volverse identificable al añadirle memoria personal. Por eso la clasificación se ejecuta dos veces, antes y después de la proyección, y la segunda solo puede elevar el carril, nunca reducirlo.

### 6.3 Los workers sirven el modelo base

La regla de que un nodo que trabaja para otros sirve su modelo base sin adaptador (P13) no es solo prudente; la exige la verificación. La capa 1 del esquema de verificación del protocolo liga un compromiso sensible a la localidad sobre las activaciones al modelo, la entrada y la precisión declarados, y detecta la sustitución de modelo con exactitud total en las pruebas reportadas [1, sección 13.3]. Un worker con su adaptador personal cargado produce otras activaciones, de modo que es indistinguible de un nodo que sustituye su modelo: o falla la verificación, o publica el adaptador para que el compromiso se calcule contra él. La segunda salida es inaceptable, porque un adaptador entrenado con la voz y las correcciones de su usuario es información personal comprimida, y los modelos pueden devolver ejemplos de entrenamiento casi literales [57]; los adaptadores pequeños son menos vulnerables a la extracción que otras formas de ajuste, pero no inmunes [58]. La auditoría muestreada, que reejecuta tareas indistinguibles de las reales, sufre el mismo problema. Con la regla, las capas 1 y 2 de verificación quedan intactas y el adaptador nunca sale del dispositivo.

La regla tiene un segundo motivo, que la sección 2.6 anticipaba. Si muchos nodos de familias distintas entrenaran adaptadores con las mismas cápsulas sociales, sus errores se correlacionarían a través de ese material compartido, sumándose a la correlación entre familias que ya existe [36]. El costo de la regla es que el conocimiento personal de un worker no mejora el servicio que presta a terceros, y se acepta deliberadamente.

### 6.4 Respuesta plural

El consenso por alineamiento múltiple de E16 calcula, para cada unidad de la respuesta, el acuerdo entre réplicas de familias distintas, y devuelve un mapa de regiones de baja confianza [1, sección 10.5]. La LCE propone usar ese mapa no solo para advertir sino para mostrar: cuando las réplicas discrepan de forma sistemática en una unidad, el ensamblador puede presentar la posición mayoritaria y la alternativa, y la memoria local añade el contexto del usuario. Es una implementación del pluralismo de Overton, que pide presentar el abanico de respuestas razonables en lugar de converger a una sola [56], y es la forma concreta de la "democratización de la diversidad de respuestas" que motivó la propuesta.

Tiene dos modos de fallo. El primero es el falso equilibrio, presentar una posición marginal como si pesara lo mismo que la mayoritaria; la regla es mostrar la posición minoritaria solo cuando la sostienen al menos dos familias o evidencia anclada, y etiquetar siempre su proporción. El segundo es que el desacuerdo tampoco prueba controversia, porque puede reflejar el error de una sola familia, y que el acuerdo prueba todavía menos de lo que el protocolo suponía, a la vista de los errores correlacionados [36] y de la homogeneidad entre modelos [35]: un acuerdo de tres familias puede ser un error compartido. La respuesta plural es por tanto una presentación de la incertidumbre, sujeta a P6, y no una afirmación sobre el estado del debate en el mundo. Como complemento, en las tareas que admiten réplicas, una de ellas puede asignarse a un par de baja afinidad local, lo que contrarresta la cámara de eco con el mismo mecanismo que E12 usa para la diversidad de familia.

Hay, en cambio, una forma de diversidad que la LCE sí aporta y que conviene no confundir con la anterior. La mente colmena artificial [35] describe homogeneidad **entre usuarios**: personas distintas que preguntan lo mismo reciben respuestas casi iguales. La proyección de tarea inyecta en Γ el registro, el léxico y la semilla de estilo de cada usuario, de modo que dos peticiones idénticas en contenido llegan a los workers con contratos distintos y producen respuestas distintas. Eso combate la monocultura a escala de población [33, 37] sin tocar la correlación de errores dentro de una petición, porque todas las réplicas de una misma petición comparten el mismo Γ. La hipótesis H-C17 separa las dos cosas para poder medirlas por separado.

### 6.5 Aprender de los resultados propios, no del tráfico ajeno

Un worker ve fragmentos de peticiones ajenas, y eso no le da derecho a convertirlos en memoria. La regla por defecto es ejecutar, devolver y descartar. Lo que el cliente sí puede hacer es analizar los resultados de sus propias peticiones, una vez verificados y usados, en un resumen social local que extrae terminología, patrones de dominio o formas de explicación sin conservar necesariamente el fragmento. Cualquier retención de contenido ajeno exigiría un permiso explícito, y su valor por defecto es no retener: la LCE no puede convertir el voluntariado computacional en recolección involuntaria de datos.

### 6.6 Compatibilidad

La extensión respeta la regla de versionado del protocolo, según la cual un participante debe ignorar los campos desconocidos de un mensaje en lugar de rechazarlo [2]. El único añadido opcional al anuncio de perfil de nodo es un bloque pequeño de capacidades cognitivas, y los mensajes de cápsulas son nuevos y opcionales. Un nodo sin LCE no ve ninguna diferencia, y un nodo con LCE que encuentra uno sin ella se comporta exactamente como el protocolo v0.2.

### 6.7 Escalones de hardware

La extensión no exige hardware nuevo para participar. El escalón C0 es Swarmbly sin cambios; C1 añade la wiki y la recuperación, que corren en CPU con muy poca memoria; C2 añade la digestión automática con el mismo modelo local que el cliente ya usa; C3 añade la caché social y las cápsulas; y C4 añade el ajuste LoRA o QLoRA [17], que necesita la memoria de un equipo de consumo de gama media. Los requisitos concretos de memoria para cada tamaño de modelo que circulan en guías prácticas no proceden de literatura revisada y deben medirse en el prototipo. Un portátil modesto con C1 y una estación con C4 son ciudadanos completos del mismo protocolo.

---

## 7. El plano social

### 7.1 Conocimiento escrito, no pesos

El plano social es opcional y es el único que añade tráfico. Su unidad es la **cápsula cognitiva**: un objeto pequeño (a lo sumo 16 KiB), firmado, que contiene un enunciado de conocimiento generalizable con su anclaje, su procedencia y sus permisos separados de cacheo, redistribución y entrenamiento. Un nodo anuncia solo metadatos de los temas que puede servir; otro pide la cápsula cuando la necesita, la usa, y la conserva si le resultó útil. No hay difusión, no hay gossip, no hay grafo global.

Compartir conocimiento escrito en lugar de parámetros es la decisión más discutible del plano social, porque existe arte previo en la dirección contraria [6, 64]. Las razones son cuatro. Un adaptador es información personal comprimida y no se puede inspeccionar [57]; una cápsula se lee. Un adaptador solo sirve a nodos de la misma familia y versión de modelo [64], y la red es heterogénea por diseño. Entrenar con adaptadores ajenos correlaciona errores (sección 6.3). Y las cápsulas pesan kilobytes donde un adaptador pesa decenas o cientos de megabytes. El aprendizaje federado y el gossip learning [62, 63] se descartan por una razón más básica: convergen hacia un modelo común, que es lo contrario de una población diversa. La composición de adaptadores queda como optimización posterior para nodos de la misma familia, no como mecanismo base.

### 7.2 Persistencia inducida por tráfico

Si un nodo A posee una cápsula, B la pide y la cachea, C la pide y la cachea, y A desaparece, la cápsula sigue en B y en C. Cuanto más útil es un conocimiento, más copias aparecen sin ningún servicio de replicación. Es la respuesta barata a la pregunta original de qué pasa con el conocimiento de un nodo que cae, y tiene un sesgo estructural que la sección 7.6 corrige: favorece lo popular.

Para lo que un usuario decide preservar explícitamente, el número de réplicas no se elige a ojo sino que se deriva de una tolerancia, con la misma lógica de E17 [1]. Si la vida de un nodo es exponencial con media de 91 días [65], la probabilidad de que un nodo concreto abandone la red en una ventana de reparación semanal es q = 1 − e^(−7/91) ≈ 0.074. Si las copias perdidas se reponen cada semana, la probabilidad de perder las r copias en la misma ventana es qʳ, y para una tolerancia ε por ventana basta r ≥ ln(1/ε)/ln(1/q). Acumulada sobre un año, la probabilidad de perder una cápsula preservada es de aproximadamente 25 % con r = 2, 2.1 % con r = 3 y 0.16 % con r = 4. El cálculo supone salidas independientes, y la concentración de hosts en pocos usuarios que documenta el protocolo [1, sección 13.6] rompe ese supuesto, de modo que la colocación de copias debe exigir operadores distintos, igual que E12 exige familias distintas.

### 7.3 Acumular, nunca reemplazar

El colapso de modelos es el modo de fallo central de que "los modelos aprendan entre ellos" [28], y su primer síntoma, la pérdida de las colas [32], ataca justo los regionalismos y la terminología poco frecuente que una red diversa debería conservar. La corrección tiene respaldo empírico y formal: acumular datos sintéticos junto a los reales acota el error [29], y el reentrenamiento iterativo es estable si la proporción de datos limpios es suficientemente grande [31]. En la LCE eso se traduce en tres restricciones. El material derivado de otros nodos es siempre minoría en cualquier lote de entrenamiento, y el corpus propio del usuario nunca se descarta. Toda cápsula usada para entrenar debe poder rastrearse hasta un origen humano declarado. Y una cápsula derivada de otra cápsula sin evidencia humana nueva no se redistribuye ni se entrena. Conviene declarar lo que estos resultados no cubren: estudian la recursión de un mismo linaje de modelos sobre su propia salida, y la red de Swarmbly es un caso distinto, con muchos linajes de familias diferentes intercambiando material resumido. La transferencia es direccional y no cuantitativa, y el experimento social debe medir el colapso directamente.

### 7.4 Transmisión cultural y conformismo

La teoría de Cavalli-Sforza y Feldman distingue tres vías de transmisión con dinámicas distintas [39]: vertical (en la LCE, del usuario a su modelo), horizontal (entre nodos) y oblicua (de nodos establecidos, en particular los nodos ancla del arranque [1, sección 14.4], hacia nodos nuevos). La horizontal propaga más rápido y homogeneiza más, y la oblicua concentra el riesgo en el arranque, cuando todos los nodos nuevos reciben de las mismas pocas fuentes. El instrumento es la contabilidad: cada pieza de conocimiento local registra su vía, y la proporción horizontal y oblicua en el entrenamiento queda acotada.

El modo de fallo es el conformismo. Con dos variantes y un sesgo conformista de intensidad D, la frecuencia p de una variante cambia por generación según Δp = D·p(1−p)(2p−1) [40]: la mayoritaria crece y la minoritaria desaparece. Una variante regional sostenida por el 20 % de un vecindario cae por debajo del 1 % en unas 37 generaciones con D = 0.1, en 18 con D = 0.2 y en 12 con D = 0.3. El riesgo no es teórico: los LLM muestran conformismo medible, creciente con el tamaño de la mayoría [45], y las redes de agentes LLM convergen por sesgos propios del modelo [46]. La caché social guarda precisamente cuántos nodos repiten un patrón, y si ese recuento decidiera qué se adopta con una probabilidad que crece más que linealmente con él, la red implementaría conformismo sin haberlo decidido. Por eso el recuento **es una etiqueta de prevalencia y no un criterio de adopción** (P14): se muestra, alimenta la confianza en el patrón, y la adopción se decide por utilidad local observada. Henrich y Boyd añaden un matiz que juega en las dos direcciones: el conformismo reduce la variación dentro de los grupos pero aumenta la diferencia entre ellos [41], de modo que es un mecanismo plausible para que emerjan los vecindarios que buscaba la propuesta original y, a la vez, el que empobrece cada uno.

### 7.5 Vecindarios y presupuesto de migración

Los vecindarios no son clusters globales sino un efecto emergente de cachés de afinidad locales: un cliente que reutiliza ciertos pares para cierto dominio porque le resultaron útiles. La homología que da número a la diversidad entre vecindarios es el modelo de islas de Wright [47]: nodos como individuos, cápsulas como variantes, vecindarios como subpoblaciones, y compartir cápsulas entre vecindarios como migración. La relación de equilibrio F_ST ≈ 1/(1+4Nm) da números directos. Con Nm = 25, F_ST ≈ 0.01 y los vecindarios se vuelven indistinguibles; con Nm = 0.1, F_ST ≈ 0.71 y quedan aislados, de modo que la deriva elimina las variantes raras dentro de cada uno; la regla de "un migrante por generación" [49] corresponde a F_ST ≈ 0.2. De ahí sale una banda inicial para el presupuesto de migración, aproximadamente 0.5 ≤ Nm ≤ 2.25, es decir 0.1 ≤ F_ST ≤ 0.33, y un estadístico de diversidad que la red puede reportar (P15).

El modo de fallo de esta homología está tan documentado como el instrumento. La inversión de F_ST para estimar Nm descansa en supuestos (islas infinitas, migración simétrica, equilibrio, ausencia de selección) que casi nunca se cumplen, y la relación puede errar por órdenes de magnitud [48]. Aquí se violan al menos dos: las cápsulas no son neutras porque se seleccionan por utilidad, y la "generación" no está definida en una red de nodos persistentes, de modo que se fija operacionalmente como un ciclo de consolidación y la banda es sensible a esa elección. Por eso el instrumento se usa en una dirección: como punto de partida y como predicción cualitativa (Nm alto homogeneiza, Nm bajo aísla), que el experimento social confirmará o refutará.

### 7.6 Persistencia ponderada por rareza

La persistencia inducida por tráfico es selección dependiente de la frecuencia positiva, porque la probabilidad de que una cápsula tenga copias crece con el número de nodos que ya la usan, y ese régimen erosiona lo raro. La homología correctora es la selección dependiente de la frecuencia negativa, cuya propiedad establecida es mantener polimorfismos estables [50]. La aplicación es hacer más exigente la tolerancia para lo raro: una cápsula preservada cuyo número estimado de poseedores cae por debajo de un umbral recibe un ε menor y, por la relación de la sección 7.2, un r mayor. Pasar de ε = 10⁻³ a ε = 10⁻⁴ por semana eleva r de 3 a 4. El número de poseedores se estima desde los manifiestos, sin censo global. El modo de fallo es simétrico: la selección negativa también mantiene variantes sin valor, y una afirmación falsa poco difundida sería, por rareza, candidata a más copias. Por eso la ponderación se aplica solo a cápsulas preservadas por un usuario, ancladas a evidencia humana con distancia epistémica no mayor que 1 y bajo un presupuesto de réplica acotado por nodo. La rareza modula cuántas copias recibe lo que alguien decidió conservar; no decide qué se conserva.

### 7.7 Afinidad con control hebbiano

La caché de afinidad registra qué pares han sido útiles para qué dominios, y es la implementación práctica de los vecindarios. Su riesgo es el modo de fallo que la neurona hebbiana aporta: sin normalización, la afinidad crece sin cota y la selección de pares se concentra en los mismos, que es la cámara de eco [52]. La neurociencia corrigió ese crecimiento con normalización del vector de pesos [53] y con escalado homeostático [54], y la regla de diseño equivalente es que **la afinidad decae con el tiempo y se normaliza por dominio**, con una influencia acotada sobre el despacho y siempre subordinada a la diversidad de familia de E12. La afinidad se mantiene separada de la reputación del protocolo, que responde a si un worker ejecuta correctamente, y de la procedencia epistémica, que responde a qué soporte tiene una información.

### 7.8 Variación anclada

La propuesta original imaginaba que una cápsula entra a la red, cada vecindario la reinterpreta, y las versiones útiles se propagan mientras las demás se extinguen. La regla de la sección 7.3 prohíbe, por su parte, redistribuir derivados de derivados. Ambas cosas se reconcilian distinguiendo de dónde viene la variación. Una "mutación" producida porque un modelo reescribe una cápsula no aporta información nueva, solo ruido correlacionado con ese modelo, y su propagación es exactamente la recursión que causa el colapso. Una variante legítima incorpora **evidencia humana nueva**: un hablante que matiza el registro de una expresión, una fuente que corrige un procedimiento, una corrección de usuario. Una cápsula puede tener descendientes solo si cada descendiente declara esa evidencia; sin ella, la revisión es una reformulación que puede usarse en local pero no se redistribuye ni entrena. La selección la hace el uso y la herencia la hace el cacheo, como proponía la idea original, pero la variación tiene que venir de fuera del sistema de modelos, que es también la condición que la literatura de autoconsumo exige: datos reales nuevos en cada generación [30].

### 7.9 Distancia epistémica

Cada afirmación registra su distancia a una fuente humana, medida en **transformaciones y no en copias**: una cápsula cacheada por B y servida a C es la misma cápsula firmada por su origen y no aumenta la distancia. Distancia 0 es una fuente del propio usuario; distancia 1, una afirmación extraída por un modelo de una fuente humana anclada, propia o del nodo de origen de una cápsula; distancia 2 o más, todo lo derivado de material de distancia 1 sin evidencia humana nueva. La regla cabe en una línea: lo que tiene distancia mayor que 1 puede cachearse y recuperarse con su etiqueta, pero no se redistribuye ni entra al entrenamiento. Una variante anclada vuelve a distancia 1. Se descarta, en cambio, la mitad de la idea exploratoria que convertía la distancia en confianza transitiva entre nodos: la confianza transitiva es lo que un adversario Sybil explota creando cadenas de identidades que se avalan entre sí [61], y el protocolo no es resistente a Sybil en sentido fuerte [1, sección 13.6]. La distancia es un dato sobre el contenido, no una puntuación sobre los nodos.

---
## 8. Arquitectura completa e invariantes

### 8.1 Vista de los tres planos

La figura reúne las secciones 5 a 7. Todo lo que no estaba en la arquitectura de Swarmbly es local al dispositivo o es una regla sobre lo que ya circula, salvo las cápsulas, que son opcionales y bajo demanda. `SPEC_LCE_ES.md` desarrolla cada componente con sus esquemas.

```text
╔══════════════════════════════════════════════════════════════════════════════╗
║ PLANO LOCAL — dispositivo del usuario (Local Cognitive Extension)            ║
║                                                                              ║
║  Capa 0  Espacio de fuentes (inmutable) + política de aprendizaje      5.7   ║
║                         │ digestión: el modelo extrae, el código agrega      ║
║                         ▼                                                    ║
║  Capa 1  Wiki Markdown, aprende rápido ("hipocampo")               5.1–5.2   ║
║          afirmaciones ancladas · tipo · madurez · procedencia                ║
║          grafo de dependencias · historial Git · afirmaciones en disputa     ║
║            ┌────────────┴─────────────┐                                      ║
║            ▼                          ▼                                      ║
║   Recuperación (hechos,       Cola de entrenamiento: solo TRAINABLE,         ║
║   creencias atribuidas,       distancia ≤ 1, social minoritario        5.3   ║
║   episodios)                          │                                      ║
║            │                          ▼                                      ║
║            │        Capa 2  Adaptador LoRA, aprende despacio ("neocorteza")  ║
║            │                repaso intercalado · N candidatos desde base +   ║
║            │                wiki · compuerta con prueba nueva      5.5–5.6   ║
║            └────────────┬─────────────┘                                      ║
║                         ▼                                                    ║
║        Modelo personal = base + adaptador + memoria (solo para su usuario)   ║
║  Caché social (prevalencia ≠ adopción) · Afinidad (decae, normaliza)  7.4–7.7║
║  Almacén de cápsulas (copias por uso; r ponderado por rareza)         7.2,7.6║
╚═════════════════════════════════════╤════════════════════════════════════════╝
                                      │ petición del usuario
                                      ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║ PLANO DE INFERENCIA — Swarmbly sin cambios en el núcleo                      ║
║  recuperación → proyección de tarea → doble clasificación → router → DAG →   ║
║  Γ (register, lexicon, entities, style_seed) → candidatos (E12, afinidad     ║
║  acotada, 1 réplica de exploración) → workers con modelo base → triage →     ║
║  verificación capas 1–3 → consenso E16 → respuesta plural → ensamblaje →     ║
║  auditoría de coherencia → resumen social de los resultados propios  6.1–6.5 ║
╚═════════════════════════════════════╤════════════════════════════════════════╝
                                      │ opcional, con permiso, bajo demanda
                                      ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║ PLANO SOCIAL — cápsulas, la única fuente de tráfico nuevo                    ║
║  manifiesto → pull (≤ 16 KiB, firmada) → uso → beneficio observado → caché   ║
║  · descendientes solo con evidencia humana nueva                       7.8   ║
║  · distancia > 1: caché etiquetada; no redistribuye ni entrena         7.9   ║
║  · migración Nm ≈ 0.5–2.25 (F_ST ≈ 0.1–0.33) como punto de partida     7.5   ║
║  · r desde tolerancia ε, copias en operadores distintos                7.2   ║
║  · sin gossip, sin grafo global, sin confianza transitiva, sin adaptadores   ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### 8.2 Invariantes

Las invariantes se enumeran porque son las que cualquier implementación debe preservar y las que el SWIP convierte en requisitos normativos. Cada una tiene una hipótesis asociada y una condición de abandono en la sección 11.

- **I1.** Los hechos viven en la wiki; a los pesos van solo patrones de comportamiento (P17; secciones 5.2–5.3).
- **I2.** Un worker que sirve a terceros usa su modelo base sin adaptador y descarta el contenido de la tarea (P13; secciones 6.3 y 6.5).
- **I3.** Acumular, nunca reemplazar: el material social es minoritario, trazable a origen humano y con distancia epistémica no mayor que 1 para entrenar o redistribuir (P18; secciones 7.3 y 7.9).
- **I4.** La variación de las cápsulas viene de evidencia humana nueva, no de reformulaciones de modelos (P18; sección 7.8).
- **I5.** La prevalencia es una etiqueta, no un criterio de adopción (P14; sección 7.4).
- **I6.** Cada adaptador se entrena desde el modelo base y la wiki, con repaso intercalado y evaluación sobre pruebas nuevas (secciones 5.5–5.6).
- **I7.** La diversidad se presupuesta y se reporta: migración acotada, F_ST y masa en las colas (P15; secciones 7.5 y 11.3).
- **I8.** Lo que el usuario no declaró en su política de aprendizaje no entrena (P19; sección 5.7).

### 8.3 Un recorrido completo: "chuta"

Un ejemplo recorre la arquitectura entera y, multiplicado, se convierte en instrumento. Un usuario hablante de español ecuatoriano escribe en sus propios textos expresiones como "¡chuta, se cayó el servidor!". La política de aprendizaje marca esos textos como suyos, y el digestor extrae dos afirmaciones ancladas: una de tipo `style` (el usuario usa la interjección en registro informal, distancia 0) y una de tipo `fact` lingüístico (en el español de Ecuador, "chuta" es una interjección informal de sorpresa o contrariedad, distancia 1). La primera puede llegar al adaptador de voz cuando alcance el estado TRAINABLE; la segunda queda en la wiki y se sirve por recuperación. Cuando el usuario pide un texto en su registro, la proyección de tarea lleva el término a `Γ.lexicon` y el registro a `Γ.register`, y los workers, que sirven su modelo base, reciben solo eso.

Si el usuario lo permite, la afirmación lingüística se publica como cápsula horizontal anclada. Un segundo nodo, cuyo usuario escribe desde otro país y recibe un fragmento con "chuta" en una tarea propia, lo observa en su caché social. El recuento de nodos y familias que repiten el patrón queda como etiqueta de prevalencia, separada de la confianza factual y sin decidir la adopción. Si ese nodo necesita después el significado, pide la cápsula, la usa y la conserva solo si le fue útil. Lo que aprende es "en Ecuador se usa 'chuta' como…", nunca "soy ecuatoriano". Si el nodo de origen desaparece, la cápsula sobrevive en las copias inducidas por uso y, por rara y preservada, con un r mayor. Si un tercer hablante matiza su uso, su revisión entra como variante anclada; si un modelo solo la reformula, la reformulación queda local.

El ejemplo importa porque un regionalismo vive en las colas de la distribución, que el colapso de modelos [28, 32] y el conformismo [40] eliminan primero. Multiplicado, se convierte en el **conjunto canario** de la sección 11.3.

---

## 9. Economía e incentivo

### 9.1 Una razón egoísta para instalar el cliente

La computación voluntaria clásica pedía altruismo. Un cliente que mantiene un modelo propio que aprende de su usuario es, en cambio, una razón egoísta para instalar el software, y el cómputo ocioso que el nodo aporta a la red pasa a ser un efecto secundario de algo que el usuario ya quería. Es, con probabilidad, el argumento estratégico más fuerte de la extensión frente a L10 [1, sección 16].

El argumento tiene su modo de fallo y se presenta con él. Si la LCE es útil sin que el nodo sirva a la red, el usuario racional instala el cliente por la LCE y desactiva el modo worker: el incentivo egoísta atrae usuarios, pero no capacidad. La regla de servir el modelo base no lo resuelve, porque dice qué se sirve y no si se sirve. Hay dos diseños posibles y ambos tienen costo. Ligar ciertas funciones sociales de la LCE, como la recuperación de cápsulas, a la contribución del nodo reintroduce una contabilidad de créditos que el protocolo trata con cautela [1, sección 14.1]. Dejar la contribución activada por defecto y medir cuántos usuarios la mantienen no garantiza nada, pero mide la cuestión. Este documento no elige: la plantea como hipótesis (H-C9) y deja L10 abierta en el protocolo, ahora con un mecanismo candidato y una métrica que puede refutarlo.

### 9.2 Costos

Los costos de la extensión están muy desequilibrados, y conviene hacerlo explícito porque determinan quién puede participar. Lo barato es casi todo: mantener la wiki, el índice, los embeddings, el grafo de dependencias, la caché social y la afinidad, que corren en CPU y ocupan del orden de megabytes a pocos gigabytes. El costo intermedio es la digestión, que usa el mismo modelo local que el cliente ya carga para orquestar. Lo caro es entrenar, y por eso el diseño lo hace opcional, infrecuente, condicionado al ocio del equipo y regenerable. El costo de red por defecto es cero; con cápsulas, es del orden de kilobytes por solicitud útil, frente a los cientos de megabytes de un adaptador. La sección 11 incluye una contabilidad del **costo cognitivo**: el tiempo, la energía y el tráfico que la extensión añade, que debe reportarse junto a sus beneficios con la misma disciplina con que el protocolo reporta su impuesto de coherencia (P6).

### 9.3 La extensión dentro del modelo de gobernanza

La LCE hereda la licencia y la gobernanza del protocolo: código bajo AGPL-3.0-or-later, textos bajo CC BY 4.0, y cambios al protocolo por SWIP [1, sección 14.2]. Lo que es puramente local (la wiki, el adaptador, la política, la afinidad) no requiere SWIP porque no afecta la interoperabilidad; lo que toca el anuncio de nodo o añade mensajes (el bloque de capacidades y las cápsulas) sí. El borrador del SWIP propone separar ambas cosas en dos propuestas si la discusión lo aconseja.

---

## 10. Privacidad, seguridad y modelo adversario

La extensión mantiene el modelo de confianza del protocolo y añade superficies nuevas, que se enumeran con su mitigación y con lo que la mitigación no cubre.

**Fuga por memoria.** La memoria personal puede volver identificable una petición que no lo era. La doble clasificación (sección 6.2) eleva el carril cuando ocurre, pero depende de un clasificador local que puede fallar; su tasa de error es un objeto de medida (experimento C3), no un supuesto.

**Fuga por adaptador.** Un adaptador personal puede devolver fragmentos de sus datos [57, 58]. La mitigación es estructural: el adaptador nunca sale del dispositivo ni se sirve a terceros (I2). Lo que no cubre es el robo del dispositivo, que queda fuera del alcance del protocolo como en cualquier software local.

**Fuga por identidad.** El bloque de capacidades cognitivas del anuncio de nodo podría revelar rasgos del usuario si fuera detallado. Por eso es grueso (dominios amplios, idiomas, disponibilidad de cápsulas) y opcional, y nunca contiene identidad, ubicación ni perfil de preferencias.

**Envenenamiento social.** Un nodo malicioso puede publicar cápsulas falsas o sesgadas. Las mitigaciones son la adopción por utilidad observada (no por popularidad), la separación entre confianza en el patrón y confianza factual, el límite de distancia epistémica, la minoría del material social en el entrenamiento, y la firma, que prueba quién firmó pero no que el contenido sea verdadero. Lo que no cubren es un adversario Sybil que fabrique muchos nodos que pidan y cacheen la misma cápsula falsa para inflar su persistencia; la ponderación por rareza no lo agrava, porque solo aplica a cápsulas preservadas por un usuario y ancladas, pero la persistencia por tráfico sí es manipulable, y el experimento C7 debe medirlo.

**Inyección de instrucciones.** Una cápsula o un fragmento devuelto es dato, nunca instrucción, igual que en el ensamblador del protocolo [1, sección 13.3]. La digestión de cápsulas ajenas corre con las mismas defensas de manejo de salida y con esquemas de contenido por tipo.

**Historial y respaldos.** El historial Git y los respaldos conservan lo que el usuario borró. El olvido debe reescribir la historia afectada y propagarse a los respaldos (sección 5.8).

**Análisis de tráfico.** Las solicitudes de cápsulas revelan interés en un tema. Se mitiga pidiendo por temas amplios a partir de manifiestos y cacheando, pero no se elimina, y queda declarada como canal residual.

---

## 11. Evaluación: hipótesis, experimentos y criterio de abandono

### 11.1 Hipótesis

Las hipótesis se numeran como en los borradores para conservar la trazabilidad. Cada una lleva la condición que la refuta.

- **H-C1 — Memoria local.** La recuperación sobre la wiki mejora tareas personalizadas frente al mismo modelo sin memoria. Muere si no mejora en el benchmark local ni en un benchmark externo de personalización [4].
- **H-C2 — Proyección de tarea.** Una proyección pequeña en Γ preserva las preferencias del usuario mejor que enviar solo el prompt, sin aumentar significativamente la tasa de redundancia ρ. Muere si el aumento de ρ supera la ganancia.
- **H-C3 — Afinidad.** La afinidad local mejora la relación calidad / costo del despacho frente a la selección sin afinidad. Muere si no mejora de forma medible.
- **H-C4 — Utilidad de las cápsulas.** Las cápsulas bajo demanda reducen solicitudes repetidas más de lo que cuesta transmitirlas. Muere si su tráfico y complejidad superan el ahorro, incluso en un benchmark diseñado para favorecer la reutilización.
- **H-C5 — Persistencia por tráfico.** Las cápsulas útiles sobreviven al recambio de nodos por caché inducida por uso, sin replicación global. Muere si la supervivencia observada queda por debajo de la predicha por el modelo de la sección 7.2.
- **H-C6 — Recuperación antes que entrenamiento.** La recuperación captura la mayor parte del beneficio; el ajuste añade beneficio solo en patrones de comportamiento estables. Muere si el ajuste no supera claramente a la recuperación sola en comportamiento.
- **H-C7 — Acumulación.** Con material social minoritario, trazable a origen humano y sin re-compartir derivados, la masa en las colas no disminuye a lo largo de los ciclos de intercambio. Muere si las colas se contraen de forma sostenida bajo las tres restricciones.
- **H-C8 — Banda de migración.** La utilidad sobre contenido poco frecuente es máxima en una banda intermedia de Nm y cae con Nm alto y con Nm bajo. Muere si es monótona en Nm, en cuyo caso el instrumento de Wright pasa a vocabulario.
- **H-C9 — Incentivo.** Entre los usuarios que adoptan la LCE, una fracción suficiente mantiene activo el modo worker a 30 y 90 días como para aumentar la capacidad neta. Muere si la LCE aumenta las instalaciones sin aumentar la capacidad servida.
- **H-C10 — Repaso intercalado.** Un adaptador entrenado sin repaso pierde rendimiento en preguntas sobre material consolidado antes, y uno con repaso no. Muere si no hay diferencia, y la homología CLS pasa a vocabulario.
- **H-C11 — Conformismo.** Con la prevalencia como etiqueta y la adopción por utilidad, la frecuencia de variantes minoritarias del conjunto canario se mantiene estable dentro de cada vecindario; sin la regla, sigue la dinámica conformista. Muere si no hay diferencia entre condiciones.
- **H-C12 — Variación anclada.** Permitir solo descendientes con evidencia humana nueva conserva la diversidad del conjunto canario, y permitir reformulaciones la reduce. Muere si ambas condiciones la conservan por igual.
- **H-C13 — Rareza.** La ponderación por rareza reduce la pérdida de cápsulas raras preservadas con un costo de réplica acotado. Muere si la reducción no compensa el tráfico o si replica preferentemente material de baja calidad.
- **H-C14 — Respuesta plural.** Mostrar la posición alternativa cuando las réplicas discrepan sistemáticamente mejora la calibración percibida sin aumentar la confianza en posiciones marginales. Muere si los usuarios no la distinguen de una respuesta única o si aumenta la adopción de posiciones con soporte débil.
- **H-C15 — Selección de adaptadores.** Con pruebas nuevas por generación, la ganancia del seleccionado en una prueba final independiente coincide con la predicha por la intensidad y la exactitud estimada; con prueba reutilizada, se sobreestima. Muere si la reutilización no produce sobreestimación medible.
- **H-C16 — Correlación por material compartido.** Si los workers sirvieran adaptadores entrenados con cápsulas comunes, la correlación de errores entre réplicas de familias distintas aumentaría con el solapamiento de esas cápsulas. Es la predicción que justifica I2; muere si no se observa aumento, en cuyo caso I2 descansa solo en la verificación y la privacidad.
- **H-C17 — Diversidad entre usuarios.** La proyección de tarea reduce la homogeneidad entre las respuestas que reciben usuarios distintos para la misma consulta abierta, medida al modo de Infinity-Chat [35], sin cambiar la correlación de errores fácticos entre réplicas de una misma petición. Muere si la homogeneidad entre usuarios no disminuye; y si la correlación de errores también cambiara, el análisis de las secciones 2.6 y 6.4 estaría equivocado y debería revisarse.

### 11.2 Experimentos

Los experimentos C0 a C8 vienen del borrador del SWIP; C9 a C12 son nuevos. Ninguno debe correrse con `MockBackend` como evidencia: el backend simulado valida el instrumento de medida y sus resultados se reportan por separado, como en el protocolo.

- **C0 — Línea base.** Swarmbly sin LCE sobre el mismo conjunto de tareas.
- **C1 — Memoria local.** Wiki con recuperación frente a C0 (H-C1).
- **C2 — Proyección de tarea.** Con y sin proyección en Γ, midiendo preferencia y ρ (H-C2); y, sobre un conjunto de consultas abiertas pedidas por perfiles de usuario distintos, la homogeneidad entre usuarios y la correlación de errores fácticos entre réplicas (H-C17).
- **C3 — Reclasificación de privacidad.** Tasa de peticiones cuyo carril sube tras la proyección y tasa de errores del clasificador.
- **C4 — Afinidad.** Despacho con y sin afinidad, con la cuota de exploración (H-C3).
- **C5 — Utilidad de cápsulas.** Solicitudes evitadas frente a bytes transmitidos (H-C4).
- **C6 — Persistencia.** Supervivencia de cápsulas bajo recambio simulado con vida media de 91 días, con y sin ponderación por rareza (H-C5, H-C13).
- **C7 — Envenenamiento social.** Cápsulas falsas inyectadas por una fracción de nodos, incluido un adversario que infla la persistencia con identidades múltiples.
- **C8 — Recuperación frente a ajuste.** Wiki con recuperación frente a wiki con recuperación y adaptador, sobre tareas de hecho y de comportamiento (H-C6).
- **C9 — Simulación social.** N nodos con corpus distintos intercambian cápsulas bajo varios niveles de Nm; se mide F_ST, utilidad sobre contenido raro, masa en las colas sobre el conjunto canario, frecuencia de variantes minoritarias con y sin regla de prevalencia, diversidad con y sin variación anclada, y correlación de errores entre réplicas (H-C7, H-C8, H-C11, H-C12, H-C16). El marco de simulación de poblaciones de LLM de Perez et al. [43] es un candidato a arnés.
- **C10 — Aprendizaje local.** Adaptador de voz frente a recuperación sola: si el usuario distingue a ciegas su propio texto del generado, si aumenta la alucinación fuera de la wiki, si el repaso evita el olvido, y si la ganancia del adaptador seleccionado se sobreestima con prueba reutilizada (H-C10, H-C15).
- **C11 — Respuesta plural.** Estudio con usuarios sobre calibración percibida y adopción de posiciones con soporte débil (H-C14).
- **C12 — Cohorte de piloto.** Retención del modo worker a 30 y 90 días entre usuarios con y sin LCE (H-C9).

### 11.3 El conjunto canario

El instrumento transversal de los experimentos sociales es un **conjunto canario**: una lista de algunas decenas a pocos cientos de regionalismos por variante de una lengua, con glosas aportadas y verificadas por hablantes nativos, usada exclusivamente para medir y nunca para entrenar. Sobre él se miden tres cosas a lo largo de los ciclos: la fracción de ítems que los nodos glosan correctamente (masa en las colas), la frecuencia de cada variante dentro de cada vecindario (para detectar la curva conformista) y la tasa de violaciones de identidad, es decir, respuestas en primera persona que atribuyen al modelo una pertenencia que solo observó. Es barato, interpretable por cualquier lector y sensible justo a los fallos que esta extensión puede provocar. Su limitación es que mide colas léxicas y no conceptuales, y debe complementarse con métricas de dispersión semántica.

### 11.4 Costo cognitivo

Cada experimento reporta, junto a su beneficio, el costo que la extensión añade: latencia local de recuperación y proyección, energía de digestión y entrenamiento, almacenamiento, tráfico de cápsulas y bytes añadidos a Γ. Un beneficio sin su costo no es un resultado.

### 11.5 Criterio de abandono

La extensión, o una de sus piezas, permanece fuera del protocolo si se cumple cualquiera de estas condiciones, enunciadas antes de medir. La afinidad se abandona si no mejora el despacho de forma medible. Las cápsulas se abandonan si su tráfico y complejidad superan el ahorro, y en ese caso Swarmbly se queda solo con la capa local. El aprendizaje social se abandona si contrae las colas aun bajo las restricciones de acumulación. El ajuste fino de comportamiento se abandona si no supera claramente a la recuperación; el de hechos se abandona sin experimento adicional, porque la evidencia [13, 14] ya basta. El bloque de capacidades se abandona si su fuga de información supera su utilidad. La respuesta plural se abandona si aumenta la adopción de posiciones con soporte débil, aunque mejore la satisfacción. Y la extensión entera queda fuera si requiere entrenamiento continuo en GPU, estado global sincronizado, gossip intenso, intercambio de adaptadores grandes, servicios centrales de conocimiento o revelación obligatoria de identidad, porque eso contradice la lógica que permite a Swarmbly democratizar la inferencia sobre hardware de consumo.

### 11.6 El arnés y la prueba de los instrumentos

El método del whitepaper v2 se aplica también a las medidas: un instrumento se prueba antes de usarlo para decidir nada. El arnés `lce_validation/` contiene seis pruebas de instrumento, cada una una simulación con una predicción enunciada de antemano y un criterio de aprobación, y `run_all` termina con error si alguna falla. La prueba **de anclaje** fabrica afirmaciones de tres maneras (palabras de contenido inventadas sobre un fragmento real, una afirmación real apuntada al fragmento equivocado, y una huella de archivo obsoleta) y exige que el verificador acepte al menos el 95 % de las afirmaciones soportadas y como mucho el 5 % de las fabricadas. La prueba **de conformismo** simula demes de agentes que adoptan una variante minoritaria del 20 % por la regla conformista o por la lineal, y exige que la primera la pierda y la segunda conserve su media, y que la guarda de I5 marque como no conforme una regla de umbral. La prueba **de migración** simula el modelo de islas de Wright–Fisher y exige que el F_ST simulado decrezca con Nm y siga 1/(1+4Nm) dentro de un factor 2 en la banda de la sección 7.5. La prueba **de persistencia** simula el recambio de nodos con vida media de 91 días y reparación semanal, y exige que la pérdida anual simulada coincida con qʳ y que la colocación en un mismo operador sea mucho peor. La prueba **de sesgo de selección** exige que la ganancia realizada siga i·r·σ, que la estimación sobre el conjunto de selección esté inflada y que la de un conjunto nuevo no lo esté. La prueba **de colapso** autoentrena una distribución categórica de cola larga y exige que reemplazar erosione la cola, que acumular la acote y que la variación anclada la preserve.

Las seis pasan en la versión publicada, y la prueba es robusta a la semilla. Junto a ellas, los experimentos C1, C2 y C10 recorren el código real (digestión, anclaje, wiki, proyección sobre Γ, compuerta) con `MockBackend`, un backend de reglas que inyecta los efectos que se quieren detectar, entre ellos errores compartidos entre familias. Con él la proyección reduce la homogeneidad entre usuarios y deja intacta la concordancia de errores entre familias, que es la predicción de H-C17, pero lo hace por construcción, y por eso se reporta como validación de la tubería y nunca como resultado. El script `run_real` repite C1 y C2 contra modelos reales servidos por Ollama o cualquier servidor compatible con OpenAI, se niega a correr si algún modelo no responde o si todos pertenecen a la misma familia, y etiqueta su salida como real. Su alcance debe declararse con cualquier cifra: un corpus sintético de un usuario, tres usuarios proyectados, diez preguntas fácticas y un conjunto canario todavía sin verificar.

---

## 12. Limitaciones

Enunciadas llanamente, como en el protocolo. Una propuesta cuyos modos de fallo están documentados puede ser mejorada por quien no la escribió.

**LC1 — Nada está medido.** Este documento es una arquitectura con hipótesis. Los números que contiene son cálculos sobre parámetros publicados o hallazgos de otros, y ninguno es un resultado de la LCE.

**LC2 — El modelo personal no aprende hechos.** Es una decisión respaldada por la evidencia [13, 14], pero tiene un costo de experiencia: el usuario que espera que "su modelo sepa" algo tendrá que entender que lo sabe su wiki.

**LC3 — La diversidad de familias es más débil de lo que el protocolo suponía, y el aprendizaje local no la repara.** Los errores correlacionados entre familias [36] y la homogeneidad entre modelos [35] reducen lo que E12, E16 y la respuesta plural pueden prometer; un acuerdo entre familias puede ser un error compartido. La LCE evita agravar el problema (I2) pero no lo corrige: el aprendizaje local diversifica la expresión y reduce la homogeneidad entre usuarios, no la correlación de errores dentro de una petición, porque esa correlación procede del preentrenamiento compartido y el adaptador no toca los hechos (secciones 2.6 y 6.4). La palanca candidata, la diversidad de evidencia entre réplicas, es una hipótesis del protocolo, no de la LCE.

**LC4 — Las homologías poblacionales transfieren con salvedades.** El modelo de Wright supone neutralidad, equilibrio e islas infinitas [48], y la "generación" debe definirse operacionalmente. Los números de la sección 7.5 son puntos de partida.

**LC5 — Los resultados sobre colapso no cubren el caso de Swarmbly.** Estudian un linaje que se reentrena con su propia salida [28, 29, 31]; una red de muchas familias intercambiando resúmenes es un caso distinto, y la transferencia es direccional.

**LC6 — El olvido en los pesos solo es verificable regenerando.** Los métodos de desaprendizaje no son fiables [59, 60]; la regeneración cuesta un ciclo de entrenamiento por solicitud de olvido que afecte al adaptador.

**LC7 — La persistencia por tráfico es manipulable.** Un adversario con muchas identidades puede inflar la persistencia de una cápsula pidiéndola y cacheándola. El protocolo no es resistente a Sybil en sentido fuerte [1, sección 13.6] y la LCE tampoco.

**LC8 — El cálculo de réplicas supone salidas independientes.** La concentración de hosts en pocos operadores lo rompe; exigir operadores distintos lo atenúa sin garantizarlo.

**LC9 — El incentivo puede atraer usuarios sin capacidad.** El mecanismo de la sección 9.1 tiene su propio modo de fallo, el polizón, y no está resuelto.

**LC10 — La capa epistémica depende de verificadores que fallan.** La verificación de anclajes, la clasificación de tipos y la de privacidad usan modelos, y los modelos no citan ni clasifican de forma fiable [20, 21]. El diseño mide sus tasas de error; no las elimina.

**LC11 — El conjunto canario mide colas léxicas.** Las colas conceptuales (formas de razonar, supuestos culturales) requieren métricas que este documento no especifica.

**LC12 — La homogeneización del propio usuario.** Escribir con un modelo reduce la diversidad entre autores [33]. Un modelo que aprende la voz de su usuario y la devuelve podría, con el tiempo, estrechar esa misma voz. No hay mitigación diseñada más allá de que la voz se entrena solo con texto escrito por el usuario, que a su vez puede estar ya escrito con ayuda del modelo.

---
## 13. Elementos a declarar como arte previo

> **Nota sobre el estado.** Los elementos EC1–EC11 **no constituyen todavía arte
> previo**: lo serán con la publicación de este documento en un registro con
> fecha (Zenodo o el repositorio público), no antes. La decisión sobre cuándo
> publicar está abierta y depende de la misma consideración que el protocolo
> registró en `publication/PRIOR_ART.md` sobre periodos de gracia.

Los elementos se divulgarán con la intención de que entren al dominio público a efectos de patentabilidad; el autor reserva el copyright del texto bajo CC BY 4.0 y licencia cualquier implementación bajo AGPL-3.0-or-later.

**EC1.** En un sistema de inferencia distribuida que despacha microtareas con un contrato global compartido, la **personalización por proyección**: el cliente recupera de una memoria local solo la información relevante para la tarea y la proyecta sobre campos ya existentes del contrato (registro, léxico, entidades, semilla de estilo), con una segunda clasificación de sensibilidad posterior a la proyección que solo puede elevar el carril. (Secciones 6.1–6.2)

**EC2.** La regla por la cual un nodo que ejecuta tareas para terceros **sirve su modelo base sin adaptador personal** y descarta el contenido, como condición simultánea de compatibilidad con la verificación por compromiso sobre activaciones, de privacidad del adaptador y de no correlación de errores por material compartido. (Sección 6.3)

**EC3.** Una **capa epistémica local** en la que cada afirmación de una memoria escrita por un modelo está anclada al fragmento de su fuente, tipada (hecho, afirmación del usuario, creencia, hipótesis, experiencia, preferencia, estilo, procedimiento) y con estado de madurez, donde solo los tipos de comportamiento en estado entrenable alimentan un adaptador, con un grafo de dependencias que invalida en cascada y con la regeneración del adaptador como mecanismo de olvido. (Secciones 5.2, 5.3 y 5.8)

**EC4.** **Cápsulas cognitivas** pequeñas, firmadas, de solicitud bajo demanda y sin difusión, con permisos separados de cacheo, redistribución y entrenamiento, cuya persistencia en la red surge de las copias inducidas por su uso. (Secciones 7.1–7.2)

**EC5.** Un **número de réplicas derivado de una tolerancia** a partir de la tasa de abandono de nodos, r ≥ ln(1/ε)/ln(1/q), con una tolerancia más estricta para las cápsulas raras y preservadas y con colocación de copias en operadores distintos. (Secciones 7.2 y 7.6)

**EC6.** La **variación anclada**: una unidad de conocimiento compartido puede tener descendientes solo si cada uno declara evidencia humana nueva, junto con una distancia epistémica medida en transformaciones y no en copias, que limita la redistribución y el entrenamiento a distancia no mayor que 1. (Secciones 7.8–7.9)

**EC7.** La regla de **prevalencia como etiqueta**: en un sistema que observa cuántos pares repiten un patrón, la probabilidad de adoptarlo, consolidarlo o entrenarlo no crece más que linealmente con ese recuento, junto con la contabilidad de la vía de llegada (vertical, horizontal, oblicua) de cada pieza de conocimiento. (Sección 7.4)

**EC8.** Un **presupuesto de migración** entre vecindarios emergentes de una red de modelos, expresado como banda de Nm y reportado como estadístico F_ST. (Sección 7.5)

**EC9.** La **selección de adaptadores por generaciones** con un conjunto de prueba recién generado desde una memoria anclada en cada generación, herencia de la receta y no de los pesos (cada adaptador se entrena desde el modelo base), y una compuerta de índice restringido que exige abstención fuera de la memoria. (Sección 5.6)

**EC10.** Una **respuesta plural** construida a partir del mapa de acuerdo por unidad de un consenso entre réplicas de familias distintas, que presenta la posición alternativa solo con soporte mínimo y siempre etiquetada con su proporción. (Sección 6.4)

**EC11.** Un **conjunto canario** de regionalismos verificados por hablantes nativos, usado exclusivamente para medir masa en las colas, dinámica conformista y violaciones de identidad en una red de modelos que intercambian conocimiento. (Sección 11.3)

---

## 14. Hoja de ruta

La hoja de ruta sigue el principio del protocolo de no afirmar antes de medir, y cada etapa termina en un veredicto. La etapa 0 fija el arnés: especificación, conjunto de tareas, conjunto canario inicial y contabilidad del costo cognitivo, todo antes de implementar ningún componente. El primer prototipo es estrictamente local y sin red: wiki con anclaje, capa epistémica, recuperación y proyección de tarea sobre Γ, evaluado con C0 a C3. El segundo prototipo añade el adaptador con repaso y la selección por generaciones, evaluado con C8 y C10; si el ajuste no supera a la recuperación, la capa 2 se retira y la LCE queda como memoria más proyección. El tercer prototipo es una simulación social sin despliegue, con nodos simulados sobre backends reales, evaluada con C4 a C7 y C9; si las cápsulas no pagan su costo, el plano social se retira. Solo después de esos veredictos se abre la discusión del SWIP en el repositorio del protocolo, separando si conviene la parte local y la de cápsulas en dos propuestas. La respuesta plural (C11) y la cohorte de piloto (C12) requieren usuarios reales y van al final.

Con esta versión, la etapa 0 y el código de los dos primeros prototipos están implementados y probados (sección 11.6), con un entrenador LoRA real para Apple Silicon como componente experimental. Lo que separa la versión 0.1 de un primer veredicto no es código sino corridas: C1, C2 y C8 con modelos reales, y la verificación del conjunto canario por hablantes nativos.

---

## 15. Conclusión

La propuesta de la que nació este documento era ambiciosa: que cada usuario tuviera un mini cerebro propio capaz de aprender de él, que esos cerebros aprendieran entre sí, y que la red resultante fuera un organismo diverso cuyo conocimiento sobreviviera a la pérdida de sus partes. La versión que sobrevive al método del whitepaper v2 es más modesta en su forma y, sospecho, más sólida en su fondo.

El cerebro personal vive en el cliente, donde Swarmbly ya concentra el estado, y está hecho sobre todo de texto: una wiki legible, anclada, tipada y versionada, de la que un adaptador ligero aprende solo la manera de hablar y de trabajar del usuario, nunca sus hechos. La red no se convierte en otra red: la personalización entra por un contrato que el protocolo ya tiene, los workers siguen sirviendo su modelo base, y la verificación queda intacta. El aprendizaje entre nodos existe, pero como intercambio opcional de conocimiento escrito, cuya variación tiene que venir de personas reales, cuya adopción depende de la utilidad y no de la popularidad, y cuya memoria se conserva por uso y se protege cuando es rara.

Lo que la revisión bibliográfica añade a esa forma es un catálogo de modos de fallo con nombre: la interferencia catastrófica, el colapso de modelos, el conformismo, la sobreestimación por reutilización de pruebas, la confianza transitiva, el desaprendizaje que no desaprende y, sobre todo, la correlación de errores entre modelos que el protocolo suponía independientes. Ninguno queda resuelto por declararlo. Todos quedan, en cambio, con una regla que los evita o con un experimento que los mide.

"Organismo" encuentra así su lectura exacta: una población con memoria cultural. Individuos con dueño, que aprenden verticalmente de sus usuarios y horizontalmente entre sí, cuya diversidad se presupuesta y se reporta, y que saben mostrar sus desacuerdos en lugar de esconderlos. Si la extensión funciona, cada nodo de Swarmbly será gradualmente más útil para su dueño **sin dejar de ser barato, autónomo y reemplazable**, y el protocolo habrá pasado de democratizar el acceso al procesamiento a democratizar también el control sobre la memoria. Si no funciona, la sección 11 dice exactamente qué piezas retirar.

---

## 16. Referencias

> **Numeración.** Los marcadores [1]–[65] corresponden a `REFERENCES_LCE.md`,
> donde cada entrada lleva su anotación de uso y su marca de verificación. Las
> entradas marcadas allí con `[STD]` se citan según su registro bibliográfico
> estándar y las marcadas ⚠️ tienen un campo sin confirmar; ambas deben cotejarse
> antes de publicar. Las demás se verificaron contra la fuente en línea entre el
> 3 y el 4 de octubre de 2026.

### Swarmbly

[1] Espinoza-Ulloa, S. A. (2026). *Fragmentación semántica y ensamblaje estocástico, versión 2: Un protocolo de inferencia descentralizada de modelos de lenguaje sobre nodos voluntarios no confiables* (Whitepaper v2). Zenodo. https://doi.org/10.5281/zenodo.23031305

[2] Espinoza-Ulloa, S. A. (2026). *Swarmbly AI* (Versión 2.0.0; especificación del protocolo v0.2 e implementación de referencia) [Software]. Zenodo. https://doi.org/10.5281/zenodo.21956743

### Personalización y memoria de agentes

[3] Zhang, Z., Rossi, R. A., Kveton, B., Shao, Y., et al. (2025). Personalization of large language models: A survey. *Transactions on Machine Learning Research*. https://arxiv.org/abs/2411.00027

[4] Salemi, A., Mysore, S., Bendersky, M., & Zamani, H. (2024). LaMP: When large language models meet personalization. En *Proceedings of the 62nd Annual Meeting of the ACL* (pp. 7370–7392). https://doi.org/10.18653/v1/2024.acl-long.399

[5] Tan, Z., Zeng, Q., Tian, Y., Liu, Z., Yin, B., & Jiang, M. (2024). Democratizing large language models via personalized parameter-efficient fine-tuning. En *Proceedings of EMNLP 2024* (pp. 6476–6491). https://doi.org/10.18653/v1/2024.emnlp-main.372

[6] Tan, Z., Liu, Z., & Jiang, M. (2024). Personalized pieces: Efficient personalized large language models through collaborative efforts. En *Proceedings of EMNLP 2024* (pp. 6459–6475). https://doi.org/10.18653/v1/2024.emnlp-main.371

[7] Karpathy, A. (2026, 4 de abril). *llm-wiki.md* [GitHub Gist]. https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

[8] Park, J. S., O'Brien, J. C., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023). Generative agents: Interactive simulacra of human behavior. En *Proceedings of UIST 2023*. https://doi.org/10.1145/3586183.3606763

[9] Packer, C., Wooders, S., Lin, K., Fang, V., Patil, S. G., Stoica, I., & Gonzalez, J. E. (2023). MemGPT: Towards LLMs as operating systems. *arXiv*. https://arxiv.org/abs/2310.08560

[10] Xu, W., Liang, Z., Mei, K., Gao, H., Tan, J., & Zhang, Y. (2025). A-MEM: Agentic memory for LLM agents. En *Advances in Neural Information Processing Systems 38 (NeurIPS 2025)*. https://arxiv.org/abs/2502.12110

[11] Kleppmann, M., Wiggins, A., van Hardenberg, P., & McGranaghan, M. (2019). Local-first software: You own your data, in spite of the cloud. En *Proceedings of Onward! 2019* (pp. 154–178). ACM. https://doi.org/10.1145/3359591.3359737

### Inyección de conocimiento, PEFT y atribución

[12] Lewis, P., Perez, E., Piktus, A., et al. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks. En *Advances in Neural Information Processing Systems 33*. https://arxiv.org/abs/2005.11401

[13] Ovadia, O., Brief, M., Mishaeli, M., & Elisha, O. (2024). Fine-tuning or retrieval? Comparing knowledge injection in LLMs. En *Proceedings of EMNLP 2024* (pp. 237–250). https://doi.org/10.18653/v1/2024.emnlp-main.15

[14] Gekhman, Z., Yona, G., Aharoni, R., Eyal, M., Feder, A., Reichart, R., & Herzig, J. (2024). Does fine-tuning LLMs on new knowledge encourage hallucinations? En *Proceedings of EMNLP 2024* (pp. 7765–7784). https://doi.org/10.18653/v1/2024.emnlp-main.444

[15] Yang, Z., Band, N., Li, S., Candès, E., & Hashimoto, T. (2025). Synthetic continued pretraining. En *ICLR 2025*. https://arxiv.org/abs/2409.07431

[16] Hu, E. J., Shen, Y., Wallis, P., et al. (2022). LoRA: Low-rank adaptation of large language models. En *ICLR 2022*. https://arxiv.org/abs/2106.09685

[17] Dettmers, T., Pagnoni, A., Holtzman, A., & Zettlemoyer, L. (2023). QLoRA: Efficient finetuning of quantized LLMs. En *Advances in Neural Information Processing Systems 36*. https://arxiv.org/abs/2305.14314

[18] Biderman, D., Portes, J., González Ortiz, J. J., Paul, M., Greengard, P., Jennings, C., King, D., Havens, S., Chiley, V., Frankle, J., Blakeney, C., & Cunningham, J. P. (2024). LoRA learns less and forgets less. *Transactions on Machine Learning Research*. https://arxiv.org/abs/2405.09673

[19] Rafailov, R., Sharma, A., Mitchell, E., Ermon, S., Manning, C. D., & Finn, C. (2023). Direct preference optimization: Your language model is secretly a reward model. En *NeurIPS 2023*. https://arxiv.org/abs/2305.18290

[20] Min, S., Krishna, K., Lyu, X., Lewis, M., et al. (2023). FActScore: Fine-grained atomic evaluation of factual precision in long form text generation. En *Proceedings of EMNLP 2023*. https://arxiv.org/abs/2305.14251

[21] Gao, T., Yen, H., Yu, J., & Chen, D. (2023). Enabling large language models to generate text with citations. En *Proceedings of EMNLP 2023*. https://arxiv.org/abs/2305.14627

### Aprendizaje continuo y sistemas complementarios

[22] McClelland, J. L., McNaughton, B. L., & O'Reilly, R. C. (1995). Why there are complementary learning systems in the hippocampus and neocortex. *Psychological Review, 102*(3), 419–457. https://doi.org/10.1037/0033-295X.102.3.419

[23] McCloskey, M., & Cohen, N. J. (1989). Catastrophic interference in connectionist networks: The sequential learning problem. *Psychology of Learning and Motivation, 24*, 109–165. https://doi.org/10.1016/S0079-7421(08)60536-8

[24] Kumaran, D., Hassabis, D., & McClelland, J. L. (2016). What learning systems do intelligent agents need? Complementary learning systems theory updated. *Trends in Cognitive Sciences, 20*(7), 512–534. https://doi.org/10.1016/j.tics.2016.05.004

[25] Kirkpatrick, J., et al. (2017). Overcoming catastrophic forgetting in neural networks. *Proceedings of the National Academy of Sciences, 114*(13), 3521–3526. https://doi.org/10.1073/pnas.1611835114

[26] Luo, Y., Yang, Z., Meng, F., Li, Y., Zhou, J., & Zhang, Y. (2023). An empirical study of catastrophic forgetting in large language models during continual fine-tuning. *arXiv*. https://arxiv.org/abs/2308.08747

[27] Scialom, T., Chakrabarty, T., & Muresan, S. (2022). Fine-tuned language models are continual learners. En *Proceedings of EMNLP 2022* (pp. 6107–6122). https://doi.org/10.18653/v1/2022.emnlp-main.410

### Colapso, homogeneización y errores correlacionados

[28] Shumailov, I., Shumaylov, Z., Zhao, Y., Papernot, N., Anderson, R., & Gal, Y. (2024). AI models collapse when trained on recursively generated data. *Nature, 631*(8022), 755–759. https://doi.org/10.1038/s41586-024-07566-y

[29] Gerstgrasser, M., Schaeffer, R., Dey, A., Rafailov, R., Sleight, H., Hughes, J., Korbak, T., Agrawal, R., Pai, D., Gromov, A., Roberts, D. A., Yang, D., Donoho, D. L., & Koyejo, S. (2024). Is model collapse inevitable? Breaking the curse of recursion by accumulating real and synthetic data. En *COLM 2024*. https://arxiv.org/abs/2404.01413

[30] Alemohammad, S., Casco-Rodriguez, J., Luzi, L., Humayun, A. I., Babaei, H., LeJeune, D., Siahkoohi, A., & Baraniuk, R. G. (2024). Self-consuming generative models go MAD. En *ICLR 2024*. https://arxiv.org/abs/2307.01850

[31] Bertrand, Q., Bose, A. J., Duplessis, A., Jiralerspong, M., & Gidel, G. (2024). On the stability of iterative retraining of generative models on their own data. En *ICLR 2024*. https://arxiv.org/abs/2310.00429

[32] Dohmatob, E., Feng, Y., Yang, P., Charton, F., & Kempe, J. (2024). A tale of tails: Model collapse as a change of scaling laws. En *Proceedings of ICML 2024*, PMLR 235, 11165–11197. https://proceedings.mlr.press/v235/dohmatob24b.html

[33] Padmakumar, V., & He, H. (2024). Does writing with language models reduce content diversity? En *ICLR 2024*. https://arxiv.org/abs/2309.05196

[34] Wu, F., Black, E., & Chandrasekaran, V. (2025). Generative monoculture in large language models. En *ICLR 2025*. https://arxiv.org/abs/2407.02209

[35] Jiang, L., Chai, Y., Li, M., Liu, M., Fok, R., Dziri, N., Tsvetkov, Y., Sap, M., Albalak, A., & Choi, Y. (2025). Artificial hivemind: The open-ended homogeneity of language models (and beyond). En *NeurIPS 2025, Datasets and Benchmarks*. https://arxiv.org/abs/2510.22954

[36] Kim, E. M., Garg, A., Peng, K., & Garg, N. (2025). Correlated errors in large language models. En *Proceedings of ICML 2025*, PMLR 267, 30038–30066. https://proceedings.mlr.press/v267/kim25e.html

[37] Kleinberg, J., & Raghavan, M. (2021). Algorithmic monoculture and social welfare. *Proceedings of the National Academy of Sciences, 118*(22), e2018340118. https://doi.org/10.1073/pnas.2018340118

[38] Santurkar, S., Durmus, E., Ladhak, F., Lee, C., Liang, P., & Hashimoto, T. (2023). Whose opinions do language models reflect? En *ICML 2023*. https://arxiv.org/abs/2303.17548

### Evolución cultural, poblaciones de LLM y conformismo

[39] Cavalli-Sforza, L. L., & Feldman, M. W. (1981). *Cultural transmission and evolution: A quantitative approach* (Monographs in Population Biology 16). Princeton University Press.

[40] Boyd, R., & Richerson, P. J. (1985). *Culture and the evolutionary process*. University of Chicago Press.

[41] Henrich, J., & Boyd, R. (1998). The evolution of conformist transmission and the emergence of between-group differences. *Evolution and Human Behavior, 19*(4), 215–241. https://doi.org/10.1016/S1090-5138(98)00018-X

[42] Brinkmann, L., Baumann, F., Bonnefon, J.-F., Derex, M., Müller, T. F., Nussberger, A.-M., Czaplicka, A., Acerbi, A., Griffiths, T. L., Henrich, J., Leibo, J. Z., McElreath, R., Oudeyer, P.-Y., Stray, J., & Rahwan, I. (2023). Machine culture. *Nature Human Behaviour, 7*(11), 1855–1868. https://doi.org/10.1038/s41562-023-01742-2

[43] Perez, J., Léger, C., Ovando-Tellez, M., Foulon, C., Dussauld, J., Oudeyer, P.-Y., & Moulin-Frier, C. (2024). Cultural evolution in populations of large language models. *arXiv*. https://arxiv.org/abs/2403.08882

[44] Vallinder, A., & Hughes, E. (2025). Cultural evolution of cooperation among LLM agents: Extended abstract. En *Proceedings of the 24th International Conference on Autonomous Agents and Multiagent Systems (AAMAS 2025)* (pp. 2771–2773). IFAAMAS. https://arxiv.org/abs/2412.10270

[45] Weng, Z., Chen, G., & Wang, W. (2025). Do as we do, not as you think: The conformity of large language models. En *ICLR 2025*. https://arxiv.org/abs/2501.13381

[46] Chuang, Y.-S., Goyal, A., Harlalka, N., et al. (2024). Simulating opinion dynamics with networks of LLM-based agents. En *Findings of NAACL 2024*. https://arxiv.org/abs/2311.09618

### Genética de poblaciones y cuantitativa

[47] Wright, S. (1931). Evolution in Mendelian populations. *Genetics, 16*(2), 97–159. https://doi.org/10.1093/genetics/16.2.97

[48] Whitlock, M. C., & McCauley, D. E. (1999). Indirect measures of gene flow and migration: F_ST ≠ 1/(4Nm+1). *Heredity, 82*(2), 117–125. https://doi.org/10.1038/sj.hdy.6884960

[49] Mills, L. S., & Allendorf, F. W. (1996). The one-migrant-per-generation rule in conservation and management. *Conservation Biology, 10*(6), 1509–1518. https://doi.org/10.1046/j.1523-1739.1996.10061509.x

[50] Ayala, F. J., & Campbell, C. A. (1974). Frequency-dependent selection. *Annual Review of Ecology and Systematics, 5*, 115–138. https://doi.org/10.1146/annurev.es.05.110174.000555

[51] Falconer, D. S., & Mackay, T. F. C. (1996). *Introduction to quantitative genetics* (4.ª ed.). Longman.

### Plasticidad hebbiana y su control

[52] Hebb, D. O. (1949). *The organization of behavior: A neuropsychological theory*. Wiley.

[53] Oja, E. (1982). Simplified neuron model as a principal component analyzer. *Journal of Mathematical Biology, 15*(3), 267–273. https://doi.org/10.1007/BF00275687

[54] Turrigiano, G. G., Leslie, K. R., Desai, N. S., Rutherford, L. C., & Nelson, S. B. (1998). Activity-dependent scaling of quantal amplitude in neocortical neurons. *Nature, 391*(6670), 892–896. https://doi.org/10.1038/36103

### Evaluación adaptativa y pluralismo

[55] Dwork, C., Feldman, V., Hardt, M., Pitassi, T., Reingold, O., & Roth, A. (2015). The reusable holdout: Preserving validity in adaptive data analysis. *Science, 349*(6248), 636–638. https://doi.org/10.1126/science.aaa9375

[56] Sorensen, T., Moore, J., Fisher, J., Gordon, M., Mireshghallah, N., Rytting, C. M., Ye, A., Jiang, L., Lu, X., Dziri, N., Althoff, T., & Choi, Y. (2024). Position: A roadmap to pluralistic alignment. En *Proceedings of ICML 2024*. https://arxiv.org/abs/2402.05070

### Privacidad, memorización, desaprendizaje y Sybil

[57] Carlini, N., Tramèr, F., Wallace, E., Jagielski, M., et al. (2021). Extracting training data from large language models. En *30th USENIX Security Symposium*. https://arxiv.org/abs/2012.07805

[58] Mireshghallah, F., Uniyal, A., Wang, T., Evans, D., & Berg-Kirkpatrick, T. (2022). An empirical analysis of memorization in fine-tuned autoregressive language models. En *Proceedings of EMNLP 2022* (pp. 1816–1826). https://doi.org/10.18653/v1/2022.emnlp-main.119

[59] Maini, P., Feng, Z., Schwarzschild, A., Lipton, Z. C., & Kolter, J. Z. (2024). TOFU: A task of fictitious unlearning for LLMs. *arXiv*. https://arxiv.org/abs/2401.06121

[60] Shi, W., Lee, J., Huang, Y., Malladi, S., Zhao, J., et al. (2025). MUSE: Machine unlearning six-way evaluation for language models. En *ICLR 2025*. https://arxiv.org/abs/2407.06460

[61] Douceur, J. R. (2002). The Sybil attack. En *Peer-to-Peer Systems (IPTPS 2002)*, LNCS 2429 (pp. 251–260). Springer. https://doi.org/10.1007/3-540-45748-8_24

### Aprendizaje descentralizado y computación voluntaria

[62] McMahan, B., Moore, E., Ramage, D., Hampson, S., & Agüera y Arcas, B. (2017). Communication-efficient learning of deep networks from decentralized data. En *Proceedings of AISTATS 2017*, PMLR 54, 1273–1282. https://arxiv.org/abs/1602.05629

[63] Hegedűs, I., Danner, G., & Jelasity, M. (2021). Decentralized learning works: An empirical comparison of gossip learning and federated learning. *Journal of Parallel and Distributed Computing, 148*, 109–124. https://doi.org/10.1016/j.jpdc.2020.10.006

[64] Huang, C., Liu, Q., Lin, B. Y., Pang, T., Du, C., & Lin, M. (2024). LoraHub: Efficient cross-task generalization via dynamic LoRA composition. En *COLM 2024*. https://arxiv.org/abs/2307.13269

[65] Anderson, D. P., & Fedak, G. (2006). The computational and storage potential of volunteer computing. En *CCGRID'06* (pp. 73–80). IEEE. https://doi.org/10.1109/CCGRID.2006.101

---

*Swarmbly LCE — Sebastián A. Espinoza-Ulloa · Whitepaper versión 0.1 (borrador). Versión en inglés: `WHITEPAPER_LCE_EN.md`. Especificación: `SPEC_LCE_ES.md`. Texto bajo CC BY 4.0.*
