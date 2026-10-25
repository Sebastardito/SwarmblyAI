---
status: current
lang: es+en
---
# Swarmbly AI — Bibliografía Anotada Maestra / Master Annotated Bibliography

**Fecha de compilación / Compile date: 2026-08-12.**

## Alcance / Scope

This document is the consolidated, citable reference base for the **Swarmbly AI** project: a proposed decentralized peer-to-peer AI inference protocol in which **prompts — not model weights — are split into micro-prompts**, dispatched to volunteer nodes, and reassembled locally by a small language model, under an explicit analogy to whole-genome shotgun sequencing and assembly.

It merges four independent research dossiers compiled in August 2026:

1. `raw_p2p.md` — decentralized / P2P / volunteer-compute LLM inference and training; Bittensor; compute marketplaces; verifiable inference; network reality.
2. `raw_decomposition.md` — Skeleton-of-Thought and prompt-level decomposition; parallel decoding; multi-agent failure modes; long-context and merging; embeddings and cosine similarity.
3. `raw_genomics.md` — genome assembly theory (Lander–Waterman, OLC, De Bruijn, scaffolding, misassembly) and the privacy of fragmented distributed compute (SMPC, FHE, TEE, de-anonymization, embedding inversion, Sybil, BOINC).
4. `raw_governance.md` — AGPL and licensing strategy, defensive publication / prior art, Swiss foundation structures, grant funding, tokens under MiCA/FINMA, and AI energy/water/carbon evidence.

Nothing has been invented. Every number, URL, arXiv ID, DOI and verification caveat present in the source dossiers has been carried forward. Where a source dossier said "I could not verify this", that statement is preserved verbatim in spirit and flagged below.

## Leyenda de verificación / Verification legend

| Marca | Significado |
|---|---|
| *(sin marca)* | Verified in the source dossier: the arXiv ID / DOI / number was fetched from the primary source page. Safe to cite. |
| ⚠️ | Partially verified, or a caveat attaches to the number, boundary, methodology or author list. Re-check before publishing. |
| `[UNVERIFIED]` | The dossier explicitly failed to verify this item or figure. **Do not cite the flagged number without an independent fetch.** |
| `[SECONDARY]` | Sourced from press, a vendor blog, an aggregator or a corporate-services firm rather than a primary document. |
| `[PARTIAL]` | Entry exists and is real, but a specific field (date, author list, numeric result, article numbering) could not be extracted. |
| `[PARAPHRASE]` | Wording is a paraphrase, not verbatim, because the canonical source blocked automated fetching. |
| ⭐ | Load-bearing citation: an entry that alone can decide an argument for or against the Swarmbly thesis. |

## Índice / Table of Contents

1. **[P2P]** — Inferencia y entrenamiento descentralizado P2P · `P2P-01 … P2P-49`
2. **[NET]** — Realidad de red: ancho de banda, latencia, interconexión · `NET-01 … NET-06`
3. **[VER]** — Verificación de cómputo no confiable: TOPLOC, zkML, TEE · `VER-01 … VER-14`
4. **[DEC]** — Descomposición de prompts, decodificación paralela, multi-agente, fusión · `DEC-01 … DEC-52`
5. **[GEN]** — Teoría de ensamblado genómico y su transferencia a texto · `GEN-01 … GEN-29`
6. **[PRIV]** — Privacidad: MPC, FHE, de-anonimización, inversión de prompts y embeddings · `PRIV-01 … PRIV-38`
7. **[VOL]** — Cómputo voluntario, Sybil, reputación, BAR, churn · `VOL-01 … VOL-08`
8. **[GOV]** — Licencias, propiedad intelectual y arte previo · `GOV-01 … GOV-21`
9. **[FND]** — Estructura de fundación y financiación · `FND-01 … FND-23`
10. **[ENV]** — Energía, agua y el argumento de sostenibilidad · `ENV-01 … ENV-19`
11. **Lagunas de la literatura / Open gaps**

---

# 1. [P2P] — Inferencia y entrenamiento descentralizado P2P

## 1.1 Linaje Petals / Hivemind / BigScience

**[P2P-01] — Petals: Collaborative Inference and Fine-tuning of Large Models.** Borzunov, Baranchuk, Dettmers, Ryabinin, Belkada, Chumachenko, Samygin, Raffel. ACL 2023 (System Demonstrations). arXiv:2209.01188. https://arxiv.org/abs/2209.01188 · https://aclanthology.org/2023.acl-demo.54/
BitTorrent-style pipeline parallelism over the open internet: each volunteer serves a contiguous block of transformer layers, clients keep embeddings locally and route activations through a chain of servers. This is the canonical prior art for decentralized LLM inference, and it splits the *model*, meaning every generated token requires a full WAN round trip through the pipeline.
*Key figures:* BLOOM-176B served on consumer GPUs at **≈1 step/sec** for interactive generation; claimed **up to 10× faster than offloading**.
*Relevancia Swarmbly:* Es el sistema de referencia que Swarmbly explícitamente **no** replica, y por tanto el punto de partida obligatorio para justificar por qué mover prompts en lugar de activaciones elimina la cadena de latencia token a token.

**[P2P-02] ⭐ — Distributed Inference and Fine-tuning of Large Language Models Over The Internet.** Borzunov, Ryabinin, Chumachenko, Baranchuk, Dettmers, Belkada, Samygin, Raffel. arXiv:2312.08361 (Dec 2023). https://arxiv.org/html/2312.08361
The full-length Petals paper containing the real measurements: a fault-tolerant inference algorithm plus a load-balancing protocol, benchmarked both in controlled network conditions and on a real geodistributed swarm. It isolates, better than any other published work, exactly how much throughput a token-serial pipeline loses to WAN latency.
*Key figures:* Llama-2-70B on 3×T4: **2.29 steps/s** at 1 Gbit/s & <5 ms RTT → **1.57 steps/s** at 100 Mbit/s & 100 ms RTT (~31% loss purely from network). BLOOM-176B on 3×A100: **1.71 → 1.23 steps/s** under the same degradation. Offloading baselines: **0.139 steps/s** (Llama-2), **0.0495 steps/s** (BLOOM). Parallel forward (64×128 batch): Llama-2 **155.1 tok/s** at 1 Gbit/s vs **128.7 tok/s** at 100 Mbit/s + 100 ms RTT; offloading **18.0 tok/s**. Real geodistributed swarm of **14 heterogeneous servers across continents: 0.83 steps/s, 32.6 tok/s** (128-token batch), **179.4 tok/s** (64×128 batch).
*Relevancia Swarmbly:* Es la referencia cuantitativa individual más útil del proyecto: demuestra que el paso hacia adelante por lotes degrada mucho menos que la decodificación secuencial bajo 100 ms de RTT, que es precisamente el argumento a favor del paralelismo a nivel de prompt.

**[P2P-03] — Petals repository (bigscience-workshop/petals).** https://github.com/bigscience-workshop/petals
The reference implementation and its operational reality. Supports Llama 3.1 405B, Mixtral 8x22B, Falcon and BLOOM, but the last tagged release is **v2.2.0 (Sept 2023)** — the project is effectively dormant. The README documents an explicit privacy caveat: *"Your data will be processed with the help of other people in the public swarm"*, with private swarms offered as the only mitigation.
*Key figures:* README claims **up to 6 tok/s for Llama-2-70B** and **up to 4 tok/s for Falcon-180B** at single-batch. Last release **v2.2.0, Sept 2023**.
*Relevancia Swarmbly:* La advertencia de privacidad del README es exactamente el problema que Swarmbly hereda — el nodo voluntario ve el texto en claro — y el estancamiento del proyecto es en sí mismo un dato sobre el coste operativo de mantener un enjambre público.

**[P2P-04] — SWARM Parallelism: Training Large Models Can Be Surprisingly Communication-Efficient.** Ryabinin, Dettmers, Diskin, Borzunov. ICML 2023. arXiv:2301.11913 (v1 Jan 2023, v2 Jun 2023). https://arxiv.org/abs/2301.11913
Builds temporary randomized pipelines between unreliable nodes and rebalances them on failure, rather than assuming a fixed topology. The design is explicitly targeted at preemptible, cheap, poorly-connected hardware.
*Key figures:* Trained a **1B-shared-parameter model (~13B before sharing)** on **preemptible T4s with <200 Mb/s** interconnect.
*Relevancia Swarmbly:* Su "rebalanceo aleatorizado ante fallos" es el modelo mental correcto para el churn de voluntarios y puede reutilizarse tal cual, descartando el pipeline.

**[P2P-05] — Distributed Deep Learning in Open Collaborations (DeDLOC / Hivemind).** Diskin, Bukhtiyarov, Ryabinin, Saulnier, Lhoest, Sinitsin, Popov, Pyrkin, Kashirin, Borzunov, Villanova del Moral, Mazur, Kobelev, Jernite, Wolf, Pekhimenko. NeurIPS 2021. arXiv:2106.10207. https://arxiv.org/abs/2106.10207 · https://github.com/yandex-research/DeDLOC
Adaptive averaging for volunteer devices with high latency and asymmetric bandwidth; the origin of the Hivemind DHT stack used for peer discovery across this whole family of systems.
*Key figures:* **40 volunteers** collaboratively pretrained ALBERT (sahajBERT) and SwAV, "comparable to traditional setups at a fraction of the cost."
*Relevancia Swarmbly:* Establece que ~40 voluntarios heterogéneos es un tamaño de cohorte viable, y aporta la pila DHT que Swarmbly probablemente reutilizaría para descubrimiento de pares.

## 1.2 Bittensor / TAO

**[P2P-06] — BitTensor: A Peer-to-Peer Intelligence Market.** Rao, Steeves, Shaabana, Attevelt, McAteer. arXiv:2003.03917 (listed date Nov 10, 2021). https://arxiv.org/abs/2003.03917
The original formulation of a market in which peers rank each other by training networks that learn neighbours' value, with rewards accruing on a ledger.
*Key figures:* Connectivity-based regularization "exponentially rewards trusted peers, making the system resistant to collusion of **up to 50 percent** of the network weight."
*Relevancia Swarmbly:* Es el enunciado original del problema de puntuación entre pares que Swarmbly enfrentará si paga a voluntarios por prompt.

**[P2P-07] — Bittensor whitepaper — "A Peer-to-Peer Intelligence Market" (Yuma Rao).** https://www.bittensor.com/whitepaper
The concrete, citable statement of stake-weighted scoring mechanics, including the consensus function and the incentive split.
*Key figures:* Consensus **C = σ(ρ(TᵀS − κ))** with temperature **ρ = 10** and shift **κ = 0.5**; incentive **I = R · C**; incentive gradient at the inflection point **δI/δS = 5/2**; suggested **50/50** bond/direct-reward split.
*Relevancia Swarmbly:* Aporta la formulación matemática concreta del scoring ponderado por stake, el mecanismo que haría falta si la calidad de salida del voluntario no fuera verificable.

**[P2P-08] ⚠️ — Yuma Consensus (taostats documentation).** https://docs.taostats.io/docs/consensus
Validators set weights on miners; the consensus engine converts weights into emissions and clips validators whose weights deviate from the stake-weighted peer view, also lowering their validator trust and hence their dividends.
*Key figures:* `[UNVERIFIED]` The widely quoted **41% miner / 41% validator / 18% subnet-owner** emission split and the commonly cited **360-block tempo** could **not** be verified from primary docs (`docs.learnbittensor.org` 302-redirected during research). **Do not cite these figures without a direct check.**
*Relevancia Swarmbly:* Documenta el mecanismo de recorte (clipping) de validadores desviados, útil como referencia de diseño, pero con cifras de reparto que Swarmbly no debe citar sin verificación.

**[P2P-09] — Bittensor docs — role model.** https://www.bittensor.com/docs
*Key figures (verbatim):* *"Miners produce the commodity, validators score the miners, subnet creators define the incentive mechanism, and stakers back validators with TAO."*
*Relevancia Swarmbly:* Define la separación de roles minero/validador/creador/staker que Swarmbly puede adoptar o rechazar explícitamente en su diseño de gobernanza de nodos.

**[P2P-10] ⭐ — Bittensor Protocol: The Bitcoin in Decentralized Artificial Intelligence? A Critical and Empirical Analysis.** Lui, Sun. arXiv:2507.02951 (Jun 2025). https://arxiv.org/abs/2507.02951
Empirical study across **all 64 active subnets**, robust across daily, weekly and monthly windows. It finds "considerable concentration in both stake and rewards", and that rewards are "overwhelmingly driven by stake" rather than by service quality.
*Key figures:* All **64 active subnets** analysed; proposes a **stake cap at the 88th percentile** to raise the median coalition size needed for a 51% attack. ⚠️ The abstract gives **no Gini coefficient** — none was found.
*Relevancia Swarmbly:* Es la crítica definitiva a citar: el scoring ponderado por stake degenera en "se paga al capital, no a la contribución", una advertencia directa contra copiar el diseño de incentivos de TAO.

**[P2P-11] — IOTA: Incentivised Orchestrated Training Architecture.** Quinque, Aboudib, Fonau, Lopez Portillo Alcocer, McCrindle, Cruz (Macrocosmos AI). arXiv:2507.17766 (2025). https://arxiv.org/html/2507.17766v1
Data- and pipeline-parallel pretraining over Bittensor SN9 with an orchestrator, layer-owning miners, and validators that *recompute* miner work and compare via cosine similarity. Uses CLASP (Shapley-value contribution attribution).
*Key figures:* Activation compression **up to 128×**; butterfly all-reduce with **O(1)** bandwidth per participant; predecessor SN9 trained models up to **14B**. ⚠️ Authors label results **preliminary, pending production validation**.
*Relevancia Swarmbly:* CLASP/Shapley y el patrón "los validadores reproducen un subconjunto aleatorio del trabajo del minero" se transfieren limpiamente a la verificación de trabajo a nivel de prompt.

**[P2P-12] `[SECONDARY]` `[UNVERIFIED]` — Templar (Bittensor SN3) — Covenant-72B.** https://news.800.works/news/2026-03-20/bittensor-covenant-72b-decentralized-llm-pretraining/
Reported as a **72B-parameter** model trained on **~1.1T tokens** over permissionless commodity internet hardware, announced **March 10, 2026**, claimed "performance-competitive with LLaMA-2-70B".
*Key figures:* **72B params, ~1.1T tokens**. **No benchmark scores, participant counts, algorithm details or bandwidth figures were published in reachable sources — treat the entire claim as unverified.** Corroborating scale figure from Epoch AI (see `NET-01`): Templar's network measured at **9e17 FLOP/s**, ~**300× smaller** than a frontier datacenter.
*Relevancia Swarmbly:* Ejemplo de la clase de afirmación no verificable que abunda en este espacio; citarlo solo con la advertencia explícita, y usar la cifra de Epoch AI como contrapeso.

## 1.3 Mercados de cómputo — qué hace realmente cada uno

**[P2P-13] — Akash Network.** https://akash.network/docs/getting-started/intro-to-akash/bids-and-leases/
A Cosmos-SDK blockchain running a **reverse auction** for containerized compute: tenants publish a YAML/SDL deployment → an on-chain *order* → providers *bid* → the winning bid becomes a *lease*, paid **per block** out of an escrow account.
*Key figures:* No ML-specific orchestration, **no verification of computation**, no model sharding. Kubernetes-adjacent IaaS with crypto settlement.
*Relevancia Swarmbly:* Un lugar donde *alquilar* nodos, no un sistema que distribuya prompts; útil solo como capa de capacidad de reserva, nunca como arquitectura.

**[P2P-14] — Gensyn.** https://docs.gensyn.ai/products-and-research
The most research-heavy of the marketplaces: a custom Ethereum rollup for ML plus a genuine publication record. Products: **Verde** (refereed-delegation verification), **Judge** (verifiable evaluation), **SkipPipe**, **NoLoCo**, **CheckFree**, **RL Swarm** (peer models critique each other), and a public testnet.
*Key figures:* See `VER-02` (Verde/RepOps), `P2P-31` (NoLoCo), `P2P-32` (SkipPipe), `P2P-33` (CheckFree), `P2P-34` (HDEE) for the measured results.
*Relevancia Swarmbly:* Verde + RepOps es la respuesta más creíble publicada a "¿ejecutó realmente el voluntario el modelo que le pedí?", pregunta central para Swarmbly.

**[P2P-15] ⚠️ — Prime Intellect (protocol repo).** https://github.com/PrimeIntellect-ai/protocol
Compute exchange plus a real decentralized-training stack (PRIME, PRIME-RL, SHARDCAST, TOPLOC, prime-iroh). The protocol architecture is Ethereum smart contracts (economics) + a **discovery service** + an **orchestrator** + a **validator network doing random challenges** + containerized **worker nodes**.
*Key figures:* **The `PrimeIntellect-ai/protocol` repo was archived January 27, 2026** (last release v0.3.11, July 2025) — the permissionless protocol layer appears deprioritized relative to their centralized cluster work.
*Relevancia Swarmbly:* Su orquestador + validador de desafíos aleatorios + workers en contenedor es esencialmente la arquitectura de referencia para despachar tareas independientes a voluntarios no confiables; su archivado es una señal de coste operativo.

**[P2P-16] `[UNVERIFIED]` — io.net.** https://io.net/docs/
Solana-based GPU aggregator built on **Ray.io** clustering; the founders originally used Ray for quant trading with **50+ A100s** at **~$100K/month**. Sells "IO Cloud" clusters.
*Key figures:* **Authoritative current documentation on IO Worker internals, verification, or GPU counts could not be retrieved** — the docs URL redirected and the landing page was a company-origin story. **Any GPU-count claim you encounter is marketing.**
*Relevancia Swarmbly:* Ejemplo de mercado de alquiler sin verificación documentada; citarlo solo para mostrar la opacidad del sector.

**[P2P-17] — Nosana.** https://learn.nosana.com
Solana-based GPU marketplace targeting **AI inference jobs** specifically (not training). Providers stake **$NOS** and join the "Nosana Grid"; jobs, nodes, pools and rewards are Solana programs.
*Key figures:* **No verification mechanism is described in the public docs reachable during research.**
*Relevancia Swarmbly:* Confirma que incluso los mercados orientados a inferencia carecen de verificación publicada — un hueco competitivo que Swarmbly puede reclamar.

**[P2P-18] — Render Network.** https://rendernetwork.com/participate-compute-clients
Originally a decentralized **GPU rendering** network (proof-of-render, node tiers), expanded to general/AI compute via RNP-004 "Compute Clients" and RNP-019. Officially supports "machine learning training, inference, fine tuning, and generative AI imaging" via an API, but its provenance and tooling remain 3D-rendering-first.
*Key figures:* Governance proposals RNP-004 and RNP-019 are the formal expansion instruments.
*Relevancia Swarmbly:* Precedente de un protocolo de cómputo distribuido con prueba de trabajo específica del dominio (proof-of-render), modelo conceptual para una eventual "prueba de inferencia" de Swarmbly.

**[P2P-19] — Golem Network.** https://blog.golem.network/ai-gpu-roadmap-update/
The oldest requestor/provider marketplace of the group. Components: GPU Provider (VM+GPU rental), **golem-workers** (fine-tuning small models on single nodes), **Modelserve** (scalable inference endpoints, validated on Whisper / Stable Diffusion class models), and AI Provider GamerHash (proof-of-concept).
*Key figures:* GPU support reached **experimental availability in mid-2024** (beta with **67 users** from a 300+ waitlist). Roadmap post dated **July 23, 2024**; no newer authoritative update found.
*Relevancia Swarmbly:* El dato de **67 usuarios beta** tras años de operación es una calibración realista y sobria de la demanda voluntaria en este mercado.

> **Juicio de conjunto sobre los siete mercados (`P2P-13`…`P2P-19`):** Akash, io.net, Nosana, Render y Golem son **mercados de alquiler con liquidación en cripto** — no resuelven la inferencia distribuida, venden máquinas. Solo Gensyn y Prime Intellect hacen investigación real de sistemas de ML distribuido.

## 1.4 Entrenamiento descentralizado sobre interconexiones lentas

**[P2P-20] — DiLoCo: Distributed Low-Communication Training of Language Models.** Douillard, Feng, Rusu, Chhaparia, Donchev, Kuncoro, Ranzato, Szlam, Shen (Google DeepMind). arXiv:2311.08105 (Nov 14, 2023). https://arxiv.org/abs/2311.08105
A federated-averaging variant with an inner AdamW optimizer running many local steps and an outer Nesterov-momentum optimizer synchronizing rarely. Robust to non-IID worker data and to workers joining or leaving mid-run.
*Key figures:* On C4 with **8 workers**, matches fully synchronous optimization while **communicating 500× less**.
*Relevancia Swarmbly:* El factor **500×** es la vara de medir estándar para "cuánto se puede recortar el tráfico WAN", y la fuente del argumento de robustez frente al churn.

**[P2P-21] — OpenDiLoCo.** Jaghouar, Ong, Hagemann (Prime Intellect). arXiv:2407.07852 (Jul 10, 2024). https://arxiv.org/abs/2407.07852
Open replication of DiLoCo built on Hivemind, demonstrating the method outside a single lab's infrastructure.
*Key figures:* Trained across **2 continents / 3 countries** at **90–95% compute utilization**; scaled DiLoCo **3× larger** than the original; FP16 all-reduce with no measured degradation.
*Relevancia Swarmbly:* Prueba de que la utilización de cómputo del 90–95% es alcanzable en despliegues intercontinentales reales, un techo útil para las proyecciones de Swarmbly.

**[P2P-22] — Streaming DiLoCo with overlapping communication: Towards a Distributed Free Lunch.** Douillard, Donchev, Rush, Kale, Charles, Garrett, Teston, Lacey, McIlroy, Shen, Ramé, Szlam, Ranzato, Barham. arXiv:2501.18512 (Jan 30, 2025). https://arxiv.org/abs/2501.18512
Three changes to DiLoCo: synchronize parameter *subsets* in sequence to cut peak bandwidth, keep training while syncing to cut wall clock, and quantize exchanged data.
*Key figures:* **~100× (two orders of magnitude) bandwidth reduction** at billion-parameter scale.
*Relevancia Swarmbly:* Marca el estado del arte en compresión de comunicación para pesos/gradientes, es decir, el mejor caso del enfoque que Swarmbly evita por completo.

**[P2P-23] — INTELLECT-1 Technical Report.** Jaghouar, Ong, Basra, Obeid, Straube, Keiblinger, Bakouch, Atkins, Panahi, Goddard, Ryabinin, Hagemann. arXiv:2412.01152 (Dec 2, 2024). https://arxiv.org/abs/2412.01152
The first decentralized pretraining run at 10B scale with published operational statistics on utilization, node count and contributor count.
*Key figures:* **10B parameters, 1T tokens**; up to **14 concurrent nodes** across **3 continents**; **30 independent compute contributors**; **83–96% compute utilization**; **MFU 36.2–41.4%**; **400× bandwidth reduction** vs standard data-parallel.
*Relevancia Swarmbly:* Establece el orden de magnitud realista de contribuyentes (30) y nodos (14) en un proyecto descentralizado de alto perfil — cifras que Swarmbly debe usar al dimensionar su enjambre esperado.

**[P2P-24] ⭐ — INTELLECT-2: A Reasoning Model Trained Through Globally Decentralized Reinforcement Learning.** Prime Intellect Team et al. arXiv:2505.07291 (May 12, 2025). https://arxiv.org/abs/2505.07291 · https://www.primeintellect.ai/blog/intellect-2
A **32B** model (from QwQ-32B) trained by asynchronous RL over a permissionless swarm. Stack: **PRIME-RL** (async distributed RL), **TOPLOC** (verify rollouts from untrusted inference workers), **SHARDCAST** (broadcast policy weights to inference workers).
*Key figures:* **4×RTX 3090** suffices to contribute; **four-step asynchrony** tolerated without degradation; training tasks filtered to **≤75% solve rate**. ⚠️ Contributor and node counts were **not** disclosed in the blog or abstract.
*Relevancia Swarmbly:* Es el sistema existente más cercano a lo que Swarmbly quiere hacer — los rollouts de RL *son* prompts independientes despachados a voluntarios no confiables y verificados individualmente; PRIME-RL + TOPLOC es la plantilla directa.

**[P2P-25] ⭐ — INTELLECT-3 — the reality check.** https://www.primeintellect.ai/blog/intellect-3
A **106B-parameter MoE** derived from GLM-4.5-Air, SFT + large-scale RL, released **Nov 26, 2025**. Stack: PRIME-RL, Verifiers/Environments Hub (500+ tasks), Prime Sandboxes (sub-10s startup at high concurrency).
*Key figures:* Trained on **512 NVIDIA H200 GPUs across 64 interconnected nodes** over two months — **a centralized cluster, not a decentralized swarm.**
*Relevancia Swarmbly:* Es el dato más aleccionador de toda la bibliografía: el laboratorio líder en entrenamiento descentralizado usó un centro de datos convencional para su modelo insignia 2025–26; Swarmbly debe dimensionar sus ambiciones en consecuencia.

**[P2P-26] — DeMo: Decoupled Momentum Optimization (the DisTrO paper).** Peng, Chen, Su, Quesnelle, Kingma, Liu (Nous Research + collaborators). arXiv:2411.19870 (Nov 29, 2024; v2 Feb 6, 2026). https://arxiv.org/abs/2411.19870 · https://github.com/bloc97/DeMo
Decouples local momentum, applies an orthonormal transform plus top-k sparsification, and reuses the momentum buffer as error feedback.
*Key figures:* Per-step communication reduced **up to two orders of magnitude**; transmits **up to 85× less data per GPU than AdamW-DDP** at comparable loss; tested at **300M and 1B**.
*Relevancia Swarmbly:* Otra medida del techo de compresión de gradientes, útil para el argumento comparativo de que mover prompts (kilobytes) es estructuralmente distinto de comprimir tensores.

**[P2P-27] ⚠️ — Nous Research — Psyche Network.** https://nousresearch.com/the-next-phase-of-psyche
Decentralized training coordinated by **Solana smart contracts**, using DisTrO/DeMo. Trained **Consilience 40B** on testnet ("the largest distributed pre-training run ever" — their own claim); also training Hermes 4 on Seed-OSS-36B.
*Key figures:* **Consilience 40B**. ⚠️ **Token counts and contributor counts are not disclosed.** Post published Sept 29, 2025, modified Nov 24, 2025.
*Relevancia Swarmbly:* Precedente de coordinación on-chain (Solana) para trabajo de ML distribuido, relevante para el diseño de liquidación de créditos de Swarmbly, pero con métricas de participación opacas.

**[P2P-28] ⚠️ — Photon: Federated LLM Pre-Training.** Sani, Iacob, Cao, … Lane (Flower Labs / Cambridge CaMLSys). arXiv:2411.02908; MLSys 2025. https://arxiv.org/abs/2411.02908 · https://flower.ai/blog/2025-05-09-photon
Federated pretraining across clusters with dramatic reductions in communication volume and wall-clock time.
*Key figures:* **64×–512×** reduction in communication volume vs standard data-parallel; for a **7B** model communication time fell from **97.2 h to 0.1 h** (~1000× less data transferred) and wall-clock improved ~**35%** (95.6 h vs 147.9 h); a **13B** run achieved **>2× the throughput** of centralized DDP in a **~3 Gbps** cross-cluster setting; up to **20% higher** samples/sec; models **1.3B–13B**. ⚠️ The baseline assumed a "reasonably generous **10 Gbps**" link — this is cross-datacenter federated, **not** consumer-broadband scale.
*Relevancia Swarmbly:* Ejemplo canónico de la trampa de comparación: cifras espectaculares que dependen de enlaces de 3–10 Gbps, dos órdenes de magnitud por encima del uplink doméstico que Swarmbly asume.

**[P2P-29] ⚠️ — Subspace Networks: Scaling Decentralized Training with Communication-Efficient Model Parallelism** (formerly "Protocol Models"). Ramasinghe, Ajanthan, Avraham, Zuo, Long (Pluralis Research). arXiv:2506.01260 (Jun 2, 2025; **v3 Jul 9, 2026 — retitled**). https://arxiv.org/abs/2506.01260
Predefines a low-dimensional subspace confining activations and gradients, reconstructed in later layers, so that model-parallel training survives consumer-grade links.
*Key figures:* **up to 99% compression**; **up to 100×** communication-efficiency gain; matches datacenter model-parallel convergence at **80 Mbps** internet vs **100 Gbps** in-datacenter, at billion-parameter scale, with negligible memory/compute overhead. ⚠️ Cite the **current** title (Subspace Networks); "Protocol Models" refers to the v1/v2 title.
*Relevancia Swarmbly:* La comparación **80 Mbps vs 100 Gbps** es la cita más limpia para cuantificar la brecha que cualquier esquema tensor-paralelo debe superar.

**[P2P-30] ⚠️ `[PARTIAL]` — Unextractable Protocol Models: Collaborative Training and Inference without Weight Materialization.** Long, Hewa Koneputugodage, Ajanthan, Zuo, Avraham, Shevchenko, Mohaghegh Dolatabadi, Ramasinghe (Pluralis). **NeurIPS 2025 poster.** https://neurips.cc/virtual/2025/poster/118911 · https://openreview.net/forum?id=H8fscnm6Xx
Periodic time-varying transforms at participant boundaries make model shards mutually incompatible across time steps, so no participant can reconstruct the full weights; reports minimal degradation on small LMs with manageable overhead.
*Key figures:* Minimal degradation reported on small LMs. ⚠️ Search surfaced arXiv ID **2605.23464** but the abs page returned no machine-readable text; title/authors/venue confirmed via NeurIPS. **Verify the arXiv ID before citing it.**
*Relevancia Swarmbly:* Ataca la imagen especular del problema de Swarmbly — cómo dejar que los voluntarios computen sin entregarles el modelo — y por tanto es la mejor referencia para contrastar "ocultar los pesos" frente a "ocultar el prompt".

**[P2P-31] — NoLoCo: No-all-reduce Low Communication Training Method for Large Models.** Kolehmainen, Blagoev, Donaghy, Ersoy, Nies (Gensyn). arXiv:2506.10911 (Jun 12, 2025). https://arxiv.org/abs/2506.10911
Eliminates the global all-reduce entirely, synchronizing implicitly via a Nesterov-momentum variant that partially averages weights with **one randomly selected peer**.
*Key figures:* **125M–6.8B** parameters; converges up to **4% faster** than DiLoCo; synchronization **an order of magnitude faster** than DiLoCo for hundreds of accelerators training over the internet; no global blocking communication.
*Relevancia Swarmbly:* Demuestra que eliminar la sincronización global es viable y beneficioso — el mismo principio que Swarmbly lleva al extremo al no sincronizar nada entre nodos.

**[P2P-32] — SkipPipe: Partial and Reordered Pipelining Framework for Training LLMs in Heterogeneous Networks.** Blagoev, Chen, Ersoy (Gensyn). arXiv:2502.19913 (Feb 27, 2025). https://arxiv.org/abs/2502.19913
Allows stages of a pipeline to be skipped and reordered to accommodate heterogeneous and unreliable nodes.
*Key figures:* **up to 55%** reduction in training iteration time vs a full pipeline; **500M–8B** models on **up to 20 nodes**; running inference on **half** the model costs only **7% perplexity** increase.
*Relevancia Swarmbly:* El resultado de **7% de perplejidad por medio modelo** es un argumento potente de que la redundancia y el salto de capas son baratos, útil cuando algunos voluntarios sean lentos.

