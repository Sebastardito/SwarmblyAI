---
status: current
lang: es
---
# Especificación del protocolo Swarmbly

**Versión 0.2 — 13 de agosto de 2026**
*Revisión 2, 14 de agosto de 2026: añade la sección 15c (niveles de privacidad y enjambres de confianza), los campos `tier` y `swarm_id` del paquete, el bloque opcional `swarm` del anuncio de nodo, el bloque `routing` de la respuesta y los códigos de error `E_TIER_VIOLATION`, `E_MTLS_REQUIRED` y `E_SWARM_UNKNOWN`. Toda adición es compatible a nivel MINOR según la sección 3: una implementación que ignore los campos nuevos se comporta exactamente como el nivel `GLOBAL`, de modo que la versión de protocolo sigue siendo `0.2`.*
Estado: **Borrador.** Normativa para la implementación de referencia; se espera que cambie antes de la v1.0.
Documentos complementarios: `WHITEPAPER_ES.md` (fundamento y evidencia), `SPEC_EN.md` (inglés).

Las palabras clave MUST, MUST NOT, REQUIRED, SHALL, SHOULD, SHOULD NOT, MAY y OPTIONAL deben interpretarse tal como se describe en RFC 2119. Se conservan deliberadamente en inglés y en mayúsculas, conforme a la práctica habitual en las especificaciones técnicas redactadas en español, para que su fuerza normativa sea inequívoca y coincida exactamente con la del texto de RFC 2119.

---

## 1. Alcance y no objetivos

Swarmbly es un protocolo para ejecutar una petición a un modelo de lenguaje descomponiéndola en microtareas semánticas, despachando esas microtareas a nodos trabajadores independientes que ejecutan cada uno un modelo pequeño completo, y reensamblando los resultados en el cliente solicitante.

**Dentro del alcance:** descomposición y planificación de la petición; los formatos de paquete, resultado y perfil; despacho, especulación y reintento; verificación de trabajadores no confiables; ensamblaje e informe de coherencia; encaminamiento basado en sensibilidad; contabilidad de créditos.

**Fuera del alcance (v0.2):** entrenamiento o ajuste fino de modelos; el transporte de descubrimiento de pares (MAY usarse cualquier DHT o mecanismo de encuentro); liquidación de pagos; un libro mayor de consenso. La v0.2 especifica deliberadamente **ninguna blockchain**.

**No objetivos explícitos.** El protocolo no proporciona confidencialidad criptográfica del contenido de la petición en los carriles PUBLIC o SANITISABLE; no proporciona resistencia fuerte a Sybil; y no reivindica paridad de latencia con la inferencia centralizada. Véanse las secciones 9 y 12 de `WHITEPAPER_ES.md`.

---

## 2. Terminología

| Término | Significado |
|---|---|
| **Petición** *P* | La entrada completa del usuario que debe responderse |
| **Plan** *D* = (V,E) | Grafo acíclico dirigido; los vértices son microtareas, las aristas son dependencias de resultado |
| **Microtarea** *tᵢ* | Un vértice del plan; la unidad de distribución |
| **Contrato global** Γ | Especificación compartida transmitida con cada paquete (sección 5) |
| **Paquete** *Kᵢ* | Lo que recibe un trabajador: Γ, los resúmenes de los predecesores y la microtarea |
| **Contig** *Rᵢ* | El resultado que un trabajador devuelve para una microtarea |
| **Costura** | La frontera entre dos contigs consecutivos en el ensamblaje |
| **Presupuesto de contexto** *S* | Tokens de contexto compartido por paquete |
| **Tasa de redundancia** ρ | Σ\|Kᵢ\| / \|P\| — el coste medido del presupuesto de contexto |
| **Carril** | PUBLIC, SANITISABLE o SENSITIVE — la clase de encaminamiento por confidencialidad del *contenido* |
| **Nivel** | GLOBAL, TRUSTED o LOCAL — la clase de encaminamiento de la *población de trabajadores* (sección 15c) |
| **Enjambre de confianza** | Submalla permisionada cuya pertenencia es una lista blanca de claves públicas bajo un operador declarado, con TLS mutuo en cada enlace |
| **Criticidad** *k* | Número de réplicas redundantes despachadas para una microtarea |
| **Orquestador** | El componente del lado del cliente que ejecuta las secciones 6 a 11 |
| **Trabajador** | Un nodo que ejecuta la sección 12 |

---

## 3. Versionado y conformidad

Todo mensaje lleva un campo `"v"` con la versión del protocolo como `MAJOR.MINOR`. Un participante MUST rechazar un mensaje cuya versión MAJOR no implemente. Un participante MUST ignorar los campos desconocidos dentro de un mensaje en lugar de rechazarlo, de modo que las adiciones MINOR sean retrocompatibles.

**Clases de conformidad.**

