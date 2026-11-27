# Swarmbly App — Architecture

*[Español](#español) below.*

## 1. Positioning

Swarmbly App is a **thin integrator** and, by decision, **only one way to
participate in Swarmbly**. The protocol never depends on this application:

```
Swarmbly Ecosystem
├── SwarmblyAI   → distributed inference protocol (evolves independently)
├── SwarmblyLCE  → local cognitive extension (evolves independently)
└── SwarmblyApp  → UX + network: UI, local API, P2P, scheduler, observability
```

The app depends on `swarmbly-v0` and `swarmbly-lce` as pip packages pinned to
exact commits and never copies their code. It adds only what those projects do
not contain.

| Concern | Source |
|---|---|
| Tier classification, router, contract Γ, planner, typed carries, consensus (§14b), select-then-splice assembly (§14), entity-grid coherence | `swarmbly_v0` (reused as-is) |
| Lane classifier, `WorkerGuard` (I2), source space, policy, wiki | `swarmbly_lce` (reused as-is) |
| Plan admission, wire packets from fields, async scheduler, local model pool (`directory.py`) | **new** — `swarmbly_app/engine/` |
| Launcher: checks and consented setup before start (`scripts/launch.py`, standard library only) | **new** |
| Recommended configuration (`advisor.py`, `catalog.py`), system check and consented installs (`doctor.py`), Ollama downloads (`model_manager.py`) | **new** |
| mDNS discovery, TLS 1.3 + channel-bound Ed25519 handshake, node manager, worker | **new** — `swarmbly_app/p2p/` |
| Local API (REST + WS), security guard, UI, SQLite, hardware/model detection | **new** |

## 2. Processes and boundaries

```
┌──────────────────────────── one process ────────────────────────────┐
│ UI thread (uvicorn)    127.0.0.1:8765  REST + WS + web UI           │
│   └─ ApiGuard: Host allowlist · Origin check · session token · CSP  │
│ chat threads           one per request                              │
│ P2P loop (thread)      0.0.0.0:9765/TCP  TLS 1.3 · mDNS 5353/UDP    │
│   └─ node manager · discovery · scheduler · worker (executor pool)  │
└─────────────────────────────────────────────────────────────────────┘
```

The admin interface and the P2P service have independent sockets and access
rules. `swarmbly-app headless` runs the node without the UI.

## 3. A distributed request

```
chat → Orchestrator.run (chat thread)
  PRIVACY        tier (swarmbly_v0.classify) + lane (LCE classifier) — on device
  ROUTING        router (swarmbly_v0) + admission (structural partition only)
  PLANNING       swarmbly_v0.planner on the admitted prompt
  PACKETS        Γ minimal + task + consumed carry; privacy self-check
  NODE SELECTION family diversity → distinct machines → load → RTT
  DISPATCH       scheduler on the P2P loop: parallel by readiness,
                 k_min up front, hedges/retries up to k_max, per-node capacity
  VERIFICATION   signature + attempt id + schema (Layer-1: not available)
  CONSENSUS      swarmbly_v0.consensus when ≥2 replicas
  ASSEMBLY       swarmbly_v0.select_then_splice (lists: spliced, no bridges)
  COHERENCE      entity grid + seam statistics
  → SPEC §19 metadata + stage log → SQLite → WebSocket → monitor
```

Every stage reports `completed`, `partial`, `skipped` or `failed`; stages that
do not apply are skipped, never completed.

**Local pool.** With multi-model on, the scheduler sees a `Directory`: the
authenticated remote workers plus a `LocalPool` pseudo-peer that runs packets
on this computer's other models (`execute_local`, never counted as serving
others). Requests that may not leave the device use the pool alone; requests
that cannot be fragmented can still get whole-request replicas from several
local families, aligned by the same consensus.

**Node roles versus model roles (3.5, D-018).** These are two different ideas
and the code names them separately:

- **Model roles** (`swarmbly_app/roles.py`: `writer`, `search_terms`,
  `fusion`, `verifier`, `embeddings`) choose *which model does which job
  inside one answer*. They are local settings and never travel on the wire.