**[P2P-33] — CheckFree / "All is Not Lost: LLM Recovery without Checkpoints".** Blagoev, Ersoy, Chen (Gensyn). arXiv:2506.15461 (Jun 18, 2025; rev. Apr 4, 2026). https://arxiv.org/abs/2506.15461 · https://github.com/gensyn-ai/CheckFree
Recovers a failed pipeline stage by weighted averaging of neighbouring stages rather than by checkpointing or redundancy; CheckFree+ handles edge stages via out-of-order pipelining.
*Key figures:* **up to 12%** wall-clock convergence improvement over redundant computation at **5–10% failure rates**; LLaMa **124M–1.5B**.
*Relevancia Swarmbly:* Cuantifica el rango de tasas de fallo (5–10%) que la literatura considera normal en nodos no confiables, una entrada directa al modelo de churn de Swarmbly.

**[P2P-34] ⭐ — HDEE: Heterogeneous Domain Expert Ensemble.** Gensyn. arXiv:2502.19385 (Feb 2025). https://arxiv.org/abs/2502.19385 · https://blog.gensyn.ai/diverse-expert-ensembles-embarrassingly-parallel-llms-from-diverse-experts/ (Feb 25, 2025)
Independently trained domain experts of *differing sizes and training lengths*, matched to domain complexity, requiring **zero** inter-node synchronization. Gensyn explicitly frames this as "embarrassingly parallel LLMs".
*Key figures:* Lowest perplexity in **20 of 21 domains** vs a homogeneous baseline **at equal compute budget**.
*Relevancia Swarmbly:* Es el análogo del lado del entrenamiento de la tesis de Swarmbly y el argumento existente más fuerte de que la descomposición a nivel de tarea supera a la tensorial en la internet abierta.

**[P2P-35] — AC-SGD: Fine-tuning Language Models over Slow Networks using Activation Compression with Guarantees.** Wang, Yuan, Rimanic, He, Dao, Chen, Ré, Zhang. arXiv:2206.01299 (Jun 2022, rev. Mar 2023). https://arxiv.org/abs/2206.01299
Compresses the *change* in activations rather than activations themselves, with an O(1/√T) convergence guarantee.
*Key figures:* Activations to **2–4 bits**; **up to 4.3×** end-to-end speedup on slow networks, **4.9×** combined with gradient compression; up to **1.5B** parameters; no quality loss.
*Relevancia Swarmbly:* Referencia del coste mínimo alcanzable al mover activaciones, el contrafactual cuantitativo frente a mover texto.

**[P2P-36] — TAH-Quant: Effective Activation Quantization in Pipeline Parallelism over Slow Network.** He, Cao, He, Bai, Yuan, Yuan (HKUST / PKU). arXiv:2506.01352 (Jun 2025). https://arxiv.org/html/2506.01352v1
Tile-wise quantization plus entropy-guided adaptive bit allocation plus Hadamard outlier suppression.
*Key figures:* **3–4 bit** activations; **up to 4.3×** end-to-end speedup; no convergence degradation; **no extra memory overhead** (unlike AC-SGD, which must store prior activations).
*Relevancia Swarmbly:* Confirma que la cuantización de activaciones se ha estancado en torno a ~4× de aceleración, muy lejos de los 4–5 órdenes de magnitud de la brecha de red (`NET-06`).

## 1.5 Herramientas de sharding local / LAN

**[P2P-37] — exo (exo-explore/exo).** Apache 2.0. https://github.com/exo-explore/exo
Connects heterogeneous devices into one cluster with **topology-aware auto-parallelism**, choosing between **tensor parallelism** and **pipeline parallelism** from live device resources, network latency and bandwidth. MLX-based backend.
*Key figures:* Claims **1.8× on 2 devices, 3.2× on 4 devices** for tensor parallelism; runs Qwen3-235B (8-bit), DeepSeek v3.1 671B (8-bit), Kimi K2 Thinking (4-bit) on **4× M3 Ultra Mac Studio**; day-0 **RDMA over Thunderbolt 5**; **44.7k stars**, v1.0.71 (Apr 23, 2026), actively developed. *(The original `exo-explore/ex-exo` repo was archived Dec 17, 2025.)*
*Relevancia Swarmbly:* Sus aceleraciones dependen de enlaces de clase LAN o superiores (Thunderbolt 5, RDMA); no es un sistema WAN, que es exactamente el hueco que la división de prompts pretende llenar.

**[P2P-38] ⭐ — llama.cpp RPC backend (`tools/rpc`).** https://github.com/ggml-org/llama.cpp/blob/master/tools/rpc/README.md
Exposes remote devices to a host `llama-cli`; weights and KV cache are split across local and remote devices proportional to memory, adjustable via `--tensor-split`. Optional local caching on RPC servers; RDMA transport on Linux where hardware allows.
*Key figures (verbatim from the README):* *"This example and the RPC backend are currently in a proof-of-concept development stage. As such, the functionality is fragile and insecure. **Never run the RPC server on an open network or in a sensitive environment!**"*
*Relevancia Swarmbly:* La advertencia es decisiva: la vía dominante de sharding local **no puede** exponerse a voluntarios por internet, lo que deja el espacio libre para una arquitectura a nivel de prompt.

**[P2P-39] ⚠️ — distributed-llama (b4rtaz).** https://github.com/b4rtaz/distributed-llama
**Tensor parallelism** with RAM split across nodes; Linux/macOS/Windows, ARM and x86_64 AVX2, Raspberry Pi; models 0.6B–405B.
*Key figures:* Requires **switched Ethernet**; node count must be a **power of 2** and is bounded by the model's KV head count. ⚠️ Benchmarks live in GitHub Discussions rather than the README — **specific tok/s figures could not be verified.**
*Relevancia Swarmbly:* Otra confirmación de que el sharding tensorial impone requisitos de red conmutada local, inviables para voluntarios residenciales.

**[P2P-40] ⚠️ — Cake (evilsocket/cake).** https://github.com/evilsocket/cake
Rust multimodal inference server that shards transformer blocks across a heterogeneous cluster with **zero-config mDNS discovery**, proportional to VRAM/compute. Workers need no pre-downloaded weights — the master streams tensors with **zstd compression + CRC32**. Backends: CUDA, Metal, Vulkan, CPU; iOS/Android/macOS/Linux/Windows; 15 text model families, 6 image (SD, FLUX), 2 TTS.
*Key figures:* ⚠️ **Explicitly experimental; no tagged releases; no published benchmarks.**
*Relevancia Swarmbly:* Interesante por el streaming de pesos bajo demanda (evita la predescarga en el nodo), técnica reutilizable si Swarmbly decide distribuir modelos pequeños a los voluntarios.

## 1.6 Paralelismo a nivel de tarea / petición sobre nodos heterogéneos o no confiables

> *Este es el corpus más delgado de los ocho temas: casi toda la literatura de inferencia descentralizada asume paralelismo de modelo o de pipeline. Lo que sigue es todo lo que opera genuinamente a granularidad de petición o tarea.*

**[P2P-41] ⚠️ — Parallax: Efficient LLM Inference Service over Decentralized Environment.** Tong, Jiang, Chen, Zhao, Lu, Qu, Yang, Ai, Yuan. arXiv:2509.26182 (Sep 30, 2025). https://arxiv.org/abs/2509.26182 · https://github.com/GradientHQ/parallax
Two-phase scheduler: (a) offline model allocation across heterogeneous GPUs jointly optimizing latency and throughput under memory and link-bandwidth constraints; (b) **request-time GPU pipeline selection** that stitches layers from different replicas into per-request execution chains. Evaluated **on real volunteer nodes**.
*Key figures:* "Consistently reduces latency and increases throughput relative to decentralized baselines" — ⚠️ **the abstract gives no specific percentages**; concrete figures could not be extracted.
*Relevancia Swarmbly:* El sistema publicado más cercano en cuanto a decisiones de enrutamiento por petición sobre un conjunto de voluntarios; su "selección de pipeline en tiempo de petición" es un híbrido entre la idea de Swarmbly y la de Petals.

**[P2P-42] ⭐ ⚠️ `[PARTIAL]` — WWW.Serve: Interconnecting Global LLM Services through Decentralization.** Wang, Xia, Chen, Chen (CMU). arXiv:2603.20661 (2026). https://arxiv.org/html/2603.20661v2
**Fully request-level, not model-parallel:** anonymous LLM servers route requests among themselves via **Proof-of-Stake-based routing** (selection probability proportional to staked credit), gossip-driven state sync, and a duel-and-judge quality evaluation that accrues credit to better hardware/models.
*Key figures:* **up to 1.5×** SLO attainment vs single-node; **27.6%** latency reduction; approaches or surpasses centralized scheduling; tolerates arbitrary node arrival/departure. ⚠️ The abs page would not yield authors/date/ID cleanly; title and authors came from the HTML version — **verify the arXiv ID.**
*Relevancia Swarmbly:* Es la coincidencia académica más próxima a "dividir prompts, no modelos, entre nodos no confiables", con un mecanismo de crédito/calidad sin confianza; es la primera lectura obligatoria del proyecto.

**[P2P-43] — Task Scheduling for Decentralized LLM Serving in Heterogeneous Networks.** Elden Ren. UC Berkeley EECS Tech Report EECS-2024-111 (May 16, 2024). https://www2.eecs.berkeley.edu/Pubs/TechRpts/2024/EECS-2024-111.html
Frames a DePIN for LLM inference over globally idle GPUs and proposes a heuristic scheduler optimizing **time per output token (TPOT)**.
*Key figures:* Uniformly lower TPOT than an integer-programming baseline **and** shorter scheduler execution time; demonstrates feasibility of consumer-grade GPUs for low-latency inference. Notably does not reference Petals.
*Relevancia Swarmbly:* Aporta la métrica de scheduling (TPOT) y evidencia de que las GPU de consumo pueden servir con baja latencia, base para el planificador de Swarmbly.

**[P2P-44] — Helix: Serving Large Language Models over Heterogeneous GPUs and Network via Max-Flow.** Mei, Zhuang, Miao, Yang, Jia, Vinayak (CMU). arXiv:2406.01566; **ASPLOS 2025**. https://arxiv.org/abs/2406.01566 · https://github.com/Thesys-lab/Helix-ASPLOS25
Formulates joint model placement plus request scheduling as **max-flow on a directed weighted graph**, solved with MILP.
*Key figures:* **up to 3.3×** throughput; **up to 66%** lower prompting latency; **up to 24%** lower decoding latency; clusters of **24–42 GPU nodes**.
*Relevancia Swarmbly:* La formulación max-flow es directamente reutilizable para asignar prompts a voluntarios bajo restricciones de ancho de banda y latencia en las aristas.

**[P2P-45] — HexGen: Generative Inference of Large Language Model over Heterogeneous Environment.** Jiang, Yan, Yao, Zhou, Chen, Yuan. arXiv:2311.11514; **ICML 2024**. https://arxiv.org/abs/2311.11514
Asymmetric partitioning combining tensor and pipeline parallelism, scheduled by constrained optimization across heterogeneous GPUs and datacenters.
*Key figures:* **up to 2.3× lower** latency deadlines and **up to 4× higher** request-rate tolerance at the same budget vs a homogeneous baseline; Llama-2-70B.
*Relevancia Swarmbly:* Cuantifica la ganancia de explotar la heterogeneidad (2.3×–4×), cifra de referencia para el planificador heterogéneo de Swarmbly.

**[P2P-46] ⚠️ — Demystifying Cost-Efficiency in LLM Serving over Heterogeneous GPUs.** Jiang, Fu, Yao, He, Miao, Klimovic, Cui, Yuan, Yoneki. arXiv:2502.00722 (Feb 2025; rev. Jun 2025). https://arxiv.org/abs/2502.00722
A MILP scheduler choosing GPU mix, deployment configuration and workload assignment; outperforms homogeneous and heterogeneous baselines across workload traces, GPU availabilities and multi-model serving.
*Key figures:* ⚠️ **No headline percentages in the abstract.**
*Relevancia Swarmbly:* Marco de optimización de coste para elegir la mezcla de GPU, aplicable a la política de admisión de nodos de Swarmbly.

**[P2P-47] ⚠️ — Hyperion: Hierarchical Scheduling for Parallel LLM Inference.** arXiv:2511.14450 (2025). https://arxiv.org/pdf/2511.14450
Offline model partitioning plus online request scheduling across heterogeneous edge nodes.
*Key figures:* **up to 52.1%** latency reduction vs GPipe; **31.2%** vs HEFT; **44.5%** lower latency for long-sequence generation. ⚠️ Despite the name, it optimizes partitioning plus sequential request assignment more than concurrent multi-request parallelism.
*Relevancia Swarmbly:* Ejemplo del margen (30–52%) que da la planificación jerárquica en el borde, y advertencia sobre nombres que prometen más paralelismo del que entregan.

**[P2P-48] ⭐ — SYNTHETIC-2 (Prime Intellect).** Launched **June 23, 2025**. https://www.primeintellect.ai/blog/synthetic-2 · https://www.primeintellect.ai/blog/synthetic-2-release
An open reasoning dataset **and** a planetary-scale distributed inference run: millions of independent prompts farmed out to heterogeneous hardware from consumer GPUs to hyperscale clusters, verified per task. Verified with **TOPLOC v2**, which adds group-level rewards, stage-by-stage replay to localize faulty nodes, and **reproducible Gumbel noise** to verify *sampling* (not just the forward pass). Difficulty annotated by Qwen3-32B/8B via pass@k.
*Key figures:* **>20 reasoning task families**; **~4 million** collaboratively generated verified traces; generated with DeepSeek-R1-0528.
*Relevancia Swarmbly:* Es el mayor despliegue real del patrón exacto de Swarmbly, y el truco del ruido de Gumbel reproducible resuelve un problema sutil (verificar el muestreo estocástico) con el que Swarmbly tropezará.

**[P2P-49] ⭐ — Planetary-Scale Inference: Building a Distributed Inference Engine for the Public Internet (Prime Intellect).** April 28, 2025. https://www.primeintellect.ai/blog/inference
Releases PRIME-IROH (pipeline comms backend), PRIME-VLLM and PRIME-PIPELINE, together with the engineering rationale for their design choices on the public internet.
*Key figures:* At **~100 ms public-internet latency**, **pipeline parallelism** is the only viable model-parallel scheme (lowest communication volume); asynchronous micro-batching does **not** help, because decoding is **memory-bandwidth-bound** from KV-cache movement rather than compute-bound.
*Relevancia Swarmbly:* El hallazgo de que la decodificación está limitada por ancho de banda de memoria es el núcleo técnico del caso de Swarmbly: si un solo flujo de decodificación no puede saturar la GPU del voluntario, ejecutar **prompts independientes** en cada nodo extrae mucho más rendimiento agregado que dividir un prompt entre nodos.

---

# 2. [NET] — Realidad de red: ancho de banda, latencia, interconexión

**[NET-01] ⭐ — Epoch AI: "How far can decentralized training over the internet scale?"** Jaime Sevilla, **December 29, 2025**. https://epoch.ai/gradient-updates/how-far-can-decentralized-training-over-the-internet-scale
A quantitative feasibility analysis of decentralized training over consumer links, and the single best source for the "why weights over consumer links is hard" argument.
*Key figures:* At **~60 Mbps typical consumer upload**, naive data parallelism with 32-bit gradients caps you at a **~600M-parameter** model to keep sync under ten minutes. Training DeepSeek-v3 (671B) naively over the internet: **~5,000 years**. DiLoCo's 500 inner steps → **500×** bandwidth cut; Streaming DiLoCo → **100×** vs naive; 4-bit quantization adds **2–4×**; combined ≈ **8× larger** models feasible. Largest runs to date — INTELLECT-1 (10B), Protocol Model 8B, Consilience 40B — all use **~1000× less compute** than frontier models. Largest active decentralized network (Templar): **9e17 FLOP/s**, **~300×** smaller than a frontier datacenter.
*Relevancia Swarmbly:* Es la mejor cita única para justificar que compartir pesos o gradientes por enlaces de consumo es inviable y que mover **prompts** en lugar de tensores esquiva el problema por completo.

**[NET-02] ⚠️ `[UNVERIFIED]` — Ancho de banda de subida del consumidor.**
- **~60 Mbps** typical consumer upload is the working assumption in Epoch AI's Dec 2025 analysis (`NET-01`), from which the 600M-parameter naive-data-parallel ceiling is derived. https://epoch.ai/gradient-updates/how-far-can-decentralized-training-over-the-internet-scale
- **FCC broadband benchmark: 100 Mbps down / 20 Mbps up.** Ookla's H1-2025 US data: **38 states + DC** delivered ≥100/20 Mbps to **≥60%** of broadband users; **five states exceeded 70%**. https://www.lightreading.com/broadband/fixed-broadband-speeds-improve-in-2025-with-exceptions-ookla
- Research papers' own operating assumptions are the most useful proxy: Petals tested **100 Mbit/s** (`P2P-02`); SWARM assumed **<200 Mb/s** (`P2P-04`); Subspace Networks targets **80 Mbps** (`P2P-29`).
*Key figures — verification failure, stated explicitly:* A current global or US **median upload** figure could **not** be obtained from a primary Ookla source. speedtest.net/global-index returned HTTP 403 through the proxy; the ComSoc summary of Ookla's US report failed with a redirect loop; the FCC's Measuring Broadband America pages returned 403. Secondary aggregators report **download** medians only (e.g. US **~302.68 Mbps** median fixed download, Dec 2025 Speedtest data per World Population Review; global fixed download **~90 Mbps** for 2024 per RSI). **Do not cite a global median upload number without fetching Ookla directly.**
*Relevancia Swarmbly:* Fija el presupuesto de ancho de banda ascendente (60–100 Mbps) sobre el que debe dimensionarse todo el protocolo, y documenta honestamente qué cifra no se puede citar.

**[NET-03] ⚠️ — Microsoft Azure inter-region latency statistics.** P50 RTT from continuous 1-minute backbone probes; dataset dated **July 30, 2026** (30-day window). https://learn.microsoft.com/en-us/azure/networking/azure-network-latency
*Key figures:* US East ↔ US West **66–71 ms**; US East ↔ Central US **28–33 ms**; Central ↔ West US **39 ms**. Transatlantic: US East ↔ West Europe **89 ms**; ↔ UK South **82 ms**; ↔ France Central **87 ms**. Transpacific: US West ↔ Japan East **100–107 ms**; ↔ Australia East **140–161 ms**; ↔ SE Asia **163–170 ms**. ⚠️ These are **backbone-to-backbone** figures between datacenters; real volunteer nodes on residential last-mile add access-network latency on top, so treat them as **optimistic lower bounds**.
*Relevancia Swarmbly:* Es la fuente citable para el presupuesto de latencia WAN (30–170 ms), y la advertencia de que son cotas inferiores optimistas debe acompañar cualquier proyección de Swarmbly.

**[NET-04] — NVIDIA H100 interconnect.** https://www.nvidia.com/en-us/data-center/h100/
*Key figures:* **NVLink on H100 SXM: 900 GB/s** per GPU (H100 NVL: **600 GB/s**); **PCIe Gen5: 128 GB/s**.
*Relevancia Swarmbly:* Establece el término superior de la comparación de ancho de banda que da sentido a toda la tesis de Swarmbly.

**[NET-05] — NVIDIA Quantum-2 InfiniBand.** https://www.nvidia.com/en-us/networking/quantum2/
*Key figures:* **400 Gb/s per port**; 64×400G or 128×200G per switch; **51.2 Tb/s** bidirectional aggregate; **>66.5 billion packets/sec**.
*Relevancia Swarmbly:* Segundo término de comparación (la red del centro de datos, no solo el bus intra-nodo), necesario para que la brecha calculada en `NET-06` sea justa.

**[NET-06] ⭐ — La brecha, calculada.** Derived from `NET-02`, `NET-03`, `NET-04`, `NET-05`.
*Key figures:* **Bandwidth:** 900 GB/s NVLink = **7,200 Gb/s** vs **~0.06 Gb/s** consumer upstream → **~120,000×**. Against InfiniBand NDR (400 Gb/s) → **~6,700×**. **Latency:** intra-node NVLink is sub-microsecond and InfiniBand is single-digit microseconds, versus **~30–170 ms** WAN RTT → **roughly 4–5 orders of magnitude**.
*Relevancia Swarmbly:* Estas dos razones **son** el argumento entero: cualquier esquema que mueva activaciones o gradientes por token paga la brecha en cada paso, mientras que un esquema que envía un prompt y recibe tokens la paga **dos veces por petición**, con una carga útil de kilobytes en lugar de gigabytes.

---

# 3. [VER] — Verificación de cómputo no confiable

## 3.1 Esquemas baratos y prácticos (lo que realmente funciona en 2026)

**[VER-01] ⭐ — TOPLOC: A Locality Sensitive Hashing Scheme for Trustless Verifiable Inference.** Ong, Di Ferrante, Pazdera, Garner, Jaghouar, Basra, Ryabinin, Hagemann (Prime Intellect). arXiv:2501.16007 (Jan 27, 2025; rev. May 30, 2025). https://arxiv.org/abs/2501.16007 · https://github.com/PrimeIntellect-ai/toploc
Commits to a locality-sensitive hash of top-k activations so a verifier can detect that a different model, prompt or precision was used. Battle-tested in INTELLECT-2 (`P2P-24`) and SYNTHETIC-2 (`P2P-48`).
*Key figures:* Detects unauthorized model, prompt or precision changes with **100% accuracy**, **0 false positives and 0 false negatives** in testing; **258 bytes per 32 tokens** vs 262 KB for raw embeddings (**~1000× compression**); validation **faster than the original inference**; robust across GPU types and computation reorderings; tested on Llama-3.1-8B-Instruct.
*Relevancia Swarmbly:* Es la primitiva de verificación más directamente aplicable al proyecto — por inferencia, barata, portable entre hardware y ya probada en producción; Swarmbly debe empezar aquí y no por zkML.

**[VER-02] ⚠️ — Verde: Verification via Refereed Delegation for Machine Learning Programs.** Arun, St. Arnaud, Titov, Wilcox, Kolobaric, Brinkmann, Ersoy, Fielding, Bonneau (Gensyn + NYU). arXiv:2502.19405 (Feb 26, 2025). https://arxiv.org/abs/2502.19405
A client delegates to multiple untrusted providers; correctness holds if **at least one is honest**, resolved by a dispute-arbitration protocol over the ML computation graph. Ships **RepOps**, a library giving **bitwise-reproducible** ML primitives across heterogeneous hardware by pinning floating-point operation order.
*Key figures:* The abstract claims "practical overheads for compute providers" but gives **no percentages**; ⚠️ concrete slowdown figures could not be extracted from the abstract page.
*Relevancia Swarmbly:* RepOps resuelve el problema subestimado de que **voluntarios honestos con GPU distintas producen bits distintos**, lo que ingenuamente parece fraude — un fallo que Swarmbly sufriría desde el primer día.

**[VER-03] ⭐ — VeriLLM: A Lightweight Framework for Publicly Verifiable Decentralized Inference.** Wang, Zhao, Song, Shi, Xia, Tong, Ai, Qu, Yang. arXiv:2509.24257 (2025). https://arxiv.org/html/2509.24257v3 · https://arxiv.org/abs/2509.24257
Lightweight re-running plus cryptographic commitments, using selective **prefill-phase recomputation** instead of full re-execution, and an isomorphic design that multiplexes verifier and inference roles on identical GPU workers so workers cannot tell whether they are being audited. Threat model is explicitly "a permissionless environment without trusted nodes" with free-riding participants.
*Key figures:* Verification at **~1% of full inference cost**; security under a **one-honest-verifier** (not honest-majority) assumption, with failure probability **P_fail ~ ρ^k** (ρ = corruption rate, k = committee size). Explicitly contrasts against zkML's "prohibitive prover costs (often hours per inference)."
*Relevancia Swarmbly:* ~1% de sobrecarga bajo el supuesto de un solo verificador honesto es probablemente el mejor punto coste/seguridad publicado para el modelo de amenaza exacto de Swarmbly, y el principio de indistinguibilidad de las tareas de auditoría es un requisito de diseño.

**[VER-04] — IMMACULATE: A Practical LLM Auditing Framework via Verifiable Computation.** Guo, Qu, Wu, Zhai, Wang, Xu, Liu, Yuan, Song, Zhang. arXiv:2602.22700 (**Feb 26, 2026**). https://arxiv.org/html/2602.22700
Detects model substitution, quantization abuse and token overbilling in black-box APIs **without trusted hardware or model internals**, via randomized auditing of a small subset of requests plus a **Logit Distance Distribution (LDD)** statistic robust to benign numerical noise.
*Key figures:* **under 1% throughput overhead**; dense and MoE architectures; experiments include LLaMA3-70B.
*Relevancia Swarmbly:* Es el trabajo más reciente sobre "¿me está haciendo trampa mi proveedor no confiable?" y, a diferencia de Verde, **no exige reproducibilidad bit a bit** — crucial en un parque de GPU heterogéneo.

**[VER-05] — opML: Optimistic Machine Learning on Blockchain.** Conway et al. (Hyper Oracle). arXiv:2401.17555 (Jan 2024). https://arxiv.org/abs/2401.17555 · related: opp/ai (arXiv:2402.15006)
An optimistic / fraud-proof model: results are assumed correct unless challenged, with an interactive dispute game bisecting down to a single disputed step.
*Key figures:* Cost model is the cheapest of the verification families; the price is a **challenge window** (latency before finality).
*Relevancia Swarmbly:* Familia de verificación económicamente más barata, adecuada para trabajos asíncronos de Swarmbly donde la finalidad diferida sea tolerable.

**[VER-06] — Proof of Sampling: A Nash Equilibrium-Secured Verification Protocol for Decentralized Systems.** Zhang, Wang, Liu, Tan, Popa, Moallemi. arXiv:2405.00295. https://arxiv.org/html/2405.00295v2
Game-theoretic randomized re-execution: verify a random fraction of jobs with penalties sized so that honest behaviour is a Nash equilibrium.
*Key figures:* Provides the formal relationship between sampling rate, penalty size and honest-play equilibrium.
*Relevancia Swarmbly:* Da la base formal para elegir la tasa de muestreo y la penalización (slashing) de la ejecución de prompts por voluntarios.

## 3.2 zkML — las sobrecargas

**[VER-07] ⭐ — zkLLM: Zero Knowledge Proofs for Large Language Models.** Sun, Li, Zhang. arXiv:2404.16109; **ACM CCS 2024**. https://arxiv.org/abs/2404.16109 · https://github.com/jvhs0706/zkllm-ccs2024
Introduces `tlookup` (a parallelized lookup argument for tensor ops) and `zkAttn` (a ZK proof for attention), with a fully parallelized CUDA implementation.
*Key figures:* **under 15 minutes** to prove one full inference of a **13B** model; proof **<200 KB**.
*Relevancia Swarmbly:* 15 minutos para probar una inferencia que dura segundos ≈ **~100–1000× de sobrecarga**: la razón cuantitativa por la que zkML no es la respuesta para Swarmbly.

**[VER-08] ⚠️ — EZKL (zkonduit) + published benchmarks.** Halo2-based, Python/JS/CLI. https://docs.ezkl.xyz/ · https://blog.ezkl.xyz/post/benchmarks/
*Key figures (from their own benchmark post):* linear regression **0.118 s**, SVM **0.318 s**, tree ensemble **0.308 s**, random forest **6.161 s**; ~**2.92× faster than Orion**, ~**65.88× faster than RISC Zero**; memory **19–383 MB** vs RISC Zero's **1.3–10.2 GB**. ⚠️ **Crucial caveat:** the suite covers **only four classical ML models** — "the study excluded neural networks and transformers due to framework compatibility constraints." **There is no published EZKL LLM-scale benchmark.**
*Relevancia Swarmbly:* Ejemplo de cifras de zkML que parecen prometedoras hasta que se lee el alcance: ninguna cubre transformers, y Swarmbly no debe extrapolarlas.

**[VER-09] ⭐ ⚠️ `[PARTIAL]` — NANOZK: Layerwise Zero-Knowledge Proofs for Verifiable Large Language Model Inference.** Zhaohui Geoffrey Wang (USC Viterbi). arXiv:2603.18046 (2026). https://arxiv.org/html/2603.18046v1
Layerwise decomposition giving constant-size per-layer proofs, with lookup-table approximations for non-arithmetic ops.
*Key figures:* **43 s** proof generation at **GPT-2 scale**; **6.9 KB per layer** (constant); **23 ms** verification; **52× average / 228× peak speedup vs EZKL**; **0.00%** perplexity degradation; soundness error **ε < 10⁻³⁷**; **3.2 minutes** to prove a full 12-layer GPT-2 in parallel. ⚠️ The HTML did not state an explicit submission date; the 2603 prefix implies March 2026.
*Relevancia Swarmbly:* Incluso el estado del arte de 2026 necesita **3.2 minutos para probar GPT-2 (124M)**; extrapolar a 7B+ cierra definitivamente la puerta a zkML en una red de voluntarios.

**[VER-10] — A Survey of Zero-Knowledge Proof Based Verifiable Machine Learning.** Peng, Zhao, Wang, Liao, Lin, Liu, Cao, Shi, Yang, Zhang. arXiv:2502.18535 (Feb 25, 2025; rev. **Mar 29, 2026**). https://arxiv.org/abs/2502.18535
Covers June 2017 – August 2025 across verifiable training, testing and inference.
*Key figures:* Names three blockers: **limited circuit expressiveness**, **high proving cost**, **deployment complexity**.
*Relevancia Swarmbly:* Cita de respaldo para descartar zkML de forma documentada y no anecdótica en el whitepaper.

## 3.3 Inferencia basada en TEE

**[VER-11] — Confidential Computing on NVIDIA Hopper GPUs: A Performance Benchmark Study.** Zhu, Yin, Deng, Almeida, Zhou (Phala). arXiv:2409.03992 (Sep 2024; rev. Nov 2024). https://arxiv.org/abs/2409.03992 · https://arxiv.org/html/2409.03992v1 · https://github.com/Phala-Network/hopper-llm-benchmark
The most-cited empirical benchmark of H100 confidential-computing mode for LLM inference.
*Key figures:* Average overhead **<7%**; "for most typical LLM queries, the overhead remains below **5%**". Llama-3.1-8B **6.85%** TPS overhead · Phi-3-14B-128k **4.58%** · Llama-3.1-70B **−0.13%** (negligible); "the overhead reduces toward zero as the model size grows". By sequence length (8B): ≤100 tok **7.16%**, ≤500 tok **6.90%**, 501–1500 tok **6.65%**. **TTFT overhead ~19%** vs **inter-token latency overhead 7.67%** — "the main bottleneck lies in the CPU–GPU IO, particularly when data is exchanged via PCIe", not GPU compute.
*Relevancia Swarmbly:* Fija el mejor caso publicado del coste de confidencialidad por hardware (<7%), el punto de comparación frente al cual la fragmentación de prompts debe justificar su valor.

