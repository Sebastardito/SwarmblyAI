# Contributing to Swarmbly LCE

*Español abajo.*

This repository follows the contribution rules of the Swarmbly protocol repository ([`Swarmbly-AI/CONTRIBUTING.md`](https://github.com/Sebastardito/Swarmbly-AI/blob/main/CONTRIBUTING.md)). In short:

1. **DCO sign-off.** Every commit carries `Signed-off-by: Name <email>` (`git commit -s`).
2. **Changes to anything visible on the wire go through a SWIP.** The LCE's wire-visible parts are the cognitive capability block of the node profile and the capsule messages (`swips/SWIP-XXXX-local-cognitive-extension.md`). Purely local components (wiki, policy, adapter, affinity) do not need a SWIP.
3. **Invariants I1–I8 are not negotiable in a PR.** `tests/test_invariants.py` has one test per invariant; a change that breaks one is a design change and needs a SWIP or a whitepaper revision first.
4. **No claim without measurement.** A PR that reports a performance or quality result must include the run (`results_real.json`) and declare its scope. Mock and simulation results are never reported as evidence.
5. **Instruments before experiments.** A new measurement comes with an instrument test in `lce_validation/instruments.py` that shows it detects what it must.
6. **Documentation is bilingual** (`_ES` / `_EN`), every document declares `status:` in its front matter, and the `§` sign is not used: write "Section 5.4" / "sección 5.4".

Licences: code AGPL-3.0-or-later; documentation CC BY 4.0.

---

## Español

Este repositorio sigue las reglas de contribución del repositorio del protocolo Swarmbly: firma DCO en cada commit; SWIP para todo lo visible en la red (bloque de capacidades y cápsulas); las invariantes I1–I8 no se negocian en un PR (`tests/test_invariants.py` tiene una prueba por invariante); ningún resultado sin medición ni sin alcance declarado; un instrumento probado antes de cada medida nueva; documentación bilingüe con `status:` en el encabezado y sin el símbolo `§`.