- Un **Trabajador Conformante** MUST implementar las secciones 7, 8, 12 y 13, y MUST emitir un compromiso de verificación cuando se solicite uno.
- Un **Orquestador Conformante** MUST implementar las secciones 5 a 11 y la sección 14, MUST implementar el router de la sección 6 (un cliente que siempre fragmenta es **no conformante**), y MUST devolver un informe de coherencia con cada respuesta.
- Una implementación que omita el informe de coherencia es no conformante. Esto es deliberado: la utilidad del protocolo depende de que su degradación sea observable.

---

## 4. Identificadores y criptografía

**Identidad de nodo.** Un par de claves Ed25519. `node_id` es la clave pública, en base64url sin relleno.

**Identidad de sesión.** `session_id` son 128 bits de un CSPRNG, generados por petición, nunca reutilizados y **nunca transmitidos a un trabajador**.

**Identidad de tarea.**

```
task_id    = hex( BLAKE2b(session_id || u16(level) || u16(index), digest_size=16) )
attempt_id = task_id || ":" || u8(attempt_counter)
```

La derivación es unidireccional para que dos trabajadores en colusión no puedan establecer que poseen fragmentos de la misma sesión comparando identificadores. Esto **no** anula la correlación temporal ni la huella digital del contrato; véase la sección 16.

**Firmas.** Los resultados MUST firmarse con la clave Ed25519 del trabajador sobre la serialización canónica (RFC 8785, JSON Canonicalization Scheme) de todos los campos que preceden a `sig`.

**Transporte.** Todos los intercambios MUST producirse sobre un canal cifrado y autenticado (TLS 1.3 o Noise). La seguridad del transporte es ortogonal a los límites de confidencialidad de la sección 15.

---

## 5. Contrato global Γ

```json
{
  "v": "0.2",
  "objective":  "string",
  "audience":   "string",
  "register":   "formal|neutral|informal|technical",
  "format":     "prose|markdown|json|code",
  "target_len": 1200,
  "lexicon":    { "prefer": ["…"], "forbid": ["…"] },
  "entities":   [ { "name": "…", "canonical": "…", "role": "…" } ],
  "style_seed": "string",
  "budget":     { "max_out_tokens": 600 }
}
```

`objective`, `register`, `format` y `entities` son REQUIRED; el resto son OPTIONAL.

`entities` es la tabla canónica de nomenclatura. Los trabajadores MUST usar la forma `canonical` para cualquier entidad listada. Esta es la defensa principal contra la denominación inconsistente entre fragmentos.

`style_seed` es una frase corta y fija que se instruye a todos los trabajadores para que igualen en registro. Cuesta pocos tokens y reduce la deriva de forma material.

**Γ MUST NOT recortarse para cumplir un presupuesto de contexto.** Si `S_target < |Γ|`, el orquestador MUST reducir en su lugar el número de microtareas (sección 9).

**Γ es el término dominante del presupuesto de contexto y, por tanto, la exposición de privacidad dominante.** Las implementaciones SHOULD minimizarlo, y MAY parafrasearlo por trabajador para dificultar la creación de huellas digitales, a costa de la consistencia entre fragmentos.

---

## 6. Router

```json
{ "decomposable": true, "score": 0.87, "threshold": 0.72, "features": { } }
```

El orquestador MUST evaluar la descomponibilidad antes de planificar y MUST disponer de una vía que se niegue a fragmentar. La clasificación de nivel (sección 15c) MUST preceder a la evaluación de descomponibilidad: una petición clasificada como `LOCAL` no se enruta nunca.

`threshold` MUST calibrarse con un objetivo asimétrico (F_β, β < 1) de modo que la fragmentación errónea se penalice más que la negativa errónea. Un umbral simétrico codificado de forma fija es no conformante.

Las características SHOULD incluir: señales de tipo de tarea; longitud de la petición; densidad de marcadores de dependencia secuencial; presencia de estado mutable compartido; y si la petición pide un único artefacto o un conjunto de elementos.

---

## 7. Plan

```json
{
  "v": "0.2",
  "nodes": [ { "task_id": "…", "level": 0, "instruction": "…",
               "kind": "extract|classify|generate|summarize|transform|judge",
               "criticality": 1, "lane": "PUBLIC" } ],
  "edges": [ { "from": "…", "to": "…", "type": "result|statement" } ]
}
```

Una arista de tipo `result` significa que el destino requiere la *salida* del origen y MUST planificarse después de él. Una arista de tipo `statement` significa que el destino solo requiere saber que el origen existe, y MAY planificarse de forma concurrente.

El plan MUST ser acíclico. El orquestador MUST negarse a fragmentar cuando la anchura del plan sea 1 en todos los niveles (una cadena no es paralelizable), y SHOULD negarse cuando la profundidad supere 4.

La anchura máxima por defecto es 8. La anchura incrementa la cola de rezagados (sección 11).

---

## 8. Paquete

