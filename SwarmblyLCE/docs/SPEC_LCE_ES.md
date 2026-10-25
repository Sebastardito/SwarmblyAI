---
status: draft
lang: es
---
# Especificación y arquitectura de la Local Cognitive Extension (LCE) de Swarmbly

**Versión 0.1 — 4 de octubre de 2026**
Estado: **Borrador.** Normativa; la implementación de referencia la sigue (sección 21) y se espera que cambie después de los prototipos de la sección 14 del whitepaper. Desde entonces varios de sus mecanismos se han medido con modelos reales (whitepaper v0.2, sección 11.7). El texto normativo aún no cambia: su próxima revisión incorporará el resultado de R13, que hace de la recuperación sobre las fuentes el contexto de respuesta por defecto y deja la wiki como capa de gobierno (procedencia, tipos, olvido, elegibilidad para entrenar).
Documentos complementarios: `WHITEPAPER_LCE_ES.md` (fundamento, homologías y evidencia), `REFERENCES_LCE.md` (bibliografía anotada; los marcadores [n] de este documento remiten a ella), `swips/SWIP-XXXX-local-cognitive-extension.md` (la parte visible en la red, en inglés, para el repositorio del protocolo), y la especificación del protocolo Swarmbly v0.2 (`Swarmbly-AI/docs/SPEC_ES.md`), que este documento no modifica.

Las palabras clave MUST, MUST NOT, REQUIRED, SHALL, SHOULD, SHOULD NOT, MAY y OPTIONAL deben interpretarse tal como se describe en RFC 2119. Se conservan en inglés y en mayúsculas, como en la especificación del protocolo, para que su fuerza normativa sea inequívoca.

**Sobre los valores por defecto.** Los parámetros marcados *provisional* en la sección 19 no proceden de mediciones de la LCE. Son puntos de partida derivados de la literatura o de cálculos enunciados, y los experimentos del whitepaper (sección 11) deben fijarlos o refutarlos antes de que esta especificación salga del estado de borrador.

---

## 1. Alcance y no objetivos

La LCE es una extensión opcional del cliente Swarmbly que añade memoria personal local, aprendizaje del modelo del usuario y un intercambio opcional de conocimiento escrito entre nodos.

**Dentro del alcance:** el espacio de fuentes y la política de aprendizaje; la wiki y su capa epistémica; la cola de entrenamiento, el adaptador y su selección; la proyección de tarea sobre el contrato Γ; las reglas que un worker con LCE debe cumplir al servir a terceros; la caché social y la afinidad; el bloque de capacidades cognitivas del anuncio de nodo; las cápsulas cognitivas y su persistencia; la respuesta plural; los informes de diversidad y de costo cognitivo.

**Fuera del alcance:** el formato interno de la wiki más allá de los atributos que esta especificación exige; el modelo base y el método de ajuste concretos; el transporte de descubrimiento; cualquier modelo global compartido; cualquier servicio central de conocimiento, identidad o confianza.

**No objetivos explícitos.** La LCE no proporciona olvido verificable en los pesos salvo por regeneración del adaptador; no garantiza que las cápsulas sean verdaderas; no proporciona resistencia fuerte a Sybil; y no reivindica que la diversidad de familias de modelo produzca errores independientes. Véase la sección 12 del whitepaper.

**Lo que esta especificación no cambia del protocolo.** El router, el plan, el paquete, el resultado, el despacho, la verificación, el ensamblaje, el consenso E16, los carriles, los niveles, los créditos y los códigos de error de la especificación v0.2 se aplican sin cambios. Un nodo que no implementa la LCE es plenamente conformante con Swarmbly.

---

## 2. Terminología

| Término | Significado |
|---|---|
| **LCE** | Local Cognitive Extension: el conjunto de componentes de esta especificación |
| **Espacio de fuentes** | Carpeta o conjunto de carpetas del usuario con material en bruto; capa 0 |
| **Política de aprendizaje** | Declaración por fuente de qué puede extraerse y para qué uso (sección 5) |
| **Wiki** | Memoria escrita por un modelo local a partir de las fuentes; capa 1 |
| **Afirmación** | Unidad mínima de la wiki: un enunciado con anclaje, tipo, madurez y procedencia (sección 6) |
| **Anclaje** | Referencia de una afirmación al fragmento exacto de la fuente del que se extrajo |
| **Distancia epistémica** *d* | Número de transformaciones por modelo entre una afirmación y su fuente humana más cercana (sección 6.6) |
| **Vía de transmisión** | `vertical` (del usuario), `horizontal` (de otro nodo) u `oblique` (de nodos establecidos hacia uno nuevo) |
| **Adaptador** | Módulo de ajuste eficiente en parámetros (LoRA o equivalente) entrenado sobre el modelo base; capa 2 |
| **Receta** | Conjunto de datos elegibles, mezcla de repaso e hiperparámetros con que se entrena un adaptador |
| **Generación** | Un ciclo de consolidación que produce candidatos a adaptador y elige como mucho uno |
| **Proyección de tarea** | Información personal mínima y relevante para una petición, expresada en campos de Γ (sección 8) |
| **Caché social** | Registro local de patrones observados en los resultados de las peticiones propias |
| **Afinidad** | Utilidad local observada de un par para un dominio (sección 10.2) |
| **Prevalencia** | Número de nodos y familias independientes en que se observó un patrón; es una etiqueta |
| **Cápsula** | Objeto firmado de a lo sumo 16 KiB con conocimiento escrito generalizable (sección 12) |
| **Variante anclada** | Cápsula descendiente que declara evidencia humana nueva (sección 12.6) |
| **Conjunto canario** | Lista de regionalismos con glosas verificadas por hablantes nativos, usada solo para medir (sección 15.3) |

