---
status: current
lang: es+en
---

# Correspondencia de commits tras la segunda purga de pesos (11 de octubre de 2026) · Commit map after the second weights purge

La confirmatoria de R11 dejó en el árbol los adaptadores entrenados y sus
lotes (`results/bench_r11_confirm/*/adapter/` y `*/data/`, unos 200
archivos), y el commit `2c21d8e` (Enmienda 13) y los siguientes los
confirmaron en el repositorio. Los adaptadores derivan en parte de
Qwen2.5-3B-Instruct (licencia qwen-research) y no se distribuyen (ver
`NOTICE`). Antes del primer push que contiene esos commits se reescribió el
historial desde `2c21d8e` para eliminar esas rutas, y `.gitignore` las
excluye desde entonces. El contenido de los demás archivos no cambió;
cambiaron los identificadores de 12 commits.

Las salidas crudas guardan en su procedencia (`git_commit`) el identificador
ANTERIOR, porque se escribieron antes de la purga y no se editan: la
confirmatoria de R11 dice `b8b474e` (publicado `b836e84`) y C2-bis dice
`1e363f2` (publicado `9fd3a1a`). Los asuntos de los commits se conservan
como se escribieron; varias de sus conclusiones (R11 «la capa 2 se
retira», C2-bis «H-C17a se sostiene», cierre de H-C2) se retiran en la
Enmienda 15 y en los documentos de resultados.

*The R11 confirmatory run left the trained adapters and their batches in
the tree (about 200 files), and commit `2c21d8e` (Amendment 13) and the
following ones committed them. The adapters derive partly from
Qwen2.5-3B-Instruct (qwen-research licence) and are not distributed.
Before the first push containing those commits, history was rewritten from
`2c21d8e` to remove those paths, and `.gitignore` excludes them since. No
other file content changed; 12 commit identifiers did. Raw outputs keep
the PREVIOUS identifier in their provenance: the R11 confirmatory run says
`b8b474e` (published `b836e84`) and C2-bis says `1e363f2` (published
`9fd3a1a`). Commit subjects are kept as written; several of their
conclusions are retracted in Amendment 15 and in the result documents.*

| Anterior · Previous | Publicado · Published | Commit |
|---|---|---|
| `2c21d8e` | `60c563e` | Enmienda 13: evaluación de R11 por servidor MLX persistente con reanudación |
| `6a73f38` | `6bb1194` | Enmienda 14: C2-bis re-corre con la petición corregida (la Γ de 4 tokens era invocación, no diseño) |
| `fd65338` | `be8fd61` | C2-bis: petición vacía (fallback amplio del Projector) — Γ completa en los 5 usuarios |
| `86ed654` | `78fd26e` | Enmienda 14 afinada: la petición corregida es la vacía (fallback amplio) — Γ completa en los 5 usuarios |
| `8327587` | `fa5da5c` | bench_r11: un solo servidor MLX activo a la vez (el pool acumulaba procesos y saturaba la RAM) |
| `7f8e30d` | `74ab3cc` | bench_r11: evaluación agrupada por brazo — 2 cargas de servidor por configuración |
| `b8b474e` | `b836e84` | bench_r11: desempaquetado del servidor anterior corregido |
| `1e363f2` | `9fd3a1a` | R11 CONFIRMATORIA: H-C6 no se sostiene — la capa 2 se retira |
| `fee944f` | `316c312` | SWIP: estado final con los veredictos confirmatorios de R13, R11 y H-C2 |
| `c4d92bc` | `244f45d` | C2-bis: H-C17a SE SOSTIENE — Γ reduce homogeneidad +0.065 [0.056, 0.074] sobre placebo igualado |
| `62296bc` | `acb2711` | SWIP: veredictos confirmatorios de R13, H-C2, C2-bis y R11 |
| `48b2cae` | `6b7bcd5` | Reporte y anclaje: C2-bis, cierre H-C2 y R11 confirmatoria en BENCH_REPORT y run_derive |

*Texto CC BY 4.0 · Text CC BY 4.0.*
