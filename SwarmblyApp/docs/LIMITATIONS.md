# Known limitations (v0.2.x)

Limitations are documented, never hidden. *[Español](#español) below.*

## Swarmbly App

1. **Only structured requests are fragmented.** A request is distributed only
   when it has a structural partition: an enumerated batch (labelled items, or
   an inline list the app rewrites losslessly into labelled items) or questions
   linked to the material that answers them. Free prose is answered locally,
   with the reason shown. This is deliberate: the alternative is slicing text,
   which SPEC §14b.7 forbids (see `AUDIT_FASE0_ES.md`, H3).
2. **Distributed requests are single-turn.** The last user message is
   fragmented; earlier turns are not packed into the plan.
3. **No internet swarms yet.** Rendezvous, relay and NAT traversal are Phase 3
   (experimental). Mode `internet` is refused honestly.
4. **TRUSTED tier needs mutual TLS** (SPEC §15c) and is not implemented; such
   requests are answered locally and nothing is sent. Automatic triage that
   raises a request to TRUSTED with no trusted swarm configured also stays local
   (`E_SWARM_UNKNOWN`: never fall back to GLOBAL).
5. **SANITISABLE content stays local.** Pseudonymisation is not implemented;
   content the lane classifier marks SANITISABLE or SENSITIVE never leaves the
   device. The lane classifier is the LCE regex baseline: it *raises* a lane, it
   never certifies that content is safe.
6. **Verification is partial.** Result signatures (Ed25519), attempt ids and
   result schema are checked before anything enters assembly. The Layer-1
   commitment (`lsh-activation-v1`) has no normative construction (SPEC §21.1)
   and sampled audit (Layer 2) is not implemented: both are reported as *not
   available*, never simulated. The stage shows **partial**.
7. **Consensus is agreement, not truth.** With `k_min ≥ 2` replicas go to
   distinct model families and are aligned with SwarmblyAI's own `consensus()`.
   Agreement is convergence: errors are correlated across families (SwarmblyAI
   L13, L23). α thresholds are upstream provisional defaults, uncalibrated.
8. **ρ is derived, not targeted.** Packets carry mandatory content only (task,
   minimal Γ, consumed carry). Following whitepaper v2 §9.7, ρ is measured on
   what workers receive and reported; no ρ target is pursued, so
   `rho_target`/`rho_reachable` are `null` with the reason.
9. **Seam similarity is lexical by default.** The default embedder hashes
   words; switch to `model.embedder = server` (Ollama `/embeddings`, e.g.
   `nomic-embed-text`) for embedding cosines. τ_sem is a placeholder in both
   cases until calibrated (SPEC §14).
10. **Hedging starts from a declared fallback.** The hedge timer is the
    observed p95 per (kind, budget) once 8 samples exist; before that it is the
    configured `hedge_fallback_ms`, and the report says which was used.
11. **Channel binding is not mutual TLS.** The handshake binds each node's
    Ed25519 identity to the TLS certificate it presents (SSH host-key model):
    a man in the middle is detected. It is not the mutual TLS that TRUSTED
    requires.
12. **mDNS can be blocked** by routers, guest Wi-Fi or client isolation.
    Manual `host:port` connection always remains available. On macOS the OS
    asks for *Local Network* permission the first time.
13. **The idle-only worker mode is a CPU heuristic** (< 50 % over 0.5 s). The
    "only when plugged in" option relies on the battery state the OS reports;
    desktops without a battery count as plugged in.
14. **No user accounts.** Identity is the node's Ed25519 key (per the product
    spec, first version).
15. **GPU detection is best-effort**; unknown values are reported as unknown.
16. **App protocol extensions** (all MINOR-safe, ignored by implementations
    that do not know them, SPEC §3): handshake fields `hs`/`tls_fp`, message
    `advertisement_update`, advertisement fields `endpoint` and
    `policy.max_concurrent`, packet field `constraints.model_family` (SWIP draft
    in `docs/SWIP-DRAFT-model-family-hint.md`), error codes `E_POLICY`,
    `E_EXECUTION`, `E_DUPLICATE`, `E_DISCONNECTED`.
