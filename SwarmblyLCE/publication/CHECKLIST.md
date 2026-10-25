---
status: current
lang: es+en
---
# Publicación de Swarmbly LCE v0.1 · Publication checklist

Este repositorio se publica en dos depósitos de Zenodo, igual que Swarmbly v2: el **artículo** (whitepaper, depósito manual) y el **software** (repositorio, por la integración de Zenodo con GitHub). La versión 0.1 contiene diseño, especificación, código y arnés, **sin resultados**; las corridas reales irán en la 0.2.

*Two Zenodo records, as for Swarmbly v2: the paper (manual upload) and the software (GitHub integration). Version 0.1 ships design, specification, code and harness, with no results.*

## 1. Antes de publicar · Before publishing

- [ ] Leer los PDF `docs/WHITEPAPER_LCE_EN.pdf` y `docs/WHITEPAPER_LCE_ES.pdf` de principio a fin (la versión inglesa es una traducción nueva).
- [ ] Revisar las tres entradas ⚠️ de `docs/REFERENCES_LCE.md` ([37], [59], [61]); cada una tiene un solo campo sin confirmar.
- [ ] Decidir si la nota de Swarmbly `FINDING_2026-10-04_correlated_errors_across_families` (pendiente de commit en `Swarmbly-AI_Clean`) se publica antes o junto con la LCE, porque el whitepaper la cita.
- [ ] `python -m pytest` y `python -m lce_validation.run_all` en verde en el Mac.
- [ ] Si se cambia cualquier `.md` de los whitepapers, regenerar los PDF: `python scripts/build_pdfs.py` (requiere pandoc, playwright con Chromium y pypdf).

## 2. Depósito del artículo · Paper record (manual)

- [ ] Zenodo → *New upload*. Archivos: `WHITEPAPER_LCE_EN.pdf`, `WHITEPAPER_LCE_ES.pdf`, `WHITEPAPER_LCE_EN.md`, `WHITEPAPER_LCE_ES.md`, `REFERENCES_LCE.md`.
- [ ] Metadatos: copiar de `publication/zenodo_whitepaper.json` (tipo *Publication → Preprint*, licencia CC BY 4.0, ORCID, palabras clave, relación *references* con 10.5281/zenodo.23031305).
- [x] Publicar y anotar el DOI del artículo: `10.5281/zenodo.23150478`.

## 3. Repositorio en GitHub · GitHub repository

- [ ] Crear el repositorio vacío `Sebastardito/SwarmblyLCE` en GitHub (sin README ni licencia, para no crear un primer commit en conflicto).
- [ ] En zenodo.org → *GitHub*, activar el interruptor de `SwarmblyLCE` **antes** de crear la release.
- [x] Añadir el DOI del artículo a `.zenodo.json` (`related_identifiers`, relación `isSupplementTo`, `resource_type: publication-preprint`) y a `CITATION.cff` (`preferred-citation.doi`); commit con `git commit -s`.
- [ ] `git push -u origin main` (el remoto `origin` ya está configurado).
- [ ] Comprobar que el workflow `tests` pasa en GitHub Actions (Python 3.10–3.13).
- [ ] Crear la release `v0.1.0` (*Swarmbly LCE v0.1.0 — draft, no results*). Zenodo crea el depósito de software y su DOI a partir de `.zenodo.json`.

## 4. Después · After

- [x] Anotar el DOI del software en `CITATION.cff` (`doi`) y en el README; añadir la insignia de DOI (v0.1.1: `10.5281/zenodo.23289041`).
- [ ] En el depósito del artículo, añadir la relación *isSupplementedBy* con el DOI del software `10.5281/zenodo.23289041` (editar metadatos en Zenodo, sin cambiar archivos).
- [x] Actualizar `docs/STATUS.md` con ambos DOI.

## 5. Hacia la versión 0.2 · Towards v0.2