- **Node roles** (`swarmbly_app/node_roles.py`: `large_model`, `reasoner`,
  `search`, `corpus`) describe *what a worker machine can run*. They ride in
  the signed advertisement (`roles`) and, for a role task, in the packet as
  `constraints.role` / `constraints.think`, both MINOR-safe. In WP4a a node
  advertises only `large_model` (a shared model at or above
  `node_roles.large_model_min_b`, 7 B by default) and `reasoner` (a shared
  model the user marked in `node_roles.reasoner_models`), and only while the
  worker role is on. The local pool derives the same roles from its own
  models without the "shared" condition, so a role-aware plan can run on one
  node. WP4b adds two opt-in executors, off by default:
  - **search.** The worker advertises the engines its own
    `evidence.providers` and SearXNG URL can really use. A search task carries
    **only a public query** in a packet with no Γ, no predecessors and no
    conversation; the requester produces it with `strip_private_details` plus
    its glossary and private terms, and if no query without private terms can
    be produced nothing is sent. The worker accepts only one short line,
    requires a shared trusted circle (the explicit *my own devices* mode is
    refused), checks its own egress policy for each engine, and records the
    query it ran on behalf of `nodo <id>` in circle `<name>` in its own
    ledger. The requester receipt shows the query, circle and member, says the
    member ran it, and says the requester cannot verify which engine answered.
  - **corpus.** The owner picks one local project and the circles allowed to
    read it; only its display name and a size bucket (`S|M|L`, from document
    count) are advertised, so every admitted peer sees them. A corpus task is
    refused with `E_ROLE_UNAVAILABLE`, before retrieval, unless the requester
    is in a circle the corpus is shared with. Retrieval reads only that
    project's roots (never personal sources or another project) and returns at
    most five passages bounded in size with a neutral citation (document
    title and span id, never a path). The worker ledger records the passages
    sent to `nodo <id>` in circle `<name>`, their count and bytes.

Placement sends a role task only to workers that advertise the role; the
models considered are the ones the role names (for `reasoner`, the worker
also honours `think: true`). Roles are self-declared and never trust the
advertiser: the requester records per-role outcomes per node (`RoleStats`) and
deprioritises a node whose role failed recently. A role never widens circle
admission, egress, lane/tier or model-size rules. If no worker advertises a
`large_model`/`reasoner` role the task may run on the best generic worker,
and the metadata, the attempt and the receipt say «role X unavailable, ran on
Y»; `search`/`corpus` have no truthful substitute, so the step fails honestly
and the partial answer names it. A `reasoner` advertisement carries
`think: true` only when the worker's Ollama `/api/show` reports the model's
`thinking` capability (cached); a model that does not support it, or an
unknown capability, is advertised without the flag, the requester sends
`think` only when the chosen advertisement has it, and a worker whose backend
refuses thinking retries once without it and records `think: false`.
A step completed by a generic worker or by the local model is marked in
`steps` with `role_fallback` and `ran_on` (and in `role_fallbacks` /
`step_fallbacks` in the metadata and the receipt); a step with no output is
`failed`, its dependants are `blocked`, and the user sees the localised note
that names them, not the first raw backend error.

**Teams (3.5, D-019).** A **team** is a named, stored plan template: an
ordered list of steps, each with a name, an instruction template (`{request}`
is replaced by the user's message), an optional node role (`search`,
`corpus`, `large_model`, `reasoner`) and dependencies on **earlier** steps
only. The same template runs on one computer (its local model pool, when that
node has every role) or across circle members, by role, because it becomes an
ordinary plan of the existing requester-central scheduler. `teams.py` stores
them as JSON under `<data>/teams.json` for the user and `<project>/teams.json`
for a project, validated on load and on save (at most 12 steps, bounded names
and instructions, known roles, unique ids, no forward edge and therefore no
cycle); writes are atomic and mode 0600. Three built-in examples are shipped
in code, read-only, and can only be duplicated. `Orchestrator.run(team=…)`
replaces the router and the planner with the template; it does **not** replace
any gate: lane/tier, circle admission at the handshake and the worker, the
egress gate, passage rules, the WP4b public-query guard for `search` and the
corpus provenance rules run unchanged, and a role never widens a permission.
The wire stays 0.2: the steps travel as ordinary packets, and a team run
produces the same receipt as any other run.

