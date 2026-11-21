# Physical P2P test — no IPs typed

Acceptance test of Phase 2: two or more computers on the **same LAN**
discover each other (mDNS), authenticate (Ed25519 bound to TLS 1.3) and
complete a real distributed micro-task — **without anyone typing an IP**.
*[Español](#español) below.*

> **3.5 note.** New installations admit peers only through a trusted circle
> (D-015). This physical test keeps the 3.4 LAN behaviour on purpose: set
> `circle.admission_mode` to `own_devices` on every node, or create a circle
> and invite the other node (see *Trusted circles* in `USER_GUIDE.md`). The
> demo scripts in section 0 set `own_devices` themselves.

## 0. Rehearsal on one machine (optional, 1 minute)

```bash
.venv/bin/python scripts/two_nodes_demo.py --fake          # protocol path, no models
.venv/bin/python scripts/multi_node_demo.py --fake --workers llama3.2:3b qwen2.5:3b --k 2
```

`--fake` replaces the models with canned answers: it validates discovery,
handshake, packets, scheduling, signatures and assembly — never model quality.
Drop `--fake` to use real Ollama models (they must already be installed;
the demos never download anything).

## 1. Preparation (every computer)

1. Install and check: `./launch.sh --setup-only` (see `INSTALL.md`).
2. Have one model in Ollama — `ollama pull llama3.2:3b`, or download it from
   the app after allowing downloads.
3. Firewall: allow **TCP 9765** (P2P) and **UDP 5353** (mDNS). On macOS accept
   the *Local Network* and incoming-connections prompts the first time.
4. Same network segment; guest Wi-Fi and "client isolation" block mDNS.

## 2. Test A — two computers

**Worker** (no window needed):

```bash
swarmbly-app config set swarm.worker_enabled true
swarmbly-app config set swarm.lan_enabled true
swarmbly-app config set model.model_name llama3.2:3b
./launch.sh --headless          # or: swarmbly-app headless
```

**Client:**

```bash
swarmbly-app config set swarm.lan_enabled true
swarmbly-app config set privacy.tier GLOBAL
swarmbly-app config set model.model_name gemma2:2b
./launch.sh                     # or: swarmbly-app
```

(`swarmbly-app` is in `.venv/bin/`; activate the environment first with
`source .venv/bin/activate`.)

Within a few seconds the client's **Swarm** view shows the worker as
*connected · authenticated · worker* (with the interface you can also do all
of this from the **Swarm** view: *Local network* on, *Share this computer* on,
and Settings → Privacy → *Privacy tier* GLOBAL on the client). In Chat, mode **Swarm LAN**, send:

> Extract one key fact per item from the following list of five items:
> apples, bridges, comets, drums, electrons. List 5 bullet points, one per
> item, separately.

Expected: the pipeline completes with `executed: distributed`; VERIFICATION
shows **partial** (signatures verified, Layer-1 not available); the worker's
"tasks served" increases. Free prose ("write an essay about…") is answered
locally with the reason shown — that is correct behaviour (no structural
partition).

## 3. Test B — five computers (1 client + 4 workers)

Give each worker a different family (`llama3.2:3b`, `qwen2.5:3b`,
`phi3.5:3.8b`, `granite3.1-dense:2b`) and on the client also set:

```bash
swarmbly-app config set swarm.k_min 2
swarmbly-app config set swarm.k_max 3
```

Verify in the Swarm view and in *Explore processing*: 4 workers authenticated; every task's replicas come from
**two different families**; CONSENSUS shows mean agreement and HIGH/MEDIUM/LOW
units — read as *agreement, not accuracy* (SwarmblyAI L13, L23).

## 4. If discovery fails

Multicast may be blocked. Connect manually from the client (Swarm view →
*Connect by address*), or with the API token written to the data directory:

```bash
TOKEN=$(cat "$HOME/Library/Application Support/Swarmbly/api_token")   # macOS
curl -X POST http://127.0.0.1:8765/api/swarm/connect \
  -H "X-Swarmbly-Token: $TOKEN" -H 'Content-Type: application/json' \
  -d '{"host":"192.168.1.20","port":9765}'
```

## 5. Two machines on different networks, through a circle relay

Use this when the two computers are **not** on the same LAN. The circle owner
runs a small relay on a host with a reachable TCP port (a VPS or a home server);
members connect outbound to it. The relay only splices the two TLS streams: it
sees who, when and how many bytes, never the task content.

**On the relay host** (from the umbrella checkout, not this App repo):

```bash
# Self-signed certificate: members pin its SHA-256, no public CA is needed.
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 \
  -keyout relay-key.pem -out relay.pem -days 365 -nodes \
  -subj "/CN=swarmbly-relay"

# SHA-256 of the DER certificate: this is the pin for the circle settings.
openssl x509 -in relay.pem -outform DER | shasum -a 256

# Serve the operator's bootstrap directory; an accepted owner push is
# persisted here as the current signed manifest.
python -m relay.server --manifest /srv/swarmbly-relay/circles \
  --cert relay.pem --key relay-key.pem --host 0.0.0.0 --port 8765
```

Open **TCP 8765** in the firewall (or 443 with TCP passthrough; a reverse proxy
that terminates TLS breaks pinning). The relay user must be able to write the
directory: accepted owner pushes replace the circle's file there.

**On the owner's App:**

1. **Bootstrap once, before setting the relay.** Create the circle; the App
   writes its first signed manifest to
   `<data>/circles/relay-publish/<circle_id>.json`. Copy that file to the
   relay's `circles/` directory once:
   ```bash
   scp "<data>/circles/relay-publish/<circle_id>.json" \
     relay-host:/srv/swarmbly-relay/circles/
   ```
   The first relay manifest must come from the operator directory; a push for
   a circle the relay does not serve yet gets `unknown_circle`, and the circle
   card says so with the hint that the operator must install it.
2. **Swarm → Trusted circles → Set relay…**: host, port and the 64-hex pin.
   The pin is mandatory; the App refuses an address without it. This signs the
   next version, which the App now pushes over the network.
3. After the bootstrap, the owner's App **pushes every new signed version
   over a registered connection**. It retries with backoff while the relay is
   unreachable and keeps only the newest unacknowledged version queued.
   The file in `circle.relay_publish_dir` stays as the bootstrap copy and the
   fallback; no periodic `rsync` is needed in normal operation. If the push
   cannot run at all, the App still writes the file and the operator can copy
   it.
4. Both nodes receive the new manifest on the control plane and show
   **registered** next to the relay in the circle card. The card also shows
   the pushed/acknowledged version, any pending version and a refusal code:
   `unknown_circle` (install the first manifest), `rate_limited` (the relay's
   30 pushes per hour), `stale_version` (the relay already has a newer
   version). A revoked member is refused and its open relay session is cut.
5. On a relay change the App pushes the same new version to the **old** relay
   too, then to the new one, so the old endpoint stops admitting members the
   new version removed.

**Test:** on the member on the *other* network, Chat mode **Swarm LAN**, send
the five-item request above. Expected: `executed: distributed`, the peer's
**Link** column says *relayed*, and the receipt has a `saltos_relay` hop naming
the relay host and stating that it saw metadata only. Direct addresses are
still tried first; unplug the relay and direct LAN peers keep working (the
relay circle shows *unreachable*, with backoff). If the circle card shows a
**security warning** instead of *registered*, the certificate did not match the
pin: stop, verify the fingerprint on the relay host, and only then publish a
new manifest version with the right pin.

## 6. What this validates — and what it does not

- ✅ Discovery without IPs, channel-bound handshake, capability exchange,
  parallel dispatch, signature checks, consensus, assembly, metadata.
- ⚠️ Real LAN latency, firewalls and multicast conditions (the physical part).
- ❌ Hole punching / NAT traversal (3.6). The relay is the off-LAN path in 3.5.
  Layer-1 verification (no normative construction upstream).

---

## Español

Prueba física de la Fase 2 (prepara cada equipo con `./launch.sh --setup-only`): dos o más computadoras en la **misma LAN** se
descubren por mDNS, se autentican (Ed25519 ligado a TLS 1.3) y completan una
microtarea real **sin teclear ninguna IP**. Ensayo previo en una sola máquina:
`python scripts/two_nodes_demo.py --fake` (valida el camino del protocolo, no
la calidad de los modelos). En cada equipo: instalar, tener un modelo en
Ollama, permitir **TCP 9765** y **UDP 5353**, aceptar el permiso de *Red local*
en macOS y estar en el mismo segmento (las redes de invitados bloquean mDNS).
Worker: `worker_enabled true`, `lan_enabled true`, `model_name`, y
`swarmbly-app headless`. Cliente: `lan_enabled true`, `privacy.tier GLOBAL`,
`model_name`, y `swarmbly-app`. En unos segundos el monitor muestra el worker
*conectado · autenticado*; en el chat, modo Swarm LAN, envía la solicitud de
los cinco ítems. Esperado: `executed: distributed`, VERIFICACIÓN **parcial**,
y el contador del worker aumenta. La prosa libre se responde localmente con la
razón visible (es lo correcto). Con cinco equipos y `k_min 2`, las réplicas de
cada tarea vienen de dos familias distintas; el consenso es *acuerdo, no
exactitud*. Si mDNS falla, conecta por dirección desde Ajustes → Swarm o con
la API usando el token del directorio de datos.

**Dos equipos en redes distintas, por el relay del círculo.** El dueño ejecuta
el relay del prototipo (checkout umbrella) en un host con **TCP 8765** abierto,
con un certificado autofirmado; calcula el pin SHA-256 del DER y lo pone en
**Swarm → Círculos de confianza → Configurar relay…** (el pin es obligatorio).
El operador instala **una vez** el primer manifiesto firmado del círculo en el
directorio `circles/` del relay (la App lo deja en
`<data>/circles/relay-publish/<circle_id>.json`; cópialo a mano). Sin ese
arranque el relay responde `unknown_circle` y la tarjeta del círculo lo indica.
Después la App del dueño **envía por red cada versión firmada** por una conexión
registrada, reintenta con backoff si el relay está caído y solo conserva la
versión más nueva sin confirmar; el archivo queda como copia de arranque y
respaldo. La tarjeta muestra la versión confirmada, la pendiente y el código de
rechazo (`unknown_circle`, `rate_limited` —30 envíos por hora—,
`stale_version`). Si cambia el relay, la misma versión se envía también al
relay anterior para que deje de admitir a los miembros retirados. Ambos nodos
muestran **registrado**; el miembro de la otra red envía la solicitud de cinco
ítems en modo Swarm LAN. Esperado: `executed: distributed`, la columna
**Enlace** dice *por relay* y el recibo incluye `saltos_relay` con el host y
que solo vio metadatos (quién, cuándo, bytes), nunca el contenido. Las
direcciones directas se prueban primero; si el relay cae, los pares de la LAN
siguen funcionando. Un aviso de seguridad significa que el certificado no
coincide con el pin: verifica la huella en el host del relay antes de publicar
una versión nueva.
