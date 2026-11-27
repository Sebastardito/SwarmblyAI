# Known limitations (v0.2.x)

Limitations are documented, never hidden. *[Español](#español) below.*

## Swarmbly App

1. **Only structured requests are fragmented.** A request is distributed only
   when it has a structural partition: an enumerated batch (labelled items, or
   an inline list the app rewrites losslessly into labelled items) or questions
   linked to the material that answers them. Free prose is answered locally,
   with the reason shown. This is deliberate: the alternative is slicing text,
   which SPEC §14b.7 forbids (see `AUDIT_FASE0_ES.md`, H3).
2. **Distributed requests are single-turn.** The last user message is
   fragmented; earlier turns are not packed into the plan.
3. **Off-LAN is a circle relay, not an internet swarm.** A circle with a relay
   can reach its members across networks (3.5, D-016), but there is no public
   rendezvous, NAT traversal or hole punching (3.6), and mode `internet` is
   still refused honestly. The relay is operated by the circle owner and sees
   metadata only (items 33–36 below).
4. **TRUSTED tier needs mutual TLS** (SPEC §15c) and is not implemented; such
   requests are answered locally and nothing is sent. Automatic triage that
   raises a request to TRUSTED with no trusted swarm configured also stays local
   (`E_SWARM_UNKNOWN`: never fall back to GLOBAL).
5. **SANITISABLE content stays local.** Pseudonymisation is not implemented;
   content the lane classifier marks SANITISABLE or SENSITIVE never leaves the
   device. The lane classifier is the LCE regex baseline: it *raises* a lane, it
   never certifies that content is safe.
6. **Verification is partial.** Result signatures (Ed25519), attempt ids and
   result schema are checked before anything enters assembly. The Layer-1
   commitment (`lsh-activation-v1`) has no normative construction (SPEC §21.1)
   and sampled audit (Layer 2) is not implemented: both are reported as *not
   available*, never simulated. The stage shows **partial**.
7. **Consensus is agreement, not truth.** With `k_min ≥ 2` replicas go to
   distinct model families and are aligned with SwarmblyAI's own `consensus()`.
   Agreement is convergence: errors are correlated across families (SwarmblyAI
   L13, L23). α thresholds are upstream provisional defaults, uncalibrated.
8. **ρ is derived, not targeted.** Packets carry mandatory content only (task,
   minimal Γ, consumed carry). Following whitepaper v2 §9.7, ρ is measured on
   what workers receive and reported; no ρ target is pursued, so
   `rho_target`/`rho_reachable` are `null` with the reason.
9. **Seam similarity is lexical by default.** The default embedder hashes
   words; switch to `model.embedder = server` (Ollama `/embeddings`, e.g.
   `nomic-embed-text`) for embedding cosines. τ_sem is a placeholder in both
   cases until calibrated (SPEC §14).
10. **Hedging starts from a declared fallback.** The hedge timer is the
    observed p95 per (kind, budget) once 8 samples exist; before that it is the
    configured `hedge_fallback_ms`, and the report says which was used.
11. **Channel binding is not mutual TLS.** The handshake binds each node's
    Ed25519 identity to the TLS certificate it presents (SSH host-key model):
    a man in the middle is detected. It is not the mutual TLS that TRUSTED
    requires.
12. **mDNS can be blocked** by routers, guest Wi-Fi or client isolation.
    Manual `host:port` connection always remains available. On macOS the OS
    asks for *Local Network* permission the first time.
13. **The idle-only worker mode is a CPU heuristic** (< 50 % over 0.5 s). The
    "only when plugged in" option relies on the battery state the OS reports;
    desktops without a battery count as plugged in.
14. **No user accounts.** Identity is the node's Ed25519 key (per the product
    spec, first version).
