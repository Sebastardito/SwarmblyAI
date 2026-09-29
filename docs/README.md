---
status: current
lang: es+en
---
# Swarmbly AI — Documentation Index · Índice de documentación

One page, everything that exists, what each thing is for, and in which order
to read it.

Una sola página: todo lo que existe, para qué sirve cada cosa y en qué orden
leerlo.

> ## ¿Se puede citar? · May I quote it?
>
> **Antes de citar cualquier cifra, mirá [`STATUS.md`](STATUS.md).** Varios
> documentos de este repositorio fueron retirados o superados por una medición
> posterior, y siguen aquí a propósito: borrarlos dejaría el registro más
> limpio y menos honesto. `STATUS.md` dice, sin abrir nada, cuál de dos cifras
> es la que se sostiene. Se genera desde los documentos, así que no puede
> desfasarse de ellos.
>
> **Before quoting any figure, see [`STATUS.md`](STATUS.md).** Several
> documents here were withdrawn or superseded by a later measurement, and they
> stay on purpose: deleting them would leave a tidier record and a less honest
> one. `STATUS.md` says, without opening anything, which of two figures stands.
> It is generated from the documents, so it cannot drift from them.
>
> Un enlace roto en este índice ya no es normal: `tests/test_docs_boundary.py`
> falla si un archivo rastreado cita un documento que no está en el árbol.
> *A broken link in this index is no longer normal:
> `tests/test_docs_boundary.py` fails when a tracked file cites a document that
> is not in the tree.*

**Versions covered / Versiones cubiertas:** whitepaper **v2.0** (v1.4 kept,
superseded) · protocol specification **v0.2 revision 2** · reference
implementation **V0** · new reference implementation **swarmbly_ref**
(Ollama bench) · validation harness **swarmbly_validation**.

---

## Start here · Empieza aquí

| Read this if… | Go to |
|---|---|
| You have two minutes and want the argument | `ONEPAGER_EN.md` · `ONEPAGER_ES.md` |
| You have five minutes and want to know what Swarmbly is | `WHITEPAPER_V2_EN.md` Section 1 (or the repository root `README.md`) |
| You want the full argument for the design | `WHITEPAPER_V2_EN.md` (v1.4 kept as `WHITEPAPER_EN.md`, superseded) |
| You are going to implement a node or a client | `SPEC_EN.md` |
| You want to see the numbers | `RESULTS_2026-09-25_refbench_EN.md` for the current campaign, `STATUS.md` for what may be quoted, and `python3 swarmbly_validation/run_all.py --all` to recompute them |
| You want to know how a figure was reached, or why one was withdrawn | the research record below |
| You want the reasoning, the alternatives, and the open questions | `WHITEPAPER_V2_EN.md` Sections 5–6, 11 and 16 — where the design is argued against itself |
| You want to know where an idea came from | `REFERENCES.md` |
| You want to contribute | `../CONTRIBUTING.md` |
| You want to know who controls this | `../GOVERNANCE.md` |

---

## The documentation set

### Whitepaper — the argument

**`WHITEPAPER_V2_EN.md`** · **`WHITEPAPER_V2_ES.md`** — *v2.0, current*

The case for Swarmbly, with the theory of fragmentation the earlier version
lacked: the semantic unit and the fragment, the derived context budget, the
five falsifiable models M1–M5 **measured against 473 real runs** (§15.9), the
validation strategy (`VALIDATION_STRATEGY_V2`) and the fragmentation
fundamentals extension (`WHITEPAPER_EXT`). This is the one to cite. Read it
first. PDFs alongside: `WHITEPAPER_V2_EN.pdf` · `WHITEPAPER_V2_ES.pdf`.

**`WHITEPAPER_EN.md`** · **`WHITEPAPER_ES.md`** — *v1.4, superseded*

Kept as the published prior-art record (Zenodo, 14 August 2026). Its measurements
remain valid with the corrections documented in v2.

*El planteamiento de Swarmbly, con la teoría de la fragmentación que a la
versión anterior le faltaba: la unidad semántica y el fragmento, el presupuesto
de contexto derivado, los cinco modelos falsables M1–M5 **medidos contra 473
corridas reales** (§15.9), la estrategia de validación
(`VALIDATION_STRATEGY_V2`) y la extensión de fundamentos (`WHITEPAPER_EXT`).
Éste es el que hay que citar. Se conserva v1.4 como registro de prior art
publicado (Zenodo, 14 de agosto de 2026), con sus mediciones válidas bajo las correcciones
documentadas en v2.*

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

