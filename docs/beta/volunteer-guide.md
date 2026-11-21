# Volunteer guide · Guía para la persona voluntaria

**Language / Idioma:** [English](#english) · [Español](#español)

> **DRAFT — to be reviewed by the maintainer.** · **BORRADOR — pendiente de revisión por el mantenedor.**

---

<a name="english"></a>

## English

### Welcome

Thank you for testing Swarmbly AI 3.5. This is alpha software: keep backups,
do not use it for anything urgent, and tell us what breaks. The beta has no
telemetry; nothing is uploaded unless you choose to send it.

### Before you start

- A computer with **8 GB RAM or more**, 10 GB free disk, macOS 12+, Windows
  10/11, or a 64-bit Linux.
- The invitation from your circle owner: a code, a small file, or a QR image.
- Python 3.11+ is not required: the installer finds or helps you install it.

### 1. Install

1. Download the release files. If you want, verify them first with
   [`docs/INSTALL.md`](../INSTALL.md) (checksums and Sigstore signature).
2. Run the installer for your system: `install.command` on macOS,
   `install.sh` on Linux, `install.bat` on Windows.
3. Choose **Quick install**. The installer explains everything before it starts.
4. The installer may prepare the sandbox at the end. That is a one-time
   WebAssembly compile: about 5 s on an Apple-silicon Mac or 60 s on a 2-vCPU
   Linux machine, about 3.3 GB of memory, cached afterwards. If the machine has
   less than 6 GB available, the app offers it on first launch instead.
5. Open Swarmbly from the desktop shortcut or the `swarmbly` command.

macOS Gatekeeper or Windows SmartScreen may warn while the paid Apple/Windows
signing accounts are not configured. Do not disable the system security; see
[`docs/releases/SIGNING.md`](../releases/SIGNING.md) for the current state.

### 2. Join a circle

1. Open **Settings → Circle** and choose **Join with an invitation**.
2. Paste the invitation code, choose the invitation file, or scan the QR.
3. The owner admits you by signing a manifest version that lists your node.
   Until then the circle does not work for you.
4. When you ask a circle question, the app may connect automatically to other
   members through the relay. It does not ask for a prompt for every pair.

### 3. What the relay sees

The relay is a small service run by your circle owner (or by someone the owner
trusts). It forwards encrypted bytes and can see **metadata**: circle and node
identifiers, who pairs with whom, when, how many bytes, and IP addresses. It
does **not** see your documents, prompts, answers, model files or keys. The
operator is asked to keep metadata logs for 7 days. Your circle owner also sees
the membership manifest (node ids and display names).

### 4. If something fails

1. Run `swarmbly doctor` in a terminal and copy its report.
2. Also find `install.log` in the folder where you installed Swarmbly.
3. Remove names, e-mail addresses, your home-folder path, and anything private.
4. Open a **beta bug** issue with the template and paste the report. If you
   prefer not to publish it, say so in the issue and wait for the maintainer.
5. Never attach documents, chats, prompts, answers, keys or invitations.

### 5. Leaving

- **Settings → Circle → Leave** removes the circle from your app.
- Ask the owner to revoke you; a new signed manifest then removes your node.
- Uninstalling keeps your Swarmbly data unless you confirm deletion.
- To withdraw from the beta, stop using it, leave the circle and ask the
  maintainer to close or redact your issue. See
  [`consent-and-privacy.md`](consent-and-privacy.md).

---

<a name="español"></a>

## Español

### Bienvenida

Gracias por probar Swarmbly AI 3.5. Es software alfa: mantén copias de
seguridad, no lo uses para nada urgente y cuéntanos qué falla. La beta no tiene
telemetría; no se sube nada salvo que tú decidas enviarlo.

### Antes de empezar

- Un equipo con **8 GB de RAM o más**, 10 GB libres, macOS 12+, Windows 10/11
  o Linux de 64 bits.
- La invitación de quien administra tu círculo: un código, un archivo pequeño o
  una imagen QR.
- No necesitas Python 3.11+: el instalador lo encuentra o te ayuda a
  instalarlo.

### 1. Instalar

1. Descarga los archivos de la versión. Si quieres, verifícalos antes con
   [`docs/INSTALL.md`](../INSTALL.md) (sumas y firma Sigstore).
2. Ejecuta el instalador de tu sistema: `install.command` en macOS,
   `install.sh` en Linux, `install.bat` en Windows.
3. Elige **Instalación rápida**. El instalador explica todo antes de empezar.
4. Puede que prepare la caja al final. Es una compilación WebAssembly de una
   sola vez: unos 5 s en un Mac con chip Apple o 60 s en un Linux de 2 vCPU,
   unos 3,3 GB de memoria, y después queda en caché. Si hay menos de 6 GB
   disponibles, la App lo ofrece en el primer arranque.
5. Abre Swarmbly desde el acceso directo o con el comando `swarmbly`.

macOS Gatekeeper o Windows SmartScreen pueden avisar mientras no estén
configuradas las cuentas de pago de Apple y Windows. No desactives la seguridad
del sistema; consulta [`docs/releases/SIGNING.md`](../releases/SIGNING.md) para
el estado actual.

### 2. Unirse a un círculo

1. Abre **Ajustes → Círculo** y elige **Unirse con una invitación**.
2. Pega el código, elige el archivo de invitación o escanea el QR.
3. Quien administra te admite firmando una versión del manifiesto que incluye
   tu nodo. Hasta entonces el círculo no funciona para ti.
4. Cuando haces una pregunta al círculo, la App puede conectarse
   automáticamente con otros miembros a través del relay. No pregunta por cada
   emparejamiento.

### 3. Qué ve el relay

El relay es un servicio pequeño que ejecuta quien administra tu círculo (o
alguien de su confianza). Reenvía bytes cifrados y puede ver **metadatos**:
identificadores de círculo y nodo, quién se empareja con quién, cuándo, cuántos
bytes y direcciones IP. **No** ve tus documentos, prompts, respuestas, modelos
ni claves. Se pide al operador que guarde los registros de metadatos 7 días.
Quien administra el círculo también ve el manifiesto de membresía
(identificadores y nombres visibles).

### 4. Si algo falla

1. Ejecuta `swarmbly doctor` en una terminal y copia el informe.
2. Busca también `install.log` en la carpeta donde instalaste Swarmbly.
3. Quita nombres, correos, la ruta de tu carpeta personal y lo que sea privado.
4. Abre una incidencia **beta bug** con la plantilla y pega el informe. Si
   prefieres no publicarlo, dilo en la incidencia y espera al mantenedor.
5. No adjuntes documentos, conversaciones, prompts, respuestas, claves ni
   invitaciones.

### 5. Salir

- **Ajustes → Círculo → Salir** quita el círculo de tu App.
- Pide a quien administra que te revoque; una nueva versión firmada del
  manifiesto quita tu nodo.
- Desinstalar conserva tus datos de Swarmbly salvo que confirmes borrarlos.
- Para retirarte de la beta, deja de usarla, sal del círculo y pide al
  mantenedor que cierre o rectifique tu incidencia. Ver
  [`consent-and-privacy.md`](consent-and-privacy.md).
