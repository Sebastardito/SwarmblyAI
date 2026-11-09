# Changelog — Swarmbly AI (distribution)

Each component keeps its own changelog: [SwarmblyCore](SwarmblyCore/), [SwarmblyLCE](SwarmblyLCE/), [SwarmblyApp](SwarmblyApp/docs/CHANGELOG.md).

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
  - the versions leading to a public network with volunteers (3.0.1 destinations, 3.1 projects, 3.2 providers and recipes, 3.3 tools, 3.4 trusted circles and private beta, 3.5 public beta, 4.0 protocol 1.0);
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