15. **GPU detection is best-effort**; unknown values are reported as unknown.
16. **App protocol extensions** (all MINOR-safe, ignored by implementations
    that do not know them, SPEC §3): handshake fields `hs`/`tls_fp`, message
    `advertisement_update`, advertisement fields `endpoint` and
    `policy.max_concurrent`, advertisement field `roles` (node roles, D-018),
    packet fields `constraints.model_family` (SWIP draft in
    `docs/SWIP-DRAFT-model-family-hint.md`), `constraints.role`,
    `constraints.think` and `constraints.carries_passages`, the signed
    `relay` field in manifests and invitations (D-016: host, port and the
    certificate SHA-256 pin; optional, ignored by older nodes), result fields
    `executor` and `sources`, control types `credit_receipt`, `credit_spend`
    and `credit_spent` (D-020; appendix below), error codes `E_POLICY`,
    `E_EXECUTION`, `E_DUPLICATE`, `E_DISCONNECTED`, `E_ROLE_UNAVAILABLE` and
    the credit codes `E_CREDIT_*`. All four node roles are in the wire schema;
    WP4b executes `search` and `corpus` only when the owner opts in.
17. **Several local models share one machine.** In multi-model mode replicas
    run on different model families but the same hardware; unless the
    recommendation allows parallel generation they take turns. Their agreement
    is still agreement, not accuracy (L23).
18. **The recommended configuration is an estimate.** It combines measured
    hardware with model sizes from a catalog verified on 2026-10-12 (sizes and
    licences can change upstream). Real memory use appears once models run.
19. **Installs are narrow by design.** The app installs only the Python
    packages it knows, into its own virtual environment. It never installs
    Ollama or system software; it shows the official instructions.
20. **Downloads need a running Ollama.** Cancelling stops the stream; partial
    files are Ollama's to clean up.
21. **Memory: C1 feeds answers made on this device; C2–C4 are described, not
    selectable.** Retrieval over your sources (hybrid: keywords and local
    embeddings) is used only for answers computed on this computer, or on a
    third-party model service you authorised for passages. It has been measured
    on one person's material and on two sealed benchmark banks (baseline of
    7 November 2026), not across many users.
22. **The interface preview is fake.** `scripts/ui_preview.py` serves canned
    answers from loopback-only workers; it measures nothing.
23. **The Windows launcher is the least tested.** `launch.bat` and the
    Windows paths of `scripts/launch.py` have not run on a real Windows
    machine yet; continuous integration covers Linux and macOS.
24. **Projects are folders, not accounts.** Two apps that open the same
    project folder at the same time can overwrite each other's copy of a
    chat; there is no locking or merging. The cloud-sync warning is detected
    from the folder's path (and, on macOS, iCloud's Desktop and Documents),
    so a sync service mounted elsewhere is not detected. A citation stops
    resolving when its file changes; the app says so and does not guess.
25. **Consent is asked after the answer, not before.** A personal or
    sensitive question that would need a public lookup is answered without
    it, and the answer offers to repeat it with the lookup; the yes covers
    that question only.
26. **Answers about documents can still contain invented details.** The
    passages come with an instruction to answer only from them, a short
    document is given whole, and labels keep their meaning across turns;
    a small model (3B) still adds facts, names and table rows that are not in
    the sources. Long documents are read as their best paragraphs, never
    whole. Grounded composition (a fact sheet, tables built by code, a
    verifier) is planned for 3.2; until then, check the labels in *Explore
    processing*.

27. **The requester cannot verify a member's search engine.** A search result
    says which member and circle ran the query and that the requester cannot
    verify the engine; the worker's own ledger is local and is not signed or
    sent back. A corpus result is labelled from the destination the requester
    sent to, not from the worker's self-description, and the passages may be
    incomplete or irrelevant: retrieval is keyword/BM25 over the shared project
    only.
28. **Corpus sharing is one project at a time.** Every admitted peer of a
    circle the owner selects sees the corpus display name and size bucket,
    even if it never asks for a passage. The owner cannot revoke a single
    passage already returned; revoking the member or removing the circle from
    the share stops new retrievals.

29. **The coordinator is a single point.** The requester plans, dispatches
    and assembles. If it goes away (stop, crash, lost machine) its run ends;
    3.5 has no plan migration, replication or hand-over. A worker that goes
    away only costs its own steps, which is what the partial answer reports.
