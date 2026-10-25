# Installation & first run

*[Español](#español) below.*

## Requirements

| | Needed | Notes |
|---|---|---|
| Python | 3.10 or newer | CI runs 3.10–3.13 |
| git | yes, for the first install | Installs the pinned SwarmblyAI and SwarmblyLCE commits |
| Model runner | recommended | [Ollama](https://ollama.com/download), or any OpenAI-compatible server (llama.cpp `--server`, vLLM) |
| Memory | 8 GB works for 1–3B models | The first-run assistant computes a budget for your machine |
| Network | none to start | Local-network discovery is off until you allow it |

Supported systems: macOS (Apple Silicon and Intel), Linux, Windows.

## The launcher (recommended)

```bash
git clone https://github.com/Sebastardito/SwarmblyApp.git
cd SwarmblyApp
./launch.sh            # macOS / Linux
launch.bat             # Windows
```

macOS: double-click `Swarmbly.command` in Finder to get the same thing in a
Terminal window. Closing the window stops the app.

The wrapper finds a Python 3.10+ interpreter (`python3.13` … `python3`, or the
one in `PYTHON=`) and runs `scripts/launch.py`, which uses only the standard
library. It goes through six checks and asks before every change:

```
  [1/6] Python        ok  3.12.4  /opt/homebrew/bin/python3.12
  [2/6] git           ok  /usr/bin/git
  [3/6] Environment   ok  .venv (Python 3.12.4)
  [4/6] Packages      ok  up to date
  [5/6] Ollama        ok  running, 2 model(s): llama3.2:3b, qwen2.5:3b
  [6/6] Port          ok  8765 free
```

| Check | When it is not ready |
|---|---|
| Python | Stops and tells you how to install 3.12 for your system |
| git | Needed only when packages must be installed |
| Environment | Offers to create `.venv` (or rebuild it if it was moved or its Python removed) |
| Packages | Offers to install or update inside `.venv` only. It reinstalls when `pyproject.toml` changes, when an import fails, or with `--reinstall` |
| Ollama | Optional. If installed but stopped, offers to start it; if missing, shows the official download page. The app also works with OpenAI-compatible servers |
| Port | If Swarmbly is already running there, opens it; if another program uses the port, picks the next free one |

On macOS the launcher also clears the hidden flag that sync tools sometimes
put on `.venv` (see Troubleshooting).

### Options

| Option | Effect |
|---|---|
| `--check` | Report only; change nothing, start nothing |
| `--setup-only` | Prepare everything, do not start |
| `--headless` | Start the node without the browser interface (worker computers, Raspberry Pi) |
| `--port N` | Interface port (default 8765) |
| `--yes` / `--no` | Answer every question yes / no (unattended runs) |
| `--dev` | Also install the test tools |
| `--reinstall` | Reinstall packages even if they look current |
| `--no-ollama` | Skip the Ollama check |
| `-- …` | Everything after `--` goes to `swarmbly-app`, e.g. `-- --data-dir ~/swarmbly-test` |

## Manual install

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
swarmbly-app                       # opens http://127.0.0.1:8765
```

Other commands:

```bash
swarmbly-app headless              # node without the interface
swarmbly-app status                # version, node id, data directory
swarmbly-app init                  # create the data directory and identity
swarmbly-app config get swarm      # read settings
swarmbly-app config set swarm.worker_enabled true
```

## First run

The first-run assistant walks through:

1. **System check** — OS, CPU, memory, storage, GPU (unknown when
   undetectable), Python packages (including the pinned SwarmblyAI and
   SwarmblyLCE commits), Ollama and ports. A missing Python package can be
   installed into the app's own environment after you confirm; Ollama itself
   is never installed for you.
2. **Recommended configuration** — derived from what was measured; each value
   says why and whether it is measured or estimated. Applying it keeps a
   backup (Settings → Recommended → Revert). It never turns on the network,
   sharing or a privacy tier.
3. **Models** — installed models and suggestions that fit your memory.
4. **Permissions** — whether Swarmbly may look for other Swarmbly computers on
   this network (mDNS) and whether it may download models through Ollama.
5. **Memory** — level C0 (none) or C1 (your sources, kept on this device).

Every step can be skipped and revisited in Settings.

**Downloads.** With the download permission on, choose a model and confirm
the dialog that shows its size and licence. Ollama does the download and
progress appears in the app. `ollama pull llama3.2:3b` in a terminal works
too.

**The session token.** The interface on `127.0.0.1` is protected by a token
created at every launch and embedded in the page the app serves; requests
without it are refused. Local scripts read it from `<data>/api_token`
(readable only by your user) and send it as the `X-Swarmbly-Token` header.

## Network ports

| Port | Protocol | Purpose | Opened when |
|---|---|---|---|
| 8765 | TCP, loopback only | Local interface and API | The app runs |
| 9765 | TCP | P2P sessions (TLS 1.3) | The app runs; other nodes connect only after a handshake |
| 5353 | UDP multicast | mDNS discovery | You allow local-network discovery |

macOS asks for *Local Network* access and incoming connections the first
time; allow both for swarms to work.

## Data locations

| OS | Data directory |
|---|---|
| macOS | `~/Library/Application Support/Swarmbly` |
| Linux | `~/.local/share/swarmbly` (or `$XDG_DATA_HOME/swarmbly`) |
| Windows | `%LOCALAPPDATA%\Swarmbly` |

Override with `--data-dir` or `SWARMBLY_DATA_DIR`. Inside: `config.json`,
`app.db` (conversations and metrics), `identity/` (your node key),
`sources/` and `wiki/` (memory), `output/` (exports and reports), `logs/`.
Nothing user-specific is ever written to the repository.

## Updating

```bash
git pull
./launch.sh            # notices the changed requirements and offers to update
```

## Uninstalling

Delete the repository folder (this removes `.venv`). To remove your
conversations, identity and settings too, delete the data directory above.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'swarmbly_app'`** (macOS) — Finder,
  sync agents or housekeeping scripts can set the `UF_HIDDEN` flag on `.venv`.
  Python silently skips hidden `.pth` files, so the editable install never
  loads (it seems to work inside the repo because the working directory hides
  the problem). The launcher fixes it on every start; by hand:
  `chflags -R nohidden .venv`.
- **`.venv` stopped working after moving the folder** — run `./launch.sh` and
  accept *Rebuild .venv*.
- **pip fails on `git+https://github.com/...`** — git is missing or GitHub is
  unreachable; install git (`xcode-select --install` on macOS) and retry.
- **"No inference backend detected"** — start Ollama, or set an
  OpenAI-compatible URL in Settings → Models.
- **Port already in use** — the launcher picks the next free port; or
  `./launch.sh --port 8766`.
- **`401 missing or invalid session token`** — the app was restarted; reload
  the page (scripts: read `<data>/api_token` again).
- **Other computers never appear** — see [P2P testing → If discovery
  fails](P2P_TESTING.md#4-if-discovery-fails).
- **Anything else** — Settings → System runs the same check as the first-run
  assistant; `./launch.sh --check` checks the installation itself.

---

## Español

**Requisitos:** Python 3.10 o más, git para la primera instalación y, de
preferencia, [Ollama](https://ollama.com/download) o un servidor compatible
con OpenAI. Funciona en macOS, Linux y Windows.

**Instalar y abrir:**

```bash
git clone https://github.com/Sebastardito/SwarmblyApp.git
cd SwarmblyApp
./launch.sh            # macOS / Linux  (Windows: launch.bat; macOS: doble clic en Swarmbly.command)
```

El lanzador revisa seis cosas y **pregunta antes de cada cambio**: Python,
git, el entorno `.venv` (lo crea o lo reconstruye), los paquetes (los instala
o actualiza solo dentro de `.venv`, y vuelve a hacerlo cuando cambia
`pyproject.toml`), Ollama (lo inicia si está instalado; si falta, muestra la
página oficial, nunca lo instala) y el puerto (si Swarmbly ya está abierto, lo
muestra; si otro programa lo usa, elige el siguiente libre). Opciones:
`--check`, `--setup-only`, `--headless`, `--port N`, `--yes`, `--no`, `--dev`,
`--reinstall`, `--no-ollama`, y `-- …` para pasar argumentos a `swarmbly-app`.

**Primer arranque:** revisión del sistema (con instalación consentida de
paquetes Python faltantes), configuración recomendada según tu hardware
(cada valor explicado, reversible, nunca activa la red ni el compartir),
modelos, permisos (buscar equipos en la red local; descargar modelos vía
Ollama mostrando tamaño y licencia) y memoria (C0 o C1). La interfaz local
está protegida por un token por arranque; los scripts lo leen de
`<data>/api_token`.

**Puertos:** 8765 (interfaz, solo local), 9765 TCP (sesiones P2P con TLS 1.3),
5353 UDP (mDNS, solo si lo permites). En macOS acepta los permisos de *Red
local* y de conexiones entrantes.

**Datos:** en el directorio por sistema operativo de la tabla anterior
(`--data-dir` o `SWARMBLY_DATA_DIR` para cambiarlo); nunca en el
repositorio. **Actualizar:** `git pull` y `./launch.sh`. **Desinstalar:**
borrar la carpeta del repositorio y, si quieres, el directorio de datos.

**Problemas frecuentes:** el error `No module named 'swarmbly_app'` en macOS
se debe a la marca oculta en `.venv` (el lanzador la corrige siempre); si
moviste la carpeta, acepta reconstruir `.venv`; si pip falla con
`git+https`, instala git; si no aparecen otros equipos, revisa
[P2P testing](P2P_TESTING.md#4-if-discovery-fails).