```json
{
  "v": "0.2",
  "attempt_id": "…",
  "contract": { },
  "predecessors": [ { "task_id": "…", "summary": "…", "tokens": 128 } ],
  "task": { "instruction": "…", "kind": "generate",
            "expects": { "format": "markdown", "min_tokens": 80, "max_tokens": 400 } },
  "constraints": { "temperature": 0.2, "top_p": 0.95, "stop": [] },
  "commitment_request": { "scheme": "lsh-activation-v1", "params": { "window": 32 } },
  "deadline_ms": 20000,
  "lane": "PUBLIC",
  "tier": "GLOBAL",
  "swarm_id": null
}
```

Un paquete cuyo `lane` sea `SENSITIVE` MUST NOT transmitirse a un nodo fuera del conjunto atestiguado (sección 15). Un orquestador que emita uno es no conformante.

`tier` es ortogonal a `lane`: `lane` clasifica el contenido, `tier` nombra la población de trabajadores que el paquete puede alcanzar (sección 15c). `tier` toma `GLOBAL` por defecto. Un paquete con `tier` igual a `TRUSTED` MUST llevar un `swarm_id` no nulo y MUST NOT ofrecerse a un nodo ausente de la lista blanca de ese enjambre. Las peticiones clasificadas como `LOCAL` nunca se serializan como paquetes.

`predecessors[].summary` transporta resultados, no paquetes brutos de aguas arriba. Los resúmenes MUST producirse localmente por el orquestador.

---

## 9. Empaquetado y presupuesto de contexto

```
S           = |Γ| + E[ Σ |predecessors[].summary| ]
ρ           = ( Σᵢ |Kᵢ| ) / |P|
ρ_floor     = ( Σᵢ ( |taskᵢ| + |Γ_min| + |carryᵢ| ) ) / |P|
```

El orquestador MUST reportar la ρ alcanzada **y** ρ_floor en los metadatos de la respuesta.

### 9.1 Contenido obligatorio: qué es un paquete como mínimo

Tres partes de un paquete son **obligatorias**. Se cuentan dentro de ρ_floor y
nunca se financian con el margen discrecional, nunca se recortan y nunca se
omiten:

1. **El bloque de la microtarea.** Un paquete sin su tarea no es un paquete.
2. **La cabecera de contrato `Γ_min`** — la representación mínima de Γ
   (sección 5). Un fragmento puntuado contra un contrato que nunca recibió mide
   la *ausencia* del contrato, no el coste de fragmentar. Es la misma exigencia
   que la prohibición de recortar Γ de la sección 5, enunciada del lado del
   empaquetado.
3. **El acarreo**, para una microtarea dependiente que *consume el valor de un
   predecesor*. Una tarea cuyo texto dice «divide el valor neto del paso 2» no
   se puede responder sin ese valor. Un paquete que no puede enunciar el valor
   que su tarea consume es **irresoluble por construcción**, y ningún tamaño de
   fragmento lo arregla; **la resolubilidad manda sobre el presupuesto.** Por eso
   el acarreo se suma a ρ_floor en el mismo plano que el texto de la tarea, en
   vez de competir por el margen con el glosario como contexto ordinario.

El acarreo es obligatorio en función del **texto de la microtarea**, no de la
forma del plan. Un plan enumerado de ítems independientes es secuencial en su
forma pero no consume nada, y forzar la salida de un predecesor en paquetes que
no la necesitan hace que el sucesor la reformule como propia. Las
implementaciones MUST condicionar el acarreo obligatorio a que la tarea consuma
un valor de un predecesor, y SHOULD usar un acarreo tipado (`[02]=2247`) en vez
de un resumen en prosa: es la misma garantía a una fracción de los tokens, y es
lo que hace que el acarreo obligatorio resulte asequible en lugar de ser un
nuevo impuesto sobre ρ.

Todo lo demás —la nota de longitud, los resúmenes de predecesores no
consumidos, el glosario, la lista de términos prohibidos y el material de
expansión determinista con ρ alta— es **contexto discrecional**, adjuntado por
orden de prioridad con lo que quede.

### 9.2 Algoritmo de empaquetado (normativo)

Sea *B* = ρ_target · |P| el presupuesto total de las microtareas que se van a despachar.

1. Calcular `mandatoryᵢ` para cada microtarea: bloque de tarea + `Γ_min` +
   acarreo (sección 9.1).
2. Calcular `ρ_floor`. Si `ρ_target < ρ_floor`, la celda es **inalcanzable**:
   registrar `rho_reachable = false` y aplicar la sección 9.3. El orquestador
   MUST NOT satisfacer un objetivo inalcanzable recortando contenido
   obligatorio; o procede en el piso, o reduce el número de microtareas y
   replanifica.
3. `slack ← max(0, B − Σᵢ mandatoryᵢ)`.
4. Asignar `budgetᵢ ← mandatoryᵢ + slack · desiredᵢ / Σⱼ desiredⱼ`, donde
   `desiredᵢ` son los tokens que el paquete *i* consumiría sin racionamiento
   alguno. Un reparto uniforme de `B / N` no es conforme: hambrea precisamente
   a los paquetes que llevan dependencias.