17. **Several local models share one machine.** In multi-model mode replicas
    run on different model families but the same hardware; unless the
    recommendation allows parallel generation they take turns. Their agreement
    is still agreement, not accuracy (L23).
18. **The recommended configuration is an estimate.** It combines measured
    hardware with model sizes from a catalog verified on 2026-10-12 (sizes and
    licences can change upstream). Real memory use appears once models run.
19. **Installs are narrow by design.** The app installs only the Python
    packages it knows, into its own virtual environment. It never installs
    Ollama or system software; it shows the official instructions.
20. **Downloads need a running Ollama.** Cancelling stops the stream; partial
    files are Ollama's to clean up.
21. **Memory: C1 is selectable, not yet used by chat.** The sources folder and
    level can be set; retrieval over sources feeding answers arrives with the
    LCE integration phase. C2–C4 are described, not selectable.
22. **The interface preview is fake.** `scripts/ui_preview.py` serves canned
    answers from loopback-only workers; it measures nothing.
23. **The Windows launcher is the least tested.** `launch.bat` and the
    Windows paths of `scripts/launch.py` have not run on a real Windows
    machine yet; continuous integration covers Linux and macOS.

## Upstream (audited repositories)

- SwarmblyAI: `swarmbly_v0` is a measurement harness; no networking, no
  verification, no lane classifier; the go/no-go coherence criterion was not
  met in its published measurement; SPEC v0.2 lags whitepaper v2 (§9, v0.3).
- SwarmblyLCE: raw retrieval beats the digested wiki (R13, −0.146); digestion
  is not run-to-run reproducible; layer 2 (C4) has no verdict (R11 refused).

---

## Español

1. Solo se fragmentan solicitudes con estructura (lote enumerado o preguntas
   ligadas a su material); la prosa libre se responde localmente con la razón
   visible. 2. Un solo turno. 3. Sin enjambres por internet (Fase 3). 4. TRUSTED
   requiere mTLS: se responde localmente sin enviar nada; si el triaje sube a
   TRUSTED sin enjambre confiable, también local. 5. Contenido SANITISABLE o
   SENSITIVE nunca sale del equipo (sin seudonimización aún). 6. Verificación
   **parcial**: firmas, ids y esquema sí; compromiso de capa 1 y auditoría no
   disponibles, nunca simulados. 7. Consenso = acuerdo, no verdad (L13, L23);
   umbrales α provisionales. 8. ρ se deriva y se reporta; no se persigue un
   objetivo. 9. Similitud de costuras léxica por defecto; τ_sem placeholder.
   10. El *hedge* usa el p95 observado tras 8 muestras; antes, un respaldo
   declarado. 11. El binding de canal no es mTLS. 12. mDNS puede estar
   bloqueado: la conexión manual sigue disponible; macOS pide permiso de *Red
   local*. 13. Modo "solo inactivo" heurístico por CPU. 14. Sin cuentas de
   usuario. 15. GPU por mejor esfuerzo. 16. Extensiones de la app compatibles
   MINOR, documentadas. 17. Varios modelos locales comparten la misma máquina
   y, salvo que el hardware lo permita, se turnan; su acuerdo sigue siendo
   acuerdo. 18. La configuración recomendada es una estimación (catálogo
   verificado el 2026-10-12). 19. Solo se instalan paquetes Python conocidos en
   el entorno de la app; nunca Ollama ni software del sistema. 20. Las
   descargas requieren Ollama en ejecución. 21. C1 se puede elegir pero aún no
   alimenta las respuestas del chat; C2–C4 solo se describen. 22. La vista
   previa de la interfaz es ficticia y solo usa loopback. 23. El lanzador de
   Windows es el menos probado (la integración continua cubre Linux y macOS).