---

## 3. Versionado y conformidad

Los objetos de la LCE que viajan por la red llevan un campo `"v"` con la versión de la extensión como `MAJOR.MINOR`, independiente de la versión del protocolo. Se aplica la regla del protocolo: un participante MUST ignorar los campos desconocidos y MUST rechazar una versión MAJOR que no implemente.

**Clases de conformidad.**

- Un **Cliente LCE conformante** MUST implementar las secciones 5, 6, 7 (si implementa adaptadores), 8 y 15.2, y MUST cumplir las invariantes de la sección 4.2.
- Un **Worker conformante con LCE instalada** MUST cumplir la sección 9 además de las obligaciones de worker del protocolo.
- Un **Nodo de cápsulas conformante** MUST implementar las secciones 11, 12 y 13, y MUST cumplir las reglas de permisos, firma, distancia y variación de la sección 12.
- Una implementación que entrene un adaptador sin la compuerta de la sección 7.5 es **no conformante**. Una implementación que sirva tareas ajenas con un adaptador personal cargado es **no conformante**.

---

## 4. Vista de componentes

### 4.1 Componentes y planos

| Componente | Plano | Visible en la red | Escalón mínimo | Sección |
|---|---|---|---|---|
| Espacio de fuentes y política | local | no | C1 | 5 |
| Wiki y capa epistémica | local | no | C1 | 6 |
| Digestor | local | no | C2 | 6.3 |
| Cola de entrenamiento y adaptador | local | no | C4 | 7 |
| Proyección de tarea | inferencia | solo a través de Γ | C1 | 8 |
| Reglas del worker | inferencia | no (comportamiento) | C0 | 9 |
| Caché social y afinidad | local | no | C3 | 10 |
| Bloque de capacidades | social | sí, opcional | C3 | 11 |
| Cápsulas y persistencia | social | sí, opcional | C3 | 12–13 |
| Respuesta plural | inferencia | metadatos de respuesta | C0 | 14 |
| Informes | local | opcional | C1 | 15 |

### 4.2 Invariantes (normativo)

Una implementación conformante MUST preservar las ocho invariantes del whitepaper (sección 8.2):

- **I1.** Las afirmaciones de tipo `fact`, `user_claim`, `opinion`, `belief`, `hypothesis` y `experience` MUST NOT entrar a ningún conjunto de entrenamiento de adaptador como aserciones. (Excepción explícita: sección 7.7.)
- **I2.** Un worker que ejecuta tareas de otro cliente MUST servir su modelo base sin adaptador personal y MUST descartar el contenido de la tarea según la sección 9.
- **I3.** La fracción de ejemplos derivados de otros nodos en cualquier lote de entrenamiento MUST ser menor que `SOCIAL_TRAIN_FRACTION_MAX`; todo ejemplo derivado de otro nodo MUST tener `d ≤ 1` y una fuente humana declarada; el corpus propio del usuario MUST NOT descartarse para hacer sitio a material social.
- **I4.** Una cápsula descendiente MUST declarar `delta_evidence` para poder redistribuirse o entrenarse.
- **I5.** La decisión de cachear, consolidar o entrenar MUST NOT depender de la prevalencia de forma más que lineal (sección 10.1).
- **I6.** Todo adaptador MUST entrenarse desde el modelo base y la wiki, con repaso intercalado, y MUST evaluarse con un conjunto de prueba generado para esa generación.
- **I7.** Un nodo que participa en el plano social SHOULD calcular y MAY publicar el informe de diversidad de la sección 15.3.
- **I8.** Una fuente sin política declarada MUST tratarse como `reference_only`.

---

## 5. Espacio de fuentes y política de aprendizaje

### 5.1 Espacio de fuentes

El espacio de fuentes es una o más carpetas locales. Una implementación:

1. MUST tratar los archivos del espacio de fuentes como inmutables desde el punto de vista de la LCE: el digestor MUST NOT modificarlos.
2. MUST calcular una huella de contenido por archivo y registrarla en el grafo de dependencias (sección 6.7).
3. MUST permitir al usuario retirar una fuente, lo que dispara el olvido de la sección 7.8.
4. MUST NOT transmitir ninguna fuente por la red por el hecho de participar en Swarmbly.

### 5.2 Política de aprendizaje

Cada fuente o carpeta MAY declarar una política. El esquema mínimo es:

```yaml
learning_policy:
  v: "0.1"
  defaults:
    reference_only: true          # I8: lo no declarado no entrena
  sources:
    "teach/style/":
      authored_by_user: true
      wiki: true
      learn_style: true
      learn_procedure: false
      retain_episodic: false
    "teach/knowledge/":
      authored_by_user: false
      wiki: true
      learn_style: false
    "teach/procedures/":
      authored_by_user: true
      wiki: true
      learn_procedure: true
    "reference_only/":
      wiki: true
      train: false
```

**Semántica.**

1. `authored_by_user = true` declara que el texto fue escrito por el usuario. Solo las fuentes con este valor MAY producir ejemplos de estilo (sección 7.2).
2. `wiki = true` permite que el digestor extraiga afirmaciones. `wiki = false` excluye la fuente de la wiki.
3. `learn_style` y `learn_procedure` permiten que las afirmaciones de esos tipos extraídas de la fuente alcancen el estado TRAINABLE.
4. `train = false` o `reference_only = true` impide que cualquier afirmación de la fuente alcance TRAINABLE.
5. `retain_episodic = false` impide conservar afirmaciones de tipo `experience`.
6. Un cambio de política MUST registrarse en el grafo de dependencias y MUST marcar como obsoletos los ejemplos de entrenamiento que dependían de la política anterior.

