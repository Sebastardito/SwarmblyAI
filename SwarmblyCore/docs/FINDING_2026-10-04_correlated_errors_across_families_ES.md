---
status: current
lang: es
---
# Los errores de familias distintas están correlacionados: lo que eso le quita a E12 y E16

**Encontrado:** 4 de octubre de 2026, durante la revisión bibliográfica de la
extensión cognitiva local (LCE).
**Clase:** evidencia externa adversa a un supuesto del diseño. **No es una
medición propia** del proyecto; ninguna cifra de esta nota procede de corridas de
Swarmbly.
**Estado:** **abierto.** Propone una limitación nueva (L23) y una enmienda de
redacción para la próxima versión del whitepaper, y una medición barata sobre el
corpus existente. No modifica el whitepaper v2 publicado.

---

## 1. Qué se encontró

Dos trabajos recientes miden lo que el whitepaper v2 daba por atenuado con la
diversidad de familias de modelo.

Kim et al. (2025) evaluaron más de 350 modelos y encontraron que, en uno de los
leaderboards estudiados, **dos modelos coinciden en la respuesta el 60 % de las
veces cuando ambos se equivocan**. La correlación crece con la arquitectura y el
proveedor compartidos, como cabía esperar, pero el hallazgo que importa aquí es
otro: **los modelos más grandes y capaces correlacionan fuertemente sus errores
incluso con arquitecturas distintas y de desarrolladores distintos** [1].

Jiang et al. (2025) muestran, sobre 26.000 consultas abiertas reales, que modelos
distintos producen respuestas sorprendentemente parecidas entre sí, además de
repetirse cada uno consigo mismo, un efecto que llaman "mente colmena artificial"
[2].

## 2. Qué afirmaciones del whitepaper v2 toca

El whitepaper ya reconoce el problema y le asigna un remedio. En la sección 10.5.4
dice que el acuerdo no es verdad porque "modelos entrenados sobre corpus solapados
comparten errores", y que por eso la sección 9.6 obliga a diversidad entre
familias. **La evidencia nueva dice que ese remedio es parcial**: la diversidad de
familia reduce la correlación debida a arquitectura y proveedor compartidos, pero
no la que procede del solapamiento de los datos de preentrenamiento, que alcanza a
modelos de familias y desarrolladores distintos y es más fuerte en los modelos más
capaces.

Las afirmaciones afectadas son tres:

- **E12** (despacho redundante preservador de diversidad): asigna réplicas a
  familias distintas suponiendo errores aproximadamente independientes. El
  supuesto se debilita; el mecanismo sigue siendo útil para la correlación de
  arquitectura y proveedor.
- **E16 / M1** (consenso por alineamiento múltiple y mapa de regiones de baja
  confianza): un acuerdo entre tres familias puede ser un error compartido. La
  retirada de fiabilidad de L13 ya impide presentar la convergencia como
  corrección; esta evidencia da una razón mecánica más para mantenerla, y afecta
  al régimen en el que M1 debía demostrar señal ("donde los modelos genuinamente
  discrepan"), que puede ser más estrecho de lo supuesto.
- **E17** (cobertura semántica): no se ve afectada en lo que afirma, porque ya
  acota disponibilidad y no corrección.

## 3. Qué no cambia

La capacidad de reportar **dónde** divergieron las réplicas sigue siendo real y
sigue siendo la que un proveedor con un solo modelo no tiene. Lo que cambia es
cuánto puede inferirse de **dónde convergieron**.

## 4. Lo que la LCE puede y no puede aportar

Una pregunta natural es si la diversidad que genera el aprendizaje local de cada
usuario corrige el problema. La respuesta, desarrollada en el whitepaper de la LCE
(Espinoza-Ulloa, 2026, doi:10.5281/zenodo.23150478; secciones 2.6, 6.4 y LC3), es que **no dentro de una misma petición**: en la LCE
los workers sirven su modelo base sin adaptador, de modo que el aprendizaje del
usuario no llega a las réplicas que E16 alinea; y aunque llegara, el adaptador
aprende comportamiento y no hechos, y LoRA conserva el conocimiento del modelo base
y con él sus errores. La correlación es, en términos de genética de poblaciones,
**identidad por descendencia**: los modelos comparten ancestría porque se
preentrenaron sobre corpus solapados, y un adaptador local se parece más a
plasticidad fenotípica que a alelos nuevos. La LCE sí reduce la homogeneidad
**entre usuarios** en tareas abiertas, que es el efecto de [2], a través de la
proyección de cada usuario sobre Γ; eso es diversidad real, pero no independencia
de errores.

## 5. Propuesta para la próxima versión del whitepaper

**5.1 Limitación nueva (texto propuesto).**

> **L23 — La diversidad de familias atenúa la correlación de errores, no la
> elimina.** Sobre más de 350 modelos, dos modelos coinciden el 60 % de las veces
> cuando ambos fallan en un leaderboard, y los modelos más capaces correlacionan
> sus errores aun con arquitecturas y desarrolladores distintos [Kim et al.,
> 2025]; modelos distintos producen además respuestas muy parecidas en tareas
> abiertas [Jiang et al., 2025]. E12 sigue reduciendo la correlación de
> arquitectura y proveedor, pero la que procede de corpus de preentrenamiento
> solapados alcanza a familias distintas. Un acuerdo entre familias puede ser un
> error compartido.

**5.2 Enmienda en 10.5.4.** Donde dice que la sección 9.6 obliga a diversidad
entre familias "por eso", añadir que esa diversidad es un remedio parcial y remitir
a L23.

**5.3 Hipótesis candidata: diversidad de evidencia.** Si la correlación procede
del conocimiento compartido, la palanca para reducirla no es la familia sino la
evidencia. Se propone como hipótesis, no como elemento: **réplicas que razonan
sobre evidencias públicas distintas** (por ejemplo, recuperando de fuentes
distintas, nunca de memoria personal de los workers) tienen errores menos
correlacionados que réplicas de familias distintas sin evidencia. Su condición de
muerte: si la correlación de errores entre réplicas con evidencia distinta no es
menor que entre réplicas de familias distintas sin evidencia, la idea se retira.

## 6. Medición barata disponible

El corpus de referencia de la sección 15.9 (473 corridas sobre cinco familias de
modelos locales) permite estimar directamente, sin corridas nuevas, la
probabilidad de coincidencia en la respuesta condicionada a que dos familias
fallen, que es la métrica de [1]. Es un instrumento que el proyecto ya tiene y
que convertiría esta nota de evidencia externa en medición propia, con su alcance
declarado (cinco familias pequeñas, tareas del benchmark, no un leaderboard
general).

## Referencias

[1] Kim, E. M., Garg, A., Peng, K., & Garg, N. (2025). Correlated errors in large language models. En *Proceedings of the 42nd International Conference on Machine Learning*, PMLR 267, 30038–30066. https://proceedings.mlr.press/v267/kim25e.html

[2] Jiang, L., Chai, Y., Li, M., Liu, M., Fok, R., Dziri, N., Tsvetkov, Y., Sap, M., Albalak, A., & Choi, Y. (2025). Artificial hivemind: The open-ended homogeneity of language models (and beyond). En *NeurIPS 2025, Datasets and Benchmarks Track*. https://arxiv.org/abs/2510.22954
