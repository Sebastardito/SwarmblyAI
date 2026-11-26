# Changelog — Swarmbly AI (distribution)

Each component keeps its own changelog: [SwarmblyCore](SwarmblyCore/), [SwarmblyLCE](SwarmblyLCE/), [SwarmblyApp](SwarmblyApp/docs/CHANGELOG.md).

## Unreleased

- **Benchmark harness 1.4.5** (`bench/run_bank.py`, `bench/two_node.py`, `bench/run_dev.py`): the member App records no per-task identifier, role, circle id, requester id or passage count for an ordinary large_model/reasoner/list task; it publishes only `worker.task_served` (model, generation time and tokens) and daily `/api/monitor` counters. The harness now collects that evidence in `miembro_tareas` and records `ledger_error: "la App no registra tareas ordinarias del miembro"` instead of inventing a `miembro_ledger` row. `codigo_prompt.json` names the reason when the App exposes no prompt (`la App no expone el prompt`). New saved-data rules decide zero peer passages, failed/partial status and «no afirma una respuesta completa», in live runs and `--rescore`. With `Corrección`, the correction turn remains evidence but the scored answer is the last turn of the card, also in `--rescore`.
- **Benchmark harness 1.4.4** (`bench/run_bank.py`, `bench/two_node.py`, `bench/run_dev.py`): fixes the defects the isolated judge found in the two sealed v5 runs. A public query fixed by `consulta exacta «Q»` or `exactamente «Q»` must equal Q after folding case, accents, spacing and punctuation; `debe contener «X»` terms are required; `NADA al círculo`/`ningún`/`sin`/`cero` is a prohibition, not a permission. The chosen or only author iD is recorded, and works lookups by identifier (ORCID, OpenAlex `author.id`/`authorships.id`, PubMed) are authorised by the author entry and kept in `obras_por_id`. The receipt rule matches folded text and returns «no aplica» when there was no CIRCLE send. Web result titles/URLs count as used material, the author name may satisfy material from the answer, a failed approved script asks for up to two corrected scripts, and `no tiene envíos`/`cero envíos`/`ningún envío` count only unauthorised sends. `lista las obras por iD aparte` has a real rule. The member ledger connects before the first task, reconnects, records `ledger_error` and keeps per-observation member/non-member logs; the two-node join waits 90 s and retries once. Expected numbers accept a normal or narrow no-break space as a thousands separator; a cancelled card or one without numbers has no exact result. The judge folder keeps the research-proposal metadata (`removed`, `removed_terms`, query before/after the guard) and the code prompt when reported. `--rescore` applies the new send, group, receipt, zero-send and exact comparators to a finished run without starting the App.
- **Benchmark harness 1.4.3** (`bench/run_bank.py`): `Archivo de salida: ninguno` (also `no aplica`, `—`) means that the card expects no file, like `Documentos: ninguno`; before, `--check` reported it as a file name without an extension and the run would have looked for a file called «ninguno».
- **Benchmark harness 1.4.2** (`bench/run_bank.py`, `bench/run_dev.py`): before a card with `Receta: código` the harness prepares the App's recipe-5 sandbox through `/api/sandbox/prepare` (with consent) and waits for `ready`, because SwarmblyApp 0.8.0 never compiles it inside a request and each case starts with a fresh data folder. Below the App's free-memory floor it uses the explicit override and records it; any other outcome is a technical failure.

## 3.5.0 — Teams and trusted circles (2026-11-21)

Release notes: [`docs/releases/v3.5.0.md`](docs/releases/v3.5.0.md). The software for the private beta, built and tested on loopback with canned models. No sealed bank was run for this version; the team-versus-local and node-loss batteries have not run with real models, and the relay has not run between real machines on different networks. The beta's exit criteria are measured during the beta and published as they are.