**[VER-12] — Confidential LLM Inference: Performance and Cost Across CPU and GPU TEEs.** Chrapek, Copik, Mettaz, Hoefler (ETH Zurich). arXiv:2509.18886 (Sep 23, 2025). https://www.arxiv.org/pdf/2509.18886
Cross-TEE comparison covering Intel SGX, Intel TDX and NVIDIA H100 CC, with cost analysis per million tokens. Llama2 7B/13B/70B, batch 1–512.
*Key figures:* **Intel SGX 4.80–6.15%** throughput / 5–7% latency overhead single-socket, but **>230%** multi-socket (NUMA pathology); **Intel TDX 5.51–10.68%** throughput / 3–10% latency single-socket, rising to **12.11–23.81%** multi-socket 70B (socket-interconnect encryption); **NVIDIA H100 cGPU 4–8%** throughput penalty, "oscillating between 7.5% and 4.4%", shrinking with larger batches; **AMD SEV-SNP** not directly evaluated, expected close to TDX. **Cost:** CPU TEEs are **27–100% cheaper** per million tokens at batch size 1, but the advantage vanishes at batch ≥128; confidential H100 carries **up to a 100% cost premium**. Intel AMX gave **2–6×** acceleration under TDX.
*Relevancia Swarmbly:* Muestra que el coste de los TEE depende críticamente del tamaño de lote y de la topología, y que la ventaja de CPU desaparece exactamente en el régimen de alto lote que un centro de datos usa y un voluntario no.

**[VER-13] ⭐ ⚠️ `[PARTIAL]` — Benchmarking Confidential GPU Inference on NVIDIA H100 under Intel TDX.** Wang, Hyee, Smith (Mozilla). arXiv:2607.19353 (2026). https://arxiv.org/abs/2607.19353 · https://arxiv.org/html/2607.19353v1
The 2026 re-measurement of TEE overhead under realistic serving loads rather than microbenchmarks.
*Key figures:* At fixed request rate — Mistral-7B (10.0 req/s) **21.8% TTFT overhead / 17.7% throughput loss**; Qwen3-30B-A3B (5.0 req/s) **27.8% TTFT / 21.1% throughput**. Closed-loop concurrency: Mistral-7B **12.7–18.8%**, Qwen3-30B **11.5–20.2%** throughput gaps; end-to-end latency overhead **8.9–15.6%** (Mistral). Larger models saturate earlier under CC mode. ⚠️ **arXiv ID confirmed to exist, but the author list is unreliable** — two independent fetches returned inconsistent names ("Wei Wang, Abdul Hyee, Waqas Burns, Smith Anonym" vs "Wei Wang, Abdul Hyee Waqas, Burns Smith"). Reported date 2026-05-20. **Verify authorship directly on arXiv before citing.**
*Relevancia Swarmbly:* Es el retrato honesto de 2026: la sobrecarga TEE es del **5–25%**, no del "<7%" que suele citarse de Phala 2024; aun así es 1–2 órdenes de magnitud más barata que zkML, pero **las GPU de consumo (RTX 3090/4090) no tienen modo CC**, de modo que los TEE son inalcanzables para Swarmbly salvo restringiéndose a proveedores H100/H200.

**[VER-14] — OWASP Top 10 for LLM Applications, 2025.** https://owasp.org/www-project-top-10-for-large-language-model-applications/assets/PDF/OWASP-Top-10-for-LLMs-v2025.pdf
The industry-standard threat catalogue for LLM systems.
*Key figures:* Directly applicable entries for a system that ingests text produced by untrusted third parties and feeds it into a local model: **LLM01 Prompt Injection, LLM03 Supply Chain, LLM05 Improper Output Handling, LLM08 Vector/Embedding Weaknesses**.
*Relevancia Swarmbly:* Cada fragmento devuelto por un voluntario es entrada no confiable que fluye hacia el modelo ensamblador local; OWASP da la taxonomía de amenazas con la que Swarmbly debe estructurar su modelo de seguridad.

---

# 4. [DEC] — Descomposición de prompts, decodificación paralela, multi-agente y fusión

## 4.1 Skeleton-of-Thought: la descomposición paralela canónica a nivel de prompt

**[DEC-01] ⭐ — Skeleton-of-Thought (SoT): Prompting LLMs for Efficient Parallel Generation.** arXiv:2307.15337 (ICLR 2024; v1 Jul 2023 as "…Large Language Models Can Do Parallel Decoding", v3 Mar 2024). https://arxiv.org/abs/2307.15337 · PDF: https://openreview.net/pdf?id=mqVgBbNCm9
Two-stage method: a skeleton prompt produces a short list of points, and each point is then expanded **independently** via parallel API calls or batched decoding. This is the direct intellectual ancestor of Swarmbly's micro-prompt dispatch.
*Key figures:* Speedup **up to 2.39×**; **>2× on 8 of 12 models** (9 open-source + 3 API). Quality (GPT-4 judge, FastChat + LLMZoo, Vicuna-80 = 80 questions / 9 categories, WizardLM = 218 questions): **improves** on knowledge, generic, common-sense, roleplay, counterfactual; **hurts** on math, coding, writing, fermi. On the LLMZoo coherence metric, "SoT is not worse than the normal generation **around 60% of the time**" — i.e. it **is worse ~40% of the time**. Verbatim: **"SoT improves the diversity and relevance while hurting the immersion and coherence"** and **"SoT currently ignores the dependencies between points."** Stated failure theory: "it is fundamentally challenging to apply SoT on questions that require step-by-step thinking, in which the latter steps require the details from the earlier steps."
*Relevancia Swarmbly:* Es el precedente exacto de la idea central de Swarmbly, con su límite estructural medido y admitido por los propios autores: la incoherencia en ~40% de las salidas es el impuesto que Swarmbly debe presupuestar y medir.

**[DEC-02] ⭐ — SoT-R (SoT with Router).** Same paper, arXiv:2307.15337. https://arxiv.org/abs/2307.15337
A router decides *per question* whether to use SoT at all. Two implementations: (a) a **GPT-4 prompting router**, (b) a **trained 120M RoBERTa router** fine-tuned on annotated LIMA with **Tversky loss** to penalize false positives.
*Key figures:* The trained **120M** router performs similarly to (Vicuna-80) or better than (WizardLM) the prompting router, sometimes surpassing the human router. The Tversky loss encodes the asymmetry that **wrongly fragmenting is worse than wrongly not fragmenting**.
*Relevancia Swarmbly:* Es la lección de diseño más transferible de toda la bibliografía: los autores originales concluyeron que la descomposición paralela debe ser **condicionada por un router, no aplicada por defecto**, y un modelo de 120M basta para ello.

**[DEC-03] — Microsoft Research blog on SoT.** https://www.microsoft.com/en-us/research/blog/skeleton-of-thought-parallel-decoding-speeds-up-and-improves-llm-output/
The official non-arXiv write-up of `DEC-01`.
*Key figures:* Same as `DEC-01`; useful as an accessible, citable secondary source.
*Relevancia Swarmbly:* Cita divulgativa alternativa para el whitepaper cuando se prefiera una fuente institucional a un preprint.

## 4.2 Prompting por descomposición (secuencial, respetuoso de dependencias)

**[DEC-04] — Chain-of-Thought (CoT).** arXiv:2201.11903 (NeurIPS 2022). https://arxiv.org/abs/2201.11903
Intermediate reasoning steps elicited by few-shot exemplars; fully sequential by construction.
*Key figures:* The baseline against which every decomposition method is measured.
*Relevancia Swarmbly:* Línea base obligatoria: cualquier ganancia de Swarmbly debe medirse contra CoT, no contra generación ingenua.

**[DEC-05] — Self-Consistency.** arXiv:2203.11171 (ICLR 2023). https://arxiv.org/abs/2203.11171
Samples *k* diverse reasoning paths **in parallel** and marginalizes by majority vote on the final answer.
*Key figures:* Gains over CoT: **GSM8K +17.9%, SVAMP +11.0%, AQuA +12.2%, StrategyQA +6.4%, ARC-challenge +3.9%**.
*Relevancia Swarmbly:* Distinción crítica: paraleliza *intentos redundantes de la tarea completa* con una fusión trivialmente segura (votar un token de respuesta); **no** paraleliza fragmentos disjuntos de una misma salida, que es lo difícil.

**[DEC-06] — Least-to-Most Prompting.** arXiv:2205.10625 (ICLR 2023). https://arxiv.org/abs/2205.10625
Decomposes into subproblems and solves them **in sequence**, feeding each answer into the next.
*Key figures:* SCAN with code-davinci-002: **≥99% accuracy with 14 exemplars vs 16% for CoT**; specialized neuro-symbolic baselines needed **15,000+** training examples.
*Relevancia Swarmbly:* Es el anti-ejemplo del despacho independiente: la ganancia dramática proviene precisamente de la **cadena de dependencia secuencial** que Swarmbly rompe.

**[DEC-07] ⚠️ — Decomposed Prompting (DecomP).** arXiv:2210.02406 (ICLR 2023, AI2). https://arxiv.org/abs/2210.02406 · https://github.com/allenai/DecomP
A modular decomposer LLM dispatches sub-tasks to specialized sub-prompt handlers, supporting recursive decomposition for long inputs and delegation to retrieval or symbolic tools.
*Key figures:* Abstract reports "outperforms prior work on few-shot prompting using GPT3" but gives ⚠️ **no numbers in the abstract**; quantitative comparisons live in the body and repo.
*Relevancia Swarmbly:* Es el análogo publicado más cercano a una arquitectura **despachador + workers**, es decir, el plano conceptual del orquestador de Swarmbly.

**[DEC-08] — Plan-and-Solve Prompting.** arXiv:2305.04091 (ACL 2023). https://arxiv.org/abs/2305.04091
Zero-shot method that first devises a plan splitting the task into subtasks, then executes it, positioning planning as a separate explicitly-elicited stage.
*Key figures:* Improves over zero-shot CoT.
*Relevancia Swarmbly:* Justifica separar la etapa de planificación (fragmentación) de la de ejecución, que es exactamente la frontera cliente/nodo de Swarmbly.

**[DEC-09] — Tree of Thoughts (ToT).** arXiv:2305.10601 (NeurIPS 2023). https://arxiv.org/abs/2305.10601
Search over a tree of intermediate "thoughts" with self-evaluation, BFS/DFS and backtracking.
*Key figures:* Parallelism here is *search-level breadth*, not output-fragment level, and it **always includes a verification/selection step**.
*Relevancia Swarmbly:* Recuerda que toda la familia de métodos de árbol incorpora verificación explícita; Swarmbly no puede omitir ese paso y esperar el mismo rendimiento.

**[DEC-10] — Graph of Thoughts (GoT).** arXiv:2308.09687 (AAAI 2024). https://arxiv.org/abs/2308.09687
Thoughts as vertices and dependencies as edges, supporting aggregation ("merging") of thoughts and feedback loops.
*Key figures:* **+62% quality on sorting over ToT while reducing cost >31%**.
*Relevancia Swarmbly:* Es el único marco de esta familia que trata la **fusión como una operación de primera clase con aristas de dependencia explícitas** en lugar de concatenación — el modelo que debe seguir el reensamblador de Swarmbly.

## 4.3 Métodos de *decodificación* paralela que explotan independencia semántica

**[DEC-11] ⚠️ — APAR: Auto-Parallel Auto-Regressive decoding.** arXiv:2401.06761 (THUDM). https://arxiv.org/abs/2401.06761 · https://github.com/thudm/apar
Instruct-tunes the model on hierarchically structured data so it emits fork tokens and plans its own parallel branches.
*Key figures:* **Up to 2× standalone; up to 4× combined with speculative decoding; 20–70% throughput increase and 20–35% latency reduction** in high-throughput serving; reduces KV-cache and attention cost. ⚠️ The abstract makes **no explicit quality-preservation claim**.
*Relevancia Swarmbly:* Demuestra que un modelo puede aprender a planificar sus propias ramas paralelas — alternativa a que el orquestador de Swarmbly decida la fragmentación externamente.

**[DEC-12] ⭐ — PASTA / PASTA-LANG (Learning to Keep a Promise).** arXiv:2502.11517 (ICML 2025). https://arxiv.org/abs/2502.11517
A learned annotation language in which the model marks semantically independent spans of *its own* response; an interpreter orchestrates asynchronous parallel decoding. Claims Pareto-dominance over prior methods on the speed/quality frontier.
*Key figures:* **Geomean speedups 1.21×–1.93×**, with length-controlled AlpacaEval win-rate deltas of **+2.2% to −7.1%** vs sequential.
*Relevancia Swarmbly:* Es la curva calidad/coste más honesta publicada para el paralelismo estilo SoT: comprar ~1.9× cuesta hasta ~7 puntos de win-rate. Ese es el precio de referencia que Swarmbly debe superar o admitir.

**[DEC-13] — Adaptive Skeleton Graph Decoding (ASGD) → "Plato".** Jin, Wu, Zheng, Zhang, Lentz. arXiv:2402.12280. https://arxiv.org/abs/2402.12280
Current version is a semantic-aware parallel decoding system ("Plato") that builds a **dependency graph over sub-problems** instead of a flat list, with pipelining and KV-cache reuse.
*Key figures:* **68% throughput gain** over autoregressive decoding; **40% net-win rate** in quality vs AR; **90% quality net-win rate vs SoT**; pipelining contributes **29%** of the speedup and KV-cache optimization cuts **75%** of overhead. ⚠️ Title/version drift: v1 was "Adaptive Skeleton Graph Decoding" — cite the version you actually read.
*Relevancia Swarmbly:* El salto de una lista plana a un **grafo de dependencias** produce un 90% de net-win frente a SoT: la evidencia más clara de que Swarmbly debe modelar dependencias entre micro-prompts, no ignorarlas.

**[DEC-14] ⭐ — Hogwild! Inference.** arXiv:2504.06261 (NeurIPS 2025). https://arxiv.org/abs/2504.06261 · https://eqimp.github.io/hogwild_llm/
Multiple instances of the same LLM generate **concurrently against a shared, concurrently-updated KV cache**, using RoPE tricks to avoid recomputation; workers "see" each other's partial memory in real time and self-organize.
*Key figures:* Modern reasoning LLMs can do this **out of the box, without fine-tuning**.
*Relevancia Swarmbly:* Es arquitectónicamente lo **opuesto** al despacho de fragmentos aislados, y el argumento más fuerte de que lo caro del paralelismo no es la concurrencia sino el **aislamiento** — precisamente lo que Swarmbly impone por razones de confianza.

**[DEC-15] — Dynamic Parallel Tree Search (DPTS).** arXiv:2502.16235. https://arxiv.org/abs/2502.16235
Parallelizes ToT-style reasoning with fine-grained KV-cache management/alignment plus a Search-and-Transition mechanism to prune redundant paths.
*Key figures:* **2–4× average speedup** on Math500 and GSM8K with Qwen-2.5 and Llama-3, **maintaining or surpassing accuracy**.
*Relevancia Swarmbly:* Demuestra que 2–4× con calidad preservada es alcanzable — pero mediante gestión compartida de KV-cache, imposible entre nodos WAN aislados.

**[DEC-16] ⭐ — ParallelBench.** Kang, Galim, Oh, et al. arXiv:2510.04767 (ICLR 2026). https://arxiv.org/abs/2510.04767
A benchmark isolating the cost of parallel decoding in diffusion LLMs, with an information-theoretic analysis plus synthetic list-operation case studies on tasks trivial for humans and AR LLMs that nonetheless break parallel decoders.
*Key figures (verbatim core claim):* **"the conditional independence assumption … causes parallel decoding to ignore token dependencies, inevitably degrading generation quality when these dependencies are strong."** Also finds current strategies "struggle to adapt their degree of parallelism based on task difficulty, thus failing to achieve meaningful speedup without compromising quality."
*Relevancia Swarmbly:* Es el enunciado formal más limpio de **por qué** la generación de fragmentos independientes pierde calidad, y generaliza por encima del nivel de token: aplica directamente a los micro-prompts de Swarmbly.

**[DEC-17] — A Survey on Parallel Text Generation.** arXiv:2508.08712 (2025). https://arxiv.org/abs/2508.08712
Taxonomy of AR-based versus non-AR parallel generation, evaluated on speed, quality and efficiency.
*Key figures:* Single best landscape citation for the field.
*Relevancia Swarmbly:* Cita de encuadre para situar Swarmbly dentro de la taxonomía existente de generación paralela.

## 4.4 Decodificación especulativa / sin pérdidas — la línea base honesta

**[DEC-18] ⭐ — Speculative Decoding.** Leviathan, Kalman, Matias. arXiv:2211.17192 (ICML 2023). https://arxiv.org/abs/2211.17192
A small draft model proposes tokens and the target model verifies them in parallel, with a rejection-sampling rule that **provably preserves the target model's output distribution**.
*Key figures:* **2×–3× on T5-XXL**; no retraining, no architecture change, **no output change**.
*Relevancia Swarmbly:* Es el punto de comparación correcto: un método que da aceleración real con **garantía matemática de cero pérdida de calidad**. Todo esquema de descomposición debe compararse contra esto, no contra la generación secuencial ingenua.

**[DEC-19] — Medusa.** arXiv:2401.10774. https://arxiv.org/abs/2401.10774 · https://github.com/FasterDecoding/Medusa
Extra decoding heads predict multiple future tokens; tree attention verifies candidate continuations.
*Key figures:* **Medusa-1: >2.2×** "without compromising generation quality" (lossless); **Medusa-2: 2.3–3.6×** with a training recipe designed to preserve backbone capability, plus a "typical acceptance" scheme.
*Relevancia Swarmbly:* Segunda línea base sin pérdidas; su rango 2.2–3.6× ya iguala o supera lo que SoT/PASTA logran **con** pérdida de calidad.

**[DEC-20] — Lookahead Decoding.** arXiv:2402.02057 (ICML 2024). https://arxiv.org/abs/2402.02057 · https://github.com/hao-ai-lab/LookaheadDecoding
Jacobi-iteration-based **exact** parallel decoding with **no draft model and no data store**, trading per-step FLOPs for fewer decoding steps.
*Key figures:* **Up to 1.8× on MT-Bench; 4×** with strong scaling across GPUs on code completion.
*Relevancia Swarmbly:* Tercera línea base exacta, y notable porque su escalado fuerte entre GPU (4×) es la comparación más directa con el paralelismo multi-nodo de Swarmbly, pero en LAN y sin pérdida.

**[DEC-21] ⭐ — Large Language Monkeys (repeated sampling).** arXiv:2407.21787 (Stanford). https://arxiv.org/abs/2407.21787
Coverage (the fraction of problems solved by *any* sample) scales log-linearly over four orders of magnitude of sample count.
*Key figures:* SWE-bench Lite with DeepSeek-Coder-V2-Instruct: **15.9% at 1 sample → 56% at 250 samples**, beating the **43%** single-sample SOTA. Critical caveat, verbatim: **"majority voting and reward models plateau beyond several hundred samples"** — without an automatic verifier you cannot cash in the coverage.
*Relevancia Swarmbly:* Implicación directa: el cómputo paralelo se convierte en calidad **solo en proporción a la fuerza del selector/fusionador**. Un ensamblador débil pone el techo a todo el sistema Swarmbly.

## 4.5 Marcos multi-agente y sus modos de fallo medidos

**[DEC-22] ⭐ — MAST: "Why Do Multi-Agent LLM Systems Fail?"** Cemri et al. (UC Berkeley). arXiv:2503.13657. https://arxiv.org/abs/2503.13657 · https://github.com/multi-agent-systems-failure-taxonomy/MAST
The reference failure taxonomy: **14 failure modes in 3 categories** — system design/specification, inter-agent misalignment, and task verification — built from rigorous trace analysis.
*Key figures:* **150 traces** with expert annotators, **inter-annotator κ = 0.88**; MAST-Data has **1,600+ annotated traces across 7 MAS frameworks**. Distribution across 1,642 traces: **FC1 system design 47.9%, FC2 inter-agent misalignment 32.15%, FC3 task verification 19.95%**. Within FC1 the two most common modes are **step repetition (15.7%)** and **task specification disobedience (11.8%)**. LLM-as-judge annotator (o1, few-shot): **94% accuracy, κ=0.77, F1=0.80**, generalizing to unseen MAS at κ=0.79. ChatDev case study interventions: **+9.4%** from workflow/consensus fixes, **+15.6%** on ProgramDev from adding high-level objective verification. Headline framing: multi-agent gains on popular benchmarks "are often minimal."
*Relevancia Swarmbly:* Da la taxonomía de fallos con la que Swarmbly debe instrumentar su telemetría, y la cifra incómoda de que casi la mitad de los fallos (47.9%) provienen del diseño del sistema, no de los modelos.

**[DEC-23] ⭐ — AgenTracer.** arXiv:2509.03312. https://arxiv.org/abs/2509.03312
Automated failure attribution for agentic systems via counterfactual replay plus programmed fault injection.
*Key figures:* **Off-the-shelf reasoning LLMs attribute failures at generally <10% accuracy**; AgenTracer-8B beats Gemini-2.5-Pro / Claude-4-Sonnet by **up to 18.18%** on Who&When; feeding its attributions back yields **4.8–14.2%** downstream gains in MetaGPT/MaAS.
*Relevancia Swarmbly:* Atribuir una mala salida al fragmento responsable es en sí una capacidad difícil y especialmente entrenada: **un ensamblador genérico de 8B no lo hará**, lo que compromete el núcleo del diseño de Swarmbly.

**[DEC-24] — "Stop Overvaluing Multi-Agent Debate".** arXiv:2502.08788. https://arxiv.org/abs/2502.08788
Systematic evaluation of **5 MAD methods × 9 benchmarks × 4 base models**.
*Key figures:* MAD "often fail[s] to outperform simple single-agent baselines such as Chain-of-Thought and Self-Consistency, **even when consuming significantly more inference-time computation**." Proposes model heterogeneity as the remedy.
*Relevancia Swarmbly:* Advertencia de que multiplicar nodos y tokens no compra calidad por sí solo; la heterogeneidad de modelos entre voluntarios podría ser, paradójicamente, una ventaja de Swarmbly.

**[DEC-25] — "When and Why Does Multi-Agent Debate Fail and Does It Really Underperform?"** Chen, Niu, Cheng, Han, Sugiyama. arXiv:2510.20963. https://arxiv.org/abs/2510.20963
A game-theoretic account: competitive MAD degenerates into a cheap-talk game ("debate hacking" — persuasive rhetoric over evidence), while consensus-seeking MAD suppresses informative disagreement and converges prematurely.
*Key figures:* Their ColMAD fix gains **up to 10 pp over prior MAD protocols and up to 4 pp over single-agent methods at matched token budgets**; cross-family model pairs can **reduce >30% of errors**.
*Relevancia Swarmbly:* El resultado de que pares de modelos de familias distintas eliminan >30% de errores es un argumento a favor de la diversidad de modelos en el enjambre de Swarmbly.

**[DEC-26] ⭐ — "Single-Agent LLMs Outperform Multi-Agent Systems on Multi-Hop Reasoning Under Equal Thinking Token Budgets".** Tran & Kiela (Stanford). arXiv:2604.02460 (2026). https://arxiv.org/html/2604.02460v1
Uses the **Data Processing Inequality** to argue that decomposition can only lose information relative to a single agent with the same budget, then tests it across Qwen3, DeepSeek-R1-Distill-Llama and Gemini 2.5.
*Key figures:* Single-agent is best or statistically tied at every budget except the smallest (100 tokens). Averages: **single-agent 0.290–0.427; sequential multi-agent 0.364–0.389**. Notable exception: **when context is heavily corrupted (α=0.7 substitution), sequential multi-agent slightly wins** — structured decomposition helps only under information-degraded conditions.
*Relevancia Swarmbly:* Es el resultado teórico más fuerte **en contra** del despacho de fragmentos: a presupuesto igual, dividir una tarea es un canal con pérdida de información. Swarmbly debe argumentar sobre acceso y coste, no sobre calidad.