5. Para cada paquete, fijar su presupuesto en `max(mandatoryᵢ, budgetᵢ)`, emitir
   el contenido obligatorio y adjuntar después los bloques discrecionales por
   orden de prioridad mientras quede sitio, truncando en un límite de token el
   primer bloque que no quepa y deteniéndose ahí.
6. Cuando un plan se despacha por niveles topológicos, cada nivel MUST recibir
   al menos la suma de sus propios `mandatoryᵢ`, y `desiredᵢ` MUST calcularse
   una sola vez a partir del plan. Recalcularlo por nivel permite que un nodo
   de integración tardío reclame margen que un nivel anterior ya había
   reservado, lo que sobrepasa ρ_target exactamente en esa cantidad y crece
   con *N*.
7. Ejecutar una pasada de corrección acotada para absorber el residuo que dejan
   los límites de bloque atómicos, y verificar después las invariantes de la
   sección 9.4.

Las implementaciones SHOULD preferir fragmentos menos numerosos y más grandes antes que muchos pequeños cuando el presupuesto sea restrictivo.

### 9.3 Una celda por debajo del piso no es una medición de ρ

Por debajo de ρ_floor no hay contexto que racionar: todo paquete se reduce a su
contenido obligatorio, de modo que **dos etiquetas ρ distintas producen paquetes
idénticos byte a byte.** Una celda cuyo objetivo queda por debajo de su propio
piso no lleva por tanto información alguna sobre ρ, sea cual sea el valor que
nombre su etiqueta, y una curva trazada a través de tales celdas informa de que
los paquetes que no llevan nada puntúan peor que los que llevan algo: una
afirmación verdadera sobre el contenido, y no una medición del presupuesto de
contexto.

En consecuencia:

- Una implementación MUST registrar `rho_reachable` por celda, a partir de un
  piso que incluya la cabecera de contrato y todo acarreo obligatorio.
- Una implementación **MUST rehusar reportar una cifra indexada por ρ calculada
  a partir de una celda por debajo del piso**, incluido cualquier agregado,
  media, tendencia o veredicto sobre un conjunto de celdas que contenga una.
  Descartar la fila es conforme; anotarla y publicarla de todos modos, no.
- Una implementación MUST NOT reportar `rho_reachable = true` a partir de un
  piso optimista que omita un acarreo que existirá en el momento del despacho.

### 9.4 Invariantes (normativo)

Antes del despacho, y para toda celda alcanzable, el orquestador MUST rehusar
continuar si no se cumplen las tres:

1. Todo paquete contiene su cabecera de contrato.
2. Toda microtarea que consuma el valor de un predecesor, y cuya dependencia
   haya producido un resumen, lo lleva.
3. La ρ alcanzada queda dentro de una tolerancia declarada respecto de
   ρ_target (la implementación de referencia usa el 5 %). ρ es la variable
   independiente; una celda fuera de tolerancia no es la celda que nombra su
   etiqueta.

Una violación es una negativa a despachar, no una advertencia. Estas
comprobaciones se dispensan para una celda **inalcanzable**, cuyos paquetes
están en el piso por definición y cuya ρ alcanzada sobrepasa necesariamente el
objetivo que no podía cumplir; tal celda puede despacharse igualmente, y la
sección 9.3 gobierna qué puede reportarse a partir de ella. Dispensar la
comprobación no es permiso para publicar la celda.

---

## 10. Resultado

```json
{
  "v": "0.2",
  "attempt_id": "…",
  "text": "…",
  "profile": { "model_family": "…", "model_version": "…", "quantization": "…",
               "prompt_template_id": "…", "sampling_params": { }, "seed": 0 },
  "commitment": { "scheme": "lsh-activation-v1", "digest": "base64", "bytes": 258 },
  "telemetry": { "gen_ms": 0, "queue_ms": 0, "tokens_out": 0, "energy_j": null },
  "sig": "base64"
}
```

El trabajador MUST reportar el perfil que realmente usó. El compromiso liga el perfil declarado al cómputo; un desajuste es un fallo de verificación, no un error de formato.

`energy_j` es OPTIONAL y anulable; la mayor parte del hardware doméstico no puede informarlo.

---

## 11. Despacho, especulación y reintento

1. **Filtrar** candidatos primero por `tier` —un paquete con `tier` igual a `TRUSTED` sólo se ofrece a nodos cuyo `node_id` figure en la lista blanca del enjambre nombrado por `swarm_id`, sobre un canal mutuamente autenticado— y después por soporte declarado de `kind`, clase de capacidad y RTT observado.
2. **Seleccionar** `k` nodos para una tarea de criticidad `k`, **maximizando la diversidad de familias de modelos** dentro de la clase de capacidad. La diversidad de candidatos es lo que hace efectiva la selección; las implementaciones MUST NOT concentrar las réplicas en una única familia de modelos cuando haya alternativas disponibles.
3. **Especular.** Arrancar un temporizador en el **p95** observado de la distribución de latencia *para ese tipo de tarea y ese presupuesto de tokens*. Al vencer, despachar una réplica adicional. Aceptar el primer resultado que verifique. Un tiempo de espera fijo es no conformante: con una probabilidad de fallo por nodo *p* y una anchura *W*, `P(≥1 fallo) = 1 − (1−p)^W`, que con *p*=0.10 y *W*=20 es el 88 %, de modo que un tiempo de espera fijo cae de forma rutinaria en la ruta crítica.
4. **Cancelar** las réplicas pendientes al aceptar, y registrar la cancelación como *lentitud*, no como *deshonestidad*. La reputación MUST distinguir ambas.
5. **Reintentar** ante un fallo de verificación, excluyendo al nodo que falló, y reportar el evento al muestreador de auditoría.