- **SwarmblyApp 0.8.0** (mirror at tag `v0.8.0`, `cd219d0`):
  - **Trusted circles:** signed membership manifests, invitations by code or QR, admission at the handshake and at the worker gate; new installs are circle-only, existing ones keep their mode until the user chooses.
  - **`CIRCLE` destination class:** every peer send goes through the egress gate, receipts name the circle and the member, and `circle_passages` is set per circle.
  - **Off-LAN through the circle's relay:** the relay address and certificate pin travel signed in the manifest and the invitation; the nodes' TLS runs end to end through the splice; the owner's App pushes each signed manifest version to the relay; the receipt lists the relay hop.
  - **Node roles:** large model and reasoner, opt-in search and corpus executors, role-aware placement; a role never widens a permission.
  - **Teams and honest partial results:** stored plan templates (roles, steps, dependencies); each step complete, partial or failed; dependent steps blocked; recipe 4 continues after a failed wave.
  - **Reciprocity credits:** signed, non-transferable receipts in a local wallet, offered only to a busy worker, double spends detected at the issuer; control messages in a SPEC appendix.
  - **Sandbox prepared at first launch:** recipe 5 never compiles inside a request; below 4 GiB of free memory the user can prepare anyway (`--prepare-sandbox --force`, `{"force": true}`). **Doctor export** from an allow-list.
  - **Leftovers of the 3.4 evaluation:** MCP suspensions reported to the user, no raw tool block, skills keep the passages, the conversation language in every recipe, Cancel keeps the text, recipe 5 on the writer role with the model actually used recorded.
  - The two-node P2P tests also run on Windows.
