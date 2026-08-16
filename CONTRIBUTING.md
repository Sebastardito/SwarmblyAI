# Contributing to Swarmbly AI · Contribuir a Swarmbly AI

**Language / Idioma:** [English](#english) · [Español](#español)

> **Contact / Contacto:** `sebas_saeu@hotmail.com`

---

<a name="english"></a>

# English

## 1. Before anything else

Swarmbly is a protocol before it is a codebase. A change to the reference
implementation is a change to one implementation of the protocol; a change to
the specification is a change to what everyone must implement. These two carry
very different review burdens, and the process below reflects that.

Three ground rules govern everything here:

1. **Every commit is signed off under the DCO.** No CLA, no copyright
   assignment. See Section 2.
2. **Every performance or quality claim cites a measurement.** No exceptions,
   including in prose. See Section 5.
3. **Protocol changes go through a SWIP.** Code that changes wire format,
   task semantics, or trust assumptions is not merged from a bare PR. See Section 6.

## 2. The DCO sign-off

This project uses the **Developer Certificate of Origin 1.1**. Every commit
must carry a `Signed-off-by` trailer matching the author's real name and a
reachable email address:

```bash
git commit -s -m "assembler: bound contig overlap search to the read window"
```

`-s` appends:

```
Signed-off-by: Jane Q. Contributor <jane@example.org>
```

Amending an existing commit: `git commit -s --amend`. Fixing a whole branch:
`git rebase --signoff main`.

Sign-off is a statement about provenance, not a form. By adding it you certify
the following, in full:

### Developer Certificate of Origin 1.1

```
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.
1 Letterman Drive
Suite D4700
San Francisco, CA, 94129

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.


Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

### Why DCO and not a CLA

This is a deliberate decision, and it is worth stating the reasoning plainly
because contributors are entitled to know what they are and are not signing
away.

- **A CLA asks for a copyright grant or assignment to a single entity.** That
  entity then holds rights the rest of the community does not. In practice
  the main thing those extra rights enable is *relicensing* — most commonly,
  selling proprietary exceptions to the copyleft the community contributed
  under. Swarmbly has explicitly rejected that business model
  (see `GOVERNANCE.md`), so the primary reason to collect a CLA does not
  apply here.
- **The community this project targets is AGPL/P2P-native and CLA-averse.**
  Contributors from that world routinely decline to sign copyright-assignment
  paperwork, and they are right to be careful: a CLA signed today binds work
  a maintainer may sell differently tomorrow. Requiring one would cost the
  project exactly the contributors it most needs.
- **A DCO is enforceable where it matters and costs nothing.** It creates a
  per-commit, auditable, git-native record of provenance. It is the mechanism
  the Linux kernel uses, so it is familiar and tooling for it is everywhere.
- **The DCO leaves copyright with the author.** Contributors keep their
  copyright and license the contribution to everyone under the project's
  license. The consequence is that no future maintainer — including the
  founder, including the Foundation — can unilaterally relicense the codebase
  out from under its contributors. That constraint is a feature. It is the
  single strongest structural guarantee this project can offer that it will
  not be captured.

**Trade-off, stated honestly:** because copyright stays distributed, a future
license change (even a benign one, such as moving to a later AGPL version
under different terms) would require broad contributor consent. The project
accepts that friction. `AGPL-3.0-**or-later**` is used precisely so that
version migration within the AGPL family does not require it.

### If CI flags a missing sign-off

The DCO check is mechanical. Add the trailer and force-push the branch; there
is no need to open a new PR. Maintainers will not merge around a failing DCO
check.

## 3. Licensing of contributions

Contributions are licensed under **AGPL-3.0-or-later**, the project's license.
Do not add code, assets, or vendored dependencies under an incompatible
license. If you are adding a dependency, state its license in the PR
description; if it is anything other than a permissive license (MIT, BSD,
Apache-2.0, ISC) or AGPL/GPL-3-compatible copyleft, flag it explicitly and
expect the review to focus there first.

Note that Apache-2.0 is one-way compatible: Apache-2.0 code may be
incorporated into an AGPL-3.0 work, but not the reverse. Do not assume the
reverse direction is available for code you take out of this project.

## 4. Code style

**Python (the V0 reference implementation).**

- Target: Python 3.11+.
- Formatting: `ruff format` (Black-compatible), line length 100.
- Linting: `ruff check`. Fix findings; do not blanket-`noqa`. A justified
  per-line `# noqa: RULE  — reason` is acceptable; a bare `# noqa` is not.
- Typing: public functions and all module boundaries are annotated. Internal
  helpers may be untyped where annotation adds no information.
- Docstrings: every public function, class, and module. State what the thing
  does and what it assumes, not how it is implemented. Assumptions are the
  valuable part in a distributed system.
- Errors: raise specific exceptions. Never `except:` bare, and never
  `except Exception: pass`. In node/network code a swallowed exception is
  indistinguishable from a silently degraded assembly, which is precisely the
  failure mode this protocol must never have.
- Naming follows the domain vocabulary and does so *consistently*. `read`,
  `contig`, `overlap`, `scaffold`, `consensus`, `coverage` mean what they mean
  in shotgun assembly. Do not use them loosely, and do not introduce a synonym
  for a concept that already has a name.
- Tests: `pytest`. A bug fix comes with a test that fails before the fix.
  Concurrency and network behaviour are tested deterministically — inject
  clocks and transports, do not `sleep()`.

**Commits.**

- Imperative mood, ≤72-character subject: `assembler: reject contigs below
  minimum coverage`.
- Prefix with the component: `assembler:`, `orchestrator:`, `node:`,
  `spec:`, `docs:`, `ci:`.
- One logical change per commit. A refactor and a behaviour change do not
  belong in the same commit; splitting them is what makes review possible.

**Documentation.**

- Markdown, wrapped at a readable width, no hard requirement on the column.
- Bilingual documents keep EN and ES in sync. If you change one and cannot
  do the other, say so in the PR and it will be tracked; do not silently let
  them drift.

## 5. The measurement rule

**Any claim about performance, quality, latency, cost, bandwidth, accuracy, or
scalability in a PR — in the code, in comments, in the description, or in
documentation — must cite a measurement.**

A citation means, at minimum:

- the command or script that produces the number (committed, and runnable);
- the hardware and model configuration it ran on (CPU/GPU, RAM, which SLM at
  which quantisation, node count);
- the number of runs and the spread, not just a single figure;
- what it was compared against, if the claim is comparative.

Not acceptable: "this is faster", "significantly reduces latency", "scales
well", "improves quality". These are unfalsifiable as written and they are how
a project's documentation ends up making claims it cannot defend.

Acceptable: "reduces median end-to-end latency for the 8-micro-task workload
from 4.2 s to 2.9 s (n=20, p95 5.1 s → 3.6 s) on the configuration in
`bench/configs/local_8node.yaml`; reproduce with `make bench-latency`."

If you believe a change is an improvement but have not measured it, say
exactly that: *"expected to reduce latency; not measured."* That is a
completely acceptable PR. Claiming it without the number is not.

This rule exists because Swarmbly's central thesis — that fragmenting the
problem beats fragmenting the model — is an empirical claim. A project whose
thesis is empirical cannot afford a documentation culture of unmeasured
assertions, and reviewers cannot un-see a number once it is in the README.

## 6. Proposing a protocol change: the SWIP process

A **SWIP** (Swarmbly Improvement Proposal) is a lightweight design document. It
is deliberately lighter than an RFC: the goal is a written, reviewable record
of *why*, not a bureaucracy.

### When a SWIP is required

Required for anything that:

- changes the wire format or any message schema;
- changes task decomposition or assembly semantics in a way that alters
  results;
- changes trust, privacy, or security assumptions;
- adds or removes a node obligation, or changes what a node may observe;
- changes the consensus rule or the coverage/redundancy model;
- is a breaking change to any public interface;
- is large enough that a reviewer would reasonably ask "was this discussed?"

**Not** required for: bug fixes, tests, documentation, refactors with no
behaviour change, performance work that preserves semantics, tooling and CI.

### Process

1. **Open a discussion issue first.** Use the SWIP issue template
   (`.github/ISSUE_TEMPLATE/swip.md`). Cheap to do, and it prevents someone
   writing a full proposal for an idea already ruled out.
2. **Write the SWIP** as `swips/SWIP-XXXX-short-title.md`, where `XXXX` is the
   issue number, zero-padded. Use the template below.
3. **Open a PR** containing the SWIP file only. Implementation goes in a
   separate PR so the design can be argued without the diff in the way.
4. **Review period: 14 days minimum** for any SWIP touching wire format,
   security, or privacy; 7 days otherwise. Short enough not to stall, long
   enough that people in other timezones and other jobs can participate.
5. **Resolution.** A SWIP ends as `Accepted`, `Rejected`, `Withdrawn`, or
   `Deferred`. Rejected and withdrawn SWIPs are merged too, with the status
   and the reasoning recorded. The record of what was considered and
   discarded is as valuable as the record of what was built — it stops the
   same idea being re-litigated every six months.
6. **Implementation** references the SWIP: `Implements SWIP-0042.` A SWIP becomes
   `Final` when a reference implementation lands and the spec is updated.

### SWIP template

```markdown
---
gip: XXXX
title: <short, descriptive>
author: <name> <<email or @handle>>
status: Draft            # Draft | Accepted | Rejected | Withdrawn | Deferred | Final
created: YYYY-MM-DD
requires: []             # SWIPs this depends on
supersedes: []           # SWIPs this replaces
spec-version: 0.2        # spec version this targets
---

## Abstract
Two or three sentences. What changes, in plain language.

## Motivation
What is broken or missing today. Be concrete: describe the scenario where
the current design produces a bad outcome. If there is evidence — a
measurement, a failed run, a user report — cite it. A motivation that only
says "it would be nicer if" is a weak motivation.

## Specification
Normative. Use RFC 2119 keywords (MUST, SHOULD, MAY) and use them precisely.
Include message schemas, state transitions, error cases, and defaults.
Written so an independent implementer could build it from this section alone,
without reading the reference implementation.

## Rationale
Why this design and not the obvious alternatives. List the alternatives you
considered and say why each was rejected. This section is what makes the SWIP
worth keeping after the decision is made.

## Backwards compatibility
Does this break existing nodes, clients, or stored artifacts? If yes: what
is the migration path, what is the deprecation window, and how do old and new
nodes behave when they meet on the network? "Not applicable" is a valid
answer but must be justified in one line, not left blank.

## Security and privacy implications
Mandatory. Every SWIP has this section, including the ones where the answer is
"none identified" — in which case say so and say why you are confident.
Address at minimum:
  - What can a malicious node now observe? Does this change how much of the
    original problem any single node can reconstruct?
  - What can a malicious node now cause? Can it poison a contig, bias a
    consensus, or force a client to accept a low-coverage assembly?
  - What can a malicious or coerced client cause on nodes?
  - Does this add a new trust assumption, or strengthen one? Name it.
  - Does anything here create a new opportunity for traffic analysis or
    correlation across micro-tasks?

## Measurement plan
How will we know this worked? State the metric, the benchmark, the baseline
you will compare against, and the threshold that would count as success —
*before* implementing. If the change is not measurable, say so explicitly and
explain how it will be validated instead (e.g. by a formal argument or a
property-based test).

## Reference implementation
Link the PR, or "not yet implemented".

## Open questions
Anything unresolved. It is better to merge a SWIP with an honest open-questions
section than to paper over uncertainty.
```

## 7. Pull requests

- Branch from `main`. Keep the branch focused.
- Fill in the PR template, including both checkboxes (DCO sign-off,
  measurement citation).
- CI must pass: format, lint, types, tests, DCO.
- Reviews are on the change, not the person. Terse review comments are not
  hostile; assume good faith in both directions.
- Maintainers may ask for a SWIP if a PR turns out to be a protocol change in
  disguise. This is common and is not a rejection.

## 8. Reporting security issues

**Do not open a public issue for a security vulnerability.** Email
`sebas_saeu@hotmail.com` with a description and, if possible,
reproduction steps. You will get an acknowledgement; coordinated disclosure
timelines will be agreed case by case.

Note that until the project has a published, staffed security policy with
committed response times, do not assume enterprise-grade turnaround. Being
honest about that is better than a `SECURITY.md` promising an SLA nobody can
meet.

## 9. Conduct

Be direct, be technical, be civil. Argue with the design, not the designer.
Persistent bad faith, harassment, or attempts to relitigate settled decisions
by attrition will get you removed from the project's spaces.

---
---

<a name="español"></a>

# Español

## 1. Antes que nada

Swarmbly es un protocolo antes que un código. Un cambio en la implementación de
referencia es un cambio en *una* implementación del protocolo; un cambio en la
especificación es un cambio en lo que todos deben implementar. Ambas cosas
tienen cargas de revisión muy distintas, y el proceso que sigue lo refleja.

Tres reglas de base rigen todo lo demás:

1. **Todo commit lleva firma DCO.** Sin CLA, sin cesión de derechos de autor.
   Ver la sección 2.
2. **Toda afirmación de rendimiento o calidad cita una medición.** Sin
   excepciones, tampoco en prosa. Ver la sección 5.
3. **Los cambios de protocolo pasan por una SWIP.** El código que modifica el
   formato de mensajes, la semántica de las tareas o los supuestos de
   confianza no se integra desde un PR suelto. Ver la sección 6.

## 2. La firma DCO

Este proyecto usa el **Developer Certificate of Origin 1.1**. Cada commit debe
llevar un trailer `Signed-off-by` con el nombre real del autor y una dirección
de correo operativa:

```bash
git commit -s -m "assembler: acota la búsqueda de solapamiento a la ventana de reads"
```

`-s` añade:

```
Signed-off-by: Juana Q. Colaboradora <juana@ejemplo.org>
```

Para enmendar un commit existente: `git commit -s --amend`. Para arreglar una
rama entera: `git rebase --signoff main`.

La firma es una declaración sobre la procedencia del código, no un trámite. Al
añadirla, certificas lo siguiente, íntegro:

### Developer Certificate of Origin 1.1

El texto del DCO se reproduce **en su versión original en inglés**, que es la
única con valor. La traducción que sigue es orientativa y no sustituye al
original.

```
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.
1 Letterman Drive
Suite D4700
San Francisco, CA, 94129

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.


Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

*Traducción orientativa, sin valor normativo:* al contribuir a este proyecto
certificas que (a) la contribución la creaste tú, total o parcialmente, y
tienes derecho a enviarla bajo la licencia libre indicada; o (b) se basa en
trabajo previo que, hasta donde sabes, está cubierto por una licencia libre
apropiada y tienes derecho a enviarlo, con o sin modificaciones, bajo la misma
licencia; o (c) te la entregó directamente otra persona que certificó (a), (b)
o (c) y tú no la has modificado; y (d) entiendes que el proyecto y tu
contribución son públicos, y que el registro de la contribución —incluidos los
datos personales que envíes con ella, tu firma entre ellos— se conserva de
forma indefinida y puede redistribuirse conforme a la licencia del proyecto.

### Por qué DCO y no CLA

Es una decisión deliberada, y conviene explicarla sin rodeos porque quien
contribuye tiene derecho a saber qué está cediendo y qué no.

- **Un CLA pide una licencia o una cesión de derechos de autor a una única
  entidad.** Esa entidad pasa a tener derechos que el resto de la comunidad no
  tiene. En la práctica, lo principal que habilitan esos derechos extra es el
  *relicenciamiento*: casi siempre, vender excepciones propietarias al
  copyleft bajo el que la comunidad contribuyó. Swarmbly ha rechazado
  explícitamente ese modelo de negocio (ver `GOVERNANCE.md`), así que el
  motivo principal para recoger un CLA aquí no existe.
- **La comunidad a la que apunta el proyecto es nativa de AGPL/P2P y recela de
  los CLA.** Quien viene de ese mundo suele negarse a firmar papeleo de cesión
  de derechos, y hace bien en desconfiar: un CLA firmado hoy vincula trabajo
  que un mantenedor podría vender de otra manera mañana. Exigirlo le costaría
  al proyecto exactamente las personas que más necesita.
- **El DCO es exigible donde importa y no cuesta nada.** Deja un registro de
  procedencia por commit, auditable y nativo de git. Es el mecanismo del
  kernel de Linux, así que resulta familiar y hay herramientas por todas
  partes.
- **El DCO deja el copyright en manos de quien escribe.** Cada persona
  conserva sus derechos y licencia su aportación a todo el mundo bajo la
  licencia del proyecto. La consecuencia es que ningún mantenedor futuro —ni
  el fundador, ni la Fundación— puede relicenciar el código unilateralmente
  por encima de quienes lo escribieron. Esa restricción no es un defecto: es
  la garantía estructural más fuerte que este proyecto puede ofrecer de que no
  será capturado.

**Contrapartida, dicha con honestidad:** como el copyright queda repartido, un
cambio futuro de licencia —incluso uno benigno— exigiría el consentimiento
amplio de quienes han contribuido. El proyecto asume esa fricción. Se usa
`AGPL-3.0-**or-later**` precisamente para que migrar de versión dentro de la
familia AGPL no la requiera.

### Si CI marca que falta la firma

La comprobación del DCO es mecánica. Añade el trailer y haz force-push de la
rama; no hace falta abrir un PR nuevo. Los mantenedores no integrarán código
esquivando una comprobación DCO fallida.

## 3. Licencia de las contribuciones

Las contribuciones se licencian bajo **AGPL-3.0-or-later**, la licencia del
proyecto. No añadas código, recursos ni dependencias vendorizadas bajo una
licencia incompatible. Si añades una dependencia, indica su licencia en la
descripción del PR; si no es permisiva (MIT, BSD, Apache-2.0, ISC) ni copyleft
compatible con AGPL/GPL-3, señálalo de forma explícita y da por hecho que la
revisión empezará por ahí.

Ten en cuenta que Apache-2.0 es compatible en un solo sentido: se puede
incorporar código Apache-2.0 a una obra AGPL-3.0, pero no al revés. No des por
supuesta la dirección inversa para el código que saques de este proyecto.

## 4. Estilo de código

**Python (implementación de referencia V0).**

- Objetivo: Python 3.11+.
- Formato: `ruff format` (compatible con Black), longitud de línea 100.
- Linting: `ruff check`. Corrige los hallazgos; no uses `noqa` en bloque. Un
  `# noqa: REGLA — motivo` justificado por línea es aceptable; un `# noqa`
  pelado no.
- Tipado: las funciones públicas y todos los límites de módulo van anotados.
  Los ayudantes internos pueden ir sin anotar si la anotación no aporta nada.
- Docstrings: en cada función, clase y módulo público. Explica qué hace y qué
  supone, no cómo está implementado. En un sistema distribuido, lo valioso son
  los supuestos.
- Errores: lanza excepciones específicas. Nunca `except:` a secas, nunca
  `except Exception: pass`. En el código de nodo y de red, una excepción
  tragada es indistinguible de un ensamblado silenciosamente degradado, que es
  justo el modo de fallo que este protocolo no puede permitirse.
- Los nombres siguen el vocabulario del dominio, y lo siguen de forma
  *consistente*. `read`, `contig`, `overlap`, `scaffold`, `consensus`,
  `coverage` significan lo que significan en ensamblado shotgun. No los uses a
  la ligera y no introduzcas un sinónimo para un concepto que ya tiene nombre.
- Pruebas: `pytest`. Una corrección de bug viene con una prueba que falla
  antes del arreglo. La concurrencia y el comportamiento de red se prueban de
  forma determinista: inyecta relojes y transportes, no uses `sleep()`.

**Commits.**

- Modo imperativo, asunto de ≤72 caracteres: `assembler: rechaza contigs por
  debajo de la cobertura mínima`.
- Prefijo con el componente: `assembler:`, `orchestrator:`, `node:`, `spec:`,
  `docs:`, `ci:`.
- Un cambio lógico por commit. Una refactorización y un cambio de
  comportamiento no van en el mismo commit; separarlos es lo que hace posible
  la revisión.

**Documentación.**

- Markdown, con un ancho de línea legible; no hay exigencia estricta de
  columna.
- Los documentos bilingües mantienen EN y ES sincronizados. Si cambias uno y
  no puedes hacer el otro, dilo en el PR y quedará registrado; no dejes que se
  desincronicen en silencio.

## 5. La regla de la medición

**Toda afirmación sobre rendimiento, calidad, latencia, coste, ancho de banda,
precisión o escalabilidad en un PR —en el código, en los comentarios, en la
descripción o en la documentación— debe citar una medición.**

Citar significa, como mínimo:

- el comando o script que produce el número (versionado y ejecutable);
- el hardware y la configuración de modelo con que se ejecutó (CPU/GPU, RAM,
  qué SLM con qué cuantización, número de nodos);
- el número de repeticiones y la dispersión, no una cifra suelta;
- contra qué se compara, si la afirmación es comparativa.

No vale: «es más rápido», «reduce significativamente la latencia», «escala
bien», «mejora la calidad». Tal como están escritas son infalsables, y así es
como la documentación de un proyecto acaba sosteniendo cosas que no puede
defender.

Sí vale: «reduce la latencia mediana extremo a extremo de la carga de 8
micro-tareas de 4,2 s a 2,9 s (n=20, p95 5,1 s → 3,6 s) con la configuración
de `bench/configs/local_8node.yaml`; reproducible con `make bench-latency`».

Si crees que un cambio mejora algo pero no lo has medido, dilo tal cual:
*«se espera que reduzca la latencia; sin medir»*. Ese PR es perfectamente
aceptable. Afirmarlo sin el número, no.

Esta regla existe porque la tesis central de Swarmbly —que fragmentar el
problema gana a fragmentar el modelo— es una afirmación empírica. Un proyecto
cuya tesis es empírica no puede permitirse una cultura documental de
aseveraciones sin medir, y quien revisa no puede des-leer un número una vez
que está en el README.

## 6. Proponer un cambio de protocolo: el proceso SWIP

Una **SWIP** (Swarmbly Improvement Proposal, propuesta de mejora de Swarmbly) es
un documento de diseño ligero. Es deliberadamente más liviano que un RFC: el
objetivo es dejar constancia escrita y revisable del *porqué*, no montar una
burocracia.

### Cuándo hace falta una SWIP

Hace falta para cualquier cosa que:

- cambie el formato de mensajes o cualquier esquema de la red;
- cambie la descomposición de tareas o la semántica de ensamblado de forma que
  altere los resultados;
- cambie los supuestos de confianza, privacidad o seguridad;
- añada o elimine una obligación de nodo, o cambie lo que un nodo puede
  observar;
- cambie la regla de consenso o el modelo de cobertura y redundancia;
- rompa la compatibilidad de cualquier interfaz pública;
- sea lo bastante grande como para que alguien pregunte, con razón, «¿esto se
  discutió?».

**No** hace falta para: corrección de bugs, pruebas, documentación,
refactorizaciones sin cambio de comportamiento, trabajo de rendimiento que
preserva la semántica, herramientas y CI.

### Proceso

1. **Abre primero un issue de discusión.** Usa la plantilla SWIP
   (`.github/ISSUE_TEMPLATE/swip.md`). Cuesta poco y evita que alguien escriba
   una propuesta completa de una idea ya descartada.
2. **Escribe la SWIP** en `swips/SWIP-XXXX-titulo-corto.md`, donde `XXXX` es el
   número del issue con ceros a la izquierda. Usa la plantilla de más abajo.
3. **Abre un PR** que contenga solo el archivo de la SWIP. La implementación va
   en un PR aparte, para poder discutir el diseño sin el diff de por medio.
4. **Periodo de revisión: 14 días como mínimo** para cualquier SWIP que toque
   el formato de mensajes, la seguridad o la privacidad; 7 días en el resto de
   casos. Lo bastante corto para no bloquear, lo bastante largo para que gente
   en otros husos horarios y con otro trabajo pueda participar.
5. **Resolución.** Una SWIP termina como `Accepted`, `Rejected`, `Withdrawn` o
   `Deferred`. Las rechazadas y retiradas también se integran, con su estado y
   su razonamiento registrados. El registro de lo que se consideró y se
   descartó vale tanto como el de lo que se construyó: evita volver a discutir
   la misma idea cada seis meses.
6. **La implementación** referencia la SWIP: `Implements SWIP-0042.` Una SWIP pasa
   a `Final` cuando aterriza una implementación de referencia y se actualiza
   la especificación.

### Plantilla de SWIP

```markdown
---
gip: XXXX
title: <corto y descriptivo>
author: <nombre> <<correo o @usuario>>
status: Draft            # Draft | Accepted | Rejected | Withdrawn | Deferred | Final
created: AAAA-MM-DD
requires: []             # SWIPs de las que depende
supersedes: []           # SWIPs a las que reemplaza
spec-version: 0.2        # versión de la especificación a la que apunta
---

## Resumen
Dos o tres frases. Qué cambia, en lenguaje llano.

## Motivación
Qué está roto o falta hoy. Sé concreto: describe el escenario en el que el
diseño actual produce un mal resultado. Si hay evidencia —una medición, una
ejecución fallida, un reporte de usuario— cítala. Una motivación que solo dice
«quedaría mejor si» es una motivación débil.

## Especificación
Normativa. Usa las palabras clave de RFC 2119 (MUST, SHOULD, MAY) y úsalas con
precisión. Incluye esquemas de mensajes, transiciones de estado, casos de
error y valores por defecto. Escrita de forma que alguien que implemente por
su cuenta pueda construirlo solo con esta sección, sin leer la implementación
de referencia.

## Justificación
Por qué este diseño y no las alternativas obvias. Enumera las alternativas que
consideraste y di por qué descartaste cada una. Esta sección es lo que hace
que la SWIP siga valiendo algo después de tomada la decisión.

## Compatibilidad hacia atrás
¿Rompe nodos, clientes o artefactos ya existentes? Si sí: cuál es la ruta de
migración, cuál la ventana de obsolescencia, y cómo se comportan los nodos
viejos y nuevos cuando se encuentran en la red. «No aplica» es una respuesta
válida, pero hay que justificarla en una línea, no dejarla en blanco.

## Implicaciones de seguridad y privacidad
Obligatoria. Toda SWIP lleva esta sección, incluidas aquellas cuya respuesta es
«ninguna identificada» — en cuyo caso dilo y explica por qué estás seguro.
Cubre como mínimo:
  - ¿Qué puede observar ahora un nodo malicioso? ¿Cambia cuánto del problema
    original puede reconstruir un solo nodo?
  - ¿Qué puede provocar ahora un nodo malicioso? ¿Puede envenenar un contig,
    sesgar un consenso o forzar a un cliente a aceptar un ensamblado con
    cobertura insuficiente?
  - ¿Qué puede provocar en los nodos un cliente malicioso o coaccionado?
  - ¿Añade un supuesto de confianza nuevo, o refuerza uno existente? Nómbralo.
  - ¿Abre alguna vía nueva de análisis de tráfico o de correlación entre
    micro-tareas?

## Plan de medición
¿Cómo sabremos que funcionó? Indica la métrica, el benchmark, la línea base
contra la que compararás y el umbral que contaría como éxito, *antes* de
implementar. Si el cambio no es medible, dilo explícitamente y explica cómo se
validará en su lugar (por ejemplo, con un argumento formal o una prueba basada
en propiedades).

## Implementación de referencia
Enlaza el PR, o escribe «aún no implementado».

## Cuestiones abiertas
Todo lo que quede sin resolver. Es mejor integrar una SWIP con una sección
honesta de cuestiones abiertas que disimular la incertidumbre.
```

## 7. Pull requests

- Parte de `main`. Mantén la rama enfocada.
- Rellena la plantilla de PR, incluidas ambas casillas (firma DCO y cita de
  medición).
- CI debe pasar: formato, lint, tipos, pruebas y DCO.
- Las revisiones son sobre el cambio, no sobre la persona. Un comentario de
  revisión escueto no es hostil; hay que presumir buena fe en ambas
  direcciones.
- Los mantenedores pueden pedir una SWIP si un PR resulta ser un cambio de
  protocolo encubierto. Es habitual y no es un rechazo.

## 8. Reportar problemas de seguridad

**No abras un issue público por una vulnerabilidad.** Escribe a
`sebas_saeu@hotmail.com` con una descripción y, a ser posible,
pasos de reproducción. Recibirás acuse de recibo; los plazos de divulgación
coordinada se acordarán caso por caso.

Mientras el proyecto no tenga una política de seguridad publicada y con
personas asignadas y tiempos de respuesta comprometidos, no des por supuesta
una respuesta de nivel empresarial. Decirlo con franqueza es mejor que un
`SECURITY.md` prometiendo un SLA que nadie puede cumplir.

## 9. Conducta

Sé directo, sé técnico, sé civilizado. Discute con el diseño, no con quien lo
diseñó. La mala fe persistente, el acoso o el intento de reabrir por desgaste
decisiones ya tomadas se saldan con la expulsión de los espacios del proyecto.
