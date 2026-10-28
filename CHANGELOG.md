# Changelog — Swarmbly AI (distribution)

Each component keeps its own changelog: [SwarmblyCore](SwarmblyCore/), [SwarmblyLCE](SwarmblyLCE/), [SwarmblyApp](SwarmblyApp/docs/CHANGELOG.md).

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
