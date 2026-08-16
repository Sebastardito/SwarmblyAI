# Swarmbly AI — Documentation Index · Índice de documentación

One page, everything that exists, what each thing is for, and in which order
to read it.

Una sola página: todo lo que existe, para qué sirve cada cosa y en qué orden
leerlo.

> **Not everything listed here is necessarily present yet.** Several of these
> documents are produced separately from this scaffolding and land in the
> repository on their own schedule. A missing file is expected, not an error.
> If a link below does not resolve, that document has not been added yet.
>
> **No todo lo que aparece aquí está necesariamente presente todavía.** Varios
> de estos documentos se elaboran por separado y llegan al repositorio a su
> propio ritmo. Que falte un archivo es lo esperable, no un fallo. Si un enlace
> no resuelve, ese documento aún no se ha añadido.

**Versions covered / Versiones cubiertas:** whitepaper **v1.4** · protocol
specification **v0.2 revision 2** · reference implementation **V0**.

---

## Start here · Empieza aquí

| Read this if… | Go to |
|---|---|
| You have two minutes and want the argument | `ONEPAGER_EN.md` · `ONEPAGER_ES.md` |
| You have five minutes and want to know what Swarmbly is | `WHITEPAPER_EN.md` Section 1 (or the repository root `README.md`) |
| You want the full argument for the design | `WHITEPAPER_EN.md` |
| You are going to implement a node or a client | `SPEC_EN.md` |
| You want to see the numbers | the dashboard, `Swarmbly_AI_Dashboard.html` |
| You want the reasoning, the alternatives, and the open questions | `WHITEPAPER_EN.md` Sections 5.4, 11 and 12 — where the design is argued against itself |
| You want to know where an idea came from | `REFERENCES.md` |
| You want to contribute | `../CONTRIBUTING.md` |
| You want to know who controls this | `../GOVERNANCE.md` |

---

## The documentation set

### Whitepaper — the argument

**`WHITEPAPER_EN.md`** · **`WHITEPAPER_ES.md`** — *v1.4*

The case for Swarmbly: why fragmenting the *problem* is a different and better
bet than fragmenting the *model*, what the shotgun-assembly analogy buys, the
architecture at a level a reader can hold in their head, the failure and threat
model, and what has and has not been demonstrated. This is the document
submitted to arXiv and the one to cite. Read it first.

*El planteamiento de Swarmbly: por qué fragmentar el problema es una apuesta
distinta y mejor que fragmentar el modelo, qué aporta la analogía del
ensamblado shotgun, la arquitectura a un nivel que quepa en la cabeza, el
modelo de fallos y de amenazas, y qué se ha demostrado y qué no. Es el
documento que se envía a arXiv y el que hay que citar.*

### Protocol specification — the contract

**`SPEC_EN.md`** · **`SPEC_ES.md`** — *v0.2, revision 2*

Normative. What an implementation must do to interoperate: message schemas,
task record format, the decomposition and assembly contracts, overlap
declaration, consensus rules, node obligations, error and timeout behaviour,
and versioning. Written so an independent implementation can be built from it
without reading the reference code — and if it cannot, that is a bug in the
specification, not in the reader.

RFC 2119 keywords (MUST, SHOULD, MAY) are used and mean what they say.
Changes go through the SWIP process (`../CONTRIBUTING.md` Section 6).

*Normativa. Lo que una implementación debe hacer para interoperar: esquemas de
mensajes, formato de registro de tarea, contratos de descomposición y
ensamblado, declaración de solapamiento, reglas de consenso, obligaciones de
los nodos, comportamiento ante errores y timeouts, y versionado. Escrita para
que se pueda construir una implementación independiente sin leer el código de
referencia; si no se puede, es un fallo de la especificación, no de quien la
lee.*

### References — the bibliography

**`REFERENCES.md`** (also distributed as `Swarmbly_AI_References.pdf`)

The authoritative bibliography: distributed and collaborative inference,
volunteer and peer-to-peer computing, task decomposition and LLM orchestration,
sequence assembly and genomics, consensus in untrusted systems, and open-source
governance. Every claim about prior work in the whitepaper and the master
documents traces back to an entry here.

This is also the file `CITATION.cff` defers to for full bibliographic detail:
where that file leaves a reference incomplete, the complete entry lives here.