---

## 12. Anuncio de perfil de nodo

```json
{
  "node_id": "base64url",
  "models": [ { "family": "…", "version": "…", "quantization": "…",
                "ctx": 8192, "tok_per_s_est": 42.0 } ],
  "capabilities": { "tee": false, "attestation": null },
  "swarm": { "swarm_id": null, "registry": null, "mtls_cert_fingerprint": null },
  "resources": { "vram_mb": 8192, "ram_mb": 32768 },
  "policy": { "max_tokens_per_task": 800, "kinds": ["extract", "generate"] },
  "reputation": { "completed": 0, "audit_pass_rate": 0.0, "since": "2026-08-13T00:00:00Z" }
}
```

Un nodo MUST NOT aceptar una tarea cuyo `kind` no figure en `policy.kinds` o cuyo `expects.max_tokens` exceda `policy.max_tokens_per_task`.

La reputación es orientativa y la calculan el orquestador y el registro de forma independiente; la reputación autorreportada por un nodo MUST NOT considerarse fiable.

`swarm` es OPTIONAL y está ausente en un nodo que sólo sirve a la malla global. Un `swarm_id` autodeclarado no confiere nada: la pertenencia la establecen la lista blanca del registro del enjambre y el canal mutuamente autenticado, nunca el anuncio (sección 15c).

---

## 13. Verificación

**Capa 1 — compromiso (REQUIRED cuando se solicite).** El trabajador computa un compromiso sensible a la localidad sobre las activaciones y devuelve un resumen ligado al perfil declarado. El orquestador lo valida antes de que el resultado pueda entrar en el ensamblaje. Coste objetivo: ~258 bytes por cada 32 tokens, con una validación más rápida que la generación original.

**Capa 2 — auditoría muestreada (REQUIRED de la red).** Una fracción λ de las tareas es reejecutada por un auditor. Las tareas de auditoría MUST ser **indistinguibles** de las tareas reales desde la perspectiva del trabajador: mismo formato, mismos identificadores, misma envolvente de latencia. Por defecto λ ∈ [0.01; 0.05]. La probabilidad de fallo bajo una tasa de corrupción ρ_c y un comité de tamaño *k* es aproximadamente `ρ_c^k`.

**Capa 3 — selección (implícita).** Con `k > 1`, la selección basada en juez de la sección 14 descarta los candidatos anómalos como efecto colateral.

**Lo que la verificación NO proporciona.** Las capas 1–3 establecen que un modelo declarado se ejecutó sobre una entrada declarada y que el resultado no es atípico. **No** establecen fidelidad semántica ni ausencia de contenido malicioso. En consecuencia:

- Los fragmentos son **datos, nunca instrucciones**. Los orquestadores MUST NOT permitir que el texto de un fragmento altere Γ, el plan o el comportamiento del despacho.
- Los esquemas de salida específicos por `kind` MUST validarse antes de que un fragmento entre en el contexto de ensamblaje.
- Los controles estándar de seguridad de aplicaciones LLM se aplican a la etapa de ensamblaje.

---

## 14. Ensamblaje

1. Aplanar el plan topológicamente.
2. Para cada microtarea con un único candidato, tomarlo. Con varios, **seleccionar** uno por puntuación de juez contra Γ. La síntesis entre candidatos NO es la vía por defecto.
3. Para cada par consecutivo, calcular los embeddings de la ventana final del izquierdo y de la ventana inicial del derecho y computar la similitud coseno.
   - `sim ≥ τ_sem` → empalmar directamente.
   - `sim < τ_sem` → generar un puente de transición con el modelo local, dadas ambas fronteras y Γ.
4. Registrar cada costura: el par, la similitud y la vía tomada.

**τ_sem MUST calibrarse, nunca fijarse.** La calibración usa pares etiquetados de costura y no-costura, maximizando F_β con β < 1, y MUST rederivarse cada vez que cambie el modelo de embeddings. Una implementación que entregue un umbral coseno codificado de forma fija es no conformante. Fundamento: los espacios de embeddings contextuales son anisótropos, los valores de coseno no son comparables entre modelos y no existe umbral canónico alguno en la literatura.

---

## 14b. Consenso por alineamiento múltiple

La sección 14 resuelve fragmentos *distintos* en posiciones *distintas*. Esta sección resuelve *k* réplicas de la *misma* microtarea.