---

## 6. Wiki y capa epistémica

### 6.1 Representación

La wiki SHOULD representarse como archivos Markdown con metadatos, legibles por humanos y compatibles con herramientas de notas, y MAY indexarse en SQLite y un índice vectorial. El formato concreto no es normativo; los atributos de la sección 6.2 sí.

### 6.2 Registro de afirmación

Toda afirmación MUST tener, como mínimo:

```yaml
claim_id: "hex"                     # huella del contenido normalizado
text: "En el español de Ecuador, 'chuta' es una interjección informal de sorpresa o contrariedad."
type: fact                          # ver 6.4
maturity: ANCHORED                  # ver 6.5
anchors:
  - source: "teach/style/notas-2026-09.md"
    span: [1204, 1268]              # desplazamientos de bytes
    source_hash: "hex"
    verified: true                  # 6.3
provenance:
  epistemic_distance: 1             # 6.6
  transmission_path: vertical       # vertical | horizontal | oblique
  origin_capsule: null              # capsule_id si llegó por cápsula
  human_source: "self"              # self | <origin_node> | <descripción>
status: active                      # active | contested | retracted
positions: []                       # solo si status = contested (sección 14.3)
depends_on: ["hex", "..."]
created: "2026-10-04T10:22:00Z"
updated: "2026-10-04T10:22:00Z"
```

### 6.3 Digestor y verificación de anclajes

1. El digestor MAY ser un modelo local. Sus salidas MUST tratarse como propuestas hasta que la verificación de anclaje las acepte.
2. La verificación de anclaje MUST comprobar, como mínimo, que el fragmento citado existe en la fuente con la huella registrada y que un verificador, que MAY ser un modelo distinto del digestor, juzga que el fragmento soporta la afirmación atómica [20].
3. Una afirmación cuyo anclaje no se verifica MUST permanecer en estado DIGESTED y MUST NOT alcanzar ningún estado posterior.
4. El índice, los enlaces, las dependencias y las transiciones de estado MUST implementarse con código determinista, no delegarse al modelo.
5. La tasa de rechazo del verificador SHOULD registrarse en el informe de la sección 15.2.

### 6.4 Tipos

| `type` | Contenido | Recuperación | Entrenamiento |
|---|---|---|---|
| `fact` | Afirmación sobre el mundo con fuente externa | sí | no (I1) |
| `user_claim` | Lo que el usuario afirma | sí, atribuida | no |
| `opinion` | Valoración del usuario | sí, atribuida | no |
| `belief` | Creencia del usuario | sí, atribuida | no |
| `hypothesis` | Afirmación en prueba | sí, marcada | no |
| `experience` | Memoria episódica | sí, si `retain_episodic` | no |
| `preference` | Preferencia de comportamiento | sí | sí, si la política lo permite |
| `style` | Rasgo de voz, registro o formato | sí | sí, si `learn_style` |
| `procedure` | Forma recurrente de hacer algo | sí | sí, si `learn_procedure` |

Una implementación MUST recuperar las afirmaciones de tipo `user_claim`, `opinion` y `belief` con su atribución explícita, y MUST NOT presentarlas como hechos.

### 6.5 Estados de madurez

```text
RAW → DIGESTED → ANCHORED → CONNECTED → CORROBORATED → CONSOLIDATED → TRAINABLE
                    ↑                                                    (solo preference,
              anclaje verificado                                          style, procedure)
```

| Transición | Condición (normativa) |
|---|---|
| RAW → DIGESTED | el digestor propuso la afirmación |
| DIGESTED → ANCHORED | anclaje verificado (6.3) |
| ANCHORED → CONNECTED | al menos un enlace a otra afirmación o concepto |
| CONNECTED → CORROBORATED | `fact`: dos fuentes humanas independientes; `style`/`preference`/`procedure`: observada en al menos `STABILITY_CYCLES` ciclos de consolidación |
| CORROBORATED → CONSOLIDATED | sin contradicción activa durante un ciclo de revisión |
| CONSOLIDATED → TRAINABLE | tipo de comportamiento, política lo permite, `d ≤ 1` |

Una contradicción detectada en la revisión MUST devolver la afirmación a CONNECTED y MAY marcarla `contested`. Retirar el anclaje MUST devolverla a DIGESTED.

### 6.6 Distancia epistémica

1. `d = 0` para afirmaciones de estilo, preferencia o procedimiento observadas directamente en texto de autoría del usuario.
2. `d = 1` para afirmaciones extraídas por un modelo de una fuente humana anclada, propia o del nodo de origen de una cápsula.
3. `d = d_padre + 1` para afirmaciones derivadas de otra afirmación sin evidencia humana nueva.
4. Copiar o cachear una cápsula sin modificarla MUST NOT cambiar `d`.
5. Una variante anclada (sección 12.6) MUST tener `d = 1`.
6. La distancia es un atributo del contenido. MUST NOT usarse para calcular confianza entre nodos, ni componerse de forma transitiva sobre identidades.

### 6.7 Grafo de dependencias

1. Una implementación MUST mantener un grafo dirigido acíclico con nodos de tipo fuente, política, afirmación, concepto, ejemplo de entrenamiento y adaptador.
2. Cuando cambia la huella de una fuente, se retira una fuente o cambia una política, todos los descendientes MUST marcarse `stale`.
3. Un adaptador cuyo conjunto de entrenamiento contiene algún ejemplo `stale` MUST marcarse `affected` y SHOULD regenerarse en el siguiente ciclo (sección 7.8).