30. **Teams are templates, not agents.** A team is a fixed list of at most 12
    steps with dependencies only on earlier steps. It cannot replan, choose
    a destination, inspect intermediate results or delegate recursively, and
    it never adds a permission. Built-in examples are read-only (duplicate
    them to edit). Teams are stored on this computer (per user, and per
    project inside a project folder): there is no account, sync or sharing of
    team definitions in 3.5.
31. **A partial answer is honest about steps, not about quality.** `complete`
    means every step returned a usable result; it does not mean the answer is
    correct. A missing step is named with its stable reason and its dependents
    are marked blocked and not retried. Recipe 4's per-item `failed` status
    carries the wave reason, but a failure of the *local* list path still
    fails that request (the per-wave continuation applies to distributed
    waves).

32. **Credits are a courtesy inside a circle, not money.** A receipt is
    signed, non-transferable and expiring; only the named worker can spend it,
    only in the same circle, and only to ask for queue priority while a worker
    is busy. It never bypasses admission, the egress gate, lane/tier or any
    other policy, and a requester without credits is still served when a slot
    is free. There is no transfer, export as a token, market or global ledger
    (SPEC §18, GOVERNANCE). The issuer detects a receipt reported spent twice
    in its own bounded log and flags it in Swarm; that is **detection, not
    prevention**, it does not stop a determined double spend, and nothing is
    broadcast beyond the circle. Because 3.5 has no mutual TLS, a stolen node
    key can spend that node's receipts until the owner revokes the member
    (R-010); protect the key. A receipt is one indivisible unit, so a large
    task does not buy several favours, and an expired receipt is lost. Wallet
    and issuer log are bounded (256 and 512 records); when the wallet is full
    a new valid receipt is refused rather than silently dropping an old one,
    and a receipt that has fallen out of the issuer's log cannot be matched by
    a later report.

33. **The relay operator sees metadata.** A circle relay forwards ciphertext it
    cannot read, but it necessarily sees who pairs with whom, when, from which
    IP, and how many bytes; it also holds the signed member list. It stores no
    payloads and the App's receipt names the hop, but traffic analysis remains
    possible. Run your own relay or trust its operator accordingly. This is the
    privacy notice requirement of R-014/D-023.
34. **No hole punching yet.** Off-LAN reachability in 3.5 is TCP through the
    circle's relay (or a direct address/overlay the circle runs). UDP/QUIC hole
    punching is a stretch goal moved to 3.6 if not ready; the relay remains the
    fallback and the correctness baseline.
35. **The first relay manifest is a manual bootstrap.** The operator must
    install the first signed manifest of each circle in the relay's `circles/`
    directory once; until then the owner's push gets `unknown_circle` and the
    circle card says so. After that the App pushes each new version over a
    registered connection; the signed file in `circle.relay_publish_dir` is
    only the bootstrap copy and the fallback. If the relay is unreachable the
    App retries with backoff and keeps the newest unacknowledged version in
    memory; an App restart loses that in-memory queue, so the operator can
    still copy the file. A relay change also pushes the same version to the
    old endpoint. One connection is kept per (circle, relay), not literally
    per relay, because the prototype binds a registration to one `circle_id`;
    the number is bounded by `circle.relay_max_connections`.
36. **Relay limits are the service's.** 4 concurrent splices per member,
    2 GiB per member per UTC day, 300 s idle and 30 s pair timeout are enforced
    by the prototype relay, not duplicated in the App; the App surfaces the
    refusal (`limit_splices`, `limit_bytes`, …) and backs off. Owner pushes
    are capped at **30 per hour per owner**; the App keeps the newest version
    queued and shows `rate_limited` until the relay accepts it. A relay
    restart resets its byte counters (a budget, not accounting), and a member
    can spend the relay's bandwidth up to those limits.