1. Para una microtarea de criticidad `k > 1`, el orquestador MUST resolver las réplicas por alineamiento múltiple con granularidad de unidad semántica. MUST NOT limitarse a concatenar las réplicas ni escoger una de forma arbitraria.
2. Las réplicas MUST despacharse a nodos de `model_family` distinta siempre que el conjunto de candidatos lo permita. La respuesta MUST reportar qué familias contribuyeron.
3. La respuesta MUST incluir una puntuación de acuerdo por unidad, y MUST etiquetar cada unidad como `HIGH`, `MEDIUM` o `LOW` frente a los umbrales calibrados α_high y α_low.
4. **α_high y α_low MUST calibrarse por modelo de embeddings, exactamente igual que τ_sem.** Una implementación que entregue umbrales de acuerdo codificados de forma fija es no conformante.
5. Las unidades que puntúen por debajo de α_low MUST exponerse al usuario como regiones de baja confianza. Suprimirlas es no conformante.
6. **Una implementación MUST NOT presentar una puntuación de acuerdo como una puntuación de exactitud o de veracidad.** El acuerdo entre réplicas es evidencia de convergencia, no de corrección; los modelos que comparten datos de entrenamiento comparten errores.
7. **Dividir una petición atómica en subpeticiones parciales NO es una operación soportada.** Un orquestador que lo haga es no conformante. Fundamento: elimina información antes del muestreo, y la redundancia no puede recuperar información que fue eliminada antes del muestreo.

---

## 15. Carriles de sensibilidad

| Carril | Criterio | Destinos permitidos |
|---|---|---|
| `PUBLIC` | Sin PII, sin secreto comercial | Cualquier trabajador conformante |
| `SANITISABLE` | PII detectable y seudonimizable | Cualquier trabajador conformante, tras la seudonimización local; rehidratado localmente en el ensamblaje |
| `SENSITIVE` | Salud, jurídico, financiero, identificable | Ejecución local, o un trabajador que presente una atestación TEE válida |

La clasificación MUST ejecutarse antes de que ningún paquete salga del dispositivo. Las tablas de correspondencia de seudonimización MUST NOT salir del dispositivo.

**Las implementaciones MUST NOT describir la fragmentación como cifrado en el texto dirigido al usuario.** El carril SANITISABLE reduce el riesgo; no lo elimina, y las interfaces SHOULD decirlo.

---

## 15b. Nodos ancla

Durante el arranque, la red MAY incluir capacidad alquilada operada por la fundación.

1. Tales nodos MUST etiquetarse como `anchor: true` en el registro.
2. La red MUST publicar la proporción del tráfico atendida por nodos ancla.
3. **Presentar el tráfico atendido por nodos ancla como atendido por la comunidad es no conformante.**

---

## 15c. Niveles de privacidad y enjambres de confianza

**Clasificación.** Toda petición MUST recibir un nivel antes de la planificación, mediante un clasificador que se ejecuta íntegramente en el dispositivo solicitante. Un clasificador que consulta a la red para decidir si una petición es privada es no conformante.

1. Una **bandera manual** (`--privacy=trusted`, `--privacy=local`) es autoritativa y MUST NOT ser anulada ni rebajada por el triaje automático.
2. El **triaje automático** MAY elevar un nivel al detectar localmente entidades nombradas de clases reguladas. MUST NOT rebajar ninguno.
3. Las implementaciones MUST NOT presentar el triaje automático como una certificación de ausencia de contenido sensible. Eleva un nivel; no exonera de ninguno.

**Niveles.**

| Nivel | Población | Transporte | Carriles permitidos |
|---|---|---|---|
| `GLOBAL` | Cualquier trabajador conformante del registro abierto | Identidad de trabajador autenticada; TLS del lado del servidor | `PUBLIC`, `SANITISABLE` |
| `TRUSTED` | Sólo nodos de la lista blanca de claves públicas del enjambre nombrado | **TLS mutuo REQUIRED** en cada enlace | `PUBLIC`, `SANITISABLE`, y `SENSITIVE` allí donde la política del enjambre y la ley aplicable lo permitan |
| `LOCAL` | Sólo el dispositivo solicitante | Sin salida a la red | Todos, incondicionalmente |

**Requisitos del enjambre de confianza.**