- [x] Preregistro de C1/C2 confirmado antes de cualquier corrida real (`docs/PREREGISTRATION_C1_C2_ES.md` / `_EN.md`), con las reglas de decisión como código (`lce_validation/decide.py`).
- [x] Corridas confirmatorias en el Mac: la 1 falló por proyección vacía (`docs/RESULTS_2026-10-05_C1_C2_run1_*`); la 2, tras las enmiendas 2 y 3, decidió H-C2 (léxico), H-C17a y H-C17b (`docs/RESULTS_2026-10-05_C1_C2_run2_*`).
- [x] Preregistro consolidado de R14, R13 y R11 (`docs/PREREGISTRATION_BENCH_R1X_*`, enmiendas 1–15) y preregistro de R12.
- [x] Pilotos exploratorios: F1a limpio (+0.500), R13 (la wiki pierde frente al RAG crudo, −0.256; superado por la confirmatoria), R11 y R12 con conclusiones retiradas o corregidas (E6, E7).
- [x] Reparaciones de la revisión (E1–E5 y N3, la comprobación de digests que no comprobaba nada) con pruebas; anclaje de cifras citadas (`tests/test_doc_figures.py`) y digests verificados.
- [x] Prueba de olvido (F-forget) y prueba A/A (Enmienda 6 c), re-corridas en la configuración confirmatoria: el olvido se sostiene como mecanismo; AA1 (98.4 %) y AA2 (8/15) fallan, R14 sin cerrar (`docs/RESULTS_2026-10-10_Fforget_AA_*`).
- [x] Digestión determinista intentada por enmienda (endpoint nativo con semilla, parser tolerante, doble pasada revertida; Enmiendas 7, 10–12): no reproducible corrida a corrida; R14 queda abierto como negativo documentado.
- [ ] Canonicalización de claims (o digestión con otro servidor) y repetir AA1/AA2.
- [x] Confirmatoria de R13 (251 preguntas, LongMemEval MIT, sin N1): R13-H1 muere, A3 − A2 = −0.146 [−0.186, −0.106] (`docs/RESULTS_2026-10-11_R13_confirm_*`).
- [x] Revisión de las confirmatorias y Enmienda 15: R11 rechazada por falla de manipulación; C2-bis y cierre de H-C2 sin veredicto; purga del historial de los adaptadores de R11 (`docs/COMMIT_MAP_2026-10-11.md`).
- [ ] Re-correr R11 con la comprobación de manipulación previa (el adaptador debe cambiar la salida en sus propios ejemplos, con la plantilla de chat del entrenamiento).
- [ ] Re-correr C2-bis con homogeneidad entre usuarios, brazo sin contrato y placebo neutro, por enmienda.
- [ ] Cierre de H-C2 con adherencia por tarea y Δρ del packer real, con la regla de compensación reescrita por enmienda antes de correr.
- [x] Release `v0.1.1` (resultados y benchmarks), push y DOI del software: `10.5281/zenodo.23289041` (el tag apunta a `1c5e3f5`; su `CITATION.cff` aún decía 0.1.0, corregido en el commit siguiente).
- [ ] Verificación del conjunto canario por tres o más hablantes nativos (`lce_validation/data/canary_verification/`), y `python -m lce_validation.canary_verify verificador_*.csv`.
- [ ] Issue de discusión del SWIP en Swarmbly-AI con el texto de `publication/SWIP_ISSUE_Swarmbly-AI.md`; después renombrar el SWIP con el número del issue.
- [ ] Opcional: probar `MLXLoRATrainer` (extra `mlx`) en Apple Silicon.
- [x] Whitepaper v0.2 con los veredictos (incluidos los negativos) y las correcciones del arnés declaradas (`docs/WHITEPAPER_LCE_v0.2_ES.md` / `_EN.md`).
- [x] PDF de la v0.2 (`scripts/build_pdfs.py`).
- [ ] Depósito de la v0.2 en Zenodo como nueva versión del registro del whitepaper (10.5281/zenodo.23150478), con la relación *isSupplementedBy* al software.
- [ ] Release `v0.2.0` del software: antes del tag, poner `version` y `date-released` en `CITATION.cff`; después, el DOI nuevo en `CITATION.cff` y el README.