**Honest partial results (3.5, D-019).** A step that cannot complete no
longer fails the whole request. `run_levels` keeps a per-step state
(`completed`, `failed`, `blocked`), records the honest reason (`node_lost`,
`deadline`, `policy_refusal`, `role_unavailable`, `no_worker`, `failed`),
marks every step that depends on a failed one as `blocked by <step>` and never
runs it, while independent steps continue. The orchestrator assembles the
steps that completed, appends a short note naming each missing step and why,
and reports `status` (`complete` / `partial` / `failed` when nothing usable
completed), `steps` (per-step status) and `missing_steps` in the metadata. A
receipt is unchanged in meaning: it lists only what was really sent. Recipe 4
keeps its per-item statuses; a failed wave marks its own items `failed` with
the reason and later waves still run. A user stop cancels the run and stays
`stopped`, never a partial answer. The requester is the coordinator: if it
goes away the run ends; there is no plan migration in 3.5.

**Data with code (recipe 5).** The approved script runs in the WebAssembly
sandbox with its working directory at the read-only `/data`, so a bare or
`./` relative read of a provided input resolves without changing the script
text. A fresh writable scratch is preopened at `/tmp` with `TMPDIR` pointing
there (openpyxl/xlsxwriter need it); it counts against the disk quota, is
never collected as output and is deleted with the run. `/out` is the only
collected output, and a relative write elsewhere is refused. The writer's
prompt shows the first CSV/TSV lines raw with the detected delimiter,
encoding and header-row fact, names each XLSX sheet with its header, and gives
one concrete read line with the exact `/data/<name>` path. Files left in
`/out` by a failed or trapped run are flagged `partial`, not shown as the
result; a failed script offers a corrected proposal, and nothing runs until
the user approves it.

**Public proposal and list preview.** The research guard keeps a private name
private in every form and treats the entity the question asks a public source
about as a public target. A passage-defined scientific name never takes a
word of that target or of a public glossary term as a genus, so a multi-word
entity stays contiguous and in question order; public-source words and its
year stay unless the year is a figure from the user's documents. A removed
term is reported once, without a sentence-initial imperative, and the list
preview uses the same private glossary entries and document names to flag
items and default to this device with the reason.

**Reciprocity credits (3.5, D-020).** A credit is a **signed, non-transferable
task receipt**, not money. When the requester accepts a verified result from a
worker that is a member of a shared, valid circle, it signs a receipt for that
worker: `receipt_id`, `circle_id`, `issuer`, `worker`, a BLAKE2b hash of the
attempt id (never task content), `tokens_out`, `generation_ms`, the model tag,
`issued_at` and `expires_at` (90 days by default, `credits.receipt_ttl_days`).
The signature is Ed25519 over canonical JSON with the existing identity
helpers. Nothing is issued for the local pool, for *my own devices* sends, for
rejected or degraded replicas, or for an executor that returned nothing; the
scheduler calls `credit.issue_for_attempt` only after verification and the
quality check accepted the replica. The receipt travels as `credit_receipt` on
the same TLS session (MINOR-safe, D-021) and is stored only if the signature,
the manifest membership of issuer and this worker, the addressee, the expiry
and the id are all valid. The wallet is local (`<data>/credits/wallet.json`,
0600, atomic writes, bounded to 256 receipts) and per circle; a receipt is one
indivisible courtesy unit, so `balance`, `earned` and `spent` count receipts.

