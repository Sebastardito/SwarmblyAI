# Signing releases · Firmar las versiones

**Language / Idioma:** [English](#english) · [Español](#español)

> **Draft for the maintainer.** This describes the release-signing setup that
> exists today and the account-dependent parts that are placeholders. It is
> not legal advice and it does not claim that the Apple or Windows accounts
> have been opened. Do not put certificates, passwords, account identifiers or
> generated keys in the repository.
>
> **Borrador para el mantenedor.** Describe la firma que ya existe y las partes
> que dependen de cuentas y todavía son marcadores. No es asesoría legal ni
> afirma que las cuentas de Apple o Windows estén abiertas. No pongas
> certificados, contraseñas, identificadores de cuenta ni claves generadas en
> el repositorio.

---

<a name="english"></a>

## English

### What already works without a paid account

`.github/workflows/release.yml` runs on a `vX.Y.Z` tag (or manually with an
existing tag). It builds:

- `swarmbly-<version>-source.tar.gz` and `.zip`: the umbrella source tree,
  including `components.lock`;
- `swarmbly-<version>-installer.tar.gz` and `.zip`: the installer entrypoints,
  the three component folders, the installer, `components.lock` and the install
  guide;
- `swarmbly-<version>-docker-image.txt`: the published image, tag, digest and
  immutable `image@digest` reference;
- `SIGNING.txt`: the exact Sigstore certificate identity, the OIDC issuer and
  the workflow run URL;
- `SHA256SUMS` over all of the above.

It then signs `SHA256SUMS` with **Sigstore keyless** using the GitHub Actions
OIDC identity:

```bash
cosign sign-blob --yes --bundle SHA256SUMS.bundle SHA256SUMS
```

No signing key is created, stored or downloaded. The signature proves that the
release workflow in this repository produced the checksum file; the checksum
file proves that the artifacts did not change after signing.

The Docker workflow (`docker.yml`) publishes the image and signs the resulting
digest keyless with the same kind of identity:

```bash
cosign sign --yes "ghcr.io/<owner>/swarmbly@<digest>"
```

### Verifying a release

See the verification section of [`docs/INSTALL.md`](../INSTALL.md). The short
form:

```bash
python scripts/verify_release.py --dir .
```

The helper checks every file in `SHA256SUMS`, then calls `cosign verify-blob`
with the identity regexp for this repository and the GitHub OIDC issuer. The
default expected identity is:

```
https://github.com/Sebastardito/SwarmblyAI/.github/workflows/release.yml@.*
```

Issuer:

```
https://token.actions.githubusercontent.com
```

`SIGNING.txt` records the exact identity of the run (for example
`...release.yml@refs/tags/v3.5.0`); the helper uses the repository-wide regexp
rather than trusting `SIGNING.txt`, because anyone can edit an unsigned text
file. To verify without fetching the public Sigstore trusted root, pass
`--trusted-root trusted_root.json`.

To verify the image:

```bash
cosign verify ghcr.io/<owner>/swarmbly@<digest> \
  --certificate-identity-regexp \
  'https://github.com/Sebastardito/SwarmblyAI/.github/workflows/docker.yml@.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

### macOS: Developer ID and notarisation (placeholder)

**Status:** the job `macos_placeholder` exists. It runs only when the complete
secret set below is present; otherwise it logs a notice and does not run. When
the secrets are present it currently logs a warning and does nothing: the build
of the `.pkg`, `codesign` and `notarytool` steps still has to be implemented.

The maintainer must open an Apple Developer Program membership and create a
**Developer ID Application** certificate (and a **Developer ID Installer**
certificate if the release is a `.pkg`). Export them as a password-protected
`.p12` and add these repository or environment secrets:

| Secret | Format |
|---|---|
| `MACOS_CERTIFICATE_P12_BASE64` | Base64 of the `.p12`, one line, no PEM armour |
| `MACOS_CERTIFICATE_PASSWORD` | Password chosen when exporting the `.p12` |
| `MACOS_KEYCHAIN_PASSWORD` | Any random password for the temporary CI keychain |
| `MACOS_NOTARY_APPLE_ID` | Apple ID e-mail used for notarisation |
| `MACOS_NOTARY_TEAM_ID` | Apple Developer team identifier |
| `MACOS_NOTARY_PASSWORD` | App-specific password for notarisation (not the Apple ID password) |

Base64 example (run locally, never commit the result):

```bash
base64 -i DeveloperID.p12 | pbcopy
```

When the signed build is implemented, the certificate identity users see is
the Apple Developer ID, not a GitHub account. Without these secrets the macOS
artifacts are unsigned and Gatekeeper will warn; the Sigstore signature and
checksums still let a user verify the download. Do not disable Gatekeeper to
work around it.

### Windows: Authenticode (placeholder)

**Status:** the job `windows_placeholder` exists. It runs only when either the
certificate set or the Azure Trusted Signing set is present; otherwise it logs
a notice and does not run. When the secrets are present it currently logs a
warning and does nothing: the packaging and `signtool` (or Azure Trusted
Signing) steps still have to be implemented.

Choose **one** path:

**A. OV/EV Authenticode certificate**

| Secret | Format |
|---|---|
| `WINDOWS_CERTIFICATE_PFX_BASE64` | Base64 of the `.pfx`, one line, no PEM armour |
| `WINDOWS_CERTIFICATE_PASSWORD` | Password of the `.pfx` |
| `WINDOWS_TIMESTAMP_URL` | Optional RFC 3161 timestamp URL; the default is the certificate authority's |

**B. Azure Trusted Signing**

| Secret | Format |
|---|---|
| `AZURE_TENANT_ID` | Azure tenant id |
| `AZURE_CLIENT_ID` | Service-principal application id allowed to sign |
| `AZURE_CLIENT_SECRET` | Service-principal secret |
| `AZURE_TRUSTED_SIGNING_ENDPOINT` | Trusted Signing account endpoint |
| `AZURE_TRUSTED_SIGNING_ACCOUNT` | Trusted Signing account name |
| `AZURE_TRUSTED_SIGNING_CERTIFICATE_PROFILE` | Certificate profile name |

Without these secrets the Windows artifacts are unsigned and SmartScreen will
warn; the Sigstore signature and checksums remain available. Do not tell users
to disable SmartScreen.

### Secret hygiene

- Put the secrets in a protected GitHub **environment** (for example
  `release`) with required reviewers, or in repository secrets if the project
  cannot use environments yet.
- Never echo a secret, put it in an artifact, or write it to `install.log`.
  The workflow checks only whether a secret is non-empty.
- Rotate the Apple app-specific password and the Windows credentials on a
  schedule, and immediately after a suspected leak.
- The release workflow's Sigstore identity is public by design. It is not a
  secret; it is what users verify.

### What is still missing

- The actual macOS `.pkg` build, `codesign`, `notarytool` submission and
  stapling.
- The actual Windows installer build and `signtool` or Azure Trusted Signing
  call.
- A distribution channel for the signed OS installers (the GitHub release
  currently carries source, installer bundle and the Docker digest).
- An independent review of this document by the maintainer.

---

<a name="español"></a>

## Español

### Lo que ya funciona sin una cuenta de pago

`.github/workflows/release.yml` se ejecuta con una etiqueta `vX.Y.Z` (o a mano
con una etiqueta existente). Construye:

- `swarmbly-<versión>-source.tar.gz` y `.zip`: el árbol fuente del umbrella,
  incluido `components.lock`;
- `swarmbly-<versión>-installer.tar.gz` y `.zip`: los lanzadores del
  instalador, las tres carpetas de componentes, el instalador,
  `components.lock` y la guía de instalación;
- `swarmbly-<versión>-docker-image.txt`: imagen publicada, etiqueta, digest y
  referencia inmutable `imagen@digest`;
- `SIGNING.txt`: identidad exacta del certificado Sigstore, emisor OIDC y URL
  de la ejecución;
- `SHA256SUMS` sobre todo lo anterior.

Después firma `SHA256SUMS` con **Sigstore sin clave**, usando la identidad OIDC
de GitHub Actions:

```bash
cosign sign-blob --yes --bundle SHA256SUMS.bundle SHA256SUMS
```

No se crea, guarda ni descarga ninguna clave de firma. La firma demuestra que
el flujo de publicación de este repositorio produjo el archivo de sumas; las
sumas demuestran que los artefactos no cambiaron después de firmarse.

El flujo de Docker (`docker.yml`) publica la imagen y firma el digest sin clave
con el mismo tipo de identidad:

```bash
cosign sign --yes "ghcr.io/<owner>/swarmbly@<digest>"
```

### Verificar una versión

Ver la sección de verificación de [`docs/INSTALL.md`](../INSTALL.md). Forma
corta:

```bash
python scripts/verify_release.py --dir .
```

El ayudante comprueba cada archivo de `SHA256SUMS` y luego llama a
`cosign verify-blob` con la expresión de identidad de este repositorio y el
emisor OIDC de GitHub. La identidad esperada por defecto es:

```
https://github.com/Sebastardito/SwarmblyAI/.github/workflows/release.yml@.*
```

Emisor:

```
https://token.actions.githubusercontent.com
```

`SIGNING.txt` registra la identidad exacta de la ejecución (por ejemplo
`...release.yml@refs/tags/v3.5.0`); el ayudante usa la expresión del repositorio
y no confía en `SIGNING.txt`, porque cualquiera puede editar un archivo de
texto sin firmar. Para verificar sin descargar la raíz pública de confianza de
Sigstore, pasa `--trusted-root trusted_root.json`.

Para verificar la imagen:

```bash
cosign verify ghcr.io/<owner>/swarmbly@<digest> \
  --certificate-identity-regexp \
  'https://github.com/Sebastardito/SwarmblyAI/.github/workflows/docker.yml@.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

### macOS: Developer ID y notarización (marcador)

**Estado:** existe el job `macos_placeholder`. Solo se ejecuta cuando está el
conjunto completo de secretos de abajo; si no, registra un aviso y no se
ejecuta. Cuando los secretos están, hoy solo registra una advertencia y no hace
nada: todavía hay que implementar la construcción del `.pkg`, `codesign` y
`notarytool`.

El mantenedor debe abrir una membresía del Apple Developer Program y crear un
certificado **Developer ID Application** (y **Developer ID Installer** si la
versión es un `.pkg`). Expórtalos como un `.p12` protegido con contraseña y
añade estos secretos de repositorio o de entorno:

| Secreto | Formato |
|---|---|
| `MACOS_CERTIFICATE_P12_BASE64` | Base64 del `.p12`, en una línea, sin armadura PEM |
| `MACOS_CERTIFICATE_PASSWORD` | Contraseña elegida al exportar el `.p12` |
| `MACOS_KEYCHAIN_PASSWORD` | Una contraseña aleatoria para el llavero temporal de CI |
| `MACOS_NOTARY_APPLE_ID` | Correo del Apple ID usado para notarizar |
| `MACOS_NOTARY_TEAM_ID` | Identificador del equipo de Apple Developer |
| `MACOS_NOTARY_PASSWORD` | Contraseña específica de app para notarizar (no la del Apple ID) |

Ejemplo de base64 (en local, nunca lo integres en el repositorio):

```bash
base64 -i DeveloperID.p12 | pbcopy
```

La identidad que ven los usuarios es la del Developer ID de Apple, no una
cuenta de GitHub. Sin estos secretos los artefactos de macOS no están firmados
y Gatekeeper avisará; la firma Sigstore y las sumas permiten igualmente
verificar la descarga. No desactives Gatekeeper para evitarlo.

### Windows: Authenticode (marcador)

**Estado:** existe el job `windows_placeholder`. Solo se ejecuta cuando está el
conjunto del certificado o el de Azure Trusted Signing; si no, registra un
aviso y no se ejecuta. Cuando los secretos están, hoy solo registra una
advertencia y no hace nada: todavía hay que implementar el empaquetado y
`signtool` (o Azure Trusted Signing).

Elige **una** vía:

**A. Certificado Authenticode OV/EV**

| Secreto | Formato |
|---|---|
| `WINDOWS_CERTIFICATE_PFX_BASE64` | Base64 del `.pfx`, en una línea, sin armadura PEM |
| `WINDOWS_CERTIFICATE_PASSWORD` | Contraseña del `.pfx` |
| `WINDOWS_TIMESTAMP_URL` | URL de sellado de tiempo RFC 3161 opcional; por defecto, la de la autoridad certificadora |

**B. Azure Trusted Signing**

| Secreto | Formato |
|---|---|
| `AZURE_TENANT_ID` | Id. de inquilino de Azure |
| `AZURE_CLIENT_ID` | Id. de aplicación del service principal autorizado a firmar |
| `AZURE_CLIENT_SECRET` | Secreto del service principal |
| `AZURE_TRUSTED_SIGNING_ENDPOINT` | Endpoint de la cuenta de Trusted Signing |
| `AZURE_TRUSTED_SIGNING_ACCOUNT` | Nombre de la cuenta de Trusted Signing |
| `AZURE_TRUSTED_SIGNING_CERTIFICATE_PROFILE` | Nombre del perfil de certificado |

Sin estos secretos los artefactos de Windows no están firmados y SmartScreen
avisará; la firma Sigstore y las sumas siguen disponibles. No le digas a nadie
que desactive SmartScreen.

### Higiene de secretos

- Pon los secretos en un **entorno** protegido de GitHub (por ejemplo
  `release`) con revisores obligatorios, o en secretos del repositorio si el
  proyecto aún no puede usar entornos.
- Nunca imprimas un secreto, lo pongas en un artefacto ni lo escribas en
  `install.log`. El flujo solo comprueba si un secreto no está vacío.
- Rota la contraseña específica de app de Apple y las credenciales de Windows
  con una cadencia, y de inmediato si sospechas una filtración.
- La identidad Sigstore del flujo es pública por diseño. No es un secreto: es
  lo que verifican los usuarios.

### Lo que falta

- La construcción real del `.pkg` de macOS, `codesign`, el envío a
  `notarytool` y el stapling.
- La construcción real del instalador de Windows y la llamada a `signtool` o
  Azure Trusted Signing.
- Un canal de distribución para los instaladores firmados de cada sistema (la
  versión de GitHub lleva hoy el fuente, el paquete del instalador y el digest
  de Docker).
- Una revisión independiente de este documento por parte del mantenedor.