1. La pertenencia al enjambre MUST ser una lista blanca de claves públicas de nodo mantenida por un registro de enjambre bajo un operador declarado. La autodeclaración de pertenencia por parte de un nodo MUST ignorarse.
2. Cada enlace dentro de un enjambre de confianza MUST usar TLS mutuo. Un enlace que autentique un solo extremo es no conformante para `tier` igual a `TRUSTED`.
3. El compromiso de la sección 13, capa 1, sigue siendo **REQUIRED** dentro de un enjambre de confianza. El TLS mutuo autentica una identidad, no el modelo que hay detrás, y la pertenencia MUST NOT aceptarse como prueba de que se sirvió el perfil declarado.
4. Un enjambre de confianza MAY relajar la auditoría muestreada de la capa 2 y MAY reducir la criticidad *k*. MUST NOT relajar la capa 1.
5. Un enjambre de confianza MAY fijar `k = 1`. Cuando lo hace, los metadatos de la respuesta MUST reportar `consensus: null` con `consensus_waived_reason: "trusted_swarm_k1"`, y el cliente MUST exponer la ausencia de mapa de confianza en lugar de mostrar uno vacío o por defecto alto. Reportar un mapa de confianza que no se calculó es no conformante.
6. No obstante la regla 5, `k` MUST ser al menos 2 siempre que la tasa de pérdida medida del enjambre *p* supere la tolerancia configurada ε, puesto que `c_eff = c(1 − p)` no deja margen alguno con `c = 1`.
7. La holgura de latencia de un enjambre de confianza MUST NOT gastarse en un esquema de partición de grano más fino. Una implementación conformante ejecuta el mismo protocolo en todos los niveles y gasta esa holgura en el presupuesto de contexto *S* de la sección 9.

**Frontera de confianza.** Un enjambre de confianza reubica la confianza en el operador de la lista blanca. Quien administra el registro puede admitir un nodo; un miembro comprometido dentro del perímetro es más peligroso que un nodo no confiable fuera de él, porque la redundancia que lo habría detectado puede haberse reducido bajo la regla 5. Las implementaciones MUST NOT describir un enjambre de confianza como algo que elimina la necesidad de confiar en alguien.

---

## 16. Canales residuales conocidos

Declarados en lugar de ocultados:

1. **Correlación temporal.** Los fragmentos de una sesión se despachan en ráfaga. La derivación unidireccional de `task_id` no lo oculta. Mitigación: despacho con jitter, a costa de latencia.
2. **Huella digital del contrato.** Un Γ distintivo es en sí mismo un identificador de sesión entre los trabajadores que lo reciben. Mitigación: paráfrasis por trabajador, a costa de consistencia.
3. **Inferencia de contenido.** Un microprompt aislado puede ser sensible por sí solo, con independencia de la ausencia de contexto global.
4. **Concentración Sybil.** Véase la sección 17.

---

## 17. Modelo de confianza

- Los trabajadores son **no confiables** y se suponen racionales, no meramente defectuosos.
- El orquestador es de confianza únicamente para su propio usuario.
- El registro es **semiconfiable**: MAY censurar o sesgar el descubrimiento; los orquestadores SHOULD usar más de uno y SHOULD conservar una vista local.
- Dentro de un enjambre `TRUSTED`, los trabajadores están **autenticados y son responsables, pero siguen sin estar verificados**: la lista blanca acota *quién* puede servir, no *qué* sirvió. La capa 1 de la sección 13 se aplica, por tanto, en todos los niveles.
- **No se proporciona resistencia a Sybil.** Únicamente mitigación por capas: reputación acumulada, coste de entrada, auditoría muestreada con penalización económica y nodos ancla operados por la fundación para el arranque en frío. Las implementaciones MUST NOT reivindicar resistencia bizantina o a Sybil.

---

## 18. Créditos

No transferibles, no preminados, con caducidad. Se ganan con un fragmento aceptado y verificado; se gastan enviando una petición. Sin mercado secundario y sin transferencia entre cuentas. Los saldos caducan según un calendario publicado.

```json
{ "node_id": "…", "balance": 0, "earned_total": 0, "spent_total": 0,
  "expires": [ { "amount": 0, "at": "ISO-8601" } ] }
```

La conversión a moneda fiduciaria es unidireccional: las empresas compran capacidad a través de una capa comercial de servicio; los voluntarios no venden créditos. La intención de diseño es permanecer fuera de los regímenes de valores y criptoactivos; es un objetivo de diseño, **no asesoramiento jurídico**, y requiere asesoría legal en la jurisdicción de operación.

---

## 19. Metadatos de la respuesta

Toda respuesta MUST incluir:

```json
{
  "rho_achieved": 1.47,
  "rho_target": 1.50, "rho_floor": 1.31, "rho_reachable": true,
  "n_tasks": 6, "n_levels": 2,
  "tau_sem": 0.71, "tau_source": "calibrated:2026-08-13:e5-base",
  "seams": [ { "left": "…", "right": "…", "similarity": 0.68, "path": "bridge" } ],
  "coherence": { "entity_grid": 0.31, "seam_free_sentence_fraction": 0.94,
                 "errors": { "entity_omission": 0, "duplicated_content": 1 } },
  "verification": { "commitments_checked": 6, "failures": 0, "audited": 1 },
  "consensus": {
    "k": 3, "families": ["…", "…", "…"], "mean_agreement": 0.0,
    "units": [ { "label": "HIGH|MEDIUM|LOW", "agreement": 0.0 } ],
    "low_confidence_regions": [ { "unit_index": 0, "agreement": 0.0 } ]
  },
  "coverage": { "c": 0.0, "p_observed": 0.0, "c_eff": 0.0,
                "expected_uncovered_fraction": 0.0 },
  "routing": { "tier": "GLOBAL|TRUSTED|LOCAL", "swarm_id": null,
               "classifier": "manual|auto", "mtls": false },
  "consensus_waived_reason": null,
  "nodes": [ { "family": "…", "version": "…", "role": "worker" } ]
}
```

