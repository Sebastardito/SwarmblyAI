# Installing Swarmbly AI · Instalar Swarmbly AI

**Language / Idioma:** [English](#english) · [Español](#español)

---

## English

### Requirements

| | Minimum | Recommended |
|---|---|---|
| System | macOS 12+, Linux (x86-64 or ARM64), Windows 10/11 | — |
| Python | 3.11 | 3.12 (the App, its dependencies and the native web search need 3.11+) |
| Memory | 8 GB RAM (1.5 B model) | 16 GB+ (3–7 B models) |
| Disk | 3 GB | 10 GB (several models) |

### Running the installer

| System | Command |
|---|---|
| macOS | double-click `install.command`, or `./install.sh` |
| Linux | `./install.sh` |
| Windows | double-click `install.bat`, or `.\install.ps1` |

The first screen explains what Swarmbly is and asks how to install:

1. **Quick install** — shows everything it will do (including which models and how many GB) and asks once to start. From then on there are no questions. Steps that need an administrator password (installing Ollama or pdftotext through the system package manager on Linux) are skipped and listed at the end with the exact command.
2. **Custom install** — goes through each step, explains it and lets you accept or skip it, choose the environment folder, the models and a documents folder for the local memory.
3. **Check an existing installation** (`--doctor`).
4. **Uninstall** (`--uninstall`).

### What each step does

| Step | What it does | Where |
|---|---|---|
| Python | Checks the version; the system Python is never modified | — |
| Isolated environment | Creates a virtual environment (`uv` if available, otherwise `venv`) | `.venv/` in this folder (custom: any folder) |
| Components | Installs SwarmblyCore and SwarmblyLCE from their folders, then SwarmblyApp without its git pins (so pip does not download another copy of Core or LCE), then the app's other dependencies | the environment |
| Sandbox preparation | Compiles the WebAssembly module once, before first use, only when at least 6 GB of memory is available (about 5 s on an Apple-silicon Mac, about 60 s on a 2-vCPU Linux machine, about 3.3 GB of memory; cached afterwards). With less memory, or if the App cannot prepare it yet, the App offers it on first launch | the environment cache |
| Ollama | Starts it if installed; otherwise installs it (macOS: Homebrew; Windows: winget; Linux: the official script, which needs `sudo`) | system |
| Models | A chat model that fits your memory (≥ 24 GB RAM: qwen2.5:7b; ≥ 10 GB: qwen2.5:3b; otherwise qwen2.5:1.5b) and `nomic-embed-text` for the local memory. Custom: choose, or add another model family | Ollama |
| pdftotext | Lets the local memory read PDFs (macOS: `brew install poppler`; Linux: `poppler-utils`; Windows: scoop or choco) | system |
| SearXNG | Local web search engine (DuckDuckGo, Google Scholar, PubMed, OpenAlex…), listening on 127.0.0.1 only; it starts and stops with the app | Swarmbly data folder |
| Your documents | Custom only (or `--sources`): a folder the local memory reads in place | app settings |
| Shortcuts | `swarmbly` launcher (`swarmbly doctor` to check), `~/.local/bin/swarmbly` on macOS/Linux, desktop shortcut (and Start menu on Windows) | `.swarmbly/`, desktop |

Everything is written to `install.log` in this folder.

### Options

```
--quick            quick install, no questions (with --yes: not even "start?")
--custom           step by step
--doctor           check an existing installation
--uninstall        remove the environment, launchers and shortcuts (data kept unless you confirm)
--dry-run          show the plan and the commands, change nothing
--lang es|en       language of the installer
--venv PATH        environment folder (default: .venv here)
--dev              editable install and test tools (for contributors)
--sources PATH     a documents folder for the local memory
--skip LIST        skip steps: ollama,models,pdf,searxng,sandbox,shortcuts,sources
--skip-prepare-sandbox
                   do not compile the sandbox at install time; the App offers it on first launch
```

### Without the installer

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install ./SwarmblyCore ./SwarmblyLCE
pip install --no-deps ./SwarmblyApp
pip install "fastapi>=0.110" "uvicorn[standard]>=0.29" "httpx>=0.27" "psutil>=5.9" "cryptography>=41" "zeroconf>=0.132"
swarmbly-app            # opens http://127.0.0.1:8765
```

### Verifying a release

The release page publishes the archives, the installer bundle, the Docker image
digest, `SHA256SUMS`, `SHA256SUMS.bundle` and `SIGNING.txt`. The checksum file
covers every artifact; the Sigstore bundle signs the checksum file with the
GitHub Actions identity of the release workflow (no project key is stored).

1. Download the artifacts into one directory.
2. Check the checksums:

   ```bash
   # Linux
   sha256sum -c SHA256SUMS
   # macOS
   shasum -a 256 -c SHA256SUMS
   ```

   On Windows, `Get-FileHash -Algorithm SHA256 <file>` and compare with
   `SHA256SUMS` by hand.
3. Check the signature with [cosign](https://docs.sigstore.dev/cosign/):

   ```bash
   cosign verify-blob --bundle SHA256SUMS.bundle \
     --certificate-identity-regexp \
     'https://github.com/Sebastardito/SwarmblyAI/.github/workflows/release.yml@.*' \
     --certificate-oidc-issuer https://token.actions.githubusercontent.com \
     SHA256SUMS
   ```

   The exact identity of the run is recorded in `SIGNING.txt`. `cosign` may
   fetch the public Sigstore trusted root on first use; pass
   `--trusted-root trusted_root.json` to verify without that fetch.
4. Or use the included helper, which runs both checks:

   ```bash
   python scripts/verify_release.py --dir .
   # No cosign installed? --checksums-only still catches corruption,
   # but not who signed the release.
   ```

The signature proves that the release workflow in this repository produced
`SHA256SUMS`; the checksums prove that the files were not changed after signing.
The per-file Docker image digest is in `swarmbly-<version>-docker-image.txt`;
the image itself is signed keyless in the registry (`cosign verify` with the
`docker.yml` identity and the same issuer).

**OS warnings.** macOS Gatekeeper and Windows SmartScreen will still warn until
the maintainer adds the Apple and Windows signing secrets described in
[`docs/releases/SIGNING.md`](releases/SIGNING.md). That is expected in the
beta; do not disable the operating system's security checks.

### Troubleshooting

| Symptom | What to do |
|---|---|
| "needs Python 3.11" | Install Python from python.org (macOS: `brew install python@3.12`; Linux: your package manager), or `PYTHON=/path/to/python3.12 ./install.sh` |
| First launch says it is preparing the sandbox | Expected once: about 5 s on an Apple-silicon Mac or 60 s on a 2-vCPU Linux machine, about 3.3 GB of memory; it is cached afterwards. The installer does this only with ≥ 6 GB available |
| Ollama "pending" at the end | Run the command shown, or install from <https://ollama.com/download>, then `swarmbly doctor` |
| PDFs "cannot be read" in Memory | Install pdftotext (command in the summary) and reopen the app |
| Web search "not answering" | Settings → Privacy → Web search → Reinstall; the app's own installer explains what is missing |
| Port 8765 busy | `swarmbly --port 8766` |
| Anything else | `swarmbly doctor`, then open an issue with `install.log` (remove anything private first) |

---

## Español

### Requisitos

| | Mínimo | Recomendado |
|---|---|---|
| Sistema | macOS 12+, Linux (x86-64 o ARM64), Windows 10/11 | — |
| Python | 3.11 | 3.12 (la App, sus dependencias y la búsqueda web nativa necesitan 3.11+) |
| Memoria | 8 GB de RAM (modelo de 1,5 B) | 16 GB o más (modelos de 3–7 B) |
| Disco | 3 GB | 10 GB (varios modelos) |

### Ejecutar el instalador

| Sistema | Comando |
|---|---|
| macOS | doble clic en `install.command`, o `./install.sh` |
| Linux | `./install.sh` |
| Windows | doble clic en `install.bat`, o `.\install.ps1` |

La primera pantalla explica qué es Swarmbly y pregunta cómo instalar:

1. **Instalación rápida**: muestra todo lo que hará (incluidos qué modelos y cuántos GB) y pregunta una vez si empieza. Desde ahí no hay más preguntas. Los pasos que necesitan contraseña de administrador (instalar Ollama o pdftotext con el gestor de paquetes en Linux) se omiten y se listan al final con el comando exacto.
2. **Instalación personalizada**: recorre cada paso, lo explica y deja aceptarlo u omitirlo, elegir la carpeta del entorno, los modelos y una carpeta de documentos para la memoria local.
3. **Comprobar una instalación existente** (`--doctor`).
4. **Desinstalar** (`--uninstall`).

### Qué hace cada paso

| Paso | Qué hace | Dónde |
|---|---|---|
| Python | Comprueba la versión; nunca modifica el Python del sistema | — |
| Entorno aislado | Crea un entorno virtual (`uv` si está, si no `venv`) | `.venv/` en esta carpeta (personalizada: cualquier carpeta) |
| Componentes | Instala SwarmblyCore y SwarmblyLCE desde sus carpetas, después SwarmblyApp sin sus fijaciones de git (para que pip no descargue otra copia de Core o LCE) y luego las demás dependencias de la app | el entorno |
| Preparación de la caja | Compila una vez el módulo WebAssembly antes del primer uso, solo si hay al menos 6 GB de memoria disponible (unos 5 s en un Mac con chip Apple, unos 60 s en un Linux de 2 vCPU, unos 3,3 GB de memoria; después queda en caché). Con menos memoria, o si la App aún no puede prepararlo, la App lo ofrece en el primer arranque | la caché del entorno |
| Ollama | Lo inicia si está instalado; si no, lo instala (macOS: Homebrew; Windows: winget; Linux: el script oficial, que necesita `sudo`) | sistema |
| Modelos | Un modelo de chat que quepa en tu memoria (≥ 24 GB de RAM: qwen2.5:7b; ≥ 10 GB: qwen2.5:3b; si no, qwen2.5:1.5b) y `nomic-embed-text` para la memoria local. Personalizada: eliges, o añades otra familia de modelos | Ollama |
| pdftotext | Permite que la memoria local lea PDF (macOS: `brew install poppler`; Linux: `poppler-utils`; Windows: scoop o choco) | sistema |
| SearXNG | Buscador web local (DuckDuckGo, Google Scholar, PubMed, OpenAlex…), que solo escucha en 127.0.0.1 y arranca y se detiene con la app | carpeta de datos de Swarmbly |
| Tus documentos | Solo en la personalizada (o con `--sources`): una carpeta que la memoria local lee en su sitio | ajustes de la app |
| Accesos directos | Lanzador `swarmbly` (`swarmbly doctor` para comprobar), `~/.local/bin/swarmbly` en macOS/Linux, acceso directo en el escritorio (y en el menú Inicio en Windows) | `.swarmbly/`, escritorio |

Todo queda registrado en `install.log`, en esta carpeta.

### Opciones

```
--quick            instalación rápida, sin preguntas (con --yes: ni siquiera «¿empezar?»)
--custom           paso a paso
--doctor           comprobar una instalación existente
--uninstall        borra el entorno, los lanzadores y los accesos directos (los datos se conservan salvo que lo confirmes)
--dry-run          muestra el plan y los comandos, sin cambiar nada
--lang es|en       idioma del instalador
--venv RUTA        carpeta del entorno (por defecto: .venv aquí)
--dev              instalación editable y herramientas de prueba (para colaboradores)
--sources RUTA     una carpeta de documentos para la memoria local
--skip LISTA       omitir pasos: ollama,models,pdf,searxng,sandbox,shortcuts,sources
--skip-prepare-sandbox
                   no compilar la caja al instalar; la App lo ofrece en el primer arranque
```

### Sin el instalador

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install ./SwarmblyCore ./SwarmblyLCE
pip install --no-deps ./SwarmblyApp
pip install "fastapi>=0.110" "uvicorn[standard]>=0.29" "httpx>=0.27" "psutil>=5.9" "cryptography>=41" "zeroconf>=0.132"
swarmbly-app            # abre http://127.0.0.1:8765
```

### Verificar una versión

La página de la versión publica los archivos, el paquete del instalador, el
digest de la imagen Docker, `SHA256SUMS`, `SHA256SUMS.bundle` y `SIGNING.txt`.
El archivo de sumas cubre todos los artefactos; el paquete Sigstore firma ese
archivo con la identidad de GitHub Actions del flujo de publicación (el
proyecto no guarda ninguna clave).

1. Descarga los artefactos en una misma carpeta.
2. Comprueba las sumas:

   ```bash
   # Linux
   sha256sum -c SHA256SUMS
   # macOS
   shasum -a 256 -c SHA256SUMS
   ```

   En Windows, usa `Get-FileHash -Algorithm SHA256 <archivo>` y compara a mano
   con `SHA256SUMS`.
3. Comprueba la firma con [cosign](https://docs.sigstore.dev/cosign/):

   ```bash
   cosign verify-blob --bundle SHA256SUMS.bundle \
     --certificate-identity-regexp \
     'https://github.com/Sebastardito/SwarmblyAI/.github/workflows/release.yml@.*' \
     --certificate-oidc-issuer https://token.actions.githubusercontent.com \
     SHA256SUMS
   ```

   La identidad exacta de la ejecución queda en `SIGNING.txt`. `cosign` puede
   descargar la raíz de confianza pública de Sigstore la primera vez; usa
   `--trusted-root trusted_root.json` para verificarla sin esa descarga.
4. O usa el ayudante incluido, que hace las dos comprobaciones:

   ```bash
   python scripts/verify_release.py --dir .
   # ¿Sin cosign? --checksums-only detecta corrupción,
   # pero no quién firmó la versión.
   ```

La firma demuestra que el flujo de publicación de este repositorio produjo
`SHA256SUMS`; las sumas demuestran que los archivos no cambiaron después de
firmarse. El digest de la imagen Docker está en
`swarmbly-<versión>-docker-image.txt`; la imagen se firma sin clave en el
registro (`cosign verify` con la identidad de `docker.yml` y el mismo emisor).

**Avisos del sistema.** macOS Gatekeeper y Windows SmartScreen seguirán
avisando hasta que el mantenedor añada los secretos de firma de Apple y
Windows descritos en [`docs/releases/SIGNING.md`](releases/SIGNING.md). Es lo
esperado en la beta; no desactives las comprobaciones de seguridad del sistema.

### Solución de problemas

| Síntoma | Qué hacer |
|---|---|
| «necesita Python 3.11» | Instala Python desde python.org (macOS: `brew install python@3.12`; Linux: tu gestor de paquetes), o `PYTHON=/ruta/a/python3.12 ./install.sh` |
| El primer arranque dice que prepara la caja | Es normal una vez: unos 5 s en un Mac con chip Apple o 60 s en un Linux de 2 vCPU, unos 3,3 GB de memoria; después queda en caché. El instalador solo lo hace con ≥ 6 GB disponibles |
| Ollama «pendiente» al final | Ejecuta el comando indicado, o instálalo desde <https://ollama.com/download>, y luego `swarmbly doctor` |
| PDF «no se puede leer» en Memoria | Instala pdftotext (el comando está en el resumen) y vuelve a abrir la app |
| Búsqueda web «sin responder» | Ajustes → Privacidad → Búsqueda web → Reinstalar; el instalador de la app explica qué falta |
| Puerto 8765 ocupado | `swarmbly --port 8766` |
| Cualquier otra cosa | `swarmbly doctor` y abre una incidencia con `install.log` (quita antes lo privado) |
