# User guide

How to use Swarmbly App once it is running. Installation is in
[INSTALL.md](INSTALL.md). *[Español](#español) below.*

The app has five views, in the sidebar (bottom bar on a phone): **Chat**,
**Swarm**, **Teams**, **Memory** and **Settings**. The node card under the navigation
shows your node identity, default mode, privacy tier, local network, peers and
whether you are sharing this computer. The **Current request** panel on the
right follows the request in progress stage by stage (on narrow screens, open
it with the *Pipeline* button).

## 1. Chat

Type a message and press **Send** (Enter; Shift+Enter for a new line).
Answers stream in; **Stop** ends one early and **Retry** asks again.

**Mode** decides where a message may be processed:

| Mode | What happens |
|---|---|
| Local | Answered on this computer only |
| Swarm LAN | Itemised requests may be shared with authenticated computers on this network; everything else is answered locally |
| Automatic | Shared only when the request splits cleanly and workers are available |
| Swarm Internet | Phase 3; not available yet |

Two conditions must hold before anything is shared: a swarm mode, **and** a
privacy tier that allows it (Settings → Privacy → *Privacy tier* = GLOBAL).
With the default tier, LOCAL, the hint under the composer tells you nothing
will be sent.

**What gets shared.** Swarmbly fragments the *problem*: only requests with a
structure are split — a list of items to process one by one, or questions tied
to the material that answers them. This one is a good first test:

> Extract one key fact per item from the following list of five items:
> apples, bridges, comets, drums, electrons. List 5 bullet points, one per
> item, separately.

Free prose ("write an essay about …") is answered locally and the processing
record says why. Messages with attachments are answered locally too.

**Attachments.** *Attach text* adds text files up to 200 KB (txt, md, csv,
json, code…). They are read on this computer.

**Under each answer** small labels say where it ran (*local model*, *local
models*, *swarm*), how many fragments or replicas were used, the agreement
between replicas, the model and the time. Agreement is convergence, not
correctness.

**Conversations** are listed on the left (a picker at the top on a phone).
*Export* saves one as Markdown, JSON or HTML; *Delete* removes it from this
computer.

**Projects** (above the conversation). Choose *Personal* or a project, or
create one. A project is a folder of yours, by default
`Documents/Swarmbly/<Project>`:

| Folder | What goes there |
|---|---|
| `sources/` | the project's documents (text, Markdown, Word, HTML, PDF) |
| `memory/` | the project's memory: notes saved from the chat (`notas.md`), a glossary (`glosario.md`: `term = equivalent`, or `term = equivalent | privado` for an entry never used in public searches), and any notes of yours |
| `chats/` | the project's conversations, one file each, kept up to date by the app |
| `exports/` | `.swarmbly` packages of the project |

- A conversation in a project reads only that project's documents and
  memory. Your personal sources are added only if you tick *Include my
  personal sources*; a personal conversation never reads a project.
- *Export .swarmbly* writes one file with the documents, memory and chats,
  and the SHA-256 of each file. It never contains API keys: if a file holds
  one of your keys, the export stops and names it.
- *Restore a .swarmbly package* checks every hash before writing anything and
  restores into a new folder. On another computer, the chats come back and
  their citations still point to the right paragraph (a citation names a
  file by the hash of its content, not by its path). If that project is
  already open here, it is restored as a copy.
- *Close project* removes it from this app; the folder stays, and *Open a
  project folder* brings it back with its chats.
- If the folder is synced by iCloud, Dropbox, OneDrive or Google Drive, the
  app warns you: those services can move files to the cloud to free space or
  create duplicates ("chat 2.json"). Prefer a folder that is not synced, or
  keep this one always on this computer.

**Remember something.** Start a message with *Recuerda:*, *Memoriza* or
*Remember*: before answering, the app writes it, dated, to the project's
`memory/notas.md` (in a personal conversation, to `notas.md` in your sources
folder). A *Saved to memory* label says where, and the next answers find it.
It stays on this computer and such a message never goes to the swarm.
*Documents* in the project bar shows what the project can read, and why a
file gave nothing (for example a scanned PDF).

**Memory and glossary proposals.** If you ask in a message to remember
something or to add it to the glossary, or you define or correct a term
("TRU significa Trial Rearing Unit", "los cucujos, también conocidos como
cucuyos…"), a card under the answer proposes notes and glossary entries.
Edit them, untick what you do not want, and press *Save to memory*; nothing
is saved otherwise. The glossary (`term = synonyms, translations`) widens
later searches: any one of the equivalents finds the term. Add `| privado`
(or `| private`) to an entry, or tick *Private: never used in public
searches* when you save it, to keep its term and equivalents out of public
queries; local answers still use it.

**Searching online.** Swarmbly never sends your question to a search engine
on its own. If you ask for online or recent references, the answer says no
search was made and offers *Search online*: you see the exact text that
would be sent, edit it, and approve it. Results from PubMed, Wikipedia (and
your SearXNG, if configured) are listed under the new answer as [W1], [W2]…
with their links. A label in an answer that matches no passage or result is
flagged as *citation without a source*.

**Public lookups need your yes when the question is about you.** If a
question is personal or sensitive, or your documents answer it, and it would
also need a public source, the answer is written without the lookup and
offers *Also search public sources*, with the names that would be sent. The
yes covers that question only. *Explore processing → What left this
computer* shows the scope (personal or project) and the consent.

**What left this computer.** The privacy receipt names every destination and
its class: *local* (this computer), *your network* (my-own-devices mode),
*trusted circle* (with the circle and the member) or *third party*. Every
task packet passes the egress gate before it is written; a peer outside every
circle is refused and appears as a blocked attempt, never as a send. Passages
of your documents are listed per destination: they reach a circle only when
that circle's *Document passages* switch is on (Swarm → Trusted circles), and
reach *my own devices* only with the equivalent switch in that mode. Both are
off by default and are separate from the third-party model-service setting.

## 2. Explore processing

*Explore processing* under an answer opens **How this answer was made**:

- **Readouts** — executed locally or distributed, privacy tier, content
  lane, micro-tasks, context ratio ρ, total time, effective coverage,
  similarity method. Each is labelled *measured*, *estimated* or *unknown*.
- **Pipeline** — the 14 stages drawn as a DNA strand. Each is *completed*,
  *partial*, *skipped* or *failed*, with its own details. A stage that did not
  apply is *skipped*, never shown as completed. *Verification* is *partial* on
  purpose: signatures are checked, while the Layer-1 commitment has no
  normative construction yet.
- **Attempts** — every micro-task attempt: task, why it was sent (first
  attempt, hedge or retry), node, model family, status, time and error code.
- **Consensus** — units where replicas agreed strongly, moderately or weakly.
- **Seams** — how the pieces were joined, with their similarity scores.
- **Caveats** — what the numbers do not mean.
- **Report** — download or save the record as JSON, Markdown or HTML, at the
  detail level chosen in Settings → Results.

## 3. Swarm

**Local network** turns discovery on or off (it asks for permission the first
time). **Search now** sends a fresh query. **Connect by address** joins a
computer directly when your network blocks discovery; its identity is still
verified.

- **Health** — discovered, connected and authenticated nodes, free and busy
  workers, unreachable nodes, model families, latency, uptime, shared
  requests and micro-tasks.
- **Map** — this computer in the centre with its local models, peers around
  it. A pulse travels along a link only when a real micro-task is sent to that
  node.
- **Peers** — each node's address, state, role, models, latency and tasks in
  flight.
- **Discovery cache** — every announcement with first seen, last confirmed and
  expiry times.
- **Your contribution** — tasks served for others, processing time, tokens,
  data in and out, shared models. Your own requests are not counted.

### Sharing this computer

**Share this computer** makes your node a worker that serves micro-tasks for
others. Settings → Swarm controls it:

| Setting | Meaning |
|---|---|
| Models offered to others | Which installed models workers may use (default: your chat model) |
| Tasks at once | Simultaneous micro-tasks |
| Tokens per task | Upper bound on each answer |
| Maximum seconds per task | Generation stops at the deadline |
| Only when idle | Serve only while the processor is mostly idle |
| Only when plugged in | Serve only on mains power |
| Pause sharing | Stop serving without leaving the swarm |

Workers serve the base model only. Your memory, sources and conversations are
never used for other people's tasks.

### Node roles · Roles del nodo

A **node role** describes what this machine offers the swarm as a worker; it is
not the per-answer model role you choose in Settings → Models. In this version
a node advertises `large_model` for shared models at or above the
**Large-model threshold** (Settings → Swarm, 7 B by default) and `reasoner`
for shared models you mark as **Reasoning models**. Both are announced in the
signed advertisement and only while **Share this computer** is on; a role
never widens a permission. A role task is sent only to a node that advertises
it. If no node has `large_model` or `reasoner`, the task may run on the best
generic worker and the answer, its stages and the receipt say «role X
unavailable, ran on Y»; tasks that need `search` or `corpus` fail honestly
until their executors are on. The Swarm panel shows your own roles and each
peer's advertised roles.

**Search and corpus (executors).** Both are off by default in Settings → Swarm.
- *Share public search* lets this worker run a public query for a member of a
  trusted circle. Only one short public query travels; your files and
  conversation never do. The query is derived from the requester's words with
  its private terms removed, and if that cannot be done no search is made. The
  requester's receipt shows the query, circle and member, and that it cannot
  verify which engine answered.
- *Corpus to share* picks one local project and a display name. In each circle
  card, **Share corpus with this circle** decides which circles may retrieve
  from it. Only the display name and a size bucket (S/M/L) are advertised; every
  admitted peer sees them. Retrieval reads that project only and returns a few
  passages with a neutral citation (document title and span, never a path).
  Returned passages are third-party material: keep them out of your own
  glossary and memory. They are treated like your documents for egress, so
  another node receives them only with that circle's **Document passages**
  switch on, and a model service only with `privacy.third_party_passages`;
  otherwise the task runs locally or fails honestly.

### Trusted circles · Círculos de confianza

A **circle** is a list of members signed by its owner. Each version has a
number and an expiry date, and it is the only thing that authorises a peer:

1. **Create** a circle in **Swarm → Trusted circles** and give it a name (for
   example *Familia* or *Lab*). This device is the owner.
2. **Invite** a node: the app shows a code (`SWC1…`) and a QR. Send either to
   the other person. The invitation is signed, expires (7 days by default) and
   can be used once.
3. **Accept** on the other device: paste the code in **Swarm → Trusted
   circles → Accept invitation**. The device sends a signed join request. If
   the owner is offline the request is kept and sent when it is reachable.
4. **Approve** the request on the owner's device. The owner signs a new
   manifest version and sends it to the newcomer; both nodes then list each
   other.
5. **Members** shows every node, its endpoints and its role. The owner can
   **revoke** a member (a new version without it) or delete the circle; a
   member can **leave**. Revocation is checked again for every task, so it
   takes effect even on a connection that was already open. Older manifest
   versions are rejected.

**Who may connect.** New installations admit a peer only when both nodes are in
a valid, unexpired circle manifest (*Only my circles*). An installation that
already existed before 3.5 keeps the old LAN rule (*My own devices*, any
authenticated peer on the LAN) and shows a notice in Swarm until you choose.
Change it in **Settings → Swarm → Peer admission**. **Accepting an invitation
is not membership yet**: the owner must approve it, and until then the
connection can only carry the join request, never a task.

Circle traffic is labelled `CIRCLE` in the receipt, with the circle's name and
the member's display name and short node id. The receipt never shows packet
content. **Document passages** are a per-circle switch in the circle card,
off by default: recipe 4 may attach passages of your project documents to
items sent to that circle only when it is on. It is separate from
`privacy.third_party_passages` (model services); an existing installation
with that flag on does not enable circle passages. *My own devices* mode has
its own switch in the same panel, also off by default. Keep the node key
private: 3.5 has no mutual TLS, so a stolen key can impersonate a member until
the owner revokes it.

**Relay (members on different networks).** If the circle's owner runs a relay,
set it in the circle card (**Set relay…**): `host:port` and the relay
certificate's **SHA-256 pin**. The pin is mandatory; a relay without it is
refused. The relay and pin travel in the signed manifest and in invitations.
The operator installs the **first** signed manifest of the circle on the relay
once; after that the owner's App pushes every new signed version over a
registered connection (with backoff while the relay is unreachable), so a
revocation reaches the relay before the next pairing. The circle card shows
the acknowledged version, the pending version and a refusal code:
`unknown_circle` means the operator must install the first manifest,
`rate_limited` is the relay's 30-push-per-hour cap, and `stale_version` means
the relay already has a newer version. The signed file the App writes under
`circle.relay_publish_dir` is the bootstrap copy and the fallback, not the
normal update path. **Renew manifest** signs a fresh version with the same
members and relay; it is pushed like any other version. On a relay change the
same new version is also pushed to the old relay, so it stops admitting
removed members. Members keep one
outbound connection to the relay; direct addresses (LAN discovery, manual
address, manifest hints) are always tried first, and only then the relay. A
relayed peer gets the **same** circle admission, worker policy and egress gate
as a direct one; the two nodes still run their own TLS 1.3 and handshake
through the relay, which forwards ciphertext. The Swarm panel shows **direct**
or **relayed** per peer, and the receipt names the relay hop and says it saw
only who, when and how many bytes — never content. The relay operator can see
that metadata and the member list, so run your own relay or trust its
operator. A pin mismatch stops that relay and shows a security warning; a
relay that is down does not stop direct LAN peers. The relay enforces its own
limits (4 concurrent splices per member, 2 GiB/day, 300 s idle) and a refusal
is shown in the circle card. No hole punching yet.

### Reciprocity credits · Créditos de reciprocidad

When you accept a verified answer from a member of one of your circles, the
requester signs a **credit receipt** for that worker. It names the circle, the
issuer, the worker, a hash of the attempt (never the task text), the tokens
generated, the model and an expiry date (90 days by default). The receipt is
kept in the worker's local wallet, under **Swarm → Reciprocity credits**, with
the balance, what was earned and spent per circle and what expires soon. It is
not money: it belongs only to the worker it names, can only be offered back
inside the same circle when that worker sends a task to a member, and the
worker may then wait for a busy slot instead of being refused. It never lets a
task skip admission, the egress gate, lane/tier or any other rule, and a node
without credits is still served whenever there is a free slot. There is no
transfer, no sale, no market and no shared ledger; a receipt expires and is
lost. If a receipt is reported spent twice, the issuer flags it in the same
panel — this is detection, not prevention, and nothing leaves the circle.
Protect the node key: a stolen key can spend that node's receipts until the
owner revokes the member (R-010).

## 4. Teams

A **team** is a plan you store and run again: named steps, each with an
instruction and, optionally, a node role (`search`, `corpus`, `large_model`,
`reasoner`), plus dependencies on earlier steps. It is a template, not an
agent: it never chooses a destination and never adds a permission. The same
team runs on this computer (its local model pool, when it has every role) or
across the members of a circle, by role.

**Make a team** in **Teams → New team**:

1. Give it a name and, if you like, a description.
2. Write each step's name and instruction. Put `{request}` where your message
   belongs; at least one step needs it.
3. Pick a node role when the step needs one. `search` runs a public query on a
   member that shares search; `corpus` reads a collection a member shares;
   `large_model` and `reasoner` ask for a model of that kind. A step with no
   role can run on any worker.
4. Tick the earlier steps this step needs. A step can depend only on steps
   above it, so a plan cannot loop.
5. **Save**. Teams are stored only on this computer: in the app's data
   directory, or inside the project folder when you are in a project. The
   limits are 12 steps, a 60-character name and 2,000 characters per
   instruction. Anything outside them is refused with a message, as are
   unknown roles and forward dependencies.

Three examples are built in (for instance *Public search → shared collection →
draft → review*). They are read-only: **Duplicate** makes an editable copy.
**Use in chat** selects the team in the composer.

**Run it:** pick the team in the chat composer's **Team** selector and send
your message. The answer, *Explore processing* and the receipt show the steps
and where each one ran. You can run the same team with the mode *Local* (its
local pool), *Swarm LAN* or *Automatic*; the privacy tier, circle admission,
egress, role and passage rules apply exactly as without a team. If a role is
missing, a `large_model` or `reasoner` step falls back to the best generic
worker and says so; a `search` or `corpus` step fails honestly.

**Partial answers.** A step that cannot finish (a node goes away, a deadline
expires, a policy refuses, a role is missing) no longer loses the whole
answer. The app assembles the steps that did finish and adds a short note
naming each missing step and why; a step that depended on it is marked
*blocked by* it and is not run. The metadata says `complete`, `partial` or
`failed` (nothing usable completed), and the per-step statuses are in
*Explore processing*. In a list (recipe 4) each item keeps its own status; a
whole failed wave marks only its items failed and later waves still run. If
you press **Stop**, the answer is *stopped*, not partial. The requester is the
coordinator: if it goes away the run ends; there is no plan migration.

## 5. Memory

The Local Cognitive Extension keeps a personal memory on this computer. It is
optional and never changes what other nodes receive.

| Level | Adds | In this version |
|---|---|---|
| C0 | Nothing: Swarmbly without the extension | Active |
| C1 | Your sources, retrieval over them, a wiki recording where each claim came from | Selectable; the source folder is prepared, retrieval in answers comes next |
| C2 | Automatic digestion of sources | Later phase |
| C3 | Social capsules between nodes | Later phase |
| C4 | Personal fine-tuning (LoRA) | Experimental upstream, no verdict |

Each level lists its requirements and whether this computer meets them.
**Your sources** opens the folder where documents go; they are read, never
modified.

## 6. Settings

The **Profile** at the top chooses how much you see: *Automatic* (the
recommended configuration), *Custom* (everyday settings) or *Advanced* (every
parameter). Every change is validated and saved at once.

| Tab | Contents |
|---|---|
| Recommended | What was measured on this computer, the proposed values with reasons, *Apply* and *Revert* |
| General | Language (English / Spanish), theme, reduced motion, output folder |
| Models | Model runner and address, chat model, several local models, answer limits, similarity method, downloads |
| Swarm | Default mode, local network, minimum and maximum responses per micro-task, fragments, timeouts, sharing this computer |
| Privacy | Privacy tier (LOCAL, GLOBAL; TRUSTED is answered locally until mutual TLS exists) |
| Results | Export format, report detail, saving a report for every shared request, export folder |
| Permissions | Local-network discovery, model downloads (internet swarms later) |
| System | The same system check as the first-run assistant, with consented installs |

**Minimum and maximum responses per micro-task.** The minimum is how many
replicas go out from the start; two or more give a map of where models
disagree, at a proportional cost. The maximum is the ceiling including extra
attempts for slow or failed workers.

**Downloads.** Settings → Models lists suggested models with size and licence.
With the download permission on, *Download* asks for confirmation and Ollama
does the rest; progress shows in the app and can be cancelled. Some licences
restrict commercial use; the dialog says so.

## 7. First launch: the code sandbox and the doctor export

**The code recipe compiles once.** On first use, recipe 5 (data with code)
compiles the WebAssembly Python module. That takes about 5 s and 3.3 GB of
memory on an Apple-silicon Mac and about 60 s on a 2-vCPU machine with 8 GB.
Swarmbly now prepares it from the first launch instead of inside a request:
when the optional `[sandbox]` extra is installed and the compiled cache is
missing or stale, a notice appears in the app and in the first-run assistant.
It shows the expected time and memory and offers **Prepare now** / **Later**.
If you choose **Later**, the notice hides for a week and recipe 5 stays
unavailable until you prepare it from Settings or with the installer flag.
The compile runs in the background (`preparing`, then `ready`, or `failed`
with the reason); the chat keeps working. Until it is ready, recipe 5 reports
why it is unavailable and the answer continues without it; the compile is
never paid inside a request. With less than 4 GB of free memory the automatic
start and a plain **Prepare now** do not start the compile; close other
applications or use a machine with more memory. If you still need recipe 5 on
that machine, an explicit **Prepare anyway** starts it after a warning: the
compile may take minutes and slow the computer or swap, so close other apps
first. That override is never automatic, the plain button keeps the floor, and
the state and doctor export record that it was forced. The command line has
the same explicit flag, `--prepare-sandbox --force`; the umbrella installer
never passes it by itself.
The measured compile time and peak memory stay local and appear in the doctor
export. The same step is available in **Settings → System**.

**Doctor export.** **Settings → System → Doctor export → Review and save…**
writes one JSON and one readable text file. The screen shows the exact text
and JSON before saving, and saving writes that same snapshot. Attach either
file to a bug report: it contains only App/LCE/Core versions, OS and
architecture, Python version, CPU/RAM/GPU class, installed extras, whether
Ollama answers and its model tags, the sandbox state and compile measurements
(including whether a low-memory override was forced), P2P counts (listening,
peers, circles, relay configured and push codes), and
the last error codes with timestamps. It never contains node ids or keys,
names, circle names or ids, member names, IP addresses or host names, paths
under your home, project names, document titles, prompts, answers, glossary,
memory, API keys or the relay host. On the command line:
`swarmbly-app doctor-export`.

## 8. Without a window (headless)

```bash
./launch.sh --headless                        # or: swarmbly-app headless
swarmbly-app config set swarm.worker_enabled true
swarmbly-app config set swarm.lan_enabled true
swarmbly-app config set model.model_name llama3.2:3b
```

Useful for a second computer or a Raspberry Pi that only lends compute.
`swarmbly-app status` prints version, node id and data directory.

## 9. Keyboard and accessibility

Every control is reachable with the keyboard and shows a visible focus ring;
*Skip to content* is the first tab stop. *Reduce motion* (Settings → General,
or your system preference) turns off pulses and animations. The theme is dark
by default; a light theme is in Settings → General.

---

## Español

La app tiene cinco vistas: **Chat**, **Swarm**, **Equipos**, **Memory** y
**Settings**.
La tarjeta del nodo muestra tu identidad, modo por defecto, nivel de
privacidad, red local, pares y si compartes tu equipo; el panel **Current
request** sigue la solicitud en curso etapa por etapa.

**Chat.** Modos: *Local* (solo este equipo), *Swarm LAN* (las solicitudes con
ítems pueden compartirse con equipos autenticados de tu red; lo demás se
responde localmente), *Automatic* (solo si la solicitud se divide limpiamente
y hay workers) y *Swarm Internet* (Fase 3). Para compartir hacen falta un modo
de enjambre **y** el nivel de privacidad GLOBAL (Settings → Privacy); con
LOCAL, que es el valor por defecto, nada se envía. Solo se fragmentan
solicitudes con estructura (listas de ítems, preguntas ligadas a su
material); la prosa libre y los mensajes con adjuntos se responden
localmente. Las etiquetas bajo cada respuesta indican dónde se ejecutó,
cuántos fragmentos o réplicas hubo, el acuerdo (convergencia, no exactitud),
el modelo y el tiempo.

**Explorar el procesamiento.** Muestra lecturas etiquetadas como *medidas*,
*estimadas* o *desconocidas*; las 14 etapas como una hebra de ADN (una etapa
que no aplica aparece *omitida*, nunca completada; la verificación es
*parcial* a propósito); cada intento con su nodo y familia; el consenso; las
costuras; las advertencias; y un reporte en JSON, Markdown o HTML.

**Swarm.** Activa la red local, busca, o conecta por dirección cuando la red
bloquea el descubrimiento. Salud, mapa (un pulso solo cuando se envía una
microtarea real), pares, caché de descubrimiento y tu contribución.
**Compartir este equipo** lo convierte en worker: eliges modelos, tareas
simultáneas, tokens y segundos por tarea, solo inactivo o conectado a la
corriente, y puedes pausar. Los workers sirven solo el modelo base; tu
memoria y tus archivos nunca se usan.

**Círculos de confianza.** Un círculo es una lista de miembros firmada por su
dueño, con número de versión y caducidad. En **Swarm → Círculos de confianza**
puedes crear uno, invitar a otro nodo (código `SWC1…` o QR, de un solo uso y
con caducidad), aceptar una invitación y aprobar la solicitud de unión. El
dueño firma una nueva versión del manifiesto al aprobar o revocar; los miembros
se listan con sus endpoints y roles, y una revocación se comprueba otra vez en
cada tarea, aunque la conexión ya estuviera abierta. Las versiones antiguas se
rechazan. Una instalación nueva solo admite pares que estén en un manifiesto
vigente (*Solo mis círculos*); una instalación anterior a 3.5 conserva la regla
LAN de 3.4 (*Mis propios dispositivos*) y muestra un aviso hasta que elijas en
**Ajustes → Swarm → Admisión de pares**. Aceptar una invitación no da
membresía: el dueño tiene que aprobarla y, hasta entonces, la conexión solo
puede llevar la solicitud, nunca una tarea. El recibo etiqueta el tráfico entre
pares como `CIRCLE`, con el nombre del círculo y el nombre y el id corto del
miembro; nunca muestra el contenido del paquete. **Los pasajes de documentos**
son un interruptor por círculo en la tarjeta del círculo, apagado por defecto:
la receta 4 solo adjunta pasajes de tus documentos a los elementos enviados a
ese círculo cuando está activo. Es independiente de
`privacy.third_party_passages` (servicios de modelos); una instalación que ya
tenía esa opción activa no enciende los pasajes del círculo. El modo *Mis
propios dispositivos* tiene su propio interruptor en el mismo panel, también
apagado por defecto. Sin TLS mutuo en 3.5, protege la clave del nodo: una clave
robada puede suplantar a un miembro hasta que el dueño lo revoque.

**Relay (miembros en redes distintas).** Si el dueño del círculo ejecuta un
relay, configúralo en la tarjeta del círculo (**Configurar relay…**):
`host:puerto` y el **pin SHA-256** del certificado del relay. El pin es
obligatorio; un relay sin él se rechaza. El relay y el pin viajan en el
manifiesto firmado y en las invitaciones. El operador instala **una vez** el
primer manifiesto firmado del círculo en el relay; después la App del dueño
envía por red cada nueva versión firmada por una conexión registrada (con
backoff si el relay está caído), así la revocación llega antes del siguiente
emparejamiento. La tarjeta del círculo muestra la versión confirmada, la
pendiente y el código de rechazo: `unknown_circle` significa que el operador
debe instalar el primer manifiesto, `rate_limited` es el límite del relay de
30 envíos por hora, y `stale_version` significa que el relay ya tiene una
versión más nueva. El archivo firmado que la App escribe en
`circle.relay_publish_dir` es la copia de arranque y el respaldo, no el camino
normal de actualización. **Renovar manifiesto** firma una versión nueva con los
mismos miembros y relay; se envía como cualquier otra versión. Si cambia el
relay, la misma versión se envía también al relay anterior para que deje de
admitir a los miembros retirados. Cada miembro mantiene una conexión saliente
al relay; las direcciones directas
(descubrimiento LAN, dirección manual, pistas del manifiesto) se prueban
primero y solo después el relay. Un par por relay pasa por la **misma**
admisión de círculo, política de worker y puerta de salida que uno directo; los
dos nodos siguen ejecutando su TLS 1.3 y su handshake a través del relay, que
solo reenvía cifrado. El panel Swarm muestra **directa** o **por relay** por
par, y el recibo nombra el salto y dice que solo vio quién, cuándo y cuántos
bytes, nunca el contenido. El operador del relay puede ver esos metadatos y la
lista de miembros: ejecuta tu propio relay o confía en su operador. Un pin que
no coincide detiene ese relay y muestra un aviso de seguridad; un relay caído
no impide que sigan funcionando los pares directos de la LAN. El relay aplica
sus propios límites (4 empalmes simultáneos por miembro, 2 GiB/día, 300 s
inactivo) y el rechazo se muestra en la tarjeta del círculo. Aún no hay hole
punching.

**Créditos de reciprocidad.** Cuando aceptas una respuesta verificada de un
miembro de uno de tus círculos, el solicitante firma un **recibo de crédito**
para ese worker. Nombra el círculo, el emisor, el worker, un hash del intento
(nunca el texto de la tarea), los tokens generados, el modelo y una fecha de
caducidad (90 días por defecto). El recibo queda en la cartera local del
worker, en **Swarm → Créditos de reciprocidad**, con el saldo, lo ganado y
gastado por círculo y lo que caduca pronto. No es dinero: pertenece solo al
worker que nombra, solo se puede ofrecer de vuelta dentro del mismo círculo
cuando ese worker envía una tarea a un miembro, y puede entonces esperar un
turno ocupado en vez de ser rechazado. Nunca permite saltar admisión, puerta de
salida, carril/tier ni ninguna otra regla, y un nodo sin créditos sigue siendo
atendido cuando hay un turno libre. No hay transferencia, venta, mercado ni
libro contable compartido; un recibo caduca y se pierde. Si un recibo se
reporta gastado dos veces, el emisor lo marca en el mismo panel: es detección,
no prevención, y nada sale del círculo. Protege la clave del nodo: una clave
robada puede gastar los recibos de ese nodo hasta que el dueño revoque al
miembro (R-010).

**Roles del nodo.** Un **rol de nodo** describe lo que esta computadora
ofrece al enjambre como worker; no es el rol de modelo por respuesta que
eliges en Ajustes → Modelos. En esta versión el nodo anuncia `large_model`
para los modelos compartidos con al menos el **Umbral de modelo grande**
(Ajustes → Swarm, 7 B por defecto) y `reasoner` para los modelos compartidos
que marques como **Modelos de razonamiento**. Ambos viajan en el anuncio
firmado y solo con **Compartir este equipo** activo; un rol nunca amplía un
permiso. Una tarea con rol se envía solo a un nodo que anuncie ese rol. Si
ningún nodo tiene `large_model` o `reasoner`, la tarea puede ejecutarse en el
mejor worker genérico y la respuesta, sus etapas y el recibo dicen «rol X no
disponible, ejecutado en Y»; las tareas que necesitan `search` o `corpus`
fallan honestamente hasta que sus ejecutores estén activos. El panel Swarm
muestra tus roles y los roles anunciados por cada par.

**Búsqueda y corpus (ejecutores).** Ambos están apagados por defecto en
Ajustes → Swarm.
- *Compartir búsqueda pública* permite que este worker ejecute una consulta
  pública en nombre de un miembro de un círculo de confianza. Solo viaja una
  consulta pública corta; tus archivos y tu conversación nunca. La consulta se
  deriva de las palabras del solicitante quitando sus términos privados, y si
  no se puede, no se busca. El recibo del solicitante muestra la consulta,
  el círculo y el miembro, y que no puede verificar qué motor respondió.
- *Corpus a compartir* elige un proyecto local y un nombre visible. En cada
  tarjeta de círculo, **Compartir corpus con este círculo** decide qué círculos
  pueden recuperar de él. Solo se anuncian el nombre visible y un tamaño
  (S/M/L); todos los pares admitidos los ven. La recuperación lee solo ese
  proyecto y devuelve unos pocos pasajes con cita neutral (título y span,
  nunca una ruta). Los pasajes devueltos son material de terceros: no entran en
  tu glosario ni en tu memoria. Se tratan como tus documentos para la salida,
  así que otro nodo los recibe solo con **Pasajes de documentos** de ese
  círculo encendido, y un servicio de modelos solo con
  `privacy.third_party_passages`; si no, la tarea se ejecuta en local o falla
  honestamente.

**Equipos.** Un **equipo** es un plan guardado para repetir: pasos con
nombre, cada uno con una instrucción y, si hace falta, un rol de nodo
(`search`, `corpus`, `large_model`, `reasoner`), más dependencias de pasos
anteriores. Es una plantilla, no un agente: nunca elige un destino ni agrega
un permiso. El mismo equipo corre en esta computadora (su pool local, cuando
tiene todos los roles) o entre los miembros de un círculo, por rol. En
**Equipos → Nuevo equipo** le pones nombre y escribes cada paso; usa
`{request}` donde va tu mensaje (al menos un paso lo necesita), elige un rol
solo cuando el paso lo requiera y marca los pasos anteriores de los que
depende. Un paso solo puede depender de pasos de arriba, así que el plan no
puede formar un ciclo. Se guardan solo en este equipo: en el directorio de
datos de la app o dentro de la carpeta del proyecto cuando estás en uno; los
límites son 12 pasos, 60 caracteres de nombre y 2.000 por instrucción, y se
rechazan roles desconocidos o dependencias hacia adelante. Hay tres ejemplos
incorporados y de solo lectura: **Duplicar** crea una copia editable. Elige el
equipo en el selector **Equipo** del chat y envía el mensaje; la respuesta,
*Explorar el procesamiento* y el recibo muestran los pasos y dónde corrió cada
uno. Las reglas de privacidad, admisión de círculo, salida, rol y pasajes
siguen igual: un rol nunca amplía un permiso. Si falta un rol, un paso
`large_model` o `reasoner` cae al mejor worker genérico y lo dice; uno de
`search` o `corpus` falla honestamente. **Respuestas parciales:** un paso que
no puede terminar (se va un nodo, vence el plazo, una política lo rechaza,
falta un rol) ya no pierde toda la respuesta. La app ensambla los pasos que sí
terminaron y añade una nota que nombra cada paso faltante y por qué; un paso
que dependía de él queda *bloqueado por* ese paso y no se ejecuta. Los
metadatos dicen `complete`, `partial` o `failed` (nada utilizable se completó)
y los estados por paso están en *Explorar el procesamiento*. En una lista
(receta 4) cada elemento conserva su estado; una ola fallida marca solo sus
elementos como fallidos y las olas siguientes siguen. **Detener** deja
*stopped*, no una respuesta parcial. El solicitante es el coordinador: si
desaparece, la ejecución termina; no hay migración de plan en 3.5.

**Memory.** C0 activa; C1 recupera pasajes de tus fuentes para las
respuestas hechas en este equipo; C2–C4 en fases posteriores.

**Proyectos** (sobre la conversación). Un proyecto es una carpeta tuya, por
defecto `Documentos/Swarmbly/<Proyecto>`, con `sources/` (documentos),
`memory/` (glosario y notas), `chats/` (las conversaciones, una por archivo)
y `exports/` (paquetes `.swarmbly`). Una conversación del proyecto solo lee
sus documentos y su memoria; tus fuentes personales se añaden solo si marcas
*Incluir mis fuentes personales*, y una conversación personal nunca lee un
proyecto. *Exportar .swarmbly* guarda documentos, memoria y chats con el
SHA-256 de cada archivo y nunca lleva claves API. *Restaurar* comprueba cada
hash antes de escribir y restaura en una carpeta nueva; en otra computadora
vuelven los chats y sus citas siguen apuntando al párrafo correcto. *Cerrar
proyecto* lo quita de la app y deja la carpeta. Si la carpeta está
sincronizada (iCloud, Dropbox, OneDrive, Google Drive), la app te avisa. Para que el proyecto recuerde algo, empieza el mensaje con *Recuerda:* o
*Memoriza*: la app lo guarda, con fecha, en `memory/notas.md` antes de
responder (en una conversación personal, en `notas.md` de tus fuentes), y las
siguientes respuestas lo encuentran. *Documentos* muestra qué puede leer el
proyecto y por qué un archivo no dio nada. Si pides recordar algo en medio
de un mensaje, o defines o corriges un término, aparece una propuesta de
memoria y glosario bajo la respuesta: la editas y la confirmas con *Guardar
en memoria*; una entrada marcada *Privado* (o `| privado`) no se usa en
búsquedas públicas, aunque las respuestas locales sí la usan. Para buscar en
internet, la respuesta ofrece *Buscar en línea*
con el texto exacto que se enviaría a PubMed y Wikipedia; lo revisas y lo
apruebas. Una etiqueta que no corresponde a ninguna fuente se marca como
*cita sin fuente*.

**Consultas públicas con tu sí.** Si la pregunta trata de ti o de tus
documentos y además pediría una fuente pública, la respuesta se escribe sin
consultarla y ofrece *Buscar también en fuentes públicas*, con los nombres
que se enviarían; el sí vale solo para esa pregunta.

**Settings.** Perfiles *Automatic*, *Custom* y *Advanced*; pestañas
Recommended, General, Models, Swarm, Privacy, Results, Permissions y System.
Mínimo de respuestas por microtarea = réplicas desde el inicio; máximo =
techo incluyendo intentos extra. Las descargas muestran tamaño y licencia y
requieren el permiso correspondiente.

**Primer arranque: el sandbox de código y la exportación de diagnóstico.**
La receta 5 compila una vez el Python WebAssembly: unos 5 s y 3,3 GB de
memoria en un Mac Apple Silicon, unos 60 s en una máquina de 2 vCPU con 8 GB.
La App lo prepara desde el primer arranque, no dentro de una solicitud: si el
complemento opcional `[sandbox]` está instalado y la caché compilada falta o
está desactualizada, aparece un aviso en la app y en el asistente inicial con
el tiempo y la memoria previstos y los botones **Preparar ahora** / **Más
tarde**. Si eliges **Más tarde**, el aviso se oculta una semana y la receta 5
sigue sin estar disponible hasta que la prepares desde Ajustes o con la opción
del instalador. La compilación ocurre en segundo plano (`preparando`, luego `listo`,
o `falló` con la razón) y el chat sigue funcionando. Hasta que está lista, la
receta 5 explica por qué no está disponible y la respuesta continúa sin ella;
la compilación nunca se paga dentro de una solicitud. Con menos de 4 GB de
memoria libre, el arranque automático y un clic normal en **Preparar ahora**
no inician la compilación; cierra otras aplicaciones o usa una computadora con
más memoria. Si aun así necesitas la receta 5 en esa máquina, **Preparar de
todos modos** la inicia tras un aviso: la compilación puede tardar minutos y
ralentizar la computadora o usar swap, así que cierra otras aplicaciones
primero. Esa anulación nunca es automática, el botón normal mantiene el
mínimo, y el estado y la exportación de diagnóstico registran que se forzó.
La línea de comandos tiene la misma opción explícita,
`--prepare-sandbox --force`; el instalador para todo el proyecto nunca la pasa
por sí solo.
El tiempo y el pico de memoria medidos se quedan
en este equipo y aparecen en la exportación de diagnóstico; el mismo paso está
en **Ajustes → Sistema**.
**Exportación de diagnóstico.** **Ajustes → Sistema → Exportación de
diagnóstico → Revisar y guardar…** escribe un JSON y un texto legible. La
pantalla muestra el texto y el JSON exactos antes de guardar, y al guardar se
escribe esa misma instantánea. Adjunta cualquiera de los dos a un informe de
error: solo contiene versiones de App/LCE/Core, sistema y arquitectura,
versión de Python, clase de CPU/RAM/GPU, complementos instalados, si Ollama
responde y sus etiquetas de modelo, el estado del sandbox y sus mediciones (incluido si se forzó la
anulación por poca memoria), contadores P2P (escucha, pares, círculos, relay configurado y códigos de envío)
y los últimos códigos de error con fecha. Nunca contiene identificadores de
nodo ni claves, nombres, nombres de círculo o sus identificadores, nombres de
miembros, direcciones IP ni nombres de host, rutas bajo tu carpeta personal,
nombres de proyectos, títulos de documentos, preguntas, respuestas, glosario,
memoria, claves de API ni el host del relay. En la terminal:
`swarmbly-app doctor-export`.

**Sin ventana:** `./launch.sh --headless` y `swarmbly-app config set …` para
equipos que solo prestan cómputo. **Accesibilidad:** todo es operable con
teclado, con foco visible; *Reduce motion* desactiva las animaciones.