37. **The sandbox cache is prepared at first launch, not normally inside a request.** The
    first code recipe needs a one-time WebAssembly compile that peaks at about
    3.3 GB. The App shows a notice with the expected time (about 5 s on Apple
    Silicon, about 60 s on a 2-vCPU machine) and memory, refuses to start with
    fewer than 4 GB free on the automatic start and on a plain *Prepare now*,
    and runs the compile in the background. An explicit *Prepare anyway* (or
    `--prepare-sandbox --force`) may override that floor after a one-line
    warning; the state, events and doctor export then record `forced: true`
    and the free memory at start. Until the cache is ready, recipe 5 is
    unavailable with the reason (preparing, not prepared, failed or too little
    free memory) and the answer continues without it: the one-time compile
    never happens inside a request. Inside a run, the guest's working
    directory is the read-only `/data` (a bare input name resolves there), a
    fresh writable scratch is preopened at `/tmp` (deleted with the run and
    counted against the disk quota), and `/out` is the only collected output;
    there is no network, no process and no other host path. A file left in
    `/out` by a failed or trapped run is partial, not a result. A cache
    recorded by another `wasi-python` or Python version is stale and is
    prepared again.
    The measurement stays local and is the only compile data in the export.
38. **The doctor export is allow-listed, not redacted.** It contains versions,
    OS/architecture, Python, CPU/RAM/GPU class, installed extras, Ollama
    reachability and model tags, the sandbox state and measurements, P2P
    counts, relay/push status codes and the last error codes with timestamps.
    It does not contain node ids or keys, names, circle names or ids, member
    names, IP addresses or host names, paths under the user's home, project
    names, document titles, prompts, answers, glossary, memory, API keys or
    the relay host. Model tags are the local Ollama names. Read the preview
    before attaching the file; the App writes exactly that preview.

39. **Retrieval widening is lexical, not semantic.** The App adds the
    glossary's equivalents and regular accent/inflection variants to the query
    it hands to LCE. A synonym the glossary does not list, an irregular verb
    form or a paraphrase can still miss the one short passage that answers the
    question; LCE remains a keyword/BM25 search with its own local embeddings.
40. **When the passages and a skill do not fit, the skill yields.** Both are
    sent, but the material budget is shared: a large skill body is shortened
    (with a marker) and, if there is no useful room left, only its labelled
    header remains. The passages are never cut for the skill.
41. **The language check only acts on a clear drift.** It uses the existing
    stopword helper, so a very short or ambiguous English answer to a Spanish
    question is not regenerated; list and code prompts do take the
    conversation's language, and the retry is recorded in
    `meta.language_retry`.

### Protocol appendix: credit control messages (D-020/D-021)

The App already keeps its MINOR-safe extension list in item 16 above, so this
appendix lives here rather than in a new `docs/PROTOCOL_APPENDIX.md`. All three
messages are new `type` values on the same TLS session; the task plane stays
wire 0.2 and an older node ignores an unknown type (SPEC §3). All signed
payloads use Ed25519 over RFC 8785-style canonical JSON (`messages.
canonical_bytes`), with `sig` excluded from the signed bytes and encoded
base64url without padding; `node_id` is the Ed25519 public key in the same
encoding. A message over 8192 canonical bytes and a receipt over 4096 are
refused before parsing. The three messages are not a ledger: nothing is
forwarded, and only the named recipient/issuer acts on them.

`credit_receipt` — issuer (requester) → worker, sent after a verified result is
accepted. Fields: `v` (wire MINOR, currently `"0.2"`), `type`,
`receipt{receipt_id (random 128-bit, base64url), circle_id, issuer, worker,
attempt (BLAKE2b-128 hex of the attempt id, never task content), tokens_out,
generation_ms, model, issued_at, expires_at, sig}`. Validation at the worker:
the receipt is structurally valid and its signature verifies against
`receipt.issuer`; the envelope was sent by that issuer; `receipt.worker` is
this node; a valid, unexpired manifest of `circle_id` lists both issuer and
this node; `now < expires_at`; `receipt_id` is not already in the wallet.
Nothing is issued for the local pool, *my own devices*, rejected/degraded
replicas or an executor that returned nothing.