### Research record — how each figure was reached

Every measurement the whitepaper rests on has its own document, and so does every
one that was withdrawn. They are kept as written; the header of each states
whether it is current, superseded or withdrawn, and `STATUS.md` collects those
states on one page. Pairs are EN · ES.

*Cada medición en la que descansa el whitepaper tiene su propio documento, y
también cada una que se retiró. Se conservan tal como se escribieron; el
encabezado de cada uno dice si está vigente, superado o retirado, y `STATUS.md`
reúne esos estados en una página.*

| Kind | Documents |
|---|---|
| Current campaign | `RESULTS_2026-09-25_refbench_EN.md` · `_ES` — 473 runs, the verdicts on M1–M5 and the L curve · `VALIDATION_STRATEGY_V2_EN.md` · `_ES` · `WHITEPAPER_EXT_EN.md` · `_ES` |
| Pre-registrations | `PREREGISTRATION_composition.md` · `_ES` · `PREREGISTRATION_term_once.md` · `_ES` · `PREREGISTRATION_comp_final_once_EN.md` · `PREREGISTRATION_comp_final_once.md` · `PREREGISTRATION_feasibility_EN.md` · `PREREGISTRATION_feasibility.md` · `PREREGISTRATION_L_curve_EN.md` · `PREREGISTRATION_L_curve.md` · `PREREGISTRATION_2026-09-25_interaction_EN.md` · `_ES` |
| Results, September 2026 | `RESULTS_2026-09-05_three_tiers.md` · `_ES` · `RESULTS_2026-09-05_oracle_and_k3.md` · `_ES` · `RESULTS_2026-09-05_oracle_v2.md` · `_ES` · `RESULTS_2026-09-05_term_once_EN.md` · `RESULTS_2026-09-05_term_once.md` · `RESULTS_2026-09-05_final_dedup_EN.md` · `RESULTS_2026-09-05_final_dedup.md` · `RESULTS_2026-09-22_lcurve_dev_EN.md` · `RESULTS_2026-09-22_lcurve_dev.md` (a method defect; the L curve itself is measured in whitepaper v2, §15.4) · `RESULTS_2026-09-25_interaction_EN.md` · `_ES` · `RESULTS_COMPOSITION_FINAL.md` · `_ES` (superseded) |
| Results, August 2026 | `RESULTS_V0_V3C.md` · `_ES` · `RESULTS_V3C_FF_COMPOSITION.md` · `_ES` · `RESULTS_V3C_GT_CORRECTED.md` · `_ES` · `RESULTS_V4.md` · `_ES` · `RESULTS_V5.md` · `_ES` · `RESULTS_V6.md` · `_ES` · `RESULTS_TABLES_DEV.md` · `_ES` · `RESULTS_TABLES_DEV2.md` · `_ES` · `RESULTS_TABLES_FINAL.md` · `_ES` (superseded) · `RESULTS_TABLES_FINAL_CORRECTED.md` · `_ES` |
| Reviews, incidents and decisions | `REVISION_2026-08-12_EN.md` · `REVISION_2026-08-12.md` · `REVISION_2026-09-05_que_hemos_medido_EN.md` · `REVISION_2026-09-05_que_hemos_medido.md` · `STATE_2026-09-04.md` · `_ES` · `INCIDENT_2026-09-04_chain_misplan.md` · `_ES` · `FINDING_2026-09-04_segmenter_splits_question_from_data.md` · `_ES` · `POSTMORTEM_2026-09-05_four_tiers.md` · `_ES` · `ADR-001_instrument_boundary.md` · `_ES` |
| Operations | `RUNBOOK.md` · `RUNBOOK_ES.md` — how to run each tier, and how to rehearse it first |

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

*Contact / Contacto: `sebas_saeu@hotmail.com`.*

## Public-facing material / Material divulgativo

- `ONEPAGER_EN.md` · `ONEPAGER_ES.md` — the two-page argument for the project, written for a general and a prospective-supporter audience: the asymmetry, why model-splitting fails, the reframing, what the first measurements showed, and what they did not show. It states the negative result rather than omitting it — a summary that hides its first failure has not earned its first success. Companion PDFs alongside.
- `DIVULGACION_ES.md` · `DIVULGACION_EN.md` — plain-language explainer of the project for a general audience. No jargon, no licensing or funding content. Companion PDFs alongside.

**Note on cross-references.** The v1.4 whitepaper and the specification write section references out as "Section 5.4.1" / "sección 5.4.1". Whitepaper v2 and the results documents use the section sign, "§5.4.1".