### 6.8 Historial

Una implementación SHOULD versionar la wiki (por ejemplo, con Git) con un commit por ciclo de consolidación. Si lo hace, el olvido de la sección 7.8 MUST reescribir la historia que contiene el contenido olvidado, y MUST propagarse a los respaldos que la implementación gestione.

---

## 7. Cola de entrenamiento y adaptador

### 7.1 Elegibilidad

Un ejemplo es elegible para entrenamiento si y solo si:

1. procede de afirmaciones en estado TRAINABLE o de pares de corrección (7.2.3);
2. todas sus afirmaciones de origen tienen `d ≤ 1`;
3. ninguna de sus dependencias está `stale`;
4. su fuente no es `reference_only`.

### 7.2 Fuentes de ejemplos

1. **Estilo**: texto de fuentes con `authored_by_user = true`, segmentado. MUST NOT usarse texto de autoría ajena para estilo.
2. **Pares pregunta-respuesta**: generados desde afirmaciones de comportamiento elegibles; cada par MUST conservar el `claim_id` y el anclaje, y MUST aceptarse solo si un verificador juzga que la respuesta se deduce del fragmento anclado.
3. **Correcciones**: cada edición del usuario a una respuesta o página MAY registrarse como par de preferencia (antes rechazado, después preferido) para optimización directa de preferencias [19].

### 7.3 Composición del lote y repaso

Todo lote de entrenamiento MUST mezclar ejemplos nuevos, una muestra de ejemplos de generaciones anteriores (repaso) y texto general, en proporciones registradas en la receta. La fracción de repaso MUST ser mayor que cero. La fracción de ejemplos derivados de otros nodos MUST cumplir I3.

### 7.4 Candidatos y generación

1. Un ciclo de consolidación SHOULD ejecutarse solo si el dispositivo está ocioso, conectado a la corriente, el usuario lo permite y hay al menos `MIN_NEW_EXAMPLES` ejemplos elegibles nuevos.
2. Cada ciclo MAY entrenar entre 1 y `N_CANDIDATES` candidatos con recetas distintas.
3. Cada candidato MUST entrenarse desde el modelo base y los ejemplos elegibles. MUST NOT inicializarse desde un adaptador anterior ni usar texto generado por un adaptador anterior como dato.
4. La receta ganadora MUST registrarse; es lo único que se hereda entre generaciones.

### 7.5 Compuerta

Un candidato MAY reemplazar al adaptador vigente solo si cumple las tres condiciones siguientes sobre un conjunto de prueba **generado para esta generación** a partir de afirmaciones ancladas que no se usaron como ejemplos de entrenamiento en ella:

1. mejora en preguntas derivadas de la wiki en al menos `GATE_MIN_GAIN`;
2. no empeora en un benchmark general más de `GATE_MAX_LOSS`;
3. se abstiene, en al menos `GATE_MIN_ABSTAIN` de los casos, ante preguntas sobre contenido que no está en la wiki.

Si varios candidatos pasan la compuerta, se elige el de mayor ganancia. Una implementación MUST NOT reutilizar el conjunto de prueba de una generación como conjunto de prueba de otra. Una implementación SHOULD conservar un conjunto de prueba final independiente, nunca usado para seleccionar, para estimar la ganancia real (experimento C10).

### 7.6 Escalón y opcionalidad

El adaptador es opcional. Un Cliente LCE conformante MAY no implementar la sección 7 y operar solo con recuperación (escalones C1–C3).

### 7.7 Hechos en parámetros por decisión explícita

Si el usuario solicita explícitamente fijar un hecho en el modelo, una implementación MAY usar preentrenamiento continuo sintético [15] sobre afirmaciones `fact` en estado CONSOLIDATED. La solicitud MUST registrarse, el adaptador resultante MUST marcarse como `contains_facts` y MUST mantenerse separado del adaptador de comportamiento.

### 7.8 Olvido

1. Retirar una fuente MUST eliminar sus afirmaciones de la wiki, marcar sus descendientes como `stale` y eliminar los ejemplos de entrenamiento derivados.
2. Un adaptador `affected` MUST dejar de usarse en un plazo de `FORGET_MAX_CYCLES` ciclos y MUST regenerarse sin los ejemplos afectados. Una implementación MUST NOT declarar olvidado un contenido en un adaptador solo por haber aplicado un método de desaprendizaje aproximado [59, 60].
3. La sección 6.8 se aplica al historial.

---

## 8. Proyección de tarea y contrato Γ

### 8.1 Correspondencia con Γ

La proyección de tarea MUST expresarse solo en campos que Γ ya define. No hay mensaje nuevo.

| Origen en la wiki | Campo de Γ | Ejemplo |
|---|---|---|
| afirmaciones `style` sobre registro | `register` | "técnico pero accesible" |
| afirmaciones `preference` sobre terminología | `lexicon` | `{"fragmentación semántica": "preferido"}` |
| nombres canónicos | `entities` | `{"Swarmbly": "Swarmbly"}` |
| afirmaciones `style` de voz | `style_seed` | descriptor breve, nunca texto del usuario |
| audiencia declarada por el usuario | `audience` | "lectores de genómica" |

### 8.2 Reglas