`credit_spend` — spender (the named worker) → a member of the same circle,
sent just before the task it is offered for, and only to a member the spender
already saw busy (a concurrency refusal or a missed deadline). Fields: `v`, `type`, `spender`,
`attempt_id` (the task this applies to), and the same signed `receipt` object.
Validation at the receiver: `spender` is the sending node and equals
`receipt.worker`; the signature verifies; a valid manifest lists the sender
and the issuer; `now < expires_at`; the receipt id was not already presented
to this worker. A valid spend only sets a short-lived priority marker for that
exact `attempt_id`. The sender marks the receipt spent in its wallet after the
message is written.

`credit_spent` — accepting worker → issuer. Fields: `v`, `type`, `receipt_id`,
`spender`, `by` (reporting worker), `reported_at`, `sig` (by `by`). It carries
no receipt copy and no task content. Validation at the issuer: `by` is the
sending node and its signature verifies; the receipt id is one this issuer
issued; `by` is listed by that receipt's circle. The issuer appends the report
to its bounded log and flags the receipt if it is reported twice (same or
different workers) or if the spender is not the named worker. An unknown
receipt id is refused (`E_CREDIT_UNKNOWN`); the issuer has no global ledger to
consult.

## Upstream (audited repositories)

- SwarmblyAI: `swarmbly_v0` is a measurement harness; no networking, no
  verification, no lane classifier; the go/no-go coherence criterion was not
  met in its published measurement; SPEC v0.2 lags whitepaper v2 (§9, v0.3).
- SwarmblyLCE: raw retrieval beats the digested wiki (R13, −0.146); digestion
  is not run-to-run reproducible; layer 2 (C4) has no verdict (R11 refused).

---

## Español

1. Solo se fragmentan solicitudes con estructura (lote enumerado o preguntas
   ligadas a su material); la prosa libre se responde localmente con la razón
   visible. 2. Un solo turno. 3. Sin enjambres por internet (Fase 3). 4. TRUSTED
   requiere mTLS: se responde localmente sin enviar nada; si el triaje sube a
   TRUSTED sin enjambre confiable, también local. 5. Contenido SANITISABLE o
   SENSITIVE nunca sale del equipo (sin seudonimización aún). 6. Verificación
   **parcial**: firmas, ids y esquema sí; compromiso de capa 1 y auditoría no
   disponibles, nunca simulados. 7. Consenso = acuerdo, no verdad (L13, L23);
   umbrales α provisionales. 8. ρ se deriva y se reporta; no se persigue un
   objetivo. 9. Similitud de costuras léxica por defecto; τ_sem placeholder.
   10. El *hedge* usa el p95 observado tras 8 muestras; antes, un respaldo
   declarado. 11. El binding de canal no es mTLS. 12. mDNS puede estar
   bloqueado: la conexión manual sigue disponible; macOS pide permiso de *Red
   local*. 13. Modo "solo inactivo" heurístico por CPU. 14. Sin cuentas de
   usuario. 15. GPU por mejor esfuerzo. 16. Extensiones de la app compatibles
   MINOR, documentadas. 17. Varios modelos locales comparten la misma máquina
   y, salvo que el hardware lo permita, se turnan; su acuerdo sigue siendo
   acuerdo. 18. La configuración recomendada es una estimación (catálogo
   verificado el 2026-10-12). 19. Solo se instalan paquetes Python conocidos en
   el entorno de la app; nunca Ollama ni software del sistema. 20. Las
   descargas requieren Ollama en ejecución. 21. C1 alimenta las respuestas hechas en
   este equipo (o en un servicio de terceros autorizado para pasajes); se ha
   medido con el material de una persona y con dos bancos sellados; C2–C4 solo
   se describen. 22. La vista
   previa de la interfaz es ficticia y solo usa loopback. 23. El lanzador de
   Windows es el menos probado (la integración continua cubre Linux y macOS).
   24. Los proyectos son carpetas, no cuentas: dos apps que abren la misma
   carpeta a la vez pueden pisarse la copia de un chat (no hay bloqueo ni
   fusión); el aviso de nube se detecta por la ruta (y en macOS, por
   Escritorio y Documentos en iCloud); una cita deja de resolverse si su
   archivo cambia, y se dice. 25. El consentimiento se pide después de la
   respuesta: una pregunta personal o sensible que necesitaría una consulta
   pública se responde sin ella y ofrece repetirla con la consulta; el sí
   vale solo para esa pregunta. 26. Las respuestas sobre documentos aún pueden
   contener detalles inventados: los párrafos llegan con la instrucción de
   responder solo con ellos, un documento corto va completo y las etiquetas
   conservan su sentido entre turnos, pero un modelo pequeño (3B) sigue
   añadiendo datos, nombres y filas que no están en las fuentes; los
   documentos largos se leen por sus mejores párrafos. La composición
   fundamentada llega en 3.2. 27. Una aprobación de herramienta pendiente vive
   en memoria, no en disco: recargar la página vuelve a mostrar la tarjeta
   porque forma parte del mensaje del asistente, pero reiniciar la app detiene
   la ejecución (no se guarda ningún token ni ejecución pendiente). Vuelve a
   enviar la pregunta después de reiniciar.

