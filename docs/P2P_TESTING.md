# Physical P2P test — no IPs typed

Acceptance test of Phase 2: two or more computers on the **same LAN**
discover each other (mDNS), authenticate (Ed25519 bound to TLS 1.3) and
complete a real distributed micro-task — **without anyone typing an IP**.
*[Español](#español) below.*

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

## 5. What this validates — and what it does not

- ✅ Discovery without IPs, channel-bound handshake, capability exchange,
  parallel dispatch, signature checks, consensus, assembly, metadata.
- ⚠️ Real LAN latency, firewalls and multicast conditions (the physical part).
- ❌ Internet swarms / NAT traversal (Phase 3). Layer-1 verification (no
  normative construction upstream).

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