1. La proyección MUST contener solo afirmaciones relevantes para la petición, seleccionadas por recuperación.
2. La proyección MUST NOT contener texto literal de fuentes del usuario, afirmaciones de tipo `experience`, `user_claim`, `opinion` o `belief`, ni identificadores personales.
3. Los bytes que la proyección añade a Γ MUST contabilizarse dentro del presupuesto de contexto *S* del protocolo y MUST NOT exceder `PROJECTION_MAX_BYTES`.
4. La proyección MUST registrarse en el informe de costo cognitivo (sección 15.2) con su tamaño en bytes.

### 8.3 Doble clasificación de privacidad

1. El cliente MUST ejecutar la clasificación de sensibilidad del protocolo antes de la recuperación y otra vez después de construir la proyección.
2. La segunda clasificación MAY elevar el carril (PUBLIC → SANITISABLE → SENSITIVE) y MUST NOT reducirlo.
3. Si la segunda clasificación eleva el carril, el cliente MUST aplicar el carril elevado a toda la petición.

---

## 9. Reglas del worker con LCE instalada

Un nodo que tiene la LCE instalada y actúa como worker para otro cliente:

1. MUST servir la tarea con el modelo base declarado en su perfil, sin ningún adaptador personal cargado. (I2)
2. MUST NOT persistir el paquete, Γ, los resúmenes de predecesores ni el resultado en la wiki, la caché social o cualquier almacén de la LCE.
3. MUST NOT usar la tarea ni su resultado como dato de entrenamiento.
4. MUST NOT derivar ni publicar una cápsula a partir de la tarea.
5. MUST descartar el contenido de la tarea al terminar, sujeto únicamente a las obligaciones de verificación y auditoría del protocolo.
6. MAY conservar métricas operativas agregadas que no contengan contenido de la tarea.

Un futuro mecanismo de permiso de retención explícito por parte del cliente originador queda fuera de esta versión; su valor por defecto, si se especifica, MUST ser no retener.

---

## 10. Caché social y afinidad

### 10.1 Caché social y prevalencia

La caché social registra patrones observados en los resultados de las peticiones **propias** del cliente, una vez verificados y usados. El registro mínimo es:

```yaml
pattern_id: "hex"
statement: "'chuta' se usa en Ecuador como interjección informal"
observations:
  independent_nodes: 5
  model_families: 3
prevalence_label: "observado en 5 nodos, 3 familias"
pattern_confidence: 0.83
factual_status: unverified          # unverified | anchored | contradicted
adopted: false
adoption_reason: null               # utility_observed | user_promoted
```

**Regla de prevalencia (normativa).**

1. `independent_nodes` y `model_families` son una etiqueta de prevalencia. MUST NOT presentarse como confianza factual.
2. La decisión de adoptar un patrón (cachear, consolidar o hacer elegible para entrenamiento) MUST basarse en utilidad local observada o en promoción explícita del usuario.
3. Si una implementación usa la prevalencia como factor de adopción, la probabilidad de adopción MUST ser, como máximo, lineal en `independent_nodes`. Una función superlineal implementa transmisión conformista [40, 45] y es no conformante.
4. Los patrones adoptados MUST conservar `transmission_path = horizontal` y MUST quedar en el espacio `social`, nunca en el espacio `self` de la wiki, salvo promoción explícita del usuario.
5. Una implementación MUST NOT convertir un patrón cultural observado en una afirmación de identidad del propio modelo (por ejemplo, "soy de X").

### 10.2 Afinidad

La afinidad registra la utilidad local observada de un par para un dominio. Para un par *p* y un dominio *g*:

```text
a(p,g) ← a(p,g) · exp(−Δt / τ) + η · u        u ∈ [0,1]: utilidad observada del último resultado
â(p,g) = a(p,g) / Σ_q a(q,g)                   normalización por dominio
```

1. La afinidad MUST decaer con el tiempo (`τ = AFFINITY_TAU`) y MUST normalizarse por dominio. Una afinidad que solo crece es no conformante (whitepaper, sección 7.7).
2. La influencia de la afinidad sobre la puntuación de selección de candidatos MUST estar acotada: `score' = score · (1 + β · â)` con `β ≤ AFFINITY_BETA_MAX`.
3. La afinidad MUST NOT anular la asignación de familias distintas de E12.
4. En tareas despachadas con `k ≥ EXPLORATION_MIN_K` réplicas, el cliente SHOULD asignar una réplica a un par con afinidad baja o nula para el dominio.
5. La afinidad MUST mantenerse separada de la reputación del protocolo y de la procedencia epistémica, y MUST NOT publicarse.

---

## 11. Bloque de capacidades cognitivas

Un nodo MAY añadir a su anuncio de perfil un bloque `cognitive`. El esquema, la semántica y los límites son los del SWIP (sección 8): `v`, `share_mode` (`none | metadata | pull`), `capsule_kinds`, `domains`, `languages`, `max_capsule_bytes`; un máximo de 1 024 bytes serializados; como mucho 16 dominios y 16 idiomas de hasta 48 bytes cada uno.

1. El bloque MUST describir capacidades gruesas, nunca biografía, ubicación, empleador, nacionalidad ni ningún atributo personal.
2. Un cliente MUST tratar el bloque como orientativo.
3. Un nodo sin LCE ignora el campo por la regla de versionado del protocolo.

---

## 12. Cápsulas cognitivas

### 12.1 Esquema

El esquema base, el identificador (BLAKE2b de 16 bytes sobre la serialización canónica RFC 8785), la firma Ed25519, los límites de tamaño y los permisos son los del SWIP (sección 9). Esta especificación añade cinco campos, todos REQUIRED en la versión `0.2` del objeto:

