---
status: current
lang: es+en
---

# Correspondencia de commits tras la purga de pesos (10 de octubre de 2026) · Commit map after the weights purge

El commit `17b52b5` incluyó por error los pesos de un adaptador de R11
(`results/bench_r11/*/adapter/*.safetensors`, 3 × 26 MB) y su lote de
entrenamiento; el commit siguiente los quitó del árbol, pero seguían en el
historial. Los pesos derivan de Qwen2.5-3B-Instruct (licencia qwen-research)
y no se distribuyen (ver `NOTICE`). Antes del primer push que contiene esos
commits se reescribió el historial desde `17b52b5` para eliminar esas rutas.
El árbol final no cambió; cambiaron los identificadores de 18 commits.

Las salidas crudas guardan en su procedencia (`git_commit`) el identificador
ANTERIOR, porque se escribieron antes de la purga y no se editan. Esta tabla
traduce cada identificador anterior al publicado.

*Commit `17b52b5` mistakenly included the weights of an R11 adapter and its
training batch; the next commit removed them from the tree but they remained
in history. The weights derive from Qwen2.5-3B-Instruct (qwen-research
licence) and are not distributed. Before the first push containing those
commits, history was rewritten from `17b52b5` to remove those paths. The final
tree did not change; 18 commit identifiers did. Raw outputs keep the PREVIOUS
identifier in their provenance (`git_commit`), because they were written
before the purge and are not edited. This table maps each previous identifier
to the published one.*

| Anterior · Previous | Publicado · Published | Commit |
|---|---|---|
| `17b52b5` | `78d7096` | R12: preregistro separado y banco social rediseñado (2 rondas, prevalencia mayoritaria real, utilidad sin clave, sonda con cápsulas) |
| `15ceeba` | `9903cad` | gitignore: artefactos de entrenamiento de R11 (regenerables con la receta) |
| `1383b52` | `646593a` | R12 exploratorio: el circuito de adopción funciona y las cápsulas de modelos propagan ignorancia (respaldo empírico de I4) |
| `2ff87b6` | `3f04dfa` | R11: la recuperación+Γ domina al adaptador; dirección de la muerte de la capa 2 fijada |
| `e226de7` | `e3a9be3` | Cierre: reporte regenerado con el veredicto R12 y convención de documentos sin signo de sección |
| `7baf5b0` | `1ac5133` | Regeneración de la ronda de reparación (E1-E8, código) |
| `7363881` | `ea04c81` | Regeneración: documentos y procedencia (SWIP con retracción E4, 10 instrumentos, R11/R12 procedencia) |
| `84f0c46` | `4457116` | F1a limpio recuperado: +0.500 [0.420, 0.578] — reproducción exacta de la corrida perdida |
| `f80c88b` | `b33f8ec` | Regeneración: EN de R11/R12, retracción de R13 y filas de STATUS |
| `140615a` | `f87b363` | R13 recuperado: A3 por digestor, -0.256 por pregunta, deleted +0.156; documentos cerrados |
| `dc191f6` | `5ca1d07` | Reparaciones con pruebas: contexto de wiki único, resumen sin sobrescritura, digests y abstención |
| `d03f42e` | `710fe35` | Enmienda 6 (antes de correr): reparaciones declaradas, N1/N2, prueba de olvido y A/A |
| `24eb224` | `de8bcd2` | R13: análisis derivado sin modelos (por digestor, por tipo, N1, abstención con exactitud, cobertura) anclado en run_derive |
| `d20b28c` | `1532919` | Documentos al día con las cifras vigentes, retracciones visibles y anclaje de cifras citadas |
| `e48fe25` | `46b6c25` | Documentos de entrada y metadatos al día: README, CITATION, .zenodo.json, NOTICE, SPEC, SWIP, issue y lista |
| `586eb21` | `eca8f88` | script de corridas: acepta el modelo con tag :latest en el chequeo |
| `01df817` | `2267dee` | F-forget y A/A: resultados anclados, reporte y documentos |
| `c65f10c` | `db87fff` | F-forget y A/A: conducta conforme al preregistro, equivalencia con R13 y documentos EN completos |

*Texto CC BY 4.0 · Text CC BY 4.0.*