Only the named worker can spend one, only in the same circle, by sending one
`credit_spend` just before a task to a member it already saw busy (a
concurrency refusal or a missed deadline): a receipt is never spent on an idle
worker. The receiver verifies it again
and, **only while busy**, lets that task wait for a slot while an uncredited
task is refused; a requester without credits is still served whenever a slot
is free. The spend is offered inside `dispatch_async` *after* circle admission
and `egress.check_call`, so a credit can never bypass admission, the egress
gate, lane/tier or any other policy. The spender marks the receipt spent. The
accepting worker reports `credit_spent` (receipt id and spender only) to the
issuer; the issuer keeps a bounded log (`<data>/credits/issued.json`) and flags
a receipt reported twice — by one worker or by different workers — in the
Swarm panel and the event bus (`credit.double_spend`). This is detection, not
prevention, and nothing is broadcast beyond the circle: no transfer API, no
token export, no market and no global ledger (SPEC §18, GOVERNANCE). A stolen
node key can spend that node's receipts until the owner revokes the member
(R-010).

## 4. Security model (summary)

- **Identity:** Ed25519 per node (`node_id` = public key), never the IP.
- **Channel:** TLS 1.3; the responder signs its certificate fingerprint and the
  initiator verifies it against the certificate received, then signs it back
  (detects a man in the middle). Replay protection by fresh nonces; per-peer
  attempt-id window; frame size cap; peer cap; keepalive.
- **Admission of peers:** a handshake authenticates; circle admission then
  authorises. In the default circle-only mode a peer must be listed by a
  valid, unexpired signed membership manifest that lists both nodes. It is
  checked at the handshake and again at the worker gate, so revocation takes
  effect. The explicit *my own devices* mode keeps the 3.4 LAN rule
  (any authenticated peer in the LAN). A valid invitation opens a
  control-only bootstrap session to send the signed join request; it never
  receives tasks. Worker gates (role, pause, kinds, budget, deadline,
  concurrency, lane/tier, idle) run in code for every packet.
- **Local API:** loopback by default; Host allowlist; Origin check on
  mutations and WebSocket; per-launch token; CSP; untrusted strings escaped.
- **Privacy:** LOCAL tier and SANITISABLE/SENSITIVE lanes never leave the
  device; packets never carry the session id or the complete request.
- **Credits (D-020).** Receipts are signed by their issuer and carry a hash of
the attempt id, never task content. The wallet is a local 0600 file, bounded,
and a receipt is spendable only by the named worker in the same circle. The
issuer's log detects a receipt reported spent twice; it does not prevent it
across nodes or across circles, and a stolen node key can spend that node's
receipts until revocation (R-010). There is no transfer, export, market or
global ledger.

**Peer sends and passages (D-017).** Every task packet passes
  `egress.check_call` with purpose `FRAGMENT` before it is written. Its
  destination class comes from the circle service, not the address:
  `CIRCLE` when the peer is listed by a valid shared manifest (the receipt
  names the circle and the member), `OWN_NETWORK` only in the explicit
  *my own devices* mode, and refused when neither holds, so an unclassified
  peer is never labelled. Document passages reach a peer only when the
  sender's per-circle `circle_passages` switch is on (off by default) or, in
  *my own devices* mode, when `circle.own_devices_passages` is on. These are
  separate from `privacy.third_party_passages`, which is about model
  services; enabling that flag never enables circle passages.

