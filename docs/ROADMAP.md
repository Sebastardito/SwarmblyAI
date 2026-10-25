# Roadmap · Hoja de ruta

**Language / Idioma:** [English](#english) · [Español](#español)

> The exit criteria below are **targets**, written before measuring so that the goalposts do not move; they carry no dates. Results that miss a target are published as they are.
>
> Los criterios de salida son **objetivos**, escritos antes de medir para que la meta no se mueva; no llevan fechas. Los resultados que no alcancen un objetivo se publican tal cual.

---

## English

| Phase | Content | Exit criteria (targets) |
|---|---|---|
| **3.0 — Integrated distribution** (this release) | SwarmblyCore, SwarmblyLCE and SwarmblyApp in one repository; interactive installer; holistic documentation | The installer works on macOS, Linux and Windows; mirrors match the lock in continuous integration |
| **3.1 — Stable** | Grounded composition (plan → retrieve → facts sheet → write → verify; tables built by code); author search with explicit consent (ORCID, OpenAlex, PubMed, Scholar through SearXNG); model roles (planner, writer, verifier) with bounded reasoning; automatic test that nothing personal leaves the device; held-out benchmark v2; C1 moved into SwarmblyLCE | Held-out sets measured and published; zero leaks in the privacy test; zero lost answers in a 100-request run |
| **3.2 — Private beta** | Capability-aware routing (a public request to the peer with the strongest model); nodes that search to fill their own gaps; progress view and clickable citations; one-click installers; orchestrator moved into SwarmblyCore (`swarmbly-core`); 5–10 external testers | ≥ 90 % successful installs; no severe bug open for two weeks; no regression on held-out sets |
| **3.3 — Public beta** | Protocol specification 1.0-rc with conformance tests; LCE specification 0.3 (retrieval over sources, wiki as governance, verifiable forgetting); external privacy review | No critical finding; a third-party node passes conformance |
| **4.0 — 1.0 of the protocol** | Protocol frozen; signed installers; versioning policy; governance in place | Public-beta criteria held for two releases |
| **Later** | Internet-wide swarms (rendezvous, NAT traversal, reputation); network credits; **SwarmblyAgents** (sub-orchestrators specialised by function, delegation one level deep, verified by sources); LCE C3–C4 | Each starts with a design document and a pre-registered experiment |

**Benchmark v2.** Four sets: the current questions on one user's material (development only); new questions written blind and a second fictional person's documents (held out); open composition with a rubric (claims supported, unsupported or contradicted; key-fact coverage; format); network batches in new domains (held out). Tuning uses development sets only; held-out sets run once per release.

---

## Español

| Fase | Contenido | Criterios de salida (objetivos) |
|---|---|---|
| **3.0 — Distribución integrada** (esta versión) | SwarmblyCore, SwarmblyLCE y SwarmblyApp en un solo repositorio; instalador interactivo; documentación de conjunto | El instalador funciona en macOS, Linux y Windows; los espejos coinciden con el lock en la integración continua |
| **3.1 — Estable** | Composición fundamentada (planificar → recuperar → hoja de datos → redactar → verificar; tablas armadas por código); búsqueda de autor con consentimiento explícito (ORCID, OpenAlex, PubMed, Scholar vía SearXNG); modelos por papel (planificador, redactor, verificador) con razonamiento acotado; prueba automática de que nada personal sale del equipo; banco v2 con conjunto reservado; C1 movida a SwarmblyLCE | Conjuntos reservados medidos y publicados; cero fugas en la prueba de privacidad; cero respuestas perdidas en una batería de 100 peticiones |
| **3.2 — Beta privada** | Enrutamiento según capacidad (una petición pública al par con el mejor modelo); nodos que buscan para llenar sus propios vacíos; vista de progreso y citas clicables; instaladores de un clic; orquestador movido a SwarmblyCore (`swarmbly-core`); 5–10 probadores externos | ≥ 90 % de instalaciones exitosas; ningún error grave abierto durante dos semanas; sin regresión en los conjuntos reservados |
| **3.3 — Beta pública** | Especificación del protocolo 1.0-rc con pruebas de conformidad; especificación LCE 0.3 (recuperación sobre las fuentes, wiki como gobierno, olvido verificable); revisión externa de privacidad | Ningún hallazgo crítico; un nodo de terceros pasa la conformidad |
| **4.0 — 1.0 del protocolo** | Protocolo congelado; instaladores firmados; política de versiones; gobernanza en marcha | Criterios de la beta pública sostenidos durante dos versiones |
| **Después** | Enjambres por internet (encuentro, NAT, reputación); créditos de red; **SwarmblyAgents** (suborquestadores especializados por función, delegación de un nivel, verificada con fuentes); LCE C3–C4 | Cada uno empieza con un documento de diseño y un experimento preregistrado |

**Banco v2.** Cuatro conjuntos: las preguntas actuales sobre el material de un usuario (solo desarrollo); preguntas nuevas escritas a ciegas y los documentos de una segunda persona ficticia (reservados); composición abierta con rúbrica (afirmaciones respaldadas, sin respaldo o contradichas; cobertura de datos clave; formato); lotes de red en dominios nuevos (reservados). Se ajusta solo con los conjuntos de desarrollo; los reservados se corren una vez por versión.