**[DEC-27] ⭐ — "When Agents Disagree: The Selection Bottleneck in Multi-Agent LLM Pipelines".** Maryanskyy, Budnikov, Kaliyev. arXiv:2603.20324 (Mar 2026). https://arxiv.org/html/2603.20324v1
210 runs across 42 tasks comparing judge-based *selection* against synthesis-style *aggregation* over homogeneous and diverse teams.
*Key figures:* Judge-based selection over diverse teams: **81% win rate vs single-model baseline (Glass's Δ=2.07)**. Homogeneous teams: **51.2%** (chance). Judge-based selection beats synthesis-style aggregation by **+63.1 pp**. **MoA-style synthesis loses to the baseline in all 42/42 tasks (0% winning preference).** Homogeneous outputs were **100% ties across 756 verdicts** under decoupled judging.
*Relevancia Swarmbly:* Implicación brutal y directamente accionable: **"seleccionar el mejor fragmento" supera a "sintetizar los fragmentos"**, y la fusión puede ser estrictamente peor que no descomponer. Swarmbly debe preferir seleccionar-y-empalmar sobre sintetizar-y-reescribir.

**[DEC-28] ⚠️ — Mixture-of-Agents (MoA).** arXiv:2406.04692 (ICLR 2025, Together AI). https://arxiv.org/abs/2406.04692 · https://github.com/togethercomputer/moa
A layered architecture where each layer's agents consume all previous-layer outputs and an aggregator synthesizes them.
*Key figures:* **65.1% on AlpacaEval 2.0 vs GPT-4 Omni's 57.5%**, using only open-source models; also reported to surpass GPT-4o on MT-Bench and FLASK. ⚠️ Note the direct tension with `DEC-27`, which found MoA-style synthesis losing 42/42.
*Relevancia Swarmbly:* Es la mejor evidencia a favor de la síntesis por capas, y su conflicto con `DEC-27` debe presentarse honestamente en el whitepaper en lugar de citarse solo el resultado favorable.

**[DEC-29] ⚠️ — "More Agents Is All You Need".** arXiv:2402.05120. https://arxiv.org/abs/2402.05120
Simple sampling-and-voting over N agent instances, with performance scaling in N across tasks.
*Key figures:* ⚠️ Individual benchmark deltas were **not verified** from the abstract page. Same structural caveat as self-consistency: parallelism is over *whole answers* with a vote-based merge, not over fragments.
*Relevancia Swarmbly:* Refuerza que el escalado por número de agentes que funciona en la literatura es el de respuestas completas con voto, no el de fragmentos disjuntos.

**[DEC-30] ⭐ — Anthropic: "How we built our multi-agent research system"** (engineering blog). https://www.anthropic.com/engineering/multi-agent-research-system
Production experience with a multi-agent architecture (Opus 4 lead + Sonnet 4 subagents), including an explicit scope statement about when the pattern works.
*Key figures:* Multi-agent **outperformed single-agent Opus 4 by 90.2%** on their internal research eval. Costs: agents use **~4× the tokens of chat; multi-agent ~15×**. **Token usage alone explains 80% of variance** on BrowseComp. Works for **breadth-first, independently-parallelizable search**; poor fit where "all agents [must] share identical context" or where there are many interdependencies — "most coding tasks involve fewer truly parallelizable tasks than research." Observed failure modes: spawning 50+ subagents for simple queries, duplicated work from vague task descriptions, endless searches, bad source selection.
*Relevancia Swarmbly:* Define con precisión industrial la clase de tareas donde la descomposición gana (búsqueda en anchura, independiente) — el nicho al que Swarmbly debe restringir su router — y cuantifica el impuesto de tokens (~15×).

**[DEC-31] ⭐ — Cognition: "Don't Build Multi-Agents"** (Walden Yan). https://cognition.com/blog/dont-build-multi-agents
The counterposition, and the sharpest statement of the seam problem, with two principles: **(1) "Share context, and share full agent traces, not just individual messages."** **(2) "Actions carry implicit decisions, and conflicting decisions carry bad results."**
*Key figures:* Canonical example: a parent splits "build Flappy Bird"; one subagent renders Super Mario-style pipes, the other a non-game-quality bird, and the parent inherits incompatible parts. On compression: a dedicated history-compression model is the escape hatch, but it is "hard to get right" and may need domain-specific fine-tuning.
*Relevancia Swarmbly:* Es la crítica cualitativa más citable contra la arquitectura de Swarmbly, y su Principio 1 (compartir contexto completo) está en tensión directa con el requisito de confidencialidad de Swarmbly: no se pueden satisfacer ambos.

**[DEC-32] ⭐ — "Can Small Agents Collaborate to Beat a Single Large Language Model?"** Żywot, Chen, Yuan, Søgaard, de Rijke. arXiv:2601.11327 (2026). https://arxiv.org/html/2601.11327v2
Orchestrator plus specialized sub-agents with restricted inter-agent communication — structurally the closest published match to Swarmbly's small-local-orchestrator design.
*Key figures:* An **8B multi-agent system ties a 32B single agent with tools on GAIA (23.0 vs 23.0) and beats it on AIME (55.0 vs 45.0)**; structured memory cuts token use **43%**; the 8B system runs **4.2× faster** than the 32B baseline. Crucially, performance is **"primarily driven by orchestrator capacity rather than sub-agent capacity"**; orchestrator-only thinking is the best configuration (**+0.6 s** latency vs **+6.1 s** for sub-agent thinking); sub-agent scaling gives "inconsistent and inefficient" returns.
*Relevancia Swarmbly:* Es la evidencia más favorable a un diseño de orquestador pequeño con muchos workers — y a la vez dice que **el techo de calidad lo fija el orquestador**, no los nodos, lo que obliga a Swarmbly a invertir en el modelo local, no en el enjambre.

## 4.6 Map-reduce de contexto largo, compresión y degradación

**[DEC-33] — Lost in the Middle.** Liu et al. arXiv:2307.03172 (TACL). https://arxiv.org/abs/2307.03172 · https://github.com/nelson-liu/lost-in-the-middle
Multi-document QA and key-value retrieval show a **U-shaped performance curve** in the position of the relevant information — high at the beginning and end of context, substantially degraded in the middle. Persists in models explicitly built for long contexts.
*Key figures:* U-shaped positional bias, robust across models and across long-context architectures.
*Relevancia Swarmbly:* Los fragmentos que caigan en el medio del prompt de reensamblado serán sistemáticamente infravalorados por el modelo local; el orden de concatenación de Swarmbly es una variable de diseño, no un detalle.

**[DEC-34] ⭐ — Context Rot.** Chroma technical report, July 2025. https://research.trychroma.com/context-rot · https://github.com/chroma-core/context-rot
Evaluates **18 models** (Claude Opus 4 / Sonnet 4 / 3.7 / 3.5 / Haiku 3.5; o3, GPT-4.1 family, GPT-4o, GPT-4 Turbo, GPT-3.5 Turbo; Gemini 2.5 Pro/Flash, 2.0 Flash; Qwen3-235B/32B/8B) on long-input reliability.
*Key figures:* Performance "grows increasingly unreliable as input length grows" across **all** models; low needle-question similarity degrades faster with length; **one distractor hurts, four compound the damage**; models do **better on shuffled haystacks than on logically coherent ones**; LongMemEval (306 prompts, ~113k tokens) shows large gaps between focused (~300-token) and full-context inputs; repeated-words task (1,090 variations, 25–10,000 words) degrades with length, with best position accuracy for early items.
*Relevancia Swarmbly:* El ensamblador de Swarmbly debe leer N fragmentos más instrucciones — exactamente el régimen que este informe mide como no fiable — y los fragmentos distractores son medibles peor que no tener fragmentos.

**[DEC-35] ⭐ — BooookScore.** arXiv:2310.00785 (ICLR 2024). https://arxiv.org/abs/2310.00785
The definitive study of *merging independently-produced summaries*, comparing **hierarchical merging** (map-reduce) against **incremental updating** (sequential) for 100k+ token books.
*Key figures:* **8 recurring coherence error types** identified from **1,193 human annotations on 100 recently-published books**; BooookScore = proportion of sentences free of these errors. **Incremental updating produces lower BooookScore but higher detail**; hierarchical merging trades detail for coherence. GPT-4 and Claude 2 > open models; Mixtral ≈ GPT-3.5-Turbo; LLaMA 2 worst. The metric saved **$15K and 500 hours** of human evaluation.
*Relevancia Swarmbly:* Es el estudio empírico más cercano a los "artefactos de costura" del texto ensamblado, y encuentra que son **sistemáticos y taxonomizables**, no incidentales: Swarmbly puede y debe medirlos con esta taxonomía.

**[DEC-36] — LLMLingua.** arXiv:2310.05736 (EMNLP 2023, Microsoft). https://arxiv.org/abs/2310.05736 · https://llmlingua.com/
Coarse-to-fine prompt compression with a budget controller, token-level iterative compression and instruction-tuned distribution alignment.
*Key figures:* **Up to 20× compression with little performance loss** on GSM8K, BBH, ShareGPT and Arxiv-March23.
*Relevancia Swarmbly:* Herramienta directa para reducir el coste de enviar contexto compartido generoso a cada worker, mitigación recomendada frente al problema de aislamiento (`DEC-31`).

**[DEC-37] — LongLLMLingua.** arXiv:2310.06839. https://arxiv.org/abs/2310.06839
Explicitly targets the three long-context problems: cost, performance reduction, and **position bias**.
*Key figures:* **+21.4% on NaturalQuestions at ~4× fewer tokens**; **94.0% cost reduction** on LooGLE; **1.4×–2.6×** end-to-end latency speedup for 10k-token prompts at 2×–6× compression.
*Relevancia Swarmbly:* Aborda directamente el sesgo posicional de `DEC-33` en el prompt de reensamblado, y cuantifica cuánto contexto puede comprimirse antes de despachar.

**[DEC-38] — RAPTOR.** arXiv:2401.18059 (ICLR 2024). https://arxiv.org/abs/2401.18059
Recursively embeds, clusters and summarizes chunks into a tree with multiple abstraction levels; retrieval draws from recursive summaries.
*Key figures:* **+20% absolute accuracy on QuALITY** (with GPT-4) over the prior best.
*Relevancia Swarmbly:* Su paso de fusión es una summarización jerárquica y semánticamente agrupada, **no una concatenación** — el patrón que el reensamblador de Swarmbly debería imitar.

**[DEC-39] ⭐ — LongRAG.** arXiv:2406.15319. https://arxiv.org/abs/2406.15319 · https://tiger-ai-lab.github.io/LongRAG/
Rebalances RAG by using **4K-token retrieval units** (grouped related documents) with a long-context reader, needing **fewer than 8 top units**.
*Key figures:* **NQ EM 62.7%, HotpotQA EM 64.3%, Qasper F1 25.9%, MultiFieldQA-en F1 57.5% — with no training**, matching fully-trained SOTA on Wikipedia benchmarks.
*Relevancia Swarmbly:* Contraevidencia directa a la fragmentación agresiva: **unidades más grandes, menos numerosas y más coherentes superan a muchas pequeñas**, lo que sugiere micro-prompts grandes y pocos, no muchos y minúsculos.

## 4.7 Medición de coherencia — cómo detectar el daño en las costuras

**[DEC-40] — Entity-grid local coherence model.** Barzilay & Lapata, *Computational Linguistics* 34(1), 2008. https://aclanthology.org/J08-1001.pdf
The classic non-LLM discourse coherence model: represents entity mentions and their grammatical roles across sentences, scoring coherence from transition probabilities in the grid.
*Key figures:* Still the standard baseline for automatic coherence evaluation and for detecting sentence-ordering / insertion damage.
*Relevancia Swarmbly:* Detector de costuras independiente del LLM que produce el texto — imprescindible para que la evaluación de Swarmbly no sea circular.

**[DEC-41] — Neural coherence models as discourse-coherence assessors.** Springer/HAL, *Using Neural Coherence Models to Assess Discourse Coherence* (2024). https://hal.science/hal-04982691v1/document
Modern neural successors to the entity grid, evaluated specifically as coherence assessors.
*Key figures:* Provides an automatic seam detector independent of the LLM producing the text.
*Relevancia Swarmbly:* Alternativa moderna a `DEC-40` para instrumentar la métrica de coherencia como ciudadano de primera clase en el eval de Swarmbly.

**[DEC-42] — LLMZoo coherence/immersion metrics as used in SoT.** See `DEC-01`. https://arxiv.org/abs/2307.15337
*Key figures:* SoT's authors measured coherence separately from relevance and diversity, and **only the coherence and immersion axes went down**.
*Relevancia Swarmbly:* Precedente operativo: cualquier evaluación de un sistema de costura que reporte solo "calidad" agregada **ocultará el fallo**; hay que reportar coherencia por separado.

## 4.8 Modelos pequeños como planificadores / orquestadores / routers

**[DEC-43] ⭐ — RouteLLM.** arXiv:2406.18665 (LMSYS / UC Berkeley). https://arxiv.org/abs/2406.18665 · https://www.lmsys.org/blog/2024-07-01-routellm/ · https://github.com/lm-sys/RouteLLM
Routers trained on preference data (Chatbot Arena) route between a strong and a weak model. Four routers: similarity-weighted Elo ranking, matrix factorization, BERT classifier, causal-LLM classifier.
*Key figures:* **Cost reduction >85% on MT Bench, 45% on MMLU, 35% on GSM8K while retaining 95% of GPT-4 performance.** The matrix-factorization router on MT Bench needed **only 14% of GPT-4 calls** at the 95% threshold (with augmented training data). Routers **transfer** when the strong/weak models are swapped at test time.
*Relevancia Swarmbly:* Evidencia de que un router barato toma bien la decisión fuerte/débil — pero nótese que **solo elige qué modelo, nunca cómo dividir la tarea**; no debe confundirse una capacidad con la otra.

**[DEC-44] — Small Language Models are the Future of Agentic AI.** Belcak et al. (NVIDIA). arXiv:2506.02153. https://arxiv.org/abs/2506.02153 · https://research.nvidia.com/labs/lpr/slm-agents/
Position paper arguing SLMs are "sufficiently powerful" and "inherently more suitable" for narrow, repetitive agentic subtasks, proposing heterogeneous agentic systems plus an LLM→SLM conversion algorithm.
*Key figures:* ⚠️ Explicitly a discussion piece, **not a benchmark study**.
*Relevancia Swarmbly:* Apoyo conceptual (no empírico) a la arquitectura de modelo pequeño local de Swarmbly; debe citarse como opinión informada, no como evidencia.

**[DEC-45] — PlanBench** (arXiv:2206.10498) **and "On the Planning Abilities of LLMs (A Critical Investigation)"** (arXiv:2302.06706). Valmeekam, Kambhampati et al. https://arxiv.org/abs/2206.10498 · https://arxiv.org/abs/2302.06706
The foundational skeptical results on autonomous LLM planning; PlanBench is the extensible benchmark for plan generation, cost-optimal planning, replanning and reasoning about change.
*Key figures:* Establishes that LLM planning ability is far below what agentic architectures assume.
*Relevancia Swarmbly:* Base de la advertencia de que el planificador/fragmentador de Swarmbly es la parte más frágil del diseño.

**[DEC-46] ⭐ — On the Limits of Innate Planning in Large Language Models.** Schepanowski & Ling (Western University). arXiv:2511.21591 (Nov 2025). https://arxiv.org/html/2511.21591v1
8-puzzle without a code interpreter across four models (GPT-5-Thinking, Gemini-2.5-Pro, GPT-5-mini, Llama 3.1 8B-Instruct).
*Key figures:* **GPT-5-Thinking 30%** with Algorithm-of-Thought; **the others near 0–2%**. With suggestive feedback GPT-5-Thinking reaches **68%** but needs ~2 attempts, **24 minutes**, 2× the moves and **75,000 tokens**. With an external validator supplying only valid moves, **no model solved any puzzle**; GPT-5-Thinking looped in **100%** of validator trials, Gemini-2.5-Pro in **92%**. GPT-5-mini made ~47 valid moves for ~6 moves of progress.
*Relevancia Swarmbly:* La cifra de **Llama-3.1-8B ≈ 0–2%** es el dato disponible más cercano a la capacidad de planificación innata de un modelo de clase 8B — es decir, del ensamblador/planificador local que Swarmbly propone.

## 4.9 Similitud semántica para fusionar texto

**[DEC-47] — Sentence-BERT (SBERT).** arXiv:1908.10084 (EMNLP-IJCNLP 2019). https://arxiv.org/abs/1908.10084 · https://sbert.net/
Siamese/triplet fine-tuning of BERT so that **cosine similarity over pooled sentence vectors** becomes meaningful.
*Key figures:* Finding the most similar pair among 10,000 sentences drops from **~50M inference computations (~65 hours) to ~5 seconds**, "maintaining the accuracy from BERT".
*Relevancia Swarmbly:* Es la base práctica del paso de deduplicación/fusión semántica local de Swarmbly, y su cifra de coste justifica hacerlo en el cliente.

**[DEC-48] — E5 / GTE / BGE (modern contrastive embedding families).** E5: *Text Embeddings by Weakly-Supervised Contrastive Pre-training*, arXiv:2212.03533 (Microsoft) · GTE: *Towards General Text Embeddings with Multi-stage Contrastive Learning*, arXiv:2308.03281 (Alibaba) · BGE / C-Pack: *C-Pack: Packed Resources for General Chinese Embeddings*, arXiv:2309.07597 (BAAI). https://arxiv.org/abs/2212.03533 · https://arxiv.org/abs/2308.03281 · https://arxiv.org/abs/2309.07597
The default open-weight choices for a local semantic-merge step, all trained with in-batch contrastive objectives whose geometry is what makes cosine usable at all.
*Key figures:* Three independent families; all open-weight; all contrastively trained.
*Relevancia Swarmbly:* Candidatos concretos para el embedder local de Swarmbly, con la advertencia de `DEC-49`–`DEC-51` sobre la portabilidad de los umbrales.

**[DEC-49] — MTEB — Massive Text Embedding Benchmark.** arXiv:2210.07316 (EACL 2023). https://arxiv.org/abs/2210.07316 · https://github.com/embeddings-benchmark/mteb
*Key figures:* **8 task types, 58 datasets, 112 languages, 33 models benchmarked.** Headline finding: **"no particular text embedding method dominates across all tasks."**
*Relevancia Swarmbly:* Implicación operativa: el embedding elegido por calidad de recuperación **no** es automáticamente el correcto para detección de casi-duplicados o fusión por redundancia; son tipos de tarea distintos con líderes distintos.

**[DEC-50] ⭐ — Is Cosine-Similarity of Embeddings Really About Similarity?** Steck et al. (Netflix). arXiv:2403.05440 (WWW '24 companion). https://arxiv.org/abs/2403.05440 · https://research.netflix.com/publication/is-cosine-similarity-of-embeddings-really-about-similarity
Analytically derives, in regularized linear matrix-factorization models with closed-form solutions, that **cosine similarity can be non-unique and "arbitrary and therefore meaningless"**, with the answer implicitly determined by the regularization scheme rather than by semantics.
*Key figures:* In deep models, multiple regularizations combine with "implicit and unintended effects when taking cosine-similarities of the resulting embeddings, rendering results opaque and possibly arbitrary." Recommends against blind use and outlines alternatives (training against the similarity objective directly, or unnormalized dot products).
*Relevancia Swarmbly:* Socava la base teórica de cualquier lógica de fusión basada en coseno; Swarmbly debe calibrar empíricamente o entrenar contra el objetivo, no asumir que el coseno mide similitud.

**[DEC-51] — Anisotropy of contextual embedding space.** Ethayarajh. arXiv:1909.00512 / ACL D19-1006. https://arxiv.org/abs/1909.00512
Shows BERT/ELMo/GPT-2 contextual representations occupy a **narrow anisotropic cone**, so *random* words already have high average cosine similarity.
*Key figures:* Raw cosine values are inflated and **not comparable across models or layers** without correction.
*Relevancia Swarmbly:* Explica por qué un umbral absoluto de coseno (p. ej. "0.85 = duplicado") **no es portable** entre modelos, un error que Swarmbly cometería por defecto.

**[DEC-52] — sentence-transformers official guidance on thresholds.** https://sbert.net/examples/sentence_transformer/applications/paraphrase-mining/README.html · https://sbert.net/docs/sentence_transformer/usage/semantic_textual_similarity.html
The library's own documentation, the closest thing to an official practice standard.
*Key figures:* `paraphrase_mining()` defaults: `query_chunk_size=5000`, `corpus_chunk_size=100000`, `top_k=100`, `max_pairs=500000`, cosine as the default score function. **The documentation specifies no recommended similarity cutoff**, and warns of asymmetry: "If B is the most similar sentence for A, A is not necessarily the most similar sentence for B."
*Relevancia Swarmbly:* Estado honesto de la práctica: **no existe umbral canónico**; cualquier número (0.7 / 0.8 / 0.85) que Swarmbly publique es un artefacto de calibración por modelo y por corpus, y debe declararse como tal.

---

# 5. [GEN] — Teoría de ensamblado genómico y su transferencia a texto

## 5.1 Estadística de cobertura de Lander–Waterman

**[GEN-01] ⭐ — Lander & Waterman (1988): *Genomic mapping by fingerprinting random clones: a mathematical analysis*.** *Genomics* 2(2):231–239. **DOI: 10.1016/0888-7543(88)90007-9**. https://doi.org/10.1016/0888-7543(88)90007-9 · https://pubmed.ncbi.nlm.nih.gov/3294162/ · Full-text PDF (Waterman's own archive): https://dornsife.usc.edu/msw/wp-content/uploads/sites/236/2023/09/msw-081.pdf
The founding paper of coverage statistics. It models clones as randomly-placed intervals on a genome and derives closed forms for the number and size of contiguous assembled regions ("islands"). It is the formal engine of the Swarmbly metaphor — and, read correctly, an argument that reconstruction from fragments is *easy*, not hard.

**Variables (verbatim from the paper):**

| Symbol | Definition |
|---|---|
| $G$ | haploid genome length in bp |
| $L$ | length of clone insert in bp |
| $N$ | number of clones fingerprinted |
| $\alpha = N/G$ | probability per base of starting a new clone |
| $T$ | amount of overlap in bp needed to detect overlap |
| $\theta = T/L$ | minimum detectable overlap, as a fraction of clone length |
| $\sigma = 1 - \theta$ | "effective" non-overlapping fraction |
| $c = LN/G$ | **redundancy of coverage** |

**Fórmulas (preservadas verbatim en LaTeX):**

$$c \;=\; \frac{LN}{G} \qquad\text{(expected coverage / redundancy)}$$

$$P(\text{a given base is not covered by any clone}) \;=\; e^{-c}$$

$$E[\text{bases not covered}] \;=\; G\,e^{-c}$$

$$E[\#\text{ apparent islands}] \;=\; N e^{-c\theta}$$

$$E[\#\text{ islands consisting of exactly } j \text{ clones}] \;=\; N e^{-2c\theta}\left(1 - e^{-c\theta}\right)^{j-1}$$

$$E[\#\text{ clones per island}] \;=\; e^{c\theta}$$

$$E[\text{island length in bp}] \;=\; L\left[\frac{e^{c\theta} - 1}{c} + (1-\sigma)\right]$$

$$P(\text{an "ocean" (gap) is real, not an undetected overlap}) \;=\; e^{-c\theta}$$

⚠️ **Verification note (carried forward verbatim):** the $\theta$-parameterised island count $Ne^{-c\theta}$, clones-per-island $e^{c\theta}$, and island-length formula were confirmed against two independent renderings of the paper. The *exactly-$j$-clones* formula appeared in one rendering with an additional leading factor $\sigma$ (i.e. $Ne^{-2c\theta}\sigma(1-e^{-c\theta})^{j-1}$). The form given above (without $\sigma$) is the one usually cited downstream. **Check page 233 of the PDF before publishing this specific formula.**

*Key figures:* Special case $\theta \to 0$ (any overlap detectable) recovers the textbook forms: $E[\#\text{contigs}] = Ne^{-c}$ and uncovered fraction $= e^{-c}$. This is why **"8× coverage"** is a rule of thumb: $e^{-8} \approx \mathbf{0.034\%}$ of bases uncovered. Design guidance from the paper: decreasing $\theta$ from **0.50 to 0.25** sharply accelerates map completion; further reduction yields diminishing returns; the authors suggest **$\theta \approx 0.15$–$0.20$** as the practical target.
*Relevancia Swarmbly:* Aporta el vocabulario cuantitativo del proyecto (cobertura, islas, océanos) y, simultáneamente, su contraargumento más fuerte: con $c=8$ solo el 0.034% del origen queda sin ver, de modo que un adversario que recolecte fragmentos con redundancia modesta alcanza cobertura casi total.

**[GEN-02] — Lander & Waterman lecture treatment** (Istrail, Brown CSCI 1810). https://cs.brown.edu/courses/csci1810/fall-2024/lectures/final_ppt_2.pdf
Clean pedagogical derivation of `GEN-01`.
*Key figures:* Useful specifically for citing the $\theta=0$ simplifications without relying on the paywalled original.
*Relevancia Swarmbly:* Fuente docente accesible para el anexo matemático del whitepaper.

**[GEN-03] — Arratia, Lander, Tavaré & Waterman (1991): *Genomic mapping by anchoring random clones*.** https://www.sciencedirect.com/science/article/abs/pii/088875439190004X · Related: *Genomic mapping by end-characterized random clones* (1995), https://pubmed.ncbi.nlm.nih.gov/7782090/
Extends the 1988 model to anchored / end-characterised clones.
*Key figures:* The companion result set for mate-pair-era planning.
*Relevancia Swarmbly:* Análogo formal de "fragmentos con metadatos de posición", es decir, del caso en que Swarmbly adjunta índices de orden a cada micro-prompt — y por tanto del caso en que el reensamblado es aún más fácil para un adversario.

## 5.2 Overlap–Layout–Consensus (OLC)

**[GEN-04] — Myers et al. (2000): *A Whole-Genome Assembly of Drosophila*.** *Science* 287(5461):2196–2204. **DOI: 10.1126/science.287.5461.2196**. https://doi.org/10.1126/science.287.5461.2196 · PDF: https://publications.mpi-cbg.de/Myers_2000_5378.pdf
The paper that proved whole-genome shotgun plus OLC works at eukaryotic scale, establishing the overlap → unitig → scaffold pipeline that became the Celera Assembler.
*Key figures:* First eukaryotic-scale WGS assembly.
*Relevancia Swarmbly:* Precedente histórico del "shotgun" que da nombre a la metáfora de Swarmbly, y fuente del pipeline de tres etapas que el proyecto reutiliza como vocabulario.

**[GEN-05] — Myers (2005): *The fragment assembly string graph*.** *Bioinformatics* 21(suppl_2):ii79–ii85. **DOI: 10.1093/bioinformatics/bti1114**. https://doi.org/10.1093/bioinformatics/bti1114 · https://pubmed.ncbi.nlm.nih.gov/16204131/ · PDF: https://publications.mpi-cbg.de/Myers_2005_5447.pdf
Reformulates OLC by removing all *transitively inferable* overlap edges, leaving a compact "string graph" on which assembly becomes path-finding. The theoretical core of modern long-read OLC assemblers (SGA, Falcon, HiFiasm, Canu).
*Key figures:* The naive overlap step is **$O(N^2)$** pairwise comparisons over $N$ reads — the dominant practical cost of OLC and the reason de Bruijn methods displaced it for short reads. Transitive reduction reduces the *graph*, not the *overlap discovery*.
*Relevancia Swarmbly:* El coste $O(N^2)$ del descubrimiento de solapamientos es la cota computacional que enfrentaría el reensamblador de Swarmbly si intentara reconstruir por solapamiento en lugar de por índices explícitos.

**[GEN-06] — Medvedev, Georgiou, Myers & Brudno (2007): *Computability of Models for Sequence Assembly*.** WABI 2007, LNCS 4645. **DOI: 10.1007/978-3-540-74126-8_27**. https://link.springer.com/chapter/10.1007/978-3-540-74126-8_27 · PDF: https://publications.mpi-cbg.de/Medvedev_2007_6364.pdf
Formalises assembly objectives and proves hardness.
*Key figures:* Assembly under realistic models is **NP-hard**; the classical Shortest Common Superstring formulation is both **NP-hard and biologically wrong** (it over-collapses repeats).
*Relevancia Swarmbly:* Es la base formal para afirmar que el reensamblado óptimo es intratable — pero también la advertencia de que la formulación SCS "colapsa repeticiones", error análogo al que cometería Swarmbly al deduplicar fragmentos parecidos.

**[GEN-07] ⚠️ — Phase transition in the computational complexity of the shortest common superstring and genome assembly.** https://www.researchgate.net/publication/364422228_Phase_transition_in_the_computational_complexity_of_the_shortest_common_superstring_and_genome_assembly
Shows the SCS/assembly problem exhibits an easy–hard phase transition as a function of coverage and repeat structure.
*Key figures:* ⚠️ **Verify the final published venue/DOI before citing.**
*Relevancia Swarmbly:* Directamente relevante para "¿cuándo más datos hacen tratable la reconstrucción?", pregunta que Swarmbly debe responder tanto para su ensamblador como para su modelo de adversario.

**[GEN-08] — Quantum Algorithms for the Shortest Common Superstring and Text Assembling Problems.** Khadiev & Safina. *Quantum Information and Computation* 24(3-4), 267–294 (2024). DOI 10.26421/QIC24.3-4-2. Preprint arXiv:2306.10572. https://arxiv.org/abs/2306.10572
Notable because it explicitly treats *text assembling* as the same formal object as SCS / genome assembly.
*Key figures:* Establishes the shared formal substrate between genome assembly and text reconstruction.
*Relevancia Swarmbly:* Es la mejor cita para la afirmación de que ensamblado genómico y ensamblado de texto son el mismo problema formal — el único puente académico legítimo de la metáfora del proyecto.

## 5.3 Ensamblado por grafos de De Bruijn

**[GEN-09] ⭐ — Pevzner, Tang & Waterman (2001): *An Eulerian path approach to DNA fragment assembly*.** *PNAS* 98(17):9748–9753. **DOI: 10.1073/pnas.171285098**. https://doi.org/10.1073/pnas.171285098 · https://pubmed.ncbi.nlm.nih.gov/11504945/ · PDF: https://cs.brown.edu/courses/csci1820/spring-2026/resources/ch2/Pevzner_2001.pdf
The pivot from OLC to de Bruijn graphs: reads are shredded into $k$-mers, $k$-mers become edges, and assembly becomes an Eulerian path problem, solvable in linear time unlike the Hamiltonian formulation of OLC.
*Key figures:* **Key structural fact:** a repeat longer than $k$ collapses into a single node/edge, creating a branch point; the Eulerian path is then **not unique**, and the number of valid reconstructions grows combinatorially with repeat count. This is the formal statement of "repeats break assembly."
*Relevancia Swarmbly:* Es la única parte de la teoría de ensamblado que ofrece **algún** obstáculo a la reconstrucción adversarial — la ambigüedad por repeticiones — y por tanto el punto exacto donde Swarmbly debe argumentar (y donde el argumento falla, porque el lenguaje natural es poco repetitivo y el adversario tiene un LM como prior).

**[GEN-10] — Zerbino & Birney (2008): *Velvet: algorithms for de novo short read assembly using de Bruijn graphs*.** *Genome Research* 18(5):821–829. **DOI: 10.1101/gr.074492.107**. https://genome.cshlp.org/content/18/5/821.long · https://pubmed.ncbi.nlm.nih.gov/18349386/ · https://github.com/dzerbino/velvet
The first widely-used short-read de Bruijn assembler.
*Key figures:* Introduced the practical error-correction heuristics: **tips** (dead-end removal), **bubbles** (Tour Bus algorithm, collapsing near-identical divergent paths), and low-coverage edge removal.
*Relevancia Swarmbly:* "Burbujas" y "puntas" son exactamente los artefactos que produciría un conjunto de fragmentos de texto casi idénticos devueltos por nodos redundantes; Velvet aporta el vocabulario y las heurísticas de limpieza.

**[GEN-11] — Bankevich et al. (2012): *SPAdes: A New Genome Assembly Algorithm and Its Applications to Single-Cell Sequencing*.** *J. Comput. Biol.* 19(5):455–477. **DOI: 10.1089/cmb.2012.0021**. https://doi.org/10.1089/cmb.2012.0021 · https://pubmed.ncbi.nlm.nih.gov/22506599/ · Open PDF: https://europepmc.org/api/getPdf?pmcid=PMC3342519
Introduced the **multisized de Bruijn graph**, using several $k$ values simultaneously so that small $k$ supplies connectivity in low-coverage regions while large $k$ resolves repeats. Still the default bacterial/single-cell assembler.
*Key figures:* Multi-$k$ construction is the standard answer to the $k$-selection tradeoff of `GEN-12`.
*Relevancia Swarmbly:* Sugiere directamente una estrategia de **fragmentación multi-escala** para Swarmbly: emitir micro-prompts de varios tamaños simultáneamente en lugar de elegir uno.

**[GEN-12] ⭐ — Chikhi & Medvedev (2014): *Informed and automated k-mer size selection for genome assembly* (KmerGenie).** *Bioinformatics* 30(1):31–37. **DOI: 10.1093/bioinformatics/btt310** · arXiv:1304.5665. https://academic.oup.com/bioinformatics/article/30/1/31/235479 · https://arxiv.org/abs/1304.5665
The canonical statement of the $k$-mer size tradeoff.
*Key figures:* **Small $k$**: "the more likely it is (i) to appear in the reads" — better graph coverage, tolerant of sequencing error, but *increases apparent repetitiveness*, tangling the graph. **Large $k$**: "Repeats longer than $k$ nucleotides can tangle the graph and break-up contigs; thus, a large value of $k$ is desired", but "the longer the $k$ the higher the chances that a $k$-mer will have an error in it", and coverage gaps appear when reads overlap by fewer than $k$ characters. Empirical: *S. aureus* best NG50 **19.4 kb** at $k=31$; *B. impatiens* best NG50 **10.4 kb** at $k=51$; human chr14 at $k=71$ gave **431 errors** vs **843 errors** at $k=41$.
*Relevancia Swarmbly:* Es el "no free lunch" central de toda reconstrucción por fragmentos: **el tamaño del fragmento intercambia robustez frente a errores contra resolución de ambigüedad, y no existe un ajuste que gane en ambos** — resultado que se transfiere directamente al tamaño del micro-prompt de Swarmbly.

**[GEN-13] — Integration of string and de Bruijn graphs for genome assembly.** https://academic.oup.com/bioinformatics/article/32/9/1301/1744507
Hybrid formalism reconciling the two paradigms.
*Key figures:* Shows the two graph families are complementary rather than exclusive.
*Relevancia Swarmbly:* Precedente de arquitectura híbrida, útil si Swarmbly combina reensamblado por índices (string-graph-like) con deduplicación por similitud ($k$-mer-like).

## 5.4 Scaffolding

**[GEN-14] — Boetzer et al. (2011): *Scaffolding pre-assembled contigs using SSPACE*.** *Bioinformatics* 27(4):578–579. **DOI: 10.1093/bioinformatics/btq683**. https://doi.org/10.1093/bioinformatics/btq683 · https://pubmed.ncbi.nlm.nih.gov/21149342/
The reference stand-alone scaffolder: uses paired-end/mate-pair reads whose two ends map to different contigs to infer order, orientation and gap size.
*Key figures:* Establishes order + orientation + gap-size inference as the three scaffolding outputs.
*Relevancia Swarmbly:* Modelo directo del paso de "ordenar y orientar" los fragmentos devueltos, incluyendo la estimación explícita de huecos — que Swarmbly debería reportar en lugar de ocultar.

**[GEN-15] — On a greedy approach for genome scaffolding (2022).** *Algorithms for Molecular Biology*. **DOI: 10.1186/s13015-022-00223-x**. https://link.springer.com/article/10.1186/s13015-022-00223-x · https://pmc.ncbi.nlm.nih.gov/articles/PMC9617463/
Modern complexity treatment of scaffolding as a graph optimisation problem; confirms hardness and analyses greedy approximation quality.
*Key figures:* Confirms NP-hardness and characterises the quality of greedy approximations.
*Relevancia Swarmbly:* Justifica que el reensamblador de Swarmbly será heurístico por necesidad matemática, no por falta de ingeniería.

**[GEN-16] — *Producing Genomic Sequences after Genome Scaffolding with Ambiguous Paths: Complexity, Approximation and Lower Bounds*.** *Algorithmica*. **DOI: 10.1007/s00453-021-00819-6**. https://link.springer.com/article/10.1007/s00453-021-00819-6
NP-hardness, inapproximability bounds and lower bounds for the sequence-production step *after* scaffolding.
*Key figures:* Inapproximability results for the post-scaffolding sequence emission problem.
*Relevancia Swarmbly:* Cota teórica sobre la fase final de emisión de texto ensamblado: incluso con el orden correcto, producir la secuencia final es duro de aproximar.

**[GEN-17] — Using the longest run subsequence problem within homology-based scaffolding.** https://link.springer.com/article/10.1186/s13015-021-00191-8
An additional complexity result in the scaffolding family.
*Key figures:* Frames a scaffolding subproblem as longest-run-subsequence.
*Relevancia Swarmbly:* Complemento formal del bloque de scaffolding; útil solo en el anexo teórico.

> **Resumen del panorama de complejidad (`GEN-14`…`GEN-17`):** scaffolding se plantea estándarmente como maximizar un conjunto ponderado de restricciones de enlace satisfechas sujeto a un ordenamiento lineal — una variante de cobertura de caminos de peso máximo / disposición lineal, que es NP-difícil. Todos los scaffolders prácticos son voraces o heurísticos. **No existe algoritmo en tiempo polinómico que garantice el scaffold correcto.**

## 5.5 Límites conocidos: repeticiones, quimeras, ensamblados erróneos

**[GEN-18] — Nagarajan & Pop (2013): *Sequence assembly demystified*.** *Nature Reviews Genetics* 14:157–167. **DOI: 10.1038/nrg3367**. https://www.nature.com/articles/nrg3367 · https://pubmed.ncbi.nlm.nih.gov/23358380/
The best single review of why assembly is hard.
*Key figures:* **Repeats, not coverage, are the binding constraint.**
*Relevancia Swarmbly:* Cita de cabecera para la afirmación de que más cobertura (más redundancia de fragmentos) no resuelve la ambigüedad estructural — ni para Swarmbly ni para su adversario.

**[GEN-19] — Kingsford, Schatz & Pop (2010): *Assembly complexity of prokaryotic genomes using short reads*.** *BMC Bioinformatics* 11:21. **DOI: 10.1186/1471-2105-11-21**. https://bmcbioinformatics.biomedcentral.com/articles/10.1186/1471-2105-11-21 · https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2821320/
Quantifies, per genome, how much of a bacterial genome is *theoretically* unresolvable at a given read length, independent of coverage.
*Key figures:* Demonstrates that repeat structure imposes a **hard ceiling** unrelated to sequencing depth.
*Relevancia Swarmbly:* Modelo formal de "hay información que ninguna cantidad de fragmentos recupera", el único mecanismo por el que la fragmentación podría ofrecer protección — y que el lenguaje natural no satisface.

**[GEN-20] — Read Length and Repeat Resolution: Exploring Prokaryote Genomes Using NGS.** *PLOS ONE*. https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0011518
Companion empirical study on the read-length / repeat-resolution frontier.
*Key figures:* Empirically maps the frontier between read length and resolvable repeats.
*Relevancia Swarmbly:* Evidencia empírica de la relación tamaño-de-fragmento ↔ ambigüedad, trasladable al dimensionado de micro-prompts.

**[GEN-21] ⭐ — Gurevich et al. (2013): *QUAST: quality assessment tool for genome assemblies*.** *Bioinformatics* 29(8):1072–1075. **DOI: 10.1093/bioinformatics/btt086**. https://doi.org/10.1093/bioinformatics/btt086 · https://pubmed.ncbi.nlm.nih.gov/23422339/ · Manual: https://quast.sourceforge.net/docs/manual.html
The standard misassembly-metric framework, and the formal answer to "how do you know your reconstruction is wrong?"
*Key figures (verbatim from the manual):* **Relocation** — "The left flanking sequence aligns over 1 kbp away from the right flanking sequence on the reference genome, or they overlap by more than 1 kbp, and both flanking sequences align on the same chromosome." **Translocation** — "where the flanking sequences align on different chromosomes." **Inversion** — "where the flanking sequences align on opposite strands of the same chromosome." Default extensive-misassembly threshold: **1 kbp** (QUAST), **7 kbp** (QUAST-LG), tunable via `--extensive-mis-size`. **Local misassembly** — "The gap or overlap between left and right flanking sequences is less than 1 kbp, and larger than 200 bp (the maximum indel length)", same strand and chromosome, tunable via `--local-mis-size`. **NA50 / NGA50** — N50/NG50 computed over *aligned blocks*, where "Aligned blocks are obtained by breaking contigs at misassembly events and removing all unaligned bases." **# misassembled contigs** = "The number of contigs that contain misassembly events."
*Relevancia Swarmbly:* Es el ítem más transferible de toda la mitad genómica: **N50 (contigüidad) puede ser alto mientras NGA50 (corrección) es mucho más bajo** — contigüidad y corrección son ejes distintos, y un ensamblado puede parecer completo y ser estructuralmente falso. Swarmbly debe adoptar esta distinción para evaluar su propio reensamblado.

**[GEN-22] — Genetic variation and the de novo assembly of human genomes.** Chaisson, Wilson & Eichler. *Nature Reviews Genetics*. **DOI: 10.1038/nrg3933**. https://www.nature.com/articles/nrg3933
Documents how heterozygosity and segmental duplication produce chimeric and collapsed contigs in real human assemblies.
*Key figures:* Chimeras and collapses are the empirical failure modes at real genome scale.
*Relevancia Swarmbly:* Análogo directo de las "quimeras" que produciría Swarmbly al fusionar fragmentos de nodos que respondieron con estilos o contenidos divergentes.

**[GEN-23] — Metagenomic assembly through the lens of validation.** https://pubmed.ncbi.nlm.nih.gov/28968737/
Survey of chimera formation and validation methods when the source is a *mixture* of genomes.
*Key figures:* The closest biological analogue to assembling fragments produced by many independent sources.
*Relevancia Swarmbly:* El caso metagenómico — muchas fuentes independientes mezcladas — es el modelo formal más fiel al enjambre de voluntarios de Swarmbly.

**[GEN-24] — Current challenges and solutions of de novo assembly.** *Quantitative Biology*, 2019. https://link.springer.com/article/10.1007/s40484-019-0166-9
Recent survey consolidating the repeat / chimera / misassembly failure taxonomy.
*Key figures:* Consolidated failure taxonomy.
*Relevancia Swarmbly:* Cita de encuadre para el anexo de modos de fallo del reensamblador.

## 5.6 Transferencia del ensamblado genómico a NLP / texto / cómputo distribuido

> **EVALUACIÓN HONESTA (preservada del dossier):** esta literatura es delgada hasta casi inexistente como programa de investigación coherente. No se encontró ningún cuerpo establecido de trabajo que transfiera OLC, De Bruijn o Lander–Waterman a NLP *como método*. Lo que existe cae en tres categorías débiles.

**[GEN-25] — Sustrato formal compartido (real, pero no una "transferencia").** See `GEN-08` (arXiv:2306.10572). https://arxiv.org/abs/2306.10572
Genome assembly and text assembly are both instances of Shortest Common Superstring / sequence reconstruction. This is a shared *problem statement*, not a transferred algorithm.
*Key figures:* Best available citation for the shared substrate; no transferred algorithm exists.
*Relevancia Swarmbly:* Delimita exactamente hasta dónde puede llegar la metáfora del proyecto sin cometer un error de categoría.

**[GEN-26] ⚠️ — Reconstructing Textual Documents from n-grams.** https://www.researchgate.net/publication/299973607_Reconstructing_Textual_Documents_from_n-grams
The nearest genuine analogue: reconstructing documents from released n-gram counts. It is simultaneously an assembly result and a privacy attack.
*Key figures:* ⚠️ **Confirm exact venue/year/DOI before citing.**
*Relevancia Swarmbly:* Doblemente relevante: valida la metáfora *y* demuestra que la reconstrucción desde fragmentos publicados es un ataque de privacidad conocido.

**[GEN-27] — Text File Recovery Using an N-Gram Model** (Springer, 2024). https://link.springer.com/chapter/10.1007/978-3-031-71025-4_11
File-carving / forensic fragment reassembly using n-gram language models — assembly-shaped, but the vocabulary is forensics, not bioinformatics.
*Key figures:* Demonstrates practical text-fragment reassembly with statistical language priors.
*Relevancia Swarmbly:* Prueba de que un modelo de lenguaje sencillo basta para reensamblar fragmentos de texto en un contexto forense — precedente directo de la capacidad del adversario.

**[GEN-28] — Distributed / HPC genome assembly (the flow is the *other* direction).** Survey: https://dl.acm.org/doi/abs/10.1007/s11227-014-1297-4 · Distributed RMI-DBG: https://www.sciencedirect.com/science/article/abs/pii/S0957417423013611 · Comparative parallel assembly: https://link.springer.com/article/10.1007/s12539-011-0062-0
The literature that exists runs from distributed computing *into* assembly, not out of it: parallel de Bruijn graph construction, distributed RMI-DBG, HPC assembly surveys.
*Key figures:* Direction of transfer is inverted relative to what Swarmbly's framing implies.
*Relevancia Swarmbly:* Advertencia editorial: el proyecto no puede reclamar linaje de una transferencia que en la literatura ocurre en sentido contrario.

**[GEN-29] ⚠️ — De Bruijn Graph Networks for genome reconstruction (2025 preprint).** https://www.preprints.org/manuscript/202510.1966
ML applied *to* assembly (GNNs on de Bruijn graphs) — again the reverse direction.
*Key figures:* ⚠️ **Preprint, not peer-reviewed.**
*Relevancia Swarmbly:* Confirma que el flujo ML↔ensamblado es de ML hacia biología, no al revés.

> **Conclusión para el proyecto (preservada del dossier):** el encuadre de ensamblado genómico debe presentarse como **metáfora y vocabulario de diseño**, no como herencia de resultados probados. No existe prior art que establezca que los algoritmos de ensamblado confieran propiedad alguna — y menos una propiedad de seguridad — al aplicarse a texto. Reclamar linaje de Lander–Waterman sería un error de categoría: **LW es un modelo de cuántos fragmentos hacen falta para *lograr* la reconstrucción. Es un argumento de que reconstruir es *fácil*, no de que sea difícil.**

---

# 6. [PRIV] — Privacidad de datos fragmentados y cómputo distribuido seguro

## 6.1 Secreto compartido y MPC para inferencia de redes neuronales

**[PRIV-01] ⭐ — Shamir (1979): *How to Share a Secret*.** *Commun. ACM* 22(11):612–613. **DOI: 10.1145/359168.359176**. https://doi.org/10.1145/359168.359176 · https://cacm.acm.org/research/how-to-share-a-secret/ · PDF: https://web.mit.edu/6.857/OldStuff/Fall03/ref/Shamir-HowToShareASecret.pdf
The $(k,n)$ threshold scheme: splits a secret $S$ into $n$ shares via a random degree-$(k-1)$ polynomial over a finite field with $f(0)=S$.
*Key figures:* Any $k$ shares reconstruct $S$, and **any $k-1$ shares reveal information-theoretically nothing** — all values of $S$ remain equally likely. Shares are *uniformly random field elements*, statistically independent of the secret.
*Relevancia Swarmbly:* Es la entrada que decide todo el argumento de privacidad: los fragmentos de lenguaje natural **no** son elementos aleatorios de un cuerpo, sino subcadenas legibles con contenido semántico propio; la diferencia no es de grado, es la diferencia entre un esquema con prueba teórico-informacional y uno sin ninguna.

**[PRIV-02] — Mohassel & Rindal (2018): *ABY³: A Mixed Protocol Framework for Machine Learning*.** ACM CCS 2018. **DOI: 10.1145/3243734.3243760** · IACR ePrint 2018/403. https://dl.acm.org/doi/pdf/10.1145/3243734.3243760 · https://eprint.iacr.org/2018/403
Three-party replicated secret sharing with efficient conversions between arithmetic, binary and Yao representations.
*Key figures:* The reference 3PC design for private ML.
*Relevancia Swarmbly:* Define el estándar de "tres partes que no coluden", supuesto de confianza que una red abierta de voluntarios **no** puede garantizar.

**[PRIV-03] — Mishra et al. (2020): *Delphi: A Cryptographic Inference Service for Neural Networks*.** USENIX Security 2020 · IACR ePrint 2020/050. https://www.usenix.org/conference/usenixsecurity20/presentation/mishra · PDF: https://www.usenix.org/system/files/sec20spring_mishra_prepub.pdf
Hybrid HE + secret-sharing system that moves linear-layer cryptography to a preprocessing phase and uses a planner to replace some ReLUs with polynomial approximations.
*Key figures:* Establishes the preprocessing/online split that all later systems adopt.
*Relevancia Swarmbly:* Muestra que incluso las optimizaciones más agresivas de MPC exigen una fase de preprocesado por par de partes, inviable con nodos efímeros.

**[PRIV-04] ⚠️ — Knott et al. (2021): *CrypTen: Secure Multi-Party Computation Meets Machine Learning*.** NeurIPS 2021 · arXiv:2109.00984. https://arxiv.org/abs/2109.00984 · https://papers.neurips.cc/paper/2021/file/2754518221cfbc8d25c13a06a4cb8421-Paper.pdf · https://github.com/facebookresearch/CrypTen
PyTorch-style MPC framework (secret-sharing based, semi-honest); the practical entry point for MPC-based inference.
*Key figures:* Reported headline: two parties "can securely predict phonemes in speech recordings using Wav2Letter faster than real-time." ⚠️ **The abstract does not state a slowdown factor; per-layer slowdowns are in the full paper's tables, not the abstract** — pull exact numbers if needed.
*Relevancia Swarmbly:* Punto de entrada práctico si Swarmbly quisiera prototipar MPC, con la advertencia de que su cifra publicitada no es un factor de ralentización.

**[PRIV-05] ⭐ — Keller (2020): *MP-SPDZ: A Versatile Framework for Multi-Party Computation*.** ACM CCS 2020. **DOI: 10.1145/3372297.3417872** · IACR ePrint 2020/521. https://dl.acm.org/doi/10.1145/3372297.3417872 · https://eprint.iacr.org/2020/521 · https://github.com/data61/MP-SPDZ
The reference implementation covering ~30 MPC protocol variants; the standard baseline for cross-protocol benchmarking.
*Key figures:* Iron reports being **65–107× faster than MP-SPDZ** in runtime and **642–652× lower in communication** for transformer inference. Since Iron itself takes **~475 s** for one BERT-Base inference (`PRIW`/`PRIV-09`), general-purpose MPC on a transformer is in the **hours-per-inference** range. Against a plaintext BERT-Base inference of order **10 ms on a GPU**, this is a slowdown of roughly **10⁴–10⁶×**.
*Relevancia Swarmbly:* Fija el orden de magnitud del coste de la criptografía genérica (10⁴–10⁶×), la cifra que hace insostenible cualquier afirmación de confidencialidad a coste cero.

**[PRIV-06] — Dong et al. (2023): *PUMA: Secure Inference of LLaMA-7B in Five Minutes*.** arXiv:2307.12533. https://arxiv.org/abs/2307.12533
3PC secure inference for LLMs; best-in-class for its setting.
*Key figures:* **LLaMA-7B in ~5 minutes**; also reports **33.91 s** for BERT-Base (RTE).
*Relevancia Swarmbly:* Es el mejor caso publicado de inferencia LLM criptográficamente segura, y sigue siendo ~5 minutos por inferencia con tres partes que no coluden.

## 6.2 Cifrado homomórfico para inferencia de transformers

**[PRIV-07] — Cheon, Kim, Kim & Song (2017): *Homomorphic Encryption for Arithmetic of Approximate Numbers* (CKKS).** ASIACRYPT 2017. **DOI: 10.1007/978-3-319-70694-8_15** · IACR ePrint 2016/421. https://link.springer.com/chapter/10.1007/978-3-319-70694-8_15 · https://eprint.iacr.org/2016/421
The approximate-arithmetic FHE scheme that makes encrypted neural network inference conceivable, supporting SIMD-packed approximate real arithmetic with rescaling.
*Key figures:* Foundational scheme underlying every HE transformer system below.
*Relevancia Swarmbly:* Referencia obligada si el whitepaper menciona FHE, aunque sea para descartarlo.

**[PRIV-08] — Chen et al. (2022): *THE-X: Privacy-Preserving Transformer Inference with Homomorphic Encryption*.** Findings of ACL 2022 · arXiv:2206.00216. https://aclanthology.org/2022.findings-acl.277/ · https://arxiv.org/abs/2206.00216
Replaces HE-unfriendly transformer ops (GELU, softmax, LayerNorm) with HE-computable approximations.
*Key figures:* **Reported accuracy drop up to 4.44% on STS-B** (per the private-inference survey `PRIV-12`) — it buys latency with accuracy.
*Relevancia Swarmbly:* Demuestra que incluso pagando el coste de FHE hay que ceder precisión, un doble impuesto que Swarmbly debe citar al comparar alternativas.

**[PRIV-09] ⭐ — Hao et al. (2022): *Iron: Private Inference on Transformers*.** NeurIPS 2022. https://proceedings.neurips.cc/paper_files/paper/2022/file/64e2449d74f84e5b1a5c96ba7b3d308e-Paper-Conference.pdf
HE + MPC hybrid; the first end-to-end private transformer inference system.
*Key figures:* **3.3–11.83× faster than SIRNN**, **3.47–14.11× lower communication**; **65–107× faster than MP-SPDZ** with **642–652×** less communication; accuracy loss "does not exceed **0.3%**". For BERT-Tiny, **84%** of runtime is non-linear layers (softmax, GELU, LayerNorm) and only ~16% is matmul. **Total communication for one BERT-Base inference: 280.99 GB.**
*Relevancia Swarmbly:* Los **280.99 GB por una sola inferencia de BERT-Base** son la cifra más contundente para demostrar que la criptografía real es incompatible con enlaces domésticos.

**[PRIV-10] ⭐ — Pang et al. (2024): *BOLT: Privacy-Preserving, Accurate and Efficient Inference for Transformers*.** IEEE S&P (Oakland) 2024. **DOI: 10.1109/SP54263.2024.00130** · IACR ePrint 2023/1893. https://ieeexplore.ieee.org/document/10646705/ · https://eprint.iacr.org/2023/1893 · PDF: https://encrypto.de/papers/PZMZS24.pdf
State-of-the-art 2PC private transformer inference with word-elimination optimizations, benchmarked on both LAN and WAN.
*Key figures (BERT-Base, one inference):*

| Setting | Latency | Communication |
|---|---|---|
| LAN (3 Gbps, 0.8 ms), no word elimination | **~91 s** | **59.61 GB** |
| LAN, with word elimination | **~53 s** | **25.74 GB** |
| WAN (100 Mbps, 40 ms), no WE | **~1,343 s** (22 min) | — |
| WAN, with WE | **~913 s** (15 min) | — |
| Iron baseline | — | **280.99 GB** |

Speedup over Iron **4.8–9.5×**; max accuracy loss **1.3%** (STS-B).
*Relevancia Swarmbly:* La degradación de **53 s en LAN a 913–1,343 s en WAN de 100 Mbps / 40 ms** demuestra que los protocolos criptográficos están limitados por la red: una red de voluntarios geodistribuida es el peor destino posible para ellos.

**[PRIV-11] — Lu et al. (2025): *BumbleBee: Secure Two-party Inference Framework for Large Transformers*.** NDSS 2025 · IACR ePrint 2023/1678. https://www.ndss-symposium.org/ndss-paper/bumblebee-secure-two-party-inference-framework-for-large-transformers/ · PDF: https://www.ndss-symposium.org/wp-content/uploads/2025-57-paper.pdf
*Key figures:* Communication reduced **80–90%** (matmul) and **80–95%** (activations); "outperforms Iron by over an order of magnitude"; **3× faster than BOLT with one-tenth the communication**. **LLaMA-7B token generation: ~8 minutes per token on CPUs.**
*Relevancia Swarmbly:* **~8 minutos por token** es la cifra individual más elocuente para cerrar el debate sobre confidencialidad criptográfica en inferencia LLM distribuida.

**[PRIV-12] ⭐ — *A Survey on Private Transformer Inference* (2024).** arXiv:2412.08145. https://arxiv.org/pdf/2412.08145
The best single consolidated comparison table; **use this as the citation of record for cross-system numbers.**
*Key figures (Table 12, BERT-Base unless noted):*

| System | Latency | Communication |
|---|---|---|
| PUMA (3PC) | **33.91 s** (RTE) | — |
| MPCFormer | **55.32 s** (QNLI) | **12.089 GB** |
| BOLT | **185 s** (SST-2) | **25.74 GB** |
| Iron | **475 s** (SST-2) | **280.99 GB** |
| NEXUS (HE-only) | **1,125 s** (SST-2) | **0.16 GB** |
| BumbleBee | **55.2 s** (GPT2-Base); **404.4 s** (BERT-Large) | — |

Accuracy losses typically **<1%**; THE-X up to **4.44%**.
*Relevancia Swarmbly:* Tabla única y citable que sustenta la conclusión central: la protección criptográfica real de la inferencia cuesta hoy **10²–10⁶×** en latencia y/o **decenas a cientos de GB** de comunicación por inferencia.

**[PRIV-13] — CipherPrune (2025): *Efficient and Scalable Private Transformer Inference*.** https://arxiv.org/html/2502.16782v1 · https://openreview.net/pdf?id=mUMvr33FTu
Recent optimisation via encrypted token pruning.
*Key figures:* Useful for the "state of the art is still slow" argument.
*Relevancia Swarmbly:* Evidencia de que la investigación sigue activa pero no ha cambiado el orden de magnitud.

**[PRIV-14] — THOR (2025): *Secure Transformer Inference with Homomorphic Encryption*.** ACM CCS 2025. **DOI: 10.1145/3719027.3765150**. https://dl.acm.org/doi/10.1145/3719027.3765150
Most recent HE-based secure transformer inference work.
*Key figures:* CCS 2025 venue; part of the ongoing HE optimisation line.
*Relevancia Swarmbly:* Completa el estado del arte 2025 de FHE para transformers en la revisión bibliográfica.

> **Nota sobre TEE:** las entradas de cómputo confidencial sobre GPU (H100 CC, Intel TDX/SGX, y el benchmark 2026) están consolidadas en `VER-11`, `VER-12` y `VER-13`, con todas sus cifras. **Síntesis:** el cómputo confidencial en GPU es la *única* tecnología hoy desplegable que da confidencialidad real a velocidad de producción — **~4–8% de sobrecarga en estado estacionario, ~20–28% en TTFT** — y es 3–5 órdenes de magnitud más barata que MPC/HE. Pero depende de una raíz de confianza en hardware y de atestación remota, que es precisamente lo que un conjunto heterogéneo de voluntarios P2P no puede aportar.

## 6.3 Por qué "trocear texto en fragmentos" NO es cifrado

**[PRIV-15] ⭐ — Sweeney (2002): *k-Anonymity: A Model for Protecting Privacy*.** *IJUFKS* 10(5):557–570. **DOI: 10.1142/S0218488502001648**. https://epic.org/wp-content/uploads/privacy/reidentification/Sweeney_Article.pdf · Independent re-estimate (Golle, 2006): https://crypto.stanford.edu/~pgolle/papers/census.pdf
Defines quasi-identifiers and k-anonymity, with the famous accompanying re-identification result.
*Key figures:* The combination of **ZIP code + birth date + gender uniquely identifies ~87% of the US population** — none of which are "identifiers" individually. **Golle (2006) revises the estimate to ~63%.**
*Relevancia Swarmbly:* Demuestra que atributos individualmente inocuos se combinan hasta la identificación única — exactamente el fallo que sufre un conjunto de micro-prompts "individualmente inofensivos".

**[PRIV-16] ⭐ — Machanavajjhala et al. (2007): *ℓ-Diversity: Privacy Beyond k-Anonymity*.** *ACM TKDD* 1(1). **DOI: 10.1145/1217299.1217302**. https://www.cs.rochester.edu/u/muthuv/ldiversity-TKDD.pdf · Follow-on (t-closeness, Li et al., ICDE 2007): https://www.cs.purdue.edu/homes/ninghui/papers/t_closeness_icde07.pdf
Shows k-anonymity is insufficient: homogeneity attacks and background-knowledge attacks break it.
*Key figures:* **Every syntactic fragmentation/generalisation defence has been broken by a subsequent attack.**
*Relevancia Swarmbly:* Es el patrón histórico con el que Swarmbly debe medirse: toda defensa sintáctica de fragmentación publicada hasta la fecha ha sido rota por un ataque posterior.

**[PRIV-17] ⭐ — Narayanan & Shmatikov (2008): *Robust De-anonymization of Large Sparse Datasets* (Netflix Prize).** IEEE S&P 2008. **DOI: 10.1109/SP.2008.33**. https://dl.acm.org/doi/10.1109/SP.2008.33 · PDF: https://www.cs.cornell.edu/~shmat/shmat_oak08netflix.pdf
De-anonymises the Netflix Prize dataset using sparse auxiliary information.
*Key figures:* Core theorem: **high-dimensional sparse data is inherently re-identifiable**; a handful of coarse, noisy attributes suffices.
*Relevancia Swarmbly:* Los conjuntos de fragmentos de prompts son datos dispersos de alta dimensión — exactamente la clase que este teorema declara re-identificable.

**[PRIV-18] ⭐ — de Montjoye et al. (2013): *Unique in the Crowd: The privacy bounds of human mobility*.** *Scientific Reports* 3:1376. **DOI: 10.1038/srep01376**. https://www.nature.com/articles/srep01376
*Key figures (verbatim):* **1.5 million individuals**, **15 months** (Apr 2006 – Jun 2007), hourly/antenna resolution. "**four spatio-temporal points are enough to uniquely identify 95% of the individuals**"; **two points identify >50%**; at most **eleven** points identify all traces. "the uniqueness of mobility traces decays approximately as the **1/10 power** of their resolution" — so **"even coarse datasets provide little anonymity."**
*Relevancia Swarmbly:* Es el análogo cuantitativo más directo a "¿cuánto ayuda realmente trocear un prompt?": degradar o fragmentar datos produce ganancia de privacidad **sublineal** frente a un coste lineal en utilidad. La respuesta es: mucho menos de lo que sugiere la intuición.

**[PRIV-19] ⭐ — Narayanan et al. (2012): *On the Feasibility of Internet-Scale Author Identification*.** IEEE S&P 2012. https://people.eecs.berkeley.edu/~dawnsong/papers/2012%20On%20the%20Feasibility%20of%20Internet-Scale%20Author%20Identification.pdf · Author's summary: https://gwern.net/doc/cs/security/2012-02-12-arvindnarayanan-iswritingstylesufficienttodeanonymizematerialonline.html
*Key figures (verbatim):* "over **2.4 million posts** taken from **100,000 blogs**—almost a billion words." Average post **305 words** (median 335). Nearest-neighbour/RLSC "is able to identify the correct blog in about **20% of cases**" among 100,000 candidates. With confidence estimation, "**increase precision from 20% to over 80% with a recall of 50%**." With three test posts, correct author in top-20 ~**35%** of the time.
*Relevancia Swarmbly:* Implicación letal: **un tramo de ~300 palabras de prosa ordinaria basta para identificar a su autor entre 100,000 candidatos con 80% de precisión al 50% de recall.** Un fragmento de prompt no es anónimo; el estilo de escritura es en sí un biométrico que sobrevive a la fragmentación.

**[PRIV-20] — Cross-domain Authorship Attribution: Blogs, Twitter Feeds, and Reddit Comments.** PETS 2016. https://petsymposium.org/2016/files/papers/Blogs,_Twitter_Feeds,_and_Reddit_Comments__Cross-domain_Authorship_Attribution.pdf
Extends attribution to *very short* spans and across platforms.
*Key figures:* Attribution survives both shortening and cross-platform domain shift.
*Relevancia Swarmbly:* Cierra la escapatoria de "los fragmentos son demasiado cortos para atribuir".

**[PRIV-21] — Forensic Authorship Analysis of Microblogging Texts (2020).** https://arxiv.org/pdf/2003.11545
Attribution on tweet-length (sub-280-character) spans.
*Key figures:* Works at sub-280-character granularity.
*Relevancia Swarmbly:* Cota inferior del tamaño de fragmento por debajo del cual la atribución de autoría sigue funcionando — muy por debajo de cualquier micro-prompt útil.

**[PRIV-22] — Shokri, Stronati, Song & Shmatikov (2017): *Membership Inference Attacks Against Machine Learning Models*.** IEEE S&P 2017. **DOI: 10.1109/SP.2017.41** · arXiv:1610.05820. https://arxiv.org/abs/1610.05820 · PDF: https://www.cs.cornell.edu/~shmat/shmat_oak17.pdf
The founding membership-inference paper: a shadow-model attack determines whether a record was in the training set from black-box query access alone.
*Key figures:* Black-box access alone suffices for membership determination.
*Relevancia Swarmbly:* Fundamenta la observación de que **la inferencia de pertenencia y de atributos opera sobre vistas parciales** — un nodo no necesita reconstruir el prompt entero para causar daño.

**[PRIV-23] — Carlini et al. (2021): *Extracting Training Data from Large Language Models*.** USENIX Security 2021. https://www.usenix.org/conference/usenixsecurity21/presentation/carlini-extracting
Verbatim extraction of memorised training sequences (including PII) from GPT-2 via black-box querying.
*Key figures:* Demonstrates verbatim memorised-sequence extraction including personal data.
*Relevancia Swarmbly:* Relevante para el riesgo de que los nodos voluntarios acumulen y exploten prompts observados como corpus de entrenamiento.

## 6.4 Inversión de prompts, embeddings y split-learning

**[PRIV-24] ⭐ — Morris, Kuleshov, Shmatikov & Rush (2023): *Text Embeddings Reveal (Almost) As Much As Text*.** EMNLP 2023 · arXiv:2310.06816. https://arxiv.org/abs/2310.06816 · https://aclanthology.org/2023.emnlp-main.765/ · https://github.com/vec2text/vec2text
The single most important citation against the "fragments/vectors are opaque" intuition.
*Key figures (abstract, verbatim):* "…a multi-step method that iteratively corrects and re-embeds text is able to **recover 92% of 32-token text inputs exactly**. We train our model to decode text embeddings from two state-of-the-art embedding models, and also show that our model can **recover important personal information (full names) from a dataset of clinical notes**."
*Relevancia Swarmbly:* Nótese la semejanza estructural con el ensamblado genómico: el método es *refinar-y-reincrustar iterativamente*, exactamente el bucle de corrección y reensamblado de un assembler. **El atacante está ejecutando un assembler**, y es más potente que el de Swarmbly porque tiene semántica.

**[PRIV-25] — Morris et al. (2023): *Language Model Inversion*.** ICLR 2024 · arXiv:2311.13647. https://arxiv.org/abs/2311.13647
Recovers prompts from next-token probability distributions.
*Key figures (Llama-2 7b):* **BLEU 59**, **token-level F1 78**, **exact prompt recovery 27%**. Works even without the full vocabulary distribution, via search-based recovery of the probability vector.
*Relevancia Swarmbly:* Si un nodo devuelve logits o distribuciones (o si el protocolo los expone para verificación), el prompt es recuperable con 27% de exactitud literal.

**[PRIV-26] — Zhang et al. (2024): *Extracting Prompts by Inverting LLM Outputs*.** EMNLP 2024. https://aclanthology.org/2024.emnlp-main.819/
Prompt recovery from generated text alone, with no access to logits.
*Key figures:* Demonstrates recovery from output text only.
*Relevancia Swarmbly:* Cierra la última escapatoria: incluso si Swarmbly solo devolviera texto generado, el prompt original es parcialmente recuperable.

**[PRIV-27] ⭐ ⚠️ — *What Does the Server See? Understanding Privacy Leakage from Large Language Models in Split Inference* (2026).** Fan, Liu, Wang & Chen. arXiv:2605.23158 (submitted 2026-05-22). https://arxiv.org/html/2605.23158
The most directly damaging published result for a "split the computation across nodes" architecture.
*Key figures:* The ActInv attack achieves "**Precision and Recall exceeding 98% across nearly all evaluated cases**", with **ROUGE-L consistently surpassing 0.96**. On Qwen3-0.6B, cutting after 2 client blocks gives **99.76% precision**; even at **7 blocks** it retains **77.74% precision**. Defences fail: with **70% activation sparsification**, precision/recall "decrease only modestly"; **Gaussian noise at variance 10⁻¹** is needed before recovery degrades substantially. Evaluated on AlpacaEval and iCliniq. ⚠️ **Recent preprint, not yet peer-reviewed — the highest-impact single claim in this half; verify carefully.**
*Relevancia Swarmbly:* Si Swarmbly distribuye activaciones en lugar de texto — el refinamiento obvio — este resultado lo destruye: **un nodo que recibe activaciones recibe el texto**, y las defensas baratas (sparsificación, ruido pequeño) están medidas y son ineficaces.

**[PRIV-28] — Erdoğan et al. (2021): *UnSplit: Data-Oblivious Model Inversion, Model Stealing, and Label Inference Attacks Against Split Learning*.** arXiv:2108.09033. https://arxiv.org/abs/2108.09033
The foundational split-learning inversion attack; recovers client inputs without knowledge of the client model.
*Key figures:* Works without knowledge of the client-side model.
*Relevancia Swarmbly:* Precedente fundacional de que el aprendizaje/inferencia dividido no protege la entrada.

**[PRIV-29] — Model Inversion in Split Learning for Personalized LLMs (2025).** arXiv:2501.05965. https://arxiv.org/html/2501.05965
Information-bottleneck analysis of *which* split points leak how much.
*Key figures:* Quantifies leakage as a function of split depth.
*Relevancia Swarmbly:* Herramienta analítica para elegir el punto de corte si Swarmbly acabara adoptando una arquitectura dividida — aunque `PRIV-27` sugiere que ningún corte es seguro.

**[PRIV-30] ⚠️ — *Prompt Inference Attack on Distributed Large Language Model Inference Frameworks*.** ACM CCS 2025. **DOI: 10.1145/3719027.3744820**. https://dl.acm.org/doi/10.1145/3719027.3744820
Attacks specifically targeting *distributed* LLM serving frameworks.
*Key figures:* ⚠️ **Full text behind a 403; details not independently verified.**
*Relevancia Swarmbly:* Es el ataque publicado dirigido exactamente a la clase de sistema que Swarmbly propone; obtener el texto completo es una tarea pendiente prioritaria.

**[PRIV-31] — BettiSplit (2026): Topology-Guided Privacy-Aware Split Learning.** arXiv:2607.24556. https://arxiv.org/html/2607.24556
Recent defence work in the split-learning privacy arms race.
*Key figures:* Demonstrates the attack/defence race is live and unresolved.
*Relevancia Swarmbly:* Útil para mostrar que el problema sigue abierto y que ninguna defensa publicada es definitiva.

## 6.5 Privacidad diferencial para texto; tasas de fallo del anonimizado de PII

**[PRIV-32] ⭐ — Brown, Lee, Mireshghallah, Shokri & Tramèr (2022): *What Does it Mean for a Language Model to Preserve Privacy?*** ACM FAccT 2022. **DOI: 10.1145/3531146.3534642** · arXiv:2202.05520. https://arxiv.org/abs/2202.05520 · https://dl.acm.org/doi/fullHtml/10.1145/3531146.3534642
The definitive conceptual argument that sanitisation-style defences fail for natural language.
*Key figures (verbatim/near-verbatim):* "Natural language reflects our private lives and identities, making its privacy concerns as broad as those of real life." Sanitisation techniques rest on "narrow assumptions" that don't match language. Privacy in text is **contextual** — the same string is sensitive in one setting and not another — so **no generic scrubber can be correct**. Conclusion: "language models should be trained on text data which was explicitly produced for public use."
*Relevancia Swarmbly:* Es el argumento de principio contra el plan de contingencia "limpiar PII antes de fragmentar": la privacidad en lenguaje es contextual, de modo que ningún limpiador basado en tipos puede ser correcto.

**[PRIV-33] ⭐ — Pilán, Lison et al. (2022): *The Text Anonymization Benchmark (TAB)*.** *Computational Linguistics* 48(4):1053–1101. **DOI: 10.1162/coli_a_00458**. https://direct.mit.edu/coli/article/48/4/1053/112770/The-Text-Anonymization-Benchmark-TAB-A-Dedicated
*Key figures — corpus:* 1,268 ECHR court cases; 2,208 document annotations; **155,006 annotated entity mentions**; 108,151 distinct entities; mean 1,442 tokens/doc.
*Key figures — measured failure rates of NER-based scrubbing:*

| System | Direct-identifier recall | Quasi-identifier recall | Precision |
|---|---|---|---|
| RoBERTa NER (OntoNotes) | **0.940** | **0.874** | **0.441** |
| Microsoft Presidio (default) | **0.460** | **0.758** | **0.761** |

Verbatim: "standard, mention-level recall seems relatively good at first sight (around 0.7), [but] a closer look at the entity-level recall over direct identifiers shows a much poorer performance (around **0.45**)." NER systems "systematically mask all occurrences of a given semantic type…without regard to their actual impact on the disclosure risk." Human annotators masked only **67.9% ± 8.3%** of entities.
*Relevancia Swarmbly:* Traducción operativa: un limpiador de PII estándar **pierde aproximadamente la mitad de los identificadores directos a nivel de entidad** y un 12–25% de los cuasi-identificadores; en un sistema que procesa muchos prompts, el fallo por entidad se compone hacia la fuga casi segura.

**[PRIV-34] ⭐ — Lukas et al. (2023): *Analyzing Leakage of Personally Identifiable Information in Language Models*.** IEEE S&P 2023. https://gangw.cs.illinois.edu/class/cs562/papers/llm-leak-sp23.pdf
*Key figures:* Undefended GPT-2-Large on ECHR — PII extraction **~23% recall / ~30% precision**, up to **10×** better than prior work. Reconstruction: **18%** accuracy vs **5.8%** for the TAB baseline (ECHR); **~7.5×** improvement on Enron. PII *inference* from 100 candidates: **70%** (ECHR), **50%** (Enron), **28%** (Yelp-Health). **With DP at ε=8, extraction recall drops to ~3% but does not reach zero — ~3% of PII sequences remain extractable.** DP inference accuracy drops to ~8% (ECHR, 100 candidates). Combining scrubbing with DP causes measurable perplexity/utility degradation.
*Relevancia Swarmbly:* Incluso con privacidad diferencial a ε=8 queda un **~3%** de secuencias de PII extraíbles, y combinar limpieza con DP degrada la utilidad de forma medible — no hay salida limpia por la vía de la sanitización.

**[PRIV-35] — *Differentially-private text generation degrades output language quality* (2025).** arXiv:2509.11176. https://arxiv.org/html/2509.11176v1
Quantifies the DP utility tax on generated text.
*Key figures:* Documents measurable language-quality degradation under DP.
*Relevancia Swarmbly:* Cuantifica el coste de calidad de la única defensa con garantía formal disponible para texto.

**[PRIV-36] — SynBench (2025): *A Benchmark for Differentially Private Text Generation*.** arXiv:2509.14594. https://arxiv.org/html/2509.14594v1
*Key figures:* Provides the standard evaluation harness for DP text generation.
*Relevancia Swarmbly:* Banco de pruebas si Swarmbly evaluara una variante con DP.

**[PRIV-37] — Prϵϵmpt (2025): *Sanitizing Sensitive Prompts for LLMs*.** arXiv:2504.05147. https://arxiv.org/pdf/2504.05147
Directly addresses the prompt-sanitisation problem, combining format-preserving encryption with type-aware handling.
*Key figures:* The closest existing system to a "sanitise before sending" design.
*Relevancia Swarmbly:* Es prior art directo del pipeline que Swarmbly necesitaría antes de despachar micro-prompts; estudiarlo es obligatorio antes de diseñar el propio.

**[PRIV-38] — De-identification of clinical data: a systematic review (2025).** https://www.sciencedirect.com/science/article/pii/S1386505625004423
Systematic review of de-identification approaches and their measured residual-risk rates across free text, images and tabular data.
*Key figures:* Consolidated residual-risk rates across modalities.
*Relevancia Swarmbly:* Fuente de tasas de riesgo residual si Swarmbly se dirige a casos de uso clínicos o regulados.

---

# 7. [VOL] — Cómputo voluntario, Sybil, reputación y churn

**[VOL-01] ⭐ — Douceur (2002): *The Sybil Attack*.** IPTPS 2002, LNCS 2429:251–260. **DOI: 10.1007/3-540-45748-8_24**. https://link.springer.com/chapter/10.1007/3-540-45748-8_24 · https://www.microsoft.com/en-us/research/publication/the-sybil-attack/
The impossibility result for open P2P systems.
*Key figures:* Without a trusted central identity authority, **a single adversary can present an arbitrary number of distinct identities**, defeating any redundancy-based or majority-vote scheme.
*Relevancia Swarmbly:* Consecuencia directa para el diseño: "ningún nodo ve el prompt completo" solo es cierto si los nodos son principales genuinamente distintos. Bajo Sybil, un adversario con 10,000 identidades baratas recibe una fracción grande de todos los fragmentos — y los reensambla con los algoritmos de la sección `GEN`.

**[VOL-02] ⚠️ — Kamvar, Schlosser & Garcia-Molina (2003): *The EigenTrust Algorithm for Reputation Management in P2P Networks*.** WWW 2003. **DOI: 10.1145/775152.775242**. https://dl.acm.org/doi/10.1145/775152.775242 · PDF: https://nlp.stanford.edu/pubs/eigentrust.pdf
The canonical P2P reputation system: global trust values via power iteration over local trust, seeded by pre-trusted peers.
*Key figures:* ⚠️ **EigenTrust requires a set of *pre-trusted* peers to be Sybil-resistant** — i.e. it reintroduces a trust anchor.
*Relevancia Swarmbly:* Mitiga Sybil pero exige semillas preconfiables, reintroduciendo exactamente el ancla de confianza que el diseño P2P pretendía eliminar.

**[VOL-03] ⭐ — Aiyer, Alvisi, Clement, Dahlin, Martin & Porth (2005): *BAR Fault Tolerance for Cooperative Services*.** SOSP 2005. **DOI: 10.1145/1095810.1095816**. https://dl.acm.org/doi/10.1145/1095810.1095816 · PDF: https://www.cs.cornell.edu/lorenzo/papers/sosp05.pdf · Extended TR: https://www.cs.utexas.edu/ftp/techreports/tr05-10.pdf
Introduces the **Byzantine / Altruistic / Rational** model: nodes are not merely correct-or-faulty, they can be *selfishly rational* (deviate when profitable), and gives protocols that are incentive-compatible under this model.
*Key figures:* Establishes that rational deviation requires explicit incentive-compatible protocol design, not just redundancy.
*Relevancia Swarmbly:* Los nodos pagados o voluntarios son el caso *racional* canónico: tienen incentivo económico tanto para (a) omitir trabajo y devolver basura plausible como para (b) retener y monetizar los datos que ven. La redundancia detecta lo primero y es **completamente ciega** a lo segundo.

**[VOL-04] ⭐ — Anderson (2019): *BOINC: A Platform for Volunteer Computing*.** *J. Grid Computing* · arXiv:1903.01699. https://arxiv.org/pdf/1903.01699 · https://boinc.berkeley.edu/boinc_a_platform_for_volunteer_computing.pdf
The source of the redundancy cost multiplier and of the most mature real-world validation model.
*Key figures:* Current scale: **~700,000 active devices**, **~4 million CPU cores**, **~560,000 GPUs**, average throughput **93 PetaFLOPS**. Volunteer decline, verbatim: "early volunteer computing projects such as SETI@home received mass media coverage in 1999-2001, and attracted on the order of **1M volunteers**. Since then…the user base has shrunk to **200K or so**." Validation model: jobs run on multiple unrelated computers; "if a strict majority of these instance[s] have equivalent results, one of them is selected as the canonical instance" (parameters `min_quorum`, `init_ninstances`, `max_error_instances`, `max_success_instances`). **Cost multiplier, verbatim: "Basic replication-based validation reduces effective computing capacity by a factor of at least two."** Mitigation: **adaptive replication** "moves this factor close to one" by identifying reliably-correct hosts, "even in the presence of malicious volunteers, while imposing only a small throughput overhead."
*Relevancia Swarmbly:* Fija el multiplicador de coste de la verificación por redundancia (**≥2×**) y, críticamente, que la replicación adaptativa solo lo reduce **perfilando hosts a lo largo del tiempo**, lo que exige identidades estables y rastreables — en tensión directa con la resistencia a Sybil y con la privacidad.

**[VOL-05] ⭐ — Anderson & Fedak (2006): *The Computational and Storage Potential of Volunteer Computing*.** CCGrid 2006. **DOI: 10.1109/CCGRID.2006.101** · arXiv:cs/0602061. https://arxiv.org/pdf/cs/0602061 · https://ieeexplore.ieee.org/document/1630798/
The source of the churn statistics (SETI@home, **331,785 hosts**, snapshot 2006-02-10, hosts that completed work in the prior two weeks).
*Key figures (verbatim):*

| Metric | Definition | Mean |
|---|---|---|
| On-fraction | "fraction of real time during which the BOINC client is running on the host" | **0.81** |
| Connected-fraction | fraction of BOINC-running time with a physical network connection | **0.83** |
| Active-fraction | fraction of BOINC-running time "when BOINC is allowed to compute and communicate" | **0.84** |
| CPU efficiency | accounting for non-BOINC load and app overhead | **0.899** |

**Average host lifetime: 91 days** from creation to last communication (an underestimate, since still-active hosts are omitted). Host concentration: **41.4%** of hosts belonged to single-host users; **44.2%** to users with 2–10 hosts; **the top user operated 2,987 hosts**. Effective duty cycle: $0.81 \times 0.84 \times 0.899 \approx \mathbf{0.61}$.
*Relevancia Swarmbly:* Aporta los tres números que Swarmbly necesita para modelar su enjambre: **ciclo de servicio efectivo ~61%**, **vida media del host 91 días**, y **el mayor usuario individual operando 2,987 hosts** — una demostración real del problema de concentración tipo Sybil en el proyecto insignia del cómputo voluntario, y por un usuario benigno sin incentivo para ocultarlo.

**[VOL-06] — SETI@home — total historical scale.** https://www.supercluster.com/editorial/analyzing-data-from-5-million-seti-home-users · https://www.seti.org/news/seti-at-home-update-21-years-of-citizen-science/
*Key figures:* Roughly **5 million** cumulative participants over **21 years**; compute phase shut down **March 2020**.
*Relevancia Swarmbly:* Cota superior histórica de participación voluntaria y recordatorio de que incluso el proyecto más famoso del género terminó cerrando.

**[VOL-07] — Zimmerman et al. (2020): *SARS-CoV-2 Simulations Go Exascale…*.** *Nature Chemistry* 13:651–659. **DOI: 10.1038/s41557-021-00707-0** (preprint PMC7337393). https://pmc.ncbi.nlm.nih.gov/articles/PMC7337393
The peer-reviewed scientific output of the Folding@home COVID-19 surge.
*Key figures:* Peer-reviewed record of the exascale volunteer campaign.
*Relevancia Swarmbly:* Demuestra que el cómputo voluntario puede producir ciencia de primer nivel cuando la carga de trabajo encaja con el modelo.

**[VOL-08] ⭐ ⚠️ — Folding@home: *Achievements from over 20 years of citizen science herald the exascale era*.** *Biophysical Journal* (2023). **DOI: 10.1016/j.bpj.2023.03.028**. https://www.cell.com/biophysj/fulltext/S0006-3495(23)00201-1 · https://pubmed.ncbi.nlm.nih.gov/36945779/ · Project announcement: https://foldingathome.org/2020/07/26/citizen-scientists-create-an-exascale-computer-to-combat-covid-19/
*Key figures:* Peak scale (COVID-19, spring 2020): "over a **million** citizen scientists"; the project announced crossing **~2.4 exaFLOPS** in April 2020, at the time exceeding the aggregate of the TOP500 list. ⚠️ **The 2.4 exaFLOPS figure is from the project's own x86-normalised counter and contemporaneous press (TechPowerUp, Tom's Hardware), not from a peer-reviewed benchmark, and is not LINPACK-comparable. Cite it as a self-reported figure.** https://www.techpowerup.com/265736/folding-home-surpasses-2-4-exaflops-faster-than-top-500-supercomputers-in-the-world
*Relevancia Swarmbly:* Lección incómoda: Folding@home alcanzó la exaescala porque su carga es **vergonzosamente paralela, sin acoplamiento de latencia y sin requisito de confidencialidad** — trayectorias MD independientes, datos públicos, resultados verificables por la física. La inferencia LLM es lo contrario en cada eje: acoplada secuencialmente entre capas, crítica en latencia, y con la carga útil siendo precisamente lo confidencial. **El precedente de escala no se transfiere.**

---

# 8. [GOV] — Licencias, propiedad intelectual y arte previo

## 8.1 AGPLv3 y la cláusula de uso en red

**[GOV-01] ⭐ — GNU Affero General Public License v3, Section 13 "Remote Network Interaction".** https://www.gnu.org/licenses/agpl-3.0.en.html · background: https://www.fsf.org/bulletin/2021/fall/the-fundamentals-of-the-agplv3
If you modify the Program and let users interact with it *remotely through a computer network*, you must offer those users the Corresponding Source of your modified version, at no charge, via a network server. This closes the "SaaS loophole" that GPLv2/v3 leave open, since plain GPL triggers only on *distribution* of binaries; Section 13 also grants special one-way compatibility with GPLv3.
*Key figures:* Ninguna cifra numérica; es el texto normativo mismo. ⚠️ `[PARAPHRASE]` gnu.org bloquea la extracción automatizada (robots.txt); verificar el texto exacto contra la fuente canónica antes de redactar avisos de licencia.
*Relevancia Swarmbly:* Es la cláusula que cierra el vacío legal que permitiría a un operador ofrecer el protocolo como servicio sin publicar sus modificaciones — la base jurídica de todo el diseño de licencia de Swarmbly.

**[GOV-02] — The scope limit that matters most (lectura de Kemitchell).** https://writing.kemitchell.com/2021/01/24/Reading-AGPL
La obligación de AGPL se activa sobre *el Programa y sus modificaciones*, no sobre la pila propietaria circundante (orquestación, enrutamiento, facturación, pesos del modelo, clientes cerrados que llaman a la API). Consecuencia práctica: un operador puede ejecutar código de inferencia AGPL sin modificar y no deber esencialmente nada más que apuntar al upstream. Kemitchell ofrece la lectura crítica más detallada de las ambigüedades de redacción (qué cuenta como "versión modificada", "interactuar remotamente", "oferta prominente").
*Key figures:* Ninguna cifra numérica; análisis textual.
*Relevancia Swarmbly:* Advierte que un operador podría envolver el núcleo AGPL de Swarmbly con una capa propietaria de enrutamiento/facturación sin obligación de publicarla — un límite de diseño que el foundation charter debe anticipar.

**[GOV-03] ⭐ — La eficacia real de AGPL es disuasión, no litigio: la prohibición absoluta de Google.** https://opensource.google/documentation/reference/using/agpl-policy
La documentación pública de código abierto de Google establece: *"Code licensed under the GNU Affero General Public License (AGPL) MUST NOT be used at Google."* Además instruye al personal a no incorporar código AGPL a google3, no usarlo en ningún producto de Google, y ni siquiera instalar programas AGPL en estaciones de trabajo, portátiles o teléfonos corporativos sin autorización de la OSPO.
*Key figures:* Prohibición categórica, sin excepciones documentadas salvo autorización de OSPO.
*Relevancia Swarmbly:* Es la prueba más fuerte de que AGPL funciona como repelente de hiperescaladores **por política, no por demanda** — el argumento central para adoptar AGPLv3 desde el día uno.

**[GOV-04] ⚠️ `[UNVERIFIED]` — AGPL enforcement history: Neo4j v. PureThink / Suhy.** https://sfconservancy.org/blog/2022/mar/30/neo4j-v-purethink-open-source-affero-gpl/ · https://www.theregister.com/2025/02/27/adverse_appeals_court_ruling_could/ · https://www.fsf.org/news/fsf-submits-amicus-brief-in-neo4j-v-suhy
Neo4j licenció Enterprise Edition como "AGPLv3 WITH Commons-Clause". Suhy eliminó la Commons Clause (apoyándose en AGPLv3 Section 7¶4, que dice que un receptor "may remove" restricciones adicionales) y redistribuyó como ONgDB. Un tribunal de distrito de California resolvió en **marzo de 2022** que AGPLv3 **no** permitía esa eliminación, y prohibió a Suhy afirmar lo contrario. Software Freedom Conservancy calificó el fallo de erróneo; la FSF presentó un amicus. Apelado ante el **Noveno Circuito** (pendiente según la cobertura de febrero de 2025).
*Key figures:* Fallo de distrito **marzo 2022**; apelación pendiente a **feb 2025**. ⚠️ `[UNVERIFIED]` Resultado final del Noveno Circuito no confirmado en esta sesión.
*Relevancia Swarmbly:* Es el precedente de referencia sobre si un tercero puede "quitar" restricciones adicionales combinadas con AGPL — relevante si Swarmbly alguna vez combina AGPL con una cláusula adicional propia.

**[GOV-05] ⚠️ `[UNVERIFIED]` — SFC v. Vizio — ¿pueden hacer cumplir el copyleft quienes no son titulares del copyright?** https://www.dlapiper.com/en-us/insights/publications/2026/01/sfc-v-vizio-ruling-on-general-public-license-compliance-key-takeaways · https://sfconservancy.org/copyleft-compliance/vizio.html
La Corte Superior de California (condado de Orange) resolvió el **23 de diciembre de 2025** que GPLv2/LGPLv2.1 **no** exigen que un distribuidor permita reinstalar código fuente modificado en el dispositivo, solo que el fuente sea obtenible y modificable para otras aplicaciones. La pregunta decisiva — si los usuarios finales son **terceros beneficiarios** que pueden hacer cumplir la GPL como contrato — fue a juicio el **12 de enero de 2026**.
*Key figures:* Fallo **23 dic 2025**; juicio **12 ene 2026**. ⚠️ `[UNVERIFIED]` Veredicto del juicio no recuperado en esta sesión — es la pregunta abierta más consecuente para decidir si una fundación necesita poseer ella misma el copyright para hacer cumplir AGPL.
*Relevancia Swarmbly:* Determina si la fundación de Swarmbly necesita retener el copyright directamente (vía CLA) para poder demandar por incumplimiento, en lugar de depender de que los usuarios finales lo hagan como terceros beneficiarios.

## 8.2 Historial real: qué pasó con los proyectos que intentaron frenar a la nube

**[GOV-06] — Elastic — SSPL/ELv2 (2021) → AGPLv3 añadida (ago 2024).** https://www.elastic.co/blog/elasticsearch-is-open-source-again · https://www.yahoo.com/tech/aws-brings-opensearch-under-linux-070100834.html
Elastic abandonó Apache 2.0 en enero de 2021 explícitamente por causa de AWS. El **29 de agosto de 2024** añadió AGPLv3 como opción. La propia enmarcación de Shay Banon del resultado: *"Amazon is fully invested in their fork, the market confusion has been (mostly) resolved, and our partnership with AWS is stronger than ever."* Traducción: el relicenciamiento no detuvo el fork; separó las marcas. OpenSearch acumuló más de 3.300 contribuyentes y AWS lo trasladó a la Linux Foundation en 2025.
*Key figures:* AGPLv3 añadida **29 ago 2024**; OpenSearch: **3.300+ contribuyentes**; traslado a Linux Foundation en 2025.
*Relevancia Swarmbly:* Muestra que relicenciar para frenar a la nube no impide el fork del hiperescalador; solo separa marcas — argumento a favor de AGPL desde el origen, no como reacción tardía.

**[GOV-07] ⭐ — Redis — SSPL/RSAL (mar 2024) → AGPLv3 (may 2025), tras que Valkey se comiera el ecosistema.** https://www.percona.com/about-percona/newsroom/press-releases/valkey-emerges-as-leading-open-source-alternative-to-redis-after-relicensing-row · https://www.infoq.com/news/2025/05/redis-agpl-license
Redis relicenció a RSALv2/SSPL en marzo de 2024, provocando el fork **Valkey** bajo la Linux Foundation. Redis revirtió a **AGPLv3 con Redis 8, anunciado ~1 de mayo de 2025**. El Valkey Adoption Report de Percona (sept 2024) encontró que el **75%** de los usuarios de Redis encuestados estaban probando, considerando o habían adoptado Valkey; **83%** en grandes empresas; **>70%** dijo que el propio cambio de licencia les motivó a buscar alternativas; **63%** conocía Valkey en ~6 meses desde su debut en marzo de 2024.
*Key figures:* **75%** probando/adoptando Valkey; **83%** grandes empresas; **>70%** motivados por el cambio de licencia; **63%** conocimiento en 6 meses.
*Relevancia Swarmbly:* Es el caso cuantitativo más completo del patrón: la mayoría de los usuarios huyó en menos de un año, y la propia Redis terminó volviendo a AGPL — validación empírica directa de la tesis "relicenciar no detiene la nube".

**[GOV-08] — Grafana — Apache 2.0 → AGPLv3 (21 abril 2021).** https://grafana.com/blog/grafana-loki-tempo-relicensing-to-agplv3/
Grafana Labs relicenció Grafana, Loki y Tempo a AGPLv3. Notablemente **eligieron AGPL en vez de SSPL/BSL** y lo dijeron explícitamente: reconocieron que AGPL "doesn't provide the same protection" que SSPL, pero sintieron que lograba el equilibrio correcto y los mantenía genuinamente open source.
*Key figures:* Relicenciamiento **21 abril 2021**; tres proyectos afectados (Grafana, Loki, Tempo).
*Relevancia Swarmbly:* Es el precedente más cercano para una fundación que quiere credibilidad copyleft en lugar de máxima prevención de captura — la misma elección que Swarmbly plantea hacer desde el inicio.

**[GOV-09] — MongoDB / SSPL — el caso de advertencia.** https://www.theregister.com/2025/08/25/linux_foundation_says_yes_to/ · https://www.mongodb.com/legal/licensing/server-side-public-license/faq
SSPL fue presentada a la OSI y efectivamente **rechazada**; el software SSPL no es open source y está excluido de Debian, Fedora y Red Hat. No detuvo a AWS (DocumentDB), y en **agosto de 2025 la Linux Foundation aceptó DocumentDB** como proyecto — es decir, el ecosistema compatible con Mongo se consolidó *fuera* de MongoDB Inc.
*Key figures:* Rechazo por OSI; exclusión de Debian/Fedora/Red Hat; DocumentDB aceptado por LF **ago 2025**.
*Relevancia Swarmbly:* Es el ejemplo más extremo de fracaso de relicenciamiento: ni siquiera abandonar el open source detuvo al hiperescalador objetivo.

**[GOV-10] ⚠️ `[SECONDARY]` — HashiCorp / BUSL — el relicenciamiento no preservó la independencia.** https://www.flowverify.co/blog/open-source-relicensing-2026-what-happened · https://en.wikipedia.org/wiki/OpenTofu
HashiCorp adoptó BUSL 1.1 en **agosto de 2023**; **OpenTofu** hizo fork bajo la Linux Foundation; **IBM adquirió HashiCorp por ~$6.4 mil millones (cerrado feb 2025)**. OpenTofu reportó acercarse a ~10 millones de descargas hacia 2026 con usuarios empresariales de producción nombrados.
*Key figures:* BUSL **ago 2023**; adquisición IBM **~$6.4 bn**, cerrada **feb 2025**; OpenTofu **~10 M** descargas (2026). ⚠️ `[SECONDARY]` cifras de adopción provienen de un blog comercial, no de la telemetría propia de OpenTofu.
*Relevancia Swarmbly:* Muestra el desenlace más drástico posible: la empresa que relicenció terminó siendo adquirida por un hiperescalador de todos modos, mientras su fork abierto prosperó bajo una fundación neutral.

**[GOV-11] ⭐ — Veredicto de conjunto sobre los cinco relicenciamientos.** https://www.softwareseni.com/the-open-source-license-change-pattern-mongodb-to-redis-timeline-2018-to-2026-and-what-comes-next/
Cada proyecto que relicenció para prevenir la captura por la nube (Mongo, Elastic, Redis, HashiCorp) obtuvo un fork respaldado por un hiperescalador o por la LF que adquirió impulso independiente; dos de los cuatro (Elastic, Redis) más tarde *volvieron* a AGPL. Los forks no desaparecieron.
*Key figures:* 4 de 4 relicenciamientos generaron un fork independiente exitoso; 2 de 4 revirtieron a AGPL.
*Relevancia Swarmbly:* **El relicenciamiento protege la marca y los ingresos comerciales del vendor; no impide que una nube bien capitalizada ofrezca el servicio gestionado.** Para una fundación sin brazo propietario que proteger, este es el argumento más fuerte a favor de AGPLv3 desde el día uno y de no moverse jamás de ahí.

## 8.3 Publicación defensiva y arte previo

**[GOV-12] — El criterio legal de "publicación impresa" que establece el arte previo (EE.UU.).** https://www.bitlaw.com/source/mpep/2128.html
MPEP 2128: un documento es una publicación impresa cuando ha sido *"disseminated or otherwise made available to the extent that persons interested and ordinarily skilled in the subject matter or art, exercising reasonable diligence, can locate it."* Los medios electrónicos cuentan (bases de datos en línea, foros, videos, redes sociales). **Crítico:** si el documento no lleva fecha de publicación, un examinador no puede usarlo bajo Section 102 sin evidencia independiente de cuándo se publicó. Las marcas de tiempo de Wayback Machine crean una presunción refutable.
*Key figures:* Estándar legal textual (MPEP 2128), sin cifra numérica asociada.
*Relevancia Swarmbly:* Fija el estándar exacto que cualquier publicación defensiva de Swarmbly debe cumplir para servir como arte previo válido ante una oficina de patentes.

**[GOV-13] ⭐ — Lo que NO cuenta de forma fiable como arte previo.** https://hroy.eu/posts/intro-defpubs/
Publicar código fuente en un repositorio Git. Según los profesionales de Linux Defenders de OIN: *"patent office staff will usually not go to software repositories and read source code in order to find prior art."* Las publicaciones defensivas efectivas usan terminología genérica (no específica del proyecto), incluyen diagramas y diagramas de flujo, explican *cómo* funciona el sistema, y se depositan donde los examinadores realmente buscan.
*Key figures:* Ninguna cifra numérica; hallazgo cualitativo pero crítico.
*Relevancia Swarmbly:* Es la advertencia más importante de toda la sección: publicar el repositorio de Swarmbly en GitHub **no** protege contra patentes de terceros; se necesita una publicación defensiva formal en lenguaje legible para examinadores.

**[GOV-14] ⚠️ `[UNVERIFIED]` — IP.com Prior Art Database / InnovationQ.** https://kb.ip.com/pad/faqs/
Venue comercial de publicación defensiva. Asigna **marcas de tiempo UTC**; cuenta con una opinión legal de McDermott Will & Emery de que las divulgaciones pueden autenticarse para sustentar invalidez bajo **35 U.S.C. Sections 102 y 103**; y — el diferenciador — también publica *The IP.com Journal* en **forma física en bibliotecas de todo el mundo**, de modo que sobrevive una copia archivística aunque la base de datos no lo haga.
*Key figures:* Marcas de tiempo UTC; respaldo legal bajo Sections 102/103. ⚠️ `[UNVERIFIED]` Precios de publicación no divulgados; tampoco confirmado si USPTO/EPO lo consultan por defecto.
*Relevancia Swarmbly:* Es la vía comercial recomendada para las 3–6 reivindicaciones arquitectónicas que Swarmbly más teme ver patentadas por terceros.

**[GOV-15] — Zenodo (CERN + OpenAIRE).** https://about.zenodo.org/policies/
Repositorio gratuito que emite **DOIs** para todos los depósitos; los archivos están versionados (los registros no); checksums MD5 y verificaciones de integridad regulares; datos replicados entre los centros de datos de CERN en Ginebra y Budapest con respaldo en cinta nocturno. Retención: *"the lifetime of the host laboratory CERN, which currently has an experimental programme defined for the next 20 years at least."* Advertencia en su propia política: *"Zenodo makes no promises of usability and understandability of deposited objects over time."*
*Key figures:* Retención declarada de al menos **20 años**; replicación en 2 centros de datos.
*Relevancia Swarmbly:* Aporta el DOI de permanencia archivística que complementa a arXiv en la pila de publicación defensiva recomendada.

**[GOV-16] ⚠️ `[UNVERIFIED]` — arXiv.** https://arxiv.org/
Servidor de preprints gratuito con marcas de tiempo de versión públicas y citables; el venue estándar para trabajo de ML/sistemas y muy rastreado. Fuerte en accesibilidad pública y fechado, débil en estar *indexado donde los examinadores de patentes buscan* — tratarlo como necesario pero no suficiente.
*Key figures:* Ninguna cifra numérica. ⚠️ `[UNVERIFIED]` No se pudo recuperar la propia declaración de política de arXiv sobre autoridad de marca de tiempo en esta sesión.
*Relevancia Swarmbly:* Primer eslabón de la pila de arte previo recomendada por su alcance y fechado, pero insuficiente por sí solo.

**[GOV-17] ⭐ — Pila de arte previo recomendada.** https://opensource.com/education/13/2/software-defensive-patents
Cinturón y tirantes: (1) preprint en arXiv por alcance y fechado, (2) DOI de Zenodo por permanencia archivística y versionado, (3) una publicación defensiva formal vía **IP.com** o **OIN's Linux Defenders** escrita en lenguaje genérico legible para examinadores, para las 3–6 reivindicaciones arquitectónicas más temidas (p. ej. programación por prueba de contribución, liquidación de créditos para inferencia distribuida, ejecución verificable de modelo parcial). Publicar solo el repositorio es el modo de fallo.
*Key figures:* Síntesis de tres capas (arXiv + Zenodo + IP.com/OIN), sin cifra numérica propia.
*Relevancia Swarmbly:* Es la receta operativa concreta que Swarmbly debe ejecutar antes de que cualquier competidor patente las 3–6 ideas arquitectónicas centrales del proyecto.

## 8.4 Patentes, OIN, CLA vs DCO, marcas

**[GOV-18] — Open Invention Network (OIN).** https://openinventionnetwork.com/about-us/corporate-overview/ · https://openinventionnetwork.com/linux-system/
OIN es la comunidad de no agresión de patentes más grande: **4.100+ organizaciones, 3+ millones de patentes activas, $10+ billones (trillion) de ingresos combinados**. La licencia cruzada libre de regalías cubre la **Linux System Definition — 5.100+ tecnologías centrales de Linux y open source** (Apache, Eclipse, Firefox, GNOME, MySQL, PostgreSQL, Python, Rust, etc.).
*Key figures:* **4.100+** organizaciones; **3+ millones** de patentes activas; **$10+ billones** en ingresos combinados; **5.100+** tecnologías cubiertas.
*Relevancia Swarmbly:* Ofrece a la fundación de Swarmbly paz de patentes gratuita en un campo de uso amplio, sin coste, simplemente al firmar el compromiso de no agresión.

**[GOV-19] — Esquema de cuotas OIN 2.0 (efectivo 27 de enero de 2026).** https://openinventionnetwork.com/participation-fees/ · https://www.globenewswire.com/news-release/2026/05/18/3296970/0/en/Advancing-Open-Source-Patent-Protection-Preservation-of-OIN-2-0-Source-Code.html
OIN pasó de gratuito para todos a un modelo de financiación compartida. Cuotas anuales de participación por ingresos:

| Nivel | Ingresos anuales | Cuota/año |
|---|---|---|
| 1 | > $500 M | **$24.000** |
| 2 | $100–500 M | **$16.000** |
| 3 | $50–100 M | **$8.000** |
| 4 | $10–50 M | **$1.000** |
| 5 | < $10 M, e individuos | **Gratis** |

Una empresa que no quiera divulgar ingresos puede simplemente pagar el Nivel 1. Las cuotas no son reembolsables; la Junta puede eximirlas. **Una nueva fundación de IA se une en el Nivel 5 — gratis.** Anunciado como OIN 2.0 en mayo de 2026.
*Key figures:* Tabla completa de 5 niveles ($24k a gratis); efectivo **27 ene 2026**.
*Relevancia Swarmbly:* Confirma que la fundación de Swarmbly puede sumarse a OIN **sin coste** al calificar como Nivel 5, obteniendo paz de patentes sobre 5.100+ tecnologías de inmediato.

**[GOV-20] ⭐ — CLA vs DCO para un proyecto gestionado por fundación.** https://opensource.com/article/18/3/cla-vs-dco-whats-difference · https://opensource.com/article/19/2/cla-problems · https://openinfra.org/dco/ · https://osr.finos.org/docs/bok/artifacts/clas-and-dcos
**DCO** (Developer Certificate of Origin, `Signed-off-by:` en el commit): ligero, sin fricción de papeleo, usado por el kernel de Linux, OpenInfra Foundation, CNCF. Es una *atestación* de procedencia, no una concesión de derechos ni un poder de relicenciamiento. **CLA**: los contribuyentes ceden o licencian derechos a la fundación, dándole capacidad de (a) relicenciar unilateralmente, (b) hacer cumplir el copyright en su propio nombre (relevante dada la cuestión no resuelta de terceros beneficiarios en `GOV-05`), (c) ofrecer excepciones comerciales. Costes: fricción para el contribuyente, y — el riesgo clave de gobernanza — un CLA es precisamente el mecanismo que permitió a Redis, Elastic, HashiCorp y MongoDB relicenciar contra la voluntad de la comunidad.
*Key figures:* Ninguna cifra numérica; comparación cualitativa de mecanismos.
*Relevancia Swarmbly:* Recomendación práctica: **DCO + una cláusula de estatuto irrevocable y bloqueada a la licencia**, o un CLA estrecho cuyo poder de relicenciamiento esté restringido contractualmente solo a licencias copyleft aprobadas por OSI — la credibilidad ganada vale más que la opcionalidad perdida.

**[GOV-21] ⭐ — Marca comercial como la palanca de control real: el modelo de la Rust Foundation.** https://rustfoundation.org/policy/rust-trademark-policy/ · https://blog.rust-lang.org/2024/11/06/trademark-update/ · historia/crítica: https://sfconservancy.org/blog/2023/jul/27/trademark-history-and-rust/
La Rust Foundation posee dos marcas denominativas ("Rust", "Cargo") más dos logotipos. **Permitido sin permiso:** declarar que un software está escrito en Rust, nombrar crates con "Rust" para señalar compatibilidad, subcomandos `cargo-foobar`, libros/blogs/papers, merchandising personal, meetups pequeños. **Requiere aprobación:** distribuir versiones significativamente modificadas *llamadas* Rust/Cargo, vender merchandising de marca, incorporar las marcas a otras marcas, eventos llamados "RustConf"/"RustCamp".
*Key figures:* 2 marcas denominativas + 2 logotipos; distinción binaria permitido/requiere-aprobación documentada explícitamente.
*Relevancia Swarmbly:* **El código es libre, el nombre no lo es** — la marca es la única palanca que sobrevive a un fork hostil y es ortogonal a la licencia de copyright; Swarmbly debe registrar su nombre en la fundación, nunca en una entidad operativa comercial.

---

# 9. [FND] — Estructura de fundación y financiación

## 9.1 Fundación suiza (Stiftung) y Verein

**[FND-01] ⭐ ⚠️ `[SECONDARY]` — Fundación suiza (Stiftung) — costes y requisitos.** https://foundation-switzerland.com/swiss-foundation-cost-fees-capital-requirements/ · https://foundation-switzerland.com/swiss-foundation-complete-guide/
**Capital mínimo: ninguno estatutario** bajo el Art. 80 del Código Civil suizo. **CHF 50.000** es la *expectativa práctica* de las autoridades de supervisión, no un piso legal. **Constitución única:** notario (escritura pública) CHF 1.000–3.000 · registro mercantil CHF 600–800 · cuota de establecimiento ESA CHF 2.500–5.000 · asesoría legal CHF 6.000–10.000 → **total típico CHF 10.000–15.000**. **Anual:** supervisión ESA ~CHF 1.200 (rango 750–2.000) · auditoría limitada CHF 2.000–5.000+ · contabilidad/administración CHF 5.000–10.000+ → **~CHF 10.000+/año**. **Exención de auditoría** posible si el balance total permanece bajo **CHF 200.000** durante dos años sucesivos.
*Key figures:* Capital mínimo estatutario: **ninguno** (expectativa práctica CHF 50.000); constitución **CHF 10.000–15.000**; anual **~CHF 10.000+**; umbral exención auditoría **CHF 200.000**. ⚠️ `[SECONDARY]` cifras de una firma de servicios corporativos suiza, no de un arancel oficial de la ESA.
*Relevancia Swarmbly:* Fija el presupuesto concreto (CHF 10–15k de constitución, CHF 10k+/año) para la opción de fundación más citada como precedente de protocolos (Ethereum, Web3, Cardano, Solana).

**[FND-02] ⭐ — Asociación suiza (Verein) — la alternativa barata, rápida y nativa de DAO.** https://www.mme.ch/en/magazine/articles/switzerland-redefines-the-foundation-era
Puede constituirse **en un día**, formalidad mínima, **sin requisito de capital**, gobernanza basada en miembros que se mapea naturalmente sobre votación tipo DAO/comunidad. Sin supervisión obligatoria. La contrapartida es una permanencia percibida más débil y ausencia de bloqueo de propósito. **Quién usa qué (según MME, firma legal cripto suiza líder):** *Fundaciones* — Anoma, Cardano, Cosmos, Dfinity, dYdX, Ethereum, LUKSO, NEAR, Polkadot, Safe, Solana, Tezos, TON. *Asociaciones* — Aragon, Badger, Casper, Linea, Nillion.
*Key figures:* Constitución en **1 día**; **sin capital mínimo**; lista completa de 14 protocolos por tipo de entidad.
*Relevancia Swarmbly:* Es la estructura recomendada para arrancar (día uno, sin capital), con una vía de estatuto explícita para convertirse en Stiftung una vez existan activos que valga la pena bloquear a un propósito.

**[FND-03] ⚠️ `[SECONDARY]` — Ethereum Foundation (Stiftung Ethereum, Zug).** https://www.moneyhouse.ch/en/company/stiftung-ethereum-21062500321 · https://www.blockhead.co/2025/06/05/ethereum-foundation-unveils-conservative-treasury-strategy-amid-major-r-d-restructuring/
La Stiftung suiza canónica para un protocolo. En 2025 publicó una política de tesorería conservadora y reestructuró I+D en clústeres de protocolo, recortando aproximadamente un 20% del personal.
*Key figures:* Recorte de personal **~20%** (2025). ⚠️ `[SECONDARY]` la cifra del 20% y la política de tesorería provienen de cobertura de prensa, no de una presentación de la EF recuperada directamente.
*Relevancia Swarmbly:* Es el precedente histórico más directo de una Stiftung suiza gobernando un protocolo abierto de gran escala, con datos reales (aunque secundarios) sobre su reestructuración financiera.

**[FND-04] — Web3 Foundation (Web 3.0 Technologies Stiftung, Zug).** https://www.businesswire.com/news/home/20231116390141/en/Web3-Foundation-Launches-$45M-USD-Decentralized-Futures-Program-To-Back-Diverse-Range-of-Ecosystem-Projects · https://www.northdata.com/Web%203%C2%B70%20Technologies%20Stiftung,%20Zug/CHE-322.596.347
Stiftung suiza detrás de Polkadot. Lanzó un **Decentralized Futures Program de $45 M** (nov 2023) para financiar equipos del ecosistema — un modelo directamente transferible para una fundación de protocolo que quiere financiar implementadores independientes en lugar de emplearlos.
*Key figures:* **$45 M** programa, lanzado **nov 2023**.
*Relevancia Swarmbly:* Modelo concreto de cómo una fundación puede desplegar capital para financiar a implementadores externos del protocolo, en lugar de construir todo internamente.

## 9.2 Alternativas jurisdiccionales

**[FND-05] ⚠️ `[UNVERIFIED]` — Cayman Islands Foundation Company.** https://www.legalnodes.com/article/caymanian-foundation-for-dao · https://www.mourant.com/updates/cayman-islands-foundation-companies-the-ideal-vehicle-for-daos-and-crypto-trading/
Envoltorio de derecho común para DAOs. **Sin contribución mínima obligatoria**; constitución típicamente **1–2 meses**; requiere un consejo de fundación, un supervisor y una oficina registrada. Reportado como *"al menos dos veces más barato de constituir"* que las fundaciones continentales (Suiza, Singapur, Liechtenstein).
*Key figures:* Constitución **1–2 meses**. ⚠️ `[UNVERIFIED]` sin cifras USD duras obtenidas; cotizaciones comunes en el sector son del orden de decenas de miles de USD de constitución más ~$10–20k/año — **tratar como folclore hasta que lo cotice un abogado.**
*Relevancia Swarmbly:* Alternativa de derecho común más rápida y barata que Suiza, pero sus cifras deben verificarse con asesoría legal antes de presupuestar.

**[FND-06] ⚠️ `[NOT RESEARCHED]` — Dutch Stichting.**
No investigado en la sesión fuente (presupuesto de búsqueda agotado). En general: escritura notarial, sin capital mínimo, sin miembros, rápida y barata (bajos miles de EUR de un dígito), estatus ANBI disponible para donaciones deducibles de impuestos. **Verificar independientemente.** Es la estructura detrás de, p. ej., la NLnet Foundation y varios organismos de estándares, por lo que es una candidata seria — simplemente no se pudieron citar cifras.
*Key figures:* Ninguna cifra verificada en esta sesión.
*Relevancia Swarmbly:* Es la estructura de la propia NLnet (fuente de financiación principal recomendada en `FND-12`), lo que la convierte en candidata natural si Swarmbly busca cercanía jurisdiccional con su primer financiador.

**[FND-07] ⚠️ `[SECONDARY]` — US 501(c)(3).** https://wylieadvisory.com/blog/1023-vs-1023-ez · https://www.irs.gov/charities-non-profits/form-1023-and-1023-ez-amount-of-user-fee
**Formulario 1023-EZ: cuota de $275, ~2–4 semanas** — pero solo si los ingresos proyectados son <$50.000/año durante dos años, activos <$250.000, no es escuela/hospital/fundación privada, sin subvenciones a individuos. **Formulario 1023: cuota de $600, ~4–12 semanas** para cualquier cosa mayor o más compleja. Añadir incorporación estatal, agente registrado y asesoría legal aparte.
*Key figures:* 1023-EZ: **$275**, **2–4 semanas**; 1023: **$600**, **4–12 semanas**. ⚠️ `[SECONDARY]` tiempos de procesamiento de un blog de asesoría; los tiempos publicados por el propio IRS fluctúan considerablemente.
*Relevancia Swarmbly:* Ruta más rápida y barata si Swarmbly decide operar (o crear un brazo) en jurisdicción estadounidense con deducibilidad fiscal directa para donantes.

**[FND-08] ⭐ ⚠️ `[UNVERIFIED]` — Patrocinio fiscal (NumFOCUS, Linux Foundation).** https://numfocus.org/projects-overview · https://corsa.center/foundations/numfocus.html · https://linuxiac.com/the-linux-foundation-spent-8-4-million-on-the-linux-kernel-project-in-2025/
La vía más rápida a un hogar legal: el patrocinador retiene los fondos, provee deducibilidad fiscal en EE.UU. y gestiona el cumplimiento; el proyecto conserva la gobernanza técnica. NumFOCUS opera dos niveles (comprehensive vs affiliated) para proyectos de computación científica.
*Key figures:* Como referencia de escala, la Linux Foundation reportó gastar **$8,4 M en el proyecto del kernel de Linux en 2025**. ⚠️ `[UNVERIFIED]` No se pudo recuperar el porcentaje de comisión administrativa de NumFOCUS ni el arancel de hospedaje de proyectos de LF; el hospedaje de LF se negocia típicamente por proyecto y puede llegar a seis cifras anuales para programas de servicio completo — **obtenerlo por escrito.**
*Relevancia Swarmbly:* Es la ruta más rápida hacia un hogar legal con deducibilidad fiscal mientras la fundación de Swarmbly madura, aunque el coste real de hospedaje debe negociarse explícitamente.

## 9.3 Modelos fundación + brazo comercial

**[FND-09] ⭐ — Mozilla Foundation + Mozilla Corporation — el modelo canónico de dos entidades.** https://en.wikipedia.org/wiki/Mozilla_Corporation · https://www.mozilla.org/en-US/about/governance/organizations/
Mozilla Corporation (fundada **3 de agosto de 2005**) es una **filial *gravable* de propiedad total** de la Mozilla Foundation. La Fundación **no** es una organización benéfica pública sencilla porque no obtiene ≥⅓ de sus ingresos de donaciones públicas; una **auditoría del IRS (2008–2012) sobre sus regalías de búsqueda se resolvió por $1,5 M en noviembre de 2012**. La Corporation reinvierte todas las ganancias en proyectos Mozilla; no hay accionistas, opciones sobre acciones ni dividendos, y no puede ser adquirida ni salir a bolsa. **Trayectoria de ingresos:** 2005 $52,9 M (95% Google) → 2011 $163,5 M (85%) → 2017 $562 M (93%) → 2022 $593 M (81%) → **2024 $680 M (86% Google)**.
*Key figures:* Ingresos 2024 **$680 M**, **86%** de Google; auditoría IRS resuelta por **$1,5 M** (2012); dos décadas de concentración de ingresos en un solo contraparte (~85%).
*Relevancia Swarmbly:* La lección es doble filo: la estructura funciona, pero produjo 20 años de concentración de ingresos de ~85% en una sola contraparte — advertencia directa contra depender de un único cliente comercial del brazo lucrativo de Swarmbly.

**[FND-10] ⭐ — Signal Foundation + Signal Messenger LLC.** https://en.wikipedia.org/wiki/Signal_Foundation
**501(c)(3) establecida el 10 de enero de 2018** por Moxie Marlinspike y Brian Acton; Signal Messenger LLC es su filial. Financiada por un **préstamo sin garantía y sin interés de Acton: $50 M (feb 2018), crecido a $105.000.400 a fines de 2018, reembolsable el 28 de febrero de 2068.** **2024: ingresos $29.413.537, gastos $38.019.696 — un déficit de ~$8,6 M.**
*Key figures:* Préstamo inicial **$50 M**, crecido a **$105.000.400**; déficit **2024 ~$8,6 M** sobre ~$38 M/año de gasto.
*Relevancia Swarmbly:* Dato instructivo: incluso una organización sin fines de lucro esencial y querida, financiada por donaciones, opera con un déficit estructural a escala de ~$38 M/año — presupuestar en consecuencia.

**[FND-11] ⭐ — Recomendación estructural (síntesis).**
Para una fundación de protocolo de IA: **Verein suizo primero** (un día, sin capital, gobernanza compatible con DAO, ~CHF 0 de constitución) para obtener una persona jurídica y una cuenta bancaria, con una vía de estatuto explícita para convertirse o generar una **Stiftung** una vez existan activos que valga la pena bloquear a un propósito. Añadir una **AG suiza o BV holandesa de propiedad total** solo cuando haya ingresos comerciales reales (soporte, plano de control alojado, certificación) — reflejando a Mozilla Corp, no precediéndola. Mantener la marca comercial en la fundación, nunca en la empresa operativa.
*Key figures:* Síntesis normativa sin cifra propia adicional a las citadas en `FND-01`/`FND-02`/`FND-09`.
*Relevancia Swarmbly:* Es la recomendación operativa concreta que Swarmbly debería adoptar como secuencia de constitución: Verein → Stiftung → brazo comercial, en ese orden y no al revés.

## 9.4 Programas de financiación (grants)

**[FND-12] ⭐ — NLnet / NGI Zero — el mejor encaje individual para este proyecto.** https://nlnet.nl/funding.html · https://nlnet.nl/commonsfund/ · https://nlnet.nl/commonsfund/guideforapplicants/
**NGI Zero Commons Fund: €5.000–€50.000 por proyecto; €21,6 M a otorgar hasta 2027.** Todos los resultados deben publicarse bajo licencia libre/open source. **La 13ª y última convocatoria del Commons Fund cerró el 1 de junio de 2026.** **Abiertos actualmente (ago 2026):** *Open Social Fund* (ActivityPub/social descentralizado, €5k–€50k) y el *Research and Higher Education Technology Fund* (€5k–€50k). **Plazos trasladados al día 3 de cada mes impar** (sept, nov, ene…) desde agosto de 2026. **Anunciados pero aún no abiertos:** *Restack*, *CodeSupply*, *ELFA*.
*Key figures:* **€5.000–€50.000** por proyecto; **€21,6 M** total hasta 2027; convocatorias abiertas hoy con la misma horquilla €5k–€50k.
*Relevancia Swarmbly:* Es la primera financiación recomendada: no dilutiva, de micro-escala, baja burocracia, y explícitamente favorable a infraestructura descentralizada — el punto de entrada natural para Swarmbly.

**[FND-13] — Sovereign Tech Agency (Alemania) y el propuesto EU Sovereign Tech Fund.** https://www.sovereign.tech/programs/fund · https://en.wikipedia.org/wiki/EU_Sovereign_Tech_Fund · https://en.wikipedia.org/wiki/Sovereign_Tech_Agency
STA ha invertido **>€24,6 M en open source desde 2022** (≈$24,9 M reportados a los dos años, oct 2024); ejemplo de premio: **€1,28 M a KDE**. Financia *mantenimiento y endurecimiento de infraestructura crítica*, no investigación nueva. **EU-STF** sigue siendo una **propuesta** en 2026: un estudio de viabilidad de 2025 (OpenForum Europe, Fraunhofer ISI, EUI, encargado por GitHub) recomienda una contribución **mínima de €350 M** del MFF de la UE para **2028–2035**. El estudio estima que el open source contribuye **€65–95 mil millones anuales** a la economía de la UE.
*Key figures:* STA **>€24,6 M** invertidos desde 2022; propuesta EU-STF **mínimo €350 M** (2028–2035); contribución económica estimada del open source **€65–95 bn/año**.
*Relevancia Swarmbly:* La elegibilidad de STA depende de que el protocolo sea demostrablemente dependido — un objetivo de financiación de fase posterior, no de arranque, una vez Swarmbly tenga adopción real.

**[FND-14] ⚠️ `[SECONDARY]` — Horizon Europe Cluster 4 (Digital, Industry & Space), programa de trabajo 2026–2027.** https://www.ideal-ist.eu/news/horizon-europe-cluster-4-work-programme-2026-2027-adopted · oficial: https://ec.europa.eu/info/funding-tenders/opportunities/docs/2021-2027/horizon/wp-call/2026-2027/wp-1-general-introduction_horizon-2026-2027_en.pdf · https://hadea.ec.europa.eu/news/horizon-europe-2026-industry-calls-now-published-2025-12-19_en
Adoptado y convocatorias publicadas (convocatorias de industria anunciadas 19 dic 2025). Temas y presupuestos indicativos relevantes:

| Convocatoria | Tema | Presupuesto | Plazo |
|---|---|---|---|
| HORIZON-CL4-2026-04-DIGITAL-EMERGING-19 | Challenge-Driven GenAI4EU Booster | ~€30 M | Abr 2026 |
| HORIZON-CL4-2026-05-DIGITAL-EMERGING-02 | Next-Generation AI Agents for Real-World Applications | ~€20 M | Sep 2026 |
| HORIZON-CL4-2026-04-DIGITAL-EMERGING-01 | Apply AI: Science for AI (pilar RAISE) | ~€15 M | Abr 2026 |
| HORIZON-CL4-2026-04-DATA-06 | Efficient & Compliant Data Access for AI | ~€10 M | Abr 2026 |

Tamaño típico de subvención individual **€3 M–€20 M+**; requiere consorcio.
*Key figures:* Tabla de 4 convocatorias, €10–30 M cada una. ⚠️ `[SECONDARY]` esta tabla proviene de un agregador, no del PDF oficial del programa de trabajo — confirmar IDs, presupuestos y plazos directamente en el portal.
*Relevancia Swarmbly:* Financiación de escala mucho mayor pero que requiere consorcio formal — relevante solo si Swarmbly forma una alianza de investigación europea multi-institucional.

**[FND-15] ⚠️ `[SECONDARY]` — EU AI Continent Action Plan / InvestAI / AI Factories.** https://digital-strategy.ec.europa.eu/en/factpages/ai-continent-action-plan · https://commission.europa.eu/topics/competitiveness/ai-continent_en · https://www.grantsfinder.eu/blog/ai-genai4eu-funding-2026
Publicado el **7 de mayo de 2025**. Cinco pilares: cómputo, datos, habilidades, algoritmos/adopción, simplificación regulatoria. **AI Factories: €10 mil millones 2021–2027; objetivo ≥13 AI Factories operativas para 2026. AI Gigafactories: €20 mil millones movilizados vía InvestAI, hasta 5 planeadas.**
*Key figures:* AI Factories **€10 bn** (2021–2027), objetivo **≥13** operativas en 2026; AI Gigafactories **€20 bn**, hasta **5** planeadas. ⚠️ `[SECONDARY]` en la cifra del EuroHPC Frontier AI Grand Challenge (~2,5% de capacidad EuroHPC por un año, plazo 13 abr 2026).
*Relevancia Swarmbly:* El ángulo más relevante no es capex de gigafactoría sino solicitar **acceso a cómputo gratuito/subsidiado** a través de las convocatorias continuas de las AI Factories.

**[FND-16] ⚠️ — Current AI (fundación de IA de interés público).** https://www.currentai.org/blogs/building-public-interest-ai---current-ais-next-chapter · https://www.currentai.org/
Lanzada en la **Cumbre de Acción de IA de París** con **>$400 M** en compromisos iniciales; el comité interino incluye a la Fundación MacArthur, la Fundación Ford, la Fundación Patrick J. McGovern, Salesforce, Google DeepMind y el gobierno francés. Áreas de enfoque: **apertura** (estándares y herramientas abiertas), **desbloqueo de conjuntos de datos** (medios/salud/educación) y **auditoría/rendición de cuentas de interés público**. A mediados de 2026 publicó un *Gap Map v0.1* de la pila de IA de código abierto.
*Key figures:* **>$400 M** compromiso inicial. ⚠️ **Conflicto de fecha:** la Cumbre de Acción de IA de París se celebró el 10–11 de febrero de 2025, pero el propio blog de Current AI muestra "announced May 13, 2025" — no citar una fecha de lanzamiento sin verificar.
*Relevancia Swarmbly:* Su *Gap Map* de la pila de IA de código abierto es una referencia directa de dónde el ecosistema ve huecos — potencialmente relevante para posicionar a Swarmbly dentro de ese mapa.

**[FND-17] ⚠️ `[UNVERIFIED]` — Innosuisse (Suiza).** https://www.innosuisse.admin.ch/en/innovation-project-with-implementation-partner · https://www.innosuisse.admin.ch/en/funding-for-national-projects · https://www.innosuisse.admin.ch/en/swiss-accelerator-innovation-projects
**Proyectos de Innovación con Socio de Implementación:** el socio de implementación debe cubrir **40–60% de los costes totales del proyecto** y aportar una **contribución en efectivo de al menos el 5%** del coste total hacia los gastos del socio de investigación. Las solicitudes deben llegar **al menos seis semanas antes** de una reunión del Consejo de Innovación; las reuniones de 2026 son **junio–noviembre** por área temática. Los proyectos deben iniciar dentro de tres meses tras la entrada en vigor del acuerdo.
*Key figures:* Socio de implementación cubre **40–60%**; contribución en efectivo mínima **5%**; solicitud **≥6 semanas** antes de la decisión. ⚠️ `[UNVERIFIED]` contribución máxima en CHF no indicada en la página consultada.
*Relevancia Swarmbly:* Una fundación/Verein suiza es plausiblemente elegible como socio de implementación, lo que abriría financiación suiza de contrapartida — pero debe confirmarse directamente con Innosuisse.

**[FND-18] ⚠️ — Open Technology Fund (EE.UU.).** https://www.opentech.fund/about/about-our-funding/ · https://clearinghouse.net/case/46258/ · https://thehill.com/regulation/court-battles/5217360-trump-admin-radio-free-europe-open-technology-fund-voice-of-america/
El Congreso asignó **$43,5 M a OTF para el año fiscal 2025** vía USAGM/State. Sus subvenciones fueron **terminadas el 15 de marzo de 2025**, impugnadas el 20 de marzo, y las terminaciones fueron **rescindidas** tras litigio (*Open Technology Fund v. Lake*, 1:25-cv-00840, D.D.C.). También opera un **FOSS Sustainability Fund** con cofinanciadores privados.
*Key figures:* Asignación FY2025 **$43,5 M**; terminación y rescisión en **marzo 2025**.
*Relevancia Swarmbly:* **El riesgo político es material y recurrente.** No construir una línea presupuestaria sobre OTF; el estatus de la asignación FY2026 no está confirmado.

**[FND-19] ⚠️ `[UNVERIFIED]` — Financiación de subvenciones de Mozilla Foundation.** https://www.mozillafoundation.org/en/what-we-do/grantmaking
Programas: **Incubator, Fellowships, Responsible Computing Challenge, Collaborative Funds**, más el **Mozilla Technology Fund (MTF)** y el histórico **MOSS**. Total histórico: **>$35 M**.
*Key figures:* Total histórico **>$35 M**. ⚠️ `[UNVERIFIED]` tema actual de MTF, tamaño de premio y plazo 2026 no recuperables — la URL de convocatoria redirige a una página general de subvenciones, sugiriendo que no hay convocatoria abierta actualmente.
*Relevancia Swarmbly:* Fuente adicional de financiación de subvenciones a monitorear, aunque sin convocatoria activa confirmada en el momento de la compilación.

## 9.5 Créditos, tokens y regulación (FINMA / MiCA)

**[FND-20] ⭐ — Taxonomía de tokens de FINMA — qué dispara la clasificación como valor.** https://www.finma.ch/en/news/2018/02/20180216-mm-ico-wegleitung/ · https://cms.law/en/che/legal-updates/finma-ico-guidelines
Las Directrices ICO de FINMA (**16 de febrero de 2018**) definen tres tipos: **tokens de pago** (criptomonedas, sin función adicional; no son valores; aplica AML); **tokens de utilidad** (acceso digital a una aplicación o servicio); **tokens de activo** (participaciones, flujos de ganancias, derechos de dividendo/interés — **valores**). **La regla decisiva para un token de crédito de cómputo:** un token de utilidad escapa al tratamiento de valor **solo si** (a) su propósito *exclusivo* es conferir derechos de acceso digital a una aplicación o servicio, **y** (b) **el token ya puede usarse de esa forma en el momento de la emisión**. **Una preventa de créditos para una red que aún no está en producción es, por tanto, la forma más clara de convertirse en emisor de valores.**
*Key figures:* Marco de tres categorías (pago/utilidad/activo); prueba de dos condiciones para escapar de la clasificación de valor.
*Relevancia Swarmbly:* Es la regla más determinante para el diseño de tokenomics: cualquier crédito de cómputo de Swarmbly debe estar operativo desde su emisión, o se convertirá en un valor regulado.

**[FND-21] — Umbrales de licenciamiento de FINMA y AML.** https://www.finma.ch/en/authorisation/fintech/
**Licencia bancaria** requerida si se aceptan depósitos de **más de 20 clientes**, o activos de clientes en cuentas propias, sin garantía bancaria. **Licencia FinTech** disponible para depósitos de clientes de **hasta CHF 100 M**, no invertidos y sin interés. **Exención:** no se requiere licencia si los criptoactivos de cada cliente residen en **direcciones blockchain individuales** (autocustodia genuina / diseño no custodial). Negociar monedas virtuales y operar un sistema de pago caen bajo la **AMLA**; servicios de custodia o wallet requieren **membresía en un SRO**.
*Key figures:* Umbral licencia bancaria **>20 clientes**; techo licencia FinTech **CHF 100 M**; exención total vía direcciones individuales no custodiales.
*Relevancia Swarmbly:* Un sistema de crédito estrictamente no custodial, donde la fundación nunca retiene activos de usuarios, permanece fuera tanto de la licencia bancaria como de la FinTech — la custodia es el disparador a evitar.

**[FND-22] ⚠️ `[PARTIAL]` — MiCA — qué queda completamente fuera de su alcance.** https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32023R1114 · https://www.innreg.com/blog/mica-regulation-guide
MiCA (Reglamento (UE) 2023/1114) se aplica a criptoactivos "able to be **transferred** and stored electronically using DLT". Exclusiones explícitas: activos que son **instrumentos financieros** bajo MiFID II o depósitos; criptoactivos **únicos y no fungibles**; monedas digitales de banco central; **activos digitales técnicamente imposibles de transferir a otros titulares**. Exenciones de whitepaper (Art. 4): **ofertas gratuitas**; menos de **150 personas por Estado miembro**; contraprestación total **≤ €1.000.000 en 12 meses**; ofertas a inversores cualificados; tokens de utilidad que dan acceso a **un bien o servicio existente y en operación**. **Cronología:** adoptado junio 2023 · reglas ART/EMT desde **30 de junio de 2024** · reglas CASP y Travel Rule desde **30 de diciembre de 2024** · licenciamiento CASP desde 2025.
*Key figures:* Umbral de exención **€1.000.000/12 meses**; **150 personas**/Estado miembro; reglas CASP desde **30 dic 2024**. ⚠️ `[PARTIAL]` la numeración exacta del Art. 3(1) no se reprodujo limpiamente — verificar contra EUR-Lex antes de redactar.
*Relevancia Swarmbly:* Los créditos técnicamente imposibles de transferir entre titulares quedan **fuera de la definición de criptoactivo de MiCA por completo** — la vía de diseño más segura para el sistema de créditos de Swarmbly.

**[FND-23] ⭐ — Diseño concreto de token/crédito que se mantiene fuera de ambos regímenes (síntesis).** https://www.finma.ch/en/news/2018/02/20180216-mm-ico-wegleitung/ · https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32023R1114 · fondo sobre credenciales no transferibles: https://chain.link/article/what-are-soulbound-tokens
Combinando FINMA (`FND-20`/`FND-21`) y MiCA (`FND-22`), la arquitectura más segura es: (1) **créditos de cómputo no transferibles** — técnicamente imposibles de transferir entre titulares, lo que los saca de la definición de criptoactivo de MiCA y de la economía de "inversión" bajo FINMA; (2) **operativos en el momento de la emisión** — créditos utilizables para inferencia al momento de la venta, sin preventa de capacidad futura; (3) **sin mercado secundario, sin rendimiento, sin apreciación, sin redención por efectivo**; (4) **puntuaciones de reputación/prueba-de-contribución no transferibles** (estilo soulbound) para peso de gobernanza y prioridad de programación de tareas, deliberadamente *desacopladas* de cualquier crédito con valor monetario; (5) **liquidación no custodial** — la fundación nunca retiene activos de usuarios; (6) si se necesita financiación fiat, usar **subvenciones y donaciones**, no preventas de crédito.
*Key figures:* Síntesis normativa de 6 principios de diseño, sin cifra numérica adicional. ⚠️ El marco regulatorio es una síntesis de fuentes primarias citadas, **no asesoría legal**; se requiere confirmación de un abogado suizo.
*Relevancia Swarmbly:* Es el plano de diseño de tokenomics recomendado para el proyecto completo — créditos no transferibles y operativos desde la emisión, reputación desacoplada del valor monetario, y liquidación no custodial.

---

# 10. [ENV] — Energía, agua y el argumento de sostenibilidad

## 10.1 Cifras autorizadas de consumo de IA

**[ENV-01] ⭐ — IEA, *Energy and AI* (2025) — las cifras macro de referencia.** https://www.iea.org/reports/energy-and-ai/executive-summary · https://www.iea.org/reports/energy-and-ai/energy-demand-from-ai
Electricidad global de centros de datos **2024: ~415 TWh ≈ 1,5% de la electricidad mundial**. Distribución geográfica 2024: **EE.UU. 45%, China 25%, Europa 15%**. **Caso Base 2030: ~945 TWh** — más del doble, aproximadamente todo el consumo actual de Japón. Emisiones: **~180 Mt CO₂ ahora → 300 Mt (Caso Base 2035) → 500 Mt (Caso Lift-Off)**; **<1,5% del total de emisiones del sector energético**.
*Key figures:* **415 TWh (2024)**, **1,5%** de electricidad mundial; proyección **945 TWh (2030)**; emisiones **180→300→500 Mt CO₂**; **<1,5%** de emisiones del sector energético.
*Relevancia Swarmbly:* Esa última cifra corta contra el alarmismo: los centros de datos son una porción de las emisiones globales que crece rápido pero sigue siendo pequeña — contexto obligatorio antes de cualquier afirmación ambiental de Swarmbly.

**[ENV-02] — LBNL / DOE, *2024 United States Data Center Energy Usage Report* (dic 2024).** https://eta-publications.lbl.gov/sites/default/files/2024-12/lbnl-2024-united-states-data-center-energy-usage-report_1.pdf · https://www.energy.gov/articles/doe-releases-new-report-evaluating-increase-electricity-demand-data-centers
Los centros de datos de EE.UU. consumieron **4,4% de la electricidad de EE.UU. en 2023**, proyectado a alcanzar **6,7%–12% para 2028**.
*Key figures:* **4,4%** (2023) → **6,7%–12%** (2028).
*Relevancia Swarmbly:* Es la proyección específica de EE.UU. más citada y la fuente detrás de la mayoría de titulares de "12% del consumo eléctrico de EE.UU.".

**[ENV-03] ⭐ — Estudio a nivel de instalación de centros de datos hyperscale de EE.UU. (arXiv:2606.05420, jun 2026) — la cifra que más importa para el argumento de Swarmbly.** https://arxiv.org/pdf/2606.05420
403 centros de datos hyperscale de EE.UU., mayo 2024–abr 2025, ubicaciones validadas por imágenes satelitales, emisiones atribuidas vía EPA eGRID2023 a nivel de autoridad de balance: electricidad **68–99 TWh (central 82 TWh) = 1,5–2,2% de la electricidad de EE.UU.**; **37–54 Mt CO₂ (central 45 Mt)**; **intensidad de carbono 545 gCO₂/kWh — ~48% POR ENCIMA del promedio de la red nacional de EE.UU. de 370 gCO₂/kWh**; mezcla de combustibles: **53,9% fósil, 20,9% nuclear, 25,3% renovables**.
*Key figures:* **545 gCO₂/kWh** vs **370 g/kWh** nacional (**+48%**); **82 TWh** central; **45 Mt CO₂** central.
*Relevancia Swarmbly:* **Es el mejor sustento empírico individual para una afirmación ambiental de cómputo distribuido**: la ubicación de los hyperscalers de EE.UU. (PJM, MISO, ERCOT, Virginia) está en redes más sucias que el promedio, así que la ventaja de eficiencia de hardware del centro de datos queda parcialmente cancelada por dónde está enchufado. No compara, sin embargo, contra dispositivos de consumo.

**[ENV-04] — Google 2026 Environmental Report (publicado 30 jun 2026, datos FY2025).** https://blog.google/company-news/outreach-and-initiatives/sustainability/2026-environmental-report/
**Emisiones operacionales bajaron 2%** interanual **a pesar de un crecimiento del 37% en demanda eléctrica anual**. **>12 GW de energía limpia nueva** contratada solo en 2025. **~7.700 millones de galones repuestos ≈ 78% del consumo de agua dulce de 2025**. 9º año consecutivo igualando el 100% de la electricidad con compras renovables (emparejamiento anual, no horario). Afirma que la infraestructura de sus centros de datos usa **83% menos energía de overhead que el promedio de la industria**; **>58 Mt CO₂e "evitadas" en 2025** (cifra autorreportada — tratar con escepticismo).
*Key figures:* Emisiones operacionales **-2%** interanual pese a **+37%** demanda; **>12 GW** clean energy nueva; **78%** de agua repuesta; **83%** menos overhead energético.
*Relevancia Swarmbly:* Fija el listón que cualquier competidor centralizado ya alcanza en eficiencia operacional, contra el cual Swarmbly debe medir honestamente sus propias afirmaciones.

**[ENV-05] — Google 2025 Environmental Report (datos FY2024) — la línea base honesta.** https://www.datacenterdynamics.com/en/news/google-data-center-power-use-up-27-emissions-down-17-report/
**Total Scope 1+2+3: 11,5 Mt CO₂e, +11%** interanual. **Scope 3 creció 22% y ahora representa el 73% de la huella total de Google** — es decir, *manufactura y cadena de suministro*, no la electricidad, es el término dominante. Demanda eléctrica de centros de datos **+27%**; emisiones de energía de centros de datos **-12%**. **66% de energía libre de carbono sobre base horaria.** 4.500 millones de galones (17 mil millones de litros) repuestos = 64% del consumo de agua dulce (subiendo del 18% del año anterior).
*Key figures:* Scope 3 = **73%** de la huella total, creciendo **22%/año**; demanda de centros de datos **+27%**; emisiones de energía **-12%**; **66%** libre de carbono horario.
*Relevancia Swarmbly:* **El 73% de Scope 3 es crítico para el argumento de `ENV-13`: el hardware, no la electricidad, domina la huella** — la base del único argumento ambiental defendible para Swarmbly.

**[ENV-06] ⚠️ — Cifras de Google por prompt (arXiv:2508.15734, ago 2025).** https://arxiv.org/abs/2508.15734 · https://cloud.google.com/blog/products/infrastructure/measuring-the-environmental-impact-of-ai-inference · cobertura crítica: https://www.technologyreview.com/2025/08/21/1122288/google-gemini-ai-energy/
Prompt de texto mediano de Gemini Apps: **0,24 Wh de energía, 0,26 mL de agua**. El límite del sistema incluye explícitamente potencia activa del acelerador, energía del sistema anfitrión, **capacidad ociosa** y overhead del centro de datos. Reportada **reducción de 33× en energía y 44× en huella de carbono en doce meses**.
*Key figures:* **0,24 Wh** y **0,26 mL** por prompt mediano; **33×** menos energía, **44×** menos carbono en 12 meses. ⚠️ Advertencias a mencionar siempre: excluye entrenamiento, es una **mediana** (no media), y la cifra de carbono usa contabilidad **basada en mercado** (compras renovables), lo que la favorece sustancialmente frente a la contabilidad basada en ubicación.
*Relevancia Swarmbly:* Fija el listón de comparación por prompt individual que cualquier afirmación de eficiencia de Swarmbly tendría que superar — y explícitamente no lo logra (ver `ENV-11`/`ENV-12`).

**[ENV-07] — Mistral Large 2 LCA (22 jul 2025) — y por qué discrepa de Google en ~170×.** https://mistral.ai/news/our-contribution-to-a-global-environmental-standard-for-ai
Realizado bajo la metodología Frugal AI de **AFNOR**, el GHG Protocol Product Standard e **ISO 14040/44**, con Carbone 4 y ADEME, revisado por pares por Resilio y Hubblo. **Entrenamiento (18 meses hasta ene 2025): 20,4 kt CO₂e · 281.000 m³ de agua · 660 kg Sb eq** (equivalente en antimonio, depleción de recursos abióticos). **Impacto marginal por respuesta de 400 tokens: 1,14 g CO₂e · 45 mL de agua · 0,16 mg Sb eq.**
*Key figures:* **1,14 g CO₂e** y **45 mL de agua** por respuesta de 400 tokens; entrenamiento **20,4 kt CO₂e**, **281.000 m³** de agua.
*Relevancia Swarmbly:* Google reporta 0,26 mL de agua por prompt; Mistral reporta 45 mL — cualquier afirmación ambiental publicada por Swarmbly **debe** declarar su límite de sistema, o carece de sentido comparativo.

**[ENV-08] — Agua — UC Riverside / UT Arlington (arXiv:2304.03271, v5 marzo 2025).** https://arxiv.org/pdf/2304.03271
Entrenar GPT-3 en los centros de datos de EE.UU. de Microsoft puede evaporar directamente **~700.000 litros** (scope-1); **3,4–15,3 millones de litros** de agua operacional total según ubicación. Inferencia: **una botella de 500 mL por cada ~10–50 respuestas de longitud media**, variando por sitio y hora del día. **WUE en sitio 0,010–1,630 L/kWh** (Georgia 0,060, Washington 0,950); **EWIF fuera de sitio 1,3–9,5 L/kWh**.
*Key figures:* WUE en sitio **0,010–1,630 L/kWh** (variación de **~163×**); botella de 500 mL por **10–50** respuestas.
*Relevancia Swarmbly:* La variación de 100× en WUE por ubicación es en sí el punto: *dónde* importa más que *cuánto* — relevante para cualquier afirmación de agua de un enjambre distribuido geográficamente.

**[ENV-09] ⚠️ `[SECONDARY]` — Microsoft.** https://www.microsoft.com/en-us/corporate-responsibility/topics/sustainability/report/ · https://sustainabilitymag.com/articles/microsofts-2030-plan-revealed-as-emissions-rise-by-23-4
Reporte 2025: **emisiones +23,4%** contra su línea base de 2020, impulsadas por el despliegue de IA/nube — la cifra "la IA está rompiendo los objetivos climáticos" más citada. Reporte 2026 (FY25): **>14,2 millones de m³** de agua repuesta (excediendo las extracciones), emparejamiento renovable anual del 100%, **92% de tasa de reutilización/reciclaje** de hardware de centro de datos desmantelado en 7 Circular Centers, **>3,2 millones de componentes reutilizados**.
*Key figures:* Emisiones **+23,4%** vs línea base 2020; **92%** reutilización/reciclaje de hardware; **>3,2 M** componentes reutilizados. ⚠️ `[SECONDARY]` la cifra del 23,4% proviene de prensa especializada, no extraída directamente del PDF.
*Relevancia Swarmbly:* El 92% de reutilización/reciclaje de hardware es un dato paralelo directo al argumento de "extender la vida útil del hardware ya fabricado" que Swarmbly puede reclamar para su propia flota de GPUs de consumo.

**[ENV-10] — PUE — Uptime Institute 2025 Global Data Center Survey.** https://mgrid.org/2025/10/01/uptime-institute-data-center-pue-stagnation-2025-liquid-cooling/ · https://datacenters.google/efficiency/
**PUE promedio global: 1,54 — estancado durante seis años consecutivos** (desde 2019). **Hyperscalers: 1,10–1,15.** **Colocación y empresa: 1,58–1,80.** **PUE promedio de la flota de Google (doce meses móviles): 1,09 (2025)**; Google también reporta **>3× más cómputo por unidad de energía que hace cinco años**, en gran parte por TPUs. **El PUE de un hogar es efectivamente ~1,0** (sin enfriadoras, sin pérdidas de conversión de UPS) — la única ventaja estructural *genuina* del cómputo voluntario.
*Key figures:* PUE global **1,54**; hyperscalers **1,10–1,15**; Google **1,09**; hogar **~1,0**.
*Relevancia Swarmbly:* El PUE del hogar de ~1,0 parece una ventaja del 35% sobre el promedio de la industria, pero contra Google (1,09) la ventaja real es de solo ~8% — ver el análisis crítico en `ENV-11`/`ENV-12`.

## 10.2 ¿Es realmente más verde lo distribuido? (evidencia en contra incluida)

**[ENV-11] ⭐ — Benchmark "Watt Counts" de inferencia LLM consciente de energía (arXiv:2604.09048, 10 abril 2026) — contradice la afirmación de que lo distribuido es más verde.** https://arxiv.org/html/2604.09048v1
Midió 10 GPUs NVIDIA, de consumo y de centro de datos, a través de tamaños de modelo y regímenes de lote: **energía por token abarca casi tres órdenes de magnitud: 0,003 J a 1 J** según el emparejamiento GPU-modelo. **La H100 NVL tuvo la menor energía por token en el 90% de los escenarios de lote** (~0,003 J/token para los modelos más grandes); H200 NVL en segundo lugar. **La potencia ociosa domina en escenarios de servidor (baja utilización)**: las GPUs están ociosas a **12–90 W** contra TDPs de **70–700 W**. TFLOPS/W es un mal predictor de la eficiencia energética real.
*Key figures:* Energía por token **0,003–1 J** (casi 3 órdenes de magnitud); H100 NVL menor energía por token en **90%** de escenarios; potencia ociosa **12–90 W** vs TDP **70–700 W**.
*Relevancia Swarmbly:* **Implicación directa para una red P2P:** un nodo voluntario a bajo ciclo de servicio paga potencia ociosa continuamente; si una 4090 está ociosa a ~20–30 W y sirve peticiones solo el 10% del tiempo, el overhead ocioso por sí solo puede superar la energía del trabajo útil — estructuralmente peor que un centro de datos que agrupa hasta alta utilización.

**[ENV-12] ⭐ — GPUs de consumo ociosas vs empresariales para inferencia LLM (ACM AIBC 2025).** https://dl.acm.org/doi/full/10.1145/3775043.3775047 · resumen: https://dcnnmagazine.com/operations/artificial-intelligence/study-finds-consumer-gpus-can-cut-ai-inference-costs/
Estudio directo de exactamente la arquitectura que Swarmbly propone: **clústeres de RTX 4090: $0,111–0,149 por millón de tokens** — el coste más bajo medido; **62%–78% del throughput de una H100 a aproximadamente la mitad del coste operacional**. Sobre carbono: **"las GPUs H100 siguen siendo más eficientes energéticamente por token."** La ruta del artículo hacia menores emisiones totales **no es el cómputo en sí sino extender la vida útil del hardware de consumo ya existente** (amortizando el carbono ya incorporado) y **la ubicación en redes ricas en renovables**.
*Key figures:* **$0,111–0,149** por millón de tokens (RTX 4090); **62–78%** del throughput de H100 a **~mitad** del coste.
*Relevancia Swarmbly:* **Es el artículo directamente más relevante — y dice que el caso más verde descansa en la reutilización de hardware y la mezcla de red, no en la eficiencia del cómputo.** Construir la afirmación de Swarmbly sobre esa base, o no hacerla.

**[ENV-13] ⚠️ `[UNVERIFIED]` — Carbono incorporado de las GPUs.** https://www.sciencedirect.com/science/article/pii/S019592552600199X · https://hyper.ai/en/headlines/3898f05a8718d46b16e19b73db399c28
La propia divulgación de Google (`ENV-05`) sitúa **Scope 3 en 73% de su huella total, creciendo 22%/año** — manufactura y cadena de suministro ahora superan a la electricidad operacional. El LCA de Mistral reporta independientemente **660 kg Sb eq** de depleción de recursos abióticos para el entrenamiento de un modelo, categoría invisible en la contabilidad basada solo en carbono. NVIDIA reporta que la **HGX B200 reduce el carbono incorporado en 24% y las emisiones operacionales en 90%** frente a predecesores.
*Key figures:* Scope 3 **73%** y creciendo **22%/año**; HGX B200 **-24%** carbono incorporado, **-90%** emisiones operacionales. ⚠️ `[UNVERIFIED]` no se pudo recuperar el kg CO₂e por GPU para la A100 — la fuente relevante (*"More than carbon"*, ScienceDirect 2026) bloqueó la extracción automatizada; **obtener este artículo es prioritario, es el núcleo del argumento de reutilización.**
*Relevancia Swarmbly:* Es la base cuantitativa que falta para el único argumento ambiental defendible de Swarmbly (carbono incorporado evitado) — conseguir el LCA de la A100 debería ser tarea prioritaria del proyecto.

> **Síntesis: banderas rojas para la afirmación ambiental de Swarmbly.** Un P2P de inferencia **no** puede afirmar de forma defendible ser más verde por token: Watt Counts (`ENV-11`) y el estudio ACM (`ENV-12`) —el más favorable a esta arquitectura— coinciden en que las GPUs de centro de datos son más eficientes por token. La **potencia ociosa** es el asesino estructural: un nodo voluntario debe permanecer encendido y alcanzable para ser útil, y a ciclos de servicio del 10–20% el consumo ocioso puede superar el trabajo útil. El PUE del hogar (~1,0) solo vence al **promedio de la industria** (1,54); contra Google (1,09) la ventaja es de apenas ~8%. La mezcla de red residencial es una moneda al aire, no una garantía: EE.UU. hyperscale corre en redes 48% más sucias que el promedio nacional (`ENV-03`), pero en Europa un nodo en Polonia será mucho más sucio que un centro de datos en Suecia — sin geo-selección de carga, asumir paridad de red en el mejor caso. Las señales marginales pueden invertir el resultado (`ENV-17`). El "boundary-shopping" (Google 0,26 mL vs Mistral 45 mL de agua por prompt, una brecha de ~170×) es el mayor riesgo reputacional: comprometerse públicamente a SCI for AI/ISO 21031 (`ENV-14`/`ENV-15`), que fuerza a incluir hardware incorporado y prohíbe compensaciones. **Lo que sí se puede afirmar de forma defendible:** carbono incorporado evitado (extender la vida de GPUs ya fabricadas, dado que Scope 3 es 73% de la huella y crece 22%/año), construcción de centro de datos evitada, consumo de agua scope-1 casi nulo (nodos enfriados por aire), y la capacidad —no la propiedad inherente— de enrutar carga a zonas de baja intensidad de carbono en tiempo real.

## 10.3 Software verde y scheduling consciente del carbono

**[ENV-14] ⭐ — Green Software Foundation — el estándar SCI.** https://greensoftware.foundation/standards/sci/ · https://greensoftware.foundation/articles/sci-specification-achieves-iso-standard-status/ · https://sci.greensoftware.foundation/
La especificación **Software Carbon Intensity** es ahora **ISO/IEC 21031:2024**. Define una tasa (carbono por unidad funcional) y críticamente **excluye neutralizaciones y compensaciones**: *"the SCI Specification does not incorporate neutralizations or offsets into its calculations."* SCI = ((E × I) + M) / R — energía operacional × intensidad de red, **más el término incorporado M**, por unidad funcional R.
*Key figures:* Fórmula **SCI = ((E × I) + M) / R**; estándar **ISO/IEC 21031:2024**; excluye explícitamente compensaciones.
*Relevancia Swarmbly:* Es la métrica que Swarmbly debe adoptar para cualquier informe de carbono, precisamente porque prohíbe "resolver" el problema con compensaciones — la disciplina que una afirmación creíble necesita.

**[ENV-15] — SCI for AI.** https://greensoftware.foundation/standards/sci-ai/
Extensión de ISO/IEC 21031 a sistemas de IA. **Ratificada Q4 2025; publicación y aprobación de preparación ISO Q1 2026; envío a ISO Q2 2026.** Cubre cinco fases de ciclo de vida (concepción, diseño/desarrollo donde se acumulan las emisiones de entrenamiento, despliegue, operación/monitoreo es decir inferencia, fin de vida) y ataca explícitamente el modo de fallo donde *"traditional approaches often focus solely on inference costs, missing the significant carbon footprint of training and data preparation."*
*Key figures:* Ratificación **Q4 2025**; 5 fases de ciclo de vida cubiertas.
*Relevancia Swarmbly:* Recomendación directa: **adoptar SCI for AI como el estándar de reporte del protocolo** — es la única metodología en vía ISO que obliga a incluir hardware incorporado y prohíbe compensar el resultado.

**[ENV-16] ⭐ — Scheduling consciente del carbono — y la trampa marginal-vs-promedio.** https://www.electricitymaps.com/resources/publications/optimizing-electricity-consumption-with-a-marginal-signal-may-not-reduce-its-carbon-footprint
Electricity Maps (23 dic 2024) comparó sus factores de emisión **promedio** con trazado de flujo contra los factores **marginales** de WattTime en **65 redes**: **55,4% mostró correlación negativa** entre ambas señales. En un análisis de desplazamiento de carga en 12 redes globales, **la optimización basada en promedio/trazado de flujo redujo las huellas de carbono consistentemente entre 7–50%**, mientras que **la optimización basada en señal marginal falló en reducir emisiones o las incrementó en algunas regiones (Dinamarca, Polonia)**.
*Key figures:* **55,4%** de 65 redes con correlación negativa marginal-vs-promedio; optimización por promedio: **-7% a -50%**; optimización marginal: falla o aumenta emisiones en algunas regiones.
*Relevancia Swarmbly:* **Si Swarmbly construye scheduling consciente del carbono, debe usar intensidad promedio horaria con trazado de flujo, no señales marginales** — de lo contrario puede optimizarse a sí mismo hacia emisiones más altas.

**[ENV-17] ⚠️ `[PARTIAL]` — ¿Funciona realmente el desplazamiento de carga consciente del carbono en equilibrio?** https://arxiv.org/html/2504.07248v1 · véase también https://doi.org/10.3390/su17146433 y https://arxiv.org/html/2508.14625
"Can Carbon-Aware Electric Load Shifting Reduce Emissions? An Equilibrium-Based Analysis" (arXiv:2504.07248, abril 2025) modela consumidores sensibles al carbono con previsión *perfecta* de intensidad de carbono y muestra que su comportamiento de equilibrio difiere materialmente de los modelos secuenciales que todos usan en la práctica — donde las señales solo se conocen *después* de que el mercado se cierra. Probado en un sistema de tres nodos e IEEE RTS-GMLC.
*Key figures:* ⚠️ `[PARTIAL]` no se pudieron extraer las conclusiones numéricas.
*Relevancia Swarmbly:* Marco honesto: **la literatura académica no considera un resultado asentado que "el scheduling consciente del carbono reduce las emisiones"** — Swarmbly no debe presentarlo como garantía, solo como capacidad.

**[ENV-18] — Electricity Maps como capa de datos.** https://www.electricitymaps.com/ · https://carbon-aware-sdk.greensoftware.foundation/docs/overview · https://docs.green-coding.io/docs/measuring/carbon/grid-carbon-intensity/
Intensidad de carbono de la red por hora y por zona, con **trazado de flujo** entre interconectores (importaciones/exportaciones atribuidas por hora en lugar de asumidas domésticas). Es la fuente de datos operacional para el enrutamiento de tareas consciente de zona y para calcular el término "I" en SCI. El **Carbon Aware SDK** de GSF envuelve esto y WattTime detrás de una API web común.
*Key figures:* Trazado de flujo por hora y por zona; API común vía Carbon Aware SDK.
*Relevancia Swarmbly:* Es la capa de datos concreta y ya disponible que Swarmbly necesitaría para implementar el enrutamiento consciente del carbono recomendado en `ENV-16`.

**[ENV-19] ⚠️ `[PARTIAL]` — Calor residual — una ventaja que tienen los centros de datos y los hogares generalmente no.** https://eu-mayors.ec.europa.eu/en/news/stockholm-sweden-heat-recovery-data-centres · https://www.sciencedirect.com/science/article/pii/S0360544223015062 · https://www.sciencedirect.com/science/article/pii/S1364032125005362
La reutilización de calor residual de centros de datos vía calefacción urbana se despliega a escala en mercados nórdicos (programa de recuperación de calor de centros de datos de Estocolmo; estudios daneses a nivel de sistema). El calor residual de un nodo doméstico es útil **solo durante la temporada de calefacción, solo si el hogar se calienta eléctricamente, y es una penalización directa en verano** donde añade carga de aire acondicionado.
*Key figures:* ⚠️ `[PARTIAL]` no se pudieron recuperar porcentajes cuantitativos de recuperación — la revisión de ScienceDirect bloqueó la extracción automatizada.
*Relevancia Swarmbly:* Esta asimetría estacional se omite rutinariamente en las afirmaciones ambientales de cómputo distribuido, y Swarmbly debe reconocerla explícitamente en lugar de ignorarla.

---

# 11. Lagunas de la literatura / Open gaps

Esta sección cierra el documento completo (secciones 1–10) señalando, con la misma honestidad que exige la leyenda de verificación, qué preguntas concretas nadie ha publicado todavía y que Swarmbly necesitaría resolver antes de poder defender su diseño ante un tribunal, un regulador o un revisor técnico exigente.

**Gobernanza y propiedad intelectual.** El desenlace de la apelación del Noveno Circuito en *Neo4j v. Suhy* y, sobre todo, el veredicto del juicio de *SFC v. Vizio* (iniciado el 12 de enero de 2026) siguen sin resolverse — y de ellos depende una pregunta de diseño concreta: ¿necesita la fundación de Swarmbly retener el copyright vía CLA para poder demandar por incumplimiento de AGPL, o pueden los usuarios finales de un protocolo P2P hacerlo como terceros beneficiarios? Nadie ha publicado un análisis legal de cómo la cláusula de "interacción remota en red" de AGPLv3 Section 13 se aplica a una topología verdaderamente descentralizada, donde no hay un único "operador" que ofrezca el servicio — el texto de la licencia asume implícitamente un servidor central.

**Fundación y financiación.** Faltan cifras verificadas para el Dutch Stichting (coste, plazos), para los aranceles administrativos de NumFOCUS y de hospedaje de proyectos de la Linux Foundation, y para la contribución máxima en CHF de Innosuisse — los tres son huecos de investigación reconocidos explícitamente en la fuente. Más profundamente, nadie ha publicado un caso de estudio de una fundación que combine (a) licenciamiento AGPL permanente, (b) un sistema de créditos no transferibles diseñado para escapar de FINMA y MiCA simultáneamente, y (c) gobernanza tipo DAO vía Verein suizo — Swarmbly sería el primer experimento real de esa combinación específica, no la aplicación de un patrón ya probado.

**Ambiental.** El hueco más citado explícitamente en la fuente es el LCA cradle-to-grave de la GPU A100 (ScienceDirect, bloqueado por robots.txt) — sin él, el argumento central de "carbono incorporado evitado" de Swarmbly carece de la cifra de kg CO₂e por GPU que lo haría cuantitativo en lugar de cualitativo. Tampoco existe ningún estudio que mida el ciclo de servicio (duty cycle) real de nodos voluntarios ejecutando específicamente cargas de inferencia LLM — los datos de BOINC (`VOL-04`, `VOL-05`) son de cómputo científico por lotes, no de servir peticiones interactivas bajo demanda, y la brecha entre ambos regímenes de utilización no ha sido medida por nadie. Ninguna publicación cruza los datos de `ENV-11` (potencia ociosa) con los de `VOL-05` (ciclo de servicio efectivo ~61%, vida media de host 91 días) para producir una cifra real de energía-por-token-útil en un enjambre voluntario genuino — Swarmbly tendría que generar esa medición él mismo.

**La laguna transversal más importante.** Ningún trabajo conecta explícitamente los tres pilares de este documento: la verificación de cómputo no confiable (`VER`) exige, según BOINC (`VOL-04`), perfilar hosts a lo largo del tiempo mediante identidades estables para que la replicación adaptativa funcione — pero eso es precisamente lo que la resistencia a Sybil (`VOL-01`) y el diseño de créditos no transferibles (`FND-23`) deben evitar para no reintroducir un ancla de confianza centralizada. Nadie ha publicado un mecanismo que resuelva esta tensión de tres vías (verificación barata, resistencia a Sybil, y créditos que no sean valores regulados) de forma simultánea. Documentar honestamente esta laguna, en lugar de asumir que alguna combinación de las piezas existentes la resuelve, es probablemente la contribución de investigación más original que Swarmbly podría hacer.