**Off-LAN through the circle relay (D-016/D-023).** A circle owner may set a
`relay` endpoint (`host`, `port` and the relay certificate's SHA-256 pin) in
the circle card. The endpoint and pin travel inside the signed manifest and
inside new invitations as MINOR-safe optional fields; a relay without a pin is
refused. Each member of a circle with a relay keeps one **idle acceptor**
connection per (circle, relay) registered with the relay's single-use signed
challenge, reconnecting with backoff; a manifest without a relay opens
nothing. The prototype can accept one splice per connection, so an outbound
pair opens a short, separate registered connection while the acceptor stays
reachable (bounded by `circle.relay_max_connections`). Direct addresses
(LAN discovery, manual `host:port`, manifest endpoint hints) are tried first
with `circle.reach_timeout_s`; only when none works does the App ask the relay
to pair. The two nodes then run their **normal** inner TLS 1.3 and
channel-bound Ed25519 handshake through the splice, so the relay forwards
ciphertext and cannot read a task. Admission, the worker gate and the WP2
egress gate are the same code paths as a direct peer; the relay is a transport
hop, not a new authorisation. The responder accepts a pair only from a node
listed by a current, shared manifest (the prototype's explicit `pair_accept`
is still required); it has no `pair_reject` frame, so a refusal closes the
connection. A pin mismatch stops that relay and raises a security warning; a
relay that is down never prevents a direct LAN peer from working.

**Owner push.** The operator installs the **first** signed manifest of a
circle on the relay once (the bootstrap copy in the relay's `circles/`
directory). After that the owner's App pushes every new signed version
(approval, revocation, relay change, dissolve, renewal) over a registered
connection with the relay's `manifest_update` frame, retrying with backoff
while the relay is unreachable. Only the newest unacknowledged version is
kept per target; a new version replaces an older pending one, and an ack
clears it. The circle card shows the acknowledged version, the pending
version and a refusal code with a one-line hint (`unknown_circle` means the
operator must install the first manifest, `rate_limited` is the relay's
30-per-hour owner cap, `stale_version` means the relay already has a newer
version). On a relay change the same new version is pushed to the relay named
in the **previous** manifest first and then to the new one, so the old relay
stops admitting removed members. The signed file in
`circle.relay_publish_dir` (default `<data>/circles/relay-publish`) remains
the operator's bootstrap copy and the fallback; the network push is the
primary path. The relay's own limits (4 concurrent splices, 2 GiB per member
per UTC day, 300 s idle, 30 s pair timeout, 30 owner pushes per hour) are
enforced by the service and surfaced in the circle card. A send that used the
relay carries the hop in its receipt: relay host/port and that it saw who,
when and how many bytes, never content.

## 5. Data directory

```
sources/  wiki/  adapters/  capsules/   LCE planes (local only)
output/   exports/ reports/             logical default output location
identity/ node_key (0600)               cache/tls/ node.crt, node.key (0600)
circles/ manifests, invitations, joins  api_token (0600)   logs/   app.db (SQLite)
circles/relay-publish/  signed manifests: operator bootstrap copy and fallback
credits/ wallet.json, issued.json (0600)  teams.json (0600)
<project>/teams.json (0600)
```

macOS `~/Library/Application Support/Swarmbly` · Linux `~/.local/share/swarmbly`
· Windows `%LOCALAPPDATA%\Swarmbly`. Override with `--data-dir`.

## 6. Decisions

| # | Decision | Date |
|---|---|---|
| Q1 | Local-first repository; the author publishes when ready | 2026-10-11 |
| Q2 | Upstream as pip dependencies pinned to audited commits | 2026-10-11 |
| Q3 | English UI by default, Spanish switchable | 2026-10-11 |
| Q4→D12 | Models downloaded only through Ollama (`/api/pull`), after explicit consent showing size, origin and licence | 2026-10-12 |
| Q5 | User data in the per-OS data directory | 2026-10-11 |
| D1 | Plan admission: structural partitions only | 2026-10-12 |
| D2 | Wire packets built from fields; Γ minimised | 2026-10-12 |
| D3 | Async scheduler; `k_min` (epistemic) / `k_max` (ceiling) | 2026-10-12 |
| D4 | Channel-bound handshake (SSH host-key model) | 2026-10-12 |
| D5 | API guard (Host/Origin/token/CSP) | 2026-10-12 |
| D11 | `constraints.model_family` extension + SWIP draft | 2026-10-12 |
| D8 | Rendezvous: VPS primary + Raspberry Pi secondary (Phase 3) | 2026-10-12 |
| D13 | Recommendations never enable the network, sharing or a tier; applying keeps a backup | 2026-10-12 |
| D14 | Installer limited to known Python packages in the app venv | 2026-10-12 |
| D-018 | Node roles (`large_model`, `reasoner`, `search`, `corpus`) are self-declared in the signed advertisement with validated metadata; placement tracks per-role success and roles never widen permissions | 2026-11-21 |
| D-020 | Credits are signed, non-transferable, expiring task receipts spent only by the named worker in the same circle; double spending is detected at the issuer, never prevented by a global ledger | 2026-11-21 |
| D-021 | Task plane stays wire 0.2; control and role extensions are MINOR-safe and ignored by older nodes | 2026-11-21 |

