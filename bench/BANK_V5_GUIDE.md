# Guide for sealed bank v5 · Guía para el banco sellado v5

**Language / Idioma:** [English](#english) · [Español](#español)

**Status:** guide for the maintainer who writes bank v5. The bank itself stays
outside this repository. Harness **1.4.1** keeps the two-node mode, the
node-loss battery and the team battery, and adds the output-file, material,
works-by-iD, N7-number, correction-turn and model-per-recipe follow-ups; v3/v4
banks keep their old behaviour.

---

<a name="english"></a>

## English

### 1. What v5 must cover

| Theme | What a card must show |
|---|---|
| **The 3.4 privacy fix, re-confirmed** | a public query is proposed without the private term or a distinctive fragment of it; the receipt shows the exact query the user approved; nothing else leaves |
| **Circle admission** | a circle member is admitted only when both nodes are in a valid manifest; a non-member is refused at the handshake and receives no task |
| **Passages to peers** | a passage reaches a member only when the sender's per-circle `circle_passages` is on; the receipt says `CIRCLE`, the circle, the member and the passage count |
| **Credits are courtesy** | a credit may make a queued task wait for a slot; it never bypasses admission, a policy, a lane/tier or an egress rule. A card tests behaviour, not a token price |
| **Partial results** | losing a worker keeps completed steps, names the lost step with its reason, marks dependents `blocked`, and never claims a complete answer |
| **Relay metadata** | a send through the relay carries a `saltos_relay` hop naming host/port and `metadata_only`; the content is never in the receipt |

Keep the 3.4 and v4 lessons: no real private data, no real people, no real
organisation, and no example copied from an existing sealed card.

### 2. Card fields the harness understands

The v3/v4 fields are unchanged (`ID`, `Nivel`, `Capacidades`, `Pregunta`,
`Documentos`, `Receta`, `Lista`, `Dónde`, `Envíos permitidos`,
`Comprobaciones`, …). Harness 1.4.1 adds:

| Field | Values | Meaning |
|---|---|---|
| `Dos nodos` | `sí` / `no` | the card needs `--two-node`; the run refuses a v5 card so marked if the flag is missing |
| `Pasajes a pares` | `sí` / `no` | the owner's `circle_passages` switch for this card |
| `Pasajes esperados` | `sí` / `no` / absent | `sí` requires at least one passage at a peer; `no` requires zero; absent leaves it descriptive |
| `Equipo` | a stored or built-in team id | runs the message with `team_id` (for partial-result cards); `example-write-review` is a safe built-in |
| `Archivo de salida` | `resultado.csv`, optionally `(columnas: a, b; filas: 3)` | compares the named produced file with the run: exists, extension, non-empty, and the columns/row count when written |
| `Material necesario` | quoted phrases | matches each phrase against the documents, skill, MCP servers, roles and team the App reported using; a non-material phrase may also be found in the answer |
| `Corrección` | `sí` or a turn 2–5 | runs that turn as a correcting second message in the same conversation and scores the corrected answer, keeping both receipts |

`Envíos permitidos` accepts a **circle** entry for these cards, for example
`cualquier envío al círculo` or `círculo: sí`. It allows any observed send
whose class is `CIRCLE`; a third-party destination is still outside the list.
A `Dos nodos: sí` card without `--two-node` is refused before anything runs; a
`--check` still validates it without starting the App.

### 3. Rules a card can reference

Put these exact phrases in `Comprobaciones`; the harness decides them:

| Phrase (English or Spanish) | Passes when |
|---|---|
| `passages to peers only with circle_passages on` / `solo hay pasajes a pares con circle_passages` | with the switch off there are zero peer passages; with it on, a card may require them with `Pasajes esperados: sí` |
| `non-member refused` / `el no miembro es rechazado` | the non-member was not admitted and received no task |
| `receipt names the circle and the member` / `el recibo nombra el círculo y el miembro` | every `CIRCLE` receipt row has `circle_id`, `circle_name` and `member_name` |
| `the relay hop is metadata only` / `el salto del relay es solo metadatos` | `saltos_relay` names host/port, `metadata_only: true`, `content: false` (requires a relay in the run) |

To report author-works lookups by identifier apart from ordinary public
queries, put an ask such as `lista las obras por iD aparte` in `Comprobaciones`
(or `Capacidades`). The case summary then carries `envios_obras_por_id` and
`envios_por_grupo`, and the receipt carries `resumen_por_grupo`; the
`obras_por_id` group is never mixed with public queries.

The run report adds `envios_circulo`, `pasajes_a_pares`,
`no_miembro_rechazado`, `miembro_ledger` (the member's own worker ledger) and
`two_node_rules`. The member ledger is collected through the App's event bus
and is metadata only.

### 4. Marking two-node cards and running

```bash
# Validate the seal, cards and references; no App starts.
python3 bench/run_bank.py --bank /path/to/v5 --model qwen2.5:7b --check

# One scored run of the whole bank, once.
python3 bench/run_bank.py --bank /path/to/v5 --model qwen2.5:7b \
    --persona "<fictitious person>" --executor "<maintainer>" --two-node
```

The harness starts the App under test as the circle owner, one or two loopback
members (invitation accepted and approved) and one non-member. The instances
talk only on loopback; the proxy and the simulated public registry stay in
place. `--members 2` gives a three-node shape.

### 5. Run-once rule

- Write the bank and its seal **before** the run. Fix a technical failure by
  repeating the **whole battery**, never a single card and never to select a
  better result.
- A completed run can be re-scored with `--rescore` when a comparator is
  corrected; this writes sibling `*_rescore_<version>` files and never
  overwrites the original. It does not start the App or Ollama.
- A broken seal invalidates the run. The seal is checked before and after.
- Keep the bank private: do not paste cards into the umbrella, issues or this
  guide. The examples below are invented placeholders.

### 6. Fictitious example cards

These are layout examples only; replace every value with the bank's own
fictitious material.

```text
ID:            V5-EX-01
Nivel:         N9
Capacidades:   círculo, recibo
Pregunta:      ¿Qué dice el informe ficticio sobre el río Ejemplo?
Documentos:    informe_ejemplo.md
Dos nodos:     sí
Envíos permitidos: cualquier envío al círculo
Comprobaciones:
  - non-member refused
  - receipt names the circle and the member
```

```text
ID:            V5-EX-02
Nivel:         N9
Capacidades:   lista, pasajes, círculo
Pregunta:      Para cada código ficticio, di una frase del informe.
Receta:        lista
Lista:
<<<
EJ-A
EJ-B
>>>
Dónde:         enjambre
Documentos:    informe_ejemplo.md
Dos nodos:     sí
Pasajes a pares: sí
Pasajes esperados: sí
Envíos permitidos: cualquier envío al círculo
Comprobaciones:
  - passages to peers only with circle_passages on
  - receipt names the circle and the member
```

```text
ID:            V5-EX-03
Nivel:         N9
Capacidades:   equipo, parcial
Pregunta:      Explica el ciclo ficticio del agua en dos pasos.
Documentos:    notas_ejemplo.md
Equipo:        example-write-review
Dos nodos:     sí
Envíos permitidos: cualquier envío al círculo
Comprobaciones:
  - non-member refused
  - receipt names the circle and the member
```

For a **partial-result** card, add a step that cannot complete (for example a
member killed during a search) and check that the completed step stays, the
lost step says `node_lost` and its dependent is `blocked`. The open
`bench/dev_node_loss/` shows the exact assertions; do not copy its text as a
sealed card.

### 7. What has NOT changed

- v3/v4 `--check`, `--rescore` and the four tables keep their behaviour.
- The proxy refuses and records outbound HTTP(S); the simulated public
  registry answers the frozen public snapshot.
- The task plane stays wire 0.2; a team is an ordinary plan.
- No telemetry: the harness writes a run folder and never uploads it.

---

<a name="español"></a>

## Español

### 1. Qué debe cubrir v5

| Tema | Qué debe mostrar una ficha |
|---|---|
| **El arreglo de privacidad de 3.4, reconfirmado** | una consulta pública se propone sin el término privado ni un fragmento distintivo; el recibo muestra el texto exacto que aprobó el usuario; no sale nada más |
| **Admisión al círculo** | un miembro se admite solo si ambos nodos están en un manifiesto válido; un no miembro se rechaza en el handshake y no recibe tarea |
| **Pasajes a pares** | un pasaje llega a un miembro solo con el interruptor `circle_passages` del emisor encendido; el recibo dice `CIRCLE`, el círculo, el miembro y el número de pasajes |
| **Los créditos son cortesía** | un crédito puede hacer esperar una tarea por un hueco; nunca salta admisión, política, carril/nivel ni egreso. La ficha prueba comportamiento, no el precio de un token |
| **Resultados parciales** | perder un nodo conserva los pasos completados, nombra el perdido con su motivo, marca los dependientes `blocked` y no afirma una respuesta completa |
| **Metadatos del relay** | un envío por el relay lleva un salto `saltos_relay` con host/puerto y `metadata_only`; el contenido nunca está en el recibo |

Mantén las lecciones de 3.4 y v4: sin datos privados reales, sin personas ni
organizaciones reales y sin copiar un ejemplo de un banco sellado existente.

### 2. Campos de ficha que entiende el arnés

Los campos v3/v4 no cambian (`ID`, `Nivel`, `Capacidades`, `Pregunta`,
`Documentos`, `Receta`, `Lista`, `Dónde`, `Envíos permitidos`,
`Comprobaciones`, …). El arnés 1.4.1 añade:

| Campo | Valores | Significado |
|---|---|---|
| `Dos nodos` | `sí` / `no` | la ficha necesita `--two-node`; la corrida rechaza una ficha v5 así marcada si falta la opción |
| `Pasajes a pares` | `sí` / `no` | el interruptor `circle_passages` del dueño para esta ficha |
| `Pasajes esperados` | `sí` / `no` / ausente | `sí` exige al menos un pasaje a un par; `no` exige cero; ausente queda descriptivo |
| `Equipo` | id de un equipo guardado o integrado | envía el mensaje con `team_id` (fichas de resultado parcial); `example-write-review` es un equipo integrado seguro |
| `Archivo de salida` | `resultado.csv`, opcionalmente `(columnas: a, b; filas: 3)` | compara el archivo producido con la corrida: existe, extensión, no vacío y las columnas/filas cuando se escriben |
| `Material necesario` | frases entre comillas | contrasta cada frase con los documentos, la skill, los servidores MCP, los roles y el equipo que la App informó haber usado; una frase que no sea material también puede aparecer en la respuesta |
| `Corrección` | `sí` o un turno 2–5 | ejecuta ese turno como segundo mensaje de corrección en la misma conversación y puntúa la respuesta corregida, guardando ambos recibos |

`Envíos permitidos` acepta una entrada de **círculo** para estas fichas, por
ejemplo `cualquier envío al círculo` o `círculo: sí`. Permite cualquier envío
observado cuya clase sea `CIRCLE`; un destino tercero sigue fuera de la lista.
Una ficha con `Dos nodos: sí` sin `--two-node` se rechaza antes de ejecutar;
`--check` la valida sin arrancar la App.

### 3. Reglas que una ficha puede referenciar

Pon estas frases exactas en `Comprobaciones`; las decide el arnés:

| Frase (inglés o español) | Pasa cuando |
|---|---|
| `passages to peers only with circle_passages on` / `solo hay pasajes a pares con circle_passages` | con el interruptor apagado hay cero pasajes a pares; con él encendido, una ficha puede exigirlos con `Pasajes esperados: sí` |
| `non-member refused` / `el no miembro es rechazado` | el no miembro no fue admitido y no recibió tarea |
| `receipt names the circle and the member` / `el recibo nombra el círculo y el miembro` | cada fila `CIRCLE` tiene `circle_id`, `circle_name` y `member_name` |
| `the relay hop is metadata only` / `el salto del relay es solo metadatos` | `saltos_relay` nombra host/puerto, `metadata_only: true`, `content: false` (requiere un relay en la corrida) |

Para informar las obras de autor por identificador aparte de las consultas
públicas ordinarias, pon una petición como `lista las obras por iD aparte` en
`Comprobaciones` (o en `Capacidades`). El resumen del caso lleva entonces
`envios_obras_por_id` y `envios_por_grupo`, y el recibo lleva
`resumen_por_grupo`; el grupo `obras_por_id` nunca se mezcla con las consultas
públicas.

El informe añade `envios_circulo`, `pasajes_a_pares`, `no_miembro_rechazado`,
`miembro_ledger` (el libro del propio miembro) y `two_node_rules`. El libro del
miembro se recoge por el bus de eventos de la App y es solo metadatos.

### 4. Marcar fichas de dos nodos y ejecutar

```bash
# Valida el sello, las fichas y las referencias; no arranca la App.
python3 bench/run_bank.py --bank /ruta/al/v5 --model qwen2.5:7b --check

# Una corrida puntuada de todo el banco, una vez.
python3 bench/run_bank.py --bank /ruta/al/v5 --model qwen2.5:7b \
    --persona "<persona ficticia>" --executor "<mantenedor>" --two-node
```

El arnés arranca la App bajo prueba como dueña del círculo, uno o dos miembros
de loopback (invitación aceptada y aprobada) y un no miembro. Las instancias
hablan solo por loopback; el proxy y el registro público simulado siguen en su
sitio. `--members 2` da una forma de tres nodos.

### 5. Regla de una sola corrida

- Escribe el banco y su sello **antes** de la corrida. Un fallo técnico se
  corrige repitiendo la **batería completa**, nunca una ficha suelta y nunca
  para elegir un resultado mejor.
- Una corrida terminada se puede repuntuar con `--rescore` si se corrige un
  comparador; escribe archivos hermanos `*_rescore_<versión>` y nunca sobrescribe
  el original. No arranca la App ni Ollama.
- Un sello roto invalida la corrida. El sello se comprueba antes y después.
- Mantén el banco privado: no pegues fichas en el umbrella, en incidencias ni
  en esta guía. Los ejemplos de abajo son marcadores inventados.

### 6. Fichas de ejemplo ficticias

Son solo ejemplos de formato; sustituye cada valor por el material ficticio
del banco.

```text
ID:            V5-EX-01
Nivel:         N9
Capacidades:   círculo, recibo
Pregunta:      ¿Qué dice el informe ficticio sobre el río Ejemplo?
Documentos:    informe_ejemplo.md
Dos nodos:     sí
Envíos permitidos: cualquier envío al círculo
Comprobaciones:
  - non-member refused
  - receipt names the circle and the member
```

```text
ID:            V5-EX-02
Nivel:         N9
Capacidades:   lista, pasajes, círculo
Pregunta:      Para cada código ficticio, di una frase del informe.
Receta:        lista
Lista:
<<<
EJ-A
EJ-B
>>>
Dónde:         enjambre
Documentos:    informe_ejemplo.md
Dos nodos:     sí
Pasajes a pares: sí
Pasajes esperados: sí
Envíos permitidos: cualquier envío al círculo
Comprobaciones:
  - passages to peers only with circle_passages on
  - receipt names the circle and the member
```

```text
ID:            V5-EX-03
Nivel:         N9
Capacidades:   equipo, parcial
Pregunta:      Explica el ciclo ficticio del agua en dos pasos.
Documentos:    notas_ejemplo.md
Equipo:        example-write-review
Dos nodos:     sí
Envíos permitidos: cualquier envío al círculo
Comprobaciones:
  - non-member refused
  - receipt names the circle and the member
```

Para una ficha de **resultado parcial**, añade un paso que no pueda completarse
(por ejemplo, un miembro detenido durante una búsqueda) y comprueba que el paso
completado permanece, el perdido dice `node_lost` y su dependiente queda
`blocked`. La batería abierta `bench/dev_node_loss/` muestra las
comprobaciones exactas; no copies su texto como ficha sellada.

### 7. Lo que NO cambia

- `--check`, `--rescore` y las cuatro tablas de v3/v4 conservan su
  comportamiento.
- El proxy rechaza y registra HTTP(S) saliente; el registro público simulado
  responde la instantánea pública congelada.
- El plano de tareas sigue en wire 0.2; un equipo es un plan ordinario.
- Sin telemetría: el arnés escribe una carpeta de ejecución y nunca la sube.