27. El solicitante no puede verificar qué motor usó un miembro: el recibo
    dice el miembro, el círculo y que no es verificable; el ledger del worker
    es local y no se firma ni se devuelve. Los pasajes del corpus se etiquetan
    según el destino al que el solicitante envió la tarea, no según lo que el
    worker diga, y pueden ser incompletos o irrelevantes (recuperación BM25
    solo sobre el proyecto compartido). 28. El corpus se comparte de un
    proyecto a la vez. Todos los pares admitidos de un círculo elegido ven el
    nombre visible y el tamaño, aunque nunca pidan un pasaje; el dueño no
    puede revocar un pasaje ya devuelto, pero quitar el círculo de la
    compartición detiene las nuevas recuperaciones. 29. El coordinador es un
    único punto: el solicitante planifica, despacha y ensambla; si desaparece
    (parada, caída, equipo perdido) su ejecución termina. 3.5 no tiene
    migración de plan, replicación ni traspaso. Un worker que se va solo
    cuesta sus propios pasos, y eso es lo que informa la respuesta parcial.
    30. Los equipos son plantillas, no agentes: una lista fija de como mucho
    12 pasos con dependencias solo de pasos anteriores. No replanifican, no
    eligen destino, no inspeccionan resultados intermedios ni delegan
    recursivamente, y nunca agregan un permiso. Los ejemplos incorporados son
    de solo lectura (duplícalos para editar). Se guardan en este equipo (por
    usuario y, dentro de un proyecto, por proyecto): en 3.5 no hay cuenta,
    sincronización ni compartición de definiciones de equipos. 31. Una
    respuesta parcial es honesta sobre los pasos, no sobre la calidad:
    `complete` significa que todos los pasos devolvieron un resultado
    utilizable, no que la respuesta sea correcta. Un paso faltante se nombra
    con su razón estable y sus dependientes quedan bloqueados y no se
    reintentan. El estado `failed` por elemento de la receta 4 lleva la razón
    de la ola, pero un fallo del camino local de listas todavía hace fallar
    esa solicitud (la continuación por olas aplica a olas distribuidas).
    32. Los créditos son una cortesía dentro de un círculo, no dinero. Un
    recibo es firmado, no transferible y caduca; solo lo puede gastar el
    worker nombrado, solo en el mismo círculo, y solo para pedir prioridad de
    cola cuando un worker está ocupado. Nunca salta admisión, puerta de
    salida, carril/tier ni ninguna otra política, y quien no tiene créditos
    sigue siendo atendido si hay un turno libre. No hay transferencia, export
    como token, mercado ni libro contable global (SPEC §18, GOVERNANCE). El
    emisor detecta en su registro acotado un recibo reportado dos veces y lo
    marca en Swarm: es **detección, no prevención**, no impide un doble gasto
    decidido y nada se difunde fuera del círculo. Sin TLS mutuo en 3.5, una
    clave de nodo robada puede gastar los recibos de ese nodo hasta que el
    dueño revoque al miembro (R-010); protege la clave. Un recibo es una
    unidad indivisible y uno caducado se pierde. Cartera y registro están
    acotados (256 y 512); si la cartera está llena, se rechaza un recibo nuevo
    válido en vez de descartar uno viejo en silencio. Los tres mensajes de
    control (`credit_receipt`, `credit_spend`, `credit_spent`) se documentan
    con sus campos, firma y validación en el apéndice en inglés de arriba; son
    MINOR-safe y un nodo antiguo ignora un tipo desconocido (SPEC §3).

