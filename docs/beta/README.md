# Swarmbly beta kit · Kit de la beta

**Language / Idioma:** [English](#english) · [Español](#español)

> **DRAFT — to be reviewed by the maintainer.** These documents are drafts for
> the 3.5 private beta. They are not legal advice and make no legal claim.
>
> **BORRADOR — pendiente de revisión por el mantenedor.** Estos documentos son
> borradores para la beta privada de 3.5. No son asesoría legal ni hacen
> afirmaciones legales.

---

<a name="english"></a>

## English

### What is in this kit

| File | For |
|---|---|
| [`volunteer-guide.md`](volunteer-guide.md) | the two-page guide a volunteer receives |
| [`consent-and-privacy.md`](consent-and-privacy.md) | consent form and privacy notice |
| [`feedback-form.md`](feedback-form.md) | questions for written feedback |
| [`install-checklist.md`](install-checklist.md) | per-OS install outcome, no personal data |
| `.github/ISSUE_TEMPLATE/beta-bug.yml` | the issue form for a beta bug |

The circle owner sends the volunteer the installer or release link, the
invitation (code, file or QR) and the volunteer guide. The maintainer keeps the
consent form, the privacy notice and the issue template.

### Bug process

A **severe beta bug** is one that blocks installation, loses data, exposes
private data, crashes repeatedly, or prevents joining or pairing. Everything
else is ordinary feedback.

1. The volunteer opens an umbrella issue with the **beta bug** template. It adds
   the `beta` label, asks for the operating system, the version, what happened
   and the doctor export. It does not ask for a name or an e-mail.
2. Before sending, the volunteer removes names, e-mail addresses, home-folder
   paths, documents, chats, prompts, answers, keys, invitations and member ids.
   GitHub issues are public unless the maintainer says otherwise.
3. The maintainer triages and labels the issue `severe` when it meets the
   definition above.
4. The beta exit criterion is **≥ 90 % successful installs per OS and no severe
   beta bug open for two weeks**. The two-week clock counts from the date the
   last severe beta bug was closed; opening a new severe bug restarts it.
5. The install tally comes only from the checklists volunteers choose to send.
   There is no telemetry and no automatic upload.

The `beta` and `severe` labels must exist in the repository; the maintainer
creates them once.

### Useful links

- Install and verification: [`../INSTALL.md`](../INSTALL.md)
- Signing and OS warnings: [`../releases/SIGNING.md`](../releases/SIGNING.md)
- Security reports that should not be public: [`../../SECURITY.md`](../../SECURITY.md)

---

<a name="español"></a>

## Español

### Qué contiene este kit

| Archivo | Para |
|---|---|
| [`volunteer-guide.md`](volunteer-guide.md) | la guía de dos páginas que recibe quien participa |
| [`consent-and-privacy.md`](consent-and-privacy.md) | formulario de consentimiento y aviso de privacidad |
| [`feedback-form.md`](feedback-form.md) | preguntas para la opinión escrita |
| [`install-checklist.md`](install-checklist.md) | resultado de la instalación por sistema, sin datos personales |
| `.github/ISSUE_TEMPLATE/beta-bug.yml` | el formulario de incidencia de la beta |

El dueño del círculo envía a la persona voluntaria el instalador o el enlace
de la versión, la invitación (código, archivo o QR) y la guía. El mantenedor
conserva el consentimiento, el aviso de privacidad y la plantilla de
incidencias.

### Proceso de errores

Un **error grave de la beta** es el que impide instalar, pierde datos, expone
datos privados, falla repetidamente o impide unirse o emparejarse. Todo lo
demás es opinión normal.

1. La persona voluntaria abre una incidencia en el umbrella con la plantilla
   **beta bug**. Añade la etiqueta `beta`, pide el sistema operativo, la
   versión, lo que pasó y el informe del doctor. No pide nombre ni correo.
2. Antes de enviar, quita nombres, correos, rutas de la carpeta personal,
   documentos, conversaciones, prompts, respuestas, claves, invitaciones e
   identificadores de miembros. Las incidencias de GitHub son públicas salvo
   que el mantenedor indique otra cosa.
3. El mantenedor clasifica y marca `severe` si cumple la definición anterior.
4. El criterio de salida de la beta es **≥ 90 % de instalaciones correctas por
   sistema y ningún error grave abierto durante dos semanas**. Las dos semanas
   se cuentan desde la fecha en que se cerró el último error grave; abrir uno
   nuevo reinicia el plazo.
5. El recuento de instalaciones sale solo de las listas que las personas
   voluntarias deciden enviar. No hay telemetría ni subida automática.

Las etiquetas `beta` y `severe` deben existir en el repositorio; el mantenedor
las crea una vez.

### Enlaces útiles

- Instalación y verificación: [`../INSTALL.md`](../INSTALL.md)
- Firma y avisos del sistema: [`../releases/SIGNING.md`](../releases/SIGNING.md)
- Informes de seguridad que no deben ser públicos: [`../../SECURITY.md`](../../SECURITY.md)