Omitir `coherence` es no conformante. Omitir `consensus` cuando `k > 1` es no conformante. Omitir `routing` es no conformante. Cuando `consensus` sea `null` porque el enjambre redujo *k* a 1, `consensus_waived_reason` MUST indicar por qué (sección 15c, regla 5).

Omitir `rho_floor` o `rho_reachable` es no conformante. Sin ellos, quien consuma la respuesta no puede saber si la celda midió el presupuesto de contexto en absoluto, que es la condición sobre la que gira la sección 9.3.

---

## 20. Códigos de error

| Código | Significado | Acción del orquestador |
|---|---|---|
| `E_KIND_UNSUPPORTED` | El trabajador no sirve este `kind` | Redespachar a otro; no es un fallo |
| `E_BUDGET_EXCEEDED` | `max_tokens` por encima de la política del nodo | Redespachar o replanificar |
| `E_DEADLINE` | Plazo vencido | La especulación ya se disparó; contar como lentitud |
| `E_COMMITMENT_UNSUPPORTED` | Esquema desconocido para el trabajador | Degradar a redundancia, o excluir |
| `E_VERIFY_FAILED` | Desajuste del compromiso | Excluir el nodo; reportar al muestreador de auditoría |
| `E_SCHEMA` | La salida viola `expects` | Reintentar una vez, luego excluir |
| `E_LANE_VIOLATION` | Paquete sensible ofrecido a un nodo abierto | **Abortar la petición.** Defecto de implementación |
| `E_TIER_VIOLATION` | Paquete `TRUSTED` ofrecido a un nodo ausente de la lista blanca del enjambre | **Abortar la petición.** Defecto de implementación |
| `E_MTLS_REQUIRED` | Enlace de enjambre de confianza presentado sin autenticación mutua | Rechazar el nodo; reportar al registro del enjambre |
| `E_SWARM_UNKNOWN` | `swarm_id` no resoluble en ningún registro configurado | Abortar; no recurrir a `GLOBAL` |

---

## 21. Cuestiones abiertas para la v1.0

1. El esquema de compromiso está especificado por interfaz, no por construcción; `lsh-activation-v1` necesita una definición normativa o una referencia normativa.
2. La federación del registro y la resistencia a la censura están sin especificar.
3. El calendario de caducidad de los créditos y la magnitud de las penalizaciones de auditoría están sin fijar, a la espera de la economía de una red en producción.
4. La compresión del contrato es el problema abierto de mayor apalancamiento: como Γ es simultáneamente el mecanismo de coherencia, la exposición de privacidad y el término de coste dominante, cualquier reducción de `|Γ|` a igual efecto mejora tres propiedades a la vez.
5. Que el orquestador pueda ser un modelo de clase 8 B con calidad aceptable está sin resolver y es objeto de la hipótesis H3 del whitepaper.
6. La granularidad de una unidad semántica —oración frente a cláusula— está sin resolver, y afecta materialmente tanto a la calidad del alineamiento de la sección 14b como a los parámetros del modelo de cobertura.
7. La correlación entre la puntuación de acuerdo de la sección 14b y la exactitud factual ya se ha medido, y **no se encontró relación alguna.** Contra un juez de clase par salió en *r* = −0.030 sobre 597 unidades semánticas; tres ejecuciones posteriores calificadas contra una clave de respuestas situaron la razón de momios común de Mantel-Haenszel en 3.47, luego 0.26, luego 1.24: por encima, por debajo y a caballo del 1 en la misma pregunta, que es ninguna señal medida tres veces. El mapa de confianza queda por tanto **retirado** como afirmación de fiabilidad, y sale del banco de pruebas V7. El mecanismo de la sección 14b sigue especificado y MAY reportarse, pero una implementación MUST reportar su salida como *acuerdo* y MUST NOT presentarla como exactitud, confianza ni garantía de fiabilidad. Lo que queda abierto no es si la correlación está ahí, sino si es posible recuperar en absoluto alguna señal por unidad de este tipo; un instrumento nuevo, y no repetir este, es la condición previa para reabrirlo.
8. La federación de registros de enjambres de confianza, la rotación de claves y la latencia de revocación están sin especificar. Mientras lo estén, el modo de fallo de la regla 1 de la sección 15c es una lista blanca desactualizada, no una sin autenticar.
9. Si un modelo de triaje de entidades nombradas lo bastante pequeño para ejecutarse en el dispositivo solicitante alcanza una exhaustividad aceptable sobre clases de entidades reguladas está sin medir, y la bandera manual existe precisamente porque está sin medir.

---

*Especificación v0.2 (revisión 2), 14 de agosto de 2026. Normativa para la implementación de referencia en `swarmbly_v0/`. Fundamento, evidencia y citas: `WHITEPAPER_ES.md`.*
