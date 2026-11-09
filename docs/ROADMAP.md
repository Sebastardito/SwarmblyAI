# Roadmap · Hoja de ruta

**Language / Idioma:** [English](#english) · [Español](#español)

> The exit criteria below are **targets**, written before measuring so that the goalposts do not move; they carry no dates. Results that miss a target are published as they are.
>
> Los criterios de salida son **objetivos**, escritos antes de medir para que la meta no se mueva; no llevan fechas. Los resultados que no alcancen un objetivo se publican tal cual.

---

## English

### Contents

1. [From the idea to today](#from-the-idea-to-today)
2. [Where the project stands](#where-the-project-stands)
3. [The road to a public network with volunteers](#the-road-to-a-public-network-with-volunteers)
4. [Volunteer programme](#volunteer-programme)
5. [Tracks that run alongside](#tracks-that-run-alongside)
6. [Decisions behind this roadmap](#decisions-behind-this-roadmap)

### From the idea to today

```mermaid
flowchart LR
  A["<b>Aug 2026</b><br/>idea and protocol<br/>whitepaper v1, repo, DOI"] --> B["<b>Aug–Sep</b><br/>measuring with<br/>real models"]
  B --> C["<b>Sep</b><br/>where fragmenting<br/>wins · whitepaper v2"]
  C --> D["<b>Oct</b><br/>private memory<br/>(LCE)"]
  D --> E["<b>Oct</b><br/>desktop app<br/>and LAN swarm"]
  E --> F["<b>Oct</b><br/>one repository,<br/>one installer (3.0)"]
  F --> G["<b>Nov</b><br/>review: destinations,<br/>projects, agents"]
```

| Stage | When | What was built | What was learned |
|---|---|---|---|
| **1 · Idea and protocol** | August 2026 | The question was whether AI could run on hardware shared by its users, like a torrent. Existing systems (Petals) split the **model**, so every token crosses the network and the slowest node sets the pace. The answer proposed here splits the **problem**, borrowing the vocabulary of genome shotgun assembly (reads, overlaps, contigs, consensus). The project began as GenoNet AI and was renamed Swarmbly. First outputs: whitepaper v1 and specification v0.2, reference implementation, measurement harness (V0), public repository (15 August), and Zenodo DOIs for the software ([10.5281/zenodo.21956743](https://doi.org/10.5281/zenodo.21956743)) and the whitepaper ([10.5281/zenodo.21957088](https://doi.org/10.5281/zenodo.21957088)) | Defensive publication: the design is dated, public and enabling. Mock runs validate the instrument, not the idea |
| **2 · Measuring with real models** | 23 August – 5 September | Campaigns with several model families, pre-registrations, and incident and post-mortem reports, published even when they went against the design | Agreement between replicas does **not** predict correctness (AUC 0.507): the confidence map was withdrawn. Distributed composition lost to a single model. The coherence-tax criterion was not met |
| **3 · Where fragmenting wins** | 21–29 September | L curve (fragment size as the variable), matched-budget campaign (473 runs), whitepaper v2 ([10.5281/zenodo.23031305](https://doi.org/10.5281/zenodo.23031305)), release v2 | **Extract with small models, aggregate with code: +46.9 points** over the model alone. This is the strongest result, and it points the design at search, extraction and verification rather than at writing |
| **4 · Private memory (LCE)** | 4–10 October | Local Cognitive Extension: whitepaper and specification 0.1 ([10.5281/zenodo.23150478](https://doi.org/10.5281/zenodo.23150478)), pre-registered runs, v0.1.0 and v0.1.1 | Local memory helps (+0.500 [0.420, 0.578]). The anchored wiki **loses** to plain retrieval over the user's documents (−0.146), so it became a governance layer. Errors are correlated across model families |
| **5 · App and LAN swarm** | 11–25 October | SwarmblyApp: local chat, real peer-to-peer over the LAN (TLS 1.3, Ed25519, mDNS), validated with 2 to 5 machines. v0.2.0 ([10.5281/zenodo.23322639](https://doi.org/10.5281/zenodo.23322639)) added guided setup. Later work added the item vote and the composition planner, public evidence (Wikidata, Wikipedia, PubMed, SearXNG), local memory in the chat, hybrid retrieval, and a heterogeneous network of 4–5 machines with routing by capability and speed | Public evidence per item fixes what small models do not know (IUCN status 8/8 against about 1/8). The network survives losing its largest node. An open test showed that a personal request could leave the device and be written without data: personal requests now stay local |
| **6 · One repository, one installer** | 25–28 October | Swarmbly AI 3.0.0 ([10.5281/zenodo.23650763](https://doi.org/10.5281/zenodo.23650763)): SwarmblyCore, SwarmblyLCE and SwarmblyApp in one distribution, an interactive installer for three systems and documentation for the whole project | Measurements so far come from one person's material; a held-out benchmark is required before calling any change general |
| **7 · Review of the next ideas** | 4 November | A review of the code and of the proposals for agents, a fuller app, projects, tools and templates. The decisions are listed [at the end](#decisions-behind-this-roadmap) | A configured third-party API received private passages on the "local" path. Controlling where each piece of data goes comes before any new feature. A Docker distribution was added so more people can try the app |
| **8 · Destinations and a sealed benchmark** | 5–7 November | Swarmbly AI 3.0.1 ([notes](releases/v3.0.1.md)): an outbound policy before every call, a privacy receipt with every answer, API keys in the keychain, a Docker image. Two sealed banks written by the maintainer, run blind by a harness and scored by an isolated judge (κ = 0.885 against a blind human review) | Nothing forbidden left in 17/17 personal-data cases; the app's receipt matched the network in 23/24; composition is still weak (0/7 pass), which sets 3.2's priority |
| **9 · Projects** | 7–9 November | Swarmbly AI 3.1.0 ([notes](releases/v3.1.0.md)): projects, citations to the paragraph, memory with the user's yes, approved online search with terms reviewed as concepts, consent per question, sentences without a source marked. Daily hands-on tests by the maintainer and automated rounds on his computer; two measurements on the sealed banks, the first diagnosed on an open fictitious battery | Nothing forbidden left in 24/24 cases and the receipt matched the network in 24/24; citation-backed claims rose; no composition passes yet (3.2). Pending exit criterion: 3–5 non-technical people understand the receipt |

### Where the project stands

| Works, measured | Not yet, or refuted |
|---|---|
| Privacy lanes; personal requests stay local; evidence sent by name only; where each call goes is enforced, with a privacy receipt per answer (3.0.1); projects, consent per question, memory with the user's yes (3.1) | Grounded composition; the receipt tried with non-technical people |
| LAN swarm: authentication, hedging, local fallback, learned speed | Internet swarms; no tools (MCP) or skills |
| Batches with evidence; extraction with aggregation by code | Distributed long-form writing; coherence-tax criterion |
| Local memory over text, Word, HTML and PDF | Grounded composition (fact sheet, tables by code, verifier) |
| Installer for three systems; Docker image; sealed benchmark banks, run once per version | Testers outside the project; a second model on the banks |

### The road to a public network with volunteers

Each version can be shown working on its own. Volunteers join in growing circles: first people the maintainer knows, then invited circles, then the public.

```mermaid
flowchart LR
  V1["<b>3.0.1</b><br/>destinations<br/>+ Docker"] --> V2["<b>3.1</b><br/>projects and<br/>privacy receipt"]
  V2 --> V3["<b>3.2</b><br/>providers by role<br/>and recipes"]
  V3 --> V4["<b>3.3</b><br/>tools: MCP<br/>and skills"]
  V4 --> V5["<b>3.4</b><br/>teams and trusted<br/>circles · private beta"]
  V5 --> V6["<b>3.5</b><br/>public network<br/>· public beta"]
  V6 --> V7["<b>4.0</b><br/>protocol 1.0<br/>· public release"]
  V7 -.-> V8["<b>later</b><br/>agent hierarchy,<br/>LCE C3–C4"]
  style V5 fill:#2a78d622,stroke:#2a78d6
  style V6 fill:#2a78d622,stroke:#2a78d6
```

| Version | Content | Exit criteria (targets) |
|---|---|---|
| **3.0.1 — Destinations** | <ul><li>Every model provider is labelled local, my network or third party, checked from its address.</li><li>An outbound policy runs before every call: answer, query expansion, embeddings, assembly, worker, retries and fallback.</li><li>A node never serves the swarm through a third-party API.</li><li>Answers record where they were actually computed.</li><li>API keys move to the system keychain.</li><li>Docker distribution.</li></ul> | A synthetic leak test fails if any path sends private passages, or other nodes' fragments, to an unauthorised destination |
| **3.1 — Projects** | <ul><li>Projects with their own folder (default `Documents/Swarmbly/<Project>`, with a warning for cloud-synced folders).</li><li>Project memory kept apart from personal memory.</li><li>Chats saved in the folder.</li><li>Export and restore as a `.swarmbly` package with hashes and without secrets.</li><li>A **privacy receipt** for each answer: what left, for whom, why.</li><li>C1 moved into SwarmblyLCE.</li></ul> | <ul><li>Two projects stay isolated.</li><li>A restore on another computer and system keeps chats, sources and citations.</li><li>3–5 non-technical people understand the receipt</li></ul> |
| **3.2 — Providers and recipes** | <ul><li>Several providers (local, OpenAI-compatible, Anthropic) assigned **by role**: planner, extractor, writer, verifier, embeddings. Third parties are an explicit choice per project and per role.</li><li>Bounded reasoning per role.</li><li>Four reference recipes, run as flows in code: *ask your documents*, *compare documents into a table*, *research with public sources*, *process a list on the swarm*.</li><li>Grounded composition, built on what 3.1 already has (C1 citations, labels, the anchoring measure): a local inventory of the request's requirements; an evidence ledger of admitted facts with their `doc:` citations, values and units checked by code; a requirement ↔ evidence matrix; a composer that writes only from admitted facts and builds tables by code; a claim auditor (deterministic first, a model check where it pays) and at most one bounded repair, off by default. All local, behind flags, measured one step at a time (F0 = 3.1, then each addition).</li><li>An open development battery, separate from the sealed banks, for S1/S2/S3, follow-ups, contradictions, consent, isolation and prompt injection.</li><li>The agent runtime is born in SwarmblyCore.</li><li>Benchmark v2 with held-out sets.</li></ul> | <ul><li>The same recipes run with a local model and with an API.</li><li>Held-out sets measured and published.</li><li>Zero unauthorised sends</li></ul> |
| **3.3 — Tools** | <ul><li>One tool broker.</li><li>MCP client: local servers approved one by one; remote ones shown as third parties.</li><li>Skills in the open Agent Skills format (`SKILL.md`), instructions only at first.</li><li>Importing never runs anything.</li><li>Author search with consent (ORCID, OpenAlex, PubMed).</li></ul> | <ul><li>Effective permissions equal the declared ones.</li><li>A page containing instructions cannot widen them</li></ul> |
| **3.4 — Teams and trusted circles · private beta** | <ul><li>Nodes announce roles: search, large model, reasoner, corpus.</li><li>The same team runs on one node or several.</li><li>**Trusted circles:** small swarms joined by invitation (code or QR) that also work beyond the LAN, through direct addresses or an overlay network.</li><li>Non-transferable reciprocity credits.</li><li>Signed installers.</li><li>**20–50 volunteers** in 3–5 circles.</li></ul> | <ul><li>Team versus equivalent local run measured.</li><li>Losing a node leaves honest partial results.</li><li>≥ 90 % successful installs.</li><li>No severe bug open for two weeks</li></ul> |
| **3.5 — Public network · public beta** | <ul><li>Rendezvous and relay; NAT traversal.</li><li>Reputation, rate limits and abuse protection.</li><li>Protocol 1.0-rc with conformance tests.</li><li>LCE specification 0.3.</li><li>External privacy review.</li><li>Automatic updates.</li><li>Open registration of volunteers.</li></ul> | <ul><li>No critical finding.</li><li>A third-party node passes conformance.</li><li>Leak test and held-out sets without regression on the public network</li></ul> |
| **4.0 — Protocol 1.0 · public release** | <ul><li>Protocol frozen, with capability negotiation, delegation and third-party destinations decided.</li><li>Versioning policy.</li><li>Governance in place (Swiss Verein).</li></ul> | Public-beta criteria held for two releases |
| **Later** | <ul><li>**SwarmblyAgents hierarchy:** one level of delegation, kept only if a held-out experiment shows it beats the flat team.</li><li>LCE C3–C4.</li><li>Further incentives for sharing.</li></ul> | Each starts with a design document and a pre-registered experiment |

**Out of scope for now:**

- sharing API keys through the swarm;
- running scripts from skills, or starting MCP servers automatically;
- delegation deeper than one level;
- calling a recipe "optimised" without a measurement;
- a transferable token (see [`GOVERNANCE.md`](../GOVERNANCE.md)).

### Volunteer programme

| Phase | Who | What volunteers do | What they get |
|---|---|---|---|
| Alpha (3.1–3.3) | People the maintainer knows, 5–10 | Install (native or Docker), use the recipes, send local reports voluntarily | Early access; their findings shape the next version |
| Private beta (3.4) | 3–5 invited circles, 20–50 people | Share their computers within their circle; try teams and batches | A swarm of their own; reciprocity credits |
| Public beta (3.5) | Anyone | Run a node on the public network, report problems | Free access to community computing |

Telemetry is never collected. Reports are files the user chooses to send. Feedback goes through GitHub issues and the private security channel ([`SECURITY.md`](../SECURITY.md)).

### Tracks that run alongside

| Track | Content |
|---|---|
| Evaluation | Benchmark v2: development and held-out sets, a second fictitious person, open composition with a rubric, network batches in new domains. Held-out sets run once per release |
| Research | Pre-registered experiments: reasoning by role; single agent → flat team → specialised models → distributed → hierarchy |
| Documentation and community | Bilingual guides, a guide for volunteers, a contributing guide, a short paper of honest results |
| Governance and funding | Swiss Verein, then Stiftung; sustainability grants; [Buy Me a Coffee](https://buymeacoffee.com/swarmbly). Support never buys influence |

### Decisions behind this roadmap

Taken on 4 November 2026:

1. **Local by default.** A third-party API is an explicit choice per project and per role, with a receipt.
2. **No sharing of API keys in the swarm.** The swarm shares open models, within trusted circles first.
3. **Standard formats:** Agent Skills (`SKILL.md`) for skills, MCP for tools.
4. **Projects** go in `Documents/Swarmbly/<Project>`, with a warning for cloud-synced folders.
5. **Trusted circles come before the open internet network.**

---

## Español

### Contenido

1. [De la idea a hoy](#de-la-idea-a-hoy)
2. [Dónde está el proyecto](#dónde-está-el-proyecto)
3. [El camino a una red pública con voluntarios](#el-camino-a-una-red-pública-con-voluntarios)
4. [Programa de voluntarios](#programa-de-voluntarios)
5. [Líneas de trabajo paralelas](#líneas-de-trabajo-paralelas)
6. [Decisiones detrás de esta hoja de ruta](#decisiones-detrás-de-esta-hoja-de-ruta)

### De la idea a hoy

```mermaid
flowchart LR
  A["<b>ago 2026</b><br/>idea y protocolo<br/>whitepaper v1, repo, DOI"] --> B["<b>ago–sep</b><br/>medir con<br/>modelos reales"]
  B --> C["<b>sep</b><br/>dónde gana<br/>fragmentar · whitepaper v2"]
  C --> D["<b>oct</b><br/>memoria privada<br/>(LCE)"]
  D --> E["<b>oct</b><br/>app de escritorio<br/>y enjambre LAN"]
  E --> F["<b>oct</b><br/>un repositorio,<br/>un instalador (3.0)"]
  F --> G["<b>nov</b><br/>revisión: destinos,<br/>proyectos, agentes"]
```

| Etapa | Cuándo | Qué se construyó | Qué se aprendió |
|---|---|---|---|
| **1 · Idea y protocolo** | Agosto de 2026 | La pregunta era si la IA podía correr en hardware compartido por sus usuarios, como un torrent. Los sistemas existentes (Petals) reparten **el modelo**, así que cada token cruza la red y el nodo más lento marca el ritmo. La respuesta que se propone aquí reparte **el problema**, con el vocabulario del ensamblaje genómico por shotgun (lecturas, solapamientos, contigs, consenso). El proyecto nació como GenoNet AI y pasó a llamarse Swarmbly. Primeros productos: whitepaper v1 y especificación v0.2, implementación de referencia, banco de medición (V0), repositorio público (15 de agosto) y DOI en Zenodo para el software ([10.5281/zenodo.21956743](https://doi.org/10.5281/zenodo.21956743)) y el whitepaper ([10.5281/zenodo.21957088](https://doi.org/10.5281/zenodo.21957088)) | Publicación defensiva: el diseño queda fechado, público y habilitante. Las corridas simuladas validan el instrumento, no la idea |
| **2 · Medir con modelos reales** | 23 de agosto – 5 de septiembre | Campañas con varias familias de modelos, preregistros, e informes de incidentes y posmortem, publicados aunque fueran en contra del diseño | El acuerdo entre réplicas **no** predice el acierto (AUC 0,507): se retiró el mapa de confianza. La composición distribuida perdió frente a un modelo solo. No se cumplió el criterio del impuesto de coherencia |
| **3 · Dónde gana fragmentar** | 21–29 de septiembre | Curva L (el tamaño del fragmento como variable), campaña con presupuesto igualado (473 corridas), whitepaper v2 ([10.5281/zenodo.23031305](https://doi.org/10.5281/zenodo.23031305)), versión v2 | **Extraer con modelos pequeños y agregar con código: +46,9 puntos** sobre el modelo solo. Es el resultado más sólido, y orienta el diseño hacia la búsqueda, la extracción y la verificación, no hacia la redacción |
| **4 · Memoria privada (LCE)** | 4–10 de octubre | Extensión Cognitiva Local: whitepaper y especificación 0.1 ([10.5281/zenodo.23150478](https://doi.org/10.5281/zenodo.23150478)), corridas preregistradas, v0.1.0 y v0.1.1 | La memoria local ayuda (+0,500 [0,420; 0,578]). La wiki anclada **pierde** frente a la recuperación simple sobre los documentos del usuario (−0,146), así que pasó a ser capa de gobierno. Los errores se correlacionan entre familias de modelos |
| **5 · App y enjambre LAN** | 11–25 de octubre | SwarmblyApp: chat local y P2P real en LAN (TLS 1.3, Ed25519, mDNS), validado con 2 a 5 máquinas. La v0.2.0 ([10.5281/zenodo.23322639](https://doi.org/10.5281/zenodo.23322639)) añadió la configuración guiada. Después llegaron el voto por ítem y el planificador de composición, la evidencia pública (Wikidata, Wikipedia, PubMed, SearXNG), la memoria local en el chat, la recuperación híbrida y una red heterogénea de 4–5 máquinas con enrutamiento por capacidad y velocidad | La evidencia por ítem corrige lo que los modelos pequeños no saben (estado UICN 8/8 frente a cerca de 1/8). La red sobrevive a la caída de su nodo mayor. Una prueba abierta mostró que una petición personal podía salir del equipo y redactarse sin datos: ahora lo personal se queda en local |
| **6 · Un repositorio, un instalador** | 25–28 de octubre | Swarmbly AI 3.0.0 ([10.5281/zenodo.23650763](https://doi.org/10.5281/zenodo.23650763)): SwarmblyCore, SwarmblyLCE y SwarmblyApp en una distribución, un instalador interactivo para tres sistemas y la documentación del conjunto | Lo medido procede del material de una sola persona; hace falta un banco reservado antes de llamar general a cualquier cambio |
| **7 · Revisión de las próximas ideas** | 4 de noviembre | Una revisión del código y de las propuestas de agentes, una app más completa, proyectos, herramientas y plantillas. Las decisiones están [al final](#decisiones-detrás-de-esta-hoja-de-ruta) | Una API de terceros configurada recibía pasajes privados en la ruta «local». Controlar adónde va cada dato es previo a cualquier funcionalidad nueva. Se añadió una distribución Docker para que más personas puedan probar la app |
| **8 · Destinos y un banco sellado** | 5–7 de noviembre | Swarmbly AI 3.0.1 ([notas](releases/v3.0.1.md#español)): una política de salida antes de cada llamada, un recibo de privacidad con cada respuesta, claves API en el llavero, una imagen Docker. Dos bancos sellados escritos por el mantenedor, corridos a ciegas por un arnés y puntuados por un juez aislado (κ = 0,885 frente a una revisión humana a ciegas) | No salió nada prohibido en 17/17 casos de datos personales; el recibo de la app coincidió con la red en 23/24; la composición sigue débil (0/7 superan), lo que fija la prioridad de 3.2 |
| **9 · Proyectos** | 7–9 de noviembre | Swarmbly AI 3.1.0 ([notas](releases/v3.1.0.md#español)): proyectos, citas al párrafo, memoria con el sí del usuario, búsqueda en línea aprobada con términos revisados como conceptos, consentimiento por pregunta, frases sin fuente marcadas. Pruebas diarias del mantenedor y rondas automáticas en su computadora; dos mediciones con los bancos sellados, la primera diagnosticada con una batería abierta ficticia | No salió nada prohibido en 24/24 casos y el recibo coincidió con la red en 24/24; subieron las afirmaciones respaldadas por citas; ninguna composición aprueba aún (3.2). Criterio de salida pendiente: que 3–5 personas no técnicas entiendan el recibo |

### Dónde está el proyecto

| Funciona, medido | Todavía no, o refutado |
|---|---|
| Carriles de privacidad; lo personal se queda en local; evidencia enviada solo por nombre; se controla adónde va cada llamada, con un recibo de privacidad por respuesta (3.0.1); proyectos, consentimiento por pregunta, memoria con el sí del usuario (3.1) | Composición fundamentada; el recibo probado con personas no técnicas |
| Enjambre LAN: autenticación, coberturas, respaldo local, velocidad aprendida | Enjambres por internet; sin herramientas (MCP) ni habilidades |
| Lotes con evidencia; extracción con agregación por código | Redacción larga distribuida; criterio del impuesto de coherencia |
| Memoria local sobre texto, Word, HTML y PDF | Composición fundamentada (hoja de datos, tablas por código, verificador) |
| Instalador para tres sistemas; imagen Docker; bancos de preguntas sellados, una corrida por versión | Probadores ajenos al proyecto; un segundo modelo en los bancos |

### El camino a una red pública con voluntarios

Cada versión puede demostrarse funcionando por sí sola. Los voluntarios entran en círculos crecientes: primero personas que conoce el mantenedor, después círculos por invitación, después el público.

```mermaid
flowchart LR
  V1["<b>3.0.1</b><br/>destinos<br/>+ Docker"] --> V2["<b>3.1</b><br/>proyectos y<br/>recibo de privacidad"]
  V2 --> V3["<b>3.2</b><br/>proveedores por papel<br/>y recetas"]
  V3 --> V4["<b>3.3</b><br/>herramientas: MCP<br/>y habilidades"]
  V4 --> V5["<b>3.4</b><br/>equipos y círculos<br/>de confianza · beta privada"]
  V5 --> V6["<b>3.5</b><br/>red pública<br/>· beta pública"]
  V6 --> V7["<b>4.0</b><br/>protocolo 1.0<br/>· versión pública"]
  V7 -.-> V8["<b>después</b><br/>jerarquía de agentes,<br/>LCE C3–C4"]
  style V5 fill:#2a78d622,stroke:#2a78d6
  style V6 fill:#2a78d622,stroke:#2a78d6
```

| Versión | Contenido | Criterios de salida (objetivos) |
|---|---|---|
| **3.0.1 — Destinos** | <ul><li>Cada proveedor de modelos queda marcado como local, de mi red o de terceros, comprobado a partir de su dirección.</li><li>Una política de salida se aplica antes de cada llamada: respuesta, expansión de consultas, embeddings, ensamblaje, worker, reintentos y respaldo.</li><li>Un nodo nunca sirve al enjambre a través de una API de terceros.</li><li>Las respuestas registran dónde se calcularon de verdad.</li><li>Las claves API pasan al llavero del sistema.</li><li>Distribución Docker.</li></ul> | Una prueba de fuga sintética falla si algún camino envía pasajes privados, o fragmentos de otros nodos, a un destino no autorizado |
| **3.1 — Proyectos** | <ul><li>Proyectos con carpeta propia (por defecto `Documentos/Swarmbly/<Proyecto>`, con aviso si está sincronizada en la nube).</li><li>Memoria de proyecto separada de la memoria personal.</li><li>Chats guardados en la carpeta.</li><li>Exportar y restaurar como paquete `.swarmbly` con hashes y sin secretos.</li><li>**Recibo de privacidad** por respuesta: qué salió, para quién y por qué.</li><li>C1 movida a SwarmblyLCE.</li></ul> | <ul><li>Dos proyectos quedan aislados.</li><li>Una restauración en otra computadora y otro sistema conserva chats, fuentes y citas.</li><li>3–5 personas no técnicas entienden el recibo</li></ul> |
| **3.2 — Proveedores y recetas** | <ul><li>Varios proveedores (locales, compatibles con OpenAI, Anthropic) asignados **por papel**: planificador, extractor, redactor, verificador, embeddings. Un tercero es una elección explícita por proyecto y por papel.</li><li>Razonamiento acotado por papel.</li><li>Cuatro recetas de referencia, ejecutadas como flujos en código: *pregunta a tus documentos*, *compara documentos en una tabla*, *investiga con fuentes públicas*, *procesa una lista en el enjambre*.</li><li>Composición fundamentada, sobre lo que ya tiene 3.1 (citas C1, etiquetas, la medida de anclaje): un inventario local de los requisitos de la petición; un registro de hechos admitidos con sus citas `doc:`, con valores y unidades comprobados por código; una matriz requisito ↔ evidencia; un compositor que solo escribe con hechos admitidos y arma las tablas por código; un auditor de afirmaciones (primero determinista, con un modelo donde compense) y como máximo una reparación acotada, desactivada por defecto. Todo local, con interruptores, medido paso a paso (F0 = 3.1 y luego cada añadido).</li><li>Una batería de desarrollo abierta, separada de los bancos sellados, para S1/S2/S3, seguimientos, contradicciones, consentimiento, aislamiento e inyección de instrucciones.</li><li>El runtime de agentes nace en SwarmblyCore.</li><li>Banco v2 con conjuntos reservados.</li></ul> | <ul><li>Las mismas recetas funcionan con un modelo local y con una API.</li><li>Conjuntos reservados medidos y publicados.</li><li>Cero envíos no autorizados</li></ul> |
| **3.3 — Herramientas** | <ul><li>Un único intermediario de herramientas.</li><li>Cliente MCP: servidores locales aprobados uno a uno; los remotos se muestran como terceros.</li><li>Habilidades en el formato abierto Agent Skills (`SKILL.md`), al principio solo instrucciones.</li><li>Importar nunca ejecuta nada.</li><li>Búsqueda de autor con consentimiento (ORCID, OpenAlex, PubMed).</li></ul> | <ul><li>Los permisos efectivos son iguales a los declarados.</li><li>Una página con instrucciones no puede ampliarlos</li></ul> |
| **3.4 — Equipos y círculos de confianza · beta privada** | <ul><li>Los nodos anuncian papeles: búsqueda, modelo grande, razonador, corpus.</li><li>El mismo equipo funciona en uno o varios nodos.</li><li>**Círculos de confianza:** enjambres pequeños por invitación (código o QR) que funcionan también fuera de la LAN, con direcciones directas o una red superpuesta.</li><li>Créditos de reciprocidad no transferibles.</li><li>Instaladores firmados.</li><li>**20–50 voluntarios** en 3–5 círculos.</li></ul> | <ul><li>Equipo frente a ejecución local equivalente, medido.</li><li>La caída de un nodo deja resultados parciales honestos.</li><li>≥ 90 % de instalaciones exitosas.</li><li>Ningún error grave abierto durante dos semanas</li></ul> |
| **3.5 — Red pública · beta pública** | <ul><li>Encuentro y relevo de nodos; travesía de NAT.</li><li>Reputación, límites y protección contra abuso.</li><li>Protocolo 1.0-rc con pruebas de conformidad.</li><li>Especificación LCE 0.3.</li><li>Revisión externa de privacidad.</li><li>Actualizaciones automáticas.</li><li>Registro abierto de voluntarios.</li></ul> | <ul><li>Ningún hallazgo crítico.</li><li>Un nodo de terceros pasa la conformidad.</li><li>Prueba de fugas y conjuntos reservados sin regresión en la red pública</li></ul> |
| **4.0 — Protocolo 1.0 · versión pública** | <ul><li>Protocolo congelado, con negociación de capacidades, delegación y destinos de terceros decididos.</li><li>Política de versiones.</li><li>Gobernanza en marcha (Verein suiza).</li></ul> | Criterios de la beta pública sostenidos durante dos versiones |
| **Después** | <ul><li>**Jerarquía de SwarmblyAgents:** un nivel de delegación, que se conserva solo si un experimento con conjunto reservado muestra que supera al equipo plano.</li><li>LCE C3–C4.</li><li>Más incentivos para compartir.</li></ul> | Cada uno empieza con un documento de diseño y un experimento preregistrado |

**Fuera de alcance por ahora:**

- compartir claves API a través del enjambre;
- ejecutar scripts de habilidades o arrancar servidores MCP automáticamente;
- delegación de más de un nivel;
- llamar «optimizada» a una receta sin medición;
- un token transferible (ver [`GOVERNANCE.md`](../GOVERNANCE.md)).

### Programa de voluntarios

| Fase | Quiénes | Qué hacen los voluntarios | Qué reciben |
|---|---|---|---|
| Alfa (3.1–3.3) | Personas que conoce el mantenedor, 5–10 | Instalar (nativo o Docker), usar las recetas, enviar informes locales si quieren | Acceso temprano; sus hallazgos dan forma a la siguiente versión |
| Beta privada (3.4) | 3–5 círculos invitados, 20–50 personas | Compartir sus computadoras dentro de su círculo; probar equipos y lotes | Un enjambre propio; créditos de reciprocidad |
| Beta pública (3.5) | Cualquiera | Correr un nodo en la red pública, informar de problemas | Acceso libre al cómputo comunitario |

Nunca se recoge telemetría. Los informes son archivos que el usuario decide enviar. Las opiniones llegan por issues de GitHub y por el canal privado de seguridad ([`SECURITY.md`](../SECURITY.md)).

### Líneas de trabajo paralelas

| Línea | Contenido |
|---|---|
| Evaluación | Banco v2: conjuntos de desarrollo y reservados, una segunda persona ficticia, composición abierta con rúbrica, lotes de red en dominios nuevos. Los reservados se corren una vez por versión |
| Investigación | Experimentos preregistrados: razonamiento por papel; agente único → equipo plano → modelos especializados → distribuido → jerarquía |
| Documentación y comunidad | Guías bilingües, guía para voluntarios, guía para contribuir, un artículo corto de resultados honestos |
| Gobernanza y financiación | Verein suiza y después Stiftung; fondos de sostenibilidad; [Buy Me a Coffee](https://buymeacoffee.com/swarmbly). El apoyo nunca compra influencia |

### Decisiones detrás de esta hoja de ruta

Tomadas el 4 de noviembre de 2026:

1. **Local por defecto.** Una API de terceros es una elección explícita por proyecto y por papel, con recibo.
2. **No se comparten claves API en el enjambre.** El enjambre comparte modelos abiertos, primero dentro de círculos de confianza.
3. **Formatos estándar:** Agent Skills (`SKILL.md`) para habilidades y MCP para herramientas.
4. **Los proyectos** van en `Documentos/Swarmbly/<Proyecto>`, con aviso si la carpeta está sincronizada en la nube.
5. **Los círculos de confianza van antes que la red abierta por internet.**