---

## Español

Swarmbly App es un integrador delgado y solo una de las maneras de participar
en Swarmbly. Reutiliza `swarmbly_v0` (clasificación de tier, router, Γ, plan,
consenso, ensamblaje, coherencia) y `swarmbly_lce` (clasificador de carril,
WorkerGuard) sin copiarlos, y añade la admisión de planes, los paquetes desde
campos, el planificador asíncrono, la red P2P, la API local protegida y la
interfaz. Cada etapa del pipeline informa completada, parcial, omitida o
fallida. La identidad del nodo es su clave Ed25519; el handshake liga esa
identidad al certificado TLS y detecta intermediarios. La API local valida
Host, Origin y un token por arranque. Cada paquete de tarea pasa por la puerta
de salida con clase `CIRCLE` (miembro de un círculo de confianza, nombrando
círculo y miembro), `OWN_NETWORK` solo en el modo explícito «mis propios
dispositivos», o se rechaza: un par fuera de todo círculo no se etiqueta. Los
pasajes de tus documentos solo llegan a un par con el interruptor por círculo
`circle_passages` encendido (apagado por defecto), o con
`circle.own_devices_passages` en el modo de dispositivos propios; nunca
reutilizan `privacy.third_party_passages`. Los **roles de nodo** (3.5, D-018:
`large_model`, `reasoner`, `search`, `corpus`) no son los roles de modelo por
respuesta de `roles.py` (writer, search_terms, fusion, verifier, embeddings):
describen lo que una máquina ofrece como worker, viajan en el anuncio firmado
(`roles`) y en el paquete (`constraints.role`/`constraints.think`), ambos
MINOR-safe, y solo sirven para colocación. En WP4a se anuncian `large_model`
(modelos compartidos con al menos `node_roles.large_model_min_b`, 7 B por
defecto) y `reasoner` (modelos compartidos marcados por el usuario); el pool
local deriva los mismos roles sin la condición de «compartido». El solicitante
solo envía una tarea con rol a un worker que lo anuncie, aprende por rol y por
nodo (`RoleStats`) y desprioriza a quien falló; un rol nunca amplía permisos.
Sin worker para `large_model`/`reasoner` se puede usar el mejor worker genérico
y el intento, los metadatos y el recibo dicen «rol X no disponible, ejecutado
en Y». El anuncio `reasoner` lleva `think: true` solo cuando el `/api/show` de
Ollama del worker informa la capacidad `thinking` del modelo (en caché); un
modelo que no la soporta, o una capacidad desconocida, se anuncia sin la
marca, el solicitante envía `think` solo si el anuncio elegido la lleva, y un
worker cuyo backend rechaza thinking reintenta una vez sin la marca y registra
`think: false`. Un paso completado por un worker genérico o por el modelo
local lleva `role_fallback` y `ran_on` en `steps` (y en `role_fallbacks` /
`step_fallbacks` de los metadatos y el recibo); un paso sin salida queda
`failed`, sus dependientes `blocked`, y el usuario lee la nota localizada que
los nombra, no el primer error técnico en inglés. WP4b añade los ejecutores
opt-in (por defecto, apagados):
**search** anuncia solo los motores que su configuración puede usar, recibe
solo una consulta pública de una línea en un paquete sin Γ, predecesores ni
conversación, exige un círculo de confianza (nunca «mis propios
dispositivos»), aplica su propia política de salida y registra en su ledger la
consulta hecha en nombre de `nodo <id>` del círculo `<name>`; el recibo del
solicitante muestra la consulta, el círculo y el miembro, y dice que no puede
verificar qué motor respondió. **corpus** comparte un proyecto local con uno o
más círculos y anuncia solo el nombre visible y el tamaño `S|M|L`; se niega
con `E_ROLE_UNAVAILABLE`, antes de recuperar nada, si el solicitante no está
en un círculo con el que se comparte, lee solo las raíces de ese proyecto y
devuelve hasta cinco pasajes acotados con cita neutral (título y span, nunca
ruta); su ledger registra los pasajes y bytes enviados a `nodo <id>` del
círculo `<name>`. Los pasajes devueltos son material de terceros para el
solicitante: se etiquetan con el miembro y el círculo reales, no entran en su
glosario ni memoria, y solo se reenvían a un nodo con `circle_passages`
encendido o a un servicio de modelos con `privacy.third_party_passages`; si
no, se ejecutan en local o la tarea falla honestamente.