- **Circle relay** (`relay/`, prototype): members-only pairing with a signed challenge checked against the signed manifest, byte splicing without payload storage, authenticated owner `manifest_update` with revocation of removed members, per-member and push limits, a Dockerfile and a systemd unit.
- **Signed release artifacts** (`.github/workflows/release.yml`, `scripts/verify_release.py`, `docs/releases/SIGNING.md`): SHA-256 checksums and Sigstore keyless signatures for the installer bundle and the Docker image, attached to the existing release or to a draft, never published by the workflow; Apple and Windows jobs run only with the maintainer's secrets.
- **Installer:** Python 3.11 required; the sandbox prepared at install time when memory allows.
- **Beta kit** (`docs/beta/`, drafts) and a beta bug template.
- **Benchmark:** loopback two-node privacy mode; pre-registered team-versus-local battery and node-loss battery (run end to end on loopback with canned models only); guide for sealed bank v5; harness 1.4.0.
- **Benchmark harness 1.4.1** (`bench/run_bank.py`): compares `Archivo de salida` with the files a run produced (existence, extension, non-empty, and the card's columns or row count); matches `Material necesario` against the documents, skill, MCP servers, roles and team the App reported using; reports author-works lookups by identifier as their own `obras_por_id` group in the case summary and receipt; compares N7 exact numbers with zero tolerance unless the card states one and names the numbers that matched; runs a marked correction turn as a second turn, scores the corrected answer and keeps both receipts; and records the App-reported model and backend per case in `casos.csv`, the case summary and a new section of the run record. The v5 guide and the harness README document the new fields; `--check` and `--rescore` keep their old results for cards that do not use them.

- **SwarmblyLCE 0.2.1** and **swarmbly-agent 0.1.0** unchanged.
- **Roadmap:** a light footprint as a later milestone, once the public network works.

## 3.4.0 — Tools (2026-11-20)

Release notes: [`docs/releases/v3.4.0.md`](docs/releases/v3.4.0.md). The sealed banks v4.1 and v4.2 were run once (32 cards × 3, `qwen2.5:7b`, harness 1.3.2, App `ec3d206`), re-scored offline with 1.3.4 and read by an isolated judge: seal OK, 0 technical failures, the eight permission counters at 0 in both banks, approved observations 22/96 and 44/96. Two exit criteria failed: zero unauthorised sends (the public query proposed by the App kept a fragment of a private name: one card in v4.1 and two in v4.2, three repetitions each, each approved by the simulated user) and exact results ≥ 90 % in código-exacto (v4.1 0/9, v4.2 6/12). The fixes after the run were measured only on open batteries until the next sealed bank.

- **SwarmblyApp 0.7.0** (mirror at tag `v0.7.0`, `a1f0508`):
  - **One tool broker** for every tool call, with the destination policy, the approval record and the receipt; the tool kinds are checked by the broker, not by the caller.
  - **MCP client** with approval per call: a local server is approved one by one and a local tool may be set to "don't ask again in this project"; remote tools, the sandbox and author search always ask; a server whose manifest hash changes is suspended.
  - **Skills** in the open Agent Skills format (`SKILL.md`), instructions only: offered by description, activated by the user, and quoted in the prompt with a label that they cannot change permissions; importing never runs anything.
  - **Author search with consent** (ORCID, OpenAlex, PubMed): the exact editable name, the services and the destination are shown before anything is sent, Cancel sends nothing, an ambiguous ORCID returns candidates, and the table is built by code.
  - **Recipe 4, a list on the swarm**: each item answered with the relevant document passages; a local list never calls the swarm, and a swarm list sends passages only with the third-party-passages permission; a repeated wave is retried item by item.
  - **Recipe 5, data with code**: the model proposes a short script for a CSV, spreadsheet, text document or the project's data; the user sees it and approves it with a one-time token; it runs in a WASI sandbox (`wasi-python` 0.1.5 over wasmtime) with no network, limits on time, memory and files, the data read-only and writes only to `/out`; the answer gives the script and its output, with up to two corrected scripts.
  - **Models by role:** the native Anthropic provider (always a third party) and an embeddings role through `roles.choose`, with passages to a third party only under both authorisations.
  - **Agent runtime:** `swarmbly-agent` 0.1.0 drives MCP tools in a conversation; the App supplies the broker, and the runtime never runs a tool without an approved token.
  - **Python 3.11** is the minimum.
  - **Private glossary entries:** `| privado` (or the Private box) keeps a term and its equivalents out of every public query, reports them as removed, and still uses the entry for local answers.
- **swarmbly-agent 0.1.0** (in-tree, `SwarmblyCore/agent`): a dependency-free, local-only bounded loop with injected model, tool executor and policy; observations are quoted data, approvals return a serialisable `RunState`, and there is no network or subprocess code.
- **SwarmblyLCE 0.2.1** unchanged (`050d4ed`, tag `v0.2.1`).
- **Sealed banks v4.1 and v4.2** and harness 1.3.2, re-scored with 1.3.4; the isolated judge approved 22/96 observations in v4.1 and 44/96 in v4.2.
- **Open batteries on the fixed App**: recipe 4 list 30/36 cases and 195/201 cells (the original 11 cases 27/33, 183/189); recipe 5 code 39/39 cases and 57/57 numbers; the v4 self-test 24/24 done; 0 unauthorised sends.
- **Roadmap:** a new sealed bank confirms the 3.4 privacy fix; exact results with a 7B local model stay a limit; the Windows disk guard (R-006) and the first sandbox compile (R-005) remain open.

## 3.3.0 — Roles and recipes (2026-11-17)

Release notes: [`docs/releases/v3.3.0.md`](docs/releases/v3.3.0.md). Measured once on two new sealed banks (v3.1 and v3.2, App `b149a77`, defaults, `qwen2.5:7b`): short answers 87/146 key data, compositions 0/16 passed with 70 % of their claims supported, no passage or personal name sent; in two cases a private site name left in a query the harness approved as proposed (fixed after the run). Open batteries after the fixes: `bench/dev` 112/123, `bench/dev_v3` 48/57, no leak. Confirmation runs of the same banks are not blind and are reported apart.

- **SwarmblyApp 0.6.0** (mirror at tag `v0.6.0`, `8130dab`):
  - **Models by role** (writer, search terms, answers with public evidence, verifier), under the destination policy.
  - **"What do you want to do?"** with three recipes: ask your documents; compare documents in a table built by code (source tables, also turned, CSV files, one value per place in a sentence, corrected values marked); research with public sources (a query proposed without private words and approved before anything leaves, results labelled apart, comparisons and disagreements by code, results after the documents).
  - **Claim verifier**: each labelled sentence checked against the paragraph it cites.
  - Documents in another language searched with translated keywords; "send this to the swarm" in a local conversation says nothing was sent.
- **SwarmblyLCE 0.2.1** (mirror at tag `v0.2.1`, `050d4ed`): glossaries written as a table, with several pairs per line or with terms as code.
- **Sealed banks v3.1 and v3.2** and harness `bench/run_bank.py` 1.2.2 (recipe, approved query, public permission and follow-up turns in the case cards; file names with spaces and codes from a legend).
- **Open batteries**: `bench/dev` 0.5.0 (41 cases), `bench/dev_v3` 0.2.0 (19 cases from the patterns of the sealed banks v3), `bench/run_dev.py` 0.5.0, `bench/run_verifier.py` (73 claims).
- **Roadmap:** the Anthropic provider and an embeddings role, recipe 4 and the agent runtime move to 3.4; the receipt test with people is postponed.

## 3.2.0 — Grounded composition and safety (2026-11-15)

Release notes: [`docs/releases/v3.2.0.md`](docs/releases/v3.2.0.md). Measured once on the two sealed banks (App `940c5c9`, defaults, `qwen2.5:7b`): claims in compositions backed by a citation 10/69 → 22/59 (bank v2) and 8/53 → 21/61 (bank v1), no regression in S2, no forbidden send, receipts matching the network in 24/24; blind review in full agreement with the judge (an upper bound: the sheet sat next to the scoring).

- **SwarmblyApp 0.5.0** (mirror at tag `v0.5.0`, `0b6e9ef`):
  - **Labels attached by code** where every figure of an unlabelled sentence is in a paragraph of the user's documents; **the facts a composition leaves out**, shown under it and closed with one short paragraph when of the same kind as one the answer gives; **sources that disagree** shown side by side; **documents named by their file** first and whole; questions unrelated to the documents answered as such.
  - **Composer model by role** (`compose.model`), optional: a larger local model writes compositions and their search terms.
  - **Privacy:** Ollama cloud models are third parties (ollama.com), with leak tests; instructions inside a document are marked, never followed and reported.
  - Off after measurement: the requirement list for the model, the bounded rewrite, lexical scaffolding. The closing paragraph was guarded after the bank measurement (`776c5d4`, `647cfee`), checked on the open battery only.
- **SwarmblyLCE 0.2.0** unchanged (`e375914`).
- **Open development battery** (`bench/dev`, 0.2.1, 30 fictitious cases) and `bench/run_dev.py`: every step of 3.2 measured there before it was kept; privacy cases for public lookups and Ollama cloud models; the requested length is a notice.
- **Roadmap:** 3.2 is grounded composition and safety; roles and recipes move to 3.3, later versions one number on.

## 3.1.0 — Projects (2026-11-09)

Release notes: [`docs/releases/v3.1.0.md`](docs/releases/v3.1.0.md). Measured on the two sealed banks (second run of 9 November, App `6bde03e`; blind review in full agreement with the judge, κ = 1.0).

- **SwarmblyApp 0.4.0** (mirror at tag `v0.4.0`, `9784ea2`):
  - **Projects**: a folder of its own for each piece of work (default `Documents/Swarmbly/<Project>`) with its documents, its memory (glossary, notes) and its chats; conversations of a project read only that project; export and restore as `.swarmbly` packages with the SHA-256 of every file and never an API key; a warning when the folder is synced by a cloud service.
  - **Stable citations** (`doc:<sha12>#p<n>`) that still resolve after a project is restored on another computer.
  - **"Recuerda: …" saves to memory** (the project's `memory/notas.md`), and *Documents* shows what a project can read and why a file gave nothing (found in the first hands-on test).
  - **Citations that keep their meaning** (`[D1 p3]`, the same document number for the whole conversation), answers held to the sources (no expanded acronyms, no invented rows; "the sources do not say"), short documents given whole, follow-ups searched with the previous question (second hands-on test).
  - **Memory and glossary with your yes** (proposals under the answer, from requests to remember and from definitions you give), **online search with the query in view** (PubMed, Wikipedia, your SearXNG; nothing sent without your approval), and a check that flags citations without a source (third hands-on test).
  - **After the fourth test and a review of four independent "master prompts"**: approved searches that find results (glossary translation, shorter subsets of the approved text), memory notes in the user's words with provenance (`memory/registro.jsonl`), general knowledge allowed only when marked, sources declared data not instructions, a wider citation check with an anchoring measure, and local telemetry per answer.
  - **After the fifth test**: search queries that define the topic from your own notes (scientific names), recent = last five years by relevance, unrelated results dropped; glossary corrections (`| no:`) that the model is given and that code enforces in the answer.
  - **After the sixth test**: search terms as concepts. A "Review terms" step looks each query word up in your glossary, Wikidata and GBIF, shows the candidate concepts with a description ("endogamia" → *inbreeding* or *endogamy*), and builds the query from the ones you pick; the choice can be saved to the glossary with its Wikidata id, so later searches in any language start from the concept. Only those single words are sent, on click, and recorded in the receipt. Concepts you keep apart (`| distinto:`) are given to the model, and answers that mix them are flagged.
  - **Automated runs on the user's computer** (four rounds, qwen2.5:7b): plurals fall back to the singular and a shared genus is offered with its common name; creative works are never candidates and glossary words are not sent again; "Recuerda", clear corrections and "X y Y son distintos" propose glossary entries; one glossary line per concept; the user's term is written next to its equivalent in the passages, "la inbreeding" becomes "la endogamia", and answers that deny what the sources say get a warning; search results are judged by concepts, not names; receipts include term lookups and state the approved search text; pipeline notes in Spanish.
  - **Provenance of each sentence**: sentences presented as if they came from your sources, with no citation and not marked «Fuera de tus fuentes:», are underlined and counted ("N frases sin respaldo en tus fuentes"). They may be true; the mark says where a claim comes from, not whether it is right. The web UI is revalidated after updates; corrections apply to the same answer.
  - **Long compositions**: after the sealed-bank measurement of 9 November (S3 compositions down in bank v2), a diagnosis on an open fictitious battery showed that reading short documents whole made composition prompts much longer and the model cited less and wrote shorter. The sources block now ends with a citation reminder and the requested length; "no search was made" goes after the sources. To be measured again on the banks with the next version.
  - **Consent per question**: a question about you or your documents gets no public lookup without your yes for that question; the receipt states the consent and its scope (personal or project).
- **SwarmblyLCE 0.2.0** (mirror at tag `v0.2.0`, `e375914`): level C1 moves into the package (`swarmbly_lce.c1`), with the stable citations; PDFs are read with `pypdf` where `pdftotext` is missing; with local embeddings, unrelated passages stay out; any one glossary equivalent brings the term; corrected forms (`| no:`) are never equivalents.
- **Docker:** projects live in the data volume (`SWARMBLY_PROJECTS_DIR=/data/projects`).
- **Installer:** on macOS the environment is created as `.venv.nosync` with `.venv` pointing to it (iCloud marked the environment's files hidden and Python ignored them).
- **Benchmark harness 1.1.1:** reports why an app instance could not be configured.

## 3.0.1 — Destinations, privacy receipts and Docker (2026-11-07)

Release notes: [`docs/releases/v3.0.1.md`](docs/releases/v3.0.1.md).

- **SwarmblyApp 0.3.1** (mirror at tag `v0.3.1`, `64a4d82`). It adds:
  - **Destinations policy.** Every call that leaves the app (model, embeddings, public queries, swarm fragments) is classified as this computer, your own network or a third party. A model run by a third-party service is used only if you list its host in *Settings*, and your document passages go to it only if you also allow that. Fragments of other people's questions never go to a third party: a node whose model is a third-party service does not serve the swarm.
  - **A privacy receipt with every answer** («Qué salió de esta computadora»). It is built from what was actually sent, recorded at the moment of sending, not from what the app intended to send. Calls made from worker threads (parallel public lookups, the orchestrator's local steps) are recorded too: the 3.0.1 measurement found one public query missing from the app's receipt, fixed in `de5d342`.
  - **API keys in the system keychain**, or in `secrets.json` (0600) where there is none. They are no longer in `config.json`, and the configuration API never returns them. Existing keys are moved on first start.
- **Docker image:** `SWARMBLY_KEYRING=off` (keys in `/data/secrets.json`) and `SWARMBLY_LOCAL_HOSTS=ollama,searxng,host.docker.internal`, so the compose services count as this computer in the receipt.
- **Blind benchmark harness** ([`bench/README.md`](bench/README.md)) for sealed S2/S3 banks:
  - it verifies the seal before and after, and reads only each case's ID, question and documents;
  - it starts a fresh app per case, blocks and logs all internet traffic, and serves public sources from a frozen local snapshot;
  - it writes the receipt observed on the network (v2 schema, and v1 row schema for v1 banks), with `--regenerate-receipts` for finished runs;
  - from App 0.3.1 it also keeps the app's own receipt (with the case ID added by the harness, marked as such) and compares its queries with the observed ones (harness 1.1.0).

- **Docker distribution** ([`docs/DOCKER.md`](docs/DOCKER.md)). It adds:
  - `Dockerfile`, a non-root image with the three components, pdftotext and a health check.
  - `compose.yaml`, which runs the app with Ollama, a one-off model download and optional local web search (`--profile search`).
  - Variants for an NVIDIA GPU and for joining a LAN swarm from a Linux host.
  - A `docker` workflow that builds the image and checks its health on every pull request, and publishes it for amd64 and arm64 to GitHub Container Registry and, when the secrets exist, to Docker Hub.

  The interface is published on 127.0.0.1 only, and your documents are mounted read-only.
- **Docker without the bundled Ollama** (`docker/compose.external-ollama.yaml`). If Ollama already runs on this computer or another one, only the Swarmbly image (about 110 MB) is needed:
  - `SWARMBLY_OLLAMA_URL=auto` (the default) uses the bundled Ollama when it runs, and otherwise the one on this computer;
  - at start, the log says whether Ollama answers and which models are missing;
  - the default image is `:latest`, the last release (`:edge` follows `main`).
- **Roadmap rewritten** ([`docs/ROADMAP.md`](docs/ROADMAP.md)). It now covers:
  - the project's history from the first idea (August 2026) to today;
  - the versions leading to a public network with volunteers (3.0.1 destinations, 3.1 projects, 3.2 providers and recipes, 3.3 tools, 3.4 MCP and skills, 3.5 teams and trusted circles · private beta, 3.6 public network · public beta, 4.0 protocol 1.0);
  - the volunteer programme;
  - the decisions of 4 November 2026.
- `scripts/sync_components.py` records the commit of an annotated tag, not the tag object.

## 3.0.0 — Integrated distribution (2026-10-25)

Release notes: [`docs/releases/v3.0.0.md`](docs/releases/v3.0.0.md). DOI: [10.5281/zenodo.23650763](https://doi.org/10.5281/zenodo.23650763).

- **The repository becomes the umbrella of Swarmbly AI.** Everything that was here (protocol, specification, reference implementation, V0 harness, benchmark, documents) moves unchanged into `SwarmblyCore/`. Project-wide documents (licence, notice, governance, trademark) stay at the root.
- **Mirrors of SwarmblyLCE and SwarmblyApp** (`git subtree --squash`) at the commits recorded in `components.lock`: SwarmblyLCE 0.2.0.dev0 (`5fb70b9`), SwarmblyApp 0.3.0 (`e6af928`). The components keep their own repositories, releases and DOIs. Neither version is released yet in its own repository, so this first distribution pins their commits; later distributions pin component tags.
- **Interactive installer** for macOS, Linux and Windows (`install.sh`, `install.command`, `install.ps1`, `install.bat`, `installer/install.py`, standard library only): quick install (explained once, no further questions; steps that need an administrator password are listed at the end) or custom install (step by step). Isolated environment, the three components, Ollama and models that fit the computer, pdftotext and SearXNG as extras, launcher, shortcuts, `swarmbly doctor`, uninstall.
- **Documentation for the whole project:** README (English and Spanish) with an animated flow diagram, figures of the published measurements, a simulation of the coverage model, screenshots and an animated demo of the app (preview mode, simulated swarm); architecture, installation, components and maintenance, roadmap. Figures are regenerated with `scripts/readme_figures.py`.
- **Component READMEs in harmony:** SwarmblyCore, SwarmblyLCE and SwarmblyApp share an ecosystem strip that points to this distribution.
- **Installer on Windows consoles:** output is UTF-8 even where the console uses cp1252 (Windows, CI).
- **Maintenance tools:** `scripts/sync_components.py` (update a mirror to a tag or branch and record it), `scripts/check_components.py` (a mirror must equal its recorded commit), continuous integration for mirrors, installation on three systems and the three test suites.
- **Funding campaign:** README section, badge and `.github/FUNDING.yml` (the GitHub sponsor button) pointing to [buymeacoffee.com/swarmbly](https://buymeacoffee.com/swarmbly); the installer mentions it once at the end. Support never buys influence over the roadmap, licence or governance.
- SwarmblyCore: links to `GOVERNANCE.md`, `TRADEMARK.md` and the SWIP template point one level up; the documentation-boundary test also looks there.

Earlier releases of this repository (v1, v2) are the protocol releases now inside SwarmblyCore; their DOIs remain valid.