```json
{
  "v": "0.2",
  "capsule_id": "hex",
  "origin_node": "base64url-ed25519-public-key",
  "kind": "term|concept|procedure|style_pattern|training_pattern",
  "topics": ["linguistics", "es-EC"],
  "statement": "En el español de Ecuador, 'chuta' es una interjección informal de sorpresa o contrariedad.",
  "examples": ["¡Chuta, se cayó el servidor!"],
  "anchor": {
    "kind": "user_source|public_source|native_speaker_note",
    "digest": "hex"
  },
  "epistemic_distance": 1,
  "transmission_path": "horizontal",
  "lineage": {
    "parent_id": null,
    "revision": 0,
    "delta_evidence": null
  },
  "preserve": false,
  "permissions": { "cache": true, "redistribute": true, "train": false },
  "expires_at": null,
  "sig": "base64"
}
```

1. `anchor.digest` MUST ser la huella del fragmento humano que soporta el enunciado. El fragmento mismo MUST NOT incluirse si procede de una fuente privada del usuario.
2. `epistemic_distance` MUST calcularse según la sección 6.6.
3. `transmission_path` es `horizontal` para cápsulas servidas a pares; `oblique` para cápsulas servidas por nodos ancla a nodos en arranque.
4. `preserve = true` indica que el usuario de origen pidió preservarla (sección 13.2).
5. Un objeto `v: "0.1"` del SWIP sin estos campos MUST tratarse como `epistemic_distance = 2` y `delta_evidence = null`, es decir, solo caché local.

### 12.2 Descubrimiento, solicitud y respuesta

Se aplican sin cambios las secciones 10 a 13 del SWIP: solicitud bajo demanda, nunca difusión ni envío no solicitado; solicitud con 1–8 temas y sin contenido del usuario; respuesta con a lo sumo 4 cápsulas y 16 384 bytes; y los códigos de error de la sección 18.

### 12.3 Procesamiento

Una cápsula recibida MUST procesarse como dato externo no confiable: MUST NOT alterar instrucciones, políticas de privacidad, clasificación, planificación, despacho ni Γ salvo mediante un paso explícito de asimilación local; MUST NOT actualizar pesos directamente; y MUST conservar su origen social salvo promoción explícita del usuario.

### 12.4 Reglas de redistribución y entrenamiento

1. Una cápsula con `epistemic_distance > 1` MUST NOT redistribuirse ni usarse como dato de entrenamiento, con independencia de sus permisos.
2. Una cápsula MAY redistribuirse solo sin modificar y solo si `permissions.redistribute = true`.
3. Una cápsula MAY usarse como dato de entrenamiento solo si `permissions.train = true`, `epistemic_distance ≤ 1`, la política local lo permite, y su inclusión respeta I3.

### 12.5 Reformulaciones

Una revisión de una cápsula producida por un modelo sin evidencia humana nueva es una reformulación. MAY usarse localmente, MUST registrarse con `d = d_padre + 1`, y MUST NOT publicarse como cápsula.

### 12.6 Variantes ancladas

Un nodo MAY publicar una cápsula descendiente solo si:

1. `lineage.parent_id` identifica a la cápsula madre;
2. `lineage.delta_evidence` declara la evidencia humana nueva:

```json
"delta_evidence": {
  "kind": "human_correction|new_source|native_speaker_note",
  "digest": "hex"
}
```

3. la descendiente está firmada por el nodo que la modifica, nunca con la firma del origen;
4. `epistemic_distance = 1`.

---

## 13. Persistencia y réplicas

### 13.1 Persistencia inducida por tráfico

Un nodo que cachea una cápsula con `cache = true` y `redistribute = true` MAY servirla a otros. No existe servicio de replicación; la persistencia resulta de las copias inducidas por uso.

### 13.2 Preservación explícita

Para cápsulas con `preserve = true`, el nodo de origen MAY solicitar un número pequeño de copias a pares que acepten, con las reglas siguientes:

1. El número de copias objetivo MUST derivarse de una tolerancia por ventana de reparación:

```text
q = 1 − exp(−W / T_host)          W: ventana de reparación; T_host: vida media de un nodo
r = ⌈ ln(1/ε) / ln(1/q) ⌉
```

2. Con `T_host = 91 días` [65] y `W = 7 días`, q ≈ 0.074; con `ε = EPS_DEFAULT` resulta r = 3.
3. Si el número estimado de poseedores de la cápsula, obtenido de los manifiestos, es menor que `RARE_HOLDERS_MAX`, se usa `ε = EPS_RARE` (r = 4 con los valores provisionales).
4. La ponderación por rareza MUST aplicarse solo a cápsulas con `preserve = true`, `epistemic_distance ≤ 1` y anclaje declarado.
5. Las copias MUST colocarse en nodos de operadores distintos cuando el perfil lo permita identificar, y el número total de copias que un nodo aloja para terceros MUST respetar `REPLICA_BUDGET_PER_NODE`.
6. El cálculo supone salidas independientes; una implementación SHOULD reportar la concentración de operadores de las copias.

---

## 14. Respuesta plural

### 14.1 Construcción

A partir del mapa de acuerdo por unidad que produce el consenso E16 del protocolo, el ensamblador MAY presentar, para una unidad con desacuerdo sistemático entre réplicas, la posición mayoritaria y una alternativa, y MAY añadir el contexto del usuario desde la proyección de tarea.

### 14.2 Reglas

1. Una posición alternativa MUST mostrarse solo si la sostienen al menos `PLURAL_MIN_FAMILIES` familias de modelo o evidencia anclada.
2. Toda posición MUST etiquetarse con la proporción de réplicas que la sostienen.
3. La respuesta MUST indicar que el acuerdo entre familias no prueba verdad y que el desacuerdo no prueba controversia.
4. La respuesta plural MUST reportarse en los metadatos de respuesta del protocolo:

```json
"plural": {
  "units": [
    { "unit": 7, "positions": [
        { "stance": "A", "share": 0.67, "families": ["qwen", "llama"] },
        { "stance": "B", "share": 0.33, "families": ["gemma"] } ] }
  ],
  "note": "agreement_is_not_truth"
}
```

### 14.3 Afirmaciones en disputa en la wiki

Una afirmación MAY marcarse `status: contested` con una lista `positions`, cada una con su postura, sus soportes (anclajes o cápsulas) y las familias que la sostienen. La recuperación de una afirmación en disputa MUST devolver todas sus posiciones.

---

## 15. Informes

### 15.1 Principio

Igual que el protocolo devuelve una auditoría de coherencia con cada respuesta (P6), la LCE reporta su costo y su efecto sobre la diversidad. Un beneficio sin su costo no es un resultado.

### 15.2 Informe de costo cognitivo (local)

Un Cliente LCE conformante MUST registrar, por petición: latencia de recuperación y proyección; bytes añadidos a Γ; carril antes y después de la reclasificación. Y por ciclo de consolidación: energía o tiempo de cómputo de digestión y entrenamiento; número de afirmaciones propuestas, ancladas y rechazadas por el verificador; candidatos entrenados; resultado de la compuerta. Y por cápsula: bytes recibidos y servidos.

### 15.3 Informe de diversidad (social)

Un nodo que participa en el plano social SHOULD calcular, y MAY publicar en forma agregada:

1. la fracción de su caché social y de su material de entrenamiento por vía de transmisión (vertical, horizontal, oblicua);
2. una estimación de F_ST entre los vecindarios que observa, con la definición operativa de generación usada;
3. la masa en las colas sobre el **conjunto canario**: fracción de regionalismos glosados correctamente, frecuencia de cada variante y tasa de violaciones de identidad.

El conjunto canario MUST NOT usarse como dato de entrenamiento ni como cápsula.

---

## 16. Escalones de hardware

| Escalón | Añade | Requisito orientativo |
|---|---|---|
| C0 | Swarmbly sin LCE | el del protocolo |
| C1 | wiki, recuperación, proyección, informes locales | CPU; almacenamiento del orden de GB |
| C2 | digestión automática | el modelo local que el cliente ya usa |
| C3 | caché social, afinidad, cápsulas | sin requisito adicional relevante |
| C4 | adaptador LoRA o QLoRA [16, 17] | memoria de un equipo de consumo de gama media; *a medir* |

Ningún escalón superior es requisito para participar en el protocolo. Los requisitos de memoria por tamaño de modelo que circulan en guías prácticas no proceden de literatura revisada y MUST medirse en el prototipo antes de publicarse como requisito.

---

## 17. Seguridad y canales residuales

1. **Adaptador.** Un adaptador personal MUST NOT transmitirse por la red ni servirse a terceros (I2). Su exposición por robo del dispositivo queda fuera del alcance.
2. **Cápsulas.** La firma prueba quién firmó, no que el contenido sea verdadero. Las cápsulas son datos, nunca instrucciones (12.3).
3. **Persistencia manipulable.** Un adversario con múltiples identidades puede inflar la persistencia de una cápsula pidiéndola y cacheándola. Es un canal residual declarado; el experimento C7 debe medirlo.
4. **Análisis de tráfico.** Las solicitudes de cápsulas revelan interés temático. Se atenúa pidiendo por temas amplios y cacheando; no se elimina.
5. **Bloque de capacidades.** Su límite de tamaño y su contenido grueso existen para impedir la fuga de identidad (sección 11).
6. **Historial.** El historial versionado conserva lo borrado salvo reescritura (6.8).

---

## 18. Códigos de error

Se reutilizan los códigos del SWIP (`E_COGNITIVE_DISABLED`, `E_CAPSULE_NOT_FOUND`, `E_CAPSULE_FORBIDDEN`, `E_CAPSULE_TOO_LARGE`, `E_CAPSULE_RATE_LIMITED`, `E_CAPSULE_BAD_SIGNATURE`, `E_CAPSULE_UNSUPPORTED`) y se añaden dos:

| Código | Significado | Acción del cliente |
|---|---|---|
| `E_CAPSULE_DISTANCE` | La cápsula tiene `epistemic_distance > 1` y se pidió para redistribuir o entrenar | Usarla solo como caché local o descartarla |
| `E_CAPSULE_NO_DELTA` | Cápsula descendiente sin `delta_evidence` | Tratarla como reformulación; no redistribuir |

Ningún fallo de cápsula MUST contarse como fallo de ejecución de una microtarea del protocolo.

---

## 19. Parámetros