**Datos con código (receta 5).** El script aprobado se ejecuta en el sandbox
WebAssembly con su directorio de trabajo en `/data` (solo lectura), así que
una lectura relativa por nombre o `./` de un archivo de entrada se resuelve
sin cambiar el texto aprobado. Un directorio temporal escribible nuevo se
preabre en `/tmp` con `TMPDIR` apuntando allí (openpyxl/xlsxwriter lo
necesitan); cuenta para la cuota de disco, nunca se recoge como salida y se
borra con la ejecución. `/out` es la única salida recogida y una escritura
relativa fuera de él se rechaza. El prompt del escritor muestra las primeras
líneas CSV/TSV tal cual, con el delimitador detectado, la codificación y si la
primera línea es cabecera, nombra cada hoja XLSX con su cabecera y da una
línea concreta de lectura con la ruta exacta `/data/<nombre>`. Los archivos
que deja una ejecución fallida o atrapada en `/out` se marcan `partial` y no
se presentan como resultado; un script fallido ofrece una propuesta corregida
y nada se ejecuta hasta que el usuario la apruebe.

**Consulta pública y vista previa de listas.** El guardián de investigación
mantiene privado un nombre en todas sus formas y trata la entidad que la
pregunta consulta en una fuente pública como objetivo público. Un nombre
científico definido por los pasajes nunca toma como género una palabra de ese
objetivo ni de un término público del glosario, así que una entidad de dos
palabras queda contigua y en el orden de la pregunta; las palabras de la
fuente pública y su año se quedan salvo que el año sea una cifra de los
documentos del usuario. Un término eliminado se informa una vez, sin un
imperativo inicial de la frase, y la vista previa de la lista usa las mismas
entradas privadas del glosario y nombres de documentos para marcar elementos
y proponer este equipo con la razón.

**Créditos de reciprocidad (3.5, D-020).** Un crédito es un **recibo de tarea
firmado y no transferible**, no dinero. Cuando el solicitante acepta un
resultado verificado de un worker que es miembro de un círculo compartido y
válido, firma un recibo para ese worker: `receipt_id`, `circle_id`, `issuer`,
`worker`, un hash BLAKE2b del id de intento (nunca el contenido de la tarea),
`tokens_out`, `generation_ms`, el modelo, `issued_at` y `expires_at` (90 días
por defecto, `credits.receipt_ttl_days`). La firma es Ed25519 sobre JSON
canónico con los ayudantes de identidad existentes. No se emite recibo para el
pool local, para el modo *mis propios dispositivos*, para réplicas rechazadas o
degradadas, ni para un ejecutor que no devolvió nada; el planificador llama a
`credit.issue_for_attempt` solo después de la verificación y de que el control
de calidad aceptó la réplica. El recibo viaja como `credit_receipt` en la misma
sesión TLS (MINOR-safe, D-021) y se guarda solo si la firma, la membresía de
emisor y worker en el manifiesto, el destinatario, la caducidad y el id son
válidos. La cartera es local (`<data>/credits/wallet.json`, 0600, escritura
atómica, acotada a 256 recibos) y por círculo; un recibo es una unidad de
cortesía indivisible, así que `balance`, `earned` y `spent` cuentan recibos.
Solo el worker nombrado puede gastarlo, solo en el mismo círculo, enviando un
`credit_spend` justo antes de una tarea a un miembro que ya vio ocupado (un
rechazo por límite de concurrencia o un plazo vencido): nunca se gasta un recibo
en un worker libre. El receptor lo verifica
otra vez y, **solo mientras está ocupado**, deja que esa tarea espere un turno
mientras una tarea sin crédito se rechaza; quien no tiene créditos sigue
siendo atendido si hay un turno libre. El gasto se ofrece dentro de
`dispatch_async` **después** de la admisión de círculo y de
`egress.check_call`, así que un crédito nunca salta admisión, puerta de
salida, carril/tier ni ninguna otra política. El gastador marca el recibo como
gastado. El worker que lo acepta reporta `credit_spent` (solo id de recibo y
gastador) al emisor; el emisor guarda un registro acotado
(`<data>/credits/issued.json`) y marca un recibo reportado dos veces —por un
worker o por workers distintos— en el panel Swarm y en el bus de eventos
(`credit.double_spend`). Es detección, no prevención, y nada se difunde fuera
del círculo: sin API de transferencia, sin exportar como token, sin mercado y
sin libro contable global (SPEC §18, GOVERNANCE). Una clave de nodo robada
puede gastar los recibos de ese nodo hasta que el dueño revoque al miembro
(R-010).

