# Consent and privacy · Consentimiento y privacidad

**Language / Idioma:** [English](#english) · [Español](#español)

> **DRAFT — to be reviewed by the maintainer.** This is not legal advice and
> makes no legal claim. It describes the beta's current practice.
>
> **BORRADOR — pendiente de revisión por el mantenedor.** No es asesoría legal
> ni hace afirmaciones legales. Describe la práctica actual de la beta.

---

<a name="english"></a>

## English

### Consent form

Participation is voluntary. You can stop at any time. Please tick what you
agree to; this form is a record for you and the maintainer, not a contract.

- [ ] I have read the volunteer guide and I understand that this is alpha
      software.
- [ ] I understand that Swarmbly has **no telemetry**: the app does not upload
      usage data, documents, prompts or answers by itself.
- [ ] I understand that the circle owner and the relay operator can see
      metadata (circle and node identifiers, pairing, time, bytes and IP
      addresses), but not my documents, prompts or answers.
- [ ] I understand that a GitHub issue is public, and that anything I paste
      there can be read by anyone.
- [ ] I will remove names, e-mail addresses, home-folder paths, documents,
      chats, prompts, answers, keys, invitations and member ids before sending
      a doctor export or a log.
- [ ] I agree to receive and send beta feedback through the GitHub issue
      tracker or the feedback form, using a handle if I prefer not to use my
      name.
- [ ] I understand that I can withdraw by leaving the circle, uninstalling the
      app and asking the maintainer to close or redact my issue.

Handle or pseudonym (optional): ______________________

Date: ______________________

### Privacy notice

**What is collected.** Only what you choose to write in an issue or feedback
form, plus the doctor export or `install.log` you choose to attach. There is no
account, no telemetry, no analytics and no automatic upload.

**What the doctor export contains.** The output of `swarmbly doctor`: operating
system and Python versions, package names and versions, pass/fail checks, Ollama
status, port checks, and the data-folder path. `install.log` contains the
installer's steps and command output. Both can contain your username or
home-folder path; remove or replace it before sending.

**What it never contains.** Your documents, conversations, prompts, answers,
model files, API keys, node private keys, invitations, circle member ids,
search queries or task payloads. If you see any of these, do not send the file
and tell the maintainer.

**Who can see what.**

- **The circle owner** sees the signed membership manifest (node ids and display
  names) and decides who is admitted or revoked.
- **The relay operator** (usually the circle owner) sees connection metadata:
  circle and node identifiers, who pairs with whom, time, bytes and IP
  addresses. The design asks the operator to keep metadata logs for 7 days and
  to keep them out of payload content.
- **The maintainer** sees the GitHub issues and any file you choose to send.
- **Other volunteers and the public** can read a public GitHub issue.

**How long it is kept.** Relay metadata: 7 days by the operator's policy. GitHub
issues and their attachments: until the issue is closed and deleted or redacted
at your request, subject to GitHub's own retention and to copies others may
have made (forks, caches, quotes). Local app data stays on your computer until
you delete it.

**What is never done.** No sale of data, no advertising profile, no automatic
telemetry, and no request for your documents to diagnose a bug.

**Withdrawing.** Leave the circle, uninstall the app (your data is kept unless
you confirm deletion), and ask the maintainer to close or redact your issue. If
you want a file removed, say which one in the issue.

**Security reports.** Do not open a public issue for a vulnerability that could
harm other volunteers; use the private channel in
[`../../SECURITY.md`](../../SECURITY.md).

---

<a name="español"></a>

## Español

### Formulario de consentimiento

La participación es voluntaria. Puedes parar cuando quieras. Marca lo que
aceptas; este formulario es un registro para ti y para el mantenedor, no un
contrato.

- [ ] He leído la guía de la persona voluntaria y entiendo que es software
      alfa.
- [ ] Entiendo que Swarmbly **no tiene telemetría**: la App no sube datos de
      uso, documentos, prompts ni respuestas por sí sola.
- [ ] Entiendo que quien administra el círculo y quien opera el relay pueden
      ver metadatos (identificadores de círculo y nodo, emparejamientos, hora,
      bytes y direcciones IP), pero no mis documentos, prompts ni respuestas.
- [ ] Entiendo que una incidencia de GitHub es pública y que cualquiera puede
      leer lo que pegue allí.
- [ ] Quitaré nombres, correos, rutas de la carpeta personal, documentos,
      conversaciones, prompts, respuestas, claves, invitaciones e
      identificadores de miembros antes de enviar un informe del doctor o un
      registro.
- [ ] Acepto recibir y enviar opiniones de la beta por el gestor de incidencias
      de GitHub o el formulario, usando un alias si prefiero no usar mi nombre.
- [ ] Entiendo que puedo retirarme saliendo del círculo, desinstalando la App y
      pidiendo al mantenedor que cierre o rectifique mi incidencia.

Alias o seudónimo (opcional): ______________________

Fecha: ______________________

### Aviso de privacidad

**Qué se recoge.** Solo lo que decidas escribir en una incidencia o formulario,
más el informe del doctor o el `install.log` que decidas adjuntar. No hay
cuenta, telemetría, analítica ni subida automática.

**Qué contiene el informe del doctor.** La salida de `swarmbly doctor`:
versiones del sistema y de Python, nombres y versiones de paquetes, comprobaciones
correctas o fallidas, estado de Ollama, comprobaciones de puertos y la ruta de la
carpeta de datos. `install.log` contiene los pasos del instalador y la salida de
los comandos. Ambos pueden contener tu nombre de usuario o la ruta de tu carpeta
personal; quítalos o sustitúyelos antes de enviar.

**Qué no contiene nunca.** Tus documentos, conversaciones, prompts, respuestas,
modelos, claves de API, clave privada del nodo, invitaciones, identificadores de
miembros del círculo, consultas de búsqueda ni payloads de tareas. Si ves algo
de eso, no envíes el archivo y avisa al mantenedor.

**Quién ve qué.**

- **Quien administra el círculo** ve el manifiesto firmado de membresía
  (identificadores y nombres visibles) y decide a quién admite o revoca.
- **Quien opera el relay** (normalmente quien administra el círculo) ve
  metadatos de conexión: identificadores de círculo y nodo, quién se empareja
  con quién, hora, bytes y direcciones IP. El diseño pide al operador guardar
  los registros de metadatos 7 días y mantenerlos fuera del contenido de los
  payloads.
- **El mantenedor** ve las incidencias de GitHub y cualquier archivo que decidas
  enviar.
- **Otras personas voluntarias y el público** pueden leer una incidencia pública
  de GitHub.

**Cuánto tiempo se conserva.** Metadatos del relay: 7 días según la política del
operador. Incidencias de GitHub y sus adjuntos: hasta que se cierren y se
borren o rectifiquen a tu petición, con la retención propia de GitHub y las
copias que otras personas puedan haber hecho (forks, cachés, citas). Los datos
locales de la App se quedan en tu equipo hasta que los borres.

**Qué no se hace.** No se venden datos, no se crea un perfil publicitario, no
hay telemetría automática y no se piden tus documentos para diagnosticar un
error.

**Retirarse.** Sal del círculo, desinstala la App (tus datos se conservan salvo
que confirmes borrarlos) y pide al mantenedor que cierre o rectifique tu
incidencia. Si quieres que se borre un archivo, dilo en la incidencia.

**Informes de seguridad.** No abras una incidencia pública por una
vulnerabilidad que pueda dañar a otras personas voluntarias; usa el canal
privado de [`../../SECURITY.md`](../../SECURITY.md).