37. La caché del sandbox se prepara, no se compila dentro de una solicitud:
    la primera receta de código necesita una compilación WebAssembly de unos
    3,3 GB de pico. La App muestra un aviso con el tiempo y la memoria
    previstos, no la inicia con menos de 4 GB libres en el arranque automático
    ni al pulsar *Preparar ahora*, y la ejecuta en segundo plano. Una acción
    explícita *Preparar de todos modos* (o `--prepare-sandbox --force`) puede
    anular ese mínimo tras un aviso de una línea; entonces el estado, los
    eventos y la exportación de diagnóstico registran `forced: true` y la
    memoria libre al iniciar. Hasta que la caché está lista, la
    receta 5 no está disponible con la razón (preparando, sin preparar, falló
    o poca memoria libre) y la respuesta sigue sin ella: la compilación nunca
    ocurre dentro de una solicitud. Dentro de una ejecución, el directorio de
    trabajo del invitado es `/data` (solo lectura; allí se resuelve un nombre
    de archivo simple), un directorio temporal escribible nuevo se preabre en
    `/tmp` (se borra con la ejecución y cuenta para la cuota de disco) y
    `/out` es la única salida recogida; no hay red, ni procesos, ni otra ruta
    del equipo. Un archivo que deja una ejecución fallida o atrapada en
    `/out` es parcial, no un resultado. Una caché de otra versión de
    `wasi-python` o de Python se considera desactualizada.
    38. La exportación de diagnóstico es una lista blanca, no un texto
    redactado: contiene versiones, sistema y arquitectura, Python, clase de
    CPU/RAM/GPU, complementos, si Ollama responde y sus etiquetas de modelo,
    el estado y las mediciones del sandbox, contadores P2P, códigos de
    relay/envío y los últimos códigos de error con fecha. No contiene
    identificadores de nodo ni claves, nombres, nombres de círculo o sus
    identificadores, nombres de miembros, IP ni nombres de host, rutas bajo tu carpeta
    personal, nombres de proyectos, títulos de documentos, preguntas,
    respuestas, glosario, memoria, claves de API ni el host del relay. Lee la
    vista previa antes de adjuntarla: la App escribe exactamente esa vista
    previa.

39. **La ampliación de la búsqueda es léxica, no semántica.** La App añade
    los equivalentes del glosario y variantes regulares de acento y flexión a
    la consulta que entrega a LCE. Un sinónimo que el glosario no lista, una
    forma verbal irregular o una paráfrasis todavía pueden no encontrar el
    pasaje corto que responde; LCE sigue siendo una búsqueda BM25/palabras
    clave con sus embeddings locales.
40. **Si los pasajes y una skill no caben, cede la skill.** Ambos se envían,
    pero el presupuesto de material es compartido: un cuerpo de skill grande se
    acorta (con una marca) y, si no queda espacio útil, solo permanece su
    cabecera etiquetada. Los pasajes nunca se recortan por la skill.
41. **La comprobación de idioma solo actúa ante una desviación clara.** Usa el
    detector de palabras vacías existente, así que una respuesta inglesa muy
    corta o ambigua a una pregunta en español no se regenera; las recetas de
    lista y código sí reciben el idioma de la conversación, y el reintento queda
    en `meta.language_retry`.