Las decisiones Q1–Q5,
D1–D14 y D-018/D-021 están en la tabla anterior.

**Equipos (3.5, D-019).** Un **equipo** es un plan guardado con nombre:
pasos ordenados, cada uno con nombre, una plantilla de instrucción (`{request}`
se sustituye por el mensaje del usuario), un rol de nodo opcional (`search`,
`corpus`, `large_model`, `reasoner`) y dependencias solo de pasos
**anteriores**. El mismo equipo corre en una computadora (su pool local,
cuando ese nodo tiene todos los roles) o entre miembros de un círculo, por
rol, porque se convierte en un plan ordinario del planificador central
existente. `teams.py` los guarda como JSON en `<data>/teams.json` y, por
proyecto, en `<project>/teams.json`, validados al cargar y al guardar (como
mucho 12 pasos, nombres e instrucciones acotados, roles conocidos, ids únicos,
sin dependencias hacia adelante y por tanto sin ciclos); la escritura es
atómica y con modo 0600. Hay tres ejemplos incorporados, de solo lectura, que
solo se pueden duplicar. `Orchestrator.run(team=…)` sustituye al router y al
planificador por la plantilla, pero **no** sustituye ninguna puerta: carril y
tier, admisión de círculo en el handshake y en el worker, puerta de salida,
reglas de pasajes, la protección de consulta pública de `search` (WP4b) y la
procedencia del corpus siguen igual, y un rol nunca amplía un permiso. El wire
sigue en 0.2: los pasos viajan como paquetes ordinarios y el recibo es el
mismo.

**Resultados parciales honestos (3.5, D-019).** Un paso que no puede
completarse ya no hace fallar toda la solicitud. `run_levels` guarda el estado
de cada paso (`completed`, `failed`, `blocked`), registra la razón honesta
(`node_lost`, `deadline`, `policy_refusal`, `role_unavailable`, `no_worker`,
`failed`), marca cada paso que depende de uno fallido como `blocked by
<step>` y no lo ejecuta, mientras los pasos independientes continúan. El
orquestador ensambla los pasos completados, añade una nota corta que nombra
cada paso faltante y su razón, e informa `status` (`complete` / `partial` /
`failed` cuando nada utilizable se completó), `steps` (estado por paso) y
`missing_steps` en los metadatos. El recibo conserva su significado: solo
enumera lo que realmente se envió. La receta 4 conserva sus estados por
elemento; una ola fallida marca sus elementos como `failed` con la razón y las
olas siguientes siguen. Una parada del usuario cancela la ejecución y queda
`stopped`, nunca una respuesta parcial. El solicitante es el coordinador: si
desaparece, la ejecución termina; no hay migración de plan en 3.5.