*La bibliografía de referencia: inferencia distribuida y colaborativa,
computación voluntaria y P2P, descomposición de tareas y orquestación de LLM,
ensamblado de secuencias y genómica, consenso en sistemas no confiables y
gobernanza de software libre. Toda afirmación sobre trabajo previo en el
whitepaper y en los documentos maestros se remite a una entrada de aquí.*

### Dashboard — the numbers

**`Swarmbly_AI_Dashboard.html`**

Self-contained interactive HTML. Open it in a browser; nothing to install and
no network access required. Presents the measured results, the comparative
analysis, and the state of the V0 reference implementation in a form that is
faster to interrogate than a table in a PDF.

Every figure it displays is backed by a reproducible measurement — the
measurement rule in `../CONTRIBUTING.md` Section 5 applies to this dashboard as
strictly as it applies to a pull request. If a number appears here without a
reproducible source behind it, that is a defect worth an issue.

*HTML interactivo y autocontenido. Ábrelo en un navegador; no hay nada que
instalar y no necesita red. Presenta los resultados medidos, el análisis
comparativo y el estado de la implementación de referencia V0 en un formato más
rápido de interrogar que una tabla en un PDF. Toda cifra que muestra está
respaldada por una medición reproducible: la regla de medición de
`../CONTRIBUTING.md` Section 5 se aplica a este panel con el mismo rigor que a un pull
request.*

---

## Related documents outside `docs/`

These live in the repository root, and are listed here so
this page is a complete index.

| File | What it is |
|---|---|
| `../README.md` | Project overview and quick start |
| `../LICENSE` | The full GNU AGPL v3.0 text — verbatim, 661 lines |
| `../NOTICE` | Copyright, license summary, and the AGPL Section 13 network-use note |
| `../CONTRIBUTING.md` | EN/ES. DCO sign-off, why not a CLA, code style, the SWIP process, the measurement rule |
| `../GOVERNANCE.md` | EN/ES. Current status, the Verein → Stiftung path, what the Foundation will and will not do, and what would count as capture |
| `../TRADEMARK.md` | Trademark policy. Marks are **not** registered; statement of intent |
| `../CITATION.cff` | Machine-readable citation metadata (CFF 1.2.0) |
| `../.zenodo.json` | Zenodo deposition metadata |
| `RESULTS_V0_V3C.md` | First measurements against real models: the corrected coherence-tax curve, the go/no-go verdict, and the V3c agreement result |

---

## Conventions

- **Bilingual documents keep EN and ES in sync.** If you change one and cannot
  do the other, say so in the PR so it is tracked rather than silently
  drifting (`../CONTRIBUTING.md` Section 4).
- **Domain vocabulary is fixed and is used precisely.** `read`, `contig`,
  `overlap`, `scaffold`, `consensus`, `coverage` carry their shotgun-assembly
  meanings throughout. Do not introduce synonyms for concepts that already have
  names.
- **PDFs are generated, not authored.** The Markdown is the source of truth. A
  `.pdf` next to a `.md` is a build artifact; edit the `.md`.
- **Version numbers are stated in each document's header** and must agree with
  `../CITATION.cff` and `../.zenodo.json`. Divergence across those three
  records weakens the prior-art chain: the dated record is the set of Zenodo
  DOIs and the `v1` tag, and a title that drifts between them is a title a
  reader cannot follow.

---

*Contact / Contacto: `sebas_saeu@hotmail.com` — placeholder; must be
replaced before publication.*

## Public-facing material / Material divulgativo

- `ONEPAGER_EN.md` · `ONEPAGER_ES.md` — the two-page argument for the project, written for a general and a prospective-supporter audience: the asymmetry, why model-splitting fails, the reframing, what the first measurements showed, and what they did not show. It states the negative result rather than omitting it — a summary that hides its first failure has not earned its first success. Companion PDFs alongside.
- `DIVULGACION_ES.md` · `DIVULGACION_EN.md` — plain-language explainer of the project for a general audience. No jargon, no licensing or funding content. Companion PDFs alongside.
- `Swarmbly_AI_Explicativo.html` — interactive bilingual dashboard that teaches the project by exploration: the bandwidth-gap comparison, the seven-step walkthrough, the confidence-map demonstration and the "when splitting does not work" checkpoint.
- `Swarmbly_AI_Dashboard.html` — technical project dashboard (status, resolutions, architecture, coverage model, limitations, roadmap).

**Note on cross-references.** All section references in the whitepaper and the specification are written out as "Section 5.4.1" / "sección 5.4.1". The Section symbol is not used anywhere in this documentation set.