| Parámetro | Valor por defecto | Origen | Estado |
|---|---|---|---|
| `CAPSULE_MAX_BYTES` | 16 384 | SWIP | normativo |
| `PROJECTION_MAX_BYTES` | 1 024 | elección de diseño | provisional |
| `EPISTEMIC_MAX_SHARE_TRAIN` | 1 | whitepaper 7.9 | normativo |
| `SOCIAL_TRAIN_FRACTION_MAX` | 0.5 (MUST); 0.2 (SHOULD) | [29, 31]; la cota fuerte es "minoritario" | provisional |
| `REPLAY_FRACTION` | > 0; 0.2–0.3 recomendado | [27]; a calibrar en C10 | provisional |
| `STABILITY_CYCLES` | 3 | elección de diseño | provisional |
| `MIN_NEW_EXAMPLES` | a calibrar | — | provisional |
| `N_CANDIDATES` | 3 (intensidad ≈ 0.85 σ) | whitepaper 5.6 | provisional |
| `GATE_MIN_GAIN` | 10 puntos | SWIP, C8 | provisional |
| `GATE_MAX_LOSS` | 2 puntos | SWIP, C8 | provisional |
| `GATE_MIN_ABSTAIN` | a calibrar | [14] | provisional |
| `FORGET_MAX_CYCLES` | 1 | whitepaper 5.8 | provisional |
| `AFFINITY_TAU` | 30 días | elección de diseño | provisional |
| `AFFINITY_BETA_MAX` | 0.2 | elección de diseño | provisional |
| `EXPLORATION_MIN_K` | 3 | E12, E17 | provisional |
| `NM_BAND` | 0.5–2.25 (F_ST ≈ 0.1–0.33) | [47, 49]; salvedades [48] | provisional |
| `T_HOST` | 91 días | [65] | parámetro de campo |
| `W` (ventana de reparación) | 7 días | elección de diseño | provisional |
| `EPS_DEFAULT` | 10⁻³ por ventana (r = 3) | whitepaper 7.2 | provisional |
| `EPS_RARE` | 10⁻⁴ por ventana (r = 4) | whitepaper 7.6 | provisional |
| `RARE_HOLDERS_MAX` | a calibrar en C6 | — | provisional |
| `REPLICA_BUDGET_PER_NODE` | a calibrar en C6 | — | provisional |
| `PLURAL_MIN_FAMILIES` | 2 | whitepaper 6.4 | provisional |

---

## 20. Cuestiones abiertas para la versión 0.2

1. Cómo ligar, si se decide hacerlo, alguna función social de la LCE a la contribución del nodo como worker sin reintroducir una economía de créditos compleja (whitepaper, sección 9.1).
2. Si conviene separar el SWIP en dos propuestas: una casi sin efecto en la red (capa local, proyección, reglas del worker) y otra para el bloque de capacidades y las cápsulas.
3. La definición operativa de "generación" para el informe de F_ST y su sensibilidad.
4. El verificador de anclajes: si basta un modelo distinto del digestor o hace falta una comprobación textual más estricta, y qué tasa de error es aceptable.
5. Las métricas de colas conceptuales que complementen al conjunto canario.
6. Si la afinidad debe considerar la correlación de errores observada entre pares, a la vista de [36].
7. El tratamiento de un usuario que también es operador de varios nodos, para la colocación de copias por operadores distintos.
8. La diversidad de evidencia entre réplicas como complemento de E12 frente a la correlación de errores entre familias. Pertenece al protocolo, no a la LCE (nota `FINDING_2026-10-04_correlated_errors_across_families_ES.md` del repositorio Swarmbly); una implementación de la LCE MUST NOT satisfacerla con memoria personal de los workers.

---

## 21. Implementación de referencia

El paquete `swarmbly_lce` implementa esta especificación; `lce_validation` contiene el arnés. La correspondencia es la siguiente.

| Sección | Módulo | Notas |
|---|---|---|
| 5 | `policy.py`, `sources.py` | política por prefijo más largo; claves desconocidas rechazadas |
| 6.2–6.6 | `claims.py` | máquina de estados con condiciones normativas; distancia por transformaciones |
| 6.3 | `anchors.py`, `digest.py` | verificación determinista más soporte léxico o por modelo |
| 6.7–6.8 | `depgraph.py`, `wiki.py` | invalidación en cascada; almacén JSON determinista apto para Git |
| 7 | `training.py` | elegibilidad, lotes con repaso, compuerta, registro de pruebas nuevas, olvido; `MLXLoRATrainer` experimental |
| 8 | `projection.py` | proyección sobre Γ, tope de bytes, doble clasificación |
| 9 | `worker.py` | `WorkerGuard` |
| 10 | `social.py`, `affinity.py` | regla de prevalencia con guarda de linealidad; afinidad con decaimiento y normalización |
| 11 | `profile.py` | bloque de capacidades |
| 12 | `capsules.py`, `canonical.py`, `crypto.py` | BLAKE2b sobre JSON canónico; Ed25519 con `cryptography` opcional |
| 13 | `persistence.py` | r desde ε; colocación por operadores distintos |
| 14 | `plural.py` | respuesta plural |
| 15 | `diversity.py`, `report.py` | F_ST, Wright, conformismo, canario, homogeneidad, concordancia de errores |
| 19 | `params.py` | parámetros normativos y provisionales |

`tests/test_invariants.py` contiene una prueba por invariante I1–I8. `lce_validation/run_all.py` ejecuta los diez instrumentos y los experimentos con backend simulado; `lce_validation/run_real.py`, los experimentos C1/C2 con modelos reales; los benchmarks (`bench_*.py`, `run_r13.py`, `bench_forget.py`, `aa_test.py`, `bench_r11.py`, `bench_c2bis.py`, `bench_hc2_closure.py`) con sus análisis (`r13_analysis.py`, `forget_analysis.py`); `run_derive.py`, que recalcula las cifras publicadas desde las salidas crudas; y `doc_figures.py`, que comprueba que cada cifra citada en los documentos coincide con ellas. Ningún resultado producido con `MockBackend` o por simulación es evidencia.

---

*Swarmbly LCE — Especificación versión 0.1 (borrador). Fundamento y evidencia: `WHITEPAPER_LCE_ES.md`. Texto bajo CC BY 4.0; cualquier implementación, bajo AGPL-3.0-or-later.*
