# User guide

How to use Swarmbly App once it is running. Installation is in
[INSTALL.md](INSTALL.md). *[Español](#español) below.*

The app has four views, in the sidebar (bottom bar on a phone): **Chat**,
**Swarm**, **Memory** and **Settings**. The node card under the navigation
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

## 4. Memory

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

## 5. Settings

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

## 6. Without a window (headless)

```bash
./launch.sh --headless                        # or: swarmbly-app headless
swarmbly-app config set swarm.worker_enabled true
swarmbly-app config set swarm.lan_enabled true
swarmbly-app config set model.model_name llama3.2:3b
```

Useful for a second computer or a Raspberry Pi that only lends compute.
`swarmbly-app status` prints version, node id and data directory.

## 7. Keyboard and accessibility

Every control is reachable with the keyboard and shows a visible focus ring;
*Skip to content* is the first tab stop. *Reduce motion* (Settings → General,
or your system preference) turns off pulses and animations. The theme is dark
by default; a light theme is in Settings → General.

---

## Español

La app tiene cuatro vistas: **Chat**, **Swarm**, **Memory** y **Settings**.
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

**Memory.** C0 activa; C1 seleccionable (la carpeta de fuentes está lista,
la recuperación en las respuestas viene después); C2–C4 en fases
posteriores.

**Settings.** Perfiles *Automatic*, *Custom* y *Advanced*; pestañas
Recommended, General, Models, Swarm, Privacy, Results, Permissions y System.
Mínimo de respuestas por microtarea = réplicas desde el inicio; máximo =
techo incluyendo intentos extra. Las descargas muestran tamaño y licencia y
requieren el permiso correspondiente.

**Sin ventana:** `./launch.sh --headless` y `swarmbly-app config set …` para
equipos que solo prestan cómputo. **Accesibilidad:** todo es operable con
teclado, con foco visible; *Reduce motion* desactiva las animaciones.
